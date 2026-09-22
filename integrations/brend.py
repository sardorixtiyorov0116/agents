"""Tender texnik topshirig'idan BEGONA brendni aniqlash.

NEGA KERAK
----------
Jasur lotni sarlavhasiga qarab "bizga mos" deydi. Brend esa sarlavhada
deyarli hech qachon yozilmaydi — o'lchandi (2026-09-14): 867 ta etender
sarlavhasida quyidagi lug'at BIRORTA ham moslik bermadi. Brend texnik
topshiriqda turadi.

JONLI HOLAT: 510351-lot "VRF tizimlarining tashqi bloklariga ta'mir"
"bizga mos" deb ko'rsatildi. Texnik topshiriqda esa "Марка/модель:
ARV6-H610/SR1MV" — bu AUX. Lotning 30 foizi (boshqaruv platasi) shu
brendning ORIGINAL qismini va aynan shu ishlab chiqaruvchi uskunasi
bilan tajribani talab qilardi. Menejer buni sarlavhadan bila olmasdi.

QAT'IY QOIDA
------------
Faqat ANIQ belgi hisobga olinadi: brend nomi butun so'z sifatida yoki
shu brendga xos model kodi (`ARV6-H610` — AUX, `GMV-` — Gree). "VRF",
"inverter" kabi umumiy so'zlar brend EMAS.

Umumiy so'z bilan to'qnashadigan nomlar faqat KONTEKSTDA hisoblanadi:
elektr sxemalarida "AUX" — qo'shimcha kontakt, "LG" — boshqa narsa
bo'lishi mumkin. Shuning uchun ular "марка/модель/кондиционер/VRF"
kabi so'z bilan BIR QATORDA kelgandagina brend deb olinadi.

Kirillcha "Гри", "Йорк" ataylab kiritilmagan ("Нью-Йорк"): noto'g'ri
ogohlantirish menejerni ogohlantirishlarga ishonmaydigan qilib qo'yadi.

Biz o'zimiz SOTADIGAN chet el brendlari (katalogda bor) begona emas —
ular `BIZ_SOTADIGAN` orqali chiqarib tashlanadi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BrendTopilma:
    """Topilgan begona brend va (bo'lsa) uning model kodi."""

    brend: str
    model: str = ""

    @property
    def korinish(self) -> str:
        """Menejerga ko'rinadigan matn: `AUX (ARV6-H610/SR1MV)`."""
        return f"{self.brend} ({self.model})" if self.model else self.brend


def _naqshlar(lugat: dict[str, tuple[str, ...]]) -> dict[str, tuple[re.Pattern[str], ...]]:
    return {brend: tuple(re.compile(n) for n in naqshlar) for brend, naqshlar in lugat.items()}


# Brendga XOS model kodlari — eng kuchli belgi, kontekst shart emas.
# Butun kod ushlanadi: menejer aynan qaysi uskuna ekanini ko'rsin.
MODEL_KODLARI = _naqshlar({
    "AUX": (r"\bARV\d?-[A-Z]?\d{3}[\w/.\-]*",),
    "Gree": (r"\bGMV\d?-[\w/.\-]+",),
    "LG": (r"\bARU[NMV]\d{3}[\w/.\-]*",),
    "Daikin": (r"\bRXY[S]?Q\d+[\w/.\-]*",),
    "Midea": (r"\bMV[68]-[\w/.\-]+",),
})

# Nomi o'ziga xos brendlar — kontekstsiz hisoblanadi.
ANIQ_NOMLAR = _naqshlar({
    "Daikin": (r"(?i)\bdaikin\b", r"(?i)\bдайкин\b"),
    "Midea": (r"(?i)\bmidea\b", r"(?i)\bмиде[аяи]\b", r"\bMDV\b"),
    "Gree": (r"\bGREE\b", r"\bGree\b"),
    "Haier": (r"(?i)\bhaier\b", r"(?i)\bхайер\b"),
    "Hisense": (r"(?i)\bhisense\b", r"(?i)\bхайсенс\b"),
    "Samsung": (r"(?i)\bsamsung\b", r"(?i)\bсамсунг\b"),
    "Mitsubishi": (r"(?i)\bmitsubishi\b", r"(?i)\bмицубиси\b", r"(?i)\bмицубиши\b"),
    "Toshiba": (r"(?i)\btoshiba\b", r"(?i)\bтошиба\b"),
    "Panasonic": (r"(?i)\bpanasonic\b", r"(?i)\bпанасоник\b"),
    "Fujitsu": (r"(?i)\bfujitsu\b",),
    "Hitachi": (r"(?i)\bhitachi\b",),
    "Tadiran": (r"(?i)\btadiran\b", r"(?i)\bтадиран\b"),
    "Chigo": (r"(?i)\bchigo\b",),
    "Clivet": (r"(?i)\bclivet\b",),
    "Swegon": (r"(?i)\bswegon\b",),
    "Systemair": (r"(?i)\bsystemair\b",),
    "Kentatsu": (r"(?i)\bkentatsu\b",),
    "Dantex": (r"(?i)\bdantex\b",),
    "Ballu": (r"(?i)\bballu\b",),
    "Electrolux": (r"(?i)\belectrolux\b",),
    "Shuft": (r"(?i)\bshuft\b",),
})

# Umumiy so'z bilan to'qnashadigan nomlar — faqat KONTEKST bilan bir qatorda.
KONTEKSTLI_NOMLAR = _naqshlar({
    "AUX": (r"\bAUX\b", r"\bAux\b"),
    "LG": (r"\bLG\b",),
    "TCL": (r"\bTCL\b",),
    "Carrier": (r"\bCarrier\b", r"\bCARRIER\b"),
    "Trane": (r"\bTrane\b", r"\bTRANE\b"),
    "York": (r"\bYork\b", r"\bYORK\b"),
    "Tica": (r"\bTica\b", r"\bTICA\b"),
})

KONTEKST = re.compile(
    r"марк|модел|бренд|brand|model|кондиц|konditsion|\bVRF\b|\bVRV\b|сплит|split"
    r"|чиллер|chiller|фанкойл|ishlab\s+chiqaruvchi|производител|завод",
    re.IGNORECASE,
)

# Katalogda bor — biz sotamiz, begona emas.
BIZ_SOTADIGAN: frozenset[str] = frozenset({"Vents"})


def begona_brendlar(
    matn: str, istisno: frozenset[str] | set[str] = BIZ_SOTADIGAN
) -> list[BrendTopilma]:
    """Matndagi begona brendlar ro'yxati (topilish tartibida, takrorsiz)."""
    if not matn:
        return []

    topilgan: dict[str, str] = {}   # brend -> birinchi model kodi

    for brend, naqshlar in MODEL_KODLARI.items():
        for naqsh in naqshlar:
            mos = naqsh.search(matn)
            if mos:
                topilgan.setdefault(brend, mos.group(0).rstrip(".,;:-/"))
                break

    for brend, naqshlar in ANIQ_NOMLAR.items():
        if brend not in topilgan and any(n.search(matn) for n in naqshlar):
            topilgan[brend] = ""

    for qator in matn.splitlines():
        if not KONTEKST.search(qator):
            continue
        for brend, naqshlar in KONTEKSTLI_NOMLAR.items():
            if brend not in topilgan and any(n.search(qator) for n in naqshlar):
                topilgan[brend] = ""

    chiqarish = {b.lower() for b in istisno}
    return [
        BrendTopilma(brend=b, model=m)
        for b, m in topilgan.items()
        if b.lower() not in chiqarish
    ]
