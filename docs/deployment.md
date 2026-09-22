# Serverga chiqarish

**Nima uchun kerak:** hozir hamma narsa bitta kompyuterda ishlaydi. U
o'chsa — tender tekshirilmaydi, ertalabki xabar kelmaydi, mijozlar boti
javob bermaydi. Jonli o'lchov: tender kuzatuvi 7 kunda atigi **2 marta**
ishlagan, chunki qolgan kunlari kompyuter o'chiq edi.

---

## 1. Nima ishga tushadi

Bitta konteynerda **uchta jarayon**:

| Jarayon | Nima qiladi |
|---|---|
| `panel` | Veb panel va ofis ko'rinishi (FastAPI, 8000-port) |
| `ichki-bot` | Menejerlar boti + tender jadvali (09:00) + haftalik hisobot |
| `mijoz-bot` | Mijozlar boti (ochiq) |

Ularni `ishga_tushir.py` boshqaradi: biri yiqilsa qayta ko'taradi,
qolgani ishlayveradi.

**Nega bitta konteyner:** uchalasi bitta SQLite fayliga
(`agentlar.db`) yozadi. Bulut xizmatlarida disk bitta xizmatga
biriktiriladi — uch xizmatga bo'lsak, ular bir xil bazani ko'rmaydi.

---

## 2. Qayerga chiqarish

### A) Railway — eng oson (backend allaqachon shu yerda)

1. Loyihani git omboriga qo'ying (hozir git yo'q):
   ```bash
   git init && git add -A && git commit -m "Agentlar tizimi"
   ```
   `.gitignore` da `.env` va `*.db` bor — **kalitlar omborga tushmaydi**.

2. Railway'da yangi loyiha → GitHub omborini ulang. Railway `Dockerfile`
   ni o'zi topadi.

3. **Volume** qo'shing: `/data` (kamida 2 GB).
   Busiz konteyner qayta ishga tushganda hamma iz, KP raqamlari va
   bilim bazasi yo'qoladi.

4. Muhit o'zgaruvchilarini panelda kiriting (4-bo'lim).

5. Domen bering (Settings → Networking → Generate Domain).

**Narxi:** taxminan $5–10/oy. Image ~1.5 GB (onnxruntime + embedding
modeli), RAM ~600 MB.

### B) VPS (o'z serveringiz)

```bash
git clone <ombor> && cd agentlar-tizimi
cp .env.example .env && nano .env        # kalitlarni kiritasiz
docker compose up -d --build
docker compose logs -f
```

`docker-compose.yml` panelni faqat `127.0.0.1:8000` ga ochadi. Tashqi
kirish uchun oldiga Caddy/nginx qo'ying (HTTPS bilan).

---

## 3. Bazani ko'chirish (ilk marta)

Mahalliy `agentlar.db` (20 MB) ichida **bilim bazasi indeksi** bor:
43 hujjat, 4954 bo'lak. Uni ko'chirmasangiz agentlar bilim bazasisiz
qoladi va serverda qayta indekslash kerak bo'ladi.

**Railway:**
```bash
railway link
railway run bash -c "cat > /data/agentlar.db" < agentlar.db
```

**VPS:**
```bash
docker compose cp agentlar.db agentlar:/data/agentlar.db
docker compose restart
```

Ko'chirishdan oldin botlarni to'xtating — SQLite yozayotgan paytda
nusxa olish faylni buzishi mumkin.

---

## 4. Muhit o'zgaruvchilari

To'liq ro'yxat — `.env.example`. Serverda **majburiy**lari:

| O'zgaruvchi | Izoh |
|---|---|
| `ANTHROPIC_API_KEY` | Busiz hech narsa ishlamaydi |
| `PANEL_PAROLI` | **Majburiy.** Pastdagi ogohlantirishni o'qing |
| `BOT_TOKEN` | Ichki bot. Bo'sh bo'lsa ishga tushmaydi |
| `BOT_RUXSAT_ETILGAN_ID` | Bo'sh bo'lsa bot hech kimga javob bermaydi |
| `MIJOZ_BOT_TOKEN` | Mijozlar boti (ixtiyoriy) |
| `TENDER_KUZATUV_VAQTI` | `09:00` — bo'sh bo'lsa avtomatik tekshiruv yo'q |
| `TZ` | `Asia/Tashkent` — Dockerfile qo'yadi, Railway'da qo'lda kiriting |

Docker o'zi qo'yadigan yo'llar (o'zgartirmang):
`BAZA_YOLI=/data/agentlar.db`, `KP_YOLI=/data/kp`,
`TEXNIK_KESH_YOLI=/data/texnik_parametrlar.json`, `VAULT_YOLI=/app/vault`.

### ⚠️ PANEL_PAROLI — nega majburiy

Panelda bor: `/izlar` (barcha so'rov va javoblar, mijoz nomlari, KP
mazmuni), `/sorov` (agentlarni ishga tushiradi — ya'ni begona odam
sizning Anthropic hisobingizdan pul sarflaydi), `/tasdiq/{id}` (inson
tasdig'ini bosib yuborishi mumkin).

Himoya **fail-closed** (`app/himoya.py`): parol qo'yilmasa panel
tashqaridan **403** qaytaradi. Ya'ni qo'yishni unutsangiz ham ma'lumot
ochilib qolmaydi — shunchaki panel ishlamaydi.

Parol yasash: `openssl rand -base64 24`
Brauzer foydalanuvchi nomini so'raydi — u doim **`jihozvent`**.

Tekshirilgan (2026-08-11, haqiqiy server, 192.168.1.3:8098):
```
parolsiz /panel    -> 401
parol bilan /panel -> 200
noto'g'ri parol    -> 401
/sorov parolsiz    -> 401
/salomat           -> 200   (sog'liq tekshiruvi uchun ochiq qoladi)
```

---

## 5. Obsidian vault

Vault (41 ta `.md`, 209 KB) mahalliy kompyuterda turadi. Serverda u
**yo'q** — papka topilmasa indekslash o'sha qismni jimgina o'tkazib
yuboradi (`bilim/indeks.py`).

Ikki yo'l:

1. **Indeksni ko'chirish (tavsiya).** Mahalliy kompyuterda indekslab,
   `agentlar.db` ni serverga ko'chirasiz (3-bo'lim). Vault o'zgarsa —
   qayta indekslab, bazani qayta ko'chirasiz.

2. **Vaultni ko'chirish.** `Jihozvent-Vault` ni loyiha ichidagi `vault/`
   papkasiga nusxalaysiz; `docker-compose.yml` uni faqat o'qish uchun
   ulaydi. Shunda serverda ham qayta indekslash mumkin.

---

## 6. Chiqargandan keyin tekshirish

```bash
curl -u jihozvent:<parol> https://<domen>/salomat?tekshir=1
```

`{"holat":"ishlayapti","llm":"ulangan"}` bo'lishi kerak.
`"kalit ishlamayapti"` chiqsa — `ANTHROPIC_API_KEY` noto'g'ri.

Keyin Telegramda:
- `/start` — bot javob berdimi;
- `/tender` — tender tekshiruvi qo'lda ishladimi;
- `/hisobot 7` — hisobot chiqdimi;
- oddiy savol — agent javob berdimi.

Loglar: `docker compose logs -f` yoki Railway → Deployments → Logs.
Boshqaruvchi har jarayonni nomi bilan yozadi:
`[2026-08-11 13:46:49] boshqaruvchi | ichki-bot: ishga tushmoqda`

---

## 7. Bilib qo'yish kerak

- **Bitta bot tokeni — bitta jarayon.** Server ishga tushgach mahalliy
  kompyuterdagi botlarni **to'xtating**. Ikkalasi bir vaqtda polling
  qilsa Telegram xabarlarni ikkiga bo'lib beradi va javob bir marta
  keladi, bir marta yo'q.
- **SQLite bitta konteynerga mo'ljallangan.** Bir nechta nusxa
  (replica) ko'tarmang.
- **Image ~1.5 GB** — embedding modeli (~120 MB) va `onnxruntime`
  shunga kiradi. Model image ichiga oldindan yuklangan, shuning uchun
  birinchi savol kutib qolmaydi.
- **Texnik kesh** (`texnik_parametrlar.json`) birinchi so'ralganda
  ~80 sekundda yig'iladi va 7 kun saqlanadi. Uni ham diskka
  (`/data`) yozamiz.

---

## 8. Windows kompyuterda avtomatik ishga tushirish (hozirgi holat)

Bulutga chiqmasdan turib ham tizim kompyuter yoqilganda **o'zi
ko'tarilishi** mumkin. 2026-08-11 da shu sozlandi.

### Nima qilingan

**Vazifa rejalashtiruvchisida** (Task Scheduler) vazifa yaratildi:

| Sozlama | Qiymat |
|---|---|
| Nomi | `Jihozvent agentlar tizimi` |
| Tetik | Tizimga kirganda (30 sekund kechikish bilan) |
| Amal | `.venv\Scripts\pythonw.exe ishga_tushir.py` |
| Yiqilsa | Har daqiqada qayta urinadi, 999 martagacha |
| Batareyada | Ishlayveradi, uzilmaydi |

`pythonw.exe` — konsol oynasi ochilmaydi. Chiqish
`chiqish/ishga_tushir.log` fayliga yoziladi (5 MB dan oshsa eskisi
`.log.eski` bo'lib saqlanadi).

### ⚠️ UYQU — shart

Tekshirilganda kompyuter **15 daqiqa** ishlatilmasa uyquga ketardi.
Uyqudagi kompyuter Telegram'ga javob bermaydi va 09:00 dagi tender
tekshiruvi ishlamaydi — ya'ni butun avtomatlashtirish behuda.

Buni o'chirish (tarmoqqa ulangan holatda uxlamasin):

```bash
powercfg /change standby-timeout-ac 0
```

Ekran o'chishi muammo emas — faqat **uyqu** to'xtatilishi kerak.
Noutbukda qopqoqni yopganda ham uxlamasligi uchun:
Sozlamalar → Tizim → Quvvat → "Qopqoq yopilganda" → "Hech narsa".

### Boshqaruv buyruqlari

```bash
schtasks /query /tn "Jihozvent agentlar tizimi" /v /fo list
```

To'xtatish / qayta ishga tushirish:

```bash
schtasks /end /tn "Jihozvent agentlar tizimi"
```

```bash
schtasks /run /tn "Jihozvent agentlar tizimi"
```

### Cheklovlar (ochiq aytilgan)

- **Svet o'chsa** yoki kompyuter o'chirilsa — tizim to'xtaydi. Qayta
  yoqilganda o'zi ko'tariladi, lekin oradagi vaqt yo'qoladi.
- **Tizimga kirish kerak.** Vazifa "tizimga kirganda" ishlaydi. Agar
  kompyuter yonib, lekin hech kim kirmasa — ko'tarilmaydi.
- **Panel faqat shu kompyuterda.** Telegram botlar esa har qanday
  qurilmadan ishlaydi — tizim qayerda turgani ahamiyatsiz.
- Bulutga o'tganda bu vazifani **o'chirish kerak** (`schtasks /delete`),
  aks holda ikkita nusxa bir vaqtda polling qiladi va javob bir kelib,
  bir kelmaydi.
