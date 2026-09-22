# Backend topshirig'i №2 — API tekshiruvi natijalari

> Bu faylni backend dasturchiga bering — Claude Code'ga to'g'ridan-to'g'ri
> topshiriq sifatida berish mumkin.

**Tekshirilgan:** `https://climavent-back-production.up.railway.app`
**Sana:** 2026-07-30
**Usul:** faqat o'qish va zararsiz probalar — hech qanday yozuv yaratilmadi,
o'zgartirilmadi, o'chirilmadi. Yozish endpointlari mavjud bo'lmagan
`id = 99999999` yoki bo'sh tana bilan tekshirildi (guard va validatsiya
handlerdan oldin ishlaydi, shuning uchun bazaga tegilmaydi).

---

## Avvalgi topshiriq bo'yicha: bajarilgan

`X-API-Key` xizmat kaliti to'g'ri ishlaydi:

| Sinov | Natija |
|---|---|
| Guvohnomasiz `POST /api/products/create` | `401` ✅ |
| To'g'ri `X-API-Key` bilan | `400` (validatsiya) — kalit qabul qilindi ✅ |
| Noto'g'ri `X-API-Key` bilan | `401` ✅ |

Kalit biz ishlatadigan **9 ta amalning hammasida** qabul qilinadi
(`products`, `product-models`, `characteristics` uchun create/update/delete).

Auth endi 32 ta yozish endpointida bor. `users/update`, `users/delete`,
`cart`, `likes` ham himoyalangan. Rahmat — narxlar endi begonaga ochiq emas.

---

## 1. KRITIK / YUQORI — tuzatish kerak

### 1.1. `PATCH` mavjud bo'lmagan id da `500` qaytaradi

```
PATCH /api/products/update/99999999        → 500  (kutilgan: 404)
PATCH /api/product-models/update/99999999  → 500  (kutilgan: 404)
```

Server ichki xatosi. Chaqiruvchi "backend yiqildi" deb tushunadi, aslida
shunchaki yozuv yo'q. Handler'da avval `findOne` qilib, topilmasa
`NotFoundException` tashlansin.

### 1.2. `PATCH /api/characteristics/update/{id}` yo'q yozuvga `200` qaytaradi

```
PATCH /api/characteristics/update/99999999 → 200  (kutilgan: 404)
```

**Eng xavflisi shu.** Hech narsa yangilanmagan bo'lsa ham "muvaffaqiyat"
qaytadi. Bizning tizim buni "narx yozildi" deb qabul qiladi va menejerga
shunday deb aytadi — aslida katalog o'zgarmagan.

Yechim: `update` natijasidagi `affected` (yoki yangilangan yozuv) tekshirilsin,
0 bo'lsa `404`.

### 1.3. Qidiruv `models` massivini qaytarmaydi

```
POST /api/products/search {"text": "вентилятор"}  → 40 natija, models: yo'q
GET  /api/products/all                            → models bor
```

Narx `product_models.price` da turadi. Qidiruv uni qaytarmagani uchun
narxni ko'rsatish uchun **butun katalogni** (`/api/products/all`, 698 KB)
yuklashga majbur bo'lamiz — har bir KP tuzilganda.

Yechim: `search` javobiga `models` (kamida `id`, `name`, `price`) qo'shilsin.

### 1.4. `POST /api/order-items/create` da auth yo'q

```
POST /api/order-items/create  → 400 (auth tekshirilmaydi)
```

`orders` himoyalangan, lekin uning qatorlari emas. Begona odam mavjud
buyurtmaga qator qo'sha oladi. `selected-to-checkout/create` da ham auth yo'q —
u qaysi foydalanuvchiga tegishli ekanini tekshirish kerakmi, ko'rib chiqing.

`reviews/create` ochiq qolgani to'g'ri (mehmon sharh yozadi), lekin
`reviews/update` va `reviews/delete` himoyalanganini tasdiqlang.

---

### 1.5. `product_model_inside.product_model_id` — BUZUQ bog'lanish

Manba: `GET /api/product-model-inside` → **932 yozuv**, hammasida
`sap_name` to'ldirilgan. Yozuvlar shakli:

```json
{ "id": 3,
  "sap_name":  "ВЦ 4-75-2,5-О-1-0,12/1500",
  "in_model_name": "ВЦ 4-75-2,5-1-0,12/1500",
  "product_model_id": 96 }
```

Muammo: `product_model_id` mavjud qatorga ishora qiladi (yetim yo'q),
lekin **butunlay boshqa oiladagi** modelga:

```
product_models.id = 96  ->  "КВН 250-2-1"   (suvli isitgich)
products.id       = 96  ->  "Дроссель клапан ДКСК и ДК"  (klapan)
```

`ВЦ` — markazdan qochma ventilyator. Isitgich ham, klapan ham emas.

**932 yozuvning 932 tasida** SAP kodi oilasi ota-model oilasiga mos
kelmaydi (`id` bo'yicha tekshirildi, massiv indeksi bo'yicha emas):

| Tekshiruv | Natija |
|---|---|
| `product_model_id` → `product_models.id` mos | **0 / 932** |
| `product_model_id` → `products.id` mos | **0 / 932** |
| `in_model_name` `product_models.name` da bor | 81 / 932 |

Yana bir misol: `КСК 113-3-02` (panjara) ga `ВКПН` va `ВКПП` (kanal
ventilyatorlari) bog'langan — bitta modelga ikki xil oila.

**Guruhlash o'zi buzilmagan:** masalan `id=261` ga 118 ta ichki yozuv
tegishli va ular o'zaro izchil. Ya'ni faqat NISHON id'lar surilgan —
ehtimol migratsiya paytida `product_models` id'lari qayta berilgan.
Eng ishonchli tuzatish yo'li — `in_model_name` bo'yicha qayta bog'lash.

**Hozircha qanday chiqib turibmiz.** `product_model_id` ni umuman
ishlatmaymiz — bog'lanishni **`in_model_name` bo'yicha** quramiz.
Ajratuvchi belgilar farq qiladi, shuning uchun taqqoslashdan oldin
soddalashtiramiz (`ПВН 500-250-2` → `ПВН500250 2`):

```
katalog: ПВН 500-250-2   ->  SAP: ПВН 500-250/2
katalog: ВР 6-28-4-1-0,37-1500  ->  SAP: ВР 6-28-4-О-1-0,37/1500
```

Shu usul bilan **1482 modeldan 185 tasiga** kod topiladi (SAP jadvalida
umuman 143 model bor, farq — bir modelning bir necha varianti).

Bu VAQTINCHA yechim: `in_model_name` unikal emas (1 ta ziddiyat bor —
`ДКСП 500Х300` ikki xil kodga ishora qiladi, biz uni ishlatmaymiz).
`product_model_id` tuzatilsa, bog'lanish ishonchli bo'ladi.

Qamrov esa yetarli emas: **1482 modeldan 1297 tasida SAP kodi yo'q.**
Narxi bor 24 modeldan faqat 9 tasiga kod topildi — qolgan 15 tasida KP
da katalog nomi chiqadi.

## 2. O'RTA — ishlashga ta'sir qiladi

### 2.1. `/api/products/all` sahifalanmaydi

```
GET /api/products/all?limit=10&page=1  → 137 yozuv (limit e'tiborga olinmaydi)
Javob hajmi: 698 KB, vaqt: ~1.7 s
```

`limit` / `page` qo'llab-quvvatlansin. Hozir mahsulot soni o'sgan sari javob
ham o'sib boradi.

### 2.2. Qidiruv model kodini topmaydi

```
"ВК-250П"        → 0 natija
"ПВН 500-250-2"  → 0 natija
"kanal ventilyatori" → 0 natija
"вентилятор"     → 40 natija
```

Model kodlari `models[].name` va `characters[].title` ichida, qidiruv esa
faqat mahsulot nomi bo'yicha ishlaydi. Menejerlar aynan model kodi bilan
qidiradi.

Yechim: qidiruvga `models.name` va `characters.title` ham qo'shilsin
(`LEFT JOIN` + `ILIKE`).

### 2.3. Sahifalash maydonlari majburiy

```
POST /api/products/lastadded {"page": 1}  → 400 (limit yo'q)
```

`limit` uchun standart qiymat (masalan 20) qo'yilsa qulayroq bo'ladi.

### 2.4. Swagger sxemasi haqiqatdan orqada

`/api/docs-json` da `users/update`, `users/delete` hamon `security` siz
ko'rinadi, aslida ular himoyalangan. Yangi guard qo'yilgan endpointlarga
`@ApiSecurity('service-key')` (yoki `@ApiBearerAuth()`) qo'shilsin — aks holda
sxemaga qarab ishlaydigan har qanday integratsiya chalg'iydi.

---

## 3. MA'LUMOT SIFATI — kod emas, kontent

Bular dasturchining emas, katalogni to'ldiradigan xodimning ishi, lekin
ro'yxatga kiritdim.

| Muammo | Miqdor |
|---|---|
| `price = 0` bo'lgan modellar | **1458 / 1482** |
| Narxi bor mahsulotlar | 3 / 137 |
| Birorta modeli yo'q mahsulotlar | 41 |
| Takroriy model nomlari | 11 ta nom |

Shubhali qiymat: `ВР 6-28-4-1-0,37-1500` narxi **14 so'm** — aniq kiritish
xatosi. Ventilyator 14 so'm bo'lmaydi. Tuzatilsin yoki 0 ga qaytarilsin.

### 3.1. Ombor qoldig'i model darajasida yo'q

`quantity` faqat `products` jadvalida. Ya'ni "ВК-250С dan nechta bor?"
degan savolga aniq javob bera olmaymiz — faqat butun seriya bo'yicha
aytamiz:

```
products[25] "Вентилятор ВК-С"  quantity = 548
  modellari: ВК-100С, ВК-125С, ВК-160С, ВК-200С, ВК-250С, ВК-315С
```

548 dona — olti modelning YIG'INDISI. Menejer mijozga aynan ВК-250С
qoldig'ini aytolmaydi.

Yechim: `product_models` jadvaliga ham `quantity` qo'shilsa, savdo
savoliga aniq javob chiqadi. Ustuvorligi past — avval narx muhim.

Takroriy nomlar (har biri 2 marta): `Д 15,5-3-500-1000`,
`ВОД-040-ДУ-0,18-1350`, `ВОД-063-ДУ-2,2-1390`, `ВОД-080-ДУ-11,0-1435`,
`ВЦП 6-46-5`. Bir xil nomli ikki model narx qidiruvida chalkashlik beradi.

---

## 4. Tekshirish uchun

Har bir tuzatishdan keyin (hech narsa yaratmaydi):

```bash
# 404 kutiladi, 500 emas
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH \
  -H 'Content-Type: application/json' -H "X-API-Key: $SERVICE_API_KEY" \
  -d '{}' https://climavent-back-production.up.railway.app/api/products/update/99999999

# 404 kutiladi, 200 emas
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH \
  -H 'Content-Type: application/json' -H "X-API-Key: $SERVICE_API_KEY" \
  -d '{}' https://climavent-back-production.up.railway.app/api/characteristics/update/99999999

# javobda "models" bo'lishi kerak
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"text":"ПВН"}' \
  https://climavent-back-production.up.railway.app/api/products/search | head -c 400

# 401 kutiladi
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Content-Type: application/json' -d '{}' \
  https://climavent-back-production.up.railway.app/api/order-items/create
```

SAP bog'lanishini (1.5) tekshirish — SAP kodi oilasi ota-model
oilasiga mos kelishi kerak:

```bash
curl -s https://climavent-back-production.up.railway.app/api/product-model-inside \
  | head -c 400
# `product_model_id` ni olib, o'sha id li modelni ko'ring:
curl -s https://climavent-back-production.up.railway.app/api/product-models/all \
  | python -c "import json,sys; d=json.load(sys.stdin); \
print({m['id']: m['name'] for m in d if m['id'] == 96})"
# Hozir: {96: 'КВН 250-2-1'} — 'ВЦ ...' SAP kodiga mos emas
```

---

## 5. Ustuvorlik

1. **1.5** — SAP kodlari buzuq bog'langan (KP ga rasmiy kod qo'ya olmayapmiz)
2. **1.2** — `characteristics` yolg'on `200` (bizga noto'g'ri ma'lumot beradi)
3. **1.4** — `order-items` auth (xavfsizlik)
4. **1.1** — `500` o'rniga `404`
5. **1.3** — qidiruvga `models` (tezlik: 698 KB o'rniga bir necha KB)
6. **2.2** — model kodi bo'yicha qidiruv (menejerlar ishi uchun)
7. Qolganlari
