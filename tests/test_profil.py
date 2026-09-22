"""Kompaniya profili — yuklash, bo'sh maydonlar, promptga ulanishi."""

from __future__ import annotations

import json

import pytest
import yaml

from app.agentlar.raqobat_tahlilchisi import RaqobatTahlilchisi
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.profil import Profil, profilni_yukla

from .soxta import SoxtaLlm, javob, matn_bloki


@pytest.fixture
def kontraktlar():
    return kontraktlarni_yukla()


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "profil.db")
    await b.tayyorla()
    return b


# --- yuklash -----------------------------------------------------------------


def test_haqiqiy_profil_yuklanadi():
    p = profilni_yukla()

    assert p.bormi
    assert p.nomi == "Jihozvent MChJ"
    assert p.kompaniya["savdo_brendi"] == "Climavent"
    assert p.kompaniya["tashkil_etilgan"] == 2002
    # Topshiriqda nomlangan 4 ta raqobatchi profilda bo'lishi shart
    nomlar = p.raqobatchi_nomlari()
    for kutilgan in ("Ventsystems", "Direct Cool Engineering", "Everest Group", "Ventstore"):
        assert kutilgan in nomlar
    assert p.taqiqlar()


def test_fayl_yoq_bolsa_bosh_profil(tmp_path):
    """Profil yo'qligi xato emas — tizim ishlashda davom etadi."""
    p = profilni_yukla(tmp_path / "yoq.yaml")

    assert p.bormi is False
    assert p.matn() == ""
    assert p.qisqa() == ""
    assert p.raqobatchi_nomlari() == []


def test_bosh_maydonlar_promptga_tushmaydi():
    """To'ldirilmagan maydon 'noma'lum' bo'lib chiqmasin — umuman ko'rinmasin."""
    p = Profil(
        {
            "kompaniya": {"nomi": "Test MChJ", "sayt": "", "email": None, "telefon": "   "},
            "mahsulotlar": {"yonalishlar": []},
            "raqobatchilar": [],
        }
    )
    matn = p.matn()

    assert "Test MChJ" in matn
    assert "sayt" not in matn
    assert "email" not in matn
    assert "telefon" not in matn
    assert "yonalishlar" not in matn
    assert "None" not in matn


def test_profil_faylida_qoshimcha_maydon_qollab_quvvatlanadi(tmp_path):
    """Profilni kodga tegmasdan kengaytirish mumkin."""
    fayl = tmp_path / "p.yaml"
    fayl.write_text(
        yaml.safe_dump(
            {"kompaniya": {"nomi": "X"}, "yangi_bolim": {"kalit": "qiymat"}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    p = profilni_yukla(fayl)

    assert "yangi bolim" in p.matn()
    assert "qiymat" in p.matn()


# --- agentga ulanishi --------------------------------------------------------


@pytest.mark.asyncio
async def test_profil_agent_promptiga_qoshiladi(kontraktlar, baza):
    llm = SoxtaLlm(
        [
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "hudud": "Toshkent",
                                "davr": "1 oy",
                                "topilmalar": [],
                                "trendlar": [],
                                "xulosa": "",
                                "topilmaganlar": [],
                            },
                            ensure_ascii=False,
                        )
                    )
                ]
            )
        ]
    )
    karim = RaqobatTahlilchisi(kontrakt=kontraktlar["competitor-watch"], llm=llm, baza=baza)
    await karim.ishla("Raqiblarni ko'rib chiq")

    tizim = llm.chaqiruvlar[0]["system"][0]["text"]
    assert "SEN QAYSI KOMPANIYA UCHUN ISHLAYSAN" in tizim
    assert "Jihozvent MChJ" in tizim
    # Agent profildagi ma'lumot uchun savol so'ramasligi aytilgan
    assert "savol so'rama" in tizim
    # Kesh saqlanib qolgan
    assert llm.chaqiruvlar[0]["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_karim_raqobatchilarni_profildan_oladi(kontraktlar, baza):
    """"Raqiblarimiz kimlar" — Karim ro'yxatni so'ramaydi, profildan oladi."""
    llm = SoxtaLlm(
        [
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "hudud": "Toshkent",
                                "davr": "1 oy",
                                "topilmalar": [],
                                "trendlar": [],
                                "xulosa": "",
                                "topilmaganlar": [],
                            },
                            ensure_ascii=False,
                        )
                    )
                ]
            )
        ]
    )
    karim = RaqobatTahlilchisi(kontrakt=kontraktlar["competitor-watch"], llm=llm, baza=baza)
    await karim.ishla("Raqiblarimiz nima qilyapti?")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "Ventsystems" in xabar
    assert "Direct Cool Engineering" in xabar


@pytest.mark.asyncio
async def test_profilsiz_ham_ishlaydi(kontraktlar, baza):
    """Profil bo'lmasa agent baribir ishlaydi (prompt qisqaradi, xolos)."""
    llm = SoxtaLlm(
        [
            javob(
                [
                    matn_bloki(
                        json.dumps(
                            {
                                "hudud": "",
                                "davr": "",
                                "topilmalar": [],
                                "trendlar": [],
                                "xulosa": "",
                                "topilmaganlar": [],
                            }
                        )
                    )
                ]
            )
        ]
    )
    karim = RaqobatTahlilchisi(
        kontrakt=kontraktlar["competitor-watch"], llm=llm, baza=baza, kompaniya=Profil({})
    )
    k = await karim.ishla("Raqiblarni ko'r")

    assert k.kim == "competitor-watch"
    tizim = llm.chaqiruvlar[0]["system"][0]["text"]
    assert "SEN QAYSI KOMPANIYA UCHUN ISHLAYSAN" not in tizim
