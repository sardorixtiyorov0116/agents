"""Xaridor ilovasidagi yordamchi (`yordamchi/`).

Eng muhim tekshiruvlar:
  - mijozga yopiq agent ilova orqali ham ochilmaydi;
  - kartochka faqat ANIQ mos kelgan mahsulotga chiqadi;
  - token boshqa foydalanuvchiniki bo'lsa — rad.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.baza import Baza
from app.konvert import Holat, Ishonch, Konvert, Manba
from app.orkestr import Natija
from app.router import Reja, RejaQadam
from bot import suhbat
from bot.mijoz_ruxsat import Tezlik
from sorovnoma.narx_sorov import NarxJavobi
from yordamchi import yadro
from yordamchi.kirish import Kirish, KirishXatosi, token_idsi
from yordamchi.til import matn as tmatn, til as til_ol, tarjimon_yasa
from yordamchi.yadro import (
    MAKS_MAHSULOT,
    Foydalanuvchi,
    Yordamchi,
    mahsulot_idlari,
    narx_matni,
)

IZOH = tmatn("izoh", "uz")

KIM = Foydalanuvchi(id=62, telefon="+998901234567", ism="Ali Valiyev")

KATALOG = [
    {"id": 10, "name_uz": "Kanal ventilyatori", "characters": [
        {"title": "ВКК-250", "insides": [{"in_model_name": "ВКК-250-Е"}]},
    ]},
    {"id": 11, "name_uz": "Panjara", "characters": [{"title": "РВР-2 300х150"}]},
    {"id": 12, "name_uz": "Ventilyator ВО", "characters": [{"title": "ВО 12-300-6,3"}]},
]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "yordamchi.db")
    await b.tayyorla()
    return b


def natija_yasa(holat: Holat, natija: dict | None = None, kim: str = "product-spec") -> Natija:
    return Natija(
        sorov="sinov",
        davomiylik_ms=0,
        yakuniy=Konvert(
            kim=kim,
            holat=holat,
            ishonch=Ishonch.YUQORI,
            natija=natija or {},
            manba=[Manba(tur="kontrakt", nom=f"{kim} kontrakti")],
        ),
    )


class SoxtaOrkestr:
    """Router tuzgan rejani `reja_tekshiruvi` ga ko'rsatadi, keyin natija qaytaradi."""

    def __init__(self, natija: Natija | None = None, rollar=("product-spec",),
                 xato: Exception | None = None):
        self.natija = natija
        self.rollar = rollar
        self.xato = xato
        self.sorovlar: list[str] = []

    async def bajar(self, sorov, kontekst=None, reja_tekshiruvi=None, kuzatuvchi=None):
        self.sorovlar.append(sorov)
        if self.xato:
            raise self.xato
        reja = Reja(niyat="sinov", qadamlar=[RejaQadam(agent=r, vazifa="…") for r in self.rollar])
        if reja_tekshiruvi and await reja_tekshiruvi(reja):
            return natija_yasa(Holat.MOS_AGENT_YOQ, kim="router")
        return self.natija


def yordamchi_yasa(baza, orkestr, katalog=KATALOG, kunlik=20, menejer=None):
    async def katalog_ol():
        return katalog

    async def menejerga(matn):
        if menejer is not None:
            menejer.append(matn)

    return Yordamchi(
        baza=baza,
        orkestr=lambda: orkestr,
        katalog=katalog_ol,
        tezlik=Tezlik(15, kunlik=kunlik),
        menejerga=menejerga,
        telefon="+998 90 354 78 88",
    )


@pytest.fixture(autouse=True)
def narx_yopiq(monkeypatch):
    """Standart holda narx savoli emas — testlar o'zi yoqadi."""
    monkeypatch.setattr(yadro, "narx_soralyaptimi", lambda matn, katalog: False)


# --- kartochkalar -------------------------------------------------------------


def test_aniq_model_kartochka_beradi():
    assert mahsulot_idlari(["ВКК-250"], KATALOG) == [10]


def test_lotin_x_va_bosh_joy_farqi_xalaqit_bermaydi():
    """Agent «РВР-2 300x150» (lotin x) yozsa ham katalogdagi kirill «х» topiladi."""
    assert mahsulot_idlari(["РВР-2  300x150"], KATALOG) == [11]


def test_ichki_ijro_nomi_ham_topiladi():
    """Narx qidiruvi ichki ijro nomini qaytaradi — kartochka ham chiqishi kerak."""
    assert mahsulot_idlari(["ВКК-250-Е"], KATALOG) == [10]


def test_taxminiy_moslik_qilinmaydi():
    """«ВКК-315» katalogda yo'q — «ВКК-250» kartochkasi CHIQMASLIGI kerak."""
    assert mahsulot_idlari(["ВКК-315", "ВО 12"], KATALOG) == []


def test_tartib_va_takror():
    assert mahsulot_idlari(["ВО 12-300-6,3", "ВКК-250", "ВКК-250-Е"], KATALOG) == [12, 10]


def test_kartochka_soni_cheklangan():
    katalog = [{"id": i, "name_uz": f"M{i}", "characters": []} for i in range(20)]
    assert len(mahsulot_idlari([f"M{i}" for i in range(20)], katalog)) == MAKS_MAHSULOT


def test_narx_matnida_markdown_va_raqam_sorash_yoq():
    matn = narx_matni(NarxJavobi(holat="narx", model="ВКК-250", narx=1250000.0))
    assert "*" not in matn and "_" not in matn
    assert "1 250 000 so'm" in matn
    assert "raqam" not in matn.lower()


# --- oqim ---------------------------------------------------------------------


async def test_salomga_model_chaqirilmaydi(baza):
    orkestr = SoxtaOrkestr()
    javob = await yordamchi_yasa(baza, orkestr).javob(KIM, "Assalomu alaykum!")
    assert "Climavent yordamchisiman" in javob.matn
    assert orkestr.sorovlar == []


async def test_bosh_xabar(baza):
    javob = await yordamchi_yasa(baza, SoxtaOrkestr()).javob(KIM, "   ")
    assert javob.holat == "chegara"


async def test_tayyor_javob_kartochka_va_izoh_bilan(baza):
    natija = natija_yasa(Holat.TUGADI, {
        "rejim": "tanlov",
        "variantlar": [{"mahsulot": "Kanal ventilyatori", "model": "ВКК-250"}],
    })
    menejer: list[str] = []
    javob = await yordamchi_yasa(baza, SoxtaOrkestr(natija), menejer=menejer).javob(
        KIM, "250 mm kanal uchun ventilyator kerak")

    assert javob.holat == "javob"
    assert javob.mahsulotlar == [10]
    assert javob.matn.endswith(IZOH)
    # Menejer har savolni ko'radi — telefon bilan.
    assert len(menejer) == 1 and KIM.telefon in menejer[0]


async def test_aniqlashtiruvchi_savolda_kartochka_yoq(baza):
    natija = natija_yasa(Holat.ANIQLIK_KERAK, {"savollar": ["Shift balandligi qancha?"]},
                         kim="hvac-calc")
    javob = await yordamchi_yasa(baza, SoxtaOrkestr(natija, rollar=("hvac-calc",))).javob(
        KIM, "120 m² ofisga ventilyatsiya")
    assert javob.holat == "savol"
    assert javob.mahsulotlar == []
    assert IZOH not in javob.matn


async def test_suhbat_davom_etadi_va_telegramdan_alohida(baza):
    """Ikkinchi xabar birinchisiga qo'shiladi; Telegram kanaliga tegmaydi."""
    savol = natija_yasa(Holat.ANIQLIK_KERAK, {"savollar": ["Balandligi?"]}, kim="hvac-calc")
    orkestr = SoxtaOrkestr(savol, rollar=("hvac-calc",))
    y = yordamchi_yasa(baza, orkestr)
    await y.javob(KIM, "120 m² ofis")
    await y.javob(KIM, "3 metr")

    assert "120 m² ofis" in orkestr.sorovlar[1] and "3 metr" in orkestr.sorovlar[1]
    assert await baza.suhbat(suhbat.MIJOZ, KIM.id) is None


@pytest.mark.parametrize("rol", ["proposal-builder", "data-query", "hr-assist"])
async def test_yopiq_agent_ilovada_ham_yopiq(baza, rol):
    menejer: list[str] = []
    orkestr = SoxtaOrkestr(natija_yasa(Holat.TUGADI, kim=rol), rollar=(rol,))
    javob = await yordamchi_yasa(baza, orkestr, menejer=menejer).javob(KIM, "narx ber")

    assert javob.holat == "menejer"
    assert "menejer" in javob.matn.lower()
    assert menejer and "Menejer kerak" in menejer[0]


async def test_kunlik_chegara_menejerga_otkazadi(baza):
    natija = natija_yasa(Holat.TUGADI, {"variantlar": []})
    menejer: list[str] = []
    y = yordamchi_yasa(baza, SoxtaOrkestr(natija), kunlik=1, menejer=menejer)
    await y.javob(KIM, "birinchi savol")
    javob = await y.javob(KIM, "ikkinchi savol")

    assert javob.holat == "chegara"
    assert "kunlik" in menejer[-1]


async def test_texnik_xatoda_mijoz_quruq_qolmaydi(baza):
    menejer: list[str] = []
    orkestr = SoxtaOrkestr(xato=RuntimeError("LLM yiqildi"))
    javob = await yordamchi_yasa(baza, orkestr, menejer=menejer).javob(KIM, "savol")

    assert javob.holat == "menejer"
    assert "+998 90 354 78 88" in javob.matn
    assert "texnik xato" in menejer[0]


async def test_narx_savoli_modelsiz_va_kartochka_bilan(baza, monkeypatch):
    monkeypatch.setattr(yadro, "narx_soralyaptimi", lambda matn, katalog: True)
    monkeypatch.setattr(yadro, "narxni_top", lambda katalog, matn, kurs=None: NarxJavobi(
        holat="narx", model="ВКК-250-Е", narx=990000.0))
    orkestr = SoxtaOrkestr()
    javob = await yordamchi_yasa(baza, orkestr).javob(KIM, "ВКК-250 narxi qancha")

    assert orkestr.sorovlar == []
    assert javob.mahsulotlar == [10]
    assert "990 000" in javob.matn


async def test_katalog_yiqilsa_ham_javob_beradi(baza):
    async def yiqiladi():
        raise RuntimeError("tarmoq")

    natija = natija_yasa(Holat.TUGADI, {"variantlar": [{"mahsulot": "x", "model": "ВКК-250"}]})
    y = yordamchi_yasa(baza, SoxtaOrkestr(natija))
    y.katalog = yiqiladi
    javob = await y.javob(KIM, "ventilyator kerak")
    assert javob.holat == "javob" and javob.mahsulotlar == []


async def test_murojaat_ilova_belgisi_bilan_yoziladi(baza):
    natija = natija_yasa(Holat.TUGADI, {"variantlar": []})
    await yordamchi_yasa(baza, SoxtaOrkestr(natija)).javob(KIM, "savol")
    royxat = await baza.murojaatlar()
    assert royxat[0]["tg_id"] == "ilova:62"
    assert royxat[0]["aloqa"] == KIM.telefon


# --- token --------------------------------------------------------------------


def jwt(yuk: dict) -> str:
    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'HS256'})}.{b64(yuk)}.imzo"


def test_token_idsi():
    assert token_idsi(jwt({"id": 62})) == "62"
    assert token_idsi(jwt({"sub": "62"})) == "62"
    assert token_idsi(jwt({"rol": "user"})) is None
    assert token_idsi("jwt-emas") is None


def kirish_yasa(javob: httpx.Response, sanoq: list | None = None) -> Kirish:
    def ishla(sorov: httpx.Request) -> httpx.Response:
        if sanoq is not None:
            sanoq.append(sorov)
        return javob
    return Kirish("https://back.test", transport=httpx.MockTransport(ishla))


async def test_tirik_token_profil_beradi_va_keshlanadi():
    sanoq: list = []
    kirish = kirish_yasa(httpx.Response(200, json={
        "id": 62, "phone_number": "+998901234567", "name": "Ali", "surname": "Valiyev"}), sanoq)

    kim = await kirish.tekshir(jwt({"id": 62}), 62)
    await kirish.tekshir(jwt({"id": 62}), 62)

    assert kim == Foydalanuvchi(id=62, telefon="+998901234567", ism="Ali Valiyev")
    assert len(sanoq) == 1
    assert sanoq[0].headers["Authorization"].startswith("Bearer ")
    assert sanoq[0].url.path == "/api/users/one/62"


async def test_boshqaning_tokeni_rad_etiladi():
    sanoq: list = []
    kirish = kirish_yasa(httpx.Response(200, json={"id": 62}), sanoq)
    with pytest.raises(KirishXatosi):
        await kirish.tekshir(jwt({"id": 7}), 62)
    assert sanoq == []  # backendga ham bormaydi


async def test_backend_boshqa_odamni_qaytarsa_rad():
    kirish = kirish_yasa(httpx.Response(200, json={"id": 7}))
    with pytest.raises(KirishXatosi):
        await kirish.tekshir("shaffof-token", 62)


async def test_eskirgan_token_rad():
    kirish = kirish_yasa(httpx.Response(401, json={"message": "Unauthorized"}))
    with pytest.raises(KirishXatosi):
        await kirish.tekshir(jwt({"id": 62}), 62)


async def test_backend_ishlamasa_token_yaroqsiz_deyilmaydi():
    kirish = kirish_yasa(httpx.Response(502))
    with pytest.raises(ConnectionError):
        await kirish.tekshir(jwt({"id": 62}), 62)


async def test_ism_orniga_telefon_yozilgan_bolsa_tashlanadi():
    kirish = kirish_yasa(httpx.Response(200, json={"user": {"id": 62, "name": "+998901234567"}}))
    kim = await kirish.tekshir(jwt({"id": 62}), 62)
    assert kim.ism == ""


# --- server -------------------------------------------------------------------


def test_server_faqat_ikki_yol_ochadi(tmp_path, monkeypatch):
    """Internetga ochiq server — ichki panel yo'llari bu yerda bo'lmasligi SHART."""
    from yordamchi.api import app

    yollar = {r.path for r in app.routes}
    assert yollar == {"/salomat", "/yordamchi/xabar"}


def test_server_tokensiz_401(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("BAZA_YOLI", str(tmp_path / "api.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from yordamchi.api import app

    with TestClient(app) as mijoz:
        javob = mijoz.post("/yordamchi/xabar", json={"user_id": 62, "text": "salom"})
        assert javob.status_code == 401
        assert mijoz.get("/salomat").json()["holat"] == "ishlayapti"


# --- til ----------------------------------------------------------------------


class SoxtaTarjimon:
    def __init__(self, xato: bool = False):
        self.xato = xato
        self.chaqiruvlar: list[tuple[str, str]] = []

    async def __call__(self, matn, til):
        self.chaqiruvlar.append((matn, til))
        return f"[{til}] {matn}"


def test_til_normallashadi():
    assert til_ol("ru") == "ru"
    assert til_ol("RU-ru") == "ru"
    assert til_ol(None) == "uz"
    assert til_ol("de") == "uz"


async def test_ruscha_salom_modelsiz(baza):
    javob = await yordamchi_yasa(baza, SoxtaOrkestr()).javob(KIM, "Привет", "ru")
    assert "ассистент Climavent" in javob.matn


async def test_ruscha_agent_javobi_tarjima_qilinadi_menejerga_ozbekcha(baza):
    natija = natija_yasa(Holat.TUGADI, {"variantlar": [{"mahsulot": "x", "model": "ВКК-250"}]})
    menejer: list[str] = []
    y = yordamchi_yasa(baza, SoxtaOrkestr(natija), menejer=menejer)
    y.tarjimon = SoxtaTarjimon()
    javob = await y.javob(KIM, "Вентилятор 250 мм", "ru")

    assert javob.matn.startswith("[ru] ")
    assert javob.matn.endswith(tmatn("izoh", "ru"))
    assert javob.mahsulotlar == [10]
    assert "[ru]" not in menejer[0]  # menejer asl o'zbekcha javobni ko'radi


async def test_ozbekcha_tarjima_chaqirilmaydi(baza):
    natija = natija_yasa(Holat.TUGADI, {"variantlar": []})
    y = yordamchi_yasa(baza, SoxtaOrkestr(natija))
    tarjimon = SoxtaTarjimon()
    y.tarjimon = tarjimon
    await y.javob(KIM, "ventilyator kerak", "uz")
    assert all(t == "uz" for _, t in tarjimon.chaqiruvlar)


async def test_ruscha_menejerga_otkazish_matni(baza):
    orkestr = SoxtaOrkestr(natija_yasa(Holat.TUGADI, kim="hr-assist"), rollar=("hr-assist",))
    javob = await yordamchi_yasa(baza, orkestr).javob(KIM, "зарплата", "ru")
    assert "менеджер" in javob.matn


def test_ruscha_narx_matni():
    matn = narx_matni(NarxJavobi(holat="narx", model="ВКК-250", narx=1250000.0, manba="5 variantdan eng arzoni"), "ru")
    assert "Цена: 1 250 000 сум" in matn
    assert "variantdan" not in matn  # o'zbekcha izoh ruscha javobga tiqilmaydi


class _SoxtaLlm:
    def __init__(self, xato=False):
        self.xato = xato
        self.soro = None

    async def javob(self, **soro):
        self.soro = soro
        if self.xato:
            raise RuntimeError("tarmoq")

        class _Blok:
            type = "text"
            text = "Расчёт вентиляции"

        class _Javob:
            content = [_Blok()]

        return _Javob()


async def test_tarjimon_promptida_til_va_qoidalar():
    llm = _SoxtaLlm()
    natija = await tarjimon_yasa(llm)("Ventilyatsiya hisobi", "ru")
    assert natija == "Расчёт вентиляции"
    assert "Russian" in llm.soro["system"]
    assert "model name" in llm.soro["system"]
    assert "человек" in llm.soro["system"] and "12 people" not in llm.soro["system"]


async def test_tarjima_yiqilsa_ozbekcha_qaytadi():
    natija = await tarjimon_yasa(_SoxtaLlm(xato=True))("Ventilyatsiya hisobi", "en")
    assert natija == "Ventilyatsiya hisobi"


async def test_ozbek_tiliga_llm_chaqirilmaydi():
    llm = _SoxtaLlm()
    assert await tarjimon_yasa(llm)("matn", "uz") == "matn"
    assert llm.soro is None
