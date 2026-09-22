# Umumiy tekshiruv — 16.09.2026

Jonli o'lchangan (prod backend + climavent.uz + adminka). Taxmin yo'q.

## 1. Ishlayotgani (qayta tekshirildi)

- №17/№18: CORS, token bekor qilish (nofaol/parol/o'chirilgan → 401), uchala
  oferta versiyasi, chegirma formulasi, sinov ma'lumotlari tozalangan.
- Rozilik oqimi: `+998909285596` (mavjud hisob, id 16) → SMS → eskirgan
  versiya bilan 409 (kod sarflanmadi) → to'g'ri versiya bilan 201.
- Sayt: oferta 18 bo'lim, shartlar 14, maxfiylik 11; cookie paneli, GA faqat
  rozilikdan keyin; `/privacy`,`/terms`,`/sell` yo'naltiriladi; `/seller` →
  adminka; `/payment` da karta maydoni yo'q; 404 sahifa ishlaydi.

## 2. Muammolar

### 🔴 Katalog narxsiz — 137 mahsulotdan 31 tasida narx bor
106 tasi saytda «narxi so'rov bo'yicha». Butun kategoriyalar bo'sh:
Qo'shimcha jihozlar 0/11, Issiqlik almashish 0/9, Maxsus ventilyatorlar 0/8,
Tom/Chang/Aspiratsiya 0/4 va h.k. Marketpleysning asosiy vazifasi narx
ko'rsatish — bu holatda sayt katalogdan nariga o'tmaydi.

### 🔴 Buyurtma holatlari yuritilmayapti
23 buyurtma: 17 tasi «yetkazilmoqda», 5 tasi «yangi», 1 tasi «bajarildi».
Oxirgi buyurtma 30.08. Ya'ni holatlarni hech kim yangilamayapti.

### 🔴 Do'konlarda yuridik nom va STIR yo'q
To'rtala do'konda ham `legal_name` va `tin` bo'sh. Sayt kodi tayyor, lekin
ko'rsatadigan ma'lumot yo'q. Elektron tijorat qonuni sotuvchini aniqlash
ma'lumotini talab qiladi (shartlar 3.1).

### 🔴 Huquqshunos tekshiruvi
Hujjatlar saytda amal qilyapti, lekin yurist ko'rmagan. 00-izohdagi 15 savol
ochiq; eng xavflilari: narx dollarga bog'langani, ma'lumotlar xorijiy
serverlarda, montajli uskunani 10 kunda qaytarish.

### 🔴 Sharhni boshqa do'kon admini tahrirlay oladi (16.09 da topildi)
`PATCH /api/reviews/update/:id` do'kon bo'yicha cheklanmagan: 1-do'kon
admini 2-do'konning mahsulotidagi sharhni yashira oldi (200). Raqobatchi
salbiy sharhni o'chirib qo'yishi mumkin. Backend №19 ga kiritildi.

### 🟡 44 ta model tavsifi bo'sh
45 ta mahsulotdan tekshirilgan 140 ta modeldan 44 tasining tavsif fayli
bo'sh (9 bayt), 1 tasida buzuq havola (#2 JVO-080S, `content="."`).
Saytda «Characteristic» bo'limi bo'm-bo'sh chiqadi.

### 🟡 Sitemapda mahsulotlar yo'q
`sitemap.xml` da 14 ta statik sahifa. Mahsulot, kategoriya va do'kon
sahifalari yo'q — Google katalogni indekslamaydi.

### 🟡 Kurs eskirgan
`usd-rate` = 12 000, oxirgi yangilanish 02.09 (2 hafta). Narxlar dollarda
saqlangani uchun har bir eskirgan kun — noto'g'ri so'm narxi.

### 🟡 Sayt admini tokeni bekor qilinmaydi
Backend o'zi aytdi: `users.is_admin` / `AdminGuard` faqat imzoni tekshiradi.
Do'kon hisoblarida tuzatildi, sayt adminlarida yo'q.

### 🟡 OTP kodi bazada ochiq saqlanadi
Backend aytdi (5 daqiqa, urinish cheklangan). Maxfiylik siyosatida SMS-kodni
alohida aytish kerak (8.3-band).

### ✅ Do'kon admini o'z rekvizitlarini tahrirlay olmaydi — QILINDI
Adminkada `/dokonim` sahifasi qo'shildi (16.09): sotuvchi logotip, tavsif,
aloqa va bank rekvizitlarini o'zi yangilaydi. Yuridik ma'lumotlar (nom,
shakl, STIR, manzil, rahbar, faoliyat) qulflangan — backend ularni do'kon
adminidan qabul qilmaydi, ular arizada tasdiqlangan holicha qoladi.

### 🟡 Ariza tasdiqlanganda sotuvchiga avtomatik xabar ketmaydi
Superadmin parol havolasini qo'lda yuboradi. Oferta 3.4 «Operator xabar
yuboradi» deydi.

### 🟢 Mayda
- `armavent`, `vents-us` do'konlari nofaol, lekin hisoblari ochiq.
- Bannerlarda havola yo'q, `is_active` maydoni umuman yo'q.
- Saytda `html lang="en-US"` — sahifa tili bilan mos emas.
- Huquqiy hujjatlar faqat o'zbekcha; ru/en tarjimasi yo'q.

### ✅ Adminka sessiyasi backendda tekshirilmasdi — TUZATILDI
16.09 da o'lchandi: hisob o'chirilgandan keyin ham uning cookie'si bilan
panel ochilaverdi (adminka ko'p ma'lumotni servis kaliti bilan o'qiydi).
Endi har 60 soniyada `store-auth/me` bilan tekshiriladi; hisob nofaol
qilinsa sessiya bir daqiqada tugaydi (sinaldi). Backend javob bermasa
sessiya buzilmaydi.

### Tuzatilgan tushunmovchiliklar
Adminkada narxsiz / rasmsiz / tavsifsiz filtrlari va sharhlarni yashirish
allaqachon bor edi. Aksiya hisoboti 16.09 da qo'shildi (savdo eksportida
aksiyasiz narx, chegirma foizi, tejalgan summa). Nofaol armavent va
vents-us do'konlarida 40 ta mahsulot bor — ular mehmonga ko'rinmaydi, bu
to'g'ri xatti-harakat.

## 3. Nima dasturlash kerak, nima yo'q

**Dasturlash kerak (kod):**
| Ish | Kim |
|---|---|
| Sayt admini tokenini bekor qilish | backend |
| Kursni avtomatik yangilash (markaziy bank) | backend |
| Ariza tasdiqlanganda SMS yoki email | backend |
| Sitemapga mahsulot/kategoriya/do'kon | sayt |
| `html lang` tilga mos bo'lishi | sayt |
| Banner havolasi va faollik | sayt + backend |
| Bo'sh tavsif va narxsiz mahsulotlar ro'yxati | adminka |
| Sharh ruxsatini do'kon bo'yicha cheklash | backend |

**Dasturlash kerak emas (ma'lumot va ish jarayoni):**
narxlarni kiritish · buyurtma holatlarini yuritish · STIR va rekvizitlarni
kiritish · bo'sh tavsiflarni to'ldirish · nofaol do'konlar bo'yicha qaror ·
huquqshunos tekshiruvi · Vercel'dagi eski `ADMIN_HISOBLAR`/`DOKONLAR_JSON`
ni o'chirish.

## 4. Tartib

1. Narxlar va buyurtma holatlari — ularsiz sayt savdo qilmaydi.
2. STIR/rekvizitlar + huquqshunos.
3. Sayt admini tokeni, kurs avtomatikasi, tasdiq xabari.
4. Sitemap, bo'sh tavsiflar, hisobotlar.
