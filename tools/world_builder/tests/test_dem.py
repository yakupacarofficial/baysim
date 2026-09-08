"""dem.py testleri — vektörleştirilmiş jeodezi ve tile üretimi."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ..dem import (
    build_tile,
    runway_surfaces,
    stitch_runway,
    enu_to_geodetic_np,
    geodetic_to_enu_np,
    sample_bilinear_np,
    write_tile,
)
from ..geodesy import GeoReference
from ..geotiff import GeoTiff
from ..manifests import load_pack
from .helpers import write_geotiff, write_pack

LTBU = GeoReference(41.1383125, 27.919002777777777, 164.4)


class VectorisedGeodesyTests(unittest.TestCase):
    """numpy sürümleri skaler geodesy.py ile birebir aynı olmalı."""

    SAMPLES = [
        (0.0, 0.0, 0.0),
        (1500.0, -2300.0, 40.0),
        (-15000.0, 15000.0, -200.0),
        (21213.0, 21213.0, 0.0),
    ]

    def test_enu_to_geodetic_matches_scalar(self) -> None:
        east = np.array([s[0] for s in self.SAMPLES], dtype=np.float64)
        north = np.array([s[1] for s in self.SAMPLES], dtype=np.float64)
        up = np.array([s[2] for s in self.SAMPLES], dtype=np.float64)

        lat, lon, alt = enu_to_geodetic_np(LTBU, east, north, up)
        for index, (e, n, u) in enumerate(self.SAMPLES):
            expected = LTBU.from_enu(e, n, u)
            self.assertAlmostEqual(lat[index], expected[0], places=10)
            self.assertAlmostEqual(lon[index], expected[1], places=10)
            self.assertAlmostEqual(alt[index], expected[2], places=6)

    def test_geodetic_to_enu_matches_scalar(self) -> None:
        points = [
            (41.129469444444446, 27.905494444444443, 154.9),
            (41.14715555555556, 27.93251111111111, 173.9),
            (41.0, 28.0, 0.0),
        ]
        lat = np.array([p[0] for p in points], dtype=np.float64)
        lon = np.array([p[1] for p in points], dtype=np.float64)
        alt = np.array([p[2] for p in points], dtype=np.float64)

        east, north, up = geodetic_to_enu_np(LTBU, lat, lon, alt)
        for index, point in enumerate(points):
            expected = LTBU.to_enu(*point)
            self.assertAlmostEqual(east[index], expected[0], places=6)
            self.assertAlmostEqual(north[index], expected[1], places=6)
            self.assertAlmostEqual(up[index], expected[2], places=6)

    def test_round_trip_through_both_directions(self) -> None:
        east = np.linspace(-15000.0, 15000.0, 11)
        north = np.linspace(15000.0, -15000.0, 11)
        zero = np.zeros_like(east)
        lat, lon, alt = enu_to_geodetic_np(LTBU, east, north, zero)
        back_east, back_north, back_up = geodetic_to_enu_np(LTBU, lat, lon, alt)
        np.testing.assert_allclose(back_east, east, atol=1e-6)
        np.testing.assert_allclose(back_north, north, atol=1e-6)
        np.testing.assert_allclose(back_up, zero, atol=1e-6)


class BilinearSamplingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        directory = Path(self._temp.name)
        data = np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float32)
        self.tiff = GeoTiff(
            write_geotiff(directory / "s.tif", data, west=28.0, north=41.0,
                          pixel_size=0.01)
        )
        self.addCleanup(self.tiff.close)

    def test_corners_and_centre(self) -> None:
        lat = np.array([41.0, 41.0, 40.99, 40.995])
        lon = np.array([28.0, 28.01, 28.0, 28.005])
        values, inside = sample_bilinear_np(self.tiff, lat, lon)
        np.testing.assert_allclose(values, [0.0, 10.0, 20.0, 15.0], atol=1e-5)
        self.assertTrue(inside.all())

    def test_outside_is_flagged_and_clamped(self) -> None:
        lat = np.array([50.0])
        lon = np.array([28.0])
        values, inside = sample_bilinear_np(self.tiff, lat, lon)
        self.assertFalse(inside[0])
        self.assertTrue(math.isfinite(float(values[0])))


class BuildTileTests(unittest.TestCase):
    """Sabit yükseklikli sentetik DEM üzerinde geometri doğrulaması."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.directory = Path(self._temp.name)
        # LTBU cevresini kapsayan, her yeri 164.4 m MSL olan duz bir DEM.
        flat = np.full((400, 400), 164.4, dtype=np.float32)
        self.dem = GeoTiff(
            write_geotiff(
                self.directory / "flat.tif", flat,
                west=27.6, north=41.4, pixel_size=0.002,
            )
        )
        self.addCleanup(self.dem.close)

    def test_grid_shape_and_step(self) -> None:
        tile = build_tile(self.dem, LTBU, radius_m=3000.0, step_m=30.0, tile_id="t")
        self.assertEqual(tile.width, 201)
        self.assertEqual(tile.height, 201)
        self.assertEqual(tile.outside_count, 0)

    def test_centre_of_flat_dem_is_zero_height(self) -> None:
        """Orijin irtifasıyla aynı düz DEM'de merkez ENU up = 0 olmalı."""
        tile = build_tile(self.dem, LTBU, radius_m=3000.0, step_m=30.0, tile_id="t")
        centre = tile.heights[tile.height // 2, tile.width // 2]
        self.assertAlmostEqual(float(centre), 0.0, places=3)

    def test_curvature_lowers_the_edges(self) -> None:
        """Düz bir DEM'de bile kenarlar yeryüzü eğriliği kadar aşağıda olmalı."""
        radius = 15000.0
        tile = build_tile(self.dem, LTBU, radius_m=radius, step_m=500.0, tile_id="t")
        # Kose, merkeze radius*sqrt(2) uzaklikta; dusus ~ d^2 / 2R
        corner_distance = radius * math.sqrt(2.0)
        expected_drop = corner_distance**2 / (2.0 * 6_371_000.0)
        corner = float(tile.heights[0, 0])
        self.assertAlmostEqual(corner, -expected_drop, delta=1.0)
        # Merkez hala sifir
        self.assertAlmostEqual(
            float(tile.heights[tile.height // 2, tile.width // 2]), 0.0, places=2
        )

    def test_north_west_corner_is_first_row_first_column(self) -> None:
        """Satır sırası kuzey→güney, sütun sırası batı→doğu olmalı."""
        ramp = np.zeros((400, 400), dtype=np.float32)
        ramp[:200, :] = 200.0  # kuzey yarisi yuksek
        dem = GeoTiff(
            write_geotiff(
                self.directory / "ramp.tif", ramp,
                west=27.6, north=41.4, pixel_size=0.002,
            )
        )
        self.addCleanup(dem.close)
        tile = build_tile(dem, LTBU, radius_m=3000.0, step_m=100.0, tile_id="t")
        self.assertGreater(tile.heights[0, 0], tile.heights[-1, 0])

    def test_water_counted_on_source_samples(self) -> None:
        sea = np.zeros((400, 400), dtype=np.float32)
        dem = GeoTiff(
            write_geotiff(
                self.directory / "sea.tif", sea,
                west=27.6, north=41.4, pixel_size=0.002,
            )
        )
        self.addCleanup(dem.close)
        tile = build_tile(dem, LTBU, radius_m=1000.0, step_m=100.0, tile_id="t")
        self.assertEqual(tile.water_count, tile.width * tile.height)
        self.assertAlmostEqual(tile.source_min_msl_m, 0.0, places=6)

    def test_rejects_invalid_arguments(self) -> None:
        with self.assertRaises(ValueError):
            build_tile(self.dem, LTBU, radius_m=0.0, step_m=30.0, tile_id="t")
        with self.assertRaises(ValueError):
            build_tile(self.dem, LTBU, radius_m=100.0, step_m=0.0, tile_id="t")
        with self.assertRaises(ValueError):
            build_tile(
                self.dem, GeoReference(float("nan"), 0.0, 0.0),
                radius_m=100.0, step_m=10.0, tile_id="t",
            )


class RunwayStitchingTests(unittest.TestCase):
    """Pist-arazi dikişi: pist düzlemine oturma ve basamaksız geçiş."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        write_pack(self.root / "TEST")
        self.pack = load_pack("TEST", worlds_dir=self.root)

        # Her yeri orijin irtifasindan 50 m yuksek, tumsek bir arazi.
        bumpy = np.full((600, 600), 150.0, dtype=np.float32)
        self.dem = GeoTiff(
            write_geotiff(
                self.root / "bumpy.tif", bumpy,
                west=27.9, north=41.1, pixel_size=0.001,
            )
        )
        self.addCleanup(self.dem.close)

    def surfaces(self):
        return runway_surfaces(self.pack)

    def test_surfaces_land_on_published_elevations(self) -> None:
        surfaces = self.surfaces()
        self.assertEqual(len(surfaces), 1)
        runway = surfaces[0]
        self.assertEqual(runway.runway_id, "09/27")
        self.assertAlmostEqual(runway.width_m, 45.0)
        # Iki esik de orijinle ayni 100 m MSL'de ama orijinden ~500 m uzakta.
        # Ayni MSL'deki bir nokta tegetin d^2/2R kadar altina duser; ENU up
        # bu yuzden sifir degil, kucuk bir negatif sayidir. Pist mesh'i de
        # ayni donusumden gectigi icin arazi ile tutarli kalir.
        expected_drop = 500.0**2 / (2.0 * 6_371_000.0)
        self.assertAlmostEqual(runway.start_up_m, -expected_drop, delta=0.002)
        self.assertAlmostEqual(runway.end_up_m, -expected_drop, delta=0.002)

    def sample(self, tile, east: float, north: float) -> float:
        i = int(round((east + tile.radius_m) / tile.step_m))
        j = int(round((tile.radius_m - north) / tile.step_m))
        return float(tile.heights[j, i])

    def test_runway_centreline_sits_just_below_the_runway_plane(self) -> None:
        """Arazi, pist düzleminin tam depress_m kadar altında olmalı."""
        depress = 0.15
        tile = build_tile(
            self.dem, self.pack.geo_reference, radius_m=1500.0, step_m=10.0,
            tile_id="t", runways=self.surfaces(), depress_m=depress,
        )
        runway = self.surfaces()[0]
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            east = runway.start_east_m + fraction * (
                runway.end_east_m - runway.start_east_m
            )
            north = runway.start_north_m + fraction * (
                runway.end_north_m - runway.start_north_m
            )
            surface = runway.start_up_m + fraction * (
                runway.end_up_m - runway.start_up_m
            )
            sampled = self.sample(tile, east, north)
            self.assertAlmostEqual(sampled, surface - depress, delta=0.05,
                                   msg=f"t={fraction}")
            # Arazi kesinlikle pistin ALTINDA kalmali; esitlik z-fighting demek.
            self.assertLess(sampled, surface, msg=f"t={fraction}")

    def test_far_terrain_is_untouched(self) -> None:
        stitched = build_tile(
            self.dem, self.pack.geo_reference, radius_m=1500.0, step_m=10.0,
            tile_id="t", runways=self.surfaces(),
        )
        raw = build_tile(
            self.dem, self.pack.geo_reference, radius_m=1500.0, step_m=10.0,
            tile_id="t", runways=[],
        )
        # Pistten 1 km kuzeyde dikis etkisi olmamali
        self.assertAlmostEqual(
            self.sample(stitched, 0.0, 1000.0),
            self.sample(raw, 0.0, 1000.0),
            places=5,
        )
        # Ama pist uzerinde fark buyuk olmali (arazi 50 m yukarideydi)
        self.assertGreater(
            abs(self.sample(raw, 0.0, 0.0) - self.sample(stitched, 0.0, 0.0)), 40.0
        )

    def test_transition_is_monotonic_and_stepless(self) -> None:
        """Omuzdan araziye geçişte sıçrama olmamalı."""
        tile = build_tile(
            self.dem, self.pack.geo_reference, radius_m=1500.0, step_m=10.0,
            tile_id="t", runways=self.surfaces(), shoulder_m=60.0, blend_m=240.0,
        )
        # Pist ortasindan kuzeye dogru kesit al (pist dogu-bati uzaniyor)
        profile = [self.sample(tile, 0.0, north) for north in range(0, 600, 10)]
        jumps = [abs(b - a) for a, b in zip(profile, profile[1:])]
        self.assertLess(max(jumps), 5.0, "Geçişte basamak var")
        # Baslangic pist duzleminde, son deger arazi seviyesinde olmali
        self.assertAlmostEqual(profile[0], -0.15, delta=0.2)
        self.assertAlmostEqual(profile[-1], 50.0, delta=1.0)

    def test_shoulder_stays_perfectly_flat(self) -> None:
        tile = build_tile(
            self.dem, self.pack.geo_reference, radius_m=1500.0, step_m=10.0,
            tile_id="t", runways=self.surfaces(), shoulder_m=60.0, blend_m=240.0,
        )
        # Yari genislik 22.5 + omuz 60 = 82.5 m'ye kadar tam duz
        runway = self.surfaces()[0]
        for north in (0.0, 20.0, 40.0, 60.0, 80.0):
            sampled = self.sample(tile, 0.0, north)
            self.assertAlmostEqual(sampled, runway.start_up_m - 0.15, delta=0.05)

    def test_zero_blend_produces_a_hard_edge(self) -> None:
        tile = build_tile(
            self.dem, self.pack.geo_reference, radius_m=1500.0, step_m=10.0,
            tile_id="t", runways=self.surfaces(), shoulder_m=0.0, blend_m=0.0,
        )
        self.assertAlmostEqual(self.sample(tile, 0.0, 0.0), -0.15, delta=0.2)
        self.assertAlmostEqual(self.sample(tile, 0.0, 100.0), 50.0, delta=1.0)

    def test_degenerate_runway_is_ignored(self) -> None:
        from ..dem import RunwaySurface

        heights = np.full((3, 3), 7.0)
        east = np.zeros((3, 3))
        north = np.zeros((3, 3))
        zero_length = RunwaySurface("x", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 45.0)
        zero_width = RunwaySurface("y", 0.0, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0)
        for runway in (zero_length, zero_width):
            result = stitch_runway(heights, east, north, runway, 10.0, 10.0)
            np.testing.assert_array_equal(result, heights)

    def test_stitching_recorded_in_manifest(self) -> None:
        tile = build_tile(
            self.dem, self.pack.geo_reference, radius_m=500.0, step_m=50.0,
            tile_id="t", runways=self.surfaces(), shoulder_m=60.0, blend_m=240.0,
        )
        entry = {"source_id": "s", "sha256": "abc", "attribution": "test"}
        _, manifest_path = write_tile(tile, self.pack, entry)
        described = json.loads(manifest_path.read_text(encoding="utf-8"))["tiles"][0]
        self.assertEqual(described["runway_stitching"]["runways"], ["09/27"])
        self.assertAlmostEqual(described["runway_stitching"]["shoulder_m"], 60.0)
        self.assertAlmostEqual(described["runway_stitching"]["blend_m"], 240.0)
        self.assertAlmostEqual(described["runway_stitching"]["depress_m"], 0.15)


class WriteTileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        write_pack(self.root / "TEST")
        self.pack = load_pack("TEST", worlds_dir=self.root)

        flat = np.full((200, 200), 100.0, dtype=np.float32)
        self.dem = GeoTiff(
            write_geotiff(
                self.root / "flat.tif", flat,
                west=27.9, north=41.1, pixel_size=0.002,
            )
        )
        self.addCleanup(self.dem.close)
        self.tile = build_tile(
            self.dem, self.pack.geo_reference,
            radius_m=500.0, step_m=50.0, tile_id="test_tile",
        )

    def test_binary_layout_round_trips(self) -> None:
        entry = {"source_id": "s", "sha256": "abc", "attribution": "test"}
        data_path, manifest_path = write_tile(self.tile, self.pack, entry)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        described = manifest["tiles"][0]
        self.assertEqual(described["sample_format"], "float32_le")
        self.assertEqual(described["row_order"], "north_to_south")
        self.assertEqual(described["column_order"], "west_to_east")
        self.assertEqual(
            described["size_bytes"], described["width"] * described["height"] * 4
        )

        raw = np.fromfile(data_path, dtype="<f4").reshape(
            described["height"], described["width"]
        )
        np.testing.assert_allclose(raw, self.tile.heights, atol=0.0)

    def test_manifest_records_grid_and_origin(self) -> None:
        entry = {"source_id": "s", "sha256": "abc", "attribution": "test"}
        _, manifest_path = write_tile(self.tile, self.pack, entry)
        described = json.loads(manifest_path.read_text(encoding="utf-8"))["tiles"][0]

        self.assertEqual(described["grid"]["space"], "local_enu_metres")
        self.assertAlmostEqual(described["grid"]["step_m"], 50.0)
        self.assertAlmostEqual(described["grid"]["east_min_m"], -500.0)
        self.assertAlmostEqual(
            described["origin"]["lat_deg"], self.pack.geo_reference.lat_deg
        )

    def test_declared_sha256_matches_written_bytes(self) -> None:
        import hashlib

        entry = {"source_id": "s", "sha256": "abc", "attribution": "test"}
        data_path, manifest_path = write_tile(self.tile, self.pack, entry)
        described = json.loads(manifest_path.read_text(encoding="utf-8"))["tiles"][0]
        self.assertEqual(
            described["sha256"], hashlib.sha256(data_path.read_bytes()).hexdigest()
        )


if __name__ == "__main__":
    unittest.main()
