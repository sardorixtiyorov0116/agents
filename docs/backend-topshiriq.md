# Backend topshirig'i — xizmat kaliti (`X-API-Key`) va yozish endpointlarini himoyalash

> Bu faylni backend dasturchiga bering — u Claude Code'ga to'g'ridan-to'g'ri
> topshiriq sifatida bersa bo'ladi. Hamma kerakli ma'lumot ichida.

---

## Kontekst

Repo: Climavent backend (NestJS + Swagger, Railway'da turadi —
`climavent-back-production.up.railway.app`, sxema `/api/docs-json`).

Kompaniyada AI agentlar tizimi ishga tushirildi. Uning ichida "Katalog
administratori" agenti bor: u mahsulot, model, narx va texnik xususiyatlarni
katalogga yozadi (har o'zgarish inson tasdig'idan keyin). Agentga backendga
**mashina sifatida** kirish kerak.

Hozirgi kirish oqimi bunga to'g'ri kelmaydi:

```
POST /api/users/login      {phone_number}   → SMS ketadi, verification_key qaytadi
POST /api/users/verify-otp {phone_number, verification_key, otp, userId} → token
```

SMS kodi telefonga keladi — bot uni o'qiy olmaydi. `refresh` endpointi ham
yo'q, ya'ni token eskirsa yana qo'lda OTP kiritish kerak bo'ladi.

Shu bilan birga sxemani tekshirganda **jiddiy xavfsizlik muammosi** topildi:
yozish endpointlarining aksariyatida auth umuman yo'q (pastda ro'yxat).

---

## Vazifa

Ikkalasini bitta yechim bilan hal qilish: `X-API-Key` sarlavhasiga asoslangan
xizmat kaliti (service key) qo'shish va uni himoyasiz turgan admin
endpointlariga qo'llash.

### 1-qadam. Kalitni sozlama sifatida qo'shish

- Yangi env o'zgaruvchi: `SERVICE_API_KEY`.
- Qiymat 32 baytlik tasodifiy satr: `openssl rand -hex 32`.
- Railway → Variables ga qo'yiladi. **Repoga, `.env.example` ga namuna
  qiymat ham yozilmaydi** — faqat bo'sh kalit nomi.
- `ConfigModule` orqali o'qiladi (hozir loyihada qanday o'qilsa, shunday).

### 2-qadam. `ServiceKeyGuard`

`src/auth/service-key.guard.ts`:

```ts
import { CanActivate, ExecutionContext, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { timingSafeEqual } from 'crypto';

@Injectable()
export class ServiceKeyGuard implements CanActivate {
  constructor(private readonly config: ConfigService) {}

  canActivate(ctx: ExecutionContext): boolean {
    const req = ctx.switchToHttp().getRequest();
    const berilgan = req.headers['x-api-key'];
    const kutilgan = this.config.get<string>('SERVICE_API_KEY');

    if (!kutilgan || typeof berilgan !== 'string') return false;

    const a = Buffer.from(berilgan);
    const b = Buffer.from(kutilgan);
    // Uzunlik oldin tekshiriladi: timingSafeEqual teng uzunlik talab qiladi.
    return a.length === b.length && timingSafeEqual(a, b);
  }
}
```

**Muhim:** solishtirish `===` bilan qilinmasin. Oddiy solishtirish javob
vaqtiga qarab kalitni belgima-belgi topib olish imkonini beradi
(timing attack). `timingSafeEqual` shuning uchun ishlatiladi.

### 3-qadam. JWT bilan birga ishlashi

Sayt foydalanuvchilari JWT bilan kiradi, bot esa kalit bilan. Ikkalasi ham
o'tishi kerak:

`src/auth/jwt-or-service-key.guard.ts`:

```ts
@Injectable()
export class JwtOrServiceKeyGuard implements CanActivate {
  constructor(
    private readonly kalit: ServiceKeyGuard,
    private readonly jwt: JwtAuthGuard,   // loyihadagi mavjud guard nomi
  ) {}

  async canActivate(ctx: ExecutionContext) {
    if (this.kalit.canActivate(ctx)) return true;   // bot
    return this.jwt.canActivate(ctx);               // odam, saytdan
  }
}
```

Ikkala guard ham provider sifatida ro'yxatdan o'tkazilsin.

### 4-qadam. Guardni qo'llash

**Shu endpointlarga `JwtOrServiceKeyGuard` qo'yilsin** (hozir auth umuman
yo'q, bot esa aynan shularga yozadi):

```
POST   PATCH  DELETE   /api/product-models/...        ← narx shu yerda
POST   PATCH  DELETE   /api/characteristics/...       ← narx shu yerda ham
POST   PATCH  DELETE   /api/category/...
POST   PATCH  DELETE   /api/banners/...
POST   PATCH  DELETE   /api/product-images/...
POST   PATCH  DELETE   /api/product-model-infos/...
POST   PATCH  DELETE   /api/product-model-inside/...
POST   PATCH  DELETE   /api/rishotkalar/...
POST   PUT             /api/r2/r2-upload, /api/r2/r2-update
```

`/api/products/create|update|delete` da allaqachon Bearer bor — ularga
qo'shimcha ravishda kalit ham o'tsin (ya'ni ular ham `JwtOrServiceKeyGuard`
ga o'tkazilsin), aks holda bot yangi mahsulot qo'sha olmaydi.

**Alohida va eng shoshilinch (bot bilan aloqasi yo'q):**

```
PATCH  /api/users/update/{id}
DELETE /api/users/delete/{id}
```

Bularda auth yo'q — hozirda internetdagi istalgan odam istalgan
foydalanuvchini tahrirlashi yoki **o'chirishi** mumkin. Bu yerga xizmat
kaliti EMAS, foydalanuvchi JWT'si qo'yilsin, ustiga "faqat o'zini yoki
admin" tekshiruvi qo'shilsin.

**TEGILMASIN** (bular ataylab ochiq — sayt mehmon foydalanuvchi uchun
ishlaydi; ularni yopish do'konni sindiradi):

```
/api/cart/...          /api/cart-items/...
/api/likes/...         /api/selected-to-checkout/...
/api/reviews/create
/api/users/register, login, signout, verify-otp
/api/products/search, lastadded, bysort, categoryslug   (POST, lekin o'qish)
```

Bu ro'yxatga tegishdan oldin frontend qaysi endpointni token'siz
chaqirayotganini tekshiring.

### 5-qadam. Swagger

Yangi guard qo'yilgan endpointlarga `@ApiSecurity('service-key')` (yoki
loyihada qabul qilingan usul) qo'shilsin — `/api/docs-json` da auth talabi
ko'rinib tursin. Hozir sxema noto'g'ri ma'lumot beryapti.

---

## Qabul qilish mezonlari

1. To'g'ri kalit bilan `PATCH /api/product-models/update/91` → `200`.
2. Kalitsiz o'sha so'rov → `401` (hozir `200` qaytaradi).
3. Noto'g'ri kalit bilan → `401`.
4. Saytdan oddiy foydalanuvchi sifatida savatga mahsulot qo'shish → avvalgidek
   ishlaydi (regressiya yo'q).
5. Saytdan admin sifatida mahsulot tahrirlash → avvalgidek ishlaydi.
6. `SERVICE_API_KEY` ni Railway'da o'zgartirib redeploy qilinsa, eski kalit
   ishlamay qoladi, saytdagi foydalanuvchilar esa tizimdan chiqib ketmaydi.
7. Kalit hech qanday log'ga, xato xabariga yoki Sentry'ga tushmaydi.

## Qat'iy talablar

- Kalit **kodga yozilmaydi**, faqat env orqali keladi.
- Kalit log'ga chiqmaydi (sarlavhalarni to'liq log qiladigan middleware bo'lsa,
  `x-api-key` maskalansin).
- Solishtirish `timingSafeEqual` bilan.
- Mavjud OTP/JWT oqimiga tegilmaydi — u o'z holicha qoladi.
- `JWT_SECRET` o'zgartirilmaydi.
- Migratsiya yoki yangi jadval kerak emas — bu yechim bazaga tegmaydi.

## Nima uchun muddatsiz JWT emas

Muqobil variant — `role: service` foydalanuvchisi ochib, unga `exp`siz JWT
imzolash. Rad etildi, chunki bunday tokenni bekor qilib bo'lmaydi: sizib
chiqsa, yagona chora `JWT_SECRET` ni almashtirish, u esa saytdagi barcha
foydalanuvchini tizimdan chiqarib yuboradi. Buni tuzatish uchun blocklist
jadvali kerak bo'ladi — natijada `X-API-Key` dan ko'p ish chiqadi.

---

## Tayyor bo'lgach

Kalitni xavfsiz kanal orqali (parol menejeri, Telegram emas) yuboring —
agentlar tizimining `.env` fayliga qo'yiladi. Botning yozish klienti
`Authorization: Bearer` o'rniga `X-API-Key` yuboradigan qilib sozlanadi.
