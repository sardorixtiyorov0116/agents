# Backend topshirig'i №29 — xaridor mobil ilovasi uchun

**Sana:** 21.09.2026

Xaridor ilovasi (Flutter, Android) boshlandi: kirish, katalog, mahsulot sahifasi va
savat tayyor, telefonda sinaldi. Ilovani qurish jarayonida quyidagilar chiqdi.

Ochiq qolganlar alohida: `backend-tekshiruv-24-27.md` (SMS matnlari va token formati)
va `backend-topshiriq-28.md` (saytda KP).

## 1. 🔴 Xaridor tokeni yashirin do'konlar mahsulotlarini ochib qo'yadi

O'lchandi (21.09):

```
GET /api/products/all?page=1&limit=500&view=card
  guvohnomasiz               → 137 ta (Jihozvent 136, Climavent 1)
  xaridor yoki servis tokeni → 177 ta (+ Armavent 20, VENTS US 20)
GET /api/stores/all          → faqat Jihozvent va Climavent
GET /api/products/one/235    → guvohnomasiz 404 (to'g'ri)
```

Ya'ni `products/all` "kirgan foydalanuvchi = admin" deb hisoblab, e'lon qilinmagan
do'konlar mahsulotlarini ham qaytaryapti. Ilovada kirgandan keyin bu 40 ta mahsulot
bosh sahifaga chiqib qoldi. Hozircha ilova katalogni tokensiz so'raydi.

**Kerak:**
- Mahsulot, kategoriya, qidiruv va banner javoblarida **xaridor** (`users`) tokeni
  mehmon bilan bir xil ko'rsin: faqat faol do'konning faol mahsulotlari.
- Yashirin do'konlar mahsuloti faqat superadmin, o'sha do'kon admini va servis
  kaliti uchun (`alladmin` bor — shu yetadi).
- Boshqa ro'yxatlarda ham tekshiring: `lastadded`, `bysort`, `categoryslug`,
  `search`, `category/slug`, `banners/all` (banner yashirin mahsulotga bog'lanmasin).

## 2. 🔴 Qidiruv kirill yozuvida ishlamaydi

```
POST /api/products/search {"text": "ventilyator"} → 40
POST /api/products/search {"text": "JV"}          → 5
POST /api/products/search {"text": "вент"}        → 0
POST /api/products/search {"text": "Вентилятор"}  → 0
POST /api/products/search {"text": "ВЦ"}          → 0
```

Bazada `name_ru` bor ("Вентилятор ВЦ 4-75" va boshqalar), lekin qidiruv uni
topmaydi — rus tilidagi xaridorlar saytda hech narsa topa olmaydi.

**Kerak:** qidiruv `name_uz`, `name_ru`, `name_en`, model nomi (`characteristics.title`),
SAP kodi va nomi (`product_model_inside.sap_name`, `in_model_name`) bo'yicha,
katta-kichik harfga qaramasdan (`ILIKE` / `unaccent`). Kirill va lotin aralash
so'rov ham ishlasin ("ВЦ 4-75", "vts"). 1-banddagi ko'rinish qoidasi shu yerda ham.

## 3. 🔴 Xaridor uchun refresh token (mobil)

Hozir `verify-otp` `tokens.accessToken` va `tokens.refreshToken` beradi, lekin
xaridor uchun yangilash endpointi yo'q (`store-auth/refresh` faqat do'kon
hisoblariga). Access token muddati tugasa, ilova foydalanuvchini chiqarib
yuboradi — u qaytadan **pullik SMS** bilan kiradi.

**Kerak** — №22.8 dagi do'kon mexanizmi kabi:

```
POST /api/users/refresh      { "refresh_token": "…" }
→ 200 { "accessToken": "…", "refreshToken": "…" }   — rotatsiya, eskisi bekor
→ 401 — noto'g'ri, muddati o'tgan yoki qayta ishlatilgan (unda butun zanjir bekor)
```

- `verify-otp` da `client: "mobile"` kelsa (ilova 21.09 dan yuboradi): access 15 daqiqa,
  refresh **90 kun, sirpanuvchi** — har yangilashda 90 kun qaytadan boshlanadi.

**Egasining talabi (21.09):** ilovadan faol foydalanayotgan xaridor **hech qachon**
chiqarib yuborilmasin. Qayta SMS bilan kirish faqat **90 kundan ortiq ilovani
ochmagan** bo'lsa so'raladi. Ya'ni: refresh token muddati — oxirgi foydalanishdan
90 kun, oxirgi kirishdan emas.

- Refresh faqat shu hollarda bekor bo'ladi: 90 kun ishlatilmagan, foydalanuvchi o'zi
  chiqdi (`signout`), eski refresh qayta ishlatildi (o'g'irlik belgisi — butun zanjir
  bekor), yoki admin hisobni bloklagan.
- Parallel so'rovlar: ilova bir vaqtda bitta refresh yuboradi, lekin tarmoq uzilib
  javob kelmay qolsa, xuddi shu refresh bilan qayta so'rashi mumkin. Shuning uchun
  **almashtirilgan refresh'ni 30 soniya davomida qabul qiling** (xuddi o'sha yangi juftlikni
  qaytaring) — aks holda internet yomon joyda xaridor "o'g'irlik" deb chiqarib yuboriladi.
- Sayt uchun hozirgidek qoladi.
- `users/signout { refresh_token }` shu refresh'ni bekor qilsin (ilova shu
  maydon bilan yuboradi).
- Iltimos, hozirgi access token muddatini ham yozib yuboring.

## 4. 🟡 Push-bildirishnomalar xaridorga

SMS faqat ikkita (yo'lda + kod, KP tayyor). Qolganlarini ilovaga push qilamiz.

- `POST /api/devices { platform, token }` **xaridor** tokeni bilan ham ishlasinmi?
  Ishlamasa — qo'shing (hozir do'kon va kuryer uchun).
- Xaridorga push yuboriladigan hodisalar:

| Hodisa | Matn (uz) | Ochiladigan sahifa |
|---|---|---|
| KP tayyor (№25/№28) | «#62: KP tayyor — ko'rib chiqing» | `/orders/62` |
| Buyurtma holati o'zgardi | «#62 buyurtma: tasdiqlandi» | `/orders/62` |
| Kuryer yo'lga chiqdi | «Kuryer Aziz yo'lda, ~14 daqiqa» | `/track/<token>` |
| Kuryer yetib keldi (№26.4) | «Kuryer yetib keldi» | `/track/<token>` |
| Topshirildi | «#62 topshirildi. Rahmat!» | `/orders/62` |

- FCM `data` da: `type`, `order_id`, kerak bo'lsa `tracking_token`.
  Matn foydalanuvchi tilida (`users.lang` yo'q bo'lsa — uz).
- SMS ketadigan ikki hodisada push **ham** ketsin (ilova ochiq bo'lsa, SMS'ni kutmasdan).

Firebase loyihasini (FCM kaliti) biz ochamiz va sizga beramiz.

## 5. 🟢 Ma'lumot: o'zini o'ziga ota qilgan kategoriyalar

`GET /api/category/all` da **#34** «Kon-qazib olish sanoati» va **#35** «Boshqa uskunalar»
`category_id` = o'z id si. Daraxt quradigan kod aylanib qolishi mumkin (ilova buni
ildiz deb oladi). `category_id` ni `null` qiling va yangilashda `category_id = id`
ni rad eting (400).

## Tekshirish

1. Xaridor tokeni bilan `products/all` — 137 ta (Armavent, VENTS US yo'q); superadmin — 177.
2. `search "вент"`, `"ВЦ 4-75"`, `"MF-150P"` — natija bor.
3. `verify-otp` + `client: "mobile"` → `users/refresh` → yangi juftlik; eski refresh → 401.
4. Xaridor tokeni bilan `POST /devices` → 201; KP yuborilganda xaridor telefoniga push keladi.
5. `category/all` da #34, #35 `category_id: null`.
