# Instagram tokenini olish (Nilufar uchun)

Nilufar Meta'ning rasmiy Graph API'sidan foydalanadi. Sahifa qirqish
(scraping) yoki uchinchi tomon xizmati ishlatilmaydi — bular Instagram
shartlariga zid va akkaunt bloklanishiga olib keladi.

## Nega ikkita qiymat kerak

Meta'da boshqa profilni tahlil qilish **o'z akkauntingiz orqali**
so'raladi. So'rov shakli shunday:

```
GET /{BIZNING_ID}?fields=business_discovery.username(raqib_profili){...}
```

Ya'ni:

| Qiymat | Nima uchun |
|---|---|
| `INSTAGRAM_USER_ID` | **Bizning** Instagram Business akkauntimiz ID'si — so'rov shu tugundan yuboriladi |
| `INSTAGRAM_TOKEN` | Shu akkaunt bizniki ekanini isbotlaydi |

Tahlil qilinayotgan profilning tokeni **kerak emas** — u shunchaki
Business yoki Creator turida va ochiq bo'lishi yetarli.

## Shartlar

1. Instagram akkaunt **Business** yoki **Creator** bo'lishi kerak
   (Settings → Account type). Shaxsiy akkaunt API'da umuman ko'rinmaydi.
2. Akkaunt **Facebook sahifasiga** ulangan bo'lishi kerak.
3. developers.facebook.com da ilova (App) yaratiladi.

## Qadamlar

1. https://developers.facebook.com → **My Apps** → **Create App** →
   turi: **Business**.
2. Ilovaga **Instagram Graph API** mahsulotini qo'shing.
3. **Tools → Graph API Explorer**:
   - ilovangizni tanlang;
   - **Generate Access Token**;
   - ruxsatlar: `instagram_basic`, `pages_show_list`,
     `pages_read_engagement`, `business_management`,
     **`instagram_manage_insights`**.

   Oxirgisi SHART: usiz qamrov, saqlashlar va ulashishlar kelmaydi —
   faqat layk va komment soni qoladi.
4. O'z ID'ingizni bilib oling — Explorer'da so'rov yuboring:

   ```
   GET /me/accounts
   ```

   Javobdagi sahifa `id` sini olib:

   ```
   GET /{sahifa_id}?fields=instagram_business_account
   ```

   Chiqqan `17841...` bilan boshlanadigan raqam — `INSTAGRAM_USER_ID`.

5. **Tokenni uzaytiring.** Explorer bergani 1-2 soatda tugaydi.
   **Tools → Access Token Debug Tool** → *Extend Access Token* — 60 kunlik
   token beradi.

6. `.env` ga yozing:

   ```
   INSTAGRAM_TOKEN=EAAG...
   INSTAGRAM_USER_ID=17841400000000000
   ```

## Tekshirish

```bash
.venv\Scripts\python -m pytest tests/test_nilufar.py -q
```

Keyin botga yozing: `https://instagram.com/climaventuz profilini tahlil qil`

## Token muddati

60 kunlik token tugagach, Nilufar aniq xato beradi ("token eskirgan").
Uzaytirish uchun 5-qadamni takrorlang. Avtomatik yangilash uchun System
User token kerak (Business Manager) — kerak bo'lsa aytilsin.

## Nima ko'rinadi, nima ko'rinmaydi

| Ko'rinadi | Ko'rinmaydi |
|---|---|
| Sarlavha matni | Videoning ovozi |
| Ko'rishlar, layk, komment soni | Montaj, keyingi kadrlar |
| Kommentlar matni (15 tagacha) | Story (24 soatlik) |
| **Video muqovasi — birinchi kadr** | Qamrov, saqlashlar (faqat o'z akkauntda) |
| Post turi (Reels / Feed) | Auditoriya demografiyasi |
 