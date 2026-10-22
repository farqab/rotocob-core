# Kalibrasyon ve Brier Raporu: Toplam Sayı Modeli

Bu rapor `scripts/backtest_calibration.py` ile üretildi. Script `rotobot.db` dosyasını salt okunur açar ve hiçbir şey yazmaz.

## Yöntem

- **Veri:** `empirical_stats_cache` tablosundaki 230 özetten, `MID` ile tekilleştirilmiş 3.958 bitmiş maç (2012–2026). Yaz ligleri hariç tutuldu. Skorlar düzenleme süresi (periyot 201–204) toplamı.
- **Walk-forward:** Her maç için yalnızca o tarihten önceki maçlar kullanıldı. Maç, tahminden sonra geçmişe eklendi. Takım başına son 15 maç, üstel ağırlık (0.14). En az 5 geçmiş maç gerekiyor.
- **Tahmin:** Her maç için takım verilerinden türetilen projeksiyonun etrafında 5 sentetik çizgi (`projeksiyon ± 0, 4, 8`). Motor her çizgi için `P(toplam > çizgi)` döndürüyor; 5.000 simülasyon.
- **Karşılaştırma:** Aynı çizgiler için basit normal dağılım tahmini ve sabit 0.5 tahmini.

## Sonuçlar

Örneklem: 1.901 maç, 9.505 tahmin (maç × çizgi).

| Ölçüt | Değer |
|---|---|
| Brier (motor) | 0.2358 |
| Brier (basit normal) | 0.2357 |
| Brier (sabit 0.5) | 0.2500 |
| Gerçek üst oranı | 0.506 |
| Motorun ortalama tahmini | 0.491 |

### Kalibrasyon

| Tahmin aralığı | n | Ortalama tahmin | Gözlenen oran |
|---|---|---|---|
| 0.3–0.4 | 1.983 | 0.353 | 0.339 |
| 0.4–0.5 | 3.386 | 0.452 | 0.460 |
| 0.5–0.6 | 2.259 | 0.554 | 0.578 |
| 0.6–0.7 | 1.875 | 0.632 | 0.681 |

## Yorum

1. **Ayırt edici güç yok denecek kadar az.** Motor ile basit normal dağılım neredeyse aynı Brier skorunu veriyor (fark 0.0001). Motorun, sadece projeksiyon ve varyanstan çıkan bilgiden fazlasını taşıdığına dair bir kanıt yok.
2. **0.6–0.7 aralığında model tutucu (yetersiz güvenli).** Tahmin 0.632, gözlenen 0.681. Bu bir "muhafazacılık" avantajı değil: model bu bölgede olasılığı olduğundan düşük gösteriyor. Bahis kararında kullanılsaydı, gerçekte değerli olan bazı bahisleri kaçırabilirdi.
3. **Çizgiler sentetik.** Bunlar projeksiyonun etrafına yerleştirildi, gerçek piyasa çizgisi değil. Bu nedenle sonuç bir piyasayı yenme iddiası değil, yalnızca olasılık dağılımının kalibrasyonunu ölçüyor.
4. **Örneklem bağımlılığı.** Her maç 5 çizgi üretiyor ve bu çizgilerdeki sonuçlar birbirine bağlı. Gerçek bağımsız gözlem sayısı 9.505'ten çok daha düşük. Bin başına farklar istatistiksel olarak tek başına kesin bir hüküm vermez.

## Kısıtlar

- Geçmiş piyasa çizgileri ve oranlar yok; **ROI bu raporla test edilemedi**.
- Walk-forward projeksiyon, production motorunun venue / lig / puan durumu karışımını birebir kopyalamıyor. Motora hazır girdi veriliyor, ama girdi üretimi aynı değil.
- Yaz ligleri ve sezon başı maçları ayrı değerlendirilmedi.

## Sonraki adımlar

- `odds_history` tablosu ile kapanış çizgilerini ve oranları arşivleyip gerçek piyasa çizgileriyle kalibrasyonu yeniden koşmak.
- Piyasa çizgisine göre ROI simülasyonu.
- 0.6–0.7 bölgesindeki eksik güveni inceleyip, gerekirse olasılık eşlemesi (kalibrasyon katmanı) eklemek. Bu, motoru değiştireceği için ayrı bir karar ve ayrı bir PR olmalı.
