"""Menejer qo'lda aytgan narx.

FOYDALANUVCHI XABARI (2026-08-10): KP tuzildi, lekin narxsiz. Menejer
"n1 tovarga 5mln, nomer 2 ga 3mln so'm qilib ber" dedi — tizim narxni
qo'ymadi va YANGI KP tuzib yubordi ("Mahsulot №2 (nomi ko'rsatilmagan)"
kabi qatorlar bilan).

Ikki narsa kerak edi:
  1) menejer aytgan narxni tushunish;
  2) YANGI KP emas, o'shaning o'zini tahrirlash.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.baza import Baza
from kp import KP, Mijoz, Qator, Shartlar
from kp.qol_narx import narx_ajrat


# --- matndan narx ajratish ----------------------------------------------------


@pytest.mark.parametrize("matn,kutilgan", [
    ("n1 tovarga 5mln nomer 2 ga 3mln so'm qilib ber", {1: 5_000_000, 2: 3_000_000}),
    ("1-tovar 5 000 000 som, 2-tovar 3 000 000 som", {1: 5_000_000, 2: 3_000_000}),
    ("birinchisiga 5 mln, ikkinchisiga 3 mln", {1: 5_000_000, 2: 3_000_000}),
    ("№1 5 млн сум, №2 3 млн сум", {1: 5_000_000, 2: 3_000_000}),
    ("1-tovarga 1 500 000 so'm", {1: 1_500_000}),
])
def test_tartib_boyicha_narx(matn, kutilgan):
    assert narx_ajrat(matn).tartib_boyicha == kutilgan


def test_nom_boyicha_narx():
    natija = narx_ajrat("ВК-315С narxi 5 mln")

    assert natija.nom_boyicha == {"ВК-315С": 5_000_000}


@pytest.mark.parametrize("matn", [
    "800 kv metr, balandligi 5 metr ombor uchun KP",
    "Tolibjon MCHJ uchun KP qilib ber, menejer Sardor Rahimxon",
    "10 dona kerak, 5 metr balandlik",
    "3 metr balandlik, 15 kishi",
])
def test_olcham_narx_deb_oqilmaydi(matn):
    """Eng xavfli xato: "5 metr" ni 5 so'm deb olish."""
    natija = narx_ajrat(matn)

    assert not natija.bormi, f"o'lcham narx deb o'qildi: {matn}"


def test_juda_kichik_son_narx_emas():
    """"2 dona" narx emas — chegaradan pastini olmaymiz."""
    assert not narx_ajrat("2 dona kerak, narxi bormi?").bormi


# --- KP ni saqlash va tiklash -------------------------------------------------


def kp_yasa(qatorlar: list[Qator]) -> KP:
    return KP(
        raqam="12951/8",
        sana=date.today(),
        mijoz=Mijoz(nomi="Tolibjon MChJ"),
        qatorlar=qatorlar,
        shartlar=Shartlar(tolov="100%"),
        rekvizitlar={"menejer": "Sardor Rahimxon"},
        valyuta="UZS",
        qqs_foizi=12,
        til="ru",
        ogohlantirishlar=["1 ta pozitsiyada narx yo'q"],
    )


def test_kp_saqlanadi_va_tiklanadi():
    """Tahrirlash uchun KP bazaga to'liq yozilishi kerak."""
    asl = kp_yasa([Qator(nomi="ДР710", spetsifikatsiya="Ø710")])

    tiklangan = KP.tikla(json.loads(json.dumps(asl.saqlash_uchun())))

    assert tiklangan.raqam == asl.raqam
    assert tiklangan.til == "ru"
    assert tiklangan.qqs_foizi == 12
    assert [q.nomi for q in tiklangan.qatorlar] == ["ДР710"]
    assert tiklangan.rekvizitlar["menejer"] == "Sardor Rahimxon"


@pytest.mark.asyncio
async def test_oxirgi_kp_bazada_saqlanadi(tmp_path):
    b = Baza(tmp_path / "kp.db")
    await b.tayyorla()
    kp = kp_yasa([Qator(nomi="ДР710")])

    await b.oxirgi_kp_yoz(901, kp.raqam, json.dumps(kp.saqlash_uchun()))
    saqlangan = await b.oxirgi_kp(901)

    assert saqlangan["raqam"] == "12951/8"
    assert KP.tikla(json.loads(saqlangan["malumot"])).qatorlar[0].nomi == "ДР710"


# --- narxni qo'llash ----------------------------------------------------------


def test_narx_qollanganda_summa_hisoblanadi():
    """Narx qo'yilgach jami va QQS o'zi hisoblanadi (koddan)."""
    kp = kp_yasa([Qator(nomi="A", qqs_foizi=12), Qator(nomi="B", qqs_foizi=12)])
    qol = narx_ajrat("n1 tovarga 5mln nomer 2 ga 3mln so'm")

    for tartib, qator in enumerate(kp.qatorlar, start=1):
        qator.birlik_narx = qol.tartib_boyicha.get(tartib)

    assert kp.summa == 8_000_000
    assert kp.toliq_narxmi is True


def test_bir_qismiga_narx_berilsa_qolgani_bosh_qoladi():
    """Yarim narx ham foydali: qolgani "buxgalteriyadan so'ralsin"."""
    kp = kp_yasa([Qator(nomi="A"), Qator(nomi="B")])
    qol = narx_ajrat("1-tovarga 5 mln so'm")

    for tartib, qator in enumerate(kp.qatorlar, start=1):
        narx = qol.tartib_boyicha.get(tartib)
        if narx is not None:
            qator.birlik_narx = narx

    assert kp.summa == 5_000_000
    assert kp.toliq_narxmi is False
    assert [q.nomi for q in kp.narxsiz_qatorlar] == ["B"]


def test_narx_modeldan_kelmaydi():
    """Asosiy qoida buzilmasin: narx FOYDALANUVCHI matnidan ajratiladi."""
    import ast
    import inspect

    import kp.qol_narx as modul

    daraxt = ast.parse(inspect.getsource(modul))
    importlar: set[str] = set()
    for tugun in ast.walk(daraxt):
        if isinstance(tugun, ast.Import):
            importlar.update(a.name.split(".")[0] for a in tugun.names)
        elif isinstance(tugun, ast.ImportFrom) and tugun.module:
            importlar.add(tugun.module.split(".")[0])

    for taqiq in ("anthropic", "openai", "app"):
        assert taqiq not in importlar, f"narx ajratishga model kirib qolgan: {taqiq}"
