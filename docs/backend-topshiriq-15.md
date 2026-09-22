# Backend va sayt topshirig'i №15 — aksiya narxi

**Kimga:** Climavent backend va sayt dasturchisiga
**Sana:** 11.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

Saytga **aksiya narxi** kerak: mahsulot kartasida qizil **"Aksiya"**
belgisi, eski narx chizilgan, yangi narx yonida. Hozir bunday imkoniyat
yo'q, ya'ni chegirmani faqat asosiy narxni o'zgartirib qilish mumkin.
Buning muammosi: aksiya tugagach, saytda arzon narx qolib ketadi va
eski narxni hech kim eslamaydi.

Aniq misol bor: 09.09.2026 dagi narx ro'yxatida **"АКЦИЯ (распродажа
скидка%)"** bo'limi bor. U yerda bazadagi 9 ta narsa uchun chegirma
narxi berilgan. Men ularni bazaga **yozmadim**, chunki narxni qo'yadigan
joy yo'q. Shu topshiriq bajarilgach, adminka ular uchun aksiya narxini
qo'yadi.

Hujjat uch qismdan iborat: **backend**, **sayt** va **adminka** (oxirgisi
meniki, siz uchun faqat ma'lumot). Oxirida savollar bor.

---

## Qisqasi

| Qism | Nima kerak |
|---|---|
| Backend | Narx turadigan ikki joyga aksiya narxi va tugash sanasi |
| Backend | Aksiya faolligini **server** hisoblaydi, sayt sanani tekshirmaydi |
| Backend | **Buyurtma aksiya narxi bilan hisoblanadi** (eng muhim band) |
| Backend | Saralash va filtr aksiya narxini hisobga oladi |
| Sayt | Kartada qizil "Aksiya" belgisi, eski narx chizilgan |
| Sayt | Mahsulot sahifasida variant bo'yicha aksiya narxi |
| Adminka | Aksiya narxini qo'yish, ro'yxatda belgi va filtr |

---

# I. BACKEND

## 1. Aksiya narxi qayerda turadi

Narx bazada **ikki joyda** turadi (dollarda):

- `product_model_inside.price` — SAP varianti narxi;
- `characteristics.price` — varianti yo'q modelning narxi.

Qoida (sayt shunday hisoblaydi): modelda variant bo'lsa narx
variantlardan olinadi, bo'lmasa modelning o'zidan.

Shuning uchun aksiya narxi ham **aynan shu ikki jadvalga** qo'shilsin —
mahsulotning o'ziga emas. Aks holda "qaysi variant aksiyada" degan
savolga javob bo'lmaydi: bitta mahsulotda 20 ta variant bo'lishi, faqat
bittasi chegirmada bo'lishi mumkin.

**Taklif — ikkala jadvalga uchta ustun:**

| Ustun | Turi | Ma'nosi |
|---|---|---|
| `sale_price` | DECIMAL, NULL | Aksiya narxi, **dollarda**. `NULL` — aksiya yo'q |
| `sale_starts_at` | TIMESTAMPTZ, NULL | Qachondan. `NULL` — darhol |
| `sale_ends_at` | TIMESTAMPTZ, NULL | Qachongacha. `NULL` — qo'lda olib tashlanguncha |

`sale_ends_at` — muammoning asosiy yechimi: aksiya o'z-o'zidan tugaydi va
asosiy narx tegilmagan holda qoladi.

**Muqobil variant** — alohida `promotions` jadvali (aksiya nomi,
sanalari, ichida variantlar ro'yxati). Afzalligi: "Qora juma" kabi
kampaniyani bitta tugma bilan yoqish/o'chirish. Kamchiligi: murakkabroq.
Hozirgi katalog uchun (177 mahsulot) oddiy ustunlar yetarli deb
o'ylayman, lekin qaror sizniki — 1-savolga qarang.

## 2. Tekshiruvlar (400 qaytarsin)

- `sale_price > 0`
- `sale_price < price` — aks holda bu aksiya emas. **Diqqat:** asosiy
  narxi yo'q (`NULL` yoki 0) variantga aksiya qo'yib bo'lmaydi — avval
  asosiy narx kerak.
- `sale_ends_at > sale_starts_at` (ikkalasi berilgan bo'lsa)
- `sale_ends_at` o'tib ketgan sana bo'lmasin (yangi aksiya qo'yilayotganda)

Aksiyani olib tashlash — `sale_price: null` yuborish.

## 3. Aksiya faolligini SERVER hisoblaydi

Faol aksiya — **hammasi** bajarilganda:

```
sale_price IS NOT NULL
AND sale_price < price
AND (sale_starts_at IS NULL OR sale_starts_at <= now())
AND (sale_ends_at   IS NULL OR sale_ends_at   >  now())
```

Sayt sanani **o'zi tekshirmasin**. Sabab: mijoz kompyuterining soati
noto'g'ri bo'lishi mumkin, vaqt zonasi xatosi oson chiqadi — natijada
bir mijozga aksiya ko'rinib, boshqasiga ko'rinmaydi. Server hisoblaydi,
sayt faqat natijani ko'rsatadi.

## 4. API javobi

### Mehmon (sayt) uchun

Variant va modelda:

| Maydon | Qiymat |
|---|---|
| `sale_price` | Aksiya **faol** bo'lsa — narx, aks holda `null` |
| `sale_ends_at` | Faol bo'lsa — tugash sanasi (saytda "3 kun qoldi" uchun), aks holda `null` |

Ya'ni tugagan yoki hali boshlanmagan aksiya mehmonga **umuman
ko'rinmaydi** — saytda qo'shimcha tekshiruv kerak emas.

Mahsulotda (hamma ro'yxat endpointlarida: `all`, `search`, `bysort`,
`lastadded`, `categoryslug`, `one`):

| Maydon | Ma'nosi |
|---|---|
| `on_sale` | Kamida bitta varianti faol aksiyada |
| `min_price` | Eng arzon **asosiy** narx (USD) |
| `min_sale_price` | Eng arzon **amaldagi** narx — aksiya hisobga olingan (USD), aksiya yo'q bo'lsa `null` |

Karta "Aksiya" belgisini `on_sale` ga qarab chiqaradi — 20 ta variantni
aylanib chiqish shart emas.

### Adminka (servis kaliti / do'kon tokeni) uchun

Xom qiymatlar — tugagan va rejalashtirilgan aksiya **ham**, ustiga
hisoblangan `sale_active: boolean`. Adminkada "aksiya tugagan",
"dushanbadan boshlanadi" degan holatlarni ko'rsatish uchun kerak.

## 5. 🔴 Buyurtma aksiya narxi bilan hisoblanishi SHART

№13 da `POST /order-items/create` narxni **server** hisoblaydigan
bo'ldi — juda to'g'ri qaror. Endi bu hisob **faol aksiya narxini**
ishlatsin:

```
amaldagi narx = faol aksiya bo'lsa sale_price, aks holda price
so'm          = round(amaldagi narx × buyurtma paytidagi kurs)
```

Bu eng muhim band. Aks holda kartada $103 ko'rinadi, buyurtmada esa $150
hisoblanadi — mijoz uchun eng yomon holat, va bu "narxni aldash" deb
qabul qilinadi.

"Faqat nom bo'yicha" (eski mijoz) yo'lida eng arzon variant tanlanadi —
u ham **amaldagi** narx bo'yicha eng arzoni bo'lsin.

**Taklif (ixtiyoriy):** `order_items` ga `regular_price` ustuni — qator
yozilgan paytdagi asosiy narx (so'mda). Shunda adminkada "aksiyada
qancha sotildi, qancha chegirma berildi" degan hisobot chiqarish mumkin
bo'ladi. Hozir buni keyinroq tiklab bo'lmaydi — asosiy narx o'zgarib
ketadi.

Savat: `cart_items.price` qo'shilgan paytdagi narx bo'lib qolaversin
(hozirgidek). Aksiya savat va buyurtma orasida tugasa, buyurtma baribir
serverda qayta hisoblanadi — to'g'ri narx yoziladi.

## 6. Saralash va filtr

- `POST /products/bysort` narx bo'yicha saralashda **amaldagi** narxni
  ishlatsin. Aks holda "arzondan qimmatga" ro'yxatida aksiyadagi mahsulot
  noto'g'ri joyda turadi.
- Yangi filtr: `on_sale=true` (masalan `GET /products/all?on_sale=true`
  yoki alohida endpoint) — saytda "Aksiya" bo'limi yoki sahifasi uchun.
- `allcount` filtr bilan mos sonni qaytarsin (№14 dagi kabi).

## 7. Yozish

`PATCH /characteristics/update/:id` va `PATCH /product-model-inside/:id`
uchala yangi maydonni qabul qilsin. Guvohnoma — hozirgi narx yozish
bilan bir xil (servis kaliti; do'kon tokeni faqat o'z mahsulotiga).

**Qismiy yangilanish ishlasin:** faqat `{ "sale_price": 103.12 }`
yuborish yetsin. №14 va №13 da `reviews`, `orders`, `order-items`
DTO'larida hamma maydon majburiy bo'lib qolgan xatoni topgan edingiz —
bu yerda ham shu tuzoq bo'lishi mumkin.

---

# II. SAYT

## 8. Mahsulot kartasi

**Belgi.** Kartaning tepasida, **"Yangi" belgisi turgan joyda va o'sha
uslubda** — faqat **qizil** rangda:

| Til | Matn |
|---|---|
| O'zbekcha | **Aksiya** |
| Ruscha | **Акция** |
| Inglizcha | **Sale** |

Belgi `on_sale === true` bo'lganda chiqadi.

**Ikkalasi ham bo'lsa** (yangi mahsulot aksiyada) — **ikkala belgi ham**
chiqsin, "Aksiya" birinchi. Bittasini yashirish ma'lumotni yo'qotadi.

**Narx.** `min_sale_price` bor va `min_price` dan kichik bo'lsa — ikki
qator:

| | Qiymat | Ko'rinishi |
|---|---|---|
| Eski narx | `min_price` | kulrang, **ustidan chizilgan** |
| Yangi narx | `min_sale_price` | **qizil, qalin** |

Masalan MF-315P uchun: eski narx chizilgan, yonida qizil
**1 237 440 so'm** ($103.12 × 12 000).

**Nozik holat:** kartada "…dan" narxi (eng arzon variant) ko'rsatiladi.
Agar aksiya **qimmat** variantda bo'lsa, eng arzon narx o'zgarmaydi —
bu holda chizilgan narx ko'rsatilmaydi, lekin **"Aksiya" belgisi baribir
chiqadi** (chunki mahsulotda aksiyadagi variant bor). Shuning uchun belgi
`on_sale` ga, chizilgan narx esa `min_sale_price < min_price` ga
bog'lansin — bular ikki xil shart.

**Ixtiyoriy:** narx yonida chegirma foizi, masalan **−30%**.

## 9. Mahsulot sahifasi

- Sarlavha yonida qizil "Aksiya" belgisi.
- Variant tanlovida har bir variantning o'z narxi: aksiyadagisi chizilgan
  eski narx + qizil yangi narx bilan.
- Tanlangan variant aksiyada bo'lsa — narx bloki kartadagidek.
- `sale_ends_at` bor bo'lsa — "Aksiya 15-sentyabrgacha" yoki "3 kun qoldi"
  (ixtiyoriy, lekin sotuvga yaxshi ta'sir qiladi).

## 10. Savat va buyurtma

- Savatda aksiya narxi ko'rinsin, eski narx chizilgan holda.
- Buyurtma summasi — serverdan (№13 dagidek). Agar mijoz savatga
  solgandan keyin aksiya tugagan bo'lsa, rasmiylashtirishda yangi narx
  chiqadi — shu holatda **ogohlantirish** ko'rsatilsa yaxshi: "Aksiya
  tugadi, narx yangilandi". Mijoz narx o'zgarganini jimgina bilib qolmasin.

## 11. "Aksiya" bo'limi (ixtiyoriy)

Menyuda yoki bosh sahifada "Aksiya" — `on_sale=true` filtri bilan.

---

# III. ADMINKA — men qilaman

Siz uchun faqat ma'lumot, backend tayyor bo'lgach bajaraman:

1. Model va variant tahririda **aksiya narxi**, boshlanish va tugash
   sanasi maydonlari; asosiy narxdan kichik ekani shu yerda ham
   tekshiriladi.
2. Mahsulotlar ro'yxatida qizil **"Aksiya"** nishoni va filtri;
   "aksiya tugagan", "rejalashtirilgan" holatlari.
3. **Ommaviy qo'yish** — bir nechta variantga bir vaqtda (narx ro'yxati
   yoki foiz bo'yicha).
4. 09.09.2026 narx ro'yxatidagi **АКЦИЯ bo'limini** import qilish.
5. Excel eksportga aksiya ustuni; hisobotlarda aksiyada sotilganlar
   (5-banddagi `regular_price` bo'lsa).

**Diqqat — 4-band uchun:** kutib turgan 9 ta narsaning ko'pida bazada
**asosiy narx yo'q** (MF ventilyatorlarda `price` bo'sh, JAN issiqlik
nasoslarining esa modeli ham yo'q). 2-banddagi `sale_price < price`
qoidasi to'g'ri — shuning uchun ular uchun avval asosiy narxni topish
kerak bo'ladi. Bu bizning ish, sizdan hech narsa talab qilmaydi.

---

## Savollar — javob kutaman

1. **Oddiy ustunlarmi yoki `promotions` jadvalimi?** Men ustunlarni
   taklif qildim (1-band). Kampaniya bo'yicha boshqarish kerak deb
   hisoblasangiz — ayting, adminkani o'shanga moslayman.

2. **Aksiya narxini do'kon admini o'zi qo'ya olsinmi?** Menimcha ha —
   narxni qo'ya olgani kabi, faqat o'z mahsulotiga. Yoki faqat superadmin?

3. **Chegirma foizi (−30%) kartada ko'rsatilsinmi?** Ixtiyoriy deb
   yozdim — sizning dizayningizga qanday mos kelishiga qarang.

4. **`regular_price` (5-band) qo'shiladimi?** Keyinroq qo'shsa ham
   bo'ladi, lekin undan oldingi aksiya savdolari uchun ma'lumot tiklanmaydi.

5. **Qachon?** Adminka qismini backend tayyor bo'lgan kuni boshlayman.

---

## Muhimlik tartibi

| № | Band | Muhimligi |
|---|---|---|
| 1–3 | Ustunlar, tekshiruv, faollikni server hisoblashi | 🔴 asos |
| 5 | Buyurtma aksiya narxi bilan | 🔴 **eng muhim** — busiz ishga tushirmaslik kerak |
| 4 | API javobida `on_sale`, `min_sale_price` | 🔴 sayt shunga tayanadi |
| 8–9 | Sayt: karta va mahsulot sahifasi | 🔴 |
| 7 | Yozish (qismiy DTO bilan) | 🔴 adminka shunga tayanadi |
| 6 | Saralash va filtr | 🟡 |
| 10 | Savatda ogohlantirish | 🟡 |
| 11 | "Aksiya" bo'limi | 🟢 ixtiyoriy |

**Iltimos:** 5-band bajarilmaguncha saytda aksiyani yoqmang. Kartada
bitta narx, buyurtmada boshqa narx chiqishidan ko'ra, aksiya umuman
bo'lmagani yaxshi.
