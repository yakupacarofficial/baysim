# LTBU çevre üretim iş akışı

Bu belge “DEM ve OSM verisi BAYSIM'e nasıl girer?” sorusunu uygulama seviyesinde açıklar. Kullanıcının Godot içinde GIS verisiyle elle uğraşması hedeflenmez; `tools/world_builder/` altında geliştirilecek araç indirme dışındaki dönüşümleri tekrarlanabilir biçimde yapacaktır.

## Bugün çalışan katman

`worlds/LTBU/` altında sürümlü dünya, pist, kaynak ve arazi manifestleri bulunur. Godot `scripts/world/procedural_airport.gd` ile resmî eşik koordinatlarını WGS84 ECEF→ENU dönüşümünden geçirip 45 metre genişliğinde pist mesh'i üretir; `scripts/world/terrain_tile.gd` ise Copernicus DEM'den türetilmiş 30 × 30 km'lik arazi tile'ını yükler.

Pist artık `Y=0` doğrulama düzlemine yatırılmaz. Gerçek `154.9 m` ve `173.9 m` eşik irtifaları kullanılır ve arazi bu düzleme dikilir; `flatten_runways_until_dem` `false` durumundadır.

### Ölçülen sonuçlar

| Kontrol | Sonuç |
|---|---|
| Eşiklerden ölçülen pist uzunluğu | 3000.5 m (beyan 3000.0 m) |
| Eşiklerden hesaplanan true bearing | 49.11° (yayımlanan 49.10°) |
| Eşik irtifalarından hesaplanan eğim | %0.633 (yayımlanan %0.6) |
| DEM'in eşik 04'te okuduğu irtifa | 153.31 m (AIP 154.9 m) |
| DEM'in eşik 22'de okuduğu irtifa | 172.25 m (AIP 173.9 m) |
| Pist ekseni boyunca arazi–pist sapması | ≤ 0.12 m (30 m ızgara yuvarlaması) |

DEM'in eşiklerde AIP değerlerine ~1.6 m yaklaşması dikey datum sorusunu ampirik olarak kapattı: kaynak MSL (jeoit) referanslıdır. Elipsoit yüksekliği taşısaydı bu bölgede yaklaşık +36 m sapma görülürdü.

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
3. `world_builder validate LTBU` komutu — tamamlandı
4. DEM proof-of-concept — tamamlandı (5 km yerine doğrudan 15 km yapıldı; veri ve performans elverdi)
5. pist düzleştirme/dikiş algoritması — tamamlandı
6. tile bölme ve gerçek LOD — bekliyor (bugün tek mesh + `lod_step` seyreltmesi var)
7. su yüzeyi malzemesi/maskesi — bekliyor
8. OSM apron/taksi yolu katmanı — bekliyor
9. yollar ve basit binalar — bekliyor
10. lisansı doğrulanmış imagery — bekliyor

DEM ve OSM aynı anda yapılmayacaktır. Önce arazinin yüksekliği ve pist teması doğru hale getirilir; ardından vektör çevre nesneleri eklenir.

## World builder bağımlılıkları

- Python 3.11+
- `numpy`: yükseklik ızgarası işlemleri
- `Pillow`: GeoTIFF okuma

GDAL, `rasterio` ve `pyproj` **kullanılmadı**. LTBU kaynağı zaten `EPSG:4326` float32 GeoTIFF'tir ve ilgilenilen alan çevresinde indirilmiştir; yeniden projeksiyon ya da format dönüşümü gerekmedi. TIFF etiketlerini doğrudan okumak bağımlılığı sıfırladı ve CI'da ek kurulum adımı istemedi. Jeodezi hesabı `tools/world_builder/geodesy.py` içinde `scripts/geo_reference.gd` ile ortak sözleşme olarak tutulur ve iki dilde de test edilir.

OSM aşamasında büyük `.osm.pbf` dosyasını kırpmak için `osmium` gerekecektir; o karar geldiğinde alınır.

Bu bağımlılıklar BAYSIM launcher'a eklenmez. Normal kullanıcı hazır AirportPack'i açarken bunlara ihtiyaç duymaz.

## Ham DEM'in deposundaki yeri

Kaynak GeoTIFF 136 MB'dır ve GitHub'ın dosya başına 100 MB katı sınırını aşar; **Git LFS** ile sürümlenir (`.gitattributes` içinde `*.tif`). Klonladıktan sonra yeniden üretim yapacaksanız `git lfs pull` gerekir.

Türetilmiş arazi tile'ı (~4 MB) düz Git'te tutulur. Böylece LFS'siz bir klon da gerçek araziyle çalışır; ham DEM yalnızca `dem crop` komutunu yeniden çalıştırmak için gerekir.
