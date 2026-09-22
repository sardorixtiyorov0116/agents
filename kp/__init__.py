"""KP (tijorat taklifi) — model, narx manbai va hujjat yaratish."""

from .hujjat import docx_yasa, hujjatlarni_yasa, pdf_yasa
from .model import KP, Mijoz, Qator, Shartlar
from .narx import (
    Narx,
    NarxRoyxati,
    keshni_tozala,
    menejer_uchun,
    menejerlar,
    narxlar,
    rekvizitlar,
)

__all__ = [
    "KP",
    "Mijoz",
    "Narx",
    "NarxRoyxati",
    "Qator",
    "Shartlar",
    "docx_yasa",
    "hujjatlarni_yasa",
    "keshni_tozala",
    "narxlar",
    "pdf_yasa",
    "rekvizitlar",
    "menejer_uchun",
    "menejerlar",
]
