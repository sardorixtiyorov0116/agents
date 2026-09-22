"""Markaziy havo tayyorlash qurilmasi (КЦКП) tanlash.

NEGA KERAK
----------
18 000 m³/soat lik binoga tizim 15 ta kanal isitgichi + 6 ta sovutgich
qo'yardi. Arifmetik to'g'ri, amaliy jihatdan noto'g'ri: bunday
masshtabda muhandis BITTA markaziy qurilma qo'yadi. Uning ichida
ventilyator ham, isitgich ham, sovutgich ham, filtr ham bor.

Katalogda КЦКП 1 600 dan 100 000 m³/soat gacha — ya'ni deyarli har
qanday obyektni qoplaydi.

MUHIM: bu TANLOV, avtomatik qaror emas. Markaziy qurilma qimmatroq va
unga alohida xona (ventkamera) kerak; tarqoq tizim arzonroq, lekin
montaj va xizmat ko'rsatish murakkabroq. Qaysi biri to'g'ri ekanini
menejer/loyihachi hal qiladi — biz ikkala variantni ham ko'rsatamiz.
"""

from __future__ import annotations

from dataclasses import dataclass

# Shundan past sarfda markaziy qurilma taklif QILINMAYDI: kichik
# obyektga u ortiqcha qimmat va ortiqcha joy egallaydi. Kanal isitgichi
# 1200 m³/soat gacha, sovutgich 3200 gacha qoplaydi — shundan yuqorida
# tarqoq tizim parallel uskunalarga bo'linib ketadi.
ENG_KAM_SARF = 2000.0

# Model nomining boshi (KIRILL harflar bilan).
BELGI = "КЦКП"


@dataclass(frozen=True)
class MarkaziyTanlov:
    nomi: str
    sigim: float          # m³/soat — nominal
    zaxira: float         # ulush — kerakligidan necha ortiq


def markaziy_tanla(
    parametrlar: dict[str, dict], sarf: float
) -> MarkaziyTanlov | None:
    """Sarfga yetadigan ENG KICHIK markaziy qurilma.

    Yetadigani bo'lmasa `None` — «eng kattasi mayli» deb olinmaydi.
    Parallel ham qo'yilmaydi: ikkita markaziy qurilma qo'yish alohida
    loyiha qarori, uni biz qabul qilmaymiz.
    """
    if sarf < ENG_KAM_SARF:
        return None

    nomzodlar = [
        (float(yozuv["havo_sarfi"]), nom)
        for nom, yozuv in parametrlar.items()
        if nom.startswith(BELGI)
        and isinstance(yozuv.get("havo_sarfi"), (int, float))
        and float(yozuv["havo_sarfi"]) >= sarf
    ]
    if not nomzodlar:
        return None
    sigim, nomi = min(nomzodlar)
    return MarkaziyTanlov(
        nomi=nomi,
        sigim=sigim,
        zaxira=round((sigim - sarf) / sarf, 3) if sarf > 0 else 0.0,
    )
