# ⚠️ SHOSHILINCH — climavent.uz mahsulot sahifalari 500 qaytaryapti

**Aniqlangan:** 18.08.2026, brauzerdan o'lchandi.

## Qamrovi

| Sahifa | Holat |
|---|---|
| `/` | 200 ✅ |
| `/aboutus`, `/contactus`, `/faq`, `/delivery` | 200 ✅ |
| `/product/1`, `/product/50`, `/product/105` | **500 ❌** |

Ya'ni **butun mahsulot katalogi mijozlar uchun ochilmaydi.**

## BACKEND AYBDOR EMAS

Hamma endpoint 200 qaytaryapti:

```
api/products/all           200
api/products/one/50        200
api/products/one/118       200
api/product-model-inside   200
api/characteristics/one/96 200
api/category/all           200
```

Xato Vercel'dagi SSR'da (`server: Vercel`, `x-vercel-cache: MISS`).

## Xatoning aynan matni

```
require() of ES Module /var/task/node_modules/@exodus/bytes/encoding-lite.js
from /var/task/node_modules/html-encoding-sniffer/lib/html-encoding-sniffer.js
not supported.
Instead change the require of encoding-lite.js in
/var/task/node_modules/html-encoding-sniffer/lib/html-encoding-sniffer.js
to a dynamic import() which is available in all CommonJS modules.
```

Bu kod xatosi emas — **bog'liqlik (dependency) xatosi**. CommonJS paket
(`html-encoding-sniffer`) endi faqat ESM bo'lgan paketni (`@exodus/bytes`)
`require()` qilmoqchi bo'lyapti va Node buni rad etyapti.

## Ehtimoliy sabab

`html-encoding-sniffer` — `jsdom` ning bog'liqligi. `jsdom` esa odatda
**server tomonda HTML tozalash** kutubxonalari bilan keladi
(`isomorphic-dompurify`, `dompurify` + `jsdom`).

Faqat `/product/*` yiqilgani buni tasdiqlaydi: R2 dan kelgan HTML aynan shu
sahifalarda render qilinadi, boshqa sahifalarda yo'q.

**Ochig'i:** men frontend topshirig'ining 3-bandida `v-html` ni DOMPurify bilan
tozalashni tavsiya qilgandim. Agar u shundan keyin qo'shilgan bo'lsa, sabab
mening tavsiyam bo'lishi mumkin. Tavsiya to'g'ri edi (XSS xavfi bor), lekin
serverda jsdom'ga tayanadigan variantni tanlash noto'g'ri bo'lgan.

## Nima qilish kerak

### 1. HOZIR — saytni tiklash (5 daqiqa)

Vercel panelida oldingi ishlaydigan deploy'ga qaytaring:
**Deployments → oxirgi ishlagan versiya → «Promote to Production»**.

Mijozlar sayti tiklanadi, keyin xotirjam tuzatasiz.

### 2. KEYIN — to'g'ri tuzatish

Serverda jsdom'ga tayanadigan tozalagichdan voz keching. Uchta yo'l:

**a) Tozalashni faqat brauzerda bajarish (eng oddiy)**

```js
// faqat klientda ishlaydi, jsdom kerak emas
const toza = ref('')
onMounted(async () => {
  const DOMPurify = (await import('dompurify')).default
  toza.value = DOMPurify.sanitize(xomHtml)
})
```
`<ClientOnly>` ichida render qiling.

**b) jsdom talab qilmaydigan kutubxona**

`sanitize-html` (htmlparser2 asosida) yoki `xss` — ikkalasi ham serverda
jsdom'siz ishlaydi.

**c) Agar `isomorphic-dompurify` qolishi shart bo'lsa**

`package.json` ga versiyani majburlash:
```json
"overrides": {
  "html-encoding-sniffer": "<4"
}
```
yoki `nuxt.config` da `build.transpile` / `nitro.externals` ni sozlash.
Bu eng mo'rt yo'l — a yoki b afzal.

### 3. Tekshirish

```
/product/50   -> 200 va narx «1 881 120 UZS» ko'rinsin
/product/37   -> 200
/             -> 200
```

## Eslatma

Bu xato marshrut muammosi (frontend topshirig'i, 0-band) bilan ALOQASI YO'Q.
Ular ikki alohida ish. Avval sayt tiklansin, keyin 0-band.
