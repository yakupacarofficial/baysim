# BAYSIM mimarisi

Bu belge çalışan sistemin sınırlarını ve kod içindeki sorumluluk dağılımını anlatır. Hedef mimari için [roadmap.md](roadmap.md), mevcut geçici UDP formatı için [telemetry-legacy-csv.md](telemetry-legacy-csv.md), pist/arazi/hava veri hattı için [real-world-data.md](real-world-data.md) kullanılır.

## Sistem sınırı

BAYSIM bir uçuş dinamiği motoru değildir. Uçağın fiziksel durumunu dışarıdaki bir üreticiden alır ve Godot sahnesinde gösterir.

```text
JSBSim / jsb-forge / kayıt dosyası
                 |
                 | telemetri
                 v
          Telemetri kaynağı
                 |
                 v
        Uçak durumu ve dönüşüm
          /       |        \
       model    kameralar    HUD
                 |
                 v
       pist / arazi / dünya
```

Bugün yalnızca UDP kaynağı ve tek uçak vardır. Diyagramdaki ortak “Telemetri kaynağı” arayüzü canlı/kayıttan oynatma adımında eklenecektir. Kullanıcı uygulamayı [Python launcher](../launcher/README.md) üzerinden yapılandırıp başlatabilir.

### `launcher/`

Python/Tk masaüstü başlatıcısıdır. Splash ekranı, kalıcı kullanıcı tercihleri, Godot/jsb-forge/JSBSim kontrolleri, UDP paket probe'u ve Godot alt-süreç yaşam döngüsünü yönetir. Uçuş fiziği çalıştırmaz ve telemetriyi renderer çalışırken aradan geçirmez.

### `scripts/world_controller.gd`

Launcher'ın ürettiği sürümlü runtime JSON'u ana sahneye uygular. UDP portu, poz yumuşatma, koordinat modu ve dünya orijini çocuk node'ların `_ready()` aşamasından önce; pencere modu ve çözünürlük ise ertelenmiş çağrıyla uygulanır.

## Çalışan bileşenler

### `scenes/World.tscn`

Ana sahnedir. Copernicus DEM'den üretilmiş LTBU arazisi, prosedürel pist üreticisi, ışık, çevre, kamera, Aircraft örneği ve HUD'u bir araya getirir. OSM katmanı (apron, taksi yolu, bina) henüz yoktur.

### `scripts/world/` ve `worlds/LTBU/`

`AirportPack` sürümlü JSON belgelerini yükleyip doğrular; pist eşiklerini ortak WGS84 ECEF→ENU hesabıyla Godot koordinatlarına dönüştürür. `ProceduralAirport` bu geometriden çalışma zamanında pist mesh'i üretir. `TerrainTile` world builder'ın ürettiği arazi tile'ını yükleyip mesh'e çevirir. LTBU dünya/pist/kaynak/arazi manifestleri ilk gerçek dünya paketidir. Üretim hattı için [LTBU çevre iş akışı](ltbu-environment-workflow.md) kullanılır.

### `tools/world_builder/`

Manifestleri doğrulayan ve ham GIS kaynaklarından türetilmiş dünya varlıkları üreten Python paketidir. Godot çalışma zamanı ham GIS verisi okumaz. `validate` komutu ölçüm kapılarını (pist uzunluğu, bearing, eğim, kaynak hash'i, DEM–eşik irtifa farkı) makinece kontrol eder; `dem crop` DEM'i düzenli ENU ızgarasına yeniden örnekler ve pist çevresini araziye diker; `imagery crop` ortofotoyu aynı kareye giydirir. Ayrıntı ve tasarım gerekçeleri için [world builder belgesi](../tools/world_builder/README.md) okunmalıdır.

Yalnızca `numpy` ve `Pillow` kullanır; bu bağımlılıklar BAYSIM launcher'ına ya da Godot çalışma zamanına girmez.

### `scripts/world/terrain_tile.gd`

Arazi tile'ı düzenli bir ENU metre ızgarası olduğu için bu sınıfta hiç jeodezi hesabı yoktur: düğüm konumu doğrudan ızgara adımından gelir, yükseklikler zaten dünya orijinine göre ENU `up` cinsindendir. Pist geometrisi de aynı çerçevede üretildiğinden ikisi ek bir hizalama adımı olmadan örtüşür.

`lod_step` her N. örneği alarak mesh yoğunluğunu düşürür. Bu geçici bir çözümdür; kamera çevresinde tile yaşam döngüsü ve gerçek LOD Faz 6'nın konusudur.

UV, tile içindeki normalize konumdur (`0..1`). Ortofoto aynı ENU karesine üretildiği için `uv1_scale = 1` ile birebir oturur; tekrarlayan detay dokuları uv1_scale'i büyüterek döşenir. Böylece doku ölçeği `lod_step`'ten bağımsızdır. Manifestte `imagery` bölümü varsa doku otomatik yüklenir, yoksa sahnedeki mevcut malzeme korunur.

### `scripts/fdm_link.gd`

- UDP `5005` portunu dinler.
- Geçici 20-alanlı CSV paketini doğrular.
- Son geçerli telemetriyi `tel` sözlüğünde tutar.
- Konum ve Euler açılarını Godot dönüşümüne çevirir.
- Render hareketini üstel yumuşatma ile hedef duruma yaklaştırır.
- Bir saniye geçerli paket gelmezse bağlantıyı kopuk sayar.

Bu sınıf bugün hem taşıma/ayrıştırma hem uçak pozunu uygulama sorumluluğunu taşır. Sürümlü protokol ve kaynak arayüzü eklenirken bu görevler ayrılacaktır.

### `scripts/geo_reference.gd`

Paylaşılabilir `GeoReference` kaynağıdır. WGS84 jeodezik konumu önce 64-bit ECEF'e, oradan yerel ENU'ya dönüştürür. Büyük dünya koordinatları `Vector3` içine yazılmadan önce yerel fark alındığı için sahnedeki kayan nokta hassasiyeti korunur.

Varsayılan kaynak [default_world_origin.tres](../resources/default_world_origin.tres) dosyasındadır. İleride pist, arazi ve bütün uçan nesneler aynı kaynağı kullanmalıdır.

### `models/TB-2/aircraft.tscn`

Bugünkü tek görsel uçak sahnesidir. TB2 GLB modelini bir `ModelRoot` altında eksen ve yükseklik düzeltmesiyle tutar; sahnenin kendisi script taşımaz, `fdm_link.gd` yalnızca `World.tscn` içindeki örneğe uygulanır. Model ayrıntıları ve açık kayıtlar için [TB-2 model belgesi](../models/TB-2/README.md) okunmalıdır.

### `tools/measure_model.gd`

Editörden çalıştırılan bir `EditorScript`'tir. Açık model sahnesinin (yoksa TB-2 paketinin) birleşik AABB'sini yazar; yeni model eklerken kanat açıklığı, uzunluk ve teker temas ofseti ölçmek için kullanılır. Çalışma zamanı sahnesine dahil değildir.

### `scripts/camera_rig.gd`

Tek bir `Camera3D` üzerinde üç görünüm sağlar:

- `1`: chase
- `2`: cockpit
- `3`: tail

Ofsetler bugün World sahnesinde TB2 için elle girilmiştir. Bir sonraki aşamada uçak profiline taşınacaktır.

### `scripts/hud.gd`

`fdm_link.gd` tarafından yayımlanan telemetri sözlüğünü metne dönüştürür. HUD, taşıma katmanına doğrudan bağlıdır; sürümlü telemetri modeli geldiğinde normalize edilmiş uçak durumunu okumalıdır.

## Koordinat sözleşmesi

Yerel dünya ENU tabanlıdır, Godot eşlemesi şöyledir:

| Fiziksel eksen | Godot ekseni |
|---|---:|
| East | `+X` |
| Up | `+Y` |
| North | `-Z` |

İki giriş modu vardır:

- `LOCAL_NORTH_EAST`: yatay konum paketteki metre cinsinden `north_m/east_m` alanlarından gelir. Dikey konum `alt_msl_m - origin_alt_msl_m` olur.
- `GEODETIC_WGS84`: `lat_deg/lon_deg/alt_msl_m` tam WGS84 → ECEF → ENU zincirinden geçer.

Her iki modda `runway_surface_y`, görsel model kökünü pist yüzeyine göre ayarlayan ek Godot ofsetidir; coğrafi irtifanın parçası değildir.

Euler dönüşümü bugün JSBSim işaret varsayımıyla `Quaternion.from_euler(theta, -psi, -phi)` kullanır. Farklı görsel modellerin kendi eksen düzeltmesi Aircraft kökünde değil, gelecekte model profilinde uygulanmalıdır.

## `jsb-forge` ilişkisi

İki proje kardeş ve bağımsız depolardır:

- `jsb-forge`: JSBSim modeli, başlangıç koşulları, görev, otopilot ve fiziksel durumun sahibi.
- `baysim`: görsel varlık, sahne, kamera, arazi ve kullanıcıya gösterilen durumun sahibi.

Şu anda doğrudan uyumlu değillerdir. `jsb-forge` waypoint hattı JSBSim'in native FlightGear UDP çıktısını üretebilir; BAYSIM ise özel UTF-8 CSV bekler. Ortak bağlantı, [roadmap.md](roadmap.md) içindeki sürümlü protokol adımında kurulacaktır.

## Bilinen teknik borçlar

- Tek GLB ve tek Aircraft sahnesi hardcoded durumdadır.
- `scripts/fdm_link.gd` hem UDP taşıma/ayrıştırma hem uçak pozu uygulama sorumluluğunu taşır; `scripts/hud.gd` normalize durum yerine ham `tel` sözlüğünü okur.
- `scripts/world_controller.gd` yalnızca `world_id == "LTBU"` paketini kabul eder.
- Eski CSV'de sürüm, uçak kimliği ve paket sıra numarası yoktur.
- `mode=0/1` anlamları prototip senaryoya özeldir.
- Arazi tek bir 30 × 30 km mesh'tir; tile yaşam döngüsü ve LOD yoktur. `lod_step` tüm tile'ı aynı oranda seyreltir ve pist dikiş koridorunu çözemeyecek kadar kabalaşabildiği için 1'de tutulur (1M düğüm). Bu sınırın dışında dünya boştur.
- Godot ön yüz için saat yönü sarımı kullanır: prosedürel mesh üreten her yerde sağ-el normali görünen yüzün TERSİNE bakmalıdır. Ters sarım sessizce görünmez geometri üretir; `tests/test_airport_pack.gd` ve `tests/test_terrain_tile.gd` bunu kontrol eder.
- Su yüzeyleri araziye gömülü düz alanlardır; ayrı bir su malzemesi veya maskesi yoktur.
- MSL yüksekliği geoit ayrımı uygulanmadan ECEF yüksekliği için yerel yaklaşım olarak kullanılır. LTBU DEM'i ölçümle MSL referanslı doğrulandığı için bu paket etkilenmez; farklı dikey datumdaki bir kaynak açık dönüşüm gerektirir.
- Çok uzun uçuşlarda yerel ENU merkezinin yeniden taşınması, yani floating-origin mekanizması henüz yoktur.
- BAYSIM'den simülasyona kontrol komutu gönderen bir geri kanal yoktur.
