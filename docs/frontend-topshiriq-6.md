# Sayt topshirig'i №6 — savat orqali KP va `/p/` havolasi

**Sana:** 21.09.2026 · Sayt №3 (KP so'rash tugmasi) va Sayt №5 (backend №25
ichida) dagi kartochka/savat qismlarining **o'rnini bosadi**. Backend qismi —
backend №28.

## Hozir saytda (21.09 da ko'rildi)

- Narxsiz kartochka: «Цена по запросу» + qora «Запросить КП» tugmasi.
- Narxli kartochka: narx va «>» — savatga qo'shish tugmasi yo'q.
- `climavent.uz/p/26` → 404.

## 0. 🔴 `/p/:id` yo'naltirish (shoshilinch)

KP tayyor bo'lganda mijozga SMS ketadi (Eskiz shabloni #90540):
`… KP tayyor. Ko'rish: climavent.uz/p/62`. Havola hozir 404.

- `/p/:id` → **301** `/profile/orders/:id` (`/k/:token` dagidek, server tomonda).
- Kirmagan bo'lsa — kirish sahifasi, kirgach shu buyurtmaga qaytadi
  (`?redirect=/profile/orders/62`).
- Buyurtma boshqa foydalanuvchiniki bo'lsa — «Buyurtma topilmadi» (backend 403/404 beradi).
- `/p/*` — `noindex`, sitemap'da yo'q.

## 1. Kartochka va mahsulot sahifasi

- **«Запросить КП» / «KP so'rash» tugmasi olib tashlanadi** — kartochkada ham,
  mahsulot sahifasida ham.
- Narx bo'lmasa narx o'rnida: **«Narxini bilish» · «Узнать цену» · «Get price»**
  (kulrang, kichik; tugma emas). Ustiga bosilsa — kichik izoh:
  «Savatga qo'shing va KP oling — narxni sotuvchi 1 ish kuni ichida beradi».
- **Hamma kartochkada bitta tugma — «Savatga»** (savat belgisi), narxli ham,
  narxsiz ham. Narxli kartochkadagi «>» o'rniga ham shu.
- Mahsulot sahifasi: «Savatga qo'shish»; narxli bo'lsa yonida «Hozir sotib olish».
  Sotuvchi bilan bog'lanish (qo'ng'iroq, Telegram) — pastdagi sotuvchi kartochkasida.

## 2. Savat — ikki yo'l: sotib olish yoki KP olish

Mijoz savatni to'ldiradi, keyin **o'zi tanlaydi**:

| savatda | tugmalar |
|---|---|
| hammasi narxli | **«Buyurtma berish»** va teng darajada **«KP olish»** |
| narxsizi bor | **«KP olish»** (asosiy). «Buyurtma berish» o'rnida izoh: «N ta mahsulot narxini sotuvchi beradi — avval KP oling» |

Jami: «Narxli: 12 400 000 so'm + 2 ta mahsulot narxi sotuvchidan».

### «KP olish» bosilganda

1. Kirmagan bo'lsa — SMS-kod bilan kirish (№18 oqimi). KP bizga mijoz
   sifatida ko'rinishi uchun kirish majburiy.
2. Oyna: kompaniya nomi, STIR (9 raqam) — ixtiyoriy; izoh («montaj bilan»,
   «Toshkentga yetkazish») — ixtiyoriy. Ism va telefon hisobdan.
3. `POST /api/orders/create` + `kind: "quote"`, `source: "site_kp"` va
   qatorlar (backend №28). Backend narxli qatorlar uchun KP ni **darhol**
   yaratib qaytaradi.
4. Mijoz KP sahifasiga o'tadi: `/profile/orders/:id/kp` — shu yerda
   **«PDF yuklab olish»** (`window.print()`, Sayt №3 dagi `/cart/kp` ko'rinishi).
   Savat tozalanadi.

**KP saytning o'zida chiqadi** — sotuvchi kutilmaydi, agar hammasi narxli bo'lsa.

### Narxsiz mahsulot bo'lsa — yechim

KP baribir **darhol** chiqadi, ikki bosqichda:

1. **Hozir — dastlabki KP.** Narxli qatorlar narxi bilan, narxsizlari ro'yxatda
   «narxi sotuvchi tomonidan 1 ish kuni ichida beriladi» deb, jamiga qo'shilmaydi.
   PDF ni hozir yuklasa bo'ladi. Sahifa tepasida: «Sotuvchi narxlarni
   tayyorlayapti — KP to'liq bo'lganda SMS keladi».
2. **Keyin — to'liq KP.** Backend narxsiz qatorlar bo'yicha sotuvchiga so'rov
   ochadi (№25 oqimi). Sotuvchi adminkada narx yozadi → KP yangi versiyasi →
   mijozga SMS #90540 → `/p/:id` → shu KP sahifasi, endi hamma narx bilan va
   «Qabul qilaman» tugmasi.

Mijoz bitta raqamli bitta KP ni ko'radi, shunchaki u to'ladi.

### KP sahifasi (`/profile/orders/:id/kp`)

- har do'kon uchun alohida varaq: sotuvchi rekvizitlari, KP raqami
  (`KP-62-v2` — buyurtma raqami va versiya), sana, **amal qilish muddati**
  (`valid_until`, standart 10 kun), jadval (№, mahsulot, model, soni, narx,
  summa), jami, yetkazish va to'lov shartlari (sotuvchi yozgan bo'lsa);
- izoh: «Narxlar sanadagi kurs bo'yicha. Yakuniy shartlar sotuvchi bilan
  kelishiladi. Ushbu hujjat ommaviy oferta emas.»;
- tugmalar: **«PDF yuklab olish»**, **«Qabul qilaman — buyurtma berish»**
  (faqat hamma qator narxli va muddati o'tmagan bo'lsa), «Rad etish»;
- muddati o'tgan: «KP eskirgan» va «Yangisini olish»
  (`POST /orders/:id/quote/request-again`).

## 3. Profil — «Buyurtmalarim»

- KP lar alohida belgi bilan: «KP · tayyor», «KP · sotuvchi narx beryapti»,
  «KP · eskirgan».
- Qabul qilingan KP — oddiy buyurtma kartochkasi (holat, yetkazish, kuzatish №24).

## 4. Matnlar

| Joy | uz | ru | en |
|---|---|---|---|
| Narxsiz narx o'rni | Narxini bilish | Узнать цену | Get price |
| Kartochka tugmasi | Savatga | В корзину | Add to cart |
| Savat, KP tugmasi | KP olish | Получить КП | Get a quote |
| KP sahifasi, narxsiz qator | Narxini sotuvchi beradi | Цену сообщит продавец | Price from seller |
| KP tayyor | KP tayyor — ko'rib chiqing | КП готово — посмотрите | Your quote is ready |

«So'rov» / «запрос» so'zlari endi ishlatilmaydi.

## Tekshirish

1. `climavent.uz/p/<id>` → kirgan foydalanuvchida buyurtma sahifasi; kirmaganda
   kirishdan keyin shu sahifa; begona buyurtma — «topilmadi».
2. Hech bir kartochkada «Запросить КП» yo'q; narxsizda «Узнать цену» + «В корзину».
3. Narxli savat → «KP olish» → KP sahifasi va PDF darhol, sotuvchi kutilmaydi;
   KP adminkada ko'rinadi.
4. Narxli savat → «Buyurtma berish» avvalgidek ishlaydi.
5. Aralash savat → dastlabki KP darhol (narxsiz qatorlar belgilangan);
   sotuvchi narx yozgach — SMS va to'liq KP, «Qabul qilaman» chiqadi.
6. Ikki do'kon mahsuloti — ikkita varaq.
7. Telefonda KP sahifasi o'qiladi va PDF bo'lib saqlanadi.
