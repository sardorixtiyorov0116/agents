"""Tijorat menejeri Temur — `proposal-builder`.

Maqsad: mijoz so'roviga rasmiy tijorat taklifi (KP) tayyorlaydi va Word/PDF
hujjat chiqaradi.

O'ZGARMAS QOIDALAR (kodda ta'minlangan, promptda emas):
  - narx FAQAT `knowledge/sales/narxlar.yaml` dan olinadi; model qaytargan
    narx e'tiborga olinmaydi — shuning uchun narx to'qib bo'lmaydi;
  - narx topilmasa qator BO'SH qoladi va ogohlantirish qo'shiladi;
  - KP raqami bazadan olinadi va takrorlanmaydi;
  - KP har doim inson tasdig'idan o'tadi (`tasdiq_kerak=True`).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError

from bilim import kontekst_matni
from integrations import ApiXatosi, katalog_narxi, mahsulot_qisqa
from integrations.climavent_client import sap_kaliti
from kp import harf
from kp.qol_narx import narx_ajrat
from kp.shakldan import qqssiz
from kp import (
    KP,
    Mijoz,
    Qator,
    Shartlar,
    hujjatlarni_yasa,
    menejer_uchun,
    menejerlar,
    narxlar,
    rekvizitlar,
)

from ..config import sozlama
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
from app.kurs import joriy as kurs_joriy

log = logging.getLogger("temur")

MAKS_KATALOG = 8

# Menejer KP tilini so'rovda aytadi ("ruscha qilib ber"). Til KODDA
# aniqlanadi, chunki u modelning javobidan OLDIN kerak: katalog mahsulot
# nomlarini ham o'sha tilda olib kelishimiz shart.
#
# DIQQAT: "o'zbek" bo'lagi "O'zbekiston" ichida ham uchraydi ("O'zbekiston
# Temir Yo'llari uchun KP") — shuning uchun faqat to'liq shakllar sanaladi.
TIL_BELGILARI = {
    "uz": re.compile(
        r"o['`‘’]?zbekcha|uzbekcha|o['`‘’]?zbek tilida|uzbek tilida|узбекском|узбекски",
        re.IGNORECASE,
    ),
    "ru": re.compile(
        r"ruscha|rus tilida|русском|по-?русски|russian",
        re.IGNORECASE,
    ),
}


def til_aniqla(matn: str) -> str | None:
    """So'rovdagi til ko'rsatmasi (aytilmagan bo'lsa None)."""
    topilgan = [
        (til, mos.start())
        for til, andoza in TIL_BELGILARI.items()
        if (mos := andoza.search(matn or ""))
    ]
    if not topilgan:
        return None
    # Ikkalasi ham uchrasa — oxirgisi kuchda (menejer fikrini o'zgartirgan).
    return max(topilgan, key=lambda x: x[1])[0]

# KP pastidagi menejer bloki uchun savol. Bir marta so'raladi — javob
# bazaga saqlanadi va keyingi KP larda qayta so'ralmaydi.
TIL_SAVOLI = (
    "KP qaysi tilda tuzilsin — ruscha yoki o'zbekcha? "
    "(mijoz qaysi tilda o'qisa, o'shani yozing)"
)

MENEJER_SAVOLI = (
    "KP da qaysi savdo menejeri ko'rsatilsin? Ism-familiya va telefon "
    "raqamini yozing (masalan: Яхшибоев Бауржон +998 90 099 12 60)"
)

TIZIM_PROMPT = """Sen "Tijorat menejeri Temur" — rasmiy tijorat taklifi (KP)
tayyorlaydigan agentsan.

VAZIFAN: mijoz so'rovidan KP uchun ma'lumotni ajratib olish — mijoz kim,
qaysi mahsulot, qancha miqdor, qanday shartlar.

QAT'IY QOIDALAR:
1) NARX YOZMAYSAN. Narx tizim tomonidan narx ro'yxatidan olinadi. Sen
   `birlik_narx` maydonini umuman to'ldirmaysan — u e'tiborga olinmaydi.
   Narx haqida taxmin ham qilmaysan.
2) SPESIFIKATSIYANI O'YLAB TOPMAYSAN. Faqat topshiriqda berilgan yoki
   "ICHKI KATALOG" bo'limidagi ma'lumotdan olasan. Bilmasang — bo'sh qoldir.
   QISQA yozasan: eng muhim 2-3 parametr, bitta qatorga sig'sin (taxminan
   90 belgi). KP jadvalidagi katak kichik — to'liq texnik tavsif bu yerga
   emas, alohida hujjatga tegishli.
3) MAHSULOT KATALOGDA TOPILMASA — foydalanuvchi mahsulot nomini aniq aytgan
   bo'lsa, uni BARIBIR `qatorlar` ga kiritasan, lekin `katalogda_yoq: true`
   qo'yasan va nomini `topilmagan_mahsulotlar` ga ham yozasan. Katalogdagi
   o'xshashini `taklif_qilingan` ga qo'shasan.
   KP ni BEKOR QILMAYSAN: katalog ishlamayotgan bo'lishi ham mumkin, bu
   foydalanuvchining aybi emas. Nomi va miqdori aytilgan har mahsulot
   `qatorlar` da bo'lishi SHART.
   O'zingdan YANGI mahsulot o'ylab topmaysan — faqat aytilganini yozasan.
4) YETKAZISH MUDDATINI TAXMIN QILMAYSAN — aytilmagan bo'lsa bo'sh qoldir.
4a) MENEJERNI O'ZING TANLAMAYSAN. `menejer` ni faqat so'rovda aniq ism
   aytilgan bo'lsa to'ldirasan ("menejer Aziz Karimov"). Aks holda BO'SH
   qoldirasan — tizim uni o'zi aniqlaydi.
5) Mijoz ma'lumoti yetishmasa — `sorash_kerak` ga yozasan.
6) Miqdor ko'rsatilmagan bo'lsa 1 deb olasan va buni `sorash_kerak` ga yozasan.
7) TIL: `til` maydoni MIJOZ tili, sen bilan gaplashilgan til EMAS. Standart —
   "ru", chunki rasmiy KP hujjatlarimiz rus tilida chiqadi. "uz" ni faqat
   mijoz uchun o'zbekcha hujjat ANIQ so'ralganda qo'yasan.

SEN QILMAYDIGAN ISHLAR:
- Mijozga hech narsa YUBORMAYSAN — faqat hujjat tayyorlanadi.
- Chegirma bermaysan va narx belgilamaysan.
- Shartnoma tuzmaysan (bu Yurist Lazizning ishi).
- Savdo strategiyasi yozmaysan (bu Savdo strategi Bekzodning ishi).

Javobni faqat so'ralgan JSON sxemasi bo'yicha ber."""

JSON_SKELET = """Javobni FAQAT quyidagi shakldagi JSON obyekti bilan ber, boshqa matn yozmasdan:
{
  "mijoz": {"nomi": "matn", "aloqa": "matn", "manzil": "matn"},
  "til": "ru (standart) | uz (faqat aniq so'ralganda)",
  "qatorlar": [
    {"nomi": "mahsulot nomi", "spetsifikatsiya": "matn yoki bo'sh",
     "miqdor": 1, "birlik": "dona", "katalogda_yoq": true/false, "izoh": "matn"}
  ],
  "topilmagan_mahsulotlar": ["katalogda yo'q mahsulot"],
  "taklif_qilingan": ["o'rniga taklif qilingan katalog mahsuloti"],
  "menejer": "so'rovda ANIQ aytilgan menejer ismi, aks holda bo'sh",
  "yetkazish": "aytilgan bo'lsa matn, aks holda bo'sh",
  "maxsus_shartlar": ["o'rnatish, kafolat va h.k."],
  "sorash_kerak": ["mijozdan aniqlashtirish kerak bo'lgan narsa"]
}"""


class TemurMijoz(BaseModel):
    nomi: str = ""
    aloqa: str = ""
    manzil: str = ""


class TemurQator(BaseModel):
    nomi: str
    spetsifikatsiya: str = ""
    miqdor: float = 1
    birlik: str = "dona"
    # Katalogda tasdiqlanmagan (topilmadi yoki katalog ishlamadi).
    katalogda_yoq: bool = False
    izoh: str = ""


class TemurNatija(BaseModel):
    """Modelning javobi. Narx maydoni ATAYLAB yo'q."""

    mijoz: TemurMijoz = Field(default_factory=TemurMijoz)
    til: str = "uz"
    qatorlar: list[TemurQator] = Field(default_factory=list)
    topilmagan_mahsulotlar: list[str] = Field(default_factory=list)
    taklif_qilingan: list[str] = Field(default_factory=list)
    menejer: str = ""
    yetkazish: str = ""
    maxsus_shartlar: list[str] = Field(default_factory=list)
    sorash_kerak: list[str] = Field(default_factory=list)


# Muhandis tavsifidan promptga tushadigan xona va model soni.
MAKS_XONA_TAVSIF = 6
MAKS_TAVSIYA = 8

# Yangi KP so'ralayotganini bildiruvchi belgilar. Bular bo'lsa bu
# tahrir emas — obyekt tasvirlangan, demak KP boshidan tuziladi.
YANGI_OBYEKT = re.compile(
    r"kv\s*metr|kv\.m|m²|м²|kvadrat|balandlig|высот|"
    r"ombor|omborxona|sex|ofis|oshxona|do'kon|склад|цех|офис",
    re.IGNORECASE,
)


def _sanab(nomlar: list[str], maks: int = 3) -> str:
    """Nomlarni sanaydi; ko'p bo'lsa "va yana N ta" deb yakunlaydi.

    Ilgari shunchaki `[:3]` olinardi — natijada "4 ta pozitsiyada narx
    yo'q (uchta nom)" degan chalg'ituvchi gap chiqardi.
    """
    if len(nomlar) <= maks:
        return ", ".join(nomlar)
    qolgani = len(nomlar) - maks
    return ", ".join(nomlar[:maks]) + f" va yana {qolgani} ta"


def _oraliq(qiymat: Any) -> str:
    """`8000` yoki `[4200, 13100]` ni o'qiladigan matnga aylantiradi."""
    if isinstance(qiymat, (list, tuple)) and len(qiymat) == 2:
        if qiymat[0] == qiymat[1]:
            return f"{qiymat[1]:,.0f}".replace(",", " ")
        return (f"{qiymat[0]:,.0f}–{qiymat[1]:,.0f}").replace(",", " ")
    if isinstance(qiymat, (int, float)):
        return f"{qiymat:,.0f}".replace(",", " ")
    return str(qiymat)


def _kurs_izohi(til: str) -> str:
    """Narx dollardan hisoblangani va qaysi kursda ekani — mijoz uchun."""
    kurs = f"{kurs_joriy():,.0f}".replace(",", " ")
    bugun = date.today().strftime("%d.%m.%Y")
    if til == "ru":
        return (f"*Цены рассчитаны по курсу {kurs} сум/доллар "
                f"(на {bugun}).")
    return (f"*Narxlar {kurs} so'm/dollar kursida hisoblangan "
            f"({bugun} holatiga).")


def _nom_boyicha_qol_narx(qol, nomi: str) -> float | None:
    """Menejer NOM bilan aytgan narx.

    Nomlar aynan mos kelmasligi mumkin ("ВК-315С" va "Вентилятор
    ВК-315С"), shuning uchun ajratuvchi belgilarsiz solishtiriladi.
    """
    kalit = sap_kaliti(nomi)
    if not kalit:
        return None
    for aytilgan, narx in qol.nom_boyicha.items():
        aytilgan_kalit = sap_kaliti(aytilgan)
        if aytilgan_kalit and (aytilgan_kalit in kalit or kalit in aytilgan_kalit):
            return narx
    return None


class TijoratMenejeri(Agent):
    """Tijorat menejeri Temur."""

    def __init__(self, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self._topilmalar: list = []
        self._katalog: list[dict[str, Any]] = []
        self._kontekst: dict[str, Any] = {}
        self._til = "ru"

    async def ishla(self, vazifa: str, kontekst: dict[str, Any] | None = None) -> Konvert:
        self.ogohlantirish = ""
        kontekst = kontekst or {}
        self._kontekst = kontekst

        # "1-tovarga 5 mln" — oxirgi KP ni tahrirlash. Modelga bormaydi.
        tahrir = await self._narx_tahriri()
        if tahrir is not None:
            return tahrir

        topshiriq = self.topshiriq_matni(vazifa, kontekst)

        # Shablonlar, standart shartlar — bilim bazasidan.
        self._topilmalar = self.bilimni_qidir(vazifa)
        if self._topilmalar:
            topshiriq += "\n\n" + kontekst_matni(self._topilmalar)

        # Til modelning javobidan OLDIN kerak: katalog nomlari ham shu
        # tilda olinadi.
        #
        # Aytilmagan bo'lsa TAXMIN QILMAYMIZ — so'raymiz. Hujjat mijozga
        # ketadi va noto'g'ri tilda chiqsa, uni qaytadan tuzishga to'g'ri
        # keladi. Bir savol — bir marta.
        # Router `vazifa` ni qayta yozganda til ko'rsatmasi yo'qolishi
        # mumkin — shuning uchun ASL so'rovga ham qaraymiz.
        asl = str((kontekst or {}).get("asl_sorov") or "")
        aytilgan = til_aniqla(vazifa) or til_aniqla(asl)

        # BIR MARTA so'raymiz. Menejer kuniga bir necha KP tuzadi —
        # har safar "ruscha" deb yozishi kerak bo'lsa, tizim bezovta
        # qiluvchi bo'lib qoladi.
        tg_id = kontekst.get("telegram_id")
        if aytilgan is None and tg_id is not None:
            try:
                saqlangan = await self.baza.foydalanuvchi_sozlamasi(tg_id)
            except Exception:
                saqlangan = None
            if saqlangan and saqlangan.get("kp_tili") in ("uz", "ru"):
                aytilgan = saqlangan["kp_tili"]
        elif aytilgan is not None and tg_id is not None:
            try:
                await self.baza.sozlama_yoz(tg_id, aytilgan)
            except Exception:
                pass

        if aytilgan is None:
            return aniqlik_kerak_konvert(
                [TIL_SAVOLI],
                "KP qaysi tilda tuzilishi aytilmagan.",
                kim=self.rol,
            ).model_copy(update={"natija": {"savollar": [TIL_SAVOLI], "kerak": "til"}})
        self._til = aytilgan
        # MUHANDIS TAVSIYASI — katalogdan oldin turadi.
        #
        # Rustam hisobdan chiqib mos diametrdagi uskunalarni allaqachon
        # tanlagan. Temur uni e'tiborsiz qoldirib o'zi qidirsa, natija
        # yomon chiqadi: 800 m² omborga SHAXTA ventilyatori yoki
        # deflektor tushib qolgan edi.
        topshiriq += self._muhandis_tavsiyasi()
        topshiriq += await self._katalog_matni(vazifa)
        topshiriq += (
            f"\n\nHUJJAT TILI: {self._til}. `nomi` va `spetsifikatsiya` ni "
            f"AYNAN shu tilda yoz. Katalogdagi nom allaqachon shu tilda "
            f"berilgan — uni o'zgartirmasdan ko'chir. "
            f"`til` maydoniga ham '{self._til}' yoz."
        )

        try:
            javob = await self.modelga_sorov(
                topshiriq=topshiriq,
                tizim_prompt=TIZIM_PROMPT,
                natija_modeli=TemurNatija,
                json_skelet=JSON_SKELET,
            )
        except anthropic.APIError as xato:
            return xato_konvert(self.rol, llm_xato_matni(xato))

        if getattr(javob, "stop_reason", None) == "refusal":
            return xato_konvert(
                self.rol, "Model so'rovni bajarishdan bosh tortdi (xavfsizlik siyosati)."
            )

        try:
            natija = TemurNatija.model_validate(json_ajrat(matn_yig(javob)))
        except (ValueError, ValidationError) as xato:
            return xato_konvert(self.rol, f"Javobni o'qib bo'lmadi: {xato}")

        if not natija.qatorlar:
            # Hech qanday mahsulot nomi aytilmagan — bu chindan aniqlashtirish
            # holati, xato emas: foydalanuvchi bitta savolga javob bersa bo'ldi.
            return aniqlik_kerak_konvert(
                natija.sorash_kerak
                or ["Qaysi mahsulot va qancha miqdorda kerak?"],
                "KP tuzish uchun mahsulot nomi kerak.",
                kim=self.rol,
            )

        # Menejer bloki mijozga ketadigan hujjatda turadi — noto'g'ri odamning
        # nomi bilan chiqmasligi uchun bilmasak SO'RAYMIZ, taxmin qilmaymiz.
        menejer = await self._menejer_aniqla(natija.menejer)
        if menejer is None:
            return aniqlik_kerak_konvert(
                [MENEJER_SAVOLI],
                "KP da ko'rsatiladigan savdo menejeri aniqlanmadi.",
                kim=self.rol,
            ).model_copy(update={"natija": {"savollar": [MENEJER_SAVOLI], "kerak": "menejer"}})

        return await self._kp_yasa(natija, menejer)

    # --- ichki katalog -------------------------------------------------------

    def _muhandis_tavsiyasi(self) -> str:
        """Oldingi agent (Rustam) tanlagan uskunalar.

        Bu ro'yxat hisobga asoslangan — diametr, havo sarfi va xona turi
        hisobga olingan. Katalogdan ko'r-ko'rona qidirishdan ancha
        ishonchli.
        """
        kontekst = self._kontekst or {}
        # Zanjir Rustam → Sardor → Temur bo'lsa, `oldingi_natija` — Sardorniki.
        # Rustamning hisobi zanjir xotirasida turadi.
        zanjir = kontekst.get("zanjir_natijalari") or {}
        oldingi = zanjir.get("hvac-calc") if isinstance(zanjir, dict) else None
        if not isinstance(oldingi, dict) or not oldingi:
            oldingi = kontekst.get("oldingi_natija") or {}
        if not isinstance(oldingi, dict):
            return ""

        uskunalar = oldingi.get("uskunalar") or []
        xonalar = oldingi.get("xonalar") or []
        ventilyatorlar = oldingi.get("ventilyatorlar") or []
        if not uskunalar and not xonalar and not ventilyatorlar:
            return ""

        qatorlar = ["\n\nMUHANDIS HISOBI (Rustam) — BIRLAMCHI ASOS:"]
        for xona in xonalar[:MAKS_XONA_TAVSIF]:
            if not isinstance(xona, dict):
                continue
            qatorlar.append(
                f"- {xona.get('nomi')}: {xona.get('maydon')} m² × "
                f"{xona.get('balandlik')} m, havo sarfi "
                f"{xona.get('havo_sarfi')} m³/soat, kanal Ø{xona.get('diametr')} mm"
            )

        # VENTILYATOR — havo sarfi bo'yicha tanlangan, hisobga to'g'ri
        # keladigan yagona ro'yxat. Shuning uchun u birinchi turadi.
        if ventilyatorlar:
            qatorlar.append(
                "\nVENTILYATOR — havo sarfi bo'yicha tanlangan "
                "(katalog texnik jadvalidan o'qilgan):"
            )
            for v in ventilyatorlar[:MAKS_TAVSIYA]:
                if not isinstance(v, dict):
                    continue
                bolaklar = [f"    {v.get('model')} — {v.get('turi')}"]
                if v.get("havo_sarfi") is not None:
                    bolaklar.append(f"{_oraliq(v['havo_sarfi'])} m³/soat")
                if v.get("bosim") is not None:
                    bolaklar.append(f"{_oraliq(v['bosim'])} Pa")
                if v.get("zaxira_foiz") is not None:
                    bolaklar.append(f"zaxira +{v['zaxira_foiz']}%")
                # BOSIM — sarf bilan teng darajada muhim. Sarfi
                # yetadigan, lekin bosimi yetmaydigan ventilyator
                # o'rnatilsa havo bermaydi.
                if v.get("bosim_yetadi") is False:
                    bolaklar.append("⚠️ BOSIMI YETMAYDI")
                elif v.get("bosim_yetadi") is None and v.get("bosim") is None:
                    bolaklar.append("bosimi katalogda yo'q")
                qatorlar.append(", ".join(bolaklar))
            # JONLI XATO (2026-08-11): Temur ro'yxatdagi 3 ta ventilyatorni
            # KP ga UCHTA alohida qator qilib qo'ydi. Mijoz bitta ombor
            # uchun uchta ventilyator sotib olmaydi — bular VARIANT.
            qatorlar.append(
                "    Ro'yxat BOSIM bo'yicha tartiblangan: bosimi yetadiganlar "
                "yuqorida. \"BOSIMI YETMAYDI\" belgisi bo'lganini ASOSIY "
                "uskuna qilib qo'yma — u o'rnatilsa havo bermaydi."
            )
            qatorlar.append(
                "    BULAR — BIR-BIRINING O'RNINI BOSUVCHI VARIANTLAR, "
                "ro'yxat emas. KP ga FAQAT BITTASINI qator qilib qo'y — "
                "birinchisini (ortiqcha zaxirasi eng kam). Qolganlarini "
                "`taklif_qilingan` ga yoz, `qatorlar` ga EMAS."
            )

        tavsiya_bor = False
        for u in uskunalar:
            if not isinstance(u, dict) or not u.get("modellar"):
                continue
            tavsiya_bor = True
            qatorlar.append(f"- Ø{u['diametr']} uchun katalogdagi modellar:")
            turlari = u.get("turlari") or []
            if turlari:
                for t in turlari[:MAKS_TAVSIYA]:
                    qatorlar.append(f"    {t.get('model')} — {t.get('turi')}")
            else:
                qatorlar.append(
                    "    " + ", ".join(str(m) for m in u["modellar"][:MAKS_TAVSIYA])
                )

        qatorlar.append(
            "\nQATORLARNI SHU RO'YXATDAN tuz — u hisobga asoslangan."
            if tavsiya_bor
            else "\nHisobdagi diametrga mos model topilmadi."
        )

        # DIAMETR ro'yxati — bu KANAL AKSESSUARLARI (deflektor, isitgich,
        # klapan). Ventilyator g'ildirak nomeri bilan ataladi (ВЦ 4-75-8),
        # shuning uchun u bu ro'yxatga tushmaydi. Aynan shu sababli
        # 800 m² omborga DEFLEKTOR asosiy uskuna bo'lib qolgan edi.
        qatorlar.append(
            "\nDIQQAT: yuqoridagi DIAMETR ro'yxati — kanal aksessuarlari "
            "(deflektor, isitgich, klapan). Ventilyatorni diametr bilan "
            "tanlab bo'lmaydi."
        )
        qatorlar.append(
            "Ventilyatorni VENTILYATOR ro'yxatidan ol."
            if ventilyatorlar
            else "Bu hisob uchun mos ventilyator topilmadi — aksessuarni "
                 "asosiy uskuna qilib qo'yma. `sorash_kerak` ga "
                 "\"ventilyator modelini muhandis havo sarfi bo'yicha "
                 "tanlasin\" deb yoz."
        )
        # Obyekt turiga mos bo'lmagan maxsus uskuna tanlanmasin.
        # Jonli sinovda 800 m² OMBORGA "шахтный вентилятор" (kon-shaxta
        # uskunasi) tanlangan edi — katalogda u shunchaki "ventilyator"
        # so'ziga mos kelgani uchun.
        qatorlar.append(
            "OBYEKT TURIGA QARA: bu ombor/ofis/sex bo'lsa, MAXSUS sanoat "
            "uskunasini (shaxta, kon-qazib olish, aspiratsiya, chang "
            "ventilyatori) tanlama — mijoz uni ANIQ so'ramagan bo'lsa. "
            "Ular boshqa sharoit uchun mo'ljallangan."
        )
        return "\n".join(qatorlar)

    async def _katalog_matni(self, vazifa: str) -> str:
        try:
            self._katalog = await self.api.qidir_keng(vazifa)
        except ApiXatosi as xato:
            # Katalog ishlamayapti — bu foydalanuvchining aybi emas.
            # KP baribir tuziladi, faqat "tasdiqlanmagan" deb belgilanadi.
            self.ogohlantirish = f"katalogga ulanib bo'lmadi ({xato})"
            return (
                "\n\nICHKI KATALOG: HOZIR ISHLAMAYAPTI (texnik nosozlik). "
                "KP ni BARIBIR tuz. Foydalanuvchi aytgan mahsulot nomini "
                "o'zgartirmasdan `qatorlar` ga yoz va `katalogda_yoq: true` qo'y. "
                "Spesifikatsiyani o'ylab topma."
            )

        if not self._katalog:
            return (
                "\n\nICHKI KATALOG: bu nom bo'yicha mos mahsulot topilmadi. "
                "KP ni BARIBIR tuz: foydalanuvchi aytgan nomni `qatorlar` ga yoz, "
                "`katalogda_yoq: true` qo'y va nomini `topilmagan_mahsulotlar` ga "
                "ham qo'sh."
            )

        qatorlar = []
        for mahsulot in self._katalog[:MAKS_KATALOG]:
            qisqa = mahsulot_qisqa(mahsulot, self._til)
            modellar = ", ".join(m for m in qisqa["modellar"] if m)
            qatorlar.append(
                f"- {qisqa['nomi']} ({qisqa['kategoriya']})"
                + (f" — modellar: {modellar}" if modellar else "")
            )
        return (
            f"\n\nICHKI KATALOG ({len(self._katalog)} ta mos mahsulot):\n"
            + "\n".join(qatorlar)
            + "\nFaqat shu ro'yxatdagi mahsulotni KP ga kirit."
        )

    # --- menejer -------------------------------------------------------------

    async def _menejer_aniqla(self, sorovdagi: str) -> dict[str, str] | None:
        """KP pastida kim turishini aniqlaydi (topilmasa — None).

        Tartib:
          1) so'rovda aniq aytilgan ism ("menejer Aziz Karimov");
          2) bazada saqlangan — foydalanuvchidan BIR MARTA so'ralgan javob;
          3) `rekvizitlar.yaml` dagi oldindan yozilgan ro'yxat.

        Uchalasi ham bo'sh bo'lsa `None` qaytadi va agent foydalanuvchidan
        so'raydi — standart nomni jimgina qo'yib yubormaydi, chunki KP
        mijozga ketadigan rasmiy hujjat.
        """
        tg_id = self._kontekst.get("telegram_id")

        if sorovdagi.strip():
            ism = sorovdagi.strip()
            # Telefon ismga bog'liq: boshqa odamning raqami qolib ketmasin.
            saqlangan = await self.baza.menejer(tg_id) if tg_id is not None else None
            if saqlangan and saqlangan["ism"] == ism:
                return self._yozuv_bilan(ism, saqlangan["telefon"])
            mos = next((m for m in menejerlar().values() if m["ism"] == ism), None)
            return self._yozuv_bilan(ism, mos["telefon"] if mos else "")

        if tg_id is not None:
            saqlangan = await self.baza.menejer(tg_id)
            if saqlangan:
                return self._yozuv_bilan(saqlangan["ism"], saqlangan["telefon"])

        xodim = menejer_uchun(tg_id)
        if xodim:
            return dict(xodim)
        return None

    @staticmethod
    def _yozuv_bilan(ism: str, telefon: str) -> dict[str, str]:
        """Ismga `rekvizitlar.yaml` dagi kirill/lotin variantini qo'shadi.

        Ism bazadan yoki so'rovdan kelganda ro'yxatdagi qo'shimcha
        maydonlar tushib qolardi va KP da avtomatik o'girish ishlab
        ketardi — pasportdagi yozuvni bosib.
        """
        yozuv = {"ism": ism, "telefon": telefon}
        mos = next((m for m in menejerlar().values() if m["ism"] == ism), None)
        if mos:
            for kalit in ("ism_kiril", "ism_lotin"):
                if mos.get(kalit):
                    yozuv[kalit] = mos[kalit]
        return yozuv

    # --- narx manbalari ------------------------------------------------------

    async def _sap_kodi(self, nom: str) -> str:
        """Model nomiga mos rasmiy SAP kodi (topilmasa bo'sh matn)."""
        try:
            return await self.api.sap_kodi(nom)
        except ApiXatosi:
            return ""

    async def _backend_narxi(self, nom: str) -> tuple[float, str] | None:
        """Backenddagi narx. API ishlamasa — None (KP baribir tuziladi)."""
        try:
            return await self.api.model_narxi(nom)
        except ApiXatosi:
            return katalog_narxi(self._katalog, nom)

    # --- KP yig'ish ----------------------------------------------------------

    @staticmethod
    def _kp_natijasi(kp: KP, fayllar: dict) -> dict[str, Any]:
        """KP ni konvert `natija` shakliga keltiradi.

        Ikki joyda ishlatiladi: yangi KP tuzilganda va narx tahrirlanganda —
        shakl bir xil bo'lishi shart, aks holda presenter chalkashadi.
        """
        return {
            "raqam": kp.raqam,
            "sana": kp.sana.isoformat(),
            "mijoz": kp.mijoz.model_dump(),
            "qatorlar": [
                {
                    "nomi": q.nomi,
                    "spetsifikatsiya": q.spetsifikatsiya,
                    "miqdor": q.miqdor,
                    "birlik": q.birlik,
                    "birlik_narx": q.birlik_narx,
                    "jami": q.jami,
                    "narx_sanasi": q.narx_sanasi,
                }
                for q in kp.qatorlar
            ],
            "summa": kp.summa,
            "qqs": kp.qqs,
            "jami": kp.jami,
            "valyuta": kp.valyuta,
            "toliq_narxmi": kp.toliq_narxmi,
            "til": kp.til,
            "ogohlantirishlar": list(kp.ogohlantirishlar),
            "fayllar": {tur: str(yol) for tur, yol in fayllar.items()},
        }

    async def _kpni_saqla(self, kp: KP) -> None:
        """Oxirgi KP ni tahrirlash uchun saqlaydi."""
        tg_id = (self._kontekst or {}).get("telegram_id")
        if tg_id is None:
            return
        try:
            await self.baza.oxirgi_kp_yoz(
                tg_id, kp.raqam, json.dumps(kp.saqlash_uchun(), ensure_ascii=False)
            )
        except Exception:
            # Saqlanmasa KP baribir tayyor, faqat keyin tahrirlab
            # bo'lmaydi — sababini bilish uchun logga yozamiz.
            log.exception("oxirgi KP saqlanmadi: %s", kp.raqam)

    async def _narx_tahriri(self) -> Konvert | None:
        """"1-tovarga 5 mln" — oxirgi KP ni tahrirlaydi.

        MODELGA UMUMAN BORMAYDI. Sabab: qatorlar va raqam allaqachon
        ma'lum, faqat narx qo'yiladi. Modelga yuborilsa, u KP ni
        boshidan tuzardi — yangi raqam, boshqa mahsulotlar va
        "Mahsulot №2 (nomi ko'rsatilmagan)" kabi qatorlar chiqardi.
        Aynan shunday bo'lgan edi.

        Mos kelmasa `None` qaytaradi va oddiy yo'l davom etadi.
        """
        kontekst = self._kontekst or {}
        tg_id = kontekst.get("telegram_id")
        if tg_id is None:
            return None

        # AYNAN oxirgi xabarga qaraymiz. `asl_sorov` da suhbat xotirasi
        # tufayli eski so'rov ham turadi ("...800 kv metr ombor...") va
        # unga qarasak, tahrir har safar "yangi KP" bo'lib ko'rinardi.
        yangi = str(kontekst.get("yangi_xabar") or kontekst.get("asl_sorov") or "")
        qol = narx_ajrat(yangi)
        if not qol.bormi or YANGI_OBYEKT.search(yangi):
            return None      # yangi KP so'ralyapti, tahrir emas

        try:
            saqlangan = await self.baza.oxirgi_kp(tg_id)
            if not saqlangan:
                return None
            kp = KP.tikla(json.loads(saqlangan["malumot"]))
        except Exception:
            return None

        ozgargan: list[str] = []
        for tartib, qator in enumerate(kp.qatorlar, start=1):
            narx = qol.tartib_boyicha.get(tartib)
            if narx is None:
                narx = _nom_boyicha_qol_narx(qol, qator.nomi)
            if narx is not None:
                qator.birlik_narx = narx
                qator.narx_sanasi = date.today().isoformat()
                ozgargan.append(f"{tartib}. {qator.nomi}")

        if not ozgargan:
            return None

        kp.ogohlantirishlar = [
            o for o in kp.ogohlantirishlar if "narx yo'q" not in o
        ]
        kp.ogohlantirishlar.append(
            f"{len(ozgargan)} ta narx MENEJER tomonidan qo'lda kiritildi "
            "— katalogga ham kiritilsin"
        )
        narxsiz = [q.nomi for q in kp.qatorlar if q.birlik_narx is None]
        if narxsiz:
            kp.ogohlantirishlar.append(
                f"{len(narxsiz)} ta pozitsiyada narx hamon yo'q "
                f"({_sanab(narxsiz)}) — buxgalteriyadan so'ralsin"
            )

        try:
            fayllar = hujjatlarni_yasa(kp, sozlama().kp_papkasi)
        except Exception as xato:
            self.ogohlantirish = f"hujjat yaratilmadi: {xato}"
            fayllar = {}

        await self._kpni_saqla(kp)
        try:
            await self.baza.kp_kuzatuv_yoz(
                kp.raqam, kp.mijoz.nomi or None, kp.jami,
                yaratildi=kp.sana.isoformat(),
            )
        except Exception:
            pass

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=self._kp_natijasi(kp, fayllar),
            manba=[Manba(tur="menejer", nom="menejer qo'lda kiritgan narx")],
            ishonch=Ishonch.YUQORI,
            tasdiq_kerak=True,
            izoh=f"KP {kp.raqam} yangilandi: {', '.join(ozgargan[:3])}",
        )

    def _muhandis_tasdigi(self, natija: TemurNatija) -> None:
        """Muhandis ro'yxatidagi model — katalogda BOR.

        Temurning o'z katalog qidiruvi so'rov matni bo'yicha ishlaydi va
        model kodini topmasligi mumkin. Shunda u ДР710 ni "katalogda yo'q"
        deb belgilab qo'yardi — vaholanki uni Rustam AYNAN katalogdan
        olgan edi. Natijada KP da yolg'on ogohlantirish chiqardi.

        Bu tekshiruv KODDA: model qaytargan belgiga emas, Rustamning
        ro'yxatiga tayanadi.
        """
        zanjir = (self._kontekst or {}).get("zanjir_natijalari") or {}
        hisob = zanjir.get("hvac-calc") if isinstance(zanjir, dict) else None
        if not isinstance(hisob, dict):
            return

        kalitlar = {
            kalit
            for uskuna in (hisob.get("uskunalar") or [])
            if isinstance(uskuna, dict)
            for model in (uskuna.get("modellar") or [])
            if (kalit := sap_kaliti(str(model)))
        }
        # Ventilyatorlar ham KATALOGDAN olingan — ular ham "topilmadi"
        # deb belgilanmasligi kerak.
        kalitlar |= {
            kalit
            for vent in (hisob.get("ventilyatorlar") or [])
            if isinstance(vent, dict)
            and (kalit := sap_kaliti(str(vent.get("model") or "")))
        }
        if not kalitlar:
            return

        def muhandisniki(nomi: str) -> bool:
            kalit = sap_kaliti(nomi)
            return bool(kalit) and any(k in kalit or kalit in k for k in kalitlar)

        for qator in natija.qatorlar:
            if qator.katalogda_yoq and muhandisniki(qator.nomi):
                qator.katalogda_yoq = False
        natija.topilmagan_mahsulotlar = [
            nom for nom in natija.topilmagan_mahsulotlar if not muhandisniki(nom)
        ]

    async def _kp_yasa(self, natija: TemurNatija, menejer: dict[str, str]) -> Konvert:
        royxat = narxlar()
        # Menejer so'rovda narx aytgan bo'lsa — u ENG USTUN manba.
        # Bu modelning taxmini emas: raqam foydalanuvchi matnidan kod
        # bilan ajratiladi (`kp/qol_narx.py`).
        qol = narx_ajrat(str((self._kontekst or {}).get("asl_sorov") or ""))
        qoldan: list[str] = []
        # So'rovda ANIQ aytilgan til ustun turadi: model uni "unutib"
        # qo'ysa ham hujjat menejer so'ragan tilda chiqadi.
        til = self._til if self._til in ("uz", "ru") else "ru"
        ogohlantirishlar: list[str] = []
        self._muhandis_tasdigi(natija)

        qatorlar: list[Qator] = []
        narxsiz: list[str] = []
        yamldan: list[str] = []
        sapsiz: list[str] = []
        # Backenddagi variant narxi DOLLARDA saqlanadi va kursga ko'paytiriladi.
        # Bunday narx ishlatilsa, kurs KP da OCHIQ yoziladi — mijoz raqam
        # qayerdan chiqqanini ko'rsin va kurs o'zgarganda bahs bo'lmasin.
        kursdan = False
        for xom in natija.qatorlar:
            # NARX HECH QACHON MODELDAN OLINMAYDI. Ikki manba, shu tartibda:
            #   1) Climavent backendi — birlamchi (sayt va KP bir xil narxni
            #      ko'rsatishi uchun);
            #   2) `narxlar.yaml` — zaxira, backendda narx bo'lmasa.
            narx_qiymati: float | None = None
            narx_sanasi = ""

            # 0) MENEJER AYTGAN NARX — hammasidan ustun. Inson buxgalteriyadan
            #    bilib aytgan raqam bazadagi eski qiymatdan ishonchliroq.
            tartib = len(qatorlar) + 1
            qol_narx = qol.tartib_boyicha.get(tartib)
            if qol_narx is None:
                qol_narx = _nom_boyicha_qol_narx(qol, xom.nomi)
            if qol_narx is not None:
                narx_qiymati = qol_narx
                narx_sanasi = date.today().isoformat()
                qoldan.append(xom.nomi)

            # Narx to'liq katalogdan qidiriladi, qidiruv natijasidan EMAS:
            # `/api/products/search` mahsulotni `models` massivisiz qaytaradi.
            backend = (
                None if narx_qiymati is not None
                else await self._backend_narxi(xom.nomi)
            )
            if backend is not None:
                # BACKEND NARXI QQS BILAN saqlanadi (buxgalteriya prays
                # faylining ustuni: «Цена USD с НДС»). KP jadvali esa
                # QQSsiz summa + alohida QQS qatoridan tuziladi, shuning
                # uchun QQS ajratib olinadi — aks holda ikki marta
                # hisoblanardi va KP 12% qimmat chiqardi.
                narx_qiymati = qqssiz(backend[0], royxat.qqs_foizi)
                narx_sanasi = date.today().isoformat()  # backend narxi — joriy
                # Menejer quvvatni aytmagan bo'lsa, bitta o'lchamda bir nechta
                # variant bor va biz eng arzonini olamiz. Buni JIM qilmaymiz:
                # `ВЦ 4-75 №2,5` da narx 156 dan 199 dollargacha farq qiladi.
                if " $ x " in backend[1]:
                    kursdan = True
                if "variantdan eng arzoni" in backend[1]:
                    ogohlantirishlar.append(
                        f"{xom.nomi}: {backend[1]} — quvvat aniq ko'rsatilsa "
                        f"narx boshqacha bo'ladi"
                    )

            if narx_qiymati is None:
                narx = royxat.top(xom.nomi)
                if narx is not None and narx.bormi:
                    narx_qiymati = narx.narx
                    narx_sanasi = narx.sana
                    yamldan.append(xom.nomi)
                elif narx is not None and narx.eskirgan and narx.narx > 0:
                    ogohlantirishlar.append(
                        f"{xom.nomi}: narx eskirgan ({narx.sana}) — ishlatilmadi"
                    )

            if narx_qiymati is None:
                narxsiz.append(xom.nomi)

            # Rasmiy SAP kodi — buxgalteriya shu kod bilan ishlaydi.
            # Topilmasa nom o'zgarmaydi: noto'g'ri kod yozgandan ko'ra
            # kodsiz chiqqani yaxshi.
            sap = await self._sap_kodi(xom.nomi)

            qatorlar.append(
                Qator(
                    nomi=sap or xom.nomi,
                    spetsifikatsiya=xom.spetsifikatsiya,
                    miqdor=xom.miqdor or 1,
                    birlik=xom.birlik or "dona",
                    birlik_narx=narx_qiymati,
                    narx_sanasi=narx_sanasi,
                    qqs_foizi=royxat.qqs_foizi,
                    izoh=xom.izoh,
                )
            )
            if not sap:
                sapsiz.append(xom.nomi)

        if qoldan:
            ogohlantirishlar.append(
                f"{len(qoldan)} ta narx MENEJER tomonidan qo'lda kiritildi "
                f"({', '.join(qoldan[:3])}) — katalogga ham kiritilsin"
            )

        if yamldan:
            ogohlantirishlar.append(
                "Narx backendda yo'q, narxlar.yaml dan olindi: "
                + ", ".join(yamldan[:3])
                + " — katalogga ham kiritilsin"
            )

        if narxsiz:
            ogohlantirishlar.append(
                # Narx buxgalteriyada: standart tovarniki SAP'da, nostandart
                # tovarniki esa har safar so'raladi. Shuning uchun "topilmadi"
                # emas, KIMDAN so'rash kerakligini yozamiz — menejer nima
                # qilishini bilsin.
                f"{len(narxsiz)} ta pozitsiyada narx yo'q "
                f"({_sanab(narxsiz)}) — buxgalteriyadan so'ralsin"
            )
        if sapsiz:
            # Mahsulot nomlari ATAYLAB takrorlanmaydi: ular yuqoridagi
            # "narx yo'q" ogohlantirishida allaqachon sanab o'tilgan.
            # Bir xil ro'yxatni uch marta o'qish foydasiz.
            ogohlantirishlar.append(
                f"{len(sapsiz)} ta qatorda rasmiy SAP kodi yo'q — "
                "katalog nomi ishlatildi"
            )
        tasdiqlanmagan = [x.nomi for x in natija.qatorlar if x.katalogda_yoq]
        if tasdiqlanmagan:
            ogohlantirishlar.append(
                "Katalogdan tasdiqlanmadi: " + _sanab(tasdiqlanmagan)
                + " — nom va spesifikatsiyani tekshiring"
            )
        elif natija.topilmagan_mahsulotlar:
            ogohlantirishlar.append(
                "Katalogda topilmadi: " + ", ".join(natija.topilmagan_mahsulotlar)
            )

        rekvizit = dict(rekvizitlar())
        # Ism KP tilidagi alifboda yoziladi: ruscha blankada kirill,
        # o'zbekchada lotin. `rekvizitlar.yaml` da `ism_kiril`/`ism_lotin`
        # yozilgan bo'lsa — o'girish qilinmaydi, o'sha ishlatiladi.
        rekvizit["menejer"] = harf.moslash(menejer["ism"], til, menejer)
        rekvizit["menejer_telefon"] = menejer["telefon"]

        raqam = await self.baza.kp_raqam_ol(
            mijoz=natija.mijoz.nomi or None,
            shakl=rekvizit.get("raqam_shakli") or "KP-{yil}-{tartib:04d}",
            boshlanish=int(rekvizit.get("raqam_boshlanishi") or 0),
        )

        shartlar_manbasi = royxat.shartlar
        kp = KP(
            raqam=raqam,
            sana=date.today(),
            mijoz=Mijoz(**natija.mijoz.model_dump()),
            qatorlar=qatorlar,
            shartlar=Shartlar(
                tolov=shartlar_manbasi.get("tolov", ""),
                # Yetkazish muddati taxmin qilinmaydi: aytilgani ishlatiladi.
                yetkazish=natija.yetkazish or shartlar_manbasi.get("yetkazish", ""),
                kafolat=shartlar_manbasi.get("kafolat", ""),
                amal_qilish_muddati=shartlar_manbasi.get("amal_qilish_muddati", ""),
                maxsus=natija.maxsus_shartlar,
            ),
            rekvizitlar=rekvizit,
            valyuta=royxat.valyuta,
            qqs_foizi=royxat.qqs_foizi,
            til=til,
            ogohlantirishlar=ogohlantirishlar,
            kirish_matni=royxat.kirish_matni(til),
            shartlar_matni=royxat.shartlar_matni(til) + (
                # `maxsus` hujjatda render QILINMAYDI — izoh shu yerga qo'yiladi,
                # chunki mijoz aynan shartlar matnini o'qiydi.
                [_kurs_izohi(til)] if kursdan else []
            ),
            narx_amal_oxiri=date.today() + timedelta(days=royxat.narx_amal_kuni),
        )

        try:
            fayllar = hujjatlarni_yasa(kp, sozlama().kp_papkasi)
        except Exception as xato:  # hujjat yozilmasa ham ma'lumot yo'qolmaydi
            self.ogohlantirish = f"hujjat yaratilmadi: {xato}"
            fayllar = {}

        # KP kuzatuvga tushadi — Aziza (kp-tracker) uning taqdirini
        # keyinchalik kuzatib boradi. Kuzatuvga tushmasa, tuzilgan taklif
        # unutilib ketadi.
        try:
            await self.baza.kp_kuzatuv_yoz(
                kp.raqam, natija.mijoz.nomi or None, kp.jami,
                yaratildi=kp.sana.isoformat(),
            )
        except Exception:  # kuzatuv yozilmasa ham KP tayyor
            self.ogohlantirish = (
                f"{self.ogohlantirish + '; ' if self.ogohlantirish else ''}"
                "KP kuzatuvga yozilmadi"
            )

        # KP ni TO'LIQ saqlaymiz: menejer keyin "1-tovarga 5 mln" desa,
        # o'sha KP ning aynan o'zi tahrirlanadi (yangisi tuzilmaydi).
        await self._kpni_saqla(kp)

        malumot = self._kp_natijasi(kp, fayllar)
        malumot.update({
            "topilmagan_mahsulotlar": natija.topilmagan_mahsulotlar,
            "taklif_qilingan": natija.taklif_qilingan,
            "sorash_kerak": natija.sorash_kerak,
        })

        return Konvert(
            kim=self.rol,
            holat=Holat.TUGADI,
            natija=malumot,
            manba=self._manbalarni_yig(),
            ishonch=Ishonch.YUQORI if kp.toliq_narxmi else Ishonch.ORTA,
            # Kontrakt: HAR DOIM — KP mijozga ketadigan rasmiy hujjat.
            tasdiq_kerak=True,
            izoh=self._izoh(kp, natija, fayllar),
        )

    def _manbalarni_yig(self) -> list[Manba]:
        manbalar: list[Manba] = list(self.bilim_manbalari(self._topilmalar))
        if self._katalog:
            manbalar.append(Manba(tur="ichki_api", nom="Climavent ichki katalogi"))
        manbalar.append(Manba(tur="bilim", nom="narxlar.yaml (narx ro'yxati)"))
        return manbalar

    def _izoh(self, kp: KP, natija: TemurNatija, fayllar: dict) -> str:
        bolaklar = [f"{kp.raqam} tayyorlandi ({len(kp.qatorlar)} ta pozitsiya)"]
        if kp.jami is not None:
            bolaklar.append(f"jami: {kp.pul(kp.jami)}")
        if not kp.toliq_narxmi:
            bolaklar.append(
                f"{len(kp.narxsiz_qatorlar)} ta pozitsiyada narx bo'sh — "
                f"buxgalteriyadan so'ralsin"
            )
        if natija.topilmagan_mahsulotlar:
            bolaklar.append("katalogda topilmadi: " + ", ".join(natija.topilmagan_mahsulotlar[:2]))
        if natija.sorash_kerak:
            bolaklar.append("aniqlashtirish: " + "; ".join(natija.sorash_kerak[:2]))
        if fayllar:
            bolaklar.append("hujjat: " + ", ".join(sorted(fayllar)))
        bolaklar.append("MIJOZGA YUBORILMADI — inson tasdig'i kerak")
        if self.ogohlantirish:
            bolaklar.append(self.ogohlantirish)
        return "; ".join(bolaklar)
