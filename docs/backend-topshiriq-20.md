# Backend topshirig'i №20 — hujjatlar saqlash joyi va majburiy tasdiqlash

**Sana:** 16.09.2026 · №19 bilan birga keldi, lekin alohida: bular boshqa
mavzu va 1-band shoshilinch.

## 1. 🔴 Sotuvchi hujjatlari qayerda saqlanmoqda?

№16 da shunday so'ralgan edi: «Yopiq saqlash (masalan R2 da **private**
bucket), faylga faqat server imzolagan havola orqali kirish».

Bizga hujjatlar **Railway ichida** saqlanayotgani aytildi. Agar shunday
bo'lsa, ikkita jiddiy muammo bor:

- **Railway diski vaqtinchalik.** Har deploy va qayta ishga tushishda
  konteyner fayl tizimi yangilanadi — sotuvchi yuklagan guvohnoma va
  pasport nusxasi yo'qoladi. Bu hujjatlar shartnoma dalili (oferta,
  2-ilova) va tekshiruv asosi.
- **Zaxira yo'q.** Bazani tiklash hujjatlarni tiklamaydi.

**So'rov:** hujjatlar Cloudflare R2 da **private** bucket'da saqlansin.
Biz allaqachon R2 ishlatamiz (`r2-upload`, `r2-content`, mahsulot
tavsiflari), ya'ni hisob va kalitlar bor — mahsulot tavsiflaridan farqi
shundaki, bu bucket ochiq bo'lmasligi kerak.

- fayl kaliti taxmin qilib bo'lmaydigan bo'lsin (UUID);
- `GET /seller-applications/documents/file` avvalgidek 5 daqiqalik
  imzolangan havola bersin, faylning o'zi ochiq URL'da turmasin;
- pasportni qarordan 30 kun keyin o'chirish (№16) R2 da ham ishlasin;
- hozir bazada ariza 0 ta — ya'ni **ko'chiriladigan eski fayl yo'q**,
  almashtirish uchun eng qulay payt.

**Javobda ayting:** hozir qayerda saqlanadi (Railway diski, Postgres
ichida, R2?) va o'zgartirgandan keyin qaysi bucket ishlatildi.

> Bugun sinov uchun bitta fayl yukladim: `id 101`,
> `registration_certificate`, `zz-sinov.pdf` (69 bayt), arizaga
> bog'lanmagan. №16 bo'yicha 24 soatda o'zi o'chishi kerak — shuni ham
> tasdiqlab qo'ying, o'chmasa qo'lda o'chiring.

## 2. 🔴 Ofertani majburiy tasdiqlatish

Hozir oferta bir marta — ariza topshirishda yoki ro'yxatdan o'tishda —
qabul qilinadi. Versiya yangilansa, eski foydalanuvchi yangi shartlarni
ko'rmaydi ham, tasdiqlamaydi ham. Oferta 12.3-band esa aynan shuni
talab qiladi: «Sotuvchi kabinetiga keyingi kirishda yangi versiyani
tasdiqlash so'raladi».

**Sotuvchi kabineti** (№16 da 🟢 deb qoldirilgan edi, endi kerak):

- `POST /store-auth/login` javobida `offer_pending: { kind, version, url }`
  — hisob qabul qilgan versiya joriysidan eski bo'lsa;
- `POST /offers/accept` — `{ kind, version }`, `offer_acceptances` ga
  yozuv (`store_user_id`, `ip`, `user_agent`);
- tasdiqlanmaguncha **yozish** amallari rad etilsin (409, masalan
  `offer_acceptance_required`), o'qish ishlayversin. Aks holda sotuvchi
  oynani yopib, ishini davom ettiraveradi.

**Xaridor:**

- `POST /users/login` va `verify-otp` da hozir yangi raqam uchun rozilik
  so'raladi (№18) — shu mexanizm **mavjud foydalanuvchiga** ham ishlasin:
  qabul qilgan versiyasi eski bo'lsa `consent_required: true` qaytsin;
- tasdiq `verify-otp` dagi `terms_version` / `privacy_version` bilan yoki
  alohida `offers/accept` bilan.

Adminka va saytdagi oynani biz qilamiz — bizga faqat shu ikkita signal va
tasdiq endpointi kerak.

## 3. 🟡 Kurs — aniqlashtirish (№19, 3-band)

Adminkaga «Bank kursini qo'yish» tugmasi qo'shildi: superadmin bir bosishda
cbu.uz dagi kursni qo'yadi. Ya'ni sizdan **qo'lda yangilash** emas, **kunlik
avtomatik** yangilash kerak (cron) — tugma faqat zaxira va shoshilinch
holat uchun.
