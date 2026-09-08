"""geodesy.py testleri.

Buradaki beklentiler `tests/test_geo_reference.gd` ile ortak sözleşmedir:
iki dil aynı WGS84→ENU sonucunu üretmezse world builder'ın geometrisi Godot
sahnesine oturmaz.
"""

from __future__ import annotations

import math
import unittest

from ..geodesy import (
    WGS84_A_M,
    WGS84_E_SQ,
    GeoReference,
    angle_difference_deg,
    ecef_to_geodetic,
    geodetic_to_ecef,
    horizontal_distance_m,
    true_bearing_deg,
)


class GeoReferenceTests(unittest.TestCase):
    def test_origin_maps_to_zero(self) -> None:
        reference = GeoReference(0.0, 0.0, 0.0)
        east, north, up = reference.to_enu(0.0, 0.0, 0.0)
        self.assertAlmostEqual(east, 0.0, places=6)
        self.assertAlmostEqual(north, 0.0, places=6)
        self.assertAlmostEqual(up, 0.0, places=6)

    def test_one_metre_axes_at_equator(self) -> None:
        """test_geo_reference.gd ile aynı bir metrelik eksen kontrolü."""
        reference = GeoReference(0.0, 0.0, 0.0)
        one_metre_lon_deg = math.degrees(1.0 / WGS84_A_M)
        meridian_radius_m = WGS84_A_M * (1.0 - WGS84_E_SQ)
        one_metre_lat_deg = math.degrees(1.0 / meridian_radius_m)

        east, north, up = reference.to_enu(0.0, one_metre_lon_deg, 0.0)
        self.assertAlmostEqual(east, 1.0, places=4)
        self.assertAlmostEqual(north, 0.0, places=4)
        self.assertAlmostEqual(up, 0.0, places=4)

        east, north, up = reference.to_enu(one_metre_lat_deg, 0.0, 0.0)
        self.assertAlmostEqual(east, 0.0, places=4)
        self.assertAlmostEqual(north, 1.0, places=4)
        self.assertAlmostEqual(up, 0.0, places=4)

        east, north, up = reference.to_enu(0.0, 0.0, 1.0)
        self.assertAlmostEqual(up, 1.0, places=6)

    def test_godot_axis_mapping(self) -> None:
        """Godot: east=+X, up=+Y, north=-Z."""
        reference = GeoReference(0.0, 0.0, 0.0)
        one_metre_lon_deg = math.degrees(1.0 / WGS84_A_M)
        meridian_radius_m = WGS84_A_M * (1.0 - WGS84_E_SQ)
        one_metre_lat_deg = math.degrees(1.0 / meridian_radius_m)

        x, y, z = reference.to_godot(one_metre_lat_deg, one_metre_lon_deg, 1.0)
        self.assertAlmostEqual(x, 1.0, places=4)
        self.assertAlmostEqual(y, 1.0, places=4)
        self.assertAlmostEqual(z, -1.0, places=4)

    def test_invalid_origin_rejected(self) -> None:
        self.assertFalse(GeoReference(91.0, 0.0, 0.0).is_valid())
        self.assertFalse(GeoReference(0.0, 181.0, 0.0).is_valid())
        self.assertFalse(GeoReference(float("nan"), 0.0, 0.0).is_valid())
        with self.assertRaises(ValueError):
            GeoReference(91.0, 0.0, 0.0).to_enu(0.0, 0.0, 0.0)


class InverseTests(unittest.TestCase):
    def test_ecef_round_trip(self) -> None:
        for lat, lon, alt in (
            (41.1383125, 27.919002777777777, 164.4),
            (0.0, 0.0, 0.0),
            (-33.9, 151.2, 25.0),
            (78.2, -15.6, 1200.0),
        ):
            x, y, z = geodetic_to_ecef(lat, lon, alt)
            back_lat, back_lon, back_alt = ecef_to_geodetic(x, y, z)
            self.assertAlmostEqual(back_lat, lat, places=9)
            self.assertAlmostEqual(back_lon, lon, places=9)
            self.assertAlmostEqual(back_alt, alt, places=6)

    def test_enu_round_trip(self) -> None:
        reference = GeoReference(41.1383125, 27.919002777777777, 164.4)
        for east, north, up in (
            (0.0, 0.0, 0.0),
            (1500.0, -2300.0, 40.0),
            (-15000.0, 15000.0, -200.0),
        ):
            lat, lon, alt = reference.from_enu(east, north, up)
            back_east, back_north, back_up = reference.to_enu(lat, lon, alt)
            self.assertAlmostEqual(back_east, east, places=5)
            self.assertAlmostEqual(back_north, north, places=5)
            self.assertAlmostEqual(back_up, up, places=5)


class RunwayMeasurementTests(unittest.TestCase):
    """LTBU eşiklerinin yayımlanan değerlerle uyumu."""

    REFERENCE = GeoReference(41.1383125, 27.919002777777777, 164.4)
    THRESHOLD_04 = (41.129469444444446, 27.905494444444443)
    THRESHOLD_22 = (41.14715555555556, 27.93251111111111)

    def test_measured_length_matches_declared(self) -> None:
        length = horizontal_distance_m(
            self.REFERENCE, *self.THRESHOLD_04, *self.THRESHOLD_22
        )
        self.assertAlmostEqual(length, 3000.0, delta=5.0)

    def test_measured_bearing_matches_published(self) -> None:
        bearing = true_bearing_deg(
            self.REFERENCE, *self.THRESHOLD_04, *self.THRESHOLD_22
        )
        self.assertLessEqual(angle_difference_deg(bearing, 49.10), 0.2)

    def test_reciprocal_bearing(self) -> None:
        forward = true_bearing_deg(
            self.REFERENCE, *self.THRESHOLD_04, *self.THRESHOLD_22
        )
        backward = true_bearing_deg(
            self.REFERENCE, *self.THRESHOLD_22, *self.THRESHOLD_04
        )
        self.assertAlmostEqual(angle_difference_deg(forward + 180.0, backward), 0.0, places=6)


class AngleTests(unittest.TestCase):
    def test_wraps_around_north(self) -> None:
        self.assertAlmostEqual(angle_difference_deg(359.0, 1.0), 2.0)
        self.assertAlmostEqual(angle_difference_deg(1.0, 359.0), 2.0)
        self.assertAlmostEqual(angle_difference_deg(180.0, 0.0), 180.0)


if __name__ == "__main__":
    unittest.main()
