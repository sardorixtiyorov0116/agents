"""E'lon manbalari — API shakli bilan `Elon` orasidagi tarjima.

Tarmoqqa CHIQILMAYDI: har manba `httpx.MockTransport` bilan sinaladi.
Bu qatlamdagi xato jimgina yuzaga chiqadi — e'lon tushib qoladi yoki
summa 100 barobar xato ko'rinadi, va buni hech kim sezmaydi.
"""

from __future__ import annotations

import pytest



# --- etender.uzex.uz (2026-09-09 da qo'shildi) --------------------------------
#
# TOPILGAN KAMCHILIK: DXMAP beshta maydonchani qamraydi, lekin
# `etender.uzex.uz` ular orasida YO'Q. Bu boshqa xarid turi — tanlov va
# tenderlar, ya'ni KATTA shartnomalar. O'lchandi: 679 ochiq lotdan 9
# tasi bizga mos, jami 17,58 mlrd so'm. Eng kattasi 9,58 mlrd.


ETENDER_YOZUV = {
    "rn": 1,
    "id": 508307,
    "display_no": "26120012508307",
    "total_count": 1,
    "name": "Konditsioner va ventilyatsiya tizimlariga texnik xizmat ko‘rsatish",
    "start_date": "2026-09-02T09:30:55",
    "end_date": "2026-09-09T09:30:55",
    "cost": 511750000.0,
    "seller_name": "TOSHKENT XALQARO AEROPORTI MChJ",
    "seller_tin": "200640719",
    "region_name": None,
    "district_name": "Сирғали тумани",
}


def _soxta_etender(yozuvlar, kod=200):
    import httpx

    def javob(soro: httpx.Request) -> httpx.Response:
        return httpx.Response(kod, json=yozuvlar)

    return httpx.AsyncClient(transport=httpx.MockTransport(javob))


@pytest.mark.asyncio
async def test_etender_lotni_oqiydi():
    from integrations.tender_manba import EtenderManba

    manba = EtenderManba(mijoz=_soxta_etender([ETENDER_YOZUV]))
    elonlar = await manba.elonlar(chek=10)

    assert len(elonlar) == 1
    e = elonlar[0]
    assert e.lot_raqami == "26120012508307"
    assert e.buyurtmachi_stir == "200640719"
    assert e.havola == "https://etender.uzex.uz/lot/508307"
    assert e.maydoncha == "etender.uzex.uz"


@pytest.mark.asyncio
async def test_etender_summasi_TIYINGA_bolinmaydi():
    """DXMAP tiyinda beradi, bu API SO'MDA.

    Buni ma'lumotning o'zi ko'rsatdi: 679 narxning 40%i 100 ga
    bo'linmaydi va ba'zilari kasrli (`42227893695.4`) — tiyin butun
    son bo'lardi. Bo'lib yuborilsa 511 mln lot 5 mln bo'lib ko'rinardi.
    """
    from integrations.tender_manba import EtenderManba

    manba = EtenderManba(mijoz=_soxta_etender([ETENDER_YOZUV]))
    elonlar = await manba.elonlar(chek=10)

    assert elonlar[0].summa == 511_750_000.0


@pytest.mark.asyncio
async def test_etender_HAQIQIY_muddat_beradi():
    """DXMAP muddat bermaydi — bu maydoncha beradi va u eng muhimi."""
    from integrations.tender_manba import EtenderManba

    manba = EtenderManba(mijoz=_soxta_etender([ETENDER_YOZUV]))
    elonlar = await manba.elonlar(chek=10)

    assert elonlar[0].muddat == "2026-09-09"
    assert "muddat" in elonlar[0].qisqa()


@pytest.mark.asyncio
async def test_etender_kalit_sozsiz_lot_TASHLANADI():
    """API qidiruv qabul qilmaydi — filtrlash kodda bo'ladi."""
    from integrations.tender_manba import EtenderManba

    aloqasiz = dict(ETENDER_YOZUV, id=1, name="Ofis mebeli yetkazib berish")
    manba = EtenderManba(mijoz=_soxta_etender([aloqasiz, ETENDER_YOZUV]))

    elonlar = await manba.elonlar(chek=10)

    assert [e.lot_raqami for e in elonlar] == ["26120012508307"]


@pytest.mark.asyncio
async def test_etender_yiqilsa_TenderXatosi():
    """Nosozlik jimgina yutilmaydi — agent uni ochiq aytadi."""
    from integrations.tender_manba import EtenderManba, TenderXatosi

    manba = EtenderManba(mijoz=_soxta_etender([], kod=500))
    with pytest.raises(TenderXatosi):
        await manba.elonlar(chek=10)


@pytest.mark.asyncio
async def test_id_siz_yozuv_tashlanadi():
    """Havola yasab bo'lmasa e'lon ko'rsatilmaydi (o'zgarmas qoida)."""
    from integrations.tender_manba import EtenderManba

    yaroqsiz = {k: v for k, v in ETENDER_YOZUV.items() if k != "id"}
    manba = EtenderManba(mijoz=_soxta_etender([yaroqsiz]))

    assert await manba.elonlar(chek=10) == []


def test_etender_standart_manbalar_royxatida():
    from integrations.tender_manba import EtenderManba, standart_manbalar

    assert any(isinstance(m, EtenderManba) for m in standart_manbalar())


@pytest.mark.asyncio
async def test_IKKALA_royxat_ham_olinadi():
    """`TradeList` va `DiscussionTradeList` — KESISHMAYDI.

    O'LCHANDI (2026-09-09): birinchisida 676 lot, ikkinchisida 236 ta,
    va ikkinchisining HECH BIR loti birinchisida yo'q. 236 tadan 233
    tasining muddati kelajakda — ya'ni bu arxiv emas, tirik ro'yxat.
    Faqat bittasini olsak, ikkinchisi butunlay ko'rinmasdi.
    """
    import httpx

    from integrations.tender_manba import EtenderManba

    chaqirilgan: list[str] = []

    def javob(soro: httpx.Request) -> httpx.Response:
        chaqirilgan.append(soro.url.path)
        if "Discussion" in soro.url.path:
            return httpx.Response(200, json=[dict(ETENDER_YOZUV, id=999,
                                                  display_no="999")])
        return httpx.Response(200, json=[ETENDER_YOZUV])

    manba = EtenderManba(mijoz=httpx.AsyncClient(
        transport=httpx.MockTransport(javob)))
    elonlar = await manba.elonlar(chek=10)

    assert any("Discussion" in y for y in chaqirilgan), chaqirilgan
    assert any("common/TradeList" in y for y in chaqirilgan), chaqirilgan
    assert len(elonlar) == 2, "ikkala ro'yxatdan ham e'lon kelmadi"


@pytest.mark.asyncio
async def test_MUHOKAMA_bosqichi_belgilanadi():
    """Muhokama savdodan farq qiladi — menejer buni ko'rishi kerak."""
    import httpx

    from integrations.tender_manba import EtenderManba

    def javob(soro: httpx.Request) -> httpx.Response:
        if "Discussion" in soro.url.path:
            return httpx.Response(200, json=[ETENDER_YOZUV])
        return httpx.Response(200, json=[])

    manba = EtenderManba(mijoz=httpx.AsyncClient(
        transport=httpx.MockTransport(javob)))
    elonlar = await manba.elonlar(chek=10)

    assert elonlar[0].maydoncha == "etender.uzex.uz (muhokama)"


# --- faqat QATNASHISH MUMKIN bo'lgan lot (2026-09-09) ------------------------
#
# O'LCHANDI: 200 ta `IN_PROCESS` lotdan 150 tasida shartnoma allaqachon
# tuzilgan, 16 tasida g'olib aniqlanmoqda. Ya'ni menejerga
# ko'rsatilayotganning 84% iga QATNASHIB BO'LMAYDI — u havolani ochadi,
# o'qiydi va vaqtini behuda sarflaydi.


def _dxmap_yozuv(**ustama):
    asos = {
        "lotId": "261110085622149",
        "organInn": "200541002",
        "organizationType": "BUDGET",
        "enktNames": "Ventilyatsiya tizimi",
        "organ": "BUYURTMACHI DM",
        "startSumma": 100_000_000,
        "platformName": "xarid.uzex.uz",
        "lotStatuses": [{"name": "E'lon", "order": 1, "isCompleted": True}],
    }
    asos.update(ustama)
    return asos


@pytest.mark.parametrize("bosqichlar,kutilgan", [
    ([{"name": "E'lon", "order": 1, "isCompleted": True}], True),
    ([{"name": "E'lon", "order": 1, "isCompleted": False}], True),
    # Shartnoma tuzilgan — ish tugagan.
    ([{"name": "E'lon", "order": 1, "isCompleted": True},
      {"name": "Shartnoma shakllandi", "order": 2, "isCompleted": True}], False),
    # G'olib aniqlanmoqda — taklif berish yopilgan.
    ([{"name": "G'olib aniqlanmoqda", "order": 1, "isCompleted": True}], False),
    # To'lov bosqichi — butunlay tugagan.
    ([{"name": "To'lov to'liq to'landi", "order": 6, "isCompleted": True}], False),
    # Bosqich yo'q — hech narsa deya olmaymiz, ko'rsatamiz.
    ([], True),
])
def test_bosqich_boyicha_ochiqlik(bosqichlar, kutilgan):
    from integrations.tender_manba import _dxmap_ochiqmi

    assert _dxmap_ochiqmi(_dxmap_yozuv(lotStatuses=bosqichlar)) is kutilgan


def test_GOLIBI_bor_lot_ochiq_emas():
    """`vendor` to'lgan bo'lsa savdo tugagan — bosqichdan qat'i nazar."""
    from integrations.tender_manba import _dxmap_ochiqmi

    assert _dxmap_ochiqmi(_dxmap_yozuv(vendor="G'olib MChJ")) is False
    assert _dxmap_ochiqmi(_dxmap_yozuv(vendorInn="123456789")) is False


@pytest.mark.asyncio
async def test_yopiq_lot_ELONGA_tushmaydi():
    """Butun oqim: shartnomasi bor lot menejerga ko'rsatilmaydi."""
    import httpx

    from integrations.tender_manba import DxmapManba

    ochiq = _dxmap_yozuv(lotId="111")
    yopiq = _dxmap_yozuv(
        lotId="222",
        lotStatuses=[{"name": "Shartnoma shakllandi", "order": 2,
                      "isCompleted": True}],
    )

    def javob(soro: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [ochiq, yopiq]})

    manba = DxmapManba(
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(javob)),
        kalit_sozlar=("ventilyatsiya",),
    )
    elonlar = await manba.elonlar(chek=10)

    assert [e.lot_raqami for e in elonlar] == ["111"]


# --- tender.mc.uz (2026-09-09 da qo'shildi) ----------------------------------
#
# ISHTIROK ETILADI: lot sahifasida taklif berish bor, `bidders_count` va
# muddat ochiq keladi. DIQQAT: bu QURILISH maydonchasi — bugungi 498 ta
# ochiq tenderdan ventilyatsiya lotlari NOL ta. Bu kutilgan hol.


MCUZ_YOZUV = {
    "id": 287372,
    "unique_name": "26411012287372",
    "name": "Ventilyatsiya tizimini o‘rnatish ishlari",
    "start_price": "1078424571",
    "placement_term": "2026-09-16 23:59:59",
    "confirmed_date": "2026-09-09 10:21:22",
    "bidders_count": 0,
    "winner_id": None,
    "status": "2",
    "region": {"id": 1, "name": "Андижанская область"},
    "district": {"id": 8, "name": "Джалакудукский"},
    "customer": {"id": 26076, "inn": 311339590, "name": "INJINIRING KOMPANIYASI"},
}


def _soxta_mcuz(yozuvlar, kod=200):
    import httpx

    def javob(soro: httpx.Request) -> httpx.Response:
        if kod >= 400:
            return httpx.Response(kod)
        return httpx.Response(200, json={"result": {"data": yozuvlar}})

    return httpx.AsyncClient(transport=httpx.MockTransport(javob))


@pytest.mark.asyncio
async def test_mcuz_lotni_oqiydi():
    from integrations.tender_manba import McuzManba

    manba = McuzManba(mijoz=_soxta_mcuz([MCUZ_YOZUV]),
                      kalit_sozlar=("ventilyatsiya",))
    elonlar = await manba.elonlar(chek=10)

    assert len(elonlar) == 1
    e = elonlar[0]
    assert e.lot_raqami == "26411012287372"
    assert e.buyurtmachi_stir == "311339590"
    assert e.havola == "https://tender.mc.uz/tender-list/tender/287372/view"
    assert e.hudud == "Андижанская область Джалакудукский"


@pytest.mark.asyncio
async def test_mcuz_summasi_SOMDA():
    """O'lchandi: 200 narxdan 66%i 100 ga bo'linmaydi — demak so'm."""
    from integrations.tender_manba import McuzManba

    manba = McuzManba(mijoz=_soxta_mcuz([MCUZ_YOZUV]),
                      kalit_sozlar=("ventilyatsiya",))
    elonlar = await manba.elonlar(chek=10)

    assert elonlar[0].summa == 1_078_424_571.0


@pytest.mark.asyncio
async def test_mcuz_TAKLIFLAR_sonini_beradi():
    """0 taklif = raqobat yo'q. Bu menejer uchun kuchli belgi."""
    from integrations.tender_manba import McuzManba

    manba = McuzManba(mijoz=_soxta_mcuz([MCUZ_YOZUV]),
                      kalit_sozlar=("ventilyatsiya",))
    elonlar = await manba.elonlar(chek=10)

    assert elonlar[0].takliflar == 0
    # NOL ham ma'lumot — natijadan tushib qolmasin.
    assert elonlar[0].qisqa()["takliflar"] == 0


@pytest.mark.asyncio
async def test_mcuz_GOLIBI_bor_lot_tashlanadi():
    """G'olib aniqlangan — taklif berib bo'lmaydi."""
    from integrations.tender_manba import McuzManba

    yopiq = dict(MCUZ_YOZUV, winner_id=555)
    manba = McuzManba(mijoz=_soxta_mcuz([yopiq]),
                      kalit_sozlar=("ventilyatsiya",))

    assert await manba.elonlar(chek=10) == []


@pytest.mark.asyncio
async def test_mcuz_faqat_OCHIQ_holat_soraladi():
    """Filtrsiz 115 390 lot (butun arxiv) keladi — so'rash ma'nosiz."""
    import httpx

    from integrations.tender_manba import McuzManba

    sorovlar: list[dict] = []

    def javob(soro: httpx.Request) -> httpx.Response:
        sorovlar.append(dict(soro.url.params))
        return httpx.Response(200, json={"result": {"data": []}})

    manba = McuzManba(
        mijoz=httpx.AsyncClient(transport=httpx.MockTransport(javob)),
        kalit_sozlar=("ventilyatsiya",),
    )
    await manba.elonlar(chek=10)

    assert sorovlar[0]["status"] == "2"
    assert sorovlar[0]["name"] == "ventilyatsiya"


@pytest.mark.asyncio
async def test_mcuz_hamma_sorov_yiqilsa_XATO():
    """Jimgina «lot yo'q» deyish — eng yomon xatolik turi."""
    from integrations.tender_manba import McuzManba, TenderXatosi

    manba = McuzManba(mijoz=_soxta_mcuz([], kod=500),
                      kalit_sozlar=("ventilyatsiya",))
    with pytest.raises(TenderXatosi):
        await manba.elonlar(chek=10)


def test_mcuz_standart_manbalar_royxatida():
    from integrations.tender_manba import McuzManba, standart_manbalar

    assert any(isinstance(m, McuzManba) for m in standart_manbalar())


def test_SOZLAMA_va_KOD_standarti_mos():
    """Ikki joyda standart ro'yxat bor — ular ajralib ketmasin.

    Bir marta shunday bo'ldi: kodda `("etender", "mcuz")` yozilgan,
    sozlamada esa `"etender"` qolgan — natijada `tender.mc.uz` ulangan
    bo'lsa ham ISHLAMADI va buni faqat jonli tekshiruv ko'rsatdi.
    """
    from app.config import Sozlama
    from integrations.tender_manba import STANDART_MANBALAR

    sozlamadagi = [
        n.strip().lower()
        for n in Sozlama.model_fields["tender_manbalari"].default.split(",")
        if n.strip()
    ]
    assert sozlamadagi == list(STANDART_MANBALAR), (
        f"sozlama {sozlamadagi}, kod {list(STANDART_MANBALAR)}"
    )
