"""TZ jadvalini (Excel) mahsulot qatorlariga ajratish — miqdori bilan.

NEGA ALOHIDA MODUL
------------------
`kp/tz.py` TZ dan MATN oladi va uni modelga beradi — xonalar va model
nomlari uchun. Lekin ko'p TZ aslida TAYYOR SPETSIFIKATSIYA: «nom —
o'lcham — miqdor». Ularni modelsiz, aniq o'qish mumkin va kerak:
miqdor 74 bo'lsa, u 74 bo'lib qolishi shart (model 1 deb qo'yardi).

HAQIQIY TZ LAR SHUNDAY KELADI (tests/etalon_tz/, 2026-10-03)
------------------------------------------------------------
  * Ro'yxat: bo'lim sarlavhasi («Решетка АДН») + «Решетка 300x150 | шт | 57».
    Tur SARLAVHADA, qatorda faqat o'lcham.
  * Spetsifikatsiya (ГОСТ 21.110 shakli): «Позиция | Наименование | Тип |
    … | Ед. | Кол-во». Tizim qatori («ПВ1 | Система …:») va guruh qatori
    («Решётki и диффузоры:») miqdorsiz turadi.
  * Zayavka: ko'p qatorli sarlavha, parametr ustunlari (L, Р, N кВт),
    seksiya qatorlari («9 СЕКЦИЯ»).
  * Bir faylda IKKI BIR XIL varaq (`Лист1` va `ЗакСпец`) — ikkinchisi
    sanalmasligi kerak, aks holda hamma miqdor ikki barobar chiqadi.
  * Faylda TZ ga aloqasiz eski varaqlar (armatura, quvur zayavkalari).
    Ular tashlanmaydi — `varaq` maydoni bilan qaytadi, tekshiruvchi
    «HVAC ga aloqasi yo'q» deb ajratadi.

Bu modul HECH NARSA TAXMIN QILMAYDI: miqdor ustuni topilmagan varaq
qatorsiz qaytadi va `ogohlantirishlar` ga sababi yoziladi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Sarlavha kataklari.
_NOM = re.compile(r"наименован", re.I)
_MIQDOR = re.compile(r"^\s*(кол[-\s.]*во|количество|коли-?\s*чест-?\s*во|кол\.?)\s*$", re.I)
_BIRLIK = re.compile(r"ед\.?\s*-?\s*(изм|измер)|^ед\.?$|единица", re.I)
_TUR = re.compile(r"тип|марка", re.I)
_BELGI = re.compile(r"позиц|обозна", re.I)
_L = re.compile(r"\bL\b|м\s*3\s*/\s*ч|м³/ч", re.I)
_P = re.compile(r"^\s*[РP]\s*,|\bПа\b", re.I)
_N = re.compile(r"квт|кВт|N\s*,", re.I)

# Tizim belgisi: П1, В2, ПВ3, ДУ1, ПД2, К1, К6р, «К1, К4», «K8.K9».
TIZIM_BELGISI = re.compile(
    r"^\s*((?:ПВ|ПД|ДУ|ДП|ДВ|КВ|П|В|К|K|E|Е)\s*\d+[рРpа-я]?(?:\s*[,.]\s*(?:ПВ|ПД|ДУ|П|В|К|K)?\s*\d+[рРp]?)*)\.?\s*$")

# Sahifa shtampi va boshqa shovqin — guruh sarlavhasi bo'lmaydi.
_SHTAMP = re.compile(
    r"^(подп|изм|лист|разраб|инв|стадия|формат|взам|н\.?\s*контр|гип|"
    r"примечани|см\.|дата|кол\.?уч|№\s*док|надписи|люди|фио|шифр|название|"
    r"наименование$|уточнение|предприятие|сокращение|документ)", re.I)


@dataclass
class TzQator:
    nomi: str
    miqdor: float
    birlik: str = ""
    tizim: str = ""          # П1, В1, «К1, К4»
    guruh: str = ""          # eng yaqin miqdorsiz sarlavha: «Решетка АДН», «9 СЕКЦИЯ»
    bolim: str = ""          # seksiya / qavat darajasidagi sarlavha
    parametrlar: dict[str, float] = field(default_factory=dict)  # L, P, N
    matn: str = ""           # qatorning hamma kataklari — parametr qidirish uchun
    varaq: str = ""
    qator_n: int = 0


@dataclass
class TzJadval:
    yol: str
    qatorlar: list[TzQator] = field(default_factory=list)
    ogohlantirishlar: list[str] = field(default_factory=list)


def _matn(k) -> str:
    if k is None:
        return ""
    return re.sub(r"\s+", " ", str(k)).strip()


def _son(k) -> float | None:
    if isinstance(k, bool):
        return None
    if isinstance(k, (int, float)):
        return float(k)
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*", str(k or ""))
    return float(m.group(1).replace(",", ".")) if m else None


@dataclass
class _Ustunlar:
    nom: int | None = None
    miqdor: int | None = None
    birlik: int | None = None
    tur: list[int] = field(default_factory=list)
    belgi: int | None = None
    parametr: dict[str, int] = field(default_factory=dict)


def _sarlavha_ustunlari(qatorlar: list[tuple], i: int) -> _Ustunlar | None:
    """i-qator sarlavhami? Bo'lsa ustunlarni (keyingi 2 qator bilan) qaytaradi."""
    qator = [_matn(k) for k in qatorlar[i]]
    miqdor = [j for j, k in enumerate(qator) if _MIQDOR.match(k)]
    if not miqdor:
        return None
    # Ko'p qatorli sarlavhaning ICHKI qatorida ham «Кол-во» bo'ladi (filtr,
    # nasos soni). Uni asosiy sarlavha deb olsak, haqiqiy miqdor ustuni
    # yo'qoladi (1-juft zayavkasi 0 qator bo'lib chiqqan edi). Asosiy
    # sarlavhada «Наименование» yoki «Ед. изм» ham bo'ladi; yo'q bo'lsa —
    # qatorda deyarli boshqa hech narsa yo'q (faqat «Кол-во»).
    toliq = [k for k in qator if k]
    if not (any(_NOM.search(k) or _BIRLIK.search(k) for k in qator) or len(toliq) <= 2):
        return None
    u = _Ustunlar(miqdor=miqdor[0])
    # Sarlavha ko'p qatorli bo'lishi mumkin: parametrlar (L, Р) 2-qatorda.
    yorliqlar = list(qator)
    for keyingi in qatorlar[i + 1:i + 3]:
        for j, k in enumerate(keyingi):
            if j < len(yorliqlar) and isinstance(k, str):
                yorliqlar[j] = (yorliqlar[j] + " " + _matn(k)).strip()
    for j, k in enumerate(qator):
        if _NOM.search(k) and u.nom is None:
            u.nom = j
        elif _BIRLIK.search(k) and u.birlik is None:
            u.birlik = j
        elif _TUR.search(k):
            u.tur.append(j)
        elif _BELGI.search(k) and u.belgi is None:
            u.belgi = j
    for j, k in enumerate(yorliqlar):
        if j <= u.miqdor:
            continue
        if "L" not in u.parametr and _L.search(k):
            u.parametr["L"] = j
        elif "P" not in u.parametr and _P.search(k):
            u.parametr["P"] = j
        elif "N" not in u.parametr and _N.search(k):
            u.parametr["N"] = j
    return u


def _birinchi_belgi(kataklar: list[str], chegara: int) -> int | None:
    """Belgi ustuni nomlanmagan jadvalda tizim belgisi qaysi katakda.

    Odatda u qatordagi BIRINCHI to'ldirilgan katak («К1, К4»), lekin
    ustun raqami har faylda boshqa (4-juftda 2-ustun). Belgiga
    o'xshamasa — belgi yo'q.
    """
    for j, k in enumerate(kataklar[:chegara]):
        if k:
            return j if TIZIM_BELGISI.match(k) else None
    return None


def _varaq_qatorlari(nom: str, qatorlar: list[tuple]) -> tuple[list[TzQator], str]:
    natija: list[TzQator] = []
    u: _Ustunlar | None = None
    guruh = bolim = tizim = oxirgi_belgi = ""
    for i, xom in enumerate(qatorlar):
        yangi = _sarlavha_ustunlari(qatorlar, i)
        if yangi is not None:
            u = yangi
            continue
        kataklar = [_matn(k) for k in xom]
        if not any(kataklar):
            continue
        if u is None:
            # Sarlavhadan OLDINGI seksiya qatori («9 СЕКЦИЯ») ham hisobda.
            birinchi = next(k for k in kataklar if k)
            if re.search(r"секци|этаж|подвал", birinchi, re.I):
                bolim = birinchi
            continue
        miqdor = _son(xom[u.miqdor]) if u.miqdor < len(xom) else None
        nomi = kataklar[u.nom] if u.nom is not None and u.nom < len(xom) else ""
        belgi_j = u.belgi
        if belgi_j is None or belgi_j >= len(kataklar) or not kataklar[belgi_j]:
            belgi_j = _birinchi_belgi(kataklar, u.nom if u.nom else u.miqdor)
        if u.nom is None:
            # Nom ustuni belgilanmagan (masalan, faqat «Кол-во» sarlavhasi):
            # miqdordan chapdagi hamma matn katagi — nom.
            nomi = " ".join(k for j, k in enumerate(kataklar[:u.miqdor])
                            if k and _son(k) is None
                            and not (j == belgi_j and TIZIM_BELGISI.match(k)))
        turlar = [kataklar[j] for j in u.tur if j < len(kataklar) and kataklar[j]]
        belgi = kataklar[belgi_j] if belgi_j is not None else ""

        if miqdor is None or miqdor <= 0:
            # Miqdorsiz qator — sarlavha. Qaysi daraja ekanini aniqlaymiz.
            matn = nomi or next((k for k in kataklar if k), "")
            if not matn or _SHTAMP.match(matn) or _SHTAMP.match(belgi or "-"):
                continue
            if re.search(r"секци|этаж|подвал|блок\s*\w$", matn, re.I):
                bolim, guruh, tizim = matn, "", ""
            elif TIZIM_BELGISI.match(belgi or ""):
                tizim, guruh = TIZIM_BELGISI.match(belgi).group(1), matn
            else:
                m = re.search(r"систем\w*\s+[\w\s-]*?\b((?:ПВ|ПД|ДУ|П|В|K|К)\d+)", matn, re.I)
                if m:
                    tizim = m.group(1)
                guruh = matn
            continue

        if not nomi and not turlar:
            continue
        tolik = " ".join(x for x in [nomi] + [t for t in turlar if t not in nomi] if x)
        q = TzQator(
            nomi=tolik,
            miqdor=miqdor,
            birlik=kataklar[u.birlik] if u.birlik is not None and u.birlik < len(kataklar) else "",
            guruh=guruh,
            bolim=bolim,
            matn=" | ".join(k for k in kataklar if k),
            varaq=nom,
            qator_n=i + 1,
        )
        if TIZIM_BELGISI.match(belgi or ""):
            q.tizim = TIZIM_BELGISI.match(belgi).group(1)
            oxirgi_belgi = q.tizim
        elif tizim:
            q.tizim = tizim
        elif not belgi and u.nom is None and oxirgi_belgi:
            # Belgi katagi BO'SH — qator oldingi tizimning davomi
            # («К6, К6р» ostidagi «Вн.блок кассетного типа»).
            q.tizim = oxirgi_belgi
        for kalit, j in u.parametr.items():
            if j < len(xom):
                qiymat = _son(xom[j])
                if qiymat is not None:
                    q.parametrlar[kalit] = qiymat
        natija.append(q)
    imzo = "\n".join(f"{q.nomi}|{q.miqdor:g}" for q in natija)
    return natija, imzo


def jadval_oqi(yol: str | Path) -> TzJadval:
    """Excel TZ dan miqdorli mahsulot qatorlari."""
    import openpyxl

    yol = Path(yol)
    natija = TzJadval(yol=str(yol))
    kitob = openpyxl.load_workbook(str(yol), data_only=True, read_only=True)
    imzolar: dict[str, str] = {}
    try:
        for varaq in kitob.worksheets:
            qatorlar = [tuple(r) for r in varaq.iter_rows(values_only=True)]
            topildi, imzo = _varaq_qatorlari(varaq.title, qatorlar)
            if not topildi:
                continue
            if imzo in imzolar:
                natija.ogohlantirishlar.append(
                    f"«{varaq.title}» varag'i «{imzolar[imzo]}» bilan bir xil — "
                    "ikkinchi marta sanalmadi")
                continue
            imzolar[imzo] = varaq.title
            natija.qatorlar += topildi
    finally:
        kitob.close()
    if not natija.qatorlar:
        natija.ogohlantirishlar.append(
            "Faylda «Кол-во» ustunli jadval topilmadi — TZ ni qo'lda tekshiring")
    return natija
