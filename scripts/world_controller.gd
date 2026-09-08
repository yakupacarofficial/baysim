extends Node3D

## Python launcher tarafindan uretilen runtime ayarlarini ana sahneye uygular.

const FdmLinkScript := preload("res://scripts/fdm_link.gd")
const DEFAULT_CONFIG_PATH := "res://runtime/launcher_config.json"
const CONFIG_ARGUMENT := "--baysim-config="


func _enter_tree() -> void:
	var config_path := _config_path_from_arguments()
	if config_path == "" or not FileAccess.file_exists(config_path):
		return

	var config := _load_config(config_path)
	if config.is_empty():
		return
	if int(config.get("config_version", 0)) != 1:
		push_error("Desteklenmeyen launcher config_version")
		return

	_apply_aircraft_config(config)
	call_deferred("_apply_display_config", config)
	print("BAYSIM launcher ayarlari uygulandi: %s" % config_path)


func _config_path_from_arguments() -> String:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with(CONFIG_ARGUMENT):
			return argument.trim_prefix(CONFIG_ARGUMENT)
	if FileAccess.file_exists(DEFAULT_CONFIG_PATH):
		return DEFAULT_CONFIG_PATH
	return ""


func _load_config(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("Launcher ayar dosyasi acilamadi: %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		push_error("Launcher ayar dosyasi gecerli JSON nesnesi degil: %s" % path)
		return {}
	return parsed


func _apply_aircraft_config(config: Dictionary) -> void:
	var aircraft := get_node_or_null("Aircraft")
	if aircraft == null:
		push_error("Launcher ayarlari uygulanamadi: Aircraft node'u bulunamadi")
		return

	var telemetry: Dictionary = config.get("telemetry", {})
	aircraft.port = clampi(int(telemetry.get("port", aircraft.port)), 1, 65535)
	aircraft.connection_timeout_s = maxf(
		float(telemetry.get("connection_timeout_s", aircraft.connection_timeout_s)),
		0.001,
	)
	aircraft.smooth = maxf(float(telemetry.get("smoothing", aircraft.smooth)), 0.0)

	var position: Dictionary = config.get("position", {})
	var source := str(position.get("source", "local"))
	aircraft.position_source = (
		FdmLinkScript.PositionSource.GEODETIC_WGS84
		if source == "wgs84"
		else FdmLinkScript.PositionSource.LOCAL_NORTH_EAST
	)

	var origin_config: Dictionary = config.get("world_origin", {})
	if aircraft.world_origin != null:
		aircraft.world_origin.origin_lat_deg = float(origin_config.get(
			"lat_deg", aircraft.world_origin.origin_lat_deg
		))
		aircraft.world_origin.origin_lon_deg = float(origin_config.get(
			"lon_deg", aircraft.world_origin.origin_lon_deg
		))
		aircraft.world_origin.origin_alt_msl_m = float(origin_config.get(
			"alt_msl_m", aircraft.world_origin.origin_alt_msl_m
		))


func _apply_display_config(config: Dictionary) -> void:
	var display: Dictionary = config.get("display", {})
	var fullscreen := bool(display.get("fullscreen", false))
	if fullscreen:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
		return

	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	var width := maxi(int(display.get("width", 1600)), 800)
	var height := maxi(int(display.get("height", 900)), 600)
	DisplayServer.window_set_size(Vector2i(width, height))
