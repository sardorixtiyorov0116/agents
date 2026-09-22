"""Tizimning bosim yo'qotishini BAHOLASH.

NEGA KERAK
----------
Ventilyatorni faqat havo sarfi bo'yicha tanlab bo'lmaydi. Ventilyator
o'z tavsifi tizim tavsifi bilan kesishgan **ish nuqtasida** ishlaydi.
Sarfi yetadigan, lekin bosimi yetmaydigan ventilyator o'rnatilsa,
mijoz "ishlayapti, lekin havo yo'q" deydi.

Jonli misol (2026-08-11): 800 m² omborga 8000 m³/soat kerak edi.
Katalogda ikkala model ham sarf bo'yicha "yetardi":

    ВО 12-300-6,3   6150–10000 m³/soat,   50–95 Pa   <- kanalli tizimga YARAMAYDI
    ВЦ 14-46-5      5000–8400 m³/soat,  860–1070 Pa  <- to'g'ri

Farq bosimda. Bu modul shu farqni ko'radigan qiladi.

BU ANIQ HISOB EMAS
------------------
Aniq aerodinamik hisob tarmoq sxemasini talab qiladi (har uchastka
uzunligi, har burilish, har o'tish) — u loyihachi ishi. Bu modul
BAHOLAYDI: kanal uzunligi va uskunalar ro'yxatidan taxminiy bosimni
chiqaradi va natija taxmin ekanini ochiq aytadi.

Formulalar kodda, model ularga aralashmaydi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Havo zichligi, kg/m³ (20 °C, normal bosim).
HAVO_ZICHLIGI = 1.2

# To'g'ri kanalda solishtirma ishqalanish, Pa/m.
# Odatiy tezlikda (5–8 m/s) amaliy qiymat 0,8–1,5 — o'rtasini olamiz.
ISHQALANISH = 1.1

# Mahalliy qarshilik koeffitsiyentlari (ζ).
# Manba: umumiy muhandislik amaliyoti, `Bosim yo'qotishi — tizim
# tavsifi` yozuvidagi jadval bilan bir xil.
QARSHILIK = {
    "burilish_yumshoq": 0.25,
    "burilish_keskin": 1.1,
    "burilish_45": 0.15,
    "tarmoq_otish": 0.35,
    "tarmoq_shoxobcha": 1.2,
    "kengayish": 0.7,
    "panjara": 2.0,
    "taqsimlagich": 2.2,
}

# Uskunalarning bosim yo'qotishi, Pa.
#
# FILTR IFLOS holatida olinadi. Toza filtr bo'yicha hisoblansa tizim
# faqat birinchi oyda ishlaydi — filtr to'lgach sarf tushib ketadi.
USKUNA = {
    "filtr_g4": 200,
    "filtr_f7": 300,
    "isitgich_suvli": 120,
    "isitgich_elektr": 40,
    "sovutgich": 160,
    "rekuperator": 250,
    "shovqin_yutgich": 60,
    "klapan": 30,
    "olovni_tosuvchi_klapan": 30,
}

# Hisoblangan bosimga qo'shiladigan zaxira.
# Kanal amalda uzunroq quriladi, ulanish sizadi, o'lchov xatosi bor.
ZAXIRA = 0.12

# Bundan yuqori bosim kanal o'lchami noto'g'ri tanlanganini bildiradi.
JUDA_YUQORI = 2000.0


@dataclass(frozen=True)
class BosimHisobi:
    """Tizimning taxminiy bosim yo'qotishi."""

    ishqalanish: float          # Pa — kanal uzunligi bo'yicha
    mahalliy: float             # Pa — burilish, tarmoq, panjara
    uskunalar: float            # Pa — filtr, isitgich va h.k.
    zaxira: float               # Pa
    jami: float                 # Pa — hammasi qo'shilgan
    tezlik: float               # m/s — hisobda ishlatilgan
    ogohlantirishlar: list[str] = field(default_factory=list)

    @property
    def taxminiy(self) -> bool:
        """Bu qiymat har doim taxmin — aniq hisob loyihachi ishi."""
        return True


def dinamik_bosim(tezlik: float) -> float:
    """`ρ·v²/2` — mahalliy qarshiliklar shunga ko'paytiriladi."""
    return HAVO_ZICHLIGI * max(tezlik, 0.0) ** 2 / 2


def bosim_yoqotishi(
    tezlik: float,
    kanal_uzunligi: float = 0.0,
    qarshiliklar: dict[str, int] | None = None,
    uskunalar: list[str] | None = None,
) -> BosimHisobi:
    """Tizimning taxminiy bosim yo'qotishi.

    `tezlik` — kanaldagi haqiqiy havo tezligi (m/s), `kanal_olchami`
    dan olinadi. `qarshiliklar` — element nomi -> soni.
    """
    ogohlantirishlar: list[str] = []

    ishqalanish = ISHQALANISH * max(kanal_uzunligi, 0.0)

    dinamik = dinamik_bosim(tezlik)
    mahalliy = 0.0
    for nomi, soni in (qarshiliklar or {}).items():
        koeffitsiyent = QARSHILIK.get(nomi)
        if koeffitsiyent is None:
            ogohlantirishlar.append(f"noma'lum qarshilik turi: {nomi}")
            continue
        mahalliy += koeffitsiyent * dinamik * max(int(soni), 0)

    uskuna_bosimi = 0.0
    for nomi in uskunalar or []:
        qiymat = USKUNA.get(nomi)
        if qiymat is None:
            ogohlantirishlar.append(f"noma'lum uskuna: {nomi}")
            continue
        uskuna_bosimi += qiymat

    asosiy = ishqalanish + mahalliy + uskuna_bosimi
    zaxira = asosiy * ZAXIRA
    jami = asosiy + zaxira

    if jami > JUDA_YUQORI:
        ogohlantirishlar.append(
            f"bosim juda yuqori ({jami:.0f} Pa) — kanal diametri kichik "
            "bo'lishi mumkin, tarmoq sxemasi qayta ko'rilsin"
        )
    if kanal_uzunligi <= 0 and not (qarshiliklar or uskunalar):
        ogohlantirishlar.append(
            "tarmoq ma'lumoti berilmadi — bosim baholanmadi"
        )

    return BosimHisobi(
        ishqalanish=round(ishqalanish, 1),
        mahalliy=round(mahalliy, 1),
        uskunalar=round(uskuna_bosimi, 1),
        zaxira=round(zaxira, 1),
        jami=round(jami, 1),
        tezlik=round(tezlik, 2),
        ogohlantirishlar=ogohlantirishlar,
    )


def yetadimi(
    ventilyator_bosimi: float | list | None, kerakli: float
) -> bool | None:
    """Ventilyatorning bosimi tizimga yetadimi.

    Katalogda bosim bitta son yoki oraliq bo'lishi mumkin. Oraliq
    bo'lsa MAKSIMALI olinadi — ventilyator eng katta bosimni eng
    kichik sarfda beradi, ya'ni bu yuqori chegara.

    Qiymat noma'lum bo'lsa `None` — "yaramaydi" DEB HISOBLANMAYDI,
    chunki katalogda ma'lumot yo'qligi ventilyator yomon degani emas.
    """
    if kerakli <= 0:
        return None
    if isinstance(ventilyator_bosimi, (list, tuple)):
        if not ventilyator_bosimi:
            return None
        eng_kop = max(float(x) for x in ventilyator_bosimi)
    elif isinstance(ventilyator_bosimi, (int, float)):
        eng_kop = float(ventilyator_bosimi)
    else:
        return None
    return eng_kop >= kerakli


# Tarmoq murakkabligi bo'yicha tayyor baholar. Foydalanuvchi tarmoq
# sxemasini bermasa shulardan foydalaniladi — "bilmadim" deyishdan
# ko'ra oraliq berish foydali, faqat taxmin ekani aytiladi.
TIPIK_TARMOQ = {
    "oddiy": {
        "izoh": "qisqa kanal, uskunasiz (devordan devorga)",
        "oraliq": (100, 250),
    },
    "kanalli": {
        "izoh": "kanalli tizim, panjaralar bilan",
        "oraliq": (250, 450),
    },
    "filtrli": {
        "izoh": "filtr va isitgich bilan kirish tizimi",
        "oraliq": (500, 900),
    },
    "toliq": {
        "izoh": "rekuperator + filtr + sovutgich",
        "oraliq": (900, 1400),
    },
}


def tipik_bosim(tarmoq: str) -> tuple[int, int] | None:
    """Tarmoq turiga ko'ra taxminiy bosim oralig'i."""
    yozuv = TIPIK_TARMOQ.get(tarmoq)
    return tuple(yozuv["oraliq"]) if yozuv else None


# Kanal tarmog'ining O'ZI yo'qotadigan bosim (uskunasiz): quvur
# ishqalanishi, burilishlar, panjaralar. `TIPIK_TARMOQ["kanalli"]` bilan
# bir xil — u aynan shu holatni bildiradi.
TARMOQ_ASOSI = (250, 450)
# Qisqa, devordan devorga kanal uchun.
QISQA_ASOS = (100, 250)


def yigilgan_bosim(
    uskunalar: list[str] | tuple[str, ...], kanalli: bool = True
) -> tuple[int, int]:
    """Tanlangan uskunalar bo'yicha bosim oralig'i.

    NEGA KERAK: `TIPIK_TARMOQ` da to'rtta TAYYOR to'plam bor va ular
    bir-birini istisno qiladi. Menejer "filtr + sovutgich, lekin
    rekuperatorsiz" desa — mos variant yo'q edi.

    Bu yerda oraliq YIG'ILADI: kanal tarmog'ining o'z yo'qotishi +
    har bir tanlangan uskunaning yo'qotishi (`USKUNA` jadvali).

    Tekshiruv: kanalli + filtr + isitgich = 570-770 Pa, eski `filtrli`
    to'plami esa 500-900 Pa edi — ya'ni yig'ma hisob tayyor to'plamlarni
    taxminan takrorlaydi, lekin ISTALGAN birikmani ham beradi.
    """
    past, yuqori = TARMOQ_ASOSI if kanalli else QISQA_ASOS
    qoshimcha = sum(USKUNA.get(nom, 0) for nom in uskunalar)
    return past + qoshimcha, yuqori + qoshimcha
