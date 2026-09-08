"""AirportPack manifestlerini yükler ve doğrular.

Doğrulama kuralları `scripts/world/airport_pack.gd` ile aynı sözleşmeyi
paylaşır; buradaki ek kontroller (kaynak hash'i, DEM karşılaştırması) Godot
çalışma zamanına değil üretim hattına aittir.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .geodesy import GeoReference

SUPPORTED_FORMAT_VERSION = 1

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORLDS_DIR = PROJECT_ROOT / "worlds"


class ManifestError(RuntimeError):
    """Manifest okunamadığında."""


@dataclass(slots=True)
class Report:
    """Bir doğrulama çalışmasının hataları, uyarıları ve ölçümleri."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def extend(self, other: "Report") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.notes.extend(other.notes)


@dataclass(slots=True)
class AirportPack:
    world_id: str
    directory: Path
    world: dict[str, Any]
    runways: dict[str, Any]
    sources: dict[str, Any]

    @property
    def geo_reference(self) -> GeoReference:
        origin = self.world.get("origin", {})
        return GeoReference(
            lat_deg=float(origin.get("lat_deg", float("nan"))),
            lon_deg=float(origin.get("lon_deg", float("nan"))),
            alt_msl_m=float(origin.get("alt_msl_m", float("nan"))),
        )

    def source(self, source_id: str) -> dict[str, Any] | None:
        for entry in self.sources.get("sources", []):
            if isinstance(entry, dict) and entry.get("source_id") == source_id:
                return entry
        return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ManifestError(f"Manifest bulunamadı: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path.name} geçerli JSON değil: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ManifestError(f"{path.name} bir JSON nesnesi olmalı")
    return parsed


def load_pack(world_id: str, worlds_dir: Path = WORLDS_DIR) -> AirportPack:
    """`worlds/<world_id>/` altındaki üç manifesti okur."""
    directory = worlds_dir / world_id
    if not directory.is_dir():
        raise ManifestError(f"Dünya paketi bulunamadı: {directory}")

    world = _load_json(directory / "world.json")
    runways_name = str(world.get("runways_file", "runways.json"))
    sources_name = str(world.get("sources_file", "sources.json"))
    return AirportPack(
        world_id=world_id,
        directory=directory,
        world=world,
        runways=_load_json(directory / runways_name),
        sources=_load_json(directory / sources_name),
    )


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_structure(pack: AirportPack) -> Report:
    """Sürüm, kimlik, orijin ve pist alanlarının biçimsel doğrulaması."""
    report = Report()

    for label, document in (
        ("world.json", pack.world),
        ("runways.json", pack.runways),
        ("sources.json", pack.sources),
    ):
        version = document.get("format_version")
        if version != SUPPORTED_FORMAT_VERSION:
            report.error(
                f"{label} format_version desteklenmiyor "
                f"(beklenen {SUPPORTED_FORMAT_VERSION}, bulunan {version!r})"
            )
        if document is not pack.world:
            if str(document.get("world_id", "")) != str(pack.world.get("world_id", "")):
                report.error(f"{label} world_id, world.json ile eşleşmiyor")

    declared_id = str(pack.world.get("world_id", ""))
    if not declared_id:
        report.error("world.json içinde world_id eksik")
    elif declared_id != pack.world_id:
        report.error(
            f"world_id ({declared_id}) klasör adıyla ({pack.world_id}) eşleşmiyor"
        )

    origin = pack.world.get("origin", {})
    if not pack.geo_reference.is_valid():
        report.error("Geçerli bir dünya orijini yok")
    if str(origin.get("horizontal_datum", "")) != "WGS84":
        report.error("Yalnızca WGS84 yatay datum destekleniyor")
    if not str(origin.get("vertical_datum", "")).strip():
        report.error("Dikey datum açıkça belirtilmeli")

    runways = pack.runways.get("runways", [])
    if not runways:
        report.error("En az bir pist tanımlanmalı")
    for runway in runways:
        if not isinstance(runway, dict):
            report.error("Pist kaydı JSON nesnesi olmalı")
            continue
        report.extend(_validate_runway_fields(runway))
    return report


def _validate_runway_fields(runway: dict[str, Any]) -> Report:
    report = Report()
    runway_id = str(runway.get("id", "isimsiz"))
    designators = runway.get("designators", [])

    if not isinstance(designators, list) or len(designators) != 2:
        report.error(f"{runway_id}: iki pist designator gerekli")
        return report
    if float(runway.get("declared_length_m", 0.0)) <= 0.0:
        report.error(f"{runway_id}: declared_length_m geçersiz")
    if float(runway.get("width_m", 0.0)) <= 0.0:
        report.error(f"{runway_id}: width_m geçersiz")

    thresholds = runway.get("thresholds", {})
    for designator in designators:
        key = str(designator)
        threshold = thresholds.get(key)
        if not isinstance(threshold, dict) or not threshold:
            report.error(f"{runway_id}: {key} eşiği eksik")
            continue
        lat = float(threshold.get("lat_deg", float("nan")))
        lon = float(threshold.get("lon_deg", float("nan")))
        elevation = float(threshold.get("elevation_msl_m", float("nan")))
        if not -90.0 <= lat <= 90.0:
            report.error(f"{runway_id}/{key}: eşik enlemi geçersiz ({lat})")
        if not -180.0 <= lon <= 180.0:
            report.error(f"{runway_id}/{key}: eşik boylamı geçersiz ({lon})")
        if elevation != elevation:  # NaN
            report.error(f"{runway_id}/{key}: eşik irtifası geçersiz")
    return report
