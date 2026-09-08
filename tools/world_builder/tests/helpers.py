"""Testler için sentetik GeoTIFF ve AirportPack üreticileri."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import PIL.TiffTags as TiffTags
from PIL import Image
from PIL.TiffImagePlugin import ImageFileDirectory_v2

from ..geotiff import RASTER_PIXEL_IS_POINT


def write_geotiff(
    path: Path,
    data: np.ndarray,
    west: float,
    north: float,
    pixel_size: float,
    raster_type: int = RASTER_PIXEL_IS_POINT,
    epsg: int = 4326,
) -> Path:
    """Verilen diziyi coğrafi referanslı bir GeoTIFF olarak yazar.

    `west`/`north`, raster_type'a göre (0,0) pikselinin merkezini ya da sol üst
    köşesini işaretler — GeoTIFF tiepoint semantiğiyle aynıdır.
    """
    ifd = ImageFileDirectory_v2()
    ifd.tagtype[33550] = TiffTags.DOUBLE
    ifd.tagtype[33922] = TiffTags.DOUBLE
    ifd.tagtype[34735] = TiffTags.SHORT
    ifd[33550] = (pixel_size, pixel_size, 0.0)
    ifd[33922] = (0.0, 0.0, 0.0, west, north, 0.0)
    ifd[34735] = (
        1, 1, 0, 3,
        1024, 0, 1, 2,            # GTModelType = geographic
        1025, 0, 1, raster_type,  # GTRasterType
        2048, 0, 1, epsg,         # GeographicType
    )
    Image.fromarray(np.asarray(data, dtype=np.float32)).save(path, tiffinfo=ifd)
    return path


def write_pack(
    directory: Path,
    *,
    world: dict | None = None,
    runways: dict | None = None,
    sources: dict | None = None,
) -> Path:
    """`worlds/TEST/` biçiminde minimal ama geçerli bir paket yazar."""
    directory.mkdir(parents=True, exist_ok=True)
    default_world = {
        "format_version": 1,
        "world_id": directory.name,
        "airport_icao": directory.name,
        "name": "Test",
        "origin": {
            "lat_deg": 41.0,
            "lon_deg": 28.0,
            "alt_msl_m": 100.0,
            "horizontal_datum": "WGS84",
            "vertical_datum": "TEST_MSL",
        },
        "bounds": {"radius_m": 1000.0},
        "runways_file": "runways.json",
        "sources_file": "sources.json",
        "render": {"flatten_runways_until_dem": True},
    }
    default_runways = {
        "format_version": 1,
        "world_id": directory.name,
        "runways": [
            {
                "id": "09/27",
                "designators": ["09", "27"],
                "declared_length_m": 1000.0,
                "width_m": 45.0,
                "surface": "concrete",
                "thresholds": {
                    "09": {
                        "lat_deg": 41.0,
                        "lon_deg": 27.994038,
                        "elevation_msl_m": 100.0,
                    },
                    "27": {
                        "lat_deg": 41.0,
                        "lon_deg": 28.005962,
                        "elevation_msl_m": 100.0,
                    },
                },
            }
        ],
    }
    default_sources = {
        "format_version": 1,
        "world_id": directory.name,
        "retrieved_at": "2026-01-01",
        "sources": [
            {
                "source_id": "test_reference",
                "provider": "Test",
                "license_status": "Public Domain",
                "usage": ["test"],
            }
        ],
    }

    (directory / "world.json").write_text(
        json.dumps(world if world is not None else default_world), encoding="utf-8"
    )
    (directory / "runways.json").write_text(
        json.dumps(runways if runways is not None else default_runways),
        encoding="utf-8",
    )
    (directory / "sources.json").write_text(
        json.dumps(sources if sources is not None else default_sources),
        encoding="utf-8",
    )
    return directory
