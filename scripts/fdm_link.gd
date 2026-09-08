extends Node3D

## JSBSim koprusunden gelen telemetriyi okur, ucaga uygular ve
## HUD'in okuyabilecegi bir sozlukte saklar.

const GeoReferenceResource := preload("res://scripts/geo_reference.gd")

@export var port := 5005
@export var runway_surface_y := 0.3
@export var smooth := 25.0
@export var connection_timeout_s := 1.0

enum PositionSource { LOCAL_NORTH_EAST, GEODETIC_WGS84 }

@export_group("World Georeference")
@export var position_source: PositionSource = PositionSource.LOCAL_NORTH_EAST
@export var world_origin: GeoReferenceResource

const FIELDS := [
	"north_m", "east_m", "alt_msl_m", "phi_rad",
	"theta_rad", "psi_rad", "ias_kts", "agl_m",
	"lat_deg", "lon_deg", "tas_kts", "gs_kts",
	"vs_mps", "alpha_deg", "beta_deg", "throttle",
	"rpm", "nz", "sim_time_s", "mode",
]

var tel := {}
var connected := false
var invalid_packet_count := 0

var _udp := PacketPeerUDP.new()
var _target_pos := Vector3.ZERO
var _target_quat := Quaternion.IDENTITY
var _got_first := false
var _last_packet_time := 0.0

func _ready() -> void:
	if _udp.bind(port) != OK:
		push_error("UDP portu acilamadi: %d" % port)
	if position_source == PositionSource.GEODETIC_WGS84:
		if world_origin == null or not world_origin.is_valid_origin():
			push_error("WGS84 konum modu icin gecerli bir world_origin gerekli")

func _process(delta: float) -> void:
	while _udp.get_available_packet_count() > 0:
		var packet := _udp.get_packet().get_string_from_utf8()
		_consume_packet(packet, Time.get_ticks_msec() / 1000.0)

	connected = (
		_got_first
		and (Time.get_ticks_msec() / 1000.0) - _last_packet_time < connection_timeout_s
	)

	if not _got_first:
		return

	var t := 1.0 - exp(-smooth * delta)
	position = position.lerp(_target_pos, t)
	quaternion = quaternion.slerp(_target_quat, t)

func _consume_packet(packet: String, received_at_s: float) -> bool:
	if not _parse(packet):
		invalid_packet_count += 1
		return false
	_last_packet_time = received_at_s
	return true

func _parse(line: String) -> bool:
	var f := line.split(",")
	if f.size() < FIELDS.size():
		return false

	# Paketi once gecici bir sozlukte dogrula. Boylece yarim veya bozuk bir
	# datagram onceki gecerli telemetriyi kismen ezemez.
	var next_tel := {}
	for i in range(FIELDS.size()):
		var raw_value := f[i].strip_edges()
		if not raw_value.is_valid_float():
			return false
		var value := raw_value.to_float()
		if not is_finite(value):
			return false
		next_tel[FIELDS[i]] = value

	if position_source == PositionSource.GEODETIC_WGS84:
		if world_origin == null or not world_origin.is_valid_origin():
			return false

	tel = next_tel

	var north: float = tel["north_m"]
	var east: float = tel["east_m"]
	var alt: float = tel["alt_msl_m"]
	var phi: float = tel["phi_rad"]
	var theta: float = tel["theta_rad"]
	var psi: float = tel["psi_rad"]

	if position_source == PositionSource.GEODETIC_WGS84:
		_target_pos = world_origin.geodetic_to_godot(
			tel["lat_deg"],
			tel["lon_deg"],
			alt,
		)
		_target_pos.y += runway_surface_y
	else:
		var origin_alt_msl_m := 0.0
		if world_origin != null:
			origin_alt_msl_m = world_origin.origin_alt_msl_m
		_target_pos = Vector3(
			east,
			alt - origin_alt_msl_m + runway_surface_y,
			-north,
		)
	_target_quat = Quaternion.from_euler(Vector3(theta, -psi, -phi))

	if not _got_first:
		_got_first = true
		position = _target_pos
		quaternion = _target_quat

	return true
