extends SceneTree

const GeoReferenceScript := preload("res://scripts/geo_reference.gd")


func _init() -> void:
	var origin := GeoReferenceScript.new()
	assert(origin.is_valid_origin())
	_assert_near(origin.geodetic_to_enu(0.0, 0.0, 0.0), Vector3.ZERO, 0.000001)

	# Ekvator uzerinde WGS84 yaricaplarindan uretilen yaklasik birer metrelik
	# boylam/enlem farklari ENU eksenlerine dogru dusmeli.
	var one_meter_lon_deg := rad_to_deg(1.0 / origin.WGS84_A_M)
	var meridian_radius_m := origin.WGS84_A_M * (1.0 - origin.WGS84_E_SQ)
	var one_meter_lat_deg := rad_to_deg(1.0 / meridian_radius_m)

	var east := origin.geodetic_to_enu(0.0, one_meter_lon_deg, 0.0)
	var north := origin.geodetic_to_enu(one_meter_lat_deg, 0.0, 0.0)
	var up := origin.geodetic_to_enu(0.0, 0.0, 1.0)
	_assert_near(east, Vector3(1.0, 0.0, 0.0), 0.0001)
	_assert_near(north, Vector3(0.0, 1.0, 0.0), 0.0001)
	_assert_near(up, Vector3(0.0, 0.0, 1.0), 0.000001)

	# Godot sahnesinde east=+X, up=+Y ve north=-Z kullaniliyor.
	_assert_near(
		origin.geodetic_to_godot(one_meter_lat_deg, one_meter_lon_deg, 1.0),
		Vector3(1.0, 1.0, -1.0),
		0.0001,
	)

	origin.origin_lat_deg = 91.0
	assert(not origin.is_valid_origin())
	print("test_geo_reference: OK")
	quit()


func _assert_near(actual: Vector3, expected: Vector3, tolerance: float) -> void:
	assert(
		actual.distance_to(expected) <= tolerance,
		"Beklenen %s, alinan %s" % [expected, actual],
	)
