"""Testlar uchun umumiy sozlash.

ENG MUHIM QOIDA: testlar tarmoqqa CHIQMAYDI. Agentlar endi ichki API'ga
ulanadi, shuning uchun standart holda har qanday API so'rovi bloklanadi —
agar biror test tasodifan tarmoqqa chiqmoqchi bo'lsa, u "API mavjud emas"
yo'lidan ketadi (bu ham tekshiriladigan haqiqiy holat).

Ichki API bilan ishlaydigan yo'lni sinash uchun `soxta_api` yordamchisidan
foydalaning (`tests/soxta.py`).
"""

from __future__ import annotations

import pytest

from integrations.climavent_client import ApiXatosi, ClimaventKlient
from integrations.climavent_yozuvchi import ClimaventYozuvchi, YozishXatosi


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "oz_transporti: test klientni o'z soxta transporti bilan quradi "
        "(umumiy tarmoq blokidan ozod)",
    )
    config.addinivalue_line(
        "markers",
        "haqiqiy_bilim: test bilim bazasini o'zi quradi (bo'sh baza blokidan ozod)",
    )


@pytest.fixture(autouse=True)
def tarmoq_yopiq(request, monkeypatch):
    """Har qanday ichki API so'rovini bloklaydi."""
    if request.node.get_closest_marker("oz_transporti"):
        return

    async def bloklangan(self, *args, **kw):
        raise ApiXatosi("test: tarmoq yopiq")

    monkeypatch.setattr(ClimaventKlient, "_sorov", bloklangan)
    monkeypatch.setattr(ClimaventKlient, "xususiyat_matni", bloklangan)

    # Tender hujjatlari va valyuta kurslari ham tarmoqdan keladi.
    # Standart holda hujjat BO'SH (brend topilmaydi, "tekshirilmadi" ham
    # emas, hujjat bahosi uchun model CHAQIRILMAYDI), kurs esa olinmaydi
    # (so'mdagi lotlar tartibi o'zgarmaydi). Test o'z qiymatini
    # `monkeypatch` bilan qo'ysa — o'shanisi ishlaydi.
    import integrations.tender_manba as tender_manba
    import integrations.valyuta as valyuta

    async def bosh_hujjat(*args, **kw):
        return tender_manba.LotHujjati()

    async def kurs_yoq(*args, **kw):
        raise valyuta.KursXatosi("test: tarmoq yopiq")

    monkeypatch.setattr(tender_manba, "etender_lot_hujjatlari", bosh_hujjat)
    monkeypatch.setattr(tender_manba, "mcuz_lot_hujjatlari", bosh_hujjat)
    monkeypatch.setattr(valyuta, "markaziy_bank_kurslari", kurs_yoq)


@pytest.fixture(autouse=True)
def yozish_yopiq(request, monkeypatch):
    """Testlar HAQIQIY katalogga hech qachon yozmaydi.

    Bu blok `oz_transporti` markeri bilan ham olib tashlanmaydi darajada
    muhim emas — o'sha markerdagi testlar o'z soxta transportini beradi va
    `_sorov` ni umuman chaqirmaydi. Lekin tasodifan haqiqiy klient yasalsa,
    so'rov shu yerda to'xtaydi.
    """
    if request.node.get_closest_marker("oz_transporti"):
        return

    async def bloklangan(self, *args, **kw):
        raise YozishXatosi("test: yozish yopiq")

    monkeypatch.setattr(ClimaventYozuvchi, "_sorov", bloklangan)
    monkeypatch.setattr(ClimaventYozuvchi, "_mavjud_yozuv", bloklangan)
    # `rasm_yukla` MULTIPART yuboradi va shu sababli `_sorov` dan
    # o'tmaydi — yuqoridagi ikki blok uni ushlamaydi. Alohida yopilmasa
    # tasodifiy test haqiqiy Cloudinary'ga surat yuklab qo'yishi mumkin.
    monkeypatch.setattr(ClimaventYozuvchi, "rasm_yukla", bloklangan)


@pytest.fixture(autouse=True)
def chiqish_yopiq(tmp_path, monkeypatch):
    """Testlar ISHLAB TURGAN kesh fayllariga yozmasin.

    JONLI MUAMMO (2026-09-09). `test_jasur.py` `Bot.tender_tekshiruvi`
    ni to'g'ridan-to'g'ri chaqirardi, u esa natijani
    `chiqish/tender_keshi.json` ga yozadi — HAQIQIY faylga. Natijada
    menejer `/tender` bosganda testdagi soxta lot chiqardi:

        1. Ventilyatorlar xaridi
           Buyurtmachi: AGMK
           https://uzex.uz/x

    Tarmoq va katalogga yozish allaqachon bloklangan edi, diskdagi kesh
    esa ochiq qolgan ekan. Endi u ham har testda vaqtinchalik papkaga
    yo'naltiriladi.
    """
    from app.config import sozlama
    from bot import tender_keshi

    monkeypatch.setattr(tender_keshi, "FAYL", tmp_path / "tender_keshi.json")
    # Texnik kesh SOZLAMA orqali yo'naltiriladi, `_texnik_kesh_fayli`
    # orqali emas: ba'zi testlar o'z kesh faylini aynan shu sozlama
    # bilan beradi va ular bizning qo'riqchimizdan keyin ishlab, o'z
    # yo'lini qo'yishi kerak.
    monkeypatch.setattr(
        sozlama(), "texnik_kesh_yoli",
        str(tmp_path / "texnik_parametrlar.json"), raising=False,
    )


@pytest.fixture(autouse=True)
def bilim_bosh(request, monkeypatch):
    """Standart holda bilim bazasi BO'SH.

    Testlar haqiqiy indeksga (va embedding modeliga) bog'lanib qolmasligi
    kerak — natija muhitga qarab o'zgarmasin. Bilim bazasi yo'lini sinash
    uchun `soxta_bilim` yordamchisidan foydalaning.
    """
    if request.node.get_closest_marker("haqiqiy_bilim"):
        return

    from bilim.qidiruv import Qidiruv

    monkeypatch.setattr(Qidiruv, "qidir", lambda self, *a, **kw: [])
    monkeypatch.setattr(Qidiruv, "agent_uchun", lambda self, *a, **kw: [])


@pytest.fixture(autouse=True)
def _katalog_keshini_tozala():
    """Har test o'z toza keshi bilan boshlanadi.

    Katalog keshi jarayon bo'yicha UMUMIY (klient nusxalari uni bo'lishadi —
    aks holda har agent katalogni qaytadan yuklardi, 11.5 s). Testlarda esa
    bu umumiylik zarar: biri soxta katalog qo'ysa, keyingisi o'shani ko'radi.
    """
    from integrations.climavent_client import _UMUMIY_KESH

    _UMUMIY_KESH._malumot.clear()
    yield
    _UMUMIY_KESH._malumot.clear()
