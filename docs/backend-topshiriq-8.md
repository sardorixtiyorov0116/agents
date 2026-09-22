# Backend topshirig'i №8 — R2 yozish, ko'rish hisoblagichi, ko'p do'kon

**Kimga:** Climavent backend dasturchisiga
**Sana:** 02.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

**Tekshirish usuli:** asosan o'qish. Yozish bo'yicha: R2 ga bir nechta
**bo'sh sinov obyekti** yozildi (hech qayerga ulanmagan) va bitta mahsulot
(#154) da `quantity` 50→51→50 qilib qaytarildi. Katalog holati o'zgarmadi —
137 ta mahsulot, hamma maydon joyida.

**Sabab:** boshqa do'konlar uchun yangi adminka qurilmoqda
(`D:/AGENTS/climavent-marketplace-admin`). U mavjud API ustida ishlaydi.

---

## Avval — tasdiq

№7 dagi qarorlar jonli tekshirildi va **to'g'ri** ekan:

| Nima | Holat |
|---|---|
| Narx DOLLARDA | ✅ `12391 × 12000 = 148 692 000 so'm` — saytdagi raqamning o'zi |
| `usd-rate` endpointi | ✅ `{"rate":12000}` |
| Narx `product_model_inside.price` da | ✅ 137 mahsulotdan **24 tasi** narxni faqat shu yerdan oladi |
| `characteristics.price` | ✅ faqat **1 ta** mahsulotda ishlatilgan |
| `product_model_id` → `characteristics.id` | ✅ shunday |

Ya'ni «ichki modellar bo'lsa narx o'shalardan» qoidasi ishlaydi. Yangi
adminka aynan shu qoidaga moslashtirildi.

---

## 1. 🔴 R2 yozish butunlay ishlamaydi

### Bu — №7 dagi «40 ta bo'sh R2 fayli» ning SABABI

№7, 3.1-bandda 40 ta 0 baytli fayl haqida yozilgan edi va «yuklashda
0 baytli faylni qabul qilmaydigan tekshiruv qo'shilsin» deyilgan. Sabab
topildi: **tekshiruv emas, yuklashning o'zi buzuq.**

### 1.1. `POST /api/r2/r2-upload` faylga har doim bo'sh `{}` yozadi

`201` qaytaradi, `key` va `url` beradi — lekin fayl ichi bo'sh.
To'rt xil tana bilan sinaldi, natija bir xil:

| `data` nima yuborildi | Faylda nima paydo bo'ldi |
|---|---|
| JSON matn (`"{\"type\":\"doc\",…}"`) | `{}` |
| Obyekt (`{type:"doc",…}`) | `{}` |
| Oddiy matn (`"shunchaki matn"`) | `{}` |
| HTML (`"<p>salom</p>"`) | `{}` |

Tekshirish (o'zingizda takrorlash uchun):

```bash
curl -s -X POST "$ASOS/api/r2/r2-upload" \
  -H 'Content-Type: application/json' -H "X-API-Key: $KEY" \
  -d '{"data":"{\"type\":\"doc\",\"content\":[]}"}'
# -> {"success":true,"key":"climavent/<uuid>.json","url":"…"}

curl -s "$ASOS/api/r2/r2-content?key=climavent/<uuid>.json"
# -> {"success":true,"data":{},…}     <-- bo'sh
```

To'g'ridan-to'g'ri R2 havolasi ham `{}` beradi — ya'ni muammo o'qishda emas,
**yozishda**.

Misol (yozilgan, tekshirilgan): `climavent/8bd33115-e1ef-470a-a9ca-6c31f30d72d0.json`

### 1.2. `PUT /api/r2/r2-update` mazmunni `{"message": …}` ichiga o'raydi

`200` qaytaradi va saqlaydi, lekin:

```
Yuborildi : {"type":"doc","content":[…]}
Saqlandi  : {"message":{"type":"doc","content":[…]}}
```

`data` ni matn sifatida yuborsak ham xuddi shunday o'raladi.
Sayt esa **toza** ProseMirror hujjatini kutadi — mavjud yozuvlar shunday
(o'qib solishtirildi, mahsulot #154).

### 1.3. Kalit formati mos emas

| Qayerdan | Kalit ko'rinishi |
|---|---|
| Mavjud yozuvlar (masalan #154 `opisaniyaJson`) | `221fbeaa-da71-47a6-b140-23d067761a4c` — **prefikssiz, kengaytmasiz** |
| Yangi `r2-upload` | `climavent/<uuid>.json` — **prefiksli, `.json` bilan** |

Ikkalasi ham `r2-content` orqali o'qiladi, lekin sayt qaysi formatni
kutayotgani noma'lum. Yangi format eski kod bilan mos keladimi?

### Topshiriq

1. `r2-upload` **haqiqatan** `data` ni faylga yozsin. Hozir nimadir yo'lda
   yo'qolyapti (ehtimol `data` bo'sh obyektga aylantirilib yuborilyapti).
2. `r2-update` mazmunni `{"message": …}` ichiga **o'ramasin** — nima
   berilgan bo'lsa, o'shani yozsin.
3. Kalit formati bitta bo'lsin. Yangi format tanlansa, eski yozuvlar
   o'qilishda davom etsin (ikkalasini ham qo'llab-quvvatlash).
4. Yozgandan keyin **qayta o'qib tekshiruv** qo'shilsa yaxshi bo'lardi —
   bo'sh fayl saqlanib qolmasin.

### Nega shoshilinch

Yangi adminkada 4 ta matnli bo'lim muharriri (Tavsif, O'lchamlar,
Vazifasi, Markirovka) tayyor — jadval, rasm, sarlavha bilan. **O'qish
ishlaydi**, mavjud kontent chiroyli yuklanadi. Saqlash esa hozir ataylab
bloklangan: adminka R2 ga yozadi → qayta o'qiydi → mos kelmasa mahsulotga
havolani ULAMAYDI. Ya'ni saytdagi mazmun buzilmaydi, lekin **hech kim matn
tahrirlay olmaydi**. Siz tuzatgan zahoti ishlab ketadi, adminka tomonda
o'zgarish shart emas.

Shu sababdan `POST /api/characteristics/create` ham ishlamayapti — u
`content` va `contentJson` ni majburiy qiladi, ular esa R2 havolalari.

---

## 2. 🔴 `GET /api/products/one/{id}` `views` va `updatedAt` ni buzadi

### Muammo

Har bir o'qish ko'rish hisoblagichini oshiradi **va shu bilan birga**
`updatedAt` ni ham yangilaydi.

O'lchov (mahsulot #154, hech narsa yozilmagan, faqat 2 marta o'qildi):

```
views     : 616 -> 618
updatedAt : 06:30:50 -> 06:31:52
```

### Ikkita oqibat

**a) Admin katalogni ko'rsa, statistika shishadi.** Adminka mahsulot
sahifasini ochganda `products/one` chaqiriladi — bu haqiqiy mijoz emas,
lekin `views` ga qo'shiladi. Sinov davomida mening o'qishlarim bitta
mahsulotga **+6 ko'rish** qo'shdi.

**b) `updatedAt` «oxirgi tahrir» sifatida yaroqsiz.** U tashrifdan ham
ko'tariladi. Yangi adminkada «tahrirlangan mahsulotlar» grafigi shu sababli
**olib tashlandi** — u tahrirni emas, tashrifni ko'rsatardi.

### Topshiriq

1. Ko'rish hisoblagichi `updatedAt` ga **tegmasin** (alohida `UPDATE` yoki
   `@UpdateDateColumn` dan chetlab o'tish).
2. Admin o'qishi uchun hisoblagichni o'tkazib yuboradigan yo'l bo'lsin —
   masalan `?count=false` parametri yoki `X-API-Key` bilan kelgan
   so'rovlarda hisoblamaslik. Ikkinchisi soddaroq: servis kaliti bilan
   kelgan so'rov mijoz tashrifi emas.

---

## 3. 🟡 Ko'p do'kon — `store_id`

### Nima uchun kerak

Yangi adminka **bir nechta do'kon** uchun mo'ljallangan: har bir do'kon
faqat o'z mahsulotlarini ko'radi va tahrirlaydi. Bazada bunday maydon yo'q,
shuning uchun hozir **`producer` maydoni** do'kon kaliti sifatida
ishlatilyapti (`Jihozvent` — 136 ta, `Climavent` — 1 ta).

Bu **vaqtinchalik konvensiya**, haqiqiy izolyatsiya emas:

| | Holat |
|---|---|
| Adminka ichida ajratish | ✅ ishlaydi (o'qish ham, yozish ham tekshiriladi) |
| API'ga to'g'ridan-to'g'ri murojaat | ❌ ajratilmaydi — kalit hamma do'kon uchun bitta |

Ya'ni do'kon admini kalitni qo'lga kiritsa, boshqa do'kon mahsulotini
o'zgartira oladi. Haqiqiy mijozlarga sotishdan oldin bu yopilishi kerak.

### Topshiriq (muhimlik tartibida)

1. `products` ga `store_id` (FK) qo'shilsin.
2. `GET /api/products/all` ga `store_id` bo'yicha filtr qo'shilsin —
   hozir 137 tasi ham yuklanib, mijoz tomonda filtrlanyapti.
3. `users` ga `store_id` va `role` qo'shilsin.
4. Yozish guvohnomasi do'konga bog'lansin: har do'kon uchun alohida kalit
   yoki `store_id` li JWT. Hozirgi `X-API-Key` hamma narsaga ochiq.

Adminka tomonda bu o'zgarish **bitta faylda** — `src/lib/dokon.ts`.
Qolgan kod tegilmaydi.

---

## 4. 🟡 Javob sxemalari hujjatlashtirilmagan

OpenAPI'da yozish endpointlarining javoblari bo'sh:

```json
"responses": { "201": { "description": "" } }
```

Natijada `POST /api/products/create` nima qaytarishini **tajriba yo'li
bilan** aniqlashga to'g'ri keldi:

```json
{ "message": "Product successfully created", "newProduct": { "id": 220, … } }
```

`id` — `newProduct` ichida. Buni bilmagan mijoz kodi «mahsulot
yaratilmadi» deb o'ylaydi (bizda aynan shunday bo'ldi).

**Topshiriq:** yozish endpointlariga `@ApiResponse` qo'shilsin — hech
bo'lmasa `products`, `category`, `characteristics`, `product-model-inside`,
`r2` uchun.

---

## 5. 🟡 Buyurtmalar servis kaliti bilan ochilmaydi

```
GET /api/orders/all        -> 401
GET /api/order-items/all   -> 401
GET /api/reviews/all       -> 401
```

`X-API-Key` bu yo'llarda qabul qilinmaydi.

**Oqibati:** adminkada **daromad va vaqt bo'yicha savdo analitikasi yo'q**.
Hozirgi ko'rsatkichlar faqat `views`, `sold_count`, `quantity` va narxdan
hisoblanadi. `sold_count` esa 137 mahsulotdan atigi 5 tasida to'ldirilgan —
ya'ni konversiya raqami deyarli bo'sh.

**Topshiriq:** servis kaliti uchun `orders` va `order-items` ga **o'qish**
ruxsati berilsin (yozish shart emas). `order_items → product → store_id`
zanjiri orqali har do'kon o'z daromadini ko'radi.

---

## 6. 🟢 Kichik narsalar

### 6.1. R2 da o'chirish endpointi yo'q

`r2-upload` bor, `r2-update` bor, `delete` yo'q. Har tahrirda yangi obyekt
yaratilsa, eskilari to'planib qolaveradi. Sinov davomida men ham ~8 ta
bo'sh obyekt qoldirdim (hech qayerga ulanmagan) — o'chirib bo'lmadi.

**Topshiriq:** `DELETE /api/r2/:key` qo'shilsin (guvohnoma bilan).

### 6.2. Bo'sh bo'lim `null` emas, `{}` bo'lib keladi

Bir xil ma'nodagi ikkita maydon turlicha qaytadi:

```
sizes      = null    (HTML maydoni)
sizesJson  = {}      (hujjat maydoni)
```

137 mahsulotdan: `sizesJson = {}` — 42 ta, `markirovkaJson = {}` — 81 ta,
`opisaniyaJson = {}` — 29 ta, `naznacheniyaJson = {}` — 28 ta.

Mijoz kodida bu oson xato: `Boolean({})` — `true`, ya'ni bo'sh bo'lim
"to'ldirilgan" deb hisoblanadi. Bizda ham shu xato bo'ldi.

**Taklif:** bo'sh bo'lganda ikkalasi ham `null` qaytarsin.

### 6.3. Rasm yuklash API

Kelishilgani bo'yicha kutyapman. Tayyor bo'lganda endpoint nomini va
tana ko'rinishini yuboring — adminkaga fayl tanlash qo'shiladi. Hozircha
faqat tayyor havola qo'yish mumkin.

### 6.4. `GET /api/products/alladmin` qisqartirilgan

Faqat `id, name_uz/ru/en, description_short_uz, quantity, category`
qaytaradi — `producer`, `price`, `views`, `characters` yo'q. Adminka
uchun aynan shular kerak, shuning uchun u `products/all?limit=300` dan
foydalanyapti (137 ta to'liq obyekt, ~2 s).

**Taklif:** `alladmin` ga `producer` va `views` qo'shilsa, adminka
ro'yxati ancha tez ochilardi.

---

## Nima qilinmasin

- Mavjud ustun turlari va nomlari o'zgartirilmasin.
- `product_models.price` / `currency` hozircha o'chirilmasin (№7, 1-band).
- Mavjud R2 kalit formati buzilmasin — yangi format qo'shilsa, eskisi ham
  o'qilishda davom etsin.
- `synchronize: true` yoqilmasin.

---

## Qisqacha ustuvorlik

| № | Ish | Nega |
|---|---|---|
| 1 | R2 yozishni tuzatish | Matn tahrirlash butunlay bloklangan |
| 2 | `views` / `updatedAt` ajratish | Statistika ishonchsiz |
| 3 | `store_id` | Ko'p do'kon xavfsizligi |
| 4 | Javob sxemalari | Mijoz kodi taxmin qilishga majbur |
| 5 | Buyurtmalarga o'qish | Daromad analitikasi yo'q |
| 6 | R2 delete, rasm API, `alladmin` | Qulaylik |
