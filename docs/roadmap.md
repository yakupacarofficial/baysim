# Geliştirme yol haritası

Bu sıra, BAYSIM'in tek-uçaklı prototipten `jsb-forge` ile birlikte veya bağımsız çalışabilen görselleştirme sistemine dönüşümünü tanımlar. Durumlar kod ve testlerle birlikte güncellenmelidir.

## Altyapı — bağımsız depo

**Durum: tamamlandı.**

- BAYSIM ayrı Git deposu olarak oluşturuldu.
- Varsayılan dal `main`.
- `jsb-forge` kodu veya uçak fiziği bu depoya kopyalanmadı.
- Birlikte çalışma sınırı dosya paylaşımı değil, sürümlü protokol olacak.

Uzak Git sunucusu henüz tanımlı değildir.

## 1. WGS84 ve yerel ENU dünya orijini

**Durum: tamamlandı.**

- Paylaşılabilir `GeoReference` kaynağı eklendi.
- `origin_lat_deg`, `origin_lon_deg`, `origin_alt_msl_m` tanımlandı.
- WGS84 → ECEF hesapları 64-bit yapılıyor.
- ECEF → yerel ENU → Godot eksen dönüşümü eklendi.
- Yerel north/east modu geriye uyumlu tutuldu.
- Yüksek rakımlı pist için MSL-orijin farkı test edildi.

Kalan ileri işler: gerçek arazi geldiğinde jeoit modeli ve çok uzun mesafeler için floating-origin.

## 2. Uçak model profilleri

**Durum: sıradaki adım.**

Her uçak için veri odaklı bir profil tanımlanacak:

- benzersiz uçak kimliği
- GLB/GLTF sahne yolu
- görsel ölçek
- eksen/yönelim düzeltmesi
- model kökü ve teker temas yüksekliği
- chase, cockpit, tail ve isteğe bağlı özel kamera bağlantıları
- ileride kontrol yüzeyi ve iniş takımı düğüm eşlemeleri

Tamamlanma ölçütü: World sahnesini değiştirmeden en az iki model profili arasında geçilebilmesi ve kamera konumlarının profil tarafından belirlenmesi.

## 3. Sürümlü telemetri protokolü

**Durum: bekliyor.**

İlk sürüm en az şunları taşımalı:

- `schema_version`, mesaj türü, uçak ve oturum kimliği
- monoton paket sıra numarası ve simülasyon zamanı
- dünya orijini ve konum referans türü
- konum, yönelim, doğrusal/açısal hızlar
- hava verileri
- kontrol komutları ve gerçek yüzey konumları
- motor dizisi ve iniş takımı durumu
- otopilot modu, hedefleri ve temel hata/komut değerleri

Tamamlanma ölçütü: aynı sözleşmenin `jsb-forge` üreticisi ve BAYSIM alıcısı tarafından sözleşme testleriyle doğrulanması; bozuk veya desteklenmeyen sürümlerin anlaşılır biçimde reddedilmesi.

## 4. Canlı ve kayıtlı telemetri kaynakları

**Durum: bekliyor.**

Normalize edilmiş uçak durumunu üreten ortak bir kaynak arayüzü kurulacak:

- canlı UDP kaynağı
- kayıt/replay kaynağı
- oynat/duraklat, hız ve zaman çizgisi
- paket kaybı ve bağlantı istatistikleri

Tamamlanma ölçütü: aynı uçuşun canlı akış ve kayıt dosyasından görsel bileşenlerde değişiklik olmadan oynatılabilmesi.

## Sonraki katmanlar

İlk dört adımdan sonra değerlendirilecek işler:

- gerçek havaalanı/pist ve arazi veri kaynakları
- floating origin ve arazi tile yaşam döngüsü
- çoklu uçak/yer hedefi/mühimmat
- animasyonlu kontrol yüzeyleri, iniş takımı ve motorlar
- kokpit göstergeleri ve otopilot hata grafikleri
- kamera kayıt/çıktı sistemi
- BAYSIM'den simülasyona kontrollü komut geri kanalı
