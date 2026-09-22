"""HR menejeri Hilola — `hr-assist`.

Maqsad: ish e'lonlari, nomzodlarni saralash va HR hujjatlari qoralamasini
tayyorlashda yordam beradi.

Chegaralar (kontraktdan): ishga olish/bo'shatish qarorini chiqarmaydi,
nomzodni yakuniy rad etmaydi, kamsituvchi mezon ishlatmaydi, xodimga
to'g'ridan-to'g'ri xabar yubormaydi.

Ikki qatlamli himoya:
  1) Xodim ma'lumoti `baza.xodimlar()` orqali olinadi — u FAQAT ruxsat
     etilgan ustunlarni o'qiydi, `maosh` va `telefon` promptga umuman
     tushmaydi (cheklov kodda, promptda emas).
  2) Kamsituvchi mezonlar tizim promptida taqiqlangan, ustiga so'rov matni
     kod tomonidan tekshiriladi va ogohlantirish qo'shiladi.
"""

from __future__ import annotations

import re
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni

from ..konvert import Holat, Ishonch, Konvert, Manba, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

# Kamsituvchi mezonlar — mezon sifatida ishlatilishi mumkin bo'lgan so'zlar.
KAMSITUVCHI = {
    "yosh": r"\byosh(i|dagi|lar|gacha|dan)?\b",
    "jins": r"\bjins(i|iga)?\b|\bayol\b|\berkak\b|\bqiz\b|\byigit\b",
    "millat": r"\bmillat(i|iga)?\b|\birq(i)?\b",
    "din": r"\bdin(i|iy)?\b",
    "oilaviy holat": r"\boilaviy\b|\bturmush qurgan\b|\bbo'ydoq\b|\bfarzand(i|li)?\b",
}

TIZIM_PROMPT = """Sen "HR menejeri Hilola" — kompaniyaning HR yordamchi agentisan.

VAZIFAN: ish e'loni, nomzodlar solishtirmasi yoki HR hujjati QORALAMASINI
tayyorlash.

BILIM BAZASI:
Senga "BILIM BAZASIDAN TOPILDI" bo'limida Mehnat kodeksi va ichki qoidalar
parchalari beriladi. Huquqiy yoki tartibga oid har javobing SHU matnlarga
asoslanadi va `manba_nomi` da qaysi hujjat/modda ekani ko'rsatiladi.
- Bazada javob bo'lmasa — "bu masala bo'yicha bazada manba yo'q, HR mas'uliga
  murojaat qiling" deb aytasan. Modda raqamini XOTIRANGDAN yozmaysan.
- Lavozim tavsifi, ish e'loni, shartnoma shablonlari bazada bo'lsa —
  o'shalarga tayanasan, o'zingdan yangi shakl to'qimaysan.

QAT'IY QOIDALAR:
1) KAMSITUVCHI MEZON ISHLATMAYSAN. Yosh, jins, millat, irq, din, oilaviy
   holat, farzandlar soni, tashqi ko'rinish — bular mezon bo'la olmaydi.
   So'rovda shunday mezon bo'lsa, uni ISHLATMAYSAN, o'rniga ish bilan bog'liq
   mezon taklif qilasan va buni `rad_etilgan_mezonlar` ga yozasan.
   Faqat ish talablariga bog'liq mezonlar: tajriba, ko'nikma, ma'lumot,
   sertifikat, til bilish darajasi, natijalar.
2) YAKUNIY QAROR CHIQARMAYSAN. "Ishga olish kerak", "bu nomzod rad etilsin"
   — bunday xulosa yozmaysan. Sen mezonlar bo'yicha solishtirasan, qaror
   insonda qoladi. `tavsiya` maydoni faqat kuzatuv bo'ladi, hukm emas.
3) MA'LUMOTNI O'YLAB TOPMAYSAN. Nomzod yoki xodim haqida berilmagan
   ma'lumotni taxmin qilmaysan — `sorash_kerak` ga yozasan.
4) Siyosat noaniq bo'lsa — HR mas'uliga yo'naltirasan.

SEN QILMAYDIGAN ISHLAR:
- Ishga olish yoki bo'shatish qarorini chiqarmaysan.
- Nomzodni yakuniy rad etmaysan.
- Xodimga to'g'ridan-to'g'ri xabar YUBORMAYSAN — faqat qoralama tayyorlaysan.
- Maosh va shaxsiy kontakt ma'lumoti bilan ishlamaysan (ular senga
  berilmaydi ham).

Natijang HAR DOIM inson tasdig'idan o'tadi — buni yodda tut va qoralama
sifatida yoz.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "vazifa_turi": "e'lon | saralash | hujjat",
  "qoralama": "tayyorlangan matn",
  "mezonlar": [
    {"nomi": "masalan Python tajribasi", "izoh": "nima uchun muhim"}
  ],
  "solishtirma": [
    {"nomzod": "matn", "moslik": "yuqori | orta | past", "izoh": "mezonlar bo'yicha"}
  ],
  "rad_etilgan_mezonlar": ["ishlatilmagan kamsituvchi mezon va sababi"],
  "sorash_kerak": ["yetishmayotgan ma'lumot"],
  "tavsiya": "kuzatuv (yakuniy qaror EMAS)"
}"""


class Mezon(BaseModel):
    nomi: str
    izoh: str = ""


class NomzodBaho(BaseModel):
    nomzod: str
    moslik: str = ""
    izoh: str = ""


class HilolaNatija(BaseModel):
    """Hilolaning `natija` maydoni."""

    vazifa_turi: str = ""
    qoralama: str = ""
    mezonlar: list[Mezon] = Field(default_factory=list)
    solishtirma: list[NomzodBaho] = Field(default_factory=list)
    rad_etilgan_mezonlar: list[str] = Field(default_factory=list)
    sorash_kerak: list[str] = Field(default_factory=list)
    tavsiya: str = ""


class HrMenejeri(Agent):
    """HR menejeri Hilola."""

    def __init__(self, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self._topilmalar: list = []
        self._xodim_ishlatildi = False

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        kontekst = kontekst or {}

        topilgan_mezonlar = self._kamsituvchi_mezonlar(vazifa)
        topshiriq = self.topshiriq_matni(vazifa, kontekst)

        # Mehnat kodeksi va ichki qoidalar — bilim bazasidan.
        self._topilmalar = self.bilimni_qidir(vazifa)
        if self._topilmalar:
            topshiriq += "\n\n" + kontekst_matni(self._topilmalar)
        else:
            topshiriq += (
                "\n\nBILIM BAZASI: bu masala bo'yicha bazada hujjat topilmadi. "
                "Modda raqamini xotirangdan yozma — HR mas'uliga yo'naltir."
            )

        self._xodim_ishlatildi = bool(kontekst.get("xodimlar_kerak"))
        if self._xodim_ishlatildi:
            xodimlar = await self.baza.xodimlar(kontekst.get("bolim"))
            topshiriq += f"\n\nXodimlar (faqat ruxsat etilgan maydonlar):\n{xodimlar}"

        if topilgan_mezonlar:
            topshiriq += (
                "\n\nDIQQAT: so'rovda kamsituvchi bo'lishi mumkin bo'lgan mezon bor "
                f"({', '.join(topilgan_mezonlar)}). Uni ISHLATMA — o'rniga ish bilan "
                "bog'liq mezon taklif qil va rad_etilgan_mezonlar ga yoz."
            )

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=HilolaNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = HilolaNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        tana = natija.model_dump(mode="json")
        # Xodimlar jadvali hali namunaviy — javobda OCHIQ aytiladi.
        ogoh = self.demo_ogohi() if self._xodim_ishlatildi else ""
        if ogoh:
            tana["demo_ogohi"] = ogoh

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=tana,
            manba=self._manbalarni_yig(kontekst),
            ishonch=Ishonch.PAST if natija.sorash_kerak else Ishonch.ORTA,
            # Yuqori xavfli agent: natija inson tasdig'isiz chiqmaydi.
            tasdiq_kerak=True,
            izoh=self._izoh(natija, topilgan_mezonlar),
        )

    @staticmethod
    def _kamsituvchi_mezonlar(vazifa: str) -> list[str]:
        """So'rovda kamsituvchi mezon bor-yo'qligini kod darajasida tekshiradi."""
        return [
            nomi
            for nomi, andoza in KAMSITUVCHI.items()
            if re.search(andoza, vazifa, re.IGNORECASE)
        ]

    def _manbalarni_yig(self, kontekst: dict[str, Any]) -> list[Manba]:
        # Bilim bazasi manbalari birinchi — javob shularga asoslangan.
        manbalar = list(self.bilim_manbalari(self._topilmalar)) or [self.kontrakt_manbasi()]
        if kontekst.get("xodimlar_kerak"):
            manbalar.append(
                Manba(tur="baza", nom="HR bazasi — cheklangan o'qish (maoshsiz, kontaktsiz)")
            )
        if kontekst.get("oldingi_agent"):
            manbalar.append(Manba(tur="agent", nom=f"{kontekst['oldingi_agent']} konverti"))
        return manbalar

    def _izoh(self, natija: HilolaNatija, kamsituvchi: list[str]) -> str:
        bolaklar = [f"{natija.vazifa_turi or 'HR vazifasi'} qoralamasi tayyorlandi"]
        if self._topilmalar:
            bolaklar.append(f"{len(self._topilmalar)} ta hujjat parchasiga asoslandi")
        else:
            bolaklar.append("bilim bazasida manba topilmadi — HR mas'uliga murojaat qiling")
        if natija.solishtirma:
            bolaklar.append(f"{len(natija.solishtirma)} ta nomzod solishtirildi")
        if kamsituvchi:
            bolaklar.append(
                "so'rovda kamsituvchi mezon aniqlandi va ishlatilmadi: " + ", ".join(kamsituvchi)
            )
        if natija.rad_etilgan_mezonlar:
            bolaklar.append(f"{len(natija.rad_etilgan_mezonlar)} ta mezon rad etildi")
        if natija.sorash_kerak:
            bolaklar.append("ma'lumot yetishmaydi: " + ", ".join(natija.sorash_kerak))
        bolaklar.append("YAKUNIY QAROR EMAS — inson tasdig'i kerak")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)
