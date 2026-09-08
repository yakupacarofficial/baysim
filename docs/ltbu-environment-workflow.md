# LTBU çevre üretim iş akışı

Bu belge “DEM ve OSM verisi BAYSIM'e nasıl girer?” sorusunu uygulama seviyesinde açıklar. Kullanıcının Godot içinde GIS verisiyle elle uğraşması hedeflenmez; `tools/world_builder/` altında geliştirilecek araç indirme dışındaki dönüşümleri tekrarlanabilir biçimde yapacaktır.

## Bugün çalışan katman

`worlds/LTBU/` altında sürümlü dünya, pist ve kaynak manifestleri bulunur. Godot `scripts/world/procedural_airport.gd` ile resmî eşik koordinatlarını mevcut WGS84 ECEF→ENU dönüşümünden geçirir ve 45 metre genişliğinde pist mesh'i üretir.

DEM gelene kadar pist `Y=0` doğrulama düzlemine yatırılır. Gerçek `154.9 m` ve `173.9 m` eşik irtifaları kaybolmaz; `runways.json` içinde saklanır.

## DEM nedir?

DEM, her pikseli metre cinsinden yükseklik taşıyan coğrafi referanslı bir raster dosyadır. Uydu fotoğrafı değildir. Godot bu GeoTIFF'i doğrudan çalışma zamanında okumayacaktır.

LTBU için hedef akış:

```text
Copernicus GLO-30 GeoTIFF
    → LTBU merkezinden 15 km yarıçapa kırp
    → NoData ve datum kontrolü
    → her örneği WGS84/EGM2008'den yerel ENU yüksekliğine çevir
    → 1–2 km terrain tile'ları üret
    → pist çevresini düzleştir ve araziye yumuşakça dik
    → Godot mesh/height tile + manifest
```

İlk denemede bütün 30 km alan yerine pist çevresindeki yaklaşık 5 km'lik parça üretilir. Koordinat, ölçek ve performans doğrulandıktan sonra alan 15 km yarıçapa genişletilir.

### Kullanıcıdan gerekecek şey

Copernicus Data Space hesabı açılması gerekebilir. Erişim anahtarı veya parola repoya yazılmaz. World builder kimlik bilgisini kullanıcı ortamından alır; indirilen ürün kimliği, sürümü, SHA-256 değeri ve attribution metni `sources.json` içine yazılır.

## OSM nedir?

OSM katmanı resim değil, vektör geometridir: yol çizgileri, bina alanları, apronlar ve taksi yolları gibi nesneler koordinat ve etiket olarak gelir.

Hedef akış:

```text
OSM PBF veya küçük alan sorgusu
    → LTBU sınırına kırp
    → aeroway/building/highway etiketlerini seç
    → düğümleri WGS84→ENU dönüştür
    → taxiway/yol şeritleri ve bina mesh'leri üret
    → Godot sahne tile'ları + attribution
```

`tile.openstreetmap.org` üzerindeki harita PNG'leri toplu indirilmeyecektir. Tekrarlanabilir üretim için lisanslı bölgesel extract kullanılır; ilk seçenek Geofabrik Türkiye `.osm.pbf` dosyasını LTBU çevresine yerel olarak kırpmaktır. Küçük geliştirme sorguları için Overpass kullanılabilir ama build'in zorunlu çevrimiçi bağımlılığı yapılmaz.

## Uygulama sırası

1. World ve runway manifestleri — tamamlandı
2. WGS84→ENU prosedürel pist — tamamlandı
3. `world_builder validate LTBU` komutu
4. 5 km DEM proof-of-concept
5. pist düzleştirme/dikiş algoritması
6. 15 km yarıçaplı tile üretimi ve LOD
7. OSM apron/taksi yolu katmanı
8. yollar ve basit binalar
9. lisansı doğrulanmış imagery

DEM ve OSM aynı anda yapılmayacaktır. Önce arazinin yüksekliği ve pist teması doğru hale getirilir; ardından vektör çevre nesneleri eklenir.

## Önerilen world builder bağımlılıkları

- Python 3.11+
- `rasterio` veya GDAL: GeoTIFF okuma/kırpma
- `numpy`: yükseklik ızgarası işlemleri
- `pyproj`: CRS/datum dönüşümü ve bağımsız doğrulama
- `osmium`: büyük `.osm.pbf` dosyasını küçük LTBU alanına kırpma

Bu bağımlılıklar BAYSIM launcher'a eklenmez. Ayrı bir world-builder ortamında sabit sürümlerle tutulur; normal kullanıcı hazır AirportPack'i açarken bunlara ihtiyaç duymaz.
