"""KP hujjatining ma'lumot modeli.

Bitta model — ikkita chiqish (docx va pdf). Hisob-kitob shu yerda, formatlash
generatorlarda: jami summa ikki hujjatda farq qilmasligi uchun.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, Field


class Qator(BaseModel):
    """KP jadvalining bitta qatori."""

    nomi: str
    spetsifikatsiya: str = ""
    miqdor: float = 1
    birlik: str = "шт"
    # Narx topilmasa None — BO'SH qoladi, taxminiy raqam yozilmaydi.
    birlik_narx: float | None = None
    narx_sanasi: str = ""
    izoh: str = ""
    # Har qatorda QQS alohida ustun bo'lib chiqadi (namunaviy KP kabi).
    qqs_foizi: float = 0

    @property
    def jami(self) -> float | None:
        """QQSsiz summa."""
        if self.birlik_narx is None:
            return None
        return self.birlik_narx * self.miqdor

    @property
    def qqs(self) -> float | None:
        if self.jami is None or not self.qqs_foizi:
            return None
        return self.jami * self.qqs_foizi / 100

    @property
    def qqs_bilan(self) -> float | None:
        if self.jami is None:
            return None
        return self.jami + (self.qqs or 0)

    @property
    def narxsizmi(self) -> bool:
        return self.birlik_narx is None


class Shartlar(BaseModel):
    tolov: str = ""
    yetkazish: str = ""
    kafolat: str = ""
    amal_qilish_muddati: str = ""
    maxsus: list[str] = Field(default_factory=list)


class Mijoz(BaseModel):
    nomi: str = ""
    aloqa: str = ""
    manzil: str = ""
    # STIR/INN — shartnoma va hisob-fakturaga o'tganda SHART bo'ladi.
    # Menejer mijozdan baribir so'raydi, shuning uchun KP bosqichidayoq
    # yozib qo'yiladi: keyin qidirib yurilmasin.
    inn: str = ""
    # Obyekt nomi va manzili ("Chilonzor savdo markazi, 3-qavat").
    # Bitta mijozda bir nechta obyekt bo'lishi mumkin — KP qaysi biriga
    # tegishli ekani hujjatda ko'rinib tursin.
    obyekt: str = ""


@dataclass
class KP:
    """Tayyor KP hujjati uchun to'liq ma'lumot."""

    raqam: str
    sana: date
    mijoz: Mijoz
    qatorlar: list[Qator]
    shartlar: Shartlar
    rekvizitlar: dict[str, str]
    valyuta: str = "UZS"
    qqs_foizi: float = 0
    til: str = "ru"
    ogohlantirishlar: list[str] = field(default_factory=list)
    # Blanka matnlari (narxlar.yaml dan)
    kirish_matni: str = ""
    shartlar_matni: list[str] = field(default_factory=list)
    # Narx amal qilish oralig'i
    narx_amal_oxiri: date | None = None

    # --- saqlash / tiklash ---------------------------------------------------
    #
    # KP ni bazaga yozib, keyin TAHRIRLASH uchun kerak: menejer
    # "1-tovarga 5 mln" desa, o'sha KP ning aynan o'zi yangilanadi.
    # `dataclasses.asdict` yetarli emas — `date` va Pydantic
    # obyektlarini o'zi tiklamaydi.

    def saqlash_uchun(self) -> dict:
        return {
            "raqam": self.raqam,
            "sana": self.sana.isoformat(),
            "mijoz": self.mijoz.model_dump(),
            "qatorlar": [q.model_dump() for q in self.qatorlar],
            "shartlar": self.shartlar.model_dump(),
            "rekvizitlar": dict(self.rekvizitlar),
            "valyuta": self.valyuta,
            "qqs_foizi": self.qqs_foizi,
            "til": self.til,
            "ogohlantirishlar": list(self.ogohlantirishlar),
            "kirish_matni": self.kirish_matni,
            "shartlar_matni": list(self.shartlar_matni),
            "narx_amal_oxiri": (
                self.narx_amal_oxiri.isoformat() if self.narx_amal_oxiri else None
            ),
        }

    @classmethod
    def tikla(cls, malumot: dict) -> "KP":
        oxiri = malumot.get("narx_amal_oxiri")
        return cls(
            raqam=malumot["raqam"],
            sana=date.fromisoformat(malumot["sana"]),
            mijoz=Mijoz(**(malumot.get("mijoz") or {})),
            qatorlar=[Qator(**q) for q in (malumot.get("qatorlar") or [])],
            shartlar=Shartlar(**(malumot.get("shartlar") or {})),
            rekvizitlar=dict(malumot.get("rekvizitlar") or {}),
            valyuta=malumot.get("valyuta", "UZS"),
            qqs_foizi=malumot.get("qqs_foizi", 0),
            til=malumot.get("til", "ru"),
            ogohlantirishlar=list(malumot.get("ogohlantirishlar") or []),
            kirish_matni=malumot.get("kirish_matni", ""),
            shartlar_matni=list(malumot.get("shartlar_matni") or []),
            narx_amal_oxiri=date.fromisoformat(oxiri) if oxiri else None,
        )

    # --- hisob-kitob ---------------------------------------------------------

    @property
    def narxli_qatorlar(self) -> list[Qator]:
        return [q for q in self.qatorlar if not q.narxsizmi]

    @property
    def narxsiz_qatorlar(self) -> list[Qator]:
        return [q for q in self.qatorlar if q.narxsizmi]

    @property
    def toliq_narxmi(self) -> bool:
        """Hamma qatorda narx bormi?"""
        return bool(self.qatorlar) and not self.narxsiz_qatorlar

    @property
    def summa(self) -> float | None:
        """QQSsiz jami. Birorta narx yo'q bo'lsa — None."""
        if not self.narxli_qatorlar:
            return None
        return sum(q.jami or 0 for q in self.narxli_qatorlar)

    @property
    def qqs(self) -> float | None:
        if self.summa is None or not self.qqs_foizi:
            return None
        return self.summa * self.qqs_foizi / 100

    @property
    def jami(self) -> float | None:
        if self.summa is None:
            return None
        return self.summa + (self.qqs or 0)

    def pul(self, qiymat: float | None) -> str:
        """Summa: 12 500 000 UZS (matn ichida ishlatish uchun)."""
        if qiymat is None:
            return "—"
        return f"{qiymat:,.0f}".replace(",", " ") + f" {self.valyuta}"

    @staticmethod
    def son(qiymat: float | None) -> str:
        """Jadval uchun raqam: 9 372 000,00 (namunaviy KP formatida)."""
        if qiymat is None:
            return ""
        butun, kasr = f"{qiymat:,.2f}".split(".")
        return f"{butun.replace(',', ' ')},{kasr}"

    def narx_sanalari(self) -> list[str]:
        """KP da ko'rsatiladigan narx sanalari (takrorsiz)."""
        sanalar = {q.narx_sanasi for q in self.narxli_qatorlar if q.narx_sanasi}
        return sorted(sanalar)
