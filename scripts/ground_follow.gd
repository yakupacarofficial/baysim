extends MeshInstance3D

@export var target: Node3D
@export var tile_size := 4.0

func _process(_delta: float) -> void:
	if target == null:
		return
	var p := target.global_position
	global_position = Vector3(
		snappedf(p.x, tile_size),
		0.0,
		snappedf(p.z, tile_size)
	)
