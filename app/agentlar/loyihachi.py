"""Loyihachi muhandis Rustam — `hvac-calc`.

Maqsad: obyekt tavsifidan ventilyatsiya hisobini chiqaradi va katalogdan
mos uskunani ko'rsatadi.

O'ZGARMAS QOIDALAR (kodda, promptda emas):
  - MODEL HISOBLAMAYDI. Uning sxemasida `havo_sarfi` yoki `diametr` kabi
    maydon UMUMAN yo'q — u faqat xona parametrlarini ajratadi. Barcha
    formula `hisob/ventilyatsiya.py` da va testlar bilan qoplangan;
  - o'lcham aytilmasa taxmin qilinmaydi — so'raladi;
  - kanal uskunasi model nomidagi DIAMETRGA qarab tanlanadi;
  - VENTILYATOR esa HAVO SARFIGA qarab tanlanadi. Backendda bu maydon
    yo'q, shuning uchun raqam mahsulotning texnik jadvalidan o'qiladi
    (`integrations/texnik.py`) — model hech narsa taxmin qilmaydi.
    Jadvali yo'q mahsulot tavsiyaga umuman tushmaydi.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from hisob import Xona, havo_sarfi, kanal_olchami, normalar, tipik_bosim, yetadimi
from integrations import ApiXatosi, mahsulot_qisqa

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

log = logging.getLogger("rustam")

# Bir so'rovda hisoblanadigan xona soni.
MAKS_XONA = 12
# Har diametr uchun ko'rsatiladigan model soni.
MAKS_MODEL = 6
# Havo sarfi bo'yicha taklif qilinadigan ventilyator soni.
MAKS_VENTILYATOR = 6

# ASPIRATSIYA — bu yerdagi hisob usuli mos kelmaydi.
#
# Xona hajmi bo'yicha karralik faqat UMUMIY almashinuv uchun.
# Chang, qipiq va kukun tizimida havo sarfi har dastgohning
# qabul qilgichi bo'yicha aniqlanadi, kanaldagi tezlik esa
# minimumdan past bo'lmasligi kerak (12–25 m/s).
ASPIRATSIYA = re.compile(
    r"aspiratsi|аспираци|chang\s*(so['`‘’]?r|tozal|yig)|"
    r"qipiq|стружк|опилк|пылеулав|циклон|siklon|"
    r"chang\s*ventilyator|пылев\w*\s*вентилятор|"
    r"payvandlash\s*tutun|сварочн\w*\s*дым",
    re.IGNORECASE,
)

ASPIRATSIYA_SAVOLLARI = [
    "Qanday material — yog'och qipig'i, un, sement, metall kukuni?",
    "Nechta dastgoh (manba) va ular bir vaqtda ishlaydimi?",
    "Har dastgohning pasportida so'rish sarfi ko'rsatilganmi?",
    "Chang PORTLASH XAVFLIMI (un, kraxmal, alyuminiy kukuni)? — "
    "bu holatda maxsus loyiha kerak",
    "Chang qayerga to'planadi va kim chiqaradi?",
]

# Faqat VENTILYATOR taklif qilinadi. Texnik jadvalda issiqlik almashgich
# va markaziy qurilmalarning ham havo sarfi bor — ular ventilyator emas.
VENTILYATOR_TURI = re.compile(r"вентилятор|ventilyator|вентиляторы", re.IGNORECASE)

# Model ba'zan ichki qoidani eslatma qilib yozib yuboradi ("hisobni tizim
# qiladi"). Bu foydalanuvchiga aloqasiz va chalg'ituvchi — filtrlaymiz.
# Bu ro'yxat jonli sinovlarda o'sdi — model har safar boshqacha
# ifodalaydi ("tizim tomonidan hisoblanadi", "hisobini tizim bajaradi",
# "faqat parametrlar ajratildi"). Shuning uchun BITTA so'z bo'yicha
# emas, ikkita alomat bo'yicha tekshiramiz: gapda "tizim"/"parametr"
# kabi ichki atama bo'lsa VA u hisob jarayoni haqida bo'lsa — bu ichki
# qoida, mijozga aloqasi yo'q.
ICHKI_ATAMALAR = ("tizim", "sxema", "parametrlar ajrat", "men hisoblamayman")
ICHKI_JARAYON = (
    "hisobla", "hisobi", "hisobni", "bajaradi", "bajariladi",
    "ko'rsatilmagan", "korsatilmagan", "bu javobda", "ajratildi",
    "ajratdim",
)

NORMA_IZOHI = (
    "Ishlatilgan havo almashinuvi normalari — umumiy amaliyot qiymatlari, "
    "rasmiy normativ hujjat ko'chirmasi emas. Loyiha uchun buyurtmachi "
    "texnik topshirig'i va amaldagi QMQ bilan solishtirilishi shart."
)

# PROMPT QISQA — ATAYLAB. Har mijoz savolida shu matn qaytadan yuboriladi,
# shuning uchun har ortiqcha jumla pulga aylanadi. Qoidalarning O'ZI
# saqlanadi, faqat tushuntirishlar olib tashlandi — ular kod izohida
# (fayl boshida) va testlarda turibdi.
TIZIM_PROMPT = """Sen "Loyihachi muhandis Rustam"san. Vazifang: matndan
XONA PARAMETRLARINI ajratish. Hisobni tizim qiladi.

QOIDALAR:
1) HISOBLAMAYSAN — havo sarfi, diametr, tezlik sxemangda yo'q.
2) O'LCHAMNI TAXMIN QILMAYSAN. Maydon yoki balandlik aytilmagan bo'lsa:
   `maydon: 0` qoldirasan va `sorash_kerak` ga yozasan. "Odatda 3 metr"
   — taxmin, taqiqlanadi. Odatiy ofis bo'lsa ham so'raysan.
3) XONA TURINI faqat berilgan ro'yxatdan tanlaysan; aniq mosi bo'lmasa
   eng yaqinini olasan va `izoh` da sababini yozasan.
4) Har xonani alohida yozasan.
5) NORMATIV HUJJATGA HAVOLA QILMAYSAN ("QMQ 2.04.05 bo'yicha" — yo'q).
6) `eslatmalar` faqat OBYEKT haqida ("zararli modda bo'lsa alohida hisob
   kerak"). TIZIMNING O'ZI haqida yozmaysan.

QILMAYSAN: issiqlik yuklamasi, dud, yong'in ventilyatsiyasi, bosim
yo'qotishi hisobi (alohida hisob kerakligini aytasan); narx va KP;
loyiha hujjati."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "obyekt": "obyekt nomi yoki tavsifi",
  "xonalar": [
    {"nomi": "xona nomi", "turi": "ro'yxatdagi tur", "maydon": 100,
     "balandlik": 3, "odamlar": 0, "izoh": "tur tanlash sababi yoki bo'sh"}
  ],
  "kanal_turi": "magistral | tarmoq",
  "sorash_kerak": ["aniqlashtirish kerak bo'lgan narsa"],
  "eslatmalar": ["OBYEKT haqidagi eslatma: alohida hisob kerakligi va h.k."]
}"""


class XonaKirishi(BaseModel):
    """Model ajratgan parametrlar. Hisob natijasi bu yerda YO'Q."""

    nomi: str = ""
    turi: str = "ofis"
    maydon: float = 0
    balandlik: float = 0
    odamlar: int = 0
    izoh: str = ""


class RustamNatija(BaseModel):
    obyekt: str = ""
    xonalar: list[XonaKirishi] = Field(default_factory=list)
    kanal_turi: str = "magistral"
    sorash_kerak: list[str] = Field(default_factory=list)
    eslatmalar: list[str] = Field(default_factory=list)


class Loyihachi(Agent):
    """Loyihachi muhandis Rustam."""

    # Bu agent o'ylamaydi — matndan maydon ajratadi (maydon, balandlik,
    # xona turi). Chuqur fikrlash natijani yaxshilamaydi, faqat chiqish
    # tokenini oshiradi.
    EFFORT = "low"

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""

        # ASPIRATSIYA — BOSHQA USUL.
        #
        # Jonli xato (2026-08-11): "yog'och sexida aspiratsiya kerak"
        # deyilganda Rustam xona maydoni va balandligini so'radi.
        # Bu noto'g'ri savol: aspiratsiyada havo sarfi xona hajmidan
        # emas, HAR MANBA (dastgoh, qabul qilgich) bo'yicha
        # hisoblanadi. Xona hajmi bo'yicha karralik bu yerda umuman
        # ishlatilmaydi.
        if ASPIRATSIYA.search(vazifa or ""):
            return aniqlik_kerak_konvert(
                ASPIRATSIYA_SAVOLLARI,
                "Aspiratsiya tizimi — havo sarfi xona hajmi bo'yicha emas, "
                "har manba (dastgoh) bo'yicha hisoblanadi. Kanaldagi tezlik "
                "ham boshqacha: chang cho'kmasligi uchun 12–25 m/s.",
                kim=self.rol,
            )

        topshiriq = self.topshiriq_matni(vazifa, kontekst)
        topshiriq += self._normalar_matni()

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=RustamNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = RustamNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        return await self._hisobla(natija)

    # --- normalar ------------------------------------------------------------

    def _normalar_matni(self) -> str:
        qatorlar = ["\n\nXONA TURLARI (faqat shu ro'yxatdan tanla):"]
        for tur, norma in normalar().items():
            bolaklar = [f"- {tur}"]
            if norma.get("izoh"):
                bolaklar.append(f"({norma['izoh']})")
            qatorlar.append(" ".join(bolaklar))
        qatorlar.append(
            "\nBu turlarning har biriga tizimda norma biriktirilgan. Sen "
            "normani ko'rmaysan va uni ishlatmaysan — faqat TURNI tanlaysan."
        )
        return "\n".join(qatorlar)

    # --- hisob ---------------------------------------------------------------

    async def _hisobla(self, natija: RustamNatija) -> Konvert:
        if not natija.xonalar:
            return aniqlik_kerak_konvert(
                natija.sorash_kerak
                or ["Qaysi xona? Maydoni (m²) va balandligi (m) qancha?"],
                "Hisob uchun xona o'lchamlari kerak.",
                kim=self.rol,
            )

        kanal_turi = natija.kanal_turi if natija.kanal_turi in ("magistral", "tarmoq") \
            else "magistral"

        xonalar: list[dict[str, Any]] = []
        ogohlantirishlar: list[str] = []
        yetishmaydi: list[str] = []
        jami_sarf = 0.0

        for kirish in natija.xonalar[:MAKS_XONA]:
            xona = Xona(
                turi=kirish.turi,
                maydon=max(kirish.maydon, 0),
                balandlik=max(kirish.balandlik, 0),
                odamlar=max(kirish.odamlar, 0),
                nomi=kirish.nomi,
            )
            havo = havo_sarfi(xona)
            kanal = kanal_olchami(havo.sarf, kanal_turi)
            jami_sarf += havo.sarf

            if havo.sarf <= 0:
                yetishmaydi.append(kirish.nomi or kirish.turi)

            xonalar.append({
                "nomi": kirish.nomi or kirish.turi,
                "turi": kirish.turi,
                "maydon": xona.maydon,
                "balandlik": xona.balandlik,
                "odamlar": xona.odamlar,
                "hajm": havo.hajm,
                "havo_sarfi": havo.sarf,
                "usul": havo.tanlangan_usul,
                "karrali_boyicha": havo.karrali_boyicha,
                "odam_boyicha": havo.odam_boyicha,
                "norma_izohi": havo.norma_izohi,
                "diametr": kanal.diametr,
                "hisobiy_diametr": kanal.hisobiy_diametr,
                "tezlik": kanal.haqiqiy_tezlik,
                "izoh": kirish.izoh,
            })
            for xabar in (*havo.ogohlantirishlar, *kanal.ogohlantirishlar):
                nomli = f"{kirish.nomi or kirish.turi}: {xabar}"
                if nomli not in ogohlantirishlar:
                    ogohlantirishlar.append(nomli)

        # Umumiy tizim — barcha xonalar bitta magistralda bo'lsa.
        umumiy = kanal_olchami(jami_sarf, kanal_turi) if jami_sarf else None

        diametrlar = sorted({x["diametr"] for x in xonalar if x["diametr"]})
        uskunalar = await self._uskunalar(diametrlar)
        # Ventilyator DIAMETR bilan tanlanmaydi — havo sarfi bilan.
        ventilyatorlar = await self._ventilyatorlar(jami_sarf)
        kerakli_bosim = tipik_bosim("kanalli")
        if jami_sarf > 0 and not ventilyatorlar:
            ogohlantirishlar.append(
                f"Katalogda {jami_sarf:,.0f} m³/soat beradigan ventilyator "
                "topilmadi — texnik jadvali bor modellar orasidan mos "
                "kelmadi. Modelni muhandis tanlashi kerak."
                .replace(",", " ")
            )

        sorash = list(natija.sorash_kerak)
        if yetishmaydi:
            sorash.append(
                "O'lcham berilmagan: " + ", ".join(yetishmaydi)
                + " — maydon (m²) va balandlikni ayting"
            )
        if sorash and not any(x["havo_sarfi"] > 0 for x in xonalar):
            return aniqlik_kerak_konvert(
                sorash, "Hisob uchun ma'lumot yetarli emas.", kim=self.rol
            )

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija={
                "obyekt": natija.obyekt,
                "kanal_turi": kanal_turi,
                "xonalar": xonalar,
                "jami_sarf": round(jami_sarf, 1),
                "umumiy_diametr": umumiy.diametr if umumiy else 0,
                "umumiy_tezlik": umumiy.haqiqiy_tezlik if umumiy else 0,
                "uskunalar": uskunalar,
                "ventilyatorlar": ventilyatorlar,
                # Tarmoq sxemasi bizda yo'q — bu TAXMINIY oraliq.
                "kerakli_bosim": {
                    "oraliq_pa": list(kerakli_bosim),
                    "izoh": "taxminiy — tarmoq sxemasi bo'yicha aniqlanadi",
                },
                "sorash_kerak": sorash,
                "eslatmalar": [*self._eslatmalar(natija.eslatmalar), NORMA_IZOHI],
                "ogohlantirishlar": ogohlantirishlar,
            },
            manba=[
                self.kontrakt_manbasi(),
                Manba(tur="hisob", nom="Ventilyatsiya hisobi (ichki modul)"),
            ],
            # Ma'lumot yetishmasa yoki ogohlantirish bo'lsa — ishonch past.
            ishonch=Ishonch.ORTA if (sorash or ogohlantirishlar) else Ishonch.YUQORI,
            # Hisob mijozga yoki loyihaga ketadi — muhandis ko'rib chiqsin.
            tasdiq_kerak=True,
            izoh=self._izoh(xonalar, jami_sarf, umumiy),
        )

    @staticmethod
    def _eslatmalar(xom: list[str]) -> list[str]:
        """Tizim haqidagi eslatmani olib tashlaydi — obyekt haqidagisi qoladi."""
        def ichkimi(matn: str) -> bool:
            past = matn.lower()
            return (any(a in past for a in ICHKI_ATAMALAR)
                    and any(j in past for j in ICHKI_JARAYON))

        return [e for e in xom if not ichkimi(e)]

    # --- katalog -------------------------------------------------------------

    async def _uskunalar(self, diametrlar: list[int]) -> list[dict[str, Any]]:
        """Diametrga mos katalog modellari — TURI bilan birga.

        Katalogda quvvat (m³/soat) strukturali maydon sifatida YO'Q, lekin
        kanal uskunalari nomida diametr turadi (`ВК-250П` -> Ø250).

        MUHIM CHEKLOV: VENTILYATORLARNI bu usul topa olmaydi. Ular
        g'ildirak nomeri bilan ataladi (`ВЦ 4-75-8`), diametr bilan emas.
        Masalan Ø710 uchun katalogda faqat `ДР710` (deflektor) chiqadi —
        va u KP ga asosiy uskuna bo'lib tushib qolgan edi.
        Shuning uchun endi har model YONIDA uning TURI ko'rsatiladi va
        ventilyator alohida tanlanishi kerakligi ochiq aytiladi.
        """
        if not diametrlar:
            return []
        try:
            mahsulotlar = await self.api.mahsulotlar()
        except ApiXatosi as xato:
            self.ogohlantirish = f"katalogga ulanib bo'lmadi ({xato})"
            return []

        natija: list[dict[str, Any]] = []
        for diametr in diametrlar:
            andoza = re.compile(rf"(?<!\d){diametr}(?!\d)")
            topilgan: list[dict[str, str]] = []
            for mahsulot in mahsulotlar:
                turi = mahsulot_qisqa(mahsulot)["nomi"]
                for model in mahsulot.get("models") or []:
                    nomi = str(model.get("name") or "")
                    if andoza.search(nomi) and not any(
                        t["model"] == nomi for t in topilgan
                    ):
                        topilgan.append({"model": nomi, "turi": turi})
                    if len(topilgan) >= MAKS_MODEL:
                        break
                if len(topilgan) >= MAKS_MODEL:
                    break
            natija.append({
                "diametr": diametr,
                "modellar": [t["model"] for t in topilgan],
                "turlari": topilgan,
            })
        return natija

    async def _ventilyatorlar(
        self, kerakli_sarf: float, tarmoq_turi: str = "kanalli",
    ) -> list[dict[str, Any]]:
        """Havo sarfi bo'yicha mos ventilyatorlar — HISOBDAN, taxminan emas.

        Backendda havo sarfi maydoni yo'q, lekin u mahsulotning texnik
        jadvalida bor (`integrations/texnik.py`). Shu jadvaldan o'qilgan
        raqamga tayanamiz — model hech narsa taxmin qilmaydi.

        Tanlash qoidasi: sarfi YETADIGANLARIDAN eng kichiklari. Aks holda
        8000 m³/soat kerak bo'lgan omborga 63000 m³/soat lik markaziy
        qurilma tushib qoladi.
        """
        if kerakli_sarf <= 0:
            return []
        try:
            parametrlar = await self.api.texnik_parametrlar()
        except Exception as xato:  # kesh/tarmoq — hisob to'xtamasin
            log.warning("texnik parametrlar olinmadi: %s", xato)
            return []

        # BOSIM — sarf bilan teng darajada muhim.
        #
        # Ventilyator o'z tavsifi tizim tavsifi bilan kesishgan
        # nuqtada ishlaydi. Sarfi yetadigan, lekin bosimi yetmaydigan
        # ventilyator "ishlaydi, lekin havo bermaydi" holatini beradi.
        # Jonli misol: ВО 12-300-6,3 sarfi 10 000 m³/soat, bosimi
        # atigi 95 Pa — kanalli tizimga umuman yaramaydi.
        #
        # Tarmoq sxemasi bizda yo'q, shuning uchun TIPIK oraliq
        # olinadi va bu taxmin ekani natijada ochiq aytiladi.
        oraliq = tipik_bosim(tarmoq_turi) or tipik_bosim("kanalli")
        kerakli_bosim = float(oraliq[0])

        nomzodlar: list[dict[str, Any]] = []
        for nomi, malumot in parametrlar.items():
            turi = str(malumot.get("turi") or "")
            if not VENTILYATOR_TURI.search(turi):
                continue
            sarf = malumot.get("havo_sarfi")
            eng_kop = sarf[1] if isinstance(sarf, list) else sarf
            if not isinstance(eng_kop, (int, float)) or eng_kop < kerakli_sarf:
                continue
            bosim = malumot.get("bosim")
            # `None` — katalogda bosim yo'q. Bu "yaramaydi" degani
            # EMAS: ma'lumot yo'qligi uchun modelni tashlab bo'lmaydi.
            bosim_yetadi = yetadimi(bosim, kerakli_bosim)
            nomzodlar.append({
                "model": nomi,
                "turi": turi,
                "havo_sarfi": sarf,
                "bosim": bosim,
                "bosim_yetadi": bosim_yetadi,
                "zaxira_foiz": round(100 * (eng_kop - kerakli_sarf) / kerakli_sarf),
            })

        # Avval bosimi yetadiganlar, keyin noma'lumlar, oxirida
        # yetmaydiganlar. Har guruh ichida zaxirasi kichigi birinchi.
        tartib = {True: 0, None: 1, False: 2}
        nomzodlar.sort(key=lambda x: (tartib[x["bosim_yetadi"]], x["zaxira_foiz"]))

        # Bir o'lchamdagi g'ildirakning barcha dvigatel variantlari bir xil
        # havo sarfini beradi (ВЦ 14-46-5-1 … -5-5). Ro'yxatda ularning
        # bittasi yetadi — menejerga 6 ta bir xil qator kerak emas.
        korilgan: set[tuple[Any, ...]] = set()
        tanlangan: list[dict[str, Any]] = []
        for nomzod in nomzodlar:
            belgi = (nomzod["turi"], str(nomzod["havo_sarfi"]), str(nomzod["bosim"]))
            if belgi in korilgan:
                continue
            korilgan.add(belgi)
            tanlangan.append(nomzod)
            if len(tanlangan) >= MAKS_VENTILYATOR:
                break
        return tanlangan

    # --- izoh ----------------------------------------------------------------

    @staticmethod
    def _izoh(xonalar: list[dict[str, Any]], jami: float, umumiy: Any) -> str:
        bolaklar = [f"{len(xonalar)} ta xona"]
        if jami:
            bolaklar.append(f"jami {jami:,.0f} m³/soat".replace(",", " "))
        if umumiy and umumiy.diametr:
            bolaklar.append(f"magistral Ø{umumiy.diametr} mm")
        return ", ".join(bolaklar)
