# Agentlar tizimi

Kompaniya ichidagi vazifalarni bajaruvchi **9 ta AI agent** va markaziy
**LLM-router**. Foydalanuvchi tabiiy tilda so'rov beradi, router so'rovni tahlil
qilib, kontraktlarga qarab mos agent(lar)ni tanlaydi va ishga soladi.

Hozirgi holat: **6-bosqich** — Tijorat menejeri Temur va KP generatori
(Word + PDF) qo'shildi.

---

## 1. Nima tayyor

| Qism | Holat |
|---|---|
| Kontraktlar (`contracts/*.yaml`) | 9 ta, hammasi ulangan |
| Umumiy konvert (Pydantic) | `manba` va `ishonch` majburiy |
| Kompaniya profili (`config/company_profile.yaml`) | har agent chaqiruvida kontekstda |
| Climavent API (`integrations/`) | birlamchi manba, faqat o'qish, keshli |
| Router — LLM asosida | niyat → agent → xavf → **aniqlik** tekshiruvi |
| 12 ta agent | ✅ hammasi kodda ulangan |
| Tasdiq oqimi | bazada saqlanadi, server restartidan omon qoladi |
| Nazorat paneli (`/panel`) | jonli zanjir (SSE), tasdiqlar, tarix |
| **3D ofis** (`/ofis`) | bo'limlarga ajratilgan, agentlar yuradi (Three.js, lokal) |
| Log ko'rinishi (`/`) | saqlab qolindi — debug quroli |
| Telegram bot | bitta bot, whitelist + inline tasdiq tugmalari |
| Kunlik tender kuzatuvi | mos e'lon bo'lsa Telegramga o'zi yuboradi |
| KP menejeri | har xodimdan bir marta so'raladi, javob bazada saqlanadi |
| Bilim bazasi (`knowledge/` + `bilim/`) | RAG: gibrid qidiruv, 4888 bo'lak |
| Javob formatlash (`presenter/`) | texnik maydonlarsiz odamcha matn |
| Router meta-javoblari | tizim savollariga o'zi javob beradi |
| Konstruktiv rad etish | taklif bilan, quruq "agent yo'q" emas |
| KP generatori (`kp/`) | Word + PDF, takrorlanmas raqam |
| Testlar | 331 ta (tarmoqqa chiqmaydi) |

## 2. Agentlar

| Rol nomi | Interfeysda | Xavf | Nima qiladi |
|---|---|---|---|
| `price-monitor` | Narx analitigi Zara | past | Bozor narxlarini kuzatadi |
| `competitor-watch` | Raqobat tahlilchisi Karim | past | Raqib topilmalari + tahliliy xulosa |
| `product-spec` | Mahsulot mutaxassisi Sardor | past | Texnik spesifikatsiya + talab bo'yicha tanlash (narxsiz) |
| `data-query` | Ma'lumot muhandisi Doston | o'rta | Bazadan SELECT, yozish — tasdiq bilan |
| `marketing` | Marketolog Malika | o'rta | Kommunikatsiya va kontent (nashr qilmaydi) |
| `sales-strategy` | Savdo strategi Bekzod | o'rta | Savdo rejasi, kanal, KPI (strategiya) |
| `proposal-builder` | Tijorat menejeri Temur | o'rta | KP hujjati (Word/PDF), narx to'qimaydi |
| `hr-assist` | HR menejeri Hilola | yuqori | HR qoralamasi (yakuniy qaror emas) |
| `legal-review` | Yurist Laziz | yuqori | Huquqiy tahlil (imzolamaydi) |
| `catalog-admin` | Katalog administratori Nodira | yuqori | Katalogga yozish (CRUD) — har amal tasdiq bilan |
| `tender-watch` | Tender kuzatuvchisi Jasur | past | Xarid e'lonlarini kuzatadi (ariza topshirmaydi) |
| `smm-analyst` | SMM tahlilchisi Nilufar | past | Instagram profil tahlili (nashr qilmaydi) |

## 3. Ishga tushirish

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

`.env` ichiga `ANTHROPIC_API_KEY` ni yozing, keyin:

```bash
.venv\Scripts\uvicorn app.main:app --reload
```

- `http://127.0.0.1:8000/ofis` — **pixel-art ofis** + ishchi panellar
- `http://127.0.0.1:8000/panel` — nazorat paneli
- `http://127.0.0.1:8000/` — oddiy log ko'rinishi (debug)
- `http://127.0.0.1:8000/docs` — API hujjati

Kalitsiz ham ilova ko'tariladi; `POST /sorov` `503` qaytaradi va sababini aytadi.

## 4. Endpoint'lar

| Metod | Yo'l | Vazifa |
|---|---|---|
| `POST` | `/sorov` | So'rov: reja + qadamlar + yakuniy konvert |
| `GET` | `/tasdiq` | Kutilayotgan tasdiqlar |
| `POST` | `/tasdiq/{iz_id}` | Tasdiqlash / rad etish (zanjir davom etadi) |
| `GET` | `/agentlar` · `/agentlar/{rol}` | Agentlar va kontraktlar |
| `GET` | `/agent-faoliyati` | Har agentning oxirgi holati |
| `GET` | `/statistika` | Panel ko'rsatkichlari |
| `GET` | `/events` | Jonli yangilanish (SSE) |
| `GET` | `/izlar` · `/izlar/{id}` | Log |
| `GET` | `/salomat` | Tizim holati |

Testlar:

```bash
.venv\Scripts\python -m pytest -q
```

## 5. Umumiy konvert

```json
{
  "kim": "price-monitor",
  "holat": "tugadi",
  "natija": { },
  "manba": [{ "tur": "veb", "nom": "Olcha.uz", "havola": "https://...", "sana": "2026-07-20" }],
  "ishonch": "yuqori",
  "tasdiq_kerak": false,
  "izoh": "1 ta narx topildi"
}
```

**Majburiy:** `holat = tugadi` bo'lganda `manba` bo'sh bo'lolmaydi — buni
Pydantic validatori tekshiradi.

### Holat turlari

Uch xil vaziyat bir xil "xato" yorlig'ini olmasligi kerak:

| Qiymat | Ma'nosi | Rang |
|---|---|---|
| `tugadi` | Muvaffaqiyatli bajarildi | yashil |
| `tasdiq_kutilmoqda` | Inson tasdig'i kutilmoqda | sariq |
| `aniqlik_kerak` | Zarur ma'lumot yo'q — savol berildi, agent chaqirilmadi | binafsha |
| `mos_agent_yoq` | Hech qaysi agent bajara olmaydi — **normal javob** | kulrang |
| `ulanmagan` | Kontrakt bor, kod yo'q | ko'k |
| `xato` | Haqiqiy nosozlik (API yiqildi, parse xatosi) | qizil |

## 6. Tuzilma

```
app/
  main.py             FastAPI: endpoint'lar, SSE, log ko'rinishi
  orkestr.py          Reja bajarish, zanjir, tasdiqdan keyin davom ettirish
  router.py           LLM-router: niyat -> agent -> xavf tekshiruvi
  kontraktlar.py      YAML kontraktlar
  konvert.py          Umumiy konvert (Holat, Ishonch, Manba, Konvert)
  llm.py              Anthropic qatlami
  sxema.py            Structured output uchun qat'iy JSON Schema
  baza.py             SQLite: log, tasdiqlar, narxlar, ish jadvallari
  profil.py           Kompaniya profilini o'qish va promptga aylantirish
  agentlar/           12 ta agent (asos.py — umumiy shablon)
  static/             panel.* (nazorat paneli)
                      ofis-model.js (xarita + agent holati)
                      ofis3d.js + vendor/three.module.js (3D ofis)
config/
  company_profile.yaml   Kompaniya profili — kodga tegmasdan tahrirlanadi
integrations/
  climavent_client.py    Ichki API klienti (faqat o'qish, keshli)
  climavent_yozuvchi.py  Katalogga yozish (faqat Nodirada)
  tender_manba.py        Tender e'lonlari manbalari (pluggable)
  instagram_klient.py    Instagram Graph API (faqat o'qish)
docs/
  climavent-api.md       API sxemasi: qaysi endpoint nima beradi
bilim/
  bolak.py            Hujjatni bo'laklarga ajratish (qonun — modda bo'yicha)
  indeks.py           Indekslash (`python -m bilim.indeks`)
  qidiruv.py          Gibrid qidiruv: semantik + BM25, papka izolyatsiyasi
  yuklab_ol.py        lex.uz dan qonun yuklash (`python -m bilim.yuklab_ol`)
knowledge/
  umumiy/ legal/ hr/ marketing/ product/ market/ sales/
presenter/
  matn.py             Umumiy formatlash qoidalari
  agentlar.py         Har agent uchun maxsus ko'rinish
bot/
  asosiy.py           Telegram bot (mantiq yo'q — Orkestrni chaqiradi)
  ruxsat.py           Whitelist + agent darajasidagi ruxsat
  formatlash.py       Konvertni o'qish qulay matnga aylantirish
contracts/            12 ta agent kontrakti (YAML)
tests/                331 ta test (tarmoqqa chiqmaydi)
```

## 7. Router mantig'i

1. **Niyat** — nechta vazifa bor? Bitta → bitta agent, bir nechta → zanjir.
2. **Agent tanlash** — kontraktdagi *chegaralar* asosida. Hech kim mos
   kelmasa `mos_agent_yoq` va ochiq izoh.
3. **Xavf tekshiruvi** — xavfi `yuqori` agentlarga (Hilola, Laziz) tasdiq
   **kodda majburan** qo'yiladi, LLM "unutib" qo'ysa ham.
4. **Aniqlik tekshiruvi** — zarur ma'lumot yetishmasa, agentlar **umuman
   chaqirilmaydi**: `aniqlik_kerak` holati bilan aniq savol qaytariladi.
   Profildan yoki API'dan olinadigan narsa uchun savol berilmaydi.

Kompaniya profili va kontraktlar prompt ichida `cache_control` bilan
keshlanadi.

## 7a. Kompaniya profili

`config/company_profile.yaml` har agent chaqiruvida promptga qo'shiladi —
shuning uchun agent "kompaniya nomi ko'rsatilmagan" deb bo'sh javob
qaytarmaydi.

- To'ldirilmagan maydon **bo'sh qoladi va promptga umuman tushmaydi** —
  "noma'lum" yozuvi modelni to'qishga undamasligi uchun.
- Faylni kodga tegmasdan tahrirlash mumkin.
- Karim raqobatchilar ro'yxatini shu profildan oladi (manba turi: `profil`).

## 7b. Climavent API — birlamchi manba

Hujjat: [`docs/climavent-api.md`](docs/climavent-api.md).

- **O'qish uchun token kerak emas** — katalog ochiq (137 mahsulot, 35 kategoriya).
- Klientda **yozish metodlari umuman yo'q** — agent yozish endpointiga
  murojaat qila olmaydi (kodda ta'minlangan, promptda emas).
- API ishlamasa xato yutilmaydi: agent "ichki manba mavjud emas" deydi.
- Javoblar 5 daqiqa keshlanadi.

**Sardor** avval ichki katalogdan qidiradi, faqat topilmasa tashqi vebga
o'tadi. Manba turi javobda aniq ko'rinadi: `ichki_api` yoki `tashqi_veb`.

Model kodlari (VK-250) mahsulot nomida emas, `models[]`/`characters[]` ichida
va **kirillcha** yozilgan (ВК-250П). Shuning uchun klient lotin/kirill
moslashuvini o'zi bajaradi va butun katalogni ko'rib chiqadi.

**Narxlar:** 137 mahsulotning 136 tasida `price = 0` — ya'ni narx
kiritilmagan. Zara buni ochiq aytadi va tashqi bozor narxini
kompaniyaning o'z narxi sifatida **ko'rsatmaydi** (`tashqi_bozor: true`).

## 8. Tasdiq oqimi

1. Agent `tasdiq_kutilmoqda` bilan qaytaradi;
2. zanjir **to'xtaydi**, natija va tasdiq **bazaga** yoziladi;
3. panel yoki bot tasdiq so'raydi;
4. inson tasdiqlaydi yoki rad etadi;
5. tasdiqlansa — zanjir davom etadi; rad etilsa — to'xtaydi va sabab yoziladi.

Holat xotirada emas, bazada: server qayta ishga tushsa ham yo'qolmaydi.

**Ikki xil tasdiq bor:**

- *natija tayyor, tasdiq uni ochadi* (Malika, Hilola, Laziz) — agent qayta
  chaqirilmaydi;
- *harakat kutilmoqda, tasdiq uni ishga tushiradi* (Doston, Nodira) — SQL yoki
  katalog amali faqat taklif qilinadi, tasdiqdan keyin bajariladi.

Ikkinchi xilini `orkestr.TAKLIF_MAYDONLARI` aniqlaydi: konvertda `taklif_sql`
yoki `taklif_amal` bo'lsa, agent tasdiqdan keyin QAYTA chaqiriladi.

## 9. Xavfsizlik: Doston (`data-query`)

Himoya **promptga tayanmaydi**, SQLite darajasida:

- `sqlite3.set_authorizer` — `DELETE` / `DROP` / `TRUNCATE` / `ALTER` /
  `ATTACH` / `PRAGMA` va ruxsat etilmagan jadvallar **rad etiladi**, yozish
  ruxsati berilgan ulanishda ham;
- o'qish ulanishi `mode=ro` bilan ochiladi — yozish jismonan imkonsiz;
- `execute` bitta buyruq bilan cheklangan — `;` orqali ikkinchisi qo'shilmaydi;
- so'rovga 5 soniyalik chegara (`set_progress_handler`).

Sinalgan va rad etilgan: to'g'ridan-to'g'ri `DELETE`/`DROP`, CTE va ichki
so'rov orqali maxfiy jadvalga kirish, `UNION`, `sqlite_master`, trigger
yaratish, rekursiv CTE.

**Hilola (`hr-assist`)** uchun cheklov ham kodda: `baza.xodimlar()` faqat
`HR_RUXSAT_ETILGAN_MAYDONLAR` ustunlarini o'qiydi — `maosh` va `telefon`
LLM promptiga hech qachon tushmaydi.

## 10. Panel va ofis

`GET /panel` — nazorat paneli:

- izometrik agentlar ko'rinishi, **so'rov maydoni**, **statistika**,
  **joriy zanjir** (qaysi qadam tugadi, qaysi biri ishlayapti, qaysi biri
  kutmoqda), **tasdiq bloki** tugmalar bilan, **tarix**.

`GET /ofis` — pixel-art ofis (tepada manzara, ostida o'sha ishchi panellar):

- yuqoridan qaralgan 2D ofis: ochiq ish maydoni, HR xonasi, yurist kabineti,
  majlis xonasi, oshxona, yo'laklar, mebel va o'simliklar;
- har agent o'z stolida; **yura oladi** — grid bo'yicha BFS yo'l topish,
  4 tomonlama yurish animatsiyasi;
- holatga bog'liq xatti-harakat: ishlayapti/tugadi → stolga qaytadi;
  `tasdiq_kutilmoqda` → **majlis xonasiga boradi va kutadi**; ulanmagan
  agent ofisda ko'rinmaydi;
- yorliqda lavozim + ism, holat matni va rangli nuqta; yorliq chegarasi —
  xavf darajasi;
- kamera: sichqoncha bilan surish, g'ildirak yoki +/− bilan zum;
- agentni bosganda kontrakti va oxirgi ishi ochiladi.

Spritlar **kodda chiziladi** — tashqi asset yo'q, litsenziya masalasi yo'q.
Kutubxona ishlatilmagan (toza Canvas), shuning uchun build qadami ham yo'q.

Jonli yangilanish — SSE (`/events`). Server bazadagi o'zgarish belgisini
kuzatadi, shuning uchun bir nechta worker bilan ham ishlaydi. Orkestr har
qadamdan keyin izni yangilaydi — zanjir haqiqatan jonli ko'rinadi.

## 11. Telegram bot

**Bitta bot, 7 ta emas** — tizim router atrofida qurilgan, foydalanuvchi qaysi
agent kerakligini bilishi shart emas. Alohida botlar zanjirli so'rovni
imkonsiz qilardi.

Botda mantiq yo'q: u `Orkestr`ni chaqiradi, xolos.

```bash
.venv\Scripts\python -m bot.asosiy
```

`.env` ga qo'shing (kodda emas):

```
BOT_TOKEN=BotFather bergan token
BOT_RUXSAT_ETILGAN_ID=123456789,987654321
BOT_HR_RUXSAT_ID=123456789
```

- `BOT_RUXSAT_ETILGAN_ID` **bo'sh bo'lsa bot hech kimga javob bermaydi** —
  ataylab shunday (xavfsiz standart).
- `BOT_HR_RUXSAT_ID` — HR ma'lumotiga kim murojaat qila oladi. Bu tekshiruv
  router reja tuzgandan **keyin**, agent ishga tushishidan **oldin** bo'ladi.
- O'z ID'ingizni bilish uchun botga yozing — u ruxsat yo'qligini aytib
  ID'ingizni ko'rsatadi.

## 12. Model

`.env` dagi `LLM_MODEL` bilan belgilanadi. Router arzon bo'lishi uchun
`ROUTER_EFFORT=low`, agentlar uchun `AGENT_EFFORT=medium`.

## 13. O'zgarmas qoidalar

- Hech bir agent o'chirish (DELETE / DROP / TRUNCATE) huquqiga ega emas
- Hech bir agent to'lov qilmaydi
- Hech bir agent hujjat imzolamaydi yoki yubormaydi
- Hech bir agent kontent nashr qilmaydi
- Ma'lumot topilmasa — "topilmadi" deyiladi, to'qib chiqarilmaydi
- Har javobda manba va ishonch darajasi bo'ladi
- Yuqori xavfli agentlar (Hilola, Laziz, Nodira) natijasi inson tasdig'isiz
  chiqmaydi; Nodira esa tasdiqsiz katalogga BITTA ham so'rov yubormaydi
- Agentlar bir-birining ishiga aralashmaydi
- Ichki API — birlamchi manba, tashqi veb — ikkilamchi
- Manba turi har doim ko'rsatiladi (`ichki_api` / `tashqi_veb` / `profil`)
- Narxlar hozircha tizimda yo'q — tashqi narx o'z narximiz sifatida
  ko'rsatilmaydi
- Doston yozish endpointlariga murojaat qilmaydi (klientda bunday metod yo'q)
- Katalogga yozish faqat Nodirada: `ClimaventYozuvchi` alohida klass, boshqa
  agentlarda u umuman yo'q. Amal, metod va yo'l 9 ta oldindan belgilangan
  jadvaldan olinadi — model ixtiyoriy endpoint ko'rsata olmaydi
  (`docs/climavent-api.md`)


## 14. Bilim bazasi (RAG)

Agentlar "o'qitilmaydi" — ularga qidiriladigan baza beriladi. Savol kelganda
tegishli parchalar topiladi, kontekstga qo'shiladi, javob **shu matnga**
asoslanadi va manba ko'rsatiladi.

```bash
.venv\Scripts\python -m bilim.indeks          # o'zgarganini indekslash
.venv\Scripts\python -m bilim.indeks --hammasi
.venv\Scripts\python -m bilim.yuklab_ol       # lex.uz dan qonunlarni yuklash
```

**Papka izolyatsiyasi.** Har agent faqat o'z papkasi + `umumiy` dan qidiradi:

| Agent | Papkalar |
|---|---|
| `legal-review` | legal, umumiy |
| `hr-assist` | hr, umumiy |
| `marketing` | marketing, umumiy |
| `product-spec` | product, umumiy |
| `competitor-watch` | market, umumiy |
| `proposal-builder` | sales (faqat — KP manbalari aralashmasin) |
| `catalog-admin` | umumiy |

**Texnik yechim:**

- **Chunking:** qonun — modda bo'yicha (`173-модда` alohida bo'lak), oddiy
  matn — sarlavha + hajm bo'yicha (~2400 belgi, 400 belgi ustma-ust);
- **Embedding:** `paraphrase-multilingual-MiniLM-L12-v2` (fastembed/ONNX,
  ~120MB, oflayn). Vektorlashda parchaga hujjat nomi va bo'lim sarlavhasi
  qo'shiladi;
- **Gibrid qidiruv:** semantik + BM25, Reciprocal Rank Fusion bilan;
- **Kirill/lotin:** qonunlar kirillcha (lex.uz), so'rov lotincha — BM25
  tokenizatsiyasida transliteratsiya qilinadi, aks holda mos kelmaydi;
- **Saqlash:** mavjud SQLite (`bilim_hujjat`, `bilim_bolak`) — alohida
  vektor bazasi kerak emas, korpus kichik.

Vault (`Jihozvent-Vault`) **joyida** indekslanadi — nusxa ko'chirilmaydi,
Obsidian'da tahrirlashda davom etish mumkin.

## 15. Javob formatlash (`presenter/`)

Tizim ichida konvert strukturalangan bo'lib qoladi; foydalanuvchiga esa
odamcha matn chiqadi:

- texnik maydonlar (`manba_turi`, `havola`, `sql`) **ko'rsatilmaydi**;
- bo'sh maydonlar umuman chiqmaydi;
- uzun ro'yxatlar qisqartiriladi ("yana 5 ta");
- manba oxirida bitta qatorda;
- ishonch past bo'lsa — ogohlantirish qatori;
- har holat uchun tushunarli xabar (tizim jim qolmaydi), zanjir to'xtasa
  qaysi qadamda to'xtagani aytiladi.


## 16. Tizim savollari va konstruktiv rad etish

**Tizim savollari.** "Qanday agentlar bor?", "Malika nima qiladi?", "Sen nima
qila olasan?" — bularga router O'ZI javob beradi, agent chaqirilmaydi.
Javob agent kontraktlaridan olinadi (o'ylab topilmaydi), shuning uchun
manba turi `kontrakt` bo'ladi.

Javob quruq ro'yxat emas: har agent uchun nima qila oladi (misollar bilan),
nima qilmaydi (chegarasi) va oxirida tayyor so'rov namunalari.

**Konstruktiv rad etish.** `mos_agent_yoq` qaytarishdan oldin router ikki
tekshiruv qiladi:

1. **Parchalash** — so'rovni mayda vazifalarga bo'lib, mavjud agentlardan
   zanjir tuzsa bo'ladimi? Bo'lsa — zanjir quriladi, rad etilmaydi.
2. **Qisman bajarish** — bir qismi bajarilsa, o'shani bajaradi.

Chindan hech nima qilib bo'lmasa ham javob uch qismli bo'ladi: nima qila
olmaydi → nima qila oladi → qanday so'rash kerak. Quruq "agent yo'q" +
ro'yxat yaroqsiz javob hisoblanadi.

## 17. Malika va Bekzod chegarasi

Chegaraning maqsadi — agentlar bir-birining ishiga aralashmasligi, foydalanuvchini
rad etish emas.

| | Malika (`marketing`) | Bekzod (`sales-strategy`) |
|---|---|---|
| **Doira** | kommunikatsiya va kontent | tijorat va reja |
| **Beradi** | kampaniya g'oyasi, reklama matni, kanal xabari, brend ohangi | savdo maqsadlari, kanal taqsimoti, KPI, KP, narx **taklifi** |
| **Bermaydi** | savdo rejasi, KPI, KP | reklama matni, kreativ kontent |

Bekzod narxni **belgilamaydi** — faqat taklif beradi, qaror rahbariyatniki.
KP yoki narx taklifi bo'lgan har javob inson tasdig'idan o'tadi.


## 18. KP generatori (Temur)

Bekzod — strategiya (chorakda bir marta), Temur — operatsion ish (kunlik):
mijoz so'rovidan rasmiy tijorat taklifi va hujjat.

```
kp/
  model.py    KP ma'lumot modeli va hisob-kitob (summa, QQS)
  narx.py     Narx manbai va rekvizitlar
  hujjat.py   Word (python-docx) va PDF (reportlab) generatorlari
knowledge/sales/
  narxlar.yaml       Narx ro'yxati — qo'lda yuritiladi
  rekvizitlar.yaml   Kompaniya rekvizitlari
```

**Narx.** Ichki API'da narx yo'q, shuning uchun `knowledge/sales/narxlar.yaml`
dan olinadi. Uchta himoya bir-birini qo'llab-quvvatlaydi:

1. modelning javob sxemasida narx maydoni **umuman yo'q** — to'qib bo'lmaydi;
2. narx faqat ro'yxatdan o'qiladi, model qaytargani e'tiborga olinmaydi;
3. `amal_qilish_kuni` dan eski (yoki sanasiz) narx **ishlatilmaydi**.

Narx topilmasa ustun bo'sh qoladi, hujjatda qizil `[narx to'ldirilishi kerak]`
belgisi va ogohlantirish chiqadi.

**Raqamlash.** `KP-2026-0001` shaklida, `kp_raqamlari` jadvalida `(yil, tartib)`
ustida UNIQUE indeks bilan — bir vaqtdagi so'rovlar ham bir xil raqam ololmaydi.

**Hujjat.** Har KP ikkala formatda chiqadi: `.docx` tahrirlash uchun, `.pdf`
yuborish uchun. Fayllar `chiqish/kp/` da. Kirill matn uchun Arial/DejaVu
shrifti ishlatiladi.

**Tasdiq.** KP — mijozga ketadigan rasmiy hujjat, shuning uchun `tasdiq_kerak`
har doim `true`. Tizim hujjatni hech qachon o'zi yubormaydi.

### 18a. TZ ↔ KP tekshiruvchi

Menejer tuzgan KP ni TZ bilan solishtiradi va farqlarni ko'rsatadi:
KP ga kirmagan qurilma, almashgan o'lcham, kuchlanish/filtr/rekuperator
farqi, KP ichida nusxa qilingan tavsif. **Hech narsani tuzatmaydi** —
farqning bir qismi menejerning ongli qarori bo'lishi mumkin.

```
kp/
  kp_pdf.py     Climavent KP PDF -> qatorlar (pypdf, koordinata bo'yicha;
                «Итого» bilan yig'indi tekshiriladi)
  tz_jadval.py  Excel TZ -> qatorlar MIQDORI bilan (ro'yxat, spetsifikatsiya,
                zayavka; bir xil varaqlar bir marta sanaladi)
  ventas.py     VENTAS HVACCALC tanlov PDF -> qurilma parametrlari
  solishtir.py  (oila, kalit) bo'yicha yig'ib solishtirish va hisobot
knowledge/product/tz_oilalari.yaml   TZ nomi va KP nomini bir oilaga bog'lash
```

    python -m skriptlar.tz_tekshir KP.pdf TZ.xlsx [TZ2.xlsx | papka/]

Etalon — 7 juft haqiqiy TZ va KP, `tests/etalon_tz/` (mijoz hujjatlari,
git ga kirmaydi). `tests/test_tz_tekshiruv.py` ularda qo'lda tasdiqlangan
farqlarni topishni talab qiladi; papka yo'q bo'lsa bu testlar o'tkazib
yuboriladi. Hozircha o'qilmaydi: skan PDF, rasm, DWG, arxiv.

## 19. Xaridor ilovasidagi yordamchi (`yordamchi/`)

Climavent xaridor ilovasida «Climavent yordamchi» chati bor. Mijoz kechasi
yozsa ham javob darhol keladi: yordamchi hisoblaydi, katalogdan mahsulot
tanlaydi va ularni **kartochka** qilib qaytaradi. Mijoz kartochkadan savatga
qo'shadi va KP ni ilovada darhol oladi.

Bu mijozlar botining ilova yo'li. Zanjir o'sha-o'sha: ruxsat
(`bot/mijoz_ruxsat.OCHIQ_AGENTLAR`), suhbat konteksti (`bot/suhbat.py`,
kanal `ilova`), narx qidiruvi (`sorovnoma/narx_sorov.py`) va mijoz matni
(`presenter`). Telegramdan farqi:

- raqam so'ralmaydi, chunki ilovaga faqat telefon bilan kiriladi;
- javob bilan katalog id'lari qaytadi, faqat ANIQ moslik bo'yicha;
- har savol menejerga ichki bot orqali boradi (`💬 Ilovadan savol`).

| Fayl | Vazifa |
|---|---|
| `yadro.py` | xabar → javob, Telegramsiz |
| `kirish.py` | ilova tokenini backendning o'zida tekshiradi (`GET /api/users/one/{id}`), JWT ichidagi id ham solishtiriladi |
| `api.py` | internetga ochiq server, faqat `POST /yordamchi/xabar` va `GET /salomat` |

**Alohida server.** Ichki panel (`app.main`) faqat ichki tarmoqqa ochiladi.
Yordamchi esa internetga ochiq, shuning uchun u ALOHIDA xizmat sifatida
ishlaydi: o'sha Docker obraz, boshqa start buyrug'i.

```bash
.venv\Scripts\python -m yordamchi          # lokal, port 8000 (PORT bilan o'zgaradi)
```

Railway (yangi xizmat, shu repo):

- Start command: `python -m yordamchi`, healthcheck: `/salomat`;
- disk `/data` ga ulanadi (`BAZA_YOLI=/data/yordamchi.db`);
- muhit: `ANTHROPIC_API_KEY`, `MIJOZ_BOT_MODEL`, `BOT_TOKEN` (lid xabarlari
  uchun), `MIJOZ_BOT_MENEJER_ID`, `YORDAMCHI_KUNLIK_LIMIT`. Ichki xizmat
  kalitlari (SAP, servis kaliti, Instagram) bu serverga BERILMAYDI.

Murojaatlar shu serverning o'z bazasida qoladi (`tg_id = ilova:<id>`).
Menejer ularni Telegram xabaridan ko'radi. Ichki botning `/murojaatlar`
buyrug'i boshqa bazani o'qigani uchun ularni ko'rsatmaydi.

Ilova tomoni: `climavent-xaridor/lib/features/assistant/`. Server manzili
`--dart-define=ASSISTANT_BASE=https://...` bilan beriladi. Manzil berilmasa
yordamchi ilovada umuman ko'rinmaydi.
