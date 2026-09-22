"""Yurist Laziz — `legal-review`.

Maqsad: shartnoma va huquqiy hujjatlarni tahlil qiladi, xavflarni xavf
darajasi bo'yicha ajratib belgilaydi va tuzatish takliflari beradi.

Chegaralar (kontraktdan): hujjatni imzolamaydi/yubormaydi, yakuniy huquqiy
kafolat bermaydi, advokat o'rnini bosmaydi, faqat tayyorlaydi — qaror inson
zimmasida.

Kontrakt: "HAR DOIM — har qanday yakuniy hujjat inson tasdig'isiz chiqmaydi".
"""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni

from ..konvert import Holat, Ishonch, Konvert, Manba, Xavf, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig, veb_manbalar
from .asos import Agent

TIZIM_PROMPT = """Sen "Yurist Laziz" — kompaniyaning huquqiy tahlil agentisan.

VAZIFAN: berilgan hujjatni (shartnoma, kelishuv) tahlil qilib, xavfli
bandlarni xavf darajasi bo'yicha ajratib ko'rsatish va tuzatish taklif qilish.
Yurisdiksiya: O'zbekiston qonunchiligi (boshqasi aytilmasa).

BILIM BAZASI (eng muhim qoida):
Senga "BILIM BAZASIDAN TOPILDI" bo'limida qonun matnlari beriladi. Har
huquqiy xulosang AYNAN SHU matnlarga asoslanishi va `manba_nomi` da qaysi
hujjat/modda ekani ko'rsatilishi SHART.
- Bazada javob bo'lmasa — "bu masala bo'yicha bazada manba yo'q, yurist bilan
  maslahatlashing" deb yozasan va `manba_yoq: true` qo'yasan.
- XOTIRANGDAN qonun moddasi raqamini YOZMAYSAN. Faqat berilgan matndagi
  modda raqamini ishlatasan.
- Baza parchasi eskirgan deb belgilangan bo'lsa — buni javobda aytasan.

QAT'IY QOIDALAR:
1) TAXMIN QILMAYSAN. Qonun bandi yoki shartnoma sharti noaniq bo'lsa — o'zingcha
   talqin qilmaysan. Bunday joyni `aniqlik_kerak` ro'yxatiga yozasan va nima
   aniqlanishi kerakligini aytasan.
2) HUJJAT TO'LIQ BO'LMASA — yetishmagan qismni `yetishmagan_qismlar` ga yozasan
   va shu holatda to'liq xulosa berib bo'lmasligini ochiq aytasan.
3) Har qaydni xavf darajasi bilan belgila: `yuqori` (jiddiy huquqiy yoki moliyaviy
   xavf), `orta` (e'tibor talab qiladi), `past` (kichik/tahririy).
4) Har qayd uchun: qaysi band, nima xavf, qanday tuzatish taklif qilinadi.
5) Qonun normasiga havola qilsang — aniq manbani ko'rsat. Manbasiz norma
   raqamini YOZMAYSAN.

SEN QILMAYDIGAN ISHLAR:
- Hujjatni IMZOLAMAYSAN va YUBORMAYSAN. Sen faqat tahlil va qoralama berasan.
- Asl hujjatni o'zgartirmaysan — tuzatishni alohida taklif sifatida yozasan.
- Yakuniy huquqiy KAFOLAT bermaysan ("bu shartnoma butunlay xavfsiz" kabi
  xulosa yozmaysan).
- Litsenziyalangan advokat o'rnini bosmaysan — jiddiy holatda buni aytasan.

Natijang HAR DOIM inson tasdig'idan o'tadi.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "hujjat_turi": "matn",
  "yurisdiksiya": "matn",
  "qaydlar": [
    {
      "band": "band raqami yoki nomi",
      "xavf": "yuqori | orta | past",
      "izoh": "nima xavf",
      "tuzatish_taklifi": "qanday tuzatish",
      "manba_nomi": "norma manbasi yoki null",
      "havola": "URL yoki null"
    }
  ],
  "xulosa": "umumiy xulosa (kafolat emas)",
  "aniqlik_kerak": ["noaniq band va nima aniqlanishi kerak"],
  "yetishmagan_qismlar": ["hujjatning yetishmagan qismi"],
  "manba_yoq": true/false
}"""


class HuquqiyQayd(BaseModel):
    """Bitta band bo'yicha huquqiy qayd."""

    band: str = ""
    xavf: Xavf = Xavf.ORTA
    izoh: str = ""
    tuzatish_taklifi: str = ""
    manba_nomi: str | None = None
    havola: str | None = None


class LazizNatija(BaseModel):
    """Lazizning `natija` maydoni."""

    hujjat_turi: str = ""
    yurisdiksiya: str = ""
    qaydlar: list[HuquqiyQayd] = Field(default_factory=list)
    xulosa: str = ""
    aniqlik_kerak: list[str] = Field(default_factory=list)
    yetishmagan_qismlar: list[str] = Field(default_factory=list)
    # Bilim bazasida tegishli manba topilmadi.
    manba_yoq: bool = False


class Yurist(Agent):
    """Yurist Laziz."""

    # Xavfli bandni TOPISH — bu naqsh tanish ishi, uzoq o'ylash emas.
    # Jonli o'lchov: medium 50s, low 28s, topilgan qayd IKKALASIDA ham
    # bir xil (o'sha yuqori xavfli band).
    EFFORT = "low"

    def __init__(self, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self._topilmalar: list = []

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""

        # Bilim bazasidan qonun matnlarini qidiramiz — xulosa shunga asoslanadi.
        self._topilmalar = self.bilimni_qidir(vazifa)
        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        if self._topilmalar:
            topshiriq += "\n\n" + kontekst_matni(self._topilmalar)
        else:
            topshiriq += (
                "\n\nBILIM BAZASI: bu masala bo'yicha bazada hujjat TOPILMADI. "
                "Qonun moddasini xotirangdan yozma — `manba_yoq: true` qo'y va "
                "yurist bilan maslahatlashish kerakligini ayt."
            )

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=LazizNatija,
                json_skelet=JSON_SKELET,
                # Ruxsat: qonunchilik manbalarini o'qish.
                veb_qidiruv=True,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = LazizNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija.model_dump(mode="json"),
            manba=self._manbalarni_yig(javob, natija, kontekst),
            ishonch=self._umumiy_ishonch(natija),
            # Kontrakt: HAR DOIM inson tasdig'i.
            tasdiq_kerak=True,
            izoh=self._izoh(natija),
        )

    def _manbalarni_yig(
        self, javob: Any, natija: LazizNatija, kontekst: dict[str, Any] | None
    ) -> list[Manba]:
        manbalar: list[Manba] = list(self.bilim_manbalari(self._topilmalar))
        korilgan: set[str] = {m.nom for m in manbalar}

        for qayd in natija.qaydlar:
            kalit = qayd.havola or qayd.manba_nomi or ""
            if not kalit or kalit in korilgan:
                continue
            korilgan.add(kalit)
            manbalar.append(
                Manba(tur="hujjat", nom=qayd.manba_nomi or kalit, havola=qayd.havola)
            )

        for veb in veb_manbalar(javob):
            if "xato" in veb:
                manbalar.append(Manba(tur="veb", nom=f"qidiruv xatosi: {veb['xato']}"))
                continue
            kalit = veb.get("havola") or veb.get("nom") or ""
            if not kalit or kalit in korilgan:
                continue
            korilgan.add(kalit)
            manbalar.append(
                Manba(tur="veb", nom=veb.get("nom") or kalit, havola=veb.get("havola"))
            )

        # Tahlil qilingan hujjatning o'zi ham manba.
        if (kontekst or {}).get("oldingi_agent"):
            manbalar.append(Manba(tur="agent", nom=f"{kontekst['oldingi_agent']} konverti"))
        if not manbalar:
            manbalar.append(Manba(tur="hujjat", nom="so'rovda berilgan hujjat matni"))
        return manbalar

    def _umumiy_ishonch(self, natija: LazizNatija) -> Ishonch:
        # Bilim bazasida manba topilmagan bo'lsa — ishonch past bo'lishi shart.
        if natija.manba_yoq or not self._topilmalar:
            return Ishonch.PAST
        # Hujjat to'liq bo'lmasa yoki noaniq band bo'lsa — ishonch past.
        if natija.yetishmagan_qismlar or not natija.qaydlar:
            return Ishonch.PAST
        if natija.aniqlik_kerak:
            return Ishonch.ORTA
        return Ishonch.YUQORI

    def _izoh(self, natija: LazizNatija) -> str:
        sanoq = {daraja: 0 for daraja in ("yuqori", "orta", "past")}
        for qayd in natija.qaydlar:
            sanoq[qayd.xavf.value] += 1

        bolaklar = [
            f"{len(natija.qaydlar)} ta qayd "
            f"(yuqori: {sanoq['yuqori']}, o'rta: {sanoq['orta']}, past: {sanoq['past']})"
        ]
        if natija.manba_yoq or not self._topilmalar:
            bolaklar.append(
                "DIQQAT: bilim bazasida bu masala bo'yicha qonun manbasi topilmadi — "
                "yurist bilan maslahatlashing"
            )
        else:
            bolaklar.append(f"{len(self._topilmalar)} ta qonun parchasiga asoslandi")
        if sanoq["yuqori"]:
            bolaklar.append(f"DIQQAT: {sanoq['yuqori']} ta yuqori xavfli band topildi")
        if natija.aniqlik_kerak:
            bolaklar.append(f"{len(natija.aniqlik_kerak)} ta noaniq band — taxmin qilinmadi")
        if natija.yetishmagan_qismlar:
            bolaklar.append("hujjat to'liq emas: " + ", ".join(natija.yetishmagan_qismlar))
        bolaklar.append("HUQUQIY KAFOLAT EMAS — inson tasdig'i kerak")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)
