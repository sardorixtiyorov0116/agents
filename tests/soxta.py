"""Testlar uchun soxta LLM va yordamchilar (API'ga chiqmaydi)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any


def matn_bloki(matn: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=matn)


def qidiruv_bloki(natijalar: list[dict[str, Any]]) -> SimpleNamespace:
    return SimpleNamespace(
        type="web_search_tool_result",
        content=[
            SimpleNamespace(
                type="web_search_result",
                title=n.get("title"),
                url=n.get("url"),
                page_age=n.get("page_age"),
            )
            for n in natijalar
        ],
    )


def javob(bloklar: list[Any], stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=bloklar, stop_reason=stop_reason)


class SoxtaLlm:
    """Oldindan berilgan javoblarni navbat bilan qaytaradi."""

    def __init__(self, javoblar: list[Any]):
        self.javoblar = list(javoblar)
        self.chaqiruvlar: list[dict[str, Any]] = []

    async def javob(self, **soro: Any) -> Any:
        self.chaqiruvlar.append(soro)
        if not self.javoblar:
            raise AssertionError("SoxtaLlm: kutilganidan ko'p chaqiruv bo'ldi")
        return self.javoblar.pop(0)


def json_javob(malumot: dict[str, Any], **kw: Any) -> SimpleNamespace:
    return javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))], **kw)


def soxta_bilim(*parchalar: tuple[str, str]) -> Any:
    """Bilim bazasi qidiruvining soxtasi.

    Misol:
        soxta_bilim(("Mehnat kodeksi, 173-modda", "Mehnat shartnomasi ..."))
    """
    from bilim.qidiruv import Topilma

    topilmalar = [
        Topilma(
            matn=matn,
            hujjat=manba.split(",")[0].strip(),
            sarlavha=manba.split(",", 1)[1].strip() if "," in manba else "",
            papka="legal",
            tur="qonun",
            ball=1.0,
        )
        for manba, matn in parchalar
    ]

    class SoxtaQidiruv:
        def __init__(self) -> None:
            self.sorovlar: list[str] = []

        def agent_uchun(self, rol: str, sorov: str, chek: int | None = None):
            self.sorovlar.append(sorov)
            return list(topilmalar)

        def qidir(self, sorov: str, papkalar: list[str], chek: int = 5):
            self.sorovlar.append(sorov)
            return list(topilmalar)

    return SoxtaQidiruv()


def soxta_api(**javoblar: Any) -> Any:
    """Ichki API klientining soxtasi (tarmoqqa chiqmaydi).

    Misol:
        api = soxta_api(qidir_keng=[MAHSULOT], katalog_xulosasi={...})
    Berilmagan metod chaqirilsa — `ApiXatosi` (API mavjud emas yo'li).
    """
    from integrations.climavent_client import ApiXatosi

    class SoxtaApi:
        def __init__(self) -> None:
            self.chaqiruvlar: list[tuple[str, tuple[Any, ...]]] = []

        def __getattr__(self, nom: str):
            async def chaqiruv(*args: Any, **kw: Any) -> Any:
                self.chaqiruvlar.append((nom, args))
                if nom not in javoblar:
                    raise ApiXatosi(f"soxta API: '{nom}' sozlanmagan")
                qiymat = javoblar[nom]
                if isinstance(qiymat, Exception):
                    raise qiymat
                return qiymat

            return chaqiruv

    return SoxtaApi()
