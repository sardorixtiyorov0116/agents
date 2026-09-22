# Backend topshirig'i №6 — tuzatish

**Kimga:** Climavent backend dasturchisiga
**Sana:** 2026-08-11
**Server:** `https://climavent-back-production.up.railway.app`
**Tekshirish usuli:** faqat o'qish. Hech narsa yaratilmadi va
o'zgartirilmadi. `POST /api/users/login` ataylab chaqirilmadi — u
haqiqiy pullik SMS yuboradi.

---

## Avval — rahmat

5-topshiriqning katta qismi bajarilgan. Jonli tekshirdim:

| Nima | Holat |
|---|---|
| `airflow_m3h`, `pressure_pa` maydonlari | ✅ qo'shilgan |
| `bulk-price` DTO (`BulkPriceItemDto`) | ✅ to'g'rilangan |
| Sahifalash — 5 ta endpointda | ✅ ishlaydi, takror yo'q |
| `limit=-1`, `limit=0`, `limit=abc` → 400 | ✅ |
| `page=-1`, `page=0` → 400 | ✅ |
| `characteristics/all` | ✅ qo'shilgan |
| Xavfsizlik — 18 ta endpoint | ✅ hammasi 401 |
| Tezlik (`limit=200`) | ✅ 253 ms |

Quyida **4 ta ish** qoldi. Birinchisi yangi va eng muhimi.

---

## 1. 🔴 `airflow_m3h` — 17 ta qiymat noto'g'ri

### Muammo

To'ldirilgan **122** qiymatdan **17 tasi xato**. Xato tasodifiy emas,
**tizimli** — aylanish tezligi (`об/мин`) havo sarfi o'rniga yozilgan.

### Qanday aniqlandi

Har bir qiymat mahsulotning **o'z texnik jadvali** bilan solishtirildi.
Jadval `products.characters[].contentJson` → R2 dagi hujjatda turadi —
ya'ni bu tashqi manba emas, sizning katalogingizning o'zi.

Ikkala manbada ham qiymat bor **91** model topildi:

```
mos keladi : 74
ZID        : 17
```

### Zid ro'yxati

| Model | Bazadagi `airflow_m3h` | Jadvalda haqiqatda (m³/soat) | Mahsulot |
|---|---|---|---|
| `ВНР-10-22-1000` | **22** | 20 050 – 40 100 | ВНР-ДУ |
| `ВКОП-5` | 1 000 | 1 120 – 4 500 | ВКОП |
| `ВКОП-6,3` | 1 000 | 2 200 – 9 100 | ВКОП |
| `ВКОП-10` | 750 | 7 060 – 28 400 | ВКОП |
| `ВКР-4` | 1 000 | 1 250 – 2 950 | ВКР |
| `ВКР-6,3` | 1 000 | 5 200 – 10 500 | ВКР |
| `ВО 12-300-5` | 1 500 | 4 800 – 7 100 | ВО 12-300 |
| `ВО 12-300-6,3` | 1 000 | 6 150 – 10 000 | ВО 12-300 |
| `ВО 30-160-9` | 950 | 9 800 – 16 195 | ВО 30-160 |
| `ВО 30-160-10` | 960 | 13 425 – 22 355 | ВО 30-160 |
| `ВО 30-160-11,2` | 950 | 18 800 – 31 140 | ВО 30-160 |
| `ВР 6-28-7,1` | 1 500 | 2 520 – 7 560 | ВР 6-28 |
| `ВР 6-28-9` | 1 500 | 5 400 – 16 200 | ВР 6-28 |
| `ВЦП 6-46-5` | 1 500 | 2 130 – 9 040 | ВЦП 6-46 |
| `ВЦП 6-46-6,3` | 1 000 | 3 040 – 12 900 | ВЦП 6-46 |
| `ВЦП 6-46-8` | 1 000 | 6 030 – 20 100 | ВЦП 6-46 |
| `ВЦП 6-46-10` | 1 000 | 8 500 – 34 000 | ВЦП 6-46 |

### Sabab — ikki dalil

**1. Qiymatlar takrorlanadi.**

```
ВЦП 6-46-5    -> 1500
ВЦП 6-46-6,3  -> 1000
ВЦП 6-46-8    -> 1000
ВЦП 6-46-10   -> 1000
```

Bular **turli o'lchamdagi** g'ildiraklar. Havo sarfi turlicha bo'lishi
SHART (jadvalda: 2 130 → 3 040 → 6 030 → 8 500). Bir xil qiymat
takrorlanishi — bu havo sarfi emas, **dvigatel tezligi**:
750, 950, 960, 1000, 1500 — klassik `об/мин` qiymatlari.

**2. `ВНР-10-22-1000` → 22.**

Bu son model **nomidan** olingan (`ВНР-10-**22**-1000`).
22 m³/soat — sanoat ventilyatori emas, stol ventilyatoridan ham kichik.

### Nima qilish kerak

1. **Migratsiya skriptini ko'ring.** Jadvaldan qaysi ustunni
   o'qiyotganini tekshiring: kerakligi `Производительность, м3/ч`,
   olinayotgani esa `Частота вращения, об/мин` ga o'xshaydi.

2. **Shu 17 ta modelni qayta to'ldiring** (yuqoridagi jadvalning
   3-ustuni — jadvaldagi haqiqiy qiymat oralig'i; bitta son kerak
   bo'lsa, maksimalini oling).

3. **Tekshiruv qo'ying.** Sanoat ventilyatorining havo sarfi
   500 m³/soatdan kam bo'lmaydi:

   ```sql
   ALTER TABLE product_models
     ADD CONSTRAINT airflow_mantiqiy
     CHECK (airflow_m3h IS NULL OR airflow_m3h >= 500);
   ```

   Shunday qoida bo'lganda bu 17 ta xato bazaga umuman kirmasdi.

4. **O'zingiz tekshirib ko'ring** — bir xil mahsulotda takrorlanuvchi
   qiymat qidiring:

   ```sql
   SELECT p.name_ru, m.airflow_m3h, count(*) AS nechta,
          string_agg(m.name, ', ' ORDER BY m.name) AS modellar
   FROM   product_models m
   JOIN   products p ON p.id = m.product_id
   WHERE  m.airflow_m3h IS NOT NULL
   GROUP  BY p.name_ru, m.airflow_m3h
   HAVING count(*) > 1
   ORDER  BY count(*) DESC;
   ```

   Bitta mahsulotda 3–4 ta model bir xil havo sarfiga ega bo'lsa —
   deyarli har doim xato.

### `pressure_pa` ni ham tekshiring

Hozir 72 ta to'ldirilgan. Ular alohida solishtirilmadi, lekin xuddi
shu skript to'ldirgan bo'lsa — u yerda ham xato bo'lishi ehtimoli
yuqori.

### Biz nima qildik (siz tuzatgunizcha)

Zid qiymat aniqlansa **jadval qiymati olinadi**, bazadagisi esa
"ishonchsiz" deb belgilanadi — ya'ni noto'g'ri raqam tijorat taklifiga
tushmaydi. Siz tuzatgach bu himoya o'z-o'zidan ishlamay qo'yadi.

---

## 2. 🔴 `product_model_inside` — TO'RTINCHI marta

Bu 2-, 3-, 4- va 5-topshiriqda ham bor edi. Holat o'zgarmagan:

```
yozuv jami                 : 941
product_model_id TO'G'RI   :   0     ← nol
nom bo'yicha tuzatiladi    : 184
qo'lda ko'rish kerak       : 757
```

Ya'ni SAP kodi **noto'g'ri modelga** bog'langan — hammasi. Shuning
uchun tijorat taklifida SAP kodi ko'rsatilmaydi.

```json
{
  "sap_name":         "ВЦ 4-75-2,5-О-1-0,12/1500",
  "in_model_name":    "ВЦ 4-75-2,5-1-0,12/1500",
  "product_model_id": 96
}
```
`product_model_id = 96` → `КВН 250-2-1` (suvli isitgich). Aloqasi yo'q.

**Migratsiya:**

```sql
-- 1-qadam: normallashtirilgan nom bo'yicha qayta bog'lash.
-- "ПВН 500-300/2" -> "ПВН5003002"
UPDATE product_model_inside AS i
SET    product_model_id = m.id
FROM   product_models AS m
WHERE  regexp_replace(upper(i.in_model_name), '[\s\-/_.]', '', 'g')
     = regexp_replace(upper(m.name),          '[\s\-/_.]', '', 'g');
```

```sql
-- 2-qadam: mos kelmaganini ro'yxat qiling — ular qo'lda ko'riladi.
SELECT i.id, i.sap_name, i.in_model_name
FROM   product_model_inside i
WHERE  NOT EXISTS (
         SELECT 1 FROM product_models m
         WHERE regexp_replace(upper(i.in_model_name), '[\s\-/_.]', '', 'g')
             = regexp_replace(upper(m.name),          '[\s\-/_.]', '', 'g')
       );
```

Shu 757 tani ro'yxat qilib bering — savdo bo'limi bilan qo'lda
ko'ramiz. Hozircha hech kim buni qilmayapti, shuning uchun SAP kodi
hech qachon ishlamaydi.

⚠️ **Diqqat — kasr verguli.** Migratsiyada `,` va `.` ni **olib
tashlamang**. Biz shu xatoni qilib, keyin tuzatdik:

```
КЦКП-3,15  ->  "КЦКП315"
КЦКП-31,5  ->  "КЦКП315"     <- bir xil bo'lib qoldi!
```

Natijada 3 150 m³/soat lik qurilmaga 31 500 biriktirilgan edi.
Yuqoridagi SQL da `[\s\-/_.]` — vergul YO'Q, ataylab.

---

## 3. 🟡 Narx — 25 / 1482 (1.6%)

`POST /api/product-models/bulk-price` tayyor va DTO to'g'ri. Faqat
SAP dan eksport qilib yuborish qoldi.

```
narxi bor          :   25 / 1482
price_valid_until  :    1 / 1482
```

`price_valid_until` ni ham to'ldiring — tijorat taklifida "narx amal
qilish muddati" bo'lishi kerak, bu hujjatning majburiy qismi.

Bu band **sizga emas, kompaniyaga** tegishli bo'lishi mumkin — lekin
yo'l tayyorligini yozib qo'ydim.

---

## 4. 🟡 `quantity` — 0 / 1482

`product_models.quantity` hamma yozuvda `NULL`.
`products.quantity` esa 93 tasida "1" — qo'lda qo'yilgan raqam,
haqiqiy ombor qoldig'i emas.

Agent "bu mahsulotdan nechta bor?" degan savolga javob bera olmaydi.
SAP dan qoldiq kelsa `product_models.quantity` ga yozilsin — narx
bilan bir vaqtda, bitta `bulk` chaqiruvda bo'lsa yaxshi bo'lardi.

---

## Muhimlik tartibi

| # | Ish | Nega |
|---|---|---|
| 1 | `airflow_m3h` — 17 ta qiymat | **Noto'g'ri raqam mijozga ketishi mumkin** |
| 2 | `product_model_inside` migratsiyasi | SAP kodi umuman ishlamaydi |
| 3 | Narx + `price_valid_until` | Har taklif narxsiz chiqadi |
| 4 | `quantity` | "Nechta bor?" savoliga javob yo'q |

1-band eng shoshilinch: qolganlari **ma'lumot yo'qligi**, birinchisi
esa **noto'g'ri ma'lumot**. Yo'qligi ko'rinadi, noto'g'risi ko'rinmaydi.

---

## Tuzatgandan keyin

Aytib qo'ying — men qayta tekshirib, natijani yozib beraman.
Tekshiruv avtomatik: har qiymat katalogning o'z jadvali bilan
solishtiriladi.
