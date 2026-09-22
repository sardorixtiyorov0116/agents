"""Lokal model adapteri — zanjirning oxirgi halqasi.

Bu qatlam ham Gemini adapteri kabi TARJIMA qiladi: agentlar so'rovni
Anthropic shaklida quradi, javobni ham o'sha shaklda o'qiydi.

Eng muhimi — lokal modelning CHEKLOVLARI jimgina o'tib ketmasligi:
structured output yo'q, rasm yo'q. Ikkalasi ham ochiq xato bilan
rad etilishi kerak, aks holda agent noto'g'ri javob olardi.

Tarmoqqa CHIQILMAYDI.
"""

from __future__ import annotations

import anthropic
import pytest

from app.llm import matn_yig, provayder
from app.ollama import javobni_ogir, model_nomi, sorovni_ogir

# --- provayderni nomdan aniqlash ---------------------------------------------


@pytest.mark.parametrize("model,kutilgan", [
    ("ollama:qwen3:8b", "ollama"),
    ("OLLAMA:Qwen3:8B", "ollama"),
    ("gemini-3.5-flash", "gemini"),
    ("claude-sonnet-4-6", "anthropic"),
])
def test_provayder_nomdan_aniqlanadi(model, kutilgan):
    assert provayder(model) == kutilgan


def test_ollama_nomi_lokal_deb_sanalmaydi():
    """Ikki nuqta MAJBURIY.

    `ollama` so'zi model nomining ichida uchrashi mumkin (masalan
    bulutdagi "ollama-hosted-..."). Prefiks `ollama:` bo'lmasa lokalga
    yuborilmaydi — aks holda so'rov jimgina noto'g'ri joyga ketardi.
    """
    assert provayder("ollama-bulutdagi-model") == "anthropic"


@pytest.mark.parametrize("kirish,kutilgan", [
    ("ollama:qwen3:8b", "qwen3:8b"),
    ("qwen3:8b", "qwen3:8b"),
    ("OLLAMA:gemma3:4b", "gemma3:4b"),
])
def test_prefiks_olib_tashlanadi(kirish, kutilgan):
    assert model_nomi(kirish) == kutilgan


# --- so'rov tarjimasi ---------------------------------------------------------


def test_tizim_prompt_BLOKLARDAN_yigiladi():
    """`asos.py` system ni kesh bloklari ro'yxati qilib beradi."""
    tana = sorovni_ogir({
        "system": [{"type": "text", "text": "Sen Jasursan.",
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": "salom"}],
    })

    assert tana["messages"][0] == {"role": "system", "content": "Sen Jasursan."}
    assert tana["messages"][1] == {"role": "user", "content": "salom"}


def test_takrorlanishdan_himoya_QOYILADI():
    """O'LCHANDI: himoyasiz model bir jumlani aylantirib yozadi."""
    tana = sorovni_ogir({"messages": [{"role": "user", "content": "salom"}]})

    assert tana["options"]["repeat_penalty"] >= 1.1, "takror himoyasi yo'q"
    assert tana["options"]["temperature"] == 0


def test_oylash_bloki_OCHIRILADI():
    """Qwen3 `<think>` yozadi — u JSON ni o'rab qo'yadi."""
    tana = sorovni_ogir({"messages": [{"role": "user", "content": "salom"}]})
    assert tana["think"] is False


def test_rasmli_sorov_OCHIQ_rad_etiladi():
    """Jimgina matnni o'qib, rasmni ko'rmagandek javob berish battari."""
    with pytest.raises(anthropic.BadRequestError, match="rasm"):
        sorovni_ogir({
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": "image/png",
                                "data": "xxx"}},
                    {"type": "text", "text": "bu nima?"},
                ],
            }],
        })


# --- javob tarjimasi ----------------------------------------------------------


def test_javob_ANTHROPIC_shaklida_qaytadi():
    javob = javobni_ogir(
        {"message": {"content": "Rekuperator — issiqlik almashtirgich."},
         "prompt_eval_count": 40, "eval_count": 12, "done_reason": "stop"},
        "qwen3:8b",
    )

    assert matn_yig(javob) == "Rekuperator — issiqlik almashtirgich."
    assert javob.stop_reason == "end_turn"
    assert javob.usage.input_tokens == 40
    assert javob.usage.output_tokens == 12


def test_oylash_bloki_javobdan_KESILADI():
    """`think: false` bo'lsa ham ba'zi modellar baribir yozadi."""
    javob = javobni_ogir(
        {"message": {"content": "<think>hmm, o'ylayapman</think>\n{\"mos\": true}"}},
        "qwen3:8b",
    )

    assert matn_yig(javob) == '{"mos": true}'
    assert "o'ylayapman" not in matn_yig(javob)


def test_uzilgan_javob_MAX_TOKENS_deb_belgilanadi():
    """`asos.py` tugash sababiga qarab qaror qiladi."""
    javob = javobni_ogir(
        {"message": {"content": "yarim"}, "done_reason": "length"}, "qwen3:8b"
    )
    assert javob.stop_reason == "max_tokens"


def test_bosh_hisoblagich_YIQITMAYDI():
    """Ollama ba'zan token sonini qaytarmaydi."""
    javob = javobni_ogir({"message": {"content": "javob"}}, "qwen3:8b")
    assert javob.usage.input_tokens == 0
    assert javob.usage.output_tokens == 0


# --- structured output --------------------------------------------------------


@pytest.mark.asyncio
async def test_structured_output_400_bilan_rad_etiladi():
    """`asos.py` AYNAN "output_config" so'ziga qarab matn rejimiga o'tadi.

    Xabar o'zgarsa o'sha zaxira yo'l jimgina ishlamay qoladi va agent
    "javobni o'qib bo'lmadi" deydi.
    """
    from app.ollama import OllamaLlm

    llm = OllamaLlm(model="qwen3:8b")
    with pytest.raises(anthropic.BadRequestError) as xato:
        await llm.javob(
            output_config={"format": {"type": "object"}},
            messages=[{"role": "user", "content": "salom"}],
        )

    assert "output_config" in str(xato.value)


@pytest.mark.asyncio
async def test_zanjir_400_da_lokalga_OTMAYDI():
    """400 da zanjir keyingi modelga o'tmasligi kerak.

    Aks holda structured output rad etilganda so'rov lokal modelga
    tushib ketardi — sifat jimgina pasayardi.
    """
    from app.zanjir import otish_kerakmi

    xato = anthropic.BadRequestError(
        "output_config format qabul qilinmadi",
        response=_soxta_javob(400), body=None,
    )
    assert otish_kerakmi(xato) is False


def _soxta_javob(kod: int):
    import httpx

    return httpx.Response(kod, request=httpx.Request("POST", "http://x"))
