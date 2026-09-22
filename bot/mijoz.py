"""Mijozlar uchun Telegram bot — ICHKI BOTDAN ALOHIDA.

Nega alohida modul va alohida token:
  - ichki bot oq ro'yxat bilan ishlaydi, bu esa OCHIQ: istalgan odam yozadi;
  - mijozga faqat ikki agent ochiq (`mijoz_ruxsat.OCHIQ_AGENTLAR`), qolgani
    yopiq — narx, HR, ichki baza va katalog o'zgartirish tashqariga chiqmaydi;
  - javob ohangi boshqacha: rasmiy, brend ohangida, ichki atamalarsiz.

Bot javob berolmagan har savol BAZAGA tushadi va menejerga xabar ketadi —
murojaat botda qolib ketmasligi uchun.

Ishga tushirish:
    .venv\\Scripts\\python -m bot.mijoz
"""

from __future__ import annotations

import asyncio
import logging
import re

from telegram import Bot as TelegramBot
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from integrations.climavent_client import ClimaventKlient

from app.baza import Baza
from app.config import sozlama
from app.kurs import joriy as kurs_joriy
from app.konvert import Holat
from app.llm import AnthropicLlm
from app.orkestr import Orkestr
from app import ovoz as ovoz_moduli
from app.profil import profil
from app.router import Reja
from app.sarf import yozuvchini_ol

from sorovnoma import oqim as sorovnoma_oqimi
from sorovnoma.narx_sorov import javob_matni, narx_soralyaptimi, narxni_top

from . import menyu, suhbat, xatolar
from .formatlash import mijoz_matni
from .mijoz_ruxsat import MENEJERGA, Tezlik, ochiq_kontraktlar, rejani_tekshir

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s", level=logging.INFO
)
# `httpx` har so'rovni to'liq URL bilan yozadi, URL ichida esa BOT TOKENI
# turadi. Log fayli yoki ekran surati bilan token sizib chiqmasligi uchun
# uni o'chiramiz — xatolar baribir ko'rinadi.
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("mijoz-bot")

# Telefon raqami: +998 90 099 12 60, 901234567 — hammasi.
TELEFON = re.compile(r"(?:\+?998)?[\s\-(]?\d{2}[\s\-)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")

# Javob oxiriga qo'shiladigan eslatma — mijoz nima kutishini bilsin.
IZOH = (
    "\n\n— — —\nBu dastlabki hisob. Aniq taklif va narx uchun menejerimiz "
    "bog'lanadi."
)

# Menejerga ketadigan xabar uzunligi. Javob to'lig'icha bazada turadi,
# bu yerda faqat "nima gaplashildi" ko'rinsin.
MENEJER_SAVOL = 400
MENEJER_JAVOB = 900

# Pastdagi tugma: mijoz raqamini QO'LDA yozmasin — bitta bosishda yuborsin.
TUGMA_TELEFON = "📞 Telefon raqamimni yuborish"

# Raqamsiz davom etish. MAJBURIY qilmaymiz.
#
# Raqam so'rab yo'lni to'sib qo'ysak, uni bermoqchi bo'lmagan mijoz
# umuman ketib qoladi — biz na raqam olamiz, na so'rov. Raqamsiz
# so'rovnoma ham menejerga foydali: u nima kerakligini biladi va
# mijozga botdan javob yozadi.
TUGMA_KEYINROQ = "⏭ Keyinroq"

# Birinchi kirish — raqam so'raladi.
ALOQA_SORASH = """Assalomu alaykum! {kompaniya} yordamchisiman.

Sizga tez javob berishimiz uchun telefon raqamingizni qoldiring —
pastdagi tugmani bosing. Raqam BIR MARTA so'raladi.

Xohlamasangiz «Keyinroq» ni bosing, davom etamiz."""

# Raqam allaqachon bor — qayta so'ramaymiz.
QAYTA_SALOM = """Assalomu alaykum! Yana ko'rishganimizdan xursandmiz.

📞 Raqamingiz bizda: {telefon}"""

ALOQA_RAHMAT = """✅ Rahmat! Raqamingiz saqlandi — boshqa so'ramaymiz.

Endi kerakli uskunani tanlang:"""

KEYINROQ_JAVOBI = """Yaxshi, raqamsiz davom etamiz.

Keyin xohlagan paytda /aloqa buyrug'i bilan qoldirishingiz mumkin."""

# Salomlashish — LLM ga umuman yubormaymiz.
#
# Nega: "Assalomu alaykum" ga router mos agent topa olmaydi va savol
# menejerga o'tib ketadi. Mijoz esa "menejerimiz javob beradi" degan
# javobni oladi — salomlashishga bunday javob g'alati. Ustiga-ustak har
# salom menejerga xabar va bir so'rov puli.
SALOMLASHISH = frozenset({
    "salom", "assalom", "assalomu alaykum", "assalomu aleykum",
    "salom alaykum", "salomatmisiz", "hayrli kun", "xayrli kun",
    "hayrli tong", "xayrli tong", "hayrli kech", "xayrli kech",
    "privet", "zdravstvuyte", "здравствуйте", "привет", "салом",
    "ассалому алайкум", "hello", "hi", "hey", "start",
})
# Salomga javob QISQA: ostidan bo'limlar ro'yxati chiqadi va uzun
# tavsif uni takrorlagan bo'lardi.
SALOM_JAVOBI = "Assalomu alaykum! Nima bilan yordam bera olaman?"

# Minnatdorchilik va xayrlashuv — bularga ham agent kerak emas.
XAYRLASHUV = frozenset({
    "rahmat", "raxmat", "katta rahmat", "tashakkur", "spasibo", "спасибо",
    "xayr", "hayr", "ok", "ok rahmat", "yaxshi", "zo'r", "thanks",
})
XAYR_JAVOBI = (
    "Arzimaydi! Yana savolingiz bo'lsa — yozavering."
)


def _oddiy_javob(matn: str) -> str | None:
    """Salom/rahmatga LLM siz javob. Mos kelmasa `None`."""
    toza = matn.lower().strip(" .!,?…\n")
    if toza in SALOMLASHISH:
        return SALOM_JAVOBI
    if toza in XAYRLASHUV:
        return XAYR_JAVOBI
    return None


KUTING = "Ko'rib chiqyapman… (10–30 soniya)"

# Telegramning "yozmoqda…" belgisi ~5 soniyada o'chadi. Javob 30 soniya
# olishi mumkin, shuning uchun uni takrorlab turamiz — aks holda mijoz
# bot qotib qolgan deb o'ylaydi.
YOZMOQDA_ORALIQ = 4.0
XATO = (
    "Kechirasiz, hozir texnik nosozlik. Menejerimizga bevosita murojaat "
    "qiling: {telefon}"
)


class MijozBot:
    """Mijoz bilan gaplashadigan bot."""

    def __init__(self) -> None:
        self.s = sozlama()
        self.baza = Baza()
        # Router faqat mijozga OCHIQ kontraktlarni ko'radi — qolgan 12
        # tasining matni promptga umuman qo'shilmaydi (token tejaladi).
        self.kontraktlar = ochiq_kontraktlar()
        self.llm = AnthropicLlm(model=self.s.mijoz_bot_model or None)
        self.tezlik = Tezlik(self.s.mijoz_bot_limit,
                             kunlik=self.s.mijoz_kunlik_limit)
        # Katalog — narx savoli uchun. Orkestr o'zi ham yasaydi,
        # lekin narx qidiruvi ORKESTRSIZ ishlaydi.
        self.api = ClimaventKlient()
        self.korinishlar = {r: k.korinish for r, k in self.kontraktlar.items()}

        kompaniya = profil().malumot.get("kompaniya") or {}
        self.kompaniya_nomi = (
            kompaniya.get("savdo_brendi") or kompaniya.get("nomi") or "Kompaniya"
        )
        self.telefon = str(kompaniya.get("telefon") or "").strip()

        # Menejerga xabar ICHKI bot orqali ketadi. Mijozlar boti buni
        # qila olmaydi: menejer u bilan hech qachon suhbat boshlamagan,
        # Telegram esa notanish chatga xabar yuborishga ruxsat bermaydi.
        self._ichki_bot = (
            TelegramBot(self.s.bot_token) if self.s.bot_token else None
        )

    def orkestr(self) -> Orkestr:
        return Orkestr(self.llm, self.baza, self.kontraktlar)

    # --- buyruqlar -----------------------------------------------------------

    async def boshla(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """`/start` — raqam (bir marta), keyin bo'limlar.

        TARTIB MUHIM. Ilgari salom, raqam tugmasi va bo'limlar BIR
        VAQTDA chiqardi: mijoz uchta narsani birdan ko'rib, qaysi
        biridan boshlashni bilmasdi va pastdagi tugma keyin ham
        osilib turaverardi.

        Endi bir vaqtda BITTA ish: avval raqam (faqat birinchi kirishda),
        keyin uskuna tanlash.
        """
        foydalanuvchi = update.effective_user
        tg_id = foydalanuvchi.id if foydalanuvchi else 0
        if foydalanuvchi:
            # `/start` — yangi mavzu, eski savol-javob zanjiri uzilsin.
            await suhbat.tozala(self.baza, suhbat.MIJOZ, tg_id)
        xabar = update.effective_message

        saqlangan = await self._saqlangan_aloqa(tg_id)
        if not saqlangan:
            await xabar.reply_text(
                ALOQA_SORASH.format(kompaniya=self.kompaniya_nomi),
                reply_markup=self._aloqa_klaviaturasi(),
            )
            return

        # Raqam bor — so'ralmaydi va pastdagi tugma OLIB TASHLANADI.
        await xabar.reply_text(
            QAYTA_SALOM.format(telefon=saqlangan),
            reply_markup=ReplyKeyboardRemove(),
        )
        await self._bolimlarni_korsat(xabar, tg_id)

    async def aloqa_buyrugi(self, update: Update,
                            _: ContextTypes.DEFAULT_TYPE) -> None:
        """`/aloqa` — raqamni keyinroq qoldirish yoki almashtirish."""
        xabar = update.effective_message
        foydalanuvchi = update.effective_user
        saqlangan = await self._saqlangan_aloqa(
            foydalanuvchi.id if foydalanuvchi else 0)
        bosh = (f"📞 Hozirgi raqamingiz: {saqlangan}\n\n"
                "Almashtirmoqchi bo'lsangiz " if saqlangan else "")
        await xabar.reply_text(
            bosh + "pastdagi tugmani bosing.",
            reply_markup=self._aloqa_klaviaturasi(),
        )

    async def _bolimlarni_korsat(self, xabar, tg_id: int = 0) -> None:
        # Savatdagi pozitsiyalar soni ro'yxatda ko'rinib tursin.
        soni = 0
        if tg_id:
            try:
                soni = len(await sorovnoma_oqimi.savatni_ol(self.baza, tg_id))
            except Exception:                        # noqa: BLE001
                log.debug("savat o'qilmadi", exc_info=True)
        await xabar.reply_text(
            sorovnoma_oqimi.bolimlar_matni(soni),
            reply_markup=sorovnoma_oqimi.bolimlar_tugmalari(),
            parse_mode="Markdown",
        )

    async def bolimlar(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """`/bolimlar` — ro'yxatni qayta ko'rsatish."""
        await self._bolimlarni_korsat(update.effective_message,
                                     update.effective_user.id if update.effective_user else 0)

    async def savat(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """`/savat` — nima to'plangani va yuborish tugmasi.

        JONLI E'TIROZ (2026-08-28): savat FAQAT pozitsiya tugagan
        zahoti bir marta ko'rinardi. Mijoz «yana qo'shish» bosib
        yo'lda adashsa yoki xabar yuqoriga surilib ketsa — savatga
        qaytishning YO'LI YO'Q edi. Ya'ni to'plangan pozitsiyalar
        ko'rinmas holda qolib ketardi va hech qachon yuborilmasdi.
        """
        xabar = update.effective_message
        foydalanuvchi = update.effective_user
        tg_id = foydalanuvchi.id if foydalanuvchi else 0

        savat = await sorovnoma_oqimi.savatni_ol(self.baza, tg_id)
        if not savat:
            await xabar.reply_text(
                "🧺 So'rovingiz hozircha bo'sh." + "\n\n" +
                "Uskuna tanlash uchun: /bolimlar")
            return
        await self._savatni_korsat(xabar, savat)

    @staticmethod
    def _aloqa_klaviaturasi() -> ReplyKeyboardMarkup:
        """Raqam so'ralayotgandagi pastki tugmalar.

        `request_contact` Telegramning o'z mexanizmi: raqam foydalanuvchi
        ROZILIGI bilan keladi, biz uni so'rab yozdirmaymiz.

        `one_time_keyboard` YETARLI EMAS: u tugmani faqat YASHIRADI,
        mijoz uni qayta ochishi mumkin va u "hali raqam kerak" degan
        taassurot qoldiradi. Raqam kelgach `ReplyKeyboardRemove` bilan
        butunlay olib tashlanadi.
        """
        return ReplyKeyboardMarkup(
            [[KeyboardButton(TUGMA_TELEFON, request_contact=True)],
             [KeyboardButton(TUGMA_KEYINROQ)]],
            resize_keyboard=True,
            input_field_placeholder="Tugmani bosing yoki savolingizni yozing…",
        )

    # Eski nom — `sorov()` ichida ishlatiladi.
    _klaviatura = _aloqa_klaviaturasi

    async def kontakt(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Tugma orqali kelgan raqam — eng ishonchli lid."""
        xabar = update.effective_message
        aloqa = xabar.contact.phone_number if xabar.contact else ""
        if not aloqa:
            return
        # ESLAB QOLINADI — keyingi so'rovda qayta so'ralmasin.
        foydalanuvchi = update.effective_user
        tg_id = foydalanuvchi.id if foydalanuvchi else 0
        try:
            await self.baza.aloqa_yoz(
                tg_id, aloqa,
                foydalanuvchi.full_name if foydalanuvchi else "")
        except Exception:
            log.warning("aloqa saqlanmadi", exc_info=True)
        await self._lid(update, aloqa, sabab="mijoz raqamini yubordi")
        # Pastdagi tugma OLIB TASHLANADI — ishi tugadi.
        await xabar.reply_text(ALOQA_RAHMAT, reply_markup=ReplyKeyboardRemove())
        await self._bolimlarni_korsat(xabar, tg_id)

    def _telefon(self) -> str:
        return self.telefon or "saytimizdagi raqam orqali"

    # --- so'rovnoma ----------------------------------------------------------

    async def tugma(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Bo'lim yoki javob tugmasi bosildi."""
        soro = update.callback_query
        if soro is None:
            return
        await soro.answer()
        tg_id = update.effective_user.id if update.effective_user else 0
        malumot = soro.data or ""

        if malumot.startswith(sorovnoma_oqimi.BOLIM_OLDI):
            await self._bolimni_boshla(
                soro, tg_id, malumot[len(sorovnoma_oqimi.BOLIM_OLDI):])
            return
        if malumot.startswith(sorovnoma_oqimi.TUGMA_OLDI):
            await self._sorovnoma_tugmasi(
                soro, update, tg_id, malumot[len(sorovnoma_oqimi.TUGMA_OLDI):])

    async def _bolimni_boshla(self, soro, tg_id: int, kalit: str) -> None:
        shakl = await sorovnoma_oqimi.boshla(self.baza, tg_id, kalit)
        if shakl is None:
            await soro.edit_message_text(
                "Bu bo'lim topilmadi. /bolimlar — ro'yxatni qayta ko'rish.")
            return
        b = sorovnoma_oqimi.bolim(kalit)
        await soro.edit_message_text(f"{b.belgi} *{b.nomi}*", parse_mode="Markdown")
        await self._sorovnomani_yubor(soro.message, shakl)

    async def _sorovnoma_tugmasi(self, soro, update: Update,
                                 tg_id: int, xom: str) -> None:
        kalit, _, qiymat = xom.partition(":")

        # SAVAT tugmalari — joriy so'rovnomaga bog'liq emas: ular
        # pozitsiya TUGAGANDAN keyin ko'rsatiladi.
        if kalit == "savat":
            await self._savat_tugmasi(
                soro, tg_id, qiymat, update.effective_user)
            return

        shakl = await sorovnoma_oqimi.joriy_shakl(self.baza, tg_id)
        if shakl is None:
            await soro.edit_message_text(
                "Bu so'rovnoma yopilgan. /bolimlar — yangisini boshlash.")
            return

        joriy = shakl.joriy()
        if joriy is None or joriy.kalit != kalit:
            # Eski xabardagi tugma bosildi — javob NOTO'G'RI savolga
            # yozilmasin.
            await soro.answer("Bu savol allaqachon o'tgan", show_alert=False)
            return

        if qiymat == sorovnoma_oqimi.BEKOR:
            await self.baza.sorovnoma_holati_ochir(tg_id)
            await soro.edit_message_text("So'rovnoma bekor qilindi.")
            await self._bolimlarni_korsat(soro.message, tg_id)
            return

        if qiymat == sorovnoma_oqimi.FAYL:
            await self._faylni_yubor(soro.message, shakl)
            return

        if qiymat == sorovnoma_oqimi.ORQAGA:
            if not shakl.orqaga():
                await soro.answer("Orqaga qaytadigan joy yo'q", show_alert=False)
                return
            await self.baza.sorovnoma_holati_yoz(
                tg_id, shakl.bolim_kaliti, shakl.javoblar)
            await self._belgilarni_yangila(soro, shakl)
            return

        xato = await sorovnoma_oqimi.javobni_qabul_qil(
            self.baza, tg_id, shakl, qiymat)
        if xato:
            await soro.answer(xato[:180], show_alert=True)
            return

        await soro.edit_message_text(
            f"✅ {joriy.matn} — *{qiymat}*", parse_mode="Markdown")
        await self._keyingisi(soro.message, update, tg_id, shakl)

    async def _savat_tugmasi(self, soro, tg_id: int, qiymat: str,
                             foydalanuvchi=None) -> None:
        if qiymat == sorovnoma_oqimi.SAVAT_QOSH:
            await soro.edit_message_text("➕ Yana uskuna tanlang:")
            await self._bolimlarni_korsat(soro.message, tg_id)
            return
        if qiymat == sorovnoma_oqimi.SAVAT_YUBOR:
            await soro.edit_message_text("📤 Yuborilmoqda…")
            await self._savatni_yubor(soro.message, foydalanuvchi, tg_id)

    async def _belgilarni_yangila(self, soro, shakl) -> None:
        """Savol O'SHA xabarda qayta chiziladi — ekran to'lib ketmasin."""
        try:
            await soro.edit_message_text(
                sorovnoma_oqimi.savol_matni(shakl),
                reply_markup=sorovnoma_oqimi.tugmalar(shakl),
                parse_mode="Markdown",
            )
        except Exception:                        # matn o'zgarmasa Telegram xato beradi
            log.debug("so'rovnoma xabari yangilanmadi", exc_info=True)

    async def _faylni_yubor(self, xabar, shakl) -> None:
        from sorovnoma import fayl_yoli

        b = sorovnoma_oqimi.bolim(shakl.bolim_kaliti)
        yol = fayl_yoli(b) if b else None
        if yol is None:
            await xabar.reply_text("Bu bo'lim uchun fayl topilmadi.")
            return
        try:
            with open(yol, "rb") as fayl:
                await xabar.reply_document(
                    fayl, filename=yol.name,
                    caption=f"{b.belgi} {b.nomi} — oprosniy list.\n\n"
                            "To'ldirib menejerimizga yuboring yoki shu yerda "
                            "savollarga javob berishda davom eting.",
                )
        except Exception:
            log.exception("oprosniy list yuborilmadi: %s", yol)
            await xabar.reply_text(
                "Faylni yuborib bo'lmadi. Savollarga javob berishda davom eting.")

    async def _sorovnomani_yubor(self, xabar, shakl) -> None:
        await xabar.reply_text(
            sorovnoma_oqimi.savol_matni(shakl),
            reply_markup=sorovnoma_oqimi.tugmalar(shakl),
            parse_mode="Markdown",
        )

    async def _keyingisi(self, xabar, update: Update, tg_id: int, shakl) -> None:
        if not shakl.tugadimi():
            await self._sorovnomani_yubor(xabar, shakl)
            return
        # Pozitsiya tugadi -> SAVATGA. Yuborish hali emas: mijozga
        # boshqa uskuna ham kerak bo'lishi mumkin.
        savat = await sorovnoma_oqimi.savatga_qosh(self.baza, tg_id, shakl)
        await xabar.reply_text(
            sorovnoma_oqimi.natija_matni(shakl), parse_mode="Markdown")
        await self._savatni_korsat(xabar, savat)

    async def _savatni_korsat(self, xabar, savat) -> None:
        await xabar.reply_text(
            sorovnoma_oqimi.savat_matni(savat),
            reply_markup=sorovnoma_oqimi.savat_tugmalari(savat),
            parse_mode="Markdown",
        )

    async def _savatni_yubor(self, xabar, foydalanuvchi, tg_id: int) -> None:
        """Savatdagi hamma pozitsiya menejerga BITTA xabar bo'lib ketadi.

        `Update` emas, FOYDALANUVCHI qabul qilinadi: bu metod tugma
        bosilganda ham chaqiriladi va u yerda `Update` yo'q — uni qo'lda
        yasash mo'rt bo'lardi.
        """
        savat = await sorovnoma_oqimi.savatni_ol(self.baza, tg_id)
        if not savat:
            await xabar.reply_text("So'rov bo'sh. /bolimlar — uskuna tanlash.")
            return

        ism = foydalanuvchi.full_name if foydalanuvchi else ""
        saqlangan = await self._saqlangan_aloqa(tg_id)
        aloqa = saqlangan or (
            f"@{foydalanuvchi.username}"
            if foydalanuvchi and foydalanuvchi.username else "")

        idlar = await sorovnoma_oqimi.yakunla(
            self.baza, tg_id, savat, ism, aloqa)
        await self._menejerga_loyiha(savat, idlar, ism, aloqa, tg_id)

        # TELEFON — faqat BIR MARTA so'raladi.
        #
        # Ilgari har so'rovnoma oxirida so'ralardi. Bir mijoz uchta
        # pozitsiya bersa, bir xil raqamni uch marta yozardi — bu
        # bezovta qiladi va ba'zilari umuman tashlab ketardi.
        if saqlangan:
            await xabar.reply_text(
                f"✅ So'rovingiz menejerimizga yuborildi "
                f"({len(savat)} ta pozitsiya).\n\n"
                f"Raqamingiz bizda saqlangan: {saqlangan}\n"
                "Tez orada bog'lanamiz.")
            return
        await xabar.reply_text(
            f"✅ So'rovingiz menejerimizga yuborildi "
            f"({len(savat)} ta pozitsiya).\n\n"
            "Tezroq bog'lanishimiz uchun telefon raqamingizni qoldiring — "
            "pastdagi tugmani bosing.",
            reply_markup=self._klaviatura(),
        )

    async def _menejerga_loyiha(self, savat, idlar, ism: str,
                                aloqa: str, tg_id: int) -> None:
        """So'rov + KP LOYIHASI menejerga.

        Loyiha yasalmasa so'rov baribir ketadi — hujjatsiz. KP
        yasashdagi nosozlik mijoz murojaatini yo'qotmasligi kerak.
        """
        from sorovnoma import menejer as sn_menejer

        sorovnoma_id = idlar[0] if idlar else 0
        natija = await sn_menejer.loyihani_yasa(
            self.baza, self.api, savat, sorovnoma_id, ism, aloqa,
            self.s.kp_papkasi)

        kp, fayllar, narxsiz = (natija if natija else (None, {}, 0))
        matn = sn_menejer.xabar_matni(savat, ism, aloqa, tg_id, kp, narxsiz)
        await self._menejerga(matn, hujjatlar=list(fayllar.values()),
                              tugmalar=(sn_menejer.tugmalar(sorovnoma_id, tg_id)
                                        if kp is not None else None))

    async def _saqlangan_aloqa(self, tg_id: int) -> str:
        """Ilgari qoldirilgan telefon. Yo'q bo'lsa bo'sh satr."""
        try:
            yozuv = await self.baza.aloqa(tg_id)
        except Exception:
            log.warning("saqlangan aloqa o'qilmadi", exc_info=True)
            return ""
        return str((yozuv or {}).get("telefon") or "")

    async def _sorovnoma_javobi(self, update: Update, xabar, tg_id: int,
                                shakl, matn: str) -> None:
        """Matnli savolga javob (o'lcham, son va h.k.)."""
        if matn.lower().strip("/ ") in ("bekor", "cancel", "otmena"):
            await self.baza.sorovnoma_holati_ochir(tg_id)
            await xabar.reply_text("So'rovnoma bekor qilindi.")
            await self._bolimlarni_korsat(xabar, tg_id)
            return

        joriy = shakl.joriy()
        if joriy is not None and joriy.tanlovlar:
            # Tugmali savolga matn yozildi — tugmani qayta ko'rsatamiz.
            await xabar.reply_text("Quyidagi tugmalardan birini tanlang:")
            await self._sorovnomani_yubor(xabar, shakl)
            return

        xato = await sorovnoma_oqimi.javobni_qabul_qil(
            self.baza, tg_id, shakl, matn)
        if xato:
            await xabar.reply_text(f"⚠️ {xato}")
            await self._sorovnomani_yubor(xabar, shakl)
            return
        await self._keyingisi(xabar, update, tg_id, shakl)

    async def _narx_javobi(self, update: Update, xabar, matn: str) -> str | None:
        """Narx savoliga javob. Yuborilgan matn qaytadi (yo'q bo'lsa None).

        Matn QAYTARILADI, chunki ovozli so'rovga ovozli javob berishda
        aynan shu matn o'qib beriladi.

        Katalog olinmasa `False` qaytariladi va so'rov ODATDAGI yo'l
        bilan ketadi: narx qidiruvi nosozligi butun botni to'xtatmasin.
        """
        try:
            katalog = await self.api.mahsulotlar()
        except Exception:
            log.warning("narx uchun katalog olinmadi", exc_info=True)
            return None

        # Tekshiruv SHU YERDA: `narx_soralyaptimi` katalogni ko'radi
        # va model nomiga qarab ham qaror qiladi (`narx_sorov.py`).
        if not narx_soralyaptimi(matn, katalog):
            return None

        javob = narxni_top(katalog, matn, kurs=kurs_joriy())
        if javob is None:
            return None

        narx_matni = javob_matni(javob, self._telefon())
        await xabar.reply_text(
            narx_matni,
            parse_mode="Markdown", disable_web_page_preview=True,
        )
        # Narx aytilgan bo'lsa ham LID: mijoz baribir buyurtma beradi
        # va menejer nima so'ralganini bilishi kerak.
        await self._lid(update, matn,
                        javob=f"narx qidiruvi: {javob.holat} ({javob.model})",
                        sabab="" if javob.holat == "narx" else "narx topilmadi")
        return narx_matni

    # --- asosiy oqim ---------------------------------------------------------

    async def ovoz(self, update: Update, kontekst: ContextTypes.DEFAULT_TYPE) -> None:
        """Ovozli xabar: matnga o'giriladi va oddiy so'rov kabi ishlanadi.

        MIJOZGA MATN KO'RSATILADI. Model noto'g'ri eshitishi mumkin, va
        mijoz nima tushunilganini ko'rmasa — javob nega bunday chiqqanini
        bilmaydi. Ko'rsatilsa, xato bo'lsa darrov tuzatib yozadi.
        """
        xabar = update.effective_message
        ovozli = xabar.voice or xabar.audio
        if ovozli is None:
            return

        davomiylik = int(getattr(ovozli, "duration", 0) or 0)
        if davomiylik > ovoz_moduli.MAKS_SONIYA:
            await xabar.reply_text(
                f"Ovozli xabar juda uzun ({davomiylik} soniya). "
                f"{ovoz_moduli.MAKS_SONIYA} soniyagacha yuboring "
                "yoki matn bilan yozing."
            )
            return

        await self._yozmoqda(xabar.chat)
        try:
            fayl = await ovozli.get_file()
            xom = bytes(await fayl.download_as_bytearray())
            matn = await ovoz_moduli.matnga(
                xom, getattr(ovozli, "mime_type", None) or "audio/ogg")
        except ovoz_moduli.OvozXatosi as xato:
            log.warning("ovoz o'girilmadi: %s", xato)
            await xabar.reply_text(
                "Ovozli xabarni tushunolmadim. Iltimos, matn bilan yozing "
                "yoki qaytadan yuboring."
            )
            return
        except Exception as xato:            # tarmoq, Telegram fayl xatosi
            log.warning("ovoz olinmadi: %s", xato)
            await xabar.reply_text(
                "Ovozli xabarni ololmadim. Matn bilan yozib yuboring."
            )
            return

        await xabar.reply_text(f"🎧 Eshitdim: «{matn}»")
        javob = await self.sorov(update, kontekst, matn=matn)
        # Ovozga ovoz bilan javob qaytariladi — mijoz qaysi usulda
        # yozgan bo'lsa, o'sha usulda javob oladi.
        if javob:
            await self._ovozli_javob(xabar, javob)

    async def _ovozli_javob(self, xabar, javob: str) -> None:
        """Javobni ovoz qilib ham yuboradi.

        OVOZ — QO'SHIMCHA, ASOSIY EMAS. Matn allaqachon yuborilgan;
        bu yerda nima bo'lsa ham mijoz javobsiz qolmaydi. Shuning
        uchun har qanday xato jimgina o'tkaziladi: «ovoz chiqmadi»
        degan xabar mijozga hech narsa bermaydi.
        """
        matn = ovoz_moduli.gapirish_uchun(javob)
        if not matn:
            return
        try:
            wav = await ovoz_moduli.ovozga(matn)
            await xabar.reply_voice(wav)
        except Exception as xato:
            log.info("ovozli javob yuborilmadi: %s", xato)

    async def sorov(self, update: Update, _: ContextTypes.DEFAULT_TYPE,
                    matn: str | None = None) -> None:
        """Mijoz so'rovi.

        `matn` tashqaridan berilishi mumkin — ovozli xabar o'girilganda
        `ovoz()` shu yo'l bilan chaqiradi. Shunda butun mantiq (so'rovnoma,
        chegaralar, savat, agentlar) bir joyda qoladi va ovoz uchun
        ikkinchi nusxa yozilmaydi.
        """
        xabar = update.effective_message
        if matn is None:
            matn = (xabar.text or "").strip()
        matn = (matn or "").strip()
        if not matn:
            return

        foydalanuvchi = update.effective_user
        tg_id = foydalanuvchi.id if foydalanuvchi else 0

        # «Keyinroq» — raqamsiz davom etamiz.
        #
        # So'rovnomadan OLDIN tekshiriladi: aks holda ochiq savolga
        # javob deb qabul qilinardi va tugma matni javobga tushardi.
        if matn == TUGMA_KEYINROQ:
            await xabar.reply_text(KEYINROQ_JAVOBI,
                                   reply_markup=ReplyKeyboardRemove())
            await self._bolimlarni_korsat(xabar, tg_id)
            return

        # SO'ROVNOMA ochiq bo'lsa — bu matn o'sha savolga javob.
        #
        # TEZLIK CHEGARASIDAN OLDIN tekshiriladi.
        #
        # JONLI XATO (2026-08-28): so'rovnomani to'ldirayotgan mijoz
        # «Biroz sekinroq yozing» degan javob olardi va to'ldirish
        # to'xtardi. Chegara LLM XARAJATINI himoya qilish uchun qo'yilgan
        # (daqiqasiga 5 ta), so'rovnoma esa LLM UMUMAN ishlatmaydi —
        # u sof shakl to'ldirish. Ya'ni chegara noto'g'ri joyda edi:
        # 5 savolli so'rovnomani bir daqiqada to'ldirish MUMKIN EMAS
        # bo'lib qolgandi.
        shakl = await sorovnoma_oqimi.joriy_shakl(self.baza, tg_id)
        if shakl is not None and not shakl.tugadimi():
            await self._sorovnoma_javobi(update, xabar, tg_id, shakl, matn)
            return

        # Bu yerdan keyin LLM ishlatilishi mumkin — chegaralar SHU YERDA.
        #
        # KUNLIK kvota birinchi tekshiriladi: u xarajatni himoya qiladi
        # va uning xabari boshqacha — «ertaga qayting» emas, «menejer
        # bog'lanadi», chunki mijozni quruq qaytarish mumkin emas.
        if not self.tezlik.kunlik_ruxsatmi(tg_id):
            await self._lid(update, matn, sabab="kunlik so'rov chegarasi")
            await xabar.reply_text(
                "Bugungi savollar chegarasiga yetdingiz." + "\n\n" +
                "Savolingizni menejerimizga yubordim — u bog'lanadi." + "\n" +
                "Uskuna tanlash esa cheklovsiz: /bolimlar"
            )
            return

        if not self.tezlik.ruxsatmi(tg_id):
            await xabar.reply_text(
                "Biroz sekinroq yozing — bir daqiqada bir necha savolga "
                "javob bera olaman." + "\n\n" +
                "Uskuna tanlash uchun: /bolimlar"
            )
            return

        # Salom / rahmat — LLM ham, menejer ham kerak emas.
        oddiy = _oddiy_javob(matn)
        if oddiy:
            await suhbat.tozala(self.baza, suhbat.MIJOZ, tg_id)
            # Raqam tugmasi QAYTA chiqarilmaydi: u faqat birinchi
            # kirishda kerak. "Rahmat" ga javoban raqam so'rash
            # bosimga o'xshaydi.
            await xabar.reply_text(oddiy)
            await self._bolimlarni_korsat(xabar, tg_id)
            return

        # NARX savoli — modeldan katalogdan qidiriladi, MODELSIZ.
        #
        # Ilgari bu router orqali agentga borardi: 10-30 soniya, bir
        # so'rov puli, natija esa baribir "menejer bog'lanadi". Endi
        # javob koddan keladi va narx bor bo'lsa DARHOL aytiladi.
        narx = await self._narx_javobi(update, xabar, matn)
        if narx:
            return narx

        # Telefon qoldirildimi? Bu — lid, darrov menejerga.
        if TELEFON.search(matn) and len(matn) < 120:
            # Tugma orqali kelgani kabi eslab qolinadi: mijoz raqamni
            # qo'lda yozgan bo'lsa ham ikkinchi marta so'ramaymiz.
            try:
                await self.baza.aloqa_yoz(
                    tg_id, TELEFON.search(matn).group(0),
                    foydalanuvchi.full_name if foydalanuvchi else "")
            except Exception:
                log.warning("aloqa saqlanmadi", exc_info=True)
            await self._lid(update, matn, sabab="mijoz aloqa qoldirdi")
            await xabar.reply_text(
                "Rahmat! Menejerimiz tez orada bog'lanadi.\n\n"
                "Shu vaqtda savolingiz bo'lsa — yozavering."
            )
            return

        kutish = await xabar.reply_text(KUTING)
        yozmoqda = asyncio.create_task(self._yozmoqda(xabar.chat))

        # Reja tuzilgach, bajarishdan OLDIN: mijozga ochiq agentmi?
        rad_sababi: list[str] = []

        async def rejani_kor(reja: Reja) -> str | None:
            qaror = rejani_tekshir(reja)
            if qaror.ruxsat:
                return None
            log.info("mijozga yopiq reja: id=%s sabab=%s", tg_id, qaror.sabab)
            rad_sababi.append(qaror.sabab)
            return qaror.sabab

        # Agent oldin savol bergan bo'lsa, bu xabar — o'sha savolga javob.
        # Ikkalasi birlashtiriladi, aks holda mijoz bir xil savolni
        # qayta-qayta eshitadi (batafsil: bot/suhbat.py).
        davom = await suhbat.boshla(self.baza, suhbat.MIJOZ, tg_id, matn)

        try:
            natija = await self.orkestr().bajar(
                davom.sorov,
                kontekst={"mijoz_boti": True, "yangi_xabar": matn},
                reja_tekshiruvi=rejani_kor,
            )
        except Exception:
            log.exception("mijoz so'rovi bajarilmadi")
            await kutish.edit_text(XATO.format(telefon=self._telefon()))
            await self._lid(update, matn, sabab="texnik xato")
            return
        finally:
            yozmoqda.cancel()

        await suhbat.yakunla(self.baza, suhbat.MIJOZ, tg_id, davom, natija)

        # Rad etilgan yoki javobsiz qolgan — menejerga.
        if rad_sababi or natija.yakuniy.holat.value in ("mos_agent_yoq", "xato"):
            await kutish.edit_text(MENEJERGA.format(telefon=self._telefon()))
            await self._lid(
                update, davom.sorov,
                sabab=rad_sababi[0] if rad_sababi else natija.yakuniy.holat.value,
            )
            return

        javob = mijoz_matni(natija)
        # Izoh faqat TAYYOR javobga qo'shiladi. Bot savol berayotgan
        # bo'lsa, "bu dastlabki hisob" degani mantiqsiz — hali hisob yo'q.
        izoh = "" if natija.yakuniy.holat is Holat.ANIQLIK_KERAK else IZOH
        await kutish.edit_text(
            self._qisqartir(javob) + izoh, disable_web_page_preview=True
        )
        # Javob berilgan bo'lsa ham yozib qo'yamiz: menejer nima
        # so'ralayotganini bilsin.
        # Menejerga TO'LIQ so'rov ketadi: mijoz uni bir necha xabarda
        # yozgan bo'lsa ham, u bitta so'rov sifatida ko'rinsin.
        await self._lid(update, davom.sorov, javob=javob, sabab="")
        return javob

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

    def _qisqartir(self, matn: str) -> str:
        chek = self.s.bot_maks_belgi
        if len(matn) <= chek:
            return matn
        return matn[:chek].rsplit("\n", 1)[0] + "\n…"

    # --- lid -----------------------------------------------------------------

    async def _lid(
        self, update: Update, savol: str, javob: str = "", sabab: str = ""
    ) -> None:
        """Murojaatni bazaga yozadi va menejerlarga xabar beradi.

        HAR bir savol yuboriladi — javob berilgani ham. Sababi: mijoz bilan
        nima gaplashilgani menejerga ko'rinib tursin. Bot "menejerimiz
        bog'lanadi" deb va'da beradi, demak menejer o'sha suhbatni bilishi
        shart. Javob qisqartirib qo'shiladi — to'lig'i `/murojaatlar` da.
        """
        foydalanuvchi = update.effective_user
        aloqa = ""
        mos = TELEFON.search(savol)
        if mos:
            aloqa = mos.group(0)
        elif foydalanuvchi and foydalanuvchi.username:
            aloqa = f"@{foydalanuvchi.username}"

        # Yangi odammi — YOZISHDAN OLDIN tekshiramiz, aks holda o'zi
        # yozgan yozuv "eski" bo'lib ko'rinadi.
        yangi_mijoz = False
        if foydalanuvchi:
            try:
                yangi_mijoz = not await self.baza.murojaat_bormi(foydalanuvchi.id)
            except Exception:
                yangi_mijoz = False

        try:
            await self.baza.murojaat_yoz({
                "tg_id": foydalanuvchi.id if foydalanuvchi else 0,
                "ism": foydalanuvchi.full_name if foydalanuvchi else "",
                "aloqa": aloqa,
                "savol": savol,
                "javob": javob or None,
                "sabab": sabab or None,
            })
        except Exception:
            log.exception("murojaat yozilmadi")

        await self._menejerga(
            self._lid_xabari(foydalanuvchi, aloqa, savol, javob, sabab, yangi_mijoz)
        )

    @staticmethod
    def _lid_xabari(
        foydalanuvchi, aloqa: str, savol: str, javob: str, sabab: str,
        yangi_mijoz: bool,
    ) -> str:
        if sabab:
            bosh = "🔔 Menejer kerak"
        elif yangi_mijoz:
            bosh = "👋 Yangi mijoz"
        else:
            bosh = "💬 Mijoz savoli"

        qatorlar = [
            bosh,
            f"👤 {foydalanuvchi.full_name if foydalanuvchi else '—'}"
            + (f" · {aloqa}" if aloqa else ""),
            "",
            f"❓ {savol[:MENEJER_SAVOL]}",
        ]
        if javob:
            qisqa = javob[:MENEJER_JAVOB]
            if len(javob) > MENEJER_JAVOB:
                qisqa = qisqa.rsplit("\n", 1)[0] + "\n…"
            qatorlar += ["", f"🤖 Bot javobi:\n{qisqa}"]
        if sabab:
            qatorlar += ["", f"⚠️ Sabab: {sabab}"]
        qatorlar.append("\nTo'liq ro'yxat: /murojaatlar")
        return "\n".join(qatorlar)

    async def _menejerga(self, xabar: str, hujjatlar=None, tugmalar=None) -> None:
        if self._ichki_bot is None:
            log.warning("BOT_TOKEN yo'q — menejerga xabar yuborilmadi")
            return
        for menejer_id in self.s.mijoz_menejer_idlar:
            try:
                # Uzun xabar QIRQILMAYDI, bo'laklanadi: 12 pozitsiyali
                # savat 3000 belgiga sig'maydi va oxirgi pozitsiyalar
                # yo'qolib ketardi (`bolaklarga_boling`).
                bolaklar = sorovnoma_oqimi.bolaklarga_boling(
                    xabar, self.s.bot_maks_belgi)
                for raqam, bolak in enumerate(bolaklar):
                    # Tugmalar faqat OXIRGI bo'lakda — menejer avval
                    # hamma pozitsiyani o'qib, keyin qaror qilsin.
                    oxirgimi = raqam == len(bolaklar) - 1
                    await self._ichki_bot.send_message(
                        menejer_id, bolak,
                        parse_mode="Markdown" if tugmalar else None,
                        reply_markup=tugmalar if oxirgimi else None,
                        disable_web_page_preview=True,
                    )
            except Exception:
                log.warning("menejerga xabar ketmadi: id=%s", menejer_id)
                continue
            # Hujjatlar XABARDAN KEYIN: tugmalar xabarda qoladi va
            # menejer avval nima so'ralganini o'qiydi.
            for yol in (hujjatlar or []):
                try:
                    with open(yol, "rb") as fayl:
                        await self._ichki_bot.send_document(
                            menejer_id, fayl, filename=yol.name)
                except Exception:
                    log.warning("menejerga hujjat ketmadi: id=%s fayl=%s",
                                menejer_id, yol)


def yasa() -> Application:
    s = sozlama()
    if not s.mijoz_bot_token:
        raise RuntimeError(
            "MIJOZ_BOT_TOKEN topilmadi. Mijozlar uchun ALOHIDA bot yarating "
            "(BotFather) va tokenini .env ga qo'shing. Ichki bot tokeni "
            "ishlatilmaydi."
        )
    if s.mijoz_bot_token == s.bot_token:
        raise RuntimeError(
            "MIJOZ_BOT_TOKEN ichki BOT_TOKEN bilan bir xil. Mijozlar boti "
            "alohida bo'lishi shart — aks holda ichki buyruqlar ochiq qoladi."
        )

    bot = MijozBot()

    async def tayyorla(ilova: Application) -> None:
        # "/" bosilganda buyruqlar ro'yxati chiqsin.
        await menyu.mijozniki_qoy(ilova.bot)
        # LLM sarfini yozish SHU YERDA yoqiladi.
        #
        # JONLI KAMCHILIK (2026-09-05): `yozuvchini_ol` faqat veb ilova va
        # ichki botda chaqirilardi. Mijozlar boti alohida jarayon, ya'ni
        # unda yozuvchi umuman qo'yilmagan edi va MIJOZLAR bilan bo'lgan
        # butun suhbat xarajati hisobga tushmasdan qolardi — `/sarf`
        # haqiqiy sarfdan kam ko'rsatardi.
        await bot.baza.tayyorla()
        yozuvchini_ol(bot.baza.sarf_yoz)

    ilova = (
        Application.builder()
        .token(s.mijoz_bot_token)
        .post_init(tayyorla)
        .build()
    )
    ilova.add_handler(CommandHandler(["start", "help"], bot.boshla))
    ilova.add_handler(
        CommandHandler(["bolimlar", "bolim", "katalog"], bot.bolimlar))
    ilova.add_handler(
        CommandHandler(["aloqa", "telefon"], bot.aloqa_buyrugi))
    ilova.add_handler(
        CommandHandler(["savat", "korzina", "sorov"], bot.savat))
    ilova.add_handler(MessageHandler(filters.CONTACT, bot.kontakt))
    # Ovoz MATNDAN OLDIN: ovozli xabarda  bo'lmaydi, shuning uchun
    # ular kesishmaydi — lekin tartib niyatni ko'rsatib turadi.
    ilova.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, bot.ovoz))
    ilova.add_handler(CallbackQueryHandler(bot.tugma))
    ilova.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.sorov))
    return xatolar.ulash(ilova)


def main() -> None:
    log.info("mijozlar boti ishga tushmoqda")
    yasa().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
