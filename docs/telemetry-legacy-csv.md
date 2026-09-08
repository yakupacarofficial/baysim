# Geçici CSV telemetri sözleşmesi

Bu belge mevcut prototipin fiilen kabul ettiği paketi tanımlar. Format sürümlü değildir ve kalıcı API sayılmamalıdır. Yerine gelecek protokol hazırlanırken mevcut davranışın test edilebilmesi için kayda geçirilmiştir.

## Taşıma

- Protokol: UDP
- Varsayılan dinleme adresi: bütün yerel arayüzler
- Varsayılan port: `5005`
- İçerik: UTF-8, virgülle ayrılmış tek kayıt
- Başlık satırı: yok
- Minimum alan sayısı: 20
- Fazladan alanlar: bugün yok sayılır
- Bağlantı zaman aşımı: son geçerli paketten sonra 1 saniye

Paket içindeki bütün ilk 20 değer sonlu bir sayı olmalıdır. Eksik, sayısal olmayan, `NaN` veya sonsuz değer taşıyan paket tamamen reddedilir; önceki geçerli durum korunur ve bağlantı zaman damgası yenilenmez.

## Alan sırası

| Sıra | Alan | Birim | Mevcut anlam |
|---:|---|---|---|
| 1 | `north_m` | m | Dünya orijininden yerel kuzey uzaklığı |
| 2 | `east_m` | m | Dünya orijininden yerel doğu uzaklığı |
| 3 | `alt_msl_m` | m | Ortalama deniz seviyesine göre irtifa |
| 4 | `phi_rad` | rad | Roll/yatış açısı |
| 5 | `theta_rad` | rad | Pitch/yunuslama açısı |
| 6 | `psi_rad` | rad | True heading/yaw açısı |
| 7 | `ias_kts` | kt | İşari hava hızı |
| 8 | `agl_m` | m | Yer yüzeyinden yükseklik |
| 9 | `lat_deg` | derece | WGS84 jeodezik enlem |
| 10 | `lon_deg` | derece | WGS84 boylam |
| 11 | `tas_kts` | kt | Hakiki hava hızı |
| 12 | `gs_kts` | kt | Yer hızı |
| 13 | `vs_mps` | m/s | Dikey hız; mevcut HUD pozitif değeri tırmanış kabul eder fakat alıcı işareti doğrulamaz |
| 14 | `alpha_deg` | derece | Hücum açısı |
| 15 | `beta_deg` | derece | Yan kayma açısı |
| 16 | `throttle` | 0..1 | Tek/özet gaz konumu; aralık henüz doğrulanmaz |
| 17 | `rpm` | rpm | Tek/özet motor devri |
| 18 | `nz` | g | Gövde Z ekseni normal yük faktörü |
| 19 | `sim_time_s` | s | Simülasyon zamanı |
| 20 | `mode` | tamsayı | `0=TIRMANIS`, `1=DAIRE`; diğerleri bilinmeyen gösterilir |

Örnek:

```text
10,20,100,0.1,0.2,0.3,90,50,40,30,100,95,-2,3,4,0.75,2200,1.1,12.5,1
```

## Konum alanlarının seçimi

`fdm_link.gd` içindeki `position_source` belirleyicidir:

- `LOCAL_NORTH_EAST` seçilirse 1, 2 ve 3 numaralı alanlar kullanılır.
- `GEODETIC_WGS84` seçilirse 9, 10 ve 3 numaralı alanlar kullanılır.

İki koordinat gösteriminin aynı pakette bulunması geçici formatın bir özelliğidir. Alıcı bu değerlerin birbirleriyle tutarlı olduğunu doğrulamaz.

## Uyum ve sınırlamalar

Bu CSV, JSBSim'in native FlightGear binary UDP paketi değildir. `jsb-forge` içindeki FlightGear çıkışını doğrudan BAYSIM `5005` portuna yönlendirmek çalışmaz.

Formatın kalıcı kullanım için eksikleri:

- Şema sürümü ve mesaj türü yok.
- Uçak/oturum kimliği yok.
- Paket sıra numarası ve üretim duvar-saati yok.
- Kontrol yüzeyleri, iniş takımı, çoklu motorlar ve otopilot durumu yok.
- Birim ve eksen bilgisi paket tarafından taşınmıyor.
- UDP kaybı, tekrar veya sıra bozulması ölçülemiyor.

Yeni protokol bu eksikleri giderdikten ve canlı/replay kaynakları onu kullandıktan sonra bu belge ve ayrıştırıcı “legacy” olarak kaldırılacaktır.
