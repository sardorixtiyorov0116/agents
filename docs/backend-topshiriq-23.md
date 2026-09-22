# Backend topshirig'i №23 — javob tezligi

**Sana:** 17.09.2026 · Sabab: foydalanuvchilar adminka va kuryer sahifasi
sekinlashganini aytdi. O'lchadik — internet emas, adminka kodi ham qisman
(o'zimiz tuzatdik). Asosiy qism — backendning har bir so'rovga sarflaydigan
vaqti.

## O'lchovlar (Toshkentdan, 17.09.2026, 3 martadan)

| so'rov | TLS ulanish | birinchi bayt |
|---|---|---|
| `GET /api/yoq-sahifa` (404, bazaga tegmaydi) | 0,20 s | **0,44–0,55 s** |
| `GET /api/settings/usd-rate` (bitta qator) | 0,20 s | 0,58–0,64 s |
| `GET /api/category/all` | 0,20 s | 0,59–0,60 s |
| `GET /api/offers/current` | 0,20 s | 0,58 s (sovuq: 1,64 s) |
| `GET /api/orders/all` (31 KB) | — | 0,63–0,71 s |
| `GET /api/products/all?limit=500` (1,3 MB) | — | 1,27–1,36 s |

Taqqoslash: `google.com` birinchi bayt 0,33 s.

Javob sarlavhasida `x-railway-edge: ams1`. **Bazaga tegmaydigan 404
ham ~0,25–0,35 s** kechikadi — ya'ni ilova Amsterdam chetidan uzoqda
(taxminimiz — AQSh regioni). Adminka Vercel'da `iad1` (AQSh Sharqiy)
regionida ishlaydi.

## Savollar (javob kerak)

1. Railway'da **ilova** qaysi regionda? (`us-west2`, `us-east4`,
   `europe-west4`, `asia-southeast1`)
2. **Postgres** qaysi regionda va qayerda (Railway ichida, Neon, Supabase…)?
   Ilova bilan bir regiondami?
3. Bitta oddiy so'rov (`settings/usd-rate`) serverning o'zida qancha
   vaqt oladi? Log'da javob vaqti yozilsa, shu bilan ayting.

## Taklif

- **Ilova va baza bir regionda** bo'lsin — agar hozir boshqa-boshqa
  bo'lsa, eng katta yutuq shu (har so'rovda baza bilan bir necha marta
  borib-kelish bo'ladi).
- Foydalanuvchilarning hammasi O'zbekistonda: **`europe-west4`
  (Amsterdam)** ga ko'chirish Toshkentdan har bir so'rovni ~0,2 s
  qisqartiradi. Ko'chirsangiz, **oldindan ayting** — adminka Vercel
  regionini ham shu bilan bir vaqtda Yevropaga (`fra1`/`ams`) o'tkazamiz,
  aks holda adminka↔backend orasi uzayib ketadi.
- `products/all?limit=500` — 1,3 MB. Adminka butun katalogni kesh bilan
  oladi, lekin sayt ro'yxat sahifalari uchun kerakli maydonlarnigina
  qaytaradigan yengil variant (yoki gzip/brotli siqish yoqilganini
  tekshirish) foydali bo'ladi. Hozir javob siqilganmi?
- Kuryer va yetkazish endpointlari (`/api/deliveries`, `/api/couriers`,
  `/api/couriers/:id/cash`) har ochilishda token bilan chaqiriladi va
  keshlanmaydi — ular 100 ms atrofida qaytsa, kuryer sahifasi sezilarli
  tezlashadi. `deliveries`da `order_id`, `store_id`, `courier_id`,
  `status` ustunlariga indeks bormi?

## Adminka tomonida qilingan (17.09)

- Yetkazish/kuryer sahifalarida backend so'rovlari ketma-ket emas,
  parallel yuboriladi.
- Buyurtma sahifasi yetkazish blokini kutmasdan ochiladi (birinchi
  ko'rinish 2,6 s → 0,45 s), blok keyin oqib keladi.
- "Yetkazishlar" sahifasi 2,0 s → 1,4 s.
