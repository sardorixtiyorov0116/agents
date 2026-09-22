# Backend topshirig'i №5

> Bu faylni backend dasturchiga bering.

**Tekshirilgan:** `https://climavent-back-production.up.railway.app`
**Sana:** 2026-08-11, birinchi tekshiruv
**Qayta tekshirilgan:** 2026-08-11, kechqurun — pastdagi holat jadvaliga qarang
**Usul:** faqat o'qish. Hech narsa yaratilmadi, o'zgartirilmadi, o'chirilmadi.
Yozish endpointlari faqat **kalitsiz va bo'sh tana** bilan chaqirildi — ruxsat
berilib qolganda ham yozuv hosil bo'lmasligi uchun.
`POST /api/users/login` **ataylab chaqirilmadi** — u haqiqiy pullik SMS yuboradi.

---

## HOLAT (kechqurun qayta o'lchandi)

Dasturchi bir necha soat ichida katta ish qildi. Har biri jonli
tekshirildi:

| # | So'ralgan | Holat | O'lchov |
|---|---|---|---|
| 1 | `airflow_m3h`, `pressure_pa` maydonlari | ✅ **qo'shildi** | maydon bor |
| 1 | ularni to'ldirish | ⏳ qisman | `airflow` 122/1482, `pressure` 72/1482 |
| 2.1 | `bulk-price` DTO tuzatish | ✅ **tuzatildi** | `BulkPriceItemDto` |
| 2 | narx yuklash | ❌ | 25/1482 (o'zgarmadi) |
| 2.2 | `price_valid_until` | ❌ | 1/1482 |
| 3 | `product_model_inside` migratsiyasi | ❌ | **0/941** to'g'ri |
| 4 | 3 endpointga sahifalash | ✅ **qo'shildi** | uchalasi ham ishlaydi |
| 5.1 | `limit=-1` → 400 | ✅ **tuzatildi** | 500 emas, 400 |
| 5.2 | `limit=abc` → 400 | ✅ **tuzatildi** | jimgina tashlamaydi |
| 6 | `characteristics/all` | ✅ **qo'shildi** | 200 |
| 7.2 | `quantity` | ❌ | 0/1482 |

**Bizning tomondan:** sahifalash qo'shilgani klientni buzdi —
`/api/product-models/all` parametrsiz **50** qaytara boshladi (oldin
1482). Narx va SAP kodi shundan qidirilardi. Tuzatildi
(`integrations/climavent_client.py::_sahifalab`), regressiya testi
qo'shildi (`tests/test_sahifalash.py`).

**Qolgan uchta ish — 3, 2 va 7.2.** Ular hali ham kuchda, quyida
batafsil.

---

## 0. XAVFSIZLIK — TO'LIQ YAXSHI ✅

Hech qanday muammo topilmadi. Bu holat 3-topshiriqdan beri saqlanib turibdi.

| Tekshirildi | Natija |
|---|---|
| `reviews/all`, `orders/all`, `order-items/all` | 401 ✅ |
| `cart/all`, `cart-items/all`, `selected-to-checkout/all` | 401 ✅ |
| `users/all`, `users/one/1` | 401 ✅ |
| `products/create`, `update`, `delete` (kalitsiz) | 401 ✅ |
| `product-models/create`, `delete` (kalitsiz) | 401 ✅ |
| `characteristics/create`, `category/create` (kalitsiz) | 401 ✅ |
| `product-models/bulk-price` (kalitsiz) | 401 ✅ |
| `x-ratelimit-limit` | 120 ✅ |
| `strict-transport-security`, `x-content-type-options`, `x-frame-options` | bor ✅ |
| `x-powered-by` | olib tashlangan ✅ |

Tezlik: `products/all?limit=100` — o'rtacha **640 ms** (5 o'lchov: 654, 646,
606, 696, 599). Birinchi so'rov 1927 ms — Railway sovuq startdan uyg'onadi.

---

## 1. ENG MUHIMI — VENTILYATOR TANLASH IMKONSIZ

Bu tizimning **asosiy to'sig'i**. Agent 800 m² ombor uchun 8000 m³/soat
havo sarfi kerakligini to'g'ri hisoblaydi, lekin **shu sarfga mos
ventilyatorni katalogdan topa olmaydi**.

### Ma'lumot BOR — lekin API dan so'rab bo'lmaydi

Butun katalogni tekshirdim (137 mahsulot, har birining R2 hujjatini
o'qib):

| Nima | Soni |
|---|---|
| Mahsulot jami | 137 |
| Texnik hujjati (R2) bor | 124 |
| Texnik hujjati **yo'q** | 13 |
| Hujjatida `Производительность, м³/ч` **bor** | **63** |
| Hujjatida `Полное давление, Па` bor | 41 |
| Shu 63 mahsulotning modellari | **894 / 1482 (60%)** |

*(7 ta R2 fayl o'qilmadi — ya'ni haqiqiy son biroz kattaroq bo'lishi
mumkin, kichikroq emas.)*

Ya'ni **894 model uchun havo sarfi ma'lumoti mavjud**. Lekin u
`characters[].contentJson` → R2 dagi **ProseMirror rich-text hujjat**
ichidagi jadvalda turadi:

```
GET /api/products/one/73
  characters[0].contentJson =
    "https://pub-...r2.dev/98c426a3-..."   ← 27 KB JSON hujjat

Ichida:
  | Типоразмеры | Напряжение, В | Мощность, Вт | Ток, А |
    Частота вращения, об/мин | Производительность, м3/час | Давление, Па |
  | ВР-500      | 220 | 57 | 0,25 | 2500 | 500 | 340 |
  | ВР-1000     | 220 | 85 | 0,37 | 2700 | 900 | 400 |
```

Bu **sayt uchun** chiroyli jadval. Lekin:

- SQL bilan `WHERE airflow >= 8000` deb **filtrlab bo'lmaydi**;
- har mahsulotda jadval **boshqacha tuzilgan** (ustunlar soni, birlashgan
  kataklar, ba'zida ikki qatorli sarlavha);
- 137 ta R2 faylni o'qish uchun 137 ta qo'shimcha HTTP so'rov kerak
  (bizda o'lchandi: ~4 daqiqa).

### `product_model_infos` — qiymat bor, ustun nomi yo'q

`GET /api/product-model-infos/all` → **9706 yozuv**, 1476 model uchun
(o'rtacha 6 ta). Bu aynan yuqoridagi jadvalning qiymatlari:

```json
{ "id": 2916, "product_model_id": 428, "info": "500х300, 520х320, 9" }
```

Maydonlar: `id`, `info`, `product_model_id`, `createdAt`, `updatedAt`.
**`info` — faqat QIYMAT.** Bu qiymat qaysi ustunga tegishli ekani
(`Производительность, м³/ч` mi, `Масса, кг` mi) hech qayerda saqlanmagan.

Tartib bo'yicha taxmin qilib ko'rdim — **ishonchsiz**:

| Mahsulot | Jadval qiymatlari `infos` bilan ustma-ust |
|---|---|
| Вентилятор радиальный ВР | 6/6 ✅ |
| Вентилятор ВК-П | 5/8 ⚠️ |
| Вентилятор ВКРВ | 0/1 ❌ |
| Вентиляторы настенные ВНР-ДУ | 0/2 ❌ |

Ya'ni 2/4. Tartibga tayanib bo'lmaydi.

### NIMA QILISH KERAK

**Variant A (tavsiya etaman) — `product_model_infos` ga ustun nomi qo'shish.**

Ma'lumot allaqachon bazada. Faqat har `info` qiymatiga u qaysi
parametrligini yozib qo'yish kerak:

```sql
ALTER TABLE product_model_infos ADD COLUMN param_key   VARCHAR(64);  -- 'airflow'
ALTER TABLE product_model_infos ADD COLUMN param_label VARCHAR(128); -- 'Производительность'
ALTER TABLE product_model_infos ADD COLUMN unit        VARCHAR(16);  -- 'm3/h'
ALTER TABLE product_model_infos ADD COLUMN value_num   NUMERIC;      -- 8000
ALTER TABLE product_model_infos ADD COLUMN sort_order  INT;
```

To'ldirish: har mahsulotning `characters[].contentJson` jadvalidagi
sarlavha qatori — aynan shu `param_label`. Migratsiya skripti jadvalni
o'qib, ustunlarni `product_model_infos` qatorlariga tartib bo'yicha
biriktiradi; mos kelmaganini ro'yxat qilib bersa, ular qo'lda ko'riladi
(yuqoridagi o'lchovga ko'ra taxminan yarmi qo'lda bo'ladi).

**Variant B (minimal) — `product_models` ga 3 ta ustun.**

Agar A og'ir bo'lsa, hech bo'lmasa ventilyatorlar uchun:

```sql
ALTER TABLE product_models ADD COLUMN airflow_m3h   INT;   -- Производительность
ALTER TABLE product_models ADD COLUMN pressure_pa   INT;   -- Полное давление
ALTER TABLE product_models ADD COLUMN power_kw      NUMERIC;
```

va `GET /api/product-models/all?airflow_min=8000&airflow_max=12000`.

Faqat shu bo'lsa ham KP oqimi ishlaydi: agent kerakli sarfni hisoblaydi,
API dan mos modellarni oladi, KP tuziladi.

### BIZ VAQTINCHA NIMA QILDIK

Kutib turmaslik uchun R2 jadvalini **o'zimiz o'qiydigan** qildik
(`integrations/texnik.py`). Natija:

```
o'qildi          : 266 model
havo sarfi bor   : 251
shundan ventilyator: 149
qamrov           : 1482 modeldan ~17%
```

Endi "8000 m³/soat" hisobiga `ВЦ 14-46-5` (5000–8400 m³/ч, 860–1070 Па,
zaxira +5%) to'g'ri tanlanadi.

**Lekin bu vaqtinchalik yechim, so'rov kuchda qoladi:**

- 137 ta qo'shimcha HTTP so'rov, **80 sekund** — keshlash majburiy;
- jadval har mahsulotda boshqacha tuzilgan, 24 ta mahsulotda umuman
  o'qib bo'lmadi (241 model);
- jadvaldagi nom katalog nomiga har doim mos kelmaydi (jadvalda
  `ВОД 112`, katalogda `ВОД-040-ДУ-0,18-1350`) — 451 model shu sababli
  bog'lanmadi;
- jadval tahrirlansa (dizayn o'zgarsa) o'qish jimgina buziladi.

Bazada bitta ustun bo'lsa — bularning hammasi kerak emas.

---

## 2. NARX — 24 / 1482 (1.6%)

Holat 4-topshiriqdan beri **o'zgarmagan**.

```
modellar jami : 1482
narxi bor     :   24   (1.6%)
valyuta       : hammasi UZS
yangilangan   : hammasi 2026-08-06T11:47:12Z (bitta yuklash)
price_valid_until bor : 0/24
```

Narxi bor 24 ta model — deyarli hammasi `ПВН` seriyasi (havo taqsimlash
panjaralari) va bitta `13mm`.

`POST /api/product-models/bulk-price` **mavjud va 401 qaytaradi** ✅ —
ya'ni yo'l tayyor. Faqat SAP dan eksport qilib yuborish kerak.

### 2.1. `bulk-price` sxemasi noto'g'ri

```json
"requestBody": {
  "content": { "application/json": {
      "schema": { "type": "array", "items": { "type": "string" } } } }
}
```

`array of string` — bu bilan narx yuborib bo'lmaydi. Kerak:

```json
[
  { "sap_name": "ВЦ 4-75-2,5-О-1-0,12/1500",
    "price": 4500000, "currency": "UZS",
    "price_valid_until": "2026-12-31" }
]
```

Swagger DTO ni to'g'rilang — aks holda integratsiya yozayotgan odam
har safar taxmin qilishi kerak.

### 2.2. `price_valid_until` hech qayerda to'ldirilmagan

24 tasining hech birida yo'q. KP da "narx amal qilish muddati" yozilishi
kerak — bu tijorat hujjatining majburiy qismi. Narx yuklashda shu maydon
ham to'ldirilsin.

---

## 3. `product_model_inside` — TO'RTINCHI MARTA

Bu 2-, 3- va 4-topshiriqda ham bor edi.

```
yozuv jami                    : 936
product_model_id TO'G'RI      :   0   ← nol
normallashtirilgan nom bo'yicha
tuzatib bo'ladigani           : 184  (20%)
qo'lda ko'rish kerak          : 752  (80%)
```

Ya'ni SAP kodi (`sap_name`) noto'g'ri modelga bog'langan — **hammasi**.
Shuning uchun KP da SAP kodi ko'rsatilmaydi.

4-topshiriqdagi migratsiya SQL o'zgarmadi, takrorlayman:

```sql
UPDATE product_model_inside AS i
SET    product_model_id = m.id
FROM   product_models AS m
WHERE  regexp_replace(upper(i.in_model_name), '[\s\-/_.]', '', 'g')
     = regexp_replace(upper(m.name),          '[\s\-/_.]', '', 'g');
```

Qolgan 752 tasini ro'yxat qilib bering — men yoki savdo bo'limi qo'lda
ko'rib chiqamiz. Buni hech kim qilmasa, SAP kodi hech qachon ishlamaydi.

---

## 4. SAHIFALASH — 3 ta endpointda yo'q

| Endpoint | `limit`/`page` | Qaytaradi |
|---|---|---|
| `GET /api/products/all` | ✅ ishlaydi | 20 (standart) / 100 / 137 |
| `GET /api/product-models/all` | ❌ **e'tiborsiz** | har doim 1482 (~1.8 MB) |
| `GET /api/product-model-inside` | ❌ e'tiborsiz | har doim 936 |
| `GET /api/product-model-infos/all` | ❌ e'tiborsiz | har doim **9706** |
| `GET /api/category/all` | ❌ e'tiborsiz | har doim 35 (kichik, muammo emas) |

`?limit=50&page=1` yuborilsa ham 1482 ta keladi. Katta uchtasiga
sahifalash qo'shilsin — hozir har chaqiruv keraksiz megabaytlarni
tashiydi.

---

## 5. VALIDATSIYA — 2 ta xato

### 5.1. `limit=-1` → **500 Internal Server Error**

```
GET /api/products/all?limit=-1&page=1
→ 500 {"statusCode":500,"message":"Internal server error"}
```

Manfiy `limit` — foydalanuvchi xatosi, server xatosi emas. **400** bo'lishi
kerak. `ParseIntPipe` ga `min: 1` qo'shing yoki DTO da `@Min(1)`.

### 5.2. `limit=abc` → **200**, parametr jimgina tashlab yuboriladi

```
GET /api/products/all?limit=abc&page=1
→ 200, 137 ta mahsulot (butun katalog)
```

Yaroqsiz qiymat **400** qaytarishi kerak. Hozir mijoz "50 ta so'radim,
137 keldi" degan holatga tushadi va buni sezmaydi.

Solishtirish uchun `products/one` to'g'ri ishlaydi:
`one/abc` → 400, `one/999999` → 404 ✅

---

## 6. `characteristics/all` YO'Q

`docs-json` da faqat 4 ta yo'l bor:

```
POST   /api/characteristics/create
GET    /api/characteristics/one/{id}
PATCH  /api/characteristics/update/{id}
DELETE /api/characteristics/delete/{id}
```

`GET /api/characteristics/all` → **404**.

Ya'ni texnik xususiyatlar ro'yxatini olib bo'lmaydi — faqat `id` ni
oldindan bilsang, bittalab. `all` qo'shilsin (sahifalash bilan).

Shu bilan birga: `characters[]` ichida **texnik xususiyat emas, rasm
havolasi** turadi:

```json
{ "id": 43, "title": "ВК-250П", "price": 0,
  "content":     "https://pub-...r2.dev/8100...",   ← rasm
  "contentJson": "https://pub-...r2.dev/98c4..." }  ← jadval hujjati
```

Nomi `characters` bo'lgani bilan bu **model kartochkasi**. Buni hujjatlab
qo'ying — aks holda har yangi dasturchi shu joyda adashadi.

---

## 7. KATALOG SIFATI

### 7.1. 41 / 137 mahsulotda **modeli yo'q**

Model bo'lmasa — narx ham, SAP kodi ham, KP qatori ham bo'lmaydi.

```
НАРУЖНЫЙ БЛОК HI-FLEXI S MAVO+
Внутренний 4-поточный кассетный блок
Чиллер - машина холодильная JV
Градирня ВГ
Парниковый отопительный агрегат АВО-44
Теплообменник ТСК
Наружний блок JAW
Внутренний блок JAN
... (jami 41 ta)
```

### 7.2. `quantity` — mavjud emas

```
product_models.quantity : 1482 tasida ham NULL
products.quantity       : 93 tasida "1", 19 tasida "50", qolgani 10/100/44/2/30/5
```

Ya'ni mahsulot darajasidagi `quantity` — **haqiqiy ombor qoldig'i emas**,
qo'lda qo'yilgan raqam. Agent "bu mahsulotdan nechta bor?" degan savolga
javob bera olmaydi. SAP dan qoldiq kelsa `product_models.quantity` ga
yozilsin (narx bilan bir vaqtda, bitta `bulk` chaqiruvda bo'lsa yaxshi).

### 7.3. Takroriy mahsulot nomi — 2 ta

```
Вентилятор ВЦ 14-46   ikki marta (48 model va 39 model bilan)
Вентилятор ВЦП 6-46   ikki marta
```

Qaysi biri to'g'ri — savdo bo'limi aytishi kerak. Ikkalasi turgani
uchun agent "qaysi birini olay?" holatiga tushadi.

### 7.4. `producer` uch xil yozilgan

```
JIHOZVENT  105
Jihozvent   31
Climavent    1
```

Bittaga keltirilsin (`UPDATE products SET producer='Jihozvent'`).

### 7.5. 3 ta kategoriya haqiqatan bo'sh

Kategoriya daraxti umuman to'g'ri ishlaydi — `categoryslug` ota
kategoriyani so'rasa bolalarinikini ham qaytaradi (id=13 → 32 ta). Lekin
uchtasi bo'sh **barg** (bolasi ham, mahsuloti ham yo'q):

| id | Nomi | Holat |
|---|---|---|
| 4 | Chiller-fankoyl / Чиллер-фанкойл | bo'sh |
| **20** | **Kanal ventilyatorlari / Канальные вентиляторы** | **bo'sh** |
| 33 | Fan koyllar / Фанкойлы | bo'sh |

**20-si muammo:** kanal ventilyatorlari (ВК, ВКП, ВК-П seriyalari)
katalogda BOR, lekin bu kategoriyaga biriktirilmagan — ular
"Maxsus ventilyatorlar" va boshqa joylarda. Agent "kanal ventilyatori
kerak" deganda shu kategoriyaga qaraydi va **bo'sh** topadi.

Ventilyatorlar hozir shunday taqsimlangan (nomida "ventilyator" bor 40 ta):

```
Markazdan qochma ventilyatorlar  10
Maxsus ventilyatorlar             7
Yumaloq kanallar uchun            4
Tom ventilyatorlari               4
Chang ventilyatorlari             4
O'qli ventilyatorlar              3
Kvadrat kanallar uchun            3
To'rtburchaklar kanallar uchun    2
Tortishma mashinalari             1
Qo'shimcha jihozlar               1
Kon-qazib olish sanoati           1
```

---

## 8. KICHIK NARSALAR

- `GET /api/likes/all` → 404. Sxemada `likes` uchun 6 ta yo'l bor, lekin
  `all` yo'q. Xavfsizlik muammosi emas — shunchaki yo'q.
- `Content-Security-Policy` sarlavhasi yo'q. API uchun jiddiy emas,
  lekin `helmet` allaqachon ulangan ekan, yoqib qo'yish oson.
- `POST /api/products/search` bo'sh matnda 400 qaytaradi ✅ to'g'ri.
- `search("ombor")` → 0 natija. Qidiruv faqat nom bo'yicha ishlaydi,
  tavsif va tayinlanish (`naznacheniya`) bo'yicha emas. Full-text indeks
  qo'shilsa qidiruv ancha foydali bo'ladi.

---

## MUHIMLIK TARTIBI

| # | Ish | Ta'siri | Og'irligi |
|---|---|---|---|
| 1 | **Havo sarfi/bosim — so'ralib bo'ladigan maydon** (1-bo'lim) | KP oqimi ishlaydi | katta |
| 2 | **Narx yuklash** (2-bo'lim) + `bulk-price` DTO tuzatish | KP da narx paydo bo'ladi | o'rta |
| 3 | `product_model_inside` migratsiyasi (3-bo'lim) | SAP kodi ishlaydi | o'rta |
| 4 | `limit=-1` → 500 va `limit=abc` → 200 (5-bo'lim) | ishonchlilik | kichik |
| 5 | Sahifalash 3 ta endpointda (4-bo'lim) | tezlik | kichik |
| 6 | Kategoriya 20 ni to'ldirish (7.5) | qidiruv aniqligi | kichik |
| 7 | `characteristics/all` (6-bo'lim) | qulaylik | kichik |
| 8 | `producer`, takroriy nom (7.3, 7.4) | tozalik | kichik |

**1 va 2 bo'lmasa tizim KP ni to'liq tugata olmaydi** — qolgani
qulaylik va tozalik.

---

## 10. ⚠️ YANGI — `airflow_m3h` QIYMATLARI NOTO'G'RI (17 ta)

Maydon qo'shilgani juda yaxshi. Lekin to'ldirilgan **122** qiymatdan
**17 tasi noto'g'ri** — va xato TIZIMLI.

### Qanday tekshirildi

Backenddagi qiymatni mahsulotning **o'z texnik jadvali** bilan
solishtirdik (`characters[].contentJson` → R2). Ikkala manbada ham
qiymat bor **91** model topildi:

```
mos keladi : 74
ZID        : 17
```

### Zid ro'yxati

| Model | backend `airflow_m3h` | Jadvalda (m³/soat) | Mahsulot |
|---|---|---|---|
| `ВКОП-10` | 750 | 7 060 – 28 400 | Ventilyator ВКОП |
| `ВКОП-5` | 1 000 | 1 120 – 4 500 | Ventilyator ВКОП |
| `ВКОП-6,3` | 1 000 | 2 200 – 9 100 | Ventilyator ВКОП |
| `ВКР-4` | 1 000 | 1 250 – 2 950 | Ventilyator ВКР |
| `ВКР-6,3` | 1 000 | 5 200 – 10 500 | Ventilyator ВКР |
| `ВНР-10-22-1000` | **22** | 20 050 – 40 100 | ВНР-ДУ |
| `ВО 12-300-5` | 1 500 | 4 800 – 7 100 | Ventilyator ВО 12-300 |
| `ВО 12-300-6,3` | 1 000 | 6 150 – 10 000 | Ventilyator ВО 12-300 |
| `ВО 30-160-9` | 950 | 9 800 – 16 195 | Ventilyator ВО 30-160 |
| `ВО 30-160-10` | 960 | 13 425 – 22 355 | Ventilyator ВО 30-160 |
| `ВО 30-160-11,2` | 950 | 18 800 – 31 140 | Ventilyator ВО 30-160 |
| `ВР 6-28-7,1` | 1 500 | 2 520 – 7 560 | Ventilyator ВР 6-28 |
| `ВР 6-28-9` | 1 500 | 5 400 – 16 200 | Ventilyator ВР 6-28 |
| `ВЦП 6-46-5` | 1 500 | 2 130 – 9 040 | Ventilyator ВЦП 6-46 |
| `ВЦП 6-46-6,3` | 1 000 | 3 040 – 12 900 | Ventilyator ВЦП 6-46 |
| `ВЦП 6-46-8` | 1 000 | 6 030 – 20 100 | Ventilyator ВЦП 6-46 |
| `ВЦП 6-46-10` | 1 000 | 8 500 – 34 000 | Ventilyator ВЦП 6-46 |

### Sabab — aylanish tezligi havo sarfi o'rniga tushgan

Ikki dalil:

**1. Qiymatlar takrorlanadi.** `750`, `950`, `960`, `1000`, `1500` —
bular klassik dvigatel tezliklari (об/мин). Havo sarfi hech qachon
bunday takrorlanmaydi: `ВЦП 6-46-5`, `-6,3`, `-8`, `-10` — bular
turli o'lchamdagi g'ildiraklar, sarfi ham turlicha bo'lishi SHART.
Backendda esa to'rttasida ham `1000`.

**2. `ВНР-10-22-1000` → 22.** Bu son model NOMIDAN olingan. 22 m³/soat
— bu sanoat ventilyatori emas, stol ventilyatoridan ham kichik.

Ehtimol migratsiya skripti jadvaldan noto'g'ri **ustunni** oldi:
"Частота вращения, об/мин" ustuni "Производительность, м3/ч" o'rniga.

### Nima qilish kerak

1. Migratsiya skriptini ko'ring — qaysi ustundan o'qiganini tekshiring.
2. Shu 17 ta modelni qayta to'ldiring.
3. **Tekshiruv qo'ying:** havo sarfi < 500 m³/soat bo'lgan sanoat
   ventilyatori bo'lmaydi. Shunday qiymat kiritilsa — ogohlantirsin.
4. `pressure_pa` ni ham shu tarzda solishtirish kerak (hozir faqat
   72 ta to'ldirilgan, ular alohida tekshirilmadi).

### Biz nima qildik

Zid holatda **jadval qiymati olinadi**, backendniki esa
`backend_zid` deb belgilab qo'yiladi. Ya'ni noto'g'ri qiymat KP ga
tushmaydi. Qiymatlar tuzatilgach bu himoya o'z-o'zidan ishlamay
qo'yadi (zid bo'lmaydi).

**Bizning tomondagi xato ham topildi va tuzatildi:** model nomidagi
kasr vergulini olib tashlaganimiz uchun `КЦКП-3,15` va `КЦКП-31,5`
bir xil kalit olardi — ya'ni 3 150 m³/soat lik qurilmaga 31 500
biriktirilgan edi. Bu 4 ta КЦКП modelida yuz bergan, backend esa
ular uchun **to'g'ri** yozgan ekan.
