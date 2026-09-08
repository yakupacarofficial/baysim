"""`world_builder imagery crop` — ortofotoyu arazinin ENU ızgarasına giydirir.

Görüntü, yükseklik tile'ıyla **aynı** ENU karesine yeniden örneklenir. Böylece
Godot tarafında doku koordinatı sadece normalize konumdur: arazi düğümünün
tile içindeki oranı doğrudan UV olur, projeksiyon düzeltmesi ya da shader
hesabı gerekmez.

Doku çözünürlüğü geometriden bağımsızdır. Arazi 30 m ızgarada dursa bile
görüntü 10 m'de kalabilir; UV normalize olduğu için ikisi birbirini bağlamaz.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .dem import enu_to_geodetic_np
from .geodesy import GeoReference
from .geotiff import GeoTiff, GeoTiffError
from .manifests import AirportPack, sha256_of

# Bellek profilini makul tutmak icin cikti satir satir uretilir.
ROW_CHUNK = 256
JPEG_QUALITY = 92


@dataclass(slots=True)
class ImageryTile:
    tile_id: str
    pixels: np.ndarray  # (height, width, 3) uint8
    radius_m: float
    pixel_m: float
    reference: GeoReference
    outside_count: int

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])


def _to_uint8_rgb(data: np.ndarray) -> np.ndarray:
    """Kaynağı 8-bit RGB'ye indirger.

    Copernicus 'True Color' ürünü 8-bit gelebildiği gibi 16-bit yansıma
    değerleri de verebilir. 16-bit gelirse sabit bir bölme yerine yüzdelik
    germe uygulanır; sabit ölçek koyu ya da yanmış bir görüntü üretirdi.
    """
    if data.ndim != 3 or data.shape[2] < 3:
        raise GeoTiffError(
            f"RGB görüntü bekleniyordu, şekil {data.shape} bulundu."
        )
    rgb = data[:, :, :3]
    if rgb.dtype == np.uint8:
        return np.ascontiguousarray(rgb)

    sample = rgb[::8, ::8].astype(np.float32)
    low = float(np.percentile(sample, 1.0))
    high = float(np.percentile(sample, 99.0))
    if high <= low:
        high = low + 1.0
    stretched = (rgb.astype(np.float32) - low) * (255.0 / (high - low))
    return np.clip(stretched, 0.0, 255.0).astype(np.uint8)


def build_imagery_tile(
    source: GeoTiff,
    reference: GeoReference,
    radius_m: float,
    pixel_m: float,
    tile_id: str,
) -> ImageryTile:
    """Ortofotoyu orijin çevresinde ±radius_m ENU karesine yeniden örnekler."""
    if radius_m <= 0.0 or pixel_m <= 0.0:
        raise ValueError("radius_m ve pixel_m pozitif olmalı")
    if not reference.is_valid():
        raise ValueError("Geçersiz dünya orijini")

    rgb = _to_uint8_rgb(source.data)
    source_height, source_width = rgb.shape[0], rgb.shape[1]

    samples = int(round(2.0 * radius_m / pixel_m)) + 1
    east_axis = np.linspace(-radius_m, radius_m, samples, dtype=np.float64)
    output = np.zeros((samples, samples, 3), dtype=np.uint8)
    outside_count = 0

    offset_x, offset_y = source._half_pixel_offset  # noqa: SLF001 — aynı paket

    for start in range(0, samples, ROW_CHUNK):
        stop = min(start + ROW_CHUNK, samples)
        north_axis = radius_m - np.arange(start, stop, dtype=np.float64) * (
            2.0 * radius_m / (samples - 1)
        )
        east, north = np.meshgrid(east_axis, north_axis)
        lat, lon, _ = enu_to_geodetic_np(
            reference, east, north, np.zeros_like(east)
        )

        fi = (lon - source._tie_lon - offset_x) / source.pixel_size_x  # noqa: SLF001
        fj = (source._tie_lat - offset_y - lat) / source.pixel_size_y  # noqa: SLF001

        inside = (
            (fi >= -1e-6) & (fi <= source_width - 1 + 1e-6)
            & (fj >= -1e-6) & (fj <= source_height - 1 + 1e-6)
        )
        outside_count += int((~inside).sum())

        fi = np.clip(fi, 0.0, source_width - 1.0000001)
        fj = np.clip(fj, 0.0, source_height - 1.0000001)
        i0 = fi.astype(np.int32)
        j0 = fj.astype(np.int32)
        i1 = np.minimum(i0 + 1, source_width - 1)
        j1 = np.minimum(j0 + 1, source_height - 1)
        tx = (fi - i0)[..., None]
        ty = (fj - j0)[..., None]

        top = rgb[j0, i0] * (1.0 - tx) + rgb[j0, i1] * tx
        bottom = rgb[j1, i0] * (1.0 - tx) + rgb[j1, i1] * tx
        output[start:stop] = np.clip(
            top * (1.0 - ty) + bottom * ty, 0.0, 255.0
        ).astype(np.uint8)

    return ImageryTile(
        tile_id=tile_id,
        pixels=output,
        radius_m=radius_m,
        pixel_m=pixel_m,
        reference=reference,
        outside_count=outside_count,
    )


def write_imagery(
    tile: ImageryTile,
    pack: AirportPack,
    source_entry: dict[str, Any],
    terrain_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Ortofotoyu JPEG olarak yazar ve arazi manifestine ekler."""
    directory = terrain_dir or (pack.directory / "terrain")
    directory.mkdir(parents=True, exist_ok=True)

    # JPEG secildi: 3000x3000 RGB, PNG olarak ~20 MB, JPEG kalite 92'de ~3 MB.
    # Arazi dokusunda kayipsizligin gorsel karsiligi yok, depo boyutunun var.
    image_path = directory / f"{tile.tile_id}.jpg"
    Image.fromarray(tile.pixels, mode="RGB").save(
        image_path, format="JPEG", quality=JPEG_QUALITY, optimize=True
    )

    manifest_path = directory / "manifest.json"
    manifest = _load_manifest(manifest_path, pack.world_id)
    manifest["imagery"] = {
        "tile_id": tile.tile_id,
        "file": image_path.name,
        "sha256": sha256_of(image_path),
        "size_bytes": image_path.stat().st_size,
        "width": tile.width,
        "height": tile.height,
        "pixel_m": tile.pixel_m,
        "generated_at": date.today().isoformat(),
        "source_id": source_entry.get("source_id"),
        "source_sha256": source_entry.get("sha256"),
        "attribution": source_entry.get("attribution"),
        "grid": {
            "space": "local_enu_metres",
            "radius_m": tile.radius_m,
            "east_min_m": -tile.radius_m,
            "east_max_m": tile.radius_m,
            "north_min_m": -tile.radius_m,
            "north_max_m": tile.radius_m,
        },
        "origin": {
            "lat_deg": tile.reference.lat_deg,
            "lon_deg": tile.reference.lon_deg,
            "alt_msl_m": tile.reference.alt_msl_m,
        },
        "uv_mapping": (
            "Normalised tile position: u = (east + radius) / (2 * radius), "
            "v = (radius - north) / (2 * radius). Pixel centres sit half a "
            "texel from the node positions, which is under one pixel of "
            "offset and is not corrected."
        ),
        "samples_outside_source": tile.outside_count,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return image_path, manifest_path


def _load_manifest(path: Path, world_id: str) -> dict[str, Any]:
    """Var olan manifesti okur; yoksa iskelet döndürür.

    Birleştirme şart: `dem crop` ve `imagery crop` aynı manifeste yazar ve
    biri diğerinin bölümünü silmemelidir.
    """
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                return existing
        except json.JSONDecodeError:
            pass
    return {"format_version": 1, "world_id": world_id, "tiles": []}
