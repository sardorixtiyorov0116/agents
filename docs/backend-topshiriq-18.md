# Backend topshirig'i №18 — hujjat versiyalari va rozilik dalili

**Sana:** 15.09.2026 · Qisqa. №17 hali ochiq (CORS, token bekor qilish) —
u muhimroq.

Oferta, foydalanish shartlari va maxfiylik siyosatining 1.0 versiyasi
e'lon qilindi (matn: `docs/huquqiy/`).

## 1. 🔴 Versiyalarni yozish (bir martalik ma'lumot)

Hozir `offers/current` faqat `seller` ni beradi, `buyer` va `privacy` — 404.

| kind | version | url | effective_at |
|---|---|---|---|
| `seller` | `1.0` (o'zgarmaydi) | `https://climavent.uz/oferta/sotuvchi` | `2026-09-15T00:00:00+05:00` |
| `buyer` | `1.0` | `https://climavent.uz/foydalanish-shartlari` | `2026-09-15T00:00:00+05:00` |
| `privacy` | `1.0` | `https://climavent.uz/maxfiylik` | `2026-09-15T00:00:00+05:00` |

`seller` uchun faqat `effective_at` yangilanadi (hozir `2026-09-14T07:24:53Z`,
matn esa 15.09 da e'lon qilindi). Versiya raqami o'zgarmasin — ochiq
formalar `1.0` bilan yuboradi.

**Tekshiruv:** `GET /api/offers/current?kind=buyer` va `?kind=privacy` → 200.

## 2. 🟡 Xaridor roziligi dalili

Saytda ro'yxatdan o'tish shakliga «Foydalanish shartlari va Maxfiylik
siyosatiga roziman» belgisi qo'shiladi (frontendga topshiriq berildi).
Sotuvchi arizasidagi kabi dalil saqlansin:

- `POST /api/users/register` (yoki yangi foydalanuvchi uchun `verify-otp`)
  ixtiyoriy `terms_version` va `privacy_version` qabul qilsin;
- ikkalasi berilsa — `offer_acceptances` ga `user_id` bilan ikki yozuv
  (`buyer`, `privacy`), `ip`, `user_agent`;
- versiya joriy emas → `409` (sotuvchi arizasidagi kabi).

Maydonlar berilmasa hozirgidek ishlasin — sayt yangilanguncha buzilmaydi.

## 3. 🟢 Sotuvchi arizasida maxfiylik roziligi

Formadagi belgi endi ofertani **va** maxfiylik siyosatini qamraydi. Ariza
yaratilganda `seller` bilan birga joriy `privacy` versiyasiga ham
`offer_acceptances` yozuvi qo'shilsin (yangi maydon shart emas).

## 4. Savol (maxfiylik siyosati 8.3-band uchun)

Sotuvchi parollari qanday saqlanadi (bcrypt / argon2)? Kirishlar jurnali
(`store_users.last_login_at` dan tashqari) yuritiladimi?
