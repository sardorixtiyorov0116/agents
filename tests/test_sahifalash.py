"""Ro'yxat endpointlari SAHIFALAB o'qilishi.

IKKI MARTA TAKRORLANGAN XATO — shuning uchun alohida test:

  2026-08-06  Backend `/api/products/all` ga standart chegara (20) qo'ydi
              (buni biz so'ragan edik). Klient parametrsiz so'rardi va
              137 o'rniga 20 ta mahsulot olardi. API 200 qaytardi, xato
              hech qayerda ko'rinmadi — Rustam Ø315 ga uskuna topa
              olmadi, Temur omborga SHAXTA ventilyatorini tanladi.

  2026-08-11  Backend `product-models/all` ga ham sahifalash qo'shdi.
              Parametrsiz so'rov 1482 o'rniga 50 ta qaytardi — ya'ni
              narx va SAP kodi modellarning 3% ida qidirilardi.

Xulosa: ro'yxat parametrsiz so'ralmaydi. Hech qachon.
"""

from __future__ import annotations

import pytest

from integrations.climavent_client import SAHIFA_HAJMI, ClimaventKlient


class SoxtaSahifalovchi:
    """Sahifalashni majburlaydigan soxta API: parametrsiz — kam qaytaradi."""

    def __init__(self, jami: int, standart_chegara: int = 20):
        self.jami = jami
        self.standart_chegara = standart_chegara
        self.sorovlar: list[str] = []

    async def javob(self, metod: str, yol: str, tana=None):
        self.sorovlar.append(yol)
        if "limit=" not in yol:
            # Backend aynan shunday qiladi: jimgina kesib qaytaradi.
            return [{"id": i, "name": f"M{i}"} for i in range(self.standart_chegara)]
        chegara = int(yol.split("limit=")[1].split("&")[0])
        sahifa = int(yol.split("page=")[1].split("&")[0])
        boshi = (sahifa - 1) * chegara
        return [
            {"id": i, "name": f"M{i}"}
            for i in range(boshi, min(boshi + chegara, self.jami))
        ]


def klient_yasa(soxta: SoxtaSahifalovchi) -> ClimaventKlient:
    k = ClimaventKlient()
    k._sorov = soxta.javob  # type: ignore[method-assign]
    return k


@pytest.mark.asyncio
@pytest.mark.parametrize("jami", [137, 1482, 941])
async def test_royxat_toliq_oqiladi(jami):
    soxta = SoxtaSahifalovchi(jami)

    natija = await klient_yasa(soxta)._sahifalab("/api/x/all", "sinov")

    assert len(natija) == jami


@pytest.mark.asyncio
async def test_har_sorovda_limit_boladi():
    """Parametrsiz so'rov — aynan shu xatoga olib kelgan edi."""
    soxta = SoxtaSahifalovchi(300)

    await klient_yasa(soxta)._sahifalab("/api/x/all", "sinov")

    assert soxta.sorovlar, "umuman so'rov yuborilmadi"
    for yol in soxta.sorovlar:
        assert "limit=" in yol and "page=" in yol, f"parametrsiz so'rov: {yol}"


@pytest.mark.asyncio
async def test_endpointlar_sahifalanadi():
    """Ikkalasi ham `_sahifalab` orqali o'qilsin — biri unutilmasin."""
    import inspect

    import integrations.climavent_client as modul

    # `modellar` ro'yxatdan chiqdi: `/api/product-models/all` backenddan
    # olib tashlangan va metodning o'zi ham yo'q (2026-09-09).
    for metod, yol in (
        (modul.ClimaventKlient.mahsulotlar, "/api/products/all"),
        (modul.ClimaventKlient.artikullar, "/api/product-model-inside"),
    ):
        manba = inspect.getsource(metod)
        assert "_sahifalab" in manba, f"{metod.__name__}: sahifalash yo'q"
        assert f'"GET", "{yol}"' not in manba, (
            f"{metod.__name__}: hali ham parametrsiz so'rayapti"
        )


@pytest.mark.asyncio
async def test_chegaraga_yetganda_ogohlantiradi():
    """Ro'yxat juda uzun bo'lsa — jimgina kesib tashlamaymiz."""
    from integrations import climavent_client

    soxta = SoxtaSahifalovchi(10_000_000)
    klient = klient_yasa(soxta)
    asl = climavent_client.MAKS_SAHIFA
    climavent_client.MAKS_SAHIFA = 3
    try:
        natija = await klient._sahifalab("/api/x/all", "sinov")
    finally:
        climavent_client.MAKS_SAHIFA = asl

    assert len(natija) == 3 * SAHIFA_HAJMI
    assert "hammasi o'qilmadi" in klient.ogohlantirish
