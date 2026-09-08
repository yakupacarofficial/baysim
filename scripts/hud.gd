extends Label

## Ucus verilerini ekrana yazar. Bir Label node'una baglanir,
## Aircraft alanina fdm_link.gd tasiyan node surüklenir.

@export var aircraft: Node3D

func _ready() -> void:
	add_theme_font_size_override("font_size", 16)
	add_theme_color_override("font_color", Color(0.6, 1.0, 0.6))
	add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	add_theme_constant_override("outline_size", 4)

func _process(_delta: float) -> void:
	if aircraft == null:
		text = "Aircraft atanmadi"
		return

	if not aircraft.connected:
		text = "JSBSim telemetrisi bekleniyor\nUDP portu: %d" % aircraft.port
		return

	var t: Dictionary = aircraft.tel
	if t.is_empty():
		return

	var hdg := fmod(rad_to_deg(t["psi_rad"]) + 360.0, 360.0)
	var mode_value := int(t["mode"])
	var mode_txt: String
	match mode_value:
		0: mode_txt = "TIRMANIS"
		1: mode_txt = "DAIRE"
		_: mode_txt = "BILINMEYEN (%d)" % mode_value

	text = "\n".join([
		"  MOD      %s" % mode_txt,
		"  SURE     %6.1f s" % t["sim_time_s"],
		"",
		"  IAS      %6.1f kt" % t["ias_kts"],
		"  TAS      %6.1f kt" % t["tas_kts"],
		"  GS       %6.1f kt" % t["gs_kts"],
		"  VS       %+6.1f m/s" % t["vs_mps"],
		"",
		"  IRTIFA   %6.0f m MSL" % t["alt_msl_m"],
		"  AGL      %6.0f m" % t["agl_m"],
		"",
		"  ENLEM    %10.6f" % t["lat_deg"],
		"  BOYLAM   %10.6f" % t["lon_deg"],
		"  KUZEY    %8.0f m" % t["north_m"],
		"  DOGU     %8.0f m" % t["east_m"],
		"",
		"  ROTA     %6.1f" % hdg,
		"  YUNUS    %+6.1f" % rad_to_deg(t["theta_rad"]),
		"  YATIS    %+6.1f" % rad_to_deg(t["phi_rad"]),
		"  ALFA     %+6.1f" % t["alpha_deg"],
		"  BETA     %+6.1f" % t["beta_deg"],
		"",
		"  GAZ      %6.0f %%" % (t["throttle"] * 100.0),
		"  DEVIR    %6.0f rpm" % t["rpm"],
		"  NZ       %+6.2f g" % t["nz"],
	])
