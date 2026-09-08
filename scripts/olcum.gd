extends Node3D

func _ready() -> void:
	var aabb := AABB()
	var first := true
	for m in find_children("*", "MeshInstance3D", true):
		var a: AABB = m.global_transform * m.get_aabb()
		if first:
			aabb = a
			first = false
		else:
			aabb = aabb.merge(a)
	print("Genislik (kanat aciklıgı) X: %.2f m" % aabb.size.x)
	print("Yukseklik Y: %.2f m" % aabb.size.y)
	print("Uzunluk Z: %.2f m" % aabb.size.z)
	print("Alt kenar Y: %.2f m" % aabb.position.y)
