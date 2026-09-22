# Narx yuklash izlari

## Manba

`PRICE JIHOZVENT_v5.1.xlsx` (buxgalteriya), 18.08.2026. 36 varaq.
Olingan ustun: **har blokning ENG OXIRGI `Цена USD с НДС` ustuni** (yashil fonli).
Undan oldingi sariq juftlik OLINMAYDI — u tannarxga o'xshaydi.

Narx backendda `product_model_inside.price` da **DOLLARDA** saqlanadi.
So'm narxi saqlanmaydi — `USD_KURSI` (12 000) ga ko'paytirib hisoblanadi.
Kurs manbasi: Excelning o'zida (`КОГ` varag'i, «Курс 12000»).

## Fayllar

| Fayl | Nima |
|---|---|
| `PRICE JIHOZVENT_v5.1 - IZOHLI.xlsx` | Manba fayl + qizil izoh kataklari (nima uchun yozilmadi) |
| `prays_v51.json` | Exceldan ajratilgan barcha narxli qatorlar |
| `reja_v51.json` | `yoziladi` / `xato` (sabab bilan) |
| `izohlar.csv` | Qaysi varaq/qator/ustunga qanday izoh qo'yilgani |
| `backend_snapshot.json` | Yozishdan oldingi backend holati |
| `backendda_yoq.md` | Oldingi (birinchi) Exceldan qolganlar |
| `filtrlar-mos-kelmadi.md` | ФЯК / ФЯГ tahlili |

## Varaq bo'yicha ustunlar

Har varaqning ustunlari QO'LDA belgilangan (`prays.py` dagi `SOZLAMA`), avtomatik
taxmin qilinmaydi — narx ustunini adashtirish jim xatoga olib keladi.

Uch xil moslashtirish:
- **nom** — Excelda tayyor model nomi (`ВКП 40х20-4E20`);
- **quvvat** — oila + o'lcham + kVt (`ВЦ 4-75 №2,5` + `0,55`);
- **o'lcham** — prefiks + AxB (`РВН 300х300`), backend shu shaklda saqlaydi.

## Ma'lum to'siqlar

1. **`product_models` da turgan modellar** (ДР, РКВ, РЩ, ФЯГ) — u yerdagi `price`
   SO'MDA va matn turida. Dollar yozib bo'lmaydi. Qaror kerak.
2. **ФЯК** — narx filtr sinfiga (G4/F6/F7/F8/F9) bog'liq, backendda sinf o'lchovi yo'q.
3. **КПУ НО / КПД НЗ** — backendda faqat `КПУ (15)`, `КПУ (30)` … (yong'inga chidamlilik
   bo'yicha), o'lcham bo'yicha yozuv yo'q.
4. **АВКв** — Excelda `200х210`, backendda `200х200`. Ikkinchi o'lcham hamma 24 qatorda
   aynan 10 mm farq qiladi. Qaysi biri to'g'ri — aniqlanishi kerak.
5. **КОП, ДКСП, КЛ** — backendda tartib raqami bilan (`КОП - 1`, `ДКСк (рис. 1) 1`,
   `КЛ-1`), Excelda o'lcham bilan. O'lcham -> raqam jadvali kerak.
6. **РВ-1, РВр-1, РВр-2** — Excelda yuzlab o'lcham, backendda o'nlab. Yetishmaganlari
   yaratilishi kerak.

---

## 2026-08-18 yakuniy holat

| | |
|---|---|
| `product_model_inside` | 981 qator, **342 tasida narx** |
| Men yozganim | 299 ta (PATCH) |
| Frontchi yaratgani | 43 ta yangi qator (ДР, ФЯГ, РКВ, РЩ) + sap_name |

Saytda tekshirildi (climavent.uz):

| Mahsulot | Saytda | Kutilgan | |
|---|---|---|---|
| ДР (118) | 576 000 UZS | 48 $ × 12 000 | ✅ |
| РКВ (154) | 13 848 000 UZS | 1 154 $ | ✅ |
| РЩ (110) | 240 000 UZS | 20 $ | ✅ |
| ФЯГ (121) | 120 000 UZS | 10 $ | ✅ |
| Katalog ro'yxati | «from 1 272 000 UZS» | ПВН 106 $ | ✅ |

`categoryslug` ham tuzatildi — narx endi ro'yxatda ham ko'rinadi.

**Qolgan ish:** 6 guruh takrorlangan nom, 43 ta bo'sh R2 fayli,
`product_models` dagi 25 ta eski narx (`ПВН …-3` avval ko'chirilsin).
