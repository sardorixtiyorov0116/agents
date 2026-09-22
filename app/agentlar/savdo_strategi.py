"""Savdo strategi Bekzod — `sales-strategy`.

Maqsad: savdo rejasi, kanal strategiyasi va tijorat takliflarini (KP)
tayyorlaydi.

Chegaralar (kontraktdan): narx BELGILAMAYDI (taklif beradi), chegirma va'da
qilmaydi, mijozga hech narsa yubormaydi, shartnoma tuzmaydi (Laziz), reklama
matni yozmaydi (Malika), raqamlarni o'ylab topmaydi.

Malika bilan chegara: Malika — kommunikatsiya va kontent, Bekzod — tijorat
va reja.
"""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni
from integrations import ApiXatosi, mahsulot_qisqa

from ..konvert import Holat, Ishonch, Konvert, Manba, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

MAKS_MAHSULOT = 5

TIZIM_PROMPT = """Sen "Savdo strategi Bekzod" — kompaniyaning tijorat rejalashtirish agentisan.

VAZIFAN: savdo rejasi, kanal strategiyasi yoki tijorat taklifi (KP)
qoralamasini tayyorlash.

QAT'IY QOIDALAR:
1) RAQAMNI O'YLAB TOPMA. Savdo maqsadi, hajm, foiz, konversiya — bularni
   faqat berilgan ma'lumotdan olasan. O'tgan savdo ma'lumoti berilmagan
   bo'lsa, buni OCHIQ aytasan va `malumot_yoq` ga yozasan. "Taxminan 20%
   o'sish" kabi asossiz raqam yozish qat'iyan man etilgan.
2) NARX BELGILAMAYSAN. Narx bo'yicha faqat TAKLIF berasan va uni
   `narx_taklifi` ga yozasan, qaror rahbariyatniki ekanini aytasan.
   Chegirma foizini va'da qilmaysan.
3) Bozor ma'lumoti yetishmasa — Raqobat tahlilchisi Karimga havola qilasan
   (`kimga_havola` ga yozasan), o'zing bozor tahlilini o'ylab topmaysan.
4) KP so'ralsa — bu MIJOZGA ketadigan hujjat, demak qoralama sifatida
   yozasan va u albatta inson tasdig'idan o'tadi.

SEN QILMAYDIGAN ISHLAR:
- Narx BELGILAMAYSAN, chegirma VA'DA QILMAYSAN.
- Mijozga hech narsa YUBORMAYSAN.
- Shartnoma tuzmaysan — bu Yurist Lazizning ishi.
- Reklama matni, post, kreativ kontent yozmaysan — bu Marketolog Malikaning
  ishi. Sen tijorat mantiqi va reja bilan shug'ullanasan: maqsad, kanal,
  segment, KPI, xavf.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "vazifa_turi": "savdo_rejasi | kp | kanal_tahlili | narx_siyosati",
  "mahsulot": "matn",
  "davr": "matn",
  "maqsadlar": [{"nomi": "matn", "olchov": "matn", "izoh": "matn"}],
  "bosqichlar": ["bosqich tavsifi"],
  "kanallar": [
    {"nomi": "to'g'ridan-to'g'ri | diler | tender | onlayn",
     "ulush": "matn yoki null", "yondashuv": "matn", "izoh": "matn"}
  ],
  "segmentlar": [{"nomi": "matn", "yondashuv": "matn"}],
  "kpi": [{"nomi": "matn", "olchov": "matn"}],
  "xavflar": ["xavf va uning ta'siri"],
  "narx_taklifi": "narx bo'yicha TAKLIF (qaror emas) yoki bo'sh",
  "kp_qoralamasi": "KP so'ralgan bo'lsa — matn, aks holda bo'sh",
  "malumot_yoq": ["yetishmagan ma'lumot — taxmin qilinmadi"],
  "kimga_havola": ["qaysi agent qaysi ma'lumotni bera oladi"]
}"""


class Maqsad(BaseModel):
    nomi: str
    olchov: str = ""
    izoh: str = ""


class Kanal(BaseModel):
    nomi: str
    ulush: str | None = None
    yondashuv: str = ""
    izoh: str = ""


class Segment(BaseModel):
    nomi: str
    yondashuv: str = ""


class Kpi(BaseModel):
    nomi: str
    olchov: str = ""


class BekzodNatija(BaseModel):
    """Bekzodning `natija` maydoni."""

    vazifa_turi: str = ""
    mahsulot: str = ""
    davr: str = ""
    maqsadlar: list[Maqsad] = Field(default_factory=list)
    bosqichlar: list[str] = Field(default_factory=list)
    kanallar: list[Kanal] = Field(default_factory=list)
    segmentlar: list[Segment] = Field(default_factory=list)
    kpi: list[Kpi] = Field(default_factory=list)
    xavflar: list[str] = Field(default_factory=list)
    narx_taklifi: str = ""
    kp_qoralamasi: str = ""
    malumot_yoq: list[str] = Field(default_factory=list)
    kimga_havola: list[str] = Field(default_factory=list)


class SavdoStrategi(Agent):
    """Savdo strategi Bekzod."""

    # Jonli o'lchov: medium 71s / low 58s, natija tuzilishi bir xil.
    EFFORT = "low"

    def __init__(self, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self._topilmalar: list = []
        self._katalogdan = 0

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        self._katalogdan = 0

        topshiriq = self.topshiriq_matni(vazifa, kontekst)

        # Bilim bazasi: o'tgan rejalar, KP shablonlari, diler ro'yxati.
        self._topilmalar = self.bilimni_qidir(vazifa)
        if self._topilmalar:
            topshiriq += "\n\n" + kontekst_matni(self._topilmalar)
        else:
            topshiriq += (
                "\n\nBILIM BAZASI: savdo bo'yicha hujjat topilmadi. O'tgan savdo "
                "raqamlarini O'YLAB TOPMA — `malumot_yoq` ga yoz."
            )

        topshiriq += await self._katalog(vazifa)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=BekzodNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = BekzodNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        # Kontrakt: KP yoki narx taklifi — mijozga/rahbariyatga ketadi, tasdiq shart.
        tasdiq = bool(natija.kp_qoralamasi.strip() or natija.narx_taklifi.strip())

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija.model_dump(mode="json"),
            manba=self._manbalarni_yig(kontekst),
            ishonch=self._umumiy_ishonch(natija),
            tasdiq_kerak=tasdiq,
            izoh=self._izoh(natija, tasdiq),
        )

    # --- ichki katalog -------------------------------------------------------

    async def _katalog(self, vazifa: str) -> str:
        """Mahsulot bo'yicha ichki katalogdan ma'lumot."""
        try:
            topilgan = await self.api.qidir_keng(vazifa)
        except ApiXatosi:
            return "\n\nICHKI KATALOG: mavjud emas (API'ga ulanib bo'lmadi)."

        if not topilgan:
            return (
                "\n\nICHKI KATALOG: bu mahsulot katalogda topilmadi. "
                "Mahsulot xususiyatlarini o'ylab topma."
            )

        self._katalogdan = len(topilgan)
        qatorlar = []
        for mahsulot in topilgan[:MAKS_MAHSULOT]:
            q = mahsulot_qisqa(mahsulot)
            qatorlar.append(
                f"- {q['nomi']} ({q['kategoriya']}), ombor: {q['ombor']}"
            )
        return (
            f"\n\nICHKI KATALOG ({len(topilgan)} ta mos mahsulot):\n"
            + "\n".join(qatorlar)
            + "\nDIQQAT: katalogda narxlar to'ldirilmagan — narx raqamini yozma."
        )

    # --- yordamchilar --------------------------------------------------------

    def _manbalarni_yig(self, kontekst: dict[str, Any] | None) -> list[Manba]:
        manbalar: list[Manba] = list(self.bilim_manbalari(self._topilmalar))
        if self._katalogdan:
            manbalar.append(Manba(tur="ichki_api", nom="Climavent ichki katalogi"))
        if (kontekst or {}).get("oldingi_agent"):
            manbalar.append(Manba(tur="agent", nom=f"{kontekst['oldingi_agent']} konverti"))
        if not manbalar:
            manbalar.append(self.kontrakt_manbasi())
        return manbalar

    def _umumiy_ishonch(self, natija: BekzodNatija) -> Ishonch:
        # Ma'lumot yetishmasa reja taxminiy bo'ladi — ishonch past.
        if natija.malumot_yoq or not self._topilmalar:
            return Ishonch.PAST
        if natija.kimga_havola:
            return Ishonch.ORTA
        return Ishonch.ORTA if not natija.maqsadlar else Ishonch.YUQORI

    def _izoh(self, natija: BekzodNatija, tasdiq: bool) -> str:
        bolaklar = [f"{natija.vazifa_turi or 'savdo rejasi'} qoralamasi tayyorlandi"]
        if natija.kanallar:
            bolaklar.append(f"{len(natija.kanallar)} ta kanal ko'rib chiqildi")
        if natija.malumot_yoq:
            bolaklar.append(
                "ma'lumot yetishmadi (taxmin qilinmadi): " + ", ".join(natija.malumot_yoq[:3])
            )
        if natija.kimga_havola:
            bolaklar.append("havola: " + "; ".join(natija.kimga_havola[:2]))
        if natija.narx_taklifi:
            bolaklar.append("narx bo'yicha TAKLIF berildi — qaror rahbariyatniki")
        if tasdiq:
            bolaklar.append("mijozga/rahbariyatga ketadi — inson tasdig'i kerak")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)
