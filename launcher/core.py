from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any
import json
import math
import os
import shutil
import socket
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
RUNTIME_CONFIG_PATH = PROJECT_ROOT / "runtime" / "launcher_config.json"
RUNTIME_LOG_PATH = PROJECT_ROOT / "runtime" / "godot.log"
DEFAULT_WORLD_MANIFEST_PATH = PROJECT_ROOT / "worlds" / "LTBU" / "world.json"


@dataclass(slots=True)
class LauncherSettings:
    godot_executable: str = ""
    jsb_forge_path: str = ""
    jsbsim_python: str = ""
    world_id: str = "LTBU"
    telemetry_port: int = 5005
    position_source: str = "local"
    origin_lat_deg: float = 0.0
    origin_lon_deg: float = 0.0
    origin_alt_msl_m: float = 0.0
    connection_timeout_s: float = 1.0
    smoothing: float = 25.0
    fullscreen: bool = False
    window_width: int = 1600
    window_height: int = 900
    auto_start_renderer: bool = False

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        godot = Path(self.godot_executable).expanduser()
        if not self.godot_executable or not godot.is_file():
            errors.append("Geçerli bir Godot çalıştırılabilir dosyası seçin.")
        if not 1 <= self.telemetry_port <= 65535:
            errors.append("UDP portu 1–65535 arasında olmalı.")
        if self.position_source not in {"local", "wgs84"}:
            errors.append("Konum kaynağı local veya wgs84 olmalı.")
        if self.world_id != "LTBU":
            errors.append("Bu sürümde yalnızca LTBU dünya paketi destekleniyor.")
        if not -90.0 <= self.origin_lat_deg <= 90.0:
            errors.append("Dünya orijini enlemi -90–90 derece arasında olmalı.")
        if not -180.0 <= self.origin_lon_deg <= 180.0:
            errors.append("Dünya orijini boylamı -180–180 derece arasında olmalı.")
        numeric_values = (
            self.origin_lat_deg,
            self.origin_lon_deg,
            self.origin_alt_msl_m,
            self.connection_timeout_s,
            self.smoothing,
        )
        if not all(math.isfinite(value) for value in numeric_values):
            errors.append("Sayısal ayarlar sonlu değerler olmalı.")
        if self.connection_timeout_s <= 0.0:
            errors.append("Bağlantı zaman aşımı sıfırdan büyük olmalı.")
        if self.smoothing < 0.0:
            errors.append("Yumuşatma negatif olamaz.")
        if self.window_width < 800 or self.window_height < 600:
            errors.append("Pencere çözünürlüğü en az 800×600 olmalı.")
        return errors

    def runtime_config(self) -> dict[str, Any]:
        return {
            "config_version": 1,
            "world": {
                "world_id": self.world_id,
                "manifest_path": "res://worlds/LTBU/world.json",
            },
            "telemetry": {
                "port": self.telemetry_port,
                "connection_timeout_s": self.connection_timeout_s,
                "smoothing": self.smoothing,
            },
            "position": {"source": self.position_source},
            "world_origin": {
                "lat_deg": self.origin_lat_deg,
                "lon_deg": self.origin_lon_deg,
                "alt_msl_m": self.origin_alt_msl_m,
            },
            "display": {
                "fullscreen": self.fullscreen,
                "width": self.window_width,
                "height": self.window_height,
            },
        }


@dataclass(frozen=True, slots=True)
class CheckResult:
    ok: bool
    summary: str
    detail: str = ""


def detected_defaults() -> LauncherSettings:
    jsb_forge = PROJECT_ROOT.parent / "jsb-forge"
    jsb_python = jsb_forge / "venvbaykar" / "Scripts" / "python.exe"
    origin = _default_world_origin()
    return LauncherSettings(
        godot_executable=str(find_godot_executable() or ""),
        jsb_forge_path=str(jsb_forge if jsb_forge.is_dir() else ""),
        jsbsim_python=str(jsb_python if jsb_python.is_file() else ""),
        position_source="wgs84",
        origin_lat_deg=float(origin.get("lat_deg", 0.0)),
        origin_lon_deg=float(origin.get("lon_deg", 0.0)),
        origin_alt_msl_m=float(origin.get("alt_msl_m", 0.0)),
    )


def _default_world_origin() -> dict[str, Any]:
    try:
        world = json.loads(DEFAULT_WORLD_MANIFEST_PATH.read_text(encoding="utf-8"))
        origin = world.get("origin", {})
        return origin if isinstance(origin, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def find_godot_executable() -> Path | None:
    explicit = os.environ.get("BAYSIM_GODOT")
    if explicit and Path(explicit).is_file():
        return Path(explicit)

    for command in ("godot", "godot4"):
        located = shutil.which(command)
        if located:
            return Path(located)

    search_roots = (Path.home() / "Documents", Path.home() / "Downloads")
    patterns = ("Godot*_win64.exe", "Godot*.exe")
    candidates: list[Path] = []
    for root in search_roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            candidates.extend(root.glob(f"**/{pattern}"))
    candidates = [path for path in candidates if "console" not in path.name.lower()]
    return sorted(candidates, reverse=True)[0] if candidates else None


def load_settings(path: Path = SETTINGS_PATH) -> LauncherSettings:
    defaults = detected_defaults()
    if not path.is_file():
        return defaults

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults

    allowed = {field.name for field in fields(LauncherSettings)}
    merged = asdict(defaults)
    merged.update({key: value for key, value in raw.items() if key in allowed})
    # Launcher v1 ayarlarında dünya kimliği yoktu ve 0,0,0 yerel sahnesi
    # kullanılıyordu. İlk AirportPack'e geçerken yalnızca bu eski biçimi LTBU
    # orijinine taşı; sürümlü yeni ayarlardaki kullanıcı değerlerine dokunma.
    if "world_id" not in raw:
        merged["world_id"] = defaults.world_id
        merged["position_source"] = defaults.position_source
        merged["origin_lat_deg"] = defaults.origin_lat_deg
        merged["origin_lon_deg"] = defaults.origin_lon_deg
        merged["origin_alt_msl_m"] = defaults.origin_alt_msl_m
    try:
        return LauncherSettings(**merged)
    except (TypeError, ValueError):
        return defaults


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def save_settings(settings: LauncherSettings, path: Path = SETTINGS_PATH) -> None:
    _atomic_write_json(path, asdict(settings))


def write_runtime_config(
    settings: LauncherSettings,
    path: Path = RUNTIME_CONFIG_PATH,
) -> Path:
    errors = settings.validation_errors()
    if errors:
        raise ValueError("\n".join(errors))
    _atomic_write_json(path, settings.runtime_config())
    return path


def check_godot(executable: str) -> CheckResult:
    path = Path(executable).expanduser()
    if not path.is_file():
        return CheckResult(False, "Godot bulunamadı", str(path))
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=_no_window_flag(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CheckResult(False, "Godot çalıştırılamadı", str(exc))
    version = (completed.stdout or completed.stderr).strip().splitlines()
    if completed.returncode == 0 and version:
        return CheckResult(True, version[0], str(path))
    return CheckResult(False, "Godot sürümü okunamadı", completed.stderr.strip())


def check_jsb_forge(project_path: str) -> CheckResult:
    path = Path(project_path).expanduser()
    required = (path / "flight_tests" / "core.py", path / "run_waypoint_mission.py")
    missing = [str(item.name) for item in required if not item.is_file()]
    if not path.is_dir():
        return CheckResult(False, "jsb-forge bulunamadı", str(path))
    if missing:
        return CheckResult(False, "jsb-forge eksik", ", ".join(missing))
    return CheckResult(True, "jsb-forge hazır", str(path))


def check_jsbsim(python_executable: str) -> CheckResult:
    path = Path(python_executable).expanduser()
    if not path.is_file():
        return CheckResult(False, "JSBSim Python ortamı bulunamadı", str(path))
    snippet = (
        "import jsbsim; "
        "print(getattr(jsbsim, '__version__', 'sürüm bilinmiyor'))"
    )
    try:
        completed = subprocess.run(
            [str(path), "-c", snippet],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=_no_window_flag(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CheckResult(False, "JSBSim kontrolü çalışmadı", str(exc))
    if completed.returncode == 0:
        return CheckResult(True, f"JSBSim {completed.stdout.strip()}", str(path))
    return CheckResult(False, "JSBSim import edilemedi", completed.stderr.strip())


def check_udp_port(port: int) -> CheckResult:
    if not 1 <= port <= 65535:
        return CheckResult(False, "Geçersiz UDP portu", str(port))
    endpoints: list[tuple[int, tuple[Any, ...]]] = []
    if socket.has_ipv6:
        endpoints.append((socket.AF_INET6, ("::", port)))
    endpoints.append((socket.AF_INET, ("0.0.0.0", port)))

    for family, endpoint in endpoints:
        sock = socket.socket(family, socket.SOCK_DGRAM)
        try:
            # Godot enables address reuse for PacketPeerUDP. On Windows a plain
            # bind can therefore succeed even while Godot already owns the port.
            # An exclusive probe gives the launcher the expected occupied/free
            # answer without relying on platform-specific process inspection.
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            if family == socket.AF_INET6:
                # Probe the same dual-stack wildcard that Godot uses. An
                # IPv6-only probe can coexist with Godot's socket on Windows
                # and would incorrectly report the port as available.
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            sock.bind(endpoint)
        except OSError as exc:
            return CheckResult(False, "UDP portu kullanımda", str(exc))
        finally:
            sock.close()
    return CheckResult(True, f"UDP {port} kullanılabilir")


def inspect_telemetry_packet(payload: bytes) -> CheckResult:
    try:
        text = payload.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        return CheckResult(False, "Paket UTF-8 değil", str(exc))
    if not text:
        return CheckResult(False, "Boş telemetri paketi")

    if text.startswith("{"):
        try:
            message = json.loads(text)
        except json.JSONDecodeError as exc:
            return CheckResult(False, "JSON telemetri bozuk", str(exc))
        version = message.get("schema_version")
        if version is None:
            return CheckResult(False, "JSON şema sürümü yok")
        return CheckResult(True, f"JSON telemetri v{version}")

    fields = text.split(",")
    if len(fields) < 20:
        return CheckResult(False, "Legacy CSV eksik", f"{len(fields)}/20 alan")
    try:
        values = [float(value.strip()) for value in fields[:20]]
    except ValueError as exc:
        return CheckResult(False, "Legacy CSV sayısal değil", str(exc))
    if not all(math.isfinite(value) for value in values):
        return CheckResult(False, "Legacy CSV sonlu olmayan değer içeriyor")
    return CheckResult(True, "Legacy CSV telemetri geçerli", f"{len(fields)} alan")


def wait_for_telemetry(port: int, timeout_s: float = 5.0) -> CheckResult:
    family = socket.AF_INET6 if socket.has_ipv6 else socket.AF_INET
    endpoint: tuple[Any, ...] = ("::", port) if socket.has_ipv6 else ("0.0.0.0", port)
    sock = socket.socket(family, socket.SOCK_DGRAM)
    if family == socket.AF_INET6:
        # Dual-stack soket IPv4 JSBSim gondericilerini de tek probe ile yakalar.
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.settimeout(timeout_s)
    try:
        sock.bind(endpoint)
        payload, sender = sock.recvfrom(65535)
    except TimeoutError:
        return CheckResult(False, "Telemetri paketi gelmedi", f"{timeout_s:.0f} sn beklendi")
    except OSError as exc:
        return CheckResult(False, "UDP dinleme başlatılamadı", str(exc))
    finally:
        sock.close()

    result = inspect_telemetry_packet(payload)
    sender_text = f"{sender[0]}:{sender[1]}"
    detail = sender_text if not result.detail else f"{sender_text} · {result.detail}"
    return CheckResult(result.ok, result.summary, detail)


def build_godot_command(
    settings: LauncherSettings,
    runtime_config_path: Path = RUNTIME_CONFIG_PATH,
) -> list[str]:
    return [
        str(Path(settings.godot_executable).expanduser()),
        "--path",
        str(PROJECT_ROOT),
        "--",
        f"--baysim-config={runtime_config_path.resolve()}",
    ]


def launch_godot(
    settings: LauncherSettings,
    runtime_config_path: Path = RUNTIME_CONFIG_PATH,
) -> subprocess.Popen[str]:
    command = build_godot_command(settings, runtime_config_path)
    return subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_no_window_flag(),
    )


def _no_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
