"""`world_builder validate <world_id>` — paket bütünlüğü ve ölçüm kapıları.

docs/real-world-data.md içindeki "Kalite kapıları" başlığının makinece
çalıştırılabilir karşılığıdır.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .geodesy import angle_difference_deg, horizontal_distance_m, true_bearing_deg
from .geotiff import GeoTiff, GeoTiffError, is_lfs_pointer
from .manifests import AirportPack, Report, sha256_of, validate_structure

# Kalite kapisi toleranslari
LENGTH_TOLERANCE_M = 5.0
BEARING_TOLERANCE_DEG = 0.2
SLOPE_TOLERANCE_PERCENT = 0.05
DEM_THRESHOLD_TOLERANCE_M = 5.0


def validate_pack(pack: AirportPack, check_dem: bool = True) -> Report:
    report = validate_structure(pack)
    if not report.ok:
        # Bicimsel hata varken olcum yapmak yaniltici sonuc uretir.
        return report

    report.extend(_validate_runway_geometry(pack))
    report.extend(_validate_sources(pack))
    if check_dem:
        report.extend(_validate_dem(pack))
    return report


def _validate_runway_geometry(pack: AirportPack) -> Report:
    report = Report()
    reference = pack.geo_reference

    for runway in pack.runways.get("runways", []):
        runway_id = str(runway.get("id", "?"))
        start_key, end_key = (str(d) for d in runway["designators"])
        thresholds = runway["thresholds"]
        start, end = thresholds[start_key], thresholds[end_key]

        measured_length = horizontal_distance_m(
            reference,
            float(start["lat_deg"]), float(start["lon_deg"]),
            float(end["lat_deg"]), float(end["lon_deg"]),
        )
        declared_length = float(runway["declared_length_m"])
        length_delta = measured_length - declared_length
        report.note(
            f"{runway_id}: eşiklerden ölçülen uzunluk {measured_length:.1f} m, "
            f"beyan {declared_length:.1f} m (fark {length_delta:+.1f} m)"
        )
        if abs(length_delta) > LENGTH_TOLERANCE_M:
            report.error(
                f"{runway_id}: ölçülen uzunluk beyandan {abs(length_delta):.1f} m "
                f"sapıyor (tolerans {LENGTH_TOLERANCE_M:.1f} m)"
            )

        measured_bearing = true_bearing_deg(
            reference,
            float(start["lat_deg"]), float(start["lon_deg"]),
            float(end["lat_deg"]), float(end["lon_deg"]),
        )
        published_bearing = start.get("true_bearing_deg")
        if published_bearing is None:
            report.warn(f"{runway_id}/{start_key}: true_bearing_deg yayımlanmamış")
        else:
            bearing_delta = angle_difference_deg(
                measured_bearing, float(published_bearing)
            )
            report.note(
                f"{runway_id}: eşiklerden hesaplanan bearing "
                f"{measured_bearing:.2f}°, yayımlanan {float(published_bearing):.2f}° "
                f"(fark {bearing_delta:.2f}°)"
            )
            if bearing_delta > BEARING_TOLERANCE_DEG:
                report.error(
                    f"{runway_id}: bearing sapması {bearing_delta:.2f}° "
                    f"(tolerans {BEARING_TOLERANCE_DEG:.2f}°)"
                )

        # Karsit esigin bearing'i ilk esikten 180 derece farkli olmali.
        opposite_bearing = end.get("true_bearing_deg")
        if published_bearing is not None and opposite_bearing is not None:
            reciprocal_delta = angle_difference_deg(
                float(published_bearing) + 180.0, float(opposite_bearing)
            )
            if reciprocal_delta > BEARING_TOLERANCE_DEG * 2:
                report.warn(
                    f"{runway_id}: yayımlanan iki bearing birbirinin tersi değil "
                    f"({reciprocal_delta:.2f}° fark)"
                )

        # Yayimlanan egim ile esik irtifalarindan hesaplanan egim.
        rise = float(end["elevation_msl_m"]) - float(start["elevation_msl_m"])
        measured_slope = abs(rise) / measured_length * 100.0
        published_slope = runway.get("published_slope_percent")
        report.note(
            f"{runway_id}: eşik irtifa farkı {rise:+.1f} m, "
            f"hesaplanan eğim %{measured_slope:.3f}"
        )
        if published_slope is not None:
            slope_delta = abs(measured_slope - float(published_slope))
            if slope_delta > SLOPE_TOLERANCE_PERCENT:
                report.warn(
                    f"{runway_id}: hesaplanan eğim %{measured_slope:.3f}, "
                    f"yayımlanan %{float(published_slope):.3f} "
                    f"(fark %{slope_delta:.3f})"
                )
    return report


def _validate_sources(pack: AirportPack) -> Report:
    report = Report()
    entries = pack.sources.get("sources", [])
    if not entries:
        report.error("sources.json içinde hiç kaynak yok")
        return report

    for entry in entries:
        if not isinstance(entry, dict):
            report.error("Kaynak kaydı JSON nesnesi olmalı")
            continue
        source_id = str(entry.get("source_id", "isimsiz"))

        for required in ("provider", "license_status", "usage"):
            if not entry.get(required):
                report.error(f"{source_id}: '{required}' alanı zorunlu")

        # Attribution yalnızca depoda taşınan/yeniden dağıtılan kaynaklar için
        # zorunludur. Yalnızca referans verilen belgeler (`file` alanı yok)
        # bu kuralın dışındadır.
        redistributed = bool(entry.get("file"))
        license_text = str(entry.get("license_status", ""))
        if (
            redistributed
            and not entry.get("attribution")
            and "public domain" not in license_text.lower()
        ):
            report.error(
                f"{source_id}: depoda taşınan kaynak public domain değil ve "
                "attribution metni yok"
            )

        for item in entry.get("verification_needed", []):
            report.warn(f"{source_id}: doğrulama bekliyor — {item}")

        relative = entry.get("file")
        if not relative:
            continue
        path = pack.directory / str(relative)
        if not path.is_file():
            report.error(f"{source_id}: dosya bulunamadı ({path})")
            continue
        if is_lfs_pointer(path):
            report.warn(
                f"{source_id}: {path.name} indirilmemiş bir LFS pointer'ı; "
                "hash doğrulaması atlandı (`git lfs pull`)"
            )
            continue

        expected_size = entry.get("size_bytes")
        actual_size = path.stat().st_size
        if expected_size is not None and int(expected_size) != actual_size:
            report.error(
                f"{source_id}: dosya boyutu {actual_size}, manifest {expected_size}"
            )
        expected_hash = entry.get("sha256")
        if expected_hash:
            actual_hash = sha256_of(path)
            if actual_hash != expected_hash:
                report.error(
                    f"{source_id}: SHA-256 uyuşmuyor\n"
                    f"    manifest: {expected_hash}\n"
                    f"    dosya   : {actual_hash}"
                )
            else:
                report.note(f"{source_id}: SHA-256 doğrulandı")
    return report


def _validate_dem(pack: AirportPack) -> Report:
    """DEM'i pist eşiklerinde örnekleyip yayımlanan irtifalarla karşılaştırır."""
    report = Report()
    entry = _find_dem_source(pack)
    if entry is None:
        report.warn("Pakette DEM kaynağı tanımlı değil; arazi kontrolü atlandı")
        return report

    path = pack.directory / str(entry["file"])
    if is_lfs_pointer(path):
        report.warn("DEM indirilmemiş bir LFS pointer'ı; örnekleme atlandı")
        return report

    try:
        dem = GeoTiff(path)
    except (GeoTiffError, OSError) as exc:
        report.error(f"DEM okunamadı: {exc}")
        return report

    with dem:
        report.extend(_sample_dem_at_thresholds(pack, dem, entry))
    return report


def _sample_dem_at_thresholds(
    pack: AirportPack, dem: GeoTiff, entry: dict[str, Any]
) -> Report:
    report = Report()
    bounds = dem.bounds
    reference = pack.geo_reference
    if not bounds.contains(reference.lat_deg, reference.lon_deg):
        report.error("Dünya orijini DEM kapsamı dışında")
        return report

    radius_m = float(pack.world.get("bounds", {}).get("radius_m", 0.0))
    if radius_m > 0.0:
        report.extend(_check_radius_coverage(dem, reference, radius_m))

    declared_datum = str(entry.get("vertical_datum", {}).get("measured", "")) or str(
        entry.get("vertical_datum", "")
    )
    report.note(f"DEM dikey datum kaydı: {declared_datum or 'belirtilmemiş'}")

    for runway in pack.runways.get("runways", []):
        runway_id = str(runway.get("id", "?"))
        for designator, threshold in runway["thresholds"].items():
            lat = float(threshold["lat_deg"])
            lon = float(threshold["lon_deg"])
            published = float(threshold["elevation_msl_m"])
            try:
                sampled = dem.sample_bilinear(lat, lon)
            except ValueError as exc:
                report.error(f"{runway_id}/{designator}: {exc}")
                continue
            delta = sampled - published
            report.note(
                f"{runway_id}/{designator}: DEM {sampled:.2f} m, "
                f"yayımlanan {published:.1f} m (fark {delta:+.2f} m)"
            )
            if abs(delta) > DEM_THRESHOLD_TOLERANCE_M:
                report.error(
                    f"{runway_id}/{designator}: DEM ile yayımlanan irtifa "
                    f"{abs(delta):.2f} m ayrışıyor "
                    f"(tolerans {DEM_THRESHOLD_TOLERANCE_M:.1f} m). "
                    "Dikey datum uyuşmazlığı olabilir."
                )
    return report


def _check_radius_coverage(dem: GeoTiff, reference, radius_m: float) -> Report:
    """world.json'daki yarıçapın tamamı DEM kapsamında mı?"""
    import math

    report = Report()
    bounds = dem.bounds
    m_per_deg_lat = 111132.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(reference.lat_deg))
    d_lat = radius_m / m_per_deg_lat
    d_lon = radius_m / m_per_deg_lon

    missing = []
    if reference.lat_deg + d_lat > bounds.north:
        missing.append("kuzey")
    if reference.lat_deg - d_lat < bounds.south:
        missing.append("güney")
    if reference.lon_deg + d_lon > bounds.east:
        missing.append("doğu")
    if reference.lon_deg - d_lon < bounds.west:
        missing.append("batı")

    if missing:
        report.error(
            f"DEM, istenen {radius_m/1000:.1f} km yarıçapı karşılamıyor; "
            f"eksik yön(ler): {', '.join(missing)}"
        )
    else:
        report.note(f"DEM {radius_m/1000:.1f} km yarıçapı tamamen kapsıyor")
    return report


def _find_dem_source(pack: AirportPack) -> dict[str, Any] | None:
    # Öncelik: usage alanı açıkça arazi/yükseklik belirten kaynak.
    for entry in pack.sources.get("sources", []):
        if not isinstance(entry, dict):
            continue
        usage = str(entry.get("usage", "")).lower()
        if usage in ("terrain", "elevation", "dem"):
            return entry
    # Fallback: eski paketlerde usage alanı olmayabilir; ilk TIFF'i al.
    for entry in pack.sources.get("sources", []):
        if not isinstance(entry, dict):
            continue
        file_name = str(entry.get("file", ""))
        if file_name.endswith((".tif", ".tiff")):
            return entry
    return None
