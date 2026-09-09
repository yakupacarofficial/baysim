class_name TerrainTile
extends MeshInstance3D

## world_builder'ın ürettiği arazi tile'ını yükleyip mesh'e çevirir.
##
## Tile, düzenli bir yerel ENU metre ızgarasıdır. Bu yüzden burada hiç
## jeodezi hesabı yoktur: düğüm konumu doğrudan ızgara adımından gelir ve
## yükseklikler zaten dünya orijinine göre ENU "up" cinsindendir. Pist
## geometrisi de aynı çerçevede üretildiği için ikisi otomatik hizalanır.

const MANIFEST_FORMAT_VERSION := 1

@export_file("*.json") var manifest_path := "res://worlds/LTBU/terrain/manifest.json"
## Boş bırakılırsa manifestteki ilk tile kullanılır.
@export var tile_id := ""
## Her N. örneği al. 1 tam çözünürlüktür.
##
## Dikkat: seyreltme, pistin dikildiği koridoru da seyreltir. 45 m genişliğinde
## bir pistin düzleştirilmiş koridoru ~165 m'dir; 30 m adımlı bir tile'da
## `lod_step = 4` ızgarayı 120 m'ye çıkarır ve koridor artık örneklenemez —
## arazi pistin üstünden geçer. Havalimanı çevresinde 1 kullanılmalıdır.
## Ölçüm: 1001 × 1001 tile, lod 1'de 1M düğüm, ~630 ms kurulum, entegre GPU'da
## ~56 fps. Kamera çevresinde gerçek tile/LOD yaşam döngüsü Faz 6'nın konusudur.
@export_range(1, 32, 1) var lod_step := 1
@export var build_on_ready := true

@export_group("Ortofoto")
## Manifestte ortofoto varsa yükleyip araziye giydir.
@export var use_imagery := true
## Ortofoto bulunamazsa sahnedeki mevcut malzeme korunur.
@export var imagery_roughness := 0.95

var tile_info: Dictionary = {}
var imagery_info: Dictionary = {}


func _ready() -> void:
	if build_on_ready:
		rebuild()


func rebuild() -> bool:
	tile_info = {}
	mesh = null

	var manifest := _load_manifest()
	if manifest.is_empty():
		return false

	var described := _select_tile(manifest)
	if described.is_empty():
		return false

	var heights := _load_heights(described)
	if heights.is_empty():
		return false

	var width := int(described["width"])
	var height := int(described["height"])
	mesh = _build_mesh(heights, width, height, float(described["grid"]["step_m"]),
		float(described["grid"]["east_min_m"]), float(described["grid"]["north_max_m"]))
	if mesh == null:
		return false

	tile_info = described
	print("Arazi tile'ı yüklendi: %s (%d x %d, lod %d)" % [
		str(described.get("tile_id", "?")), width, height, lod_step,
	])

	if use_imagery:
		_apply_imagery(manifest)
	return true


func _apply_imagery(manifest: Dictionary) -> void:
	## Ortofoto varsa araziye giydirir. Yoksa sahnedeki malzemeye dokunmaz;
	## görüntü henüz üretilmemişken çim dokusu çalışmaya devam etmeli.
	imagery_info = {}
	var described: Variant = manifest.get("imagery")
	if not described is Dictionary or (described as Dictionary).is_empty():
		return

	var imagery: Dictionary = described
	var texture_path := manifest_path.get_base_dir().path_join(
		str(imagery.get("file", ""))
	)
	if not ResourceLoader.exists(texture_path):
		push_warning("Ortofoto manifestte var ama dosya yüklenemiyor: %s" % texture_path)
		return

	var texture: Texture2D = load(texture_path)
	if texture == null:
		push_warning("Ortofoto dokusu okunamadı: %s" % texture_path)
		return

	var material := StandardMaterial3D.new()
	material.albedo_texture = texture
	# Doku tile'ın tamamına birebir oturur; UV zaten 0..1 normalize.
	material.uv1_scale = Vector3.ONE
	# Kenarda tekrar etmesin, ufukta tile'ın aynası görünmesin.
	material.texture_repeat = false
	# Anizotropik filtreleme eğik açılarda pikselleşmeyi büyük ölçüde azaltır.
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.roughness = imagery_roughness
	material.metallic = 0.0
	material_override = material

	imagery_info = imagery
	print("Ortofoto giydirildi: %s (%d x %d, %.0f m/piksel)" % [
		str(imagery.get("tile_id", "?")),
		int(imagery.get("width", 0)),
		int(imagery.get("height", 0)),
		float(imagery.get("pixel_m", 0.0)),
	])


func _load_manifest() -> Dictionary:
	if not FileAccess.file_exists(manifest_path):
		push_error("Arazi manifesti bulunamadı: %s" % manifest_path)
		return {}
	var file := FileAccess.open(manifest_path, FileAccess.READ)
	if file == null:
		push_error("Arazi manifesti açılamadı: %s" % manifest_path)
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		push_error("Arazi manifesti geçerli JSON nesnesi değil: %s" % manifest_path)
		return {}
	var manifest: Dictionary = parsed
	if int(manifest.get("format_version", 0)) != MANIFEST_FORMAT_VERSION:
		push_error("Desteklenmeyen arazi manifesti sürümü")
		return {}
	return manifest


func _select_tile(manifest: Dictionary) -> Dictionary:
	var tiles: Array = manifest.get("tiles", [])
	if tiles.is_empty():
		push_error("Arazi manifestinde hiç tile yok")
		return {}
	for entry: Variant in tiles:
		if entry is Dictionary and (tile_id.is_empty() or str(entry.get("tile_id", "")) == tile_id):
			return entry
	push_error("Arazi tile'ı bulunamadı: %s" % tile_id)
	return {}


func _load_heights(described: Dictionary) -> PackedFloat32Array:
	if str(described.get("sample_format", "")) != "float32_le":
		push_error("Desteklenmeyen örnek biçimi: %s" % str(described.get("sample_format", "")))
		return PackedFloat32Array()
	if str(described.get("row_order", "")) != "north_to_south":
		push_error("Desteklenmeyen satır sırası: %s" % str(described.get("row_order", "")))
		return PackedFloat32Array()

	var data_path := manifest_path.get_base_dir().path_join(str(described.get("file", "")))
	if not FileAccess.file_exists(data_path):
		push_error("Arazi verisi bulunamadı: %s" % data_path)
		return PackedFloat32Array()
	var file := FileAccess.open(data_path, FileAccess.READ)
	if file == null:
		push_error("Arazi verisi açılamadı: %s" % data_path)
		return PackedFloat32Array()

	var expected_bytes := int(described["width"]) * int(described["height"]) * 4
	if int(file.get_length()) != expected_bytes:
		push_error("Arazi verisi boyutu manifestle uyuşmuyor: %d != %d" % [
			file.get_length(), expected_bytes,
		])
		return PackedFloat32Array()

	# Godot hedef platformlarının tamamı little-endian; dosya da <f4 yazıldı.
	return file.get_buffer(expected_bytes).to_float32_array()


func _build_mesh(
	heights: PackedFloat32Array,
	width: int,
	height: int,
	step_m: float,
	east_min_m: float,
	north_max_m: float,
) -> ArrayMesh:
	var step := maxi(lod_step, 1)
	var columns := (width - 1) / step + 1
	var rows := (height - 1) / step + 1
	if columns < 2 or rows < 2:
		push_error("LOD adımı tile için fazla büyük")
		return null

	var extent_m := float(width - 1) * step_m
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	vertices.resize(columns * rows)
	normals.resize(columns * rows)
	uvs.resize(columns * rows)

	for row in range(rows):
		var source_row := row * step
		for column in range(columns):
			var source_column := column * step
			var index := row * columns + column
			var elevation := heights[source_row * width + source_column]
			# Godot: x=east, y=up, z=-north. Satır 0 kuzeydedir.
			var east_m := east_min_m + float(source_column) * step_m
			var south_m := -north_max_m + float(source_row) * step_m
			vertices[index] = Vector3(east_m, elevation, south_m)
			# UV, tile içindeki normalize konumdur (0..1). Satır 0 kuzey, sütun
			# 0 batı olduğu için ızgara oranı doğrudan UV'dir; ortofoto da aynı
			# ENU karesine üretildiğinden `uv1_scale = 1` ile birebir oturur.
			# Tekrarlayan detay dokuları uv1_scale'i büyüterek döşenir. LOD
			# adımı değişse de ölçek kaymaz.
			uvs[index] = Vector2(
				float(source_column) * step_m / extent_m,
				float(source_row) * step_m / extent_m,
			)
			normals[index] = _grid_normal(
				heights, width, height, source_column, source_row, step, step_m
			)

	var indices := PackedInt32Array()
	indices.resize((columns - 1) * (rows - 1) * 6)
	var cursor := 0
	for row in range(rows - 1):
		for column in range(columns - 1):
			var top_left := row * columns + column
			var top_right := top_left + 1
			var bottom_left := top_left + columns
			var bottom_right := bottom_left + 1
			# Godot ön yüz için SAAT YÖNÜ sarımı kullanır: sağ-el kuralıyla
			# hesaplanan normal, görünen yüzün TERSİNE bakar. Yukarı bakan bir
			# yüzey için sağ-el normali -Y olmalıdır. Ters sarım, araziyi
			# yukarıdan tamamen görünmez yapar.
			indices[cursor] = top_left
			indices[cursor + 1] = top_right
			indices[cursor + 2] = bottom_left
			indices[cursor + 3] = top_right
			indices[cursor + 4] = bottom_right
			indices[cursor + 5] = bottom_left
			cursor += 6

	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = indices

	var array_mesh := ArrayMesh.new()
	array_mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return array_mesh


func _grid_normal(
	heights: PackedFloat32Array,
	width: int,
	height: int,
	column: int,
	row: int,
	step: int,
	step_m: float,
) -> Vector3:
	## Merkezî farklardan yüzey normali. Kenarlarda tek taraflı farka düşer.
	##
	## Godot eksenlerinde çalışır: sütun artışı +X (doğu), satır artışı +Z
	## (güney). y = g(x, z) yükseklik alanının normali (-dg/dx, 1, -dg/dz).
	var west_column := maxi(column - step, 0)
	var east_column := mini(column + step, width - 1)
	var north_row := maxi(row - step, 0)
	var south_row := mini(row + step, height - 1)

	var x_span := float(east_column - west_column) * step_m
	var z_span := float(south_row - north_row) * step_m
	if x_span <= 0.0 or z_span <= 0.0:
		return Vector3.UP

	var slope_x := (
		heights[row * width + east_column] - heights[row * width + west_column]
	) / x_span
	var slope_z := (
		heights[south_row * width + column] - heights[north_row * width + column]
	) / z_span
	return Vector3(-slope_x, 1.0, -slope_z).normalized()
