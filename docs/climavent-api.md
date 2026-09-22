# Climavent backend API

Kompaniyaning o'z tizimi — agentlar uchun **birlamchi manba**. Tashqi veb
faqat bu yerda topilmagan narsa uchun ishlatiladi.

| | |
|---|---|
| **Asos manzil** | `https://climavent-back-production.up.railway.app` |
| **OpenAPI (JSON)** | `/api/docs-json` |
| **OpenAPI (YAML)** | `/api/docs-yaml` |
| **Swagger UI** | `/api/docs` (JS bilan chiziladi — skript uchun `docs-json` ishlating) |
| **Admin panel** | `https://climavent-admin.vercel.app/` |
| **Nomi / versiya** | Climavent backend 1.0.1 (NestJS) |

## Autentifikatsiya

**O'qish uchun token KERAK EMAS** — mahsulot, kategoriya, model va
xususiyatlar endpointlari ochiq. Bu tekshirildi.

`security` belgisi faqat quyidagilarda bor:

- `/api/orders/*` — barcha amallar (buyurtmalar)
- `POST /api/products/create`, `PATCH /api/products/update/{id}`,
  `DELETE /api/products/delete/{id}` — mahsulot o'zgartirish (admin)

Agentlar **faqat o'qiydi**, shuning uchun token hozircha talab qilinmaydi.
Kerak bo'lganda `.env` dagi `CLIMAVENT_TOKEN` ishlatiladi (kodda emas) —
klient uni `Authorization: Bearer …` sifatida yuboradi.

> **Diqqat:** buyurtmalar (`/api/orders/*`) token talab qiladi va Doston
> ularga token bo'lmasa murojaat qila olmaydi. Bu normal holat — agent
> "manba mavjud emas" deydi, to'qib chiqarmaydi.

---

## Agentlar ishlatadigan endpointlar

### Mahsulotlar

| Metod | Yo'l | Beradi |
|---|---|---|
| `GET` | `/api/products/all` | Barcha mahsulotlar (hozir **137 ta**), to'liq obyekt bilan |
| `GET` | `/api/products/allcount` | Mahsulotlar soni (oddiy raqam) |
| `GET` | `/api/products/one/{id}` | Bitta mahsulot |
| `POST` | `/api/products/search` | Matn bo'yicha qidiruv |
| `POST` | `/api/products/categoryslug` | Kategoriya bo'yicha, sahifalab |
| `POST` | `/api/products/bysort` | Saralangan ro'yxat, sahifalab |
| `POST` | `/api/products/lastadded` | Oxirgi qo'shilganlar |

**Qidiruv tanasi:** `{"text": "ventilyator"}` → mahsulotlar ro'yxati
(JSON massiv). Javob kodi `201` (NestJS POST uchun standart).

**Kategoriya/sort tanasi:** `{"price": "asc", "limit": 20, "page": 1,
"category_id": 13}` — to'rttasi ham majburiy.

### Mahsulot obyekti

Muhim maydonlar:

```
id, name_uz, name_ru, name_en
description_short_uz / _ru / _en
price            — narx (pastdagi ogohlantirishga qarang)
quantity         — ombordagi soni
producer         — "JIHOZVENT" / "Jihozvent" / "Climavent"
category_id, category { id, name_uz, name_ru, name_en }
models[]         — { id, name, price } model variantlari
characters[]     — { id, title, price, content } texnik xususiyatlar
images[]         — rasm havolalari
sizes, opisaniya, naznacheniya, markirovka — R2 fayl havolalari
    (`…Json` variantlari — o'sha ma'lumotning JSON ko'rinishi)
views, sold_count, reviews[]
```

> ### ⚠️ Narxlar hozircha bo'sh
> `137` mahsulotning **136 tasida `price = 0`**. Ya'ni ichki tizimda narx
> ma'lumoti to'ldirilmagan. Bu ochiq holat:
> - Zara (`price-monitor`) "ichki narx ma'lumoti mavjud emas" deb aytadi;
> - tashqi bozor narxi topilsa, u **tashqi manba** deb belgilanadi va
>   kompaniyaning o'z narxi sifatida ko'rsatilmaydi.

### Kategoriyalar

| Metod | Yo'l | Beradi |
|---|---|---|
| `GET` | `/api/category/all` | Barcha kategoriyalar (**35 ta**) |
| `GET` | `/api/category/one/{id}` | Bitta kategoriya |
| `POST` | `/api/category/slug` | Kategoriyadagi mahsulotlar |

Kategoriya obyekti: `id, name_uz, name_ru, name_en, category_id`
(`category_id` — ota kategoriya, ya'ni ierarxiya bor).

### Model va xususiyatlar (Sardor uchun muhim)

| Metod | Yo'l | Beradi |
|---|---|---|
| `GET` | `/api/product-models/oneproductid/{id}` | Mahsulotning model variantlari |
| `GET` | `/api/product-models/one/{id}` | Bitta model |
| `GET` | `/api/product-model-infos/all` | Model bo'yicha qo'shimcha ma'lumot |
| `GET` | `/api/characteristics/one/{id}` | Bitta texnik xususiyat |

Odatda `GET /api/products/one/{id}` javobida `models[]` va `characters[]`
allaqachon keladi — alohida so'rov shart emas.

### Boshqa resurslar (hozircha agentlarda ishlatilmaydi)

`banners`, `cart`, `cart-items`, `likes`, `reviews`, `rishotkalar`,
`selected-to-checkout`, `users`, `r2` (fayl saqlash),
`order-items`, `orders` (token talab qiladi).

---

## Amaliy eslatmalar

- **Javob kodi:** `GET` uchun `200`, `POST` uchun `201`.
- **Sahifalash:** `limit` + `page` majburiy bo'lgan joyda ikkalasini ham
  yuborish kerak, aks holda `400`.
- **Til:** matn maydonlari uch tilda (`_uz`, `_ru`, `_en`). Agentlar
  standart holda `uz` ni oladi, bo'sh bo'lsa `ru` → `en` ga tushadi.
- **`producer` maydoni** turlicha yozilgan (`JIHOZVENT`, `Jihozvent`,
  `Climavent`) — solishtirishda registr hisobga olinmaydi.
- **API ishlamasa:** agent "ichki manba mavjud emas" deydi va shuni
  `izoh`ga yozadi. To'qib chiqarish yo'q.

## Qayta tekshirish

Sxema o'zgarganda:

```bash
curl -s https://climavent-back-production.up.railway.app/api/docs-json | python -m json.tool | head -40
```

---

## Yozish (katalog administratori Nodira)

Yozish `integrations/climavent_yozuvchi.py` orqali boradi. O'qish klienti
(`ClimaventKlient`) da yozish metodi **umuman yo'q** — shuning uchun boshqa
agentlar katalogni o'zgartira olmaydi.

### Ruxsat etilgan amallar (boshqasi yo'q)

| Amal | Metod | Yo'l |
|---|---|---|
| `mahsulot_yarat` | POST + PATCH | `/api/products/create`, so'ng `/api/products/update/{id}` |
| `mahsulot_yangila` | PATCH | `/api/products/update/{id}` |
| `mahsulot_ochir` | DELETE | `/api/products/delete/{id}` |
| `xususiyat_yarat` | POST | `/api/characteristics/create` |
| `xususiyat_yangila` | PATCH | `/api/characteristics/update/{id}` |
| `xususiyat_ochir` | DELETE | `/api/characteristics/delete/{id}` |
| `ichki_yarat` | POST | `/api/product-model-inside` |
| `ichki_yangila` | PATCH | `/api/product-model-inside/{id}` |
| `ichki_ochir` | DELETE | `/api/product-model-inside/{id}` |

`mahsulot_yarat` **ikki bosqichli**: `CreateProductDto` da atigi 10 maydon
bor, `sizes`/`opisaniya`/`naznacheniya`/`markirovka` (va `Json` juftlari)
qabul qilinmaydi. Shuning uchun avval POST, so'ng qolgan maydonlar yangi
`id` ga PATCH bilan qo'yiladi.

> **`model_*` amallari olib tashlandi** (2026-09-09). Ular
> `/api/product-models/*` ga qarardi, backendda esa bunday yo'l **yo'q** —
> Swagger (`/api/docs-json`) bilan tekshirilgan, har chaqiruv 404 berardi.
> Bu katalogda "model" aslida `characteristics`, ya'ni `xususiyat_*`.

Hammasi guvohnoma talab qiladi (2026-07-30 dan beri).

### Rasm — amal jadvalida ATAYLAB yo'q

Rasm zanjiri boshqacha, chunki **model surat yarata olmaydi**. U faqat
havola yozishi mumkin, havolani esa o'ylab topib qo'yadi — natijada
katalogga ishlamaydigan yoki begona surat biriktirilardi. Shuning uchun
zanjir teskari qurilgan:

```
rasm mazmuni ODAMDAN
  → POST /api/images/upload-image   (multipart, Cloudinary)  → HAVOLA
  → POST /api/product-images/create  {image_link, product_id}
```

Havola **hech qachon modeldan kelmaydi** — u backend javobidan olinadi.

| Metod | Nima qiladi |
|---|---|
| `ClimaventYozuvchi.rasm_yukla(bayt, nom)` | Cloudinary'ga yuklaydi, havola qaytaradi |
| `.rasmni_biriktir(mahsulot_id, havola)` | havolani mahsulotga bog'laydi |
| `.rasm_qoy(mahsulot_id, bayt, nom)` | ikkalasi bitta chaqiruvda |
| `.rasmni_ochir(rasm_id)` | rasm yozuvini o'chiradi (Cloudinary faylini emas) |

Yuklash **yagona multipart** so'rov, shuning uchun umumiy `_sorov` dan
o'tmaydi: `Content-Type` ni kutubxona o'zi qo'yishi kerak. Shu sababli
testlardagi tarmoq bloki uni alohida yopadi (`tests/conftest.py`) —
aks holda tasodifiy test haqiqiy katalogga surat yuklab qo'yardi.

Qo'lda:

```bash
python -m skriptlar.rasm_qoy 158 D:/rasmlar/rsk-klapani.jpg --korish
```

> **Hajmi:** 2026-09-09 da 177 mahsulotdan **176 tasida rasm bor**.
> Ya'ni bu ommaviy to'ldirish vositasi emas — u yangi qo'shilgan
> mahsulot uchun va rasmsiz qolgan yagona yozuv (id 158) uchun.

### Guvohnoma

`X-API-Key: <SERVICE_API_KEY>` — asosiy yo'l. Kalit backendda ham, bizning
`.env` da ham bir xil turadi; eskirmaydi.

`Authorization: Bearer <CLIMAVENT_TOKEN>` — zaxira (odam JWT'si, eskiradi).

Klient ikkalasini ham yuboradi: qaysi biri qabul qilinishi endpointga bog'liq.

Tekshirish (hech narsa yaratmaydi — bo'sh tana 400 qaytaradi):

```bash
curl -s -o /dev/null -w '%{http_code}
' -X POST   -H 'Content-Type: application/json' -H "X-API-Key: $SERVICE_API_KEY"   -d '{}' https://climavent-back-production.up.railway.app/api/products/create
```

`400` — kalit qabul qilindi. `401` — kalit noto'g'ri.

`users`, `orders`, `cart`, `reviews`, `likes` yo'llari jadvalda **yo'q** —
Nodira ularga texnik jihatdan murojaat qila olmaydi.

### Narx qayerda turadi

Narx mahsulotning o'zida emas:

- `product_models.price` — model narxi (matn: `"1200000"`);
- `characteristics.price` — xususiyat narxi (son).

Tijorat menejeri Temur KP tuzganda narxni **avval shu yerdan** oladi,
topilmasa `knowledge/sales/narxlar.yaml` ga tushadi va buni KP da ochiq
yozadi.

### Dollar kursi — bitta manba

`product_model_inside.price` **dollarda** saqlanadi; so'm narxi bazada
yo'q, o'qiyotganda kursga ko'paytirib hisoblanadi. Ya'ni kurs — butun
katalog narxini ko'paytiruvchi yagona raqam.

| Nima | Qayerda |
|---|---|
| Manba | `GET /api/settings/usd-rate` — sayt ham shundan hisoblaydi |
| O'qish | `ClimaventKlient.kurs()` |
| Amaldagi qiymat | `app/kurs.py` → `joriy()` |
| Zaxira | `sozlama().usd_kursi` — faqat sayt javob bermaganda |
| Yozish | `PATCH /api/settings/usd-rate` (Swagger: "admin/bot") — **hali ulanmagan** |

> **2026-09-09 da topilgan:** kurs ikki joyda mustaqil yashagan — bizning
> sozlamada 12 000, backendda ham 12 000, Markaziy bankda esa 11 813.21.
> Hamma so'm narxi ~1.6% yuqori chiqib turgan va buni hech kim
> sezmagan, chunki ikkala tomon ham "o'zicha to'g'ri" ishlardi.

Kunlik tekshiruv (`Bot.kurs_tekshiruvi`, soat 09:15) Markaziy bank kursi
bilan farqni o'lchaydi va chegaradan oshsa menejerga xabar beradi.
**Kursni o'zi o'zgartirmaydi:** qaysi kurs to'g'ri ekani biznes qarori —
ko'p kompaniya narxni MB kursidan yuqoriroq oladi. Shu siyosat uchun
`USD_USTAMA_FOIZ` bor.

Qo'lda tekshirish:

```bash
python -m skriptlar.kurs_tekshir
```

### Xavfsizlik qatlamlari

1. HTTP metodi va yo'l `AMALLAR` jadvalidan olinadi — model ixtiyoriy
   endpoint ko'rsata olmaydi.
2. Har amal maydonlari oq ro'yxatdan o'tadi (`is_admin` kabi begona kalit
   tashlanadi).
3. Bir so'rovda ko'pi bilan `MAKS_AMAL = 20` yozuv o'zgaradi.
4. `mahsulot_yangila` avval mavjud yozuvni o'qib ustiga qo'yadi — PATCH
   to'liq DTO talab qilgani uchun maydonlar o'chib ketmaydi.
5. Yozish FAQAT inson tasdig'idan keyin bajariladi (orkestrdagi
   `TAKLIF_MAYDONLARI` mexanizmi).
6. Test to'plamida `conftest.py` yozish klientini butunlay bloklaydi.

---

## Texnik parametrlar (havo sarfi, bosim) — R2 jadvalidan

`product_models` da havo sarfi (m³/soat) va bosim (Pa) uchun **maydon
yo'q** (`docs/backend-topshiriq-5.md`, 1-bo'lim). Ma'lumot faqat shu
yo'lda:

```
GET /api/products/one/{id}
  → characters[i].contentJson = "https://pub-….r2.dev/…"   (ProseMirror JSON)
       ичида: | Модель | Мощность, кВт | Производительность, м3/ч | Полное давление, Па |
              | ВЦ 14-46-2 | 0,18       | 570-800                  | 270-310             |
```

Buni `integrations/texnik.py` o'qiydi:

| Funksiya | Vazifasi |
|---|---|
| `jadval_gridlari(hujjat)` | `colspan`/`rowspan` ni yoyib, jadvalni to'rtburchak to'rga aylantiradi |
| `ustun_turi(sarlavha)` | `havo` / `bosim` / `quvvat` — "по теплу", "расход воды" ATAYLAB chiqarib tashlanadi |
| `son_oraligi("570-800")` | `(570, 800)` — oraliqli qiymatlar ham o'qiladi |
| `hujjatdan_parametrlar(hujjat)` | butun hujjatdan model parametrlari |
| `moslashtir(parametrlar, katalog_nomlari)` | jadval nomini katalog modeliga bog'laydi |

Klientda: `await api.texnik_parametrlar()` →
`{model nomi: {havo_sarfi, bosim, quvvat_kvt, turi}}`.

**Qimmat:** 137 mahsulot × (1 `products/one` + 1–3 R2 fayl) ≈ **80 sekund**.
Shu sababli natija `chiqish/texnik_parametrlar.json` ga yoziladi va
`TEXNIK_KESH_KUNLARI` (standart 7 kun) davomida qayta yig'ilmaydi.
Majburan yangilash: `await api.texnik_parametrlar(yangila=True)`.

**Qamrov (2026-08-11 o'lchovi):** 266 model, shundan **149 tasi
ventilyator** havo sarfi bilan. Qolgani jadvalda bor, lekin nomlar
katalog nomiga bog'lanmadi (masalan jadvalda `ВОД 112`, katalogda
`ВОД-040-ДУ-0,18-1350`) — bu backend ma'lumot sifati masalasi.

**Qoida:** raqam FAQAT jadvaldan olinadi. Jadval tushunarsiz bo'lsa
parametr bo'sh qoladi — taxmin qilinmaydi (`tests/test_texnik.py`).
