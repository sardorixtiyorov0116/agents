"""KP uchun narx manbai va kompaniya rekvizitlari.

Narxlar `knowledge/sales/narxlar.yaml` da qo'lda yuritiladi (ichki API'da
narx maydoni hozircha to'ldirilmagan).

O'ZGARMAS QOIDALAR:
  - narx topilmasa BO'SH qoladi, taxminiy raqam yozilmaydi;
  - har narxda sana bo'ladi va KP da ko'rsatiladi;
  - eskirgan narx ISHLATILMAYDI (bo'sh deb hisoblanadi).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import sozlama
from integrations.climavent_client import kalitla

NARX_FAYLI = "narxlar.yaml"
REKVIZIT_FAYLI = "rekvizitlar.yaml"


@dataclass(frozen=True)
class Narx:
    """Bitta mahsulot narxi."""

    kod: str
    nomi: str
    narx: float
    valyuta: str
    sana: str
    eskirgan: bool = False

    @property
    def bormi(self) -> bool:
        """Narx haqiqatan mavjudmi? (0 — "narx yo'q", "bepul" emas)"""
        return self.narx > 0 and not self.eskirgan


def _sana_ajrat(qiymat: Any) -> date | None:
    if isinstance(qiymat, date):
        return qiymat
    if not qiymat:
        return None
    try:
        return datetime.fromisoformat(str(qiymat).strip()).date()
    except ValueError:
        return None


class NarxRoyxati:
    """Narx ro'yxati va unda qidirish."""

    def __init__(self, malumot: dict[str, Any]):
        self.valyuta = malumot.get("valyuta") or "UZS"
        self.qqs_foizi = float(malumot.get("qqs_foizi") or 0)
        self.amal_qilish_kuni = int(malumot.get("amal_qilish_kuni") or 0)
        self.shartlar: dict[str, str] = {
            k: str(v).strip() for k, v in (malumot.get("shartlar") or {}).items() if v
        }
        # Namunaviy blanka matnlari (til bo'yicha).
        self.narx_amal_kuni = int(malumot.get("narx_amal_kuni") or 30)
        self._shartlar_matni = malumot.get("shartlar_matni") or {}
        self._kirish_matni = malumot.get("kirish_matni") or {}
        self._narxlar = [n for n in (malumot.get("narxlar") or []) if isinstance(n, dict)]

    def _eskirganmi(self, sana: date | None) -> bool:
        if not self.amal_qilish_kuni:
            return False
        if sana is None:
            # Sanasi yo'q narx ishonchsiz — eskirgan deb hisoblaymiz.
            return True
        return (date.today() - sana).days > self.amal_qilish_kuni

    def top(self, nomi: str) -> Narx | None:
        """Mahsulot nomi yoki kodi bo'yicha narx topadi.

        Kirill/lotin farqi hisobga olinmaydi (katalogdagi kabi).
        """
        if not nomi:
            return None
        sorov_kalitlari = kalitla(nomi)
        if not sorov_kalitlari:
            return None

        for yozuv in self._narxlar:
            nomzodlar = [str(yozuv.get("kod") or ""), str(yozuv.get("nomi") or "")]
            mos = any(
                s in n or n in s
                for nomzod in nomzodlar
                for n in kalitla(nomzod)
                for s in sorov_kalitlari
                if n and s
            )
            if not mos:
                continue

            sana = _sana_ajrat(yozuv.get("sana"))
            try:
                qiymat = float(yozuv.get("narx") or 0)
            except (TypeError, ValueError):
                qiymat = 0.0

            return Narx(
                kod=str(yozuv.get("kod") or ""),
                nomi=str(yozuv.get("nomi") or ""),
                narx=qiymat,
                valyuta=self.valyuta,
                sana=sana.isoformat() if sana else "",
                eskirgan=self._eskirganmi(sana) if qiymat > 0 else False,
            )
        return None

    def shartlar_matni(self, til: str = "ru") -> list[str]:
        """KP pastidagi shartlar abzaslari."""
        xom = self._shartlar_matni.get(til) or self._shartlar_matni.get("ru") or []
        return [" ".join(str(m).split()) for m in xom if str(m).strip()]

    def kirish_matni(self, til: str = "ru") -> str:
        """Sarlavhadan keyingi kirish jumlasi."""
        xom = self._kirish_matni.get(til) or self._kirish_matni.get("ru") or ""
        return " ".join(str(xom).split())

    @property
    def narx_soni(self) -> int:
        """Haqiqiy (nolga teng bo'lmagan) narxlar soni."""
        return sum(1 for n in self._narxlar if float(n.get("narx") or 0) > 0)


def _yukla(fayl: str) -> dict[str, Any]:
    yol: Path = sozlama().bilim_papkasi / "sales" / fayl
    if not yol.is_file():
        return {}
    malumot = yaml.safe_load(yol.read_text(encoding="utf-8"))
    return malumot if isinstance(malumot, dict) else {}


def _ozgarish_belgisi(fayl: str) -> float:
    """Faylning oxirgi tahrirlangan vaqti (yo'q bo'lsa 0).

    Kesh kaliti sifatida ishlatiladi: administrator YAML ni tahrirlasa,
    belgi o'zgaradi va keyingi so'rovda fayl qaytadan o'qiladi. Busiz
    yangi menejer yoki yangi narx faqat tizim qayta yoqilgach ko'rinardi
    va "nega o'zgarmadi?" degan savol tug'ilardi.
    """
    yol: Path = sozlama().bilim_papkasi / "sales" / fayl
    try:
        return yol.stat().st_mtime
    except OSError:
        return 0.0


@lru_cache
def _narxlar(_belgi: float) -> NarxRoyxati:
    return NarxRoyxati(_yukla(NARX_FAYLI))


def narxlar() -> NarxRoyxati:
    return _narxlar(_ozgarish_belgisi(NARX_FAYLI))


@lru_cache
def _rekvizitlar(_belgi: float) -> dict[str, str]:
    """Kompaniya rekvizitlari — bo'sh maydonlar tashlanadi.

    `menejerlar` bu yerga kirmaydi: u ichma-ich tuzilma, matn emas
    (`menejerlar()` funksiyasiga qarang).
    """
    return {
        k: str(v).strip()
        for k, v in _yukla(REKVIZIT_FAYLI).items()
        if k != "menejerlar" and str(v or "").strip()
    }


def rekvizitlar() -> dict[str, str]:
    return _rekvizitlar(_ozgarish_belgisi(REKVIZIT_FAYLI))


@lru_cache
def _menejerlar(_belgi: float) -> dict[str, dict[str, str]]:
    """Telegram ID -> {ism, telefon}.

    Bot bir necha xodimga beriladi, KP da esa AYNAN so'rov yuborgan
    menejerning nomi turishi kerak.
    """
    xom = _yukla(REKVIZIT_FAYLI).get("menejerlar") or {}
    if not isinstance(xom, dict):
        return {}
    natija: dict[str, dict[str, str]] = {}
    for kalit, qiymat in xom.items():
        if not isinstance(qiymat, dict):
            continue
        ism = str(qiymat.get("ism") or "").strip()
        if not ism:
            continue
        yozuv = {
            "ism": ism,
            "telefon": str(qiymat.get("telefon") or "").strip(),
        }
        # Ixtiyoriy: ismning qo'lda yozilgan kirill/lotin varianti.
        # Bo'lsa — avtomatik o'girish o'rniga shu ishlatiladi (pasportdagi
        # yozuvni faqat egasi biladi: "Шухрат" -> Shuhrat yoki Shukhrat).
        for qoshimcha in ("ism_kiril", "ism_lotin"):
            qiy = str(qiymat.get(qoshimcha) or "").strip()
            if qiy:
                yozuv[qoshimcha] = qiy
        natija[str(kalit).strip()] = yozuv
    return natija


def menejerlar() -> dict[str, dict[str, str]]:
    return _menejerlar(_ozgarish_belgisi(REKVIZIT_FAYLI))


def menejer_uchun(telegram_id: Any) -> dict[str, str] | None:
    """So'rov yuborgan xodimning KP dagi ma'lumoti (topilmasa None)."""
    if telegram_id is None:
        return None
    return menejerlar().get(str(telegram_id).strip())


def keshni_tozala() -> None:
    """Keshni majburan bo'shatadi.

    Odatda kerak emas — fayl o'zgarganda o'zi qayta o'qiladi
    (`_ozgarish_belgisi`). Testlarda va fayl yo'li almashtirilganda
    ishlatiladi, chunki u holda vaqt belgisi o'zgarmasligi mumkin.
    """
    _narxlar.cache_clear()
    _rekvizitlar.cache_clear()
    _menejerlar.cache_clear()
