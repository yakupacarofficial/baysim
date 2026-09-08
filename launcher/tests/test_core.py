from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import socket
import sys
import unittest

from launcher.core import (
    LauncherSettings,
    build_godot_command,
    check_udp_port,
    inspect_telemetry_packet,
    load_settings,
    save_settings,
    write_runtime_config,
)


class LauncherSettingsTests(unittest.TestCase):
    def valid_settings(self) -> LauncherSettings:
        return LauncherSettings(
            godot_executable=sys.executable,
            jsb_forge_path="C:/example/jsb-forge",
            jsbsim_python=sys.executable,
            telemetry_port=5055,
            position_source="wgs84",
            origin_lat_deg=37.0,
            origin_lon_deg=35.0,
            origin_alt_msl_m=42.5,
            connection_timeout_s=1.5,
            smoothing=20.0,
            window_width=1280,
            window_height=720,
        )

    def test_settings_round_trip(self) -> None:
        settings = self.valid_settings()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(settings, path)
            self.assertEqual(load_settings(path), settings)

    def test_runtime_config_shape(self) -> None:
        settings = self.valid_settings()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            write_runtime_config(settings, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["config_version"], 1)
        self.assertEqual(payload["world"]["world_id"], "LTBU")
        self.assertEqual(payload["telemetry"]["port"], 5055)
        self.assertEqual(payload["position"]["source"], "wgs84")
        self.assertEqual(payload["world_origin"]["alt_msl_m"], 42.5)

    def test_invalid_port_is_rejected(self) -> None:
        settings = self.valid_settings()
        settings.telemetry_port = 70000
        self.assertTrue(any("UDP portu" in error for error in settings.validation_errors()))

    def test_legacy_settings_migrate_to_ltbu_origin(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"position_source": "local", "origin_lat_deg": 0.0}),
                encoding="utf-8",
            )
            settings = load_settings(path)
        self.assertEqual(settings.world_id, "LTBU")
        self.assertEqual(settings.position_source, "wgs84")
        self.assertAlmostEqual(settings.origin_lat_deg, 41.1383125)

    def test_godot_command_uses_user_argument_separator(self) -> None:
        settings = self.valid_settings()
        config = Path("C:/temp/baysim.json")
        command = build_godot_command(settings, config)
        self.assertIn("--", command)
        self.assertEqual(command[-1], f"--baysim-config={config.resolve()}")

    def test_udp_check_detects_ipv6_listener(self) -> None:
        if not socket.has_ipv6:
            self.skipTest("IPv6 kullanılamıyor")
        listener = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        try:
            listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            listener.bind(("::", 0))
            port = listener.getsockname()[1]
            self.assertFalse(check_udp_port(port).ok)
        finally:
            listener.close()


class TelemetryInspectionTests(unittest.TestCase):
    LEGACY_PACKET = (
        b"10,20,100,0.1,0.2,0.3,90,50,40,30,100,95,-2,3,4,"
        b"0.75,2200,1.1,12.5,1"
    )

    def test_valid_legacy_csv(self) -> None:
        result = inspect_telemetry_packet(self.LEGACY_PACKET)
        self.assertTrue(result.ok)
        self.assertIn("Legacy CSV", result.summary)

    def test_incomplete_legacy_csv(self) -> None:
        result = inspect_telemetry_packet(b"1,2,3")
        self.assertFalse(result.ok)

    def test_json_requires_schema_version(self) -> None:
        self.assertFalse(inspect_telemetry_packet(b'{"type":"aircraft_state"}').ok)
        self.assertTrue(inspect_telemetry_packet(b'{"schema_version":1}').ok)


if __name__ == "__main__":
    unittest.main()
