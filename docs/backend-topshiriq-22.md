# Backend topshirig'i №22 — kuryerlar va yetkazib berish

**Sana:** 17.09.2026 · №19, №20, №21 hali ochiq — ulardagi 🔴 bandlar
(sharh ruxsati, hujjatlarni R2 ga ko'chirish, parol almashtirish) oldinroq.
Bu topshiriq katta: bosqichma-bosqich chiqarish mumkin (1–5 → 6–8 → 9–10).

## Kontekst

Buyurtmani do'kon omboridan olib, mijozga **kuryer** yetkazadi. Keyinchalik
uchta mobil ilova bo'ladi: sotuvchi, kuryer, xaridor. Ilovalar shu backendga
ulanadi — shuning uchun hamma narsa **API orqali** va ilovaga tayyor
(push-bildirishnoma, uzoq yashaydigan sessiya) qilib yozilsin.

Hozircha **ilova yozilmaydi**: adminkada kuryer biriktirish va kuryer uchun
telefonda ochiladigan sahifa qilinadi. Endpointlar shunday bo'lsinki, keyin
ilova ularni o'zgarishsiz ishlatsin.

### Hali aniqlanmagan — shuning uchun moslashuvchan qilinsin

| savol | qanday yechiladi |
|---|---|
| Kuryer kimniki: platformanikimi, do'konnikimi? | `couriers.store_id` — `null` = platforma kuryeri, raqam = shu do'kon kuryeri. Ikkalasi ham ishlaydi |
| Og'ir uskuna (VRF blok) — yengil mashina yetmaydi | `vehicle_type` kuryerda va `required_vehicle` yetkazishda; mos kelmaganga biriktirish → 409 |
| Mijoz kuryerga pul to'laydimi? | `cod_amount` (naqd olinadigan summa). `0` = oldindan to'langan. Pul hisobi 9-bandda |
| Tashqi xizmat (Yandex Dostavka va h.k.) | hozir yo'q, lekin `provider` maydoni (`own`) qoldirilsin |

## 1. 🔴 Kuryer hisobi

Kirish, `token_version`, jurnal (№17, №21) qayta yozilmasin — kuryer
**`store_users` dagi yangi rol**: `role = "courier"`.

Profil — `couriers`:

| maydon | |
|---|---|
| `id` | |
| `store_user_id` | unique, `store_users.id` |
| `store_id` | `null` — platforma kuryeri |
| `full_name`, `phone` | telefon `+998XXXXXXXXX`, unique |
| `vehicle_type` | `foot` · `bike` · `car` · `van` · `truck` |
| `is_active` | superadmin/do'kon o'chirib qo'ya oladi (tokenlar ham bekor — `token_version`) |
| `is_online` | kuryerning o'zi "ishdaman / ishda emasman" |
| `last_lat`, `last_lng`, `last_seen_at` | 6-band |
| `created_at`, `updated_at` | |

Endpointlar:

```
POST   /api/couriers              — superadmin (istalgan store_id yoki null),
                                    do'kon admini (faqat o'z store_id)
GET    /api/couriers?store_id=&is_active=&is_online=
PATCH  /api/couriers/:id
DELETE /api/couriers/:id          — faol yetkazishi bo'lsa 409; aks holda
                                    is_active=false (tarix saqlanadi)
```

Parol №12 dagi bir martalik havola orqali o'rnatiladi (chatda parol yurmaydi).

**Ruxsatlar (majburiy, backendda):**
- do'kon admini faqat **o'z** kuryerlarini ko'radi va o'zgartiradi, boshqa
  do'konniki → 403 (№19 dagi sharh xatosi takrorlanmasin);
- kuryer tokeni **faqat** `/api/courier/*` ga kiradi; `/api/products`,
  `/api/orders/all`, `/api/stores` va boshqalar → 403.

## 2. 🔴 Yetkazishlar — `deliveries`

Bitta buyurtmada bir nechta do'kon tovari bo'lishi mumkin → **har do'kon
uchun alohida yetkazish** (olish manzili har xil).

| maydon | |
|---|---|
| `id` | |
| `order_id` | |
| `store_id` | tovar olinadigan do'kon |
| `courier_id` | `null` — hali biriktirilmagan |
| `status` | 3-band |
| `provider` | `own` (hozircha yagona qiymat) |
| `required_vehicle` | `foot` … `truck`, standart `car` |
| `pickup_address`, `pickup_lat`, `pickup_lng` | standart — do'kon manzilidan |
| `dropoff_address`, `dropoff_lat`, `dropoff_lng`, `dropoff_details` | kirish, qavat, xonadon, mo'ljal |
| `recipient_name`, `recipient_phone` | |
| `window_from`, `window_to` | kelishilgan vaqt oralig'i |
| `items` | shu do'kondan olinadigan `order_items.id` lar |
| `cod_amount` | so'mda; `0` — oldindan to'langan |
| `cash_collected` | kuryer haqiqatda olgan summa |
| `delivery_fee` | kuryer/yetkazish haqi (hozir `null` bo'lishi mumkin) |
| `proof_photo_url` | **R2** (№20 dagi kabi — Railway diskiga emas) |
| `proof_code_hash` | 5-band; ochiq kod saqlanmaydi |
| `failure_reason` | `client_unreachable` · `client_refused` · `wrong_address` · `damaged` · `other` |
| `failure_comment` | |
| `assigned_at`, `accepted_at`, `picked_up_at`, `delivered_at`, `failed_at` | |
| `created_at`, `updated_at` | |

Tarix — `delivery_events`: `delivery_id`, `from_status`, `to_status`,
`actor_type` (`superadmin` · `store` · `courier` · `system`), `actor_id`,
`lat`, `lng`, `comment`, `created_at`. Har holat o'zgarishi yoziladi.

### Buyurtmaga qo'shimcha maydonlar

Hozir `orders.location` — bitta matn. Kuryerga yetmaydi:
`orders.recipient_name`, `recipient_phone`, `address_details`, `lat`, `lng`
(ixtiyoriy) qo'shilsin; `POST /api/orders/create` qabul qilsin. Eski
buyurtmalarda `null` bo'lib qoladi — yetkazish yaratilayotganda qo'lda
to'ldiriladi. Saytda manzil formasi — alohida sayt topshirig'i.

## 3. 🔴 Holatlar va o'tishlar

```
pending ──assign──▶ assigned ──accept──▶ accepted ──pickup──▶ picked_up
   ▲                   │                                          │
   └──── reject ───────┘                                        start
                                                                  ▼
             delivered ◀──deliver── on_the_way ──fail──▶ failed ──▶ returned
```

| o'tish | kim | shart |
|---|---|---|
| `pending → assigned` | superadmin, do'kon | kuryer faol, transporti mos |
| `assigned → pending` (reject) | kuryer | sabab majburiy |
| `assigned → accepted` | kuryer | |
| `accepted → picked_up` | kuryer | |
| `picked_up → on_the_way` | kuryer | |
| `on_the_way → delivered` | kuryer | 5-band: kod yoki rasm |
| `on_the_way → failed` | kuryer | `failure_reason` majburiy |
| `failed → returned` | do'kon, superadmin | tovar omborga qaytdi |
| `failed → pending` | do'kon, superadmin | qayta yetkazish |
| har qanday, `delivered` dan tashqari → `cancelled` | do'kon, superadmin | |

Ruxsat etilmagan o'tish → **409** (`{"message":"picked_up dan delivered ga o'tib bo'lmaydi"}`).

**Buyurtma holati bilan bog'lanish:**
- birinchi yetkazish `on_the_way` → buyurtma `shipping`;
- buyurtmaning **hamma** yetkazishlari `delivered` → buyurtma `done`;
- buyurtma `cancelled` qilinsa → faol yetkazishlar `cancelled`, kuryerga push.

## 4. 🔴 Endpointlar

### Adminka (superadmin va do'kon admini)

```
POST  /api/deliveries                   { order_id, store_id, ...manzil maydonlari }
                                        — manzil berilmasa buyurtmadan olinadi
GET   /api/deliveries?status=&store_id=&courier_id=&order_id=&date_from=&date_to=
GET   /api/deliveries/:id               — events bilan
PATCH /api/deliveries/:id               — faqat pending/assigned da manzil, vaqt, cod
POST  /api/deliveries/:id/assign        { courier_id }
POST  /api/deliveries/:id/cancel        { comment }
POST  /api/deliveries/:id/return
POST  /api/deliveries/:id/retry
GET   /api/orders/:id                   — javobga `deliveries` qo'shilsin
```

Do'kon admini faqat `store_id` o'ziniki bo'lgan yetkazishlarni ko'radi va
faqat o'z kuryerlarini biriktiradi. Platforma kuryerini (`store_id = null`)
faqat superadmin biriktiradi.

### Kuryer

```
GET   /api/courier/me
PATCH /api/courier/me                   { is_online }
GET   /api/courier/deliveries?scope=active|history
GET   /api/courier/deliveries/:id
POST  /api/courier/deliveries/:id/accept
POST  /api/courier/deliveries/:id/reject   { comment }
POST  /api/courier/deliveries/:id/pickup
POST  /api/courier/deliveries/:id/start
POST  /api/courier/deliveries/:id/deliver  { code? , photo? (multipart), cash_collected? }
POST  /api/courier/deliveries/:id/fail     { failure_reason, failure_comment?, photo? }
POST  /api/courier/location                { lat, lng, accuracy }
```

- Kuryer **faqat o'ziga** biriktirilgan yetkazishni ko'radi; boshqasi → 404.
- **Maxfiylik:** mijoz telefoni va aniq manzil yetkazish faol paytda
  ko'rinadi. `delivered`/`failed` dan **24 soat** o'tgach tarixda telefon
  yashiriladi (`+998 90 *** ** 96`), manzil — faqat tuman/ko'cha.
- Har amalda `lat`/`lng` ixtiyoriy qabul qilinsin → `delivery_events` ga.

## 5. 🔴 Topshirishni isbotlash

- `on_the_way` ga o'tganda mijozga SMS: *"Buyurtmangiz yo'lda. Kuryer:
  Ism, +998… Topshirish kodi: 4821"*. Kod 4 raqam, `bcrypt`/HMAC bilan
  saqlanadi, 5 ta noto'g'ri urinishdan keyin bloklanadi.
- `deliver`: to'g'ri **kod** yoki **rasm** (mijoz telefonsiz, kodni topa
  olmadi — rasm majburiy, `comment` bilan). Ikkalasi ham yo'q → 400.
- `cod_amount > 0` bo'lsa `cash_collected` majburiy; `cod_amount` dan
  farq qilsa `comment` majburiy.
- SMS — №18 dagi OTP yuboruvchi xizmat orqali; test raqamlaridan
  tashqariga sinovda yuborilmasin.

## 6. 🟡 Joylashuv

- `POST /api/courier/location` — kuryer ilovasi/sahifasi faol yetkazish
  bor paytda **30–60 soniyada** bir yuboradi. `couriers.last_*` yangilanadi.
- Yo'l tarixi (`courier_locations`) faqat faol yetkazish paytida yoziladi
  va **30 kundan keyin o'chiriladi** (cron). Ish vaqtidan tashqari joylashuv
  saqlanmaydi.
- `GET /api/deliveries/:id` javobida kuryerning oxirgi joylashuvi va
  `last_seen_at` — adminkada xaritada ko'rsatish uchun.
- Mijozga jonli kuzatuv — keyin, xaridor ilovasi bilan.

## 7. 🟡 Push-bildirishnomalar (ilovaga tayyorlik)

`device_tokens`: `id`, `owner_type` (`store_user` · `user`), `owner_id`,
`platform` (`ios` · `android` · `web`), `token` (FCM), `last_used_at`.

```
POST   /api/devices        { platform, token }   — tokendagi egaga yoziladi
DELETE /api/devices/:token
```

Bitta xizmat (FCM — iOS, Android va PWA web-push'ni birga qoplaydi).
Xato qaytargan (`UNREGISTERED`) token o'chirilsin. Hodisalar:

| hodisa | kimga |
|---|---|
| yangi buyurtma / KP so'rovi | do'kon adminlari (o'z do'koni) |
| yetkazish biriktirildi / bekor qilindi / manzil o'zgardi | kuryer |
| kuryer rad etdi, `failed` | do'kon adminlari |
| `on_the_way`, `delivered` | mijoz (hozircha SMS; ilova chiqqach push) |

Push yuborilmasa asosiy amal buzilmasin (navbat yoki `try/catch` + log).

## 8. 🟡 Mobil sessiya

Ilova har kuni qayta parol so'ramasligi kerak, lekin o'g'irlangan token
abadiy ishlamasin:

- `access_token` — **15 daqiqa**; `refresh_token` — **60 kun**, bazada
  **hash** bilan, har ishlatilganda yangisi beriladi (rotation), eskisi
  qayta ishlatilsa — shu hisobning barcha refresh tokenlari bekor.
- `POST /api/store-auth/refresh`, `POST /api/store-auth/logout` (joriy
  qurilma), `token_version` oshsa hammasi bekor (№17 bilan bir xil).
- Adminka (veb) hozirgi tokenda qolaveradi — bu faqat ilova uchun,
  `client: "mobile"` bilan kirilganda.

## 9. 🟢 Naqd pul hisobi

- `GET /api/couriers/:id/cash` — kuryer qo'lidagi, hali topshirilmagan summa
  (`cash_collected` yig'indisi − topshirilgan).
- `POST /api/couriers/:id/cash-handover { amount, comment }` — do'kon admini
  yoki superadmin puldni qabul qildi; `cash_handovers` jadvaliga yoziladi.
- Kuryerda 24 soatdan ortiq topshirilmagan naqd bo'lsa — adminlarga push.

## 10. 🟢 Hisobotlar

`GET /api/deliveries/stats?date_from=&date_to=&store_id=&courier_id=`:
jami, `delivered`, `failed` (sabab bo'yicha), o'rtacha
`assigned → delivered` vaqti, o'z vaqtida yetkazilganlar ulushi
(`delivered_at <= window_to`), kuryerlar bo'yicha kesim.

## Adminka tomoni (biz qilamiz, endpointlar chiqqach)

Buyurtma sahifasida "Yetkazish" bloki (yaratish, kuryer biriktirish, holat
tarixi, xarita); "Kuryerlar" bo'limi; kuryer uchun telefonda ochiladigan
alohida sahifa (PWA). Endpoint yo'q paytda bo'limlar ko'rinmaydi.

## Huquqiy tomon (biz)

Kuryer joylashuvi va mijoz ma'lumotlarini kuryerga berish — maxfiylik
siyosatiga qo'shiladi; kuryer bilan shartnoma (xodim yoki pudratchi) —
huquqshunos bilan. Backendga ta'siri: yuqoridagi muddatlar (24 soat, 30 kun).

## Tekshirish

1. Do'kon admini boshqa do'kon kuryerini ko'rmaydi, o'zgartira olmaydi,
   yetkazishga biriktira olmaydi → 403.
2. Kuryer tokeni bilan `/api/orders/all`, `/api/products` (yozish),
   `/api/stores` → 403; boshqa kuryerning yetkazishi → 404.
3. `truck` talab qilingan yetkazishga `car` kuryer → 409.
4. `picked_up → delivered` (sakrab) → 409; to'g'ri zanjir → 200, har qadam
   `delivery_events` da.
5. Kodsiz va rasmsiz `deliver` → 400; noto'g'ri kod 5 marta → blok.
6. Buyurtmaning ikki yetkazishidan biri `delivered` → buyurtma `shipping`da;
   ikkinchisi ham → `done`.
7. `cod_amount = 1 500 000`, `cash_collected` yo'q → 400.
8. 24 soatdan keyin kuryer tarixida telefon yashirilgan.
9. Faol yetkazishi bor kuryerni o'chirish → 409; `is_active=false` → uning
   eski tokeni 401.
10. Refresh token ikki marta ishlatilsa → ikkinchisi 401 va hisobning barcha
    refresh tokenlari bekor.
