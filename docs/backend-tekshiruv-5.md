# Backend tekshiruvi №5 — 4-topshiriqdan keyin

**Tekshirilgan:** `https://climavent-back-production.up.railway.app`
**Sana:** 2026-08-06, kechqurun (4-topshiriq berilganidan bir necha soat keyin)
**Usul:** faqat o'qish va zararsiz probalar.

---

## Qisqacha

Dasturchi bir necha soat ichida **4-topshiriqning katta qismini** bajardi.
Bu jiddiy ish — pastda har biri tekshirilgan holda.

---

## BAJARILGAN ✅

### 1.2 `product_models` da `sap_name`

Endi SAP kodi **modelning o'zida**:

```json
{
  "id": 44, "name": "КСК 113-2-01",
  "price": null, "currency": "UZS",
  "price_updated_at": null, "price_valid_until": null,
  "sap_name": null, "quantity": null
}
```

To'ldirilgani: **183 / 1482**. Bu eski `product_model_inside` jadvalining
buzuq bog'lanishini chetlab o'tish imkonini beradi.

### 1.3 Narx maydoni tartibga solindi

| | Ertalab | Hozir |
|---|---|---|
| Tip | `string` | `int` / `null` |
| Buzuq qiymat (`"."`) | 2 ta | **0** |
| `0` va `null` ajratilganmi | yo'q | **ha** (1458 ta `null`) |
| `currency` | yo'q | **bor** (1482 ta, UZS) |
| `price_updated_at` | yo'q | **bor** |
| `price_valid_until` | yo'q | **bor** |

Bu bizning tomonda muhim: endi «narx kiritilmagan» va «narx nol»
aralashib ketmaydi.

### 2.1 `quantity` maydoni qo'shildi

`product_models` da maydon **bor**. Ma'lumot hali to'ldirilmagan
(0 / 1482) — quyida.

### 2.2 Ommaviy narx yuklash endpointi

```
POST /api/product-models/bulk-price  →  401 (guvohnomasiz)
```

Endpoint mavjud va himoyalangan. Narxlar Excel'dan yuklanishi mumkin.

### 2.3 `product-model-inside` sahifalash

```
?limit=5&page=1  →  5 ta    ✅ (ertalab 932 ta qaytardi)
```

### 2.4 `/products/all` standart chegara

```
Ertalab:  137 ta, 698 KB
Hozir  :   20 ta, 101 KB
```

### 2.6 `updatedAfter` filtri

```
?updatedAfter=2026-08-06T00:00:00Z  →  1 ta
```

Ishlaydi. Inkremental sinxronizatsiya endi mumkin.

### Xavfsizlik — o'zgarmagan, hammasi joyida

`reviews/all`, `order-items/all`, `cart-items/*`,
`selected-to-checkout/deletebyuser` — hammasi **401**.
Sarlavhalar (HSTS, nosniff, frame-options), tezlik cheklovi (120) bor,
`x-powered-by` yo'q. `500` → `400` ishlaydi.

---

## QOLGAN ❌

### 1. `sap_name` faqat 183 / 1482 to'ldirilgan

Maydon bor, ma'lumot chala. Natijada narxi bor 24 modeldan
**faqat 9 tasiga** SAP kodi topilyapti — ertalabgi bilan bir xil.

**Kerak:** qolgan modellarga SAP kodini kiritish. Eski
`product_model_inside` jadvalida 932 ta kod bor — ularni
normallashtirilgan nom bo'yicha ko'chirish mumkin (4-topshiriq,
1.1-bo'limdagi SQL).

### 2. `quantity` bo'sh — 0 / 1482

Maydon qo'shilgani yaxshi, lekin ma'lumotsiz u ishlamaydi.
«ВК-250С dan nechta bor?» — hamon javob bera olmaymiz.

Qoldiq qayerdan keladi (SAP? ombor tizimi?) — aniqlanishi kerak.

### 3. `product-models/all` sahifalanmaydi

```
/api/products/all?limit=20        →  20 ta     ✅
/api/product-models/all?limit=10&page=1  →  1482 ta  ❌
```

`products` tuzatilgan, `product-models` esa qolib ketgan. Har chaqiruvda
352 KB.

### 4. 1.1 — eski jadval bog'lanishi

`product_model_inside`: **932 / 932 hamon noto'g'ri modelga ishora
qiladi.**

Lekin bu endi **ustuvor emas**: `sap_name` modelga ko'chgach, u jadval
kerak bo'lmay qoladi. Uni tuzatish o'rniga — qolgan kodlarni modelga
ko'chirish (1-band) foydaliroq.

### 5. 1.4 — takroriy model nomlari

11 ta nom hamon ikki martadan takrorlanadi.

### 6. 2.5 — `narx_turi` belgisi yo'q

`standart` / `buyurtma` ajratilmagan. Nostandart mahsulot hamon
«narxi kiritilmagan» bo'lib ko'rinadi.

### 7. Shubhali narx

`ВР 6-28-4-1-0,37-1500` = **14 so'm**. Kiritish xatosi, tuzatilmagan.

---

## Bizning tomonda qilingan ish

`integrations/climavent_client.py` yangi maydonga o'tkazildi:

- `sap_kodlari()` endi **ikki manbadan** yig'adi:
  1. `product_models.sap_name` — asosiy;
  2. `product_model_inside` — zaxira (yangi maydon to'ldirilmaguncha).
- Yangi `modellar()` metodi — narx, valyuta, SAP kodi va qoldiq bir
  joydan olinadi.

Natija: SAP xaritasi **1177 yozuv** (avval faqat eski jadvaldan edi).
Narxli modellar bo'yicha qamrov o'zgarmadi (9/24) — chunki narxi bor
modellarning ko'pida `sap_name` hali yo'q.

---

## Keyingi ustuvorlik

| # | Ish | Kim | Nega |
|---|---|---|---|
| 1 | Qolgan `sap_name` larni to'ldirish | dasturchi | KP da rasmiy kod chiqishi uchun |
| 2 | **Narxlarni yuklash** (endpoint tayyor) | kompaniya | Eng katta to'siq |
| 3 | `quantity` ni to'ldirish | dasturchi + ombor | Savdoning eng ko'p savoli |
| 4 | `product-models/all` sahifalash | dasturchi | 352 KB har chaqiruvda |
| 5 | `narx_turi` belgisi | dasturchi | Nostandart tovar xato bo'lib ko'rinmasin |
| 6 | 14 so'mlik narx va takroriy nomlar | katalog admini | Kontent |

Endpoint tayyor bo'lgani uchun **2-band endi kompaniya tomonida**:
buxgalter SAP'dan Excel chiqarsa, narxlar bir kunda yuklanadi.
