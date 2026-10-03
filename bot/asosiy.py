"""Telegram bot — tizimga kirish nuqtasi.

BITTA bot, 7 ta emas: butun tizim router atrofida qurilgan, foydalanuvchi
qaysi agent kerakligini bilishi shart emas. Alohida botlar zanjirli so'rovni
("raqibni ko'r va kampaniya tuz") imkonsiz qilardi.

Botda MANTIQ YO'Q: u faqat xabarni qabul qiladi, mavjud `Orkestr`ni chaqiradi
va natijani ko'rsatadi. Barcha qaror router va agentlarda.

Ishga tushirish:
    .venv\\Scripts\\python -m bot.asosiy
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from datetime import time as dt_time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram import Bot as TelegramBot
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.baza import Baza
from app.config import sozlama
from app.kontraktlar import reyestr
from app.llm import AnthropicLlm
from app.orkestr import Natija, Orkestr, TasdiqXatosi
from app.router import Reja
from hisobot import Davr, hisobot_matni, hisobot_yig

from .formatlash import javob_matni, reja_matni, tasdiq_matni
from presenter.matn import xabarni_bol
from app.agentlar.kp_kuzatuvchi import _kun_farqi
from app import katalog_salomatligi
from app import kurs as kurs_moduli
from integrations.climavent_client import ClimaventKlient
from integrations.valyuta import KursXatosi, markaziy_bank_kursi
from integrations.valyuta import matn as kurs_matni
from integrations.valyuta import solishtir as kurs_solishtir
from presenter.agentlar import AJRATGICH
from bilim.qidiruv import transliteratsiya
from app.agentlar.tijorat_menejeri import til_aniqla

from . import kp_oqim, menyu, otkazilgan, suhbat, tekshir_oqim, tender_keshi, xatolar
from .ruxsat import Ruxsat

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s", level=logging.INFO
)
# `httpx` har so'rovni to'liq URL bilan yozadi, URL ichida esa BOT TOKENI
# turadi. Log fayli yoki ekran surati bilan token sizib chiqmasligi uchun
# uni o'chiramiz — xatolar baribir ko'rinadi.
logging.getLogger("httpx").setLevel(logging.WARNING)
from app import ovoz as ovoz_moduli
from app.sarf import yozuvchini_ol
from app.sarf_ogoh import Ogohlantiruvchi

log = logging.getLogger("bot")

SALOM = """Salom! Men kompaniya agentlar tizimining kirish nuqtasiman.

Tabiiy tilda yozing — router so'rovni tahlil qilib, mos agent(lar)ni tanlaydi.
Qaysi agent kerakligini bilishingiz shart emas.

Masalan:
• iPhone 15 narxini Toshkent bozorida topib bering
• Raqiblarning aksiyalarini ko'rib chiqing va kampaniya taklif qiling
• Qaysi shahardagi mijozlar eng ko'p buyurtma bergan?

/tekshir — tayyor KP ni TZ bilan solishtirish (farqlar ro'yxati)
/agentlar — kim nima qiladi
/tasdiq — tasdiq kutayotgan ishlar
/menejer (yoki /manager) — KP da kimning nomi chiqishi
/tender — xarid e'lonlarini hoziroq tekshirish
/murojaatlar — mijozlar botiga kelgan savollar va berilgan javoblar
/hisobot — tizim qancha ish qilgani
   /hisobot           — o'tgan hafta
   /hisobot 2 hafta   — oxirgi 14 kun
   /hisobot oy        — oxirgi 30 kun"""


# Telegramning "yozmoqda…" belgisi ~5 soniyada o'chadi. Karim veb qidiruv
# bilan 3 daqiqagacha ishlashi mumkin — belgi yangilanmasa, foydalanuvchi
# bot qotib qolgan deb o'ylaydi.
YOZMOQDA_ORALIQ = 4.0

# Shu vaqtdan uzoq ishlaydigan agentlar — rejada oldindan aytamiz.
SEKIN_AGENTLAR = {
    "competitor-watch": "2-3 daqiqa",
    "price-monitor": "1-2 daqiqa",
    "sales-strategy": "1 daqiqacha",
    "marketing": "1 daqiqacha",
    "hr-assist": "1 daqiqacha",
}


# Telefon raqami: +998 90 099 12 60, +998900991260, 90 099 12 60 — hammasi.
TELEFON = re.compile(r"[+\d][\d\s\-()]{6,}\d")


def _menejer_ajrat(matn: str) -> tuple[str, str]:
    """"Яхшибоев Бауржон +998 90 099 12 60" -> (ism, telefon)."""
    topilgan = TELEFON.search(matn or "")
    if not topilgan:
        return "", ""
    telefon = " ".join(topilgan.group().split())
    ism = (matn[: topilgan.start()] + " " + matn[topilgan.end() :]).strip(" ,;:-\n\t")
    return " ".join(ism.split()), telefon


# Bir chaqiruvda ko'rsatiladigan murojaat soni.
MUROJAAT_CHEK = 15


def _murojaat_matni(y: dict) -> str:
    """Bitta murojaatni o'qiladigan matnga aylantiradi."""
    vaqt = str(y.get("vaqt") or "")[:16].replace("T", " ")
    qatorlar = [
        f"💬 #{y['id']} · {vaqt}",
        f"👤 {y.get('ism') or '—'}"
        + (f" · {y['aloqa']}" if y.get("aloqa") else ""),
        "",
        f"❓ {y['savol']}",
    ]
    if y.get("javob"):
        qatorlar += ["", f"🤖 {y['javob']}"]
    else:
        qatorlar += ["", "🤖 Bot javob bermadi."]
    if y.get("sabab"):
        qatorlar += ["", f"⚠️ {y['sabab']}"]
    return "\n".join(qatorlar)


def _kutish_izohi(reja: Reja) -> str:
    """Sekin agent tanlansa, qancha kutishni oldindan aytamiz.

    Karim veb qidiruvni 18 martagacha bajaradi — bu 2-3 daqiqa. Bu vaqtni
    qisqartirib bo'lmaydi (qidiruv tashqi xizmat), lekin kutish noma'lum
    bo'lmasligi kerak: xodim javob kelmayapti deb o'ylab, so'rovni qayta
    yuboradi va ikki barobar ko'p pul ketadi.
    """
    muddatlar = [
        SEKIN_AGENTLAR[q.agent] for q in (reja.qadamlar or [])
        if q.agent in SEKIN_AGENTLAR
    ]
    if not muddatlar:
        return ""
    return f"\n\n⏳ Taxminan {muddatlar[0]} vaqt oladi — kutib turing."


# Qadam tugaganda holat qatorida ko'rsatiladigan qisqa natija. Kalitlar
# agentlar bo'yicha turlicha, shuning uchun birinchi topilgani olinadi.
# Hech biri bo'lmasa bo'sh qaytadi — qator baribir "✅ Ism" bo'lib qoladi.
NATIJA_KALITLARI = (
    ("havo_sarfi", "{} m³/soat"),
    ("kp_raqami", "{}"),
    ("raqam", "{}"),
    ("variantlar", "{} ta variant"),
)


def _qisqa_natija(konvert: Any) -> str:
    """Konvertdan bir og'iz natija ajratadi (topilmasa — bo'sh satr)."""
    natija = getattr(konvert, "natija", None)
    if not isinstance(natija, dict):
        return ""
    for kalit, andoza in NATIJA_KALITLARI:
        qiymat = natija.get(kalit)
        if isinstance(qiymat, list):
            qiymat = len(qiymat) or None
        if qiymat:
            return andoza.format(qiymat)
    return ""


# Matn bilan bekor qilish. Tugma bosish qulay, lekin foydalanuvchi
# ko'pincha shunchaki "bekor qil" deb yozadi — va ilgari bu oddiy
# so'rov sifatida modelga ketardi (pul sarflanardi, natija esa yo'q).
BEKOR_SOZLARI = frozenset({
    "bekor", "bekor qil", "bekor qilamiz", "bekor qildim", "rad et",
    "rad etaman", "kerakmas", "kerak emas", "to'xtat", "toxtat",
    "otmena", "отмена", "отменить", "не надо", "cancel",
})

KUN_NOMLARI = (
    "dushanba", "seshanba", "chorshanba", "payshanba",
    "juma", "shanba", "yakshanba",
)

# `/hisobot` argumenti — odam qanday yozsa, shunday tushunilsin.
#
# "14 nima?" degan savol tug'ilmasligi kerak: shuning uchun "2 hafta",
# "3 oy", "oy" — hammasi ishlaydi, faqat quruq raqam emas.
BIRLIKLAR = {
    "kun": 1, "kunlik": 1,
    "hafta": 7, "haftalik": 7, "haftada": 7,
    "oy": 30, "oylik": 30, "oyda": 30,
    "kvartal": 90, "chorak": 90,
    "yil": 365, "yillik": 365,
}
# Juda uzoq davr bazani bo'sh yuklaydi va hisobot ma'nosini yo'qotadi.
MAKS_KUN = 365

# "2 hafta", "3 oy", "10 kun" — son + birlik.
SON_BIRLIK = re.compile(r"(\d+)\s*([a-zA-Zʼ'`Ѐ-ӿ]+)")


def _davr_nomi(soni: int, birlik: str) -> str:
    return f"oxirgi {soni} {birlik}" if soni > 1 else f"oxirgi {birlik}"


def _davrni_oqi(arglar: list[str]) -> Davr:
    """`/hisobot`, `/hisobot 14`, `/hisobot 2 hafta`, `/hisobot oy`."""
    xom = " ".join(arglar).strip().lower()
    if not xom:
        return Davr.kunlar(7, "o'tgan hafta")

    # "2 hafta", "3 oy"
    mos = SON_BIRLIK.search(xom)
    if mos:
        soni = int(mos.group(1))
        birlik = mos.group(2)
        koeffitsient = BIRLIKLAR.get(birlik)
        if koeffitsient:
            kun = max(1, min(soni * koeffitsient, MAKS_KUN))
            return Davr.kunlar(kun, _davr_nomi(soni, birlik))
        # "14 kunlik" emas, shunchaki "14 dona" kabi — sonni kun deb olamiz
        return Davr.kunlar(max(1, min(soni, MAKS_KUN)))

    # Faqat birlik: "hafta", "oy"
    for birlik, koeffitsient in BIRLIKLAR.items():
        if xom == birlik:
            return Davr.kunlar(koeffitsient, f"oxirgi {birlik}")

    # Faqat raqam: "14"
    if xom.isdigit():
        return Davr.kunlar(max(1, min(int(xom), MAKS_KUN)))

    return Davr.kunlar(7, "o'tgan hafta")


def _korinishlar() -> dict[str, str]:
    return {rol: k.korinish for rol, k in reyestr().items()}


class Bot:
    def __init__(self) -> None:
        s = sozlama()
        self.s = s
        self.ruxsat = Ruxsat(s)
        self.baza = Baza()
        self.llm = AnthropicLlm()
        self.kontraktlar = reyestr()
        self.korinishlar = _korinishlar()
        # MIJOZLAR botiga ulanish. KP loyihasini mijozga yuborish uchun
        # kerak: mijoz ICHKI bot bilan hech qachon gaplashmagan va
        # Telegram notanish chatga xabar yuborishga ruxsat bermaydi.
        # Mijoz esa mijozlar botiga o'zi yozgan — o'sha chat ochiq.
        self._mijoz_bot = (
            TelegramBot(s.mijoz_bot_token) if s.mijoz_bot_token else None
        )
        # `post_init` da to'ldiriladi — ogohlantirish yuborish uchun kerak.
        self.ilova = None
        self.ogohlantiruvchi = Ogohlantiruvchi(self.baza, self._llm_limiti)

    @staticmethod
    def _llm_limiti(provayder: str) -> int:
        s = sozlama()
        return s.gemini_kunlik_limit if provayder == "gemini" else 0

    async def sarfni_yoz(self, yozuv: dict[str, Any]) -> None:
        """Sarf yozuvi + limitga yaqinlashgan bo'lsa ogohlantirish.

        Bu funksiya HAR LLM chaqiruvidan keyin ishlaydi, shuning uchun
        ichidagi hech nima asosiy ishni to'xtatmasligi kerak: yozuv ham,
        xabar yuborish ham alohida `try` ichida.
        """
        await self.baza.sarf_yoz(yozuv)
        try:
            matn = await self.ogohlantiruvchi.yozuvdan_keyin(yozuv)
        except Exception:
            log.exception("sarf ogohlantirishi hisoblanmadi")
            return
        if matn:
            await self._ogohlantirishni_yubor(matn)

    async def _ogohlantirishni_yubor(self, matn: str) -> None:
        """Ogohlantirishni menejerlarga yuboradi.

        Oluvchilar — `BOT_RUXSAT_ETILGAN_ID`: limit hammaning ishini
        to'xtatadi, shuning uchun bu bitta odamning xabari emas.
        """
        if self.ilova is None:
            log.warning("ogohlantirish yuborilmadi: ilova hali tayyor emas")
            return
        for tg_id in self.s.ruxsat_etilgan_idlar:
            try:
                await self.ilova.bot.send_message(
                    tg_id, matn[: self.s.bot_maks_belgi],
                    disable_web_page_preview=True,
                )
            except Exception:
                log.exception("ogohlantirish yuborilmadi: id=%s", tg_id)

    def orkestr(self) -> Orkestr:
        return Orkestr(llm=self.llm, baza=self.baza, kontraktlar=self.kontraktlar)

    # --- yordamchilar --------------------------------------------------------

    async def _ruxsatmi(self, update: Update) -> int | None:
        """Ruxsat bo'lsa foydalanuvchi ID'sini, bo'lmasa None qaytaradi."""
        foydalanuvchi = update.effective_user
        tg_id = foydalanuvchi.id if foydalanuvchi else None
        qaror = self.ruxsat.foydalanuvchi(tg_id)
        if not qaror.ruxsat:
            log.warning("ruxsatsiz urinish: id=%s", tg_id)
            if update.effective_message:
                await update.effective_message.reply_text(f"⛔ {qaror.sabab}")
            return None
        return tg_id

    @staticmethod
    async def _yozmoqda(chat) -> None:
        """Javob tayyorlanguncha "yozmoqda…" belgisini yangilab turadi."""
        try:
            while True:
                await chat.send_action(ChatAction.TYPING)
                await asyncio.sleep(YOZMOQDA_ORALIQ)
        except asyncio.CancelledError:
            pass
        except Exception:      # tarmoq uzilsa javob berish to'xtamasin
            log.debug("yozmoqda belgisi yuborilmadi", exc_info=True)

    async def _uzun_javob(self, update: Update, matn: str, nomi: str) -> None:
        """Uzun natijani fayl sifatida yuboradi."""
        xabar = update.effective_message
        if xabar is None:
            return
        if len(matn) <= self.s.bot_maks_belgi:
            await xabar.reply_text(matn, disable_web_page_preview=True)
            return

        qisqa = matn[: self.s.bot_maks_belgi].rsplit("\n", 1)[0]
        await xabar.reply_text(
            f"{qisqa}\n\n… natija uzun, to'liq matni faylda.", disable_web_page_preview=True
        )
        fayl = io.BytesIO(matn.encode("utf-8"))
        fayl.name = nomi
        await xabar.reply_document(fayl)

    async def _tayyor_fayllar(self, xabar, natija: Natija) -> None:
        """Agent yaratgan hujjatlarni (KP docx/pdf) biriktiradi.

        Fayl diskda yaratilgan bo'lsa, uni foydalanuvchiga YETKAZISH shart —
        aks holda "hujjat tayyor" deyilib, hech narsa kelmaydi.
        """
        fayllar = (natija.yakuniy.natija or {}).get("fayllar") or {}
        if not isinstance(fayllar, dict) or xabar is None:
            return

        for tur in ("pdf", "docx"):  # avval yuborish uchun, keyin tahrirlash uchun
            yol_matni = fayllar.get(tur)
            if not yol_matni:
                continue
            yol = Path(yol_matni)
            if not yol.is_file():
                log.warning("hujjat topilmadi: %s", yol)
                continue
            try:
                with yol.open("rb") as fayl:
                    await xabar.reply_document(fayl, filename=yol.name)
            except Exception:
                log.exception("hujjatni yuborib bo'lmadi: %s", yol)

    async def _kutilgan_javob(self, tg_id: int, matn: str) -> tuple[str, str] | None:
        """Berilgan savolga kelgan javobni qayta ishlaydi.

        Javob kontekstsiz qolmasligi kerak: "Aziz Karimov +998901234567" yoki
        "o'zbekcha" o'zi alohida so'rov emas — u oldingi KP so'rovining
        davomi. `(asl_sorov, tasdiq_matni)` qaytaradi.
        """
        kutilayotgan = await self.baza.savol(tg_id)
        if not kutilayotgan:
            return None

        tur = kutilayotgan["tur"]
        asl = kutilayotgan["sorov"]

        if tur == "menejer":
            ism, telefon = _menejer_ajrat(matn)
            if not ism or not telefon:
                return None  # javob tushunarsiz — savol kuchda qoladi
            await self.baza.menejer_yoz(tg_id, ism, telefon)
            await self.baza.savol_ochir(tg_id)
            log.info("menejer saqlandi: id=%s", tg_id)
            return asl, (
                f"✅ Saqlandi: {ism}, {telefon}\n"
                "Endi qayta so'ramayman. O'zgartirish uchun: /menejer"
            )

        if tur == "til":
            til = til_aniqla(matn)
            if til is None:
                return None  # "ruscha"/"o'zbekcha" deyilmagan — savol turaveradi
            await self.baza.savol_ochir(tg_id)
            # Tilni ASL so'rovga qo'shamiz — Temur uni o'sha yerdan o'qiydi.
            qoshimcha = "ruscha" if til == "ru" else "o'zbekcha"
            atama = "rus tilida" if til == "ru" else "o'zbek tilida"
            return f"{asl} ({qoshimcha})", f"✅ KP {atama} tuziladi."

        return None

    def _tasdiq_tugmalari(self, iz_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"ha:{iz_id}"),
                    InlineKeyboardButton("❌ Rad etish", callback_data=f"yoq:{iz_id}"),
                ]
            ]
        )

    # --- buyruqlar -----------------------------------------------------------

    async def boshla(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        tg_id = await self._ruxsatmi(update)
        if tg_id is None:
            return
        # `/start` — yangi mavzu, eski savol-javob zanjiri uzilsin.
        await suhbat.tozala(self.baza, suhbat.ICHKI, tg_id)
        await update.effective_message.reply_text(SALOM)

    async def agentlar(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._ruxsatmi(update) is None:
            return
        qatorlar = ["👥 Agentlar:\n"]
        for k in self.kontraktlar.values():
            holat = "✅" if k.amalga_oshirilgan else "🔧"
            qatorlar.append(f"{holat} {k.korinish} — xavf: {k.xavf.value}\n   {k.maqsad.strip()}")
        await update.effective_message.reply_text("\n".join(qatorlar))

    # --- avtomatik tender kuzatuvi -------------------------------------------

    async def tender_tekshiruvi(
        self,
        ctx: ContextTypes.DEFAULT_TYPE,
        hammasini_korsat: bool = False,
        faqat_yangilik: bool = False,
    ) -> None:
        """Kunlik tekshiruv — natijadan qat'i nazar HAR DOIM xabar beradi.

        Ilgari mos e'lon bo'lmasa bot jim turardi. Lekin jimlik ikki xil
        ma'no berardi: "tekshirdim, mos e'lon yo'q" va "umuman
        tekshirmadim" (manba yiqilgan, jadval o'chgan, xato bo'lgan) —
        ularni tashqaridan ajratib bo'lmasdi.

        Endi har tekshiruvdan keyin xabar keladi. "Hech narsa yo'q" degan
        quruq xabar bo'lmasligi uchun ichida NIMA ko'rilgani yoziladi:
        nechta e'lon, qaysi manbadan, nega mos kelmadi.
        """
        oluvchilar = self.s.tender_idlar
        if not oluvchilar:
            return

        try:
            # HAR DOIM HOZIR OCHIQ bo'lganini so'raymiz, "yangisi"ni emas.
            #
            # Ilgari kunlik tekshiruv faqat YANGI lotni ko'rsatardi va
            # natija "hammasi ilgari ko'rilgan" bo'lib chiqardi. Menejer
            # chatni tozalasa yoki xabarni o'tkazib yuborsa, ro'yxatni
            # boshqa hech qachon ko'rmasdi — lot esa hali ochiq turardi.
            #
            # Endi ikkalasi ham bir xil savolga javob beradi: "hozir
            # qanday ochiq tender bor". Takrorlanishning oldini
            # `faqat_yangilik` oladi — matn o'zgarmagan bo'lsa,
            # kundagi ikkinchi tekshiruv jim turadi.
            konvert = await self.orkestr().agentni_chaqir(
                "tender-watch",
                "Yangi xarid e'lonlarini tekshir",
                {"hammasini_korsat": True},
            )
        except Exception as xato:
            log.exception("tender kuzatuvi bajarilmadi")
            # Nosozlikni ham AYTAMIZ: aks holda menejer tekshiruv
            # ishlayapti deb o'ylab yuraveradi.
            await self._tenderga_yubor(
                ctx, oluvchilar,
                "📋 Tender kuzatuvi\n\n"
                "⚠️ Tekshiruv bajarilmadi.\n"
                f"Sabab: {xato}\n\n"
                "Qayta urinish: /tender",
            )
            return

        matn = self._tender_xabari(konvert)
        saqlangan = tender_keshi.oqi()
        eski_matn = saqlangan[0] if saqlangan else ""

        mos = (konvert.natija or {}).get("mos_elonlar") or []
        # KESHGA FAQAT LOTLI NATIJA YOZILADI.
        #
        # Jonli holat: kesh "Bizga mos e'lon topilmadi" xabarini
        # saqlab qoldi va `/tender` uni DARHOL qaytaraverdi —
        # menejer lot bor-yo'qligini bila olmadi. Bo'sh natija
        # eskisini o'chirmaydi: keyingi tekshiruv lot topsa,
        # kesh yangilanadi.
        if mos:
            tender_keshi.yoz(matn)
        # KUNDAGI IKKINCHI TEKSHIRUV jim turadi, agar ro'yxat
        # O'ZGARMAGAN bo'lsa. Aks holda menejer bir kunda ikkita bir xil
        # ro'yxat olardi va o'qishni to'xtatardi.
        if faqat_yangilik and matn.strip() == eski_matn.strip():
            log.info("tender kuzatuvi: ro'yxat o'zgarmadi, xabar yuborilmadi")
            return
        await self._tenderga_yubor(ctx, oluvchilar, matn)

        log.info(
            "tender kuzatuvi: %d ta mos, %d ta oluvchi", len(mos), len(oluvchilar)
        )
        await otkazilgan.belgila(self.baza, "tender-kuzatuvi")

    async def kp_eslatmasi(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Javobsiz qolgan tijorat takliflari haqida kunlik eslatma.

        LLM CHAQIRILMAYDI. Ro'yxat bazadan sof so'rov bilan olinadi
        (`baza.javobsiz_kplar`). Ikki sabab:
          - kvota sarflanmaydi (Gemini bepul tarifda kuniga 20 so'rov);
          - ro'yxatda XATO BO'LMAYDI — yo'q KP eslatilmaydi, bor KP
            tushib qolmaydi. Model bu yerda hech narsa qo'shmaydi.

        Mijozga hech narsa yuborilmaydi: eslatma MENEJERGA boradi,
        qo'ng'iroqni odam qiladi (kontrakt talabi).
        """
        oluvchilar = self.s.tender_idlar
        if not oluvchilar:
            return

        try:
            kutayotganlar = await self.baza.javobsiz_kplar(
                kun=self.s.kp_eslatma_kuni, chek=self.s.kp_eslatma_cheki
            )
        except Exception as xato:
            log.exception("KP eslatmasi bajarilmadi")
            await self._tenderga_yubor(
                ctx, oluvchilar,
                "📄 KP eslatmasi\n\n⚠️ Ro'yxat olinmadi.\n"
                f"Sabab: {xato}\n\nQayta urinish: /kpkuzatuv",
            )
            return

        await self._tenderga_yubor(
            ctx, oluvchilar, self._kp_eslatma_xabari(kutayotganlar)
        )
        log.info(
            "KP eslatmasi: %d ta javobsiz, %d ta oluvchi",
            len(kutayotganlar), len(oluvchilar),
        )
        await otkazilgan.belgila(self.baza, "kp-eslatmasi")

    async def tender_muddati(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Muddati yaqin tenderlar haqida kunlik eslatma.

        LLM CHAQIRILMAYDI — ro'yxat oxirgi tekshiruv KESHIDAN olinadi
        va muddat sanasi bo'yicha saralanadi. Kvota sarflanmaydi.

        NEGA KERAK: lot topiladi, keyin unutiladi. Aziza KP lar uchun
        aynan shu ishni qiladi va u yerda 25 ta unutilgan taklif
        topilgandi.
        """
        oluvchilar = self.s.tender_idlar
        if not oluvchilar:
            return
        saqlangan = tender_keshi.oqi()
        if saqlangan is None:
            return
        matn = tender_keshi.shoshilinchlar(
            saqlangan[0], self.s.tender_muddat_kuni
        )
        if not matn:
            return
        await self._tenderga_yubor(ctx, oluvchilar, matn)
        log.info("tender muddat eslatmasi yuborildi")
        await otkazilgan.belgila(self.baza, "tender-muddati")

    async def kurs_tekshiruvi(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Dollar kursi Markaziy bankdan qanchalik uzoqlashganini tekshiradi.

        LLM CHAQIRILMAYDI — ikki raqam solishtiriladi, xolos.

        NEGA KERAK: narx bazada DOLLARDA saqlanadi va so'mga kursga
        ko'paytirib hisoblanadi. Ya'ni bu bitta raqam KP ni ham, tender
        bahosini ham, saytdagi narxni ham bir vaqtda siljitadi. Va xato
        ko'rinmaydi — hamma joyda raqam "chiroyli" chiqaveradi.
        2026-09-09 da farq 1.58% edi va uni hech kim sezmagan.

        QAROR QILINMAYDI: kurs O'ZGARTIRILMAYDI, faqat xabar beriladi.
        Qaysi kurs to'g'ri ekani biznes qarori — ko'p kompaniya narxni
        Markaziy bank kursidan yuqoriroq oladi.
        """
        oluvchilar = self.s.tender_idlar
        if not oluvchilar:
            return

        klient = ClimaventKlient()
        try:
            mb = await markaziy_bank_kursi()
        except KursXatosi as xato:
            log.warning("kurs tekshiruvi: %s", xato)
            return

        # Saytdagi qiymatni o'qiymiz va joriy kursni ham yangilab qo'yamiz —
        # bot kun bo'yi eski raqamdan hisoblab yurmasin.
        saytdagi = await klient.kurs()
        kurs_moduli.qoy(saytdagi)

        natija = kurs_solishtir(mb, saytdagi, self.s.usd_ustama_foiz)
        if not natija.sezilarlimi(self.s.usd_farq_chegarasi):
            log.info("kurs tekshirildi: farq chegaradan kichik")
            await otkazilgan.belgila(self.baza, "kurs-tekshiruvi")
            return

        xabar = (
            "💱 DOLLAR KURSI CHETGA CHIQDI\n"
            f"{AJRATGICH}\n"
            f"{kurs_matni(natija)}\n"
            f"{AJRATGICH}\n"
            "Katalogdagi narx dollarda saqlanadi, so'm narxi shu kursga "
            "ko'paytirib chiqariladi — ya'ni bu farq HAMMA taklifga tegadi.\n\n"
            "Kursni o'zim o'zgartirmadim: qaysi kurs to'g'ri ekani "
            "sizning qaroringiz."
        )
        await self._tenderga_yubor(ctx, oluvchilar, xabar)
        log.info("kurs farqi haqida xabar yuborildi")
        await otkazilgan.belgila(self.baza, "kurs-tekshiruvi")

    def _kp_eslatma_xabari(self, kutayotganlar: list[dict[str, Any]]) -> str:
        """Eslatma matni. Bo'sh bo'lsa ham xabar keladi.

        Jimlik ikki xil ma'no berardi: "hammasi joyida" va "tekshiruv
        umuman ishlamadi". Ularni ajratib bo'lmasdi.
        """
        kun = self.s.kp_eslatma_kuni
        if not kutayotganlar:
            return (
                "📄 KP eslatmasi\n\n"
                f"✅ {kun} kundan ortiq javobsiz turgan taklif yo'q."
            )

        # MIJOZ BO'YICHA GURUHLANADI. Jonli ma'lumotda bitta mijozga 8 ta
        # taklif chiqdi (АГМК) — 20 qatorli ro'yxat menejerga tushunarsiz
        # edi. Qo'ng'iroq mijozga qilinadi, taklifga emas.
        # NOMLAR TURLICHA YOZILGAN. Jonli ma'lumotda bitta korxona
        # "Олмалиқ АГМК" va "Olmaliq AGMK" deb ikki xil yozilgan —
        # guruhlash aynan taqqoslasa ular ikki mijoz bo'lib ko'rinardi.
        # Kalit uchun transliteratsiya ishlatiladi (kirill/lotin farqi
        # yo'qoladi), ko'rsatishda esa ASL yozuv qoladi.
        #
        # ATAYLAB YUZAKI: "Hoshimjon" va "Hoshimkon" birlashtirilmaydi —
        # ular boshqa harf bilan farq qiladi va haqiqatan boshqa korxona
        # bo'lishi mumkin. Noto'g'ri birlashtirish nomni yo'qotardi.
        guruh: dict[str, list[dict[str, Any]]] = {}
        korinishi: dict[str, str] = {}
        for yozuv in kutayotganlar:
            mijoz = (yozuv.get("mijoz") or "").strip() or "mijoz ko'rsatilmagan"
            kalit = transliteratsiya(mijoz).strip()
            guruh.setdefault(kalit, []).append(yozuv)
            korinishi.setdefault(kalit, mijoz)

        # Eng uzoq kutgani birinchi — u eng ko'p e'tibor talab qiladi.
        tartib = sorted(
            guruh.items(),
            key=lambda x: -max(
                _kun_farqi(str(y.get("yaratildi") or "")) for y in x[1]
            ),
        )

        qatorlar = [
            "📄 KP eslatmasi",
            "",
            f"⏳ {len(kutayotganlar)} ta taklif {kun} kundan beri javobsiz "
            f"({len(guruh)} ta mijoz):",
            "",
        ]
        for kalit, yozuvlar in tartib:
            mijoz = korinishi[kalit]
            eng_eski = max(
                _kun_farqi(str(y.get("yaratildi") or "")) for y in yozuvlar
            )
            summa = sum(float(y.get("summa") or 0) for y in yozuvlar)
            summa_matni = f" · {summa:,.0f} so'm".replace(",", " ") if summa else ""
            raqamlar = ", ".join(str(y["raqam"]) for y in yozuvlar)
            qatorlar.append(
                f"• {mijoz} — {len(yozuvlar)} ta{summa_matni}\n"
                f"   {eng_eski} kun oldin · {raqamlar}"
            )
        qatorlar += [
            "",
            "Javob kelgan bo'lsa holatini yangilang: /kpkuzatuv",
        ]
        return "\n".join(qatorlar)

    async def katalog_hisoboti(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Haftalik katalog salomatligi — Nodiraning avtonom ishi.

        LLM CHAQIRILMAYDI va KATALOG O'ZGARTIRILMAYDI. Nodira hech
        qachon o'z-o'zidan yozmaydi (kontrakt talabi) — bu ish faqat
        SANAYDI va menejerga aytadi. Nima to'ldirish kerakligi
        ko'rinib tursin, qaror odamda qolsin.
        """
        oluvchilar = self.s.tender_idlar
        if not oluvchilar:
            return

        try:
            mahsulotlar = await self.orkestr().api.mahsulotlar()
            olchov = katalog_salomatligi.hisobla(mahsulotlar)
            yoq_oilalar = katalog_salomatligi.bosma_katalogdan_yoq(mahsulotlar)
            matn = katalog_salomatligi.matn(olchov, yoq_oilalar)
        except Exception as xato:
            log.exception("katalog hisoboti bajarilmadi")
            await self._tenderga_yubor(
                ctx, oluvchilar,
                "🗂 Katalog salomatligi\n\n⚠️ Hisobot tayyorlanmadi.\n"
                f"Sabab: {xato}",
            )
            return

        await self._tenderga_yubor(ctx, oluvchilar, matn)
        log.info(
            "katalog hisoboti: %d variant, %d narxsiz, %d ta oluvchi",
            olchov["variant"], olchov["narxsiz"], len(oluvchilar),
        )
        await otkazilgan.belgila(self.baza, "katalog-hisoboti")

    def _tender_xabari(self, konvert: Any) -> str:
        """Kuzatuv natijasini xabarga aylantiradi (mos e'lon bo'lmasa ham)."""
        nomi = self.korinishlar.get("tender-watch", "Tender kuzatuvchisi")
        natija = konvert.natija or {}
        mos = natija.get("mos_elonlar") or []

        if mos:
            # Mos e'lon bor — to'liq ro'yxat, havolalari bilan.
            return f"🔔 {nomi} — {len(mos)} ta mos e'lon\n\n" + javob_matni(
                Natija(sorov="kunlik kuzatuv", davomiylik_ms=0, yakuniy=konvert),
                self.korinishlar,
            )

        q = [f"📋 {nomi}", ""]
        if konvert.holat.value == "xato":
            q.append("⚠️ Tekshiruv tugallanmadi.")
            q.append(konvert.izoh or "Sabab ko'rsatilmagan.")
            q.append("")
            q.append("Qayta urinish: /tender")
            return "\n".join(q)

        # "HAMMASI ILGARI KO'RILGAN" DEGAN GAP OLIB TASHLANDI.
        #
        # U eski mantiqdan qolgan edi: tekshiruv faqat YANGI lotni
        # qidirardi. Endi har tekshiruv HOZIR OCHIQ lotlarni beradi,
        # ya'ni "ilgari ko'rilgan" degan tushuncha umuman yo'q —
        # menejer uchun lot ko'rilganmi yoki yo'qmi ahamiyatsiz,
        # muhimi u hali ochiqmi.
        korilgan = natija.get("yangi_korildi") or natija.get("jami_korildi") or 0

        q.append("Bizga mos e'lon topilmadi.")
        q.append("")
        if korilgan:
            q.append(f"   {korilgan} ta ochiq e'lon ko'rildi, mos kelgani yo'q.")
        else:
            q.append("   Manbada umuman e'lon topilmadi.")
        # Sarlavhasi mos, hujjati o'qilgach chiqarilgan lotlar — jimgina
        # yo'qolmasin, menejer sababini ko'rsin.
        chiqarilgan = [c for c in natija.get("hujjat_chiqargan") or [] if isinstance(c, dict)]
        if chiqarilgan:
            q.append(f"   Hujjati o'qilgach {len(chiqarilgan)} ta lot chiqarildi:")
            for lot in chiqarilgan:
                q.append(
                    f"   · {str(lot.get('sarlavha') or '—')[:80]} — {lot.get('sabab') or ''}"
                )

        manbalar = natija.get("manbalar") or []
        if manbalar:
            q.append(f"   Manbalar: {', '.join(str(m) for m in manbalar)}")

        # Modelning xulosasi FAQAT e'lon ko'rilganda qo'shiladi —
        # o'shanda u "nega mos kelmadi" degan yangi ma'lumot beradi.
        # E'lon umuman bo'lmasa u yuqoridagi qatorni takrorlaydi, xolos.
        xulosa = (natija.get("xulosa") or "").strip()
        if xulosa and korilgan:
            q.append("")
            q.append(f"   {xulosa}")

        qamrov = (natija.get("qamrov_izohi") or "").strip()
        if qamrov:
            q.append("")
            q.append(f"ℹ️ {qamrov}")
        return "\n".join(q)

    async def _tenderga_yubor(
        self, ctx: ContextTypes.DEFAULT_TYPE, oluvchilar: set[int], matn: str
    ) -> None:
        """Uzun xabarni BO'LIB yuboradi — kesib tashlamaydi.

        JIM YO'QOTISH EDI: ilgari `matn[:bot_maks_belgi]` qilinardi.
        Jonli holat: 12 ta mos e'lon topilgan, menejerga 5 tasi
        yetgan — qolgan 7 tasi hech qayerda ko'rinmasdan yo'qolgan.
        Telegram chegarasi 4096 belgi, e'lon esa ~250 belgi.
        """
        bolaklar = xabarni_bol(matn, self.s.bot_maks_belgi)
        for tg_id in oluvchilar:
            for i, bolak in enumerate(bolaklar, 1):
                davomi = (
                    f"\n\n— {i}/{len(bolaklar)} —" if len(bolaklar) > 1 else ""
                )
                try:
                    await ctx.bot.send_message(
                        tg_id, bolak + davomi, disable_web_page_preview=True
                    )
                except Exception:
                    log.exception("tender xabari yuborilmadi: id=%s", tg_id)
                    break

    async def tender(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """`/tender` — HOZIR nima bor, shuni ko'rsatadi.

        `hammasini_korsat=True`: menejer o'zi so'raganda "ko'rilgan"
        jurnaliga qaralmaydi. U "yangi nima bor" emas, "hozir nima bor"
        degan savolni beradi — ilgari javob "hammasi ilgari ko'rilgan"
        bo'lib chiqardi va menejer o'sha ro'yxatni umuman ko'rmagan
        bo'lsa ham bo'sh qolardi.
        """
        if await self._ruxsatmi(update) is None:
            return

        saqlangan = tender_keshi.oqi()
        # KESH ESKIRGAN yoki YO'Q bo'lsa — hoziroq tekshiramiz.
        #
        # Menejer 09:00 dan OLDIN so'rasa, kechagi ro'yxatni ko'rsatish
        # noto'g'ri: muddati o'tgan lotlar hali unda turibdi. Shuning
        # uchun eskisini ko'rsatib qo'ya qolmaymiz — qaytadan olamiz.
        if (
            saqlangan is None
            or tender_keshi.yoshi_daqiqa(saqlangan[1]) >= self.s.tender_kesh_daqiqa
            # Keshda lot yo'q bo'lsa uni ko'rsatishning ma'nosi yo'q.
            or not tender_keshi.lotlimi(saqlangan[0])
        ):
            await update.effective_message.reply_text("Tekshiryapman…")
            await self.tender_tekshiruvi(ctx)
            return

        matn, vaqt = saqlangan
        yosh = tender_keshi.yoshi_daqiqa(vaqt)
        belgi = (
            f"\n\n🕒 {yosh // 60} soat oldingi holat" if yosh >= 60 else ""
        )
        for bolak in xabarni_bol(matn + belgi, self.s.bot_maks_belgi):
            await update.effective_message.reply_text(
                bolak, disable_web_page_preview=True
            )


    async def kp(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """`/kp` — boshqariladigan savol-javob orqali KP.

        Erkin matnli yo'l o'zgarmaydi; bu unga QO'SHIMCHA. Vazifa
        oldindan ma'lum bo'lgani uchun router chaqirilmaydi.
        """
        tg_id = await self._ruxsatmi(update)
        if tg_id is None:
            return
        await kp_oqim.boshla(self.baza, update.effective_message, tg_id)

    async def kp_hujjati(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Shakl ochiq bo'lganda yuborilgan fayl — texnik topshiriq.

        Shakl ochiq BO'LMASA hech narsa qilmaydi: menejer boshqa
        maqsadda fayl yuborgan bo'lishi mumkin.
        """
        tg_id = await self._ruxsatmi(update)
        if tg_id is None:
            return
        xabar = update.effective_message
        hujjat = xabar.document
        if hujjat is None:
            return
        # `/tekshir` seansi ochiq bo'lsa fayl O'SHANGA tegishli (KP yoki TZ).
        if tekshir_oqim.faolmi(tg_id):
            if (hujjat.file_size or 0) > tekshir_oqim.MAKS_HAJM:
                await tekshir_oqim.hujjat(xabar, tg_id, None, hujjat.file_name or "fayl",
                                          hujjat.file_size or 0)
                return
            fayl = await hujjat.get_file()
            await tekshir_oqim.hujjat(xabar, tg_id, fayl, hujjat.file_name or "fayl",
                                      hujjat.file_size or 0)
            return
        fayl = await hujjat.get_file()
        await kp_oqim.hujjat(
            self.baza, xabar, tg_id, fayl, hujjat.file_name or "tz"
        )

    async def kp_tugmasi(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        soro = update.callback_query
        if soro is None:
            return
        await soro.answer()
        tg_id = update.effective_user.id if update.effective_user else None
        if not self.ruxsat.foydalanuvchi(tg_id).ruxsat:
            await soro.edit_message_text("⛔ Sizda ruxsat yo'q.")
            return
        await kp_oqim.tugma(self.baza, soro, tg_id)

    async def tekshir(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """`/tekshir` — tayyor KP ni TZ bilan solishtirish (`bot/tekshir_oqim.py`)."""
        tg_id = await self._ruxsatmi(update)
        if tg_id is None:
            return
        await tekshir_oqim.boshla(update.effective_message, tg_id)

    async def tekshir_tugmasi(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        soro = update.callback_query
        if soro is None:
            return
        await soro.answer()
        tg_id = update.effective_user.id if update.effective_user else None
        if not self.ruxsat.foydalanuvchi(tg_id).ruxsat:
            await soro.edit_message_text("⛔ Sizda ruxsat yo'q.")
            return
        await tekshir_oqim.tugma(soro, tg_id)

    async def menejer(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """KP da kimning nomi chiqishini ko'rsatadi va o'zgartiradi.

        `/menejer` — hozirgisini ko'rsatadi.
        `/menejer Ism Familiya +998...` — darhol almashtiradi.
        """
        tg_id = await self._ruxsatmi(update)
        if tg_id is None:
            return

        xabar = update.effective_message
        arg = " ".join(ctx.args or []).strip()

        if arg:
            ism, telefon = _menejer_ajrat(arg)
            if not ism or not telefon:
                await xabar.reply_text(
                    "Ism-familiya va telefon raqamini birga yozing.\n"
                    "Masalan: /menejer Яхшибоев Бауржон +998 90 099 12 60"
                )
                return
            await self.baza.menejer_yoz(tg_id, ism, telefon)
            await xabar.reply_text(f"✅ Yangilandi:\n\n{ism}\n{telefon}")
            return

        from kp import menejer_uchun

        xodim = await self.baza.menejer(tg_id) or menejer_uchun(tg_id)
        if xodim:
            await xabar.reply_text(
                f"👤 KP da shu ma'lumot chiqadi:\n\n"
                f"{xodim['ism']}\n{xodim['telefon']}\n\n"
                f"O'zgartirish: /menejer Ism Familiya +998 XX XXX XX XX"
            )
            return

        await xabar.reply_text(
            "Hali menejer ko'rsatilmagan.\n\n"
            "KP so'raganingizda o'zim so'rayman, yoki hoziroq yozing:\n"
            "/menejer Ism Familiya +998 XX XXX XX XX"
        )

    async def murojaatlar(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Mijozlar botidagi suhbatlar — savol va bot bergan javob bilan.

        Menejer "mijoz bilan nima gaplashildi" ni ko'rishi shart: bot unga
        "menejerimiz bog'lanadi" deb va'da beradi.

        `/murojaatlar` — oxirgi ko'rilmaganlar.
        `/murojaatlar hammasi` — ko'rilganlari bilan birga.
        """
        if await self._ruxsatmi(update) is None:
            return

        hammasimi = bool(ctx.args) and ctx.args[0].lower().startswith("hamma")
        yozuvlar = await self.baza.murojaatlar(
            holat=None if hammasimi else "yangi", chek=MUROJAAT_CHEK
        )
        xabar = update.effective_message
        if not yozuvlar:
            await xabar.reply_text(
                "Yangi murojaat yo'q."
                if not hammasimi else "Murojaatlar hali yo'q."
            )
            return

        for y in reversed(yozuvlar):
            await xabar.reply_text(
                _murojaat_matni(y)[: self.s.bot_maks_belgi],
                disable_web_page_preview=True,
            )
        if not hammasimi:
            for y in yozuvlar:
                await self.baza.murojaat_korildi(y["id"])
            await xabar.reply_text(
                f"{len(yozuvlar)} ta murojaat ko'rilgan deb belgilandi.\n"
                "Hammasi: /murojaatlar hammasi"
            )

    async def _bekor_qil(self, update: Update, tg_id: int) -> None:
        """Kutilayotgan tasdiqni rad etadi va suhbatni tozalaydi."""
        xabar = update.effective_message
        # `/kp` shakli ochiq bo'lsa — birinchi navbatda o'shani to'xtatamiz.
        # Aks holda menejer "bekor" desa ham savollar davom etardi.
        if await kp_oqim.bekor(self.baza, xabar, tg_id):
            return
        if await tekshir_oqim.bekor(xabar, tg_id):
            return
        await suhbat.tozala(self.baza, suhbat.ICHKI, tg_id)
        await self.baza.savol_ochir(tg_id)

        kutilayotgan = await self.baza.kutilayotgan_tasdiqlar()
        if not kutilayotgan:
            await xabar.reply_text(
                "Bekor qilindi. Kutilayotgan ish yo'q edi — yangi so'rov yozing."
            )
            return

        oxirgi = kutilayotgan[-1]
        try:
            await self.orkestr().davom_ettir(
                oxirgi["iz_id"], tasdiqlaymi=False, izoh="foydalanuvchi bekor qildi"
            )
        except Exception:
            log.exception("bekor qilishda xato: iz=%s", oxirgi["iz_id"])
            await xabar.reply_text("⚠️ Bekor qilib bo'lmadi — /tasdiq dan ko'ring.")
            return

        qolgan = len(kutilayotgan) - 1
        matn = f"❌ Bekor qilindi: {oxirgi['korinish']}"
        if qolgan:
            matn += f"\n\nYana {qolgan} ta ish tasdiq kutmoqda — /tasdiq"
        await xabar.reply_text(matn)

    async def sorovnoma_tugmasi(self, update: Update,
                                ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """KP loyihasi tugmasi: mijozga yuborish yoki o'zim yuborish."""
        soro = update.callback_query
        if soro is None:
            return
        await soro.answer()
        if await self._ruxsatmi(update) is None:
            return

        from sorovnoma import menejer as sn_menejer

        xom = (soro.data or "")[len(sn_menejer.TUGMA_OLDI):]
        bolaklar = xom.split(":")
        if len(bolaklar) != 3:
            return
        sorovnoma_id, mijoz_tg_id, amal = bolaklar

        yozuv = await self._sorovnoma_topib(sorovnoma_id)
        aloqa = str((yozuv or {}).get("aloqa") or "")
        ism = str((yozuv or {}).get("ism") or "")

        if amal == sn_menejer.OZIM:
            await soro.edit_message_reply_markup(reply_markup=None)
            await soro.message.reply_text(
                sn_menejer.ozim_matni(aloqa, mijoz_tg_id),
                parse_mode="Markdown", disable_web_page_preview=True)
            return

        if amal != sn_menejer.YUBOR:
            return

        yuborildi = await self._kpni_mijozga_yubor(
            mijoz_tg_id, sn_menejer.loyiha_raqami(int(sorovnoma_id)))
        if yuborildi:
            # Tugmalar OLIB TASHLANADI — ikki marta yuborilmasin.
            await soro.edit_message_reply_markup(reply_markup=None)
            await soro.message.reply_text(sn_menejer.yuborildi_matni(ism))
            return
        await soro.message.reply_text(
            "⚠️ Mijozga yuborilmadi (botni bloklagan yoki chat yopilgan).\n\n"
            + sn_menejer.ozim_matni(aloqa, mijoz_tg_id),
            parse_mode="Markdown", disable_web_page_preview=True)

    async def _sorovnoma_topib(self, sorovnoma_id: str) -> dict | None:
        try:
            hammasi = await self.baza.sorovnomalar(holat=None, chek=200)
        except Exception:
            log.warning("so'rovnoma topilmadi", exc_info=True)
            return None
        return next((y for y in hammasi if str(y["id"]) == str(sorovnoma_id)), None)

    async def _kpni_mijozga_yubor(self, mijoz_tg_id: str, raqam: str) -> bool:
        """PDF ni MIJOZLAR boti orqali yuboradi."""
        from sorovnoma import menejer as sn_menejer

        if self._mijoz_bot is None:
            log.warning("MIJOZ_BOT_TOKEN yo'q — KP yuborilmadi")
            return False
        yol = self.s.kp_papkasi / f"KP_{raqam}.pdf"
        if not yol.exists():
            log.warning("KP fayli topilmadi: %s", yol)
            return False
        try:
            await self._mijoz_bot.send_message(
                int(mijoz_tg_id), sn_menejer.MIJOZGA, parse_mode="Markdown")
            with open(yol, "rb") as fayl:
                await self._mijoz_bot.send_document(
                    int(mijoz_tg_id), fayl, filename=yol.name)
        except Exception:
            log.exception("KP mijozga yuborilmadi: id=%s", mijoz_tg_id)
            return False
        return True

    async def sorovnomalar(self, update: Update,
                           ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Mijozlar botida to'ldirilgan oprosniy listlar.

        Xabar menejerga darhol ketadi, lekin xabar YO'QOLISHI mumkin
        (telefon o'chgan, chat tozalangan, bot bloklangan). Yozuv esa
        bazada qoladi — bu buyruq o'shani ko'rsatadi.

        `/sorovnomalar`         — yangilari
        `/sorovnomalar hammasi` — ko'rilganlari bilan
        """
        if await self._ruxsatmi(update) is None:
            return

        from sorovnoma import SorovnomaShakli
        from sorovnoma.oqim import menejer_matni

        hammasimi = bool(ctx.args) and ctx.args[0].lower().startswith("hamma")
        yozuvlar = await self.baza.sorovnomalar(
            holat=None if hammasimi else "yangi", chek=MUROJAAT_CHEK)
        xabar = update.effective_message
        if not yozuvlar:
            await xabar.reply_text(
                "Yangi so'rovnoma yo'q." if not hammasimi
                else "So'rovnomalar hali yo'q.")
            return

        for y in reversed(yozuvlar):
            shakl = SorovnomaShakli(bolim_kaliti=y["bolim"],
                                    javoblar=y["javoblar"])
            matn = menejer_matni(shakl, ism=y.get("ism") or "",
                                 aloqa=y.get("aloqa") or "",
                                 tg_id=y.get("tg_id") or "")
            await xabar.reply_text(matn[: self.s.bot_maks_belgi],
                                   parse_mode="Markdown")
        if not hammasimi:
            for y in yozuvlar:
                await self.baza.sorovnoma_korildi(y["id"])
            await xabar.reply_text(
                f"{len(yozuvlar)} ta so'rovnoma ko'rilgan deb belgilandi." + "\n"
                "Hammasi: /sorovnomalar hammasi")

    async def sarf(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """LLM sarfi — bepul tarif limitiga qancha qolgani.

        Tizim bepul tarifdagi modelga tayanganda limit REAL xavf. Ilgari
        unga yaqinlashganimizni faqat URILGANDA bilardik — menejer KP
        so'ragan payt, mijoz kutib turganda. Endi oldindan ko'rinadi.

        Raqamlar SQL agregatsiyasidan keladi, modeldan emas.
        """
        if await self._ruxsatmi(update) is None:
            return

        from app.sarf_hisoboti import hisobot_matni

        matn = await hisobot_matni(self.baza)
        await update.effective_message.reply_text(matn[: self.s.bot_maks_belgi])

    async def hisobot(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Tizim qancha ish qilgani.

        `/hisobot`          — oxirgi 7 kun
        `/hisobot 2 hafta`  — oxirgi 14 kun
        `/hisobot oy`       — oxirgi 30 kun
        `/hisobot 14`       — oxirgi 14 kun (quruq raqam ham ishlaydi)

        Raqamlar KODDAN keladi (SQL agregatsiyasi), model ishlatilmaydi:
        bir xil davr har safar bir xil natija berishi shart.
        """
        if await self._ruxsatmi(update) is None:
            return

        davr = _davrni_oqi(ctx.args or [])
        h = await asyncio.to_thread(hisobot_yig, self.s.baza_fayli, davr)
        await update.effective_message.reply_text(
            hisobot_matni(h), disable_web_page_preview=True
        )

    async def haftalik_hisobot(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Dushanba ertalab avtomatik yuboriladi."""
        oluvchilar = self.s.tender_idlar
        if not oluvchilar:
            return
        try:
            h = await asyncio.to_thread(
                hisobot_yig, self.s.baza_fayli, Davr.kunlar(7, "o'tgan hafta")
            )
            matn = hisobot_matni(h)
        except Exception:
            log.exception("haftalik hisobot tayyorlanmadi")
            return
        for tg_id in oluvchilar:
            try:
                await ctx.bot.send_message(tg_id, matn, disable_web_page_preview=True)
            except Exception:
                log.warning("hisobot yuborilmadi: id=%s", tg_id)
        log.info("haftalik hisobot yuborildi: %d oluvchi", len(oluvchilar))
        await otkazilgan.belgila(self.baza, "haftalik-hisobot")

    async def tasdiqlar(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._ruxsatmi(update) is None:
            return
        kutilayotgan = await self.baza.kutilayotgan_tasdiqlar()
        if not kutilayotgan:
            await update.effective_message.reply_text("Kutilayotgan tasdiq yo'q.")
            return
        for t in kutilayotgan:
            await update.effective_message.reply_text(
                f"⏸ {t['korinish']}\n\n{t['sorov']}\n\n💬 {t['izoh']}",
                reply_markup=self._tasdiq_tugmalari(t["iz_id"]),
            )

    # --- asosiy oqim ---------------------------------------------------------

    async def sorov(self, update: Update, _: ContextTypes.DEFAULT_TYPE,
                    matn: str | None = None) -> None:
        """Menejer so'rovi.

        `matn` tashqaridan berilishi mumkin — ovozli xabar o'girilganda
        `ovoz()` shu yo'l bilan chaqiradi, shunda butun mantiq (KP shakli,
        tasdiq, suhbat konteksti) bir joyda qoladi.
        """
        tg_id = await self._ruxsatmi(update)
        if tg_id is None:
            return

        xabar = update.effective_message
        if matn is None:
            matn = (xabar.text or "").strip()
        matn = (matn or "").strip()
        if not matn:
            return

        # "bekor qil" — kutilayotgan tasdiqni rad etadi. Modelga
        # yubormaymiz: bu buyruq, so'rov emas.
        if matn.lower().strip(" .!?") in BEKOR_SOZLARI:
            if await kp_oqim.bekor(self.baza, xabar, tg_id):
                return
            await self._bekor_qil(update, tg_id)
            return

        # `/kp` shakli ochiq bo'lsa — bu xabar SAVOLGA JAVOB, yangi so'rov
        # emas. Routerga yuborilsa, "250 kv, 3 metr" alohida so'rov deb
        # tushunilardi va shakl uzilib qolardi.
        if await kp_oqim.javob(self.baza, xabar, tg_id, matn):
            return

        # Oldin savol berilgan bo'lsa (menejer kim, KP qaysi tilda), bu
        # xabar — o'sha savolga javob. Asl so'rov tiklanadi.
        kutilgan = await self._kutilgan_javob(tg_id, matn)
        if kutilgan:
            matn, tasdiq = kutilgan
            await xabar.reply_text(f"{tasdiq}\n\nSo'rovingizni davom ettiraman…")
            # Asl so'rov allaqachon tiklandi — suhbat konteksti bilan
            # yana birlashtirilsa, bir xil matn ikki marta tushardi.
            await suhbat.tozala(self.baza, suhbat.ICHKI, tg_id)

        # Agent oldin aniqlashtirish so'ragan bo'lsa, bu xabar — javob.
        # Ikkalasi birlashtiriladi (batafsil: bot/suhbat.py).
        davom = await suhbat.boshla(self.baza, suhbat.ICHKI, tg_id, matn)

        yozmoqda = asyncio.create_task(self._yozmoqda(xabar.chat))

        # Router reja tuzgach, bajarishdan OLDIN: foydalanuvchiga rejani
        # ko'rsatamiz va agent darajasidagi ruxsatni tekshiramiz.
        async def rejani_kor(reja: Reja) -> str | None:
            # Reja faqat ZANJIR yoki SEKIN ish bo'lganda ko'rsatiladi.
            # Bitta tez agent uchun "Reja: Temur ishlaydi" — keraksiz
            # xabar: natija baribir kim javob berganini yozadi.
            izoh = _kutish_izohi(reja)
            if len(reja.qadamlar or []) > 1 or izoh:
                await xabar.reply_text(reja_matni(reja, self.korinishlar) + izoh)
            qaror = self.ruxsat.reja(tg_id, reja)
            if not qaror.ruxsat:
                log.warning("ruxsatsiz agent: id=%s reja=%s", tg_id, reja.qadamlar)
                return qaror.sabab
            return None

        # BOSQICHLARNI KO'RSATISH. Zanjir 60–80 soniya olishi mumkin va shu
        # muddat davomida menejer bo'sh ekranga qarab turardi. Endi bitta
        # xabar tahrirlanib boradi: kim ishlayotgani va nima chiqqani
        # ko'rinadi. Yangi xabar yuborilmaydi — chat to'lib ketmasin.
        holat_xabari: Any = None
        qatorlar: list[str] = []

        async def qadam_holati(agent: str, konvert: Any) -> None:
            nonlocal holat_xabari
            kim = self.korinishlar.get(agent) or agent
            if konvert is None:
                qatorlar.append(f"⏳ {kim} ishlayapti…")
            else:
                natija_izohi = _qisqa_natija(konvert)
                qatorlar[-1] = f"✅ {kim}" + (f" — {natija_izohi}" if natija_izohi else "")
            matn_holat = "\n".join(qatorlar)
            if holat_xabari is None:
                holat_xabari = await xabar.reply_text(matn_holat)
            else:
                await holat_xabari.edit_text(matn_holat)

        try:
            natija = await self.orkestr().bajar(
                davom.sorov,
                # KP pastidagi menejer bloki AYNAN so'rov yuborgan xodimniki
                # bo'lishi uchun (bot bir necha kishida ishlaydi).
                kontekst={
                    "telegram_id": tg_id,
                    # Suhbat xotirasi eski so'rovni ham qo'shib yuboradi.
                    # Ba'zi agentlar (Temur) esa AYNAN oxirgi xabarni
                    # bilishi kerak: "1-tovarga 5 mln" — bu tahrir,
                    # yangi KP emas.
                    "yangi_xabar": matn,
                },
                reja_tekshiruvi=rejani_kor,
                kuzatuvchi=qadam_holati,
            )
        except Exception as xato:  # bot tushib qolmasin
            log.exception("so'rov bajarilmadi")
            await xabar.reply_text(f"⚠️ So'rov bajarilmadi: {xato}")
            return
        finally:
            yozmoqda.cancel()

        await suhbat.yakunla(self.baza, suhbat.ICHKI, tg_id, davom, natija)

        # Agent savol berdi — javob kelganda shu so'rovni davom ettiramiz.
        kerak = (natija.yakuniy.natija or {}).get("kerak")
        if kerak in ("menejer", "til"):
            await self.baza.savol_yoz(tg_id, kerak, davom.sorov)

        await self._uzun_javob(
            update, javob_matni(natija, self.korinishlar),
            f"natija-{natija.iz_id}.txt"
        )
        await self._tayyor_fayllar(xabar, natija)

        if natija.yakuniy.tasdiq_kerak and natija.iz_id is not None:
            await xabar.reply_text(
                tasdiq_matni(natija, self.korinishlar),
                reply_markup=self._tasdiq_tugmalari(natija.iz_id),
            )

    async def ovoz(self, update: Update, kontekst: ContextTypes.DEFAULT_TYPE) -> None:
        """Menejerdan kelgan ovozli xabar.

        RUXSAT ENG BIRINCHI tekshiriladi — o'girish pullik chaqiruv, va
        ichki bot oq ro'yxat bilan ishlaydi. Aks holda notanish odam
        ovoz yuborib token sarflay olardi.
        """
        tg_id = await self._ruxsatmi(update)
        if tg_id is None:
            return

        xabar = update.effective_message
        ovozli = xabar.voice or xabar.audio
        if ovozli is None:
            return

        davomiylik = int(getattr(ovozli, "duration", 0) or 0)
        if davomiylik > ovoz_moduli.MAKS_SONIYA:
            await xabar.reply_text(
                f"Ovozli xabar juda uzun ({davomiylik} s). "
                f"{ovoz_moduli.MAKS_SONIYA} soniyagacha yuboring."
            )
            return

        try:
            fayl = await ovozli.get_file()
            xom = bytes(await fayl.download_as_bytearray())
            matn = await ovoz_moduli.matnga(
                xom, getattr(ovozli, "mime_type", None) or "audio/ogg")
        except Exception as xato:
            log.warning("ovoz o'girilmadi: %s", xato)
            await xabar.reply_text(
                "Ovozli xabarni tushunolmadim — matn bilan yozing.")
            return

        await xabar.reply_text(f"🎧 Eshitdim: «{matn}»")
        # JAVOB FAQAT MATNDA.
        #
        # Menejerga keladigan javob ko'pincha jadval bo'ladi: tender
        # ro'yxati lot raqamlari bilan, KP pozitsiyalari, narx jadvali.
        # «lot ikki yuz oltmish bir million...» degan ovozni tinglab
        # bo'lmaydi va u ko'z bilan o'qishdan sekinroq. Mijozlar botida
        # esa javob qisqa va tavsifiy — u yerda ovoz qaytariladi.
        await self.sorov(update, kontekst, matn=matn)

    async def tasdiq_tugmasi(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        soro = update.callback_query
        if soro is None:
            return
        await soro.answer()

        tg_id = update.effective_user.id if update.effective_user else None
        if not self.ruxsat.foydalanuvchi(tg_id).ruxsat:
            await soro.edit_message_text("⛔ Sizda ruxsat yo'q.")
            return

        qaror, _, xom_id = (soro.data or "").partition(":")
        if not xom_id.isdigit():
            return
        iz_id = int(xom_id)
        tasdiqlaymi = qaror == "ha"

        # Tugmalarni olib tashlaymiz — ikki marta bosilmasin.
        await soro.edit_message_reply_markup(reply_markup=None)

        try:
            natija = await self.orkestr().davom_ettir(
                iz_id,
                tasdiqlaymi,
                izoh=f"Telegram: {update.effective_user.full_name}"
                if update.effective_user
                else "Telegram",
            )
        except TasdiqXatosi as xato:
            await soro.message.reply_text(f"⚠️ {xato}")
            return
        except Exception as xato:
            log.exception("tasdiq bajarilmadi")
            await soro.message.reply_text(f"⚠️ Tasdiq bajarilmadi: {xato}")
            return

        bosh = "✅ Tasdiqladingiz." if tasdiqlaymi else "❌ Rad etdingiz."
        await soro.message.reply_text(bosh)

        matn = javob_matni(natija, self.korinishlar)
        if len(matn) <= self.s.bot_maks_belgi:
            await soro.message.reply_text(matn, disable_web_page_preview=True)
        else:
            fayl = io.BytesIO(matn.encode("utf-8"))
            fayl.name = f"natija-{iz_id}.txt"
            await soro.message.reply_document(fayl)

        # Tasdiqlangan hujjat — endi qo'lda yuborish mumkin.
        await self._tayyor_fayllar(soro.message, natija)


def yasa() -> Application:
    s = sozlama()
    if not s.bot_token:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env fayliga BotFather bergan tokenni qo'shing."
        )

    bot = Bot()
    if not bot.ruxsat.sozlanganmi():
        log.warning(
            "BOT_RUXSAT_ETILGAN_ID bo'sh — bot hech kimga javob bermaydi. "
            ".env ga ruxsat etilgan Telegram ID'larni yozing."
        )

    async def tayyorla(ilova: Application) -> None:
        await bot.baza.tayyorla()
        # LLM sarfini yozish shu yerda YOQILADI. `app/llm.py` bazani
        # import qilmaydi — u testlarda va alohida skriptlarda
        # bazasiz ham ishlashi kerak, shuning uchun bog'lanish teskari.
        yozuvchini_ol(bot.sarfni_yoz)
        bot.ilova = ilova
        # "/" bosilganda buyruqlar ro'yxati chiqsin.
        await menyu.ichkini_qoy(ilova.bot, bot.ruxsat.hammasi)
        log.info("Bot tayyor. Ruxsat etilgan foydalanuvchilar: %d", len(bot.ruxsat.hammasi))

    ilova = Application.builder().token(s.bot_token).post_init(tayyorla).build()
    ilova.add_handler(CommandHandler(["start", "help"], bot.boshla))
    ilova.add_handler(CommandHandler("agentlar", bot.agentlar))
    ilova.add_handler(CommandHandler("tasdiq", bot.tasdiqlar))
    ilova.add_handler(CommandHandler(["menejer", "manager", "menedjer"], bot.menejer))
    ilova.add_handler(CommandHandler("tender", bot.tender))
    ilova.add_handler(CommandHandler(["murojaatlar", "murojaat"], bot.murojaatlar))
    ilova.add_handler(CommandHandler(["hisobot", "report"], bot.hisobot))
    ilova.add_handler(CommandHandler("sarf", bot.sarf))
    ilova.add_handler(
        CommandHandler(["sorovnomalar", "sorovnoma"], bot.sorovnomalar))
    ilova.add_handler(
        CommandHandler(["bekor", "cancel"],
                       lambda u, c: bot._bekor_qil(u, u.effective_user.id))
    )
    ilova.add_handler(CommandHandler("kp", bot.kp))
    ilova.add_handler(CommandHandler("tekshir", bot.tekshir))
    ilova.add_handler(CallbackQueryHandler(bot.tekshir_tugmasi, pattern=r"^tekshir:"))
    # KP shakli tugmalari `kp:` bilan boshlanadi — tasdiq tugmalaridan
    # OLDIN turishi shart, aks holda umumiy ishlovchi ularni yutib yuboradi.
    ilova.add_handler(CallbackQueryHandler(bot.kp_tugmasi, pattern=r"^kp:"))
    ilova.add_handler(
        CallbackQueryHandler(bot.sorovnoma_tugmasi, pattern=r"^snm:"))
    ilova.add_handler(CallbackQueryHandler(bot.tasdiq_tugmasi))
    # TZ fayli — `/kp` shakli ochiq bo'lganda. Matn ishlovchisidan
    # OLDIN turadi, lekin ular kesishmaydi (`Document` va `TEXT`).
    ilova.add_handler(MessageHandler(filters.Document.ALL, bot.kp_hujjati))
    ilova.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, bot.ovoz))
    ilova.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.sorov))

    _kuzatuvni_rejala(ilova, bot, s)
    _kp_eslatmasini_rejala(ilova, bot, s)
    _kurs_tekshiruvini_rejala(ilova, bot, s)
    _muddat_eslatmasini_rejala(ilova, bot, s)
    _katalog_hisobotini_rejala(ilova, bot, s)
    _hisobotni_rejala(ilova, bot, s)
    # Tarmoq uzilishi 30 qatorli traceback yozmasin (`bot/xatolar.py`).
    return xatolar.ulash(ilova)


# JADVAL VAQTI TOSHKENT BO'YICHA.
#
# python-telegram-bot mintaqasiz `time` ni UTC deb oladi (PTB 22.8
# hujjati: "If the timezone is None, the default timezone of the bot will
# be used, which is UTC"). Ilgari barcha vaqtlar mintaqasiz yaratilardi va
# 5 soat kechikardi: "09:00" tender tekshiruvi 14:00 da, "15:00" dagisi
# 20:00 da ishlardi (2026-09-14 da logdan aniqlandi). KP eslatmasi, kurs
# tekshiruvi va hisobotlar ham shunday siljigan edi.
TOSHKENT = ZoneInfo("Asia/Tashkent")


def _jadval_vaqti(soat: int, daqiqa: int) -> dt_time:
    """Sozlamadagi "SS:DD" — Toshkent vaqti bo'yicha."""
    return dt_time(hour=soat, minute=daqiqa, tzinfo=TOSHKENT)


def _hisobotni_rejala(ilova: Application, bot: Bot, s) -> None:
    """Haftalik hisobotni dushanba ertalabga qo'yadi.

    Nega dushanba: hafta boshida o'qilsa, xulosa shu haftaga ta'sir
    qiladi. Juma kuni kelgan hisobot dam olishga ketadi va unutiladi.
    """
    if ilova.job_queue is None:
        log.warning("JobQueue yo'q — haftalik hisobot yuborilmaydi (qo'lda: /hisobot)")
        return
    if not s.tender_idlar:
        log.info("Hisobot oluvchi yo'q — BOT_RUXSAT_ETILGAN_ID bo'sh")
        return

    soat, daqiqa = s.hisobot_vaqti
    belgilangan = _jadval_vaqti(soat, daqiqa)
    ilova.job_queue.run_daily(
        bot.haftalik_hisobot,
        time=belgilangan,
        days=(s.hisobot_kuni,),
        name="haftalik-hisobot",
    )
    # Dushanba kompyuter o'chiq bo'lsa hisobot yo'qolmasin.
    ilova.job_queue.run_once(
        lambda ctx: otkazilgan.ushlab_qol(
            bot.baza, "haftalik-hisobot", bot.haftalik_hisobot, ctx,
            belgilangan, hafta_kuni=s.hisobot_kuni,
        ),
        when=1,
        name="hisobot-otkazilgan",
    )
    log.info(
        "Haftalik hisobot rejaga qo'yildi: %s %02d:%02d, %d ta oluvchi "
        "(o'tkazib yuborilgani ishga tushganda ushlab qolinadi)",
        KUN_NOMLARI[s.hisobot_kuni], soat, daqiqa, len(s.tender_idlar),
    )


def _kuzatuvni_rejala(ilova: Application, bot: Bot, s) -> None:
    """Kunlik tender tekshiruvini rejaga qo'yadi (sozlangan bo'lsa)."""
    vaqt = s.tender_vaqti
    if vaqt is None:
        log.info(
            "TENDER_KUZATUV_VAQTI bo'sh — avtomatik tekshiruv o'chirilgan "
            "(qo'lda: /tender)."
        )
        return
    if ilova.job_queue is None:
        log.warning(
            "JobQueue mavjud emas — `pip install \"python-telegram-bot[job-queue]\"` "
            "kerak. Avtomatik tekshiruv ishlamaydi."
        )
        return

    vaqtlar = s.tender_vaqtlari
    for tartib, (soat, daqiqa) in enumerate(vaqtlar):
        belgilangan = _jadval_vaqti(soat, daqiqa)
        # BIRINCHI tekshiruv har doim xabar beradi ("bugun nima bor").
        # KEYINGILARI faqat YANGI lot chiqqanda — aks holda menejer
        # kuniga ikki xil bir xil ro'yxat olardi va o'qishni to'xtatardi.
        birinchimi = tartib == 0
        ilova.job_queue.run_daily(
            _tender_ishi(bot, jim=not birinchimi),
            time=belgilangan,
            name=f"tender-kuzatuvi-{soat:02d}{daqiqa:02d}",
        )
        # O'TKAZIB YUBORILGANINI USHLAB QOLISH — faqat BIRINCHISI uchun.
        #
        # `run_daily` faqat tizim YOQIQ bo'lganda ishlaydi. Kompyuter
        # 09:00 da o'chiq bo'lsa, o'sha kunlik xabar butunlay yo'qoladi.
        # Ikkinchi tekshiruv uchun ushlab qolish kerak emas: u baribir
        # faqat yangilikni aytadi va birinchisi allaqachon bajarilgan.
        if birinchimi:
            ilova.job_queue.run_once(
                lambda ctx, v=belgilangan: otkazilgan.ushlab_qol(
                    bot.baza, "tender-kuzatuvi", bot.tender_tekshiruvi, ctx, v,
                ),
                when=1,
                name="tender-otkazilgan",
            )
    log.info(
        "Tender kuzatuvi rejaga qo'yildi: %s, %d ta oluvchi "
        "(birinchisi har doim, keyingilari faqat yangilik bo'lsa)",
        ", ".join(f"{s_:02d}:{d:02d}" for s_, d in vaqtlar), len(s.tender_idlar),
    )


def _tender_ishi(bot: Bot, jim: bool):
    """Rejali chaqiruv uchun o'ram.

    `jim=True` — yangi lot bo'lmasa xabar yuborilmaydi.
    """
    async def ishla(ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await bot.tender_tekshiruvi(ctx, faqat_yangilik=jim)

    return ishla


def _kp_eslatmasini_rejala(ilova: Application, bot: Bot, s) -> None:
    """Kunlik KP eslatmasini rejaga qo'yadi.

    Tender kuzatuvi bilan BIR XIL naqsh: kunlik ish + o'tkazib
    yuborilganini ushlab qolish. Farqi — bu ish LLM chaqirmaydi,
    shuning uchun kvota tugagan bo'lsa ham ishlayveradi.
    """
    vaqt = s.kp_eslatma_soati
    if vaqt is None:
        log.info("KP_ESLATMA_VAQTI bo'sh — eslatma o'chirilgan (qo'lda: /kpkuzatuv).")
        return
    if ilova.job_queue is None:
        log.warning("JobQueue mavjud emas — KP eslatmasi ishlamaydi.")
        return
    if not s.tender_idlar:
        log.info("KP eslatmasi oluvchisi yo'q — BOT_RUXSAT_ETILGAN_ID bo'sh")
        return

    soat, daqiqa = vaqt
    belgilangan = _jadval_vaqti(soat, daqiqa)
    ilova.job_queue.run_daily(
        bot.kp_eslatmasi, time=belgilangan, name="kp-eslatmasi",
    )
    ilova.job_queue.run_once(
        lambda ctx: otkazilgan.ushlab_qol(
            bot.baza, "kp-eslatmasi", bot.kp_eslatmasi, ctx, belgilangan,
        ),
        when=1,
        name="kp-eslatma-otkazilgan",
    )
    log.info(
        "KP eslatmasi rejaga qo'yildi: har kuni %02d:%02d, %d kundan "
        "javobsizlar, %d ta oluvchi",
        soat, daqiqa, s.kp_eslatma_kuni, len(s.tender_idlar),
    )


def _kurs_tekshiruvini_rejala(ilova: Application, bot: Bot, s) -> None:
    """Kunlik dollar kursi tekshiruvini rejaga qo'yadi.

    KP eslatmasi bilan bir xil naqsh: kunlik ish + o'tkazib
    yuborilganini ushlab qolish. LLM chaqirmaydi.
    """
    vaqt = s.kurs_tekshiruv_soati
    if vaqt is None:
        log.info("KURS_TEKSHIRUV_VAQTI bo'sh — tekshiruv o'chirilgan.")
        return
    if ilova.job_queue is None:
        log.warning("JobQueue mavjud emas — kurs tekshiruvi ishlamaydi.")
        return
    if not s.tender_idlar:
        log.info("Kurs tekshiruvi oluvchisi yo'q — BOT_RUXSAT_ETILGAN_ID bo'sh")
        return

    soat, daqiqa = vaqt
    belgilangan = _jadval_vaqti(soat, daqiqa)
    ilova.job_queue.run_daily(
        bot.kurs_tekshiruvi, time=belgilangan, name="kurs-tekshiruvi",
    )
    ilova.job_queue.run_once(
        lambda ctx: otkazilgan.ushlab_qol(
            bot.baza, "kurs-tekshiruvi", bot.kurs_tekshiruvi, ctx, belgilangan,
        ),
        when=1,
        name="kurs-tekshiruv-otkazilgan",
    )
    log.info(
        "Kurs tekshiruvi rejaga qo'yildi: har kuni %02d:%02d, "
        "chegara %.2f%%, ustama %.2f%%",
        soat, daqiqa, s.usd_farq_chegarasi, s.usd_ustama_foiz,
    )


def _muddat_eslatmasini_rejala(ilova: Application, bot: Bot, s) -> None:
    """Tender muddati yaqinlashganda kunlik eslatma."""
    vaqt = s.tender_muddat_soati
    if vaqt is None or ilova.job_queue is None or not s.tender_idlar:
        return
    soat, daqiqa = vaqt
    belgilangan = _jadval_vaqti(soat, daqiqa)
    ilova.job_queue.run_daily(
        bot.tender_muddati, time=belgilangan, name="tender-muddati",
    )
    ilova.job_queue.run_once(
        lambda ctx: otkazilgan.ushlab_qol(
            bot.baza, "tender-muddati", bot.tender_muddati, ctx, belgilangan,
        ),
        when=1,
        name="tender-muddat-otkazilgan",
    )
    log.info(
        "Tender muddat eslatmasi rejaga qo'yildi: har kuni %02d:%02d "
        "(%d kun qolganda)", soat, daqiqa, s.tender_muddat_kuni,
    )


def _katalog_hisobotini_rejala(ilova: Application, bot: Bot, s) -> None:
    """Haftalik katalog salomatligi hisobotini rejaga qo'yadi."""
    vaqt = s.katalog_hisobot_soati
    if vaqt is None:
        log.info("KATALOG_HISOBOT_VAQTI bo'sh — hisobot o'chirilgan.")
        return
    if ilova.job_queue is None or not s.tender_idlar:
        return

    soat, daqiqa = vaqt
    belgilangan = _jadval_vaqti(soat, daqiqa)
    ilova.job_queue.run_daily(
        bot.katalog_hisoboti,
        time=belgilangan,
        days=(s.katalog_kuni,),
        name="katalog-hisoboti",
    )
    ilova.job_queue.run_once(
        lambda ctx: otkazilgan.ushlab_qol(
            bot.baza, "katalog-hisoboti", bot.katalog_hisoboti, ctx,
            belgilangan, hafta_kuni=s.katalog_kuni,
        ),
        when=1,
        name="katalog-otkazilgan",
    )
    log.info(
        "Katalog hisoboti rejaga qo'yildi: %s %02d:%02d, %d ta oluvchi",
        KUN_NOMLARI[s.katalog_kuni], soat, daqiqa, len(s.tender_idlar),
    )


def main() -> None:
    yasa().run_polling()


if __name__ == "__main__":
    main()
