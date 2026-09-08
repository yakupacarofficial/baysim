"""world_builder komut satırı arayüzü."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .dem import build_tile, runway_surfaces, write_tile
from .geotiff import GeoTiff, GeoTiffError, is_lfs_pointer
from .imagery import build_imagery_tile, write_imagery
from .manifests import WORLDS_DIR, ManifestError, Report, load_pack
from .validate import _find_dem_source, validate_pack

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def _force_utf8_output() -> None:
    """Windows konsolu varsayılan olarak cp1252 kullanır; Türkçe çıktı bozulur."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _print_report(report: Report, verbose: bool) -> None:
    if verbose:
        for note in report.notes:
            print(f"  · {note}")
    for warning in report.warnings:
        print(f"  ! UYARI  {warning}")
    for error in report.errors:
        print(f"  x HATA   {error}")


def command_validate(args: argparse.Namespace) -> int:
    try:
        pack = load_pack(args.world_id, worlds_dir=args.worlds_dir)
    except ManifestError as exc:
        print(f"x {exc}", file=sys.stderr)
        return EXIT_FAILED

    print(f"== {pack.world_id} paketi doğrulanıyor ==")
    report = validate_pack(pack, check_dem=not args.no_dem)
    _print_report(report, verbose=not args.quiet)

    print()
    if report.ok:
        suffix = f" ({len(report.warnings)} uyarı)" if report.warnings else ""
        print(f"GEÇTİ{suffix}")
        return EXIT_OK
    print(f"BAŞARISIZ — {len(report.errors)} hata, {len(report.warnings)} uyarı")
    return EXIT_FAILED


def command_dem_crop(args: argparse.Namespace) -> int:
    try:
        pack = load_pack(args.world_id, worlds_dir=args.worlds_dir)
    except ManifestError as exc:
        print(f"x {exc}", file=sys.stderr)
        return EXIT_FAILED

    entry = _find_dem_source(pack)
    if entry is None:
        print("x sources.json içinde bir DEM (.tif) kaynağı tanımlı değil", file=sys.stderr)
        return EXIT_FAILED

    dem_path = pack.directory / str(entry["file"])
    if not dem_path.is_file():
        print(f"x DEM bulunamadı: {dem_path}", file=sys.stderr)
        return EXIT_FAILED
    if is_lfs_pointer(dem_path):
        print(
            f"x {dem_path.name} indirilmemiş bir Git LFS pointer'ı. "
            "`git lfs pull` çalıştırın.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    radius_m = float(
        args.radius
        if args.radius is not None
        else pack.world.get("bounds", {}).get("radius_m", 15000.0)
    )
    step_m = float(args.step)
    tile_id = args.tile_id or (
        f"{pack.world_id.lower()}_{int(radius_m / 1000)}km_{int(step_m)}m"
    )

    print(f"== {pack.world_id} arazi tile'ı üretiliyor ==")
    print(f"  kaynak    : {dem_path.name}")
    print(f"  yarıçap   : {radius_m/1000:.1f} km")
    print(f"  adım      : {step_m:.1f} m")

    try:
        dem = GeoTiff(dem_path)
    except (GeoTiffError, OSError) as exc:
        print(f"x DEM okunamadı: {exc}", file=sys.stderr)
        return EXIT_FAILED

    runways = [] if args.no_stitch else runway_surfaces(pack)
    if runways:
        print(f"  dikiş     : {', '.join(r.runway_id for r in runways)} "
              f"(omuz {args.shoulder:.0f} m, geçiş {args.blend:.0f} m)")

    with dem:
        tile = build_tile(
            dem, pack.geo_reference, radius_m, step_m, tile_id,
            runways=runways, shoulder_m=args.shoulder, blend_m=args.blend,
            depress_m=args.depress,
        )

    if tile.outside_count:
        print(
            f"  ! {tile.outside_count} düğüm kaynak rasterın dışında kaldı; "
            "kenar değerleri kullanıldı"
        )

    data_path, manifest_path = write_tile(tile, pack, entry)
    print(f"  ızgara    : {tile.width} x {tile.height} düğüm")
    print(f"  yükseklik : {tile.heights.min():.1f} .. {tile.heights.max():.1f} m (ENU up)")
    print(f"  yazıldı   : {data_path.relative_to(pack.directory.parent.parent)}")
    print(f"              {manifest_path.relative_to(pack.directory.parent.parent)}")
    return EXIT_OK


def command_imagery_crop(args: argparse.Namespace) -> int:
    try:
        pack = load_pack(args.world_id, worlds_dir=args.worlds_dir)
    except ManifestError as exc:
        print(f"x {exc}", file=sys.stderr)
        return EXIT_FAILED

    entry = _find_source(pack, args.source_id)
    if entry is None:
        print(
            "x Ortofoto kaynağı bulunamadı. sources.json içine 'usage' değeri "
            "'imagery' olan bir kayıt ekleyin ya da --source-id verin.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    image_path = pack.directory / str(entry["file"])
    if not image_path.is_file():
        print(f"x Ortofoto bulunamadı: {image_path}", file=sys.stderr)
        return EXIT_FAILED
    if is_lfs_pointer(image_path):
        print(
            f"x {image_path.name} indirilmemiş bir Git LFS pointer'ı. "
            "`git lfs pull` çalıştırın.",
            file=sys.stderr,
        )
        return EXIT_FAILED

    radius_m = float(
        args.radius
        if args.radius is not None
        else pack.world.get("bounds", {}).get("radius_m", 15000.0)
    )
    pixel_m = float(args.pixel)
    tile_id = args.tile_id or (
        f"{pack.world_id.lower()}_{int(radius_m / 1000)}km_ortho"
    )

    print(f"== {pack.world_id} ortofoto tile'ı üretiliyor ==")
    print(f"  kaynak    : {image_path.name}")
    print(f"  yarıçap   : {radius_m/1000:.1f} km")
    print(f"  piksel    : {pixel_m:.1f} m")

    try:
        source = GeoTiff(image_path)
    except (GeoTiffError, OSError) as exc:
        print(f"x Ortofoto okunamadı: {exc}", file=sys.stderr)
        return EXIT_FAILED

    with source:
        print(f"  girdi     : {source.width} x {source.height}, "
              f"{source.band_count} bant, {source.data.dtype}")
        try:
            tile = build_imagery_tile(
                source, pack.geo_reference, radius_m, pixel_m, tile_id
            )
        except (GeoTiffError, ValueError) as exc:
            print(f"x Ortofoto işlenemedi: {exc}", file=sys.stderr)
            return EXIT_FAILED

    if tile.outside_count:
        share = tile.outside_count / float(tile.width * tile.height) * 100.0
        print(f"  ! pikselin %{share:.1f}'i kaynak görüntünün dışında kaldı; "
              "kenar değerleri kullanıldı")

    written, manifest_path = write_imagery(tile, pack, entry)
    print(f"  çıktı     : {tile.width} x {tile.height} piksel, "
          f"{written.stat().st_size/1e6:.1f} MB")
    print(f"  yazıldı   : {written.relative_to(pack.directory.parent.parent)}")
    print(f"              {manifest_path.relative_to(pack.directory.parent.parent)}")
    return EXIT_OK


def _find_source(pack, source_id: str | None):
    for candidate in pack.sources.get("sources", []):
        if not isinstance(candidate, dict) or not candidate.get("file"):
            continue
        if source_id is not None:
            if candidate.get("source_id") == source_id:
                return candidate
            continue
        if "imagery" in [str(u).lower() for u in candidate.get("usage", [])]:
            return candidate
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.world_builder",
        description="BAYSIM AirportPack doğrulayıcı ve arazi üretici.",
    )
    parser.add_argument(
        "--worlds-dir",
        type=Path,
        default=WORLDS_DIR,
        help="Dünya paketlerinin bulunduğu dizin (varsayılan: worlds/)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Manifestleri ve ölçüm kapılarını doğrula"
    )
    validate_parser.add_argument("world_id")
    validate_parser.add_argument(
        "--no-dem", action="store_true", help="DEM örneklemesini atla"
    )
    validate_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Ölçüm notlarını gizle"
    )
    validate_parser.set_defaults(func=command_validate)

    dem_parser = subparsers.add_parser("dem", help="Arazi verisi işlemleri")
    dem_sub = dem_parser.add_subparsers(dest="dem_command", required=True)
    crop_parser = dem_sub.add_parser(
        "crop", help="DEM'i ENU ızgarasına yeniden örnekleyip tile üret"
    )
    crop_parser.add_argument("world_id")
    crop_parser.add_argument(
        "--radius",
        type=float,
        default=None,
        help="Metre cinsinden yarıçap (varsayılan: world.json bounds.radius_m)",
    )
    crop_parser.add_argument(
        "--step", type=float, default=30.0, help="Izgara adımı, metre (varsayılan 30)"
    )
    crop_parser.add_argument("--tile-id", default=None, help="Tile kimliği")
    crop_parser.add_argument(
        "--no-stitch",
        action="store_true",
        help="Pist-arazi dikişini uygulama (ham DEM yüzeyini koru)",
    )
    crop_parser.add_argument(
        "--shoulder",
        type=float,
        default=60.0,
        help="Pist kenarından sonra tam düz kalan omuz genişliği, metre",
    )
    crop_parser.add_argument(
        "--depress",
        type=float,
        default=0.15,
        help="Pist koridorunda arazinin pist yüzeyinin altına indirileceği "
             "miktar, metre. Sıfır yaparsanız pist araziyle z-fight eder.",
    )
    crop_parser.add_argument(
        "--blend",
        type=float,
        default=240.0,
        help="Omuzdan araziye geçiş kuşağının genişliği, metre",
    )
    crop_parser.set_defaults(func=command_dem_crop)

    imagery_parser = subparsers.add_parser("imagery", help="Ortofoto işlemleri")
    imagery_sub = imagery_parser.add_subparsers(dest="imagery_command", required=True)
    ortho_parser = imagery_sub.add_parser(
        "crop", help="Ortofotoyu arazinin ENU ızgarasına yeniden örnekle"
    )
    ortho_parser.add_argument("world_id")
    ortho_parser.add_argument("--radius", type=float, default=None)
    ortho_parser.add_argument(
        "--pixel", type=float, default=10.0,
        help="Çıktı doku çözünürlüğü, metre/piksel (varsayılan 10)",
    )
    ortho_parser.add_argument("--tile-id", default=None)
    ortho_parser.add_argument(
        "--source-id", default=None,
        help="Kullanılacak sources.json kaydı (varsayılan: usage'ı 'imagery' olan)",
    )
    ortho_parser.set_defaults(func=command_imagery_crop)

    return parser


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
