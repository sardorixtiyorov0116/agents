"""DXMAP manbasi — davlat xaridlarining markaziy portali.

Bu yerdagi testlar ikki narsani qo'riqlaydi:
  1) SUMMA TIYINDAN SO'MGA o'giriladi. Portal API si tiyinda beradi;
     bo'linmasa har bir narx 100 barobar katta chiqadi (JV-65 dagi
     valyuta xatosining aynan o'zi).
  2) HAVOLASIZ e'lon chiqmaydi. Shartnomada shunday yozilgan, chunki
     menejer tekshira olmaydigan lot foydasiz.
"""

from __future__ import annotations

import json

import httpx
import pytest

from integrations.tender_manba import (
    DxmapManba,
    TenderXatosi,
    _dxmap_sarlavha,
    standart_manbalar,
)


def yozuv(**ustama):
    """Portal qaytaradigan bitta lot — haqiqiy javobdan ko'chirilgan shakl."""
    asos = {
        "lotId": 261111145619293,
        "organ": '"XIVA MURUVVAT" DM',
        "organInn": "201987332",
        "organizationType": "BUDGET",
        "enktCodes": "33.12.18.000-00001",
        "enktNames": "Ventilyatsiya va konditsiyalash tizimiga texnik xizmat",
        "startSumma": 460000000,          # TIYINDA
        "date": "2026-09-04",
        "startDate": "2026-09-04",
        "platformName": "xarid.uzex.uz",
        "purchaseType": "E_STORE",
        "regionName": "Xorazm viloyati",
        "districtName": "Xiva shahar",
        "lotStatus": "IN_PROCESS",
    }
    asos.update(ustama)
    return asos


def transport(yozuvlar, holat=200):
    """Har qanday kalit so'zga bir xil javob qaytaradigan soxta portal."""
    chaqiruvlar: list[dict] = []

    def ishlov(sorov: httpx.Request) -> httpx.Response:
        chaqiruvlar.append(json.loads(sorov.content.decode() or "{}"))
        if holat >= 400:
            return httpx.Response(holat)
        return httpx.Response(200, json={"content": yozuvlar})

    return httpx.MockTransport(ishlov), chaqiruvlar


async def manba_bilan(yozuvlar, holat=200, **kw):
    tr, chaqiruvlar = transport(yozuvlar, holat)
    async with httpx.AsyncClient(transport=tr) as mijoz:
        m = DxmapManba(mijoz=mijoz, kalit_sozlar=("ventilyatsiya",), **kw)
        return await m.elonlar(chek=40), chaqiruvlar


# --- summa ---------------------------------------------------------------

async def test_summa_tiyindan_somga_ogiriladi():
    elonlar, _ = await manba_bilan([yozuv(startSumma=100_000_000)])
    # Portalda "1 000 000,00 so'm" deb ko'rsatiladi.
    assert elonlar[0].summa == 1_000_000


async def test_summa_yoq_bolsa_None_qoladi():
    """Nol summa 0 so'm emas — «ma'lum emas» degani."""
    elonlar, _ = await manba_bilan([yozuv(startSumma=0)])
    assert elonlar[0].summa is None
    assert "summa" not in elonlar[0].qisqa()


# --- havola --------------------------------------------------------------

async def test_havola_lot_stir_va_turdan_yigiladi():
    elonlar, _ = await manba_bilan([yozuv()])
    assert elonlar[0].havola == (
        "https://xarid.icppa.uz/contracts/organ/201987332/261111145619293/BUDGET"
    )


@pytest.mark.parametrize("yoq", ["lotId", "organInn", "organizationType"])
async def test_havola_yigib_bolmasa_elon_TASHLANADI(yoq):
    elonlar, _ = await manba_bilan([yozuv(**{yoq: None})])
    assert elonlar == []


async def test_nomsiz_lot_tashlanadi():
    """Sarlavhasiz e'lon menejerga hech narsa aytmaydi."""
    elonlar, _ = await manba_bilan([yozuv(enktNames="")])
    assert elonlar == []


# --- sarlavha ------------------------------------------------------------

def test_kop_pozitsiyali_lot_qisqartiriladi():
    nom = _dxmap_sarlavha({"enktNames": "Sheben\nTuproq\nDyubel\nSalnik\nBoshqa"})
    assert nom == "Sheben / Tuproq / Dyubel (+2 pozitsiya)"


def test_bitta_pozitsiya_ozgarmaydi():
    assert _dxmap_sarlavha({"enktNames": "Metall ventilyatsiya shaxtasi"}) == (
        "Metall ventilyatsiya shaxtasi"
    )


# --- maydonlar -----------------------------------------------------------

async def test_tuzilgan_maydonlar_toldiriladi():
    elonlar, _ = await manba_bilan([yozuv()])
    e = elonlar[0]
    assert e.lot_raqami == "261111145619293"
    assert e.buyurtmachi_stir == "201987332"
    assert e.maydoncha == "xarid.uzex.uz"
    assert e.hudud == "Xorazm viloyati Xiva shahar"
    assert e.tasnif == "33.12.18.000-00001"


async def test_bosh_maydon_natijaga_tushmaydi():
    """«Bor» deb ko'rsatilgan bo'sh maydon menejerni chalg'itadi."""
    elonlar, _ = await manba_bilan([yozuv(regionName="", districtName="")])
    assert "hudud" not in elonlar[0].qisqa()


# --- so'rov shakli -------------------------------------------------------

async def test_faqat_jarayondagi_lotlar_soraladi():
    _, chaqiruvlar = await manba_bilan([yozuv()])
    assert chaqiruvlar[0] == {"search": "ventilyatsiya", "lotStatus": "IN_PROCESS"}


async def test_bosqich_ochirilsa_filtr_yuborilmaydi():
    _, chaqiruvlar = await manba_bilan([yozuv()], bosqich="")
    assert "lotStatus" not in chaqiruvlar[0]


async def test_har_kalit_soz_alohida_soraladi():
    tr, chaqiruvlar = transport([yozuv()])
    async with httpx.AsyncClient(transport=tr) as mijoz:
        m = DxmapManba(mijoz=mijoz, kalit_sozlar=("ventilyatsiya", "panjara"))
        await m.elonlar(chek=40)
    assert [c["search"] for c in chaqiruvlar] == ["ventilyatsiya", "panjara"]


async def test_takrorlangan_lot_bir_marta_qaytadi():
    """Ikki kalit so'z bitta lotni topsa — ro'yxatda bitta bo'ladi."""
    tr, _ = transport([yozuv()])
    async with httpx.AsyncClient(transport=tr) as mijoz:
        m = DxmapManba(mijoz=mijoz, kalit_sozlar=("ventilyatsiya", "shamollatish"))
        elonlar = await m.elonlar(chek=40)
    assert len(elonlar) == 1


# --- nosozlik ------------------------------------------------------------

async def test_hamma_sorov_yiqilsa_XATO_beriladi():
    """Jimgina «e'lon yo'q» deyish — eng yomon xatolik turi."""
    with pytest.raises(TenderXatosi):
        await manba_bilan([], holat=500)


async def test_bitta_soz_yiqilsa_qolganlari_ishlaydi():
    navbat = [500, 200]

    def ishlov(sorov: httpx.Request) -> httpx.Response:
        kod = navbat.pop(0)
        if kod >= 400:
            return httpx.Response(kod)
        return httpx.Response(200, json={"content": [yozuv()]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(ishlov)) as mijoz:
        m = DxmapManba(mijoz=mijoz, kalit_sozlar=("ventilyatsiya", "panjara"))
        elonlar = await m.elonlar(chek=40)
    assert len(elonlar) == 1


async def test_javob_json_bolmasa_yiqilmaydi():
    def ishlov(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>xizmat vaqtincha ishlamayapti")

    async with httpx.AsyncClient(transport=httpx.MockTransport(ishlov)) as mijoz:
        m = DxmapManba(mijoz=mijoz, kalit_sozlar=("ventilyatsiya",))
        with pytest.raises(TenderXatosi):
            await m.elonlar(chek=40)


# --- qamrov / sozlama ----------------------------------------------------

def test_qamrov_kalit_sozlarni_ochiq_aytadi():
    """Topilmagan e'lon jimgina yo'qolmasin — nima qidirilgani ko'rinsin."""
    matn = DxmapManba(kalit_sozlar=("ventilyatsiya", "panjara")).qamrov()
    assert "ventilyatsiya" in matn and "panjara" in matn


def test_STANDART_holatda_faqat_ishtirok_etiladigan_manba():
    """DXMAP standart holatda O'CHIQ — u AXBOROT portali.

    O'LCHANDI (2026-09-09): DXMAP havolasi taklif berish sahifasiga olib
    bormaydi (o'z kartochkasini ko'rsatadi) va API haqiqiy maydoncha
    havolasini bermaydi. Ustiga `IN_PROCESS` lotlarning 84% ida
    shartnoma allaqachon tuzilgan.
    """
    manbalar = standart_manbalar()

    assert not any(isinstance(m, DxmapManba) for m in manbalar)
    # Faqat taklif berish mumkin bo'lgan maydonchalar.
    nomlar = [m.nomi for m in manbalar]
    assert any("etender" in n for n in nomlar), nomlar
    assert any("tender.mc.uz" in n for n in nomlar), nomlar


def test_DXMAP_sozlama_bilan_yoqiladi():
    """Boshqa maydonchada ro'yxatdan o'tilsa — qaytarib yoqiladi."""
    manbalar = standart_manbalar(["etender", "dxmap"])

    assert any(isinstance(m, DxmapManba) for m in manbalar)
