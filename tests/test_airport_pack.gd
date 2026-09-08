extends SceneTree

const AirportPackScript := preload("res://scripts/world/airport_pack.gd")
const ProceduralAirportScript := preload("res://scripts/world/procedural_airport.gd")
const LTBU_WORLD := "res://worlds/LTBU/world.json"


func _init() -> void:
	var bundle := AirportPackScript.load_bundle(LTBU_WORLD)
	var errors := AirportPackScript.validate_bundle(bundle)
	assert(errors.is_empty(), "; ".join(errors))

	var world: Dictionary = bundle["world"]
	var runway_document: Dictionary = bundle["runways"]
	var runway: Dictionary = runway_document["runways"][0]
	var geo_reference := AirportPackScript.make_geo_reference(world)
	var flat_geometry := AirportPackScript.runway_geometry(runway, geo_reference, true)
	var profile_geometry := AirportPackScript.runway_geometry(runway, geo_reference, false)

	# AIP koordinatları saniyenin yüzde biri hassasiyetinde yayımlandığından
	# hesaplanan eşik mesafesi, beyan edilen 3000 metreden birkaç metre sapabilir.
	assert(absf(
		float(flat_geometry["horizontal_length_m"])
		- float(runway["declared_length_m"])
	) <= 5.0)
	var published_bearing := float(runway["thresholds"]["04"]["true_bearing_deg"])
	assert(_angle_difference_deg(
		float(flat_geometry["computed_true_bearing_deg"]),
		published_bearing,
	) <= 0.2)

	var center: Vector3 = flat_geometry["center"]
	assert(Vector2(center.x, center.z).length() <= 0.5)
	assert(absf(center.y) <= 0.000001)
	assert(absf(
		float(profile_geometry["end"].y) - float(profile_geometry["start"].y) - 19.0
	) <= 0.05)

	var corners := AirportPackScript.runway_quad_corners(flat_geometry)
	assert(corners.size() == 4)
	assert(absf(corners[0].distance_to(corners[1]) - 45.0) <= 0.001)

	var airport := ProceduralAirportScript.new()
	airport.build_on_ready = false
	root.add_child(airport)
	assert(airport.rebuild())
	var runway_mesh := airport.get_node_or_null("Runway_04_22") as MeshInstance3D
	assert(runway_mesh != null)
	assert(runway_mesh.mesh != null)
	assert(runway_mesh.mesh.get_surface_count() == 1)
	assert(absf(
		float(runway_mesh.get_meta("computed_true_bearing_deg")) - published_bearing
	) <= 0.2)

	print("test_airport_pack: OK")
	quit()


func _angle_difference_deg(first: float, second: float) -> float:
	return absf(fposmod(first - second + 180.0, 360.0) - 180.0)
