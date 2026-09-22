# Backend topshirig'i №21 — parolni o'zi almashtirish, kirishlar jurnali, KP so'rovi

**Sana:** 16.09.2026 · №19 va №20 hali ochiq — ulardagi 🔴 bandlar (sharh
ruxsati, hujjatlarni R2 ga ko'chirish) muhimroq.

Kontekst: do'konlarga kabinet topshirilmoqda. Parolni sotuvchining o'zi
bilishi va o'zi almashtirishi kerak (oferta 4.10: kabinetdagi harakatlar
sotuvchi nomidan hisoblanadi). Hozir parolni faqat superadmin o'rnata oladi.

## 1. 🔴 Parolni o'zi almashtirish

```
POST /api/store-auth/change-password
Authorization: Bearer <do'kon yoki superadmin tokeni>
{ "current_password": "...", "new_password": "..." }
```

- Joriy parol bcrypt bilan tekshirilsin; noto'g'ri → **401**
  (`{"message":"Joriy parol noto'g'ri"}`).
- Yangi parol: kamida **8** belgi, joriysi bilan bir xil bo'lmasin → **400**.
- Muvaffaqiyatda `token_version` oshsin (boshqa qurilmalardagi sessiyalar
  bekor bo'ladi, №17) va **joriy sessiya uchun yangi token** qaytsin:
  `{ "token": "<yangi JWT>" }`. Aks holda parolni almashtirgan odamning
  o'zi ham darhol chiqarib yuboriladi.
- Cheklov: bitta hisobga **15 daqiqada 5 ta** noto'g'ri urinish → **429**.
- Jurnalga yozilsin (2-band, `event = "password_changed"`).

Adminkada "Sozlamalar → Parolni o'zgartirish" formasi tayyor — endpoint
chiqishi bilan ishlaydi (hozir "xizmat hali ishga tushmagan" deydi).

## 2. 🟡 Kirishlar jurnali

`store_user_logins`:

| maydon | |
|---|---|
| `id` | |
| `store_user_id` | `null` bo'lishi mumkin — mavjud bo'lmagan login bilan urinish |
| `login` | kiritilgan login (parol HECH QACHON yozilmaydi) |
| `event` | `login_success` · `login_failed` · `password_changed` · `password_set` (bir martalik havola orqali) · `logout` |
| `ip`, `user_agent` | `req.ip` (№17 dagi `trust proxy` sozlamasi bilan) |
| `created_at` | |

Endpointlar (yangidan eskiga, `?limit=` standart 20, maks 100):

```
GET /api/store-auth/logins            — o'z hisobining yozuvlari (do'kon admini)
GET /api/store-users/:id/logins       — superadmin, istalgan hisob
```

Javob: `[{ "event", "ip", "user_agent", "created_at" }]`.

Saqlash muddati — 12 oy (maxfiylik siyosatiga shunday yoziladi).

Adminkada: do'kon admini "Sozlamalar"da o'z so'nggi kirishlarini, superadmin
do'kon sahifasida har hisobning kirishlarini ko'radi. Endpoint yo'q paytda
bo'lim ko'rinmaydi.

## 3. 🟡 KP so'rovi — buyurtmadan ajratish

Saytda narxsiz va murakkab mahsulotlar uchun "Savatga" o'rniga **"KP so'rash"**
tugmasi qo'shiladi (sayt topshirig'i №3). Hozirgi holat: 23 buyurtmadan 22
tasining summasi 0 — ya'ni mijozlar allaqachon buyurtma orqali narx
so'rayapti, lekin buni oddiy buyurtmadan ajratib bo'lmaydi.

- `orders.kind`: `"order"` (standart, eski yozuvlar) | `"quote"`.
- `POST /api/orders/create` ixtiyoriy `kind` va `comment` (≤ 2000 belgi),
  `company_name` (≤ 255), `company_tin` (9 raqam, ixtiyoriy) qabul qilsin.
- `GET /api/orders/all` va `oneuser` javobida shu maydonlar qaytsin;
  `?kind=quote` filtri.
- Holatlar o'sha (`new` → … ), faqat `quote` uchun sotuvchi KP yuborganini
  belgilash maqsadida `quote_sent` holati qo'shilsin.

Adminkada buyurtmalar ro'yxatida "KP so'rovi" belgisi va alohida tab tayyor —
`kind` kelishi bilan ko'rinadi.

## Tekshirish

1. Noto'g'ri joriy parol → 401; to'g'ri → 200 va yangi token; eski token →
   401; yangi token → 200.
2. 6-noto'g'ri urinish → 429.
3. Muvaffaqiyatli va muvaffaqiyatsiz kirish jurnalda ko'rinadi, parol yozilmagan.
4. `kind: "quote"` bilan buyurtma → `GET /orders/all?kind=quote` da bor.
