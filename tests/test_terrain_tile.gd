extends SceneTree

## Arazi tile'ının manifestle tutarlı yüklendiğini ve ızgara geometrisinin
## world_builder'ın yazdığı ENU çerçevesine oturduğunu doğrular.

const TerrainTileScript := preload("res://scripts/world/terrain_tile.gd")
const MANIFEST := "res://worlds/LTBU/terrain/manifest.json"


func _init() -> void:
	if not FileAccess.file_exists(MANIFEST):
		print("test_terrain_tile: OK (arazi tile'ı üretilmemiş, atlandı)")
		quit()
		return

	var described := _first_tile()
	assert(not described.is_empty(), "Manifestte tile yok")

	var terrain := TerrainTileScript.new()
	terrain.build_on_ready = false
	terrain.manifest_path = MANIFEST
	terrain.lod_step = 8
	root.add_child(terrain)
	assert(terrain.rebuild(), "Arazi tile'ı yüklenemedi")
	assert(terrain.mesh != null)
	assert(terrain.mesh.get_surface_count() == 1)

	var width := int(described["width"])
	var height := int(described["height"])
	var step_m := float(described["grid"]["step_m"])
	var radius_m := float(described["grid"]["radius_m"])

	# LOD adimi 8 icin beklenen dugum sayisi
	var columns := (width - 1) / 8 + 1
	var rows := (height - 1) / 8 + 1
	var arrays := terrain.mesh.surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	assert(vertices.size() == columns * rows,
		"Beklenen %d düğüm, bulunan %d" % [columns * rows, vertices.size()])
	assert(indices.size() == (columns - 1) * (rows - 1) * 6)

	# Izgara, orijin cevresinde +-radius kadar simetrik olmali.
	var first := vertices[0]
	var last := vertices[vertices.size() - 1]
	assert(absf(first.x + radius_m) <= 0.001,
		"Batı kenarı %f, beklenen %f" % [first.x, -radius_m])
	assert(absf(first.z + radius_m) <= 0.001,
		"Kuzey kenarı %f, beklenen %f" % [first.z, -radius_m])
	# Son dugum LOD adimi yuzunden tam koseye denk gelmeyebilir.
	var expected_last_x := -radius_m + float((columns - 1) * 8) * step_m
	var expected_last_z := -radius_m + float((rows - 1) * 8) * step_m
	assert(absf(last.x - expected_last_x) <= 0.001)
	assert(absf(last.z - expected_last_z) <= 0.001)

	# Yukseklikler manifestteki araliga sigmali.
	var minimum := float(described["enu_up_min_m"])
	var maximum := float(described["enu_up_max_m"])
	for vertex in vertices:
		assert(vertex.y >= minimum - 0.001 and vertex.y <= maximum + 0.001,
			"Yükseklik aralık dışı: %f" % vertex.y)

	# Normaller yukari bakmali; ters sarim veya isaret hatasi burada yakalanir.
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	assert(normals.size() == vertices.size())
	for normal in normals:
		assert(normal.y > 0.0, "Aşağı bakan normal: %s" % normal)
		assert(absf(normal.length() - 1.0) <= 0.001)

	# Sarim yonu. Godot on yuz icin SAAT YONU sarimi kullanir: sag-el
	# kuraliyla hesaplanan (b-a)x(c-a) normali, GORUNEN yuzun tersine bakar.
	# Yukari bakan arazi icin bu carpim -Y olmalidir. Ters sarim, araziyi
	# yukaridan tamamen gorunmez yapar ve geriye yalnizca gokyuzunun yesil
	# zemin rengi kalir.
	for triangle in range(0, indices.size(), 3):
		var a := vertices[indices[triangle]]
		var b := vertices[indices[triangle + 1]]
		var c := vertices[indices[triangle + 2]]
		assert((b - a).cross(c - a).y < 0.0,
			"Ters sarımlı üçgen: %d" % triangle)

	# Bilinmeyen tile kimligi hata vermeli, sessizce ilk tile'a dusmemeli.
	terrain.tile_id = "boyle-bir-tile-yok"
	assert(not terrain.rebuild())

	print("test_terrain_tile: OK")
	quit()


func _first_tile() -> Dictionary:
	var file := FileAccess.open(MANIFEST, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		return {}
	var tiles: Array = parsed.get("tiles", [])
	return tiles[0] if not tiles.is_empty() else {}
