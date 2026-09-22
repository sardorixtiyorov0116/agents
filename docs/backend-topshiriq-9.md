# Backend topshirig'i №9 — `characteristics` shartnomasi

**Kimga:** Climavent backend dasturchisiga
**Sana:** 03.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

**Tekshirish usuli:** yaratish/o'chirish sinovlari **o'z sinov
yozuvlarimizda** bajarildi (`ZZ-` prefiksli modellar, mahsulot #171 va
#24). Har bir sinovdan keyin yozuv va u yaratgan R2 obyektlari
o'chirildi; oxirida qoldiq nolga tekshirildi. **Katalog o'zgarmadi.**
Mavjud mahsulot yoki modelning mazmuniga tegilmadi.

**Sabab:** yangi adminkaga model qo'shish va model uchun texnik jadval
muharriri qo'shildi. Shu ish davomida `characteristics` endpointlarida
hujjatda yozilmagan va o'zaro ziddiyatli xatti-harakatlar topildi.

---

## Avval — №8 tasdiqlandi

Oltita bandning hammasi jonli tekshirildi. **Hammasi ishlayapti.**

| № | Band | Tekshiruv |
|---|---|---|
| 1 | R2 yozish | ✅ satr ham, obyekt ham to'g'ri yoziladi; bo'sh `data` → 400; `DELETE` → 200; eski prefiksiz 744 ta havola hamon o'qiladi |
| 2 | `views` / `updatedAt` | ✅ #171: kalit bilan va `?count=false` bilan sanalmadi, kalitsiz +2, `updatedAt` umuman o'zgarmadi |
| 3 | `store_id` | ✅ `stores/all` ishlaydi, `alladmin?store_id=1` → 1, `=2` → 137 |
| 4 | Javob sxemalari | ✅ OpenAPI da misollar bor |
| 5 | Buyurtmalar | ✅ kalitsiz 401, `X-API-Key` bilan 200 |
| 6.2 | Bo'sh bo'lim `null` | ✅ 137 mahsulot × 8 maydon: `{}` — **0 ta** |
| 6.3 | Rasm yuklash | ✅ Cloudinary ishlayapti: PNG/GIF → 201, `DELETE` → 200 |

**Kodlash alohida tekshirildi:** `Тест — кириллица, o'zbek so'zi` R2 ga
yozilib qayta o'qilganda **bayt-ma-bayt butun** qaytdi.

Bitta kichik tuzatish: 6.3-band «Railway'ga qo'yilmagan» deb yozilgan
edi, lekin kalitlar **allaqachon o'rnatilgan** va rasm yuklash prodda
ishlayapti.

---

## 1. 🔴 `characteristics/update` obyektni buzib yozadi

**Eng jiddiy nuqta.** `contentJson` ga obyekt yuborilsa, backend uni
`String()` bilan aylantirib, R2 fayliga shuni yozadi:

```
"[object Object]"
```

**Xato bermaydi — `200 OK` qaytaradi.** Ya'ni texnik jadval jimgina
yo'q bo'ladi va buni faqat saytda ochib ko'rganda bilish mumkin.

### O'lchov

```
PATCH /api/characteristics/update/345
{"contentJson": {"type":"doc","content":[…]}}
→ 200
→ fayl ichi: "[object Object]"          ← hujjat yo'q
```

Solishtirish uchun, JSON satri yuborilganda mazmun saqlanadi:

```
PATCH /api/characteristics/update/345
{"contentJson": "{\"type\":\"doc\",\"content\":[…]}"}
→ 200
→ fayl ichi: "{\"type\":\"doc\",…}"      ← satr, lekin mazmun butun
```

### Kerak

Obyekt kelganda ikkitasidan biri:

1. Uni JSON sifatida yozish (afzal — mavjud 301 ta fayl aynan shunday,
   ichida **obyekt** turibdi), yoki
2. `400` bilan rad etish.

`String()` ga tashlash — eng yomon variant, chunki ma'lumot yo'qoladi
va chaqiruvchi buni bilmaydi.

---

## 2. 🟠 `create` va `update` bir xil maydonni ikki xil tushunadi

`content` va `contentJson` uchun ikki endpoint ikki xil ishlaydi:

| Endpoint | `content` ga nima berilsa |
|---|---|
| `POST /characteristics/create` | **shundayligicha saqlanadi** |
| `PATCH /characteristics/update/{id}` | **R2 ga yuklanadi**, havolasi saqlanadi |

### O'lchov

```
CREATE content="<p>Salom jadval</p>"
→ bazada: "<p>Salom jadval</p>"                    ← matnning o'zi

CREATE content="https://pub-….r2.dev/climavent/a4ce9894.json"
→ bazada: "https://pub-….r2.dev/climavent/a4ce9894.json"   ← havola

PATCH  content="<p>PATCH bilan yangilandi</p>"
→ bazada: "https://pub-….r2.dev/climavent/01e0ad7c.json"   ← YANGI havola
→ fayl ichi: "<p>PATCH bilan yangilandi</p>"
```

### Buning oqibati

Mavjud modelni yangilamoqchi bo'lgan mijoz tabiiy ravishda havola
yuboradi (chunki bazada havola turibdi va `create` ham havolani qabul
qiladi). Natijada:

```
PATCH contentJson="https://…/338e971c.json"    ← to'g'ri jadval shu yerda
→ bazada: "https://…/3c050bf7.json"            ← BOSHQA fayl
→ 3c050bf7 ichida: "https://…/338e971c.json"   ← havolaning O'ZI yozilgan
```

Ya'ni jadval o'rniga saytda URL matni chiqadi. Biz aynan shunga
uchradik — adminka bo'limlarni R2 ga o'zi yozadi va havola ulaydi,
`characteristics` da esa bu usul ishlamadi.

### Kerak

Ikkalasi bir xil ishlasin. Qaysi biri to'g'ri deb hisoblasangiz —
o'shanisi, lekin **ikkalasida ham bir xil**. Tavsiya: `update` ham
`create` kabi shundayligicha saqlasin, R2 ga yozishni chaqiruvchi o'zi
qilsin (`r2-upload` allaqachon ishlaydi va tekshirilgan).

Agar `update` ning hozirgi xatti-harakati ataylab bo'lsa, hujjatga
yozilsin — hozir OpenAPI da bu haqda hech narsa yo'q.

---

## 3. 🟡 Model narxi butun son, ichki variant narxi o'nlik

`characteristics.price` o'nlik sonni rad etadi, `product_model_inside.price`
esa qabul qiladi.

### O'lchov

| So'rov | Natija |
|---|---|
| `POST /characteristics/create` `price: 123.45` | **400** |
| `POST /characteristics/create` `price: 123` | 201 |
| `PATCH /characteristics/update/{id}` `price: 99.99` | **400** |
| `PATCH /characteristics/update/{id}` `price: 99` | 200 |
| `PATCH /product-model-inside/{id}` `price: 10.5` | **200** |

Katalog holati bu farqni tasdiqlaydi:

| Daraja | Narxlar soni | O'nligi |
|---|---:|---:|
| Model (`characters`) | 302 | **0** |
| Ichki variant (`insides`) | 419 | **89** |

O'nlik namunalari: `2475.07`, `3023.17`, `409.09`, `278.24`.

### Xato matni tushunarsiz

400 qaytganda javob shunday:

```json
{"message":"So'rovdagi parametr formati noto'g'ri","error":"Bad Request","statusCode":400}
```

Qaysi maydon aybdorligi aytilmaydi. Solishtirish uchun, boshqa
endpointlar aniq yozadi: `{"message":["sap_name should not be empty"]}`.

### Kerak

1. Model narxi ham o'nlikni qabul qilsin (ichki variantlar bilan bir xil
   bo'lsin) — yoki cheklov ataylab bo'lsa, hujjatda yozilsin.
2. 400 javobi qaysi maydon rad etilganini aytsin.

---

## 4. 🟡 Javob kaliti `newBaner`

`POST /characteristics/create` javobi:

```json
{ "message": "Characteristic successfully created",
  "newBaner": { "id": 347, "product_id": 171, "title": "…", "views": 0 } }
```

`newBaner` — banner modulidan ko'chirilgan qolgan nom (`banner` ham
xato yozilgan). `products/create` da bu `newProduct`.

**Kerak:** `newCharacteristic` (yoki hamma joyda bitta nom, masalan
`data`). Eski nomni bir muddat parallel qoldirsangiz, mijozlar
buzilmaydi.

---

## 5. 🟢 Kichik: hujjatdagi ikkita noaniqlik

### 5.1. `/products/all` standart chegarasi

№8 javobida `GET /products/all?store_id=2 → 137 ta` deb yozilgan. Amalda
**20 ta** qaytadi — endpoint standart `limit=20` bilan ishlaydi.

| So'rov | Natija |
|---|---:|
| `/products/all?store_id=2` | 20 |
| `/products/all?store_id=2&limit=200` | 137 |
| `/products/alladmin?store_id=2` | 137 |

Xato emas, lekin hujjatdagi raqam adashtiradi. OpenAPI da standart
chegara ko'rsatilsa yaxshi bo'lardi.

### 5.2. `CreateCharacteristicDto` da majburiy maydonlar ro'yxati noto'g'ri

Swagger `required: ['content','contentJson','price','product_id']` deydi.
Amalda o'lchandi (narx butun son qilib, faqat bitta maydon o'zgartirilib):

| Maydon | Hujjatda | Amalda |
|---|---|---|
| `content` | majburiy | ✅ majburiy, bo'sh bo'lmasin |
| `price` | majburiy | ✅ majburiy |
| `title` | ixtiyoriy | ✅ ixtiyoriy (bo'sh ham o'tadi) |
| `product_id` | majburiy (number) | satr ham qabul qilinadi |

Bu banddagi narsalar shoshilinch emas.

---

## Xulosa — nima kerak

| № | Nima | Muhimligi |
|---|---|---|
| 1 | `update` obyektni `"[object Object]"` qilib yozmasin | 🔴 ma'lumot yo'qoladi |
| 2 | `create` va `update` `content` ni bir xil tushunsin | 🟠 |
| 3 | Model narxi o'nlikni qabul qilsin; 400 qaysi maydon ekanini aytsin | 🟡 |
| 4 | `newBaner` → `newCharacteristic` | 🟡 |
| 5 | Hujjatdagi ikki noaniqlik | 🟢 |

1 va 2-bandlar bitta tuzatish bilan yopiladi: `update` ham `create` kabi
qiymatni shundayligicha saqlasa, obyekt masalasi ham, ikki xil ma'no
masalasi ham yo'qoladi.

---

## Adminka tomonida nima qilingan

Tuzatishni kutmasdan ishlashi uchun adminka hozirgi xatti-harakatga
moslashtirildi:

- Model jadvali `update` ga **mazmun** sifatida yuboriladi (havola emas)
- `contentJson` **JSON satri** sifatida yuboriladi (obyekt emas)
- O'qish yo'li ikkala shaklni ham tushunadi — eski fayllarda obyekt,
  muharrir saqlaganlarida satr
- Model narx maydoni butun songa cheklangan (`step="1"`), ichki variant
  maydoni o'nlikda qoldi

Siz 1 va 2-bandlarni tuzatganingizdan keyin adminkani bir shaklga
qaytaramiz. Shu sababli **tuzatishdan oldin ayting** — o'qish yo'lini
mos ravishda o'zgartiramiz, aks holda muharrir eski yozuvlarni ochganda
adashadi.
