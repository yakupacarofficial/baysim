# BAYSIM world builder

AirportPack manifestlerini doğrular ve ham GIS kaynaklarından Godot'un yükleyeceği türetilmiş dünya varlıklarını üretir. Godot çalışma zamanında ham GIS verisi okumaz; yalnızca buradan çıkan sürümlü paketi yükler.

## Bağımlılıklar

`numpy` ve `Pillow`. GDAL, rasterio ve pyproj **kullanılmaz**.

Bu, `docs/ltbu-environment-workflow.md` içindeki ilk plandan bilinçli bir sapmadır. LTBU kaynağı zaten `EPSG:4326` float32 GeoTIFF'tir ve ilgilenilen alan çevresinde indirilmiştir; yeniden projeksiyon ya da format dönüşümü gerekmez. TIFF etiketlerini doğrudan okumak bağımlılığı sıfırlar, Windows'ta kurulum derdini kaldırır ve CI'da ek adım istemez. Farklı bir CRS, sıkıştırma ya da vektör veri (OSM) gerektiğinde bu karar yeniden değerlendirilir.

## Komutlar

```powershell
python -m tools.world_builder validate LTBU
python -m tools.world_builder dem crop LTBU --radius 15000 --step 30
python -m tools.world_builder imagery crop LTBU --radius 15000 --pixel 10
```

### `validate <world_id>`

`docs/real-world-data.md` içindeki "Kalite kapıları" başlığının makinece çalıştırılabilir karşılığıdır. Sırasıyla:

- üç manifestin `format_version` ve `world_id` tutarlılığı
- dünya orijini, yatay/dikey datum bildirimi
- pist designator, uzunluk, genişlik ve eşik alanları
- **eşiklerden ölçülen uzunluk** ile beyan edilen uzunluk (tolerans 5 m)
- **eşiklerden hesaplanan bearing** ile yayımlanan true bearing (tolerans 0.2°)
- karşıt eşik bearing'lerinin birbirinin tersi olması
- eşik irtifalarından hesaplanan eğim ile yayımlanan eğim (tolerans %0.05)
- depoda taşınan kaynakların lisans/attribution kaydı ve SHA-256 doğrulaması
- DEM'in `bounds.radius_m` yarıçapını kapsaması
- **DEM'in pist eşiklerinde okuduğu irtifa** ile yayımlanan irtifa (tolerans 5 m)

Son kontrol dikey datum uyuşmazlığını yakalar: elipsoit yüksekliği taşıyan bir DEM Türkiye'de ~36 m sapma verir ve toleransı aşar.

Çıkış kodu: `0` geçti, `1` hata var. Uyarılar başarısızlık sayılmaz. `--no-dem` DEM örneklemesini atlar; `-q` ölçüm notlarını gizler.

### `dem crop <world_id>`

DEM'i dünya orijini çevresinde `±radius` metrelik bir kareye **düzenli ENU ızgarası** olarak yeniden örnekler.

Neden lat/lon değil de ENU ızgarası? Godot sahnesi metre tabanlı yerel ENU'dur ve pist geometrisi de aynı çerçevede üretilir. Tile doğrudan ENU'ya örneklenince çalışma zamanında düğüm başına trigonometri gerekmez — mesh kurulumu `x = x0 + i*step` kadar basitleşir ve arazi ile pist otomatik hizalanır.

Her düğüm için:

1. ENU yatay konumu jeodezik koordinata çevrilir
2. DEM oradan çift doğrusal örneklenir (MSL)
3. `(lat, lon, h_msl)` ileri yönde ENU'ya döndürülür, `up` bileşeni yazılır

Üçüncü adım yeryüzü eğriliğini hesaba katar: 15 km yarıçaplı bir karenin köşesi merkeze 21.2 km uzaktadır ve teğet düzleminin ~35 m altına düşer. Düz bir teğet düzlemi kullanmak uzaktaki araziyi bu kadar yukarıda gösterirdi.

Seçenekler: `--radius` (varsayılan `world.json` → `bounds.radius_m`), `--step` (varsayılan 30 m), `--tile-id`, `--no-stitch`, `--shoulder`, `--blend`.

#### Pist-arazi dikişi

Varsayılan olarak her pist çevresi pist düzlemine oturtulur. Pist ekseni üzerindeki izdüşüme göre:

- yarı genişlik + `--shoulder` (varsayılan 60 m) yarıçapına kadar yükseklik, pist yüzeyinin `--depress` (varsayılan 0.15 m) kadar altındadır
- sonraki `--blend` (varsayılan 240 m) kuşağında smoothstep ile DEM'e döner

`--depress` şart. Arazi ile pist mesh'i tam olarak aynı düzleme düşerse derinlik tamponu ikisi arasında karar veremez ve pist araziyle kırpışır (z-fighting): ekranda pist yerine yeşilin içinde dağınık koyu lekeler görünür. Birkaç santimlik fark bunu tamamen kaldırır ve fiziksel olarak da doğrudur — pist, tesviye edilmiş zeminin üstüne dökülen bir kaplamadır.

**Godot tarafında LOD uyarısı:** dikilen koridor 45 m'lik pist için ~165 m genişliğindedir. `terrain_tile.gd` içindeki `lod_step` ızgarayı seyreltir; 30 m adımlı bir tile'da `lod_step = 4` aralığı 120 m'ye çıkarır ve koridor artık örneklenemez, arazi pistin üstünden geçer. Havalimanı çevresinde `lod_step = 1` kullanılmalıdır.

Pist yüzeyi iki eşik ENU yüksekliği arasında doğrusal interpolasyondur; `procedural_airport.gd`'nin ürettiği dörtgen de aynı iki yükseklikten kurulduğu için ikisi birebir örtüşür.

### `imagery crop <world_id>`

Ortofotoyu **arazi tile'ıyla aynı ENU karesine** yeniden örnekler. Kaynak, `sources.json` içinde `usage` değeri `imagery` olan kayıttan bulunur; `--source-id` ile de seçilebilir.

Doku çözünürlüğü geometriden bağımsızdır: arazi 30 m ızgarada dursa bile görüntü `--pixel 10` ile 10 m'de kalabilir. Godot tarafında UV, tile içindeki normalize konumdur (`0..1`), bu yüzden ikisi birbirini bağlamaz ve `lod_step` değişse de doku kaymaz.

Kaynak 8-bit gelebildiği gibi 16-bit yansıma değerleri de taşıyabilir. 16-bit'te sabit bir bölme koyu ya da yanmış görüntü üretirdi; onun yerine %1–%99 yüzdelik germe uygulanır.

Çıktı JPEG'dir (kalite 92). 3000×3000 RGB, PNG olarak ~20 MB, JPEG olarak ~1–3 MB; arazi dokusunda kayıpsızlığın görsel karşılığı yok, depo boyutunun var.

**Manifest paylaşılır:** `dem crop` ve `imagery crop` aynı `manifest.json` dosyasına yazar ve yalnızca kendi bölümlerini günceller. Biri diğerinin kaydını silmez; `tests/test_imagery.py` bunu iki yönde de doğrular.

Yeni bir görüntü ekledikten sonra Godot'un onu içe aktarması gerekir:

```powershell
godot --headless --path . --import
```

## Çıktı biçimi

```text
worlds/<world_id>/terrain/
├── manifest.json
├── <tile_id>.f32          # yükseklik
└── <tile_id>_ortho.jpg    # ortofoto (varsa)
```

`.f32` dosyası little-endian float32, satır sırası kuzey→güney, sütun sırası batı→doğu, dolgu yok. Manifest ızgara adımını, yarıçapı, dünya orijinini, kaynak SHA-256'sını, attribution metnini, dikiş parametrelerini ve verinin kendi SHA-256'sını taşır.

EXR yerine ham ikili seçildi: kodek belirsizliği yok, kayıpsız, iki tarafta da tek satırda okunuyor ve manifest hash'iyle bütünlüğü doğrulanabiliyor.

Türetilmiş tile düz Git'te sürümlenir (`.gitattributes` içinde `*.f32 binary`). Birkaç MB'lık bu dosya sayesinde LFS'siz bir klon da gerçek araziyle çalışır; 136 MB'lık ham DEM yalnızca yeniden üretim için gerekir.

## Testler

```powershell
python -m unittest discover -s . -t . -v
```

`tests/test_geodesy.py` beklentileri `tests/test_geo_reference.gd` ile ortak sözleşmedir: iki dil aynı WGS84→ENU sonucunu üretmezse world builder'ın geometrisi Godot sahnesine oturmaz. `tests/test_dem.py` ayrıca vektörleştirilmiş numpy yolunun skaler `geodesy.py` ile birebir aynı sonucu verdiğini doğrular.

Ham DEM'e bağlı testler dosya yokken ya da indirilmemiş bir LFS pointer'ıyken kendini atlar; CI LFS nesnelerini indirmez.
