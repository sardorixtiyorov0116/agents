# Backend topshirig'i №28 — KP saytda darhol chiqadi

**Sana:** 21.09.2026 · №25 ustiga kichik qo'shimcha. Sayt tomoni — Sayt №6.

## Nega

Mijoz savatdan sotib olmasdan KP chiqarib olishi kerak (kompaniyalar KP ni
rahbariyatga tasdiqlatadi). Hozir №25 da KP ni faqat sotuvchi yuboradi —
narxi saytda bor mahsulot uchun ham mijoz 1 ish kuni kutadi. Saytda
chiqarilgan har bir KP adminkada ko'rinishi kerak (kim, qaysi mahsulot,
qancha — bu bizning savdo varonkamiz).

## 1. 🔴 `source: "site_kp"` — narxli qatorlarga KP darhol

`POST /api/orders/create` (va qatorlar `order-items/create` bilan qo'shilgach —
qaysi joyda qulay bo'lsa) `kind: "quote"`, `source: "site_kp"` bilan kelsa:

- har do'kon uchun `order_quotes` da **v1** avtomatik yaratilsin: narxli
  qatorlar joriy sayt narxi bilan (aksiya hisobga olingan, so'mda, joriy
  kurs bo'yicha — mijoz ko'rgan narx), narxsiz qatorlar `price: null`;
  `sent_by: null`, `actor_type: system`, `valid_until` = bugun + 10 kun;
- do'konning **hamma** qatori narxli bo'lsa — shu do'kon KP si tayyor;
  buyurtmaning hamma qatori narxli bo'lsa holat darhol `quote_sent`;
- narxsiz qator bo'lsa holat `new` qoladi va sotuvchiga push
  «#62: mijoz KP oldi, N ta qatorga narx kerak». Sotuvchi `PUT …/quote`
  bilan narx yozadi → **v2** (narxli qatorlar narxini ham o'zgartira oladi);
- javobda `quotes` (v1) qaytsin — sayt KP sahifasini shundan chizadi.

**SMS:** darhol chiqqan v1 da SMS **ketmaydi** (mijoz KP ni ekranda ko'rib
turibdi). #90540 faqat sotuvchi narxsiz qatorlarni to'ldirib, KP to'liq
bo'lganda bir marta ketadi.

**№25 ga o'zgartirish:** `PUT …/quote` da «shu do'konning hamma qatoriga narx
qo'yilishi shart» qoidasi qoladi. `quote/accept` faqat buyurtmaning hamma
qatori narxli bo'lsa (aks holda 409 «Sotuvchi hali narx bermagan»).

## 2. 🟡 Adminka uchun

- `GET /api/orders/all?kind=quote` da `source` (`site_kp` · `manual` ·
  eski yozuvlarda `null`) va filtr `?source=site_kp`.
- `GET /api/orders/quote-stats` ga: `site_kp_count`, `site_kp_accepted`,
  ya'ni saytda nechta KP chiqarildi va nechtasi buyurtmaga aylandi.
- **Narxsiz mahsulotga talab:** `GET /api/orders/quote-stats/unpriced` —
  do'kon kesimida narxsiz modellar va ular necha marta KP ga tushgani
  (`[{ product_model_id, name, model, requests, last_requested_at }]`).
  Adminkada sotuvchiga «bu modelga 8 marta KP olindi — narx qo'ying» deb
  ko'rsatamiz.

## Tekshirish

1. Hammasi narxli savat, `source: site_kp` → javobda v1, holat `quote_sent`, SMS yo'q.
2. Aralash → v1 da narxsiz qatorlar `null`, holat `new`, sotuvchiga push; `PUT …/quote` → v2, `quote_sent`, SMS bir marta.
3. Narxsiz qatori bor KP ni `accept` → 409.
4. v1 narxlari sayt ko'rsatgan narx bilan bir xil (aksiya va kurs bilan).
5. `orders/all?kind=quote&source=site_kp` faqat saytdagi KP larni qaytaradi.
