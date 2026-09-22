"""Dollar kursi — Markaziy bank va backend qiymatlarini solishtirish.

NEGA KERAK
----------
`product_model_inside.price` bazada DOLLARDA saqlanadi, so'm narxi esa
o'qiyotganda kursga ko'paytirib hisoblanadi. Ya'ni kurs — butun katalog
narxini ko'paytiruvchi bitta raqam: u xato bo'lsa, KP ham, tender bahosi
ham, saytdagi narx ham bir vaqtda xato bo'ladi.

Shu qadar muhim raqam esa IKKI JOYDA qo'lda yozib qo'yilgan edi: bizning
`sozlama().usd_kursi` da va backendning `settings.usd-rate` da. Ikkisi
mustaqil o'zgargani uchun bot bilan sayt turli narx ko'rsatishi mumkin,
va ularni hech kim kuzatmasdi.

BU MODUL QARAR QILMAYDI
-----------------------
U faqat uchta raqamni yonma-yon qo'yadi: Markaziy bank kursi, backenddagi
kurs va bizning zaxira qiymat. Qaysi biri to'g'ri ekanini INSON hal
qiladi — chunki bu biznes qarori, texnik emas:

  ko'p kompaniya narxni Markaziy bank kursidan YUQORIROQ oladi (bank yoki
  bozor kursi bo'yicha). Shuning uchun MB kursini ko'r-ko'rona qo'yish
  butun katalogni ARZONLASHTIRIB yuborishi mumkin.

Shu sababli `sozlama().usd_ustama` bor: "MB kursi + N%" degan siyosatni
ochiq yozib qo'yish uchun. Nolga teng bo'lsa — sof MB kursi.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

MB_MANZILI = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/"
MB_KUTISH = 15.0
# Kurs kuniga bir marta o'zgaradi — tez-tez so'rashning ma'nosi yo'q.
MB_KESH_SONIYA = 3600.0

_KESH: tuple[float, "MbKursi"] | None = None


class KursXatosi(RuntimeError):
    """Kursni olishning iloji bo'lmadi (tarmoq yoki javob shakli)."""


@dataclass(frozen=True)
class MbKursi:
    """Markaziy bankdagi bir kunlik kurs."""

    qiymat: float
    sana: str
    ozgarish: float      # oldingi kunga nisbatan farq (so'm)

    def ustama_bilan(self, ustama_foiz: float) -> float:
        return self.qiymat * (1 + ustama_foiz / 100)


async def markaziy_bank_kursi(
    mijoz: httpx.AsyncClient | None = None, keshdan: bool = True
) -> MbKursi:
    """Markaziy bankning bugungi USD kursi.

    Javob bitta elementli ro'yxat bo'lib keladi; `Rate` va `Diff` matn
    ko'rinishida, shuning uchun ochiq songa keltiriladi.
    """
    global _KESH
    if keshdan and _KESH is not None and time.monotonic() - _KESH[0] < MB_KESH_SONIYA:
        return _KESH[1]

    try:
        if mijoz is not None:
            javob = await mijoz.get(MB_MANZILI, timeout=MB_KUTISH)
        else:
            async with httpx.AsyncClient(timeout=MB_KUTISH) as m:
                javob = await m.get(MB_MANZILI)
        javob.raise_for_status()
        malumot = javob.json()
    except (httpx.HTTPError, ValueError) as xato:
        raise KursXatosi(f"Markaziy bank kursi olinmadi: {xato}") from xato

    if not isinstance(malumot, list) or not malumot:
        raise KursXatosi("Markaziy bank javobi kutilgan shaklda emas (bo'sh ro'yxat)")

    yozuv = malumot[0]
    try:
        kurs = MbKursi(
            qiymat=float(yozuv["Rate"]),
            sana=str(yozuv.get("Date", "")),
            ozgarish=float(yozuv.get("Diff") or 0),
        )
    except (KeyError, TypeError, ValueError) as xato:
        raise KursXatosi(f"Markaziy bank javobida kurs o'qilmadi: {xato}") from xato

    if kurs.qiymat <= 0:
        raise KursXatosi(f"Markaziy bank noto'g'ri kurs qaytardi: {kurs.qiymat}")

    _KESH = (time.monotonic(), kurs)
    return kurs


@dataclass(frozen=True)
class KursSolishtiruvi:
    """Uch manbadagi kurs yonma-yon."""

    mb: MbKursi
    backend: float | None
    nishon: float           # MB kursi + ustama (biz tavsiya qiladigan qiymat)
    ustama_foiz: float

    @property
    def farq_foiz(self) -> float | None:
        """Backend nishondan necha foizga chetda."""
        if not self.backend or not self.nishon:
            return None
        return (self.backend - self.nishon) / self.nishon * 100

    def sezilarlimi(self, chegara_foiz: float) -> bool:
        farq = self.farq_foiz
        return farq is not None and abs(farq) >= chegara_foiz


def solishtir(
    mb: MbKursi, backend: float | None, ustama_foiz: float = 0.0
) -> KursSolishtiruvi:
    return KursSolishtiruvi(
        mb=mb,
        backend=backend,
        nishon=round(mb.ustama_bilan(ustama_foiz), 2),
        ustama_foiz=ustama_foiz,
    )


def matn(s: KursSolishtiruvi) -> str:
    """Odam o'qiy oladigan qisqa hisobot."""

    def son(q: float | None) -> str:
        return "—" if q is None else f"{q:,.2f}".replace(",", " ")

    qatorlar = [
        f"Markaziy bank ({s.mb.sana}): {son(s.mb.qiymat)} so'm"
        + (f"  ({s.mb.ozgarish:+.2f})" if s.mb.ozgarish else ""),
    ]
    if s.ustama_foiz:
        qatorlar.append(f"Ustama {s.ustama_foiz:+.2f}% bilan: {son(s.nishon)} so'm")
    qatorlar.append(f"Saytda hozir: {son(s.backend)} so'm")

    farq = s.farq_foiz
    if farq is None:
        qatorlar.append("Farq hisoblanmadi — saytdagi kurs o'qilmadi.")
    elif abs(farq) < 0.01:
        qatorlar.append("Farq yo'q.")
    else:
        tomon = "yuqori" if farq > 0 else "past"
        qatorlar.append(
            f"Farq: {farq:+.2f}% — saytdagi kurs shunchaga {tomon}. "
            "Ya'ni katalogdagi hamma so'm narxi shu foizga siljigan."
        )
    return "\n".join(qatorlar)


# --- barcha valyutalar (tender summalari uchun) -------------------------------
#
# etender lotni SO'MDA ham, DOLLARDA ham, YEVRODA ham e'lon qiladi.
# O'lchandi (2026-09-14): 866 ochiq lotdan 802 tasi UZS, 54 tasi USD,
# 10 tasi EUR. Ilgari valyuta umuman o'qilmasdi va hamma summa "so'm"
# deb ko'rsatilardi — 81 205,70 dollarlik lot "81 206 so'm" bo'lib
# chiqardi. Saralash ham xom son bilan edi: 700 000 yevrolik lot
# 1 mln so'mlik lotdan pastda turardi.

MB_HAMMASI = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
_KESH_HAMMASI: tuple[float, dict[str, float]] | None = None

# Menejerga ko'rsatiladigan nom. Ro'yxatda yo'q valyuta ISO kodi bilan chiqadi.
VALYUTA_NOMI = {
    "UZS": "so'm",
    "USD": "dollar",
    "EUR": "yevro",
    "RUB": "rubl",
    "CNY": "yuan",
}


async def markaziy_bank_kurslari(
    mijoz: httpx.AsyncClient | None = None, keshdan: bool = True
) -> dict[str, float]:
    """Markaziy bankning bugungi kurslari: `{ISO kod: 1 birlik necha so'm}`.

    `Nominal` 1 dan katta bo'lishi mumkin (kurs bir necha birlik uchun
    berilgan) — shuning uchun 1 birlikka bo'linadi. UZS har doim 1.
    """
    global _KESH_HAMMASI
    if (
        keshdan
        and _KESH_HAMMASI is not None
        and time.monotonic() - _KESH_HAMMASI[0] < MB_KESH_SONIYA
    ):
        return dict(_KESH_HAMMASI[1])

    try:
        if mijoz is not None:
            javob = await mijoz.get(MB_HAMMASI, timeout=MB_KUTISH)
        else:
            async with httpx.AsyncClient(timeout=MB_KUTISH) as m:
                javob = await m.get(MB_HAMMASI)
        javob.raise_for_status()
        malumot = javob.json()
    except (httpx.HTTPError, ValueError) as xato:
        raise KursXatosi(f"Markaziy bank kurslari olinmadi: {xato}") from xato

    if not isinstance(malumot, list) or not malumot:
        raise KursXatosi("Markaziy bank javobi kutilgan shaklda emas (bo'sh ro'yxat)")

    kurslar: dict[str, float] = {"UZS": 1.0}
    for yozuv in malumot:
        if not isinstance(yozuv, dict):
            continue
        try:
            kod = str(yozuv["Ccy"]).strip().upper()
            nominal = float(yozuv.get("Nominal") or 1) or 1.0
            qiymat = float(yozuv["Rate"]) / nominal
        except (KeyError, TypeError, ValueError):
            continue
        if kod and qiymat > 0:
            kurslar[kod] = qiymat

    if len(kurslar) == 1:
        raise KursXatosi("Markaziy bank javobida birorta ham kurs o'qilmadi")

    _KESH_HAMMASI = (time.monotonic(), kurslar)
    return dict(kurslar)


def somga(
    summa: object, valyuta: object, kurslar: dict[str, float] | None
) -> float | None:
    """Summani so'mga keltiradi.

    Kursi noma'lum valyuta uchun `None` — taxminiy kurs O'YLAB TOPILMAYDI.
    """
    if summa is None:
        return None
    try:
        qiymat = float(summa)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    kod = str(valyuta or "UZS").strip().upper() or "UZS"
    if kod == "UZS":
        return qiymat
    kurs = (kurslar or {}).get(kod)
    return qiymat * kurs if kurs else None


def pul_matni(summa: object, valyuta: object = "UZS") -> str:
    """Summa O'Z VALYUTASIDA: `12 500 000 so'm`, `81 205,70 dollar`.

    So'm butun songacha yumaloqlanadi (avvalgidek). Xorijiy valyutada
    tiyin/sent yo'qolmasin — kasrli bo'lsa ikki xona qoldiriladi.
    """
    try:
        qiymat = float(summa)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "—"
    kod = str(valyuta or "UZS").strip().upper() or "UZS"
    nomi = VALYUTA_NOMI.get(kod, kod)
    if kod == "UZS" or qiymat.is_integer():
        son = f"{qiymat:,.0f}".replace(",", " ")
    else:
        # "81,205.70" -> "81 205.70" -> "81 205,70"
        son = f"{qiymat:,.2f}".replace(",", " ").replace(".", ",")
    return f"{son} {nomi}"
