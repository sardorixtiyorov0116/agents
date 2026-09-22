# Sayt topshirig'i №2 — SEO va katalog ko'rinishi

**Sana:** 16.09.2026 · Huquqiy hujjatlar, cookie va rozilik ishi qabul
qilindi, jonli tekshirildi — rahmat. Quyidagilar 16.09 tekshiruvida topildi.

## 1. 🔴 Mahsulot sahifasida meta tavsif o'rniga fayl havolasi

`/product/1` da:

```
<meta name="description" content="https://pub-80900f61c8cc4ae4925918001a11ff3b.r2.dev/bcd0e0e6-...">
```

Ya'ni R2 fayl havolasi. Google qidiruv natijasida shu ko'rinadi.

**Kerak:** tavsif matnidan olingan ~160 belgi (HTML teglari tozalangan).
Manba tartibi: `description_short_{til}` → tavsif faylining matni →
mahsulot nomi + kategoriya. `og:description` ham shunday.

## 2. 🔴 Sitemapda mahsulotlar yo'q

`sitemap.xml` da 14 ta statik sahifa. Mahsulot, kategoriya va do'kon
sahifalari yo'q — Google 137 ta mahsulotni ko'rmaydi.

**Kerak:** `/product/:id` (137 ta), `/category/:slug`, `/stores/:slug`
qo'shilsin, `lastmod` = `updatedAt`. Nofaol do'kon va mahsulotlar
chiqmasin. `robots.txt` dagi `Sitemap:` qatori joyida — o'zgartirish kerak
emas.

## 3. 🟡 Sahifa tili har doim `en-US`

`<html lang="en-US">` — sahifa o'zbekcha yoki ruscha bo'lganda ham.
Qidiruv tizimi tilni noto'g'ri aniqlaydi.

**Kerak:** `lang` joriy tilga mos bo'lsin (`uz`, `ru`, `en`), sahifalarga
`hreflang` havolalari qo'shilsin (hozir 0 ta).

## 4. 🟡 Narxi yo'q mahsulotlar

137 mahsulotdan 106 tasida narx yo'q. Bu bizning ma'lumot muammomiz, lekin
saytda shu holat foydali chiqishi kerak: «narxi so'rov bo'yicha» yonida
bog'lanish yoki so'rov qoldirish tugmasi bo'lsa, lead yo'qolmaydi.
Hozir mahsulot sahifasida «Bog'lanish» bor — ro'yxatda ham ko'rinsinmi,
o'zingiz qaraysiz.

## 5. 🟢 Banner havolasi

Backendga `link`, `is_active`, `sort_order` qo'shish so'raldi (№19, 5-band).
Tayyor bo'lgach banner bosilganda o'sha havolaga o'tsin, nofaoli chiqmasin.

## 6. 🟡 Yangi versiyani majburiy tasdiqlatish

Oferta yoki maxfiylik siyosati yangilansa, eski foydalanuvchi yangi
shartlarni ko'rmaydi. Backenddan shu signal so'raldi (№20, 2-band):
mavjud foydalanuvchi kirganda `consent_required: true` va joriy
versiyalar qaytadi.

Kerak: kirishda shunday javob kelsa, kod so'ralgandan keyin (yoki kod
bilan birga) tasdiq oynasi chiqsin — matn 3-banddagi bilan bir xil,
havolalar `/foydalanish-shartlari` va `/maxfiylik`. Tasdiqlanmasa
kirish yakunlanmaydi. Backend tayyor bo'lgach aytamiz.

## 7. 🟢 Tekshirish

- `/product/1` meta tavsifi — matn, havola emas.
- `sitemap.xml` — 150+ URL.
- Til almashtirilganda `<html lang>` o'zgaradi.
