# Backend va sayt topshirig'i №16 — sotuvchi o'zi ariza topshirishi

**Kimga:** Climavent backend va sayt dasturchisiga
**Sana:** 14.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

Hozir do'konni ham, uning loginini ham faqat superadmin adminkada qo'lda
yaratadi. Marketpleys ishga tushgach ishlab chiqaruvchi va distribyutorlar
**o'zi ariza topshirishi** kerak:

1. saytda forma to'ldiradi, hujjatlarini yuklaydi, ofertani qabul qiladi;
2. superadmin adminkada arizani tekshiradi;
3. tasdiqlasa — **nofaol** do'kon va kirish hisobi avtomatik ochiladi,
   sotuvchi parolini o'zi bir martalik havola orqali o'rnatadi;
4. sotuvchi profil va tovarlarni to'ldirgach, superadmin do'konni
   faollashtiradi (№14 dagi `is_active` — nofaol do'kon saytda ko'rinmaydi).

Darhol ochilib ketadigan ro'yxatdan o'tish **ataylab** qilinmayapti:
soxta do'kon va qalbaki tovarning oldini olish uchun har bir sotuvchi
tekshiriladi (Uzum ham 2–4 kun tekshiradi).

Huquqiy asos — `docs/huquqiy/01-sotuvchilar-uchun-oferta.docx`: 3-bo'lim
(shartnoma tuzish tartibi) va 2-ilova (ariza maydonlari va hujjatlar).
Hujjatlar hali huquqshunos tekshiruvida, lekin maydonlar tarkibi
o'zgarmaydi deb hisoblaymiz.

Hujjat uch qismdan iborat: **backend**, **sayt** va **adminka**. Adminka
qismi **tayyor** va shu topshiriqdagi API'ni kutib turibdi — endpoint
nomlari va javob shakli o'zgarsa, iltimos oldindan ayting.

---

## Qisqasi

| Qism | Nima kerak |
|---|---|
| Backend | `seller_applications` jadvali, holatlar va tarix |
| Backend | Hujjatlarni **yopiq** saqlash (pasport!) va qisqa muddatli havola |
| Backend | Oferta versiyalari va qabul qilinganining dalili |
| Backend | Ommaviy endpointlar (sayt) va superadmin endpointlari |
| Backend | Tasdiqlash — **bitta tranzaksiyada** do'kon + hisob + parol havolasi |
| Backend | Parolni bir martalik havola orqali o'rnatish |
| Backend | `stores` ga rekvizitlar (STIR, bank, huquqiy shakl) |
| Sayt | "Sotuvchi bo'lish" formasi, ariza holati sahifasi, oferta sahifalari |
| Adminka | Arizalar bo'limi, qaror, parol o'rnatish sahifasi — **tayyor** |

## Oqim

```
Sayt formasi ──POST──> [pending] ──────────────> [approved] → do'kon (nofaol)
                          │  ▲                                + store_user (parolsiz)
                          │  │ sotuvchi to'ldiradi            + parol o'rnatish tokeni
                          ▼  │
                      [needs_info]
                          │
                          └────────────────────> [rejected] → sabab sotuvchiga
```

`pending` va `needs_info` dan `approved` yoki `rejected` ga o'tish mumkin.
`approved` va `rejected` — **yakuniy** holat, ulardan chiqib bo'lmaydi
(qayta urinish uchun sotuvchi yangi ariza topshiradi).

---

# I. BACKEND

## 1. `seller_applications` jadvali

| Ustun | Turi | Izoh |
|---|---|---|
| `id` | serial | |
| `status` | text | `pending` / `needs_info` / `approved` / `rejected` |
| `legal_form` | text | `llc` (MChJ), `jsc` (AJ), `other_legal_entity`, `sole_proprietor` (YaTT) |
| `legal_name` | text | To'liq nomi, davlat ro'yxatidagi kabi |
| `tin` | text | STIR — 9 raqam. YaTT uchun JShShIR (14 raqam) ham qabul qilinsin — 3-savol |
| `registered_at` | date, NULL | Davlat ro'yxatidan o'tgan sana |
| `legal_address` | text | |
| `director_name` | text | Rahbar F.I.Sh. (YaTT da — tadbirkorning o'zi) |
| `director_position` | text, NULL | |
| `bank_name` | text | |
| `bank_account` | text | Hisob raqami — 20 raqam |
| `bank_mfo` | text | Bank kodi — 5 raqam |
| `vat_payer` | boolean | QQS to'lovchisimi |
| `vat_code` | text, NULL | QQS to'lovchisi kodi (`vat_payer = true` bo'lsa majburiy) |
| `contact_name` | text | Mas'ul shaxs — kabinet shu odamga ochiladi |
| `contact_phone` | text | `+998XXXXXXXXX` |
| `contact_email` | text | |
| `store_name` | text | Saytda ko'rinadigan do'kon nomi |
| `business_type` | text | `manufacturer`, `distributor`, `dealer`, `reseller` |
| `categories` | text | Tovar toifalari (erkin matn) |
| `brands` | text, NULL | |
| `warehouse_address` | text, NULL | Ombor yoki shourum |
| `delivery_regions` | text, NULL | Yetkazish va montaj hududlari |
| `comment` | text, NULL | Sotuvchining erkin izohi |
| `offer_version` | text | Qabul qilingan oferta versiyasi |
| `offer_accepted_at` | timestamptz | |
| `offer_ip` | text | |
| `offer_user_agent` | text | |
| `public_token` | text, UNIQUE | Tasodifiy 32 bayt — sotuvchining holat sahifasi uchun (5-band) |
| `info_request` | text, NULL | Superadmin so'ragan ma'lumot (oxirgisi) |
| `reject_reason` | text, NULL | |
| `admin_note` | text, NULL | Ichki izoh — **sotuvchiga hech qachon ko'rsatilmaydi** |
| `reviewed_by` | int, NULL | `store_users.id` — kim qaror chiqardi |
| `reviewed_at` | timestamptz, NULL | |
| `store_id` | int, NULL | Tasdiqlangach |
| `store_user_id` | int, NULL | Tasdiqlangach |
| `created_at`, `updated_at` | timestamptz | |

**Tarix — `seller_application_events`:** `id`, `application_id`, `type`
(`created`, `info_requested`, `resubmitted`, `approved`, `rejected`,
`note`, `documents_purged`), `actor_id` (NULL — sotuvchi yoki tizim),
`message`, `created_at`. Har bir holat o'zgarishi va izoh shu yerga
yoziladi. Nizo bo'lganda "kim, qachon, nima uchun" degan savolga javob
shu jadvaldan olinadi.

## 2. Hujjatlar — 🔴 YOPIQ saqlash

Ariza bilan **pasport nusxasi** keladi. U ochiq havola orqali hech qachon
ochilmasligi kerak.

- **Cloudinary emas**: u yerdagi rasm havolasi hammaga ochiq.
- Yopiq saqlash (masalan R2 da **private** bucket), faylga faqat server
  beradigan **imzolangan havola** orqali kiriladi, havola muddati
  **5 daqiqa** — 2-savol.
- Fayl nomi — tasodifiy kalit. Asl nom faqat bazada saqlanadi.

**`seller_application_documents`:** `id`, `application_id` (yuklash
paytida NULL), `type`, `file_key`, `original_name`, `mime`, `size`,
`created_at`, `deleted_at`.

**Turlar (`type`):** `registration_certificate` (davlat ro'yxatidan
o'tganlik guvohnomasi), `director_appointment` (rahbarni tayinlash
qarori), `passport` (pasport yoki ID-karta), `power_of_attorney`
(ishonchnoma), `dealer_authorization` (brend egasining ruxsati),
`certificate` (muvofiqlik sertifikati), `other`.

**Majburiy hujjatlar:**

| `legal_form` | Majburiy |
|---|---|
| `sole_proprietor` | `registration_certificate`, `passport` |
| boshqalari | `registration_certificate`, `director_appointment`, `passport` |

**Tekshiruv:** faqat PDF, JPG, PNG — turini **magic bytes** bo'yicha
aniqlang (`images/upload-image` dagi kabi); bitta fayl ≤ 10 MB; bitta
arizada ≤ 10 fayl.

**O'chirish:** ariza `approved` yoki `rejected` bo'lgandan **30 kun**
keyin `passport` turidagi fayllar saqlash joyidan o'chirilsin, yozuvda
`deleted_at` qo'yilsin va `documents_purged` hodisasi yozilsin (oferta,
2-ilova, 2.3-band). Qolgan hujjatlar saqlanadi.

## 3. Oferta versiyalari

**`offer_versions`:** `id`, `kind` (`seller`, `buyer`, `privacy`),
`version` (masalan `"1.0"`), `url` (saytdagi sahifa), `published_at`,
`effective_at`, `is_current`.

**`offer_acceptances`:** `id`, `kind`, `version`, `application_id`,
`store_id`, `store_user_id`, `user_id` (xaridor uchun, keyinroq),
`accepted_at`, `ip`, `user_agent`.

Ariza yaratilganda bitta `offer_acceptances` yozuvi qo'shilsin. Bu
shartnoma tuzilganining **dalili** (oferta, 3.6-band) — o'chirilmaydi va
tahrirlanmaydi.

Keyingi bosqich (🟢): oferta yangilanganda do'kon admini keyingi kirishda
yangi versiyani tasdiqlaydi — `store-auth/login` javobida
`offer_pending: { version, url }`, tasdiq `POST /api/offers/accept`.
Hozir shart emas.

## 4. Ommaviy endpointlar (sayt uchun, guvohnomasiz)

Hammasiga **rate limit**: bitta IP dan soatiga 5 ta ariza, 30 ta fayl — 4-savol.

### `GET /api/offers/current?kind=seller`

```json
{ "version": "1.0", "url": "https://climavent.uz/oferta/sotuvchi", "effective_at": "2026-10-01T00:00:00Z" }
```

### `POST /api/seller-applications/documents` — fayl yuklash

`multipart/form-data`: `file`, `type`. Javob:

```json
{ "id": 41, "type": "passport", "original_name": "pasport.pdf", "size": 348211 }
```

Yuklangan, lekin 24 soat ichida arizaga bog'lanmagan fayl o'chirilsin.
Nega alohida: katta faylni forma yuborilishidan oldin yuklab, progress
ko'rsatish va xato bo'lsa faqat o'sha faylni qayta yuborish mumkin.

### `POST /api/seller-applications` — ariza

```json
{
  "legal_form": "llc",
  "legal_name": "\"AIRCOOL TASHKENT\" MChJ",
  "tin": "305123456",
  "registered_at": "2019-04-12",
  "legal_address": "Toshkent sh., Yunusobod t., ...",
  "director_name": "Rahimov Botir",
  "director_position": "Direktor",
  "bank_name": "Kapitalbank",
  "bank_account": "20208000900123456001",
  "bank_mfo": "01088",
  "vat_payer": true,
  "vat_code": "326050012345",
  "contact_name": "Aliyeva Nodira",
  "contact_phone": "+998901234567",
  "contact_email": "sales@aircool.uz",
  "store_name": "Aircool",
  "business_type": "distributor",
  "categories": "Konditsionerlar, VRF tizimlari",
  "brands": "Midea, Gree",
  "warehouse_address": null,
  "delivery_regions": "Toshkent sh. va viloyati",
  "comment": null,
  "document_ids": [41, 42, 43],
  "offer_version": "1.0",
  "offer_accepted": true
}
```

Javob `201`:

```json
{ "id": 17, "status": "pending", "public_token": "b3f1…" }
```

**Tekshiruvlar:**

| Holat | Javob |
|---|---|
| Majburiy maydon yo'q, format noto'g'ri (STIR, hisob 20 raqam, MFO 5 raqam, telefon, email) | `400` |
| `offer_accepted !== true` | `400` |
| `offer_version` joriy versiya emas (sahifa eskirgan) | `409` |
| Majburiy hujjat yetishmaydi (2-band jadvali) | `400`, xabarda qaysi tur |
| Shu STIR bilan `pending`/`needs_info`/`approved` ariza bor | `409` |
| Shu STIR bilan do'kon bor (8-band) | `409` |
| `document_ids` begona yoki allaqachon boshqa arizaga bog'langan | `400` |

### `GET /api/seller-applications/status/:public_token`

Sotuvchining holat sahifasi uchun. **Faqat** quyidagilar qaytsin — bank,
pasport, ichki izoh qaytmasin:

```json
{
  "status": "needs_info",
  "store_name": "Aircool",
  "created_at": "2026-09-14T09:12:00Z",
  "info_request": "Direktorni tayinlash qarori yuklanmagan",
  "reject_reason": null,
  "missing_documents": ["director_appointment"]
}
```

### `PATCH /api/seller-applications/status/:public_token`

Faqat `status = needs_info` bo'lganda (aks holda `409`). Ariza
maydonlari (qismiy) va yangi `document_ids` qabul qilinadi. Natijada
holat `pending` ga qaytadi va `resubmitted` hodisasi yoziladi.

## 5. Superadmin endpointlari

**Guvohnoma:** servis kaliti yoki **superadmin** tokeni. `store_admin`
tokeni → `403`, guvohnomasiz → `401`. Arizalar do'kon adminiga **hech
qachon** ko'rinmasin: ular raqobatchining rekvizitlari va pasport
ma'lumotlari.

Superadmin tokeni bilan kelgan amalda `reviewed_by` va hodisaning
`actor_id` si shu hisobdan olinsin. Adminka qaror amallarini aynan
kirgan superadmin tokeni bilan yuboradi.

| Metod va yo'l | Tana | Javob |
|---|---|---|
| `GET /api/seller-applications/all?status=&page=&limit=` | — | Ro'yxat, `X-Total-Count` sarlavhasi bilan (№13 dagi kabi) |
| `GET /api/seller-applications/one/:id` | — | To'liq ariza + `documents` + `events` |
| `GET /api/seller-applications/:id/documents/:docId/url` | — | `{ "url": "...", "expires_at": "..." }` — 5 daqiqalik imzolangan havola |
| `POST /api/seller-applications/:id/approve` | `{ "login": "aircool", "slug": "aircool" }` | 6-band |
| `POST /api/seller-applications/:id/reject` | `{ "reason": "..." }` | Yangilangan ariza |
| `POST /api/seller-applications/:id/request-info` | `{ "message": "..." }` | Yangilangan ariza |
| `PATCH /api/seller-applications/update/:id` | `{ "admin_note": "..." }` | Yangilangan ariza |
| `POST /api/store-users/:id/password-setup` | — | `{ "password_setup_token": "...", "expires_at": "..." }` — 7-band |

`reason` va `message` — kamida 10 belgi. Ariza yakuniy holatda bo'lsa
`approve`, `reject`, `request-info` → `409`.

**Ariza obyekti** (`all` va `one` da). `all` ro'yxatida `documents` va
`events` o'rniga `documents_count` yetadi:

```json
{
  "id": 17,
  "status": "pending",
  "legal_form": "llc",
  "legal_name": "\"AIRCOOL TASHKENT\" MChJ",
  "tin": "305123456",
  "registered_at": "2019-04-12",
  "legal_address": "…",
  "director_name": "Rahimov Botir",
  "director_position": "Direktor",
  "bank_name": "Kapitalbank",
  "bank_account": "20208000900123456001",
  "bank_mfo": "01088",
  "vat_payer": true,
  "vat_code": "326050012345",
  "contact_name": "Aliyeva Nodira",
  "contact_phone": "+998901234567",
  "contact_email": "sales@aircool.uz",
  "store_name": "Aircool",
  "business_type": "distributor",
  "categories": "Konditsionerlar, VRF tizimlari",
  "brands": "Midea, Gree",
  "warehouse_address": null,
  "delivery_regions": "Toshkent sh. va viloyati",
  "comment": null,
  "offer_version": "1.0",
  "offer_accepted_at": "2026-09-14T09:12:00Z",
  "offer_ip": "84.54.1.2",
  "info_request": null,
  "reject_reason": null,
  "admin_note": null,
  "reviewed_by": null,
  "reviewed_at": null,
  "store_id": null,
  "store_user_id": null,
  "store_user_login": null,
  "documents_count": 3,
  "created_at": "2026-09-14T09:12:00Z",
  "updated_at": "2026-09-14T09:12:00Z",
  "documents": [
    { "id": 41, "type": "passport", "original_name": "pasport.pdf", "mime": "application/pdf", "size": 348211, "created_at": "…", "deleted_at": null }
  ],
  "events": [
    { "id": 1, "type": "created", "actor": null, "message": null, "created_at": "…" }
  ]
}
```

E'tibor bering: javobda `reviewed_by` va `events[].actor` — **login
matni** (ID emas), `public_token` va `offer_user_agent` esa **qaytmaydi**.

## 6. 🔴 Tasdiqlash — bitta tranzaksiyada

`POST /api/seller-applications/:id/approve` bitta tranzaksiyada:

1. `stores` ga yozuv: `name = store_name`, `slug` (tanadan, bo'lmasa
   nomdan yasalsin va unikal qilinsin), **`is_active = false`**,
   `phone`/`email` — mas'ul shaxsnikidan, rekvizitlar arizadan (8-band),
   `application_id`.
2. `store_users` ga yozuv: `role = store_admin`, `login` tanadan,
   `full_name = contact_name`, **parolsiz** (parol maydoni bo'sh — bu
   hisob bilan parol o'rnatilmaguncha kirib bo'lmaydi).
3. Parol o'rnatish tokeni (7-band).
4. Ariza: `status = approved`, `store_id`, `store_user_id`,
   `reviewed_by`, `reviewed_at`, `approved` hodisasi.

Biror qadam yiqilsa — **hammasi qaytariladi**. Aks holda do'koni bor-u
hisobi yo'q yoki ariza "kutilmoqda"-yu do'kon ochilgan holat qoladi.

Javob `201`:

```json
{
  "store": { "id": 12, "name": "Aircool", "slug": "aircool", "is_active": false },
  "store_user": { "id": 31, "login": "aircool" },
  "password_setup_token": "9c1e…",
  "password_setup_expires_at": "2026-09-17T09:30:00Z"
}
```

| Holat | Javob |
|---|---|
| Ariza yakuniy holatda | `409` |
| `login` band | `409`, xabar: login band |
| `slug` band | `409`, xabar: slug band |
| Shu STIR bilan do'kon allaqachon bor | `409` |

## 7. Parolni bir martalik havola orqali o'rnatish

Nega parolni superadmin o'ylab topib yubormaydi: parol **hech kimga**,
superadminga ham ko'rinmasligi, xat yoki Telegram'da ochiq yurmasligi
kerak.

**Token:** tasodifiy 32 bayt, bazada **xesh** holida saqlanadi, muddati
**72 soat**, **bir martalik**. Yangi token berilsa eskisi bekor bo'ladi.

### `POST /api/store-auth/set-password` (guvohnomasiz)

```json
{ "token": "9c1e…", "password": "••••••••" }
```

| Holat | Javob |
|---|---|
| Muvaffaqiyat | `200` `{ "login": "aircool" }` — token bekor bo'ladi |
| Token yo'q, ishlatilgan yoki muddati o'tgan | **`410`** |
| Parol 8 belgidan qisqa | `400` |

Rate limit: bitta IP dan daqiqasiga 10 urinish.

### `POST /api/store-users/:id/password-setup` (superadmin)

Sotuvchi havolani yo'qotsa yoki muddati o'tsa — yangi token. Mavjud
paroli bor hisob uchun ham ishlasin ("parolni unutdim" o'rniga).

**Havola manzili.** Parol o'rnatish sahifasi **adminkada**:
`https://<adminka>/parol-ornatish?token=…`. Backend SMS yoki email
yubormasa, havolani adminka o'zi yasaydi va superadmin sotuvchiga qo'lda
yuboradi — backendga adminka domeni kerak emas. SMS yoki email
yuboriladigan bo'lsa, domen uchun `ADMIN_URL` sozlamasi kerak — 1-savol.

## 8. `stores` ga rekvizitlar

Yangi ustunlar (hammasi NULL bo'lishi mumkin — eski do'konlarda yo'q):
`legal_form`, `legal_name`, `tin`, `legal_address`, `director_name`,
`bank_name`, `bank_account`, `bank_mfo`, `vat_payer`, `vat_code`,
`business_type`, `application_id`.

**Kim ko'radi:**

| Maydonlar | Mehmon (sayt) | O'z do'koni | Superadmin |
|---|---|---|---|
| `legal_name`, `tin` | ✅ | ✅ | ✅ |
| Bank, rahbar, QQS, `application_id` | ❌ | ✅ | ✅ |

Saytda sotuvchining yuridik nomi va STIR ko'rinishi elektron tijorat
qonuni talabi bo'lishi mumkin. Aniq ro'yxat huquqshunos javobidan keyin
tasdiqlanadi (`docs/huquqiy/02`, 3.1-band).

**Kim o'zgartiradi:** `legal_name`, `tin`, `legal_form` — faqat
superadmin. Do'kon admini bank rekvizitlarini o'zgartira oladi, lekin
buni hodisa sifatida yozib qo'yish yaxshi (to'lov firibgarligidan himoya).

`PATCH /api/stores/update/:id` qismiy yangilanishni qabul qilsin (№14
dagi DTO tuzog'i).

## 9. Xabarnomalar

Backendda SMS yoki email yuborish imkoni **bo'lsa** (1-savol):

| Hodisa | Kimga | Mazmuni |
|---|---|---|
| `created` | Sotuvchi | "Arizangiz qabul qilindi" + holat sahifasi havolasi |
| `info_requested` | Sotuvchi | So'ralgan ma'lumot + holat sahifasi havolasi |
| `approved` | Sotuvchi | Login + parol o'rnatish havolasi |
| `rejected` | Sotuvchi | Sabab |
| `created`, `resubmitted` | Superadminlar | "Yangi ariza" (ixtiyoriy, Telegram bot bo'lsa ham bo'ladi) |

Imkoni **bo'lmasa** — birinchi bosqichda bu band o'tkazib yuboriladi:
sotuvchi holatni saytdagi holat sahifasida ko'radi, parol havolasini
superadmin adminkadan nusxalab yuboradi. Adminka ikkala yo'lga ham tayyor.

---

# II. SAYT

## 10. "Sotuvchi bo'lish" sahifasi — `/sotuvchi-bolish`

- Tepada qisqa: kim ariza bera oladi (faqat MChJ, AJ, YaTT), qanday
  hujjatlar kerak, tekshiruv 5 ish kunigacha.
- Forma **bosqichlarga** bo'linsin (bitta uzun forma odamni qo'rqitadi):
  1. Kompaniya — huquqiy shakl, nomi, STIR, sana, manzil, rahbar
  2. Bank — bank, hisob raqami, MFO, QQS
  3. Aloqa va do'kon — mas'ul shaxs, do'kon nomi, faoliyat turi,
     toifalar, brendlar, hududlar
  4. Hujjatlar — **huquqiy shaklga qarab** majburiy ro'yxat o'zgaradi
     (I.2-band jadvali), har bir fayl alohida yuklanadi, progress bilan
  5. Oferta — oferta havolasi va **belgilanmagan** katak "Ofertani
     o'qidim va qabul qilaman". Katak oldindan belgilangan bo'lmasin —
     aks holda rozilik haqiqiy hisoblanmasligi mumkin.
- Mijoz tomonda ham backenddagi tekshiruvlar: STIR 9 (YaTT da 9 yoki 14)
  raqam, hisob 20 raqam, MFO 5 raqam, telefon `+998`.
- `409` (shu STIR bilan ariza bor) — tushunarli matn: "Bu STIR bilan
  ariza allaqachon topshirilgan".
- Muvaffaqiyatda — holat sahifasi havolasi va "havolani saqlab qo'ying"
  degan eslatma (SMS/email bo'lmasa sotuvchi holatni faqat shu havola
  orqali ko'radi).

## 11. Ariza holati sahifasi — `/sotuvchi-bolish/holat/:token`

- Holat: kutilmoqda, ma'lumot so'ralgan, tasdiqlangan, rad etilgan.
- `needs_info` da — so'ralgan ma'lumot matni, yetishmayotgan hujjatlar
  va to'ldirish formasi (`PATCH …/status/:token`).
- `approved` da — "Kirish ma'lumotlari sizga yuboriladi".
- `rejected` da — sabab.
- Sahifa **indekslanmasin** (`noindex`) va `Referrer-Policy: no-referrer`
  bo'lsin — manzilda token bor.

## 12. Huquqiy sahifalar

- `/oferta/sotuvchi`, `/foydalanish-shartlari`, `/maxfiylik` — versiya
  va sana bilan; footer'da havolalar.
- Xaridor ro'yxatdan o'tganda — **belgilanmagan** katak "Foydalanish
  shartlari va maxfiylik siyosatiga roziman", qabul `offer_acceptances`
  ga `user_id` bilan yozilsin (🟡).
- Menyu yoki footer'da "Sotuvchi bo'lish" havolasi.

---

# III. ADMINKA — tayyor

Quyidagilar allaqachon yozilgan va shu API'ni kutib turibdi. Endpoint
ishga tushguncha bo'limda "Backend hali tayyor emas" deb yoziladi.

1. **Arizalar** bo'limi (faqat superadmin) — ro'yxat, holat bo'yicha
   filtr, qidiruv, navbat (eng uzoq kutgan tepada), yon panelda
   kutilayotgan arizalar soni.
2. **Ariza sahifasi** — rekvizitlar, hujjatlar (5 daqiqalik havola faqat
   bosilganda so'raladi, sahifaga yozilmaydi), tarix, avtomatik
   tekshiruv: STIR, hisob raqami va MFO formati, majburiy hujjatlar,
   shu STIR bilan boshqa ariza yoki do'kon, do'kon nomi bandligi.
3. **Qaror** — tasdiqlash (login va slug bilan), ma'lumot so'rash, rad
   etish, ichki izoh. Tasdiqlangach parol o'rnatish havolasi nusxalash
   tugmasi bilan chiqadi. "Yangi kirish havolasi" tugmasi ham bor.
4. **`/parol-ornatish`** — sotuvchi parolini o'rnatadigan ommaviy sahifa.

---

## Savollar — javob kutaman

1. **SMS yoki email yuborish imkoniyati bormi** (Eskiz, SMTP va h.k.)?
   Yo'q bo'lsa, birinchi bosqichda 9-bandni o'tkazib yuboramiz.
2. **Yopiq fayl saqlash** — R2'da private bucket va imzolangan havola
   qila olasizmi? Pasportni Cloudinary'ga qo'ymaslik shart.
3. **YaTT identifikatori** — STIR (9) yoki JShShIR (14)? Ikkalasini
   qabul qilishni taklif qildim.
4. **Spam himoyasi** — rate limit yetadimi yoki captcha kerakmi?
5. **Qachon?** Adminka tayyor, sayt qismi backenddan keyin.

---

## Muhimlik tartibi

| № | Band | Muhimligi |
|---|---|---|
| 1 | Jadval va holatlar | 🔴 asos |
| 2 | Hujjatlarni yopiq saqlash | 🔴 **pasportsiz ishga tushirmaslik yaxshi** |
| 5 | Superadmin endpointlari | 🔴 adminka shunga tayanadi |
| 6 | Tasdiqlash tranzaksiyasi | 🔴 |
| 7 | Parol o'rnatish | 🔴 busiz tasdiqlangan sotuvchi kira olmaydi |
| 4 | Ommaviy endpointlar | 🔴 sayt shunga tayanadi |
| 3 | Oferta versiyalari va dalil | 🔴 huquqiy dalil |
| 10–11 | Sayt: forma va holat sahifasi | 🔴 |
| 8 | `stores` rekvizitlari | 🟡 |
| 12 | Huquqiy sahifalar | 🟡 ishga tushishdan oldin |
| 9 | Xabarnomalar | 🟢 imkon bo'lsa |

---

## Oldindan ogohlantirish (hozircha ish emas)

Huquqiy tekshiruvda bitta savol chiqdi: valyuta qonuni tovar narxini
chet el valyutasiga bog'lashni taqiqlaydi, bizda esa narx dollarda
saqlanib, kurs bo'yicha so'mga aylantiriladi. Huquqshunos javobini
kutyapmiz. Hozir **hech narsani o'zgartirmang** — kerak bo'lsa alohida
topshiriq yozaman. Faqat shuni bilib qo'ying: №15 dagi aksiya narxi ham
shunga bog'liq bo'lishi mumkin.
