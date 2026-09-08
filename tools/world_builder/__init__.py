"""BAYSIM world builder.

AirportPack manifestlerini doğrular ve ham GIS kaynaklarından Godot'un
yükleyeceği türetilmiş dünya varlıklarını üretir. Godot çalışma zamanı ham
GIS verisi okumaz; yalnızca buradan çıkan sürümlü paketi yükler.

Kullanım:
    python -m tools.world_builder validate LTBU
    python -m tools.world_builder dem crop LTBU --radius 15000 --step 30
"""

__all__ = ["dem", "geodesy", "geotiff", "manifests", "validate"]
