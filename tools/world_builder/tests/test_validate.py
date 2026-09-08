"""manifests.py ve validate.py testleri."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from ..geotiff import is_lfs_pointer
from ..manifests import (
    PROJECT_ROOT,
    WORLDS_DIR,
    ManifestError,
    load_pack,
    validate_structure,
)
from ..validate import validate_pack
from .helpers import write_pack


class LoadPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)

    def test_missing_world_raises(self) -> None:
        with self.assertRaises(ManifestError):
            load_pack("YOK", worlds_dir=self.root)

    def test_invalid_json_raises(self) -> None:
        directory = self.root / "TEST"
        directory.mkdir()
        (directory / "world.json").write_text("{ bozuk", encoding="utf-8")
        with self.assertRaises(ManifestError):
            load_pack("TEST", worlds_dir=self.root)

    def test_honours_custom_file_names(self) -> None:
        write_pack(self.root / "TEST")
        directory = self.root / "TEST"
        world = json.loads((directory / "world.json").read_text(encoding="utf-8"))
        world["runways_file"] = "pistler.json"
        (directory / "world.json").write_text(json.dumps(world), encoding="utf-8")
        (directory / "pistler.json").write_text(
            (directory / "runways.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
        pack = load_pack("TEST", worlds_dir=self.root)
        self.assertEqual(len(pack.runways["runways"]), 1)


class StructureValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)

    def pack_with(self, **overrides):
        write_pack(self.root / "TEST", **overrides)
        return load_pack("TEST", worlds_dir=self.root)

    def base_world(self) -> dict:
        write_pack(self.root / "TEST")
        return json.loads(
            (self.root / "TEST" / "world.json").read_text(encoding="utf-8")
        )

    def test_valid_pack_passes(self) -> None:
        report = validate_structure(self.pack_with())
        self.assertTrue(report.ok, report.errors)

    def test_unsupported_format_version(self) -> None:
        world = self.base_world()
        world["format_version"] = 99
        report = validate_structure(self.pack_with(world=world))
        self.assertFalse(report.ok)
        self.assertTrue(any("format_version" in e for e in report.errors))

    def test_world_id_mismatch_between_documents(self) -> None:
        write_pack(self.root / "TEST")
        runways = json.loads(
            (self.root / "TEST" / "runways.json").read_text(encoding="utf-8")
        )
        runways["world_id"] = "BASKA"
        report = validate_structure(self.pack_with(runways=runways))
        self.assertFalse(report.ok)
        self.assertTrue(any("world_id" in e for e in report.errors))

    def test_missing_vertical_datum(self) -> None:
        world = self.base_world()
        world["origin"]["vertical_datum"] = ""
        report = validate_structure(self.pack_with(world=world))
        self.assertTrue(any("Dikey datum" in e for e in report.errors))

    def test_non_wgs84_horizontal_datum(self) -> None:
        world = self.base_world()
        world["origin"]["horizontal_datum"] = "ED50"
        report = validate_structure(self.pack_with(world=world))
        self.assertTrue(any("WGS84" in e for e in report.errors))

    def test_runway_without_two_designators(self) -> None:
        write_pack(self.root / "TEST")
        runways = json.loads(
            (self.root / "TEST" / "runways.json").read_text(encoding="utf-8")
        )
        runways["runways"][0]["designators"] = ["09"]
        report = validate_structure(self.pack_with(runways=runways))
        self.assertTrue(any("designator" in e for e in report.errors))

    def test_out_of_range_threshold_coordinates(self) -> None:
        write_pack(self.root / "TEST")
        runways = json.loads(
            (self.root / "TEST" / "runways.json").read_text(encoding="utf-8")
        )
        runways["runways"][0]["thresholds"]["09"]["lat_deg"] = 120.0
        report = validate_structure(self.pack_with(runways=runways))
        self.assertTrue(any("enlemi" in e for e in report.errors))


class MeasurementGateTests(unittest.TestCase):
    """Geometri kapıları gerçekten sapma yakalıyor mu?"""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        write_pack(self.root / "TEST")

    def load(self):
        return load_pack("TEST", worlds_dir=self.root)

    def rewrite_runways(self, mutate) -> None:
        path = self.root / "TEST" / "runways.json"
        runways = json.loads(path.read_text(encoding="utf-8"))
        mutate(runways)
        path.write_text(json.dumps(runways), encoding="utf-8")

    def test_length_mismatch_is_an_error(self) -> None:
        self.rewrite_runways(
            lambda r: r["runways"][0].__setitem__("declared_length_m", 2000.0)
        )
        report = validate_pack(self.load(), check_dem=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("uzunluk" in e for e in report.errors))

    def test_bearing_mismatch_is_an_error(self) -> None:
        self.rewrite_runways(
            lambda r: r["runways"][0]["thresholds"]["09"].__setitem__(
                "true_bearing_deg", 123.0
            )
        )
        report = validate_pack(self.load(), check_dem=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("bearing" in e for e in report.errors))

    def test_missing_bearing_is_only_a_warning(self) -> None:
        report = validate_pack(self.load(), check_dem=False)
        self.assertTrue(report.ok, report.errors)
        self.assertTrue(any("true_bearing_deg" in w for w in report.warnings))

    def test_redistributed_source_needs_attribution(self) -> None:
        path = self.root / "TEST" / "sources.json"
        sources = json.loads(path.read_text(encoding="utf-8"))
        sources["sources"].append(
            {
                "source_id": "carried",
                "provider": "Someone",
                "license_status": "All rights reserved",
                "usage": ["terrain"],
                "file": "source/x.tif",
            }
        )
        path.write_text(json.dumps(sources), encoding="utf-8")
        report = validate_pack(self.load(), check_dem=False)
        self.assertTrue(any("attribution" in e for e in report.errors))

    def test_reference_only_source_needs_no_attribution(self) -> None:
        report = validate_pack(self.load(), check_dem=False)
        self.assertFalse(any("attribution" in e for e in report.errors))

    def test_source_hash_mismatch_is_an_error(self) -> None:
        source_dir = self.root / "TEST" / "source"
        source_dir.mkdir()
        (source_dir / "data.bin").write_bytes(b"gercek icerik")
        path = self.root / "TEST" / "sources.json"
        sources = json.loads(path.read_text(encoding="utf-8"))
        sources["sources"].append(
            {
                "source_id": "hashed",
                "provider": "Someone",
                "license_status": "Public Domain",
                "usage": ["terrain"],
                "file": "source/data.bin",
                "sha256": "0" * 64,
            }
        )
        path.write_text(json.dumps(sources), encoding="utf-8")
        report = validate_pack(self.load(), check_dem=False)
        self.assertTrue(any("SHA-256" in e for e in report.errors))


class LtbuPackTests(unittest.TestCase):
    """Depodaki gerçek LTBU paketi doğrulamadan geçmeli."""

    def test_ltbu_structure_and_geometry(self) -> None:
        pack = load_pack("LTBU", worlds_dir=WORLDS_DIR)
        report = validate_pack(pack, check_dem=False)
        self.assertTrue(report.ok, "\n".join(report.errors))

    def test_ltbu_dem_matches_published_elevations(self) -> None:
        pack = load_pack("LTBU", worlds_dir=WORLDS_DIR)
        dem_path = pack.directory / "source" / "copernicus_glo30_ltbu.tif"
        if not dem_path.is_file() or is_lfs_pointer(dem_path):
            self.skipTest("DEM indirilmemiş (git lfs pull)")
        report = validate_pack(pack, check_dem=True)
        self.assertTrue(report.ok, "\n".join(report.errors))

    def test_terrain_manifest_matches_binary(self) -> None:
        manifest_path = WORLDS_DIR / "LTBU" / "terrain" / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest("Arazi tile'ı henüz üretilmemiş")
        import hashlib

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for tile in manifest["tiles"]:
            data_path = manifest_path.parent / tile["file"]
            self.assertTrue(data_path.is_file(), f"{tile['file']} yok")
            self.assertEqual(data_path.stat().st_size, tile["size_bytes"])
            self.assertEqual(
                hashlib.sha256(data_path.read_bytes()).hexdigest(), tile["sha256"]
            )
            self.assertEqual(
                tile["width"] * tile["height"] * 4, tile["size_bytes"]
            )


if __name__ == "__main__":
    unittest.main()
