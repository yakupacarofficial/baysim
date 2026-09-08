#!/usr/bin/env bash
# BAYSIM birleşik test çalıştırıcısı.
# GDScript (headless Godot) ve Python (unittest) testlerini sırayla çalıştırır.
# Godot yürütülebiliri: $BAYSIM_GODOT, yoksa PATH üzerindeki `godot`.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 2

GODOT="${BAYSIM_GODOT:-godot}"
FAILED=0
GODOT_MISSING=0

GDSCRIPT_TESTS=(
	"res://tests/test_geo_reference.gd"
	"res://tests/test_fdm_link.gd"
	"res://tests/test_airport_pack.gd"
	"res://tests/test_terrain_tile.gd"
)

if ! command -v "$GODOT" >/dev/null 2>&1 && [ ! -x "$GODOT" ]; then
	echo "!! Godot bulunamadı ($GODOT). BAYSIM_GODOT ayarlayın veya PATH'e ekleyin." >&2
	echo "!! GDScript testleri atlandı (doğrulanmadı)." >&2
	GODOT_MISSING=1
else
	for test_path in "${GDSCRIPT_TESTS[@]}"; do
		name="$(basename "$test_path" .gd)"
		echo "== $name =="
		output="$("$GODOT" --headless --path . --script "$test_path" 2>&1)"
		echo "$output"
		if echo "$output" | grep -q "$name: OK"; then
			echo "-- $name: PASS"
		else
			echo "-- $name: FAIL"
			FAILED=1
		fi
		echo
	done
fi

echo "== python unittest (launcher + world_builder) =="
if python -m unittest discover -s . -t . -v; then
	echo "-- python: PASS"
else
	echo "-- python: FAIL"
	FAILED=1
fi

echo
if [ "$FAILED" -ne 0 ]; then
	echo "BAZI TESTLER BAŞARISIZ"
	exit 1
fi
if [ "$GODOT_MISSING" -ne 0 ]; then
	echo "PYTHON TESTLERİ GEÇTİ · GDScript testleri Godot yokluğunda atlandı"
	exit 2
fi

echo "TÜM TESTLER GEÇTİ"
exit 0
