"""So'rovnoma savatidan KP LOYIHASI.

NEGA LOYIHA, TAYYOR KP EMAS
---------------------------
KP — tijorat majburiyati: blankada kompaniya nomi, direktor imzosi va
"narxlar 30 kun amal qiladi" degan qator turadi. Uni botga yozgan
istalgan odamga avtomat yuborish narx E'LON QILISH degani. Narx xato
bo'lsa (kurs eskirgan, chegirma hisobga olinmagan, mijoz maxsus
shartli) — nizoni bekor qilib bo'lmaydi.

Shuning uchun hujjat MENEJERGA boradi. Uning oldida ikkita yo'l:
tugmani bosib botdan yuborish yoki o'zi yuborish. Menejerning vaqti KP
TUZISHGA ketadi, yuborishga emas — shu qism avtomatlashadi va oxirgi
qadamda odam qoladi.

NARX QAMROVI (2026-08-27 da o'lchandi)
--------------------------------------
Filtr 17/17, panjara 136/264, ventilyator 83/244 modelda narx bor.
Ya'ni bu bo'limlarda KP ko'pincha TO'LIQ chiqadi — umumiy katalogdagi
24/1482 raqamiga qarab kutilganidan ancha yaxshi. Qolgan bo'limlarda
narx kamroq: qator baribir qo'yiladi, narx BO'SH qoladi va menejerga
«buxgalteriyadan so'ralsin» deb belgilanadi.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from kp.model import KP, Mijoz, Qator, Shartlar

from .talab import SorovnomaShakli, bolim

log = logging.getLogger("sorovnoma.kp")

# Model nomi javoblardan YIG'ILADI: katalogda u "РВН 500х300"
# ko'rinishida turadi, mijoz esa modelni va o'lchamni alohida
# tanlaydi. Qaysi javoblardan yig'ilishi YAML da (`nom_qolipi`).
#
# Kirilcha «х» — LOTIN «x» EMAS. Katalogda kirillchasi ishlatilgan va
# lotincha bilan qidirsak hech nima topilmasdi.
OLCHAM_AJRATGICHI = "х"


def _olcham_normal(matn: str) -> str:
    """«500x300», «500 х 300», «500*300» -> «500х300» (kirilcha)."""
    toza = str(matn or "").strip().lower()
    for belgi in ("x", "х", "*", "×", "на"):
        toza = toza.replace(belgi, "|")
    bolaklar = [b.strip() for b in toza.split("|") if b.strip()]
    return OLCHAM_AJRATGICHI.join(bolaklar) if len(bolaklar) >= 2 else ""


# Qolipda o'lcham sifatida ishlatiladigan kalitlar — ular kirilcha
# «х» ga keltiriladi (`_olcham_normal`).
OLCHAM_KALITLARI = ("olcham", "kesim")


def model_nomi(bolim_kaliti: str, javoblar: dict[str, Any]) -> str:
    """Javoblardan katalogdagi model nomini yig'adi. Yig'ilmasa bo'sh.

    Qolip YAML da yoziladi (`nom_qolipi`), kodda emas: 12 ta bo'lim
    bor va har birining nom tuzilishi boshqacha. Kodda bo'lsa yangi
    bo'lim qo'shish dasturchi ishi bo'lardi.

    Qolip FORMAT SATRI: `{kalit}` javob bilan almashadi, qolgani
    o'zgarishsiz qoladi. Shu tufayli javobga bog'liq bo'lmagan nom ham
    yozish mumkin (`nom_qolipi: "ВГ"`) — gradirnya va chillerda
    mijozning javoblari model nomini bermaydi, lekin oila nomi
    "aniqlanmadi" dan foydaliroq.

    Javob BO'SH bo'lsa o'sha bo'lak tushib qoladi, nom esa YASALADI:
    «РВН» ham «РВН 500х300» kabi qidiriladi va oila darajasidagi narx
    topilishi mumkin.
    """
    from .talab import bolim

    b = bolim(bolim_kaliti)
    if b is None or not b.nom_qolipi:
        return ""

    natija = b.nom_qolipi
    for kalit in _qolip_kalitlari(b.nom_qolipi):
        xom = str(javoblar.get(kalit) or "").strip()
        agar_olcham = kalit in OLCHAM_KALITLARI
        qiymat = (_olcham_normal(xom) or xom) if agar_olcham else xom
        natija = natija.replace("{" + kalit + "}", qiymat)
    # Bo'sh javoblardan qolgan ortiqcha bo'shliqlar yig'ishtiriladi.
    return " ".join(natija.split())


def _qolip_kalitlari(qolip: str) -> list[str]:
    """«{model} {olcham}» -> ["model", "olcham"] — TARTIB saqlanadi."""
    import re

    return re.findall(r"\{(\w+)\}", qolip)


def _miqdor(javoblar: dict[str, Any]) -> float:
    try:
        return max(float(javoblar.get("soni") or 1), 1.0)
    except (TypeError, ValueError):
        return 1.0


def _spetsifikatsiya(shakl: SorovnomaShakli) -> str:
    """Mijoz bergan javoblar — KP ning «O'lchov» ustuni uchun.

    Nomga sig'magan hamma narsa shu yerda qoladi: iqlim ijrosi, RAL
    rangi, KRV. Menejer ularni qayta so'ramasin.
    """
    from .oqim import _yorliq

    bolaklar = []
    for kalit, qiymat in shakl.javoblar.items():
        if kalit == "soni" or not str(qiymat).strip():
            continue
        savol, javob = _yorliq(shakl, kalit, qiymat)
        bolaklar.append(javob)
    return ", ".join(bolaklar)


def _ventilyator_qatori(
    javoblar: dict[str, Any],
    parametrlar: dict[str, dict[str, Any]],
    katalog: list[dict[str, Any]],
    kurs: float,
    qqs: float,
    ogohlantirishlar: list[str],
) -> str:
    """Sarf va bosimga qarab model tanlaydi. Topilmasa bo'sh satr.

    Mijoz model nomini bilmaydi — u «8000 m³/soat, 450 Pa» deydi. Bu
    KP ning B yo'li (`kp/shakldan.py`), shuning uchun o'sha tanlovchi
    qayta ishlatiladi: ikkinchi marta yozilsa mezonlar ajralib ketardi.
    """
    from kp.shakldan import _uskuna_tanla

    try:
        sarf = float(javoblar.get("sarf") or 0)
    except (TypeError, ValueError):
        sarf = 0.0
    if sarf <= 0:
        ogohlantirishlar.append(
            "Ventilyator: havo sarfi ko'rsatilmagan — model menejer "
            "tomonidan tanlansin")
        return ""

    bosim_oraligi = None
    try:
        bosim = float(javoblar.get("bosim") or 0)
        if bosim > 0:
            bosim_oraligi = (int(bosim), int(bosim))
    except (TypeError, ValueError):
        pass

    nomzodlar = _uskuna_tanla(parametrlar, katalog, sarf, kurs,
                             bosim_oraligi, qqs)
    if not nomzodlar:
        ogohlantirishlar.append(
            f"Ventilyator: {sarf:.0f} m³/soat"
            + (f", {bosim_oraligi[0]} Pa" if bosim_oraligi else "")
            + " uchun katalogda mos model topilmadi")
        return ""
    return str(nomzodlar[0]["nomi"])


def _narx_qidirilsinmi(bolim_kaliti: str, nom: str) -> bool:
    """Bu nom bilan katalogdan narx qidirish MA'NOLIMI?

    JONLI XATO (2026-08-28): chiller bo'limi qatori «Chiller» deb
    nomlandi va katalogdan «Sovitish mashinasi JV (chiller) / JV-65»
    ga tushib, KP ga 11 063 so'm narx yozildi. Mijoz esa 120 kVt
    so'ragan edi — JV-65 butunlay boshqa o'lcham.

    QOIDA: qolip faqat HARFLI matndan iborat bo'lsa (masalan "ВГ",
    "Chiller"), nom mijozning javoblaridan hech narsa olmaydi. Bunday
    umumiy nom bilan topilgan narx TASODIFIY bo'ladi — qaysi model
    birinchi mos kelsa, o'shaniki.

    Bo'sh narxli qator menejerga tushunarli: u to'ldiradi. NOTO'G'RI
    narxli qator esa tekshirilmasdan mijozga ketishi mumkin.
    """
    from .talab import bolim

    b = bolim(bolim_kaliti)
    if b is None or not b.nom_qolipi:
        return True                      # nom boshqa yo'l bilan aniqlangan
    return bool(_qolip_kalitlari(b.nom_qolipi))


def _markaziy_qatori(
    javoblar: dict[str, Any],
    parametrlar: dict[str, dict[str, Any]],
    ogohlantirishlar: list[str],
) -> str:
    """Sarfga yetadigan eng kichik КЦКП. Topilmasa bo'sh satr."""
    from hisob.markaziy import markaziy_tanla

    try:
        sarf = float(javoblar.get("sarf") or 0)
    except (TypeError, ValueError):
        return ""
    if sarf <= 0:
        return ""
    tanlov = markaziy_tanla(parametrlar, sarf)
    if tanlov is None:
        ogohlantirishlar.append(
            f"КЦКП: {sarf:.0f} m³/soat uchun katalogda mos qurilma topilmadi")
        return ""
    return str(tanlov.nomi)


def savatdan_qatorlar(
    savat: list[dict[str, Any]],
    katalog: list[dict[str, Any]],
    parametrlar: dict[str, dict[str, Any]],
    kurs: float,
    qqs: float,
) -> tuple[list[Qator], list[str], list[str]]:
    """(qatorlar, ogohlantirishlar, narxsiz modellar)."""
    from kp.shakldan import katalog_narxi_xavfsiz

    qatorlar: list[Qator] = []
    ogohlantirishlar: list[str] = []
    narxsiz: list[str] = []

    for pozitsiya in savat:
        kalit = str(pozitsiya.get("bolim") or "")
        javoblar = dict(pozitsiya.get("javoblar") or {})
        b = bolim(kalit)
        shakl = SorovnomaShakli(bolim_kaliti=kalit, javoblar=javoblar)

        nom = model_nomi(kalit, javoblar)
        if not nom and kalit == "ventilyator":
            nom = _ventilyator_qatori(javoblar, parametrlar, katalog,
                                      kurs, qqs, ogohlantirishlar)
        elif kalit == "kckp":
            # КЦКП o'lchami SARFGA qarab tanlanadi — mijoz uni bilmaydi.
            # `hisob/markaziy.py` dagi tanlovchi qayta ishlatiladi:
            # ikkinchi marta yozilsa mezonlar ajralib ketardi.
            nom = _markaziy_qatori(javoblar, parametrlar, ogohlantirishlar) or nom
        if not nom:
            # Model aniqlanmadi — qator baribir QO'YILADI, chunki mijoz
            # buni so'ragan. Menejer nomni o'zi yozadi.
            nom = f"{b.nomi if b else kalit} — model aniqlanmadi"
            ogohlantirishlar.append(
                f"{b.nomi if b else kalit}: model aniqlanmadi, menejer tanlasin")

        narx = (katalog_narxi_xavfsiz(katalog, nom, kurs, qqs)
                if _narx_qidirilsinmi(kalit, nom) else None)
        if narx is None:
            narxsiz.append(nom)

        qatorlar.append(Qator(
            nomi=nom,
            spetsifikatsiya=_spetsifikatsiya(shakl),
            miqdor=_miqdor(javoblar),
            birlik="dona",
            birlik_narx=narx[0] if narx else None,
            narx_sanasi=date.today().isoformat() if narx else "",
            qqs_foizi=qqs,
        ))
    return qatorlar, ogohlantirishlar, narxsiz


def loyiha_yasa(
    savat: list[dict[str, Any]],
    raqam: str,
    mijoz_nomi: str,
    aloqa: str,
    katalog: list[dict[str, Any]],
    parametrlar: dict[str, dict[str, Any]],
    kurs: float,
    royxat: Any,
    rekvizit: dict[str, str],
    til: str = "uz",
) -> KP:
    """Savatdan KP loyihasi."""
    qqs = float(getattr(royxat, "qqs_foizi", 0) or 0)
    qatorlar, ogohlantirishlar, narxsiz = savatdan_qatorlar(
        savat, katalog, parametrlar, kurs, qqs)

    if narxsiz:
        ogohlantirishlar.append(
            "Narx topilmadi (qator bo'sh qoldi): "
            + ", ".join(narxsiz) + " — buxgalteriyadan so'raladi")

    # Bu ogohlantirish HUJJATDA qoladi va menejer uni o'chirmasa mijoz
    # ham ko'radi. Ataylab shunday: loyiha tekshirilmasdan yuborilsa,
    # buni hech bo'lmasa mijoz sezadi va so'raydi.
    ogohlantirishlar.insert(0, "So'rovnoma asosida tuzilgan dastlabki "
                               "hisob — menejer tasdiqlagach kuchga kiradi")

    from kp.shakldan import _kurs_matni

    kursdan = any(q.birlik_narx for q in qatorlar)
    return KP(
        raqam=raqam,
        sana=date.today(),
        mijoz=Mijoz(nomi=mijoz_nomi, aloqa=aloqa),
        qatorlar=qatorlar,
        shartlar=Shartlar(
            tolov=royxat.shartlar.get("tolov", ""),
            yetkazish=royxat.shartlar.get("yetkazish", ""),
            kafolat=royxat.shartlar.get("kafolat", ""),
            amal_qilish_muddati=royxat.shartlar.get("amal_qilish_muddati", ""),
        ),
        rekvizitlar=rekvizit,
        valyuta=royxat.valyuta,
        qqs_foizi=qqs,
        til=til,
        ogohlantirishlar=ogohlantirishlar,
        kirish_matni=royxat.kirish_matni(til),
        shartlar_matni=royxat.shartlar_matni(til) + (
            [_kurs_matni(kurs, til)] if kursdan else []),
    )
