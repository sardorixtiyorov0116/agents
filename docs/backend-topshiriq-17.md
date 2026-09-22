# Backend topshirig'i №17 — CORS (qisqa)

**Kimga:** Climavent backend
**Sana:** 15.09.2026

№15 va №16-tekshiruv javoblari production'da tekshirildi — hammasi to'g'ri,
rahmat. Bitta band qolib ketdi.

## 1. 🔴 Adminka domenini CORS ro'yxatiga qo'shing

```
https://climavent-marketplace-admin.vercel.app
```

Bu bizning Next.js adminka. Docs'dagi `climavent-admin.vercel.app` — boshqa
ilova ("ADMIN PANEL - Climavent").

Hozirgi holat (15.09.2026):

```
OPTIONS /api/seller-applications
Origin: https://climavent-marketplace-admin.vercel.app
-> 200, access-control-allow-origin YO'Q
```

**Nega kerak:** sotuvchi ariza formasi adminkada —
`/sotuvchi-bolish`. Brauzer hujjat yuklash, ariza va to'ldirishni
to'g'ridan-to'g'ri backendga yubora olishi kerak. CORS yopiqligi uchun forma
hozir adminka serveri orqali ishlayapti, bu esa:

- faylni **4 MB** bilan cheklaydi (Vercel so'rov chegarasi);
- ariza cheklovini (soatiga 5 ta) va `offer_ip` ni **Vercel IP** siga
  yozishi mumkin.

Domen qo'shilgach adminkada hech narsa o'zgartirish kerak emas — forma
o'zi to'g'ridan-to'g'ri yo'lga o'tadi.

## 2. Savol: `X-Forwarded-For` hisobga olinadimi?

1-band bajarilguncha adminka serveri sotuvchi IP'sini `X-Forwarded-For`
va `X-Real-IP` sarlavhalarida yuboradi. Backend (`trust proxy`, throttler)
shuni o'qiydimi yoki Railway proksisi ortidagi manzilnimi? Bir og'iz
javob yetadi.

## 3. 🔴 O'chirilgan va nofaol hisob tokeni ishlashda davom etadi

15.09.2026 da tekshirildi (vaqtinchalik superadmin, keyin o'chirildi):

| Qadam | `GET /seller-applications/all` | `GET /store-auth/me` |
|---|---|---|
| Hisob faol | 200 | — |
| `is_active: false` qilingandan keyin | **200** | 401 |
| Hisob o'chirilgandan keyin | **200** | 401 |
| O'chirilgandan keyin yozish (`PATCH /seller-applications/update/999999`) | **404** — ya'ni guvohnoma o'tdi | — |

Ya'ni guard faqat JWT imzosi va ichidagi `role` ni tekshiradi, hisob
bazada borligini va faolligini — yo'q. Faqat `/store-auth/me` tekshiradi.

**Oqibat:** ishdan bo'shagan xodim yoki bloklangan do'kon admini tokeni
muddati tugaguncha hamma narsani qila oladi — superadmin bo'lsa arizalar,
pasport havolalari, do'konlar. "Nofaol qilish" amalda hech narsani
to'xtatmaydi. Adminka sessiyasi 12 soat yashaydi, token muddati
qanchaligini bilmayman.

**Taklif:** guard har so'rovda `store_users` dan `id` bo'yicha `is_active`
ni tekshirsin (yoki tokenda `token_version` va hisobda hisoblagich —
parol almashtirilganda, nofaol qilinganda, o'chirilganda oshadi). Yo'q
yoki nofaol bo'lsa — 401.

## 4. 🟡 Saytda chegirma foizi 1% kam chiqishi mumkin

`floor((1 − sale/price) × 100)` suzuvchi nuqtada aniq foizni bir birlikka
kamaytiradi: price **2509.6**, sale **2007.68** (aniq 20%) →
`0.19999…` → **−19%**. Adminkada shu sinovda aynan shunday chiqdi va
`+ 1e-6` bilan tuzatildi. Sayt ham pastga yuvarlaydi (№15 javobi, 3-savol)
— u yerda ham kichik zaxira qo'shing, aks holda "−20%" tugmasi bilan
qo'yilgan aksiya kartochkada "−19%" bo'ladi.

## 5. Tozalash (ixtiyoriy)

Sinov arizasi **#19** (`zz-sinov-16b`, STIR 999016016, holati `rejected`)
bazada qolgan — №16 sinovidan keyin yaratilgan. O'chirib yuborsangiz bo'ladi.

---

**Tekshirish:** 1-band tayyor bo'lsa, shu so'rovda
`access-control-allow-origin: https://climavent-marketplace-admin.vercel.app`
qaytishi kerak:

```bash
curl -s -o /dev/null -D - -X OPTIONS \
  https://climavent-back-production.up.railway.app/api/seller-applications \
  -H "Origin: https://climavent-marketplace-admin.vercel.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```
