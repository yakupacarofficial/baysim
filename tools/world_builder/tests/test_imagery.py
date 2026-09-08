"""imagery.py testleri — sentetik RGB GeoTIFF üzerinde."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from ..dem import build_tile, write_tile
from ..geotiff import GeoTiff, GeoTiffError
from ..imagery import _to_uint8_rgb, build_imagery_tile, write_imagery
from ..manifests import load_pack
from .helpers import write_geotiff, write_pack


def _write_rgb_geotiff(path: Path, data: np.ndarray, west: float, north: float,
                       pixel_size: float) -> Path:
    """helpers.write_geotiff tek bantlıdır; burada RGB yazıyoruz."""
    import PIL.TiffTags as TiffTags
    from PIL.TiffImagePlugin import ImageFileDirectory_v2

    ifd = ImageFileDirectory_v2()
    ifd.tagtype[33550] = TiffTags.DOUBLE
    ifd.tagtype[33922] = TiffTags.DOUBLE
    ifd.tagtype[34735] = TiffTags.SHORT
    ifd[33550] = (pixel_size, pixel_size, 0.0)
    ifd[33922] = (0.0, 0.0, 0.0, west, north, 0.0)
    ifd[34735] = (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 2, 2048, 0, 1, 4326)
    Image.fromarray(data, mode="RGB").save(path, tiffinfo=ifd)
    return path


class ToUint8Tests(unittest.TestCase):
    def test_uint8_passes_through(self) -> None:
        data = np.zeros((4, 4, 3), dtype=np.uint8)
        data[1, 1] = (10, 20, 30)
        result = _to_uint8_rgb(data)
        self.assertEqual(result.dtype, np.uint8)
        np.testing.assert_array_equal(result, data)

    def test_extra_bands_are_dropped(self) -> None:
        rgba = np.zeros((4, 4, 4), dtype=np.uint8)
        self.assertEqual(_to_uint8_rgb(rgba).shape, (4, 4, 3))

    def test_sixteen_bit_is_percentile_stretched(self) -> None:
        """Sentinel yansıma değerleri 16-bit gelebilir; sabit bölme yanlış olur."""
        data = np.linspace(1000, 5000, 32 * 32 * 3, dtype=np.uint16)
        data = data.reshape(32, 32, 3)
        result = _to_uint8_rgb(data)
        self.assertEqual(result.dtype, np.uint8)
        # Germe sonrasi tum aralik kullanilmali, karanlik kalmamali
        self.assertLess(int(result.min()), 20)
        self.assertGreater(int(result.max()), 235)

    def test_single_band_is_rejected(self) -> None:
        with self.assertRaises(GeoTiffError):
            _to_uint8_rgb(np.zeros((4, 4), dtype=np.uint8))


class BuildImageryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        write_pack(self.root / "TEST")
        self.pack = load_pack("TEST", worlds_dir=self.root)
        self.reference = self.pack.geo_reference

    def source(self, data: np.ndarray, pixel_size: float = 0.002) -> GeoTiff:
        path = _write_rgb_geotiff(
            self.root / "ortho.tif", data, west=27.9, north=41.1,
            pixel_size=pixel_size,
        )
        tiff = GeoTiff(path)
        self.addCleanup(tiff.close)
        return tiff

    def test_grid_shape_follows_radius_and_pixel(self) -> None:
        source = self.source(np.zeros((200, 200, 3), dtype=np.uint8))
        tile = build_imagery_tile(
            source, self.reference, radius_m=500.0, pixel_m=10.0, tile_id="t"
        )
        self.assertEqual(tile.width, 101)
        self.assertEqual(tile.height, 101)

    def test_uniform_colour_survives_resampling(self) -> None:
        data = np.zeros((200, 200, 3), dtype=np.uint8)
        data[:, :] = (12, 200, 64)
        tile = build_imagery_tile(
            self.source(data), self.reference, radius_m=500.0, pixel_m=25.0,
            tile_id="t",
        )
        np.testing.assert_array_equal(
            tile.pixels[tile.height // 2, tile.width // 2], (12, 200, 64)
        )
        self.assertEqual(tile.outside_count, 0)

    def test_north_south_orientation_is_preserved(self) -> None:
        """Çıktının ilk satırı kuzeye bakmalı; ters çevrilirse harita aynalanır."""
        # Renk siniri tam DUNYA ORIJININDE olmali. Kaynak west=27.9,
        # north=41.1, piksel 0.002 derece; orijin (41.0, 28.0) kaynagin
        # (50, 50) pikseline denk gelir. Ortadan bolersek tile'in tamami
        # tek renkte kalir ve test hicbir sey olcmez.
        data = np.zeros((200, 200, 3), dtype=np.uint8)
        data[:50, :] = (255, 0, 0)   # orijinin kuzeyi kirmizi
        data[50:, :] = (0, 0, 255)   # guneyi mavi
        tile = build_imagery_tile(
            self.source(data), self.reference, radius_m=1000.0, pixel_m=25.0,
            tile_id="t",
        )
        self.assertGreater(int(tile.pixels[0, tile.width // 2][0]), 200)
        self.assertGreater(int(tile.pixels[-1, tile.width // 2][2]), 200)

    def test_east_west_orientation_is_preserved(self) -> None:
        data = np.zeros((200, 200, 3), dtype=np.uint8)
        data[:, :50] = (255, 0, 0)   # orijinin batisi kirmizi
        data[:, 50:] = (0, 0, 255)   # dogusu mavi
        tile = build_imagery_tile(
            self.source(data), self.reference, radius_m=1000.0, pixel_m=25.0,
            tile_id="t",
        )
        self.assertGreater(int(tile.pixels[tile.height // 2, 0][0]), 200)
        self.assertGreater(int(tile.pixels[tile.height // 2, -1][2]), 200)

    def test_samples_outside_source_are_reported(self) -> None:
        # Kucuk bir kaynak, cok buyuk bir tile istegi
        source = self.source(np.zeros((20, 20, 3), dtype=np.uint8), pixel_size=0.0005)
        tile = build_imagery_tile(
            source, self.reference, radius_m=5000.0, pixel_m=100.0, tile_id="t"
        )
        self.assertGreater(tile.outside_count, 0)

    def test_rejects_invalid_arguments(self) -> None:
        source = self.source(np.zeros((20, 20, 3), dtype=np.uint8))
        with self.assertRaises(ValueError):
            build_imagery_tile(source, self.reference, 0.0, 10.0, "t")
        with self.assertRaises(ValueError):
            build_imagery_tile(source, self.reference, 100.0, 0.0, "t")


class WriteImageryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        write_pack(self.root / "TEST")
        self.pack = load_pack("TEST", worlds_dir=self.root)

        data = np.zeros((200, 200, 3), dtype=np.uint8)
        data[:, :] = (40, 120, 60)
        path = _write_rgb_geotiff(
            self.root / "ortho.tif", data, west=27.9, north=41.1, pixel_size=0.002
        )
        source = GeoTiff(path)
        self.addCleanup(source.close)
        self.tile = build_imagery_tile(
            source, self.pack.geo_reference, radius_m=500.0, pixel_m=25.0,
            tile_id="test_ortho",
        )
        self.entry = {
            "source_id": "sentinel", "sha256": "abc", "attribution": "test attr",
        }

    def test_writes_jpeg_and_manifest_entry(self) -> None:
        image_path, manifest_path = write_imagery(self.tile, self.pack, self.entry)
        self.assertTrue(image_path.is_file())
        self.assertEqual(image_path.suffix, ".jpg")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        imagery = manifest["imagery"]
        self.assertEqual(imagery["tile_id"], "test_ortho")
        self.assertEqual(imagery["width"], self.tile.width)
        self.assertEqual(imagery["attribution"], "test attr")
        self.assertAlmostEqual(imagery["grid"]["radius_m"], 500.0)

    def test_declared_hash_matches_file(self) -> None:
        import hashlib

        image_path, manifest_path = write_imagery(self.tile, self.pack, self.entry)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["imagery"]["sha256"],
            hashlib.sha256(image_path.read_bytes()).hexdigest(),
        )

    def test_imagery_and_terrain_share_one_manifest(self) -> None:
        """İki komut aynı manifeste yazar; biri diğerini silmemeli."""
        flat = np.full((200, 200), 100.0, dtype=np.float32)
        height_source = GeoTiff(
            write_geotiff(self.root / "flat.tif", flat, west=27.9, north=41.1,
                          pixel_size=0.002)
        )
        self.addCleanup(height_source.close)
        height_tile = build_tile(
            height_source, self.pack.geo_reference, radius_m=500.0, step_m=50.0,
            tile_id="height",
        )

        # Once goruntu, sonra arazi
        write_imagery(self.tile, self.pack, self.entry)
        _, manifest_path = write_tile(height_tile, self.pack, self.entry)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("imagery", manifest, "dem crop görüntü kaydını sildi")
        self.assertEqual(len(manifest["tiles"]), 1)

        # Sonra tersi: arazi yazili haldeyken goruntuyu tekrar yaz
        write_imagery(self.tile, self.pack, self.entry)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("imagery", manifest)
        self.assertEqual(len(manifest["tiles"]), 1,
                         "imagery crop arazi kaydını sildi")


if __name__ == "__main__":
    unittest.main()
