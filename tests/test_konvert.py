"""Umumiy konvert va kontraktlar."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.kontraktlar import kontraktlarni_yukla
from app.konvert import (
    Holat,
    Ishonch,
    Konvert,
    Manba,
    mos_agent_yoq_konvert,
    ulanmagan_konvert,
    xato_konvert,
)


def test_konvert_maydonlari_ozbekcha():
    k = Konvert(
        kim="price-monitor",
        holat=Holat.TUGADI,
        natija={"a": 1},
        manba=[Manba(tur="veb", nom="Olcha", havola="https://olcha.uz")],
        ishonch=Ishonch.YUQORI,
    )
    chiqdi = k.model_dump(mode="json")
    assert set(chiqdi) == {
        "kim",
        "holat",
        "natija",
        "manba",
        "ishonch",
        "tasdiq_kerak",
        "izoh",
    }
    assert chiqdi["holat"] == "tugadi"
    assert chiqdi["ishonch"] == "yuqori"
    assert chiqdi["tasdiq_kerak"] is False


def test_tugadi_holatida_manba_majburiy():
    with pytest.raises(ValidationError):
        Konvert(kim="price-monitor", holat=Holat.TUGADI, ishonch=Ishonch.YUQORI)


def test_xato_holatida_manba_shart_emas():
    k = xato_konvert("price-monitor", "narx topilmadi")
    assert k.holat is Holat.XATO
    assert k.manba == []


def test_holatlar_ajratilgan():
    """Turli vaziyat bir xil 'xato' yorlig'ini olmasligi kerak.

    Holatlar to'liq ro'yxati `test_aniqlik.py` da tekshiriladi.
    """
    mos_yoq = mos_agent_yoq_konvert("Buyurtma berish kontraktlarda yo'q")
    assert mos_yoq.holat is Holat.MOS_AGENT_YOQ
    assert mos_yoq.kim == "router"

    ulanmagan = ulanmagan_konvert("legal-review", "kontrakt bor, kod yo'q")
    assert ulanmagan.holat is Holat.ULANMAGAN
    assert ulanmagan.kim == "legal-review"

    # Ikkalasi ham xato emas
    assert Holat.XATO not in (mos_yoq.holat, ulanmagan.holat)


def test_kontraktlar_yuklanadi():
    kontraktlar = kontraktlarni_yukla()
    # Son QO'LDA yozilmaydi: yangi agent qo'shilganda bu test
    # xato bermasligi kerak — u kontrakt SIFATINI tekshiradi, sonini emas.
    from app.config import ILDIZ
    fayllar = list((ILDIZ / "contracts").glob("*.yaml"))
    assert len(kontraktlar) == len(fayllar)
    assert kontraktlar["price-monitor"].korinish == "Narx analitigi Zara"
    assert kontraktlar["legal-review"].korinish == "Yurist Laziz"

    # Xavf darajalari topshiriq hujjatidagidek
    kutilgan = {
        "price-monitor": "past",
        "competitor-watch": "past",
        "product-spec": "past",
        "data-query": "orta",
        "marketing": "orta",
        "sales-strategy": "orta",
        "proposal-builder": "orta",
        "hr-assist": "yuqori",
        "legal-review": "yuqori",
        "catalog-admin": "yuqori",
        "tender-watch": "past",
        "smm-analyst": "past",
        "kp-tracker": "orta",
        "hvac-calc": "orta",
        # Anvar: xato montaj maslahati jarohatga olib kelishi mumkin,
        # lekin javob har doim inson ko'zidan o'tadi.
        "montaj-guide": "orta",
    }
    assert {r: k.xavf.value for r, k in kontraktlar.items()} == kutilgan

    # Kontraktdagi `amalga_oshirilgan` bayrog'i haqiqatga mos bo'lishi shart:
    # bayroq bor, lekin klass yo'q (yoki aksincha) — router foydalanuvchini
    # aldab qo'yadi.
    from app.agentlar import AGENT_KLASSLARI

    ulangan = {r for r, k in kontraktlar.items() if k.amalga_oshirilgan}
    assert ulangan == set(AGENT_KLASSLARI)


def test_kontrakt_matnida_chegaralar_bor():
    kontraktlar = kontraktlarni_yukla()
    matn = kontraktlar["price-monitor"].matn()
    assert "QILMAYDI" in matn
    assert "Raqib tahlili qilmaydi" in matn
