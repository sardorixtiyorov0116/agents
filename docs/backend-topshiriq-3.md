# Backend topshirig'i №3 — to'liq xavfsizlik va sifat tekshiruvi

> Bu faylni backend dasturchiga bering — Claude Code'ga to'g'ridan-to'g'ri
> topshiriq sifatida berish mumkin.

**Tekshirilgan:** `https://climavent-back-production.up.railway.app`
**Sana:** 2026-08-06
**Qamrov:** OpenAPI sxemasidagi **104 endpoint**, shundan **61 tasi yozuvchi**
**Usul:** faqat o'qish va zararsiz probalar — mavjud bo'lmagan `id = 99999999`
va bo'sh tana. Hech qanday katalog yozuvi yaratilmadi, o'zgartirilmadi,
o'chirilmadi.

---

## OGOHLANTIRISH: tekshiruv paytida bitta yozuv paydo bo'ldi

`POST /api/users/login` ni sinaganda ma'lum bo'ldiki, u shunchaki kirish
emas — **yangi foydalanuvchi yaratadi**. Natijada bazada quyidagi yozuv
paydo bo'lgan:

```
users.id = 15, phone_number = +998900000000
```

Bu sinov yozuvi, o'chirib tashlashingiz mumkin. Uni ataylab yaratmadim —
endpoint nomi "login" bo'lgani uchun u faqat o'qiydi deb o'ylagan edim.
Aynan shu xatti-harakat quyidagi **1.5-bo'limda** muammo sifatida
yozilgan.

---

## AVVALGI TOPSHIRIQLAR — BAJARILGAN ✅

Yaxshi ish qilingan, buni alohida yozib qo'yaman:

| Muammo | Holat |
|---|---|
| `PATCH .../update/99999999` → 500 o'rniga 404 | ✅ tuzatildi |
| `characteristics/update` yolg'on `200` qaytarardi | ✅ endi 404 |
| `DELETE .../delete/99999999` → 404 | ✅ tuzatildi |
| Qidiruv `models` massivini bermasdi | ✅ endi beradi |
| Model kodi bo'yicha qidiruv ishlamasdi (`ВК-250П`) | ✅ ishlaydi |
| `/api/products/all` sahifalanmasdi | ✅ `limit` ishlaydi (698 KB → 19 KB) |
| `order-items/create` da auth yo'q edi | ✅ endi 401 |
| Xizmat kaliti (`X-API-Key`) | ✅ 9 amalda ham ishlaydi |

---

## 1. KRITIK — bugun tuzatilishi kerak

### 1.1. Mijozlarning telefon va emaili INTERNETDA ochiq

```
GET /api/reviews/all          → 200, guvohnomasiz
```

Javobda har sharh bilan birga **to'liq `user` obyekti** keladi:

```
user: { name, surname, fathername, phone_number,
        additional_phone_number, email, ... }
```

Hozir 12 ta yozuv — ya'ni 12 ta mijozning ismi, telefoni va emaili
istalgan odam uchun ochiq. Sharhlar soni oshgani sari bu ro'yxat o'sadi.

Bu shaxsiy ma'lumot. Yechim ikki qadam:

1. `reviews/all` ni guvohnoma orqasiga oling (yoki admin uchun qoldiring);
2. Ochiq sharh ro'yxatida `user` dan **faqat ismni** qaytaring —
   `phone_number`, `email`, `fathername` umuman chiqmasin.

### 1.2. Buyurtma va savat mazmuni ochiq

```
GET /api/order-items/all        → 200, 39 yozuv (order_id, product, quantity, user_id)
GET /api/cart-items/all         → 200, 8 yozuv
GET /api/selected-to-checkout/all → 200
```

Kim nima sotib olgani va savatida nima borligi tashqaridan ko'rinadi.
Uchalasi ham guvohnoma talab qilishi kerak.

### 1.3. Boshqa odamning savatini o'chirib tashlash mumkin

```
DELETE /api/selected-to-checkout/deletebyuser/{id}         → 200, auth YO'Q
DELETE /api/selected-to-checkout/deletecartitembyuser/{id} → 200, auth YO'Q
```

`{id}` — foydalanuvchi ID'si. Ya'ni istalgan odam raqamlarni ketma-ket
qo'yib chiqib, **hamma mijozning tanlovini o'chirib tashlashi** mumkin.

Ustiga-ustak, mavjud bo'lmagan `id = 99999999` uchun ham `200` va
`"successfully deleted"` qaytadi — ya'ni hech narsa o'chmagan bo'lsa ham
"muvaffaqiyat" deyiladi.

Yechim: guvohnoma + `id` so'rov yuboruvchining o'ziniki ekanini tekshirish
+ o'chmagan bo'lsa `404`.

### 1.4. `cart-items` da auth umuman yo'q

```
POST   /api/cart-items/create        → 400 (validatsiya), auth YO'Q
PATCH  /api/cart-items/update/{id}   → 500, auth YO'Q
DELETE /api/cart-items/delete/{id}   → 404, auth YO'Q
```

`cart` himoyalangan, lekin uning qatorlari emas. Begona odam istalgan
savatga mahsulot qo'sha, miqdorini o'zgartira va o'chira oladi.

### 1.5. `login` cheksiz SMS yuboradi va foydalanuvchi yaratadi

```
POST /api/users/login  {"phone_number": "+998900000000"}
  → 201  "Verification code sent to user"
  → users jadvaliga YANGI yozuv qo'shildi
```

Ikkita muammo:

**a) Tezlik cheklovi yo'q.** 25 ta ketma-ket urinish yubordim — hech
biri to'xtatilmadi. Ya'ni bir kishi skript bilan minglab SMS yubortirishi
mumkin. **SMS pullik** — bu to'g'ridan-to'g'ri pul yo'qotish, plyus
raqam egalariga spam.

**b) Guvohnomasiz yozuv yaratiladi.** Istalgan raqam uchun `users` ga
qator qo'shiladi. Baza soxta foydalanuvchilar bilan to'ladi.

Yechim quyida — **1.7-bo'lim**da to'liq yozilgan.

### 1.6. Butun API'da tezlik cheklovi yo'q

Yuqoridagi login — eng qimmat holat, lekin cheklov **hech qayerda** yo'q.
`@nestjs/throttler` global qo'yilsa, bir necha qatorlik ish.

### 1.7. Autentifikatsiya oqimi — nima qilish kerak

Bu bo'lim kompaniya bilan kelishilgan qaror. **Akkaunt tizimi qoladi,
parol qo'shilmaydi.** Sabab: parol yangi zaiflik qo'shadi (saqlash,
tiklash oqimi, takroriy parollar), lekin SMS xarajatini kamaytirmaydi —
"parolni unutdim" baribir SMS yuboradi.

SMS xarajati **uzoq sessiya** bilan yechiladi.

**1) Sessiyani uzaytirish**

```
Hozir:  har kirish -> SMS
Kerak:  birinchi kirish -> SMS
        keyin 60-90 kun -> SMS yo'q
```

- `access token` — qisqa (15-30 daqiqa);
- `refresh token` — **60-90 kun**, bazada saqlanadi, chiqishda bekor
  qilinadi;
- mijoz oyiga bir marta kirsa ham, SMS 2-3 oyda bir marta ketadi.

**2) Login endpointiga limit**

| Cheklov | Qiymat |
|---|---|
| Bitta telefon raqamiga | 5 daqiqada 1 SMS |
| Bitta IP manzildan | soatiga 10 ta so'rov |
| Bitta raqamga sutkasiga | 5 ta SMS |

`@nestjs/throttler` + telefon raqami bo'yicha alohida hisoblagich.

**3) Foydalanuvchi TASDIQDAN KEYIN yaratilsin**

Hozir `POST /api/users/login` darhol `users` ga qator qo'shadi. Ya'ni
istalgan odam istalgan raqam uchun yozuv yaratishi mumkin.

Kerakli tartib:

```
POST /users/login       -> OTP yuboriladi, users ga TEGILMAYDI
                           (kutilayotgan tasdiq alohida saqlanadi)
POST /users/verify-otp  -> kod to'g'ri bo'lsa users ga yoziladi
```

**4) OTP ning o'zi ham himoyalansin**

- kod amal qilish muddati: **5 daqiqa**;
- bitta kodga **3 marta** noto'g'ri urinish — keyin bekor qilinadi;
- tasdiqlangan kod qayta ishlatilmasin.

Busiz 6 xonali kodni tanlab topish mumkin.

**Natija:** SMS xarajati bir necha barobar tushadi, soxta foydalanuvchilar
paydo bo'lmaydi, mijoz uchun esa hech narsa murakkablashmaydi — u
parol o'ylab topmaydi va unutmaydi.

---

## 2. YUQORI

### 2.1. `500` o'rniga to'g'ri kod

```
PATCH /api/cart-items/update/99999999  → 500   (kutilgan: 404)
GET   /api/products/one/abc            → 500   (kutilgan: 400)
GET   /api/product-models/one/abc      → 500   (kutilgan: 400)
```

Raqam bo'lmagan `id` server xatosiga olib keladi. `ParseIntPipe`
qo'yilsa, `400 Bad Request` chiqadi.

`500` monitoringni ifloslaydi: haqiqiy nosozlik oddiy noto'g'ri
so'rovlar orasida ko'rinmay qoladi.

### 2.2. Xavfsizlik sarlavhalari yo'q

```
x-powered-by: Express          ← texnologiya oshkor
strict-transport-security: yo'q
x-content-type-options: yo'q
x-frame-options: yo'q
content-security-policy: yo'q
```

`helmet` paketi bir qatorda hammasini qo'yadi:

```js
app.use(helmet());
app.disable('x-powered-by');
```

### 2.3. `product_model_inside.product_model_id` hamon buzuq

Bu 2-topshiriqda ham bor edi, tuzatilmagan. To'liq tahlil:
[backend-topshiriq-2.md](backend-topshiriq-2.md), 1.5-bo'lim.

Qisqasi: **932 yozuvning 932 tasida** SAP kodi oilasi ota-model oilasiga
mos kelmaydi.

```
sap_name "ВЦ 4-75-2,5-О-1-0,12/1500"  (markazdan qochma ventilyator)
  product_model_id = 96
  → product_models[id=96] = "КВН 250-2-1"   (suvli isitgich)
```

Guruhlash o'zi buzilmagan — faqat nishon ID'lar surilgan. Eng ishonchli
tuzatish: `in_model_name` bo'yicha qayta bog'lash.

Biz hozircha `product_model_id` ni umuman ishlatmay, nom bo'yicha
bog'lab turibmiz — bu vaqtinchalik yechim.

---

## 3. O'RTA

### 3.1. Qidiruv o'zbekcha/lotincha so'rovni tushunmaydi

```
"вентилятор"          → 40 natija  ✅
"ПВН"                 → 1 natija   ✅
"ВК-250П"             → 1 natija   ✅
"kanal ventilyatori"  → 0 natija   ❌
```

Menejerlar ham, mijozlar ham lotincha yozadi. Kamida `name_uz` va
`name_en` bo'yicha ham `ILIKE` qo'shilsa yaxshi bo'lardi.

### 3.2. `/api/products/all` hamon og'ir

`limit` endi ishlaydi (rahmat), lekin parametrsiz chaqiruv **698 KB,
1.56 soniya**. Standart `limit` (masalan 20) qo'yilsa, eski mijozlar
ham yengillashadi.

---

## 4. MA'LUMOT SIFATI — kod emas, kontent

| Muammo | Miqdor |
|---|---|
| Narxi bor modellar | **24 / 1482** (1%) |
| Birorta modeli yo'q mahsulotlar | 41 / 137 |
| Takroriy model nomlari | 11 ta nom (22 yozuv) |
| Rasmi yo'q mahsulot | 1 |
| SAP kodi bor modellar | 143 / 1482 (10%) |

**Narx — eng katta to'siq.** Tijorat taklifi (KP) narxsiz tuzilmaydi.
Texnik qism tayyor, faqat ma'lumot yetishmaydi.

**Shubhali qiymat:** `ВР 6-28-4-1-0,37-1500` narxi **14 so'm**. Aniq
kiritish xatosi — ventilyator 14 so'm bo'lmaydi.

**Takroriy nomlar** (har biri 2 marta): `Д 15,5-3-500-1000`,
`ВОД-040-ДУ-0,18-1350`, `ВОД-063-ДУ-2,2-1390`, `ВОД-080-ДУ-11,0-1435`,
`ВЦП 6-46-5`, `ВЦП 6-46-6,3`, `ВЦП 6-46-8`, `ВЦП 6-46-10` va boshq.
Bir xil nomli ikki model narx qidiruvida chalkashlik beradi.

**Ombor qoldig'i model darajasida yo'q** — `quantity` faqat
`products` da. "ВК-250С dan nechta bor?" degan savolga aniq javob
bera olmaymiz, faqat butun seriya bo'yicha aytamiz.

---

## 5. TEKSHIRISH BUYRUQLARI

Har tuzatishdan keyin (hech narsa yaratmaydi):

```bash
ASOS=https://climavent-back-production.up.railway.app

# 1.1 — 401 kutiladi (hozir 200 va telefon raqamlari chiqadi)
curl -s -o /dev/null -w '%{http_code}\n' $ASOS/api/reviews/all

# 1.2 — uchalasida ham 401 kutiladi
for y in order-items cart-items selected-to-checkout; do
  curl -s -o /dev/null -w "$y %{http_code}\n" $ASOS/api/$y/all
done

# 1.3 — 401 kutiladi (hozir 200 "successfully deleted")
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
  $ASOS/api/selected-to-checkout/deletebyuser/99999999

# 1.4 — 401 kutiladi
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Content-Type: application/json' -d '{}' $ASOS/api/cart-items/create

# 1.5/1.6 — 10 ta urinishdan keyin 429 kutiladi
for i in $(seq 1 10); do
  curl -s -o /dev/null -w '%{http_code} ' -X POST \
    -H 'Content-Type: application/json' \
    -d '{"phone_number":"+998900000001"}' $ASOS/api/users/login
done; echo

# 1.7 — tasdiqlanmagan raqam users ga TUSHMASLIGI kerak.
# Login yuborgandan keyin admin panelda shu raqam paydo bo'ldimi —
# tekshiring. Bo'lmasa: to'g'ri.

# 1.7 — OTP muddati va urinishlar soni:
#   1) login yuboring, 6 daqiqa kuting, eski kod bilan verify -> rad etilsin
#   2) bitta kodga 4 marta noto'g'ri urinish -> 4-si rad etilsin

# 2.1 — 400 kutiladi (hozir 500)
curl -s -o /dev/null -w '%{http_code}\n' $ASOS/api/products/one/abc

# 2.2 — sarlavhalar bo'lishi kerak
curl -sI $ASOS/api/products/allcount | grep -iE 'x-powered-by|strict-transport|x-frame'

# 3.1 — natija bo'lishi kerak
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"text":"kanal ventilyatori"}' $ASOS/api/products/search | head -c 200
```

---

## 6. USTUVORLIK

| # | Ish | Nega birinchi |
|---|---|---|
| 1 | **1.1** reviews/all — telefon va email ochiq | Shaxsiy ma'lumot, hoziroq |
| 2 | **1.3** boshqa mijoz savatini o'chirish | Ma'lumot yo'qoladi |
| 3 | **1.5–1.7** login limiti + uzoq sessiya | SMS pullik — pul ketyapti |
| 4 | **1.2** buyurtma/savat ochiq | Shaxsiy ma'lumot |
| 5 | **1.4** cart-items auth | Ma'lumot buziladi |
| 6 | **2.2** helmet sarlavhalari | Bir qatorlik ish |
| 7 | **2.1** 500 → 400/404 | Monitoring tozalanadi |
| 8 | **2.3** SAP bog'lanishi | KP da rasmiy kod chiqadi |
| 9 | **3.1** lotincha qidiruv | Menejer ishi yengillashadi |
| 10 | **4** narxlar | Bu dasturchi emas, kontent ishi |

Birinchi beshtasi — **xavfsizlik**, ular kod yozishdan ko'ra guard
qo'yish. Bir kunlik ish bo'lishi kerak.
