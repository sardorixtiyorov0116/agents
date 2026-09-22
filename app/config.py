"""Sozlamalar — .env faylidan yoki muhit o'zgaruvchilaridan o'qiladi."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ILDIZ = Path(__file__).resolve().parent.parent

log = logging.getLogger("sozlama")


# `TEZ_ROLLAR_ROYXATI` da shu belgi tursa — HAMMA rol tez modelga
# o'tadi. Rollarni bittalab sanash mo'rt: yangi agent qo'shilganda uni
# ro'yxatga qo'shish unutiladi va u jimgina eski modelda qolib ketadi.
HAMMA_ROL = "*"


class Sozlama(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ILDIZ / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str | None = None

    # Model ID'lari doim to'liq ko'rinishda beriladi, sana qo'shilmaydi.
    #
    # Bu yerdagi qiymat `.env` dagi LLM_MODEL bilan BIR XIL bo'lishi kerak.
    # Aks holda `.env` siz ishga tushirilganda tizim jimgina boshqa (va
    # qimmatroq) modelga o'tib ketadi va buni hech kim sezmaydi.
    llm_model: str = "claude-sonnet-4-6"

    # TEZ MODEL — yengil ishlar uchun.
    #
    # Hamma agent bir xil modelda ishlashi shart emas. Ba'zi ish "o'ylash"
    # emas, "ajratish": reja tuzuvchi 15 ta nomdan bittasini tanlaydi,
    # Rustam matndan raqam ajratadi (formulaning o'zi kodda). Bunday ish
    # uchun arzonroq va tezroq model yetarli — sifat tushmaydi, vaqt esa
    # sezilarli qisqaradi.
    #
    # Bo'sh qoldirilsa hamma `llm_model` da ishlaydi (eski holat).
    # Bitta nom yoki VERGUL bilan ajratilgan zaxira zanjiri:
    #
    #     TEZ_MODEL=gemini-3.5-flash,claude-haiku-4-5
    #
    # Birinchisi yiqilsa (kvota, 429, 503, tarmoq) keyingisi urinadi
    # (`app/zanjir.py`). Bitta nom yozilsa hech qanday o'ram
    # qo'shilmaydi va xatti-harakat avvalgidek qoladi.
    tez_model: str = "claude-haiku-4-5"
    # Tez modelda ishlaydigan rollar (vergul bilan). `router` — reja
    # tuzuvchi (u agent emas, lekin har so'rovda chaqiriladi).
    #
    # Bu yerga SIFAT MUHIM bo'lgan agentni qo'shmang: Sardor uskuna
    # tanlaydi, Temur mijoz o'qiydigan matnni yozadi.
    #
    # `*` — HAMMA rol tez modelga o'tadi (`HAMMA_ROL`).
    #
    # XONA TURI — eng nozik joy. 2026-08-17 da o'lchanganda Haiku 4.5
    # restoran/kafeni "dokon" deb tanlagan edi — 6 sinovdan 6 tasida.
    # Natija: 250 m² restoranga 12 000 o'rniga 4 800 m³/soat (2,5
    # barobar kam), Ø900 o'rniga Ø560 kanal. Shu sababli `hvac-calc`
    # uzoq vaqt chetda turgan edi.
    #
    # 2026-08-26 da Gemini 3.5 Flash shu sinovdan O'TDI — 5 tadan 5 tasi
    # to'g'ri (restoran, kafe, sex, savdo zali, sanuzel). Shuning uchun
    # `*` ga o'tkazildi.
    #
    # MAXFIYLIK: Google BEPUL tarifda so'rovlarni model o'qitish uchun
    # ishlatishi mumkin. `*` bilan mijoz nomi, narx va (hr-assist
    # orqali) maosh ham Gemini'ga boradi. Bu ONGLI qaror edi — Anthropic
    # hisobida mablag' tugagani uchun muqobil yo'l yo'q edi. Hisob
    # to'lganda bu qatorni `router` ga qaytaring.
    tez_rollar_royxati: str = "router"

    # --- Zaxira provayder (Gemini) ---
    #
    # `TEZ_MODEL` nomi "gemini" bilan boshlansa, tizim shu kalitni
    # ishlatadi (`app/gemini.py`). Bo'sh bo'lsa Gemini umuman yoqilmaydi.
    #
    # DIQQAT: Google BEPUL tarifda so'rovlarni model o'qitish uchun
    # ishlatadi. Mijoz ismi, telefoni, narx va maosh ko'radigan rollarni
    # `TEZ_ROLLAR_ROYXATI` ga QO'SHMANG.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"

    # Bepul tarif limitlari. STANDART QIYMAT 0 = "noma'lum".
    #
    # Aniq son ATAYLAB yozilmadi: Google bepul tarif chegaralarini
    # e'lonsiz o'zgartiradi va modelga qarab har xil. Kodga taxminiy
    # raqam yozilsa, `/sarf` ishonchli ko'rinishda NOTO'G'RI foiz
    # ko'rsatardi — sonini umuman bilmaganimizdan yomonroq.
    #
    # Haqiqiy sonni Google AI Studio -> "Rate limits" da ko'rib,
    # `.env` ga yozing. Nol bo'lsa `/sarf` faqat sarflangan sonni
    # ko'rsatadi, foizni emas.
    gemini_kunlik_limit: int = 0
    gemini_daqiqalik_limit: int = 0

    router_effort: str = "low"
    agent_effort: str = "medium"
    maks_token: int = 8000

    # Panel paroli. BO'SH BO'LSA panel faqat mahalliy ulanishga javob
    # beradi (`app/himoya.py`) — serverda uni qo'yish SHART, aks holda
    # izlar, KP mazmuni va `/sorov` tashqariga ochilib qoladi.
    panel_paroli: str | None = None

    baza_yoli: str = "agentlar.db"
    # `mijozlar`, `buyurtmalar`, `xodimlar` jadvallari HAQIQIY ma'lumotmi?
    #
    # Standart qiymat `False` — chunki hozir ular NAMUNAVIY qatorlar bilan
    # to'ldirilgan (`_urugla`). Doston va Hilola javobiga ogohlantirish
    # qo'shadi: menejer soxta raqamni haqiqat deb qabul qilmasligi kerak.
    # Real baza ulangach `.env` da `ISH_BAZASI_HAQIQIY=true` qilinadi.
    ish_bazasi_haqiqiy: bool = False
    kontraktlar_yoli: str = "contracts"
    profil_yoli: str = "config/company_profile.yaml"
    maks_qadam: int = 4

    # --- Lokal model (Ollama) — zanjirning oxirgi halqasi ---
    #
    # Bulut kvotasi tugaganda ishlaydi. Sifati o'lchangan va PASTROQ
    # (`app/ollama.py` dagi raqamlar), shuning uchun faqat oxirida
    # turadi — birinchi qatorga qo'yilsa sifat jimgina tushadi.
    ollama_asos: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # --- Bilim bazasi (RAG) ---
    bilim_yoli: str = "knowledge"
    # Obsidian vault joyida indekslanadi (nusxa ko'chirilmaydi).
    vault_yoli: str = r"D:\AGENTS\Jihozvent-Vault"
    # Embedding modeli.
    #
    # O'LCHANDI (2026-09-07): oldingi model (paraphrase-multilingual-MiniLM)
    # 50 tilni qamrardi va O'ZBEKCHA ular orasida yo'q edi. Natijada
    # semantik qidiruv faqat so'z mos kelganda ishlardi:
    #   «Xonada juda shovqinli» -> qozonxona tortishma mashinalari (xato)
    #   «Ofisda havo dim»       -> tutun chiqarish ventilyatori (xato)
    # e5-large XLM-RoBERTa asosida, 100 tilni qamraydi (o'zbekcha bor):
    #   ikkala savol ham TO'G'RI hujjatni topdi.
    #
    # DIQQAT: model almashtirilsa INDEKSNI QAYTA QURISH shart —
    # vektor o'lchami 384 dan 1024 ga o'zgaradi.
    bilim_model: str = "intfloat/multilingual-e5-large"
    # Agentga beriladigan parchalar soni.
    bilim_chek: int = 5
    # Tayyorlangan KP hujjatlari shu papkaga yoziladi.
    kp_yoli: str = "chiqish/kp"

    @property
    def tez_rollar(self) -> set[str]:
        """Tez modelda ishlaydigan rollar.

        `tez_model` bo'sh bo'lsa BO'SH to'plam qaytadi — ya'ni ro'yxatda
        nom qolib ketsa ham hech kim noma'lum modelga yuborilmaydi.
        """
        if not self.tez_modellar:
            return set()
        return {
            b.strip().lower()
            for b in re.split(r"[,;\s]+", self.tez_rollar_royxati or "")
            if b.strip()
        }

    # QIMMAT modelda qoladigan rollar — `TEZ_ROLLAR_ROYXATI=*` bo'lsa ham.
    #
    # NEGA TESKARI RO'YXAT. `TEZ_ROLLAR_ROYXATI` da hamma arzon rolni
    # sanash mo'rt edi: yangi agent qo'shilganda uni ro'yxatga qo'shish
    # unutiladi va u JIMGINA qimmat modelga tushib qolardi. Bu yerda
    # teskarisi — standart holat arzon, chetga chiqish esa ATAYLAB
    # yoziladi.
    #
    # KIMGA ARZIYDI. Uch mezon: xato PUL turadimi, ish MUHOKAMA
    # talab qiladimi, va KAM uchraydimi. Uchalasi mos kelsa qimmat
    # model o'zini oqlaydi:
    #
    #   legal-review     — shartnomadagi o'tkazib yuborilgan band
    #                      real pul turadi, kam uchraydi;
    #   sales-strategy   — maslahat asosida qaror qabul qilinadi;
    #   competitor-watch — tahlil va xulosa, mexanik ish emas.
    #
    # KIMGA ARZIMAYDI — bu o'lchangan, taxmin emas. `hvac-calc` xona
    # turini tanlaydi va 2026-08-17 da Haiku 4.5 uni 6 sinovdan 6 tasida
    # ADASHTIRGAN, Gemini Flash esa 5/5 to'g'ri topgan. Ya'ni "qimmatroq
    # — yaxshiroq" qoidasi bu yerda ishlamaydi.
    #
    # BO'SH QOLDIRILGAN: Anthropic hisobida mablag' yo'q. Ro'yxatga rol
    # yozilsa, u ishlamay qoladi. Hisob to'lgandan keyin to'ldiring.
    sekin_rollar_royxati: str = ""

    @property
    def sekin_rollar(self) -> set[str]:
        """Arzon modelga O'TKAZILMAYDIGAN rollar."""
        return {
            b.strip().lower()
            for b in re.split(r"[,;\s]+", self.sekin_rollar_royxati or "")
            if b.strip()
        }

    @property
    def tez_modellar(self) -> list[str]:
        """Zaxira zanjiri — tartib SAQLANADI.

        To'plam emas, ro'yxat: zanjirda tartib ma'noli, birinchisi
        asosiy. Takrorlar tashlanadi, aks holda bir model ikki marta
        sinalib vaqt ketardi.
        """
        korilgan: set[str] = set()
        natija: list[str] = []
        for nom in re.split(r"[,;\s]+", self.tez_model or ""):
            nom = nom.strip()
            if nom and nom.lower() not in korilgan:
                korilgan.add(nom.lower())
                natija.append(nom)
        return natija

    @property
    def hamma_rol_tezmi(self) -> bool:
        """Butun tizim tez modelda ishlaydimi (`TEZ_ROLLAR_ROYXATI=*`)."""
        return HAMMA_ROL in self.tez_rollar

    @property
    def bilim_papkasi(self) -> Path:
        yol = Path(self.bilim_yoli)
        return yol if yol.is_absolute() else ILDIZ / yol

    @property
    def vault_papkasi(self) -> Path | None:
        if not self.vault_yoli:
            return None
        yol = Path(self.vault_yoli)
        return yol if yol.is_dir() else None

    @property
    def kp_papkasi(self) -> Path:
        yol = Path(self.kp_yoli)
        return yol if yol.is_absolute() else ILDIZ / yol

    @property
    def texnik_kesh_fayli(self) -> Path:
        yol = Path(self.texnik_kesh_yoli)
        return yol if yol.is_absolute() else ILDIZ / yol

    @property
    def bilim_bolimlari(self) -> list[str]:
        return ["umumiy", "legal", "hr", "marketing", "product",
                "market", "sales", "montaj", "normativ"]

    # --- Climavent ichki API (birlamchi ma'lumot manbai) ---
    climavent_api_asos: str = "https://climavent-back-production.up.railway.app"
    # O'qish uchun token kerak emas. Quyidagilar KATALOGGA YOZISH uchun —
    # ikkalasidan biri bo'lsa Nodira ishlaydi, ikkalasi ham bo'sh bo'lsa yo'q.
    #
    # `service_api_key` — mashina uchun doimiy kalit (`X-API-Key` sarlavhasi).
    #   Afzal yo'l: eskirmaydi, bekor qilish oson (backendda env almashtiriladi).
    # `climavent_token` — odam sifatida kirib olingan JWT (`Bearer`).
    #   Eskiradi, shuning uchun faqat zaxira.
    service_api_key: str | None = None
    climavent_token: str | None = None
    climavent_kutish: float = 20.0
    # Havo sarfi/bosim jadvallari R2 dan yig'iladi (~4 daqiqa), shuning
    # uchun natija diskka keshlanadi. Katalog kamdan-kam o'zgaradi.
    texnik_kesh_yoli: str = "chiqish/texnik_parametrlar.json"
    texnik_kesh_kunlari: float = 7.0

    # `product_model_inside.price` — DOLLARDA saqlanadi (backend shunday
    # qaror qilgan, Swagger izohida ham yozilgan). So'm narxi bazada
    # SAQLANMAYDI — o'qiyotganda shu kursga ko'paytirib hisoblanadi.
    #
    # Ataylab shunday: kurs o'zgarganda 1482 yozuvni yangilash kerak emas,
    # faqat shu raqam almashadi. Ikki valyuta ustuni bo'lganda ular
    # bir-biriga zid bo'lib qolardi.
    #
    # DIQQAT: `product_models.price` va `characteristics.price` — SO'MDA.
    # Ularga bu kurs QO'LLANILMAYDI.
    #
    # BU QIYMAT — ZAXIRA, manba emas. Haqiqiy kurs backendda turadi
    # (`GET /api/settings/usd-rate`) va sayt ham o'shandan foydalanadi.
    # Bot alohida raqamdan hisoblasa, mijoz saytda bir narx, KP da
    # boshqa narx ko'radi. Shuning uchun `ClimaventKlient.kurs()`
    # birinchi, bu esa faqat backend javob bermaganda.
    usd_kursi: float = 12000.0
    # Narx siyosati: Markaziy bank kursiga qo'shiladigan ustama (%).
    #
    # Ko'p kompaniya narxni MB kursidan yuqoriroq oladi (bank/bozor
    # kursi bo'yicha). Shuning uchun MB kursi TO'G'RIDAN-TO'G'RI
    # qo'llanmaydi — u shu ustama bilan tavsiya qilinadi, qarorni esa
    # inson qabul qiladi. 0 bo'lsa — sof MB kursi.
    usd_ustama_foiz: float = 0.0
    # Kurs solishtiruvida shu foizdan katta farq "sezilarli" hisoblanadi
    # va menejerga xabar beriladi. Kunlik tebranish shovqin bo'lmasin.
    usd_farq_chegarasi: float = 1.0
    # Katalog tez-tez o'zgarmaydi — javoblar shuncha soniya keshlanadi.
    #
    # 2026-08-17 da o'lchandi: sovuq katalog 11.5 s yuklanadi (137 mahsulot
    # 2.2 s + 1482 model 9.3 s). Ilgari TTL 300 s edi — menejer 5 daqiqa
    # tanaffus qilsa, keyingi KP so'roviga o'sha 11.5 s qo'shilardi. Katalog
    # esa kuniga bir marta ham o'zgarmaydi, shuning uchun 6 soat.
    climavent_kesh_ttl: float = 21600.0

    # --- Instagram (SMM tahlili, faqat o'qish) ---
    # Meta Graph API tokeni va bizning Instagram Business akkaunt ID'imiz.
    # Ikkalasi ham bo'lmasa SMM tahlilchisi ishlamaydi va buni ochiq aytadi.
    instagram_token: str | None = None
    instagram_user_id: str | None = None
    instagram_kutish: float = 25.0

    # --- Telegram bot ---
    bot_token: str | None = None
    # Vergul bilan ajratilgan Telegram foydalanuvchi ID'lari.
    bot_ruxsat_etilgan_id: str = ""
    # HR ma'lumotiga murojaat qila oladigan ID'lar (umumiy ro'yxatning qismi).
    bot_hr_ruxsat_id: str = ""
    # Katalogni O'ZGARTIRA oladigan ID'lar. Bo'sh bo'lsa — umumiy ro'yxatdagi
    # hamma (har amal baribir tasdiqdan o'tadi).
    bot_katalog_ruxsat_id: str = ""
    # Bundan uzun natija fayl sifatida yuboriladi.
    bot_maks_belgi: int = 3000

    # --- Tender kuzatuvi (avtomatik) ---
    # Har kuni shu vaqt(lar)da tekshiriladi (mahalliy vaqt, "SS:DD").
    # VERGUL bilan bir nechta vaqt berish mumkin: "09:00,15:00".
    # Bo'sh bo'lsa avtomatik tekshiruv umuman yoqilmaydi.
    #
    # IKKI MARTA TEKSHIRISH — NEGA. Lotlarning muddati qisqa bo'lishi
    # mumkin (o'lchandi 2026-09-09: 13 ta lotdan 3 tasining muddati
    # o'sha kuni tugardi). Kuniga bir marta tekshirilsa, ertalab
    # chiqqan lot ertasi kungacha ko'rinmasdi — 24 soatgacha yo'qotish.
    #
    # SHOVQIN BO'LMAYDI: ikkinchi tekshiruv faqat YANGI lot chiqqanda
    # xabar beradi (`faqat_yangi`), aks holda jim turadi.
    tender_kuzatuv_vaqti: str = ""
    # Xabar keladigan Telegram ID'lar. Bo'sh bo'lsa — umumiy ro'yxatdagi hamma.
    tender_kuzatuv_id: str = ""

    # Qaysi tender manbalari yoqilgan (vergul bilan).
    #
    # Standart — TAKLIF BERISH mumkin bo'lgan maydonchalar:
    #   etender — kompaniya ERI kaliti bilan ro'yxatdan o'tgan, lot
    #     sahifasida "o'z taklifingizni bering" bor;
    #   mcuz    — tender.mc.uz ("Shaffof qurilish"), taklif berish va
    #     `bidders_count` ochiq. Qurilish maydonchasi, shuning uchun
    #     ventilyatsiya lotlari kam chiqadi — bu kutilgan hol.
    #
    # `dxmap` axborot portali: havolasi taklif berish sahifasiga olib
    # bormaydi va lotlari boshqa maydonchalarda — u yerlarda alohida
    # ro'yxatdan o'tish kerak. Boshqa maydonchada ham ro'yxatdan
    # o'tilsa shu yerga qo'shiladi:
    #     TENDER_MANBALARI=etender,mcuz,dxmap
    tender_manbalari: str = "etender,mcuz"

    # `/tender` keshi shuncha daqiqadan keyin eskirgan hisoblanadi va
    # fonda yangilanadi. Rejali tekshiruvlar orasidagi vaqtdan
    # kichikroq: aks holda kesh hech qachon yangilanmasdi.
    tender_kesh_daqiqa: int = 180

    # Tender muddati eslatmasi: shuncha kun qolganda ogohlantiriladi,
    # va shu vaqtda yuboriladi. LLM chaqirilmaydi — ro'yxat keshdan
    # olinadi, shuning uchun kvota sarflanmaydi.
    tender_muddat_kuni: int = 2
    tender_muddat_vaqti: str = "08:30"

    # --- KP eslatmasi (avtomatik) ---
    #
    # NEGA KERAK. O'LCHANDI (2026-09-08): 25 ta tijorat taklifi
    # "yuborildi" holatida 40 kundan beri turibdi, 26 tadan faqat 1 tasi
    # shartnomaga aylangan. Tizim KP tayyorlaydi va keyin unutadi —
    # haqiqiy savdo xodimi esa bir necha kundan keyin surishtirardi.
    #
    # Bu ish LLM SIZ bajariladi: ro'yxat bazadan sof so'rov bilan
    # olinadi. Shu tufayli kvota sarflanmaydi va ro'yxatda xato
    # bo'lmaydi — yo'q KP eslatilmaydi, bor KP tushib qolmaydi.
    kp_eslatma_vaqti: str = "09:30"
    # Dollar kursi tekshiruvi. Markaziy bank kursini ertalab e'lon
    # qiladi, shuning uchun undan keyin. Bo'sh bo'lsa — o'chirilgan.
    kurs_tekshiruv_vaqti: str = "09:15"
    # Shuncha kundan beri javobsiz turgani eslatiladi.
    kp_eslatma_kuni: int = 5
    # Bitta xabarga sig'adigan maksimal KP soni.
    kp_eslatma_cheki: int = 20

    # --- Katalog salomatligi (avtomatik) ---
    #
    # O'LCHANDI (2026-09-08): 342 variantdan 21 tasida narx bor (6%),
    # 271 tasida havo sarfi/bosimi yo'q. Bu tizimning eng katta to'sig'i
    # va uni KO'RISH uchun kimdir katalogni ochib sanashi kerak edi.
    #
    # HAFTADA bir marta: katalog kundan-kunga o'zgarmaydi, kunlik xabar
    # esa o'qilmay qoladigan shovqinga aylanardi.
    katalog_hisobot_kuni: int = 0        # 0 = dushanba
    katalog_hisobot_vaqti: str = "09:45"

    # --- Haftalik hisobot ---
    # Qaysi kun (0 = dushanba) va qaysi soatda yuboriladi.
    # Dushanba ertalab: xulosa shu haftaga ta'sir qilsin.
    hisobot_kuni_raqami: int = 0
    hisobot_soati: str = "09:00"

    @property
    def hisobot_kuni(self) -> int:
        return max(0, min(self.hisobot_kuni_raqami, 6))

    @property
    def hisobot_vaqti(self) -> tuple[int, int]:
        try:
            soat, _, daqiqa = (self.hisobot_soati or "09:00").partition(":")
            vaqt = (int(soat), int(daqiqa or 0))
        except ValueError:
            return (9, 0)
        return vaqt if 0 <= vaqt[0] <= 23 and 0 <= vaqt[1] <= 59 else (9, 0)

    # --- Mijozlar boti (ochiq, whitelist YO'Q) ---------------------------
    # ALOHIDA token: ichki bot bilan aralashtirilmaydi. Bo'sh bo'lsa
    # mijozlar boti umuman ishga tushmaydi.
    mijoz_bot_token: str = ""
    # Yangi murojaat haqida xabar keladigan menejerlar.
    mijoz_bot_menejer_id: str = ""
    # Bitta odam daqiqasiga nechta so'rov yubora oladi (flood himoyasi).
    # Daqiqasiga nechta LLM so'rovi — FLOOD himoyasi.
    #
    # JONLI XATO (2026-08-28): 5 edi va oddiy mijoz unga urilardi.
    # Uskuna qidirayotgan odam bir daqiqada 6-7 savol berishi normal:
    # «kanal ventilyatori bormi», «250 mm», «narxi qancha»... U esa
    # «Biroz sekinroq yozing» degan javob olardi va ketardi.
    #
    # Bu chegara XARAJATNI himoya qilmaydi — buning uchun KUNLIK
    # chegara bor (`mijoz_kunlik_limit`). Bu faqat skript bilan
    # bombardimon qilishga qarshi.
    mijoz_bot_limit: int = 15

    # Bitta mijoz kuniga nechta LLM so'rovi qila oladi.
    #
    # NEGA KERAK: Gemini bepul tarifida kuniga JAMI 20 ta so'rov
    # (2026-08-28 da o'lchandi). Kunlik chegarasiz bitta qiziquvchan
    # odam butun kvotani yeb qo'yishi va qolgan mijozlar javobsiz
    # qolishi mumkin edi.
    #
    # So'rovnoma bu chegaraga KIRMAYDI — u LLM ishlatmaydi.
    mijoz_kunlik_limit: int = 8
    # Mijozlar boti uchun ALOHIDA model. Bo'sh bo'lsa — umumiy LLM_MODEL.
    # Bu yerdagi ish (ventilyatsiya hisobi uchun parametr ajratish, katalog
    # savoli) og'ir emas — arzonroq model bilan sifat deyarli tushmaydi,
    # xarajat esa bir necha barobar kamayadi.
    mijoz_bot_model: str = ""

    @property
    def mijoz_menejer_idlar(self) -> set[int]:
        """Lid xabari keladiganlar. Bo'sh bo'lsa — ichki bot ro'yxati."""
        return self._idlar(self.mijoz_bot_menejer_id) or self.ruxsat_etilgan_idlar

    @property
    def tender_idlar(self) -> set[int]:
        return self._idlar(self.tender_kuzatuv_id) or self.ruxsat_etilgan_idlar

    @property
    def tender_manba_nomlari(self) -> list[str]:
        """Yoqilgan manba nomlari. Takrorlar tashlanadi, tartib saqlanadi."""
        korilgan: set[str] = set()
        natija: list[str] = []
        for nom in re.split(r"[,;\s]+", self.tender_manbalari or ""):
            kalit = nom.strip().lower()
            if kalit and kalit not in korilgan:
                korilgan.add(kalit)
                natija.append(kalit)
        return natija

    @property
    def tender_muddat_soati(self) -> tuple[int, int] | None:
        return self._soat_daqiqa(self.tender_muddat_vaqti)

    @property
    def katalog_hisobot_soati(self) -> tuple[int, int] | None:
        """Katalog hisoboti vaqti. Bo'sh bo'lsa — o'chirilgan."""
        return self._soat_daqiqa(self.katalog_hisobot_vaqti)

    @property
    def katalog_kuni(self) -> int:
        return max(0, min(self.katalog_hisobot_kuni, 6))

    @property
    def kp_eslatma_soati(self) -> tuple[int, int] | None:
        """KP eslatmasi vaqti. Bo'sh bo'lsa — eslatma o'chirilgan."""
        return self._soat_daqiqa(self.kp_eslatma_vaqti)

    @property
    def kurs_tekshiruv_soati(self) -> tuple[int, int] | None:
        """Kurs tekshiruvi vaqti. Bo'sh bo'lsa — tekshiruv o'chirilgan."""
        return self._soat_daqiqa(self.kurs_tekshiruv_vaqti)

    @property
    def tender_vaqti(self) -> tuple[int, int] | None:
        """BIRINCHI kuzatuv vaqti (eski kod shuni kutadi)."""
        vaqtlar = self.tender_vaqtlari
        return vaqtlar[0] if vaqtlar else None

    @property
    def tender_vaqtlari(self) -> list[tuple[int, int]]:
        """Hamma kuzatuv vaqti, tartiblangan va takrorsiz.

        Noto'g'ri yozilgan vaqt JIMGINA TASHLANADI, lekin qolganlari
        ishlaydi — bitta xato butun kuzatuvni to'xtatmasin.
        """
        korilgan: set[tuple[int, int]] = set()
        natija: list[tuple[int, int]] = []
        for bolak in re.split(r"[,;\s]+", self.tender_kuzatuv_vaqti or ""):
            vaqt = self._soat_daqiqa(bolak)
            if vaqt and vaqt not in korilgan:
                korilgan.add(vaqt)
                natija.append(vaqt)
        return sorted(natija)

    @staticmethod
    def _soat_daqiqa(xom: str) -> tuple[int, int] | None:
        """"SS:DD" ni (soat, daqiqa) ga o'giradi.

        Bo'sh yoki noto'g'ri qiymat — `None`, ya'ni "o'chirilgan".
        Noto'g'ri vaqtda jimgina 00:00 ga tushib qolish battari bo'lardi:
        eslatma yarim tunda kelardi va sababi ko'rinmasdi.
        """
        xom = (xom or "").strip()
        if not xom:
            return None
        try:
            soat, _, daqiqa = xom.partition(":")
            vaqt = (int(soat), int(daqiqa or 0))
        except ValueError:
            return None
        if 0 <= vaqt[0] <= 23 and 0 <= vaqt[1] <= 59:
            return vaqt
        return None

    @staticmethod
    def _idlar(qator: str) -> set[int]:
        """Telegram ID ro'yxatini o'qiydi.

        Asosiy ajratgich — VERGUL:  `111, 222, 333`

        Lekin nuqta-vergul, bo'sh joy va yangi qator ham qabul qilinadi.
        Sababi: ro'yxat qo'lda to'ldiriladi va noto'g'ri ajratgich
        ishlatilsa natija BO'SH to'plam bo'lardi — bot esa bo'sh ro'yxatda
        HECH KIMGA javob bermaydi. Ya'ni bitta nuqta-vergul butun tizimni
        jimgina o'chirib qo'yardi.
        """
        bolaklar = [b for b in re.split(r"[,;\s]+", (qator or "").strip()) if b]
        idlar = {int(b) for b in bolaklar if b.isdigit()}
        # Raqam bo'lmagan yozuvlar. Odatda "@foydalanuvchi" yoki ism —
        # ular jimgina tashlansa, menejer "qo'shdim, lekin ishlamayapti"
        # holatiga tushadi va sababini topa olmaydi.
        tashlangan = [b for b in bolaklar if not b.isdigit()]
        if tashlangan:
            log.warning(
                "ID ro'yxatida tushunarsiz yozuv: %s — faqat Telegram ID "
                "raqami yoziladi, vergul bilan: 111111, 222222",
                ", ".join(repr(b) for b in tashlangan[:5]),
            )
        return idlar

    @property
    def ruxsat_etilgan_idlar(self) -> set[int]:
        return self._idlar(self.bot_ruxsat_etilgan_id)

    @property
    def hr_idlar(self) -> set[int]:
        return self._idlar(self.bot_hr_ruxsat_id)

    @property
    def katalog_idlar(self) -> set[int]:
        return self._idlar(self.bot_katalog_ruxsat_id)

    @property
    def baza_fayli(self) -> Path:
        yol = Path(self.baza_yoli)
        return yol if yol.is_absolute() else ILDIZ / yol

    @property
    def kontraktlar_papkasi(self) -> Path:
        yol = Path(self.kontraktlar_yoli)
        return yol if yol.is_absolute() else ILDIZ / yol

    @property
    def profil_fayli(self) -> Path:
        yol = Path(self.profil_yoli)
        return yol if yol.is_absolute() else ILDIZ / yol


@lru_cache
def sozlama() -> Sozlama:
    return Sozlama()
