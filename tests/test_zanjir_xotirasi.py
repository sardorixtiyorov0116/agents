"""Zanjir xotirasi — oldingi qadamlarning natijasi yo'qolmasin.

JONLI XATO (2026-08-10): "800 m² ombor uchun KP" so'raldi. Reja
Rustam → Sardor → Temur bo'ldi. Rustam hisobni to'g'ri qildi
(8000 m³/soat, Ø710, ДР710), Sardor esa bitta variant ham
qaytarmadi ("to'liq katalogni bering" dedi). Temurga faqat
Sardorning bo'sh javobi yetib bordi — KP umuman tuzilmadi,
o'rniga 7 ta savol chiqdi.

Sabab: orkestr faqat ENG OXIRGI qadamning natijasini uzatardi.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Holat, Ishonch, Konvert, Manba
from app.orkestr import Orkestr

from .soxta import SoxtaLlm, json_javob


class YozibOluvchi:
    """Har chaqiriqda kelgan kontekstni saqlaydigan soxta agent."""

    def __init__(self, rol: str, natija: dict[str, Any]):
        self.rol = rol
        self._natija = natija
        self.korgan_kontekst: dict[str, Any] = {}

    async def ishla(self, vazifa: str, kontekst=None) -> Konvert:
        self.korgan_kontekst = dict(kontekst or {})
        return Konvert(
            kim=self.rol, holat=Holat.TUGADI, ishonch=Ishonch.YUQORI,
            manba=[Manba(tur="baza", nom="sinov")], natija=self._natija,
        )


def router_javobi(rollar: list[str]):
    return json_javob({
        "niyat": "test",
        "vazifa_soni": len(rollar),
        "qadamlar": [
            {"agent": r, "vazifa": f"{r} vazifasi",
             "tasdiq_kerak": False, "tasdiq_sababi": ""}
            for r in rollar
        ],
        "mos_agent_yoq": False,
        "izoh": "",
    })


async def zanjirni_yurgiz(monkeypatch, tmp_path, agentlar: list[YozibOluvchi]):
    xarita = {a.rol: a for a in agentlar}
    monkeypatch.setattr(
        "app.orkestr.agent_yasa",
        lambda kontrakt, *a, **kw: xarita.get(kontrakt.rol),
    )
    baza = Baza(tmp_path / "zanjir.db")
    await baza.tayyorla()
    llm = SoxtaLlm([router_javobi([a.rol for a in agentlar])])
    return await Orkestr(llm, baza, kontraktlarni_yukla()).bajar("sinov so'rovi")


@pytest.mark.asyncio
async def test_uchinchi_qadam_birinchi_qadam_natijasini_koradi(monkeypatch, tmp_path):
    """Temur (3-qadam) Rustamning (1-qadam) hisobini ko'rishi shart."""
    rustam = YozibOluvchi("hvac-calc", {"xonalar": [{"diametr": 710}]})
    sardor = YozibOluvchi("product-spec", {"variantlar": []})
    temur = YozibOluvchi("proposal-builder", {"kp": "12951/8"})

    await zanjirni_yurgiz(monkeypatch, tmp_path, [rustam, sardor, temur])

    zanjir = temur.korgan_kontekst.get("zanjir_natijalari") or {}
    assert "hvac-calc" in zanjir, "Rustamning hisobi Temurga yetib bormadi"
    assert zanjir["hvac-calc"]["xonalar"][0]["diametr"] == 710
    # Oldingi qadam ham o'z joyida qoladi (mavjud xulq buzilmasin).
    assert temur.korgan_kontekst["oldingi_agent"] == "product-spec"


@pytest.mark.asyncio
async def test_birinchi_qadam_bosh_zanjir_koradi(monkeypatch, tmp_path):
    """Birinchi agentda oldingi natija yo'q — kontekst iflos bo'lmasin."""
    rustam = YozibOluvchi("hvac-calc", {"xonalar": []})

    await zanjirni_yurgiz(monkeypatch, tmp_path, [rustam])

    assert "zanjir_natijalari" not in rustam.korgan_kontekst
    assert "oldingi_natija" not in rustam.korgan_kontekst


# --- agentlar zanjirdan foydalanishi ------------------------------------------


def test_temur_zanjirdan_muhandis_hisobini_oladi():
    """Sardor o'rtada tursa ham Rustamning ro'yxati promptga tushsin."""
    from app.agentlar.tijorat_menejeri import TijoratMenejeri

    temur = TijoratMenejeri.__new__(TijoratMenejeri)
    temur._kontekst = {
        # Bevosita oldingi — Sardor, va u bo'sh qaytardi.
        "oldingi_agent": "product-spec",
        "oldingi_natija": {"variantlar": []},
        "zanjir_natijalari": {
            "hvac-calc": {
                "xonalar": [{
                    "nomi": "Ombor", "maydon": 800.0, "balandlik": 5.0,
                    "havo_sarfi": 8000.0, "diametr": 710,
                }],
                "uskunalar": [{
                    "diametr": 710,
                    "modellar": ["ДР710"],
                    "turlari": [{"model": "ДР710", "turi": "Aylanma deflektor"}],
                }],
            },
        },
    }

    matn = temur._muhandis_tavsiyasi()

    assert "ДР710" in matn
    assert "8000.0 m³/soat" in matn


def test_sardor_muhandis_modellarini_saralashda_ishlatadi():
    """Muhandis tanlagan model MAKS_NOMZOD chegarasidan tashqarida qolmasin."""
    from app.agentlar.mahsulot_mutaxassisi import MahsulotMutaxassisi

    sardor = MahsulotMutaxassisi.__new__(MahsulotMutaxassisi)
    sardor._kontekst = {
        "oldingi_natija": {"uskunalar": [{"modellar": ["ДР710", "ВК-315С"]}]},
    }

    assert sardor._muhandis_modellari() == "ДР710 ВК-315С"

    katalog = [
        {"id": 1, "name": "Klapan", "models": [{"name": "КВ-100"}]},
        {"id": 2, "name": "Deflektor", "models": [{"name": "ДР710"}]},
    ]
    saralangan = MahsulotMutaxassisi._saralab(
        katalog, "ombor ventilyatsiya " + sardor._muhandis_modellari(), set()
    )

    assert saralangan[0]["id"] == 2, "muhandis modeli ro'yxat boshida turmadi"


def test_sardor_toliq_katalog_soramaydi():
    """"To'liq katalogni bering" — foydalanuvchi bera olmaydigan javob."""
    from app.agentlar.mahsulot_mutaxassisi import MahsulotMutaxassisi

    nomzodlar = [{"id": i, "name": f"Mahsulot {i}"} for i in range(137)]

    matn = MahsulotMutaxassisi._nomzod_matni(
        MahsulotMutaxassisi.__new__(MahsulotMutaxassisi), nomzodlar
    )

    assert "To'liq katalog SO'RAMA" in matn
    assert "MOSLIGI bo'yicha" in matn


def test_muhandis_royxatidagi_model_katalogda_bor_hisoblanadi():
    """ДР710 ni Rustam katalogdan olgan — "topilmadi" degan yolg'on chiqmasin."""
    from app.agentlar.tijorat_menejeri import TemurNatija, TemurQator, TijoratMenejeri

    temur = TijoratMenejeri.__new__(TijoratMenejeri)
    temur._kontekst = {
        "zanjir_natijalari": {
            "hvac-calc": {"uskunalar": [{"diametr": 710, "modellar": ["ДР710"]}]},
        },
    }
    natija = TemurNatija(
        qatorlar=[
            TemurQator(nomi="Айланма дефлектор ДР710", katalogda_yoq=True),
            TemurQator(nomi="Чуждый ВЕНТ-999", katalogda_yoq=True),
        ],
        topilmagan_mahsulotlar=["ДР710 — Айланма дефлектор", "ВЕНТ-999"],
    )

    temur._muhandis_tasdigi(natija)

    assert natija.qatorlar[0].katalogda_yoq is False
    # Muhandis ro'yxatida yo'q mahsulot o'z belgisini saqlab qoladi.
    assert natija.qatorlar[1].katalogda_yoq is True
    assert natija.topilmagan_mahsulotlar == ["ВЕНТ-999"]


def test_ventilyator_ham_katalogda_bor_hisoblanadi():
    """Rustam tanlagan ventilyator "topilmadi" deb belgilanmasin."""
    from app.agentlar.tijorat_menejeri import TemurNatija, TemurQator, TijoratMenejeri

    temur = TijoratMenejeri.__new__(TijoratMenejeri)
    temur._kontekst = {
        "zanjir_natijalari": {
            "hvac-calc": {
                "ventilyatorlar": [{"model": "ВЦ 14-46-5-1", "havo_sarfi": [5000, 8400]}],
            },
        },
    }
    natija = TemurNatija(
        qatorlar=[TemurQator(nomi="Вентилятор ВЦ 14-46-5-1", katalogda_yoq=True)],
        topilmagan_mahsulotlar=["ВЦ 14-46-5-1"],
    )

    temur._muhandis_tasdigi(natija)

    assert natija.qatorlar[0].katalogda_yoq is False
    assert natija.topilmagan_mahsulotlar == []


def test_ventilyatorlar_promptda_variant_deb_ataladi():
    """Uch ventilyator KP ga uchta qator bo'lib tushmasligi kerak."""
    from app.agentlar.tijorat_menejeri import TijoratMenejeri

    temur = TijoratMenejeri.__new__(TijoratMenejeri)
    temur._kontekst = {
        "zanjir_natijalari": {
            "hvac-calc": {
                "xonalar": [{"nomi": "Ombor", "maydon": 800.0, "balandlik": 5.0,
                             "havo_sarfi": 8000.0, "diametr": 710}],
                "ventilyatorlar": [
                    {"model": "ВЦ 14-46-5-1", "turi": "Ventilyator VC 14-46",
                     "havo_sarfi": [5000, 8400], "bosim": [860, 1070],
                     "zaxira_foiz": 5},
                    {"model": "ВЦП 6-46-5", "turi": "Ventilyator ВЦП 6-46",
                     "havo_sarfi": [2130, 9040], "bosim": [504, 976],
                     "zaxira_foiz": 13},
                ],
            },
        },
    }

    matn = temur._muhandis_tavsiyasi()

    assert "ВЦ 14-46-5-1" in matn
    assert "5 000–8 400 m³/soat" in matn
    assert "VARIANTLAR" in matn
    assert "FAQAT BITTASINI" in matn


# --- narx tahriri routersiz ---------------------------------------------------


@pytest.mark.parametrize("matn", [
    "n1 tovarga 12 mln so'm qilib ber",
    "1-tovarga 5 000 000 som, 2-tovarga 3 mln",
    "№1 5 млн сум",
])
def test_narx_tahriri_routersiz_bajariladi(matn):
    """Tayyor KP narxini o'zgartirish — butun zanjirni qayta yurgizmaydi."""
    reja = Orkestr._narx_tahriri_rejasi("eski so'rov", {"yangi_xabar": matn})

    assert reja is not None
    assert [q.agent for q in reja.qadamlar] == ["proposal-builder"]
    assert reja.qadamlar[0].tasdiq_kerak is True


@pytest.mark.parametrize("matn", [
    # Yangi obyekt tasvirlangan — bu yangi KP, tahrir emas.
    "800 kv metr ombor uchun KP qilib ber, narxi 5 mln",
    # Narx umuman yo'q.
    "Tolibjon MChJ uchun KP qilib ber",
    # Bo'sh xabar.
    "",
])
def test_narx_tahriri_bolmagan_holat_routerga_ketadi(matn):
    assert Orkestr._narx_tahriri_rejasi("so'rov", {"yangi_xabar": matn}) is None


def test_yangi_xabar_yoq_bolsa_routerga_ketadi():
    assert Orkestr._narx_tahriri_rejasi("so'rov", None) is None
