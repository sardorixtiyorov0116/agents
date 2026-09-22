# №19–22 tekshiruvi

**Kimga:** Climavent backend dasturchisiga
**Sana:** 17.09.2026

Javob yozishga ulgurmagan ekansiz — o'zimiz production'da tekshirdik.
№19, №20, №21, №22 deyarli to'liq ishlaydi, rahmat. Adminka hammasiga
ulandi va chiqarildi (kuryer telefon sahifasi `/kuryer` ham).
Quyida — topilganlar va javob kerak bo'lgan savollar.

## ✅ Tekshirildi va ishlaydi

| band | natija |
|---|---|
| №19.1 sharh ruxsati | begona do'kon sharhi → 403, begona do'kon PATCH → 403 |
| №19.3 kurs | cron 17.09 da 12 000 → 11 797,46 qo'ydi, tarix yozilgan (`source: auto`) |
| №19.5 banner | `is_active`, `link`, `sort_order` bor |
| №19.6 roziliklar | `offers/acceptances` ishlaydi, do'kon admini → 403; adminkadan qabul qilinganda haqiqiy IP va brauzer yozildi |
| №19.7 ariza | `DELETE` yo'q id → 404, do'kon admini → 403 |
| №20.2 oferta | loginda `offer_pending`; tasdiqlanmaguncha yozish → 409 `offer_acceptance_required`; `offers/accept` dan keyin 200 |
| №21.1 parol | noto'g'ri joriy → 401, qisqa → 400, to'g'ri → yangi token, eski token → 401; 6-urinish → 429 |
| №21.2 jurnal | o'z jurnali va superadmin jurnali ishlaydi, parol matni yozilmaydi; begona hisob jurnali → 403 |
| №21.3 KP | `orders/all?kind=quote` ishlaydi |
| №22 kuryer | do'kon admini platforma kuryerini yarata olmaydi (403); begona do'kon kuryerini ko'rish/tahrir/naqd → 403; kuryer tokeni `orders/all`, `couriers`, `deliveries`, `store-users`, `products/create` → 403 |
| №22 yetkazish | to'liq zanjir adminka va kuryer sahifasi orqali: yaratish → biriktirish → accept → pickup → start → noto'g'ri kod ("qolgan urinish: 4") → rasm + izoh + naqd bilan deliver → buyurtma `done`; isbot rasmi faqat token bilan; begona do'kon → 404; `stats` begona do'konga 0 qaytaradi; naqd qabul qilish ishlaydi |
| №22.8 refresh | `client: "mobile"` → 15 daqiqa + 60 kun; rotatsiya; eski refresh qayta ishlatilsa → 401 va yangisi ham bekor |
| devices | POST 201, DELETE 200 |

## 🔴 Kirish cheklovi butun IP'ni 1 soatga yopadi

Sinov paytida (15–20 daqiqada ~20 ta `store-auth/login`, har xil
loginlar bilan) serverning **IP manzili** bo'yicha
`429 ThrottlerException`, `Retry-After: 2909` — deyarli **bir soat**
**barcha** loginlar uchun yopildi (to'g'ri parol bilan ham).

Muammo: ofisdagi hamma sotuvchi va kuryer bitta tashqi IP ortida
(bitta Wi-Fi yoki bitta mobil operator NAT'i). Bitta odam parolni
bir necha marta xato tersa — hamma bir soat kira olmaydi. Kuryerlar
kun davomida ko'p marta qayta kiradi.

**Taklif:**
- noto'g'ri urinishlar **login + IP** bo'yicha sanalsin (masalan
  15 daqiqada 5 ta), faqat shu login bloklansin;
- IP bo'yicha umumiy chegara ancha yuqori bo'lsin (masalan
  daqiqasiga 30) va blok qisqa bo'lsin (1–5 daqiqa);
- **muvaffaqiyatli** kirishlar hisoblagichga qo'shilmasin.

## 🟡 Kichik izohlar

1. **`refreshToken` nomi.** Login va refresh javobida `refreshToken`
   (camelCase), `POST /store-auth/refresh` esa `refresh_token` qabul
   qiladi, qolgan maydonlar ham snake_case (`refresh_expires_at`,
   `expires_in`). Bitta uslubga keltiring — mobil ilova yozilishidan oldin.
2. **Kuryerning `store_users` yozuvi.** `DELETE /store-users/delete/218`
   (kuryer hisobi) → 409 "Kuryer hisobi /api/couriers orqali
   boshqariladi" — to'g'ri. Lekin `store-users/all` ro'yxatida kuryer
   hisoblari ham chiqadi. Ro'yxatga `?role=` filtri qo'shing yoki
   kuryerlarni standartda chiqarmang — adminkada "do'kon hisoblari"
   orasida kuryer ko'rinib qolmasin.
3. **Kuryer parol havolasi javobi.** `POST /couriers/{id}/password-setup`
   javobida muddat qaysi kalitda keladi? `POST /couriers` da
   `password_setup_expires_at` bor edi — ikkalasida bir xil bo'lsin.
4. **Kuryer ro'yxatidagi yetkazish.** `GET /courier/deliveries` javobida
   `dropoff_lat/lng` bo'lsa, kuryer sahifasida "Yo'l ko'rsatish" aniq
   nuqtaga ochiladi (hozir manzil matni bo'yicha qidiradi).

## Sinovdan qolgan ma'lumot

- **Yetkazish #11** — #26 buyurtmada (sinov telefoni +998 90 928 55 96
  egasining buyurtmasi). Yetkazishni o'chirish endpointi yo'q. #26
  buyurtma holati `new` ga qaytarildi. #11 ni bazadan o'chirsangiz bo'ladi.
- **Kuryer #7** (`zz-kuryer`, store_user 218) — nofaol qilindi,
  o'chirib bo'lmadi (tarix saqlanadi). Kerak bo'lmasa bazadan o'chiring.
- #11 dan oldingi yetkazish id'lari (1–10) sizning sinovlaringiz
  bo'lsa, ularni ham tozalang.
- Sinov telefoniga "Buyurtmangiz yo'lda" SMS'i ketdi — bu biz kutgan narsa.

## Savol

№19.2 (sayt admini tokeni `users.is_admin` bazadan tekshirilishi),
№19.4 (ariza qarori bo'yicha SMS/email), №19.8 (OTP xeshlash) va
№20.1 (hujjatlar R2 da) tashqaridan tekshirib bo'lmaydi — qilingan
bo'lsa, qisqacha yozib qo'ying: hujjatlar qaysi bucket'da, OTP qanday
saqlanadi.
