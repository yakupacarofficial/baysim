extends SceneTree

const GeoReferenceScript := preload("res://scripts/geo_reference.gd")
const FdmLink := preload("res://scripts/fdm_link.gd")


func _init() -> void:
	var fdm := FdmLink.new()

	# Uygulama acilisinda, ilk gecerli paket gelmeden baglanti var denmemeli.
	fdm._process(0.0)
	assert(not fdm.connected)

	# Eksik paketler telemetri durumunu degistirmemeli.
	assert(not fdm._parse("10,20,100,0.1,0.2,0.3"))
	assert(fdm.tel.is_empty())

	var valid_packet := (
		"10,20,100,0.1,0.2,0.3,90,50,40,30,100,95,-2,3,4,0.75,2200,1.1,12.5,1"
	)
	assert(fdm._parse(valid_packet))
	assert(fdm.tel.size() == fdm.FIELDS.size())
	assert(fdm.tel["ias_kts"] == 90.0)
	assert(fdm.position.is_equal_approx(Vector3(20.0, 100.3, -10.0)))

	# Sayisal olmayan deger tum paketi gecersiz kilmali ve son iyi durum korunmali.
	var previous_tel := fdm.tel.duplicate()
	var malformed_packet := valid_packet.replace("0.75", "bozuk")
	assert(not fdm._parse(malformed_packet))
	assert(fdm.tel == previous_tel)

	# Bozuk paket baglanti zamanini yenilememeli.
	assert(fdm._consume_packet(valid_packet, 10.0))
	assert(fdm.get("_last_packet_time") == 10.0)
	assert(not fdm._consume_packet("gecersiz,paket", 20.0))
	assert(fdm.get("_last_packet_time") == 10.0)
	assert(fdm.invalid_packet_count == 1)

	fdm.free()

	# Yerel N/E akisi da MSL irtifasini dunya orijinine gore sifirlamali.
	var local_origin := GeoReferenceScript.new()
	local_origin.origin_alt_msl_m = 99.0
	var local_fdm := FdmLink.new()
	local_fdm.world_origin = local_origin
	assert(local_fdm._parse(valid_packet))
	assert(local_fdm.position.is_equal_approx(Vector3(20.0, 1.3, -10.0)))
	local_fdm.free()

	# WGS84 modunda north/east alanlari yerine lat/lon ve MSL kullanilmali.
	var geodetic_origin := GeoReferenceScript.new()
	geodetic_origin.origin_lat_deg = 40.0
	geodetic_origin.origin_lon_deg = 30.0
	geodetic_origin.origin_alt_msl_m = 99.0
	var geodetic_fdm := FdmLink.new()
	geodetic_fdm.position_source = FdmLink.PositionSource.GEODETIC_WGS84
	geodetic_fdm.world_origin = geodetic_origin
	assert(geodetic_fdm._parse(valid_packet))
	assert(geodetic_fdm.position.is_equal_approx(Vector3(0.0, 1.3, 0.0)))
	geodetic_fdm.free()

	print("test_fdm_link: OK")
	quit()
