"""Bot uchun formatlash — asosiy ish `presenter/` qatlamida.

Bu yerda faqat botga xos qismlar qoladi: reja xabari va tasdiq so'rovi.
Natijaning o'zi `presenter.javob_matni` orqali odamcha matnga aylanadi.
"""

from __future__ import annotations

from app.orkestr import Natija
from app.router import Reja
from presenter import (  # noqa: F401 (bot uchun qayta eksport)
    HOLAT_BELGISI,
    javob_matni,
    mijoz_matni,
)

__all__ = [
    "HOLAT_BELGISI", "javob_matni", "mijoz_matni",
    "reja_matni", "tasdiq_matni",
]


def reja_matni(reja: Reja, korinishlar: dict[str, str]) -> str:
    """"Karim va Malika ishlaydi" — qisqa reja xabari."""
    if reja.aniqlik_kerak:
        return "❓ Avval bir nechta narsani aniqlashtirish kerak…"
    if reja.mos_agent_yoq or not reja.qadamlar:
        return f"➖ Mos agent topilmadi.\n{reja.izoh}"

    ismlar = [korinishlar.get(q.agent, q.agent).split()[-1] for q in reja.qadamlar]
    kim = " → ".join(ismlar) if len(ismlar) > 1 else ismlar[0]
    qatorlar = [f"🧭 Reja: {kim} ishlaydi"]
    for i, qadam in enumerate(reja.qadamlar, 1):
        belgi = " (tasdiq kerak)" if qadam.tasdiq_kerak else ""
        qatorlar.append(f"{i}. {korinishlar.get(qadam.agent, qadam.agent)}{belgi}")
    return "\n".join(qatorlar)


def tasdiq_matni(natija: Natija, korinishlar: dict[str, str]) -> str:
    """Tugmalar ustidagi qisqa savol.

    Ilgari bu yerda "⏸ {kim} natijani tayyorladi, lekin u inson
    tasdig'isiz chiqmaydi" deyilardi. Bu natija sarlavhasida
    ("⏸ Tijorat menejeri Temur — tasdiq kutilmoqda") allaqachon
    aytilgan — bir gapni ikki marta o'qish keraksiz.
    """
    return "Tasdiqlaysizmi?"
