"""Bilim bazasi (RAG) — agentlar qidiradigan ishonchli manba.

Agent "o'qitilmaydi": savol kelganda tegishli hujjat parchalari qidiriladi va
kontekstga qo'shiladi. Bazada topilmasa — agent buni ochiq aytadi.
"""

from .bolak import Bolak, bol, qonunmi
from .indeks import Indeks, vektorla
from .qidiruv import AGENT_PAPKALARI, Qidiruv, Topilma, kontekst_matni, qidiruv

__all__ = [
    "AGENT_PAPKALARI",
    "Bolak",
    "Indeks",
    "Qidiruv",
    "Topilma",
    "bol",
    "kontekst_matni",
    "qidiruv",
    "qonunmi",
    "vektorla",
]
