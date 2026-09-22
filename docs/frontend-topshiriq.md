# Frontend topshirig'i №1 — climavent.uz

**Sana:** 18.08.2026
**Sayt:** https://climavent.uz (Vue / Element Plus, Vercel'da)
**Backend:** https://climavent-back-production.up.railway.app

Quyidagilar jonli saytda tekshirilgan (taxmin emas).

---

## 0. ⚠️ ENG MUHIMI — sahifa almashganda eski sahifa ekranda qolyapti

### Takrorlash (men shunday takrorladim)

1. `https://climavent.uz/` ni to'liq yuklang.
2. Katalogdagi istalgan mahsulot kartasiga bosing (men «External grille RVN» ni tanladim).

### Natija

| Nima | Holat |
|---|---|
| URL | `/product/105` — **to'g'ri o'zgardi** |
| Sahifa sarlavhasi (`<title>`) | «External grille RVN \| Climavent UZ» — **to'g'ri o'zgardi** |
| Ekrandagi mazmun | **BOSH SAHIFA qolgan** — o'sha 40 ta karta turibdi |
| «Add to cart», «Production time», «Shipping» | **yo'q** — mahsulot sahifasi umuman render bo'lmagan |
| Mahsulot 105 uchun API so'rovi | **yuborilmagan** |

4 soniya kutdim — o'zgarmadi. Ya'ni bu «sekin yuklanyapti» emas.

Teskari tomoni ham shunday: mahsulot sahifasidan logotipga bosib bosh sahifaga
qaytsam, URL `/` bo'ladi, lekin ekranda mahsulot sahifasi qoladi (karta soni 0).

### Bu aynan siz aytgan xato

«Mahsulotga kirsam oldingi mahsulotning narxi ko'rinib qolyapti» — sabab shu:
**yangi sahifa render bo'lmaydi, eskisi ekranda qoladi.** Narx eskisiniki
bo'lgani uchun mijoz noto'g'ri raqamni ko'radi. Bu narx xatosi emas, marshrut xatosi.

### Server tomoni AYBDOR EMAS

`/product/50` ni ketma-ket 6 marta so'radim — **6 tasida ham** narx ma'lumoti
(`156.76`) va `insides` massivi HTML ichida bor edi. Javob hajmi ham bir xil
(462 104 bayt). Ya'ni SSR to'g'ri ishlaydi, muammo brauzerdagi render/hydration da.

### Qidirish kerak bo'lgan joylar

1. `<NuxtPage>` / `<router-view>` da **`:key`** yo'qmi? Bir xil komponent boshqa
   parametr bilan qayta ishlatilsa Vue uni yangilamaydi.
   Yechim: `<NuxtPage :key="$route.fullPath" />`.
2. Mahsulot ma'lumoti `onMounted` da olinayotgan bo'lsa — u faqat bir marta
   ishlaydi. `watch(() => route.params.id, ...)` yoki `useAsyncData` ning
   `watch` parametri kerak.
3. Karta bosilganda `router.push` ishlatilyaptimi yoki `history.pushState`?
   Ikkinchisi Vue Router'ni xabardor qilmaydi — URL o'zgaradi, komponent yo'q.
   (Sahifada mahsulot kartalari `<a href>` emas, `<div class="products-col">` —
   ular `<NuxtLink>` ga o'tkazilsa, muammoning katta qismi o'z-o'zidan yopiladi
   va SEO ham yaxshilanadi.)
4. Konsolda 404 xatosi bor — tekshirilsin, o'sha yiqilgan chunk router'ni
   to'xtatib qo'ygan bo'lishi mumkin.

### Qabul mezoni

- Har marshrut almashganda yangi sahifa **to'liq** render bo'lsin.
- Bitta mahsulotdan boshqasiga o'tganda narx, model ro'yxati, xususiyat va rasm —
  **hammasi** yangilansin, eskisidan hech narsa qolmasin.
- Orqaga/oldinga tugmalari ham shunday ishlasin.

---

## 1. Katalog ro'yxatida narx ko'rinmaydi — «Цена по запросу»

### Holat

- **Mahsulot sahifasi ISHLAYDI.** `/product/50` da narx to'g'ri chiqadi:
  `1 881 120 UZS` = `156.76 $ × 12 000`. Ya'ni front `insides[].price` ni
  o'qiydi va kursga ko'paytiradi — mantiq to'g'ri qurilgan.
- **Bosh sahifa va kategoriya ro'yxatida** esa hamma mahsulot
  «Цена по запросу» / «Price on request» deb turibdi — narxi bor mahsulotlarda ham
  (РВН, РВИ, РВ-1, 4РВП, ДКСп, КС, RSK, КИД, ВЦ 4-75 …).

### Sabab

Ro'yxat `POST /api/products/categoryslug` dan keladi va **o'sha javobda `insides` YO'Q**:

```
products/one/{id}     -> characters[].insides[]  ✅
categoryslug          -> characters[]            ❌ insides yo'q
```

`product.price` va `models[].price` esa `null` — narx faqat `insides[].price` da.

### Nima qilish kerak

1. Backend `categoryslug` javobiga `insides` ni qo'shadi (backend topshirig'i №7, 2-band).
   **Shu bajarilmaguncha front tomondan tuzatib bo'lmaydi.**
2. Front tomonda: karta narxini `characters[].insides[].price` ning **minimumidan**
   hisoblang va `«… dan boshlab»` deb ko'rsating — chunki bitta mahsulotda
   o'nlab variant va o'nlab narx bor.
   Misol: ВЦ 4-75 -> eng arzoni 156,76 $ -> «1 881 120 so'mdan boshlab».
3. `insides` bo'sh yoki hamma `price = null` bo'lsagina «Цена по запросу» yozilsin.

**Muhim:** «dan boshlab» so'zi tushib qolmasin. Aks holda mijoz eng arzon
variantning narxini butun mahsulotning narxi deb tushunadi.

---

## 2. Xususiyat bo'limida `pub-….r2.dev/…` havolasi chiqib qolyapti

### Ma'lumot qanday saqlangan

Backend matnli maydonlarni bazada emas, **R2 da** saqlaydi. API faqat havola qaytaradi:

| Maydon | Nima |
|---|---|
| `characters[].content` | HTML matn (R2 havolasi) |
| `characters[].contentJson` | ProseMirror JSON (R2 havolasi) |
| `products.opisaniya / naznacheniya / markirovka / sizes` (+ `…Json`) | shu tartibda |

Fayl mazmuni **JSON bilan o'ralgan matn**:
```
"<p style=\"text-align: center;\"><strong>Технические характеристики</strong></p>…"
```
Ya'ni `res.text()` emas, `res.json()` qilish kerak (yoki `JSON.parse`).

R2 brauzerdan o'qiladi — CORS ochiq, tekshirdim (HTTP 200).

### Muammo

Bu maydonlar ba'zan **havolaning o'zi sifatida** ekranga chiqyapti. Ya'ni qayerdadir
qiymat fetch qilinmasdan to'g'ridan-to'g'ri render qilinyapti.

Backendda 43 ta nosoz yozuv bor (backend topshirig'i №7, 3.1-band):
- 40 tasida R2 fayli **0 bayt**;
- 2 tasida havola o'rniga `"."` yoki `{}` yozilgan (`/product/2`);
- 1 tasi deyarli bo'sh.

Bu holatlarda `fetch` muvaffaqiyatsiz tugaydi yoki bo'sh qaytadi.

### Nima qilish kerak

1. **Har bir R2 maydoni uchun bitta umumiy yordamchi** yozilsin, masalan
   `useRemoteHtml(url)`:
   - `url` bo'sh, `null`, `{}` yoki `http` bilan boshlanmasa -> **hech narsa
     chiqarmaydi** (havolani ham chiqarmaydi);
   - `fetch` -> `res.json()` -> HTML matn;
   - `fetch` yiqilsa yoki javob bo'sh bo'lsa -> «Ma'lumot mavjud emas» ko'rsatilsin,
     **havola hech qachon ekranga chiqmasin**;
   - yuklanayotganda skelet/spinner.
2. Shu yordamchi `content`, `contentJson`, `opisaniya`, `naznacheniya`,
   `markirovka`, `sizes` — **hammasiga** qo'llanilsin. Hozir kamida bittasida
   xom qiymat render qilinmoqda.
3. HTML `v-html` bilan chiqariladi — **sanitizatsiya** qo'yilsin (DOMPurify yoki
   shunga o'xshash). Hozir R2 dagi ixtiyoriy HTML to'g'ridan-to'g'ri sahifaga
   tushmoqda; katalog administratori orqali `<script>` kirsa XSS bo'ladi.

### Qayerda sinash kerak

| Sahifa | Nima ko'rinishi kerak |
|---|---|
| `/product/37` | «Characteristic» — hozir bo'm-bo'sh (16 ta fayl 0 bayt) |
| `/product/2` | `content` = `"."`, `sizesJson` = `{}` |
| `/product/94`, `/product/31`, `/product/40`, `/product/4` | bo'sh fayllar |
| `/product/50` | to'g'ri holat — bularni buzmaslik kerak |

---

## 3. Valyuta almashtirgichi

Saytda `UZS` / `USD` tugmalari bor. Narx bazada **DOLLARDA** turibdi, so'm esa
kursga ko'paytirib hisoblanadi.

Tekshirilsin:
1. Kurs qayerda turibdi va u backenddagi/Exceldagi **12 000** bilan bir xilmi?
   Kurs kodda qotib qolmasin — sozlamadan olinsin.
2. `USD` tanlanganda bazadagi son **o'zgarishsiz** ko'rsatilsinmi (156,76 $) —
   ya'ni so'mdan qaytarib bo'linmasin (ikki marta yaxlitlash xatosi chiqadi).
3. KP va sayt bitta kursni ishlatsin.

---

## Ustuvorlik

| № | Ish | Kim |
|---|---|---|
| 0 | **Marshrut almashganda sahifa render bo'lmasligi** | front — ENG MUHIMI |
| 1 | `categoryslug` ga `insides` | backend (bloklaydi) |
| 2 | Ro'yxatda «… dan boshlab» narx | front |
| 3 | R2 maydonlari uchun umumiy yordamchi + havola chiqmasligi | front |
| 4 | `v-html` sanitizatsiyasi | front (xavfsizlik) |
| 5 | Kurs bitta manbadan | front |

## Foydali ma'lumot

- Mahsulot sahifasi URL shakli: `/product/{id}`
- Narxi bor mahsulotlar: ВЦ 4-75 (50), ВЦ 14-46, РВН, РВИ, РВ-1, 4РВП, ВКП,
  ВКПП, ПВН, ПВФ, КС, RSK, КИД, КО, КОГ, КВУ
- Jami: `product_model_inside` da 941 qatordan 299 tasida narx bor
