# BAYSIM geliştirme yol haritası

Bu belge işlerin bağımlılık sırasını, her fazın çıktısını ve tamamlanma ölçütünü tanımlar. Gerçek dünya veri kaynakları ve veri üretim hattı için [real-world-data.md](real-world-data.md) kullanılır.

## Ürün hedefi

İlk ana dikey dilim şudur:

> Kullanıcı `jsb-forge` içinden bir uçak ve gerçek bir havalimanı seçer; pistten veya havada başlatılan JSBSim uçuşunu doğru konum/yönelimle BAYSIM'de canlı izler, aynı uçuşu daha sonra kayıttan oynatır ve otopilot davranışını kameralar/HUD üzerinden inceler.

Bu hedef için gerçek dünya grafiğini ilk sıraya almak doğru değildir. Önce uçak seçimi, ortak telemetri ve replay sınırları sabitlenmelidir; aksi durumda arazi ve pist kodu geçici tek-uçak/CSV yapısına bağlanır.

## Temel ilkeler

- Uçuş fiziğinin sahibi `jsb-forge`, görselleştirmenin sahibi BAYSIM'dir.
- Canlı ve replay akışları aynı normalize edilmiş uçak durumunu üretir.
- Veri kaynağı, sürüm, indirme tarihi, lisans ve dönüşüm bilgisi manifestte tutulur.
- İlk gerçek-dünya paketi çevrimdışı ve deterministik olur; internet zorunlu çalışma zamanı bağımlılığı değildir.
- Coğrafi doğruluk ile görsel süs ayrıdır. Önce pist/irtifa/eksen doğruluğu, sonra imagery ve binalar gelir.
- Bu sistem eğitim, mühendislik gözlemi ve görselleştirme içindir; sertifikalı seyrüsefer verisi değildir.

## Faz 0 — depo ve jeodezi temeli

**Durum: tamamlandı.**

- BAYSIM bağımsız Git deposu ve `main` dalı olarak oluşturuldu.
- GitHub remote'u: `https://github.com/yakupacarofficial/baysim.git`
- WGS84 → ECEF → yerel ENU dönüşümü eklendi.
- `origin_lat_deg`, `origin_lon_deg`, `origin_alt_msl_m` tanımlandı.
- Yerel north/east ve WGS84 konum modları test edildi.
- Splash ekranlı Python launcher, sistem sağlık kontrolleri ve Godot süreç yönetimi eklendi.
- Launcher ayarları sürümlü runtime JSON üzerinden Godot ana sahnesine bağlandı.

## Faz 1 — uçak model profilleri

**Durum: sıradaki uygulama fazı.**

### Çıktılar

- `AircraftProfile` adlı veri kaynağı
- benzersiz `aircraft_id`
- GLB/GLTF veya PackedScene yolu
- ölçek ve model eksen dönüşümü
- görsel kök/teker temas yüksekliği
- chase, cockpit, tail ve özel kamera bağlantıları
- profil kayıt defteri ve uçak spawn sistemi
- mevcut TB2 sahnesinin profile taşınması
- dış model gerektirmeyen basit bir debug-aircraft profili

### Tamamlanma ölçütü

World sahnesi değiştirilmeden TB2 ve debug-aircraft arasında geçilebilmeli; tüm kameralar profil verisinden kurulmalı; eksik model/profil anlaşılır hata vermelidir.

## Faz 2 — sürümlü telemetri protokolü

**Durum: bekliyor.**

### Çıktılar

- repo içinde makinece doğrulanabilir `schema/v1` tanımı
- `hello/session`, `aircraft_state`, `event` ve `end` mesajları
- şema sürümü, oturum/uçak kimliği, paket sıra numarası
- simülasyon zamanı ve isteğe bağlı üretim zamanı
- dünya orijini, yatay/dikey datum ve koordinat referansı
- konum, quaternion yönelim, hızlar ve hava verileri
- kontrol komutları/gerçek yüzeyler, motorlar ve iniş takımı
- otopilot modu, hedefleri, hataları ve komutları
- eski CSV için sınırlı geçiş adaptörü

JSON ile başlanması planlanır: 60–120 Hz tek/az uçak için incelenebilirlik ve sözleşme testi, ikili format kazancından daha değerlidir. Ölçüm göstermeden özel binary protokole geçilmez.

### Tamamlanma ölçütü

Aynı örnek mesajlar `jsb-forge` üreticisi ve BAYSIM alıcısında sözleşme testlerinden geçmeli; desteklenmeyen sürüm, eksik zorunlu alan ve sıra kaybı ölçülebilir olmalıdır.

## Faz 3 — ortak canlı/replay kaynak katmanı

**Durum: bekliyor.**

### Çıktılar

- taşıma ayrıntılarından bağımsız normalize `AircraftState`
- `UdpTelemetrySource`
- `ReplayTelemetrySource`
- zaman çizgisi: oynat, duraklat, ileri/geri sar, hız seç
- kayıt dosyası başlığında şema, senaryo, uçak ve dünya manifesti
- paket kaybı, gecikme ve bağlantı istatistikleri

### Tamamlanma ölçütü

Aynı uçuş canlı UDP ve kayıt dosyasından model, kamera ve HUD koduna dokunulmadan oynatılmalı. Belirli replay zamanı aynı uçak durumunu deterministik üretmelidir.

## Faz 4 — `jsb-forge` dikey entegrasyonu

**Durum: bekliyor.**

### Çıktılar

- `jsb-forge` waypoint döngüsünde v1 telemetri üreticisi
- pistten kalkış ve havada başlangıç için ortak scenario manifesti
- BAYSIM'in `hello/session` mesajından doğru uçak ve dünya profilini seçmesi
- görev sonu, payload bırakma ve kritik olay mesajları
- mevcut FlightGear çıkışının bağımsız/opsiyonel kalması

### Tamamlanma ölçütü

En az bir `ground` ve bir `air` senaryosu 1× gerçek zamanda canlı izlenmeli, kaydedilmeli ve tekrar oynatılmalıdır. Başlangıç konumu, heading, MSL irtifası ve simülasyon zamanı iki projede aynı olmalıdır.

## Faz 5 — gerçek havalimanı paketi v1

**Durum: veri hattı tasarlandı, uygulama bekliyor.**

### Kapsam

İlk sürüm tek seçilmiş havalimanına odaklanır:

- havalimanı/pist kataloğu
- pist uç noktaları, true heading, genişlik, yüzey ve displaced threshold
- dünya orijini ve dikey datum
- 20–30 km çevrede DEM tabanlı arazi
- prosedürel pist işaretleri ve basit apron/taksi yolu bağlamı
- veri/lisans/dönüşüm manifesti

Uydu görüntüsü bu fazın zorunlu kabul kriteri değildir. Pist ve arazi doğru çalıştıktan sonra sağlayıcı politikası belirlenerek eklenir.

### Tamamlanma ölçütü

Seçilen pistin ölçülen sahne uzunluğu ve true heading'i kaynak verinin toleransı içinde olmalı; pist eşik irtifaları araziyle görsel olarak çakışmamalı; ground-start uçak tekerleri pist seviyesinde görünmelidir.

## Faz 6 — tile tabanlı arazi ve scenery

**Durum: bekliyor.**

### Çıktılar

- kamera/uçak çevresinde arazi tile yaşam döngüsü ve LOD
- floating-origin; coğrafi gerçek durum korunurken Godot sahnesi yeniden merkezlenir
- pist/apron düzleştirme ve DEM ile dikiş
- OSM/Overture tabanlı yollar, binalar ve önemli nesneler
- sağlayıcıdan bağımsız raster/imagery katmanı
- disk önbelleği ve veri sürümü sabitleme
- uzun görevler için bellek/FPS bütçeleri

Küresel 3D Tiles/Cesium Native entegrasyonu doğrudan ana uygulama yolu yapılmadan önce ayrı bir teknik deneme olarak ölçülür.

### Tamamlanma ölçütü

En az 100 km'lik replay boyunca görünür origin titreşimi, tile çatlağı veya kontrolsüz bellek büyümesi olmamalı; aynı veri paketi çevrimdışı tekrar açılabilmelidir.

## Faz 7 — gerçek hava ve görsel çevre

**Durum: bekliyor.**

### Çıktılar

- METAR/TAF sağlayıcı adaptörü ve yerel cache
- rüzgâr yönü/hızı, sıcaklık, basınç, görüş, bulut ve yağış modeli
- hava snapshot'ının scenario ve replay içine gömülmesi
- görsel hava ile JSBSim atmosfer girişlerinin aynı normalize kaynaktan üretilmesi
- kullanıcı tarafından elle override edilebilen deterministik hava profili

### Tamamlanma ölçütü

Bir METAR snapshot'ından üretilen rüzgâr/basınç değerleri hem `jsb-forge` hem BAYSIM manifestinde aynı olmalı; replay güncel internet verisi değişse bile aynı havayı göstermelidir.

## Faz 8 — uçak sistemleri, kameralar ve otopilot gözlemi

**Durum: bekliyor.**

- animasyonlu aileron/elevator/rudder/elevon, flap, gear ve motorlar
- model profiline bağlı sınırsız kamera socket'i
- kokpit göstergeleri ve çoklu viewport
- otopilot hedef/gerçek/hata grafikleri
- kontrol doygunluğu, limiter ve mod geçiş olayları
- ekran/video alma ve senkron telemetri dışa aktarımı

## Faz 9 — çoklu varlık ve ürünleştirme

**Durum: bekliyor.**

- çoklu uçak, mühimmat, hava/yer hedefleri
- entity kimliği ve yaşam döngüsü olayları
- görev editörü ile görsel senaryo hazırlama
- performans profilleri, ayar ekranı ve export paketleri
- CI testleri, veri paketi doğrulayıcı ve geriye uyumluluk matrisi

## Şimdi başlayabileceğimiz işler

Bağımlılık sırasına göre bir sonraki geliştirme paketi Faz 1'dir:

1. `AircraftProfile` Resource şemasını tanımla.
2. TB2'nin hardcoded dönüşüm ve kamera ofsetlerini profile taşı.
3. Debug-aircraft profiliyle runtime model değiştirmeyi test et.
4. Profil formatını ve yeni model ekleme akışını `models/README.md` içinde belgele.

Bu tamamlanınca Faz 2 protokolü tasarlanırken uçak kimliği ve kamera/model seçiminin gerçek tüketicisi hazır olacaktır.
