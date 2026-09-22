"""Ofis harakat mantig'i — brauzersiz simulyatsiya.

`app/static/ofis-model.js` sof mantiq: xarita, yo'l topish, band kataklar va
agent holati. Uni Node'da yurgizib 60 soniyalik ofis hayotini bir necha
soniyada tekshiramiz. Brauzerda bunday o'lchov ishonchsiz — oyna ko'rinmasa
`requestAnimationFrame` to'xtaydi va agentlar joyida qotib qoladi.

Sinaladigan uchta qoida:
  1. Ikki agent hech qachon ustma-ust tushmaydi (bir-birini aylanib o'tadi).
  2. Bo'sh agent o'z bo'limidan chiqmaydi.
  3. Ishlayotgan agent boshqa bo'limlarga boradi.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ILDIZ = Path(__file__).resolve().parent.parent
SKRIPT = ILDIZ / "tests" / "ofis_simulyatsiya.mjs"


# Bir nechta urug' — bitta tasodifiy yo'l "omadli" bo'lib qolmasin.
# Urug' qat'iy bo'lgani uchun yiqilgan holat har doim qayta chiqariladi:
#   node tests/ofis_simulyatsiya.mjs --seed=7
URUGLAR = (1, 7, 42)


@pytest.fixture(scope="module", params=URUGLAR, ids=lambda u: f"urug{u}")
def natija(request) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node o'rnatilmagan — ofis simulyatsiyasi o'tkazib yuborildi")

    jarayon = subprocess.run(
        [node, str(SKRIPT), f"--seed={request.param}"],
        cwd=ILDIZ,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert jarayon.stdout, f"skript hech narsa qaytarmadi: {jarayon.stderr}"
    return json.loads(jarayon.stdout)


def test_agentlar_ustma_ust_tushmaydi(natija: dict):
    """Gavda diametri ~0.55 katak — 0.6 dan yaqin bo'lsa ichma-ich kirgan."""
    assert natija["eng_yaqin_katak"] >= 0.6, (
        f"{natija['eng_yaqin_kim']} orasi {natija['eng_yaqin_katak']} katak"
    )


def test_bosh_agent_boshqa_bolimda_qolmaydi(natija: dict):
    """Yo'lak, oshxona va majlis — umumiy joy, ular hisobga olinmaydi."""
    assert natija["bosh_begona_xonada_kadr"] == 0


def test_ishlayotgan_agent_kompyuteri_oldida_ham_otiradi(natija: dict):
    """Faqat yurib yursa ofis jonli emas — vaqtining bir qismida stolida."""
    assert natija["stolida_ishladi_kadr"] > 0


def test_kimdir_oshxonada_ovqatlanadi(natija: dict):
    assert natija["oshxonada_ovqatlandi_kadr"] > 0


def test_majlisda_orindiqqa_otirishadi(natija: dict):
    """Stol atrofida tik turmasin — hammasi stulga cho'kadi."""
    assert natija["majlis"]["orindiqda_otirdi"] == natija["agentlar_soni"]


def test_ishlayotganlarning_kopchiligi_boshqa_bolimga_boradi(natija: dict):
    """Har biri emas — agent vaqtining yarmida o'z stolida ishlaydi,
    shuning uchun bittasi 60 soniyada chiqmasligi ham normal."""
    ishlayotganlar = [
        "marketing", "legal-review", "hr-assist",
        "proposal-builder", "data-query", "smm-analyst",
    ]
    chiqqan = [
        rol for rol in ishlayotganlar
        if len(set(natija["borgan"][rol]) - {"yolak"}) > 1
    ]
    assert len(chiqqan) >= len(ishlayotganlar) - 2, f"faqat {chiqqan} chiqdi"


def test_savol_chiqsa_hamma_majlisga_yigiladi(natija: dict):
    """Savol (`aniqlik_kerak` / `tasdiq_kutilmoqda`) — butun jamoa yig'iladi."""
    majlis = natija["majlis"]
    assert majlis["hamma_yigildi"], "agentlarning hammasi majlis xonasiga kirmadi"
    # Har kimga o'z o'rindig'i — ikki kishi bitta stulda o'tirmaydi.
    assert majlis["turli_orindiq"] == natija["agentlar_soni"]
    # Foydalanuvchi savolga javob berguncha yig'ilib ulgurishsin. Aniq vaqt
    # tasodifga bog'liq (agentlar qayerda turgan edi) — o'lchovda 13-20 s
    # chiqadi, chegara kengroq qo'yilgan: bu tezlik testi emas, "yo'lda
    # tiqilib qolmadimi" testi.
    assert majlis["yigilish_soniya"] < 30


def test_savol_yopilgach_tarqalishadi(natija: dict):
    assert natija["majlis"]["tarqaldi"]


def test_simulyatsiya_xatosiz(natija: dict):
    assert natija["xatolar"] == []
