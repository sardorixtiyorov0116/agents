"""Raqobat tahlilchisi Karim — `competitor-watch`.

Maqsad: raqobatchilarning mahsulot, narx, aksiya va yangiliklarini ochiq
manbalardan yig'ib, sanasi va manbasi bilan qaytaradi hamda qisqa tahliliy
xulosa chiqaradi.

Chegaralar (kontraktdan): marketing rejasi tuzmaydi (bu Malikaning ishi),
faqat ochiq va qonuniy manbalardan yig'adi, maxfiy ma'lumot olishga urinmaydi,
raqibga qarshi harakat qilmaydi.
"""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni

from ..konvert import Holat, Ishonch, Konvert, Manba, xato_konvert
from ..llm import json_ajrat, llm_xato_matni, matn_yig, veb_manbalar
from .asos import Agent

# Veb qidiruvlar soni.
#
# O'LCHANDI (2026-08-19, 9 ta haqiqiy yurish izidan):
#
#     manba     vaqt     topilma
#        1      54 s        8
#       55     157 s       12
#       63     104 s        0     <- eng ko'p manba, HECH QANDAY topilma
#       70     138 s        8
#      154     265 s       16
#
# Ikki xulosa:
#  1) Vaqt manba soniga deyarli CHIZIQLI bog'liq — har manba ~1.2 s.
#  2) Ko'p manba yaxshi natija BERMAYDI: bitta manbali yurish 8 ta topilma
#     bergan, 63 manbali esa nolta.
#
# Bundan tashqari javob `MAKS_TOPILMA = 10` bilan cheklangan — ya'ni 60 dan
# ortiq manba javobga umuman sig'maydi, faqat vaqt yeydi.
#
# 20 -> 8: taxminan 50-60 manba, bu 10 ta topilma uchun yetarli.
# DIQQAT: bu o'zgarish jonli o'lchov bilan tasdiqlanmagan (Anthropic
# balansi tugagan, Gemini esa veb qidiruvni qo'llab-quvvatlamaydi).
# Balans tiklangach `izlar` dagi yangi yurishlar bilan tekshirilsin.
VEB_MAKS = 8

# Bitta javobdagi maksimal topilma soni.
#
# Nega chegara kerak: o'lchov ko'rsatdiki, Karimning vaqti deyarli butunlay
# JAVOB YOZISHGA ketadi (5 100 chiqish tokeni, 88 soniya). Chegarasiz u 25 ta
# topilma yozadi, ularning ko'pi mayda-chuyda. Menejer baribir yuqoridagi
# bir nechtasini o'qiydi. 10 taga cheklash javobni ikki barobar tezlashtiradi
# va sifatni pasaytirmaydi — muhimi yuqorida qoladi.
MAKS_TOPILMA = 10

TIZIM_PROMPT = """Sen "Raqobat tahlilchisi Karim" — kompaniyaning raqobat kuzatuvchi agentisan.

VAZIFAN: so'ralgan raqobatchilar bo'yicha ochiq manbalardan ma'lumot yig'ib,
har topilmani sanasi va manbasi bilan qaytarish, so'ng qisqa tahliliy xulosa
chiqarish.

MANBALAR UCH XIL:
- KOMPANIYA PROFILI — raqobatchilar RO'YXATI va turi. Bu ISHONCHLI ichki
  manba. Savol shunchaki "raqiblarimiz kimlar" bo'lsa, javob ALLAQACHON
  profilda: veb qidiruvsiz javob ber, har topilmada
  `manba_nomi: "kompaniya profili"` va `ichki_manba: true` qo'y.
- ICHKI TAHLIL HUJJATLARI — topshiriqdagi shu nomli bo'lim. Bu bizning
  o'z tahlilimiz: har raqobatchi bo'yicha dosye (kimning distribyutori,
  qaysi segmentda), bozor hajmi, TAM-SAM-SOM. Profildan ANCHA
  BATAFSIL. Undan olingan har topilmada `ichki_manba: true` va
  `manba_nomi` ga HUJJAT NOMINI yozasan.
- VEB QIDIRUV — raqiblar NIMA QILAYOTGANI (yangi aksiya, mahsulot,
  yangilik) uchun. Faqat shu kerak bo'lganda ishlat.

Tartib: avval ichki manbalar (profil + tahlil hujjatlari), keyin
qidiruvdan topilgani. Qidiruv ishlamasa ham, ichki manbadan bilganingni
ALBATTA yoz — bo'sh javob qaytarma.

ICHKI HUJJAT SANASI ESKI bo'lishi mumkin. Raqamni (bozor hajmi, ulush)
hujjatdan olsang, uni "bizning tahlilimizga ko'ra" deb belgila — bugungi
jonli ma'lumot deb ko'rsatma.

QAT'IY QOIDALAR:
1) MA'LUMOTNI O'YLAB TOPMA. Manbadan (profil yoki veb) topmagan narsani
   yozmaysan — raqibni yoki yo'nalishni `topilmaganlar` ro'yxatiga qo'shasan.
   To'qib chiqarish qat'iyan man etilgan.
2) Har topilma uchun manba nomi, havola va sanani ko'rsat. Sana topilmasa —
   bo'sh qoldir va ishonchni pasaytir (eski ma'lumot noto'g'ri qaror beradi).
3) Manba ishonchsiz bo'lsa (forum, mish-mish, rasmiy bo'lmagan kanal) —
   `manba_ishonchsiz: true` qilib belgila va ishonchni pasaytir.
4) `xulosa` — faqat topilgan faktlarga tayangan QISQA tahliliy xulosa
   (2-4 gap): nima o'zgardi, qaysi yo'nalishda harakat bor. Fakt bo'lmasa,
   xulosa ham bo'lmaydi — buni ochiq ayt.
5) ENG KO'PI 10 TA TOPILMA yoz. Hammasini emas — eng MUHIMLARINI tanla:
   yangi mahsulot, narx o'zgarishi, yirik shartnoma, bozorga kirish.
   Mayda yangilik va takroriy xabarni tashlab yubor. Ro'yxat uzun bo'lgani
   foyda bermaydi — menejer baribir yuqoridagilarini o'qiydi.

SEN QILMAYDIGAN ISHLAR:
- Marketing rejasi yoki kampaniya tuzmaysan (bu Marketolog Malikaning ishi).
  Xulosang faqat kuzatuv, tavsiya emas.
- Maxfiy ma'lumot olishga urinmaysan: faqat ochiq va qonuniy manbalar
  (rasmiy saytlar, ochiq ijtimoiy tarmoq sahifalari, matbuot). Yopiq tizim,
  ichki hujjat yoki shaxsiy ma'lumotga urinmaysan.
- Raqibga qarshi hech qanday harakat qilmaysan.
- Narx bo'yicha to'liq tahlil qilmaysan (bu Narx analitigi Zaraning ishi) —
  raqib aksiyasi kontekstida narx eslatilsa, faqat kuzatuv sifatida yozasan.

QIDIRUV: `web_search` vositasidan foydalanib joriy ma'lumotni top. Hudud va
davrni so'rovga qarab hisobga ol. Rasmiy manbalarga ustunlik ber.

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "hudud": "matn",
  "davr": "matn",
  "topilmalar": [
    {
      "raqib": "matn",
      "mavzu": "narx | mahsulot | aksiya | reklama | yangilik",
      "tafsilot": "matn",
      "sana": "YYYY-MM-DD yoki null",
      "manba_nomi": "matn yoki null",
      "havola": "URL yoki null",
      "ishonch": "yuqori | orta | past",
      "manba_ishonchsiz": true/false,
      "ichki_manba": true/false
    }
  ],
  "trendlar": ["izoh"],
  "xulosa": "matn",
  "topilmaganlar": ["raqib yoki yo'nalish nomi"]
}"""


class Topilma(BaseModel):
    """Bitta raqib bo'yicha bitta manbadagi topilma."""

    raqib: str
    mavzu: str = ""
    tafsilot: str = ""
    sana: str | None = None
    manba_nomi: str | None = None
    havola: str | None = None
    ishonch: Ishonch = Ishonch.ORTA
    manba_ishonchsiz: bool = False
    # Kompaniya profilidan olingan (veb emas) — ishonchli ichki manba.
    ichki_manba: bool = False


class KarimNatija(BaseModel):
    """Karimning `natija` maydoni."""

    hudud: str = ""
    davr: str = ""
    topilmalar: list[Topilma] = Field(default_factory=list, max_length=MAKS_TOPILMA)
    trendlar: list[str] = Field(default_factory=list)
    xulosa: str = ""
    topilmaganlar: list[str] = Field(default_factory=list)


ISHONCH_TARTIBI = {Ishonch.PAST: 0, Ishonch.ORTA: 1, Ishonch.YUQORI: 2}

# Promptga tushadigan eski topilma soni.
MAKS_TARIX = 25


class RaqobatTahlilchisi(Agent):
    """Raqobat tahlilchisi Karim."""

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        topshiriq = self.topshiriq_matni(vazifa, kontekst)

        # Raqobatchilar ro'yxati profildan keladi — Karim ularni so'ramaydi.
        nomlar = self.kompaniya.raqobatchi_nomlari()
        if nomlar:
            topshiriq += (
                "\n\nKompaniya profilidagi ma'lum raqobatchilar (so'rovda aniq nom "
                "aytilmasa shulardan boshla):\n"
                + "\n".join(f"- {n}" for n in nomlar)
            )

        # BILIM BAZASI — `market` papkasi. Profil faqat NOMLARNI beradi,
        # bu yerda esa har raqobatchi bo'yicha dosye, bozor hajmi va
        # segment tahlili bor. Ilgari papka biriktirilgan-u, hech qachon
        # so'ralmasdi: Karim 8 ta nom bilan qolib ketardi, veb qidiruv
        # esa Gemini'da umuman ishlamaydi.
        topilmalar = self.bilimni_qidir(vazifa)
        if topilmalar:
            topshiriq += "\n\nICHKI TAHLIL HUJJATLARI:\n" + kontekst_matni(topilmalar)
        else:
            topshiriq += (
                "\n\nICHKI TAHLIL HUJJATLARI: bu so'rov bo'yicha hujjat "
                "topilmadi."
            )

        topshiriq += await self._tarix_matni()

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=KarimNatija,
                json_skelet=JSON_SKELET,
                veb_qidiruv=True,
                # Bir nechta raqobatchi bo'yicha qidiradi — chegara kattaroq.
                veb_maks=VEB_MAKS,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = KarimNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        await self._tarixga_yoz(natija)

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=natija.model_dump(mode="json"),
            manba=self._manbalarni_yig(javob, natija),
            ishonch=self._umumiy_ishonch(natija),
            # Kontrakt: odatda tasdiq kerak emas — strategik ta'sir bo'lsa
            # router qadam darajasida tasdiq qo'yadi.
            tasdiq_kerak=False,
            izoh=self._izoh(natija),
        )

    # --- natijani boyitish ---------------------------------------------------

    async def _tarix_matni(self) -> str:
        """Oldingi topilmalar — takrorlanmasin, o'zgarish ko'rinsin.

        Tarixsiz Karim har safar noldan boshlaydi va menejerga o'tgan oyda
        aytilgan narsani yana aytadi. Eng qimmatli xulosa esa aynan
        O'ZGARISHDA: "narxni ko'targan", "yangi model chiqargan".
        """
        try:
            eski = await self.baza.topilmalar(chek=MAKS_TARIX)
        except Exception:
            return ""      # tarix o'qilmasa ham tahlil davom etadi
        if not eski:
            return ""

        qatorlar = ["\n\nOLDINGI TOPILMALAR (bazadan, yangisidan eskisiga):"]
        for yozuv in eski:
            sana = str(yozuv.get("vaqt") or "")[:10]
            mavzu = yozuv.get("mavzu") or ""
            tafsilot = str(yozuv.get("tafsilot") or "")[:140]
            qatorlar.append(
                f"- [{sana}] {yozuv['raqib']} · {mavzu}: {tafsilot}"
            )
        qatorlar.append(
            "\nSHU TARIXDAN FOYDALAN:\n"
            "- yuqoridagi bilan AYNAN bir xil topilmani qayta yozma;\n"
            "- o'zgargan bo'lsa (narx, model, aksiya) — buni `trendlar` da "
            "ochiq ayt: nima edi, nima bo'ldi;\n"
            "- yangi topilma bo'lsa oddiy yoz;\n"
            "- tarix asosida YANGI FAKT to'qima — u faqat solishtirish uchun."
        )
        return "\n".join(qatorlar)

    async def _tarixga_yoz(self, natija: KarimNatija) -> None:
        """Topilmalarni tarixga yozadi (ruxsat: yozish bor, o'chirish yo'q)."""
        for topilma in natija.topilmalar:
            await self.baza.topilma_yoz(
                {
                    "raqib": topilma.raqib,
                    "mavzu": topilma.mavzu,
                    "tafsilot": topilma.tafsilot,
                    "sana": topilma.sana,
                    "manba": topilma.manba_nomi,
                    "havola": topilma.havola,
                }
            )

    def _manbalarni_yig(self, javob: Any, natija: KarimNatija) -> list[Manba]:
        manbalar: list[Manba] = []
        korilgan: set[str] = set()

        for topilma in natija.topilmalar:
            kalit = topilma.havola or topilma.manba_nomi or ""
            if not kalit or kalit in korilgan:
                continue
            korilgan.add(kalit)
            manbalar.append(
                Manba(
                    # Ichki manba (kompaniya profili) veb bilan chalkashmasin.
                    tur="profil" if topilma.ichki_manba else "veb",
                    nom=topilma.manba_nomi or kalit,
                    havola=topilma.havola,
                    sana=topilma.sana,
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
                Manba(
                    tur="veb",
                    nom=veb.get("nom") or kalit,
                    havola=veb.get("havola"),
                    sana=veb.get("sana"),
                )
            )

        if not manbalar:
            manbalar.append(Manba(tur="veb", nom="veb qidiruv — natija topilmadi"))
        return manbalar

    def _umumiy_ishonch(self, natija: KarimNatija) -> Ishonch:
        if not natija.topilmalar:
            return Ishonch.PAST

        eng_past = min(natija.topilmalar, key=lambda t: ISHONCH_TARTIBI[t.ishonch]).ishonch
        if any(t.manba_ishonchsiz for t in natija.topilmalar) and eng_past is Ishonch.YUQORI:
            eng_past = Ishonch.ORTA
        # Sana yo'qligi faqat veb topilmasi uchun muhim: profildagi ma'lumot
        # (raqobatchi kimligi) sanaga bog'liq emas.
        vebdagilar = [t for t in natija.topilmalar if not t.ichki_manba]
        if any(t.sana is None for t in vebdagilar) and eng_past is Ishonch.YUQORI:
            eng_past = Ishonch.ORTA
        if natija.topilmaganlar and eng_past is Ishonch.YUQORI:
            eng_past = Ishonch.ORTA
        return eng_past

    def _izoh(self, natija: KarimNatija) -> str:
        bolaklar = [f"{len(natija.topilmalar)} ta topilma"]
        raqiblar = sorted({t.raqib for t in natija.topilmalar})
        if raqiblar:
            bolaklar.append("raqiblar: " + ", ".join(raqiblar))
        if natija.topilmaganlar:
            bolaklar.append("topilmadi: " + ", ".join(natija.topilmaganlar))
        if natija.trendlar:
            bolaklar.append(f"{len(natija.trendlar)} ta trend belgilandi")
        if any(t.manba_ishonchsiz for t in natija.topilmalar):
            bolaklar.append("ba'zi manbalar ishonchsiz deb belgilandi")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)
