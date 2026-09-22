# №14 javobiga javob

**Kimdan:** Adminka
**Sana:** 10.09.2026
**Adminka commitlari:** `851e8d0`, `0f0bee6`, `f22d0a4`

Rahmat — oltala band ham tekshirildi, hammasi siz aytgandek ishlayapti.
Quyida uchta narsa: bitta o'zimizdagi tuzatish, ikkita qaroringizga
javob va bitta iltimos.

---

## Tekshirdim — hammasi mos keldi

Servis kaliti bilan va kalitsiz yonma-yon o'lchadim:

```
                            mehmon   servis kaliti
products/allcount             137         177
products/all                  137         177
stores/all                      2           4
products/one/235              404         200
stores/one/7                  404         200
stores/slug/armavent          404         200
products/alladmin               -         177
search "VR 80"                  0           4
```

`products.is_active` va `reviews.is_hidden` maydonlari joyida, buyurtma
holatlari ko'chgan: `shipping 17, done 1, new 5`.

---

## ⚠️ Ogohlantirishingiz bizga aynan tegdi — tuzatildi

> «Agar adminkada shunday joy bo'lsa, so'rovga kalit qo'shing.»

Bor edi. Adminkaning **hamma o'qish so'rovlari** kalitsiz ketardi
(`oqi()` faqat `Accept` yuborardi). Ya'ni deploydan keyin adminka
"mehmon" bo'lib qolgan edi:

- katalogda 177 o'rniga **137** mahsulot;
- do'konlar ro'yxatida 4 o'rniga **2** ta;
- Armavent va VENTS US mahsulotlari **umuman ochilmasdi** (404).

Superadmin o'sha ikki do'konni ko'ra ham, tahrirlay ham olmay qolgan
edi. Kalit qo'shildi, hozir yana 177 / 4 / 200.

**Bu sizning xatoyingiz emas** — o'zgarish to'g'ri, ogohlantirish ham
o'z vaqtida keldi, biz tomonda tegishli joy bor ekan, xolos. Yozib
qo'yyapman, chunki keyinchalik "adminkadan mahsulot yo'qoldi" degan
gap chiqsa, sababi shu bo'lishi mumkin.

---

## Adminkaga qo'shildi

1. **Mahsulot `is_active`** — formada "Saytda ko'rinsin" katakchasi,
   jadvalda "Saytda yo'q" nishoni va shu nomli filtr.
2. **Sharh `is_hidden`** — har bir sharhda yashirish/qaytarish tugmasi.
   O'chirish ATAYLAB qo'yilmadi (sababi pastda).
3. **Buyurtma holati** — tanlov: Yangi / To'langan / Yetkazilyapti /
   Yetkazildi / Bekor qilingan. Aralash buyurtmada do'kon adminiga tugma
   umuman chiqmaydi va sababi yoziladi — 403 ni ko'rgandan ko'ra,
   bosishdan oldin bilgani yaxshi.

Hammasi jonli sinaldi va **qaytarildi**: sharh #17 yashirildi
(`reviews_count` 1 → 0, mehmonga ko'rinmadi) va qaytarildi; mahsulot
#235 sotuvdan olindi va qaytarildi; buyurtma #4 `shipping → done →
shipping`. Oxirida baza sinovdan oldingi holatda.

---

## Qarorlaringizga javob

**`paid` haqida — roziman, o'zgartirmang.** Siz to'g'ri o'qidingiz:
to'lov `shipping` ga o'tkazsa, adminга qiladigan ish qolmasdi va
"jo'natdim" degan qadam yo'qolardi. Hozirgidek qolsin.

**Sharh: `is_hidden` ni asosiy yo'l qilganingiz uchun rahmat.**
Adminkada `DELETE` tugmasini umuman qo'ymadim — yashirilgani
qaytariladi, o'chirilgani yo'q. Sizning Swagger'dagi izohingiz bilan
bir xil.

---

## Ikkita iltimos

**1. №13 hujjatini olmagan ekansiz** — kechirasiz, biz tomondan
yetkazilmagan. Shu xat bilan birga qayta yuborilyapti. Ichida to'rtta
band bor, ikkitasi adminkani to'sib turibdi:

- `GET /api/users/all` va `/users/one/{id}` servis kalitini qabul
  qilmaydi (401). Shuning uchun **Foydalanuvchilar** bo'limi mijozlar
  ro'yxatini savat/buyurtma/sharh javoblari ichidan yig'yapti — ya'ni
  ro'yxatdan o'tgan-u hech narsa qilmagan mijoz umuman ko'rinmaydi.
- Buyurtma qatorlarida narx yozilmaydi (40 tadan 39 tasida `price = 0`,
  23 buyurtmadan 22 tasida `totalAmount = 0`). Pul analitikasi shunga
  qarab turibdi.

Qolgan ikkitasi kichikroq: `refresh_token` javobdan chiqarilsin va
`likes/alllikes` da `user` obyekti bo'lsin.

**2. Do'kon hisobi kerak emas, rahmat** — adminkaga superadmin va do'kon
hisobi yaratish formasi qo'shildi (Do'konlar sahifasi). Hisoblarni
o'zimiz yaratamiz. `store_users` hozircha ataylab bo'sh: hisob
yaratilgach `ADMIN_HISOBLAR` muhit o'zgaruvchisi olib tashlanadi.

---

Yana bir bor rahmat — ayniqsa deploy tartibini o'ylab, saytni oldin
chiqarganingiz va eski nomlarni qabul qilib turganingiz uchun. Bizda
shoshilinch o'zgartirish kerak bo'lmadi.
