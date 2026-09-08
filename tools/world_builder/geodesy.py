"""WGS84 → ECEF → yerel ENU dönüşümü.

Bu modül `scripts/geo_reference.gd` ile **aynı** sonucu üretmek zorundadır.
Sabitler ve formüller bilerek birebir aynı tutulmuştur; world builder'ın
ürettiği geometri ile Godot çalışma zamanının hesabı ayrışırsa pist ve arazi
birbirine oturmaz. `tests/test_geodesy.py` içindeki beklenen değerler
`tests/test_geo_reference.gd` ile ortak sözleşmedir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

WGS84_A_M = 6378137.0
WGS84_E_SQ = 6.6943799901413165e-3


def geodetic_to_ecef(
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
) -> tuple[float, float, float]:
    """Jeodezik konumu yer merkezli kartezyen koordinata çevirir."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    prime_vertical_radius = WGS84_A_M / math.sqrt(1.0 - WGS84_E_SQ * sin_lat * sin_lat)
    return (
        (prime_vertical_radius + alt_m) * cos_lat * math.cos(lon),
        (prime_vertical_radius + alt_m) * cos_lat * math.sin(lon),
        (prime_vertical_radius * (1.0 - WGS84_E_SQ) + alt_m) * sin_lat,
    )


def ecef_to_geodetic(x: float, y: float, z: float) -> tuple[float, float, float]:
    """ECEF → (lat_deg, lon_deg, alt_m). Bowring'in kapalı form çözümü."""
    a = WGS84_A_M
    e_sq = WGS84_E_SQ
    b = a * math.sqrt(1.0 - e_sq)
    e_prime_sq = e_sq / (1.0 - e_sq)

    p = math.hypot(x, y)
    if p == 0.0:  # kutup
        lat = math.copysign(math.pi / 2.0, z)
        return math.degrees(lat), 0.0, abs(z) - b

    theta = math.atan2(z * a, p * b)
    lat = math.atan2(
        z + e_prime_sq * b * math.sin(theta) ** 3,
        p - e_sq * a * math.cos(theta) ** 3,
    )
    lon = math.atan2(y, x)
    sin_lat = math.sin(lat)
    prime_vertical_radius = a / math.sqrt(1.0 - e_sq * sin_lat * sin_lat)
    alt = p / math.cos(lat) - prime_vertical_radius
    return math.degrees(lat), math.degrees(lon), alt


@dataclass(frozen=True, slots=True)
class GeoReference:
    """Yerel ENU sahnesinin WGS84 referans noktası."""

    lat_deg: float
    lon_deg: float
    alt_msl_m: float

    def is_valid(self) -> bool:
        values = (self.lat_deg, self.lon_deg, self.alt_msl_m)
        if not all(math.isfinite(value) for value in values):
            return False
        return -90.0 <= self.lat_deg <= 90.0 and -180.0 <= self.lon_deg <= 180.0

    def to_enu(
        self,
        lat_deg: float,
        lon_deg: float,
        alt_msl_m: float,
    ) -> tuple[float, float, float]:
        """(east, north, up) metre döndürür."""
        if not self.is_valid():
            raise ValueError("Geçersiz WGS84 dünya orijini")

        ox, oy, oz = geodetic_to_ecef(self.lat_deg, self.lon_deg, self.alt_msl_m)
        px, py, pz = geodetic_to_ecef(lat_deg, lon_deg, alt_msl_m)
        dx, dy, dz = px - ox, py - oy, pz - oz

        lat0 = math.radians(self.lat_deg)
        lon0 = math.radians(self.lon_deg)
        sin_lat, cos_lat = math.sin(lat0), math.cos(lat0)
        sin_lon, cos_lon = math.sin(lon0), math.cos(lon0)

        east = -sin_lon * dx + cos_lon * dy
        north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
        up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
        return east, north, up

    def to_godot(
        self,
        lat_deg: float,
        lon_deg: float,
        alt_msl_m: float,
    ) -> tuple[float, float, float]:
        """Godot sahne eksenlerinde (x=east, y=up, z=-north) döndürür."""
        east, north, up = self.to_enu(lat_deg, lon_deg, alt_msl_m)
        return east, up, -north

    def from_enu(
        self,
        east_m: float,
        north_m: float,
        up_m: float,
    ) -> tuple[float, float, float]:
        """`to_enu` işleminin tersi: ENU metre → (lat_deg, lon_deg, alt_msl_m)."""
        if not self.is_valid():
            raise ValueError("Geçersiz WGS84 dünya orijini")

        lat0 = math.radians(self.lat_deg)
        lon0 = math.radians(self.lon_deg)
        sin_lat, cos_lat = math.sin(lat0), math.cos(lat0)
        sin_lon, cos_lon = math.sin(lon0), math.cos(lon0)

        dx = -sin_lon * east_m - sin_lat * cos_lon * north_m + cos_lat * cos_lon * up_m
        dy = cos_lon * east_m - sin_lat * sin_lon * north_m + cos_lat * sin_lon * up_m
        dz = cos_lat * north_m + sin_lat * up_m

        ox, oy, oz = geodetic_to_ecef(self.lat_deg, self.lon_deg, self.alt_msl_m)
        return ecef_to_geodetic(ox + dx, oy + dy, oz + dz)


def horizontal_distance_m(
    reference: GeoReference,
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
) -> float:
    """İki noktanın ortak ENU düzlemindeki yatay uzaklığı."""
    ea, na, _ = reference.to_enu(lat_a, lon_a, 0.0)
    eb, nb, _ = reference.to_enu(lat_b, lon_b, 0.0)
    return math.hypot(eb - ea, nb - na)


def true_bearing_deg(
    reference: GeoReference,
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
) -> float:
    """A'dan B'ye yerel ENU düzlemindeki true bearing (0=kuzey, saat yönü)."""
    ea, na, _ = reference.to_enu(lat_a, lon_a, 0.0)
    eb, nb, _ = reference.to_enu(lat_b, lon_b, 0.0)
    return math.degrees(math.atan2(eb - ea, nb - na)) % 360.0


def angle_difference_deg(first: float, second: float) -> float:
    """İki açı arasındaki en kısa mutlak fark."""
    return abs((first - second + 180.0) % 360.0 - 180.0)
