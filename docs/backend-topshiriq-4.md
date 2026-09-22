# Backend topshirig'i №4

> Bu faylni backend dasturchiga bering — Claude Code'ga to'g'ridan-to'g'ri
> topshiriq sifatida berish mumkin.

**Tekshirilgan:** `https://climavent-back-production.up.railway.app`
**Sana:** 2026-08-06
**Usul:** faqat o'qish va zararsiz probalar. Hech narsa yaratilmadi,
o'zgartirilmadi, o'chirilmadi.

---

## 0. AVVALGI TOPSHIRIQ — YAXSHI BAJARILGAN

3-topshiriqning xavfsizlik qismi **to'liq** yopilgan. Buni alohida yozib
qo'yaman, chunki ish sifatli qilingan:

| Nima | Holat |
|---|---|
| `reviews/all` — mijoz telefoni va emaili ochiq edi | ✅ 401 |
| `order-items/all`, `cart-items/all`, `selected-to-checkout/all` | ✅ 401 |
| Begona odam savatini o'chirish (`deletebyuser/{id}`) | ✅ 401 |
| `cart-items` create / update / delete — auth yo'q edi | ✅ 401 |
| Tezlik cheklovi (`x-ratelimit-limit: 120`) | ✅ qo'yilgan |
| `helmet` sarlavhalari, `x-powered-by` olib tashlangan | ✅ |
| `500` → `400` (`ParseIntPipe`) | ✅ |
| Lotincha qidiruv (`ventilyator` → 40 natija) | ✅ ishlaydi |

Quyidagi ro'yxat — **qolgani va yangi topilganlari**.

---

## 1. BIRINCHI NAVBATDA

### 1.1. `product_model_inside.product_model_id` — uchinchi marta

Bu 2- va 3-topshiriqda ham bor edi. Holat o'zgarmagan: **932 yozuvning
932 tasi** noto'g'ri modelga bog'langan.

```json
{
  "id": 3,
  "sap_name":      "ВЦ 4-75-2,5-О-1-0,12/1500",   // markazdan qochma ventilyator
  "in_model_name": "ВЦ 4-75-2,5-1-0,12/1500",
  "product_model_id": 96                            // → "КВН 250-2-1" (suvli isitgich)
}
```

Bugun qo'shimcha o'lchov qildim: `in_model_name` ni
`product_models.name` bilan **aynan** solishtirsa, 932 tadan faqat **81
tasi** mos tushadi. Ya'ni nomlar ham bir xil yozilmagan — ajratuvchi
belgilar farq qiladi:

```
product_models.name          ПВН 500-300-2
product_model_inside.sap_name ПВН 500-300/2      ← "/" va "-"
```

**Nima qilish kerak (migratsiya skripti):**

```sql
-- 1-qadam: normallashtirilgan nom bo'yicha qayta bog'lash.
-- Normallashtirish: bo'sh joy, "-", "/", "_", "." — hammasi olib tashlanadi,
-- harflar katta qilinadi.  "ПВН 500-300/2" -> "ПВН5003002"
UPDATE product_model_inside AS i
SET    product_model_id = m.id
FROM   product_models AS m
WHERE  regexp_replace(upper(i.in_model_name), '[\s\-/_.]', '', 'g')
     = regexp_replace(upper(m.name),          '[\s\-/_.]', '', 'g');
```

```sql
-- 2-qadam: mos kelmaganlarni ro'yxat qilib bering — ular qo'lda ko'riladi.
SELECT i.id, i.sap_name, i.in_model_name
FROM   product_model_inside i
WHERE  NOT EXISTS (
         SELECT 1 FROM product_models m
         WHERE regexp_replace(upper(i.in_model_name), '[\s\-/_.]', '', 'g')
             = regexp_replace(upper(m.name),          '[\s\-/_.]', '', 'g')
       );
```

**Diqqat:** avval `SELECT` bilan nechta qator o'zgarishini ko'ring, keyin
`UPDATE` qiling. Bir xil normallashtirilgan nomga ikkita model to'g'ri
kelsa — ular ham qo'lda ko'rilsin (bunday nomlar 11 ta bor, 1.4-bo'limga
qara).

**Nega muhim:** tijorat taklifida (KP) mahsulotning rasmiy SAP kodi
chiqishi kerak. Hozir biz `product_model_id` ni umuman ishlatmay, nomni
o'zimiz normallashtirib bog'lab turibmiz — bu vaqtinchalik yechim va u
narxi bor 24 modeldan faqat 9 tasini qamrab olyapti.

### 1.2. `product_models` da `sap_name` bo'lsin

Yuqoridagi muammoning ILDIZI shu: SAP kodi alohida jadvalda turadi va
uni har safar bog'lash kerak.

```
Hozir:  product_models  →  product_model_inside.sap_name  (bog'lanish buzuq)
Kerak:  product_models.sap_name                            (to'g'ridan-to'g'ri)
```

1.1 dagi migratsiya ishlagach, qiymatni modelning o'ziga ko'chirish
mumkin. Shundan keyin `product_model_inside` faqat tarix uchun qoladi va
hech kim uni bog'lashga urinmaydi.

### 1.3. Narx maydonida buzuq qiymatlar

```
id=807   "Д 2,7-1-3,0-3000"        price = "."     ← raqam emas
id=1003  "ВКОП-8"                  price = "."     ← raqam emas
id=?     "ВР 6-28-4-1-0,37-1500"   price = "14"    ← 14 so'm, aniq xato
```

`price` hozir **matn** (`string`) tipida, shuning uchun `"."` kabi
qiymat bemalol saqlanyapti. Ikki ish:

1. Tipni `numeric(14,2)` ga o'tkazing (yoki `int` — tiyin kerak
   bo'lmasa), `NULL` ruxsat etilsin;
2. **`0` va `NULL` ni ajrating.** Hozir `"0"` ikki ma'noni bildiryapti:
   "narx kiritilmagan" va "narx nol". Bizning tizim buni ajrata olmaydi
   va KP da noto'g'ri narx chiqish xavfi bor. `NULL` = kiritilmagan.

Qo'shimcha maydonlar (juda foydali bo'lardi):

| Maydon | Nega |
|---|---|
| `currency` | so'mmi, dollarmi — hozir taxmin qilyapmiz |
| `price_updated_at` | narx qachon yangilangan — KP da "narx N kunlik" deyish uchun |
| `price_valid_until` | taklif muddati |

### 1.4. Takroriy model nomlari

11 ta nom ikki martadan takrorlanadi (jami 22 yozuv):

```
Д 15,5-3-500-1000        ВЦП 6-46-5
ВОД-040-ДУ-0,18-1350     ВЦП 6-46-6,3
ВОД-063-ДУ-2,2-1390      ВЦП 6-46-8
ВОД-080-ДУ-11,0-1435     ВЦП 6-46-10   va boshq.
```

Bir xil nomli ikki model narx qidiruvida chalkashlik beradi: qaysi
biriga narx qo'yilgan noma'lum bo'ladi. Ikkitasi haqiqatan boshqa
mahsulot bo'lsa — nomini aniqlashtiring; nusxa bo'lsa — o'chiring.

Keyinchalik takrorlanmasligi uchun: `UNIQUE (product_id, name)`.

---

## 2. YANGI — tizim uchun kerak

### 2.1. Model darajasida ombor qoldig'i

`quantity` faqat `products` da bor, `product_models` da yo'q.

```
Savol:  "ВК-250С dan nechta bor?"
Javob:  bera olmaymiz — faqat butun seriya bo'yicha aytamiz
```

Mijoz va menejer aynan modelni so'raydi, seriyani emas. `product_models`
ga `quantity` (yoki `stock`) qo'shilsa, savdo bo'limining eng ko'p
beriladigan savoliga aniq javob chiqadi.

### 2.2. Narxni ommaviy yuklash uchun endpoint

1482 modelning 24 tasida narx bor (1,6%). Qolganini kimdir kiritishi
kerak — bittalab `PATCH` bilan emas.

```
POST /api/product-models/bulk-price
Content-Type: application/json
X-API-Key: <xizmat kaliti>

[
  {"name": "ПВН 500-300-2", "price": 1930000, "currency": "UZS"},
  {"name": "ПВН 500-300-3", "price": 2520000, "currency": "UZS"}
]
```

Javobda: nechtasi yangilandi, nechta nom topilmadi (ro'yxat bilan).
Nom bo'yicha topish 1.1 dagi normallashtirish bilan bo'lsin.

Bu bo'lsa, narxlar Excel'dan bir marta yuklanadi. Busiz kontent ishi
bir necha kunga cho'ziladi.

### 2.3. `product-model-inside` sahifalanmaydi

```
GET /api/product-model-inside?limit=5&page=1  →  932 ta yozuv qaytadi
```

Boshqa endpointlarda sahifalash bor, bu yerda yo'q. Bir xil qilish
kerak.

### 2.4. `/api/products/all` — sahifalash chala

```
(parametrsiz)        → 698 KB, 137 ta, 1.21 s
?limit=20            → 698 KB, 137 ta      ← limit YOLG'IZ ishlamaydi
?limit=20&page=1     →  86 KB,  20 ta      ← faqat ikkalasi birga
```

1. `limit` `page` siz ham ishlasin (`page` bo'lmasa `1` deb olinsin);
2. parametrsiz chaqiruvga standart chegara qo'yilsin (masalan 20).

Hozir har bir mijoz sahifani ochganda 698 KB yuklab olyapti.

### 2.5. Modelda "standart / buyurtma bo'yicha" belgisi

Kompaniyada narx ikki xil yuritiladi:

- **standart tovar** — narx SAP'da turadi;
- **standart bo'lmagan** (nostandart o'lcham, maxsus bajarilish) — narx
  har safar buxgalterdan so'raladi, oldindan turgan narx yo'q.

Tizim buni **hozir ajrata olmaydi**: `product_models` da bunday maydon
yo'q. Natijada nostandart mahsulot ham "narxi kiritilmagan" bo'lib
ko'rinadi va uni xato deb hisoblaymiz.

```
product_models.narx_turi:  'standart' | 'buyurtma'
```

Bo'lsa, agent nostandart mahsulotga narx qidirmay, tijorat taklifida
darrov "narx buxgalteriyadan so'raladi" deb yozadi — bu to'g'ri javob,
xato emas.

### 2.6. O'zgarganlarini olish (inkremental sinxronizatsiya)

Bizning tizim katalogni takrorlab o'qiydi. Hozir har safar hammasini
olishga majburmiz.

```
GET /api/product-models/all?updatedAfter=2026-08-01T00:00:00Z
```

`updatedAt` allaqachon bor — faqat filtr qo'shilsa yetadi. Bu trafikni
ham, javob vaqtini ham keskin kamaytiradi.

---

## 3. LOGIN VA SMS — tasdiqlashingiz kerak

**Buni men tekshira olmadim, ataylab:** `POST /api/users/login` haqiqiy
SMS yuboradi va u pullik. Kompaniya pulini sarflamaslik uchun sinamadim.

3-topshiriqdagi 1.5–1.7 bo'limlari bo'yicha javob bering:

- [ ] `POST /users/login` endi `users` jadvaliga **darhol yozmaydimi**?
      (yozuv faqat `verify-otp` dan keyin paydo bo'lishi kerak)
- [ ] Bitta raqamga **5 daqiqada 1 SMS** cheklovi qo'yildimi?
- [ ] Bitta raqamga **sutkasiga 5 ta SMS** cheklovi qo'yildimi?
- [ ] `refresh token` **60–90 kunga** uzaytirildimi?
      *(bu SMS xarajatini kamaytirishning ASOSIY yo'li — mijoz har
      kirishda SMS olmaydi)*
- [ ] OTP muddati **5 daqiqa**, **3 marta** xato urinishdan keyin bekor
      qilinadimi?
- [ ] Tasdiqlangan kod qayta ishlatilmaydimi?
- [ ] Sinov paytida paydo bo'lgan yozuv o'chirildimi?
      `users.id = 15`, `phone_number = +998900000000`

Agar bularning biri qilinmagan bo'lsa — 3-topshiriqning 1.7-bo'limida
to'liq yozilgan.

---

## 4. KICHIK KAMCHILIKLAR

### 4.1. Qidiruvda qo'shimchali shakl

```
kanal ventilyator   → 6 natija  ✅
kanal ventilyatori  → 0 natija  ❌
```

`ventilyatori` alohida so'z deb hisoblanadi va kesishma bo'sh chiqadi.
O'zbek tilida qo'shimcha odatiy — `ILIKE '%so'z%'` ishlatilsa yoki
so'z oxiridagi 1-2 harf kesilsa yechiladi. Shoshilinch emas.

### 4.2. Modeli yo'q mahsulotlar

**41 / 137** mahsulotning birorta modeli yo'q. Ular katalogda ko'rinadi,
lekin ularni tanlab bo'lmaydi va narx ham chiqmaydi. Bu kontent ishi —
dasturchi emas, katalog administratori hal qiladi.

### 4.3. Rasmi yo'q mahsulot — 1 ta

---

## 5. TEKSHIRISH BUYRUQLARI

Hech narsa yaratmaydi va o'chirmaydi:

```bash
ASOS=https://climavent-back-production.up.railway.app

# 1.1 — bog'lanish to'g'rilanganini tekshirish.
# "ВЦ ..." sap_name li yozuv "ВЦ ..." modeliga ko'rsatishi kerak.
curl -s "$ASOS/api/product-model-inside" | head -c 400
curl -s "$ASOS/api/product-models/one/96"

# 1.3 — buzuq narx qolmasin (hozir 2 ta "." qiymat bor)
curl -s "$ASOS/api/product-models/all" \
  | python -c "import sys,json;d=json.load(sys.stdin);print([(m['id'],m['name'],m['price']) for m in d if not str(m['price'] or '0').replace('.','').isdigit()])"

# 2.1 — model darajasida qoldiq bormi
curl -s "$ASOS/api/product-models/one/44" | grep -o quantity || echo "quantity YO'Q"

# 2.3 — 5 ta qaytishi kerak
curl -s "$ASOS/api/product-model-inside?limit=5&page=1" \
  | python -c "import sys,json;print(len(json.load(sys.stdin)),'ta')"

# 2.4 — limit yolg'iz ishlashi kerak
curl -s -o /dev/null -w '%{size_download} bayt\n' "$ASOS/api/products/all?limit=20"

# 2.5 — filtr ishlashi kerak
curl -s -o /dev/null -w '%{size_download} bayt\n' \
  "$ASOS/api/product-models/all?updatedAfter=2026-08-01T00:00:00Z"

# 4.1 — natija bo'lishi kerak
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"text":"kanal ventilyatori"}' "$ASOS/api/products/search" | head -c 200
```

---

## 6. USTUVORLIK

| # | Ish | Kim | Nega shu tartibda |
|---|---|---|---|
| 1 | **1.1** `product_model_id` migratsiyasi | dasturchi | Uchinchi topshiriq, KP da rasmiy kod shundan |
| 2 | **1.3** narx tipi va buzuq qiymatlar | dasturchi | Narx kiritishdan OLDIN bo'lishi kerak |
| 3 | **2.2** ommaviy narx yuklash | dasturchi | Busiz 1458 ta narx qo'lda kiritiladi |
| 4 | **3** login/SMS tasdig'i | dasturchi | SMS pullik — pul ketyapti |
| 5 | **2.1** model darajasida qoldiq | dasturchi | Savdoning eng ko'p savoli |
| 5b | **2.5** standart/buyurtma belgisi | dasturchi | Nostandart tovar "xato" bo'lib ko'rinmasin |
| 6 | **1.2** `sap_name` ni modelga ko'chirish | dasturchi | 1.1 dan keyin, ildizni yopadi |
| 7 | **2.4** `/products/all` standart limit | dasturchi | Bir soatlik ish, sayt tezlashadi |
| 8 | **2.3** `product-model-inside` sahifalash | dasturchi | Bir xillik |
| 9 | **1.4** takroriy nomlar | katalog admini | Kontent |
| 10 | **2.5** `updatedAfter` filtri | dasturchi | Bizga qulaylik, shoshilinch emas |
| 11 | **4.1** qo'shimchali qidiruv | dasturchi | Kichik kamchilik |
| 12 | **4.2** modeli yo'q 41 mahsulot | katalog admini | Kontent |

---

## 7. ENG MUHIM GAP

Texnik tomondan tizim tayyor: ventilyatsiya hisobi ishlaydi, katalog
o'qiladi, KP tuziladi, hujjat yaratiladi.

**Yagona haqiqiy to'siq — narx.** 1482 modelning 24 tasida narx bor.
Bu dasturchining ishi emas: narxlar kompaniyada Excel yoki 1C da
bo'lishi kerak. Ular topilib, 2.2 dagi endpoint orqali yuklansa —
tijorat taklifi to'liq avtomatlashadi.
