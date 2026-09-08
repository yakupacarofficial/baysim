"""geotiff.py testleri — sentetik ama gerçek GeoTIFF dosyalarıyla."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from ..geotiff import (
    RASTER_PIXEL_IS_AREA,
    RASTER_PIXEL_IS_POINT,
    GeoTiff,
    GeoTiffError,
    is_lfs_pointer,
)
from .helpers import write_geotiff


class GeoTiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.directory = Path(self._temp.name)
        self.addCleanup(self._temp.cleanup)
        # 4 sutun x 3 satir, 0.01 derece piksel, (0,0) merkezi 10E 50N
        self.data = np.array(
            [
                [10.0, 11.0, 12.0, 13.0],
                [20.0, 21.0, 22.0, 23.0],
                [30.0, 31.0, 32.0, 33.0],
            ],
            dtype=np.float32,
        )
        self.path = write_geotiff(
            self.directory / "grid.tif", self.data, west=10.0, north=50.0,
            pixel_size=0.01,
        )

    def open(self, path: Path) -> GeoTiff:
        tiff = GeoTiff(path)
        self.addCleanup(tiff.close)
        return tiff

    def test_reads_header(self) -> None:
        tiff = self.open(self.path)
        self.assertEqual((tiff.width, tiff.height), (4, 3))
        self.assertEqual(tiff.epsg, 4326)
        self.assertEqual(tiff.raster_type, RASTER_PIXEL_IS_POINT)
        self.assertAlmostEqual(tiff.pixel_size_x, 0.01)

    def test_pixel_centre_round_trip(self) -> None:
        tiff = self.open(self.path)
        for i in range(tiff.width):
            for j in range(tiff.height):
                lat, lon = tiff.pixel_center(i, j)
                self.assertEqual(tiff.index_of(lat, lon), (i, j))

    def test_bounds_cover_pixel_centres(self) -> None:
        tiff = self.open(self.path)
        bounds = tiff.bounds
        self.assertAlmostEqual(bounds.west, 10.0)
        self.assertAlmostEqual(bounds.east, 10.0 + 3 * 0.01)
        self.assertAlmostEqual(bounds.north, 50.0)
        self.assertAlmostEqual(bounds.south, 50.0 - 2 * 0.01)
        self.assertTrue(bounds.contains(49.995, 10.015))
        self.assertFalse(bounds.contains(49.5, 10.015))

    def test_nearest_sampling(self) -> None:
        tiff = self.open(self.path)
        self.assertAlmostEqual(tiff.sample_nearest(50.0, 10.0), 10.0)
        self.assertAlmostEqual(tiff.sample_nearest(49.98, 10.03), 33.0)
        with self.assertRaises(ValueError):
            tiff.sample_nearest(0.0, 0.0)

    def test_bilinear_midpoint_is_average(self) -> None:
        tiff = self.open(self.path)
        # (0,0)=10, (1,0)=11, (0,1)=20, (1,1)=21 pikselinin tam ortasi
        value = tiff.sample_bilinear(50.0 - 0.005, 10.0 + 0.005)
        self.assertAlmostEqual(value, (10.0 + 11.0 + 20.0 + 21.0) / 4.0, places=4)

    def test_pixel_is_area_offsets_by_half_pixel(self) -> None:
        area_path = write_geotiff(
            self.directory / "area.tif", self.data, west=10.0, north=50.0,
            pixel_size=0.01, raster_type=RASTER_PIXEL_IS_AREA,
        )
        area = self.open(area_path)
        self.assertEqual(area.raster_type, RASTER_PIXEL_IS_AREA)
        lat, lon = area.pixel_center(0, 0)
        # Tiepoint kose oldugu icin ilk pikselin merkezi yarim piksel iceride
        self.assertAlmostEqual(lon, 10.005)
        self.assertAlmostEqual(lat, 49.995)

    def test_window_returns_requested_region(self) -> None:
        tiff = self.open(self.path)
        patch, bounds = tiff.window(
            south=50.0 - 0.011, north=50.0 - 0.009,
            west=10.0 + 0.009, east=10.0 + 0.021,
        )
        self.assertEqual(patch.shape, (1, 2))
        np.testing.assert_allclose(patch, [[21.0, 22.0]])
        self.assertAlmostEqual(bounds.west, 10.01)

    def test_window_outside_extent_raises(self) -> None:
        tiff = self.open(self.path)
        with self.assertRaises(ValueError):
            tiff.window(south=0.0, north=0.1, west=0.0, east=0.1)

    def test_rejects_non_4326(self) -> None:
        path = write_geotiff(
            self.directory / "utm.tif", self.data, west=10.0, north=50.0,
            pixel_size=0.01, epsg=32635,
        )
        with self.assertRaises(GeoTiffError):
            GeoTiff(path)

    def test_rejects_ungeoreferenced_tiff(self) -> None:
        plain = self.directory / "plain.tif"
        from PIL import Image

        Image.fromarray(self.data).save(plain)
        with self.assertRaises(GeoTiffError):
            GeoTiff(plain)


class LfsPointerTests(unittest.TestCase):
    def test_detects_pointer_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pointer = Path(directory) / "big.tif"
            pointer.write_text(
                "version https://git-lfs.github.com/spec/v1\n"
                "oid sha256:0000\nsize 1\n",
                encoding="utf-8",
            )
            self.assertTrue(is_lfs_pointer(pointer))
            with self.assertRaises(GeoTiffError):
                GeoTiff(pointer)

    def test_missing_file_is_not_pointer(self) -> None:
        self.assertFalse(is_lfs_pointer(Path("yok-boyle-bir-dosya.tif")))


if __name__ == "__main__":
    unittest.main()
