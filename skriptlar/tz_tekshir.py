"""TZ ni tayyor KP bilan solishtiradi va farqlarni chiqaradi.

NEGA KERAK
----------
Menejer KP ni qo'lda tuzadi. Haqiqiy 7 juftda (2026-10-03) deyarli har
birida farq chiqdi: KP ga kirmagan qurilma, almashgan o'lcham, tushib
qolgan HEPA filtr, nusxa qilingan tavsif. Bu skript KP yuborilishidan
OLDIN shu farqlarni ko'rsatadi.

QAROR QILMAYDI
--------------
Farqning bir qismi menejerning ongli qarori bo'lishi mumkin (mijoz bilan
kelishilgan). Skript hech narsani tuzatmaydi va hech narsa yozmaydi.

ISHLATISH
---------
    python -m skriptlar.tz_tekshir KP.pdf TZ.xlsx [TZ2.xlsx …]
    python -m skriptlar.tz_tekshir KP.pdf papka_yoki_fayllar/

TZ fayllari: Excel spetsifikatsiya / ro'yxat / zayavka (.xlsx) yoki
VENTAS tanlov ma'lumotnomalari (.pdf — papka ham bo'ladi). Skan PDF,
rasm va DWG hozircha qabul qilinmaydi — skript buni ochiq aytadi.

Chiqish kodi: 0 — jiddiy farq yo'q, 1 — jiddiy farq bor, 2 — o'qib bo'lmadi.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kp.kp_pdf import kp_oqi
from kp.solishtir import JIDDIY, Natija, hisobot, solishtir, ventas_solishtir
from kp.tz_jadval import jadval_oqi
from kp.ventas import ventas_oqi


def _fayllar(yollar: list[str]) -> list[Path]:
    natija: list[Path] = []
    for y in map(Path, yollar):
        if y.is_dir():
            natija += sorted(p for p in y.rglob("*") if p.is_file())
        else:
            natija.append(y)
    return natija


def tekshir(kp_yoli: str, tz_yollari: list[str]) -> tuple[Natija | None, list[str]]:
    """(natija, ogohlantirishlar). Natija `None` — solishtiradigan TZ yo'q."""
    kp = kp_oqi(kp_yoli)
    ogoh: list[str] = []
    if not kp.yigindi_mosmi():
        ogoh.append("KP qatorlari yig'indisi «Итого» bilan mos emas — PDF to'liq "
                    "o'qilmagan bo'lishi mumkin")

    jadval_qatorlari = []
    qurilmalar = []
    for yol in _fayllar(tz_yollari):
        if yol.resolve() == Path(kp_yoli).resolve():
            continue    # TZ papkasida KP ning o'zi ham turgan bo'lishi mumkin
        kengaytma = yol.suffix.lower()
        if kengaytma == ".xlsx":
            j = jadval_oqi(yol)
            jadval_qatorlari += j.qatorlar
            ogoh += [f"{yol.name}: {o}" for o in j.ogohlantirishlar]
        elif kengaytma == ".pdf":
            q = ventas_oqi(yol)
            if q is not None:
                qurilmalar.append(q)
            else:
                ogoh.append(f"{yol.name}: tanlov ma'lumotnomasi emas (skan chizma yoki "
                            "boshqa PDF) — hozircha o'qilmaydi")
        else:
            ogoh.append(f"{yol.name}: «{kengaytma}» hozircha o'qilmaydi "
                        "(rasm, DWG, arxiv — keyingi bosqichda)")

    if qurilmalar and not jadval_qatorlari:
        return ventas_solishtir(qurilmalar, kp), ogoh
    if jadval_qatorlari:
        natija = solishtir(jadval_qatorlari, kp)
        if qurilmalar:
            ogoh.append("TZ da ham Excel, ham tanlov PDF bor — faqat Excel solishtirildi")
        return natija, ogoh
    return None, ogoh


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    kp_yoli, tz_yollari = argv[0], argv[1:]
    try:
        natija, ogoh = tekshir(kp_yoli, tz_yollari)
    except Exception as xato:     # noqa: BLE001 — skript: sababini aytib chiqamiz
        print(f"O'qib bo'lmadi: {xato}")
        return 2
    for o in ogoh:
        print(f"! {o}")
    if natija is None:
        print("Solishtiradigan TZ topilmadi.")
        return 2
    print(hisobot(natija, f"KP: {Path(kp_yoli).name}"))
    return 1 if any(f.daraja == JIDDIY for f in natija.farqlar) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
