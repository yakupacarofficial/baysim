# Gerçek dünya veri planı

Bu belge BAYSIM'in pist, arazi, scenery ve hava verisini hangi kurallarla alacağını tanımlar. Kaynak koşulları değişebildiği için her veri paketi indirme anındaki lisans ve kaynak sürümünü kendi manifestinde saklamalıdır.

## Önerilen ilk dikey dilim

Tek bir havalimanı seçilir ve çevrimdışı bir `AirportPack` üretilir. İlk paket şu katmanlarla sınırlandırılır:

1. havalimanı ve pist metadatası
2. pist uç noktaları ve eşik irtifaları
3. 20–30 km kırpılmış yükseklik modeli
4. prosedürel pist mesh'i/işaretleri
5. dünya orijini ve datum bilgisi
6. kaynak/lisans manifesti

Bu yaklaşım ağ bağlantısı olmadan deterministik kalkış ve replay testi sağlar. Küresel streaming, fotogrametri ve yüksek çözünürlüklü imagery sonraki katmanlardır.

## Veri kaynakları

### Havalimanı ve pist kataloğu — OurAirports

Önerilen başlangıç kaynağı [OurAirports açık verisi](https://ourairports.com/data/)'dir. `airports.csv` ve `runways.csv`; ICAO/yerel kimlik, pist uzunluğu-genişliği, yüzey, true heading, iki pist ucunun koordinatları, MSL irtifaları ve displaced-threshold alanlarını sağlayabilir.

- Lisans: Public Domain
- Avantaj: küresel, basit CSV, GitHub üzerinden sürümlenebilir
- Sınırlama: doğruluk veya kullanıma uygunluk garantisi yoktur

Bu nedenle kaynak veri görselleştirme/başlangıç tahmini için uygundur; sertifikalı seyrüsefer verisi olarak sunulmaz. Kritik bir saha için kullanıcı tarafından sağlanan survey veya kullanım hakkı doğrulanmış resmi AIP verisi override edebilmelidir.

### Arazi yüksekliği — Copernicus DEM

Önerilen ilk DEM [Copernicus DEM GLO-30](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)'dur.

- küresel yaklaşık 30 m örnekleme
- GLO-30/GLO-90 için lisanslı erişim ve zorunlu attribution
- yatay referans WGS84
- dikey referans EGM2008 (`EPSG:3855`)
- erişim için Copernicus Data Space/CCM kaydı gerekebilir

30 m DEM pist yüzeyini tek başına doğru modellemez. Pist düzlemi, eşik irtifalarıyla ayrıca oluşturulmalı; çevre DEM'i piste doğru kontrollü biçimde stitch edilmelidir.

### Yollar, taksi yolları ve binalar — OpenStreetMap / Overture

[OpenStreetMap verisi](https://www.openstreetmap.org/copyright) ODbL kapsamındadır ve görünür attribution gerektirir. Havalimanı sınırı, taxiway, apron, yol, bina ve çevre nesneleri için kullanılabilir.

Standart `tile.openstreetmap.org` sunucusu bir veri dağıtım altyapısı değildir. [OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/) bulk indirmeyi ve çevrimdışı prefetch'i yasaklar. BAYSIM airport-pack üreticisi standart raster tile sunucusunu scrape etmemelidir; küçük sorgu için uygun API, lisanslı sağlayıcı, bölgesel extract veya self-hosted veri kullanılmalıdır.

[Overture Maps](https://docs.overturemaps.org/) özellikle bina/ulaşım verisini alan bazında GeoJSON/GeoParquet olarak indirmek için alternatif bir normalizasyon katmanı olabilir. Bina temasının ODbL yükümlülükleri ayrıca korunmalıdır.

### Hava — AviationWeather.gov

[AviationWeather.gov Data API](https://aviationweather.gov/data/api/) dünya çapında METAR ve TAF'ı JSON/GeoJSON/CSV/XML biçimlerinde sunar.

- sorgular dar kapsamlı ve cache'li olmalı
- özel User-Agent kullanılmalı
- mevcut sınır: dakikada en fazla 100 istek
- METAR tipik olarak saatlik değiştiği için frame veya saniye bazında sorgulanmamalı

İndirilen ham rapor, çözülmüş değerler ve veri zamanı scenario snapshot'ına yazılır. Replay hiçbir zaman “şimdiki METAR”ı yeniden sorgulamaz.

### Imagery ve küresel 3D içerik

İlk AirportPack için imagery sağlayıcısı henüz seçilmemiştir. Kaynağı/lisansı belirsiz Google/Bing/başka web haritası tile'ları indirilmeyecek veya repoya eklenmeyecektir. İlk sürüm prosedürel malzeme ve gerekirse kullanıcının lisanslı yerel GeoTIFF'i ile çalışmalıdır.

Uzun vadede [OGC 3D Tiles 1.1](https://www.ogc.org/standards/3DTiles/) açık streaming formatı değerlendirilebilir. [Cesium Native](https://cesium.com/learn/cesium-native/ref-doc/) 3D Tiles seçimi, WGS84 hesabı ve raster overlay altyapısı sağlar; ancak Godot bağlantısı ana resmi motor entegrasyonlarından biri değildir ve Cesium Native henüz kararlı 1.0 geriye uyumluluk garantisi vermemektedir. Bu nedenle önce ayrı bir performans/uyumluluk denemesi gerekir.

## `AirportPack` önerisi

Üretilmiş büyük varlıklar doğrudan ana Git geçmişine eklenmemeli; küçük manifest ve test fixture'ları commit edilmelidir.

```text
worlds/<airport_id>/
├── world.json
├── sources.json
├── airport.geojson
├── runways.geojson
├── terrain/
│   ├── manifest.json
│   ├── height_*.exr
│   └── mesh_*.res
├── imagery/                 # opsiyonel, lisans izin verirse
└── generated/               # yeniden üretilebilir Godot varlıkları
```

`world.json` en az şunları taşımalıdır:

- `world_id`, `format_version`
- airport/ICAO kimliği ve görünen ad
- `origin_lat_deg`, `origin_lon_deg`, `origin_alt_msl_m`
- `horizontal_datum`, `vertical_datum`
- tile sınırı ve LOD ayarları
- varsayılan runway/start noktaları
- bağlı kaynak manifesti

`sources.json` her girdi için şunları taşımalıdır:

- sağlayıcı ve doğrudan kaynak URL'si
- dataset/sürüm/release kimliği
- erişim/indirme zamanı
- lisans ve zorunlu attribution metni
- indirilen dosyanın SHA-256 değeri
- uygulanan kırpma, reprojection, resample ve mesh dönüşümleri

## Veri üretim hattı

Godot çalışma zamanında ham GIS verisi işlemek yerine ayrı, tekrar üretilebilir bir araç hattı kullanılmalıdır:

1. ICAO veya koordinatla alanı seç.
2. Kaynak sürümlerini sabitle ve ham dosya hash'lerini al.
3. Pist uç noktalarını/saha sınırını doğrula.
4. DEM'i alan çevresinde kırp; datum ve NoData hücrelerini doğrula.
5. ENU dünya orijinini seç; tercihen ana pist referans noktası.
6. Pist mesh'ini eşik koordinatları, width ve displaced threshold ile üret.
7. DEM'i Godot tile/heightmap biçimine dönüştür.
8. Pist çevresini kontrollü düzleştir ve araziyle stitch et.
9. Kaynak/lisans manifestini ve QA raporunu üret.
10. Paket doğrulayıcıyı çalıştır.

Python + GDAL/rasterio tabanlı bir `tools/world_builder/` bu görev için uygundur; Godot tarafı yalnızca üretilmiş manifest ve render varlıklarını yüklemelidir.

## İrtifa ve datum kuralları

Bugünkü `GeoReference`, MSL değerlerini ECEF hesabında yerel yaklaşım olarak kullanır. Gerçek DEM entegrasyonunda bu bilgi açık hale getirilmelidir:

- her yükseklik alanı `MSL_EGM2008`, `ELLIPSOID_WGS84` veya açık başka bir datum belirtir
- Copernicus DEM ile karşılaştırılan uçak/pist irtifası EGM2008 MSL'e normalize edilir
- datum bilinmiyorsa sessiz dönüşüm yapılmaz; uyarı veya açık “approximate” modu gerekir
- yerel 20–30 km pakette geoit farkının yavaş değiştiği varsayımı test edilerek belgelenir

## Pistten ve havada başlangıç

### Pistten başlangıç

- başlangıç noktası runway threshold + centerline ofsetinden üretilir
- true heading kullanılır; manyetik heading'e sessiz dönüşüm yapılmaz
- başlangıç MSL irtifası pist mesh'iyle aynı kaynaktan gelir
- görsel modelin teker temas yüksekliği AircraftProfile'dan uygulanır
- `jsb-forge` ve BAYSIM aynı scenario/world manifestini referans eder

### Havada başlangıç

- WGS84 lat/lon, MSL irtifası, true heading, IAS/TAS koşulu açıkça saklanır
- terrain altındaki veya güvenli AGL'in altındaki başlangıç doğrulamada reddedilir
- ilk telemetri gelene kadar model başlangıç manifestindeki preview konumunda gösterilebilir

## Kalite kapıları

- Runway endpoint'lerinden hesaplanan uzunluk kaynak uzunluğuyla belirlenen toleransta uyuşmalı.
- Hesaplanan bearing ile kaynak true heading arasında yön/threshold farkı dışında açıklanamayan sapma olmamalı.
- Pist mesh'i ve DEM arasında görünür boşluk/z-fighting olmamalı.
- Ground-start modelinin teker temas noktaları pist seviyesinde olmalı.
- Havada başlangıçtaki görsel AGL ile telemetri AGL farkı raporlanmalı.
- NoData, datum bilinmezliği ve eksik threshold koordinatı sessizce sıfıra çevrilmemeli.
- Her ekranda/veri paketinde gereken attribution gösterilebilmeli.

## İlk uygulama kararı için gereken kullanıcı girdisi

AirportPack v1 başlamadan önce tek bir test havalimanı/ICAO seçilmelidir. İyi bir ilk saha şu özellikleri taşımalıdır:

- OurAirports'ta iki pist ucunun koordinatları ve irtifaları dolu
- çevresinde belirgin fakat aşırı karmaşık olmayan topoğrafya
- bir adet ana pist
- kullanıcının görsel olarak tanıdığı ve sonucu kontrol edebileceği bir saha
