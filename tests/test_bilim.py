"""Bilim bazasi — bo'lish, papka izolyatsiyasi, transliteratsiya, RAG ulanishi."""

from __future__ import annotations

import json

import pytest

from app.agentlar.yurist import Yurist
from app.baza import Baza
from app.kontraktlar import kontraktlarni_yukla
from app.konvert import Ishonch
from bilim.bolak import bol, hajm_boyicha_bol, moddalarga_bol, qonunmi
from bilim.qidiruv import AGENT_PAPKALARI, kontekst_matni, transliteratsiya

from .soxta import SoxtaLlm, javob, matn_bloki, soxta_bilim

QONUN = """ЎЗБЕКИСТОН РЕСПУБЛИКАСИНИНГ МЕҲНАТ КОДЕКСИ

1-модда. Меҳнат тўғрисидаги қонунчиликнинг вазифалари
Меҳнат тўғрисидаги қонунчиликнинг вазифалари фуқароларнинг меҳнатга бўлган
конституциявий ҳуқуқларини рўёбга чиқаришдан иборат.

2-модда. Меҳнат муносабатлари
Меҳнат муносабатлари меҳнат шартномаси асосида юзага келади ва тарафларнинг
ҳуқуқ ҳамда мажбуриятлари билан белгиланади.

3-модда. Меҳнат шартномаси
Меҳнат шартномаси ходим билан иш берувчи ўртасидаги келишувдир.
"""


# --- bo'lish -----------------------------------------------------------------


def test_qonun_moddalarga_bolinadi():
    assert qonunmi(QONUN)
    bolaklar = moddalarga_bol(QONUN)

    # Kirish qism + 3 ta modda
    sarlavhalar = [b.sarlavha for b in bolaklar]
    assert any("1-модда" in s for s in sarlavhalar)
    assert any("3-модда" in s for s in sarlavhalar)
    # Har modda o'z matni bilan
    uchinchi = next(b for b in bolaklar if "3-модда" in b.sarlavha)
    assert "келишувдир" in uchinchi.matn


def test_oddiy_matn_qonun_deb_hisoblanmaydi():
    assert not qonunmi("Bu oddiy hujjat. Modda haqida gap yo'q.")


def test_hajm_boyicha_bolishda_ustma_ust_bor():
    matn = ". ".join(f"Bu {i}-gap va u yetarlicha uzun bo'lishi kerak" for i in range(200))
    bolaklar = hajm_boyicha_bol(matn)

    assert len(bolaklar) > 1
    # Chegarada ustma-ust: oldingi bo'lakning oxiri keyingisining boshida
    assert all(len(b.matn) <= 2500 for b in bolaklar)


def test_markdown_sarlavhalar_boyicha_bolinadi():
    matn = (
        "# Sarlavha bir\n\n" + "Matn " * 60 + "\n\n## Sarlavha ikki\n\n" + "Boshqa matn " * 60
    )
    bolaklar = bol(matn)

    sarlavhalar = {b.sarlavha for b in bolaklar}
    assert "Sarlavha bir" in sarlavhalar
    assert "Sarlavha ikki" in sarlavhalar


def test_bosh_matn_bolak_bermaydi():
    assert bol("") == []
    assert bol("   ") == []


# --- transliteratsiya --------------------------------------------------------


def test_kirill_lotinga_ogiriladi():
    """Qonun kirillcha, so'rov lotincha — ikkalasi moslashishi kerak."""
    assert transliteratsiya("шартнома") == "shartnoma"
    assert transliteratsiya("меҳнат") == "mehnat"
    assert transliteratsiya("модда") == "modda"
    # Lotincha matn o'zgarmaydi
    assert transliteratsiya("shartnoma") == "shartnoma"


def test_tokenlashda_kirill_lotin_bir_xil():
    """Bir xil so'z ikki alifboda bir xil tokenga tushadi."""
    from bilim.qidiruv import _tokenla

    assert _tokenla("Меҳнат шартномаси") == _tokenla("Mehnat shartnomasi")
    assert _tokenla("шартнома") == ["shartnoma"]


def test_savol_sozlari_tashlanadi():
    from bilim.qidiruv import _tokenla

    tokenlar = _tokenla("Bu qanday va qachon bo'ladi?")
    assert "qanday" not in tokenlar
    assert "qachon" not in tokenlar


# --- papka izolyatsiyasi -----------------------------------------------------


def test_agentlar_birbirining_bazasini_kormaydi():
    """O'zgarmas qoida: agentlar bir-birining bilim bazasini ko'rmaydi."""
    assert AGENT_PAPKALARI["legal-review"] == ["legal", "umumiy"]
    assert AGENT_PAPKALARI["hr-assist"] == ["hr", "umumiy"]

    # Yurist HR papkasini ko'rmaydi va aksincha
    assert "hr" not in AGENT_PAPKALARI["legal-review"]
    assert "legal" not in AGENT_PAPKALARI["hr-assist"]
    assert "marketing" not in AGENT_PAPKALARI["legal-review"]

    # Hamma `umumiy` ni ko'radi — Temurdan tashqari: KP matni faqat
    # sotuv shablonlari va shartlaridan tuzilishi kerak.
    for rol, papkalar in AGENT_PAPKALARI.items():
        if rol == "proposal-builder":
            assert papkalar == ["sales"]
            continue
        assert "umumiy" in papkalar


def test_har_agent_royxatda_bor():
    from app.agentlar import AGENT_KLASSLARI

    for rol in AGENT_KLASSLARI:
        assert rol in AGENT_PAPKALARI, f"{rol} uchun papka belgilanmagan"


# --- kontekst matni ----------------------------------------------------------


def test_kontekst_matnida_manba_va_ogohlantirish():
    from bilim.qidiruv import Topilma

    topilmalar = [
        Topilma(
            matn="173-modda matni",
            hujjat="Mehnat kodeksi",
            sarlavha="173-модда",
            papka="hr",
            tur="qonun",
            ball=1.0,
        )
    ]
    matn = kontekst_matni(topilmalar)

    assert "Mehnat kodeksi, 173-модда" in matn
    assert "173-modda matni" in matn
    # Xotiradan javob berishga qarshi ogohlantirish
    assert "xotirangdan javob berma" in matn


def test_bosh_topilmada_kontekst_yoq():
    assert kontekst_matni([]) == ""


def test_eskirgan_hujjat_belgilanadi():
    from bilim.qidiruv import Topilma

    matn = kontekst_matni(
        [Topilma(matn="x", hujjat="Eski qonun", sarlavha="", papka="legal",
                 tur="qonun", ball=1.0, eskirgan=True)]
    )
    assert "ESKIRGAN" in matn


# --- agentga ulanishi --------------------------------------------------------


@pytest.fixture
def kontrakt():
    return kontraktlarni_yukla()["legal-review"]


@pytest.fixture
async def baza(tmp_path):
    b = Baza(tmp_path / "bilim.db")
    await b.tayyorla()
    return b


def laziz_javob(**ustama):
    malumot = {
        "hujjat_turi": "shartnoma",
        "yurisdiksiya": "O'zbekiston",
        "qaydlar": [
            {
                "band": "4.2",
                "xavf": "yuqori",
                "izoh": "Jarima chegarasiz",
                "tuzatish_taklifi": "Chegara qo'ying",
                "manba_nomi": "Fuqarolik kodeksi, 261-модда",
                "havola": None,
            }
        ],
        "xulosa": "Bitta jiddiy band",
        "aniqlik_kerak": [],
        "yetishmagan_qismlar": [],
        "manba_yoq": False,
    }
    malumot.update(ustama)
    return SoxtaLlm([javob([matn_bloki(json.dumps(malumot, ensure_ascii=False))])])


@pytest.mark.asyncio
async def test_bilim_bazasi_promptga_qoshiladi(kontrakt, baza):
    qidiruv_soxta = soxta_bilim(
        ("Fuqarolik kodeksi, 261-модда", "Неустойка (жарима) деб ...")
    )
    llm = laziz_javob()
    laziz = Yurist(kontrakt=kontrakt, llm=llm, baza=baza, qidiruv_manbasi=qidiruv_soxta)
    k = await laziz.ishla("Jarima bandi qonunga mos keladimi?")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "BILIM BAZASIDAN TOPILDI" in xabar
    assert "Неустойка" in xabar

    # Manba konvertda ko'rinadi
    assert any(m.tur == "bilim" for m in k.manba)
    assert any("261" in m.nom for m in k.manba)
    assert "qonun parchasiga asoslandi" in k.izoh


@pytest.mark.asyncio
async def test_baza_topmasa_ochiq_aytadi(kontrakt, baza):
    """O'zgarmas qoida: topmasa xotiradan javob bermaydi."""
    llm = laziz_javob(manba_yoq=True, qaydlar=[])
    # Standart holda bilim bazasi bo'sh (conftest)
    laziz = Yurist(kontrakt=kontrakt, llm=llm, baza=baza)
    k = await laziz.ishla("Noma'lum masala")

    xabar = llm.chaqiruvlar[0]["messages"][0]["content"]
    assert "TOPILMADI" in xabar
    assert "xotirangdan yozma" in xabar

    assert k.ishonch is Ishonch.PAST
    assert "qonun manbasi topilmadi" in k.izoh


@pytest.mark.asyncio
async def test_promptda_modda_talabi_bor(kontrakt):
    from app.agentlar.yurist import TIZIM_PROMPT

    assert "BILIM BAZASI" in TIZIM_PROMPT
    assert "XOTIRANGDAN qonun moddasi raqamini YOZMAYSAN" in TIZIM_PROMPT


# --- vault papkalari to'g'ri bo'limga tushadi ---------------------------------
#
# Avval butun vault `umumiy` ga tushardi. Natijada Rustamdan ventilyatsiya
# normasi so'ralganda unga RAQOBATCHILAR tahlili chiqardi, Temur esa
# vaultdagi mijoz portretlarini umuman ko'rmasdi.


def test_vault_papkalari_bolimlarga_taqsimlangan():
    from bilim.indeks import VAULT_XARITASI

    assert VAULT_XARITASI["04-Raqobat"] == "market"
    assert VAULT_XARITASI["02-Mahsulotlar"] == "product"
    assert VAULT_XARITASI["05-Mijozlar"] == "sales"
    assert VAULT_XARITASI["06-Strategiya"] == "marketing"
    # Kompaniya profili hammaga kerak
    assert VAULT_XARITASI["01-Kompaniya"] == "umumiy"


def test_notanish_vault_papkasi_yoqolmaydi(tmp_path, monkeypatch):
    """Vaultga yangi papka qo'shilsa, u indeksdan tushib qolmasligi kerak."""
    from app.config import sozlama
    from bilim.indeks import papkalar

    vault = tmp_path / "vault"
    (vault / "07-Yangi bolim").mkdir(parents=True)
    (vault / "04-Raqobat").mkdir()
    bilim = tmp_path / "knowledge"
    for b in ("umumiy", "market"):
        (bilim / b).mkdir(parents=True)

    s = sozlama()
    monkeypatch.setattr(s, "vault_yoli", str(vault), raising=False)
    monkeypatch.setattr(s, "bilim_yoli", str(bilim), raising=False)

    natija = papkalar()
    nomlar = {b: [y.name for y in yollar] for b, yollar in natija.items()}

    assert "04-Raqobat" in nomlar["market"]
    assert "07-Yangi bolim" in nomlar["umumiy"], "notanish papka yo'qolib ketdi"


def test_vault_ildizi_ikki_marta_oqilmaydi(tmp_path, monkeypatch):
    """Ildiz yo'li `rglob` bilan qo'shilsa, har hujjat ikki marta tushardi."""
    from app.config import sozlama
    from bilim.indeks import fayllar, papkalar

    vault = tmp_path / "vault"
    (vault / "04-Raqobat").mkdir(parents=True)
    (vault / "04-Raqobat" / "raqib.md").write_text("matn", encoding="utf-8")
    (vault / "README.md").write_text("matn", encoding="utf-8")
    bilim = tmp_path / "knowledge"
    for b in ("umumiy", "market"):
        (bilim / b).mkdir(parents=True)

    s = sozlama()
    monkeypatch.setattr(s, "vault_yoli", str(vault), raising=False)
    monkeypatch.setattr(s, "bilim_yoli", str(bilim), raising=False)

    natija = papkalar()
    umumiy = fayllar(natija["umumiy"])
    market = fayllar(natija["market"])

    assert [f.name for f in umumiy] == ["README.md"]
    assert [f.name for f in market] == ["raqib.md"]


def test_bekzod_bozor_va_pozitsiyalashni_koradi():
    """Savdo yondashuvi mijoz + bozor + pozitsiyalashsiz tuzilmaydi."""
    from bilim.qidiruv import AGENT_PAPKALARI

    papkalar = set(AGENT_PAPKALARI["sales-strategy"])
    assert {"sales", "market", "marketing"} <= papkalar


def test_indeks_yangilansa_qidiruv_keshi_eskiradi():
    """Bot qayta ishga tushmasdan yangi hujjatni ko'rishi kerak."""
    from bilim.qidiruv import Qidiruv

    class SoxtaIndeks:
        def __init__(self):
            self.v = (1, "2026-09-15T10:00:00", 0, 10)
            self.yuklandi = 0

        def versiya(self):
            return self.v

        def bolaklar(self, papkalar):
            self.yuklandi += 1
            return []

    indeks = SoxtaIndeks()
    q = Qidiruv(indeks)

    q._yukla(["normativ"])
    q._yukla(["normativ"])
    assert indeks.yuklandi == 1          # o'zgarmagan — keshdan

    indeks.v = (2, "2026-09-15T11:00:00", 0, 24)   # vaultga hujjat qo'shildi
    q._yukla(["normativ"])
    assert indeks.yuklandi == 2          # qayta o'qildi


def test_normativ_hujjatlar_hisob_va_montajga_ochiq():
    """SHNQ/QMQ (vault `08-Normativ`) — alohida bo'lim, hammaga emas.

    `umumiy` ga tushsa marketing va raqobat agentlariga ham chiqardi.
    """
    from app.config import sozlama
    from bilim.indeks import VAULT_XARITASI
    from bilim.qidiruv import AGENT_PAPKALARI

    assert VAULT_XARITASI["08-Normativ"] == "normativ"
    # Bo'limlar ro'yxatida bo'lmasa indekslanmaydi.
    assert "normativ" in sozlama().bilim_bolimlari
    assert "normativ" in AGENT_PAPKALARI["hvac-calc"]
    assert "normativ" in AGENT_PAPKALARI["montaj-guide"]
    for rol in ("marketing", "smm-analyst", "competitor-watch", "proposal-builder"):
        assert "normativ" not in AGENT_PAPKALARI[rol]


# --- embedding modelini almashtirish ------------------------------------------
#
# E5 oilasi PREFIKS talab qiladi («passage:» / «query:»). Prefikssiz
# sifat sezilarli pasayadi, lekin xato BERMAYDI — ya'ni jimgina yomon
# ishlaydi. Shuning uchun test bilan qo'riqlanadi.


def test_e5_modelida_prefiks_qoyiladi(monkeypatch):
    from types import SimpleNamespace

    from bilim import indeks as indeks_moduli

    monkeypatch.setattr(
        indeks_moduli, "sozlama",
        lambda: SimpleNamespace(bilim_model="intfloat/multilingual-e5-large"))

    assert indeks_moduli._prefiksli(["salom"], "passage") == ["passage: salom"]
    assert indeks_moduli._prefiksli(["salom"], "query") == ["query: salom"]


def test_boshqa_modelga_prefiks_QOYILMAYDI(monkeypatch):
    """Prefiks E5 dan boshqasiga oddiy matn bo'lib tushadi va vektorni buzadi."""
    from types import SimpleNamespace

    from bilim import indeks as indeks_moduli

    monkeypatch.setattr(
        indeks_moduli, "sozlama",
        lambda: SimpleNamespace(
            bilim_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"))

    assert indeks_moduli._prefiksli(["salom"], "passage") == ["salom"]
    assert indeks_moduli._prefiksli(["salom"], "query") == ["salom"]


def test_hujjat_va_savol_BOSHQACHA_vektorlanadi(monkeypatch):
    """Indekslash «passage», qidiruv «query» ishlatishi shart."""
    import inspect
    import pathlib

    from bilim import indeks as indeks_moduli

    # Manba FAYLDAN o'qiladi, atributdan emas: boshqa testlar
    # `Qidiruv.qidir` ni soxta funksiya bilan almashtiradi.
    manba = pathlib.Path(indeks_moduli.__file__).with_name("qidiruv.py")
    assert 'tur="query"' in manba.read_text(encoding="utf-8")

    # Indekslash sukut bo'yicha «passage» — `vektorla` imzosiga qaraladi.
    imzo = inspect.signature(indeks_moduli.vektorla)
    assert imzo.parameters["tur"].default == "passage"


@pytest.mark.haqiqiy_bilim
def test_olcham_mos_kelmasa_qidiruv_YIQILMAYDI(monkeypatch, tmp_path):
    """Model almashib, indeks qayta qurilmasa — BM25 ishlayversin.

    Eng yomon holat: eski 384 o'lchamli vektorlarga yangi 1024
    o'lchamli savol ko'paytirilishi. Bu yo xato beradi, yo ma'nosiz
    ball chiqaradi — ikkalasi ham jim halokat.
    """
    import importlib

    import numpy as np

    from rank_bm25 import BM25Okapi

    qidiruv_moduli = importlib.import_module("bilim.qidiruv")
    q = qidiruv_moduli.Qidiruv.__new__(qidiruv_moduli.Qidiruv)
    # Qidirilayotgan so'z FAQAT bitta bo'lakda bo'lsin. BM25 ballari
    # nisbiy: so'z korpusning yarmida uchrasa IDF nolga teng bo'lib,
    # ball ham nol chiqadi. Shuning uchun uchta bo'lak kerak.
    bolaklar = [
        {"matn": "ventilyatsiya hisobi", "nomi": "H", "yol": "/H.md",
         "sarlavha": "", "papka": "umumiy", "tur": "matn", "eskirgan": 0},
        {"matn": "buxgalteriya hisoboti", "nomi": "B", "yol": "/B.md",
         "sarlavha": "", "papka": "umumiy", "tur": "matn", "eskirgan": 0},
        {"matn": "kadrlar boshqaruvi", "nomi": "K", "yol": "/K.md",
         "sarlavha": "", "papka": "umumiy", "tur": "matn", "eskirgan": 0},
    ]
    # Indeksda 384, modeldan 1024 keladi.
    bm25 = BM25Okapi([qidiruv_moduli._tokenla(b["matn"]) for b in bolaklar])
    q._kesh = {("umumiy",): (bolaklar, np.zeros((3, 384), dtype=np.float32), bm25)}
    q.indeks = None

    monkeypatch.setattr(qidiruv_moduli, "vektorla",
                        lambda m, tur="passage": np.zeros((1, 1024), dtype=np.float32))

    # Semantik qism o'tkazib yuboriladi, AMMO BM25 topishi shart —
    # aks holda qidiruv jimgina bo'sh javob berardi.
    natija = q.qidir("ventilyatsiya", ["umumiy"], chek=3)
    assert [t.hujjat for t in natija] == ["H"], "BM25 ham ishlamay qoldi"


def test_ARALASH_olchamli_indeks_qidiruvni_yiqitmaydi(monkeypatch):
    """Qayta qurish paytida bazada ikki xil o'lcham bo'ladi.

    Uch soat davom etadigan migratsiya vaqtida eski (384) va yangi
    (1024) vektorlar bir vaqtda turadi. `np.array` ularni bitta
    massivga yig'a olmaydi — himoyasiz qidiruv butunlay yiqilardi.
    """
    import importlib

    import numpy as np

    qidiruv_moduli = importlib.import_module("bilim.qidiruv")
    q = qidiruv_moduli.Qidiruv.__new__(qidiruv_moduli.Qidiruv)
    q._kesh = {}

    def bolak(matn, olcham):
        return {"matn": matn, "nomi": "H", "sarlavha": "", "papka": "umumiy",
                "tur": "matn", "eskirgan": 0,
                "vektor": np.zeros(olcham, dtype=np.float32).tobytes()}

    class SoxtaIndeks:
        def bolaklar(self, papkalar):
            # Ikkitasi yangi o'lchamda, bittasi eski — aralash holat.
            return [bolak("yangi bir", 1024), bolak("yangi ikki", 1024),
                    bolak("eski", 384)]

    q.indeks = SoxtaIndeks()

    bolaklar, vektorlar, _ = q._yukla(["umumiy"])

    assert vektorlar.shape == (2, 1024), "ko'pchilik o'lcham olinmadi"
    assert len(bolaklar) == 2


def _cheklov_qidiruvi(monkeypatch, hujjatlar):
    """Semantik qism o'chirilgan, BM25 o'rniga qo'lda ball beriladigan qidiruv.

    `hujjatlar` — bo'laklarning hujjat nomlari, ball tartibida.
    """
    import importlib

    import numpy as np

    moduli = importlib.import_module("bilim.qidiruv")
    q = moduli.Qidiruv.__new__(moduli.Qidiruv)
    bolaklar = [
        {"matn": f"matn {i}", "nomi": nom, "yol": f"/{nom}.md", "sarlavha": "",
         "papka": "product", "tur": "matn", "eskirgan": 0}
        for i, nom in enumerate(hujjatlar)
    ]

    class SoxtaBm25:
        def get_scores(self, tokenlar):
            # Birinchi bo'lak eng yuqori ball — ro'yxat tartibi saqlanadi.
            return np.array([len(bolaklar) - i for i in range(len(bolaklar))],
                            dtype=np.float64)

    q._kesh = {("product",): (bolaklar, np.zeros((len(bolaklar), 8),
                                                 dtype=np.float32), SoxtaBm25())}
    q.indeks = None
    # Semantik qism o'chadi: o'lcham ataylab mos kelmaydi.
    monkeypatch.setattr(moduli, "vektorla",
                        lambda m, tur="passage": np.zeros((1, 1024), dtype=np.float32))
    return q


@pytest.mark.haqiqiy_bilim
def test_bitta_hujjat_butun_javobni_EGALLAMAYDI(monkeypatch):
    """Bir hujjatning uch bo'lagi uchala o'rinni olib qo'ymasin.

    O'LCHANGAN muammo: «Шум от вентиляции» so'roviga «ВКПП»
    hujjatining uchala bo'lagi chiqib, shovqin bostirgich hujjati
    javobdan butunlay siqib chiqarilgandi. Agentga bitta manba
    yetib borardi — uch xil manba o'rniga.
    """
    q = _cheklov_qidiruvi(monkeypatch, ["A", "A", "A", "B", "C"])

    natija = q.qidir("shovqin", ["product"], chek=3)

    nomlar = [t.hujjat for t in natija]
    assert nomlar.count("A") <= 2, f"bitta hujjat cheklovdan oshdi: {nomlar}"
    assert "B" in nomlar, f"boshqa hujjat siqib chiqarildi: {nomlar}"


@pytest.mark.haqiqiy_bilim
def test_cheklov_javob_SONINI_KAMAYTIRMAYDI(monkeypatch):
    """Faqat bitta hujjat mos kelsa, javob baribir to'liq bo'lsin.

    Cheklov chetga surganlar TASHLANMAYDI — joy qolsa qaytariladi.
    Aks holda bitta hujjatga tegishli savol 5 o'rniga 2 parcha
    olardi va agent kontekstsiz qolardi.
    """
    q = _cheklov_qidiruvi(monkeypatch, ["A", "A", "A", "A", "A"])

    natija = q.qidir("shovqin", ["product"], chek=4)

    assert len(natija) == 4, "cheklov javob sonini kamaytirdi"
    assert all(t.hujjat == "A" for t in natija)


@pytest.mark.haqiqiy_bilim
def test_cheklovda_ball_TARTIBI_saqlanadi(monkeypatch):
    """Chetga surilgan parcha oxiriga tushsin, o'rtaga emas."""
    q = _cheklov_qidiruvi(monkeypatch, ["A", "A", "A", "B"])

    natija = q.qidir("shovqin", ["product"], chek=4)

    # A, A, B — keyin chetga surilgan uchinchi A.
    assert [t.hujjat for t in natija] == ["A", "A", "B", "A"]
