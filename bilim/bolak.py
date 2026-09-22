"""Hujjatlarni qidiriladigan bo'laklarga ajratish.

Ikki xil bo'lish:
  - QONUN hujjati — modda bo'yicha ("173-modda ..."). Har modda alohida
    bo'lak bo'ladi, chunki javobda aynan modda havolasi kerak.
  - ODDIY matn — sarlavhalar bo'yicha, keyin hajm bo'yicha (ustma-ust bilan).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Taxminiy: 1 token ~ 4 belgi. 600 token ~ 2400 belgi, 100 token ~ 400 belgi.
MAKS_BELGI = 2400
USTMA_UST = 400
MIN_BELGI = 120

# Modda sarlavhalari. lex.uz o'zbekcha matnida "1-модда." shaklida (raqam
# oldin, kirillcha), ruschada "Статья 1.", lotinchada "1-modda".
MODDA = re.compile(
    r"^\s*(?:"
    r"\d+(?:[-–]\d+)?\s*[-–]\s*(?:модда|modda)"   # 173-модда / 173-modda
    r"|(?:модда|modda|статья|статья)\s*\d+"        # Модда 173 / Статья 173
    r")\b",
    re.IGNORECASE | re.MULTILINE,
)

# Markdown sarlavhasi
SARLAVHA = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


@dataclass
class Bolak:
    """Indekslanadigan bitta parcha."""

    matn: str
    sarlavha: str = ""
    tartib: int = 0
    metadata: dict = field(default_factory=dict)


def qonunmi(matn: str) -> bool:
    """Hujjat modda bilan tuzilganmi?"""
    return len(MODDA.findall(matn)) >= 3


def _tozala(matn: str) -> str:
    matn = matn.replace("\r\n", "\n").replace("\r", "\n")
    matn = re.sub(r"\n{3,}", "\n\n", matn)
    return matn.strip()


def moddalarga_bol(matn: str) -> list[Bolak]:
    """Qonun matnini moddalarga ajratadi."""
    matn = _tozala(matn)
    joylar = [(m.start(), m.group(0).strip()) for m in MODDA.finditer(matn)]
    if not joylar:
        return []

    bolaklar: list[Bolak] = []
    # Birinchi moddagacha bo'lgan qism — hujjat sarlavhasi/preambula.
    if joylar[0][0] > MIN_BELGI:
        bolaklar.append(Bolak(matn=matn[: joylar[0][0]].strip(), sarlavha="Kirish qism"))

    for i, (boshi, nomi) in enumerate(joylar):
        oxiri = joylar[i + 1][0] if i + 1 < len(joylar) else len(matn)
        parcha = matn[boshi:oxiri].strip()
        if len(parcha) < 20:
            continue

        # Juda uzun modda bo'lsa — ichida yana bo'lamiz, sarlavhani saqlab.
        if len(parcha) > MAKS_BELGI * 2:
            for j, kichik in enumerate(hajm_boyicha_bol(parcha)):
                bolaklar.append(
                    Bolak(matn=kichik.matn, sarlavha=f"{nomi} ({j + 1}-qism)")
                )
        else:
            bolaklar.append(Bolak(matn=parcha, sarlavha=nomi))

    for tartib, bolak in enumerate(bolaklar):
        bolak.tartib = tartib
    return bolaklar


def hajm_boyicha_bol(matn: str) -> list[Bolak]:
    """Matnni hajm bo'yicha bo'ladi, chegaralarda ustma-ust qoldiradi."""
    matn = _tozala(matn)
    if len(matn) <= MAKS_BELGI:
        return [Bolak(matn=matn)] if len(matn) >= MIN_BELGI else []

    bolaklar: list[Bolak] = []
    boshi = 0
    while boshi < len(matn):
        oxiri = min(boshi + MAKS_BELGI, len(matn))
        if oxiri < len(matn):
            # Gap yoki abzas chegarasida uzamiz.
            for ajratgich in ("\n\n", ". ", "\n", " "):
                joy = matn.rfind(ajratgich, boshi + MAKS_BELGI // 2, oxiri)
                if joy > 0:
                    oxiri = joy + len(ajratgich)
                    break
        parcha = matn[boshi:oxiri].strip()
        if len(parcha) >= MIN_BELGI:
            bolaklar.append(Bolak(matn=parcha))
        if oxiri >= len(matn):
            break
        boshi = max(oxiri - USTMA_UST, boshi + 1)

    for tartib, bolak in enumerate(bolaklar):
        bolak.tartib = tartib
    return bolaklar


def sarlavhalar_boyicha_bol(matn: str) -> list[Bolak]:
    """Markdown hujjatini sarlavhalar bo'yicha bo'ladi."""
    matn = _tozala(matn)
    joylar = [(m.start(), m.group(2).strip()) for m in SARLAVHA.finditer(matn)]
    if not joylar:
        return hajm_boyicha_bol(matn)

    bolaklar: list[Bolak] = []
    if joylar[0][0] > MIN_BELGI:
        for kichik in hajm_boyicha_bol(matn[: joylar[0][0]]):
            bolaklar.append(kichik)

    for i, (boshi, nomi) in enumerate(joylar):
        oxiri = joylar[i + 1][0] if i + 1 < len(joylar) else len(matn)
        parcha = matn[boshi:oxiri].strip()
        if len(parcha) < MIN_BELGI:
            continue
        for kichik in hajm_boyicha_bol(parcha) or [Bolak(matn=parcha)]:
            bolaklar.append(Bolak(matn=kichik.matn, sarlavha=nomi))

    for tartib, bolak in enumerate(bolaklar):
        bolak.tartib = tartib
    return bolaklar


def bol(matn: str, qonun: bool | None = None) -> list[Bolak]:
    """Hujjat turiga qarab mos bo'lish usulini tanlaydi."""
    matn = _tozala(matn)
    if not matn:
        return []
    if qonun is None:
        qonun = qonunmi(matn)
    if qonun:
        bolaklar = moddalarga_bol(matn)
        if bolaklar:
            return bolaklar
    return sarlavhalar_boyicha_bol(matn)
