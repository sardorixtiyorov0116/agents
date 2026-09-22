"""`/kp` oqimi — Telegramsiz.

Telegram obyektlari soxta: `reply_text` nima yozilganini yozib oladi.
Tarmoqqa chiqilmaydi — katalog ham soxta.

Bu yerda TEKSHIRILADIGAN uch narsa:

  1. Savol-javob ketma-ketligi va tugma bosilishi.
  2. Noto'g'ri javobda savol KUCHDA QOLADI.
  3. Shakl ochiq bo'lganda xabar ROUTERGA ketmaydi — u savolga javob.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.baza import Baza
from bot import kp_oqim
from kp.shakl import YO_L_MODEL, YO_L_OBYEKT, Shakl


class SoxtaXabar:
    """`reply_text` va `reply_document` chaqiruvlarini yozib oladi."""

    def __init__(self) -> None:
        self.matnlar: list[str] = []
        self.tugmalar: list[Any] = []
        self.hujjatlar: list[str] = []

    async def reply_text(self, matn: str, reply_markup=None, **_: Any) -> None:
        self.matnlar.append(matn)
        self.tugmalar.append(reply_markup)

    async def reply_document(self, fayl, filename: str = "", **_: Any) -> None:
        self.hujjatlar.append(filename)

    @property
    def oxirgi(self) -> str:
        return self.matnlar[-1] if self.matnlar else ""


class SoxtaSoro:
    """Tugma bosilishi (callback query)."""

    def __init__(self, data: str, xabar: SoxtaXabar) -> None:
        self.data = data
        self.message = xabar
        self.ogohlantirishlar: list[str] = []
        self.tahrirlar: list[str] = []

    async def answer(self, matn: str = "", show_alert: bool = False) -> None:
        if matn:
            self.ogohlantirishlar.append(matn)

    async def edit_message_text(self, matn: str, **_: Any) -> None:
        self.tahrirlar.append(matn)


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "oqim.db")
    await b.tayyorla()
    return b


# `ВЦ 4-75-2,5` da BESHTA quvvat bor va narxi har xil — aynan shu holatda
# aniqlashtiruv savoli chiqadi (`kp/shakldan.py::_qatorlar_modeldan`).
_ANIQLIK_KATALOG = [{
    "name_uz": "Ventilyator ВЦ 4-75",
    "characters": [{
        "title": "ВЦ 4-75-2,5",
        "insides": [
            {"in_model_name": "ВЦ 4-75-2,5-1-0,12/1500", "price": 156.76},
            {"in_model_name": "ВЦ 4-75-2,5-1-0,75/3000", "price": 199.33},
        ],
    }],
}]


class _SoxtaMijoz:
    """`_yakunla` kutgan ikkita metod — tarmoqqa chiqmasdan."""

    async def mahsulotlar(self):
        return _ANIQLIK_KATALOG

    async def texnik_parametrlar(self, yangila=False):
        return {}


@pytest.fixture(autouse=True)
def _mijoz_soxta(monkeypatch):
    monkeypatch.setattr(kp_oqim, "_mijoz", lambda: _SoxtaMijoz())


# --- oqim ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kp_boshlanganda_birinchi_savol_beriladi(baza):
    xabar = SoxtaXabar()

    await kp_oqim.boshla(baza, xabar, 111)

    assert "Yangi KP" in xabar.matnlar[0]
    assert "Mijoz kim" in xabar.matnlar[1]
    assert await kp_oqim.faolmi(baza, 111)


@pytest.mark.asyncio
async def test_javob_shaklga_ketadi_ROUTERGA_EMAS(baza):
    """Eng muhim ulanish: shakl ochiq bo'lsa xabar so'rov deb qaralmaydi."""
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)

    ishlatildi = await kp_oqim.javob(baza, xabar, 111, "Sinov MChJ")

    assert ishlatildi is True
    assert "Nima kerak" in xabar.oxirgi


@pytest.mark.asyncio
async def test_shakl_yoq_bolsa_xabar_TEGILMAYDI(baza):
    """Shakl ochilmagan bo'lsa oddiy so'rov o'z yo'li bilan ketishi kerak."""
    xabar = SoxtaXabar()

    ishlatildi = await kp_oqim.javob(baza, xabar, 999, "ВК-250П narxi qancha")

    assert ishlatildi is False
    assert xabar.matnlar == []


@pytest.mark.asyncio
async def test_notogri_javobda_savol_QAYTA_beriladi(baza):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    await kp_oqim.javob(baza, xabar, 111, "Sinov MChJ")
    await kp_oqim.javob(baza, xabar, 111, YO_L_OBYEKT)

    await kp_oqim.javob(baza, xabar, 111, "bilmayman")     # o'lcham kutilgan

    assert any("⚠️" in m for m in xabar.matnlar[-2:])
    assert "Maydon va balandlik" in xabar.oxirgi           # o'sha savol qaytdi


@pytest.mark.asyncio
async def test_tugma_javobni_yozadi(baza):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    await kp_oqim.javob(baza, xabar, 111, "Sinov MChJ")

    soro = SoxtaSoro(f"{kp_oqim.TUGMA_OLDI}yol:{YO_L_MODEL}", xabar)
    await kp_oqim.tugma(baza, soro, 111)

    saqlangan = await baza.kp_shakli(111)
    assert saqlangan["javoblar"]["yol"] == YO_L_MODEL
    assert soro.tahrirlar, "tugmalar olib tashlanishi kerak"


@pytest.mark.asyncio
async def test_eski_tugma_NOTOGRI_savolga_yozilmaydi(baza):
    """Menejer yuqoridagi eski xabar tugmasini bossa — e'tiborsiz qoldiriladi."""
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    await kp_oqim.javob(baza, xabar, 111, "Sinov MChJ")
    await kp_oqim.javob(baza, xabar, 111, YO_L_MODEL)

    # "mijoz" savoli allaqachon o'tgan
    soro = SoxtaSoro(f"{kp_oqim.TUGMA_OLDI}mijoz:xxx", xabar)
    await kp_oqim.tugma(baza, soro, 111)

    saqlangan = await baza.kp_shakli(111)
    assert saqlangan["javoblar"]["mijoz"] == "Sinov MChJ"   # o'zgarmadi
    assert soro.ogohlantirishlar


@pytest.mark.asyncio
async def test_bekor_shaklni_ochiradi(baza):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)

    bekor_qilindi = await kp_oqim.bekor(baza, xabar, 111)

    assert bekor_qilindi is True
    assert not await kp_oqim.faolmi(baza, 111)


@pytest.mark.asyncio
async def test_bekor_shakl_yoq_bolsa_FALSE(baza):
    """Bot bu qiymatga qarab tasdiqni bekor qilish yo'liga o'tadi."""
    assert await kp_oqim.bekor(baza, SoxtaXabar(), 999) is False


@pytest.mark.asyncio
async def test_shakl_qayta_ishga_tushgandan_keyin_davom_etadi(baza, tmp_path):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    await kp_oqim.javob(baza, xabar, 111, "Sinov MChJ")
    await kp_oqim.javob(baza, xabar, 111, YO_L_OBYEKT)

    # "bot qayta ishga tushdi"
    yangi_baza = Baza(tmp_path / "oqim.db")
    yangi_xabar = SoxtaXabar()
    await kp_oqim.javob(yangi_baza, yangi_xabar, 111, "250 kv, 3 metr")

    assert "Xona turi" in yangi_xabar.oxirgi


# --- savol matni --------------------------------------------------------------


@pytest.mark.asyncio
async def test_qadam_hisobi_korinadi(baza):
    xabar = SoxtaXabar()

    await kp_oqim.boshla(baza, xabar, 111)

    assert "1/" in xabar.matnlar[1]


def test_tanlov_tugmalari_yasaladi():
    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")          # keyingisi — "Nima kerak?"

    tugmalar = kp_oqim._tugmalar(shakl)

    tekis = [t for qator in tugmalar.inline_keyboard for t in qator]
    # Ikki tanlov + «Orqaga» (javob berilgan, qaytish mumkin).
    tanlovlar = [t for t in tekis if kp_oqim.ORQAGA not in t.callback_data]
    assert len(tanlovlar) == 2
    assert all(t.callback_data.startswith(kp_oqim.TUGMA_OLDI) for t in tekis)


def test_otkazsa_boladigan_savolda_OTKAZ_tugmasi_bor():
    shakl = Shakl()

    tugmalar = kp_oqim._tugmalar(shakl)      # "Mijoz kim?" — o'tkazsa bo'ladi

    tekis = [t for qator in tugmalar.inline_keyboard for t in qator]
    assert any(kp_oqim.OTKAZ in t.callback_data for t in tekis)


# --- aniqlashtiruvdan keyin shakl TIQILIB QOLMAYDI ----------------------------
#
# HAQIQIY XATO edi (2026-08-19, demo tayyorlashda ushlandi): quvvat noaniq
# bo'lganda savol beriladi, lekin javob "Shakl allaqachon to'ldirilgan" deb
# rad etilardi — menejer KP ni HECH QACHON yakunlay olmasdi. Sabab: shakl
# barcha oddiy savollarga javob olgan (tugadimi()==True), lekin aniqlashtiruv
# `Shakl` doirasidan TASHQARIDA edi.


async def _aniqlikkacha(baza, xabar, tg_id=111, miqdor="3 dona"):
    """Yordamchi: mijoz -> model -> aniqlashtiruv savoli chiqquncha."""
    await kp_oqim.boshla(baza, xabar, tg_id)
    await kp_oqim.javob(baza, xabar, tg_id, "Sinov MChJ")
    await kp_oqim.javob(baza, xabar, tg_id, YO_L_MODEL)
    await kp_oqim.javob(baza, xabar, tg_id, f"ВЦ 4-75-2,5 — {miqdor}")
    await kp_oqim.javob(baza, xabar, tg_id, "2 hafta")        # yetkazish
    await kp_oqim.javob(baza, xabar, tg_id, "Kafolat 1 yil")  # shartlar -> aniqlik


@pytest.mark.asyncio
async def test_aniqlik_soralgandan_keyin_KP_yakunlanadi(baza):
    """Bitta model ko'p quvvatli bo'lsa — savol beriladi va JAVOB QABUL QILINADI."""
    xabar = SoxtaXabar()
    await _aniqlikkacha(baza, xabar)

    assert "2 xil variant" in xabar.oxirgi, "aniqlashtiruv savoli chiqmadi"

    # Shu javobdan keyin ENDI KP TUGASHI kerak — avval bu yerda
    # "Shakl allaqachon to'ldirilgan" chiqardi.
    await kp_oqim.javob(baza, xabar, 111, "ВЦ 4-75-2,5-1-0,75/3000")

    assert "allaqachon to'ldirilgan" not in xabar.oxirgi
    assert "KP tayyor" in xabar.oxirgi, xabar.oxirgi
    assert xabar.hujjatlar, "hujjat yuborilmadi"
    assert not await kp_oqim.faolmi(baza, 111)


@pytest.mark.asyncio
async def test_aniqlik_javobida_ASL_MIQDOR_saqlanadi(baza, monkeypatch):
    """Menejer faqat model nomini yozadi — «3 dona» qayta so'ralmaydi."""
    import kp.shakldan as shakldan_modul

    yuborilgan = {}
    asl_yig = shakldan_modul.yig

    def kuzatuvchi(javoblar, *args, **kw):
        yuborilgan["oxirgi"] = javoblar
        return asl_yig(javoblar, *args, **kw)

    monkeypatch.setattr(kp_oqim, "yig", kuzatuvchi)

    xabar = SoxtaXabar()
    await _aniqlikkacha(baza, xabar, miqdor="3 dona")

    await kp_oqim.javob(baza, xabar, 111, "ВЦ 4-75-2,5-1-0,75/3000")

    assert yuborilgan["oxirgi"]["mahsulotlar"][0]["miqdor"] == 3.0


async def _obyekt_aniqligigacha(baza, xabar, tg_id=222):
    """Obyekt yo'li: mos NARXLI uskuna topilmay, model so'raladigan holat.

    `texnik_parametrlar` bo'sh (soxta mijoz) — demak hech qanday model
    sarf bo'yicha mos kelmaydi va `Aniqlik(index=-1)` chiqadi.
    """
    await kp_oqim.boshla(baza, xabar, tg_id)
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "350 kv, 5 metr", "oshxona",
                  "12", "yoq", "ikkalasi", "yoq", "40", "__tayyor__", "2 hafta", "Kafolat 1 yil"):
        await kp_oqim.javob(baza, xabar, tg_id, javob)


@pytest.mark.asyncio
async def test_obyekt_yolida_model_aytilsa_HISOB_SAQLANADI(baza):
    """JONLI XATO (2026-08-21): 350 m² oshxonaga KP da BITTA qator chiqardi.

    Sabab: mos narxli uskuna topilmaganda menejerdan model so'ralardi,
    javob kelgach esa `yol` "model" ga o'tkazilib, butun obyekt hisobi
    — havo sarfi, kanal, PANJARA, yo'nalish — tashlab yuborilardi.

    Endi obyekt yo'li saqlanadi: panjara ham, ikkita ventilyator ham
    (kirish + chiqish) KP da qoladi.
    """
    xabar = SoxtaXabar()
    await _obyekt_aniqligigacha(baza, xabar)

    assert "topilmadi" in xabar.oxirgi, xabar.oxirgi

    await kp_oqim.javob(baza, xabar, 222, "ВЦ 14-46-8-1")

    saqlangan = await baza.kp_shakli(222)
    assert saqlangan is None, "KP yakunlanmadi"
    assert "KP tayyor" in xabar.oxirgi, xabar.oxirgi
    # Panjara qatorlari KP matnida ko'rinishi kerak — bitta qator emas.
    assert "РВН" in xabar.oxirgi or "РВИ" in xabar.oxirgi, xabar.oxirgi


@pytest.mark.asyncio
async def test_obyekt_aniqligida_yol_MODELGA_otmaydi(baza, monkeypatch):
    """`yol` "obyekt" bo'lib qolsin — aks holda panjara hisoblanmaydi."""
    import kp.shakldan as shakldan_modul

    korilgan = {}
    asl_yig = shakldan_modul.yig

    def kuzatuvchi(javoblar, *args, **kw):
        korilgan["javoblar"] = dict(javoblar)
        return asl_yig(javoblar, *args, **kw)

    monkeypatch.setattr(kp_oqim, "yig", kuzatuvchi)

    xabar = SoxtaXabar()
    await _obyekt_aniqligigacha(baza, xabar)
    await kp_oqim.javob(baza, xabar, 222, "ВЦ 14-46-8-1")

    assert korilgan["javoblar"]["yol"] == YO_L_OBYEKT
    assert korilgan["javoblar"]["qol_uskuna"] == "ВЦ 14-46-8-1"
    assert korilgan["javoblar"]["yonalish"] == "ikkalasi"


@pytest.mark.asyncio
async def test_aniqlik_kutilayotganda_TUGMA_shaklga_tegmaydi(baza):
    """Aniqlashtiruv paytida eski tugma bosilsa — shakl buzilmasligi kerak."""
    xabar = SoxtaXabar()
    await _aniqlikkacha(baza, xabar, miqdor="1 dona")

    soro = SoxtaSoro(f"{kp_oqim.TUGMA_OLDI}yol:{YO_L_MODEL}", xabar)
    await kp_oqim.tugma(baza, soro, 111)                     # eski tugma

    assert soro.ogohlantirishlar, "eski tugma jimgina qabul qilingan"
    saqlangan = await baza.kp_shakli(111)
    assert kp_oqim.KUTILAYOTGAN_ANIQLIK in saqlangan["javoblar"], \
        "aniqlashtiruv holati eski tugma bosilgach yo'qolib qoldi"


@pytest.mark.asyncio
async def test_aniqlik_bosh_javobda_savol_qaytadi(baza):
    xabar = SoxtaXabar()
    await _aniqlikkacha(baza, xabar, miqdor="1 dona")

    await kp_oqim.javob(baza, xabar, 111, "   ")             # bo'sh javob

    assert "Model nomini yozing" in xabar.oxirgi
    saqlangan = await baza.kp_shakli(111)
    assert kp_oqim.KUTILAYOTGAN_ANIQLIK in saqlangan["javoblar"], \
        "bo'sh javobda ham aniqlashtiruv holati saqlanishi kerak"


# --- TZ fayli -----------------------------------------------------------------
#
# Menejer TZ yuborsa, undan shakl javoblari TAKLIF qilinadi. Eng muhim
# qoida: qiymat shaklga JIMGINA yozilmaydi — menejerga "nima topildi"
# ro'yxati ko'rsatiladi.


class SoxtaFayl:
    """`download_to_drive` — faylni diskka yozadi."""

    def __init__(self, matn: str) -> None:
        self.matn = matn

    async def download_to_drive(self, yol: str) -> None:
        from pathlib import Path

        Path(yol).write_text(self.matn, encoding="utf-8")


@pytest.fixture
def _tz_soxta(monkeypatch):
    """Modelni soxtalashtirish — testda tarmoqqa chiqilmaydi."""
    from kp.tz import TzNatija, TzXona

    async def soxta(tz_matni, turlar):
        return TzNatija(
            mijoz="TOY MCHJ", obyekt="Chilonzor SM", inn="123456789",
            xonalar=[TzXona(nomi="Zal", turi="restoran", maydon=500,
                            balandlik=3.5, odamlar=200)],
        )

    monkeypatch.setattr(kp_oqim, "_tz_ajrat", soxta)


@pytest.mark.asyncio
async def test_TZ_shakl_yoq_bolsa_TEGILMAYDI(baza):
    """Menejer boshqa maqsadda fayl yuborgan bo'lishi mumkin."""
    xabar = SoxtaXabar()

    ishlatildi = await kp_oqim.hujjat(
        baza, xabar, 999, SoxtaFayl("Ombor 800 m2"), "tz.txt")

    assert ishlatildi is False
    assert xabar.matnlar == []


@pytest.mark.asyncio
async def test_TZ_javoblarni_TOLDIRADI(baza, _tz_soxta):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)

    await kp_oqim.hujjat(
        baza, xabar, 111, SoxtaFayl("Restoran zali 500 m2, 3.5 m"), "tz.txt")

    javoblar = (await baza.kp_shakli(111))["javoblar"]
    assert javoblar["mijoz"] == "TOY MCHJ"
    assert javoblar["olcham"] == {"maydon": 500.0, "balandlik": 3.5}
    assert javoblar["xona_turi"] == "restoran"


@pytest.mark.asyncio
async def test_TZ_topilganlarni_KORSATADI(baza, _tz_soxta):
    """Qiymat jimgina yozilmaydi — menejer nima topilganini ko'radi."""
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)

    await kp_oqim.hujjat(baza, xabar, 111, SoxtaFayl("..."), "tz.txt")

    hammasi = " ".join(xabar.matnlar)
    assert "TZ dan topildi" in hammasi
    assert "TOY MCHJ" in hammasi
    assert "500" in hammasi


@pytest.mark.asyncio
async def test_TZ_menejer_javobini_BOSMAYDI(baza, _tz_soxta):
    """Menejer allaqachon aytgan qiymat TZ bilan almashtirilmaydi."""
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    await kp_oqim.javob(baza, xabar, 111, "Boshqa MChJ")     # mijoz

    await kp_oqim.hujjat(baza, xabar, 111, SoxtaFayl("..."), "tz.txt")

    javoblar = (await baza.kp_shakli(111))["javoblar"]
    assert javoblar["mijoz"] == "Boshqa MChJ", "TZ menejer javobini bosdi"


@pytest.mark.asyncio
async def test_TZ_oqilmasa_SABABINI_aytadi(baza):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)

    await kp_oqim.hujjat(baza, xabar, 111, SoxtaFayl(""), "bosh.txt")

    assert "⚠️" in xabar.oxirgi
    assert "matn topilmadi" in xabar.oxirgi or "Skanerlangan" in xabar.oxirgi


# --- uskuna tanlash: BITTA xabar, ✅ belgilar ----------------------------------
#
# JONLI E'TIROZ (2026-08-26): har bosishda YANGI xabar chiqardi va ekran
# «✅ Tizimga nima qo'shamiz? — rekuperator» qatorlari bilan to'lardi.
# Menejer nima tanlanganini yo'qotib qo'yardi.


def _uskuna_savoligacha() -> Shakl:
    shakl = Shakl()
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "350 kv, 6 m",
                  "ishlab_chiqarish", "20", "yoq", "ikkalasi", "yoq", "40"):
        shakl.javob_ber(javob)
    return shakl


def test_tanlangan_uskunaga_BELGI_qoyiladi():
    shakl = _uskuna_savoligacha()
    shakl.javob_ber("filtr")

    tekis = [t.text for q in kp_oqim._tugmalar(shakl).inline_keyboard for t in q]

    assert any(t.startswith("✅") and "Filtr" in t for t in tekis)
    assert not any(t.startswith("✅") and "Sovutgich" in t for t in tekis)


def test_tanlanganlar_SAVOL_MATNIDA_ham_korinadi():
    """Tugmalar ekranga sig'masa ham menejer nima tanlaganini bilsin."""
    shakl = _uskuna_savoligacha()
    shakl.javob_ber("filtr")
    shakl.javob_ber("sovutgich")

    matn = kp_oqim._savol_matni(shakl)

    assert "Tanlandi:" in matn
    assert "Filtr" in matn and "Sovutgich" in matn


def test_bosim_TUGMADA_korsatiladi():
    """Menejer qaysi qism qancha bosim qo'shishini tugmada ko'rsin."""
    shakl = _uskuna_savoligacha()

    tekis = [t.text for q in kp_oqim._tugmalar(shakl).inline_keyboard for t in q]

    assert any("+200 Pa" in t for t in tekis)


def test_uskuna_savolida_ROYXAT_TAKRORLANMAYDI():
    """Izohlar tugmalarda — ostida yana ro'yxat bo'lsa xabar ikki barobar."""
    shakl = _uskuna_savoligacha()

    matn = kp_oqim._savol_matni(shakl)

    assert "• Filtr" not in matn


def test_TAYYOR_tugmasida_belgi_BOSHQACHA():
    """«✅ Tayyor» bo'lsa, u ham tanlangandek ko'rinardi."""
    shakl = _uskuna_savoligacha()

    tekis = [t.text for q in kp_oqim._tugmalar(shakl).inline_keyboard for t in q]
    tayyor = next(t for t in tekis if "Tayyor" in t)

    assert not tayyor.startswith("✅")


@pytest.mark.asyncio
async def test_uskuna_bosilganda_YANGI_XABAR_chiqmaydi(baza):
    """Savol O'SHA xabarda qoladi — ekran to'lib ketmasin."""
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    for javob in ("Sinov MChJ", YO_L_OBYEKT, "350 kv, 6 m",
                  "ishlab_chiqarish", "20", "yoq", "ikkalasi", "yoq", "40"):
        await kp_oqim.javob(baza, xabar, 111, javob)

    oldingi = len(xabar.matnlar)
    soro = SoxtaSoro(f"{kp_oqim.TUGMA_OLDI}uskuna:filtr", xabar)
    await kp_oqim.tugma(baza, soro, 111)

    assert len(xabar.matnlar) == oldingi, "yangi xabar yuborildi"
    assert soro.tahrirlar, "mavjud xabar yangilanmadi"
    javoblar = (await baza.kp_shakli(111))["javoblar"]
    assert javoblar["uskunalar"] == ["filtr"]


@pytest.mark.asyncio
async def test_ORQAGA_tugmasi_ishlaydi(baza):
    """Menejer xato tugma bossa — `/bekor` qilib boshidan boshlamasin."""
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    await kp_oqim.javob(baza, xabar, 111, "Sinov MChJ")
    await kp_oqim.javob(baza, xabar, 111, YO_L_OBYEKT)

    soro = SoxtaSoro(f"{kp_oqim.TUGMA_OLDI}olcham:{kp_oqim.ORQAGA}", xabar)
    await kp_oqim.tugma(baza, soro, 111)

    javoblar = (await baza.kp_shakli(111))["javoblar"]
    assert "yol" not in javoblar
    assert soro.tahrirlar, "savol qayta chizilmadi"


def test_ORQAGA_tugmasi_KORINADI():
    shakl = Shakl()
    shakl.javob_ber("Sinov MChJ")

    tekis = [t.text for q in kp_oqim._tugmalar(shakl).inline_keyboard for t in q]

    assert any("Orqaga" in t for t in tekis)


def test_BIRINCHI_savolda_orqaga_YOQ():
    """Qaytadigan joy yo'q — tugma ham bo'lmasin."""
    tekis = [t.text for q in kp_oqim._tugmalar(Shakl()).inline_keyboard for t in q]

    assert not any("Orqaga" in t for t in tekis)


@pytest.mark.asyncio
async def test_orqaga_qaytadigan_joy_yoq_bolsa_OGOHLANTIRADI(baza):
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)

    soro = SoxtaSoro(f"{kp_oqim.TUGMA_OLDI}mijoz:{kp_oqim.ORQAGA}", xabar)
    await kp_oqim.tugma(baza, soro, 111)

    assert soro.ogohlantirishlar


@pytest.mark.asyncio
async def test_kp_boshlanishida_TZ_haqida_aytiladi(baza):
    """Menejer fayl tashlash mumkinligini bilmasa, imkoniyat ishlatilmaydi."""
    xabar = SoxtaXabar()

    await kp_oqim.boshla(baza, xabar, 111)

    assert "texnik topshiriq" in xabar.matnlar[0].lower()
    assert "Word" in xabar.matnlar[0]


@pytest.mark.asyncio
async def test_TZ_kech_tashlansa_NIMA_TUSHIB_QOLGANI_aytiladi(baza, _tz_soxta):
    """Qo'lda berilgan javob TZ nikidan ustun — menejer buni bilsin."""
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)
    await kp_oqim.javob(baza, xabar, 111, "Boshqa MChJ")      # mijoz qo'lda

    await kp_oqim.hujjat(baza, xabar, 111, SoxtaFayl("..."), "tz.txt")

    hammasi = " ".join(xabar.matnlar)
    assert "OLINMADI" in hammasi
    assert "mijoz nomi" in hammasi


def test_GEMINI_kvota_xatosi_TUSHUNARLI():
    """Kvota tugasa menejer xom xato matnini emas, ko'rsatmani ko'rsin.

    Tizim Gemini'ni ham ishlatadi (router, TZ o'qish), shuning uchun
    uning xatolari ham tarjima qilinishi kerak.
    """
    from app.llm import llm_xato_matni

    class Xato(Exception):
        status_code = 429

    matn = llm_xato_matni(Xato("429 RESOURCE_EXHAUSTED: Quota exceeded"))

    assert "limit" in matn.lower()
    assert "/kp" in matn, "menejer nima qilishini bilmaydi"


def test_gemini_kalit_xatosi_TUSHUNARLI():
    from app.llm import llm_xato_matni

    matn = llm_xato_matni(Exception("API key not valid. Please pass a valid API key."))

    assert "GEMINI_API_KEY" in matn


@pytest.mark.asyncio
async def test_TZ_tahlil_xatosi_KP_ni_toxtatmaydi(baza, monkeypatch):
    """LLM yiqilsa ham menejer KP ni qo'lda tuza olsin."""
    async def yiqiladi(matn, turlar):
        raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")

    monkeypatch.setattr(kp_oqim, "_tz_ajrat", yiqiladi)
    xabar = SoxtaXabar()
    await kp_oqim.boshla(baza, xabar, 111)

    await kp_oqim.hujjat(baza, xabar, 111, SoxtaFayl("TZ matni"), "tz.txt")

    assert "limit" in xabar.oxirgi.lower()
    assert "qo'lda javob bering" in xabar.oxirgi
    assert await kp_oqim.faolmi(baza, 111), "shakl yopilib qoldi"


# --- Xulosa qatorlari ---------------------------------------------------------
#
# JONLI E'TIROZ (2026-08-27): 3 xonali TZ dan chiqqan KP xulosasida
# "РВН 1000х1000 · 8 dona" va "РВН 1000х1000 · 3 dona" ketma-ket turardi.
# Bular banket zali va oshxonaning panjaralari, lekin xulosada farq
# ko'rinmasdi va menejer buni takror deb o'qirdi. Hujjatda farq bor edi
# (xona nomi `spetsifikatsiya` ustunida), xulosada esa yo'q.


def test_xulosa_qatorida_XONA_NOMI_korinadi():
    from kp.model import Qator
    from bot.kp_oqim import _qator_belgisi

    q = Qator(
        nomi="РВН 1000х1000",
        spetsifikatsiya="Банкетный зал — havo taqsimlash panjarasi, "
                        "jonli kesim 0.51 m², tezlik 2.0 m/s",
        miqdor=8.0, birlik="dona",
    )

    assert _qator_belgisi(q) == "РВН 1000х1000 (Банкетный зал)"


def test_xona_nomi_yoq_bolsa_faqat_nom():
    from kp.model import Qator
    from bot.kp_oqim import _qator_belgisi

    q = Qator(nomi="КЦКП-40", spetsifikatsiya="markaziy havo tayyorlash qurilmasi",
              miqdor=1.0, birlik="dona")

    assert _qator_belgisi(q) == "КЦКП-40"


def test_uzun_bolak_xona_nomi_deb_QABUL_QILINMAYDI():
    """Ajratgich spetsifikatsiya ichida ham uchrashi mumkin."""
    from kp.model import Qator
    from bot.kp_oqim import _qator_belgisi

    q = Qator(
        nomi="ВЦ 4-75",
        spetsifikatsiya="juda uzun texnik tavsif " * 4 + " — qolgani",
        miqdor=1.0, birlik="dona",
    )

    assert _qator_belgisi(q) == "ВЦ 4-75"


def test_bir_xil_panjara_ikki_xonada_FARQLANADI():
    from kp.model import Qator
    from bot.kp_oqim import _qator_belgisi

    zal = Qator(nomi="РВН 1000х1000", spetsifikatsiya="Банкетный зал — panjara",
                miqdor=8.0, birlik="dona")
    oshxona = Qator(nomi="РВН 1000х1000", spetsifikatsiya="Кухня — panjara",
                    miqdor=3.0, birlik="dona")

    assert _qator_belgisi(zal) != _qator_belgisi(oshxona)


# --- Aniqlik savolining yopiq halqasi -----------------------------------------
#
# JONLI XATO (2026-08-28): 120 000 m³/soat ga mos КЦКП topilmaganda
# savol shunday chiqardi:
#
#   «Model nomini o'zingiz ko'rsatasizmi YOKI TARQOQ TIZIMGA
#    O'TAMIZMI? … Model nomini yozing yoki /bekor»
#
# Ya'ni ikkita yo'l taklif qilinardi, lekin faqat BITTASI qabul
# qilinardi. Menejer «tarqoq» deb yozdi — o'sha savol qayta chiqdi.
# Chiqish yo'li yo'q edi.


def test_KCKP_topilmasa_TUGMA_beriladi():
    from hisob import markaziy_tanla
    from kp.shakldan import TARQOQQA_OT, _markaziy_kp

    # Markaziy qurilma topilmaydigan sarf.
    assert markaziy_tanla({}, 120000.0) is None

    from kp.narx import narxlar, rekvizitlar

    natija = _markaziy_kp(
        javoblar={"markaziy": "ha", "mijoz": "S"},
        hisob={"sarf": 120000.0, "diametr": 1000},
        parametrlar={}, katalog=[], kurs=12000.0,
        royxat=narxlar(), rekvizit=dict(rekvizitlar()),
        til="uz", raqam="S", ogohlantirishlar=[],
    )

    assert natija.aniqlik is not None
    assert natija.aniqlik.tanlovlar
    assert natija.aniqlik.tanlovlar[0]["qiymat"] == TARQOQQA_OT


def test_savol_matnida_ENDI_ikkinchi_yol_vada_qilinmaydi():
    """Tugma bo'lmasa, savol ham ikkinchi yo'lni va'da qilmasin."""
    from kp.narx import narxlar, rekvizitlar
    from kp.shakldan import _markaziy_kp

    natija = _markaziy_kp(
        javoblar={"markaziy": "ha", "mijoz": "S"},
        hisob={"sarf": 120000.0, "diametr": 1000},
        parametrlar={}, katalog=[], kurs=12000.0,
        royxat=narxlar(), rekvizit=dict(rekvizitlar()),
        til="uz", raqam="S", ogohlantirishlar=[],
    )

    # Savol endi faqat FAKTNI aytadi, tanlov tugmada.
    assert "o'tamizmi" not in natija.aniqlik.savol


@pytest.mark.parametrize("yozilgan", [
    "tarqoq", "Tarqoq", "ТАРҚОҚ", "tarqoq tizim", "раздельная",
])
def test_tarqoq_deb_YOZILSA_ham_qabul_qilinadi(yozilgan):
    """Menejer tugma o'rniga yozishi mumkin."""
    from bot.kp_oqim import TARQOQ_SOZLARI

    assert yozilgan.lower() in TARQOQ_SOZLARI


def test_aniqlik_callback_TELEGRAM_chegarasiga_sigadi():
    from bot.kp_oqim import TUGMA_OLDI
    from kp.shakldan import TARQOQQA_OT

    malumot = f"{TUGMA_OLDI}aniqlik:{TARQOQQA_OT}"

    assert len(malumot.encode("utf-8")) <= 64


# --- Aniqlik savolida ogohlantirishlar ----------------------------------------
#
# JONLI E'TIROZ (2026-08-28): 120 000 m³/soat da hisobiy diametr
# 2555 mm va tezlik 42 m/s edi — tarmoq bir necha kanalga bo'linishi
# kerak. Menejer esa faqat «kanal Ø1000 mm» ni ko'rib qaror qabul
# qilardi: ogohlantirishlar KP TUZILGANDAN KEYIN chiqardi.
#
# Qaror aniqlik savolida qabul qilinadi — ma'lumot ham shu yerda
# bo'lishi kerak.


class _YigMoq:
    """Yuborilgan xabarlarni to'playdi."""

    def __init__(self):
        self.matnlar: list[str] = []
        self.tugmalar = None

    async def reply_text(self, matn, reply_markup=None, **k):
        self.matnlar.append(matn)
        if reply_markup is not None:
            self.tugmalar = reply_markup
        return self


class _SoxtaBaza:
    async def kp_shakli_yoz(self, *a, **k):
        pass


def _natija_ogohlantirish_bilan(ogohlantirishlar):
    from kp.narx import narxlar, rekvizitlar
    from kp.shakldan import _markaziy_kp

    return _markaziy_kp(
        javoblar={"markaziy": "ha", "mijoz": "S"},
        hisob={"sarf": 120000.0, "diametr": 1000},
        parametrlar={}, katalog=[], kurs=12000.0,
        royxat=narxlar(), rekvizit=dict(rekvizitlar()),
        til="uz", raqam="S", ogohlantirishlar=list(ogohlantirishlar),
    )


@pytest.mark.asyncio
async def test_aniqlik_savolida_OGOHLANTIRISH_korinadi():
    from bot.kp_oqim import _aniqlik_sorash
    from kp.shakl import Shakl

    natija = _natija_ogohlantirish_bilan([
        "magistral kanal: tezlik 42.4 m/s — tavsiya chegarasidan yuqori"])
    xabar = _YigMoq()

    await _aniqlik_sorash(_SoxtaBaza(), xabar, 1, Shakl(javoblar={}), natija)

    assert "42.4 m/s" in xabar.matnlar[0]


@pytest.mark.asyncio
async def test_ogohlantirishsiz_savol_TOZA_qoladi():
    from bot.kp_oqim import _aniqlik_sorash
    from kp.shakl import Shakl

    xabar = _YigMoq()

    await _aniqlik_sorash(_SoxtaBaza(), xabar, 1, Shakl(javoblar={}),
                          _natija_ogohlantirish_bilan([]))

    assert "⚠️" not in xabar.matnlar[0]


@pytest.mark.asyncio
async def test_KOP_ogohlantirish_savolni_KOMIB_yubormaydi():
    """Hammasi chiqarilsa menejer tugmani topmasdi."""
    from bot.kp_oqim import ANIQLIK_OGOH_SONI, _aniqlik_sorash
    from kp.shakl import Shakl

    natija = _natija_ogohlantirish_bilan([f"ogohlantirish {i}" for i in range(12)])
    xabar = _YigMoq()

    await _aniqlik_sorash(_SoxtaBaza(), xabar, 1, Shakl(javoblar={}), natija)

    matn = xabar.matnlar[0]
    assert matn.count("⚠️") <= ANIQLIK_OGOH_SONI
    assert "va yana" in matn


@pytest.mark.asyncio
async def test_ogohlantirish_bilan_ham_TUGMA_qoladi():
    """Ogohlantirishlar tugmani siqib chiqarmasin."""
    from bot.kp_oqim import _aniqlik_sorash
    from kp.shakl import Shakl

    natija = _natija_ogohlantirish_bilan([f"ogoh {i}" for i in range(8)])
    xabar = _YigMoq()

    await _aniqlik_sorash(_SoxtaBaza(), xabar, 1, Shakl(javoblar={}), natija)

    assert xabar.tugmalar is not None
