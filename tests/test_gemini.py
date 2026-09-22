"""Gemini adapteri — Anthropic shakli bilan Gemini shakli orasidagi tarjima.

Bu qatlamning butun ma'nosi: agentlar va router O'ZGARMAYDI. Ular so'rovni
Anthropic shaklida quradi, javobni ham o'sha shaklda o'qiydi. Shuning uchun
testlar aynan CHEGARANI tekshiradi — tarjima to'g'ri bo'lmasa, xato jimgina
yuzaga chiqadi: agent "javobni o'qib bo'lmadi" deydi va sabab ko'rinmaydi.

Tarmoqqa CHIQILMAYDI.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from app.gemini import (
    javobni_ogir,
    sorovni_ogir,
    sxemani_ogir,
)
from app.llm import matn_yig, provayder
from app.sxema import qatiy_sxema

# --- provayderni nomdan aniqlash ----------------------------------------------


@pytest.mark.parametrize("model,kutilgan", [
    ("gemini-3.5-flash", "gemini"),
    ("Gemini-3.7-Flash", "gemini"),
    ("claude-sonnet-4-6", "anthropic"),
    ("claude-haiku-4-5", "anthropic"),
    ("", "anthropic"),
])
def test_provayder_nomdan_aniqlanadi(model, kutilgan):
    assert provayder(model) == kutilgan


# --- sxema tarjimasi ----------------------------------------------------------


class Ichki(BaseModel):
    nomi: str
    soni: int


class Tashqi(BaseModel):
    sarlavha: str
    ichkilar: list[Ichki] = Field(default_factory=list)
    izoh: str | None = None


def test_ref_va_defs_joyiga_qoyiladi():
    """Gemini `$ref` ni tushunmaydi — sxema 400 bilan rad etiladi."""
    natija = sxemani_ogir(qatiy_sxema(Tashqi))

    matn = str(natija)
    assert "$ref" not in matn
    assert "$defs" not in matn
    # Ichki modelning maydonlari joyiga qo'yilgan bo'lishi kerak.
    ichki = natija["properties"]["ichkilar"]["items"]
    assert set(ichki["properties"]) == {"nomi", "soni"}


def test_additional_properties_tashlanadi():
    """Anthropic talab qiladi, Gemini rad etadi."""
    assert "additionalProperties" not in str(sxemani_ogir(qatiy_sxema(Tashqi)))


def test_ixtiyoriy_maydon_nullable_boladi():
    """`str | None` -> pydantic `anyOf` beradi, Gemini `nullable` kutadi."""
    natija = sxemani_ogir(qatiy_sxema(Tashqi))
    izoh = natija["properties"]["izoh"]

    assert izoh["type"] == "string"
    assert izoh["nullable"] is True
    assert "anyOf" not in izoh


def test_maydonlar_tartibi_beriladi():
    """`propertyOrdering` javobni barqarorroq qiladi."""
    natija = sxemani_ogir(qatiy_sxema(Tashqi))

    assert natija["propertyOrdering"] == ["sarlavha", "ichkilar", "izoh"]


def test_haqiqiy_agent_sxemasi_tarjima_qilinadi():
    """Sardorning sxemasi eng murakkabi — ichma-ich ro'yxatlar bilan."""
    from app.agentlar.mahsulot_mutaxassisi import TanlovNatija

    natija = sxemani_ogir(qatiy_sxema(TanlovNatija))

    assert "$ref" not in str(natija)
    variant = natija["properties"]["variantlar"]["items"]
    assert "moslik_darajasi" in variant["properties"]


# --- so'rov tarjimasi ---------------------------------------------------------


def test_system_bloklari_yigiladi():
    """Anthropic `system` ro'yxat bo'lishi mumkin, Gemini bitta matn kutadi."""
    tana = sorovni_ogir({
        "system": [
            {"type": "text", "text": "Sen muhandissan.",
             "cache_control": {"type": "ephemeral"}},
        ],
        "messages": [{"role": "user", "content": "Salom"}],
    })

    assert tana["systemInstruction"]["parts"][0]["text"] == "Sen muhandissan."
    assert tana["contents"][0]["parts"][0]["text"] == "Salom"


def test_assistant_roli_model_ga_ogiriladi():
    """Gemini'da javob roli "assistant" emas, "model"."""
    tana = sorovni_ogir({
        "messages": [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ],
    })

    assert [x["role"] for x in tana["contents"]] == ["user", "model"]


def test_rasm_inline_data_ga_ogiriladi():
    tana = sorovni_ogir({
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": "image/png", "data": "QUJD"}},
            {"type": "text", "text": "Nima bu?"},
        ]}],
    })

    qismlar = tana["contents"][0]["parts"]
    assert qismlar[0]["inline_data"] == {"mime_type": "image/png", "data": "QUJD"}
    assert qismlar[1]["text"] == "Nima bu?"


def test_json_format_response_schema_ga_otadi():
    tana = sorovni_ogir({
        "messages": [{"role": "user", "content": "x"}],
        "max_tokens": 1234,
        "output_config": {
            "effort": "low",
            "format": {"type": "json_schema", "schema": qatiy_sxema(Ichki)},
        },
    })

    konfig = tana["generationConfig"]
    assert konfig["responseMimeType"] == "application/json"
    assert konfig["maxOutputTokens"] == 1234
    assert set(konfig["responseSchema"]["properties"]) == {"nomi", "soni"}


def test_effort_tashlanadi():
    """`effort` — Anthropic'ga xos. Yuborilsa Gemini so'rovni rad etardi."""
    tana = sorovni_ogir({
        "messages": [{"role": "user", "content": "x"}],
        "output_config": {"effort": "high"},
    })

    assert "effort" not in str(tana)


# --- javob tarjimasi ----------------------------------------------------------


def _gemini_javobi(matn: str, tugash: str = "STOP") -> dict:
    return {
        "candidates": [{
            "content": {"parts": [{"text": matn}]},
            "finishReason": tugash,
        }],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
    }


def test_matn_agentlar_kutgan_shaklda_qaytadi():
    """`matn_yig()` — agentlar javobni AYNAN shu funksiya bilan o'qiydi."""
    javob = javobni_ogir(_gemini_javobi('{"nomi": "test"}'), "gemini-3.5-flash")

    assert matn_yig(javob) == '{"nomi": "test"}'
    assert javob.usage.input_tokens == 10
    assert javob.usage.output_tokens == 20


@pytest.mark.parametrize("gemini,anthropic_nomi", [
    ("STOP", "end_turn"),
    ("MAX_TOKENS", "max_tokens"),
    ("SAFETY", "refusal"),
    ("PROHIBITED_CONTENT", "refusal"),
    ("NOMALUM", "end_turn"),
])
def test_tugash_sababi_ogiriladi(gemini, anthropic_nomi):
    """Router aynan `refusal` qiymatiga qarab "model rad etdi" deydi."""
    javob = javobni_ogir(_gemini_javobi("x", gemini), "m")

    assert javob.stop_reason == anthropic_nomi


def test_sorov_toliq_tosilsa_refusal():
    """Nomzod umuman qaytmasa — so'rovning o'zi to'silgan."""
    javob = javobni_ogir({"promptFeedback": {"blockReason": "SAFETY"}}, "m")

    assert javob.stop_reason == "refusal"
    assert matn_yig(javob) == ""


def test_pause_turn_hech_qachon_chiqmaydi():
    """`pause_turn` — Anthropic server-vositalariga xos.

    `asos.py` uni ko'rsa so'rovni QAYTA yuboradi. Gemini'dan bunday
    qiymat kelmasligi kerak, aks holda cheksiz tsikl bo'lardi.
    """
    for sabab in ("STOP", "MAX_TOKENS", "SAFETY", "OTHER", ""):
        assert javobni_ogir(_gemini_javobi("x", sabab), "m").stop_reason != "pause_turn"
