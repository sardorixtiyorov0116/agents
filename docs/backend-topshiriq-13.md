# Backend topshirig'i №13 — mijozlar bo'limi uchun

**Kimga:** Climavent backend dasturchisiga
**Sana:** 10.09.2026
**Server:** `https://climavent-back-production.up.railway.app`

Adminkaga **Foydalanuvchilar** bo'limi qo'shildi: kim savatga solgan, kim
sotib olgan, mijozning aloqa ma'lumoti, buyurtmalari va sharhlari. Bo'lim
ishlaydi, lekin **chala** — chunki mijozlar ro'yxati endpointi adminga
ochiq emas. Quyida o'lchangan holat va so'rovlar.

**Tekshirish usuli:** har bir endpointga `X-API-Key` (servis kaliti)
bilan `GET` yuborildi. Hech narsa yozilmadi, faqat o'qish.

---

## 1. `users` endpointlari servis kalitini qabul qilmaydi — **asosiy so'rov**

| Endpoint | Servis kaliti bilan |
|---|---|
| `GET /api/users/all` | ❌ 401 `{"message":"Unauthorized"}` |
| `GET /api/users/one/{id}` | ❌ 401 `{"message":"User unauthorized"}` |
| `GET /api/users/badges/{id}` | ❌ 401 |
| `GET /api/cart/oneuser/{id}` | ❌ 401 |
| `GET /api/orders/oneuser/{id}` | ❌ 401 |
| `GET /api/likes/useralllikes/{id}` | ❌ 401 |

Ya'ni adminka mijozlar ro'yxatini **umuman ololmaydi**.

Hozircha vaqtinchalik yechim qildim: mijoz obyekti `cart/all`,
`orders/all` va `reviews/all` javoblarida ichma-ich kelayotgani uchun
ro'yxat **o'shalardan yig'ilyapti**. Buning ikkita kamchiligi bor:

1. Ro'yxatdan o'tgan, lekin hali hech narsa qilmagan mijoz adminkada
   **umuman ko'rinmaydi**. Ya'ni "saytda nechta mijoz bor?" degan
   savolga adminka javob bera olmaydi.
2. Ro'yxat butun jadvalni yuklab, xotirada yig'iladi. Hozir buyurtma 23
   ta, savat 4 ta — muammo emas. Mijoz soni minglab bo'lganda bu usul
   ishlamay qoladi.

**So'rov:** `GET /api/users/all` va `GET /api/users/one/{id}` servis
kalitini qabul qilsin — xuddi №11 da `cart-items`, `likes`, `reviews`,
`orders`, `order-items` uchun qilganingizdek. Iloji bo'lsa `all` ga
`page`/`limit` va `search` (ism/telefon/e-pochta bo'yicha) qo'shilsin.

---

## 2. `refresh_token` API javobida qaytyapti

`cart/all`, `orders/all` va `reviews/all` javoblaridagi **har bir**
ichma-ich `user` obyektida `refresh_token` maydoni to'ldirilgan holda
keladi:

```
cart/all      user obyekti: 4  ta, refresh_token to'ldirilgan: 4  ta
orders/all    user obyekti: 23 ta, refresh_token to'ldirilgan: 23 ta
reviews/all   user obyekti: 12 ta, refresh_token to'ldirilgan: 12 ta
```

Qiymat `$2b$08$…` bilan boshlanadi va 60 belgi — ya'ni bu **bcrypt
hash**, tirik token emas. Shuning uchun undan foydalanib sessiya
o'g'irlab bo'lmaydi va bu shoshilinch xavf emas. Lekin baribir:

- parol/token hash'ining API javobida qiladigan ishi yo'q;
- hash bo'lsa ham, u offlayn hujum uchun material;
- adminka uni **ataylab** o'z tipiga kiritmayapti va klientga
  uzatmayapti, lekin bu tashqi himoya, backendniki emas.

**So'rov:** `refresh_token` (va shu qatorda `password`/`hash` bo'lsa
o'shalar ham) serializatsiyadan chiqarilsin — `@Exclude()`, yoki
`select` da ochiq ro'yxat.

---

## 3. `likes` javobida mijoz obyekti yo'q

| Endpoint | `user` ichma-ich keladimi |
|---|---|
| `GET /api/cart/all` | ✅ ha |
| `GET /api/orders/all` | ✅ ha |
| `GET /api/reviews/all` | ✅ ha |
| `GET /api/likes/alllikes` | ❌ yo'q, faqat `user_id` |

Natijada faqat layk bosgan mijoz adminkada `#4` bo'lib turadi — ismi ham,
telefoni ham yo'q. Hozir katalogda aynan shunday bitta mijoz bor.

**So'rov:** `likes/alllikes` javobiga `user` qo'shilsin — `reviews/all`
dagi bilan bir xil shaklda (2-banddagi tozalash bilan birga).

---

## 4. Buyurtmalarda narx yozilmayapti

```
orders.totalAmount = 0        23 buyurtmadan 22 tasida
order_items.price  = 0        40 qatordan 39 tasida
cart_items.price   > 0        14 qatordan 3 tasida
```

Ya'ni "mijoz qancha pulga buyurtma berdi", "eng ko'p pul sarflagan mijoz
kim", "oyiga qancha savdo bo'ldi" degan savollarga javob **yo'q**.
Adminkada bunday qatorlar "narx yozilmagan" deb ko'rsatilyapti — nolni
haqiqiy summa deb ko'rsatish yolg'on bo'lardi.

Sabab, taxminimcha: buyurtma yaratilayotganda narx `product_model_inside`
dan ko'chirilmayapti. Bu ko'chirish **shart**, chunki katalog narxi
keyin o'zgaradi va eski buyurtma summasi buzilib ketadi.

**So'rov:**
- `POST /api/order-items/create` da `price` majburiy bo'lsin va
  buyurtma berilgan paytdagi so'm narxi yozilsin;
- `orders.totalAmount` qatorlar yig'indisidan hisoblansin;
- eski 22 buyurtmani orqaga tiklash shart emas — ular shundayligicha
  qolsin, adminka ularni "narx yozilmagan" deb ko'rsatadi.

---

## 5. Buyurtma holatlari bir xil emas

Bazadagi qiymatlar:

```
"Yetkazilyapti"  17 ta
"Tolanmagan"      5 ta
"Done"            1 ta
```

Uch xil yozuv, ikki xil til va bittasi inglizcha. Adminka ularni
shundayligicha ko'rsatyapti — tarjima qila olmaydi, chunki qiymatlar
oldindan ma'lum emas.

**So'rov:** holatlar qat'iy ro'yxat (enum) bo'lsin, masalan
`new | paid | shipping | done | cancelled`. Ko'rinadigan matnni adminka
va sayt o'zi tarjima qiladi. Ko'chirishda: `Yetkazilyapti → shipping`,
`Tolanmagan → new`, `Done → done`.

---

## 6. Kelajak uchun eslatma — do'kon bo'yicha chegara

Hozir `cart-items/all`, `order-items/all` va boshqalar **butun bazani**
qaytaradi. Adminka do'kon izolyatsiyasini o'zi qilyapti: har bir qatorni
ko'rinadigan mahsulot id'lari bo'yicha filtrlaydi va do'kon admini
begona do'konning mijozini ham, o'z mijozining boshqa do'kondagi savatini
ham ko'rmaydi.

Bu **hozircha yetarli**, lekin ikkita sababdan vaqtinchalik:

1. Filtr adminkada — boshqa mijoz (mobil ilova va h.k.) shu kalit bilan
   hammasini ko'rib oladi.
2. Qatorlar soni o'sganda butun jadvalni tortib olish qimmatlashadi.

**Taklif (shoshilinch emas):** do'kon tokeni bilan kelgan so'rovda
`cart-items`, `order-items`, `orders` faqat o'sha do'kon mahsulotlariga
tegishli qatorlarni qaytarsin.

---

## Muhimlik tartibi

| № | Band | Muhimligi |
|---|---|---|
| 1 | `users/all` servis kalitini qabul qilsin | 🔴 yuqori — bo'lim shunisiz chala |
| 4 | Buyurtmada narx yozilsin | 🔴 yuqori — pul analitikasi yo'q |
| 2 | `refresh_token` javobdan olib tashlansin | 🟡 o'rta |
| 3 | `likes` da `user` bo'lsin | 🟡 o'rta |
| 5 | Holatlar enum bo'lsin | 🟢 past |
| 6 | Do'kon bo'yicha chegara | 🟢 past, kelajak uchun |

Savol bo'lsa yozing.
