# Backend topshirig'i №26 — domen o'zgarishi va kuryer ishini to'liq qilish

**Sana:** 17.09.2026

## 0. 🔴 SHOSHILINCH — adminka domeni o'zgardi

Adminka endi **`https://climavent-hamkor.vercel.app`**. Eski
`climavent-marketplace-admin.vercel.app` unga 307 bilan yo'naltiradi.

O'lchandi: yangi domendan preflight so'rovga **`Access-Control-Allow-Origin` qaytmaydi**:

```
OPTIONS /api/seller-applications/documents  Origin: https://climavent-hamkor.vercel.app
→ 200, access-control-allow-origin YO'Q
```

Ya'ni `/sotuvchi-bolish` sahifasidan hujjat yuklash brauzerda ishlamaydi.

**Kerak:**
- CORS ruxsat ro'yxatiga `https://climavent-hamkor.vercel.app` qo'shilsin.
  Eskisi bir oy qolsin, keyin olib tashlanadi.
- `SELLER_PORTAL_URL` → `https://climavent-hamkor.vercel.app`. Arizani tasdiqlash
  xatidagi parol havolasi shundan olinadi.
- Kodda eski domen qattiq yozilgan joylar bo'lsa — almashtiring.

---

Quyidagilar kuryer ishini "ishlaydi"dan "professional"ga olib chiqadi.
Adminka va kuryer sahifasi tomonini biz qilamiz.

## 1. 🔴 Kuryer shartnomasi (oferta) va hujjatlari

Sotuvchi ofertasi mexanizmi (№18, №20) kuryer uchun takrorlanadi.

**Kuryer ofertasi:**
- `offers` ga `kind: "courier"`. Matnini biz beramiz (huquqshunos bilan).
- `POST /store-auth/login` kuryer uchun ham `offer_pending` qaytarsin.
- Kuryer ofertani tasdiqlamaguncha `/api/courier/*` yozish amallari 409 bersin.
  `me` va o'qish ochiq qoladi.

**Kuryer hujjatlari:** №16 dagi yopiq saqlash va 5 daqiqalik havola kabi.

```
POST /api/couriers/:id/documents     multipart: type, file   — do'kon admini / superadmin
GET  /api/couriers/:id/documents
GET  /api/couriers/:id/documents/:docId/url
```

| `type` | Qachon talab qilinadi |
|---|---|
| `passport` | doim |
| `driver_license` | `vehicle_type` = `car` / `van` / `truck` bo'lsa |
| `vehicle_registration` | transport bo'lsa (texpasport) |
| `self_employed_certificate` | `employment_type = self_employed` bo'lsa |
| `contract` | imzolangan shartnoma (skaner) |

**`couriers` ga qo'shimcha maydonlar:**
- `employment_type`: `employee` · `self_employed` · `ip` (YaTT) · `contractor` (tashqi kompaniya);
- `tin` (JShShIR yoki STIR);
- `license_categories` — haydovchilik guvohnomasi toifalari, masalan `["B","C"]`;
- `documents_verified_at` va `verified_by`.

Mashina ma'lumotlari (`vehicle_plate`, sig'im) kuryerda emas, alohida jadvalda — 1a-band.

`documents_verified_at` bo'sh bo'lsa kuryerni biriktirish 409 bersin: «hujjatlari tasdiqlanmagan».

Pasport skanini ishdan ketgandan keyin 30 kun o'tib o'chirish №16 qoidasi bilan bir xil.

## 1a. 🔴 "Mening transportim" — kuryerning mashinalari

**Muammo.** Hozir `couriers.vehicle_type` bitta maydon va uni faqat admin o'zgartiradi. Aslida kuryerda bir nechta transport bo'lishi mumkin (bugun o'z mashinasi, ertaga ijaradagi furgon). Lekin mashinani kuryer erkin o'zgartira olsa:
- yuk mashinasi kerak bo'lgan tovar yengil mashinaga tushadi;
- guvohnoma toifasi mashinaga mos kelmaydi;
- mijoz xaritada boshqa mashinani ko'radi.

**Yechim:** kuryer bir nechta transport qo'shadi, do'kon tasdiqlaydi, kuryer smena boshida tasdiqlanganlaridan birini tanlaydi.

**Jadval `courier_vehicles`:**

| Maydon | |
|---|---|
| `id`, `courier_id` | |
| `vehicle_type` | `foot` · `bike` · `car` · `van` · `truck` |
| `plate` | davlat raqami, `foot` / `bike` da bo'sh bo'lishi mumkin; unique (faol yozuvlar orasida) |
| `model`, `color` | ixtiyoriy — mijoz mashinani tanishi uchun |
| `capacity_kg`, `capacity_m3` | |
| `owner` | `own` · `rented` · `company` |
| `status` | `pending` · `approved` · `rejected` · `archived` |
| `reject_reason`, `verified_by`, `verified_at` | |
| `created_at`, `updated_at` | |

Texpasport rasmi — 1-banddagi hujjatlarga `type: vehicle_registration` va `vehicle_id` bilan.

**`couriers.active_vehicle_id`** — hozir ishlatilayotgan transport. `couriers.vehicle_type` endi shundan olinadi (eski mijozlar buzilmasligi uchun javobda qoladi).

**Kuryer uchun:**

```
GET    /api/courier/vehicles
POST   /api/courier/vehicles                multipart: vehicle_type, plate, model?, color?, capacity_kg?, capacity_m3?, owner, registration_photo
PATCH  /api/courier/vehicles/:id            faqat `pending` yoki `rejected` da (tasdiqlangani o'zgarmaydi — yangisini qo'shadi)
DELETE /api/courier/vehicles/:id            → `archived`; faol transport bo'lsa 409
POST   /api/courier/vehicles/:id/activate   faol transportni tanlash
```

**Adminka uchun** (do'kon admini — o'z kuryerlari, superadmin — hammasi):

```
GET  /api/couriers/:id/vehicles
POST /api/couriers/:id/vehicles/:vid/approve
POST /api/couriers/:id/vehicles/:vid/reject     { reason }
POST /api/couriers/:id/vehicles                 admin o'zi qo'shsa — darhol `approved`
```

**Qoidalar:**
- `activate` faqat `approved` transport uchun, aks holda 409.
- Kuryerda `accepted` / `picked_up` / `on_the_way` yetkazish bo'lsa, `activate` 409 beradi: yo'lda mashina almashmaydi.
- **Guvohnoma toifasi:** `car` → B, `van` → B (3,5 t gacha), `truck` → C. `license_categories` da bo'lmasa, `activate` 409 beradi («guvohnoma toifasi mos emas»).
- **Biriktirish** (`/deliveries/:id/assign`) kuryerning **faol** transportiga qaraydi: turi (№22 dagidek) va sig'imi (7-band).
- Faol transporti yo'q kuryerni biriktirish — 409.
- Yangi transport qo'shilganda do'kon adminlariga push: «Kuryer X yangi transport qo'shdi — tasdiqlang».
- Har o'zgarish tarixga (`courier_vehicle_events`): kim, qachon, qaysi holatdan qaysi holatga.

**Mijoz va kuzatish (№24):** `courier` obyektida `vehicle: { type, model, color, plate }`. Davlat raqami faqat `on_the_way` da, mijoz mashinani tanishi uchun.

**Ko'chirish:** mavjud har bir kuryer uchun hozirgi `vehicle_type` bilan bitta `approved` transport yaratilsin va `active_vehicle_id` ga qo'yilsin.

## 2. 🔴 Olib ketishda tekshiruv va rasm

`POST /api/courier/deliveries/:id/pickup` endi `multipart` ham qabul qilsin:
- `photo` — tovar yuklangan holatdagi rasm. `required_vehicle` `van` yoki `truck` bo'lsa majburiy;
- `items_checked` — `order_item_id` lar ro'yxati. Kuryer har qatorni «oldim» deb belgilaydi, hammasi bo'lmasa 400;
- `comment`.

Rasm №22 dagi isbot rasmlari qatorida saqlansin: `proofs[].kind = pickup | delivery | failure`.

Nizo chiqqanda («tovar shikastlangan yetib keldi») kim javobgarligini aynan shu rasm hal qiladi.

## 3. 🔴 Qabul qiluvchi imzosi va ismi

B2B yetkazishda mijoz kompaniyasi tovarni o'z xodimi orqali qabul qiladi, shuning uchun kod har doim ham bo'lmaydi.

`deliver` ga qo'shimcha maydonlar:
- `received_by_name` (≤ 120) — tovarni qabul qilgan odam;
- `signature` — PNG, kuryer telefonida barmoq bilan chizilgan, `proofs[].kind = signature`.

**Topshirish qoidasi:**
- Kod bo'lsa — yetadi.
- Kod bo'lmasa — rasm + (imzo **yoki** `received_by_name` + izoh).

## 4. 🟡 Yetib keldim va kutish

```
POST /api/courier/deliveries/:id/arrived      { lat, lng }
```

- `on_the_way` holatida qoladi, `arrived_at` yoziladi.
- Mijozga **SMS yuborilmaydi** (narxni tejash — foydalanuvchi qarori, 17.09).
  Kuryer qo'ng'iroq qiladi; kuzatish sahifasi (№24) holatni «Kuryer yetib
  keldi» deb ko'rsatsin. Mobil ilovada — push.
- Kutish vaqti `arrived_at` dan hisoblanadi.
- Mijoz javob bermay 15 daqiqa o'tsa, `fail` da `client_unreachable` ga dalil sifatida ishlatiladi.
- Qo'ng'iroqlar sonini ham yozish mumkin: kuryer sahifasi `POST .../call-attempt` yuboradi.

## 5. 🟡 Joylashuv: yo'nalish va tezlik

`POST /api/courier/location` endi `heading` (0–360) va `speed` (m/s) ham qabul qilsin.

- Qiymatlar `couriers.last_heading`, `last_speed` ga yoziladi.
- Adminka va mijoz xaritasida mashinacha shu tomonga buriladi.
- Hozir yo'nalishni biz ikki nuqtadan hisoblayapmiz. GPS'dan kelgani aniqroq.

## 6. 🟡 Yetkazish haqi va kuryer daromadi

`deliveries.delivery_fee` bor, lekin hech qayerda ishlatilmaydi.

**Tariflar:**
- Tarif jadvali `courier_rates`: `store_id` (null — platforma), `vehicle_type`, `base_fee`, `per_km`, `floor_fee` (qavatga ko'tarish), `wait_fee_per_15min`.
- Yetkazish yaratilganda `delivery_fee` tarifdan taklif qilinsin. Adminkada o'zgartirsa bo'ladi.

**Kuryer uchun:**

```
GET /api/courier/earnings?period=today|week|month
→ { delivered, failed, fees_total, cash_collected, cash_handed_over, cash_balance, days: [{date, delivered, fees}] }
```

**Hisob-kitob:**

```
POST /api/couriers/:id/payouts          { amount, period_from, period_to, comment }   — do'kon admini / superadmin
GET  /api/couriers/:id/payouts
```

## 7. 🟡 Og'irlik va hajm — to'g'ri transport

HVAC uskunasining ko'pi yengil mashinaga sig'maydi.

- `product_model_inside` yoki `characteristics` ga `weight_kg`, `length_cm`, `width_cm`, `height_cm` maydonlari qo'shilsin (ixtiyoriy).
- Yetkazish yaratilganda jami og'irlik va hajm hisoblanib `required_vehicle` taklif qilinsin.
- Kuryerning **faol transporti** sig'imidan (`capacity_kg`, `capacity_m3`, 1a-band) oshsa, biriktirishda ogohlantirish qaytsin (`warnings[]`). 409 emas — bir necha qatnovda olib ketish mumkin.
- `loaders_needed` (yuk ko'taruvchilar soni) va `floor` / `has_elevator` — `deliveries` ga.

## 8. 🟡 Smena

```
POST /api/courier/shift/start   { lat, lng, vehicle_id }
POST /api/courier/shift/end     { lat, lng }
GET  /api/courier/shifts?from=&to=
```

- Smena boshida transport tanlanadi: `vehicle_id` → `activate` bilan bir xil qoidalar (1a-band). Smena davomida transport almashmaydi.
- `is_online` smenadan avtomatik: smena ochiq bo'lsa `true`.
- Smena yopilganda faol yetkazish bo'lsa 409.
- Adminkada kuryer qachon ishga chiqib qachon ketgani ko'rinadi.

## 9. 🟢 Hodisa (shikast, avariya, o'g'irlik)

```
POST /api/courier/deliveries/:id/incident     multipart: type, comment, photos[]
```

- `type`: `damage` · `accident` · `theft` · `other`.
- Do'kon adminlariga darhol push yuboriladi.
- Yetkazish holati o'zgarmaydi. Do'kon `cancel` yoki `retry` qiladi.

## 10. 🟢 Naqd pul: kassa cheki

Mijozdan naqd yoki karta orqali pul olinsa, sotuvchi **fiskal chek** berishi shart.

Kerakli maydonlar (hozircha faqat saqlanadi):
- `payment_method` (`cash` · `card_terminal` · `payme` · `click`);
- `fiscal_receipt_url` yoki `fiscal_sign`.

To'lov ilovasi (Payme/Click) QR orqali sotuvchi hisobiga to'g'ridan-to'g'ri to'lash — keyingi bosqich. Unda kuryer naqd pul tashimaydi.

## Tekshirish

1. Yangi domendan `/sotuvchi-bolish` hujjat yuklash ishlaydi (CORS).
2. Ofertani qabul qilmagan kuryer `accept` qila olmaydi (409). Qabul qilgach — ishlaydi.
3. Hujjati tasdiqlanmagan kuryerni biriktirish — 409.
4. `truck` yetkazishda rasmsiz `pickup` — 400. Hamma qator belgilanmasa — 400.
4a. Kuryer yangi transport qo'shadi → `pending`, `activate` → 409. Admin tasdiqlaydi → `activate` 200. Guvohnomada C yo'q kuryer `truck` ni faollashtira olmaydi — 409. `on_the_way` yetkazishi bor kuryer transport almashtira olmaydi — 409. Faol transporti `car` bo'lgan kuryerni `truck` yetkazishga biriktirish — 409.
5. Kodsiz `deliver`: rasm + imzo → 200. Rasm + izohning o'zi (ism yo'q) → 400.
6. `arrived` → SMS ketmaydi, `arrived_at` yoziladi; `fail` da kutish daqiqalari tarixda.
7. `earnings` kunlar bo'yicha summasi `deliveries` bilan mos.
