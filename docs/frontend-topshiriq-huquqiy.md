# Frontend topshirig'i: huquqiy hujjatlar, rozilik va cookie

**Sana:** 15.09.2026 · **Sayt:** climavent.uz (Nuxt)

Oferta, foydalanish shartlari va maxfiylik siyosatining 1.0 versiyasi tayyor.
Saytdagi sahifalar (`/oferta/sotuvchi`, `/maxfiylik`, `/foydalanish-shartlari`,
`LegalDoc` komponenti) juda yaxshi qilingan — faqat matnni ulash kerak.
Matn o'zbek tilida (rasmiy); ru/en bo'sh, sahifa bo'sh tilda uz matnni
ko'rsatadi (bu sizning `TlDcy_RC` modulingizda allaqachon shunday).

## Matn qayerdan olinadi

```
GET https://climavent-marketplace-admin.vercel.app/api/huquqiy/{tur}
tur = oferta-sotuvchi | foydalanish-shartlari | maxfiylik
```

Guvohnoma kerak emas, CORS ochiq, 5 daqiqa keshlanadi. Javob sizning
modulingiz shaklida — `LegalDoc` ga to'g'ridan-to'g'ri beriladi:

```json
{
  "tur": "oferta-sotuvchi",
  "kind": "seller",
  "version": "1.0",
  "date": "15.09.2026",
  "url": "https://climavent.uz/oferta/sotuvchi",
  "uz": { "intro": "Ushbu hujjat «CLIMAVENT» MChJ ...", "sections": [{ "h": "Atamalar", "body": ["1.1. Platforma — ...", ["ro'yxat bandi", "..."]] }] },
  "ru": { "intro": "", "sections": [] },
  "en": { "intro": "", "sections": [] }
}
```

- `h` da raqam **yo'q** — `LegalDoc` bo'limlarni o'zi raqamlaydi; tartib
  hujjatdagi bo'lim raqamlariga mos (matn ichidagi «9.4-band», «4-ilova»
  havolalari to'g'ri chiqadi).
- `body` — satr (paragraf) yoki satrlar massivi (ro'yxat). HTML yo'q.
- Zaxira: xuddi shu JSON'lar `docs/huquqiy/sayt/*.json` da. API ochilmasa
  sahifa bo'sh qolmasligi uchun ularni loyihaga qo'shib, fallback qiling.

Matn keyin o'zgarsa, sayt qayta deploysiz yangisini oladi.

## 1. `/oferta/sotuvchi` va sotuvchi formasi

`TlDcy_RC` modulidagi bo'sh `{ uz, ru, en }` o'rniga shu API javobini SSR'da
oling (`useAsyncData`). `uz.sections` to'lgach sizning `i()` shartingiz
`true` bo'ladi — oferta sahifasi ham, `/sotuvchi-bolish` formasi ham o'zi
ochiladi. «Kuchga kirgan sana» uchun `date` ni yoki `offers/current` dagi
`effective_at` ni ishlating (backendga 15.09.2026 qilib qo'yish so'raldi).

Formadagi belgi matni (`t.offer.accept`) — belgi **oldindan qo'yilmagan**
bo'lsin, havolalar yangi oynada ochilsin:

| til | matn |
|---|---|
| uz | Ofertani va Maxfiylik siyosatini o'qidim, shartlarni qabul qilaman va arizadagi shaxsga doir ma'lumotlar ishlanishiga roziman |
| ru | Я прочитал(а) оферту и Политику конфиденциальности, принимаю условия и согласен(на) на обработку персональных данных из заявки |
| en | I have read the offer and the Privacy Policy, accept the terms and consent to the processing of personal data in the application |

«Oferta» → `/oferta/sotuvchi`, «Maxfiylik siyosati» → `/maxfiylik`.

## 2. `/maxfiylik` va `/foydalanish-shartlari`

Hozirgi kodga yozilgan matnni API javobi bilan almashtiring (`LegalDoc`
o'zgarmaydi). Eski matnlarni olib tashlash muhim: ularda marketpleys
modeliga zid bandlar bor — «Visa/Mastercard/Uzcard/Humo bilan onlayn
to'lov», «buyurtma to'lov tasdiqlangach qabul qilinadi», «narx 10 kun amal
qiladi». Yangi shartlarda to'lov **bevosita sotuvchiga** qilinadi.

Agar sayt haqiqatan onlayn to'lov qabul qilayotgan bo'lsa (`/payment`,
`/checkout`) — bizga ayting, shartlar boshqacha yoziladi.

`/privacy` → `/maxfiylik`, `/terms` → `/foydalanish-shartlari`: 301
yo'naltirish (ikki nusxa bo'lmasin).

## 3. Xaridor ro'yxatdan o'tishi — rozilik belgisi

SMS-kod so'raladigan shaklda (telefon kiritiladigan joy) belgi qo'shing.
Oldindan qo'yilmagan; belgisiz «Kod yuborish» tugmasi faol emas.

| til | matn |
|---|---|
| uz | Foydalanish shartlari va Maxfiylik siyosati bilan tanishdim, shaxsga doir ma'lumotlarim ishlanishiga roziman |
| ru | Я ознакомился(ась) с Пользовательским соглашением и Политикой конфиденциальности и согласен(на) на обработку моих персональных данных |
| en | I have read the Terms of use and the Privacy Policy and consent to the processing of my personal data |

Belgi faqat yangi foydalanuvchi uchun kerak; hisobi bor odam kirganda
so'ralmaydi. Backend rozilik yozuvini qabul qila boshlagach (№18, 2-band)
versiyalarni so'rovga qo'shasiz — hozircha faqat belgi.

## 4. Cookie ogohlantirishi

Saytda Google Analytics (`G-2NXZ7YXE01`) rozilik so'ramasdan ishlayapti.
Maxfiylik siyosatining 9-bo'limi endi shunday deydi: **analitik cookie faqat
rozilikdan keyin**.

- Google Consent Mode v2: sahifa yuklanishida `analytics_storage: 'denied'`
  (va `ad_storage`, `ad_user_data`, `ad_personalization`: `'denied'`) —
  `gtag('config')` dan **oldin**.
- Pastda ixcham panel, ikkita teng tugma:
  - «Qabul qilish» → `gtag('consent', 'update', { analytics_storage: 'granted' })`;
  - «Faqat zarurlari» → `denied` qoladi.
- Tanlov `localStorage` da (`cookie_consent`: `all` | `necessary`, sana bilan)
  12 oy saqlanadi; tanlov bo'lsa panel chiqmaydi.
- Footer'da «Cookie sozlamalari» havolasi panelni qayta ochadi.

| til | matn | tugmalar |
|---|---|---|
| uz | Sayt ishlashi uchun zarur cookie-fayllardan foydalanamiz. Roziligingiz bilan tashriflar statistikasi uchun Google Analytics ham yoqiladi. Batafsil — Maxfiylik siyosati. | Qabul qilish · Faqat zarurlari |
| ru | Мы используем необходимые cookie-файлы для работы сайта. С вашего согласия также включается Google Analytics для статистики посещений. Подробнее — Политика конфиденциальности. | Принять · Только необходимые |
| en | We use essential cookies to run the site. With your consent we also enable Google Analytics for visit statistics. Details — Privacy Policy. | Accept · Essential only |

«Maxfiylik siyosati» → `/maxfiylik#sec-9`.

## 5. Footer

«Для предпринимателей» / pastki huquqiy qatorga qo'shing:

| uz | ru | en | havola |
|---|---|---|---|
| Huquq buzilishi haqida xabar berish | Сообщить о нарушении прав | Report an infringement | `/foydalanish-shartlari#sec-10` |
| Cookie sozlamalari | Настройки cookie | Cookie settings | panelni ochadi |

## 6. Do'kon sahifasi — sotuvchi rekvizitlari

Elektron tijorat qonuni sotuvchini aniqlash ma'lumotini talab qiladi.
`GET /api/stores/slug/{slug}` allaqachon `legal_name` va `tin` beradi.
`/stores/:slug` da (va tovar sahifasidagi sotuvchi blokida) ular bo'lsa:

> Sotuvchi: {legal_name} · STIR {tin}

Bo'sh bo'lsa qator ko'rsatilmaydi.

## Tekshirish

1. `/oferta/sotuvchi` — 18 bo'lim, oxirgisi «4-ilova. Huquq egalari
   shikoyatlarini ko'rib chiqish tartibi»; «tayyorlanmoqda» yozuvi yo'q.
2. `/sotuvchi-bolish` — forma ochiq, belgisiz yuborilmaydi.
3. `/foydalanish-shartlari` — 14 bo'lim, 10-bo'lim «Huquq buzilishi…»;
   onlayn karta to'lovi haqida gap yo'q. `/maxfiylik` — 11 bo'lim.
4. Yashirin oynada saytni oching: GA so'rovi (`google-analytics.com/g/collect`)
   «Qabul qilish» bosilmaguncha ketmaydi.
5. Ro'yxatdan o'tishda belgisiz kod yuborilmaydi.
