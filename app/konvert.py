"""Umumiy konvert — agentlar, router va interfeys orasidagi yagona til.

Har agent natijani AYNAN shu formatda qaytaradi:

    {
      "kim": "price-monitor",
      "holat": "tugadi",
      "natija": { },
      "manba": [],
      "ishonch": "yuqori",
      "tasdiq_kerak": false,
      "izoh": ""
    }
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Holat(str, Enum):
    """Ish holati.

    `mos_agent_yoq` va `ulanmagan` — xato emas, normal javoblar: tizim to'g'ri
    ishlayapti, faqat vazifa hech kimning kontraktiga tushmadi yoki agent hali
    kodda yozilmagan. `xato` faqat haqiqiy nosozlik uchun.
    """

    TUGADI = "tugadi"
    TASDIQ_KUTILMOQDA = "tasdiq_kutilmoqda"
    ANIQLIK_KERAK = "aniqlik_kerak"
    MOS_AGENT_YOQ = "mos_agent_yoq"
    ULANMAGAN = "ulanmagan"
    XATO = "xato"


class Ishonch(str, Enum):
    """Javobga ishonch darajasi."""

    YUQORI = "yuqori"
    ORTA = "orta"
    PAST = "past"


class Xavf(str, Enum):
    """Agentning xavf darajasi (kontraktdan)."""

    PAST = "past"
    ORTA = "orta"
    YUQORI = "yuqori"


class Manba(BaseModel):
    """Ma'lumot qayerdan olindi."""

    tur: str  # "veb" | "baza" | "hujjat" | "kontrakt"
    nom: str
    havola: str | None = None
    sana: str | None = None


class Konvert(BaseModel):
    """Agentlar orasidagi yagona javob formati.

    `manba` va `ishonch` majburiy: agent har doim qayerdan olganini va
    qanchalik ishonishini ko'rsatadi (9-bo'lim).
    """

    kim: str
    holat: Holat
    natija: dict[str, Any] = Field(default_factory=dict)
    manba: list[Manba] = Field(default_factory=list)
    ishonch: Ishonch
    tasdiq_kerak: bool = False
    izoh: str = ""

    @model_validator(mode="after")
    def _manba_majburiy(self) -> Konvert:
        # Ish muvaffaqiyatli tugagan bo'lsa, manba ko'rsatilishi shart.
        # Xato yoki tasdiq kutilayotgan holatda manba bo'lmasligi mumkin.
        if self.holat is Holat.TUGADI and not self.manba:
            raise ValueError(
                f"'{self.kim}': holat=tugadi bo'lganda kamida bitta manba ko'rsatilishi shart"
            )
        return self


def xato_konvert(kim: str, izoh: str, natija: dict[str, Any] | None = None) -> Konvert:
    """Xato holati uchun tayyor konvert."""
    return Konvert(
        kim=kim,
        holat=Holat.XATO,
        natija=natija or {},
        manba=[],
        ishonch=Ishonch.PAST,
        tasdiq_kerak=False,
        izoh=izoh,
    )


def tasdiq_konverti(kim: str, izoh: str, natija: dict[str, Any] | None = None) -> Konvert:
    """Inson tasdig'i kutilayotgan holat uchun tayyor konvert."""
    return Konvert(
        kim=kim,
        holat=Holat.TASDIQ_KUTILMOQDA,
        natija=natija or {},
        manba=[],
        ishonch=Ishonch.ORTA,
        tasdiq_kerak=True,
        izoh=izoh,
    )


def aniqlik_kerak_konvert(
    savollar: list[str], izoh: str = "", kim: str = "router"
) -> Konvert:
    """Zarur ma'lumot yetishmayapti — savol beriladi.

    Bu xato emas: tizim bo'sh natija chiqargandan ko'ra aniq savol bergani
    yaxshi. Javob kelgach zanjir ishga tushadi.

    Routerdan tashqari agent ham qaytarishi mumkin (`kim` — o'z roli), masalan
    Temur mahsulot nomini bilmasa.
    """
    return Konvert(
        kim=kim,
        holat=Holat.ANIQLIK_KERAK,
        natija={"savollar": savollar},
        manba=[],
        ishonch=Ishonch.ORTA,
        tasdiq_kerak=False,
        izoh=izoh or "Aniqlashtirish kerak: " + "; ".join(savollar),
    )


def tizim_javobi_konverti(javob: str) -> Konvert:
    """Tizim haqidagi savolga routerning o'z javobi.

    Manba — agent kontraktlari: javob o'ylab topilmaydi, kontraktlardan
    olinadi, shuning uchun bu to'liq qonuniy `tugadi` javob.
    """
    return Konvert(
        kim="router",
        holat=Holat.TUGADI,
        natija={"javob": javob},
        manba=[Manba(tur="kontrakt", nom="agent kontraktlari")],
        ishonch=Ishonch.YUQORI,
        tasdiq_kerak=False,
        izoh="tizim haqidagi savolga javob berildi",
    )


def mos_agent_yoq_konvert(izoh: str, natija: dict[str, Any] | None = None) -> Konvert:
    """Hech qaysi agent bajara olmaydi — bu normal javob, xato emas."""
    return Konvert(
        kim="router",
        holat=Holat.MOS_AGENT_YOQ,
        natija=natija or {},
        manba=[],
        ishonch=Ishonch.ORTA,
        tasdiq_kerak=False,
        izoh=izoh,
    )


def ulanmagan_konvert(kim: str, izoh: str) -> Konvert:
    """Agent kontrakti bor, lekin kodda hali yozilmagan."""
    return Konvert(
        kim=kim,
        holat=Holat.ULANMAGAN,
        natija={},
        manba=[],
        ishonch=Ishonch.ORTA,
        tasdiq_kerak=False,
        izoh=izoh,
    )
