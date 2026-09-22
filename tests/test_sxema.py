"""Structured output sxemasi qat'iy bo'lishi kerak."""

from __future__ import annotations

from app.agentlar.narx_kuzatuvchi import ZaraNatija
from app.router import reja_sxemasi
from app.sxema import qatiy_sxema


def _obyektlar(tugun):
    if isinstance(tugun, dict):
        if tugun.get("type") == "object":
            yield tugun
        for qiymat in tugun.values():
            yield from _obyektlar(qiymat)
    elif isinstance(tugun, list):
        for element in tugun:
            yield from _obyektlar(element)


def test_har_obyekt_qatiy():
    sxema = qatiy_sxema(ZaraNatija)
    obyektlar = list(_obyektlar(sxema))
    assert obyektlar
    for obyekt in obyektlar:
        assert obyekt["additionalProperties"] is False
        assert set(obyekt["required"]) == set(obyekt.get("properties", {}))


def test_qollab_quvvatlanmaydigan_kalitlar_yoq():
    matn = str(qatiy_sxema(ZaraNatija))
    for kalit in ("'title'", "'default'", "'maxLength'", "'minimum'"):
        assert kalit not in matn


def test_router_sxemasida_agent_enumi():
    sxema = reja_sxemasi(["price-monitor", "marketing"])
    agent = sxema["schema"]["properties"]["qadamlar"]["items"]["properties"]["agent"]
    assert agent["enum"] == ["price-monitor", "marketing"]
