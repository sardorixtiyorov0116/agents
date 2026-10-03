"""Yordamchining yadrosi: xabar keladi, javob qaytadi. Telegramsiz.

NEGA ALOHIDA, `bot/mijoz.py` NI CHAQIRMASDAN
--------------------------------------------
Mijozlar botining `sorov()` usuli Telegram `Update` obyekti bilan
ishlaydi: javobni o'zi yuboradi, «yozmoqda…» belgisini o'zi qo'yadi,
raqamni tugma orqali so'raydi. Ilovaga esa bularning hech biri kerak
emas — ilova bitta HTTP so'rov yuboradi va bitta javob kutadi.

Shuning uchun bu yerda faqat ZANJIR takrorlanadi, uning bo'g'inlari
emas: ruxsat (`rejani_tekshir`), suhbat konteksti (`bot/suhbat.py`),
narx qidiruvi (`sorovnoma/narx_sorov.py`), mijoz matni (`presenter`)
— hammasi o'sha modullar. Mijozga qaysi agent ochiq ekani hamon BITTA
joyda: `bot/mijoz_ruxsat.OCHIQ_AGENTLAR`.

TELEGRAMDAN FARQI
-----------------
  - raqam SO'RALMAYDI: ilovaga faqat telefon bilan kiriladi, ya'ni
    har murojaatda aloqa bor;
  - so'rovnoma (`/bolimlar`) yo'q — ilovada katalog va savat bor;
  - javob bilan birga katalogdagi MAHSULOT ID'lari qaytadi. Ilova
    ularni kartochka qilib ko'rsatadi, mijoz bosib sahifasiga o'tadi,
    savatga qo'shadi va KP ni darhol oladi.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.baza import Baza
from app.konvert import Holat
from app.kurs import joriy as kurs_joriy
from app.orkestr import Orkestr
from app.router import Reja
from bot import suhbat
from bot.mijoz_ruxsat import Tezlik, rejani_tekshir
from integrations.climavent_client import mahsulot_qisqa
from presenter import mijoz_matni
from sorovnoma.narx_sorov import NarxJavobi, narx_soralyaptimi, narxni_top

log = logging.getLogger("yordamchi")

# Bitta javobda ko'rsatiladigan eng ko'p kartochka. Ko'prog'i ekranni
# to'ldirib, matnni pastga surib yuboradi.
MAKS_MAHSULOT = 6

# Ilova xabar maydoni bunday uzun matnni qabul qilmaydi, lekin server
# baribir tekshiradi: chegarasiz matn — chegarasiz token.
MAKS_MATN = 1500

# Menejerga ketadigan xabar uzunligi (`bot/mijoz.py` dagidek).
MENEJER_SAVOL = 400
MENEJER_JAVOB = 900

SALOMLASHISH = frozenset({
    "salom", "assalom", "assalomu alaykum", "assalomu aleykum",
    "salom alaykum", "salomatmisiz", "hayrli kun", "xayrli kun",
    "hayrli tong", "xayrli tong", "hayrli kech", "xayrli kech",
    "privet", "zdravstvuyte", "здравствуйте", "привет", "салом",
    "ассалому алайкум", "hello", "hi", "hey",
})
XAYRLASHUV = frozenset({
    "rahmat", "raxmat", "katta rahmat", "tashakkur", "spasibo", "спасибо",
    "xayr", "hayr", "ok", "ok rahmat", "yaxshi", "zo'r", "thanks",
})

SALOM_JAVOBI = (
    "Assalomu alaykum! Men Climavent yordamchisiman.\n\n"
    "Ventilyatsiya yoki konditsioner bo'yicha yozing: xona maydoni, "
    "balandligi, necha kishi ishlashi — men hisoblab, katalogdan mos "
    "uskunani topaman."
)
XAYR_JAVOBI = "Arzimaydi! Yana savolingiz bo'lsa — yozavering."

# Javob oxiridagi eslatma: hisob TAXMINIY, va mijoz keyingi qadamni
# bilishi kerak. Telegramdagi «menejer bog'lanadi» o'rniga — ilovada
# KP ni o'zi darhol oladi.
IZOH = (
    "\n\nBu dastlabki hisob. Mahsulotni savatga qo'shib, KP ni darhol "
    "olishingiz mumkin. Savol qolsa — menejerimiz bog'lanadi."
)

MENEJERGA = (
    "Bu savolga menejerimiz aniqroq javob beradi. Savolingizni unga "
    "yubordim — ish vaqtida siz bilan bog'lanadi.\n\n"
    "Shoshilinch bo'lsa: {telefon}"
)
KUNLIK_CHEGARA = (
    "Bugungi savollar chegarasiga yetdingiz.\n\n"
    "Savolingizni menejerimizga yubordim — u bog'lanadi. Katalog va "
    "savat esa cheklovsiz ishlaydi."
)
SEKINROQ = "Biroz sekinroq yozing — bir daqiqada bir necha savolga javob bera olaman."
XATO = (
    "Kechirasiz, hozir texnik nosozlik. Savolingizni menejerga yubordim.\n\n"
    "Shoshilinch bo'lsa: {telefon}"
)
BOSH = "Savolingizni yozing."


@dataclass(frozen=True)
class Foydalanuvchi:
    """Kim yozyapti — backend tasdiqlagan ma'lumot (`yordamchi/kirish.py`)."""

    id: int
    telefon: str = ""
    ism: str = ""


@dataclass
class Javob:
    """Ilovaga qaytadigan javob.

    `holat`:
      - `javob`    — tayyor javob;
      - `savol`    — yordamchi aniqlashtiruvchi savol berdi;
      - `menejer`  — javob berilmadi, murojaat menejerga ketdi;
      - `chegara`  — tezlik yoki kunlik chegara.
    """

    matn: str
    holat: str = "javob"
    mahsulotlar: list[int] = field(default_factory=list)

    def json(self) -> dict[str, Any]:
        return {"text": self.matn, "status": self.holat, "product_ids": self.mahsulotlar}


def oddiy_javob(matn: str) -> str | None:
    """Salom/rahmatga LLM siz javob. Mos kelmasa `None`."""
    toza = matn.lower().strip(" .!,?…\n")
    if toza in SALOMLASHISH:
        return SALOM_JAVOBI
    if toza in XAYRLASHUV:
        return XAYR_JAVOBI
    return None


# --- natijadan mahsulot id'lari ---------------------------------------------

def _normal(matn: str) -> str:
    """Solishtirish uchun: kichik harf, lotin x -> kirill х, bo'shliqsiz."""
    return re.sub(r"\s+", "", str(matn).lower().replace("x", "х"))


def _nomlar(natija: dict[str, Any]) -> list[str]:
    """Agent natijasidagi model/mahsulot nomlari — TARTIB bilan.

    Tartib muhim: agent eng mosini birinchi qo'yadi, kartochkalar ham
    shu tartibda chiqishi kerak.
    """
    nomlar: list[str] = []
    for variant in natija.get("variantlar") or []:
        if isinstance(variant, dict):
            nomlar += [str(variant.get("model") or ""), str(variant.get("mahsulot") or "")]
    for ventilyator in natija.get("ventilyatorlar") or []:
        if isinstance(ventilyator, dict):
            nomlar.append(str(ventilyator.get("model") or ""))
    if natija.get("mahsulot"):
        nomlar.append(str(natija["mahsulot"]))
    return [n for n in nomlar if n.strip()]


def mahsulot_idlari(nomlar: list[str], katalog: list[dict[str, Any]]) -> list[int]:
    """Nomlarni katalog id'lariga aylantiradi. FAQAT aniq moslik.

    Taxminiy moslik qilinmaydi: noto'g'ri kartochka mijozni noto'g'ri
    mahsulot sahifasiga olib boradi va u o'shani savatga qo'shadi.
    Topilmagan nom matnda qoladi — kartochkasiz.
    """
    indeks: dict[str, int] = {}
    for mahsulot in katalog:
        mid = mahsulot.get("id")
        if not isinstance(mid, int):
            continue
        qisqa = mahsulot_qisqa(mahsulot)
        # Ichki ijro nomlari ham: narx qidiruvi (`narx_sorov._nomlar`)
        # aynan shular bilan javob qaytaradi.
        ichki = [
            str(i.get("in_model_name") or "")
            for b in (mahsulot.get("characters") or []) if isinstance(b, dict)
            for i in (b.get("insides") or []) if isinstance(i, dict)
        ]
        for nom in [qisqa["nomi"], *qisqa["modellar"], *ichki]:
            if nom.strip():
                indeks.setdefault(_normal(nom), mid)

    idlar: list[int] = []
    for nom in nomlar:
        mid = indeks.get(_normal(nom))
        if mid is not None and mid not in idlar:
            idlar.append(mid)
        if len(idlar) >= MAKS_MAHSULOT:
            break
    return idlar


def narx_matni(j: NarxJavobi) -> str:
    """Narx javobi — ILOVA uchun.

    `narx_sorov.javob_matni` dan farqi: Markdown yo'q (ilova uni xom
    ko'rsatardi) va «raqamingizni qoldiring» yo'q — raqam bizda bor.
    """
    if j.holat == "narx":
        narx = f"{j.narx:,.0f}".replace(",", " ")
        qatorlar = [j.model, "", f"Narxi: {narx} so'm (QQS bilan)"]
        if j.manba:
            qatorlar.append(j.manba)
        qatorlar += ["", "Savatga qo'shsangiz, KP darhol tayyor bo'ladi."]
        return "\n".join(qatorlar)

    if j.holat == "narxsiz":
        qatorlar = [f"{j.model} — katalogimizda bor."]
        if j.parametrlar:
            qatorlar.append("")
            qatorlar += [f"• {k}: {v}" for k, v in list(j.parametrlar.items())[:5]]
        qatorlar += [
            "",
            "Bu model narxi buyurtma parametrlariga bog'liq (o'lcham, ijro, "
            "miqdor). Savolingizni menejerga yubordim — u hisoblab beradi.",
        ]
        return "\n".join(qatorlar)

    qatorlar = [f"«{j.model}» nomli modelni katalogimizdan topa olmadim."]
    if j.takliflar:
        qatorlar += ["", "Balki bulardan biri?"]
        qatorlar += [f"• {t}" for t in j.takliflar]
    return "\n".join(qatorlar)


# --- yadro -------------------------------------------------------------------

Menejerga = Callable[[str], Awaitable[None]]


async def _jim(_: str) -> None:
    return None


class Yordamchi:
    """Bitta xabar -> bitta javob.

    Bog'liqliklar tashqaridan beriladi — testda LLM ham, katalog ham,
    Telegram ham soxta bo'ladi.
    """

    def __init__(
        self,
        baza: Baza,
        orkestr: Callable[[], Orkestr],
        katalog: Callable[[], Awaitable[list[dict[str, Any]]]],
        tezlik: Tezlik,
        menejerga: Menejerga = _jim,
        telefon: str = "",
    ) -> None:
        self.baza = baza
        self.orkestr = orkestr
        self.katalog = katalog
        self.tezlik = tezlik
        self.menejerga = menejerga
        self.telefon = telefon

    async def javob(self, kim: Foydalanuvchi, matn: str) -> Javob:
        matn = (matn or "").strip()[:MAKS_MATN]
        if not matn:
            return Javob(BOSH, holat="chegara")

        # Kunlik kvota birinchi: u XARAJATNI himoya qiladi. Mijoz quruq
        # qaytmaydi — savol menejerga ketadi.
        if not self.tezlik.kunlik_ruxsatmi(kim.id):
            await self._lid(kim, matn, sabab="kunlik so'rov chegarasi")
            return Javob(KUNLIK_CHEGARA, holat="chegara")
        if not self.tezlik.ruxsatmi(kim.id):
            return Javob(SEKINROQ, holat="chegara")

        oddiy = oddiy_javob(matn)
        if oddiy:
            await suhbat.tozala(self.baza, suhbat.ILOVA, kim.id)
            return Javob(oddiy)

        # Narx savoli — MODELSIZ, katalogdan (`bot/mijoz.py` dagidek).
        katalog = await self._katalog()
        if katalog and narx_soralyaptimi(matn, katalog):
            topilgan = narxni_top(katalog, matn, kurs=kurs_joriy())
            if topilgan is not None:
                await self._lid(
                    kim, matn,
                    javob=f"narx qidiruvi: {topilgan.holat} ({topilgan.model})",
                    sabab="" if topilgan.holat == "narx" else "narx topilmadi",
                )
                return Javob(
                    narx_matni(topilgan),
                    mahsulotlar=mahsulot_idlari([topilgan.model], katalog),
                )

        rad_sababi: list[str] = []

        async def rejani_kor(reja: Reja) -> str | None:
            qaror = rejani_tekshir(reja)
            if qaror.ruxsat:
                return None
            log.info("mijozga yopiq reja: id=%s sabab=%s", kim.id, qaror.sabab)
            rad_sababi.append(qaror.sabab)
            return qaror.sabab

        davom = await suhbat.boshla(self.baza, suhbat.ILOVA, kim.id, matn)
        try:
            natija = await self.orkestr().bajar(
                davom.sorov,
                kontekst={"mijoz_boti": True, "yangi_xabar": matn},
                reja_tekshiruvi=rejani_kor,
            )
        except Exception:
            log.exception("yordamchi so'rovi bajarilmadi")
            await self._lid(kim, matn, sabab="texnik xato")
            return Javob(XATO.format(telefon=self.telefon), holat="menejer")

        await suhbat.yakunla(self.baza, suhbat.ILOVA, kim.id, davom, natija)

        if rad_sababi or natija.yakuniy.holat.value in ("mos_agent_yoq", "xato"):
            await self._lid(
                kim, davom.sorov,
                sabab=rad_sababi[0] if rad_sababi else natija.yakuniy.holat.value,
            )
            return Javob(MENEJERGA.format(telefon=self.telefon), holat="menejer")

        matn_javob = mijoz_matni(natija)
        if natija.yakuniy.holat is Holat.ANIQLIK_KERAK:
            # Savol berilyapti — hali hisob yo'q, kartochka ham, izoh ham yo'q.
            return Javob(matn_javob, holat="savol")

        await self._lid(kim, davom.sorov, javob=matn_javob)
        return Javob(
            matn_javob + IZOH,
            mahsulotlar=mahsulot_idlari(_nomlar(natija.yakuniy.natija), katalog),
        )

    async def _katalog(self) -> list[dict[str, Any]]:
        """Katalog olinmasa bo'sh ro'yxat: narx qidiruvi va kartochkalar
        tushib qoladi, lekin yordamchi javob berishda davom etadi."""
        try:
            return await self.katalog()
        except Exception:
            log.warning("katalog olinmadi", exc_info=True)
            return []

    async def _lid(self, kim: Foydalanuvchi, savol: str, javob: str = "",
                   sabab: str = "") -> None:
        """Murojaatni bazaga yozadi va menejerlarga xabar beradi.

        HAR savol yuboriladi, javob berilgani ham — menejer mijoz bilan
        nima gaplashilganini bilishi kerak (`bot/mijoz.py::_lid`).
        """
        try:
            await self.baza.murojaat_yoz({
                "tg_id": f"ilova:{kim.id}",
                "ism": kim.ism,
                "aloqa": kim.telefon,
                "savol": savol,
                "javob": javob or None,
                "sabab": sabab or None,
            })
        except Exception:
            log.exception("murojaat yozilmadi")

        try:
            await self.menejerga(lid_xabari(kim, savol, javob, sabab))
        except Exception:
            log.warning("menejerga xabar ketmadi", exc_info=True)


def lid_xabari(kim: Foydalanuvchi, savol: str, javob: str, sabab: str) -> str:
    bosh = "🔔 Menejer kerak" if sabab else "💬 Ilovadan savol"
    qatorlar = [
        f"{bosh} · Climavent ilovasi",
        f"👤 {kim.ism or '—'}" + (f" · {kim.telefon}" if kim.telefon else ""),
        "",
        f"❓ {savol[:MENEJER_SAVOL]}",
    ]
    if javob:
        qisqa = javob[:MENEJER_JAVOB]
        if len(javob) > MENEJER_JAVOB:
            qisqa = qisqa.rsplit("\n", 1)[0] + "\n…"
        qatorlar += ["", f"🤖 Yordamchi javobi:\n{qisqa}"]
    if sabab:
        qatorlar += ["", f"⚠️ Sabab: {sabab}"]
    return "\n".join(qatorlar)
