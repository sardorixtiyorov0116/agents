# Backend topshirig'i №12 — himoyasiz yozish endpointlari

**Kimga:** Climavent backend dasturchisiga
**Sana:** 07.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

**Tekshirish usuli:** barcha yozish endpointlariga **bo'sh tana** (`{}`)
guvohnomasiz yuborildi. Bo'sh tana ataylab: yaroqli yozuv yaratilmaydi,
lekin javob kodi guard bor-yo'qligini aniq ko'rsatadi —

- `401` → guard bor, so'rov to'xtatilgan
- `400` → **guard yo'q**, so'rov validatsiyaga yetib borgan

Sinovdan keyin qatorlar sanaldi: sharh 12, layk 27, buyurtma 23 —
o'zgarmagan. **Bazaga hech narsa yozilmadi.**

**Sabab:** №11 javobingizda `POST /reviews/create` da guard yo'qligini
o'zingiz aytdingiz. Tasdiqladim — va **yana bittasini** topdim.

---

## Avval — №11 tasdiqlandi

To'rtala band ham jonli tekshirildi, hammasi ishlaydi:

| Band | Tekshiruv |
|---|---|
| 1. Servis kaliti bilan `GET` | ✅ beshtasi ham 200; `POST /cart-items/create` hamon 401 |
| 2. Mahsulot hisoblagichlari | ✅ `alladmin` da beshtasi ham bor |
| 3. `order_items.product_model_id` | ✅ FK bor, matnli `product_model` ham qolgan |
| 4. `r2` / `images` do'kon tokeni | ✅ |

Hisoblagichlarni xom qatorlar bilan solishtirdim:

```
likes    xom qator = 27    likes_count yig'indisi = 27    MOS
reviews  xom qator = 12    reviews_count yig'indisi = 12  MOS
```

`cart_count` hamma joyda 0 — kutilgan holat, hisoblagich yangi ishga
tushgan.

**Kumulyativ qaroringiz tasdiqlanadi.** Sabablaringiz to'g'ri, ustiga
bittasini qo'shaman: kumulyativ raqamni keyin tiklab bo'lmaydi, joriysini
esa istalgan payt `GROUP BY` bilan sanash mumkin. Alohida endpoint hozir
kerak emas — `cart-items/all` ochilgani uchun kerak bo'lganda o'sha
yerdan sanaymiz.

Adminka o'z tomonida tayyor turgan edi, shuning uchun hisoblagichlar
kelishi bilan dashboarddagi karta va jadvaldagi ustun o'zi paydo bo'ldi.
Faqat yorliqni tuzatdim: «Savatda» → «Savatga solingan», chunki
birinchisi joriy holatni anglatardi.

---

## 1. 🔴 `POST /reviews/create` — guard yo'q

Tasdiqlandi:

```
POST /api/reviews/create        (guvohnomasiz, bo'sh tana)
→ 400 {"message":["review should not be empty","review must be a string",
        "stars should not be empty","stars must be a number...",
        "user_id should not be empty","user_id must be a number..."]}
```

`401` emas, `400`. Ya'ni so'rov guard'dan o'tib, validatsiyaga yetib
borgan.

Xato matni yana bir narsani ko'rsatadi: **`user_id` tanadan olinadi.**
Ya'ni yozuvchi o'zi kim ekanini o'zi aytadi va hech kim tekshirmaydi.

### Amalda nima qilish mumkin

- Tokensiz, istalgan `user_id` nomidan sharh yozish
- Istalgan mahsulotga istalgancha 5 yulduz qo'yish
- Raqobatchi mahsulotiga 1 yulduz qo'yish
- Skript bilan minglab sharh yozish

### Nega bu endi qimmatroqqa tushadi

№11 dan keyin sharhlar **ikki joyda** ko'rinadi:

- Saytdagi mahsulot sahifasida
- `products.reviews_count` orqali adminka analitikasida

Ya'ni soxta sharh endi faqat saytni emas, biz qurayotgan analitikani ham
buzadi.

### Kerak

`POST /likes/create` da ishlatilgan `UserSelfBodyGuard` shu yerga ham
qo'yilsin: `user_id` tanadagi qiymatdan emas, **tokendan** olinsin.

Solishtirish uchun — o'sha moduldagi qolgan endpointlar to'g'ri
himoyalangan:

| Endpoint | Guvohnomasiz |
|---|---|
| `POST /reviews/create` | **400 — guard yo'q** |
| `PATCH /reviews/update/{id}` | 401 ✅ |
| `DELETE /reviews/delete/{id}` | 401 ✅ |
| `GET /reviews/all` | 401 ✅ |

Ya'ni butun modulda bitta endpoint tushib qolgan.

---

## 2. 🟠 `POST /selected-to-checkout/create` — bunda ham guard yo'q

Buni siz aytmagan edingiz, sinov paytida chiqdi:

```
POST /api/selected-to-checkout/create   (guvohnomasiz)
→ 400   ← guard yo'q
```

Bu modulning qolgan qismi himoyalangan:

| Endpoint | Guvohnomasiz |
|---|---|
| `POST /selected-to-checkout/create` | **400 — guard yo'q** |
| `DELETE /selected-to-checkout/deletebyuser/{id}` | 401 ✅ |
| `DELETE /selected-to-checkout/deletecartitembyuser/{id}` | 401 ✅ |
| `GET /selected-to-checkout/all` | servis kaliti bilan 200 (№11 da ochilgan) |

Ta'siri sharhchalik og'ir emas — bu xaridorning «to'lovga tanlangan»
ro'yxati. Lekin naqsh bir xil: begona odam boshqa foydalanuvchi nomidan
yozuv qo'sha oladi. Xuddi shu `UserSelfBodyGuard` yetarli.

---

## 3. Qolgan yozish endpointlari — hammasi joyida

To'liq sinov natijasi (guvohnomasiz, bo'sh tana):

```
POST /api/reviews/create                400  ← guard yo'q
POST /api/selected-to-checkout/create   400  ← guard yo'q

POST /api/likes/create                  401  ✅
POST /api/cart/create                   401  ✅
POST /api/cart-items/create             401  ✅
POST /api/orders/create                 401  ✅
POST /api/order-items/create            401  ✅
POST /api/products/create               401  ✅
POST /api/characteristics/create        401  ✅
POST /api/product-model-inside          401  ✅
POST /api/product-images/create         401  ✅
POST /api/category/create               401  ✅
POST /api/stores/create                 401  ✅
POST /api/store-users/create            401  ✅
POST /api/r2/r2-upload                  401  ✅

DELETE /api/reviews/delete/{id}         401  ✅
DELETE /api/likes/delete                401  ✅
DELETE /api/products/delete/{id}        401  ✅
DELETE /api/cart-items/delete/{id}      401  ✅
```

Ya'ni 117 endpointdan ikkitasi tushib qolgan, qolgani mustahkam.

---

## 4. ⚠️ OpenAPI `security` maydoniga ishonib bo'lmaydi

Buni auditda ishlatmoqchi bo'lsangiz — ehtiyot bo'ling:

| Endpoint | OpenAPI `security` | Amalda |
|---|---|---|
| `POST /likes/create` | `null` | **401** (guard BOR) |
| `POST /reviews/create` | `null` | 400 (guard yo'q) |
| `POST /selected-to-checkout/create` | `null` | 400 (guard yo'q) |

Uchalasi ham hujjatda bir xil ko'rinadi, lekin biri himoyalangan,
ikkitasi yo'q. Ya'ni **hujjatga qarab guard bor-yo'qligini aniqlab
bo'lmaydi** — faqat jonli so'rov ko'rsatadi.

Tuzatgandan keyin `@ApiBearerAuth()` ham qo'yib chiqilsa, keyingi audit
osonlashadi.

---

## 5. 🟢 Eslatma: `producer` hamon majburiy

№10 ning 5-bandi ikkinchi qadamda to'xtab qolgan:

```
CreateProductDto majburiy:
  name_uz, name_ru, name_en, description_short_uz, description_short_ru,
  description_short_en, quantity, producer, store_id, category_id
```

`store_id` majburiy bo'ldi — bu bajarilgan. Lekin `producer` ham majburiy
bo'lib qolgan, ya'ni do'kon hamon ikki joyda yozilyapti va ular bir-biriga
mos kelmay qolishi mumkin.

Keyingi qadam: `producer` yozishdan chiqarilsin (`store.name` dan
to'ldirilsin), o'qishda qolsin. Shoshilinch emas.

---

## Xulosa

| № | Nima | Muhimligi |
|---|---|---|
| 1 | `POST /reviews/create` ga `UserSelfBodyGuard` | 🔴 soxta sharh, reyting buzilishi |
| 2 | `POST /selected-to-checkout/create` ga o'sha guard | 🟠 |
| 4 | Tuzatgandan keyin `@ApiBearerAuth()` qo'yilsin | 🟢 |
| 5 | `producer` yozishdan chiqarilsin | 🟢 |

1 va 2 bitta guard bilan yopiladi va bir necha qatorlik ish.

Siz to'g'ri qildingiz — №11 doirasida tegmadingiz, chunki xulqni
o'zgartirsangiz sayt tomonida sharh qoldirish buzilishi mumkin edi.
Endi alohida topshiriq sifatida qilinsa, front tomon bilan birga
tekshirish ham osonroq bo'ladi: sharh yozishda token yuborilishi kerak
bo'lib qoladi.
