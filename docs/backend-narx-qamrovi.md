# Backend bazasi — narx va texnik parametr qamrovi

Sana: 2026-08-21. Manba: `chiqish/narx/backend_snapshot.json`.

## Ikki jadval bor va ular BIR-BIRIGA MOS KELMAYDI

### 1. `product_model` (modellar) — 1482 ta

| | soni |
|---|---|
| jami model | 1482 |
| narxi bor | 25 |
| narxi yo'q | 1457 |
| havo sarfi bor | 122 |
| bosimi bor | 72 |
| **narx VA havo sarfi bor** | **5** |

### 2. `product_model_inside` (variantlar) — 981 ta

| | soni |
|---|---|
| jami variant | 981 |
| narxi bor | 342 |
| narxi yo'q | 639 |
| havo sarfi / bosim ustuni | **jadvalda umuman YO'Q** |

## Asosiy muammo

Narx asosan `inside` jadvalida (342 ta),
texnik parametr esa `model` jadvalida (122 ta).
Ikkalasi ham bor yozuv — atigi 5 ta.

`/kp` obyekt tavsifidan uskuna tanlashi uchun IKKALASI ham kerak:
sarf bo'yicha topadi, narx bo'yicha KP ga qo'yadi.

## Bog'lanish buzuq (alohida xato)

`product_model_inside.product_model_id` — 981 yozuvdan 981 tasi
NOTO'G'RI modelga ishora qiladi.

Misol: `ВЦ 4-75-2,5-1-0,12/1500` (ventilyator varianti) ->
`product_model_id=96` -> `КВН 250-2-1` (suvli isitgich).
To'g'ri ota model bazada BOR: `ВЦ 4-75-2,5-1`, id=1236.

Barcha `product_model_id` qiymatlari 29..327 oralig'ida (152 xil),
to'g'ri modellar esa 1..1577 oralig'ida. Ya'ni eski id maydoni
ishlatilgan — import paytida id moslashtirilmagan.

## Nima qilish kerak

1. `product_model.airflow_m3h` va `pressure_pa` ni to'ldirish —
   ayniqsa ВЦ 4-75, ВЦ 14-46, ВР 6-28 oilalariga (bular eng ko'p sotiladi).
2. `product_model_inside.product_model_id` ni to'g'rilash (nom bo'yicha).
3. Yoki: `inside` jadvaliga sarf/bosim ustunlarini qo'shish.


## Takrorlanishlar

### A. `product_model` ichida — 11 ta takror nom

1482 yozuv, 1471 noyob nom. Ulardan **7 tasi zararsiz** (ikkala nusxa
bir xil, hamma maydon bo'sh), **4 tasi ZIDDIYATLI** — bir xil nom,
lekin texnik parametri HAR XIL:

| Model | 1-nusxa (sarf / bosim) | 2-nusxa (sarf / bosim) |
|---|---|---|
| ВЦП 6-46-5 | 1500 / 2130 | 1500 / 2160 |
| ВЦП 6-46-6,3 | 1500 / 3040 | 1000 / 2890 |
| ВЦП 6-46-8 | 1500 / 6220 | 1000 / 6030 |
| ВЦП 6-46-10 | 1000 / 8500 | 1000 / 11980 |

Ikki nusxaning `product_id` si ham har xil (65 va 66) — ya'ni ВЦП 6-46
katalogda IKKI MARTA alohida mahsulot sifatida kiritilgan. Saytda ham
"ВЕНТИЛЯТОР ВЦП 6-46" ikki marta ko'rinadi.

XAVFI: `/kp` bu modelni tanlasa, qaysi nusxa birinchi kelsa o'shanikini
oladi — bosim 2890 yoki 3040 Pa bo'lishi tasodifga bog'liq.

### B. `product_model_inside` ichida — 1 ta takror

`ДКСп 500х300х350` ikki marta (id 644 va 645), ikkalasi ham narxsiz.
Zararsiz, lekin tozalash kerak.

### C. Ikki jadval ORASIDA — 107 ta bir xil nom

Bir mahsulot ikkala jadvalda ham yozilgan.

| | soni |
|---|---|
| ikkalasida ham narx bor (ziddiyat) | **0** |
| faqat `inside` da narx | 54 |
| faqat `model` da narx | 1 (`ВК-100П`, 999 000 so'm) |
| ikkalasida ham narx yo'q | 52 |

Eng ko'p kesishadigan oilalar: ВКПП (18), ДР (18), ВК- (12),
ФПГ (10), ФПК (10), ПВО (9), ВКП (7), RSK (6), ФКГ (6).

**Narx ziddiyati yo'q** — shuning uchun hozircha noto'g'ri narx
chiqarish xavfi yo'q. `katalog_narxi()` tekshirildi: `inside` dagi
dollarni kursga ko'paytiradi, `model` dagi so'mni ko'paytirmaydi —
ikkalasi ham to'g'ri.
