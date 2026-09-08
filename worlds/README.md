# BAYSIM dünya paketleri

Her gerçek dünya bölgesi `worlds/<world_id>/` altında bağımsız ve sürümlü bir `AirportPack` olarak tutulacaktır. Godot çalışma zamanında ham GIS verisi indirmez veya dönüştürmez; world builder tarafından üretilmiş paketi yükler.

İlk pilot paket bir havalimanının pist orta noktası çevresinde yaklaşık 20–30 km'lik alanla sınırlandırılacaktır. Uygulama sırası:

1. `world.json` ve `sources.json`
2. doğrulanmış pist uçları ve prosedürel pist mesh'i
3. düz doğrulama zemini üzerinde ENU/heading/irtifa testleri
4. kırpılmış DEM ve pist-arazi dikişi
5. apron, taksi yolu, yol ve basit bina katmanları
6. lisansı uygunsa imagery

Büyük üretilmiş DEM, imagery ve mesh çıktıları ana Git geçmişine eklenmemelidir. Küçük manifestler, üretim tarifleri ve test fixture'ları sürümlenir. Ayrıntılı veri kuralları için [`docs/real-world-data.md`](../docs/real-world-data.md) okunmalıdır.

İlk pilot havalimanı LTBU olarak sabitlenmiştir. Paket ayrıntıları ve doğrulama notları için [`LTBU/README.md`](LTBU/README.md) okunmalıdır.
