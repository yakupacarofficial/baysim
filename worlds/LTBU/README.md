# LTBU pilot AirportPack

Bu paket Tekirdağ Çorlu Atatürk Havalimanı'nı BAYSIM'in ilk gerçek dünya doğrulama sahası olarak tanımlar.

## Veri kararı

Pist bilgileri DHMİ AIP Türkiye `LTBU AD 2.12` tablosundan alınmıştır. Resmî tabloda pist `04/22`, boyut `3000 × 45 m`, true bearing değerleri `049.10°/229.12°`, eşik irtifaları `154.9 m/173.9 m` olarak yayımlanır.

Kullanıcının ilk taslağındaki koordinatlar yaklaşık `2749 m` ve `39.77°` ürettiği için kaynak değerleriyle uyuşmamıştır; fixture içine doğrudan alınmamıştır.

## Geçici görsel davranış

Her iki gerçek eşik irtifası manifestte korunur. DEM ve pist-arazi dikişi eklenene kadar `flatten_runways_until_dem` pist mesh'ini dünya orijinindeki `Y=0` düzlemine yatırır. Böylece düz doğrulama zemini pisti kesmez. Profil modu açıldığında yaklaşık 19 metrelik eşik irtifa farkı mesh'e uygulanabilir.

Pist uç koordinatlarının yuvarlanması nedeniyle jeodezik ölçüm, yayımlanan 3000 metreden birkaç metre farklı çıkabilir. Test toleransı bu kaynak hassasiyetini açıkça kabul eder; geometriyi zorla 3000 metreye ölçeklemez.

## Sonraki katmanlar

1. prosedürel pist doğrulaması
2. 15 km yarıçapta Copernicus GLO-30 kırpımı
3. pist düzleştirme ve DEM dikişi
4. lisanslı bölgesel OSM extract'inden apron/taksi yolu/yol/bina
5. lisansı doğrulanmış imagery veya kullanıcı GeoTIFF'i
