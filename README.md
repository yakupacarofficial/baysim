# BAYSIM

BAYSIM, JSBSim uçuşlarını Godot 4 içinde canlı veya kayıttan görselleştirmek için geliştirilen bağımsız bir istemcidir. Fizik hesabını yapmaz; mevcut prototip UDP `5005` üzerinden telemetri alır.

## Mevcut durum

- TB2 GLB modeli
- Resmî DHMİ eşik verilerinden üretilen LTBU prosedürel pisti, gerçek eşik irtifalarıyla
- Copernicus GLO-30 tabanlı 30 × 30 km LTBU arazisi, pist-arazi dikişiyle
- AirportPack doğrulayıcısı ve arazi üreticisi (`tools/world_builder`)
- Takip, kokpit ve kuyruk kameraları (`1`, `2`, `3`)
- Uçuş telemetrisi HUD'u
- Yerel north/east veya WGS84 tabanlı konumlandırma
- Eksik ve bozuk UDP paketlerine karşı atomik telemetri doğrulaması
- Splash ekranlı Python başlatıcı, sağlık kontrolleri ve runtime ayarları

`jsb-forge` ile BAYSIM henüz aynı UDP protokolünü kullanmıyor. Ortak ve sürümlenmiş telemetri sözleşmesi ayrı bir geliştirme adımıdır.

## Belgeler

- [Mimari ve bileşen sınırları](docs/architecture.md)
- [Geçici CSV telemetri sözleşmesi](docs/telemetry-legacy-csv.md)
- [Geliştirme yol haritası](docs/roadmap.md)
- [Gerçek dünya veri ve AirportPack planı](docs/real-world-data.md)
- [LTBU DEM/OSM uygulama akışı](docs/ltbu-environment-workflow.md)
- [Dünya paketi klasör kuralları](worlds/README.md)
- [World builder: doğrulama ve arazi üretimi](tools/world_builder/README.md)
- [Görsel modeller ve varlık provenansı](models/README.md)
- [Python launcher kullanımı ve mimarisi](launcher/README.md)

Davranış, veri sözleşmesi veya mimari değiştiğinde ilgili belge kod ve testlerle aynı commit içinde güncellenir.

## Başlatma

Depo, LTBU arazisiyle birlikte klonlandığı gibi çalışır. Araziyi ham DEM'den **yeniden üretmek** isterseniz önce `git lfs pull` gerekir; ayrıntı için [world builder belgesi](tools/world_builder/README.md).

Godot editörünü açmak gerekmez. Windows'ta `start_baysim.cmd` dosyasına çift tıklayın veya:

```powershell
python run_baysim.py
```

Splash ekranından sonra Godot, JSBSim ve UDP kontrollerinin bulunduğu launcher açılır. Renderer kullanıcı onayıyla başlatılır.

## Dünya koordinatları

[default_world_origin.tres](resources/default_world_origin.tres) sahnenin WGS84 referans noktasını tutar:

- `origin_lat_deg`: referans enlemi
- `origin_lon_deg`: referans boylamı
- `origin_alt_msl_m`: referansın deniz seviyesine göre irtifası

`Aircraft` düğümündeki `position_source` iki modu destekler:

- `LOCAL_NORTH_EAST`: UDP'deki `north_m/east_m` kullanılır. Dikey konum `alt_msl_m - origin_alt_msl_m` olarak hesaplanır.
- `GEODETIC_WGS84`: UDP'deki `lat_deg/lon_deg/alt_msl_m`, WGS84 ECEF üzerinden yerel ENU'ya dönüştürülür.

Godot sahne eksenleri `east=+X`, `up=+Y`, `north=-Z` olarak kullanılır. Büyük ECEF değerleri 64-bit olarak hesaplanır ve ancak yerel fark alındıktan sonra `Vector3`'e dönüştürülür; bu, gerçek koordinatları doğrudan sahneye yazmanın oluşturacağı titreşimi önler.

MSL irtifası şu an WGS84 elipsoit yüksekliğine yerel bir yaklaşım olarak kullanılır. Geniş alanlı ve santimetre hassasiyetli arazi çalışmasında jeoit ayrımı ayrıca ele alınmalıdır.

## Testler

GDScript ve launcher testlerini tek komutta çalıştırın:

```powershell
.\run_tests.cmd
```

```bash
./run_tests.sh
```

Godot yürütülebiliri PATH'te değilse `BAYSIM_GODOT` ortam değişkeniyle yol verilir. Yalnızca launcher testleri için:

```powershell
python -m unittest discover -s launcher/tests -v
```

Aynı testler her push ve pull request'te GitHub Actions üzerinde çalışır ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
