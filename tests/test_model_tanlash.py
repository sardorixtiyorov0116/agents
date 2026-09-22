"""Har agent o'z modelida ishlaydi.

NEGA KERAK: hamma agent bitta modelda ishlaganda yengil ish ham qimmat
modelga tushadi. Reja tuzuvchi 15 ta nomdan bittasini tanlaydi, Rustam
matndan raqam ajratadi — bunga arzon model yetarli.

Bu yerda ikkita nozik joy tekshiriladi:

  1. Model ALMASHDIMI — ro'yxatdagi rol tez modelga, qolgani umumiyga.
  2. `effort` OLIB TASHLANDIMI — Haiku 4.5 bu parametrni qabul qilmaydi
     va yuborilsa butun so'rov 400 bilan rad etiladi. Ya'ni bu tekshiruv
     bo'lmasa, tez modelga o'tgan agent umuman ishlamay qoladi.
"""

from __future__ import annotations

import pytest

from app.config import Sozlama
from app.llm import AnthropicLlm


class SoxtaMijoz:
    """`messages.create` ni yozib oladi va bo'sh javob qaytaradi."""

    def __init__(self) -> None:
        self.sorovlar: list[dict] = []
        self.messages = self

    async def create(self, **soro):
        self.sorovlar.append(soro)
        return type("Javob", (), {"content": [], "stop_reason": "end_turn"})()


# --- model almashtirish ------------------------------------------------------


def test_model_bilan_ulanishni_qayta_ishlatadi() -> None:
    """Yangi model — o'sha HTTP mijozi. Aks holda har so'rov qayta ulanardi."""
    mijoz = SoxtaMijoz()
    asl = AnthropicLlm(mijoz=mijoz, model="claude-sonnet-4-6")
    tez = asl.model_bilan("claude-haiku-4-5")

    assert tez.model == "claude-haiku-4-5"
    assert tez.mijoz is mijoz          # ulanish bo'linadi
    assert asl.model == "claude-sonnet-4-6"  # aslga tegilmadi


def test_bir_xil_model_yangi_nusxa_yasamaydi() -> None:
    asl = AnthropicLlm(mijoz=SoxtaMijoz(), model="claude-sonnet-4-6")
    assert asl.model_bilan("claude-sonnet-4-6") is asl
    assert asl.model_bilan("") is asl


# --- effort moslashuvi -------------------------------------------------------


@pytest.mark.asyncio
async def test_haiku_uchun_effort_olib_tashlanadi() -> None:
    """Haiku effortni tushunmaydi — u olib tashlanadi, format qoladi."""
    mijoz = SoxtaMijoz()
    llm = AnthropicLlm(mijoz=mijoz, model="claude-haiku-4-5")

    await llm.javob(
        messages=[{"role": "user", "content": "salom"}],
        output_config={"effort": "low", "format": {"type": "json_schema"}},
    )

    konfig = mijoz.sorovlar[0]["output_config"]
    assert "effort" not in konfig
    assert konfig["format"] == {"type": "json_schema"}


@pytest.mark.asyncio
async def test_effort_yolgiz_bolsa_output_config_umuman_yuborilmaydi() -> None:
    mijoz = SoxtaMijoz()
    llm = AnthropicLlm(mijoz=mijoz, model="claude-haiku-4-5")

    await llm.javob(
        messages=[{"role": "user", "content": "salom"}],
        output_config={"effort": "medium"},
    )

    assert "output_config" not in mijoz.sorovlar[0]


@pytest.mark.asyncio
async def test_sonnetda_effort_saqlanadi() -> None:
    mijoz = SoxtaMijoz()
    llm = AnthropicLlm(mijoz=mijoz, model="claude-sonnet-4-6")

    await llm.javob(
        messages=[{"role": "user", "content": "salom"}],
        output_config={"effort": "medium"},
    )

    assert mijoz.sorovlar[0]["output_config"]["effort"] == "medium"


@pytest.mark.asyncio
async def test_chaqiruvchining_lugati_ozgartirilmaydi() -> None:
    """So'rov lug'ati qayta ishlatilishi mumkin — unga tegilmasligi kerak."""
    mijoz = SoxtaMijoz()
    llm = AnthropicLlm(mijoz=mijoz, model="claude-haiku-4-5")
    konfig = {"effort": "low", "format": {"type": "json_schema"}}

    await llm.javob(messages=[], output_config=konfig)

    assert konfig["effort"] == "low"   # asl lug'at butun


# --- sozlama -----------------------------------------------------------------


def test_tez_rollar_royxati_oqiladi() -> None:
    s = Sozlama(tez_model="claude-haiku-4-5", tez_rollar_royxati="router, kp-tracker")
    assert s.tez_rollar == {"router", "kp-tracker"}


def test_hisob_agenti_tez_modelga_otmaydi() -> None:
    """Rustam standart ro'yxatda BO'LMASLIGI kerak.

    2026-08-17 da o'lchandi: Haiku restoranni "dokon" deb tanlab, havo
    sarfini 2.5 barobar kam chiqardi. Bu test uni beixtiyor qaytarib
    qo'yishdan saqlaydi — o'lchamasdan qo'shilsa, sinov qizil bo'ladi.
    """
    assert "hvac-calc" not in Sozlama().tez_rollar


def test_tez_model_bosh_bolsa_hech_kim_otmaydi() -> None:
    """Ro'yxatda nom qolib ketsa ham, model yo'q bo'lsa hech kim o'tmaydi."""
    s = Sozlama(tez_model="", tez_rollar_royxati="router,hvac-calc")
    assert s.tez_rollar == set()


# --- orkestrning haqiqiy yo'li ----------------------------------------------
#
# 2026-08-19: botda `NameError: llm_yasa is not defined` chiqdi.
# Sabab: `app/orkestr.py` da import qatoriga `llm_yasa` qo'shilmagan edi.
#
# Nega mavjud testlar tutmagan: `_llm_uchun` soxta LLM ni O'ZGARTIRMASDAN
# qaytaradi (`isinstance(self.llm, AnthropicLlm)` tekshiruvi), shuning
# uchun muammoli qator testlarda HECH QACHON bajarilmasdi. U faqat
# haqiqiy Anthropic mijozi bilan ishga tushardi — ya'ni ishlab
# chiqarishda. Quyidagi test aynan shu yo'lni yuradi.


@pytest.mark.asyncio
async def test_orkestr_tez_modelga_HAQIQIY_llm_bilan_otadi(monkeypatch, tmp_path) -> None:
    from app.baza import Baza
    from app.kontraktlar import kontraktlarni_yukla
    from app.orkestr import Orkestr

    s = Sozlama(anthropic_api_key="sinov", tez_model="claude-haiku-4-5",
                tez_rollar_royxati="router")
    monkeypatch.setattr("app.orkestr.sozlama", lambda: s)
    monkeypatch.setattr("app.llm.sozlama", lambda: s)

    baza = Baza(tmp_path / "sinov.db")
    await baza.tayyorla()
    haqiqiy = AnthropicLlm(mijoz=SoxtaMijoz(), model="claude-sonnet-4-6")
    orkestr = Orkestr(llm=haqiqiy, baza=baza, kontraktlar=kontraktlarni_yukla())

    tez = orkestr._llm_uchun("router")        # AYNAN shu qator yiqilardi
    boshqa = orkestr._llm_uchun("proposal-builder")

    assert tez.model == "claude-haiku-4-5"
    assert boshqa is haqiqiy
    # Ulanish qayta ishlatiladi — har so'rovda yangi HTTP mijozi ochilmaydi.
    assert tez.mijoz is haqiqiy.mijoz
