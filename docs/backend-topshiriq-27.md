# Backend topshirig'i №27 — dollar kursini avtomatik yangilash faqat yoqilganda

**Sana:** 17.09.2026 · kichik, lekin 🔴

## Muammo

№19 da kunlik cron qo'shildi va 17.09 da kursni **12 000 → 11 797,46** qildi —
saytdagi hamma so'm narxlari o'zgardi. Foydalanuvchi (egasi) kurs
**o'zidan-o'zi o'zgarmasligini** so'ragan edi: avtomatik yangilash faqat
adminkada galochka yoqilganda ishlashi kerak. Qo'lda o'zgartirish va
«Bank kursini qo'yish» tugmasi (`POST /settings/usd-rate/refresh`) avvalgidek qoladi.

## Kerak

```
GET   /api/settings/usd-rate/auto          — servis kaliti, superadmin
→ { "enabled": false, "updated_at": "…", "updated_by": "superadmin" }

PATCH /api/settings/usd-rate/auto          — superadmin (do'kon admini 403)
{ "enabled": true }
→ { "enabled": true, … }
```

- **Standart qiymat — `false`.** Migratsiya `settings` ga `usd_rate_auto = false` yozsin.
- **Cron** har ishga tushganda avval shu sozlamani o'qisin. `false` bo'lsa —
  hech narsa qilmasin (logga ham yozmasin, jim).
- Yoqish/o'chirish kurs tarixiga (`/usd-rate/history`) yozilsin:
  `source: "auto_toggle"`, `note: "avtomatik yangilash yoqildi"` / `"o'chirildi"`,
  `actor` — kim bosgani. Kurs qiymati o'zgarmaydi (`old_value = new_value`).
- `enabled: true` qilinganda darhol yangilash **shart emas** — keyingi cron
  kutiladi. Darhol kerak bo'lsa adminkada «Bank kursini qo'yish» tugmasi bor.

## Adminka (tayyor)

Sozlamalar → «USD kursi» kartasida galochka «Kursni har kuni avtomatik
yangilash». Endpoint yo'q paytda galochka o'chirib qo'yilgan va «hozir kurs
har kuni avtomatik yangilanmoqda» ogohlantirishi turadi — endpoint chiqishi
bilan o'zi ishlaydi.

## Tekshirish

1. Migratsiyadan keyin `GET …/auto` → `enabled: false`; cron ishlagach kurs o'zgarmagan.
2. `PATCH { enabled: true }` → keyingi cron kursni yangilaydi; tarixda ikki yozuv (yoqildi, kurs).
3. Do'kon admini `PATCH` → 403.
