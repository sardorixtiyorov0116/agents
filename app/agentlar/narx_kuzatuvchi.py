"""Narx analitigi Zara — `price-monitor`.

Maqsad: berilgan mahsulotlarning joriy bozor narxlarini ishonchli manbalardan
topib, kuzatib boradi va strukturalangan holda qaytaradi.

Chegaralar (kontraktdan): sotib olish/sotish qarorini chiqarmaydi, chegirma
muzokarasi qilmaydi, raqib tahlili qilmaydi. Faqat kuzatadi va xabar beradi.
"""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from integrations import ApiXatosi, mahsulot_qisqa, narx_bormi

from ..konvert import Holat, Ishonch, Konvert, Manba, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig, veb_manbalar
from .asos import Agent

# Narxning keskin o'zgarishi chegarasi (kontrakt: >20% — e'tiborga havola).
KESKIN_OZGARISH = 0.20

TIZIM_PROMPT = """Sen "Narx analitigi Zara" — kompaniyaning narx kuzatuvchi agentisan.

VAZIFAN: so'ralgan mahsulotlarning joriy bozor narxini ishonchli manbalardan
topib, strukturalangan holda qaytarish.

ICHKI NARX HOLATI (juda muhim):
Kompaniyaning o'z tizimida mahsulot narxlari HOZIRCHA TO'LDIRILMAGAN.
Topshiriqda "ICHKI NARX" bo'limi bo'lsa, aynan shunga tayan.
- Ichki narx yo'q bo'lsa — buni OCHIQ ayt: "ichki narx ma'lumoti mavjud emas".
- Tashqi bozordan topilgan narxni HECH QACHON kompaniyaning o'z narxi
  sifatida ko'rsatma. Har bunday yozuvda `tashqi_bozor: true` qo'y va
  izohda bu raqib/bozor narxi ekanini ayt.
- Ichki tizimda `narx = 0` bo'lsa, bu "bepul" emas — "narx kiritilmagan"
  degani. Uni narx sifatida yozma.

QAT'IY QOIDALAR:
1) NARXNI O'YLAB TOPMA. Manbadan topmagan narxni yozmaysan — mahsulotni
   `topilmaganlar` ro'yxatiga qo'shasan va `narx` maydonini bo'sh (null)
   qoldirasan. To'qib chiqarish qat'iyan man etilgan.
2) Har narx uchun manba nomi va havolani ko'rsat. Havolasi yo'q narx — ishonchsiz.
3) Manbalar zid bo'lsa — ikkalasini ham alohida yozuv sifatida ko'rsat va
   `ziddiyatlar` ro'yxatida tushuntir.
4) Manba ishonchsiz bo'lsa (e'lon sayti, forum, sanasi yo'q sahifa) —
   `manba_ishonchsiz: true` qilib belgila va ishonchni pasaytir.
5) Har yozuv uchun sanani ko'rsat (narx qachonlik). Sana topilmasa — bo'sh qoldir
   va ishonchni pasaytir.
6) Valyutani so'ralganidek ber. Kursni o'zingdan o'ylab konvertatsiya qilma —
   manbada ko'rsatilgan valyutani yozib, `izoh`da ayt.

SEN QILMAYDIGAN ISHLAR:
- Sotib olish yoki sotish bo'yicha qaror/tavsiya bermaysan.
- Chegirma muzokarasi qilmaysan.
- Raqobatchilarni tahlil qilmaysan (bu Raqobat tahlilchisi Karimning ishi).
- Mahsulotning texnik xususiyatlarini bermaysan (bu Mahsulot mutaxassisi Sardorning ishi).
Faqat kuzatasan va xabar berasan.

QIDIRUV: `web_search` vositasidan foydalanib joriy narxlarni top. Hududni va
valyutani so'rovga qarab hisobga ol. Rasmiy sotuvchi saytlari va yirik
marketpleyslarga ustunlik ber.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

# Structured output ishlamay qolsa (masalan API `format`ni rad etsa) — shu
# skeletni promptga qo'shib, matn rejimida JSON so'raymiz.
JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "bozor": "matn",
  "valyuta": "matn",
  "yozuvlar": [
    {
      "mahsulot": "matn",
      "narx": 0 yoki null,
      "valyuta": "matn yoki null",
      "sana": "YYYY-MM-DD yoki null",
      "manba_nomi": "matn yoki null",
      "havola": "URL yoki null",
      "ishonch": "yuqori | orta | past",
      "manba_ishonchsiz": true/false,
      "tashqi_bozor": true/false,
      "izoh": "matn"
    }
  ],
  "topilmaganlar": ["mahsulot nomi"],
  "ziddiyatlar": ["izoh"],
  "diqqat": ["izoh"],
  "ichki_narx_holati": "ichki tizimdagi narx haqida ochiq javob"
}"""


class NarxYozuvi(BaseModel):
    """Bitta mahsulot uchun bitta manbadagi narx."""

    mahsulot: str
    narx: float | None = None
    valyuta: str | None = None
    sana: str | None = None
    manba_nomi: str | None = None
    havola: str | None = None
    ishonch: Ishonch = Ishonch.ORTA
    manba_ishonchsiz: bool = False
    # Tashqi bozor/raqib narxi — kompaniyaning o'z narxi EMAS.
    tashqi_bozor: bool = True
    izoh: str = ""


class ZaraNatija(BaseModel):
    """Zaraning `natija` maydoni."""

    bozor: str = ""
    valyuta: str = ""
    yozuvlar: list[NarxYozuvi] = Field(default_factory=list)
    topilmaganlar: list[str] = Field(default_factory=list)
    ziddiyatlar: list[str] = Field(default_factory=list)
    diqqat: list[str] = Field(default_factory=list)
    # Ichki tizimda narx bor-yo'qligi haqidagi ochiq javob.
    ichki_narx_holati: str = ""


ISHONCH_TARTIBI = {Ishonch.PAST: 0, Ishonch.ORTA: 1, Ishonch.YUQORI: 2}


class NarxKuzatuvchi(Agent):
    """Narx analitigi Zara."""

    def __init__(self, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self._ichki_xabar = ""

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        self._ichki_xabar = ""

        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += await self._ichki_narx(vazifa)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=ZaraNatija,
                json_skelet=JSON_SKELET,
                veb_qidiruv=True,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = ZaraNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        diqqat = await self._tarixni_yangila(natija)
        natija.diqqat.extend(diqqat)

        manbalar = self._manbalarni_yig(javob, natija)
        ishonch = self._umumiy_ishonch(natija)
        izoh = self._izoh(natija)

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija.model_dump(mode="json"),
            manba=manbalar,
            ishonch=ishonch,
            # Kontrakt: odatda tasdiq kerak emas — Zara faqat e'tiborga havola qiladi.
            tasdiq_kerak=False,
            izoh=izoh,
        )

    # --- ichki narx (birlamchi manba) ----------------------------------------

    async def _ichki_narx(self, vazifa: str) -> str:
        """Ichki katalogda narx bor-yo'qligini tekshiradi.

        Hozircha deyarli barcha mahsulotda narx bo'sh — bu ochiq holat, yashirilmaydi.
        """
        try:
            topilgan = await self.api.qidir_keng(vazifa)
        except ApiXatosi as xato:
            self.ogohlantirish = f"ichki katalogga ulanib bo'lmadi ({xato})"
            return (
                "\n\nICHKI NARX: ichki tizimga ulanib bo'lmadi — ichki narx holati "
                "noma'lum. Faqat tashqi bozor narxini qidir va ularni tashqi deb belgila."
            )

        if not topilgan:
            self._ichki_xabar = "mahsulot ichki katalogda topilmadi"
            return (
                "\n\nICHKI NARX: bu mahsulot ichki katalogda topilmadi, shuning uchun "
                "ichki narx ham yo'q. Tashqi bozor narxini qidirishing mumkin — "
                "lekin ularni `tashqi_bozor: true` deb belgila."
            )

        narxlilar = [m for m in topilgan if narx_bormi(m)]
        if not narxlilar:
            self._ichki_xabar = (
                f"ichki katalogda {len(topilgan)} ta mos mahsulot bor, "
                "lekin narx to'ldirilmagan"
            )
            return (
                f"\n\nICHKI NARX: ichki katalogda {len(topilgan)} ta mos mahsulot topildi, "
                "lekin ularning NARXI TO'LDIRILMAGAN (price = 0). Ya'ni ichki narx "
                "ma'lumoti mavjud emas — buni `ichki_narx_holati` da ochiq ayt. "
                "Tashqi bozor narxini o'z narximiz sifatida KO'RSATMA."
            )

        self._ichki_xabar = f"ichki katalogda {len(narxlilar)} ta narx topildi"
        qatorlar = [
            f"- {mahsulot_qisqa(m)['nomi']}: {m.get('price')}" for m in narxlilar[:5]
        ]
        return (
            "\n\nICHKI NARX (birlamchi manba, `tashqi_bozor: false` bilan yoz):\n"
            + "\n".join(qatorlar)
        )

    # --- natijani boyitish ---------------------------------------------------

    async def _tarixni_yangila(self, natija: ZaraNatija) -> list[str]:
        """Narxlarni bazaga yozadi va keskin o'zgarishni belgilaydi.

        Ruxsat: ichki bazaga narx tarixini YOZISH mumkin, o'chirish — yo'q.
        """
        diqqat: list[str] = []
        for yozuv in natija.yozuvlar:
            if yozuv.narx is None or not yozuv.valyuta:
                continue

            oxirgi = await self.baza.oxirgi_narx(yozuv.mahsulot, yozuv.valyuta)
            if oxirgi and oxirgi["narx"]:
                farq = (yozuv.narx - oxirgi["narx"]) / oxirgi["narx"]
                if abs(farq) > KESKIN_OZGARISH:
                    diqqat.append(
                        f"{yozuv.mahsulot}: narx {oxirgi['narx']:.2f} -> {yozuv.narx:.2f} "
                        f"{yozuv.valyuta} ({farq:+.0%}) — keskin o'zgarish, e'tibor bering"
                    )

            await self.baza.narx_yoz(
                {
                    "mahsulot": yozuv.mahsulot,
                    "bozor": natija.bozor,
                    "narx": yozuv.narx,
                    "valyuta": yozuv.valyuta,
                    "sana": yozuv.sana,
                    "manba": yozuv.manba_nomi,
                    "havola": yozuv.havola,
                }
            )
        return diqqat

    def _manbalarni_yig(self, javob: Any, natija: ZaraNatija) -> list[Manba]:
        manbalar: list[Manba] = []
        korilgan: set[str] = set()

        for yozuv in natija.yozuvlar:
            kalit = yozuv.havola or yozuv.manba_nomi or ""
            if not kalit or kalit in korilgan:
                continue
            korilgan.add(kalit)
            manbalar.append(
                Manba(
                    tur="veb",
                    nom=yozuv.manba_nomi or kalit,
                    havola=yozuv.havola,
                    sana=yozuv.sana,
                )
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
                Manba(tur="veb", nom=veb.get("nom") or kalit, havola=veb.get("havola"), sana=veb.get("sana"))
            )

        if not manbalar:
            # Hech narsa topilmasa ham konvert manbasiz chiqmaydi: nima
            # qilinganini ochiq ko'rsatamiz.
            manbalar.append(Manba(tur="veb", nom="veb qidiruv — natija topilmadi"))
        return manbalar

    def _umumiy_ishonch(self, natija: ZaraNatija) -> Ishonch:
        topilgan = [y for y in natija.yozuvlar if y.narx is not None]
        if not topilgan:
            return Ishonch.PAST

        eng_past = min(topilgan, key=lambda y: ISHONCH_TARTIBI[y.ishonch]).ishonch
        if any(y.manba_ishonchsiz for y in topilgan) and eng_past is Ishonch.YUQORI:
            eng_past = Ishonch.ORTA
        if (natija.topilmaganlar or natija.ziddiyatlar) and eng_past is Ishonch.YUQORI:
            eng_past = Ishonch.ORTA
        return eng_past

    def _izoh(self, natija: ZaraNatija) -> str:
        bolaklar: list[str] = []
        topilgan = sum(1 for y in natija.yozuvlar if y.narx is not None)
        bolaklar.append(f"{topilgan} ta narx topildi")

        # Ichki narx holati har doim ochiq aytiladi.
        if natija.ichki_narx_holati:
            bolaklar.append(f"ichki narx: {natija.ichki_narx_holati}")
        elif self._ichki_xabar:
            bolaklar.append(f"ichki narx: {self._ichki_xabar}")

        tashqilar = sum(1 for y in natija.yozuvlar if y.narx is not None and y.tashqi_bozor)
        if tashqilar:
            bolaklar.append(
                f"{tashqilar} ta narx TASHQI bozordan — kompaniyaning o'z narxi emas"
            )
        if natija.topilmaganlar:
            bolaklar.append("topilmadi: " + ", ".join(natija.topilmaganlar))
        if natija.ziddiyatlar:
            bolaklar.append(f"{len(natija.ziddiyatlar)} ta manba ziddiyati belgilandi")
        if any(y.manba_ishonchsiz for y in natija.yozuvlar):
            bolaklar.append("ba'zi manbalar ishonchsiz deb belgilandi")
        bolaklar.extend(natija.diqqat)
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)
