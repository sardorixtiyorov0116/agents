# Backend topshirig'i №24 — mijoz kuryerni kuzatadi (va sayt №4)

**Sana:** 17.09.2026 · №23 (javob tezligi) hali ochiq, lekin bu topshiriqqa
to'sqinlik qilmaydi.

## Kontekst

№22 ishlayapti. Adminka va kuryer sahifasiga xarita qo'shildi (OpenStreetMap,
Leaflet): kuryer har 45 soniyada joylashuvini yuboradi, adminkada jonli xarita
bor, yetkazish yaratishda manzil xaritadan belgilanadi (`dropoff_lat/lng`).

Endi **mijoz** ham ko'rishi kerak: kuryer qayerda, qachon yetib keladi,
buyurtma qaysi bosqichda — Uzum va Yandex Go'dagidek. Mijozdan kirish
talab qilinmaydi: SMS'dagi havola — kalitning o'zi.

## 1. 🔴 Kuzatish havolasi

- `start` (→ `on_the_way`) da `tracking_token` yaratilsin: **32 ta hex belgi**
  (16 bayt tasodifiy, faqat `0-9a-f` — SMS shablonidagi `%w` ga `-`/`_`
  belgilarisiz mos kelishi uchun). Bazada **faqat SHA-256 xeshi**
  (`deliveries.tracking_token_hash`, unique indeks) — №21 dagi refresh tokenlar kabi.
- SMS'dagi havola: `climavent.uz/k/<token>` (qisqa, `https://` siz); sayt uni
  `/kuzatish/<token>` ga 301 bilan yo'naltiradi.
- Havola **24 soat** amal qiladi: yetkazish `delivered` / `failed` /
  `cancelled` / `returned` bo'lgandan keyin 24 soat o'tgach — 410.
- `retry` va qayta `start` da yangi token, eskisi bekor.

**Adminka uchun** (SMS shabloni tasdiqlanmaguncha havolani qo'lda yuborish kerak):

```
POST /api/deliveries/:id/tracking-link     — do'kon admini (o'z do'koni), superadmin
→ 200 { "url": "https://climavent.uz/kuzatish/…", "expires_at": null }
```

Faqat `accepted`, `picked_up`, `on_the_way` da; boshqa holatda 409.
Chaqirilganda yangi token yaratiladi (eski havola bekor) — ochiq token
bazada saqlanmagani uchun boshqa yo'l yo'q. Tarixga `tracking_link_created`.

## 2. 🔴 Ochiq endpoint

```
GET /api/tracking/:token        — guvohnomasiz
```

Javob (faqat shu maydonlar — ortiqcha hech narsa):

```json
{
  "status": "on_the_way",
  "steps": [
    { "status": "accepted",   "at": "2026-09-17T09:10:00Z" },
    { "status": "picked_up",  "at": "2026-09-17T09:25:00Z" },
    { "status": "on_the_way", "at": "2026-09-17T09:31:00Z" }
  ],
  "order_id": 62,
  "store": { "name": "Jihozvent", "phone": "+998…" },
  "courier": { "first_name": "Aziz", "vehicle_type": "car", "phone": "+998…" },
  "courier_location": { "lat": 41.2995, "lng": 69.2401, "at": "…", "stale": false },
  "destination": { "lat": 41.2856, "lng": 69.2034, "address": "Toshkent, Chilonzor…" },
  "window": { "from": "…", "to": "…" },
  "eta_minutes": 14,
  "cod_amount": 250000,
  "items": [{ "name": "Ventilyator VO 06-300", "model": "ВО 06-300-5", "quantity": 2 }],
  "delivered_at": null
}
```

**Maxfiylik qoidalari (majburiy):**

| Maydon | Qachon beriladi |
|---|---|
| `courier_location` | **Faqat** `picked_up` va `on_the_way` da. Koordinata 4 xonagacha yumaloqlansin (~11 m). `last_seen_at` 5 daqiqadan eski bo'lsa `stale: true` |
| `courier.first_name` | Faqat ism (familiyasiz) |
| `courier.phone` | Faqat `on_the_way` da. Keyinchalik raqamni yashirish (proksi qo'ng'iroq) kerak bo'lsa alohida qilamiz |
| `destination.address` | Mijozning o'z manzili — beriladi; `dropoff_details` (kvartira, qavat) **berilmaydi** |
| Yakunlangandan keyin | `courier_location` va `courier.phone` — null |

Tarixda `actor_id`, kuryer ID, do'kon ID, mijoz telefoni **chiqmasin**.

**`eta_minutes`:** hozircha oddiy baho — kuryer joyidan manzilgacha to'g'ri
masofa × 1,4 (shahar yo'llari) ÷ 25 km/soat, pastki chegara 3 daqiqa. Joylashuv
yo'q yoki eskirgan bo'lsa `null`. Keyin marshrut xizmati bilan almashtiramiz.

**Himoya:**
- IP bo'yicha daqiqasiga 60 so'rov (sahifa 15 soniyada yangilanadi — 4/daq).
- Noto'g'ri token — 404 (bor-yo'qligi farqlanmasin); muddati o'tgan — 410.
- `Cache-Control: no-store`, `X-Robots-Tag: noindex`.

## 3. 🟡 Kuryer joylashuvi tezroq

Kuzatish ochiq bo'lsa 45 soniya uzoq. Kuryer sahifasi `on_the_way` da
**15 soniyada** bir yuboradi (adminka tomonida o'zgartiramiz). №22 dagi
chegara (daqiqasiga 30) yetadi — tekshirib qo'ying, `courier_locations` ga
yozish hajmi oshmasin: 15 soniyadan tez kelgan nuqtalar tarixga yozilmasin,
faqat `couriers.last_*` yangilansin.

## 4. 🔴 SMS — Eskizga TOPSHIRILDI (17.09, moderatsiyada)

Shablon **#90539**. Matn **harfma-harf** shunday yuborilsin (aks holda Eskiz rad etadi):

```
Climavent: buyurtma #%d yo'lda. Kuryer: %w. Kuzatish: climavent.uz/k/%w Kod: %d
```

- `%d` — buyurtma raqami va 4 xonali kod; `%w` — kuryerning **ismi**
  (bitta so'z, familiyasiz) va 32 ta hex belgili token.
- Faqat oddiy `'` (U+0027) apostrof — `‘` yoki `ʻ` SMS'ni unicode'ga
  o'tkazadi va bitta SMS 160 emas, 70 belgi bo'lib narxi ikki barobar oshadi.
  Kuryer ismida ham shunday belgilar bo'lsa `'` ga almashtiring.
- Namunaviy uzunlik: 119 belgi — bitta SMS.

**Narxni tejash uchun qaror (foydalanuvchi, 17.09):** mijozga SMS **faqat
shu bittasi** ketadi. №22 dagi «Buyurtmangiz #… topshirildi» SMS'i
**yuborilmasin**. Qolgan xabarlar mobil ilova chiqqach push bo'ladi.
Shablon tasdiqlanmaguncha SMS xatosi amalni buzmasin (№22 dagidek).

## 5. 🟢 Tozalash (sinovlardan qolgan)

Bazadan o'chirish mumkin — hammasi bizning sinovimiz:

- kuryer **#7** `zz-kuryer` (store_user 218) va **#8** `zz-kuryer2` (store_user 226) — ikkalasi nofaol;
- yetkazish **#11** (#26 buyurtma, `delivered`, isbot rasmi bilan) va **#13** (#26, `cancelled`);
- ularning `delivery_events`, `courier_locations`, `cash_handovers` yozuvlari.

#26 buyurtmaning o'zi qoladi (holati `new`). **#12 ga tegmang** — foydalanuvchi sinayapti.

---

# Sayt №4 — kuzatish sahifasi

`https://climavent.uz/kuzatish/:token` (va ixtiyoriy `/k/:token` → 301).

**Ko'rinish (telefon uchun birinchi):**

1. **Xarita** ekranning yuqori ~55% i: manzil pini va kuryer belgisi,
   ikkalasi sig'adigan masshtab. Leaflet + OpenStreetMap (adminkadagi kabi,
   atribusiya bilan). Kuryer belgisi yangi nuqtaga silliq suriladi.
2. **Kartochka** pastda: katta harflar bilan holat («Kuryer yo'lda»),
   **«~14 daqiqa»** (ETA yo'q bo'lsa — vaqt oralig'i), kuryer ismi va
   transporti, **«Kuryerga qo'ng'iroq»** (faqat `on_the_way` da),
   **«Do'konga qo'ng'iroq»**.
3. **Qadamlar:** Qabul qilindi → Kuryer oldi → Yo'lda → Topshirildi, vaqtlari bilan.
4. **Naqd to'lov** bo'lsa: «Kuryerga 250 000 so'm tayyorlab qo'ying».
5. **Tovarlar** — yig'iladigan ro'yxat.
6. `stale: true` — «Kuryer joylashuvi 5 daqiqadan beri yangilanmagan».
7. **Topshirilgan:** yashil holat, vaqt, xarita va qo'ng'iroq tugmalari yo'q.
8. **410/404:** «Havola muddati o'tgan» va «Buyurtmalarim» havolasi.

**Texnik:**
- 15 soniyada yangilanadi, sahifa yashirin bo'lsa to'xtaydi (`visibilitychange`);
  `delivered` / `cancelled` da yangilanish to'xtaydi.
- `noindex`, sitemap'ga kirmaydi, sahifa kesh qilinmaydi.
- Uch til (`?lang=` va cookie — №2 dagidek).
- Token hech qayerga log qilinmasin (analitika hodisalarida ham yo'l
  `/kuzatish/:token` emas, `/kuzatish` deb yozilsin).
- Brend: logotip va ranglar adminkadagidek — belgi fayli
  `https://climavent-hamkor.vercel.app/brend/belgi.svg` (vektor).

## Tekshirish

1. `start` → SMS'da havola; havola ochiladi, kuryer va manzil xaritada.
2. `accepted` holatida (tokenni `tracking-link` bilan olib) `courier_location` null.
3. Javobda `dropoff_details`, kuryer familiyasi, ID lar yo'q.
4. `delivered` dan keyin `courier_location` va telefon null; 24 soatdan keyin 410.
5. `retry` → eski havola 404.
6. 61-so'rov bir daqiqada → 429.
7. Noto'g'ri token → 404, javob vaqti to'g'ri token bilan bir xil (timing orqali token borligini bilib bo'lmasin).
