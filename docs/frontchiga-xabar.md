# Climavent — narx jadvali: aniqlashtirish so'rovi

Salom. Men Climavent uchun agent tizimi (KP tuzuvchi bot) tomonida ishlayapman.
Buxgalteriyaning `PRICE JIHOZVENT_v5.1.xlsx` praysidan narxlarni backendga
yukladim. Quyidagilar **jonli API dan o'lchangan**, taxmin emas.

## Nima qilinganini

`product_model_inside.price` ga **299 ta narx** yozildi, DOLLARDA.
Yozgandan keyin qayta o'qib solishtirdim — 0 farq, 0 xato.
Qamrov: ВЦ 4-75, ВЦ 14-46, ВКП, ВКПП, ПВН, ПВФ, КС, RSK, КИД, КО, КОГ, КВУ,
РВН, РВИ, РВ-1, 4РВП.

Sizning tushuntirishingizni tasdiqlayman: sayt narxni haqiqatan
`product_model_inside.price` dan oladi (`/product/50` da `1 881 120 UZS` =
`156.76 $ × 12 000` — tekshirdim).

## Muammo: 4 ta oila ko'chirishdan chetda qolgan

| Oila | `product_models` da | `product_model_inside` da | `sap_name` bor |
|---|---|---|---|
| ДР  | 25 model | **0** | **0** |
| ФЯГ | 24 model | **0** | **0** |
| РКВ |  9 model | **0** | **0** |
| РЩ  |  6 model | **0** | **0** |

Ya'ni bu 64 ta modelga:
- ichki jadvalda narx qo'yadigan **joy yo'q**;
- `sap_name` bo'lmagani uchun SAP ko'prigi ham **ishlamaydi**;
- buxgalter admin paneldagi SAP narx tahriri orqali ham **kirita olmaydi**.

Menda ular uchun 44 ta narx tayyor turibdi (masalan `РКВ-150 = 1 154 $`,
`ДР100 = 56 $`, `ФЯГ 610х305х45 = 13 $`, `1РЩ 1000х52 = 20 $`).

**SAVOL: bu 64 ta modelni siz ko'chirasizmi, yoki men `POST /api/product-model-inside`
orqali 44 ta narxli qatorni yaratib qo'yaymi?**

Siz qilsangiz afzal — nomlash va SAP kodlarini o'zingiz belgilaysiz.
Men qilsam, nomlarni mavjud tartibga moslayman (`ДР100`, `1РЩ 1000х52`,
`РКВ-150`, `ФЯГ 610х305х45`), lekin `sap_name` bo'sh qoladi.

## SAP ko'prigi haqida aniqlik

Siz «ikki jadval `sap_name` orqali bog'langan» dedingiz. O'lchadim:

```
product_model_inside:  938 qatordan 932 tasida sap_name bor  (99%)
product_models:       1482 qatordan 183 tasida sap_name bor  (12%)
```

Ko'prik eski katalogning 12 foizini ulaydi (183 ta, shundan narxi bori 36 ta).
Shuning uchun KP tomonida men faqat SAP ga tayanmayman — narxni `in_model_name`
bo'yicha ham qidiraman. Agar SAP kodlarini to'ldirish rejangiz bo'lsa ayting,
o'shanda SAP ni birlamchi qilaman.

## Eski jadvaldagi 25 ta narx

`product_models.price` da 25 ta eski narx qolgan (so'mda, 2025-yildan).
Ular yangisidan ~4% arzon, masalan:

```
eski: ПВН 500-250-2 = 1 700 000 so'm
yangi: ПВН 500-250/2 = 136 $ = 1 632 000 so'm
```

Agar sayt bu jadvalni hech qayerda o'qimasa — ularni `NULL` qilib tashlash
mumkin. Faqat `ПВН …-3` variantlari yangisida umuman yo'q, ular avval
qo'shilishi kerak.

**SAVOL: sayt `product_models` jadvalini biror joyda o'qiydimi?**

## Kichik kuzatuvlar (shoshilinch emas)

1. `POST /api/products/categoryslug` javobida `characters[].insides` YO'Q —
   shuning uchun katalog ro'yxatida hamma «Цена по запросу» bo'lib turibdi,
   narx bazada bo'lsa ham. `products/one/{id}` da esa bor.
2. `product_model_inside` da 9 guruh takrorlangan nom bor (masalan
   `ГТП 200x100х1000` -> id 445 va 945). Narx yozishda chetlab o'tdim.
3. 302 ta xususiyatdan 43 tasining R2 fayli bo'sh (0 bayt) yoki buzuq —
   `/product/37` da «Characteristic» bo'limi shu sababdan bo'm-bo'sh.
