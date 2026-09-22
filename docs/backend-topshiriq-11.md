# Backend topshirig'i №11 — savat, layk, sharh va hisoblagichlar

**Kimga:** Climavent backend dasturchisiga
**Sana:** 04.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

**Tekshirish usuli:** bu topshiriqda faqat **o'qish** so'rovlari bajarildi.
Hech narsa yaratilmadi va o'zgartirilmadi.

**Sabab:** adminkaning analitika bo'limi tayyor va mahsulot, model hamda
ichki variant darajasigacha tushadi. Yetishmayotgan yagona narsa —
**xarid niyati**: mahsulot necha marta savatga solingan, necha marta
yoqtirilgan. Ko'rish soni «qaradi» degani, savat esa «olmoqchi bo'ldi»
degani — bu ikkisi butunlay boshqa signal.

---

## Avval — №9 va №10 tasdiqlandi

Ikkala topshiriqning katta qismi bajarilgan. Jonli tekshirdim:

| Band | Holat |
|---|---|
| №9.1 `update` obyektni `"[object Object]"` qilardi | ✅ tuzatilgan — endi fayl ichida haqiqiy obyekt |
| №9.3 model narxi butun son edi | ✅ tuzatilgan — `12.75` qabul qilinadi |
| №9.4 javob kaliti `newBaner` | ✅ `newCharacteristic` qo'shilgan (eskisi orqaga moslik uchun qolgan) |
| №10.1 `stores` maydonlari | ✅ hammasi joyida |
| №10.3 do'kon CRUD + `store-auth` | ✅ ishlaydi |
| №10.4 **server tomonda izolyatsiya** | ✅ **403** — begona do'kon yozuviga tegib bo'lmaydi |
| №10.5 `store_id` majburiy | ✅ |
| №10.6 `alladmin` da `store_id` | ✅ |
| Do'kon o'chirish himoyasi | ✅ 409 va nechta mahsulot borligi aytiladi |

Izolyatsiyani haqiqiy `store_admin` hisobi yaratib sinadim: o'z do'koni
mahsulotini o'zgartira oldi, begonasiga tekkanda 403 oldi — o'zgartirishda
ham, o'chirishda ham. **Rahmat, bu eng muhim band edi.**

Adminka shu ikki tuzatishdan keyin vaqtinchalik yechimlaridan voz kechdi:
model narxi endi tiyin bilan yoziladi, `contentJson` esa obyekt sifatida
yuboriladi va katalogdagi eski 301 ta yozuv bilan bir shaklda saqlanadi.

---

## 1. 🟠 Savat, layk va sharhlar servis kaliti bilan yopiq

`orders` va `order-items` №8 da ochilgan edi va buzilish bo'lmadi.
Qolganlari hamon yopiq:

| Endpoint | `X-API-Key` bilan | OpenAPI da e'lon qilingan |
|---|---|---|
| `GET /api/cart/all` | **401** | — |
| `GET /api/cart-items/all` | **401** | `[{bearer}]` |
| `GET /api/likes/alllikes` | **401** | — |
| `GET /api/reviews/all` | **401** | `[{bearer}]` |
| `GET /api/selected-to-checkout/all` | **401** | `[{bearer}]` |
| `GET /api/orders/all` | ✅ 200, 23 ta | `[{bearer},{service-key}]` |
| `GET /api/order-items/all` | ✅ 200, 40 ta | `[{bearer},{service-key}]` |

Farq aniq ko'rinib turibdi: ochilganlarida `service-key` e'lon qilingan,
yopiqlarida esa faqat `bearer` — ya'ni **xaridor** JWT si.

Adminkada xaridor tokeni yo'q va bo'lishi ham kerak emas: u do'kon
kabineti, mijoz kabineti emas.

### Kerak

`orders` ga qilingani kabi, bu endpointlarga ham `service-key` qo'shilsin.
**Faqat `GET`** — yozish (`create`, `delete`, `update`) tegilmasin, ular
xaridor tokenida qolsin.

Kamida `cart-items/all` va `likes/alllikes` kerak. `reviews/all` va
`selected-to-checkout/all` ham foydali bo'lardi.

---

## 2. 🟠 Mahsulotda hisoblagichlar yo'q

Mahsulot obyektida `views` va `sold_count` bor, qolganlari yo'q:

```
views            274
sold_count       0
cart_count       — maydon yo'q
likes_count      — maydon yo'q
reviews_count    — maydon yo'q
reviews          [] (bo'sh massiv)
```

### Nega ro'yxatni o'qish yetarli emas

1-band bajarilsa ham, adminka har safar butun `cart-items` jadvalini
yuklab, o'zi sanashi kerak bo'ladi. Hozir yozuvlar kam, lekin savat
jadvali eng tez o'sadigan jadvallardan biri — bir yildan keyin bu
dashboard ochilishini sekinlashtiradi.

### Kerak

`products` javobiga uchta hisoblagich qo'shilsin:

```
products.cart_count       — nechta savatda turibdi
products.likes_count      — nechta layk
products.reviews_count    — nechta sharh
```

`views` va `sold_count` allaqachon shunday ishlaydi — bular ularning
yoniga tabiiy tushadi. `alladmin` ro'yxatiga ham qo'shilsa yaxshi:
adminkaning mahsulotlar jadvali aynan o'sha endpointdan o'qiydi.

Agar ikkalasidan birini tanlash kerak bo'lsa — **hisoblagichlar muhimroq**.
Ular bilan 1-band ochilmasa ham analitika ishlaydi.

---

## 3. 🟠 `order_items.product_model` — matn, FK emas

```
order_items kalitlari:
  id, order_id, product_id, product_model, quantity, price,
  createdAt, updatedAt, order, product

product_model turi : string
qiymat             : "ВК-125С"
product_model_id   : YO'Q
```

Ya'ni buyurtma qatorida modelning **nomi nusxasi** saqlanadi, `characteristics`
jadvaliga bog'lanish yo'q.

### Bu amalda nimaga olib kelgan — o'lchandi

40 ta buyurtma qatorini katalogdagi 282 ta noyob model nomi bilan
solishtirdim:

| | |
|---|---:|
| Model nomi topildi | 37 |
| **Topilmadi** | **3** |
| Topilganlaridan nomi bir necha modelda takrorlanadi | 1 |

Topilmaganlari: `ПП 1-11-2-2`, `УЭО-6`, `АОЭ-12` — model qayta nomlangan
yoki o'chirilgan bo'lsa kerak.

Bundan tashqari, katalogdagi **282 ta nomdan 17 tasi takrorlanadi** —
masalan `ВЦ 4-75-6,3` ikki xil mahsulotda bor. Ya'ni nom topilgan
taqdirda ham qaysi model ekani aniq emas.

Xulosa: **model bo'yicha sotuvni ishonchli hisoblab bo'lmaydi.** 7% qator
umuman bog'lanmaydi, bog'langanlarining bir qismi noaniq.

### Kerak

`order_items.product_model_id` (FK → `characteristics.id`) qo'shilsin.
Matnli `product_model` **saqlanib qolsin** — u tarix uchun kerak: model
o'chirilsa ham buyurtmada nima sotilgani ko'rinib tursin.

Eski yozuvlarni backfill qilish shart emas: nomlar noaniq bo'lgani uchun
avtomatik bog'lash xato natija berishi mumkin. Yangi buyurtmalardan
boshlansa yetarli.

---

## 4. 🟢 Kichik: `r2` va `images` do'kon tokenini tanimaydi

Do'kon hisobi tokeni (`store-auth/login` bergan JWT) bilan:

| Modul | Natija |
|---|---|
| `products`, `characteristics`, `product-model-inside` | ✅ qabul qiladi |
| `stores`, `store-users` | ✅ qabul qiladi |
| `r2/*` | ❌ 401 «Invalid or expired token» |
| `images/*` | ❌ 401 «Invalid or expired token» |

Adminka bu ikkisini servis kalitida qoldirdi va shunday ishlayapti.
Izolyatsiya buzilmaydi: R2 obyekti va Cloudinary rasmi o'z-o'zicha hech
kimga tegishli emas, ular mahsulotga **ulanganda** ma'no kasb etadi —
ulash esa mahsulot endpointi orqali, token bilan tekshiriladi.

Shoshilinch emas, lekin bir xil bo'lgani yaxshi: guard shu ikki modulda
ham `store-auth` tokenini tanisa, adminka hamma yozishni bitta
guvohnomada qilardi.

---

## Xulosa — ish tartibi

| № | Nima | Muhimligi |
|---|---|---|
| 2 | `cart_count`, `likes_count`, `reviews_count` | 🟠 eng foydalisi |
| 1 | `cart`, `likes`, `reviews` `GET` lariga `service-key` | 🟠 |
| 3 | `order_items.product_model_id` (FK) | 🟠 |
| 4 | `r2` va `images` do'kon tokenini tanisin | 🟢 |

**Boshlash uchun tavsiya:** 2-band. U bitta migratsiya va bir nechta
`@@Column` bilan yopiladi, adminka esa darrov ishlata boshlaydi — 1-band
ochilishini kutmasdan.

---

## Adminka tomonida nima tayyor

Hisoblagichlar kelishi bilan quyidagilar darrov ishlaydi, qo'shimcha
ish talab qilmaydi:

- Dashboardda «savatga solingan» KPI kartasi
- Mahsulotlar jadvalida savat ustuni va u bo'yicha saralash
- Analitikada **ko'rish → savat → sotuv** voronkasi

`product_model_id` kelsa, «qaysi model ko'proq sotilgan» reytingi
qo'shiladi — hozir model darajasida faqat **ko'rishlar** bor
(302 modeldan 6 tasida ko'rish qayd etilgan, jami 12 ta; hisoblagich
yaqinda ishga tushgani uchun raqamlar hali kichik).
