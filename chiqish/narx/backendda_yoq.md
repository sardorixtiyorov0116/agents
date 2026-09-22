# Narx bor, lekin yozilmagan

Manba: `New Лист Microsoft Excel.xlsx`, ustun `Цена USD с НДС` (har blokning ENG OXIRGISI).
Holat: 2026-08-18.

---

## A. `product_models` da turibdi — USD YOZIB BO'LMAYDI (20 ta)

Bu modellarning `product_model_inside` da qatori YO'Q. `product_models.price` esa
SO'MDA (`currency: UZS`) va MATN turida — u yerga dollar yozsak, `ДР100` "56 so'm"
bo'lib ko'rinadi. Shuning uchun TEGILMADI.

**Qaror kerak** (uchta yo'l README da).

| id | Model | Narx, USD |
|---|---|---|
| 1573 | РКВ-150   | 1154 |
| 1575 | РКВ1-260  | 1607 |
| 228 | ДР100  | 56 |
| 229 | ДР110  | 48 |
| 231 | ДР150  | 59 |
| 232 | ДР180  | 60 |
| 233 | ДР200  | 69 |
| 235 | ДР250  | 84 |
| 236 | ДР300  | 83 |
| 237 | ДР315  | 79 |
| 238 | ДР350  | 81 |
| 239 | ДР400  | 81 |
| 240 | ДР450  | 92 |
| 241 | ДР500  | 110 |
| 242 | ДР550  | 117 |
| 243 | ДР600  | 144 |
| 244 | ДР630  | 131 |
| 246 | ДР710  | 191 |
| 248 | ДР800  | 221 |
| 250 | ДР1000 | 282 |

---

## B. Backendda UMUMAN yo'q (11 ta)

Qo'shish uchun: `POST /api/product-model-inside`.

| Model | Narx, USD | Izoh |
|---|---|---|
| ВЦ 14-46 №2, 0,25 kVt / 1500 | 160,33 | backendda 2,0 uchun 0,37 / 1,5 / 2,2 bor |
| Вентилятор ВР 2,5 А | 196,23 | "ВР ... А" oilasi katalogda umuman yo'q |
| Вентилятор ВР 3 А   | 264,39 | — |
| Вентилятор ВР 3,5 А | 375,06 | — |
| ВКПП/ВКПП-Ш 40х20-1,8 | 206 | nomida "/ВКПП-Ш" bor — ikki mahsulot bitta qatordami? |
| ВКПП 70х40-2DM31 | 432 | backendda `2D31` bor, `2DM31` yo'q |
| ВКПП 80х50-4D40  | 608 | backendda `2D35` bor |
| КПР 40-20 | 222 | butun КПР oilasi katalogda yo'q |
| КПР 50-30 | 307 | — |
| КПР 60-30 | 353 | — |
| КПР 80-50 | 506 | — |

---

## C. Oldingi Exceldan qolgan (6 ta, ВЦ 4-75)

| O'lcham | kVt | Narx USD | characteristic id |
|---|---|---|---|
| ВЦ 4-75-2,5  | 0,37 | 174,51  | 96  |
| ВЦ 4-75-3,15 | 1,1  | 235,14  | 97  |
| ВЦ 4-75-4    | 0,25 | 260,52  | 98  |
| ВЦ 4-75-8    | 5,5  | 1326,23 | 101 |
| ВЦ 4-75-10   | 5,5  | 2038,11 | 102 |
| ВЦ 4-75-12,5 | 15,0 | 3811,15 | 103 |

---

## D. Excelda narxi yo'q (`-` turibdi) — 22 ta

Bular xato emas, shunchaki narx qo'yilmagan: ВКП 80х50-4D40, ВКП 90х50-4D45,
РКВ-038/060/075/110, РКВ1-160/310/400, КПР 50-25/60-35/70-40/90-50/100-50,
ДР120/230/650/750/900/1100/1200, ВКПП 90х50-4D40.

---

## E. Backenddagi ma'lumot xatosi (alohida)

`product_model_inside` da **10 ta takrorlangan nom** bor — bir xil nomda ikkita
yozuv (masalan `ГТП 200x100х1000` -> id 445 va 945). Narx yozishda bular
ATAYLAB chetlab o'tildi (qaysi biriga yozishni bilib bo'lmaydi).
Backendda tozalanishi kerak.
