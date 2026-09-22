# Backend topshirig'i №19

**Sana:** 16.09.2026 · №17 va №18 qabul qilindi, jonli tekshirildi — rahmat.
Quyidagilar 16.09 dagi umumiy tekshiruvda topildi.

## 1. 🔴 Sharhni boshqa do'kon admini tahrirlay oladi

`PATCH /api/reviews/update/:id` do'kon bo'yicha cheklanmagan.

O'lchangan: `store_id = 1` (climavent) admini tokeni bilan
`PATCH /api/reviews/update/2` → **200**. 2-sharh esa 14-mahsulotga
(`store_id = 2`, jihozvent) tegishli.

Ya'ni bitta sotuvchi raqobatchisining mahsulotidagi salbiy sharhni
yashirib qo'yishi mumkin. Oferta 6.5 va 9.3 bandlariga ham zid.

**Kerak:** do'kon admini faqat o'z do'koni mahsulotlariga tegishli sharh
bilan ishlasin (yashirish/qaytarish), boshqasi **403**. Superadmin hammasini
ko'radi.

**Shu bilan birga — barcha yozish endpointlarini bir marta ko'rib chiqing.**
Bizga jadval qaytarsangiz kifoya: qaysi endpoint do'kon bo'yicha
cheklangan, qaysi biri yo'q:

`products/update` · `products/delete` · `product-images/*` ·
`characteristics/*` · `product-model-inside/*` · `reviews/update` ·
`reviews/delete` · `orders/update` · `order-items/*` · `banners/*` ·
`category/*` · `stores/update` · `store-users/*`

## 2. 🔴 Sayt admini tokeni bekor qilinmaydi

O'zingiz aytgan edingiz (№17 javobi, 3-band izohi): `users.is_admin`,
`AdminGuard` va boshqalar faqat imzoni tekshiradi. Do'kon hisoblarida
qilingan ishni shu yerda ham takrorlang: hisob bazadan tekshirilsin,
`is_admin` tokendan emas bazadan olinsin, parol almashganda eski token
bekor bo'lsin.

## 3. 🟡 Kursni avtomatik yangilash

`settings/usd-rate` = 12 000, oxirgi yangilanish **02.09** — 2 hafta.
Narxlar dollarda saqlanadi, ya'ni har bir eskirgan kun noto'g'ri so'm narxi.

**Kerak:** kunlik avtomatik yangilanish (Markaziy bank ochiq API'si),
kim/qachon o'zgartirgani yozib borilsin, qo'lda o'zgartirish ham qolsin
(adminkadagi sozlamalar sahifasi). Avtomatik manba ishlamasa — eski qiymat
qolsin va xato jurnalga tushsin.

## 4. 🟡 Ariza bo'yicha qaror sotuvchiga avtomatik xabar qilinsin

Hozir superadmin parol o'rnatish havolasini qo'lda yuboradi. Oferta 3.4:
«Operator Arizada ko'rsatilgan elektron pochta yoki telefon raqamiga xabar
yuboradi».

**Kerak:** `approve` da — parol o'rnatish havolasi bilan xabar (SMS yoki
email, qaysi biri arzon bo'lsa); `reject` va `request-info` da — sabab va
ariza holati havolasi bilan. Yuborilgani `seller_application_events` ga
yozilsin.

## 5. 🟡 Banner maydonlari

`banners` da `is_active` va `link` yo'q (uchala bannerda ham). Saytda banner
bosilganda hech qayerga o'tmaydi, mavsumiy bannerni o'chirib qo'yish ham
mumkin emas.

**Kerak:** `is_active` (default true), `link` (ixtiyoriy, ichki yo'l yoki
to'liq URL), `sort_order`. Mehmonga faqat faollari chiqsin.

## 6. 🟢 Rozilik yozuvlarini ko'rish

`offer_acceptances` ga yozilyapti, lekin o'qish yo'li yo'q. Superadmin uchun
`GET /api/offers/acceptances?kind=&user_id=&store_id=&page=` bo'lsa,
adminkada «kim, qachon, qaysi versiyani qabul qilgan» ko'rinadi. Nizo
chiqqanda shu dalil kerak bo'ladi.

## 7. 🟢 Sotuvchi arizasini o'chirish

`DELETE /api/seller-applications/:id` yo'q — sinov va spam arizalarni har
safar siz qo'lda o'chiryapsiz. Superadmin uchun qo'shing (hujjatlari va
hodisalari bilan).

## 8. 🟢 OTP kodi

Ochiq saqlanishini aytgan edingiz. Xeshlash (yoki kod tasdiqlangach darhol
o'chirish) yaxshiroq bo'lardi. Biz maxfiylik siyosatida SMS-kodni alohida
yozamiz.

## Savollar

1. `stores/update` da do'kon admini **qaysi maydonlarni** o'zgartira oladi?
   O'lchadik: o'z do'koni → 200, begona do'kon → 403 (to'g'ri). Biz adminkada
   sotuvchining o'zi uchun profil va rekvizit formasi qilmoqchimiz —
   `legal_name`, `tin`, `legal_form`, `bank_*`, `vat_*`, `director_name`,
   `legal_address` ni sotuvchining o'ziga ochsak bo'ladimi, yoki ular faqat
   superadminda qolishi kerakmi?
2. Buyurtma holati o'zgarishining tarixi (kim, qachon) saqlanadimi?
