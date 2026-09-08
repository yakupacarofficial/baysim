class_name DebugCamera
extends Camera3D

## Arazi ve pist dikişini çalışma zamanında incelemek için serbest uçuş kamerası.
##
## Yalnızca aktif (`current`) olduğunda girdi işler; sahnedeki uçuş kamerasıyla
## `F1` ile karşılıklı geçiş yapar. Kontroller ham tuş kodlarıyla okunur çünkü
## projede tanımlı bir InputMap eylemi yoktur; okuma `is_physical_key_pressed`
## ile yapılır, böylece Türkçe F klavyede de WASD fiziksel olarak aynı yerde
## kalır.
##
## Kontroller
##   W/A/S/D      bakış yönünde ileri/geri, yanlara
##   Q/E          dünya dikeyinde aşağı/yukarı
##   Shift        hızlı (varsayılan 50×)
##   Alt          yavaş (varsayılan 0.05×) — dikiş kuşağını incelemek için
##   Sağ tık      basılı tutarken fare ile bakış
##   Tekerlek     FOV ile optik yakınlaştırma
##   F1           uçuş kamerasına geri dön
##   F2           çizim modu: normal / tel kafes / gölgesiz / aşırı çizim

@export_group("Hareket")
## Değiştirici basılı değilken metre/saniye.
@export var base_speed := 30.0
@export var fast_multiplier := 50.0
@export var slow_multiplier := 0.05
## Hızlanma yumuşatması; 0 anında tepki verir.
@export var acceleration := 12.0

@export_group("Bakış")
@export var mouse_sensitivity := 0.15
@export_range(1.0, 89.0, 0.5) var max_pitch_deg := 89.0

@export_group("Zoom")
@export_range(1.0, 179.0, 1.0) var min_fov := 20.0
@export_range(1.0, 179.0, 1.0) var max_fov := 90.0
@export var fov_step := 5.0

@export_group("Entegrasyon")
## F1 ile dönülecek kamera. Boşsa geçiş devre dışı kalır.
@export var flight_camera: Camera3D
@export var toggle_key := KEY_F1
## F2 ile görüntüleme modunu döndürür (tel kafes, aşırı çizim, gölgesiz).
@export var draw_mode_key := KEY_F2
## Konum/FOV/hız okumasını ekrana yaz.
@export var show_readout := true

## Arazi ızgarasını ve pist dikişini incelemek için görüntüleme modları.
const DRAW_MODES: Array[Dictionary] = [
	{"name": "normal", "mode": Viewport.DEBUG_DRAW_DISABLED},
	{"name": "tel kafes", "mode": Viewport.DEBUG_DRAW_WIREFRAME},
	{"name": "gölgesiz", "mode": Viewport.DEBUG_DRAW_UNSHADED},
	{"name": "aşırı çizim", "mode": Viewport.DEBUG_DRAW_OVERDRAW},
]

var _yaw_deg := 0.0
var _pitch_deg := 0.0
var _looking := false
var _velocity := Vector3.ZERO
var _readout: Label
var _draw_mode_index := 0


func _ready() -> void:
	_sync_angles_from_transform()
	fov = clampf(fov, min_fov, max_fov)
	# Tel kafes çizimi ancak motor tel kafes indeksleri üretirse çalışır.
	RenderingServer.set_debug_generate_wireframes(true)
	if show_readout:
		_build_readout()


func _sync_angles_from_transform() -> void:
	## Sahnedeki başlangıç yönelimini koru; aktifleşince kamera zıplamasın.
	_yaw_deg = rad_to_deg(rotation.y)
	_pitch_deg = clampf(rad_to_deg(rotation.x), -max_pitch_deg, max_pitch_deg)


func _notification(what: int) -> void:
	# Pencere odağı giderken fare yakalamayı bırak, yoksa imleç kaybolur.
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_WM_WINDOW_FOCUS_OUT:
		_set_looking(false)


func _exit_tree() -> void:
	_set_looking(false)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == toggle_key:
			_toggle()
			get_viewport().set_input_as_handled()
			return
		if current and event.keycode == draw_mode_key:
			_cycle_draw_mode()
			get_viewport().set_input_as_handled()
			return
		# Uçuş kamerası tuşlarına basıldıysa kontrolü ona devret. Olay
		# tüketilmez; camera_rig.gd aynı basışta kendi modunu seçer.
		if current and event.keycode in [KEY_1, KEY_2, KEY_3]:
			_deactivate()
			return

	if not current:
		return

	if event is InputEventMouseButton:
		match event.button_index:
			MOUSE_BUTTON_RIGHT:
				_set_looking(event.pressed)
				get_viewport().set_input_as_handled()
			MOUSE_BUTTON_WHEEL_UP:
				if event.pressed:
					_zoom(-fov_step)
					get_viewport().set_input_as_handled()
			MOUSE_BUTTON_WHEEL_DOWN:
				if event.pressed:
					_zoom(fov_step)
					get_viewport().set_input_as_handled()
	elif event is InputEventMouseMotion and _looking:
		_yaw_deg -= event.relative.x * mouse_sensitivity
		_pitch_deg = clampf(
			_pitch_deg - event.relative.y * mouse_sensitivity,
			-max_pitch_deg,
			max_pitch_deg,
		)
		_apply_rotation()


func _process(delta: float) -> void:
	if not current:
		if _readout != null:
			_readout.visible = false
		return

	var target_velocity := _input_direction() * _current_speed()
	# Üstel yumuşatma: kare hızından bağımsız, fdm_link.gd ile aynı yaklaşım.
	if acceleration > 0.0:
		_velocity = _velocity.lerp(target_velocity, 1.0 - exp(-acceleration * delta))
	else:
		_velocity = target_velocity
	global_position += _velocity * delta

	if _readout != null:
		_readout.visible = true
		_readout.text = _readout_text()


func _input_direction() -> Vector3:
	var direction := Vector3.ZERO
	# Godot'ta -Z ileridir; yatay eksenler kameranın kendi tabanından gelir.
	if Input.is_physical_key_pressed(KEY_W):
		direction -= global_basis.z
	if Input.is_physical_key_pressed(KEY_S):
		direction += global_basis.z
	if Input.is_physical_key_pressed(KEY_A):
		direction -= global_basis.x
	if Input.is_physical_key_pressed(KEY_D):
		direction += global_basis.x
	# Dikey hareket bakıştan bağımsız, dünya dikeyinde.
	if Input.is_physical_key_pressed(KEY_E):
		direction += Vector3.UP
	if Input.is_physical_key_pressed(KEY_Q):
		direction -= Vector3.UP
	return direction.normalized() if direction.length_squared() > 0.0 else Vector3.ZERO


func _current_speed() -> float:
	var speed := base_speed
	if Input.is_physical_key_pressed(KEY_SHIFT):
		speed *= fast_multiplier
	if Input.is_physical_key_pressed(KEY_ALT):
		speed *= slow_multiplier
	return speed


func _apply_rotation() -> void:
	# YXZ sırası: önce yaw, sonra pitch. Roll birikmez.
	global_basis = Basis.from_euler(
		Vector3(deg_to_rad(_pitch_deg), deg_to_rad(_yaw_deg), 0.0)
	)


func _zoom(amount: float) -> void:
	fov = clampf(fov + amount, min_fov, max_fov)


func _set_looking(enabled: bool) -> void:
	if _looking == enabled:
		return
	_looking = enabled
	Input.mouse_mode = (
		Input.MOUSE_MODE_CAPTURED if enabled else Input.MOUSE_MODE_VISIBLE
	)


func _toggle() -> void:
	if current:
		_deactivate()
		return
	_sync_angles_from_transform()
	make_current()


func _cycle_draw_mode() -> void:
	_draw_mode_index = (_draw_mode_index + 1) % DRAW_MODES.size()
	get_viewport().debug_draw = DRAW_MODES[_draw_mode_index]["mode"]


func _deactivate() -> void:
	_set_looking(false)
	_velocity = Vector3.ZERO
	# Uçuş görünümü hata ayıklama çizimiyle bırakılmamalı.
	_draw_mode_index = 0
	get_viewport().debug_draw = Viewport.DEBUG_DRAW_DISABLED
	if flight_camera != null:
		flight_camera.make_current()
	elif current:
		push_warning("DebugCamera: flight_camera atanmadı, geçilecek kamera yok")


# --- Ekran okuması ------------------------------------------------------


func _build_readout() -> void:
	var layer := CanvasLayer.new()
	layer.name = "DebugCameraReadout"
	# HUD'un üstünde kalsın.
	layer.layer = 10
	add_child(layer)

	_readout = Label.new()
	_readout.position = Vector2(16.0, 16.0)
	_readout.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_readout.add_theme_font_size_override("font_size", 14)
	_readout.add_theme_color_override("font_color", Color(1.0, 0.85, 0.4))
	_readout.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_readout.add_theme_constant_override("outline_size", 4)
	_readout.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_readout.offset_left = -260.0
	_readout.offset_right = -16.0
	_readout.offset_top = 16.0
	layer.add_child(_readout)


func _readout_text() -> String:
	# Sahne ekseni east=+X, up=+Y, north=-Z. Okuma ENU olarak gösterilir ki
	# world_builder ve manifest değerleriyle doğrudan karşılaştırılabilsin.
	var east := global_position.x
	var up := global_position.y
	var north := -global_position.z
	var horizontal_m := Vector2(east, north).length()

	var speed_label := "normal"
	if Input.is_physical_key_pressed(KEY_SHIFT):
		speed_label = "HIZLI"
	elif Input.is_physical_key_pressed(KEY_ALT):
		speed_label = "yavaş"

	return "\n".join([
		"SERBEST KAMERA",
		"",
		"DOĞU     %9.1f m" % east,
		"KUZEY    %9.1f m" % north,
		"YUKARI   %9.1f m" % up,
		"ORİJİNE  %9.1f m" % horizontal_m,
		"",
		"FOV      %9.1f°" % fov,
		"HIZ      %9.1f m/s" % _velocity.length(),
		"MOD      %9s" % speed_label,
		"ÇİZİM    %9s" % str(DRAW_MODES[_draw_mode_index]["name"]),
		"",
		"F1 uçuş · F2 çizim",
	])
