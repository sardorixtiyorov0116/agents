# Sayt topshirig'i №3 — "KP so'rash" va savatdan KP

**Sana:** 16.09.2026

## Nega

- 177 mahsulotdan 126 tasida narx yo'q.
- 23 buyurtmadan 22 tasining summasi **0** — mijozlar narxsiz mahsulotni
  "sotib olib", aslida narx so'rayapti.
- Xaridorlarning katta qismi kompaniyalar: ular to'lashdan oldin KP va QQS
  bilan hisob-faktura olib, rahbariyatdan tasdiqlatadi.
- To'lov saytda emas, sotuvchiga bevosita (foydalanish shartlari 6-bo'lim).

Ya'ni "Buyurtma berish" ko'p mahsulot uchun noto'g'ri va'da beradi.

## 1. "KP so'rash" tugmasi

**Qachon chiqadi:** mahsulotning narxi yo'q bo'lsa (`min_price` bo'sh yoki 0).
Mahsulot ro'yxatida va mahsulot sahifasida "Savatga" o'rniga.

**Oyna (modal):**

| maydon | |
|---|---|
| Ism | majburiy, hisobdan to'ldiriladi |
| Telefon | majburiy, hisobdan to'ldiriladi |
| Kompaniya nomi | ixtiyoriy |
| STIR | ixtiyoriy, 9 raqam |
| Model | mahsulotning modellaridan tanlanadi |
| Soni | standart 1 |
| Izoh | ixtiyoriy: "montaj bilan", "Toshkentga yetkazish" |

Kirmagan foydalanuvchi — avval SMS-kod bilan kirish (rozilik belgisi bilan,
№18 oqimi), keyin oyna ochiladi.

**Yuborish:** `POST /api/orders/create` + `kind: "quote"` va yuqoridagi
maydonlar (backend №21, 3-band). Backend tayyor bo'lguncha `kind` siz
yuboring — buyurtma sifatida tushadi, hozirgi kabi.

**Tasdiq:** "So'rov yuborildi. Sotuvchi ish kunlari 24 soat ichida
bog'lanib, KP yuboradi." + "Buyurtmalarim" havolasi. `/payment` sahifasiga
YUBORILMASIN.

Profilda KP so'rovlari "KP so'rovi" belgisi bilan ko'rinsin.

## 2. Savatdan KP yuklab olish

Savat sahifasida **"KP yuklab olish (PDF)"** tugmasi.

- Alohida chop etish sahifasi (`/cart/kp`) va brauzerning "PDF saqlash"i
  (`window.print()`) yetarli — PDF kutubxonasi shart emas.
- Savatda bir nechta do'kon mahsuloti bo'lsa — **har do'kon uchun alohida
  KP** (sahifada ketma-ket, har biri yangi varaqdan):
  - sotuvchi: `legal_name`, STIR, manzil, telefon, email
    (`GET /api/stores/slug/{slug}`);
  - KP raqami va sanasi, **amal qilish muddati: 10 kun**;
  - jadval: №, mahsulot, model, soni, narxi (so'm), summasi;
  - jami summa;
  - izoh: «Narxlar sanadagi kurs bo'yicha hisoblangan. Yakuniy narx va
    yetkazib berish shartlari sotuvchi tasdiqlagandan keyin belgilanadi.
    Ushbu hujjat ommaviy oferta emas.»
- Narxsiz qatorlar: narx o'rniga «so'rov bo'yicha», jami summaga qo'shilmaydi.
- Chop etishda sarlavha, footer, cookie paneli yashirinsin.

## 3. Tekshirish

1. Narxsiz mahsulotda "Savatga" yo'q, "KP so'rash" bor; narxlisida — aksincha.
2. KP so'rovi adminkada buyurtmalar ro'yxatida chiqadi (backend №21 dan
   keyin "KP so'rovi" belgisi bilan).
3. Ikki do'kondan mahsulotli savatdan KP — ikkita alohida varaq, har birida
   o'z sotuvchisining rekvizitlari.
4. Telefonda KP sahifasi o'qiladi va PDF qilib saqlanadi.
