# Runtime dosyaları

Python launcher bu klasörde kullanıcıya ve çalıştırmaya özel dosyalar üretir:

- `launcher_config.json`: Godot başlamadan önce uygulanan port, konum, dünya orijini ve pencere ayarları
- `godot.log`: son renderer sürecinin standart çıktısı

Bu dosyalar tekrar üretilebilir ve Git tarafından izlenmez. Kalıcı varsayılanlar kodda veya sürümlenmiş Resource/manifest dosyalarında tutulmalıdır.
