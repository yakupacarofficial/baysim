"""Coğrafi referanslı GeoTIFF okuma — yalnızca numpy ve Pillow ile.

GDAL/rasterio bilerek kullanılmaz. LTBU kaynağı zaten EPSG:4326 float32'dir;
yeniden projeksiyon gerekmediği için TIFF etiketlerini doğrudan okumak hem
bağımlılığı sıfırlar hem CI'da ek kurulum istemez. Farklı bir CRS veya
sıkıştırma gerektiğinde bu modül genişletilir ya da GDAL'a geçilir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# TIFF etiket numaralari
_TAG_MODEL_PIXEL_SCALE = 33550
_TAG_MODEL_TIEPOINT = 33922
_TAG_MODEL_TRANSFORM = 34264
_TAG_GEO_KEY_DIRECTORY = 34735
_TAG_GDAL_NODATA = 42113

# GeoKey numaralari
_KEY_RASTER_TYPE = 1025
_KEY_GEOGRAPHIC_TYPE = 2048

RASTER_PIXEL_IS_AREA = 1
RASTER_PIXEL_IS_POINT = 2

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


class GeoTiffError(RuntimeError):
    """GeoTIFF okunamadığında veya desteklenmeyen bir yapı taşıdığında."""


def is_lfs_pointer(path: Path) -> bool:
    """Dosya, indirilmemiş bir Git LFS pointer'ı mı?"""
    try:
        with path.open("rb") as handle:
            return handle.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX
    except OSError:
        return False


@dataclass(frozen=True, slots=True)
class Bounds:
    west: float
    east: float
    south: float
    north: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.west <= lon <= self.east and self.south <= lat <= self.north


class GeoTiff:
    """EPSG:4326 tabanlı, eksen hizalı bir yükseklik rasterı."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if is_lfs_pointer(self.path):
            raise GeoTiffError(
                f"{self.path} indirilmemiş bir Git LFS pointer'ı. "
                "`git lfs pull` çalıştırın."
            )

        self._image = Image.open(self.path)
        self.width, self.height = self._image.size
        tags = self._image.tag_v2

        if tags.get(_TAG_MODEL_TRANSFORM) is not None:
            raise GeoTiffError(
                "ModelTransformationTag taşıyan (döndürülmüş/eğik) raster "
                "desteklenmiyor; yalnızca eksen hizalı raster okunur."
            )

        pixel_scale = tags.get(_TAG_MODEL_PIXEL_SCALE)
        tiepoint = tags.get(_TAG_MODEL_TIEPOINT)
        if not pixel_scale or not tiepoint:
            raise GeoTiffError(
                "ModelPixelScale veya ModelTiepoint etiketi yok; dosya "
                "coğrafi referanslı bir GeoTIFF değil."
            )

        self.pixel_size_x = float(pixel_scale[0])
        self.pixel_size_y = float(pixel_scale[1])
        if self.pixel_size_x <= 0.0 or self.pixel_size_y <= 0.0:
            raise GeoTiffError("Piksel boyutu pozitif olmalı")

        tie_i, tie_j = float(tiepoint[0]), float(tiepoint[1])
        self._tie_lon, self._tie_lat = float(tiepoint[3]), float(tiepoint[4])
        # Tiepoint her zaman (0,0) pikselini isaretlemeyebilir.
        self._tie_lon -= tie_i * self.pixel_size_x
        self._tie_lat += tie_j * self.pixel_size_y

        self.geo_keys = self._parse_geo_keys(tags.get(_TAG_GEO_KEY_DIRECTORY))
        self.raster_type = self.geo_keys.get(_KEY_RASTER_TYPE, RASTER_PIXEL_IS_AREA)
        self.epsg = self.geo_keys.get(_KEY_GEOGRAPHIC_TYPE)
        if self.epsg is not None and self.epsg != 4326:
            raise GeoTiffError(
                f"Yalnızca EPSG:4326 destekleniyor, dosya EPSG:{self.epsg} bildiriyor."
            )

        nodata_raw = tags.get(_TAG_GDAL_NODATA)
        self.nodata: float | None = None
        if nodata_raw is not None:
            try:
                self.nodata = float(str(nodata_raw).strip().strip("\x00"))
            except ValueError:
                self.nodata = None

        self._data: np.ndarray | None = None

    def close(self) -> None:
        """Altındaki dosya tanıtıcısını serbest bırakır."""
        image, self._image = getattr(self, "_image", None), None
        if image is not None:
            image.close()

    def __enter__(self) -> "GeoTiff":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # noqa: BLE001 — yıkım sırasında sessiz kal
            pass

    @staticmethod
    def _parse_geo_keys(directory) -> dict[int, int]:
        """GeoKeyDirectory'den yalnızca satır içi (short) anahtarları alır."""
        keys: dict[int, int] = {}
        if not directory:
            return keys
        values = list(directory)
        for index in range(4, len(values) - 3, 4):
            key_id, location, _count, value = values[index : index + 4]
            if location == 0:
                keys[int(key_id)] = int(value)
        return keys

    @property
    def data(self) -> np.ndarray:
        """Raster verisi (ilk erişimde okunur).

        Tek bantlı yükseklik rasterları float32'ye çevrilir. Çok bantlı
        görüntüler (RGB ortofoto) kendi dtype'ında bırakılır: 3000×3000'lik
        bir RGB'yi float32'ye çevirmek 27 MB yerine 108 MB tutardı.
        """
        if self._data is None:
            if self._image is None:
                raise GeoTiffError(
                    "Raster kapatıldı ve verisi hiç okunmamıştı; yeniden açın."
                )
            array = np.asarray(self._image)
            if array.ndim == 2:
                array = array.astype(np.float32)
            elif array.ndim != 3:
                raise GeoTiffError(
                    f"2 veya 3 boyutlu raster bekleniyordu, {array.ndim} bulundu."
                )
            self._data = array
        return self._data

    @property
    def band_count(self) -> int:
        return 1 if self.data.ndim == 2 else int(self.data.shape[2])

    def require_single_band(self) -> np.ndarray:
        if self.band_count != 1:
            raise GeoTiffError(
                f"Bu işlem tek bantlı raster gerektirir, "
                f"{self.path.name} {self.band_count} bant taşıyor."
            )
        return self.data

    # --- Coğrafi ↔ piksel dönüşümü -------------------------------------

    @property
    def _half_pixel_offset(self) -> tuple[float, float]:
        """PixelIsArea rasterında tiepoint köşeyi, PixelIsPoint'te merkezi gösterir."""
        if self.raster_type == RASTER_PIXEL_IS_POINT:
            return 0.0, 0.0
        return self.pixel_size_x * 0.5, self.pixel_size_y * 0.5

    def pixel_center(self, i: int, j: int) -> tuple[float, float]:
        """(i, j) pikselinin merkezinin (lat, lon) değeri."""
        offset_x, offset_y = self._half_pixel_offset
        lon = self._tie_lon + offset_x + i * self.pixel_size_x
        lat = self._tie_lat - offset_y - j * self.pixel_size_y
        return lat, lon

    def index_of(self, lat: float, lon: float) -> tuple[int, int]:
        """(lat, lon)'a en yakın piksel indeksi (i, j). Kırpılmaz."""
        offset_x, offset_y = self._half_pixel_offset
        i = (lon - self._tie_lon - offset_x) / self.pixel_size_x
        j = (self._tie_lat - offset_y - lat) / self.pixel_size_y
        return int(round(i)), int(round(j))

    @property
    def bounds(self) -> Bounds:
        """Piksel merkezlerinin kapsadığı sınırlar."""
        # pixel_center(i, j) -> (lat, lon)
        south_lat, west_lon = self.pixel_center(0, self.height - 1)
        north_lat, east_lon = self.pixel_center(self.width - 1, 0)
        return Bounds(west=west_lon, east=east_lon, south=south_lat, north=north_lat)

    # --- Örnekleme -----------------------------------------------------

    def sample_nearest(self, lat: float, lon: float) -> float:
        """En yakın piksel değeri. Kapsam dışında ValueError."""
        self.require_single_band()
        i, j = self.index_of(lat, lon)
        if not (0 <= i < self.width and 0 <= j < self.height):
            raise ValueError(
                f"({lat:.6f}, {lon:.6f}) raster kapsamı dışında (i={i}, j={j})"
            )
        return float(self.data[j, i])

    def sample_bilinear(self, lat: float, lon: float) -> float:
        """Dört komşudan ağırlıklı örnek; arazi profili için daha yumuşak."""
        self.require_single_band()
        offset_x, offset_y = self._half_pixel_offset
        fi = (lon - self._tie_lon - offset_x) / self.pixel_size_x
        fj = (self._tie_lat - offset_y - lat) / self.pixel_size_y
        i0, j0 = math.floor(fi), math.floor(fj)
        if not (0 <= i0 < self.width - 1 and 0 <= j0 < self.height - 1):
            return self.sample_nearest(lat, lon)
        tx, ty = fi - i0, fj - j0
        block = self.data[j0 : j0 + 2, i0 : i0 + 2]
        top = block[0, 0] * (1.0 - tx) + block[0, 1] * tx
        bottom = block[1, 0] * (1.0 - tx) + block[1, 1] * tx
        return float(top * (1.0 - ty) + bottom * ty)

    def window(
        self,
        south: float,
        north: float,
        west: float,
        east: float,
    ) -> tuple[np.ndarray, Bounds]:
        """Verilen sınırları kapsayan en küçük piksel penceresini döndürür."""
        i_west, j_north = self.index_of(north, west)
        i_east, j_south = self.index_of(south, east)
        i0, i1 = max(0, min(i_west, i_east)), min(self.width - 1, max(i_west, i_east))
        j0, j1 = max(0, min(j_north, j_south)), min(self.height - 1, max(j_north, j_south))
        if i0 > i1 or j0 > j1:
            raise ValueError("İstenen pencere raster kapsamıyla kesişmiyor")

        patch = self.require_single_band()[j0 : j1 + 1, i0 : i1 + 1].copy()
        # pixel_center(i, j) -> (lat, lon)
        north_lat, west_lon = self.pixel_center(i0, j0)
        south_lat, east_lon = self.pixel_center(i1, j1)
        return patch, Bounds(
            west=west_lon, east=east_lon, south=south_lat, north=north_lat
        )
