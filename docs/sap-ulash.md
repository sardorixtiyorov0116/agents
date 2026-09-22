# SAP ni agentlar tizimiga ulash — variantlar

**Sana:** 2026-08-06
**Maqsad:** narx (va imkoni bo'lsa ombor qoldig'i) SAP'dan tizimga tushsin.

> Bu hujjat qaror qabul qilish uchun. Qaysi variant tanlanishi sizdagi
> SAP turiga va IT siyosatiga bog'liq — pastda har birining sharti,
> mehnati va xavfi yozilgan.

---

## Nima uchun kerak

| Ko'rsatkich | 2026-08-06 | 2026-08-19 |
|---|---:|---:|
| Katalogdagi model (`product_models`) | 1482 | 1482 |
| Variant (`product_model_inside`) | — | 981 |
| **Narxi bor** (variantlarda, USD) | 24 | **419** |
| `sap_name` to'ldirilgan (variantlarda) | 932 | 981 |

Tijorat taklifi (KP) narxsiz tuzilmaydi. Texnik qismning hammasi tayyor:
hisob, katalog, KP shakli, docx/pdf hujjat. **Faqat raqam yetishmaydi.**

> [!warning] 2026-08-19 da TEKSHIRILDI: bizdagi `sap_name` SAP MATERIAL
> KODI EMAS.
>
> 981 ta variantning **725 tasida** `sap_name` model nomining aynan
> nusxasi. Farq qiladigan 256 tasi esa faqat yozilish varianti:
>
> ```
> nom = ПВН 500-250-2                sap = ПВН 500-250/2
> nom = ВЦ 4-75-2,5-1-0,12/1500      sap = ВЦ 4-75-2,5-О-1-0,12/1500
> nom = ВКПН 100х50-4D63             sap = -            (bo'sh belgi)
> ```
>
> RAQAMLI ko'rinishdagi kod (SAP `MATNR` odatda shunday) — **0 ta**.
>
> Ya'ni maydon noto'g'ri nomlangan: u rasmiy BELGILANISH saqlaydi,
> SAP kaliti emas. Bog'lanish kaliti hozircha YO'Q.

Yaxshi xabar: narxni NOM bo'yicha ham bog'lash mumkinligi amalda
isbotlandi — 2026-08-18 da buxgalteriya praysidan 419 ta narx aynan
shu yo'l bilan yuklandi (1365 qatordan 456 tasi nom bo'yicha topildi).

---

## Umumiy tamoyil — qaysi variant bo'lmasin

> [!warning] SAP — moliyaviy yadro. Uchta qoida buzilmaydi.

1. **Faqat o'qish.** Agentlar SAP'ga hech qachon yozmaydi. Yozish
   huquqi berilgan integratsiya — buxgalteriya ma'lumotiga xavf.
2. **Alohida texnik foydalanuvchi.** Odamning akkaunti ishlatilmaydi:
   u ishdan ketsa integratsiya to'xtaydi, va kim nima qilganini
   ajratib bo'lmaydi.
3. **Faqat kerakli maydonlar.** Material kodi, nomi, narxi, valyutasi,
   (imkoni bo'lsa) qoldiq. Kontragent, shartnoma, moliyaviy hujjat —
   **kerak emas va so'ralmaydi**.

Agentlar tizimi SAP'ga **to'g'ridan-to'g'ri ulanmaydi.** Zanjir shunday:

```
SAP  →  backend (product_models.price)  →  agent  →  KP
```

Nega: agent har KP tuzganda SAP'ni bezovta qilishi noto'g'ri. Backend —
buferi. U allaqachon bor va agentlar u bilan ishlaydi.

---

## Variant 1 — Qo'lda eksport (Excel/CSV)

**Bugun ishlaydi. Hech qanday SAP ishi kerak emas.**

```
Buxgalter SAP'dan narx ro'yxatini Excel'ga tushiradi
        ↓
Fayl backendga yuklanadi (bulk-price endpoint)
        ↓
Agentlar narxni ko'radi
```

| | |
|---|---|
| **Mehnat** | Backendda 1 kun (yuklash endpointi — 4-topshiriq, 2.2-band) |
| **SAP tomonida** | Hech narsa. Buxgalter oddiy hisobot chiqaradi |
| **Yangilanish** | Qo'lda, oyiga bir-ikki marta |
| **Xavf** | Yo'q |

**Kamchiligi:** narx eskiradi. Lekin bu **hozirgi 1,6% dan ancha
yaxshi** va butun zanjirni sinab ko'rish imkonini beradi.

> Tavsiya: qaysi variant tanlansa ham, **shundan boshlash kerak.**
> Bir hafta ichida KP ishlay boshlaydi, keyin avtomatlashtirasiz.

---

## Variant 2 — Rejali eksport (fayl orqali) ⭐ real maqsad

SAP'da rejali topshiriq (`background job`) tuziladi: har kecha narx
ro'yxatini CSV qilib umumiy papkaga yoki FTP/SFTP ga qo'yadi. Bizning
skript uni ertalab olib, backendga yuklaydi.

```
SAP job (har kecha 02:00)  →  narxlar.csv  →  SFTP
                                              ↓
                          bizning skript (03:00) → backend
```

| | |
|---|---|
| **Mehnat** | SAP'da 1-2 kun (ABAP dasturchi yoki funktsional konsultant), bizda 1 kun |
| **SAP tomonida** | Hisobot varianti + rejali topshiriq. Yangi kod deyarli yo'q |
| **Yangilanish** | Har kuni avtomatik |
| **Xavf** | Past — SAP'ga tashqaridan ulanish YO'Q, faqat fayl chiqadi |

**Nega bu eng real variant:** ko'p kompaniyada SAP tashqi tarmoqqa
ochilmaydi va IT xavfsizlik bo'limi buni ma'qullamaydi. Fayl eksporti
esa allaqachon o'rnatilgan amaliyot — buxgalteriya baribir hisobot
chiqaradi.

---

## Variant 3 — SAP OData / REST API

SAP S/4HANA yoki SAP Gateway o'rnatilgan bo'lsa, standart OData servisi
orqali material va narx ma'lumotini so'rasa bo'ladi.

```
GET /sap/opu/odata/sap/API_PRODUCT_SRV/A_Product?$filter=...
```

| | |
|---|---|
| **Mehnat** | SAP'da servisni yoqish va huquq berish (1-3 kun), bizda 1-2 kun |
| **SAP tomonida** | Gateway sozlanishi, texnik foydalanuvchi, rol |
| **Yangilanish** | Real vaqtda |
| **Xavf** | O'rta — tarmoq ochiladi, shuning uchun VPN yoki oq ro'yxat kerak |

**Sharti:** S/4HANA yoki NetWeaver Gateway bor bo'lishi. Eski ECC 6.0 da
ham qo'shsa bo'ladi, lekin bu alohida loyiha.

---

## Variant 4 — RFC / BAPI (klassik SAP)

Eski SAP ERP (ECC) uchun an'anaviy yo'l: `pyrfc` kutubxonasi orqali
`BAPI_MATERIAL_GET_DETAIL` kabi standart funksiyalar chaqiriladi.

| | |
|---|---|
| **Mehnat** | O'rtacha, lekin o'rnatish qiyin |
| **Sharti** | **SAP NetWeaver RFC SDK** kerak — u litsenziyalangan va faqat SAP mijozlari yuklab oladi |
| **Xavf** | O'rta |

**Kamchiligi:** SDK'ni serverga o'rnatish, versiyalar mosligi, litsenziya
masalasi. Fayl eksporti bilan bir xil natijani ancha qiyin yo'ldan
oladi. Faqat real vaqt chindan kerak bo'lsa mantiqiy.

---

## Variant 5 — Bazaga to'g'ridan-to'g'ri ulanish ❌

SAP HANA yoki Oracle bazasiga to'g'ridan-to'g'ri `SELECT`.

> [!danger] Tavsiya etilmaydi
> - SAP litsenziya shartlari buni odatda **taqiqlaydi**;
> - jadval tuzilishi murakkab va versiyalar orasida o'zgaradi
>   (narx bitta jadvalda emas — `MARA`, `A004`, `KONP` va h.k.);
> - ilova qatlamidagi mantiq chetlab o'tiladi, natija noto'g'ri chiqishi
>   mumkin.

Buni faqat SAP konsultanti aniq ko'rsatma bersa qilish kerak.

---

## Taqqoslash

| Variant | Mehnat | SAP ishi | Yangilanish | Xavf | Kimga mos |
|---|---|---|---|---|---|
| 1. Qo'lda eksport | 1 kun | yo'q | qo'lda | yo'q | **hozir boshlash uchun** |
| 2. Rejali fayl | 2-3 kun | kam | kunlik | past | **asosiy maqsad** |
| 3. OData | 3-5 kun | o'rta | real vaqt | o'rta | S/4HANA bo'lsa |
| 4. RFC/BAPI | 5+ kun | o'rta | real vaqt | o'rta | faqat ECC va zarurat bo'lsa |
| 5. To'g'ridan baza | — | — | — | yuqori | ❌ |

---

## Tavsiya qilingan yo'l

**1-bosqich (shu hafta).** Backendga ommaviy yuklash endpointi
(4-topshiriq, 2.2). Buxgalter SAP'dan bir marta Excel chiqaradi.
Natija: KP ishlay boshlaydi, butun zanjir sinaladi.

**2-bosqich (bir oy ichida).** SAP'da rejali eksport. Narx har kuni
o'zi yangilanadi, hech kim hech narsa qilmaydi.

**3-bosqich (kerak bo'lsa).** OData — agar narx kun davomida o'zgarsa
va real vaqt chindan kerak bo'lsa. Ko'p holatda kerak bo'lmaydi.

---

## Eksportda nima bo'lishi kerak

Qaysi variant bo'lmasin, minimal to'plam:

| Maydon | Nega |
|---|---|
| **SAP material kodi** | Bizdagi `sap_name` bilan bog'lanadi — kalit shu |
| Material nomi | Tekshirish uchun |
| **Narx** | Asosiy maqsad |
| Valyuta | So'mmi, dollarmi — hozir taxmin qilyapmiz |
| Narx amal qilish sanasi | KP da "narx N kunlik" deyish uchun |
| Qoldiq (bo'lsa) | "ВК-250С dan nechta bor?" — savdoning eng ko'p savoli |
| Standart / buyurtma belgisi | Nostandart tovarga narx qidirilmasin |

Namuna:

```csv
sap_kod;nomi;narx;valyuta;sana;qoldiq;turi
ПВН 500-300/2;Нагреватель водяной;1930000;UZS;2026-08-01;12;standart
ПВН 600-300/2;Нагреватель водяной;2220000;UZS;2026-08-01;5;standart
```

---

## Aniqlanishi kerak

- [ ] Sizda SAP ning qaysi turi? (S/4HANA · Business One · ECC/R3)
- [ ] Kim administratsiya qiladi — ichki IT mi, tashqi integratormi?
- [ ] Buxgalter SAP'dan hisobotni **o'zi chiqara oladimi**?
- [ ] IT xavfsizlik siyosati SAP'ga tashqaridan ulanishga ruxsat beradimi?
- [x] ~~`sap_name` dagi kodlar SAP material kodi bilanmi?~~ —
      **YO'Q, tekshirildi 2026-08-19.** Yuqoridagi ogohlantirishga qara.
- [ ] Buxgalteriyaning `PRICE JIHOZVENT_v5.1.xlsx` praysi SAP'dan
      chiqarilganmi yoki qo'lda yuritiladimi? Agar SAP'dan bo'lsa,
      ko'chirish amalda ALLAQACHON ishlayapti — faqat avtomatlashtirish
      qoladi.
- [ ] SAP'dan 20-30 qatorlik NAMUNA: material kodi, nomi, narxi,
      valyutasi, o'lchov birligi. Butun eksport kerak emas — namuna
      kalit masalasini hal qiladi.

## Kalit masalasi — uchta yo'l

| Yo'l | Sharti | Mehnat |
|---|---|---|
| **A. Nom bo'yicha** | SAP dagi nom katalog nomiga yaqin | ishlayapti (456/1365) |
| **B. Kod bo'yicha** | SAP kodi bazaga bir marta ko'chiriladi | yangi ustun + bir martalik moslashtirish |
| **C. Qo'lda xarita** | Ikkalasi ham mos kelmasa | 1482 qator, muhandis ishi |

B eng ishonchli: `product_model_inside` ga `sap_material_kodi` ustuni
qo'shilib, SAP eksporti bilan bir marta to'ldiriladi. Shundan keyin
narx yangilash butunlay avtomatlashadi va nom o'zgarsa ham buzilmaydi.
