# Backend topshirig'i №14 — nofaol do'kon, yozish endpointlari va bir nechta savol

**Kimga:** Climavent backend dasturchisiga
**Sana:** 10.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

Bu hujjatda uch xil narsa bor:

1. **Saytdagi haqiqiy muammo** — nofaol do'kon hech qayerda hisobga
   olinmaydi (1-band). Eng muhimi shu.
2. Adminka uchun kerak bo'lgan **ikkita yozish endpointi** (2 va 3-band).
3. **Savollar** — javob kutaman, chunki ba'zi qarorlar sizniki.

**Tekshirish usuli — hech narsa buzilmadi.** Yozish endpointlari
**bo'sh tana** (`{}`) yoki **mavjud bo'lmagan id** bilan sinaldi:
javob kodi guard bor-yo'qligini ko'rsatadi, lekin bazaga hech narsa
yozilmaydi. Buyurtma sinovida esa yozuvning **o'z hozirgi qiymatlari**
qaytadan yuborildi. Sinovdan keyin sanaldi: kategoriya 35, sharh 12,
buyurtma 23, `store_users` 0 — **hammasi o'zgarmagan**.

---

## 1. 🔴 Nofaol do'kon saytda ochiq turibdi

`stores.is_active = false` bayrog'i **hech bir ommaviy endpointda**
hisobga olinmaydi. Ya'ni do'konni "nofaol" qilish hozir hech narsani
o'zgartirmaydi.

Bazadagi holat: `Armavent` (id 7) va `VENTS US` (id 8) — `is_active =
false`. Ularda 40 ta mahsulot bor.

**Guvohnomasiz o'lchandi (ya'ni sayt aynan shuni oladi):**

| So'rov | Natija | Nofaol do'konnikidan |
|---|---|---|
| `POST /api/products/search` `{"text":"ventilyator"}` | 77 ta | **37 ta** |
| `POST /api/products/search` `{"text":"VR 80"}` | 4 ta | **4 ta — hammasi** |
| `POST /api/products/bysort` | 177 ta | **40 ta** |
| `POST /api/products/lastadded` | 177 ta | **40 ta** |
| `GET /api/products/all` | 177 ta | **40 ta** |
| `GET /api/products/allcount` | **177** | ichida 40 |
| `GET /api/products/one/235` | **200** | Armavent mahsuloti ochiladi |
| `GET /api/stores/slug/armavent` | **200** | nofaol do'kon sahifasi ochiladi |
| `GET /api/stores/one/7` | **200** | shu |
| `GET /api/stores/all` | 4 ta | **2 tasi nofaol** |

Ya'ni:

- **Qidiruvda chiqadi.** "VR 80" deb qidirilsa, chiqqan to'rttala
  natija ham nofaol do'konniki.
- **To'g'ridan-to'g'ri havola ishlaydi.** Do'kon ro'yxatdan tushgan
  bo'lsa ham, odamlarda uning havolasi saqlanib qolgan bo'lishi mumkin —
  ochsa, do'kon ham, mahsulotlari ham ochilaveradi.
- **`stores/all` nofaolni ham qaytaradi**, ya'ni ro'yxatdan yashirish
  hozir frontendning o'z ishi. Frontend uni filtrlashi mumkin, lekin
  qidiruv va to'g'ridan-to'g'ri havolani u tuzata olmaydi.

**So'rov:**

1. Hamma **ommaviy o'qish** endpointlari `store.is_active = true`
   bo'yicha filtrlansin: `products/all`, `products/search`,
   `products/bysort`, `products/lastadded`, `products/categoryslug`,
   `products/allcount`, `stores/all`.
2. **To'g'ridan-to'g'ri murojaat** nofaol do'konga yoki uning
   mahsulotiga **404** bersin: `products/one/{id}`, `stores/one/{id}`,
   `stores/slug/{slug}`.
3. **`allcount` filtrdan keyingi sonni** qaytarsin — aks holda sahifalash
   buziladi (177 deydi, 137 ta ko'rsatadi).
4. **Adminka bundan chetda qolsin.** `products/alladmin` va servis
   kaliti bilan kelgan so'rovlar hamon **hammasini** qaytarsin — men
   nofaol do'kon mahsulotlarini ko'rib, tahrirlab turishim kerak.

Adminkada bu holat hozircha shunday hal qilindi: nofaol do'kon
kartasida ochiq ogohlantirish chiqadi — "nofaol deb belgilangan, lekin
N ta mahsuloti saytda hamon ko'rinyapti". Ya'ni superadmin yolg'on
xotirjamlikda qolmaydi. Lekin bu **yechim emas**, faqat ogohlantirish.

---

## 2. 🔴 `PATCH /api/orders/update/{id}` — buyurtma holatini o'zgartirish

| Guvohnoma | Javob |
|---|---|
| Servis kaliti (`X-API-Key`) | ❌ 401 `{"message":"User unauthorized"}` |
| Do'kon tokeni (`store-auth/login`) | ❌ 401 `{"message":"Invalid or expired token"}` |

Endpoint faqat **mijoz** JWT'sini qabul qiladi. Natijada do'kon admini
"Tolanmagan → Yetkazilyapti → Yetkazildi" degan eng oddiy ishni
adminkadan qila olmaydi — holatni faqat mijozning o'zi o'zgartira
oladi, bu esa mantiqan teskari.

**So'rov:** servis kaliti va do'kon tokeni ham qabul qilinsin.

---

## 3. 🟡 `DELETE /api/reviews/delete/{id}` — sharhni o'chirish

| Guvohnoma | Javob |
|---|---|
| Servis kaliti | ❌ 401 `{"message":"User unauthorized"}` |
| Do'kon tokeni | ❌ 401 `{"message":"Invalid or expired token"}` |

Sharhlar bo'limi tayyor: o'rtacha baho, past baholar, mahsulot bo'yicha
kesim, qidiruv va filtr. Lekin spam yoki haqorat sharhni o'chirish
imkoni yo'q. Bo'limda buni ochiq yozib qo'ydim.

**So'rov:** `DELETE /api/reviews/delete/{id}` va
`PATCH /api/reviews/update/{id}` servis kaliti hamda do'kon tokenini
qabul qilsin.

---

## 4. 🔴 Holatlar enum bo'lishi kerak (№13 ning 5-bandi)

Bu 2-bandning **oldsharti**. Hozir bazada:

```
"Yetkazilyapti"  17 ta
"Tolanmagan"      5 ta
"Done"            1 ta
```

Adminkaga holat tanlash ro'yxatini qo'yishim kerak, lekin qat'iy ro'yxat
bo'lmasa, u yerga nima yozishni bilmayman.

Tartib shunday bo'lsa yaxshi: **enum → `orders/update` ochiladi →
adminkada tugma paydo bo'ladi.** Birinchi ikkitasi bajarilsa,
uchinchisini bir kunda qilaman.

---

## 5. 🟢 `category/*` do'kon tokenini qabul qilmaydi

| So'rov | Servis kaliti | Do'kon tokeni |
|---|---|---|
| `POST /api/category/create` | 400 (o'tdi, validatsiya to'xtatdi) | ❌ 401 |
| `PATCH /api/category/update/1` | — | ❌ 401 |
| `POST /api/products/create` | 400 (o'tdi) | ✅ 400 (o'tdi) |

Ya'ni `products/create` do'kon tokenini qabul qiladi, `category/create`
esa yo'q. Adminkada kategoriya baribir faqat superadminga ochiq va u
servis kaliti bilan ketadi, shuning uchun **hozir muammo emas**. Lekin
bir xil bo'lgani yaxshi — kelajakda esdan chiqib, tushunarsiz 401 ga
duch kelmaslik uchun yozib qo'yyapman.

---

## 6. 🟢 Taklif: mahsulotning o'z `is_active` i

Hozir mahsulotni saytdan yashirishning yagona yo'li — butun do'konni
nofaol qilish. Mahsulot obyektida `is_active`/`is_hidden` kabi maydon
umuman yo'q (tekshirdim).

Amalda kerak bo'ladi: bitta mahsulot vaqtincha sotuvda bo'lmasa, uni
o'chirib tashlash noto'g'ri (buyurtmalar tarixi unga bog'langan), butun
do'konni yopish esa ortiqcha.

**Taklif:** `products.is_active` (standart `true`) qo'shilsin va 1-banddagi
filtrga u ham kirsin. Shoshilinch emas.

---

## Savollar — javob kutaman

1. **1-band qachon qilinadi?** Bu saytdagi haqiqiy muammo: hozir nofaol
   do'kon mahsulotlari qidiruvda chiqyapti va havola orqali ochilyapti.
   Boshqa hammasidan muhimroq.

2. **Bitta buyurtmada bir nechta do'kon mahsuloti bo'lsa, holatni kim
   o'zgartira oladi?** Mening taklifim: superadmin — istalganini;
   do'kon admini — faqat buyurtmadagi **hamma qator** o'ziniki bo'lsa.
   Agar sizda boshqa fikr bo'lsa (masalan, holat buyurtmaga emas,
   qatorga tegishli bo'lsin), ayting — adminkani o'shanga moslayman.

3. **Sharhni o'chirish kerakmi yoki yashirish?** `is_hidden` bayrog'i
   xavfsizroq: xato bilan o'chirilgan sharhni qaytarib bo'lmaydi.
   Qaysi biri sizga qulay?

4. **Holatlar enum ro'yxati qanday bo'ladi?** Mening taklifim:
   `new | paid | shipping | done | cancelled`. Ko'chirish:
   `Tolanmagan → new`, `Yetkazilyapti → shipping`, `Done → done`.
   Ko'rinadigan matnni adminka va sayt o'zi tarjima qiladi.

5. **№13 dagi bandlar qanday ketyapti?** Ayniqsa ikkitasi:
   `users/all` servis kalitiga ochilishi va buyurtma qatorlarida
   narx yozilishi. Ular hamon kuchda va adminkada mijozlar bo'limi
   hamda pul analitikasi shularga bog'lanib turibdi.

---

## Muhimlik tartibi

| № | Band | Muhimligi |
|---|---|---|
| 1 | Nofaol do'kon hamma ommaviy endpointda filtrlansin, to'g'ridan-to'g'ri havolaga 404 | 🔴 saytdagi muammo |
| 4 | Buyurtma holatlari enum | 🔴 2-band uchun oldshart |
| 2 | `orders/update` servis kaliti va do'kon tokenini qabul qilsin | 🔴 yuqori |
| 3 | `reviews/delete` (yoki `is_hidden`) ochilsin | 🟡 o'rta |
| 5 | `category/*` do'kon tokenini qabul qilsin | 🟢 past |
| 6 | `products.is_active` | 🟢 past |

№13 dagi bandlar (mijozlar ro'yxati, buyurtmada narx, `refresh_token`,
`likes` da `user`) bu hujjatdan mustaqil va hamon kuchda.

Javobingizni kutaman — ayniqsa yuqoridagi beshta savolga.
