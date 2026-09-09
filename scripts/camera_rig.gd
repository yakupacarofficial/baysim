extends Camera3D

@export var target: Node3D

@export var chase_offset := Vector3(0, 20, 45)
@export var chase_smooth := 4.0
@export var cockpit_offset := Vector3(0, 0.5, -2.5)
@export var tail_offset := Vector3(0, 1.5, 4.0)

enum Mode { CHASE, COCKPIT, TAIL }
var mode: Mode = Mode.CHASE

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_1: mode = Mode.CHASE
			KEY_2: mode = Mode.COCKPIT
			KEY_3: mode = Mode.TAIL

func _process(delta: float) -> void:
	if target == null:
		return

	match mode:
		Mode.CHASE:
			var yaw_basis := Basis(Vector3.UP, target.global_rotation.y)
			var desired := target.global_position + yaw_basis * chase_offset
			var t := 1.0 - exp(-chase_smooth * delta)
			global_position = global_position.lerp(desired, t)
			var dir := (target.global_position - global_position).normalized()
			var up := Vector3.UP
			if abs(dir.dot(up)) > 0.999:
				up = Vector3.FORWARD
			look_at(target.global_position, up)

		Mode.COCKPIT:
			global_transform = target.global_transform * Transform3D(Basis(), cockpit_offset)

		Mode.TAIL:
			global_transform = target.global_transform * Transform3D(Basis(), tail_offset)
