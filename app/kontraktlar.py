"""Agent kontraktlari — router uchun asosiy ma'lumot manbai.

Kontraktlar `contracts/*.yaml` fayllarida saqlanadi va bu yerda Pydantic
modeliga o'giriladi. Router aynan shu kontraktlarga (ayniqsa "chegaralar" va
"tasdiq_qachon" qismlariga) qarab qaror qiladi.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from .config import sozlama
from .konvert import Xavf


class Kontrakt(BaseModel):
    """7 qismli agent kontrakti + interfeys uchun identifikatorlar."""

    rol: str
    lavozim: str
    ism: str
    xavf: Xavf
    amalga_oshirilgan: bool = False

    maqsad: str
    input: list[str]
    output: list[str]
    chegaralar: list[str]
    ruxsatlar: list[str]
    tasdiq_qachon: list[str]
    xato_holati: list[str]

    @property
    def korinish(self) -> str:
        """Interfeysda ko'rsatish shakli: 'Narx analitigi Zara'."""
        return f"{self.lavozim} {self.ism}"

    def _sarlavha(self) -> str:
        return f"### {self.rol} — {self.korinish} (xavf: {self.xavf.value})"

    @staticmethod
    def _royxat(sarlavha: str, qatorlar: list[str]) -> str:
        ichi = "\n".join(f"    - {q}" for q in qatorlar)
        return f"  {sarlavha}:\n{ichi}"

    def matn(self) -> str:
        """Kontraktning TO'LIQ matni — 7 qismi ham.

        Bu shakl agentning o'ziga va tizim savoliga javob berishga kerak
        ("falon agent nima qila oladi?"). Router uchun esa `qisqa_matn`
        ishlatiladi — pastdagi izohga qara.
        """
        ulangan = "ha" if self.amalga_oshirilgan else "yo'q"
        qismlar = [
            self._sarlavha(),
            f"  Maqsad: {self.maqsad.strip()}",
            self._royxat("Input", self.input),
            self._royxat("Output", self.output),
            self._royxat("QILMAYDI (chegaralar)", self.chegaralar),
            self._royxat("Ruxsatlar", self.ruxsatlar),
            self._royxat("Inson tasdig'i qachon", self.tasdiq_qachon),
            self._royxat("Xato holati", self.xato_holati),
            f"  Kodda ulangan: {ulangan}",
        ]
        return "\n".join(qismlar)

    def qisqa_matn(self) -> str:
        """Router uchun qisqartirilgan shakl.

        Router uchta narsani hal qiladi: qaysi agent (maqsad + chegaralar),
        tasdiq kerakmi (tasdiq_qachon), ulanganmi. Qolgan uch qism —
        `input`, `output`, `ruxsatlar`, `xato_holati` — unga kerak emas:
        ular agentning O'Z ishini tavsiflaydi, tanlashga ta'sir qilmaydi.

        Nega bu muhim: to'liq reyestr har so'rovda ~9 300 token, qisqasi
        ~4 700. Farq har savolda takrorlanadi.
        """
        ulangan = "ha" if self.amalga_oshirilgan else "yo'q"
        return "\n".join([
            self._sarlavha(),
            f"  Maqsad: {self.maqsad.strip()}",
            self._royxat("QILMAYDI (chegaralar)", self.chegaralar),
            self._royxat("Inson tasdig'i qachon", self.tasdiq_qachon),
            f"  Kodda ulangan: {ulangan}",
        ])


# Interfeys va router prompti uchun tartib (topshiriq hujjatidagi jadval bo'yicha).
TARTIB = [
    "price-monitor",
    "competitor-watch",
    "product-spec",
    "data-query",
    "marketing",
    "sales-strategy",
    "proposal-builder",
    "hr-assist",
    "legal-review",
]


def kontraktlarni_yukla(papka: Path | None = None) -> dict[str, Kontrakt]:
    """Papkadagi barcha YAML kontraktlarni o'qiydi: {rol: Kontrakt}."""
    papka = papka or sozlama().kontraktlar_papkasi
    if not papka.is_dir():
        raise FileNotFoundError(f"Kontraktlar papkasi topilmadi: {papka}")

    natija: dict[str, Kontrakt] = {}
    for fayl in sorted(papka.glob("*.yaml")):
        malumot = yaml.safe_load(fayl.read_text(encoding="utf-8"))
        kontrakt = Kontrakt.model_validate(malumot)
        if kontrakt.rol in natija:
            raise ValueError(f"Rol nomi takrorlangan: {kontrakt.rol} ({fayl})")
        natija[kontrakt.rol] = kontrakt

    if not natija:
        raise ValueError(f"Papkada birorta kontrakt yo'q: {papka}")

    # Tanish rollar hujjatdagi tartibda, qolganlari oxirida (alifbo bo'yicha).
    def kalit(rol: str) -> tuple[int, str]:
        return (TARTIB.index(rol) if rol in TARTIB else len(TARTIB), rol)

    return {rol: natija[rol] for rol in sorted(natija, key=kalit)}


@lru_cache
def reyestr() -> dict[str, Kontrakt]:
    """Kesh bilan kontraktlar reyestri."""
    return kontraktlarni_yukla()


def kontraktlar_matni(
    kontraktlar: dict[str, Kontrakt] | None = None, qisqa: bool = False
) -> str:
    """Barcha kontraktlarni bitta matnga yig'adi.

    `qisqa=True` — router uchun (arzon shakl). Standart to'liq shakl tizim
    savoliga javob berishda ishlatiladi.
    """
    kontraktlar = kontraktlar or reyestr()
    return "\n\n".join(
        (k.qisqa_matn() if qisqa else k.matn()) for k in kontraktlar.values()
    )
