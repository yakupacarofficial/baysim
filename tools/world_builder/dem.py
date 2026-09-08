"""`world_builder dem crop` — DEM'i düzenli ENU ızgarasına yeniden örnekler.

Neden lat/lon ızgarası değil de ENU ızgarası?
Godot sahnesi metre tabanlı yerel ENU'dur ve pist geometrisi de aynı çerçevede
üretilir. Tile'ı doğrudan düzenli bir ENU ızgarasına örneklersek çalışma
zamanında düğüm başına trigonometri gerekmez: `x = x0 + i*step`,
`z = z0 + j*step`, `y = height[j][i]`. Arazi ile pist otomatik olarak aynı
çerçevede olur ve mesh kurulumu tamamen doğrusal bir okuma hâline gelir.

Yükseklikler yeryüzü eğriliğini içerir: her düğüm için önce yatay konum
jeodezik koordinata çevrilir, DEM oradan örneklenir, sonra (lat, lon, h_msl)
ileri yönde ENU'ya döndürülüp `up` bileşeni yazılır. 15 km'de bu, düz teğet
düzlemine göre yaklaşık 18 metrelik farkı doğru şekilde hesaba katar.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from .geodesy import WGS84_A_M, WGS84_E_SQ, GeoReference
from .geotiff import GeoTiff
from .manifests import AirportPack, sha256_of

TERRAIN_FORMAT_VERSION = 1
GENERATOR = "tools/world_builder dem crop"


# --- Vektörleştirilmiş jeodezi ------------------------------------------
# geodesy.py skaler referanstır ve `scripts/geo_reference.gd` ile sözleşmeyi
# paylaşır. Aşağıdaki numpy sürümleri onunla birebir aynı formülü uygular;
# tests/test_dem.py iki yolun aynı sonucu verdiğini doğrular.


def _geodetic_to_ecef_np(
    lat_deg: np.ndarray, lon_deg: np.ndarray, alt_m: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    n = WGS84_A_M / np.sqrt(1.0 - WGS84_E_SQ * sin_lat * sin_lat)
    return (
        (n + alt_m) * cos_lat * np.cos(lon),
        (n + alt_m) * cos_lat * np.sin(lon),
        (n * (1.0 - WGS84_E_SQ) + alt_m) * sin_lat,
    )


def _ecef_to_geodetic_np(
    x: np.ndarray, y: np.ndarray, z: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a = WGS84_A_M
    e_sq = WGS84_E_SQ
    b = a * math.sqrt(1.0 - e_sq)
    e_prime_sq = e_sq / (1.0 - e_sq)

    p = np.hypot(x, y)
    theta = np.arctan2(z * a, p * b)
    lat = np.arctan2(
        z + e_prime_sq * b * np.sin(theta) ** 3,
        p - e_sq * a * np.cos(theta) ** 3,
    )
    lon = np.arctan2(y, x)
    sin_lat = np.sin(lat)
    n = a / np.sqrt(1.0 - e_sq * sin_lat * sin_lat)
    alt = p / np.cos(lat) - n
    return np.degrees(lat), np.degrees(lon), alt


def _rotation(reference: GeoReference) -> tuple[float, float, float, float]:
    lat0 = math.radians(reference.lat_deg)
    lon0 = math.radians(reference.lon_deg)
    return math.sin(lat0), math.cos(lat0), math.sin(lon0), math.cos(lon0)


def enu_to_geodetic_np(
    reference: GeoReference,
    east: np.ndarray,
    north: np.ndarray,
    up: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sin_lat, cos_lat, sin_lon, cos_lon = _rotation(reference)
    dx = -sin_lon * east - sin_lat * cos_lon * north + cos_lat * cos_lon * up
    dy = cos_lon * east - sin_lat * sin_lon * north + cos_lat * sin_lon * up
    dz = cos_lat * north + sin_lat * up

    ox, oy, oz = _geodetic_to_ecef_np(
        np.float64(reference.lat_deg),
        np.float64(reference.lon_deg),
        np.float64(reference.alt_msl_m),
    )
    return _ecef_to_geodetic_np(ox + dx, oy + dy, oz + dz)


def geodetic_to_enu_np(
    reference: GeoReference,
    lat_deg: np.ndarray,
    lon_deg: np.ndarray,
    alt_msl_m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sin_lat, cos_lat, sin_lon, cos_lon = _rotation(reference)
    ox, oy, oz = _geodetic_to_ecef_np(
        np.float64(reference.lat_deg),
        np.float64(reference.lon_deg),
        np.float64(reference.alt_msl_m),
    )
    px, py, pz = _geodetic_to_ecef_np(lat_deg, lon_deg, alt_msl_m)
    dx, dy, dz = px - ox, py - oy, pz - oz

    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
    return east, north, up


def sample_bilinear_np(
    dem: GeoTiff, lat: np.ndarray, lon: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Dizi hâlinde çift doğrusal örnekleme. (değerler, kapsam_maskesi) döndürür."""
    offset_x, offset_y = dem._half_pixel_offset  # noqa: SLF001 — aynı paket
    fi = (lon - dem._tie_lon - offset_x) / dem.pixel_size_x  # noqa: SLF001
    fj = (dem._tie_lat - offset_y - lat) / dem.pixel_size_y  # noqa: SLF001

    # Tam kenardaki bir örnek, derece aritmetiğinin yuvarlama hatası yüzünden
    # bir pikselin milyonda biri kadar dışarı düşebilir. Maske gerçek kapsam
    # boşluklarını yakalamalı, bu gürültüyü değil.
    edge_tolerance = 1e-6
    inside = (
        (fi >= -edge_tolerance)
        & (fi <= dem.width - 1 + edge_tolerance)
        & (fj >= -edge_tolerance)
        & (fj <= dem.height - 1 + edge_tolerance)
    )
    fi = np.clip(fi, 0.0, dem.width - 1.0000001)
    fj = np.clip(fj, 0.0, dem.height - 1.0000001)

    i0 = np.floor(fi).astype(np.int64)
    j0 = np.floor(fj).astype(np.int64)
    i1 = np.minimum(i0 + 1, dem.width - 1)
    j1 = np.minimum(j0 + 1, dem.height - 1)
    tx = (fi - i0).astype(np.float64)
    ty = (fj - j0).astype(np.float64)

    data = dem.data
    top = data[j0, i0] * (1.0 - tx) + data[j0, i1] * tx
    bottom = data[j1, i0] * (1.0 - tx) + data[j1, i1] * tx
    return top * (1.0 - ty) + bottom * ty, inside


# --- Tile üretimi --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunwaySurface:
    """Pistin ENU düzlemindeki iki ucu ve genişliği."""

    runway_id: str
    start_east_m: float
    start_north_m: float
    start_up_m: float
    end_east_m: float
    end_north_m: float
    end_up_m: float
    width_m: float


def runway_surfaces(pack: AirportPack) -> list[RunwaySurface]:
    """Manifestteki pistleri ortak ENU çerçevesine taşır."""
    reference = pack.geo_reference
    surfaces: list[RunwaySurface] = []
    for runway in pack.runways.get("runways", []):
        designators = runway.get("designators", [])
        if len(designators) != 2:
            continue
        thresholds = runway.get("thresholds", {})
        start = thresholds.get(str(designators[0]))
        end = thresholds.get(str(designators[1]))
        if not start or not end:
            continue
        se, sn, su = reference.to_enu(
            float(start["lat_deg"]),
            float(start["lon_deg"]),
            float(start["elevation_msl_m"]),
        )
        ee, en, eu = reference.to_enu(
            float(end["lat_deg"]),
            float(end["lon_deg"]),
            float(end["elevation_msl_m"]),
        )
        surfaces.append(
            RunwaySurface(
                runway_id=str(runway.get("id", "?")),
                start_east_m=se, start_north_m=sn, start_up_m=su,
                end_east_m=ee, end_north_m=en, end_up_m=eu,
                width_m=float(runway.get("width_m", 0.0)),
            )
        )
    return surfaces


def stitch_runway(
    heights: np.ndarray,
    east: np.ndarray,
    north: np.ndarray,
    runway: RunwaySurface,
    shoulder_m: float,
    blend_m: float,
    depress_m: float = 0.15,
) -> np.ndarray:
    """Pist çevresini pist düzlemine oturtur ve araziye yumuşakça bağlar.

    Pist gövdesi ve omzu pist yüzeyinin `depress_m` kadar altına indirilir;
    omuzdan sonraki `blend_m` genişliğinde bir kuşakta smoothstep ile DEM'e
    döner.

    Depresyon şart: arazi ile pist mesh'i tam olarak aynı düzleme düşerse
    derinlik tamponu ikisi arasında karar veremez ve pist, araziyle
    dikiş dikiş kırpışır (z-fighting). Birkaç santimlik fark hem bunu
    tamamen kaldırır hem fiziksel olarak doğrudur: pist, tesviye edilmiş
    zeminin üstüne dökülen bir kaplamadır.
    """
    ax, az = runway.start_east_m, runway.start_north_m
    bx, bz = runway.end_east_m, runway.end_north_m
    dx, dz = bx - ax, bz - az
    length_sq = dx * dx + dz * dz
    if length_sq <= 0.0 or runway.width_m <= 0.0:
        return heights

    # Her düğümün pist ekseni üzerindeki izdüşümü
    t = ((east - ax) * dx + (north - az) * dz) / length_sq
    t = np.clip(t, 0.0, 1.0)
    closest_east = ax + t * dx
    closest_north = az + t * dz
    distance = np.hypot(east - closest_east, north - closest_north)

    surface_height = (
        runway.start_up_m + t * (runway.end_up_m - runway.start_up_m) - depress_m
    )

    flat_radius = runway.width_m * 0.5 + shoulder_m
    blend_radius = flat_radius + blend_m

    # 0 = tamamen pist, 1 = tamamen arazi
    if blend_m > 0.0:
        weight = np.clip((distance - flat_radius) / blend_m, 0.0, 1.0)
    else:
        weight = (distance > flat_radius).astype(np.float64)
    smooth = weight * weight * (3.0 - 2.0 * weight)  # smoothstep

    affected = distance <= blend_radius
    blended = surface_height * (1.0 - smooth) + heights * smooth
    return np.where(affected, blended, heights)


@dataclass(slots=True)
class TerrainTile:
    tile_id: str
    heights: np.ndarray  # (height, width) float32, satır sırası kuzey→güney
    radius_m: float
    step_m: float
    reference: GeoReference
    outside_count: int
    water_count: int
    source_min_msl_m: float
    source_max_msl_m: float
    stitched_runways: list[str]
    shoulder_m: float
    blend_m: float
    depress_m: float

    @property
    def width(self) -> int:
        return int(self.heights.shape[1])

    @property
    def height(self) -> int:
        return int(self.heights.shape[0])


def build_tile(
    dem: GeoTiff,
    reference: GeoReference,
    radius_m: float,
    step_m: float,
    tile_id: str,
    runways: list[RunwaySurface] | None = None,
    shoulder_m: float = 60.0,
    blend_m: float = 240.0,
    depress_m: float = 0.15,
) -> TerrainTile:
    """DEM'i orijin çevresinde ±radius_m ENU karesine yeniden örnekler."""
    if radius_m <= 0.0 or step_m <= 0.0:
        raise ValueError("radius_m ve step_m pozitif olmalı")
    if not reference.is_valid():
        raise ValueError("Geçersiz dünya orijini")

    samples = int(round(2.0 * radius_m / step_m)) + 1
    east_axis = np.linspace(-radius_m, radius_m, samples, dtype=np.float64)
    north_axis = np.linspace(radius_m, -radius_m, samples, dtype=np.float64)
    east, north = np.meshgrid(east_axis, north_axis)
    zero = np.zeros_like(east)

    # 1) Izgara düğümünün yatay jeodezik konumu
    lat, lon, _ = enu_to_geodetic_np(reference, east, north, zero)
    # 2) DEM'den MSL yüksekliği
    elevation, inside = sample_bilinear_np(dem, lat, lon)
    # 3) İleri dönüşüm; `up` eğrilik düzeltmesini de içerir
    _, _, up = geodetic_to_enu_np(reference, lat, lon, elevation)

    # Su, kaynak DEM'de tam 0.0 m MSL olarak kodlanır. Bu ancak ENU/eğrilik
    # dönüşümünden ÖNCE, ham örnek üzerinde anlamlıdır.
    water_count = int((elevation == 0.0).sum())
    source_min = float(elevation.min())
    source_max = float(elevation.max())

    # 4) Pist çevresini pist düzlemine dik
    stitched: list[str] = []
    for runway in runways or []:
        up = stitch_runway(
            up, east, north, runway, shoulder_m, blend_m, depress_m
        )
        stitched.append(runway.runway_id)

    return TerrainTile(
        tile_id=tile_id,
        heights=up.astype(np.float32),
        radius_m=radius_m,
        step_m=step_m,
        reference=reference,
        outside_count=int((~inside).sum()),
        water_count=water_count,
        source_min_msl_m=source_min,
        source_max_msl_m=source_max,
        stitched_runways=stitched,
        shoulder_m=shoulder_m,
        blend_m=blend_m,
        depress_m=depress_m,
    )


def _load_existing_manifest(path: Path, world_id: str) -> dict[str, Any]:
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                return existing
        except json.JSONDecodeError:
            pass
    return {"format_version": TERRAIN_FORMAT_VERSION, "world_id": world_id}


def write_tile(
    tile: TerrainTile,
    pack: AirportPack,
    source_entry: dict[str, Any],
    terrain_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Tile'ı `.f32` + `manifest.json` olarak yazar. (veri, manifest) döndürür."""
    directory = terrain_dir or (pack.directory / "terrain")
    directory.mkdir(parents=True, exist_ok=True)

    data_path = directory / f"{tile.tile_id}.f32"
    # Little-endian float32, satır sırası kuzey→güney, sütun sırası batı→doğu.
    tile.heights.astype("<f4").tofile(data_path)

    manifest_path = directory / "manifest.json"
    # Manifest paylasilir: `imagery crop` da ayni dosyaya yazar. Ezmek yerine
    # yalnizca kendi bolumumuzu guncelleriz.
    manifest = _load_existing_manifest(manifest_path, pack.world_id)
    manifest.update({
        "format_version": TERRAIN_FORMAT_VERSION,
        "world_id": pack.world_id,
        "generated_at": date.today().isoformat(),
        "generator": GENERATOR,
        "source_id": source_entry.get("source_id"),
        "source_sha256": source_entry.get("sha256"),
        "attribution": source_entry.get("attribution"),
        "tiles": [
            {
                "tile_id": tile.tile_id,
                "file": data_path.name,
                "sha256": sha256_of(data_path),
                "size_bytes": data_path.stat().st_size,
                "width": tile.width,
                "height": tile.height,
                "sample_format": "float32_le",
                "row_order": "north_to_south",
                "column_order": "west_to_east",
                "grid": {
                    "space": "local_enu_metres",
                    "step_m": tile.step_m,
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
                "height_reference": (
                    "Local ENU 'up' relative to the world origin, earth curvature "
                    "included. Add origin.alt_msl_m to recover MSL elevation."
                ),
                "vertical_datum": source_entry.get("vertical_datum", {}).get(
                    "measured", "unknown"
                ),
                "enu_up_min_m": float(tile.heights.min()),
                "enu_up_max_m": float(tile.heights.max()),
                "source_msl_min_m": tile.source_min_msl_m,
                "source_msl_max_m": tile.source_max_msl_m,
                "runway_stitching": {
                    "runways": tile.stitched_runways,
                    "shoulder_m": tile.shoulder_m,
                    "blend_m": tile.blend_m,
                    "depress_m": tile.depress_m,
                    "note": (
                        "Grid nodes within half-width + shoulder of a runway "
                        "centreline are forced onto the runway surface plane "
                        "lowered by depress_m, then smoothstepped back to the "
                        "DEM across blend_m. The depression keeps the runway "
                        "mesh strictly above the terrain so the two cannot "
                        "z-fight."
                    ),
                },
                "water_cells": tile.water_count,
                "water_note": (
                    "Cells where the source DEM reads exactly 0.0 m MSL, which "
                    "Copernicus DEM uses for sea surface. Counted before the ENU "
                    "and curvature transform, where the value is still meaningful."
                ),
                "samples_outside_source": tile.outside_count,
            }
        ],
    })

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return data_path, manifest_path
