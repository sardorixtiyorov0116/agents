"""Shakl javoblaridan KP yig'ish — LLM CHAQIRILMAYDI.

Erkin matnli yo'lda (`app/agentlar/tijorat_menejeri.py`) model matnni
tushunishi kerak: qaysi mahsulot, qancha miqdor, qanaqa obyekt. Shu
sababli u sekin — o'lchandi, 80 soniya.

Shaklda esa javoblar TUZILGAN holda keladi. Ya'ni tushunish kerak emas:

  A) model ma'lum   -> narx qidiriladi, hujjat yasaladi   (~0,2 s)
  B) obyekt ma'lum  -> havo sarfi KODDA hisoblanadi       (2,8 ms)

TO'XTASH QOIDASI (eng muhimi): bu modul JIM QARO'R QILMAYDI.

  - Bitta o'lchamda bir nechta quvvat bo'lsa (`ВЦ 4-75 №2,5` da beshta,
    narxi 156 dan 199 dollargacha) — variantlar RO'YXATI qaytariladi va
    menejerdan so'raladi. Ilgari eng arzoni jim tanlanardi.
  - Narx topilmasa — qator BO'SH qoladi va oxirida ro'yxat qilinadi.
  - Uskuna topilmasa — o'ylab topilmaydi, ochiq aytiladi.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from hisob import (
    Xona,
    havo_sarfi,
    kanal_olchami,
    normalar,
    panjara_tanla,
    tipik_bosim,
    yetadimi,
)

from .model import KP, Mijoz, Qator, Shartlar
from .narx import narxlar, rekvizitlar

# Bitta o'lchamga shuncha variantdan ko'p to'g'ri kelsa, ro'yxat
# menejerni bosib ketadi. Eng mosini ko'rsatamiz.
MAKS_VARIANT = 6

# Ventilyator sig'imi kerakligidan shuncha foizgacha ortiq bo'lsa —
# bu MAQBUL zaxira. Muhandislikda 10-20% odatiy: u tarmoqdagi
# noaniqlikni (kanal uzunligi, ifloslanish) qoplaydi. Shu oraliqdagi
# modellar TEXNIK JIHATDAN TENG deb qaraladi.
MAQBUL_ZAXIRA = 0.30

# Bitta uskuna yetmasa parallel qo'yiladi. Shuncha donadan oshsa —
# kattaroq uskuna buyurtma qilish arzonroq bo'lishi mumkin, buni
# menejerga aytamiz.
MAKS_PARALLEL = 10

# Aniqlik tugmasi: markaziy qurilmadan tarqoq tizimga o'tish.
TARQOQQA_OT = "__tarqoq__"


# --- hujjat tili --------------------------------------------------------------
#
# JONLI E'TIROZ (2026-08-26): ruscha KP da o'lchov birligi «dona» bo'lib
# chiqardi — jadval sarlavhasi «Ед. изм», ichida esa o'zbekcha so'z.
# Mijozga ketadigan hujjatda ikki til aralashib turishi puxta ko'rinmaydi.
#
# Shuning uchun KP ga tushadigan HAR QANDAY matn shu yerdan olinadi.

# O'lchov birligi. Menejer qo'lda boshqacha yozsa (`kg`, `m`), u
# o'zgarmaydi — faqat «dona»/«шт» juftligi hujjat tiliga moslanadi.
BIRLIK = {"uz": "dona", "ru": "шт"}
DONA_BELGILARI = {"dona", "шт", "шт.", "dona.", "pcs"}

MATN = {
    "uz": {
        "sarf": "m³/soat",
        "kanal": "kanal Ø{d} mm",
        "bosim": "taxminiy bosim {a}-{b} Pa",
        "bosim_aniq": "bosim ~{b} Pa",
        "ikki_yonalish": "kirish va chiqish uchun",
        "sorish_tizimi": "so'rish tizimi",
        "panjara": "havo taqsimlash panjarasi",
        "jonli_kesim": "jonli kesim {y} m²",
        "tezlik": "tezlik {v} m/s",
        "tizim_uchun": "{sarf} m³/soat tizim uchun",
        "isitgich": "kanal isitgichi",
        "sovutgich": "kanal sovutgichi",
        "issiqlik_almashtirgich": "issiqlik almashtirgich",
        "shovqin": "shovqin pasaytirgich",
        "parallel": "{soni} dona parallel",
        "markaziy": "markaziy havo tayyorlash qurilmasi",
    },
    "ru": {
        "sarf": "м³/ч",
        "kanal": "канал Ø{d} мм",
        "bosim": "ориентировочное давление {a}-{b} Па",
        "bosim_aniq": "давление ~{b} Па",
        "ikki_yonalish": "на приток и вытяжку",
        "sorish_tizimi": "вытяжная система",
        "panjara": "решётка воздухораспределительная",
        "jonli_kesim": "живое сечение {y} м²",
        "tezlik": "скорость {v} м/с",
        "tizim_uchun": "для системы {sarf} м³/ч",
        "isitgich": "канальный нагреватель",
        "sovutgich": "канальный охладитель",
        "issiqlik_almashtirgich": "теплообменник",
        "shovqin": "шумоглушитель",
        "parallel": "{soni} шт. параллельно",
        "markaziy": "центральный кондиционер",
    },
}


def _t(til: str, kalit: str, **qiymatlar: Any) -> str:
    """Hujjat tilidagi matn bo'lagi."""
    andoza = MATN.get(til, MATN["ru"]).get(kalit, "")
    return andoza.format(**qiymatlar) if qiymatlar else andoza


def _birlik(til: str, aytilgan: str = "") -> str:
    """Hujjat tilidagi o'lchov birligi.

    Menejer `kg` yoki `m` yozsa — o'zgartirilmaydi. Faqat «dona»/«шт»
    hujjat tiliga moslanadi.
    """
    standart = BIRLIK.get(til, BIRLIK["ru"])
    toza = (aytilgan or "").strip().lower()
    if not toza or toza in DONA_BELGILARI:
        return standart
    return aytilgan.strip()


@dataclass
class Aniqlik:
    """Menejerdan so'raladigan narsa — KP tuzilmaydi.

    `index` — `javoblar["mahsulotlar"]` dagi qaysi qatorga tegishli.
    -1 — B yo'lida (obyekt): aniq qator yo'q, javob YANGI qator sifatida
    qo'shiladi (`bot/kp_oqim.py` da hal qilinadi).
    """

    savol: str
    variantlar: list[dict[str, Any]] = field(default_factory=list)
    index: int = -1
    # TUGMALI tanlovlar: [{"qiymat": "tarqoq", "yorliq": "Tarqoq tizim"}].
    #
    # JONLI XATO (2026-08-28): КЦКП topilmaganda savol «model nomini
    # ko'rsatasizmi YOKI TARQOQ TIZIMGA O'TAMIZMI?» deb ikkita yo'l
    # taklif qilardi, lekin faqat model nomini qabul qilardi. Menejer
    # «tarqoq» deb yozdi — o'sha savol qayta chiqdi. Yopiq halqa.
    tanlovlar: list[dict[str, str]] = field(default_factory=list)


@dataclass
class Natija:
    """Yig'ish natijasi: yo KP, yo aniqlashtirish."""

    kp: KP | None = None
    aniqlik: Aniqlik | None = None
    ogohlantirishlar: list[str] = field(default_factory=list)
    hisob: dict[str, Any] | None = None      # B yo'lida — havo sarfi hisobi

    @property
    def tayyormi(self) -> bool:
        return self.kp is not None


# --- narx qidirish ------------------------------------------------------------


def _variantlar(katalog: list[dict[str, Any]], nom: str) -> list[dict[str, Any]]:
    """Nomga mos VARIANTLAR (`characters[].insides[]`), narxi bilan.

    Menejer `ВЦ 4-75-2,5` deb yozsa — beshta variant qaytadi. Bittasini
    o'zimiz tanlamaymiz, ro'yxatni menejerga ko'rsatamiz.
    """
    from integrations.climavent_client import _mos_keladimi, kalitla

    aniq: list[dict[str, Any]] = []
    keng: list[dict[str, Any]] = []
    sorov_kalitlari = kalitla(nom)
    for mahsulot in katalog:
        for xususiyat in mahsulot.get("characters") or []:
            if not isinstance(xususiyat, dict):
                continue
            for ichki in xususiyat.get("insides") or []:
                if not isinstance(ichki, dict):
                    continue
                variant_nomi = str(ichki.get("in_model_name") or "")
                if not variant_nomi:
                    continue
                yozuv = {"nomi": variant_nomi, "narx_usd": ichki.get("price")}
                if sorov_kalitlari & kalitla(variant_nomi):
                    aniq.append(yozuv)
                elif _mos_keladimi(nom, variant_nomi):
                    keng.append(yozuv)
    return aniq or keng


def _quvvat(nom: str) -> str:
    """Variant nomidan quvvat va aylanish: `…-0,75/3000` -> `0,75 kVt / 3000`."""
    mos = re.search(r"-([\d,\.]+)/(\d+)\s*$", nom)
    if not mos:
        return ""
    return f"{mos.group(1)} kVt / {mos.group(2)} ayl"


# --- A yo'l: model ma'lum -----------------------------------------------------


def _qatorlar_modeldan(
    mahsulotlar: list[dict[str, Any]],
    katalog: list[dict[str, Any]],
    kurs: float,
    qqs: float,
    til: str = "ru",
) -> tuple[list[Qator], list[str], Aniqlik | None]:
    """Har mahsulot uchun qator. Noaniqlik bo'lsa — darhol to'xtaymiz."""
    qatorlar: list[Qator] = []
    narxsiz: list[str] = []
    ogohlantirishlar: list[str] = []
    for index, xom in enumerate(mahsulotlar):
        nom = str(xom.get("nomi") or "").strip()
        # Loyiha qisqartmasi tarjima qilingan bo'lsa — ogohlantirishlari
        # KP ga o'tsin (`kp/qisqartma.py`).
        ogohlantirishlar += [str(o) for o in (xom.get("ogohlantirishlar") or [])]
        variantlar = _variantlar(katalog, nom)
        narxlilar = [v for v in variantlar if v["narx_usd"] is not None]

        # Bir nechta NARXLI variant bor va ular har xil narxda —
        # menejer qaysi quvvatni nazarda tutganini bilmaymiz.
        agar_xilma_xil = len({v["narx_usd"] for v in narxlilar}) > 1
        if agar_xilma_xil and not any(v["nomi"] == nom for v in narxlilar):
            return [], [], Aniqlik(
                # «QUVVAT» EMAS, «VARIANT».
                #
                # JONLI XATO (2026-08-29): «ФЯГ 592х592 da 2 xil QUVVAT
                # bor» deb chiqardi. Filtrda quvvat yo'q — u ikki xil
                # QALINLIKDA (45 va 100 mm). Xabar ventilyator uchun
                # yozilgan va hamma mahsulotga qo'llanib ketgan edi.
                savol=(f"«{nom}» da {len(narxlilar)} xil variant bor va "
                       f"narxi har xil. Qaysi biri?"),
                index=index,
                variantlar=[
                    {"nomi": v["nomi"],
                     "quvvat": _quvvat(v["nomi"]),
                     # Menejerga ko'rsatiladigan raqam — QQS BILAN,
                     # chunki u saytdagi narx bilan solishtiradi.
                     "narx_som": round(float(v["narx_usd"]) * kurs)}
                    for v in sorted(narxlilar,
                                    key=lambda v: float(v["narx_usd"]))[:MAKS_VARIANT]
                ],
            ), []

        topilgan = katalog_narxi_xavfsiz(katalog, nom, kurs, qqs)
        if topilgan is None:
            narxsiz.append(nom)
        # ASL NOM spetsifikatsiyada qoladi: menejer mijoz nima
        # so'raganini va biz nimaga aylantirganimizni yonma-yon ko'rsin.
        asl = str(xom.get("asl_nomi") or "").strip()
        bolim = str(xom.get("bolim") or "").strip()
        spek = f"{bolim} · {asl}" if asl and bolim else (asl or "")
        qatorlar.append(Qator(
            nomi=nom,
            spetsifikatsiya=spek,
            miqdor=float(xom.get("miqdor") or 1),
            birlik=_birlik(til, str(xom.get("birlik") or "")),
            birlik_narx=topilgan[0] if topilgan else None,
            narx_sanasi=date.today().isoformat() if topilgan else "",
            qqs_foizi=qqs,
        ))
    return qatorlar, narxsiz, None, ogohlantirishlar


# --- B yo'l: obyekt tavsifi ---------------------------------------------------


def xonalar_royxati(javoblar: dict[str, Any]) -> list[dict[str, Any]]:
    """Shakl javoblaridan xonalar ro'yxati.

    `javoblar["xonalar"]` bo'lsa — o'sha. Bo'lmasa BITTA xona
    (`olcham` + `xona_turi` + `odamlar`) dan ro'yxat yasaladi, ya'ni
    eski shakllar ham, saqlangan javoblar ham buzilmaydi.
    """
    xom = javoblar.get("xonalar")
    if isinstance(xom, list) and xom:
        return [x for x in xom if isinstance(x, dict)]

    olcham = javoblar.get("olcham") or {}
    turi = str(javoblar.get("xona_turi") or "ofis")
    return [{
        "nomi": turi,
        "turi": turi,
        "maydon": float(olcham.get("maydon") or 0),
        "balandlik": float(olcham.get("balandlik") or 3.0),
        "odamlar": int(javoblar.get("odamlar") or 0),
    }]


def _tanlangan_uskunalar(javoblar: dict[str, Any]) -> list[str]:
    """Shakl kalitlari -> `hisob/bosim.py::USKUNA` jadvalidagi nomlar."""
    from kp.shakl import USKUNA_TANLOVI

    nomlar = {k: n for k, _y, n in USKUNA_TANLOVI}
    return [nomlar[k] for k in (javoblar.get("uskunalar") or []) if k in nomlar]


# Kanal uzunligi aytilganda burilishlar soni SHU nisbatda olinadi.
#
# Menejerdan har burilishni sanashni so'rash mumkin emas — u buni
# bilmaydi. Amaliyotda tarmoqda taxminan har 10 metrga bitta burilish
# to'g'ri keladi. Bu HAM taxmin, lekin uzunlikka bog'langan taxmin
# tayyor oraliqdan aniqroq.
METR_BURILISHGA = 10.0


def bosim_hisobi(
    javoblar: dict[str, Any], tezlik: float, xona_soni: int = 1
) -> tuple[tuple[int, int] | None, bool]:
    """Bosim oralig'i va u HAQIQIY hisobmi degan belgi.

    Kanal uzunligi aytilgan bo'lsa — `bosim_yoqotishi()` bilan aniq
    hisoblanadi (uzunlik x ishqalanish + burilishlar + panjaralar +
    uskunalar + 12% zaxira). Aks holda tayyor oraliq qaytadi.

    NEGA MUHIM: tayyor oraliq har doim YUQORI chegara bo'yicha talab
    qilinadi. Sanuzelning qisqa so'rish kanaliga 450 Pa talab qilindi,
    holbuki haqiqiy hisob 104 Pa berardi — mos ventilyator umuman
    topilmadi (jonli holat, 2026-08-26).
    """
    from hisob.bosim import bosim_yoqotishi, yigilgan_bosim

    uskunalar = _tanlangan_uskunalar(javoblar)
    uzunlik = javoblar.get("kanal_uzunligi")

    if isinstance(uzunlik, (int, float)) and uzunlik > 0 and tezlik > 0:
        qarshiliklar = {
            "burilish_yumshoq": max(1, round(float(uzunlik) / METR_BURILISHGA)),
            # Har xonaning o'z panjarasi bor; bittadan kam bo'lmaydi.
            "panjara": max(1, xona_soni),
        }
        if xona_soni > 1:
            qarshiliklar["tarmoq_shoxobcha"] = xona_soni - 1
        natija = bosim_yoqotishi(tezlik, float(uzunlik), qarshiliklar, uskunalar)
        jami = int(round(natija.jami))
        return (jami, jami), True

    if "uskunalar" in javoblar or javoblar.get("qisqa_kanal"):
        return yigilgan_bosim(
            uskunalar, kanalli=not javoblar.get("qisqa_kanal")
        ), False
    return tipik_bosim(str(javoblar.get("tarmoq") or "kanalli")), False


def tanlangan_bosim(javoblar: dict[str, Any]) -> tuple[int, int] | None:
    """Uzunliksiz bosim oralig'i (eski chaqiruvlar uchun)."""
    return bosim_hisobi(javoblar, tezlik=0.0)[0]


def _sorish_xonasimi(turi: str) -> bool:
    """Bu xona FAQAT SO'RISHGA quriladimi (`havo_almashinuvi.yaml`)."""
    return bool((normalar().get(turi) or {}).get("faqat_sorish"))


def hisobni_bajar(javoblar: dict[str, Any]) -> dict[str, Any]:
    """Har xona uchun havo sarfi va kanal — SOF KOD, model chaqirilmaydi.

    IKKI GURUHGA BO'LINADI:

      `kirish`  — oddiy xonalar. Ular bitta tizimga birlashtiriladi va
                  magistral kanal UMUMIY sarfga qarab o'lchanadi.
      `sorish`  — `faqat_sorish` belgilangan xonalar (sanuzel). Ular
                  ALOHIDA tizim: sanuzel havosi boshqa xonalarga
                  aralashtirilmaydi, aks holda hid butun binoga
                  tarqaladi.

    Ilgari bitta xona hisoblanardi va TZ dagi qolgan xonalar tashlab
    yuborilardi.
    """
    xonalar = xonalar_royxati(javoblar)

    hisoblangan: list[dict[str, Any]] = []
    ogohlantirishlar: list[str] = []
    for xom in xonalar:
        turi = str(xom.get("turi") or "ofis")
        xona = Xona(
            nomi=str(xom.get("nomi") or turi),
            maydon=float(xom.get("maydon") or 0),
            balandlik=float(xom.get("balandlik") or 3.0),
            odamlar=int(xom.get("odamlar") or 0),
            turi=turi,
        )
        natija = havo_sarfi(xona)
        kanal = kanal_olchami(natija.sarf)
        hisoblangan.append({
            "nomi": xona.nomi,
            "turi": turi,
            "maydon": xona.maydon,
            "balandlik": xona.balandlik,
            "odamlar": xona.odamlar,
            "hajm": natija.hajm,
            "sarf": natija.sarf,
            "usul": natija.tanlangan_usul,
            "diametr": kanal.diametr,
            "tezlik": kanal.haqiqiy_tezlik,
            "sorish": _sorish_xonasimi(turi),
        })
        for xabar in (*natija.ogohlantirishlar, *kanal.ogohlantirishlar):
            ogohlantirishlar.append(f"{xona.nomi}: {xabar}")

    kirish = [x for x in hisoblangan if not x["sorish"]]
    sorish = [x for x in hisoblangan if x["sorish"]]
    kirish_sarfi = round(sum(x["sarf"] for x in kirish), 1)
    sorish_sarfi = round(sum(x["sarf"] for x in sorish), 1)

    # Magistral kanal UMUMIY sarfga qarab o'lchanadi — bitta xonanikiga
    # emas, aks holda tizim bo'g'ilib qoladi.
    magistral = kanal_olchami(kirish_sarfi) if kirish_sarfi else None
    sorish_kanali = kanal_olchami(sorish_sarfi) if sorish_sarfi else None
    if magistral:
        for xabar in magistral.ogohlantirishlar:
            ogohlantirishlar.append(f"magistral kanal: {xabar}")

    if sorish and kirish:
        ogohlantirishlar.append(
            f"{len(sorish)} ta xona faqat so'rishga quriladi "
            f"({', '.join(x['nomi'] for x in sorish)}) — ular ALOHIDA "
            "tizim, umumiy kanalga ulanmaydi"
        )

    asosiy = kirish_sarfi or sorish_sarfi
    asosiy_kanal = magistral or sorish_kanali

    # BOSIM kanal hisobidan KEYIN: aniq hisob uchun kanaldagi haqiqiy
    # tezlik kerak, u esa diametr tanlanganda ma'lum bo'ladi.
    bosim, aniq_hisob = bosim_hisobi(
        javoblar,
        asosiy_kanal.haqiqiy_tezlik if asosiy_kanal else 0.0,
        xona_soni=len(kirish) or 1,
    )
    if aniq_hisob:
        ogohlantirishlar.append(
            f"Bosim kanal uzunligi ({javoblar.get('kanal_uzunligi')} m) "
            f"bo'yicha hisoblandi: ~{bosim[1]} Pa. Burilishlar soni "
            "uzunlikka qarab taxmin qilindi — loyihachi tekshirsin"
        )
    return {
        "xonalar": hisoblangan,
        # `sarf` va `diametr` — ESKI KALITLAR, mavjud kod ularga tayanadi.
        "sarf": asosiy,
        "diametr": asosiy_kanal.diametr if asosiy_kanal else 0,
        "tezlik": asosiy_kanal.haqiqiy_tezlik if asosiy_kanal else 0,
        "hajm": round(sum(x["hajm"] for x in hisoblangan), 2),
        "usul": hisoblangan[0]["usul"] if hisoblangan else "hisoblanmadi",
        "kirish_sarfi": kirish_sarfi,
        "sorish_sarfi": sorish_sarfi,
        "sorish_diametri": sorish_kanali.diametr if sorish_kanali else 0,
        "sorish_tezligi": sorish_kanali.haqiqiy_tezlik if sorish_kanali else 0,
        "sorish_xonalari": len(sorish),
        "bosim": bosim,
        "bosim_aniq": aniq_hisob,
        "ogohlantirishlar": ogohlantirishlar,
    }


def _sarfga_mosmi(yozuv: dict[str, Any], sarf: float) -> bool:
    oraliq = yozuv.get("havo_sarfi")
    if isinstance(oraliq, list) and len(oraliq) == 2:
        past, yuqori = oraliq
    elif isinstance(oraliq, (int, float)):
        past = yuqori = oraliq
    else:
        return False
    return past <= sarf <= yuqori


# ASOSIY uskuna FAQAT ventilyator bo'lishi mumkin.
#
# Jonli xato (2026-08-21): 600 m³/soat ga asosiy uskuna qilib `ПВН 500-250-2`
# — kanal ISITGICHI tanlangan edi. Sabab: isitgichda `havo_sarfi` bor, `bosim`
# esa `None` — shuning uchun u sarf filtridan ham, bosim filtridan ham
# o'tib ketardi va narxi arzonroq bo'lgani uchun birinchi o'ringa chiqardi.
# Eski LLM tizimida ham AYNAN shu sinf xato bo'lgan (Ø710 ga `ДР710` —
# deflektor asosiy uskuna bo'lib qolgan, `app/agentlar/loyihachi.py` ga qara).
#
# Toifa nomida "entilyator" bo'lsa — ventilyator ("Ventilyator ВЦ 4-75",
# "ВК-П ventilyatori", "Devorga o'rnatiladigan ventilyatorlar"). ДН/ВДН —
# tortish va puflash mashinalari, ular ham ventilyator, lekin nomida bu
# so'z yo'q.
VENTILYATOR_BELGILARI = ("entilyator", "ДН va ВДН")


def _ventilyatormi(yozuv: dict[str, Any]) -> bool:
    """Model ventilyator toifasidanmi.

    Toifa umuman ko'rsatilmagan bo'lsa — ROST deb hisoblanadi: eski
    yozuvlarda `turi` bo'lmasligi mumkin va ularni butunlay yo'qotib
    qo'ygandan ko'ra o'tkazgan yaxshi (sarf va bosim baribir tekshiriladi).
    """
    turi = yozuv.get("turi")
    if not turi:
        return True
    return any(belgi in turi for belgi in VENTILYATOR_BELGILARI)


def _bosimga_mosmi(yozuv: dict[str, Any], bosim_oraligi: tuple[int, int] | None) -> bool:
    """Fan sarfga mos bo'lsa ham, bosimi yetmasa — «ishlayapti, havo yo'q».

    Jonli misol `hisob/bosim.py` da: ВО 12-300-6,3 sarf bo'yicha
    yetardi, bosimi (50-95 Pa) kanalli tizim uchun (250-450 Pa) yetmasdi.
    Model bosimi noma'lum bo'lsa — «yaramaydi» DEB HISOBLANMAYDI, faqat
    ANIQ yetarsiz bo'lganda chetlatiladi.
    """
    if bosim_oraligi is None:
        return True
    return yetadimi(yozuv.get("bosim"), bosim_oraligi[1]) is not False


def _bosim_oraligidami(yozuv: dict[str, Any],
                       bosim_oraligi: tuple[int, int] | None) -> bool:
    """Kerakli bosim ventilyatorning ISH ORALIG'IDA turadimi?

    JONLI XATO (2026-08-27 da topildi): 8000 m³/soat, 450 Pa so'ralganda
    `ВР 12-26-5,5-1-45,0-2940` tanlandi. Uning ish oralig'i 6800-8000 Pa
    — ya'ni so'ralgandan 15 BAROBAR yuqori. Sababi: `_bosimga_mosmi`
    faqat «bosimi YETADIMI» ni tekshiradi, «ORTIQCHA EMASMI» ni emas.
    8000 Pa li ventilyator 450 Pa talabidan albatta o'tib ketardi.

    Oqibati ikki tomonlama:
      - 45 kVt dvigatel 5,5 kVt o'rniga — narx bir necha barobar;
      - ventilyator o'z egri chizig'idan tashqarida ishlaydi: FOIK
        past, shovqin baland.

    Bu yerda model CHETLATILMAYDI, faqat tartibda pastga tushadi
    (`_uskuna_tanla`). Sabab: oraliq ma'lumoti to'liq emas va qat'iy
    chetlatish KP ni umuman uskunasiz qoldirishi mumkin.

    MUHANDIS TASDIG'I KERAK: "ish oralig'ida" degani hozir «kerakli
    bosim [min, max] ichida» deb olingan.
    """
    if bosim_oraligi is None:
        return True
    oraliq = yozuv.get("bosim")
    if not isinstance(oraliq, list) or len(oraliq) < 2:
        return True                      # noma'lum — jazolanmaydi
    try:
        past, yuqori = float(oraliq[0]), float(oraliq[1])
    except (TypeError, ValueError):
        return True
    kerak = float(bosim_oraligi[1])
    return past <= kerak <= yuqori


def _uskuna_tanla(
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    sarf: float,
    kurs: float,
    bosim_oraligi: tuple[int, int] | None = None,
    qqs: float = 0.0,
) -> list[dict[str, Any]]:
    """Havo sarfiga VA bosimga mos modellar — TEXNIK MOSLIK bo'yicha.

    NARX FILTR EMAS. Ilgari narxi yo'q model butunlay chetlatilardi va
    KP asosiy uskunasiz qolardi. Endi eng mos model tanlanadi, narxi
    bo'lmasa qator BO'SH narx bilan chiqadi va «buxgalteriyadan
    so'ralsin» deb belgilanadi. Menejer uchun to'g'ri uskunali,
    narxsiz KP — uskunasiz KP dan foydaliroq.

    TARTIB:
      1) ORTIQCHA ZAXIRA kam bo'lgani (sig'imi kerakligiga eng yaqin) —
         katta ventilyator kichik tizimga qo'yilsa, u ortiqcha pul,
         ortiqcha shovqin va ortiqcha elektr sarfi;
      2) teng bo'lsa — NARXI BOR bo'lgani (KP darrov to'liq chiqsin);
      3) undan keyin — arzonrog'i.

    Filtrlash kodda: model «menimcha bu mos» demaydi, raqam solishtiriladi.
    Narx QQSsiz qaytadi (`qqssiz` ga qara).
    """
    nomzodlar: list[dict[str, Any]] = []
    for nom, yozuv in parametrlar.items():
        if not _ventilyatormi(yozuv):
            continue
        if not _sarfga_mosmi(yozuv, sarf) or not _bosimga_mosmi(yozuv, bosim_oraligi):
            continue
        narx = katalog_narxi_xavfsiz(katalog, nom, kurs, qqs)
        oraliq = yozuv.get("havo_sarfi")
        sarf_oraligi = (list(oraliq) if isinstance(oraliq, list)
                        else [oraliq, oraliq])
        nomzodlar.append({
            "nomi": nom,
            "sarf": sarf_oraligi,
            "narx_som": narx[0] if narx else None,
            "zaxira": _zaxira_foizi(sarf_oraligi, sarf),
            "bosim_mos": _bosim_oraligidami(yozuv, bosim_oraligi),
        })
    nomzodlar.sort(key=lambda n: (
        # BOSIM ISH ORALIG'IDA bo'lgani BIRINCHI. Ish oralig'idan
        # tashqaridagi ventilyator sarf bo'yicha ideal bo'lsa ham
        # noto'g'ri: u o'z egri chizig'idan tashqarida ishlaydi va
        # dvigateli bir necha barobar katta bo'ladi (`_bosim_oraligidami`).
        0 if n["bosim_mos"] else 1,
        # 0-30% zaxira — amalda hammasi MAQBUL (muhandislikda 10-20%
        # zaxira normal, u tarmoqdagi noaniqlikni qoplaydi). Shu
        # oraliqdagilar TENG deb qaraladi, shuning uchun narxi borini
        # tanlaymiz — KP darrov to'liq chiqsin. 30% dan oshgani esa
        # ortiqcha pul va shovqin, u tartibda pastga tushadi.
        0 if n["zaxira"] <= MAQBUL_ZAXIRA else 1,
        n["narx_som"] is None,
        n["zaxira"],
        n["narx_som"] if n["narx_som"] is not None else 0,
    ))
    return nomzodlar[:MAKS_VARIANT]


def _zaxira_foizi(oraliq: list[Any], sarf: float) -> float:
    """Ventilyator sig'imi kerakligidan necha foiz ortiq.

    Katta ventilyatorni kichik tizimga qo'yish — ortiqcha pul, ortiqcha
    shovqin va ortiqcha elektr sarfi. Shuning uchun ZAXIRASI KAM bo'lgan
    model afzal.
    """
    try:
        yuqori = float(oraliq[1])
    except (TypeError, ValueError, IndexError):
        return 0.0
    if sarf <= 0:
        return 0.0
    return max(0.0, (yuqori - sarf) / sarf)


# --- tarmoq turiga bog'liq qo'shimcha uskuna ---------------------------------
#
# Menejer "filtr va isitgich bilan kirish tizimi" ni tanlasa, KP da isitgich
# BO'LISHI kerak. Ilgari bu javob faqat bosim oralig'iga ta'sir qilardi va
# KP ga bitta ventilyator tushib, tanlov nomi bilan hujjat mazmuni bir-biriga
# ZID bo'lib qolardi (jonli holat: 500 m² restoranga bitta ventilyator).
#
# Qidirish DIAMETR bo'yicha EMAS. Diametr raqamini model nomidan qidirish
# sinab ko'rildi va axlat berdi: Ø710 uchun butun katalogda bitta `ДР710`
# (deflektor) chiqadi, Ø800 uchun esa siklonlar (`ЦН-11-800` — chang tutgich)
# aralashib ketadi. Shuning uchun TOIFA (`turi` maydoni) bo'yicha qidiriladi.

# Tarmoq turi -> KP ga qo'shiladigan uskuna toifalari.
TARMOQ_USKUNASI: dict[str, tuple[str, ...]] = {
    "oddiy": (),
    "kanalli": (),
    "filtrli": ("isitgich",),
    "toliq": ("sovutgich", "issiqlik_almashtirgich"),
}

# Toifa kaliti -> (`turi` maydonidagi belgi, KP dagi o'zbekcha nom).
USKUNA_TOIFALARI: dict[str, tuple[str, str]] = {
    "isitgich": ("ПВН", "kanal isitgichi"),
    "sovutgich": ("PVF", "kanal sovutgichi"),
    "issiqlik_almashtirgich": ("KSK", "issiqlik almashtirgich"),
}

# Yo'nalish -> (ventilyator soni, kerakli panjara turlari).
#
# Kirish + chiqish tizimida IKKITA ventilyator kerak: biri toza havo
# beradi, ikkinchisi ishlatilganini so'rib chiqaradi. Ilgari yo'nalish
# so'ralmasdi va KP ga har doim bitta ventilyator tushardi.
#
# РВИ faqat SO'RISHDA ishlatiladi (teskari klapanli), shuning uchun
# kirish tarmog'iga РВН qo'yiladi.
YONALISH_TARKIBI: dict[str, tuple[int, tuple[str, ...]]] = {
    "kirish": (1, ("РВН",)),
    "chiqish": (1, ("РВИ",)),
    "ikkalasi": (2, ("РВН", "РВИ")),
}

# Yo'nalish aytilmagan bo'lsa (eski shakl, saqlangan javoblar) — kirish
# deb olinadi: bu eng keng tarqalgan holat va ilgarigi xulq-atvor.
YONALISH_STANDART = "kirish"


def _yonalishni_tekshir(
    javoblar: dict[str, Any], ogohlantirishlar: list[str]
) -> str:
    """Xona turi FAQAT SO'RISHGA bo'lsa, yo'nalishni to'g'rilaydi.

    Sanuzelga havo alohida quvur bilan berilmaydi — u yonidagi
    xonalardan o'z-o'zidan kiradi. Maqsad shu: xonada bosim PAST
    bo'lsin, shunda hid tashqariga chiqmaydi. Kirish tarmog'i qo'yilsa
    bosim ko'tariladi va hid koridorga tarqaladi.

    Bu normalar faylida `faqat_sorish: true` bilan belgilanadi — qaysi
    xona turi shundayligi KODDA emas, o'sha faylda turadi.

    JIM TUZATMAYMIZ: menejerga nima o'zgarganini va NEGA o'zgarganini
    aytamiz, aks holda u KP dagi farqni tushunmaydi.
    """
    yonalish = str(javoblar.get("yonalish") or YONALISH_STANDART)
    if yonalish not in YONALISH_TARKIBI:
        yonalish = YONALISH_STANDART

    if yonalish == "chiqish":
        return yonalish

    # HAMMA xona faqat so'rishga bo'lsagina butun tizim so'rishga
    # o'tkaziladi. Aralash obyektda (sex + sanuzel) sanuzel butun
    # binoni so'rish tizimiga aylantirib yubormasligi kerak — har
    # xonaning panjarasi `_panjaralar` da alohida tanlanadi.
    #
    # XATO TUZATILDI: bu yerda `javoblar["xona_turi"]` ga qaralardi.
    # Xona halqasi qo'shilgach u OXIRGI kiritilgan xonani saqlaydigan
    # bo'ldi — sanuzel oxirida kiritilsa, sex ham so'rishga o'tib
    # ketardi va KP ga bitta ventilyator tushardi.
    turlar = [str(x.get("turi") or "") for x in xonalar_royxati(javoblar)]
    if not turlar or not all(_sorish_xonasimi(t) for t in turlar):
        return yonalish

    nomi = turlar[0] if len(set(turlar)) == 1 else "bu obyekt"
    ogohlantirishlar.append(
        f"«{nomi}» faqat SO'RISHGA quriladi — havo yonidagi xonalardan "
        "o'zi kiradi. Kirish tarmog'i qo'yilsa xonada bosim ko'tariladi "
        "va hid tashqariga tarqaladi. Shuning uchun hisob faqat so'rish "
        "bo'yicha qilindi."
    )
    return "chiqish"


# PANJARA qaysi tarmoq turida kerak.
#
# XATO TUZATILDI (2026-08-21): ilgari bu yerda "panjara katalogda YO'Q"
# deb yozilgan edi. Tekshirilganda РВН va РВИ oilalari NARXI BILAN
# birga backendda turgani aniqlandi (har biri 64 ta o'lcham). Ular
# `havo_sarfi` maydoniga ega emas — shuning uchun `_uskuna_tanla` ularni
# ko'rmaydi va "yo'q" degan xulosa chiqqan edi. Panjara sarf bo'yicha
# emas, JONLI KESIM yuzasi bo'yicha tanlanadi (`hisob/panjara.py`).
TARMOQ_PANJARASI = ("kanalli", "filtrli", "toliq")

# Tarmoq turi nomida tilga olinadi, lekin katalogda MAHSULOT sifatida yo'q.
# Jim qoldirilsa menejer ham, mijoz ham ularni KP ichida deb o'ylaydi.
# FILTR (ФЯГ/ФЯК/ФЯП) katalogda BOR va narxi ham bor, lekin u havo
# sarfiga qarab emas, havo tayyorlash qurilmasining filtr seksiyasi
# o'lchamiga qarab tanlanadi — buni bu yerda hisoblab bo'lmaydi.
# Shuning uchun "yo'q" demaymiz, "alohida tanlanadi" deymiz.
TARMOQ_YETISHMAYDIGANI: dict[str, tuple[str, ...]] = {
    "oddiy": (),
    "kanalli": (),
    "filtrli": ("filtr (ФЯГ — katalogda bor, o'lchami bo'yicha tanlanadi)",),
    "toliq": (
        "filtr (ФЯГ — katalogda bor, o'lchami bo'yicha tanlanadi)",
        "rekuperator",
    ),
}


def _qoshimcha_tanla(
    parametrlar: dict[str, dict[str, Any]],
    belgi: str,
    sarf: float,
) -> tuple[str | None, int, float | None]:
    """Toifadagi mos model va NECHTA kerakligi.

    Qaytaradi `(model_nomi, soni, eng_katta_sigim)`.

    BITTASI YETMASA — PARALLEL QO'YILADI. 18 000 m³/soat ga eng katta
    isitgich 1200 m³/soat bo'lsa, 15 dona parallel o'rnatiladi. Bu
    o'ylab topilgan yechim emas: katta tizim baribir bir necha tarmoqqa
    bo'linadi (kanal hisobi ham «Ø1128 kerak — standartdan katta,
    bo'lish kerak» deb ogohlantiradi), va panjaralarni ham xuddi
    shunday ko'paytiramiz.

    Ilgari bu holatda «bu o'lchamda YO'Q» deb qator umuman qo'yilmasdi
    va menejer KP ni qo'lda to'ldirishi kerak edi (jonli e'tiroz,
    2026-08-26).

    Bitta uskunani ORTIQCHA yuk bilan ishlatmaymiz — soni har doim
    yuqoriga yumaloqlanadi.
    """
    nomzodlar = [
        (float(yozuv["havo_sarfi"]), nom)
        for nom, yozuv in parametrlar.items()
        if belgi in (yozuv.get("turi") or "")
        and isinstance(yozuv.get("havo_sarfi"), (int, float))
        and float(yozuv["havo_sarfi"]) > 0
    ]
    if not nomzodlar:
        return None, 0, None
    nomzodlar.sort()

    yetadigan = [(n, nom) for n, nom in nomzodlar if n >= sarf]
    if yetadigan:
        return yetadigan[0][1], 1, None

    # Bittasi yetmadi — ENG KATTASIDAN parallel qo'yamiz.
    eng_katta_sigim, eng_katta_nom = nomzodlar[-1]
    soni = math.ceil(sarf / eng_katta_sigim)
    return eng_katta_nom, soni, eng_katta_sigim


def _bosim_sababi(
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    hisob: dict[str, Any],
    kurs: float,
    qqs: float,
) -> str:
    """Ventilyator topilmaganining SABABI: sarfmi yoki bosimmi?

    Menejer hamma qismni tanlaganda bosim 1000 Pa dan oshadi, katalogdagi
    narxli ventilyatorlar esa 600 Pa gacha. Natijada hech narsa mos
    kelmaydi va KP da mahsulot KAMAYADI. Sababi aytilmasa menejer
    «ko'proq tanladim — kamroq chiqdi» degan holatga tushadi.
    """
    bosim = hisob.get("bosim")
    if not bosim:
        return ""

    # Bosim SHARTISIZ nechta model mos kelardi?
    bosimsiz = _uskuna_tanla(parametrlar, katalog, hisob["sarf"], kurs, None, qqs)
    if not bosimsiz:
        return ""      # sarf bo'yicha ham yo'q — bosim aybdor emas

    # NARXI BOR ventilyatorlar orasidagi eng yuqori bosim. Narxsizlarini
    # sanash chalg'itadi: ular baribir KP ga tusholmaydi, lekin bosimi
    # yuqori bo'lishi mumkin (chang ventilyatorlari 8000 Pa gacha).
    nomlar = {x["nomi"] for x in bosimsiz}
    eng_kop = 0.0
    for nom, yozuv in parametrlar.items():
        if nom not in nomlar:
            continue
        b = yozuv.get("bosim")
        qiymat = max(b) if isinstance(b, (list, tuple)) and b else b
        if isinstance(qiymat, (int, float)):
            eng_kop = max(eng_kop, float(qiymat))

    sabab = (
        f"SABABI — BOSIM: tanlangan qismlar bilan tizimga ~{bosim[1]:.0f} Pa "
        "kerak"
    )
    if eng_kop:
        sabab += (f", narxi bor ventilyatorlar esa {eng_kop:.0f} Pa gacha "
                  "beradi")
    sabab += (". Qismlarni kamaytirsangiz mos uskuna topiladi.")
    return sabab


def _kerakli_toifalar(javoblar: dict[str, Any]) -> tuple[str, ...]:
    """KP ga qo'shiladigan uskuna toifalari.

    Yangi shaklda menejer qismlarni BITTALAB tanlaydi — o'sha ro'yxat
    ishlatiladi. Eski shaklda tayyor to'plam nomi (`tarmoq`) turadi.
    """
    # MARKAZIY QURILMA tanlangan bo'lsa, isitgich/sovutgich uning
    # ICHIDA — alohida qator qo'yilsa, mijoz ikki marta to'laydi.
    if javoblar.get("markaziy") == "ha":
        return ()
    if "uskunalar" in javoblar or javoblar.get("qisqa_kanal"):
        tanlangan = javoblar.get("uskunalar") or []
        # Shakldagi kalit -> katalog toifasi. Rekuperator va klapan
        # bosimga ta'sir qiladi, lekin ularni katalogdan tanlab
        # bo'lmaydi — ular `_hisobga_kirmaydi` orqali aytiladi.
        # SHOVQIN PASAYTIRGICH esa alohida yo'l bilan tanlanadi
        # (`_shovqin_qatori`): uning sig'imi model NOMIDA turadi.
        return tuple(k for k in ("isitgich", "sovutgich") if k in tanlangan)
    return TARMOQ_USKUNASI.get(str(javoblar.get("tarmoq") or ""), ())


def _eng_yaqin_bosim(
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    sarf: float,
    kurs: float,
    qqs: float,
) -> tuple[str, float, float] | None:
    """Sarfga mos, lekin bosimi biroz yetmagan ENG KUCHLI model.

    Qaytaradi `(nomi, bosimi, kerakli_bosim)`.

    NEGA KERAK: bosim talabi taxminiy oraliqning YUQORI chegarasi
    bo'yicha qo'yiladi. 405 Pa beradigan model 450 Pa talabidan 10%
    kam bo'lgani uchun rad etiladi — bu ehtiyotkorlik, lekin menejer
    faqat «topilmadi» xabarini ko'radi va nima qilishni bilmaydi.
    """
    from hisob.bosim import TARMOQ_ASOSI

    kerak = float(TARMOQ_ASOSI[1])
    eng_yaxshi: tuple[str, float, float] | None = None
    for nom, yozuv in parametrlar.items():
        if not _ventilyatormi(yozuv) or not _sarfga_mosmi(yozuv, sarf):
            continue
        b = yozuv.get("bosim")
        qiymat = max(b) if isinstance(b, (list, tuple)) and b else b
        if not isinstance(qiymat, (int, float)):
            continue
        if eng_yaxshi is None or float(qiymat) > eng_yaxshi[1]:
            eng_yaxshi = (nom, float(qiymat), kerak)
    return eng_yaxshi


def _sorish_ventilyatori(
    hisob: dict[str, Any],
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    kurs: float,
    qqs: float,
    narxsiz: list[str],
    ogohlantirishlar: list[str],
    til: str = "ru",
    javoblar: dict[str, Any] | None = None,
) -> list[Qator]:
    """`faqat_sorish` xonalari uchun ALOHIDA ventilyator.

    Bu qator qo'shilmasa KP da sanuzel panjaralari turadi-yu, ularni
    tortadigan ventilyator bo'lmaydi — hujjat o'z ichida to'liq emas.
    """
    sarf = float(hisob.get("sorish_sarfi") or 0)
    if sarf <= 0:
        return []

    # SO'RISH TIZIMINING O'Z BOSIMI.
    #
    # Kirish tizimining bosimi ISHLATILMAYDI: sanuzel so'rishida filtr
    # ham, isitgich ham yo'q. Kanal uzunligi aytilgan bo'lsa aniq
    # hisoblanadi, aks holda tarmoqning tayyor oralig'i olinadi.
    from hisob.bosim import bosim_yoqotishi, yigilgan_bosim

    uzunlik = javoblar.get("kanal_uzunligi") if javoblar else None
    tezlik = float(hisob.get("sorish_tezligi") or 0)
    if isinstance(uzunlik, (int, float)) and uzunlik > 0 and tezlik > 0:
        xona_soni = max(1, int(hisob.get("sorish_xonalari") or 1))
        natija = bosim_yoqotishi(
            tezlik, float(uzunlik),
            {"burilish_yumshoq": max(1, round(float(uzunlik) / METR_BURILISHGA)),
             "panjara": xona_soni},
            ["klapan"],          # so'rishda teskari klapan bo'ladi
        )
        jami = int(round(natija.jami))
        sorish_bosimi: tuple[int, int] = (jami, jami)
    else:
        sorish_bosimi = yigilgan_bosim([])

    nomzodlar = _uskuna_tanla(
        parametrlar, katalog, sarf, kurs, sorish_bosimi, qqs
    )
    nomlar = [x["nomi"] for x in (hisob.get("xonalar") or []) if x.get("sorish")]
    izoh = ", ".join(nomlar) or "so'rish"
    if not nomzodlar:
        # ENG YAQIN VARIANTNI ko'rsatamiz. Bosim talabi oraliqning
        # YUQORI chegarasi bo'yicha qo'yiladi, shuning uchun 10% yetmay
        # qolgan model ham rad etiladi — menejer esa shunchaki
        # «topilmadi» xabarini ko'radi va nima qilishni bilmaydi.
        yaqin = _eng_yaqin_bosim(parametrlar, katalog, sarf, kurs, qqs)
        xabar = (f"So'rish tizimiga ({izoh}, {sarf:.0f} m³/soat) mos "
                 "ventilyator topilmadi")
        if yaqin:
            nomi, bosimi, kerak = yaqin
            xabar += (f". Eng yaqini — {nomi}: {bosimi:.0f} Pa beradi, "
                      f"kerak ~{kerak:.0f} Pa. Muhandis bilan tekshiring")
        else:
            xabar += " — modelni o'zingiz qo'shing"
        ogohlantirishlar.append(xabar)
        return []

    tanlangan = nomzodlar[0]
    if tanlangan["narx_som"] is None:
        narxsiz.append(tanlangan["nomi"])
    return [Qator(
        nomi=tanlangan["nomi"],
        spetsifikatsiya=(
            f"{_t(til, 'sorish_tizimi')} ({izoh}), {sarf:.0f} "
            f"{_t(til, 'sarf')}, "
            + _t(til, "kanal", d=hisob.get("sorish_diametri"))
        ),
        miqdor=1, birlik=_birlik(til),
        birlik_narx=tanlangan["narx_som"],
        narx_sanasi=(date.today().isoformat()
                     if tanlangan["narx_som"] is not None else ""),
        qqs_foizi=qqs,
    )]


def _shovqin_qatori(
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    sarf: float,
    kurs: float,
    qqs: float,
    narxsiz: list[str],
    ogohlantirishlar: list[str],
    til: str = "ru",
) -> list[Qator]:
    """Shovqin pasaytirgich — KESIM O'LCHAMI bo'yicha (`hisob/shovqin.py`).

    `_uskuna_tanla` uni topa olmaydi: katalogda `havo_sarfi` maydoni
    yo'q, faqat dB jadvali bor. Sig'imi esa model NOMIDA turadi
    (`КГП 50-30` = 500x300 mm kanal).
    """
    from hisob import olchamdan_sigim, shovqin_tanla

    nomlar = [
        nom for nom, yozuv in parametrlar.items()
        if "KGP" in (yozuv.get("turi") or "") or "KGT" in (yozuv.get("turi") or "")
    ]
    natija = shovqin_tanla(nomlar, sarf)
    if natija is None:
        ogohlantirishlar.append(
            "shovqin pasaytirgich katalogda topilmadi — alohida so'ralsin"
        )
        return []

    tanlangan, soni = natija
    spets = (f"{_t(til, 'shovqin')}, "
             + _t(til, "jonli_kesim", y=tanlangan.yuza) + ", "
             + _t(til, "tizim_uchun", sarf=f"{sarf:.0f}"))
    if soni > 1:
        spets += ", " + _t(til, "parallel", soni=soni)
        ogohlantirishlar.append(
            f"shovqin pasaytirgich: eng kattasi "
            f"{tanlangan.sigim:,.0f}".replace(",", " ")
            + f" m³/soat, kerak esa {sarf:.0f} — {soni} dona PARALLEL qo'yildi"
        )

    narx = katalog_narxi_xavfsiz(katalog, tanlangan.nomi, kurs, qqs)
    if narx is None:
        narxsiz.append(tanlangan.nomi)
    return [Qator(
        nomi=tanlangan.nomi,
        spetsifikatsiya=spets,
        miqdor=float(soni), birlik=_birlik(til),
        birlik_narx=narx[0] if narx else None,
        narx_sanasi=date.today().isoformat() if narx else "",
        qqs_foizi=qqs,
    )]


def _panjaralar(
    javoblar: dict[str, Any],
    xonalar: list[dict[str, Any]] | None,
    katalog: list[dict[str, Any]],
    sarf: float,
    kurs: float,
    qqs: float,
    narxsiz: list[str],
    ogohlantirishlar: list[str],
    til: str = "ru",
) -> list[Qator]:
    """Panjara HAR XONA uchun alohida hisoblanadi.

    Umumiy sarfdan bitta panjara turi hisoblansa, xonalarga qanday
    taqsimlanishi ko'rinmaydi — menejer KP dan nechta panjara qaysi
    xonaga ketishini bilmaydi. Bino bo'ylab tarqatish esa aynan shu.

    Sanuzel kabi `faqat_sorish` xonalarga har doim so'rish panjarasi
    (РВИ) qo'yiladi — menejer nimani tanlaganidan qat'i nazar.
    """
    yonalish = _yonalishni_tekshir(javoblar, ogohlantirishlar)
    _soni, panjara_turlari = YONALISH_TARKIBI[yonalish]

    if not xonalar:
        qatorlar: list[Qator] = []
        for turi in panjara_turlari:
            qatorlar += _panjara_qatorlari(
                katalog, sarf, kurs, qqs, narxsiz, ogohlantirishlar,
                turi=turi, til=til)
        return qatorlar

    qatorlar = []
    for xona in xonalar:
        xona_sarfi = float(xona.get("sarf") or 0)
        if xona_sarfi <= 0:
            continue
        turlar = ("РВИ",) if xona.get("sorish") else panjara_turlari
        for turi in turlar:
            qatorlar += _panjara_qatorlari(
                katalog, xona_sarfi, kurs, qqs, narxsiz, ogohlantirishlar,
                turi=turi, xona_nomi=str(xona.get("nomi") or ""), til=til,
            )
    return qatorlar


def _qoshimcha_qatorlar(
    javoblar: dict[str, Any],
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    sarf: float,
    kurs: float,
    qqs: float,
    narxsiz: list[str],
    ogohlantirishlar: list[str],
    xonalar: list[dict[str, Any]] | None = None,
    til: str = "ru",
) -> list[Qator]:
    """Menejer tanlagan tarmoq turi talab qiladigan qo'shimcha uskunalar.

    `narxsiz` va `ogohlantirishlar` JOYIDA to'ldiriladi — chaqiruvchi
    ularni KP ning umumiy ro'yxatiga qo'shadi.
    """
    tarmoq = str(javoblar.get("tarmoq") or "")
    qatorlar: list[Qator] = []

    for toifa in _kerakli_toifalar(javoblar):
        belgi, _uz_nomi = USKUNA_TOIFALARI[toifa]
        nomi = _t(til, toifa) or _uz_nomi
        model, soni, eng_katta = _qoshimcha_tanla(parametrlar, belgi, sarf)
        if model is None:
            ogohlantirishlar.append(
                f"{nomi} ({belgi}) katalogda topilmadi — alohida so'ralsin"
            )
            continue
        spets = f"{nomi}, " + _t(til, "tizim_uchun", sarf=f"{sarf:.0f}")
        if soni > 1:
            # PARALLEL o'rnatish — buni ochiq aytamiz, aks holda
            # menejer «nega 15 dona?» deb hayron bo'ladi.
            spets += ", " + _t(til, "parallel", soni=soni)
            ogohlantirishlar.append(
                f"{nomi}: eng kattasi {eng_katta:.0f} m³/soat, kerak esa "
                f"{sarf:.0f} — {soni} dona PARALLEL qo'yildi. Tizim shuncha "
                "tarmoqqa bo'linishi kerak, loyihachi tasdiqlasin"
            )
        if soni > MAKS_PARALLEL:
            ogohlantirishlar.append(
                f"{nomi}: {soni} dona — bu juda ko'p. Kattaroq uskuna "
                "buyurtma qilish arzonroq bo'lishi mumkin"
            )
        narx = katalog_narxi_xavfsiz(katalog, model, kurs, qqs)
        if narx is None:
            narxsiz.append(model)
        qatorlar.append(Qator(
            nomi=model,
            spetsifikatsiya=spets,
            miqdor=float(soni), birlik=_birlik(til),
            birlik_narx=narx[0] if narx else None,
            narx_sanasi=date.today().isoformat() if narx else "",
            qqs_foizi=qqs,
        ))

    if "shovqin" in (javoblar.get("uskunalar") or []):
        qatorlar += _shovqin_qatori(
            parametrlar, katalog, sarf, kurs, qqs, narxsiz,
            ogohlantirishlar, til,
        )

    if _panjara_kerakmi(javoblar, tarmoq):
        qatorlar += _panjaralar(
            javoblar, xonalar, katalog, sarf, kurs, qqs,
            narxsiz, ogohlantirishlar, til,
        )

    yetishmayotgan = _hisobga_kirmaydi(javoblar, tarmoq)
    if yetishmayotgan:
        ogohlantirishlar.append(
            "Tanlangan tizim turida bor, lekin bu hisobga KIRMAYDI: "
            + ", ".join(yetishmayotgan) + " — alohida tanlanadi"
        )
    return qatorlar


def _panjara_kerakmi(javoblar: dict[str, Any], tarmoq: str) -> bool:
    """Qisqa, devordan devorga kanalga panjara tarmog'i qo'yilmaydi."""
    if javoblar.get("qisqa_kanal"):
        return False
    if "uskunalar" in javoblar:
        return True
    return tarmoq in TARMOQ_PANJARASI


def _hisobga_kirmaydi(javoblar: dict[str, Any], tarmoq: str) -> tuple[str, ...]:
    """Tanlangan, lekin bu yerda hisoblanmaydigan qismlar.

    Menejer «rekuperator» ni tanlagan bo'lsa, u KP ga qator bo'lib
    TUSHMAYDI (katalogda sarf bo'yicha tanlanmaydi) — lekin bosimga
    ta'sir qiladi. Jim qoldirilsa menejer uni KP ichida deb o'ylaydi.
    """
    if "uskunalar" not in javoblar and not javoblar.get("qisqa_kanal"):
        return TARMOQ_YETISHMAYDIGANI.get(tarmoq, ())

    # SHOVQIN PASAYTIRGICH bu ro'yxatda YO'Q: u endi KP ga qator bo'lib
    # tushadi (`_shovqin_qatori`), shuning uchun «hisobga kirmaydi»
    # deyish noto'g'ri bo'lardi.
    izohlar = {
        "filtr": "filtr (ФЯГ — katalogda bor, o'lchami bo'yicha tanlanadi)",
        "rekuperator": "rekuperator",
        "klapan": "klapan",
    }
    tanlangan = javoblar.get("uskunalar") or []
    return tuple(izohlar[k] for k in tanlangan if k in izohlar)


def _panjara_qatorlari(
    katalog: list[dict[str, Any]],
    sarf: float,
    kurs: float,
    qqs: float,
    narxsiz: list[str],
    ogohlantirishlar: list[str],
    turi: str = "РВН",
    xona_nomi: str = "",
    til: str = "ru",
) -> list[Qator]:
    """Panjara — o'lchami va SONI hisoblanadi (`hisob/panjara.py`).

    Panjara `_uskuna_tanla` orqali topilmaydi: uning `havo_sarfi`
    maydoni yo'q, u JONLI KESIM yuzasi bo'yicha tanlanadi.
    """
    hisob = panjara_tanla(sarf, turi)
    if hisob is None:
        ogohlantirishlar.append(
            f"{turi} panjarasi hisoblanmadi (jadval topilmadi) — alohida tanlansin"
        )
        return []
    # Qaysi xonaga ketishi KP da ko'rinib tursin — montajchi ham,
    # mijoz ham buni jadvaldan o'qiy olsin.
    xona_belgisi = f"{xona_nomi} — " if xona_nomi else ""

    ogohlantirishlar += hisob.ogohlantirishlar
    narx = katalog_narxi_xavfsiz(katalog, hisob.nomi, kurs, qqs)
    if narx is None:
        narxsiz.append(hisob.nomi)
    return [Qator(
        nomi=hisob.nomi,
        spetsifikatsiya=(
            f"{xona_belgisi}{_t(til, 'panjara')}, "
            + _t(til, "jonli_kesim", y=hisob.bitta_yuza) + ", "
            + _t(til, "tezlik", v=hisob.haqiqiy_tezlik)
        ),
        miqdor=float(hisob.soni), birlik=_birlik(til),
        birlik_narx=narx[0] if narx else None,
        narx_sanasi=date.today().isoformat() if narx else "",
        qqs_foizi=qqs,
    )]


def qqssiz(narx: float | None, qqs_foizi: float) -> float | None:
    """Katalog narxidan QQSsiz summani ajratadi.

    NEGA KERAK: buxgalteriya narx faylida ustun sarlavhasi
    «Цена USD с НДС» — ya'ni QQS narx ICHIDA. Backendga aynan shu
    raqam yozilgan.

    KP jadvali esa QQSsiz summa + alohida QQS qatori + jami
    ko'rinishida tuziladi (`kp/model.py`). Katalog narxi to'g'ridan-
    to'g'ri qo'yilsa, QQS IKKI MARTA hisoblanadi va KP 12% qimmat
    chiqadi. Sayt esa o'sha narxni QQSsiz ko'rsatadi — mijoz saytda
    bir narx, KP da boshqa narx ko'rardi.

    Tekshirilgan (2026-08-21): `PRICE JIHOZVENT_v5.1`, `ВЦ 4-75`
    varag'i, 9-qator 12-ustun = «Цена USD с НДС», qiymati 156.76 —
    backenddagi narx bilan bir xil.
    """
    if narx is None or qqs_foizi <= 0:
        return narx
    return narx / (1 + qqs_foizi / 100)


def katalog_narxi_xavfsiz(
    katalog: list[dict[str, Any]], nom: str, kurs: float, qqs: float = 0.0
) -> tuple[float, str] | None:
    """Katalog narxi, QQSsiz holatga keltirilgan.

    `qqs` berilmasa narx O'ZGARMAYDI — eski chaqiruvlar buzilmasin.
    """
    from integrations.climavent_client import katalog_narxi

    topilgan = katalog_narxi(katalog, nom, kurs=kurs)
    if topilgan is None:
        return None
    return qqssiz(topilgan[0], qqs), topilgan[1]


def _narxsiz_mos(
    parametrlar: dict[str, dict[str, Any]],
    sarf: float,
    bosim_oraligi: tuple[int, int] | None = None,
) -> list[str]:
    """Sarfga (va bosimga) MOS, lekin narxi kiritilmagan modellar.

    «Topilmadi» deb to'xtash foydasiz: menejer nima yo'qligini bilmaydi.
    Bu ro'yxat bilan u buxgalteriyaga aniq nima so'rashini biladi.
    """
    mos = [
        nom for nom, yozuv in parametrlar.items()
        if _ventilyatormi(yozuv)
        and _sarfga_mosmi(yozuv, sarf)
        and _bosimga_mosmi(yozuv, bosim_oraligi)
    ]
    return sorted(mos)[:MAKS_VARIANT]


# --- yig'ish ------------------------------------------------------------------


def _kurs_matni(kurs: float, til: str) -> str:
    raqam = f"{kurs:,.0f}".replace(",", " ")
    bugun = date.today().strftime("%d.%m.%Y")
    if til == "ru":
        return f"*Цены рассчитаны по курсу {raqam} сум/доллар (на {bugun})."
    return f"*Narxlar {raqam} so'm/dollar kursida hisoblangan ({bugun} holatiga)."


def _qamrov_izohi(til: str) -> str:
    """Avtomatik hisob — faqat ASOSIY USKUNA tanlovi.

    Mijoz/menejer bu qatorni ko'rmasa, faqat asosiy uskuna narxini
    butun tizim narxi deb tushunib qolishi mumkin (jonli holat: 500 kv.m
    restoranga bitta fan chiqib, "qo'shimcha hech narsa kerakmasmi" degan
    savol tug'ilgan edi — kanal, panjara, ikkinchi fan ko'rinmay qolgan).
    """
    if til == "ru":
        return ("*Расчёт покрывает только подбор основного оборудования "
                "(вентилятор) по расходу воздуха и давлению. Каналы, "
                "решётки/диффузоры, монтажные материалы и мощность "
                "отопления/охлаждения в данный расчёт не входят — "
                "требуется отдельный инженерный расчёт для полного проекта.")
    return ("*Hisob faqat asosiy uskuna (fan/vent birligi) tanlovini "
            "qamrab oladi — havo sarfi va bosim bo'yicha. Kanal, "
            "diffuzor/panjara, montaj materiallari va isitish/sovutish "
            "quvvati ushbu hisobga kiritilmagan — to'liq loyiha uchun "
            "muhandis hisobi talab qilinadi.")


def _kp_yasa(
    javoblar: dict[str, Any],
    qatorlar: list[Qator],
    raqam: str,
    royxat: Any,
    rekvizit: dict[str, Any],
    til: str,
    kurs: float,
    ogohlantirishlar: list[str],
) -> KP:
    """Qatorlardan tayyor KP hujjati.

    IKKI YO'L uchun umumiy: oddiy (ventilyator + qismlar) va markaziy
    qurilmali. Ilgari bu kod faqat `yig()` ichida edi va markaziy yo'l
    uni takrorlashi kerak bo'lardi — shartlar matni ikki joyda turib,
    biri unutilib ketishi mumkin edi.
    """
    kursdan = any(q.birlik_narx for q in qatorlar)
    return KP(
        raqam=raqam,
        sana=date.today(),
        mijoz=Mijoz(
            nomi=str(javoblar.get("mijoz") or ""),
            inn=str(javoblar.get("inn") or ""),
            obyekt=str(javoblar.get("obyekt") or ""),
        ),
        qatorlar=qatorlar,
        shartlar=Shartlar(
            tolov=royxat.shartlar.get("tolov", ""),
            yetkazish=str(javoblar.get("yetkazish")
                          or royxat.shartlar.get("yetkazish", "")),
            kafolat=royxat.shartlar.get("kafolat", ""),
            amal_qilish_muddati=royxat.shartlar.get("amal_qilish_muddati", ""),
            maxsus=[javoblar["shartlar"]] if javoblar.get("shartlar") else [],
        ),
        rekvizitlar=rekvizit,
        valyuta=royxat.valyuta,
        qqs_foizi=royxat.qqs_foizi,
        til=til,
        ogohlantirishlar=ogohlantirishlar,
        kirish_matni=royxat.kirish_matni(til),
        shartlar_matni=royxat.shartlar_matni(til) + (
            [_kurs_matni(kurs, til)] if kursdan else []
        ) + (
            [_qamrov_izohi(til)] if javoblar.get("yol") == "obyekt" else []
        ),
        narx_amal_oxiri=date.today() + timedelta(days=royxat.narx_amal_kuni),
    )


def _markaziy_kp(
    javoblar: dict[str, Any],
    hisob: dict[str, Any],
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    raqam: str,
    kurs: float,
    royxat: Any,
    rekvizit: dict[str, Any],
    til: str,
    ogohlantirishlar: list[str],
) -> Natija:
    """Markaziy qurilmali KP: bitta КЦКП + panjaralar.

    Isitgich, sovutgich, filtr va ventilyator QURILMA ICHIDA — ular
    alohida qator bo'lib qo'yilmaydi, aks holda mijoz ikki marta
    to'lardi.
    """
    from hisob import markaziy_tanla

    sarf = float(hisob.get("sarf") or 0)
    tanlangan = markaziy_tanla(parametrlar, sarf)
    if tanlangan is None:
        return Natija(
            aniqlik=Aniqlik(
                savol=(f"{sarf:.0f} m³/soat ga mos markaziy qurilma (КЦКП) "
                       "katalogda topilmadi."),
                tanlovlar=[{"qiymat": TARQOQQA_OT,
                            "yorliq": "🔀 Tarqoq tizimga o'tish"}],
            ),
            hisob=hisob,
            ogohlantirishlar=ogohlantirishlar,
        )

    narxsiz: list[str] = []
    narx = katalog_narxi_xavfsiz(katalog, tanlangan.nomi, kurs, royxat.qqs_foizi)
    if narx is None:
        narxsiz.append(tanlangan.nomi)
    qatorlar = [Qator(
        nomi=tanlangan.nomi,
        spetsifikatsiya=(
            f"{_t(til, 'markaziy')}, {sarf:.0f} {_t(til, 'sarf')} "
            f"({tanlangan.sigim:.0f} gacha)"
        ),
        miqdor=1, birlik=_birlik(til),
        birlik_narx=narx[0] if narx else None,
        narx_sanasi=date.today().isoformat() if narx else "",
        qqs_foizi=royxat.qqs_foizi,
    )]
    ogohlantirishlar.append(
        f"Markaziy qurilma tanlandi ({tanlangan.nomi}, "
        f"+{tanlangan.zaxira * 100:.0f}% zaxira). Ventilyator, isitgich, "
        "sovutgich va filtr uning ICHIDA — alohida qator qo'yilmadi. "
        "Qurilmaga alohida ventkamera kerak."
    )

    # SANUZEL SO'RISHI MARKAZIY QURILMAGA ULANMAYDI.
    #
    # КЦКП kirish tomonini qoplaydi, lekin `faqat_sorish` xonalari
    # alohida tizim: ularning havosi boshqa xonalarga aralashtirilmaydi.
    # Bu qator bo'lmasa KP da sanuzel panjaralari turadi-yu, ularni
    # tortadigan ventilyator bo'lmaydi (jonli holat, 2026-08-26).
    if hisob.get("sorish_sarfi"):
        qatorlar += _sorish_ventilyatori(
            hisob, parametrlar, katalog, kurs, royxat.qqs_foizi,
            narxsiz, ogohlantirishlar, til, javoblar,
        )

    # Panjaralar baribir kerak — havo binoga ular orqali tarqaladi.
    qatorlar += _panjaralar(
        javoblar, hisob.get("xonalar"), katalog, sarf, kurs,
        royxat.qqs_foizi, narxsiz, ogohlantirishlar, til,
    )
    if narxsiz:
        ogohlantirishlar.append(
            "Narx topilmadi (qator bo'sh qoldi): " + ", ".join(narxsiz)
            + " — buxgalteriyadan so'raladi"
        )
    return Natija(
        kp=_kp_yasa(javoblar, qatorlar, raqam, royxat, rekvizit, til,
                    kurs, ogohlantirishlar),
        ogohlantirishlar=ogohlantirishlar,
        hisob=hisob,
    )


def yig(
    javoblar: dict[str, Any],
    katalog: list[dict[str, Any]],
    *,
    raqam: str,
    kurs: float,
    parametrlar: dict[str, dict[str, Any]] | None = None,
    til: str = "uz",
    menejer: dict[str, str] | None = None,
) -> Natija:
    """Shakl javoblaridan KP. LLM chaqirilmaydi."""
    royxat = narxlar()
    rekvizit = dict(rekvizitlar())
    if menejer:
        # `kp/hujjat.py` aynan shu ikki kalitni o'qiydi — boshqacha nomlansa
        # menejer bloki hujjatda BO'SH chiqadi.
        rekvizit["menejer"] = menejer.get("ism", "")
        rekvizit["menejer_telefon"] = menejer.get("telefon", "")

    ogohlantirishlar: list[str] = []
    hisob: dict[str, Any] | None = None

    if javoblar.get("yol") == "obyekt":
        hisob = hisobni_bajar(javoblar)
        ogohlantirishlar += hisob["ogohlantirishlar"]
        bosim_oraligi = hisob.get("bosim")

        # MARKAZIY QURILMA tanlangan — ventilyator, isitgich, sovutgich
        # va filtr uning ICHIDA. Alohida ventilyator qidirilmaydi.
        if javoblar.get("markaziy") == "ha":
            return _markaziy_kp(
                javoblar, hisob, parametrlar or {}, katalog, raqam, kurs,
                royxat, rekvizit, til, ogohlantirishlar,
            )

        # MENEJER O'ZI KO'RSATGAN model — katalogda mos narxli uskuna
        # topilmaganda so'raladi (`bot/kp_oqim.py::_aniqlikni_yop`).
        # Bu holatda ham obyekt yo'li davom etadi: panjara, qo'shimcha
        # uskuna va yo'nalish baribir hisoblanadi.
        qol_uskuna = str(javoblar.get("qol_uskuna") or "").strip()
        if qol_uskuna:
            qol_narx = katalog_narxi_xavfsiz(katalog, qol_uskuna, kurs, royxat.qqs_foizi)
            nomzodlar = [{
                "nomi": qol_uskuna,
                "sarf": [],
                "narx_som": qol_narx[0] if qol_narx else None,
            }]
            if qol_narx is None:
                ogohlantirishlar.append(
                    f"{qol_uskuna}: narx katalogda yo'q — buxgalteriyadan so'ralsin"
                )
        else:
            nomzodlar = _uskuna_tanla(
                parametrlar or {}, katalog, hisob["sarf"], kurs, bosim_oraligi,
                royxat.qqs_foizi,
            )
        if not nomzodlar:
            narxsiz_mos = _narxsiz_mos(parametrlar or {}, hisob["sarf"], bosim_oraligi)
            savol = (f"{hisob['sarf']:.0f} m³/soat va ~{bosim_oraligi[1] if bosim_oraligi else '?'} "
                     "Pa bosimga mos, NARXI BOR uskuna katalogda topilmadi.")
            if narxsiz_mos:
                savol += (f" Sarf va bosim bo'yicha mos keladigan {len(narxsiz_mos)} ta "
                          "model bor, lekin narxi kiritilmagan.")
            # SABABINI AYTAMIZ. Menejer hamma qismni tanlaganda bosim
            # ko'tarilib ketadi va hech qanday ventilyator mos kelmay
            # qoladi — natijada KP da MAHSULOT KAMAYADI. Sababi
            # aytilmasa bu tushunarsiz: «ko'proq tanladim, kamroq
            # chiqdi» (jonli e'tiroz, 2026-08-26).
            sabab = _bosim_sababi(parametrlar or {}, katalog, hisob, kurs, royxat.qqs_foizi)
            if sabab:
                savol += " " + sabab
            savol += " Model nomini o'zingiz ko'rsatasizmi?"
            return Natija(
                aniqlik=Aniqlik(savol=savol,
                                variantlar=[{"nomi": n, "quvvat": "", "narx_som": None}
                                            for n in narxsiz_mos]),
                hisob=hisob,
                ogohlantirishlar=ogohlantirishlar,
            )
        spetsifikatsiya = (
            f"{hisob['sarf']:.0f} {_t(til, 'sarf')}, "
            + _t(til, "kanal", d=hisob["diametr"])
        )
        if bosim_oraligi:
            kalit = "bosim_aniq" if hisob.get("bosim_aniq") else "bosim"
            spetsifikatsiya += ", " + _t(
                til, kalit, a=bosim_oraligi[0], b=bosim_oraligi[1])
        # Kirish + chiqish tizimida IKKITA ventilyator: biri toza havo
        # beradi, ikkinchisi ishlatilganini so'rib chiqaradi.
        #
        # Yo'nalish SHU YERDA ham `_yonalishni_tekshir` orqali olinadi:
        # aks holda sanuzelga panjara bittada (so'rish) chiqib,
        # ventilyator ikkita bo'lib qolardi — hujjat o'z ichida zid.
        # Ogohlantirish takrorlanmasin uchun bo'sh ro'yxatga yoziladi.
        yonalish = _yonalishni_tekshir(javoblar, [])
        vent_soni, _panjaralar = YONALISH_TARKIBI[yonalish]
        if vent_soni > 1:
            spetsifikatsiya += f" ({_t(til, 'ikki_yonalish')})"
        qatorlar = [Qator(
            nomi=nomzodlar[0]["nomi"],
            spetsifikatsiya=spetsifikatsiya,
            miqdor=float(vent_soni), birlik=_birlik(til),
            birlik_narx=nomzodlar[0]["narx_som"],
            narx_sanasi=(date.today().isoformat()
                         if nomzodlar[0]["narx_som"] is not None else ""),
            qqs_foizi=royxat.qqs_foizi,
        )]
        narxsiz: list[str] = []
        if nomzodlar[0]["narx_som"] is None:
            # Texnik jihatdan eng mosi tanlandi, lekin narxi katalogda
            # yo'q. To'g'ri uskunali narxsiz KP — uskunasiz KP dan
            # foydaliroq: menejer narxni buxgalteriyadan oladi.
            narxsiz.append(nomzodlar[0]["nomi"])
        if len(nomzodlar) > 1:
            ogohlantirishlar.append(
                f"{hisob['sarf']:.0f} m³/soat ga {len(nomzodlar)} ta model mos "
                f"keladi — ortiqcha zaxirasi eng kami olindi "
                f"({nomzodlar[0]['nomi']}, +{nomzodlar[0]['zaxira'] * 100:.0f}%). "
                "Boshqasi kerak bo'lsa nomini ayting."
            )
        # SO'RISH TIZIMI ALOHIDA VENTILYATOR talab qiladi.
        # Sanuzel havosi boshqa xonalar bilan bitta kanalga qo'shilmaydi —
        # aks holda hid butun binoga tarqaladi. Shuning uchun bu guruhga
        # o'z ventilyatori tanlanadi.
        if hisob.get("sorish_sarfi") and hisob.get("kirish_sarfi"):
            qatorlar += _sorish_ventilyatori(
                hisob, parametrlar or {}, katalog, kurs, royxat.qqs_foizi,
                narxsiz, ogohlantirishlar, til, javoblar,
            )
        qatorlar += _qoshimcha_qatorlar(
            javoblar, parametrlar or {}, katalog, hisob["sarf"], kurs,
            royxat.qqs_foizi, narxsiz, ogohlantirishlar,
            xonalar=hisob.get("xonalar"), til=til,
        )
    else:
        qatorlar, narxsiz, aniqlik, qisqartma_ogohi = _qatorlar_modeldan(
            javoblar.get("mahsulotlar") or [], katalog, kurs, royxat.qqs_foizi,
            til,
        )
        if aniqlik is not None:
            return Natija(aniqlik=aniqlik, ogohlantirishlar=ogohlantirishlar)
        # Qisqartma tarjimasi ogohlantirishlari (`kp/qisqartma.py`) —
        # TAKRORSIZ, chunki bir xil bo'lim bir necha qatorda uchraydi.
        for o in qisqartma_ogohi:
            if o not in ogohlantirishlar:
                ogohlantirishlar.append(o)

    if narxsiz:
        ogohlantirishlar.append(
            "Narx topilmadi (qator bo'sh qoldi): " + ", ".join(narxsiz)
            + " — buxgalteriyadan so'raladi"
        )

    kp = _kp_yasa(javoblar, qatorlar, raqam, royxat, rekvizit, til,
                  kurs, ogohlantirishlar)
    return Natija(kp=kp, ogohlantirishlar=ogohlantirishlar, hisob=hisob)
