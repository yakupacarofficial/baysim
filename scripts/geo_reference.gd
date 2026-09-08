class_name GeoReference
extends Resource

## WGS84 konumlarini kucuk ve hassas bir yerel ENU sahnesine donusturur.
## ENU Vector3 sirasi: x=east, y=north, z=up.

const WGS84_A_M := 6378137.0
const WGS84_E_SQ := 6.6943799901413165e-3

@export_range(-90.0, 90.0, 0.000001) var origin_lat_deg := 0.0
@export_range(-180.0, 180.0, 0.000001) var origin_lon_deg := 0.0
@export var origin_alt_msl_m := 0.0


func is_valid_origin() -> bool:
	return (
		is_finite(origin_lat_deg)
		and is_finite(origin_lon_deg)
		and is_finite(origin_alt_msl_m)
		and origin_lat_deg >= -90.0
		and origin_lat_deg <= 90.0
		and origin_lon_deg >= -180.0
		and origin_lon_deg <= 180.0
	)


func geodetic_to_enu(lat_deg: float, lon_deg: float, alt_msl_m: float) -> Vector3:
	if not is_valid_origin():
		push_error("Gecersiz WGS84 dunya orijini")
		return Vector3.ZERO

	# ECEF islemleri dunya yaricapi mertebesindedir. PackedFloat64Array kullanmak,
	# Godot'un varsayilan 32-bit Vector3 yapisina erken donup hassasiyet kaybetmeyi onler.
	var origin_ecef := _geodetic_to_ecef(
		origin_lat_deg,
		origin_lon_deg,
		origin_alt_msl_m,
	)
	var point_ecef := _geodetic_to_ecef(lat_deg, lon_deg, alt_msl_m)
	var dx := point_ecef[0] - origin_ecef[0]
	var dy := point_ecef[1] - origin_ecef[1]
	var dz := point_ecef[2] - origin_ecef[2]

	var lat0 := deg_to_rad(origin_lat_deg)
	var lon0 := deg_to_rad(origin_lon_deg)
	var sin_lat := sin(lat0)
	var cos_lat := cos(lat0)
	var sin_lon := sin(lon0)
	var cos_lon := cos(lon0)

	var east := -sin_lon * dx + cos_lon * dy
	var north := (
		-sin_lat * cos_lon * dx
		- sin_lat * sin_lon * dy
		+ cos_lat * dz
	)
	var up := (
		cos_lat * cos_lon * dx
		+ cos_lat * sin_lon * dy
		+ sin_lat * dz
	)
	return Vector3(east, north, up)


func geodetic_to_godot(lat_deg: float, lon_deg: float, alt_msl_m: float) -> Vector3:
	var enu := geodetic_to_enu(lat_deg, lon_deg, alt_msl_m)
	return Vector3(enu.x, enu.z, -enu.y)


static func _geodetic_to_ecef(
	lat_deg: float,
	lon_deg: float,
	alt_m: float,
) -> PackedFloat64Array:
	var lat := deg_to_rad(lat_deg)
	var lon := deg_to_rad(lon_deg)
	var sin_lat := sin(lat)
	var cos_lat := cos(lat)
	var prime_vertical_radius := WGS84_A_M / sqrt(1.0 - WGS84_E_SQ * sin_lat * sin_lat)

	return PackedFloat64Array([
		(prime_vertical_radius + alt_m) * cos_lat * cos(lon),
		(prime_vertical_radius + alt_m) * cos_lat * sin(lon),
		(prime_vertical_radius * (1.0 - WGS84_E_SQ) + alt_m) * sin_lat,
	])
