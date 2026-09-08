class_name ProceduralAirport
extends Node3D

## AirportPack pistlerini çalışma zamanında metre ölçekli Godot mesh'lerine çevirir.

const AirportPackScript := preload("res://scripts/world/airport_pack.gd")

@export_file("*.json") var world_manifest_path := "res://worlds/LTBU/world.json"
@export var build_on_ready := true

var bundle: Dictionary = {}


func _ready() -> void:
	if build_on_ready:
		rebuild()


func rebuild() -> bool:
	_clear_generated_nodes()
	bundle = AirportPackScript.load_bundle(world_manifest_path)
	var errors := AirportPackScript.validate_bundle(bundle)
	if not errors.is_empty():
		push_error("AirportPack geçersiz: %s" % "; ".join(errors))
		return false

	var world: Dictionary = bundle["world"]
	var runway_document: Dictionary = bundle["runways"]
	var geo_reference := AirportPackScript.make_geo_reference(world)
	var render: Dictionary = world.get("render", {})
	var flatten_vertical := bool(render.get("flatten_runways_until_dem", true))
	for runway_value: Variant in runway_document.get("runways", []):
		var runway: Dictionary = runway_value
		var geometry := AirportPackScript.runway_geometry(
			runway,
			geo_reference,
			flatten_vertical,
		)
		var runway_mesh := _create_runway_mesh(runway, geometry)
		if runway_mesh == null:
			return false
		add_child(runway_mesh)
	print("AirportPack yüklendi: %s" % str(world.get("world_id", "?")))
	return true


func _create_runway_mesh(runway: Dictionary, geometry: Dictionary) -> MeshInstance3D:
	var corners := AirportPackScript.runway_quad_corners(geometry)
	if corners.size() != 4:
		push_error("Pist geometrisi üretilemedi: %s" % str(runway.get("id", "?")))
		return null

	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = "Runway_%s" % str(runway.get("id", "?")).replace("/", "_")
	mesh_instance.mesh = _build_quad_mesh(corners, geometry)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.18, 0.18, 0.19)
	material.roughness = 0.88
	mesh_instance.material_override = material
	mesh_instance.set_meta("runway_id", str(runway.get("id", "")))
	mesh_instance.set_meta("computed_length_m", float(geometry["horizontal_length_m"]))
	mesh_instance.set_meta("computed_true_bearing_deg", float(
		geometry["computed_true_bearing_deg"]
	))
	return mesh_instance


func _build_quad_mesh(corners: PackedVector3Array, geometry: Dictionary) -> ArrayMesh:
	var normal := (corners[1] - corners[0]).cross(corners[2] - corners[0]).normalized()
	var width_m: float = geometry["width_m"]
	var length_m: float = geometry["spatial_length_m"]
	var vertices := PackedVector3Array([
		corners[0], corners[1], corners[2],
		corners[1], corners[3], corners[2],
	])
	var uvs := PackedVector2Array([
		Vector2(0.0, 0.0), Vector2(width_m, 0.0), Vector2(0.0, length_m),
		Vector2(width_m, 0.0), Vector2(width_m, length_m), Vector2(0.0, length_m),
	])

	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for index in range(vertices.size()):
		surface.set_normal(normal)
		surface.set_uv(uvs[index])
		surface.add_vertex(vertices[index])
	return surface.commit()


func _clear_generated_nodes() -> void:
	for child in get_children():
		remove_child(child)
		child.queue_free()
