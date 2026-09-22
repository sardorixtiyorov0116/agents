# Backend tekshiruvi №4 — 3-topshiriq qanday bajarilgan

**Tekshirilgan:** `https://climavent-back-production.up.railway.app`
**Sana:** 2026-08-06
**Usul:** faqat o'qish va zararsiz probalar (mavjud bo'lmagan `id = 99999999`,
bo'sh tana). Hech narsa yaratilmadi, o'zgartirilmadi, o'chirilmadi.

> **Login sinalmadi — ataylab.** `POST /api/users/login` haqiqiy SMS
> yuboradi va u pullik. Kompaniya pulini sarflamaslik uchun 1.5–1.7
> bo'limlarini men tekshira olmadim. Ularni dasturchining o'zi
> tasdiqlashi kerak — pastdagi ro'yxatga qara.

---

## 1. XAVFSIZLIK — hammasi bajarilgan ✅

| Topshiriq | Kutilgan | Natija |
|---|---|---|
| **1.1** `reviews/all` — telefon va email ochiq | 401 | **401** ✅ |
| **1.2** `order-items/all` | 401 | **401** ✅ |
| **1.2** `cart-items/all` | 401 | **401** ✅ |
| **1.2** `selected-to-checkout/all` | 401 | **401** ✅ |
| **1.3** `selected-to-checkout/deletebyuser/{id}` | 401 | **401** ✅ |
| **1.3** `.../deletecartitembyuser/{id}` | 401 | **401** ✅ |
| **1.4** `cart-items/create` | 401 | **401** ✅ |
| **1.4** `cart-items/update/{id}` | 401 | **401** ✅ |
| **1.4** `cart-items/delete/{id}` | 401 | **401** ✅ |

Qo'shimcha tekshirdim — bularda ham shaxsiy ma'lumot ochiq emas:
`/api/users/all` → 401, `/api/orders/all` → 401, `/api/users/one/1` → 401.

### 1.6 Tezlik cheklovi — qo'yilgan ✅

```
x-ratelimit-limit: 120
x-ratelimit-remaining: 119
x-ratelimit-reset: 60
```

Hisoblagich haqiqatan kamayib boryapti — cheklov ishlayapti.

### 2.2 Xavfsizlik sarlavhalari — qo'yilgan ✅

```
strict-transport-security: max-age=31536000; includeSubDomains
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
x-powered-by: YO'Q (olib tashlangan)
```

`content-security-policy` yo'q — lekin bu faqat API uchun muhim emas
(brauzerda sahifa render qilinmaydi). Talab qilmayman.

### 2.1 `500` o'rniga to'g'ri kod — bajarilgan ✅

```
GET   /api/products/one/abc          → 400  (avval 500)
GET   /api/product-models/one/abc    → 400  (avval 500)
PATCH /api/cart-items/update/9999999 → 401  (guard oldinroq ishlaydi)
```

### 3.1 Lotincha qidiruv — ishlaydi ✅

| So'rov | Natija |
|---|---|
| `вентилятор` | 40 |
| `ventilyator` | 40 |
| `isitgich` | 4 |
| `filtr` | 6 |
| `kanal ventilyator` | 6 |
| `ВК-250П` | 1 |

Faqat bitta chekka holat qoldi: `kanal ventilyatori` → **0**. Sababi —
qo'shimchali shakl (`ventilyatori`) alohida so'z deb hisoblanadi va
kesishma bo'sh chiqadi. Bu kichik kamchilik, shoshilinch emas.

---

## 2. TUZATILMAGAN ❌

### 2.3 `product_model_inside.product_model_id` — hamon buzuq

Bu uchinchi topshiriqda ham bor edi. Holat o'zgarmagan:

```
932 yozuvning 932 tasida nishon noto'g'ri
```

Namuna (bugun olingan):

```json
{
  "sap_name": "ВЦ 4-75-2,5-О-1-0,12/1500",   // markazdan qochma ventilyator
  "in_model_name": "ВЦ 4-75-2,5-1-0,12/1500",
  "product_model_id": 96                      // → "КВН 250-2-1" (suvli isitgich)
}
```

Qo'shimcha o'lchov: `in_model_name` ni `product_models.name` bilan aynan
solishtirsak, **932 tadan faqat 81 tasi** mos tushadi. Ya'ni nomlar ham
bir xil yozilmagan (ajratuvchi belgilar farq qiladi: `500-250-2` va
`500-250/2`).

**Kerakli ish ikki qadam:**

1. `in_model_name` ni normallashtirib (`-`, `/`, `_`, `.`, bo'sh joy —
   hammasini bir xil belgiga keltirib) `product_models.name` bilan
   solishtirib, `product_model_id` ni QAYTA yozing;
2. Mos kelmagan qatorlarni alohida ro'yxat qilib bering — ular qo'lda
   ko'riladi.

Biz hozircha `product_model_id` ni umuman ishlatmay, nomni
normallashtirib bog'lab turibmiz (`integrations/climavent_client.py`,
`sap_kaliti`). Bu vaqtinchalik yechim — baza to'g'rilangach olib
tashlanadi.

### 3.2 `/api/products/all` — sahifalash chala

```
(parametrsiz)        → 698 KB, 137 ta, 1.21 s
?limit=20            → 698 KB, 137 ta      ← limit YOLG'IZ ISHLAMAYDI
?limit=20&page=1     →  86 KB,  20 ta      ← ikkalasi birga ishlaydi
?take=20             → 698 KB
?offset=0&limit=20   → 698 KB
```

Ikki narsa kerak:

1. `limit` `page` siz ham ishlasin (`page` bo'lmasa 1 deb olinsin);
2. parametrsiz chaqiruvga standart chegara qo'yilsin (masalan 20) —
   hozir har mijoz 698 KB yuklab olyapti.

---

## 3. TEKSHIRA OLMADIM — dasturchi tasdiqlasin

Bular login orqali sinaladi, login esa pullik SMS yuboradi.
Iltimos, o'zingiz tekshirib javob bering:

- [ ] **1.5** `POST /users/login` endi `users` jadvaliga darhol yozmaydimi?
      (yozuv faqat `verify-otp` dan keyin paydo bo'lishi kerak)
- [ ] **1.5** bitta raqamga 5 daqiqada 1 SMS cheklovi qo'yildimi?
- [ ] **1.5** bitta raqamga sutkasiga 5 ta SMS cheklovi qo'yildimi?
- [ ] **1.7** `refresh token` 60–90 kunga uzaytirildimi?
      (mijoz har kirishda SMS olmasligi uchun — bu eng katta SMS tejash)
- [ ] **1.7** OTP muddati 5 daqiqa, 3 marta xato urinishdan keyin bekor?
- [ ] Sinov paytida paydo bo'lgan yozuv o'chirildimi?
      `users.id = 15, phone_number = +998900000000`

---

## 4. MA'LUMOT SIFATI — deyarli o'zgarmagan

| Ko'rsatkich | 3-topshiriqda | Bugun |
|---|---:|---:|
| Narxi bor modellar | 24 / 1482 | **26 / 1482** |
| SAP kodi bor yozuvlar | 143 / 1482 | 932 / 932 (`product_model_inside`) |
| Mahsulotlar | 137 | 137 |

**Narx — hamon eng katta to'siq.** 1482 modeldan 26 tasida narx bor
(1,8%). Tijorat taklifi (KP) narxsiz tuzilmaydi: texnik qism tayyor,
faqat ma'lumot yetishmaydi. Bu dasturchining ishi emas — narxlar
kimdadir Excel yoki 1C da turgan bo'lishi kerak.

---

## 5. XULOSA

Xavfsizlik bo'yicha topshiriq **to'liq bajarilgan** — 9 ta ochiq
endpoint yopilgan, tezlik cheklovi va helmet sarlavhalari qo'yilgan,
`500` xatolari to'g'ri kodga almashtirilgan, lotincha qidiruv
ishlayapti. Bu jiddiy ish, yaxshi bajarilgan.

Qolgan ikkitasi:

| # | Ish | Kim |
|---|---|---|
| 1 | `product_model_id` ni qayta bog'lash (932 yozuv) | dasturchi |
| 2 | `/products/all` ga standart `limit` | dasturchi |
| 3 | Login/SMS bo'limini tasdiqlash (3-bo'lim) | dasturchi |
| 4 | **Narxlarni bazaga kiritish** | kompaniya |
