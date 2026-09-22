"""Kompaniya profili — agentlar kim uchun ishlayotganini bilishi uchun.

Profil `config/company_profile.yaml` da turadi va har agent chaqiruvida
promptga qo'shiladi. Shuning uchun:
  - agent profilda BOR ma'lumot uchun savol so'ramaydi;
  - profil o'zgarganda kodga tegilmaydi;
  - to'ldirilmagan maydon bo'sh qoladi va promptga umuman tushmaydi —
    "noma'lum" degan yozuv modelni to'qishga undamasligi uchun.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import sozlama


# Kompaniya blokidan hamma agent ko'radigan asosiy maydonlar.
KOMPANIYA_ASOSI = frozenset(
    {"nomi", "savdo_brendi", "soha", "tur", "hudud", "asosiy_bozor", "til", "valyuta"}
)

# Qaysi agentga profilning qaysi qismi kerak. Ortiqchasi yuborilmaydi —
# har chaqiruvda token tejaladi.
AGENT_BOLIMLARI: dict[str, tuple[str, ...]] = {
    "marketing": ("brend", "mijozlar", "mahsulotlar", "raqobatchilar"),
    "competitor-watch": ("raqobatchilar", "raqobat_izohi", "mahsulotlar", "brend"),
    "product-spec": ("mahsulotlar", "sertifikatlar"),
    "price-monitor": ("mahsulotlar",),
    "sales-strategy": ("mahsulotlar", "mijozlar", "raqobatchilar"),
    "proposal-builder": ("mahsulotlar",),
    # Jasurga XIZMATLAR ro'yxati shart. O'LCHANDI (2026-09-08): usiz u
    # 11 ta haqiqiy tenderdan 6 tasini o'tkazib yuborardi — hammasi
    # "texnik xizmat", "montaj", "ta'mirlash" lotlari. Agent to'g'ri
    # o'ylardi ("biz uskuna sotamiz"), lekin kompaniya montaj,
    # puskonaladka va servis ham qilishini BILMASDI.
    "tender-watch": ("xizmatlar",),
    "data-query": (),
    "hr-assist": ("toliq_nomi",),
    "legal-review": ("toliq_nomi", "manzil", "tashkil_etilgan", "eksport_bozorlari"),
}


def _bosh(qiymat: Any) -> bool:
    """Bo'sh maydonmi? (None, bo'sh matn, bo'sh ro'yxat/lug'at)"""
    if qiymat is None:
        return True
    if isinstance(qiymat, str):
        return not qiymat.strip()
    if isinstance(qiymat, (list, dict, tuple, set)):
        return len(qiymat) == 0
    return False


def _tozala(tugun: Any) -> Any:
    """Bo'sh maydonlarni olib tashlaydi (rekursiv)."""
    if isinstance(tugun, dict):
        yangi = {k: _tozala(v) for k, v in tugun.items()}
        return {k: v for k, v in yangi.items() if not _bosh(v)}
    if isinstance(tugun, list):
        yangi_royxat = [_tozala(v) for v in tugun]
        return [v for v in yangi_royxat if not _bosh(v)]
    if isinstance(tugun, str):
        return tugun.strip()
    return tugun


class Profil:
    """Kompaniya profili va uni promptga aylantirish."""

    def __init__(self, malumot: dict[str, Any]):
        self.malumot = _tozala(malumot or {})

    @property
    def bormi(self) -> bool:
        return bool(self.malumot)

    @property
    def kompaniya(self) -> dict[str, Any]:
        return self.malumot.get("kompaniya", {})

    @property
    def nomi(self) -> str:
        return self.kompaniya.get("nomi", "")

    @property
    def raqobatchilar(self) -> list[dict[str, Any]]:
        xom = self.malumot.get("raqobatchilar", [])
        return [r for r in xom if isinstance(r, dict)]

    def raqobatchi_nomlari(self) -> list[str]:
        return [r["nomi"] for r in self.raqobatchilar if r.get("nomi")]

    def taqiqlar(self) -> list[str]:
        return list(self.malumot.get("brend", {}).get("taqiqlar", []))

    # --- promptga aylantirish ------------------------------------------------

    def matn(self) -> str:
        """Profilni prompt uchun o'qish qulay matnga aylantiradi."""
        if not self.bormi:
            return ""
        return _yoz(self.malumot).strip()

    def agent_uchun(self, rol: str) -> str:
        """Agentga FAQAT o'ziga kerakli bo'limlarni beradi.

        To'liq profil har chaqiruvda ~1100 token oladi, lekin Dostonga
        sertifikatlar ham, Lazizga raqobatchilar ro'yxati ham kerak emas.
        Kesh buzilmaydi: har agentning prefiksi o'zi uchun barqaror qoladi.
        """
        if not self.bormi:
            return ""

        kerak = AGENT_BOLIMLARI.get(rol, ())
        tanlangan: dict[str, Any] = {}

        # Kompaniya bloki hammaga, lekin qisqartirilgan holda.
        kompaniya = {
            k: v
            for k, v in self.kompaniya.items()
            if k in KOMPANIYA_ASOSI or k in kerak
        }
        if kompaniya:
            tanlangan["kompaniya"] = kompaniya

        for bolim in kerak:
            if bolim in ("kompaniya",) or bolim in KOMPANIYA_ASOSI:
                continue
            qiymat = self.malumot.get(bolim)
            if not _bosh(qiymat):
                tanlangan[bolim] = qiymat

        return _yoz(tanlangan).strip()

    def qisqa(self) -> str:
        """Router uchun qisqartirilgan profil (butun katalog kerak emas)."""
        if not self.bormi:
            return ""
        bolaklar: list[str] = []
        k = self.kompaniya
        if k:
            qatorlar = [f"{k.get('nomi', '')}"]
            if k.get("savdo_brendi"):
                qatorlar.append(f"savdo brendi: {k['savdo_brendi']}")
            for kalit in ("soha", "hudud", "asosiy_bozor", "valyuta"):
                if k.get(kalit):
                    qatorlar.append(f"{kalit}: {k[kalit]}")
            bolaklar.append("Kompaniya: " + " · ".join(q for q in qatorlar if q))

        yonalishlar = self.malumot.get("mahsulotlar", {}).get("yonalishlar", [])
        if yonalishlar:
            bolaklar.append("Mahsulot yo'nalishlari: " + "; ".join(yonalishlar))

        nomlar = self.raqobatchi_nomlari()
        if nomlar:
            bolaklar.append("Ma'lum raqobatchilar: " + ", ".join(nomlar))

        narx = self.malumot.get("mahsulotlar", {}).get("narx_holati")
        if narx:
            bolaklar.append(f"Narx holati: {narx}")

        return "\n".join(bolaklar)


def _yoz(tugun: Any, chuqurlik: int = 0) -> str:
    """Lug'at/ro'yxatni bosqichli matnga aylantiradi (YAML'ga o'xshash)."""
    bosh = "  " * chuqurlik
    qatorlar: list[str] = []

    if isinstance(tugun, dict):
        for kalit, qiymat in tugun.items():
            nom = kalit.replace("_", " ")
            if isinstance(qiymat, (dict, list)):
                qatorlar.append(f"{bosh}{nom}:")
                qatorlar.append(_yoz(qiymat, chuqurlik + 1))
            else:
                qatorlar.append(f"{bosh}{nom}: {qiymat}")
    elif isinstance(tugun, list):
        for element in tugun:
            if isinstance(element, dict):
                ichi = " · ".join(
                    f"{k.replace('_', ' ')}: {v}"
                    for k, v in element.items()
                    if not isinstance(v, (dict, list))
                )
                qatorlar.append(f"{bosh}- {ichi}")
            else:
                qatorlar.append(f"{bosh}- {element}")
    else:
        qatorlar.append(f"{bosh}{tugun}")

    return "\n".join(q for q in qatorlar if q.strip())


def profilni_yukla(fayl: Path | None = None) -> Profil:
    """Profil faylini o'qiydi. Fayl bo'lmasa — bo'sh profil (xato emas)."""
    fayl = fayl or sozlama().profil_fayli
    if not fayl.is_file():
        return Profil({})
    malumot = yaml.safe_load(fayl.read_text(encoding="utf-8"))
    if not isinstance(malumot, dict):
        return Profil({})
    return Profil(malumot)


@lru_cache
def profil() -> Profil:
    """Kesh bilan profil (kontraktlar reyestriga o'xshash)."""
    return profilni_yukla()
