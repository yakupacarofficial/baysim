# BAYSIM Python Launcher

Launcher, kullanıcıyı doğrudan Godot editörüne sokmadan BAYSIM renderer'ını yapılandırır, kontrol eder, başlatır ve durdurur. Python standart kütüphanesindeki Tk/ttk kullanılır; ek GUI paketi kurulmaz.

Gereksinimler: Python 3.10 veya üzeri, Tk desteği ve Godot 4. `jsb-forge`/JSBSim yalnızca bağlantılı uçuşları çalıştırmak için gereklidir; launcher bağımsız BAYSIM kullanımına da izin verir.

## Başlatma

Windows'ta `start_baysim.cmd` dosyasına çift tıklayın veya terminalden:

```powershell
python run_baysim.py
```

Splash ekranından sonra kontrol paneli açılır. Renderer varsayılan olarak otomatik başlamaz; kullanıcı `BAYSIM'i başlat` düğmesine basar. İstenirse ayarlardan sonraki açılışlar için otomatik başlatma seçilebilir.

Yeni kullanıcı ayarlarının WGS84 orijini pilot LTBU paketinin pist orta noktasından okunur. Dünya kimliği içermeyen eski `launcher/settings.json` dosyaları açılışta LTBU/WGS84 orijinine taşınır; Godot, JSBSim, port ve görüntü tercihleri korunur.

## Sağlık kontrolleri

Launcher dört ayrı kontrol yapar:

- **Godot Engine:** seçilen executable üzerinde `--version` çalıştırılır.
- **jsb-forge:** klasör ve temel waypoint/core dosyaları aranır.
- **JSBSim Python:** seçilen Python ortamında `import jsbsim` ve sürüm okuma çalıştırılır.
- **UDP portu:** IPv4 ve IPv6 üzerinde portun BAYSIM tarafından bind edilebilir olup olmadığı kontrol edilir.

UDP bağlantısız bir protokoldür; “bağlandı” sorgusu yoktur. `5 sn telemetri bekle` testi launcher kapalı portu geçici olarak bind eder ve gelen ilk paketin UTF-8 legacy CSV veya sürümlü JSON olup olmadığını denetler. Godot renderer çalışırken aynı portu launcher dinleyemez.

## Uygulanan ayarlar

- Godot executable yolu
- `jsb-forge` ve JSBSim Python yolları
- UDP telemetri portu
- bağlantı zaman aşımı ve poz yumuşatma
- `local` veya `wgs84` konum modu
- dünya orijini enlem/boylam/MSL irtifası
- pencere çözünürlüğü ve tam ekran
- isteğe bağlı otomatik renderer başlatma

Kullanıcı tercihleri Git tarafından izlenmeyen `launcher/settings.json` dosyasına yazılır. Her başlatmada ayrıca `runtime/launcher_config.json` üretilir ve Godot'a `--baysim-config=<path>` kullanıcı argümanıyla geçirilir.

Godot ana sahnesindeki `scripts/world_controller.gd`, çocuk node'lar `_ready()` almadan önce bu dosyayı okuyarak UDP portunu, koordinat modunu ve dünya orijinini uygular. Pencere ayarı sahne hazır olduğunda uygulanır.

## Süreç ve log

Godot ayrı bir alt süreç olarak başlatılır. Launcher:

- PID ve çalışma durumunu gösterir,
- standart çıktıyı arayüzün log alanına aktarır,
- son çıktıyı `runtime/godot.log` dosyasına yazar,
- `Renderer'ı durdur` veya launcher kapanışıyla süreci sonlandırır.

Launcher şu aşamada `jsb-forge` görevini kendisi başlatmaz. Yalnızca kurulumunu doğrular ve dışarıdan gelen telemetriyi test eder. Scenario seçimi ve iki proje arasında kontrollü başlatma, sürümlü protokol/entegrasyon fazında eklenecektir.

## Test

```powershell
python -m unittest discover -s launcher/tests -v
```

GUI testi otomatik olarak pencere açmaz. Çekirdek ayar serileştirmesi, runtime config, Godot komut satırı, çift yığınlı UDP port kontrolü ve paket doğrulama mantığı bağımsız test edilir.
