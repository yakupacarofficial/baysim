# LTBU pilot AirportPack

Bu paket Tekirdağ Çorlu Atatürk Havalimanı'nı BAYSIM'in ilk gerçek dünya doğrulama sahası olarak tanımlar.

## Veri kararı

Pist bilgileri DHMİ AIP Türkiye `LTBU AD 2.12` tablosundan alınmıştır. Resmî tabloda pist `04/22`, boyut `3000 × 45 m`, true bearing değerleri `049.10°/229.12°`, eşik irtifaları `154.9 m/173.9 m` olarak yayımlanır.

Kullanıcının ilk taslağındaki koordinatlar yaklaşık `2749 m` ve `39.77°` ürettiği için kaynak değerleriyle uyuşmamıştır; fixture içine doğrudan alınmamıştır.

## Arazi

`terrain/` altındaki tile Copernicus GLO-30'dan `world_builder dem crop` ile üretilmiştir: dünya orijini çevresinde ±15 km, 30 m adımlı düzenli ENU ızgarası (1001 × 1001 düğüm, ~4 MB).

Pist artık `Y=0` düzlemine yatırılmaz; `flatten_runways_until_dem` `false` durumundadır ve gerçek `154.9 m` / `173.9 m` eşik irtifaları kullanılır. Arazi bu düzleme dikilir: pist gövdesi + 60 m omuz, pist yüzeyinin **0.15 m altındadır**, sonraki 240 m'de smoothstep ile DEM'e döner. Bu depresyon olmadan iki yüzey çakışır ve pist araziyle z-fight eder.

Pist ekseni boyunca arazi, pist düzleminin 0.15 m altında kalır; ızgara yuvarlamasından gelen sapma 0.12 m'yi geçmez.

Arazi mesh'i `lod_step = 1` (30 m) ile kurulmalıdır. Daha seyrek örnekleme dikiş koridorunu çözemez ve pist araziye gömülür.

### Dikey datum doğrulaması

DEM'in dikey datumu GeoTIFF başlığında bildirilmemiştir. Eşiklerde örneklenerek ölçüldü: eşik 04 için `153.31 m` (AIP `154.9 m`), eşik 22 için `172.25 m` (AIP `173.9 m`). Yaklaşık 1.6 m'lik fark 30 m çözünürlüklü bir yüzey modeli için beklenen aralıktadır. Kaynak elipsoit yüksekliği taşısaydı bu bölgede yaklaşık **+36 m** sapma görülürdü; dolayısıyla veri MSL (jeoit) referanslıdır ve jeoit dönüşümü uygulanmaz.

### Su

15 km yarıçapta düğümlerin **%5'i** Marmara kıyısına denk gelir ve kaynak DEM'de tam `0.0 m` MSL olarak kodlanmıştır. Bu geometrik olarak doğrudur ama ayrı bir su malzemesi yoktur; deniz şu an düz bir arazi parçası gibi görünür.

## Ölçüm sonuçları

| Kontrol | Ölçülen | Kaynak | Tolerans |
|---|---:|---:|---:|
| Pist uzunluğu | 3000.5 m | 3000.0 m | 5 m |
| True bearing | 49.11° | 49.10° | 0.2° |
| Eğim | %0.633 | %0.6 | %0.05 |

Pist uç koordinatlarının yuvarlanması nedeniyle jeodezik ölçüm yayımlanan değerden birkaç metre farklı çıkabilir. Testler bu kaynak hassasiyetini açıkça kabul eder; geometriyi zorla 3000 metreye ölçeklemez.

Tümü `python -m tools.world_builder validate LTBU` ile yeniden üretilebilir.

## Sonraki katmanlar

1. tile bölme ve gerçek LOD
2. su yüzeyi malzemesi
3. lisanslı bölgesel OSM extract'inden apron/taksi yolu/yol/bina
4. lisansı doğrulanmış imagery veya kullanıcı GeoTIFF'i
