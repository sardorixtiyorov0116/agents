"""Anthropic API xatolari tushunarli matnga aylantiriladi.

Xom xato menejerga hech narsa aytmaydi:

    API xatosi: Error code: 401 - {'type': 'error', 'error': {...}}

Kerak bo'lgani — sabab va yechim: "kalit yaroqsiz, .env da yangilang".

DIQQAT: xato TURI o'zgarmaydi, faqat MATN tarjima qilinadi. `asos.py`
structured-output rad etilganini `BadRequestError` matnidan biladi —
xatoni boshqa turga o'rasak, o'sha zaxira yo'l buzilardi.
"""

from __future__ import annotations

import anthropic
import httpx
import pytest

from app.llm import XATO_IZOHLARI, AnthropicLlm, llm_xato_matni


def _status_xatosi(kod: int, matn: str = "") -> anthropic.APIStatusError:
    javob = httpx.Response(
        status_code=kod,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        json={"type": "error", "error": {"type": "test", "message": matn}},
    )
    return anthropic.APIStatusError(matn or f"HTTP {kod}", response=javob, body=None)


class SoxtaMijoz:
    """`messages.create` chaqirilganda berilgan xatoni tashlaydi."""

    def __init__(self, xato: Exception):
        self._xato = xato
        self.messages = self

    async def create(self, **_):
        raise self._xato


@pytest.mark.parametrize("kod", sorted(XATO_IZOHLARI))
def test_har_bir_kod_ozbekcha_izoh_beradi(kod: int):
    matn = llm_xato_matni(_status_xatosi(kod))
    assert matn == XATO_IZOHLARI[kod]
    assert "Error code" not in matn      # xom JSON chiqmasin
    assert "{" not in matn


def test_kalit_yaroqsiz_bolsa_nima_qilish_aytiladi():
    """Aynan shu holat ishlab turgan tizimni to'xtatgan edi."""
    matn = llm_xato_matni(_status_xatosi(401))
    assert "ANTHROPIC_API_KEY" in matn
    assert ".env" in matn


def test_mablag_tugasa_alohida_aytiladi():
    """400 kodi umumiy — sababi xabar matnidan ajratiladi."""
    matn = llm_xato_matni(_status_xatosi(400, "Your credit balance is too low"))
    assert "mablag'" in matn


def test_notanish_kod_ham_xom_json_chiqarmaydi():
    matn = llm_xato_matni(_status_xatosi(418))
    assert "418" in matn
    assert "{" not in matn


def test_ulanish_uzilsa_internet_haqida_aytiladi():
    xato = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    assert "internet" in llm_xato_matni(xato).lower()


@pytest.mark.asyncio
async def test_javob_xato_turini_ozgartirmaydi():
    """Agentlar `except anthropic.APIError` bilan ushlaydi — tur saqlanadi."""
    llm = AnthropicLlm(mijoz=SoxtaMijoz(_status_xatosi(401)), model="test")
    with pytest.raises(anthropic.APIStatusError):
        await llm.javob(messages=[{"role": "user", "content": "salom"}])


@pytest.mark.asyncio
async def test_tekshir_ishlaydigan_kalitda_none_qaytaradi():
    class Ok:
        def __init__(self):
            self.messages = self

        async def create(self, **_):
            return object()

    assert await AnthropicLlm(mijoz=Ok(), model="test").tekshir() is None


@pytest.mark.asyncio
async def test_tekshir_yaroqsiz_kalitda_sababni_qaytaradi():
    llm = AnthropicLlm(mijoz=SoxtaMijoz(_status_xatosi(401)), model="test")
    sabab = await llm.tekshir()
    assert sabab and "ANTHROPIC_API_KEY" in sabab
