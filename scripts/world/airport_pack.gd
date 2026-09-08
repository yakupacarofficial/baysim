class_name AirportPack
extends RefCounted

## Sürümlü AirportPack JSON dosyalarını yükler, doğrular ve Godot geometrisine
## dönüştürür. Bütün konumlar ortak GeoReference üzerinden hesaplanır.

const GeoReferenceScript := preload("res://scripts/geo_reference.gd")
const SUPPORTED_FORMAT_VERSION := 1


static func load_bundle(world_manifest_path: String) -> Dictionary:
	var world := _load_json_object(world_manifest_path)
	if world.is_empty():
		return {}

	var base_dir := world_manifest_path.get_base_dir()
	var runways_path := base_dir.path_join(str(world.get("runways_file", "runways.json")))
	var sources_path := base_dir.path_join(str(world.get("sources_file", "sources.json")))
	return {
		"world": world,
		"runways": _load_json_object(runways_path),
		"sources": _load_json_object(sources_path),
		"world_manifest_path": world_manifest_path,
	}


static func validate_bundle(bundle: Dictionary) -> PackedStringArray:
	var errors := PackedStringArray()
	if bundle.is_empty():
		errors.append("AirportPack yüklenemedi")
		return errors

	var world: Dictionary = bundle.get("world", {})
	var runway_document: Dictionary = bundle.get("runways", {})
	var sources: Dictionary = bundle.get("sources", {})
	_validate_version(world, "world.json", errors)
	_validate_version(runway_document, "runways.json", errors)
	_validate_version(sources, "sources.json", errors)

	var world_id := str(world.get("world_id", ""))
	if world_id.is_empty():
		errors.append("world_id eksik")
	if str(runway_document.get("world_id", "")) != world_id:
		errors.append("runways.json world_id eşleşmiyor")
	if str(sources.get("world_id", "")) != world_id:
		errors.append("sources.json world_id eşleşmiyor")

	var origin: Dictionary = world.get("origin", {})
	var geo_reference := make_geo_reference(world)
	if origin.is_empty() or not geo_reference.is_valid_origin():
		errors.append("Geçerli dünya orijini bulunamadı")
	if str(origin.get("horizontal_datum", "")) != "WGS84":
		errors.append("Yalnızca WGS84 yatay datum destekleniyor")
	if str(origin.get("vertical_datum", "")).is_empty():
		errors.append("Dikey datum açıkça belirtilmeli")

	var runways: Array = runway_document.get("runways", [])
	if runways.is_empty():
		errors.append("En az bir pist gerekli")
	for runway_value: Variant in runways:
		if not runway_value is Dictionary:
			errors.append("Pist kaydı JSON nesnesi olmalı")
			continue
		_validate_runway(runway_value, errors)
	return errors


static func make_geo_reference(world: Dictionary) -> GeoReference:
	var origin: Dictionary = world.get("origin", {})
	var geo_reference := GeoReferenceScript.new()
	geo_reference.origin_lat_deg = float(origin.get("lat_deg", NAN))
	geo_reference.origin_lon_deg = float(origin.get("lon_deg", NAN))
	geo_reference.origin_alt_msl_m = float(origin.get("alt_msl_m", NAN))
	return geo_reference


static func runway_geometry(
	runway: Dictionary,
	geo_reference: GeoReference,
	flatten_vertical: bool,
) -> Dictionary:
	var designators: Array = runway.get("designators", [])
	if designators.size() != 2:
		return {}
	var start_designator := str(designators[0])
	var end_designator := str(designators[1])
	var thresholds: Dictionary = runway.get("thresholds", {})
	var start_threshold: Dictionary = thresholds.get(start_designator, {})
	var end_threshold: Dictionary = thresholds.get(end_designator, {})
	if start_threshold.is_empty() or end_threshold.is_empty():
		return {}

	var start := _threshold_to_godot(start_threshold, geo_reference)
	var end := _threshold_to_godot(end_threshold, geo_reference)
	if flatten_vertical:
		start.y = 0.0
		end.y = 0.0

	var horizontal_delta := Vector3(end.x - start.x, 0.0, end.z - start.z)
	var horizontal_length_m := horizontal_delta.length()
	if horizontal_length_m <= 0.0:
		return {}
	var true_bearing_deg := fposmod(
		rad_to_deg(atan2(horizontal_delta.x, -horizontal_delta.z)),
		360.0,
	)
	return {
		"start": start,
		"end": end,
		"center": (start + end) * 0.5,
		"horizontal_length_m": horizontal_length_m,
		"spatial_length_m": start.distance_to(end),
		"computed_true_bearing_deg": true_bearing_deg,
		"width_m": float(runway.get("width_m", 0.0)),
	}


static func runway_quad_corners(geometry: Dictionary) -> PackedVector3Array:
	if geometry.is_empty():
		return PackedVector3Array()
	var start: Vector3 = geometry["start"]
	var end: Vector3 = geometry["end"]
	var width_m: float = geometry["width_m"]
	var horizontal_direction := Vector3(end.x - start.x, 0.0, end.z - start.z).normalized()
	if horizontal_direction.is_zero_approx() or width_m <= 0.0:
		return PackedVector3Array()
	var right := Vector3(-horizontal_direction.z, 0.0, horizontal_direction.x)
	var half_width := width_m * 0.5
	return PackedVector3Array([
		start - right * half_width,
		start + right * half_width,
		end - right * half_width,
		end + right * half_width,
	])


static func _threshold_to_godot(
	threshold: Dictionary,
	geo_reference: GeoReference,
) -> Vector3:
	return geo_reference.geodetic_to_godot(
		float(threshold.get("lat_deg", NAN)),
		float(threshold.get("lon_deg", NAN)),
		float(threshold.get("elevation_msl_m", NAN)),
	)


static func _load_json_object(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}


static func _validate_version(
	document: Dictionary,
	label: String,
	errors: PackedStringArray,
) -> void:
	if int(document.get("format_version", 0)) != SUPPORTED_FORMAT_VERSION:
		errors.append("%s format_version desteklenmiyor" % label)


static func _validate_runway(runway: Dictionary, errors: PackedStringArray) -> void:
	var runway_id := str(runway.get("id", "isimsiz"))
	var designators: Array = runway.get("designators", [])
	if designators.size() != 2:
		errors.append("%s için iki pist designator gerekli" % runway_id)
		return
	if float(runway.get("declared_length_m", 0.0)) <= 0.0:
		errors.append("%s uzunluğu geçersiz" % runway_id)
	if float(runway.get("width_m", 0.0)) <= 0.0:
		errors.append("%s genişliği geçersiz" % runway_id)

	var thresholds: Dictionary = runway.get("thresholds", {})
	for designator_value: Variant in designators:
		var designator := str(designator_value)
		var threshold: Dictionary = thresholds.get(designator, {})
		if threshold.is_empty():
			errors.append("%s eşiği eksik" % designator)
			continue
		var lat := float(threshold.get("lat_deg", NAN))
		var lon := float(threshold.get("lon_deg", NAN))
		var elevation := float(threshold.get("elevation_msl_m", NAN))
		if not is_finite(lat) or lat < -90.0 or lat > 90.0:
			errors.append("%s eşik enlemi geçersiz" % designator)
		if not is_finite(lon) or lon < -180.0 or lon > 180.0:
			errors.append("%s eşik boylamı geçersiz" % designator)
		if not is_finite(elevation):
			errors.append("%s eşik irtifası geçersiz" % designator)
