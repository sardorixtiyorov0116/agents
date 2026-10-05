"""`/kp` — KP tili va «KP tayyor» xulosasi (2026-10-05 e'tirozlari).

  * «o'zbekcha yozsam o'zbekcha chiqadimi?» — til saqlangan sozlama edi,
    o'zgartirish yo'li yo'q edi. Endi `/kp uz` / `/kp ru`.
  * «PDF dagini yana botda yozyapti, ortiqcha» — 50 qatorlik KP oldidan
    chatga o'sha 50 qator yozilardi. Endi faqat soni.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.baza import Baza
from bot import kp_oqim
from kp.model import KP, Mijoz, Qator, Shartlar
from kp.shakldan import Natija


class SoxtaXabar:
    def __init__(self) -> None:
        self.matnlar: list[str] = []
        self.hujjatlar: list[str] = []

    async def reply_text(self, matn: str, reply_markup=None, **_: Any) -> None:
        self.matnlar.append(matn)

    async def reply_document(self, fayl, filename: str = "", **_: Any) -> None:
        self.hujjatlar.append(filename)


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "xulosa.db")
    await b.tayyorla()
    return b


@pytest.mark.parametrize("matn, til", [
    ("/kp uz", "uz"), ("/kp ru", "ru"), ("/kp o'zbekcha", "uz"), ("/kp ruscha", "ru"),
    ("/kp", None), ("/kp@climavent_bot", None),
])
def test_til_buyruqdan(matn, til):
    assert kp_oqim.til_buyruqdan(matn) == til


@pytest.mark.asyncio
async def test_kp_uz_tilni_saqlaydi_va_aytadi(baza):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 77, til="ru")
    assert "KP tili: *ruscha*" in xabar.matnlar[0]
    await kp_oqim.boshla(baza, xabar, 77, til="uz")
    assert (await baza.foydalanuvchi_sozlamasi(77))["kp_tili"] == "uz"
    await kp_oqim.boshla(baza, xabar, 77)              # aytilmasa — saqlangani
    assert "oʻzbekcha" in xabar.matnlar[-2]


@pytest.mark.asyncio
async def test_KP_tayyor_xulosasida_qatorlar_royxati_YOQ(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(kp_oqim, "sozlama", lambda: SimpleNamespace(kp_yoli=str(tmp_path)))
    qatorlar = [Qator(nomi="- 9 СЕКЦИЯ", birlik_narx=0.0)] + [
        Qator(nomi=f"Вентилятор канальный ВК-{d}С (В{d})") for d in range(100, 150)]
    monkeypatch.setattr(kp_oqim, "hujjatlarni_yasa", lambda kp, papka: {})
    kp = KP(raqam="X-1", sana=date.today(), mijoz=Mijoz(nomi="Sinov"), qatorlar=qatorlar,
            shartlar=Shartlar(), rekvizitlar={}, til="ru")
    xabar = SoxtaXabar()
    await kp_oqim._natijani_yubor(xabar, Natija(kp=kp))
    matn = "\n".join(xabar.matnlar)
    assert "ВК-120С" not in matn                       # hujjatdagi qatorlar chatda yo'q
    assert "50 pozitsiya" in matn and "Narxsiz: 50" in matn
    assert "til: ruscha" in matn
