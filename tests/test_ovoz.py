"""Ovozli xabar — eshitish, gapirish va JIM QOLMASLIK.

Eng muhim qoida shu yerda qo'riqlanadi: mijoz ovoz yuborsa, bot
har qanday holatda JAVOB BERADI. Ilgari botda ovoz ishlovchisi umuman
yo'q edi — ovozli xabar hech qanday javobsiz qolardi.
"""

from __future__ import annotations

import base64
import struct
from types import SimpleNamespace

import httpx
import pytest

from app import ovoz


def javob_matn(matn: str, kirish: int = 331, chiqish: int = 36) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": matn}]}}],
        "usageMetadata": {"promptTokenCount": kirish,
                          "candidatesTokenCount": chiqish},
    }


def javob_audio(pcm: bytes) -> dict:
    return {
        "candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "audio/L16;rate=24000",
                            "data": base64.b64encode(pcm).decode()}}
        ]}}],
        "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 500},
    }


@pytest.fixture(autouse=True)
def kalit(monkeypatch):
    monkeypatch.setattr(ovoz, "sozlama",
                        lambda: SimpleNamespace(gemini_api_key="sinov-kalit"))


def ulash(monkeypatch, ishlov):
    """`app.ovoz` ichidagi httpx mijozini soxta transport bilan almashtiradi."""
    asl = httpx.AsyncClient

    def yasovchi(*a, **kw):
        kw["transport"] = httpx.MockTransport(ishlov)
        return asl(*a, **kw)

    monkeypatch.setattr(ovoz.httpx, "AsyncClient", yasovchi)


# --- eshitish -------------------------------------------------------------


async def test_ovoz_matnga_ogiriladi(monkeypatch):
    sorovlar = []

    def ishlov(s: httpx.Request) -> httpx.Response:
        sorovlar.append(s)
        return httpx.Response(200, json=javob_matn(
            "Menga 200 metr kvadrat ofis uchun ventilyatsiya kerak"))

    ulash(monkeypatch, ishlov)
    matn = await ovoz.matnga(b"soxta-ogg-baytlari")

    assert "200 metr kvadrat" in matn
    assert ovoz.ESHITISH_MODELI in str(sorovlar[0].url)


async def test_audio_base64_bolib_yuboriladi(monkeypatch):
    yuborilgan = {}

    def ishlov(s: httpx.Request) -> httpx.Response:
        import json
        yuborilgan.update(json.loads(s.content))
        return httpx.Response(200, json=javob_matn("salom"))

    ulash(monkeypatch, ishlov)
    await ovoz.matnga(b"ABC", mime="audio/ogg")

    qismlar = yuborilgan["contents"][0]["parts"]
    ichki = qismlar[1]["inline_data"]
    assert ichki["mime_type"] == "audio/ogg"
    assert base64.b64decode(ichki["data"]) == b"ABC"


async def test_bosh_javob_XATO_beriladi(monkeypatch):
    """Model matn qaytarmasa — jimgina bo'sh satr emas, xato.

    Bo'sh satr qaytsa, bot uni savol deb `sorov` ga uzatardi va mijoz
    tushunarsiz javob olardi.
    """
    ulash(monkeypatch, lambda s: httpx.Response(200, json=javob_matn("")))
    with pytest.raises(ovoz.OvozXatosi):
        await ovoz.matnga(b"ovoz")


async def test_bosh_fayl_rad_etiladi():
    with pytest.raises(ovoz.OvozXatosi):
        await ovoz.matnga(b"")


async def test_juda_katta_fayl_rad_etiladi():
    with pytest.raises(ovoz.OvozXatosi):
        await ovoz.matnga(b"x" * (ovoz.MAKS_BAYT + 1))


async def test_http_xatosi_yutilmaydi(monkeypatch):
    ulash(monkeypatch, lambda s: httpx.Response(429, text="quota exceeded"))
    with pytest.raises(ovoz.OvozXatosi) as x:
        await ovoz.matnga(b"ovoz")
    assert "429" in str(x.value)


async def test_kalitsiz_ochiq_xato(monkeypatch):
    monkeypatch.setattr(ovoz, "sozlama",
                        lambda: SimpleNamespace(gemini_api_key=""))
    with pytest.raises(ovoz.OvozXatosi) as x:
        await ovoz.matnga(b"ovoz")
    assert "kalit" in str(x.value).lower()


# --- gapirish -------------------------------------------------------------


async def test_matndan_ovoz_yasaladi(monkeypatch):
    pcm = b"\x01\x02" * 100
    ulash(monkeypatch, lambda s: httpx.Response(200, json=javob_audio(pcm)))
    wav = await ovoz.ovozga("Salom, narxi 12 million so'm")

    assert wav.startswith(b"RIFF") and b"WAVE" in wav[:16]
    assert wav.endswith(pcm)


async def test_wav_sarlavhasi_togri():
    """Telegram noto'g'ri sarlavhali faylni o'ynatmaydi."""
    pcm = b"\x00" * 480
    wav = ovoz._wav(pcm)
    kanal, chastota = struct.unpack("<HI", wav[22:28])
    assert kanal == 1
    assert chastota == ovoz.PCM_CHASTOTA
    assert struct.unpack("<I", wav[40:44])[0] == len(pcm)


async def test_ovozsiz_javob_XATO(monkeypatch):
    ulash(monkeypatch, lambda s: httpx.Response(200, json=javob_matn("matn")))
    with pytest.raises(ovoz.OvozXatosi):
        await ovoz.ovozga("salom")


async def test_bosh_matndan_ovoz_yasalmaydi():
    with pytest.raises(ovoz.OvozXatosi):
        await ovoz.ovozga("   ")


# --- sarf hisobi ----------------------------------------------------------


async def test_sarf_qayd_etiladi(monkeypatch):
    yozuvlar = []

    async def yozuvchi(yozuv):
        yozuvlar.append(yozuv)

    from app import sarf
    sarf.yozuvchini_ol(yozuvchi)
    try:
        ulash(monkeypatch, lambda s: httpx.Response(
            200, json=javob_matn("salom", kirish=331, chiqish=36)))
        await ovoz.matnga(b"ovoz")
    finally:
        sarf.yozuvchini_ol(None)

    assert yozuvlar, "ovoz chaqiruvi sarf hisobiga tushmadi"
    assert yozuvlar[-1]["kirish"] == 331
    assert yozuvlar[-1]["chiqish"] == 36
    assert yozuvlar[-1]["provayder"] == "gemini"


# --- gapirish uchun matn tayyorlash ---------------------------------------


def test_markdown_belgilar_olib_tashlanadi():
    """`**`, `*`, `#` ovozda «yulduzcha», «panjara» bo'lib eshitiladi."""
    assert ovoz.gapirish_uchun("**Salom!** *Narxi* 12 mln") == "Salom! Narxi 12 mln"


def test_havola_oqilmaydi():
    q = ovoz.gapirish_uchun("Batafsil https://climavent.uz/katalog sahifada")
    assert "http" not in q and "climavent" not in q


def test_ajratgich_chiziq_olib_tashlanadi():
    assert "—" not in ovoz.gapirish_uchun("Javob\n\n— — —\nIzoh")


def test_tinish_belgisidan_oldingi_boshliq_yoqoladi():
    assert ovoz.gapirish_uchun("Narxi *12 mln*.") == "Narxi 12 mln."


def test_uzun_javob_GAP_OXIRIDA_kesiladi():
    uzun = "Bu gap. " * 200
    q = ovoz.gapirish_uchun(uzun)
    assert len(q) <= ovoz.GAPIRISH_CHEGARASI
    assert q.endswith("."), "yarim gapda kesilgan"


def test_qisqa_javob_ozgarmaydi():
    assert ovoz.gapirish_uchun("Salom") == "Salom"


def test_bosh_matn_bosh_qaytadi():
    assert ovoz.gapirish_uchun("") == ""
    assert ovoz.gapirish_uchun("   ") == ""


def test_yorliqli_havola_butunlay_olib_tashlanadi():
    """«Batafsil: https://…» — yorliq ham ketadi, osilib qolmaydi."""
    q = ovoz.gapirish_uchun("Narxi 12 mln. Batafsil: https://climavent.uz/a")
    assert "Batafsil" not in q
    assert q == "Narxi 12 mln."
