# Topshiriq №25 — KP oqimi: so'rovdan qabul qilingan buyurtmagacha (backend + sayt №5)

**Sana:** 17.09.2026 · №24 (kuzatish) bilan parallel qilinsa bo'ladi.

## Muammo (climavent.uz, 17.09 da ko'rildi)

1. **Katalog kartochkasi:** deyarli hamma mahsulotda «Narxi so'rov bo'yicha»
   va yonida «KP so'rash» — ikkalasi bir gapni ikki marta aytadi. Katalog
   do'kon emas, e'lonlar taxtasidek ko'rinadi.
2. **Mahsulot sahifasi:** narx o'rnida 4 ta bir-biriga raqobat qiluvchi
   harakat — «Narxini so'rash» (qo'ng'iroq), «Telegramda yozish», telefon
   raqami va pastroqda yana «KP so'rash». Mijoz qaysi birini bosishini bilmaydi.
3. **KP so'rovi yuborilgandan keyin hech narsa yo'q.** Sotuvchi `quote_sent`
   holatini qo'yadi, lekin KP ning o'zi — narxlar, amal muddati, hujjat —
   tizimda yo'q. Mijoz uni ko'rmaydi, qabul qila olmaydi, buyurtmaga
   aylantira olmaydi. Hammasi telefon va Telegramda davom etadi.
4. «So'rov» so'zi hamma joyda (ruscha «Цена по запросу» + «Запросить КП»).

## Yechim (qisqasi)

- **KP — alohida mijoz turi yoki alohida savat EMAS.** Bu buyurtmaning bir
  turi (`kind: quote` allaqachon bor) — faqat narxni sotuvchi beradi.
- **Bitta yo'l: savat.** Narxli ham, narxsiz ham mahsulot «Savatga»
  qo'shiladi. Savat oxirida tizim o'zi hal qiladi: hammasi narxli bo'lsa —
  «Buyurtma berish», narxsizi bo'lsa — «KP so'rash». Kompaniya uchun
  narxli savatdan ham KP olish mumkin.
- **Kartochkada bitta tugma** — «Savatga». Narx o'rnida narx yoki «Narxi
  kelishiladi» (kulrang, kichik).
- **KP tizim ichida yuboriladi:** sotuvchi adminkada har qatorga narx
  yozadi, amal muddatini qo'yadi, «KP yuborish» ni bosadi. Mijoz profilda
  KP ni ko'radi, PDF yuklaydi va **«Qabul qilaman»** bosadi — so'rov
  oddiy buyurtmaga aylanadi.

---

# Backend

## 1. 🔴 Narxsiz mahsulot savatga va buyurtmaga tushadi

- `cart-items/create` narxsiz model yoki variantni qabul qilsin (narx `null`).
- `POST /orders/create`: qatorlardan birortasi narxsiz bo'lsa, `kind` avtomatik
  `quote` bo'ladi (mijoz `order` yuborsa ham). Javobda `kind` qaytadi —
  sayt «so'rov yuborildi» yoki «buyurtma qabul qilindi» deb to'g'ri yozadi.
- Bitta savatda bir necha do'kon mahsuloti bo'lsa, buyurtma hozir qanday
  bo'linayotgan bo'lsa shunday qoladi. Har do'kon o'z qatorlariga KP beradi.

## 2. 🔴 Sotuvchi KP yuboradi

```
PUT /api/orders/:id/quote            — do'kon admini (faqat o'z qatorlari), superadmin
{
  "items": [{ "order_item_id": 125, "price": 36100228 }, …],   // so'mda, har qator uchun
  "valid_until": "2026-09-27",                                  // standart: bugun + 10 kun
  "delivery_terms": "2 hafta, Toshkent bo'ylab bepul",          // ixtiyoriy, ≤ 500
  "payment_terms": "50% oldindan, bank o'tkazmasi",             // ixtiyoriy, ≤ 500
  "note": "…"                                                   // ixtiyoriy, ≤ 2000
}
```

- Faqat `kind = quote` va holat `new` yoki `quote_sent` da (qayta yuborish =
  yangi versiya). Boshqa holatda 409.
- Aralash buyurtmada do'kon admini faqat o'z qatorlariga narx qo'yadi;
  begona `order_item_id` — 403.
- `order_items.price` yoziladi, `orders.totalAmount` qayta hisoblanadi.
- Yangi jadval `order_quotes` (tarix va nizo uchun): `order_id`, `store_id`,
  `version`, `items` (JSON: qator, nom, model, soni, narx), `valid_until`,
  `delivery_terms`, `payment_terms`, `note`, `sent_by` (store_user), `sent_at`.
  Har yuborish — yangi versiya, eskisi o'zgarmaydi.
- Barcha do'kon qatorlariga narx qo'yilgach buyurtma holati `quote_sent`.
- **Mijozga xabar:** SMS — Eskiz shabloni **#90540** (17.09 da topshirildi,
  moderatsiyada), matn harfma-harf:
  `Climavent: #%d so'rovingiz bo'yicha KP tayyor. Ko'rish: climavent.uz/p/%d`
  (ikkala `%d` — buyurtma raqami; oddiy `'` apostrof). Sayt `/p/:id` ni
  `/profile/orders/:id` ga yo'naltiradi (kirmagan bo'lsa — kirishdan keyin).
  E-pochta bo'lsa — qo'shimcha ravishda xat. Qayta yuborilgan versiyada SMS
  **qayta ketmaydi** (faqat birinchi KP da) — narxni tejash.

Javob va `GET /orders/:id`, `oneuser` da: `quotes: [{ version, store_id, valid_until, delivery_terms, payment_terms, note, sent_at, items }]`.

## 3. 🔴 Mijoz qabul qiladi yoki rad etadi

```
POST /api/orders/:id/quote/accept    — buyurtma egasi
{ "version": 2, "company_name"?: "…", "company_tin"?: "123456789" }

POST /api/orders/:id/quote/reject    — buyurtma egasi
{ "reason": "Qimmat" }               // ixtiyoriy, ≤ 500
```

- **Accept:** faqat `quote_sent` da, `version` oxirgisi bo'lsa va
  `valid_until` o'tmagan bo'lsa (aks holda 409 — «KP eskirgan, yangisini
  so'rang»). Natija: `kind` → `order`, holat → `new`, `quote_accepted_at`,
  qabul qilingan versiya belgilanadi, narxlar qulflanadi. Do'kon adminlariga
  push (№22 mexanizmi): «#62: mijoz KP ni qabul qildi».
- `kind` faqat shu yo'l bilan `quote` → `order` o'zgaradi (№21 dagi
  «o'zgarmaydi» qoidasiga yagona istisno).
- **Reject:** holat `cancelled`, sabab saqlanadi, sotuvchiga push.
- **Mijoz yangi KP so'rashi:** eskirgan KP da `POST /api/orders/:id/quote/request-again` → holat `new`, sotuvchiga push.

## 4. 🟡 Buyurtma holati tarixi (№19 dagi savol)

KP oqimi uchun kerak bo'ldi. `order_events`: `order_id`, `from_status`,
`to_status`, `event` (`created`, `status_changed`, `quote_sent`,
`quote_accepted`, `quote_rejected`, `delivery_*`), `actor_type`
(`customer` / `store` / `superadmin` / `system`), `actor_id`, `note`,
`created_at`. `GET /orders/:id` javobida `events`. Mijozga (`oneuser`) —
`actor_id` siz.

## 5. 🟡 SLA hisobi

`GET /api/orders/all?kind=quote` javobida `quote_due_at` = `createdAt` + 1 ish
kuni (dush–juma, 09:00–18:00 Toshkent). Adminka «24 soat ichida javob
bering» sanog'ini shundan chizadi. `GET /api/deliveries/stats` ga o'xshash
`GET /api/orders/quote-stats`: o'rtacha javob vaqti, KP → buyurtma ulushi,
do'konlar bo'yicha.

---

# Sayt №5

## 1. Kartochka

- Narx bo'lsa — narx (aksiya bilan, avvalgidek). Narx bo'lmasa — **«Narxi
  kelishiladi»** (kulrang, kichik; ru «Цена договорная», en «Price on
  request»). Bir nechta model va eng arzonining narxi bor bo'lsa —
  **«… so'mdan»**.
- **Bitta tugma — «Savatga»** (savat belgisi), narxli-narxsizligidan
  qat'i nazar. «KP so'rash» va «So'rash» tugmalari kartochkadan olib tashlanadi.

## 2. Mahsulot sahifasi

- **Narx bloki:** narx yoki «Narxi kelishiladi» + bir qator izoh: «Narxni
  sotuvchi KP orqali 1 ish kuni ichida beradi».
- **Asosiy tugma:** «Savatga qo'shish». Narxli bo'lsa yonida «Hozir sotib olish».
- **Ikkilamchi havola** (tugma emas): «Kompaniya uchun KP kerakmi?» → hozirgi
  KP oynasi (hamma mahsulot uchun, narxli ham).
- **Sotuvchi bilan bog'lanish** (qo'ng'iroq, Telegram, raqam) — narx blokidan
  olib, pastdagi **sotuvchi kartochkasiga** ko'chiriladi. Ular tugma sifatida
  narx yonida raqobat qilmasin.
- «Xavfsiz to'lov: Humo/Uzcard/Visa/Mastercard» bloki olib tashlansin
  (№19–20 javobida o'zingiz aytgansiz) — o'rniga «To'lov sotuvchiga: bank
  o'tkazmasi, karta yoki naqd».

## 3. Savat — yagona yo'l

- Narxsiz qatorlar narx o'rnida «kelishiladi» bilan ko'rinadi; jami
  «narxli qatorlar: … so'm + N ta narxi kelishiladi».
- **Pastdagi tugma o'zi almashadi:**
  - hammasi narxli → **«Buyurtma berish»** + ostida havola «Kompaniya uchun
    KP olish»;
  - narxsizi bor → **«KP so'rash»** va izoh: «N ta mahsulot narxini
    sotuvchi aytadi. KP ni profilingizda ko'rasiz va qabul qilsangiz buyurtma
    rasmiylashadi».
- KP formasi (kompaniya, STIR, izoh) — mavjud oynadan, savat uchun.
- «KP yuklab olish (PDF)» — nomi **«Narx taklifini yuklab olish»**; narxsiz
  qatorlar avvalgidek «kelishiladi».

## 4. Profil — «Buyurtmalarim»

- KP so'rovi kartochkasi: «Sotuvchi KP tayyorlayapti» (sanoq: «odatda 1 ish kuni»).
- `quote_sent` bo'lsa: **KP sahifasi** — do'kon rekvizitlari, qatorlar narxi
  bilan, amal muddati, yetkazish va to'lov shartlari, izoh; tugmalar
  **«Qabul qilaman»** (kompaniya va STIR so'ralsa to'ldiriladi),
  **«Rad etish»**, **«PDF yuklab olish»** (savatdagi KP komponentidan,
  sotuvchi narxlari bilan).
- Muddati o'tgan: «KP eskirgan» va «Yangisini so'rash».
- Qabul qilingach — oddiy buyurtma kartochkasi (holat, yetkazish, №24 kuzatish).

## 5. Matnlar

| Joy | uz | ru | en |
|---|---|---|---|
| Narxsiz narx o'rni | Narxi kelishiladi | Цена договорная | Price on request |
| Savat, narxsiz bo'lsa | KP so'rash | Запросить КП | Request a quote |
| Mahsulotda ikkilamchi | Kompaniya uchun KP kerakmi? | Нужно КП для компании? | Need a quote for your company? |
| Profil | KP tayyor — ko'rib chiqing | КП готово — посмотрите | Your quote is ready |

«So'rov» / «запрос» so'zi bir ekranda **bir martadan ortiq** ishlatilmasin.

## Tekshirish

1. Narxsiz mahsulot savatga tushadi; savatda «KP so'rash» chiqadi; buyurtma `kind: quote`.
2. Narxli + narxsiz aralash savat → bitta KP so'rovi, narxli qatorlar narxi saqlanadi.
3. Do'kon admini begona qatorga narx qo'ya olmaydi (403).
4. KP yuborilgach mijozga SMS; profilda KP ko'rinadi; PDF narxlar bilan.
5. Qabul → `kind: order`, holat `new`, narxlar o'zgarmaydi; sotuvchiga push.
6. `valid_until` o'tgan KP ni qabul qilish → 409; «yangisini so'rash» → holat `new`.
7. `order_events` da butun yo'l ko'rinadi.

---

**Adminka tomoni (biz):** «KP so'rovlari» alohida bo'lim (Savdo guruhida,
javob kutilayotganlar soni nishon bilan, 24 soat sanog'i), so'rov sahifasida
har qatorga narx kiritish, amal muddati va shartlar, KP ko'rinishini oldindan
ko'rish, «KP yuborish», versiyalar tarixi. Endpointlar chiqqach qilamiz.
