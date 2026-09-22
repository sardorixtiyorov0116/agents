"""Marketolog Malika — `marketing`.

Maqsad: kampaniya g'oyasi, reklama matni va kontent qoralamasini tayyorlaydi.

Chegaralar (kontraktdan): kontentni o'zi nashr qilmaydi/yubormaydi, byudjet
sarflamaydi, yolg'on yoki asossiz va'da yozmaydi, raqib ma'lumotini o'zi
yig'maydi — uni Karim (`competitor-watch`) zanjir orqali beradi.

Shuning uchun bu agentda veb qidiruv YO'Q: kirish ma'lumoti so'rovdan yoki
`kontekst.oldingi_natija` dan keladi.
"""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni

from ..konvert import Holat, Ishonch, Konvert, Manba, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig
from .asos import Agent

TIZIM_PROMPT = """Sen "Marketolog Malika" — kompaniyaning marketing agentisan.

VAZIFAN: kampaniya g'oyasi, reklama matni va kontent QORALAMASINI tayyorlash.

QAT'IY QOIDALAR:
1) FAKTSIZ DA'VO YOZMA. "Eng arzon", "bozorda birinchi", "sifat kafolati" kabi
   da'volarni faqat kirish ma'lumotida tasdiq bo'lsa yozasan. Tasdiq bo'lmasa —
   da'voni umuman yozmaysan va uni `asossiz_dovolar` ro'yxatiga qo'yasan
   (nima yozilmaganini ochiq ko'rsatasan).
2) MAHSULOT MA'LUMOTINI O'YLAB TOPMA. Xususiyat, narx yoki natija raqamini
   o'zingdan yozmaysan. Ma'lumot yetishmasa — matnni umumiy qoldirasan va
   yetishmagan narsani `sorash_kerak` ro'yxatiga yozasan.
3) Kirish ma'lumoti kontekstda kelgan bo'lsa (masalan Raqobat tahlilchisi
   Karimning topilmalari), aynan shunga tayan va `asos` maydonida qaysi
   ma'lumotdan foydalanganingni ayt.
4) Har variant uchun kanal va ohangni ko'rsat.
5) "BREND VA POZITSIYALASH HUJJATLARI" bo'limi bo'lsa — OHANG va
   POZITSIYALASHNI o'sha yerdan olasan, o'zingdan o'ylab topmaysan.
   Hujjatdagi tasdiq da'vo uchun ASOS bo'ladi: shunga tayansang,
   `asos` maydonida hujjat nomini yozasan.

SEN QILMAYDIGAN ISHLAR:
- Kontentni NASHR QILMAYSAN va yubormaysan. Sen faqat qoralama tayyorlaysan —
  nashr qarori insonda.
- Byudjetni sarflamaysan, reklama uchun to'lov qilmaysan. Byudjet haqida faqat
  taklif yozishing mumkin, sarflash emas.
- Raqib ma'lumotini O'ZING YIG'MAYSAN (bu Raqobat tahlilchisi Karimning ishi).
  Raqib haqida ma'lumot kerak bo'lsa va kontekstda yo'q bo'lsa — buni
  `sorash_kerak` ga yozasan.
- Narx tahlili qilmaysan (bu Narx analitigi Zaraning ishi).

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "kampaniya_nomi": "matn",
  "auditoriya": "matn",
  "goya": "matn",
  "asos": ["qaysi ma'lumotga tayanildi"],
  "variantlar": [
    {
      "kanal": "Instagram | Telegram | SMS | ...",
      "ohang": "matn",
      "matn": "reklama matni"
    }
  ],
  "tavsiya_kanal": "matn",
  "tavsiya_vaqt": "matn",
  "sorash_kerak": ["yetishmayotgan ma'lumot"],
  "asossiz_dovolar": ["yozilmagan da'vo va sababi"]
}"""


# Promptga tushadigan raqib topilmalari soni.
MAKS_RAQIB_TARIXI = 15


class KontentVariant(BaseModel):
    """Bitta kanal uchun reklama matni varianti."""

    kanal: str = ""
    ohang: str = ""
    matn: str = ""


class MalikaNatija(BaseModel):
    """Malikaning `natija` maydoni."""

    kampaniya_nomi: str = ""
    auditoriya: str = ""
    goya: str = ""
    asos: list[str] = Field(default_factory=list)
    variantlar: list[KontentVariant] = Field(default_factory=list)
    tavsiya_kanal: str = ""
    tavsiya_vaqt: str = ""
    sorash_kerak: list[str] = Field(default_factory=list)
    asossiz_dovolar: list[str] = Field(default_factory=list)


class Marketolog(Agent):
    """Marketolog Malika."""

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        self._bilim_topilmalari = []
        topshiriq = self.topshiriq_matni(vazifa, kontekst)

        # BILIM BAZASI — `marketing` papkasi: pozitsiyalash (STP),
        # brend-arxetip, kommunikatsiya strategiyasi, SWOT, PEST.
        #
        # Malikaning 1-qoidasi "faktsiz da'vo yozma". Bu hujjatlarsiz
        # unda tasdiq manbasi yo'q edi va matn umumiy chiqardi —
        # papka biriktirilgan bo'lsa ham hech qachon so'ralmasdi.
        topilmalar = self.bilimni_qidir(vazifa)
        self._bilim_topilmalari = topilmalar
        if topilmalar:
            topshiriq += "\n\nBREND VA POZITSIYALASH HUJJATLARI:\n" + kontekst_matni(
                topilmalar
            )
        else:
            topshiriq += (
                "\n\nBREND VA POZITSIYALASH HUJJATLARI: bu so'rov bo'yicha "
                "hujjat topilmadi — brend ohangini o'zingdan o'ylab topma."
            )

        topshiriq += await self._raqib_tarixi(kontekst)

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=MalikaNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = MalikaNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija.model_dump(mode="json"),
            manba=self._manbalarni_yig(kontekst),
            ishonch=self._umumiy_ishonch(natija, kontekst),
            # Nashr etiladigan kontent tasdiqdan o'tadi — buni router qadam
            # darajasida qo'yadi (kontrakt: "Har qanday nashr etiladigan
            # kontentda"), agent esa qoralamani tayyorlab beradi.
            tasdiq_kerak=False,
            izoh=self._izoh(natija),
        )

    async def _raqib_tarixi(self, kontekst: dict[str, Any] | None) -> str:
        """Karim yozib qo'ygan raqib topilmalari.

        Zanjirda Karim oldin ishlagan bo'lsa, uning natijasi allaqachon
        `oldingi_natija` da keladi — u holda takrorlamaymiz. Lekin Malika
        YAKKA chaqirilganda raqib konteksti umuman bo'lmasdi: kampaniya
        bozorni ko'rmasdan tuzilardi.
        """
        if (kontekst or {}).get("oldingi_natija"):
            return ""
        try:
            eski = await self.baza.topilmalar(chek=MAKS_RAQIB_TARIXI)
        except Exception:
            return ""
        if not eski:
            return ""

        qatorlar = ["\n\nRAQOBATCHILAR HAQIDA MA'LUM (Karim to'plagan, bazadan):"]
        for yozuv in eski:
            sana = str(yozuv.get("vaqt") or "")[:10]
            tafsilot = str(yozuv.get("tafsilot") or "")[:130]
            qatorlar.append(f"- [{sana}] {yozuv['raqib']}: {tafsilot}")
        qatorlar.append(
            "\nBu ma'lumot FON uchun: kampaniya bozor holatiga mos bo'lsin. "
            "Raqobatchini kampaniya matnida NOMLAB QORALAMAYSAN. Shu "
            "topilmaga tayansang, `asos` maydonida qaysi biri ekanini ayt."
        )
        return "\n".join(qatorlar)

    def _manbalarni_yig(self, kontekst: dict[str, Any] | None) -> list[Manba]:
        """Malika kontent yaratadi — manbasi kirish ma'lumoti.

        Zanjirda oldingi agent bergan bo'lsa, aynan shuni ko'rsatamiz; aks
        holda kontraktning o'zi manba bo'ladi (nimaga tayanganini yashirmaymiz).
        """
        manbalar: list[Manba] = []
        oldingi = (kontekst or {}).get("oldingi_agent")
        if oldingi:
            manbalar.append(Manba(tur="agent", nom=f"{oldingi} konverti"))
        # Brend hujjatlari ishlatilgan bo'lsa — ular ham manba.
        manbalar.extend(self.bilim_manbalari(getattr(self, "_bilim_topilmalari", [])))
        return manbalar or [self.kontrakt_manbasi()]

    def _umumiy_ishonch(self, natija: MalikaNatija, kontekst: dict[str, Any] | None) -> Ishonch:
        if natija.sorash_kerak:
            return Ishonch.PAST
        # Zanjirdan kelgan faktlarga tayangan qoralama ishonchliroq.
        if (kontekst or {}).get("oldingi_natija") and natija.asos:
            return Ishonch.YUQORI
        return Ishonch.ORTA

    def _izoh(self, natija: MalikaNatija) -> str:
        bolaklar = [f"{len(natija.variantlar)} ta kontent varianti"]
        if natija.tavsiya_kanal:
            bolaklar.append(f"tavsiya kanal: {natija.tavsiya_kanal}")
        if natija.sorash_kerak:
            bolaklar.append("ma'lumot yetishmaydi: " + ", ".join(natija.sorash_kerak))
        if natija.asossiz_dovolar:
            bolaklar.append(f"{len(natija.asossiz_dovolar)} ta asossiz da'vo yozilmadi")
        bolaklar.append("QORALAMA — nashr qilinmadi")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)
