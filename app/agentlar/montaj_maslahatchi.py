"""Ventilyatsiya maslahatchisi Anvar — `montaj-guide`.

Maqsad: bilim bazasiga tayangan maslahat. Rustam havo sarfini
HISOBLAYDI, Temur KP tuzadi, Anvar esa TUSHUNTIRADI: qayerga
o'rnatiladi, nega havo yo'q, siklon qanday tanlanadi, VRF bilan
chillerning farqi nima.

Rol nomi kodda `montaj-guide` bo'lib qoldi (kontrakt fayli va
baza yozuvlari shunga bog'langan), lekin qamrovi kengaygan —
kontraktga qarang.

NEGA ALOHIDA AGENT
------------------
Bu ish hisobdan boshqacha va XAVFI boshqacha. Noto'g'ri hisob —
uskuna yetarli havo bermaydi. Noto'g'ri montaj maslahati esa
tushib ketgan uskuna yoki yong'in yo'liga aylanishi mumkin.
Shuning uchun chegaralari alohida va qattiqroq.

O'ZGARMAS QOIDALAR (kodda, promptda emas):
  - JAVOB BILIM BAZASIGA TAYANADI. Bazada topilmasa — model o'zidan
    to'qib chiqarmasin uchun javobga manba biriktiriladi va topilma
    bo'lmasa buni ochiq aytadi;
  - XAVFSIZLIK MAVZULARI kodda ushlanadi: ko'taruvchi konstruksiya,
    yong'in ventilyatsiyasi, dud chiqarish — bu savollarga javob
    o'rniga "mutaxassisga" deyiladi (`XAVFLI_MAVZU`);
  - normativ band raqami javobda qolmaydi — u tekshirilmagan bo'ladi
    (`_bandlarni_olib_tashla`).
"""

from __future__ import annotations

import re
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni

from ..konvert import (
    Holat,
    Ishonch,
    Konvert,
    Manba,
    aniqlik_kerak_konvert,
    xato_konvert,
)
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

MAKS_QADAM = 10
MAKS_TEKSHIRUV = 10

# Bu mavzular BIZNING ishimiz emas. Javob berish o'rniga kim
# qilishini aytamiz. Ro'yxat kontraktdagi chegaralardan olingan.
XAVFLI_MAVZU = {
    # "ko'tara oladimi", "ko'taruvchi konstruksiya", "og'irlikni ko'tar"
    # — hammasi bitta savol: bino bu og'irlikni ushlaydimi.
    "konstruksiya": re.compile(
        r"ko['`‘’]?tar\w*\s+ol\w*|"
        r"ko['`‘’]?tar\w*\s*(konstruksiya|qobiliyat)|"
        r"og['`‘’]?irlikni\s*ko['`‘’]?tar|"
        r"нес[уy]щ\w*|balka|ферм|перекрыти|"
        r"(tom|devor|shift|перекрыти\w*)\s+\w*\s*ko['`‘’]?tar",
        re.IGNORECASE,
    ),
    "yongin": re.compile(
        r"yong['`‘’]?in|дымоудал|противопожарн|пожарн|dud\s*chiqar|"
        r"olovni\s*to['`‘’]?s|огнезадерж",
        re.IGNORECASE,
    ),
    "elektr": re.compile(
        r"kabel\s*kesim|сечени\w*\s*кабел|elektr\s*sxema|"
        r"avtomat\s*nomina|щит\s*собра",
        re.IGNORECASE,
    ),
}

XAVFLI_JAVOB = {
    "konstruksiya": (
        "Uskuna og'irligini tom yoki devor ko'taradimi — buni "
        "KONSTRUKTOR hisoblaydi. Men uskunaning og'irligini ayta olaman, "
        "lekin binoning ko'tarish qobiliyati bo'yicha xulosa bera olmayman."
    ),
    "yongin": (
        "Yong'in ventilyatsiyasi, dud chiqarish va olovni to'suvchi "
        "klapanlar — LITSENZIYALI loyihachi ishi. Bu yerda taxmin "
        "qilib bo'lmaydi: xato yechim odam hayotiga tegishli."
    ),
    "elektr": (
        "Kabel kesimi va himoya nominali — ELEKTRIK ishi. Men ventilyatorga "
        "alohida uzgich va termik himoya kerakligini ayta olaman, "
        "lekin sxema va hisobni elektrik qiladi."
    ),
}

# Normativ band raqami — model uni tekshira olmaydi, ya'ni yozsa
# ishonchli ko'rinadigan tekshirilmagan da'vo bo'ladi.
BAND_RAQAMI = re.compile(
    r"\b(ShNQ|ШНК|QMQ|КМК|SNiP|СНиП|ГОСТ|GOST)\s*[\d.\-]+"
    r"(\s*(ning|dagi)?\s*[\d.]+\s*-?\s*band\w*)?",
    re.IGNORECASE,
)

TIZIM_PROMPT = """Sen "Ventilyatsiya bo'yicha maslahatchi Anvar"san.

VAZIFANG — ikki turdagi savolga amaliy javob berish:
  1) MONTAJ: uskunani qayerga va qanday o'rnatish, ishga tushirish,
     nosozlik sababini topish;
  2) SOHA SAVOLLARI: aspiratsiya va siklon, qozon tortishma
     mashinalari, sovutish va namlik, konditsionerlash (split, VRF,
     chiller), baktericid ishlov, shovqin, havo taqsimlash,
     avtomatika, o'lchov-sozlash, maxsus obyektlar.

Ikkinchi turda HISOB QILMAYSAN — tanlash mantig'ini tushuntirasan
va qanday ma'lumot kerakligini aytasan.

O'ZINGNI "montaj maslahatchisi" deb atamaysan — sen ventilyatsiya
bo'yicha maslahatchisan.

QOIDALAR:
1) BERILGAN BILIMGA TAYAN. "MONTAJ BILIMI" bo'limidan foydalanasan.
   U yerda javob bo'lmasa — o'zingdan to'qimaysan, `bazada_yoq` ga
   yozasan.
2) NORMATIV BAND RAQAMINI YOZMAYSAN. "ShNQ 2.04.05 ning 4.7-bandi"
   — YO'Q. Buning o'rniga: "amaldagi ShNQ bilan solishtiring".
3) OBYEKTNI KO'RMAGANSAN. Aniq masofa va mahkamlash nuqtasini joyida
   muhandis belgilaydi — buni `joyida_aniqlanadi` ga yozasan.
4) XAVFSIZLIKDA TAXMIN QILMAYSAN. Bilmasang "mutaxassis ko'rishi
   kerak" deysan.
5) SABABNI TARTIB BILAN BER. Muammo so'ralsa, ehtimoliy sabablarni
   TEKSHIRISH OSONLIGI bo'yicha tartibla: avval bir daqiqada
   tekshiriladigani, keyin og'iri.
6) QISQA VA AMALIY. Har qadam — bajariladigan ish, umumiy gap emas.

QILMAYSAN: havo sarfi hisobi (Rustam), narx va smeta (Temur),
ko'taruvchi konstruksiya hisobi, yong'in ventilyatsiyasi loyihasi,
elektr sxemasi.

DIQQAT: qozon DUD SO'RGICHI (дымосос, Д/ДН) — oddiy qozon uskunasi,
u haqida gapirasan. YONG'IN dud chiqarishi (дымоудаление) esa
boshqa narsa — u haqida gapirmaysan.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "vaziyat": "savolni o'z so'zing bilan bir gapda",
  "qadamlar": [
    {"nima": "bajariladigan ish", "nega": "sababi qisqa"}
  ],
  "tekshiruv": ["ishga tushirishdan oldin tekshiriladigan narsa"],
  "sabablar": [
    {"sabab": "ehtimoliy sabab", "qanday_tekshirish": "qanday aniqlanadi"}
  ],
  "joyida_aniqlanadi": ["obyektni ko'rmasdan aytib bo'lmaydigan narsa"],
  "sorash_kerak": ["javob berish uchun yetishmayotgan ma'lumot"],
  "bazada_yoq": ["bilim bazasida topilmagan, muhandisdan so'rash kerak"]
}"""


class Qadam(BaseModel):
    nima: str
    nega: str = ""


class Sabab(BaseModel):
    sabab: str
    qanday_tekshirish: str = ""


class AnvarNatija(BaseModel):
    vaziyat: str = ""
    qadamlar: list[Qadam] = Field(default_factory=list)
    tekshiruv: list[str] = Field(default_factory=list)
    sabablar: list[Sabab] = Field(default_factory=list)
    joyida_aniqlanadi: list[str] = Field(default_factory=list)
    sorash_kerak: list[str] = Field(default_factory=list)
    bazada_yoq: list[str] = Field(default_factory=list)


def xavfli_mavzu(matn: str) -> str | None:
    """Savol bizning chegaramizdan tashqaridami (topilmasa None)."""
    for nomi, andoza in XAVFLI_MAVZU.items():
        if andoza.search(matn or ""):
            return nomi
    return None


def bandlarni_olib_tashla(matn: str) -> str:
    """Normativ band raqamini olib tashlaydi.

    Model uni tekshira olmaydi — yozsa, tekshirilmagan da'vo
    ishonchli ko'rinishda chiqadi. Shuning uchun KODDA olinadi,
    promptga tayanmaymiz.
    """
    tozalangan = BAND_RAQAMI.sub("amaldagi normativ hujjat", matn or "")
    return re.sub(r"\s{2,}", " ", tozalangan).strip()


class MontajMaslahatchi(Agent):
    """Montaj bo'yicha maslahatchi Anvar."""

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        savol = (vazifa or "").strip()
        if not savol:
            return aniqlik_kerak_konvert(
                ["Qanday obyekt va qaysi uskuna haqida gap ketyapti?"],
                "Montaj savoli tushunarli emas.",
                kim=self.rol,
            )

        # XAVFSIZLIK CHEGARASI — modelgacha. Bu savolga javob
        # bermaymiz, kim qilishini aytamiz.
        mavzu = xavfli_mavzu(savol)
        if mavzu is not None:
            return Konvert(
                kim=self.rol,
                holat=Holat.TUGADI,
                natija={
                    "vaziyat": savol[:200],
                    "chegaradan_tashqari": XAVFLI_JAVOB[mavzu],
                    "qadamlar": [],
                },
                manba=[self.kontrakt_manbasi()],
                ishonch=Ishonch.YUQORI,
                izoh=XAVFLI_JAVOB[mavzu],
            )

        topilmalar = self.bilimni_qidir(savol)
        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        if topilmalar:
            topshiriq += "\n\nMONTAJ BILIMI:\n" + kontekst_matni(topilmalar)
        else:
            topshiriq += (
                "\n\nMONTAJ BILIMI: bu savol bo'yicha bazada hujjat "
                "topilmadi. Umumiy amaliyotdan chiqib javob bersang ham, "
                "har bandni `bazada_yoq` ga ham yozib qo'y — muhandis "
                "tekshirishi kerak."
            )

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=AnvarNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = AnvarNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        return self._yakunla(natija, topilmalar)

    def _yakunla(self, natija: AnvarNatija, topilmalar: list) -> Konvert:
        if not natija.qadamlar and not natija.sabablar and natija.sorash_kerak:
            return aniqlik_kerak_konvert(
                natija.sorash_kerak,
                "Montaj maslahati uchun ma'lumot yetishmayapti.",
                kim=self.rol,
            )

        tozala = bandlarni_olib_tashla
        malumot: dict[str, Any] = {
            "vaziyat": tozala(natija.vaziyat),
            "qadamlar": [
                {"nima": tozala(q.nima), "nega": tozala(q.nega)}
                for q in natija.qadamlar[:MAKS_QADAM]
            ],
            "tekshiruv": [tozala(t) for t in natija.tekshiruv[:MAKS_TEKSHIRUV]],
            "sabablar": [
                {"sabab": tozala(s.sabab),
                 "qanday_tekshirish": tozala(s.qanday_tekshirish)}
                for s in natija.sabablar[:MAKS_QADAM]
            ],
            "joyida_aniqlanadi": [tozala(x) for x in natija.joyida_aniqlanadi],
            "sorash_kerak": natija.sorash_kerak,
            "bazada_yoq": natija.bazada_yoq,
        }

        manbalar = [self.kontrakt_manbasi()]
        for topilma in topilmalar[:3]:
            manbalar.append(
                Manba(tur="hujjat", nom=getattr(topilma, "sarlavha", "montaj bilimi"))
            )

        # Bazada topilmasa ishonch past: javob umumiy amaliyotdan,
        # kompaniya hujjatidan emas.
        ishonch = Ishonch.YUQORI if topilmalar else Ishonch.ORTA
        if natija.bazada_yoq:
            ishonch = Ishonch.ORTA

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=malumot,
            manba=manbalar,
            ishonch=ishonch,
            izoh=self._izoh(natija, bool(topilmalar)),
        )

    @staticmethod
    def _izoh(natija: AnvarNatija, bilim_bormi: bool) -> str:
        bolaklar = []
        if natija.qadamlar:
            bolaklar.append(f"{len(natija.qadamlar)} ta qadam")
        if natija.sabablar:
            bolaklar.append(f"{len(natija.sabablar)} ta ehtimoliy sabab")
        if not bilim_bormi:
            bolaklar.append("bazada hujjat topilmadi — umumiy amaliyot")
        if natija.joyida_aniqlanadi:
            bolaklar.append("bir qismi joyida aniqlanadi")
        return ", ".join(bolaklar) or "montaj maslahati"
