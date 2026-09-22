# №24–27 tekshiruvi

**Kimga:** Climavent backend dasturchisiga
**Sana:** 21.09.2026

Javoblar uchun rahmat. To'rttala topshiriq production'da, Swagger'da hamma
endpoint bor. №26 va №27 deyarli to'liq. Asosiy muammo — **ikkala SMS
matni** Eskiz'ga topshirilgan shablonlarga mos emas: shu holida SMS rad
etiladi. Quyida — tekshirilganlar va tuzatish kerak bo'lganlar.

## ✅ Tekshirildi va ishlaydi

| band | natija |
|---|---|
| Swagger | №24–27 dagi hamma yo'l bor: `tracking/{token}`, `deliveries/{id}/tracking-link`, `orders/{id}/quote` (+ `accept`/`reject`/`request-again`), `orders/quote-stats`, `courier/vehicles`, `couriers/{id}/documents`, `shift/*`, `earnings`, `payouts`, `incident`, `arrived`, `call-attempt`, `courier-rates`, `usd-rate/auto` |
| №24 noto'g'ri token | 404 `Topilmadi` (avval 500 edi — tuzatilgan), qisqa token ham 404 |
| №24 sarlavhalar | `Cache-Control: no-store`, `X-Robots-Tag: noindex`, `x-ratelimit-limit: 60` |
| №24 sayt | `climavent.uz/k/<token>` server tomonida `/kuzatish/<token>` ga yo'naltiradi |
| №26.0 CORS | preflight: `climavent-hamkor.vercel.app` va eski domen — ikkalasiga `Access-Control-Allow-Origin` qaytadi |
| №26 ko'chirish | kuryer #7 ga `approved` transport yaratilgan, `active_vehicle_id` qo'yilgan |
| №27 | `GET …/auto` → `enabled: false`; kalitsiz `GET`/`PATCH` → 401; kurs tarixida 19.09 dan keyin `auto` yozuvi yo'q — cron kursni o'zgartirmayapti |
| №24.5 tozalash | #7 bo'yicha to'g'ri aytdingiz — u faol va #12 ga biriktirilgan, topshiriqdagi ma'lumot xato edi. #12 yakunlangach #7 va store_user 218 ni o'chirishni so'raymiz |

## 🔴 №24 — token formati va SMS matni

**1. Token 32 ta hex belgi bo'lishi kerak.** Hozir 32 bayt base64url
(43 belgi). Topshiriqda: **16 bayt → 32 ta hex belgi** (`0-9a-f`). Sabab:
Eskiz shablonidagi `%w` bitta so'zni kutadi, `-` va `_` belgilari unga mos
kelmasligi mumkin, uzun token esa SMS'ni 160 belgidan oshiradi.
Xesh (SHA-256) va qolgan mantiq o'zgarmaydi.

**2. SMS matni o'zgartirilmasin.** Shablon **#90539** 17.09 da Eskiz'ga
topshirilgan va moderatsiyada. Matn **harfma-harf** shunday bo'lishi shart:

```
Climavent: buyurtma #%d yo'lda. Kuryer: %w. Kuzatish: climavent.uz/k/%w Kod: %d
```

Javobdagi `Buyurtmangiz #62 yo'lda. … https://climavent.uz/kuzatish/<token> Topshirish kodi: …`
shablonga to'g'ri kelmaydi — Eskiz rad etadi. Yangi shablon topshirmaymiz.

- `%w` — kuryerning **ismi** (bitta so'z, familiyasiz) va token;
- `https://` siz, qisqa yo'l `/k/` — sayt uni allaqachon yo'naltiryapti,
  `TRACKING_LINK_PATH=/k/` ni hozir qo'ysa bo'ladi;
- faqat oddiy `'` (U+0027); kuryer ismidagi `‘` / `ʻ` ham `'` ga almashsin.

**3. Javobda yo'q:** №22 dagi «Buyurtmangiz #… topshirildi» SMS'i
o'chirildimi? Topshiriq bo'yicha mijozga **faqat** «yo'lda» SMS'i ketadi.

## 🔴 №25 — KP SMS shabloni

Javobda: `Climavent: #%w buyurtma bo'yicha KP tayyor. Ko'rish: %w` va havola
`https://climavent.uz/profile/orders/:id`. Eskiz'ga topshirilgani — **#90540**:

```
Climavent: #%d so'rovingiz bo'yicha KP tayyor. Ko'rish: climavent.uz/p/%d
```

Ikkala `%d` — buyurtma raqami. `/p/:id` ni sayt `/profile/orders/:id` ga
yo'naltiradi (saytchiga alohida topshiriq — hozir 404).

**Javobda yo'q:** KP qayta yuborilganda (2-, 3-versiya) SMS **qayta
ketmasligi** kerak — faqat birinchi KP da. E-pochta har safar ketsa mayli.

`kind` ni `order-items/create` da aniqlash — buyurtma qatorsiz yaratilishini
hisobga olsak, to'g'ri qaror. Saytga shunday yetkazamiz.

## 🟡 №26 — mavjud kuryer biriktirilmay qoldi

Deploydan keyin yagona kuryer #7 da `documents_verified_at: null` va
`license_categories: []`. Hujjatlarni biz adminkadan yuklab tasdiqlaymiz;
shungacha **iltimos, #7 ga `documents_verified_at` ni qo'lda qo'yib
bering** (siz taklif qilgandek) — #12 sinovi davom etsin.

Savol: #7 ning faol transporti `truck`, guvohnomasida C yo'q — ko'chirish
buni tekshirmasdan faol qilgan. Keyingi `activate` / `shift/start` da 409
beradimi? Bizningcha shunday bo'lishi to'g'ri; ko'chirilganlar uchun
istisno kerak emas.

## Hali tekshirilmadi

Kuzatishning to'liq javobi (maxfiylik qoidalari, `accepted` da joylashuv
null, `retry` dan keyin eski havola 404, 24 soatdan keyin 410) — haqiqiy
token kerak. Yagona mos yetkazish #12, `tracking-link` uni bekor qiladi.
Token hex'ga o'tgach yangi sinov yetkazishida tekshiramiz.

## Qisqasi — kerak

1. №24: token → 32 hex; SMS matni #90539 bilan harfma-harf; «topshirildi» SMS'i yo'qligini tasdiqlash.
2. №25: SMS matni #90540 bilan harfma-harf; qayta versiyada SMS yo'q.
3. №26: #7 ga `documents_verified_at` ni vaqtincha qo'yish.
