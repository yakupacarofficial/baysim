# Bayraktar TB2 görsel modeli

Bu klasör TB2'ye ait görsel varlıkları ve Godot sarmalayıcı sahnesini tek paket halinde tutar. JSBSim aerodinamik/kütle modeli bu klasörün parçası değildir.

## İçerik

- `tb2.glb`: ana görsel model
- `tb2_0.png` … `tb2_3.png`: modele bağlı texture dosyaları
- `aircraft.tscn`: telemetri script'ini ve görsel eksen düzeltmesini taşıyan Godot sahnesi

Ölçülen yaklaşık sınırlar 11,96 m genişlik, 2,30 m yükseklik ve 7,54 m uzunluktur. GLB, `ModelRoot` altında Y ekseninde 180° çevrilmiş ve `+0,4 m` yükseltilmiştir.

Bugünkü kamera ofsetleri `World.tscn` içinde elle tanımlıdır. Uçak profili aşamasında eksen düzeltmesi, teker temas yüksekliği ve kamera bağlantıları bu klasördeki profile taşınacaktır.

## Açık provenans kaydı

Modelin kaynak URL'si, üreticisi, lisansı ve projede kullanım izni henüz belgelenmemiştir. GLB içindeki `Sketchfab_Scene` düğüm adı yalnızca olası kaynağa işaret eder; lisans kanıtı değildir. Dağıtımdan önce aşağıdakiler kayda alınmalıdır:

- kaynak sayfa ve indirme tarihi
- eser sahibi
- lisans türü ve lisans metni/bağlantısı
- uygulanan ölçek, eksen, materyal veya geometri değişiklikleri

Kaynak kesinleşmeden bu varlık “yeniden dağıtımı doğrulanmış” kabul edilmemelidir.
