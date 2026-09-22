"""Structured output uchun JSON Schema yordamchisi.

Anthropic API'ning `output_config.format` maydoni qat'iy sxema talab qiladi:
har obyektda `additionalProperties: false` va barcha maydonlar `required`.
Bundan tashqari ayrim kalit so'zlar qo'llab-quvvatlanmaydi — ularni olib
tashlaymiz.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# Structured outputs qo'llab-quvvatlamaydigan (yoki keraksiz) kalitlar.
TASHLANADIGAN = frozenset(
    {
        "title",
        "default",
        "examples",
        "format",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
)


def _tozala(tugun: Any) -> Any:
    if isinstance(tugun, list):
        return [_tozala(x) for x in tugun]
    if not isinstance(tugun, dict):
        return tugun

    yangi = {k: _tozala(v) for k, v in tugun.items() if k not in TASHLANADIGAN}

    # Obyekt bo'lsa — qat'iy qilamiz.
    if "properties" in yangi or yangi.get("type") == "object":
        yangi["type"] = "object"
        yangi["additionalProperties"] = False
        yangi["required"] = list(yangi.get("properties", {}).keys())
    return yangi


def qatiy_sxema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic modelidan qat'iy JSON Schema yasaydi."""
    return _tozala(model.model_json_schema())


def json_format(model: type[BaseModel]) -> dict[str, Any]:
    """`output_config.format` uchun tayyor qiymat."""
    return {"type": "json_schema", "schema": qatiy_sxema(model)}
