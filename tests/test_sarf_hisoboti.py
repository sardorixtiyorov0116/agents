"""`/sarf` hisoboti — bazadan yig'ish va matn.

Raqamlar SQL agregatsiyasidan keladi, modeldan emas: bir xil kun har
safar bir xil natija berishi shart.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.baza import Baza
from app.config import sozlama
from app.sarf import kvota_kuni
from app.sarf_hisoboti import hisobot_matni


@pytest.fixture
async def baza(tmp_path):
    b = Baza(yol=tmp_path / "sinov.db")
    await b.tayyorla()
    return b


def _yozuv(provayder="gemini", rol="router", kirish=100, chiqish=20,
           xato=None, kun=None, vaqt=None):
    hozir = datetime.now(timezone.utc)
    return {
        "vaqt": (vaqt or hozir).isoformat(timespec="seconds"),
        "kun": kun or kvota_kuni(provayder, hozir),
        "provayder": provayder,
        "model": "gemini-3.5-flash",
        "rol": rol,
        "kirish": kirish,
        "chiqish": chiqish,
        "ms": 1200,
        "xato": xato,
    }


@pytest.mark.asyncio
async def test_kunlik_yigindi(baza):
    for _ in range(3):
        await baza.sarf_yoz(_yozuv(kirish=100, chiqish=20))
    # Xatoli chaqiruvda javob umuman kelmaydi -> token nol.
    await baza.sarf_yoz(_yozuv(kirish=0, chiqish=0, xato="429 quota"))

    kun = kvota_kuni("gemini")
    y = await baza.sarf_kunlik("gemini", kun)

    assert y["soni"] == 4            # xatoli urinish ham kvotani yeydi
    assert y["muvaffaq"] == 3
    assert y["xatolar"] == 1
    assert y["kirish"] == 300
    assert y["chiqish"] == 60


@pytest.mark.asyncio
async def test_rollar_boyicha_ajratiladi(baza):
    await baza.sarf_yoz(_yozuv(rol="router"))
    await baza.sarf_yoz(_yozuv(rol="router"))
    await baza.sarf_yoz(_yozuv(rol="hvac-calc"))

    rollar = await baza.sarf_rollar("gemini", kvota_kuni("gemini"))

    assert rollar[0]["rol"] == "router" and rollar[0]["soni"] == 2
    assert rollar[1]["rol"] == "hvac-calc" and rollar[1]["soni"] == 1


@pytest.mark.asyncio
async def test_provayderlar_ajratiladi(baza):
    await baza.sarf_yoz(_yozuv(provayder="gemini"))
    await baza.sarf_yoz(_yozuv(provayder="anthropic"))

    kun = kvota_kuni("gemini")
    assert (await baza.sarf_kunlik("gemini", kun))["soni"] == 1
    assert (await baza.sarf_kunlik("anthropic", kvota_kuni("anthropic")))["soni"] == 1


@pytest.mark.asyncio
async def test_boshqa_kun_bugungi_songa_QOSHILMAYDI(baza):
    await baza.sarf_yoz(_yozuv())
    await baza.sarf_yoz(_yozuv(kun="2020-01-01"))

    assert (await baza.sarf_kunlik("gemini", kvota_kuni("gemini")))["soni"] == 1


@pytest.mark.asyncio
async def test_oxirgi_daqiqa_oynasi(baza):
    hozir = datetime.now(timezone.utc)
    await baza.sarf_yoz(_yozuv(vaqt=hozir))
    await baza.sarf_yoz(_yozuv(vaqt=hozir - timedelta(minutes=5)))

    chegara = (hozir - timedelta(seconds=60)).isoformat(timespec="seconds")

    assert await baza.sarf_oxirgi_daqiqa("gemini", chegara) == 1


@pytest.mark.asyncio
async def test_limit_xatolari_alohida_korinadi(baza):
    await baza.sarf_yoz(_yozuv(xato="Gemini: RESOURCE_EXHAUSTED"))
    await baza.sarf_yoz(_yozuv(xato="APIConnectionError"))

    xatolar = await baza.sarf_xatolari("gemini", kvota_kuni("gemini"))

    assert len(xatolar) == 2


# --- Matn --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_yozuv_yoq_bolsa_TUSHUNARLI_xabar(baza):
    matn = await hisobot_matni(baza)

    assert "Hali birorta ham so'rov yozilmagan" in matn


@pytest.mark.asyncio
async def test_matnda_asosiy_raqamlar_bor(baza):
    await baza.sarf_yoz(_yozuv(rol="router"))
    await baza.sarf_yoz(_yozuv(rol="hvac-calc", xato="quota"))

    matn = await hisobot_matni(baza)

    assert "gemini" in matn
    assert "So'rovlar: 2" in matn
    assert "router" in matn and "hvac-calc" in matn
    assert "Xatolar: 1" in matn


@pytest.mark.asyncio
async def test_limit_NOMALUM_bolsa_foiz_KORSATILMAYDI(baza, monkeypatch):
    """Taxminiy limit yozib, ishonchli ko'rinishda noto'g'ri foiz
    ko'rsatish — sonini umuman bilmaganimizdan yomonroq.

    Limit ATAYLAB nolga qo'yiladi: `.env` da haqiqiy son turishi
    mumkin va u holda bu test o'rnatmaga bog'liq bo'lib qolardi.
    """
    await baza.sarf_yoz(_yozuv())

    s = sozlama()
    monkeypatch.setattr(s, "gemini_kunlik_limit", 0, raising=False)
    monkeypatch.setattr(s, "gemini_daqiqalik_limit", 0, raising=False)
    monkeypatch.setattr("app.sarf_hisoboti.sozlama", lambda: s)

    matn = await hisobot_matni(baza)

    assert "%" not in matn
    assert "Kunlik limit noma'lum" in matn


@pytest.mark.asyncio
async def test_limit_berilgan_bolsa_foiz_va_belgi_chiqadi(baza, monkeypatch):
    for _ in range(8):
        await baza.sarf_yoz(_yozuv())

    s = sozlama()
    monkeypatch.setattr(s, "gemini_kunlik_limit", 10, raising=False)
    monkeypatch.setattr("app.sarf_hisoboti.sozlama", lambda: s)

    matn = await hisobot_matni(baza)

    assert "8/10 (80%)" in matn
    assert "🟡" in matn          # 75% dan oshgan


@pytest.mark.asyncio
async def test_limitning_90_foizida_QIZIL(baza, monkeypatch):
    for _ in range(95):
        await baza.sarf_yoz(_yozuv())

    s = sozlama()
    monkeypatch.setattr(s, "gemini_kunlik_limit", 100, raising=False)
    monkeypatch.setattr("app.sarf_hisoboti.sozlama", lambda: s)

    assert "🔴" in await hisobot_matni(baza)


@pytest.mark.asyncio
async def test_zanjirda_modellar_alohida_korinadi(baza):
    """Zaxira zanjiri ishlaganda qaysi model javob berganini ko'rish shart."""
    y = _yozuv()
    y["model"] = "gemini-3.5-flash"
    y["xato"] = "RESOURCE_EXHAUSTED"
    await baza.sarf_yoz(y)

    z = _yozuv()
    z["model"] = "gemini-3.6-flash"
    await baza.sarf_yoz(z)

    matn = await hisobot_matni(baza)

    assert "Modellar (zanjir):" in matn
    assert "gemini-3.5-flash: 1 ta (1 xato)" in matn
    assert "gemini-3.6-flash: 1 ta" in matn


@pytest.mark.asyncio
async def test_bitta_model_bolsa_ORTIQCHA_qator_qoshilmaydi(baza):
    await baza.sarf_yoz(_yozuv())
    await baza.sarf_yoz(_yozuv())

    assert "Modellar (zanjir):" not in await hisobot_matni(baza)


# --- Xarajat ------------------------------------------------------------------
#
# JONLI E'TIROZ (2026-08-28): "tokenlarni suvday ichib yubordi". Bu
# tuyg'u O'LCHOVSIZ paydo bo'ladi. Aslida ikki xil xarajat bor:
# QURISH (bir martalik, katta) va ISHLASH (takrorlanadigan, kichik).
# `/sarf` ikkinchisini so'mga aylantiradi — taxmin qilish o'rniga.


def test_model_narxi_TOLIQ_nom_bilan_topiladi():
    from app.sarf_hisoboti import model_narxi

    assert model_narxi("claude-haiku-4-5-20251001") == (1.0, 5.0)


def test_model_narxi_QISQA_nom_bilan_ham_topiladi():
    from app.sarf_hisoboti import model_narxi

    assert model_narxi("claude-opus-5") == (5.0, 25.0)


def test_ENG_UZUN_mos_kelgan_yozuv_tanlanadi():
    """«gemini» yozuvi «gemini-3.5-flash» dan oldin tushib qolmasin."""
    from app.sarf_hisoboti import model_narxi

    assert model_narxi("gemini-3.5-flash-lite") == (0.0, 0.0)


def test_NOMALUM_model_narxsiz():
    """Taxminiy narx yozishdan ko'ra «noma'lum» deganimiz yaxshi."""
    from app.sarf_hisoboti import model_narxi, xarajat_somda

    assert model_narxi("yoq-bunday-model") is None
    assert xarajat_somda("yoq-bunday-model", 1000, 500, 12000.0) is None


def test_olchangan_KP_narxi():
    """O'lchangan: bitta TZ -> KP = 1124 kirish + 420 chiqish token."""
    from app.sarf_hisoboti import xarajat_somda

    haiku = xarajat_somda("claude-haiku-4-5", 1124, 420, 12000.0)
    opus = xarajat_somda("claude-opus-5", 1124, 420, 12000.0)

    assert 35 <= haiku <= 45
    assert 185 <= opus <= 200


def test_bepul_tarif_NOL():
    from app.sarf_hisoboti import xarajat_somda

    assert xarajat_somda("gemini-3.5-flash", 100_000, 50_000, 12000.0) == 0.0


@pytest.mark.asyncio
async def test_hisobotda_XARAJAT_korinadi(baza):
    y = _yozuv(provayder="anthropic")
    y["model"] = "claude-haiku-4-5"
    y["kun"] = kvota_kuni("anthropic")
    y["kirish"], y["chiqish"] = 1124, 420
    await baza.sarf_yoz(y)

    matn = await hisobot_matni(baza)

    assert "Bugungi xarajat" in matn
    assert "so'm" in matn


@pytest.mark.asyncio
async def test_bepul_tarifda_XARAJAT_NOL_deb_aytiladi(baza):
    """Nol xarajat ham ma'lumot: menejer «hisoblanmadi» deb o'ylamasin."""
    y = _yozuv()
    y["kirish"], y["chiqish"] = 1124, 420
    await baza.sarf_yoz(y)

    matn = await hisobot_matni(baza)

    assert "bepul tarif" in matn


@pytest.mark.asyncio
async def test_NOMALUM_model_bolsa_ochiq_aytiladi(baza):
    """Xarajatni kam ko'rsatgandan ko'ra «noma'lum» degan halolroq."""
    y = _yozuv(provayder="anthropic")
    y["model"] = "yoq-bunday-model"
    y["kun"] = kvota_kuni("anthropic")
    y["kirish"], y["chiqish"] = 1000, 500
    await baza.sarf_yoz(y)

    matn = await hisobot_matni(baza)

    assert "qisman noma'lum" in matn


@pytest.mark.asyncio
async def test_bepul_chegaradan_oshsa_BILLING_haqida_ogohlantiradi(baza, monkeypatch):
    """Narx fayli nol turib, billing yoqilgan bo'lsa pul jimgina ketardi.

    Bepul tarifda har model kuniga chegaradan oshmaydi. Oshgan bo'lsa —
    bu bepul tarif emas.
    """
    for _ in range(25):
        y = _yozuv()
        y["kirish"], y["chiqish"] = 1124, 420
        await baza.sarf_yoz(y)

    s = sozlama()
    monkeypatch.setattr(s, "gemini_kunlik_limit", 20, raising=False)
    monkeypatch.setattr("app.sarf_hisoboti.sozlama", lambda: s)

    matn = await hisobot_matni(baza)

    assert "billing yoqilgan bo'lishi mumkin" in matn


@pytest.mark.asyncio
async def test_chegara_ichida_billing_ogohlantirishi_YOQ(baza, monkeypatch):
    for _ in range(3):
        y = _yozuv()
        y["kirish"], y["chiqish"] = 1124, 420
        await baza.sarf_yoz(y)

    s = sozlama()
    monkeypatch.setattr(s, "gemini_kunlik_limit", 20, raising=False)
    monkeypatch.setattr("app.sarf_hisoboti.sozlama", lambda: s)

    matn = await hisobot_matni(baza)

    assert "billing" not in matn


# --- Kesh chegirmasi ----------------------------------------------------------
#
# Keshdan o'qilgan tokenlar to'liq narxning 10%ini turadi. Provayder
# ularni `kirish` ICHIDA qaytaradi, shuning uchun avval ayrilib, keyin
# arzon narxda qaytariladi — aks holda tejamkorlik umuman ko'rinmasdi.


def test_keshdan_oqilgan_tokenlar_ARZON_hisoblanadi():
    from app.sarf_hisoboti import xarajat_somda

    keshsiz = xarajat_somda("claude-haiku-4-5", 8465, 382, 12000.0)
    keshli = xarajat_somda("claude-haiku-4-5", 8465, 382, 12000.0, keshdan=4412)

    assert keshli < keshsiz
    assert 0.55 < keshli / keshsiz < 0.70      # ~40% tejam


def test_kesh_NOL_bolsa_narx_ozgarmaydi():
    from app.sarf_hisoboti import xarajat_somda

    a = xarajat_somda("claude-haiku-4-5", 5000, 500, 12000.0)
    b = xarajat_somda("claude-haiku-4-5", 5000, 500, 12000.0, keshdan=0)

    assert a == b


def test_keshdan_kirishdan_KOP_bolsa_cheklanadi():
    """Buzuq ma'lumot narxni MANFIY qilib yubormasin."""
    from app.sarf_hisoboti import xarajat_somda

    narx = xarajat_somda("claude-haiku-4-5", 1000, 100, 12000.0, keshdan=99999)

    assert narx > 0


@pytest.mark.asyncio
async def test_hisobotda_KESH_qatori_korinadi(baza):
    y = _yozuv(provayder="anthropic")
    y["model"] = "claude-haiku-4-5"
    y["kun"] = kvota_kuni("anthropic")
    y["kirish"], y["chiqish"], y["keshdan"] = 8465, 382, 4412
    await baza.sarf_yoz(y)

    matn = await hisobot_matni(baza)

    assert "Keshdan" in matn
    assert "tejaldi" in matn


@pytest.mark.asyncio
async def test_kesh_ishlamasa_qator_YOQ(baza):
    """Bepul tarifda kesh yo'q — ortiqcha qator chiqmasin."""
    y = _yozuv(provayder="anthropic")
    y["model"] = "claude-haiku-4-5"
    y["kun"] = kvota_kuni("anthropic")
    y["kirish"], y["chiqish"], y["keshdan"] = 8465, 382, 0
    await baza.sarf_yoz(y)

    matn = await hisobot_matni(baza)

    assert "Keshdan" not in matn
