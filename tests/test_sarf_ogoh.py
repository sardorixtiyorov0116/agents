"""Limit ogohlantirishi.

NEGA BU TESTLAR BOR
-------------------
`/sarf` sonni ko'rsatadi, lekin uni menejer YOZISHI kerak — hech kim
har soatda buyruq yozib turmaydi. Ogohlantirish teskari yo'nalishda
ishlaydi, shuning uchun uning ikkita xossasi qat'iy:

1. TAKRORLANMASLIK. Limitga yetgan bot har chaqiruvda xabar yuborsa,
   menejer telefoni ko'miladi va o'sha xabarlar orasida haqiqiy KP
   yo'qoladi.

2. XATO YO'LI SOZLAMASIZ ISHLASHI. `GEMINI_KUNLIK_LIMIT` standart
   holatda 0 ("noma'lum") — Google chegaralarni e'lonsiz o'zgartirgani
   uchun taxminiy raqam yozishni rad etganmiz. Demak ko'p o'rnatmada
   FOIZ yo'li umuman ishlamaydi va yagona ishlaydigan signal — Google
   qaytargan `RESOURCE_EXHAUSTED` xatosi.
"""

from __future__ import annotations

import pytest

from app.sarf_ogoh import XATO_CHEGARASI, Ogohlantiruvchi


class SoxtaBaza:
    """Faqat ogohlantiruvchi ishlatadigan ikki metod."""

    def __init__(self):
        self.yozuvlar: list[dict] = []

    async def sarf_kunlik(self, provayder, kun):
        mos = [y for y in self.yozuvlar
               if y["provayder"] == provayder and y["kun"] == kun]
        return {"soni": len(mos)}

    async def sarf_xatolari(self, provayder, kun, chek=5):
        mos = [y for y in self.yozuvlar
               if y["provayder"] == provayder and y["kun"] == kun and y["xato"]]
        return list(reversed(mos))[:chek]


KUN = "2026-08-26"


def _yozuv(xato=None, provayder="gemini", kun=KUN, rol="router"):
    return {"provayder": provayder, "kun": kun, "rol": rol,
            "vaqt": f"{kun}T14:05:00+00:00", "xato": xato}


def _yasa(limit=0):
    baza = SoxtaBaza()
    return baza, Ogohlantiruvchi(baza, lambda p: limit)


async def _oqim(baza, ogoh, yozuvlar):
    """Yozuvlarni ketma-ket o'tkazadi, chiqqan xabarlarni qaytaradi."""
    xabarlar = []
    for y in yozuvlar:
        baza.yozuvlar.append(y)
        matn = await ogoh.yozuvdan_keyin(y)
        if matn:
            xabarlar.append(matn)
    return xabarlar


# --- Sabab 1: limit xatolari (sozlamasiz ishlaydi) ---------------------------


@pytest.mark.asyncio
async def test_uchta_limit_xatosidan_keyin_ogohlantiradi():
    baza, ogoh = _yasa(limit=0)          # limit NOMA'LUM

    xabarlar = await _oqim(baza, ogoh,
                           [_yozuv(xato="RESOURCE_EXHAUSTED")] * XATO_CHEGARASI)

    assert len(xabarlar) == 1
    assert "limit xatosi 3 marta" in xabarlar[0]
    assert "/kp qo'lda to'ldirish BARIBIR ishlaydi" in xabarlar[0]


@pytest.mark.asyncio
async def test_ikkita_xato_hali_YETARLI_EMAS():
    """Bitta-ikkita xato bir zumlik cho'qqi bo'lishi mumkin."""
    baza, ogoh = _yasa(limit=0)

    xabarlar = await _oqim(baza, ogoh, [_yozuv(xato="429")] * 2)

    assert xabarlar == []


@pytest.mark.asyncio
async def test_xabar_BIR_MARTA_yuboriladi():
    baza, ogoh = _yasa(limit=0)

    xabarlar = await _oqim(baza, ogoh, [_yozuv(xato="quota")] * 20)

    assert len(xabarlar) == 1


@pytest.mark.asyncio
async def test_limitga_ALOQASIZ_xatolar_ogohlantirmaydi():
    """3 ta tarmoq uzilishi limit tugagani degani emas."""
    baza, ogoh = _yasa(limit=0)

    xabarlar = await _oqim(baza, ogoh,
                           [_yozuv(xato="APIConnectionError: internet yo'q")] * 10)

    assert xabarlar == []


@pytest.mark.asyncio
async def test_muvaffaqiyatli_chaqiruvlar_ogohlantirmaydi():
    baza, ogoh = _yasa(limit=0)

    assert await _oqim(baza, ogoh, [_yozuv()] * 50) == []


# --- Sabab 2: limitning foizi ------------------------------------------------


@pytest.mark.asyncio
async def test_75_foizda_ogohlantiradi():
    baza, ogoh = _yasa(limit=100)

    xabarlar = await _oqim(baza, ogoh, [_yozuv()] * 75)

    assert len(xabarlar) == 1
    assert "75%" in xabarlar[0]
    assert "75/100" in xabarlar[0]
    assert "Qolgan: 25" in xabarlar[0]


@pytest.mark.asyncio
async def test_har_chegara_ALOHIDA_bir_marta():
    baza, ogoh = _yasa(limit=100)

    xabarlar = await _oqim(baza, ogoh, [_yozuv()] * 100)

    assert len(xabarlar) == 3          # 75%, 90%, 100%
    assert "75%" in xabarlar[0]
    assert "90%" in xabarlar[1]
    assert "TUGADI" in xabarlar[2]


@pytest.mark.asyncio
async def test_limitdan_keyin_ham_TAKRORLANMAYDI():
    baza, ogoh = _yasa(limit=10)

    xabarlar = await _oqim(baza, ogoh, [_yozuv()] * 40)

    assert len(xabarlar) == 3


@pytest.mark.asyncio
async def test_limit_NOMALUM_bolsa_foiz_yoli_JIM():
    baza, ogoh = _yasa(limit=0)

    assert await _oqim(baza, ogoh, [_yozuv()] * 500) == []


@pytest.mark.asyncio
async def test_limit_tugaganda_qolda_ishlash_yoli_aytiladi():
    baza, ogoh = _yasa(limit=4)

    xabarlar = await _oqim(baza, ogoh, [_yozuv()] * 4)

    assert "/kp qo'lda to'ldirish ishlayveradi" in xabarlar[-1]


# --- Kun almashishi ----------------------------------------------------------


@pytest.mark.asyncio
async def test_yangi_kvota_kunida_QAYTA_ogohlantiradi():
    """Kunlik limit yangilanadi — holat ham yangilanishi kerak."""
    baza, ogoh = _yasa(limit=4)

    birinchi = await _oqim(baza, ogoh, [_yozuv(kun="2026-08-26")] * 4)
    ikkinchi = await _oqim(baza, ogoh, [_yozuv(kun="2026-08-27")] * 4)

    assert len(birinchi) >= 1 and len(ikkinchi) >= 1


@pytest.mark.asyncio
async def test_provayderlar_bir_biriga_TASIR_QILMAYDI():
    baza = SoxtaBaza()
    # Faqat gemini limitli.
    ogoh = Ogohlantiruvchi(baza, lambda p: 10 if p == "gemini" else 0)

    xabarlar = await _oqim(baza, ogoh,
                           [_yozuv(provayder="anthropic")] * 20
                           + [_yozuv(provayder="gemini")] * 10)

    assert len(xabarlar) == 3
    assert all("gemini" in x for x in xabarlar)


# --- Xotira va baza mos kelmasa ----------------------------------------------


@pytest.mark.asyncio
async def test_xabar_yuborishdan_OLDIN_baza_tekshiriladi():
    """Panel va bot alohida jarayonlar — xotiradagi sanoq faqat darvoza.

    Bu yerda xotira 3 ta xato deb hisoblaydi, lekin bazada 1 tasi bor.
    Xabar chiqmasligi kerak, aks holda noto'g'ri signal berilardi.
    """
    baza = SoxtaBaza()
    ogoh = Ogohlantiruvchi(baza, lambda p: 0)

    xabarlar = []
    for _ in range(XATO_CHEGARASI):
        y = _yozuv(xato="RESOURCE_EXHAUSTED")
        # Bazaga ATAYLAB yozilmaydi.
        matn = await ogoh.yozuvdan_keyin(y)
        if matn:
            xabarlar.append(matn)

    assert xabarlar == []


@pytest.mark.asyncio
async def test_baza_kechikkanda_keyinroq_baribir_ogohlantiradi():
    """Yuqoridagi holat vaqtinchalik bo'lsa — signal yo'qolib ketmasin."""
    baza = SoxtaBaza()
    ogoh = Ogohlantiruvchi(baza, lambda p: 0)

    for _ in range(XATO_CHEGARASI):
        await ogoh.yozuvdan_keyin(_yozuv(xato="quota"))      # bazasiz

    xabarlar = await _oqim(baza, ogoh, [_yozuv(xato="quota")] * XATO_CHEGARASI)

    assert len(xabarlar) == 1


@pytest.mark.asyncio
async def test_kichik_limitda_chegara_OTKAZIB_yuborilishi_mumkin():
    """limit=4 da 90% ga tushadigan butun son yo'q: 3/4=75%, 4/4=100%.

    Ya'ni xabarlar soni chegaralar soniga TENG EMAS — bu kutilgan
    xatti-harakat, chegara har doim "shu darajadan oshgani" bo'yicha
    tanlanadi, "shu darajaga aniq tushgani" bo'yicha emas.
    """
    baza, ogoh = _yasa(limit=4)

    xabarlar = await _oqim(baza, ogoh, [_yozuv()] * 4)

    assert len(xabarlar) == 2
    assert "75%" in xabarlar[0] and "TUGADI" in xabarlar[1]


# --- Sabab 3: lokal (zaxira) modelga tushildi --------------------------------


@pytest.mark.asyncio
async def test_LOKAL_modelga_tushilsa_ogohlantiriladi():
    """Jim xavf: lokal model ishlayveradi, tizim "sog'" ko'rinadi.

    Lekin sifat o'lchangan darajada pastroq. Menejer buni bilmasa,
    pastroq javobni odatdagi javob deb qabul qiladi.
    """
    o = Ogohlantiruvchi(SoxtaBaza(), lambda p: 0)

    matn = await o.yozuvdan_keyin(
        {"provayder": "ollama", "model": "qwen3:8b", "kun": "2026-09-07"}
    )

    assert matn is not None, "lokal modelga tushilgani aytilmadi"
    assert "LOKAL" in matn
    assert "sifati pastroq" in matn


@pytest.mark.asyncio
async def test_lokal_ogohi_kuniga_BIR_MARTA():
    """Har chaqiruvda xabar yuborilsa, menejer telefoni ko'miladi."""
    o = Ogohlantiruvchi(SoxtaBaza(), lambda p: 0)
    yozuv = {"provayder": "ollama", "model": "qwen3:8b", "kun": "2026-09-07"}

    birinchi = await o.yozuvdan_keyin(dict(yozuv))
    ikkinchi = await o.yozuvdan_keyin(dict(yozuv))
    uchinchi = await o.yozuvdan_keyin(dict(yozuv))

    assert birinchi is not None
    assert ikkinchi is None and uchinchi is None


@pytest.mark.asyncio
async def test_yangi_kunda_lokal_ogohi_QAYTA_beriladi():
    """Ertaga yana lokalga tushsa — bu yangi hodisa, aytilishi kerak."""
    o = Ogohlantiruvchi(SoxtaBaza(), lambda p: 0)

    await o.yozuvdan_keyin(
        {"provayder": "ollama", "model": "qwen3:8b", "kun": "2026-09-07"})
    ertaga = await o.yozuvdan_keyin(
        {"provayder": "ollama", "model": "qwen3:8b", "kun": "2026-09-08"})

    assert ertaga is not None


@pytest.mark.asyncio
async def test_BULUT_yozuvi_lokal_ogohini_bermaydi():
    o = Ogohlantiruvchi(SoxtaBaza(), lambda p: 0)

    matn = await o.yozuvdan_keyin(
        {"provayder": "gemini", "model": "gemini-3.5-flash", "kun": "2026-09-07"})

    assert matn is None
