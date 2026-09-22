# №16 tekshiruvi — sotuvchi arizalari

**Kimga:** Climavent backend dasturchisiga
**Sana:** 14.09.2026

№16 production'da boshidan oxirigacha sinab ko'rildi: hujjat yuklash →
ariza → ma'lumot so'rash → to'ldirish → izoh → adminkadan tasdiqlash →
parol o'rnatish → sotuvchi kirishi. Deyarli hammasi topshiriqdagidek
ishlaydi — rahmat. Topilgan **bitta xato** va ikkita kichik izoh quyida.

## 🔴 Xato: arizaga qaror chiqargan superadminni o'chirib bo'lmaydi

```
DELETE /api/store-users/delete/35   (servis kaliti)
-> 500 {"statusCode":500,"message":"Internal server error"}
```

- `zz-t16-super` (id 35) — vaqtinchalik superadmin, #16 arizani **tasdiqlagan**.
- Nazorat: xuddi shunday yaratilgan, lekin qaror chiqarmagan superadmin
  o'sha payt **200** bilan o'chdi.
- Taxmin: `seller_applications.reviewed_by` va/yoki
  `seller_application_events.actor_id` → `store_users.id` tashqi kaliti
  o'chirishni to'sib, tutilmagan xato 500 bo'lib chiqyapti.

**Nima kerak:** tarix saqlanishi shart (kim qaror chiqargani — nizo
uchun dalil). Taklif: FK `ON DELETE SET NULL` + ustunda loginni matn
sifatida ham saqlash (masalan `reviewed_by_login`, `actor_login`), shunda
hisob o'chsa ham tarixda "kim" ko'rinib qoladi. Hech bo'lmasa 500 o'rniga
409 va tushunarli xabar.

**Hozirgi holat:** id 35 hisob o'chmay qoldi — biz uni `is_active=false`
qildik va parolini tasodifiy qiymatga almashtirdik (kirib bo'lmaydi,
tekshirildi). Xato tuzatilgach o'chirib qo'ying yoki bizga ayting.
#16 sinov arizasi ham qoladi (arizani o'chirish endpointi yo'q) — nomi
`zz-sinov-16`, STIR 999016016. Uni bazadan qo'lda o'chirsangiz bo'ladi.

## 🔴 CORS: adminka production domeni ruxsat ro'yxatida yo'q

Sotuvchi ariza formasi endi adminkada ochiq sahifa:
`https://climavent-marketplace-admin.vercel.app/sotuvchi-bolish`.
Brauzer so'rovni **to'g'ridan-to'g'ri** backendga yuboradi — shunda ariza
cheklovi (soatiga 5 ta) va `offer_ip` sotuvchining o'z IP'siga yoziladi.

Lekin CORS shu domenga ruxsat bermaydi (tekshirildi 14.09.2026):

```
OPTIONS /api/seller-applications   Origin: https://climavent-marketplace-admin.vercel.app
-> 200, access-control-allow-origin YO'Q
(localhost:3000 va climavent-admin.vercel.app uchun bor)
```

**Iltimos:** `https://climavent-marketplace-admin.vercel.app` ni CORS
ruxsat ro'yxatiga qo'shing. Docs'dagi `climavent-admin.vercel.app` —
boshqa ilova ("ADMIN PANEL - Climavent"), bizning Next.js adminka emas.

Shu tuzatilguncha forma **zaxira yo'l** bilan ishlaydi: adminka serveri
(`/ariza-proksi/*`) orqali, faqat 3 ta ochiq amal, servis kalitisiz.
Uning ikki kamchiligi bor, CORS tuzatilgach ikkalasi o'z-o'zidan yo'qoladi
(forma har safar avval to'g'ridan-to'g'ri yo'lni sinaydi):

1. **IP.** Proksi sotuvchi IP'sini `X-Forwarded-For` va `X-Real-IP` da
   yuboradi. Backend `trust proxy` sozlamasiga qarab buni hisobga olmasligi
   mumkin — unda cheklov barcha sotuvchi uchun bitta Vercel manziliga
   yoziladi va `offer_ip` Vercel manzili bo'ladi. Qanday sozlanganini ayting.
2. **Fayl hajmi.** Vercel so'rov tanasini ~4,5 MB bilan cheklaydi, shuning
   uchun zaxira yo'lda fayl 4 MB gacha.

## 🟡 Izoh 1: to'ldirishda allaqachon bog'langan hujjat

`PATCH /seller-applications/status/:token` ga arizaning **o'z** eski
hujjatlari bilan birga `document_ids` yuborilsa:

```
400 "document_ids: hujjat topilmadi, muddati o'tgan yoki boshqa arizaga bog'langan"
```

Topshiriqda "yangi document_ids" deyilgan, ya'ni xatti-harakat
shartnomaga zid emas. Lekin saytdagi forma to'liq ro'yxatni yuborishi
tabiiy — shu arizaning o'z hujjatlarini e'tiborsiz qoldirib qabul qilish
yaxshiroq bo'lardi. Saytchi hozircha faqat yangi yuklangan id'larni
yuborsin.

## 🟡 Izoh 2: `actor` servis kaliti bilan `null`

Servis kaliti bilan qilingan so'rash va izohda tarixda `actor: null`.
Bu kutilgan (kalit odam emas). Adminka qarorlarni superadmin tokeni bilan
yuboradi — u yerda login to'g'ri yozilyapti (`approved(zz-t16-super)`).

## ✅ Tasdiqlangan

| Band | Natija |
|---|---|
| Guvohnomasiz superadmin endpointlari | 401 |
| `store_admin` tokeni (8 ta amal) | 403 "Bu amal faqat superadmin uchun" |
| Soxta fayl (magic bytes) | 400 |
| Majburiy hujjatlar (MChJ: guvohnoma, buyruq, pasport) | 400, qaysi tur yetishmasligi aytiladi |
| Eski oferta versiyasi | 409 |
| Rate limit (arizalar) | 429 ishlaydi |
| Holat sahifasi | maxfiy maydon yo'q; so'rov matni ko'rinadi, ichki izoh ko'rinmaydi |
| `one/:id` | `public_token`, `offer_user_agent` yo'q; `reviewed_by` — login |
| Hujjat havolasi | https, 5 daqiqa, fayl mazmuni bayt-bayt bir xil, buzilgan token 404 |
| `needs_info` → to'ldirish → `pending`; `pending` da PATCH | 409 |
| Tasdiqlash | do'kon `is_active=false`, rekvizitlar ko'chdi, `application_id`, hisob `store_admin` |
| Nofaol do'kon mehmonga | ko'rinmaydi |
| Qayta tasdiqlash / rad etish | 409 |
| Parol havolasi | ishladi; qayta ishlatish 410; qisqa parol 400 |
| Sotuvchi kirishi | ✅, o'z nofaol do'konini va bank rekvizitini ko'radi, arizalarga 403 |
| Yangi havola (superadmin tokeni) | ✅, eski parol o'chmaydi |
| Do'kon va sotuvchi hisobini o'chirish | 200, arizada `store_id`/`store_user_id` null bo'ldi |

Tekshirib bo'lmadi (tashqaridan ko'rinmaydi): pasport 30 kundan keyin
o'chishi, fayllar yopiq bucket'da turishi.
