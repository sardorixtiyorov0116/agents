# Backend topshirig'i №7 — narx va valyuta

**Sana:** 18.08.2026
**Holat:** `product_model_inside.price` ga 299 ta narx yozildi (USD). Sayt ularni
qisman ko'rsatyapti — quyidagi uchta ish qolgan.

---

## 1. «Nega `UZS` deb yozilgan va nima qilish kerak»

### Hozirgi holat (o'lchandi)

`product_models` jadvalida ikkita eski maydon bor:

| Maydon | Holat |
|---|---|
| `price` | **MATN** turida, qiymat **so'mda** (masalan `"1650000"`). 1482 yozuvdan 25 tasida to'ldirilgan |
| `currency` | 1482 yozuvning **hammasida** `"UZS"` — hech qachon o'zgartirilmagan, ya'ni bu haqiqiy tanlov emas, standart qiymat |

Bu sxema biz «narx `product_model_inside` da, dollarda» degan qarorga kelishimizdan
OLDIN yaratilgan. Endi ikkita joyda ikki xil valyutali narx bor:

```
product_models.price        -> SO'M,   matn,  25 ta yozuv
product_model_inside.price  -> DOLLAR, son,   299 ta yozuv
```

### Chalkashlik allaqachon boshlangan

```
ВР 6-28-4-1-0,37-1500    price = 14      currency = 'UZS'
```

14 so'm bo'lishi mumkin emas. Kimdir **14 dollar** deb kiritgan, jadval esa uni
`UZS` deb belgilab qo'ygan. Bitta yozuvda bu xato allaqachon sodir bo'lgan.

### Nima qilish kerak

**Tavsiya: `product_models.price` dan butunlay voz kechish.**

1. Qolgan 44 ta narxli modelni (`ДР` 18, `РКВ` 2, `РЩ` 6, `ФЯГ` 18) uchun
   `product_model_inside` ga qator yaratilsin va narx **DOLLARDA** o'sha yerga
   yozilsin. Ro'yxat: `chiqish/narx/reja_v51.json` -> `xato` -> sabab
   «product_models jadvalida».
2. `product_models.price` va `currency` **eskirgan** deb belgilansin
   (`@deprecated` izohi + Swagger tavsifiga «ISHLATILMAYDI, `product_model_inside.price`
   ga qarang»). Darrov o'chirmang — eski mijoz kodi bo'lishi mumkin.
3. Yangi yozishlarda `product_models.price` ga narx yozish **taqiqlansin**
   (DTO dan olib tashlanmasa ham, hech bo'lmasa hujjatda).

Sabab: bitta narx ikkita joyda va ikkita valyutada turmasin. Kurs mijoz tomonda
bitta sozlamadan olinadi (`USD_KURSI = 12000`), shuning uchun bazada faqat
DOLLAR saqlanadi.

**Muqobil (agar 1-yo'l og'ir bo'lsa):** `product_models` ga `price_usd NUMERIC(10,2)`
ustuni qo'shilsin, eski `price` tegilmasin. Kamchiligi — bitta jadvalda ikki
valyutali ikkita narx ustuni qoladi.

---

## 2. `POST /api/products/categoryslug` javobiga `insides` qo'shilsin

**Muammo:** saytda katalog ro'yxatida hamma mahsulot «Цена по запросу» deb turibdi,
narx bazada bo'lsa ham.

**Sabab (o'lchandi):**

```
GET  /api/products/one/{id}        -> characters[].insides[]   ✅ BOR
GET  /api/characteristics/one/{id} -> insides[]                ✅ BOR
POST /api/products/categoryslug    -> characters[]             ❌ YO'Q
```

`categoryslug` javobidagi `characters` elementi:
`id, title, price, content, contentJson, product_id, createdAt, updatedAt`
— `insides` yo'q. Narx esa faqat `insides[].price` da.

**Topshiriq:** `categoryslug` service'idagi `include` / `relations` ga
`characters -> insides` qo'shilsin — `products/one` dagi bilan aynan bir xil.

**Tekshirish:**
```
POST /api/products/categoryslug
{"price":"ASC","limit":5,"page":1,"category_id":14}
```
`characters[0].insides` massivi bo'lishi va ichida `price` ko'rinishi kerak.

**Qo'shimcha:** DTO da `price: "ASC"` MAJBURIY maydon. Saralash `products.price`
bo'yicha bo'lsa, u deyarli hamma yozuvda bo'sh — ya'ni saralash ishlamayapti.
Tekshirilsin: saralash `insides[].price` ning minimumi bo'yicha bo'lishi kerak.

---

## 3. Ma'lumot tozalash

### 3.1. Bo'sh va buzuq R2 fayllari — 43 ta

302 ta xususiyatning `content` / `contentJson` havolasi tekshirildi. Natija:

| Muammo | Soni |
|---|---|
| R2 fayli **0 bayt** (bo'sh) | 40 |
| Havola o'rniga `"."` yoki `{}` yozilgan | 2 |
| Mazmuni deyarli bo'sh (`"<p>.</p>"`) | 1 |

Ta'siri: saytda xususiyat bo'limi **butunlay bo'sh** chiqadi (o'zim ko'rdim:
`/product/37`, «Characteristic» bo'limida faqat model nomlari, matn yo'q).

To'liq ro'yxat: `chiqish/narx/front_nosoz.json`.
Eng ko'p ta'sirlangan mahsulotlar: 37 (ПНЭ — 16 ta bo'sh fayl), 94 (ДКСп),
31 (ПВН), 40 (КБС), 4 (JV), 2 (HI-SMART H), 1 (HI-FLEXI).

**Topshiriq:** bo'sh fayllar qayta yuklansin yoki tegishli maydon `NULL` qilinsin.
`NULL` bo'lsa front «ma'lumot yo'q» deb ko'rsata oladi; hozir esa bo'sh
fayl «yuklandi» deb hisoblanadi va bo'sh blok chiqadi.

**Oldini olish:** yuklashda 0 baytli faylni qabul qilmaydigan tekshiruv qo'shilsin.

### 3.2. `product_model_inside` da takrorlangan nomlar — 9 guruh

Bir xil nomda bir nechta yozuv. Narx yozishda ular **ataylab chetlab o'tildi** —
qaysi biriga yozishni aniqlab bo'lmaydi.

| Nomi | id'lar |
|---|---|
| ГТП 200x100х1000 | 445, 945 |
| ГТП 300x200х1000 | 446, 946 |
| ГТП 400x200х1000 | 447, 947 |
| ГТП 400x300х1000 | 448, 948 |
| ГТП 400x400х1000 | 449, 949 |
| КОГ 400х400 | 498, 499 |
| КГП 30-15 (10) | 619, 621 |
| КГП 40-20 (10) | 620, 622 |
| ДКСп 500х300х350 | 644, 645, 655 |

**Topshiriq:** dublikatlar o'chirilsin, `in_model_name` ga UNIQUE cheklov qo'yilsin.

### 3.3. `product_model_inside.product_model_id` nomi noto'g'ri

U `characteristics.id` ga ishora qiladi, `product_models.id` ga EMAS.
Tasdiq: id=96 -> inside «ВЦ 4-75-2,5», characteristics «ВЦ 4-75-2,5»,
lekin product_models id=96 «КВН 250-2-1».

Swagger izohi to'g'ri yozilgan («Characteristic (model) id») — shu yetarli,
hozir o'zgartirmang (mijoz kodi shunga moslashgan). Kelajakda migratsiya
qilinsa `characteristic_id` deb nomlansin.

---

## Nima qilinmasin

- Mavjud ustun turlari va nomlari o'zgartirilmasin.
- `synchronize: true` / `sync({alter:true})` yoqilmasin.
- Narx ma'lumotining o'zi backendda qo'lda o'zgartirilmasin — u Exceldan yuklanadi.
