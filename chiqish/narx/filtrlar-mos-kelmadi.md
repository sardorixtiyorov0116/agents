# Filtrlar (ФЯК / ФЯГ) — 82 ta narx

Manba: `New Лист Microsoft Excel.xlsx`, 18.08.2026 13:03 (varaqlar `ФЯК. (2)`, `ФЯГ. (2)`).
Narx: har varaqning ENG OXIRGI `Цена USD с НДС` ustuni (yashil).

## O'lcham jadvali TOPILDI

`products.sizesJson` maydonida (`characters[].contentJson` da emas):

| Mahsulot | Model | O'lcham qatori |
|---|---|---|
| 120 — ФЯК | 24 (`ФЯК-1`…`ФЯК-24`) | 24 |
| 121 — ФЯГ | 24 (`ФЯГ-1`…`ФЯГ-24`) | 24 |

Tartib bir xil, ya'ni `ФЯГ-1 = 287×287×45`, `ФЯГ-2 = 287×287×100` va hokazo.

## Excelning `МОДЕЛЬ` ustuni ISHLATILMAYDI

U takrorlanadi: `287×287×300` va `305×305×300` — ikkalasi ham `295-295-300-3`
deb yozilgan. Moslashtirish A/B/L ustunlaridan qilindi.

---

## ФЯГ — moslashdi (13 ta)

13 ta narxning hammasi bitta modelga aniq tushdi, ziddiyat yo'q.
Faqat `G4 (EU4)` sinfida narx bor; `G3 (EU3)` qatorlari bo'sh.

| O'lcham | Model | id | Narx |
|---|---|---|---|
| 287×287×45 | ФЯГ-1 | 302 | 10 $ |
| 305×305×45 | ФЯГ-3 | 304 | 10 $ |
| 490×287×45 | ФЯГ-5 | 306 | 12 $ |
| 500×500×45 | ФЯГ-7 | 308 | 15 $ |
| 592×287×45 | ФЯГ-9 | 310 | 13 $ |
| … | | | |

**Lekin yozib bo'lmaydi:** bular `product_models` yozuvlari, u yerdagi `price`
SO'MDA va matn turida. Bu — hisobotdagi 1-bo'lim bilan BIR XIL to'siq (РКВ, ДР).

---

## ФЯК — moslashmaydi (64 ta)

Narx FILTR SINFIGA bog'liq, backendda esa sinf o'lchovi YO'Q.

Bitta o'lcham, besh xil narx:

| O'lcham | Sinf | Narx |
|---|---|---|
| 592×592×300, 6 karman | G4 (EU4) | 28 $ |
| 592×592×300, 6 karman | F6 (М6, EU6) | 30 $ |
| 592×592×300, 6 karman | F7 (EU7) | 29 $ |
| 592×592×300, 6 karman | F8 (EU8) | 31 $ |
| 592×592×300, 6 karman | F9 (EU9) | 33 $ |

Backendda esa faqat `ФЯК-13` bor — bitta yozuv, bitta narx maydoni.
24 ta modelning **14 tasiga** bir nechta narx to'g'ri keladi.

**Kerak:** `product_model_inside` da o'lcham × sinf bo'yicha qatorlar,
masalan `ФЯК-13-F7`. Shundan keyin 64 ta narx ham joyiga tushadi.

---

Ma'lumot: `chiqish/narx/filtrlar.json` — 82 qator, jami 2 004 USD.
