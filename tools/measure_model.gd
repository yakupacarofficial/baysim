@tool
extends EditorScript

## Bir görsel model sahnesinin birleşik AABB'sini ölçer. Yeni bir uçak modeli
## eklerken kanat açıklığı, uzunluk ve teker temas ofseti için kullanılır.
##
## Kullanım: ölçülecek sahneyi editörde aç ve Dosya > Çalıştır ile bu scripti
## çalıştır. Açık sahne yoksa TB-2 paketi ölçülür.

const FALLBACK_SCENE := "res://models/TB-2/aircraft.tscn"


func _run() -> void:
	var root := get_scene()
	var owns_root := false
	if root == null:
		var packed: PackedScene = load(FALLBACK_SCENE)
		if packed == null:
			push_error("measure_model: sahne yüklenemedi: %s" % FALLBACK_SCENE)
			return
		root = packed.instantiate()
		owns_root = true

	var meshes := root.find_children("*", "MeshInstance3D", true, false)
	if meshes.is_empty():
		push_warning("measure_model: MeshInstance3D bulunamadı (%s)" % root.name)
		if owns_root:
			root.free()
		return

	var aabb := AABB()
	var first := true
	for mesh_node: MeshInstance3D in meshes:
		var world_aabb: AABB = mesh_node.global_transform * mesh_node.get_aabb()
		if first:
			aabb = world_aabb
			first = false
		else:
			aabb = aabb.merge(world_aabb)

	print_rich("[b]measure_model: %s[/b]" % root.name)
	print("  Genişlik (kanat açıklığı) X : %.3f m" % aabb.size.x)
	print("  Yükseklik Y                 : %.3f m" % aabb.size.y)
	print("  Uzunluk Z                   : %.3f m" % aabb.size.z)
	print("  Alt kenar Y (teker ofseti)  : %.3f m" % aabb.position.y)

	if owns_root:
		root.free()
