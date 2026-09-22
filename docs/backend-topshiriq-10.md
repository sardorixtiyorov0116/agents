# Backend topshirig'i №10 — do'konlar jadvali va do'kon hisoblari

**Kimga:** Climavent backend dasturchisiga
**Sana:** 03.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

**Tekshirish usuli:** kaskad tekshiruvi uchun **o'z sinov zanjirimiz**
qurildi (`ZZ-KASKAD-…` mahsuloti → modeli → ichki varianti), o'chirildi
va har bir bo'g'in alohida so'rov bilan tekshirildi. Sinov mahsulotlari
`producer: "ZZ-SINOV-DOKON"` bilan yaratilgan, ya'ni hech qaysi haqiqiy
do'konga tegmagan. Hammasi tozalandi. **Katalog o'zgarmadi.**

**Sabab:** yangi adminka do'konlarni hozircha **o'z faylida** saqlaydi
(`data/tizim.json` + `ADMIN_HISOBLAR` muhit o'zgaruvchisi). Bu vaqtinchalik
yechim edi, chunki backendda do'kon tushunchasi yo'q edi. Endi `stores`
jadvali paydo bo'ldi — do'konlarni butunlay backendga ko'chirish vaqti keldi.

---

## 0. Tasdiq — kaskad o'chirish TO'G'RI ishlaydi

Savol tug'ilgan edi: mahsulot o'chirilsa, uning modellari va ichki
modellari ham o'chadimi? **Ha.** O'lchandi:

```
Zanjir qurildi:  mahsulot #231 → model #358 → ichki variant #1003

O'chirishdan oldin:
  model            200, mavjud
  ichki variant    200, mavjud

DELETE /api/products/delete/231  → 200

O'chirishdan keyin:
  mahsulot         404
  model            bo'sh (yozuv yo'q)
  ichki variant    404
```

Faqat modelni o'chirish ham to'g'ri kaskadlanadi:

```
DELETE /api/characteristics/delete/359  → 200
  ichki variant #1004 → 404
```

Ya'ni FK lar to'g'ri sozlangan, yetim yozuv qolmaydi. **Bu bandda
qiladigan ish yo'q** — ma'lumot uchun yozildi.

Bitta kichik nomuvofiqlik: o'chirilgan modelni so'raganda
`GET /characteristics/one/{id}` **404 emas, bo'sh tanali 200** qaytaradi.
Mahsulot va ichki variant 404 beradi. Bir xil bo'lsa yaxshi.

---

## Hozirgi holat — nima bor, nima yo'q

№8 dan keyin `stores` jadvali paydo bo'ldi va u ishlayapti:

```json
GET /api/stores/all
[{"id":1,"name":"Climavent","slug":"climavent","is_active":true,
  "createdAt":"…","updatedAt":"…"}, {"id":2,"name":"Jihozvent",…}]
```

`products.store_id` to'ldirilgan va `products/one` javobida to'liq
`store` obyekti qaytadi. **Poydevor tayyor.** Yetishmayotgani:

| Nima | Holat |
|---|---|
| `stores` jadvali | ✅ bor |
| `products.store_id` | ✅ bor va to'ldirilgan |
| Do'kon tavsifi, logotipi, aloqa ma'lumoti | ❌ yo'q |
| Do'kon yaratish / tahrirlash API si | ❌ faqat `GET /stores/all` bor |
| Do'kon admini hisobi va kirishi | ❌ yo'q |
| Server tomonda do'konlar orasidagi izolyatsiya | ❌ yo'q |
| `producer` maydoni | ⚠️ hamon bor, `store_id` bilan takrorlanadi |

---

## 1. `stores` jadvalini to'ldirish

Hozir jadvalda faqat `name`, `slug`, `is_active` bor. Adminka va sayt
uchun quyidagilar kerak.

### Qo'shilsin

| Ustun | Tur | Izoh |
|---|---|---|
| `description_uz` | text, null | Do'kon haqida qisqa matn |
| `description_ru` | text, null | Sayt uch tilli — uchtasi ham kerak |
| `description_en` | text, null | |
| `logo_url` | varchar, null | Cloudinary havolasi |
| `phone` | varchar, null | Aloqa |
| `email` | varchar, null | |
| `address` | varchar, null | |
| `telegram` | varchar, null | Ixtiyoriy |
| `website` | varchar, null | Ixtiyoriy |
| `color` | varchar(7), null | Adminka do'konni rang bilan ajratadi (`#2563eb`) |
| `sort_order` | int, default 0 | Saytda ko'rsatish tartibi |

### Cheklovlar

- `slug` — **unique**, kichik harf, faqat `a-z0-9-`. Sayt URL manzilida
  ishlatiladi, keyin o'zgartirish og'riqli bo'ladi.
- `name` — bo'sh bo'lmasin.
- `is_active = false` bo'lsa: saytda ko'rinmasin, lekin adminkada
  ko'rinsin va mahsulotlari o'chib ketmasin.

### Logotip

Alohida yuklash endpointi kerak emas — `POST /api/images/upload-image`
allaqachon ishlaydi va tekshirilgan. Adminka logotipni o'sha orqali
yuklab, qaytgan havolani `logo_url` ga yozadi.

---

## 2. Do'kon hisoblari — ALOHIDA jadval bo'lsin

Do'kon nomi bilan bir qatorda login/parol saqlash oson ko'rinadi, lekin
tavsiya qilmayman. Sabablari:

1. Bitta do'konda bir nechta xodim ishlaydi. Bitta umumiy parol bo'lsa,
   kim nima o'zgartirganini bilib bo'lmaydi.
2. Xodim ishdan ketsa, butun do'kon parolini almashtirish kerak.
3. Parolni almashtirganda do'kon yozuvi ham `UPDATE` bo'ladi — audit
   chalkashadi.

### Taklif: `store_users`

| Ustun | Tur | Izoh |
|---|---|---|
| `id` | pk | |
| `store_id` | fk → `stores.id` | `NULL` = superadmin, barcha do'konni ko'radi |
| `login` | varchar, **unique** | |
| `password_hash` | varchar | Ochiq parol **hech qachon** saqlanmasin |
| `full_name` | varchar, null | Kim ekanini bilish uchun |
| `role` | enum(`superadmin`,`store_admin`) | |
| `is_active` | bool, default true | O'chirish o'rniga bloklash |
| `last_login_at` | timestamp, null | |
| `createdAt` / `updatedAt` | | |

### Nega mavjud `users` jadvaliga qo'shilmaydi

`users` — **xaridorlar** jadvali: `cart`, `likes`, `orders`,
`selected-to-checkout` hammasi unga bog'langan. Do'kon adminini o'sha
yerga qo'shsak, xaridor va admin bir xil makonda bo'ladi: xaridor
ro'yxatdan o'tganda tasodifan `store_id` tushib qolishi, yoki adminning
savati paydo bo'lishi mumkin. Ikki xil narsa — ikki xil jadval.

№8 da `users.store_id` va `users.role` qo'shilgan edi. Agar ular hali
hech qayerda ishlatilmayotgan bo'lsa, olib tashlash mumkin.

### Parol

- `bcrypt` yoki `argon2` (NestJS da `bcrypt` odatiy).
- Ochiq parol javobda **hech qachon** qaytmasin — `GET /store-users/all`
  da ham, `create` javobida ham.
- Parolni faqat superadmin o'zgartira olsin, yoki egasi o'zi.

---

## 3. Kerakli endpointlar

### Do'konlar

```
GET    /api/stores/all              ✅ bor
GET    /api/stores/one/{id}         bitta do'kon, to'liq
POST   /api/stores/create           superadmin
PATCH  /api/stores/update/{id}      superadmin (yoki o'z do'koni)
DELETE /api/stores/delete/{id}      superadmin
```

**`DELETE` uchun muhim savol:** do'kon o'chirilganda mahsulotlari nima
bo'ladi?

Tavsiya: **o'chirilmasin.** Mahsuloti bor do'konni o'chirishga urinilsa
`409` qaytarilsin va nechta mahsulot borligi aytilsin. O'chirish o'rniga
`is_active = false` ishlatilsin. Kaskad o'chirish bu yerda juda xavfli —
bitta noto'g'ri so'rov 137 ta mahsulotni yo'q qiladi.

### Do'kon hisoblari

```
POST   /api/store-auth/login        {login, password} -> {token, store, role}
POST   /api/store-auth/logout
GET    /api/store-auth/me           joriy hisob + do'koni

GET    /api/store-users/all         superadmin (yoki o'z do'koni)
POST   /api/store-users/create      superadmin
PATCH  /api/store-users/update/{id} parol almashtirish shu yerda
DELETE /api/store-users/delete/{id}
```

Token JWT bo'lsin va ichida kamida `{ user_id, store_id, role }` bo'lsin.

---

## 4. 🔴 Eng muhimi — server tomonda izolyatsiya yo'q

Hozir adminka hamma narsani bitta `SERVICE_API_KEY` bilan qiladi. Ya'ni:

> **Do'kon admini texnik jihatdan boshqa do'konning mahsulotini
> o'zgartira oladi va o'chira oladi.** Buni faqat adminkaning o'z kodi
> to'sib turibdi.

Adminka har bir yozish amalidan oldin mahsulot kimga tegishliligini
tekshiradi — lekin bu **mijoz tomonidagi** himoya. Kalitni qo'lga
kiritgan odam `curl` bilan istalgan mahsulotni o'chira oladi.

Bu №8 ning 3-bandidagi 4-qadam edi va siz tasdiq so'ragan edingiz.
**Tasdiq: kerak.** Yondashuv:

1. `store-auth/login` JWT beradi, ichida `store_id` va `role`.
2. Yozish endpointlari (`products`, `characteristics`,
   `product-model-inside`, `product-images`, `r2`) guard orqali
   o'tsin: token `store_admin` bo'lsa, tegilayotgan yozuv
   `store_id` bilan mos kelishi tekshirilsin, mos kelmasa `403`.
3. `SERVICE_API_KEY` **superadmin** sifatida qoladi — hozirgi bot va
   integratsiyalar buzilmaydi.

Shu qilingandan keyin adminka o'z faylidagi hisoblardan butunlay voz
kechadi va backendga o'tadi.

---

## 5. `producer` dan bosqichma-bosqich voz kechish

Hozir do'kon **ikki joyda** yozilgan: `products.producer` (matn) va
`products.store_id` (FK). Ikkitasi bir-biriga mos kelmay qolishi vaqt
masalasi.

Taklif qilingan tartib:

1. `POST /products/create` da `store_id` **majburiy** qilinsin.
   Hozir faqat `producer` majburiy — ya'ni yangi mahsulot `store_id`
   siz yaratilishi mumkin.
2. `producer` yozishdan chiqarilsin, lekin o'qishda qolsin —
   `store.name` dan to'ldirilsin. Eski mijozlar buzilmaydi.
3. Hech kim `producer` ni o'qimay qo'ygach, ustun olib tashlansin.

Adminka 2-qadamdan keyin `store_id` ga to'liq o'tadi.

---

## 6. Kichik: `alladmin` `store_id` qaytarmaydi

```
GET /api/products/alladmin  ->  kalitlar:
  category, description_short_uz, id, name_en, name_ru, name_uz,
  producer, quantity, views
```

`store_id` ham, `store` ham yo'q — faqat `producer` bor. `?store_id=`
filtri esa ishlaydi. Ro'yxatda do'konni ko'rsatish uchun `store_id`
(yoki qisqa `store: {id, name}`) qo'shilsa yaxshi bo'lardi — hozir
adminka buni `producer` matnidan taxmin qilishga majbur.

---

## 6b. 🟠 Savat, layk va sharhlar `X-API-Key` bilan yopiq

Adminkaga «mahsulot necha marta savatga solingan» ko'rsatkichi kerak —
bu xarid niyatining eng aniq signali. Ko'rish soni «qaradi» degani,
savat esa «olmoqchi bo'ldi» degani.

Hozir bu ma'lumot olinmaydi:

| Endpoint | `X-API-Key` bilan |
|---|---|
| `GET /api/cart/all` | **401** |
| `GET /api/cart-items/all` | **401** |
| `GET /api/likes/alllikes` | **401** |
| `GET /api/reviews/all` | **401** |
| `GET /api/orders/all` | ✅ 200 (№8 da ochilgan) |
| `GET /api/order-items/all` | ✅ 200 |

№8 da `orders` va `order-items` aynan shu tarzda ochilgan edi va
buzilish bo'lmadi. Xuddi shu narsa savat, layk va sharhlarga ham kerak —
**faqat o'qish**, yozish endpointlari tegilmasin.

Yana yaxshiroq variant: mahsulot obyektiga tayyor hisoblagichlar
qo'shilsa, adminka minglab qatorni o'qib sanamaydi:

```
products.cart_count      — nechta savatda turibdi
products.likes_count     — nechta layk
products.reviews_count   — nechta sharh
```

`views` va `sold_count` allaqachon shunday ishlaydi — bu ularning yoniga
tabiiy qo'shiladi.

### Model darajasida ham kerak

`order-items` da `product_model` bor, lekin u **matn** (`"ВК-125С"`) —
model nomining nusxasi, FK emas. Ya'ni model qayta nomlansa, eski
buyurtmalar bog'lanishini yo'qotadi va model bo'yicha sotuvni aniq
hisoblab bo'lmaydi.

`order_items.product_model_id` (FK → `characteristics.id`) qo'shilsa,
«qaysi model ko'proq sotilgan» degan savolga aniq javob bo'ladi. Matnli
`product_model` tarix uchun qolaversin.

---

## 7. Kichik: R2 da yetim fayllar to'planyapti

Mahsulot o'chirilganda uning R2 fayllari (`opisaniya`, `sizes`,
`markirovka`, model jadvallari) R2 da qolib ketadi. Xuddi shunday,
mazmun tahrirlanganda eski fayl o'chirilmaydi — har saqlashda yangi
obyekt yaratiladi.

Bu shoshilinch emas (fayllar kichik), lekin vaqt o'tib to'planadi.
Yechim variantlari: o'chirishda kaskad qilish, yoki vaqti-vaqti bilan
ishga tushadigan tozalovchi (bazada havolasi yo'q obyektlarni o'chiradi).

Xuddi shu narsa Cloudinary rasmlariga ham tegishli.

---

## Xulosa — ish tartibi

| № | Nima | Muhimligi |
|---|---|---|
| 4 | Server tomonda do'kon izolyatsiyasi (JWT + guard) | 🔴 xavfsizlik |
| 1 | `stores` jadvaliga tavsif, logotip, aloqa maydonlari | 🟠 |
| 2 | `store_users` jadvali va parol hash'i | 🟠 |
| 3 | Do'kon CRUD + `store-auth` endpointlari | 🟠 |
| 5 | `store_id` majburiy, `producer` dan voz kechish | 🟡 |
| 6 | `alladmin` da `store_id` | 🟡 |
| 6b | Savat/layk/sharh o'qishga ochilsin + hisoblagichlar | 🟠 analitika |
| 7 | R2 / Cloudinary yetim fayllari | 🟢 |
| 0 | `characteristics/one` o'chirilganda 404 bersin | 🟢 |

**Boshlash uchun tavsiya:** 1 → 2 → 3 birga qilinsin (bitta
migratsiya + bitta modul), keyin 4. Shundan keyin adminka do'konlarni
fayldan backendga ko'chiradi va `ADMIN_HISOBLAR` muhit o'zgaruvchisi
kerak bo'lmay qoladi.

---

## Adminka hozir nima qilyapti

Kutish davomida adminka do'konlarni shunday saqlaydi:

- `data/tizim.json` — do'kon nomi, slug, rang, tavsif
- `ADMIN_HISOBLAR` muhit o'zgaruvchisi — login va scrypt hash'i
- Do'kon mahsulotlari `producer` matni bo'yicha ajratiladi

Bu ishlayapti, lekin: Vercel'da fayl tizimi faqat o'qish uchun, ya'ni
yangi do'kon qo'shilganda uni qo'lda muhit o'zgaruvchisiga ko'chirish
kerak. Backendga o'tgach bu muammo yo'qoladi.

**Iltimos, tayyor bo'lganda ayting** — adminka bir kunda o'tadi, lekin
o'tish paytida ikkala manba parallel ishlashi kerak.
