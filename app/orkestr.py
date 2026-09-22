"""Orkestr — routerning rejasini bajaradi va hamma qadamni logga yozadi.

Router faqat reja tuzadi; bu modul rejani bajaradi:
  - har qadamda mos agentni topadi va ishga soladi,
  - har qadamdan keyin `holat`ni tekshiradi (xato bo'lsa zanjir to'xtaydi),
  - tasdiq kerak bo'lsa `tasdiq_kutilmoqda` bilan to'xtaydi,
  - oldingi agentning konverti keyingisiga input bo'lib uzatiladi.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from bilim import Qidiruv, qidiruv
from integrations import ClimaventKlient
from kp.qol_narx import narx_ajrat

from .agentlar import agent_yasa
from .agentlar.tijorat_menejeri import YANGI_OBYEKT
from .baza import Baza
from .config import sozlama
from .kontraktlar import Kontrakt, reyestr
from .konvert import (
    Holat,
    Konvert,
    aniqlik_kerak_konvert,
    mos_agent_yoq_konvert,
    tizim_javobi_konverti,
    ulanmagan_konvert,
    xato_konvert,
)
from .llm import AnthropicLlm, Llm, llm_xato_matni, tez_llm
from .sarf import rol_bilan
from .profil import Profil, profil
from .router import Reja, RejaQadam, Router, RouterXatosi

# Zanjir shu holatlarda to'xtaydi — keyingi qadamga o'tish ma'nosiz.
# ANIQLIK_KERAK ham shu yerda: agent savol bergan bo'lsa, javobsiz keyingi
# qadamni bajarish noto'g'ri natija beradi.
TOXTATUVCHI = frozenset(
    {Holat.XATO, Holat.TASDIQ_KUTILMOQDA, Holat.ULANMAGAN, Holat.ANIQLIK_KERAK}
)

# Harakatni tasdiq kutib to'xtatgan agentlar: konvertdagi taklif maydoni ->
# tasdiqdan keyin agentga beriladigan kontekst kaliti. Harakat FAQAT shu
# yo'l orqali bajariladi, ya'ni inson "ha" demaguncha hech narsa yozilmaydi.
TAKLIF_MAYDONLARI = {
    "taklif_sql": "tasdiqlangan_sql",      # Doston — bazaga yozish
    "taklif_amal": "tasdiqlangan_amal",    # Nodira — katalogga yozish
    "taklif_holat": "tasdiqlangan_holat",  # Aziza — KP holatini o'zgartirish
}

# Rejani bajarishdan oldin ko'rib chiqadigan ilgak: rad etish sababini
# qaytarsa, zanjir ishga tushmaydi (None — davom etadi).
log = logging.getLogger(__name__)

RejaTekshiruvi = Callable[["Reja"], Awaitable[str | None]]

# Qadam kuzatuvchisi: (agent nomi, konvert). Konvert `None` bo'lsa — qadam
# endi boshlandi; to'ldirilgan bo'lsa — tugadi.
QadamKuzatuvchisi = Callable[[str, "Konvert | None"], Awaitable[None]]


async def _xabar_ber(
    kuzatuvchi: QadamKuzatuvchisi | None, agent: str, konvert: "Konvert | None"
) -> None:
    """Kuzatuvchini chaqiradi. Xatosi zanjirni HECH QACHON to'xtatmaydi —
    bu shunchaki ko'rsatkich, ishning o'zi emas."""
    if kuzatuvchi is None:
        return
    try:
        await kuzatuvchi(agent, konvert)
    except Exception:
        log.debug("qadam kuzatuvchisi xato berdi", exc_info=True)


class QadamIzi(BaseModel):
    """Bitta qadamning logi: qaysi agent chaqirildi, nima kirdi, nima chiqdi."""

    tartib: int
    agent: str
    korinish: str
    vazifa: str
    kirish_kontekst: dict[str, Any] = Field(default_factory=dict)
    konvert: Konvert
    davomiylik_ms: int


class Natija(BaseModel):
    """`/sorov` endpointi qaytaradigan to'liq natija."""

    iz_id: int | None = None
    sorov: str
    reja: Reja | None = None
    qadamlar: list[QadamIzi] = Field(default_factory=list)
    yakuniy: Konvert
    davomiylik_ms: int


class Orkestr:
    def __init__(
        self,
        llm: Llm,
        baza: Baza,
        kontraktlar: dict[str, Kontrakt] | None = None,
        kompaniya: Profil | None = None,
        api: ClimaventKlient | None = None,
        qidiruv_manbasi: Qidiruv | None = None,
    ):
        self.llm = llm
        self.baza = baza
        self.kontraktlar = kontraktlar or reyestr()
        self.kompaniya = kompaniya if kompaniya is not None else profil()
        # Bitta klient — kesh barcha agentlar orasida bo'linadi.
        self.api = api if api is not None else ClimaventKlient()
        # Bilim bazasi qidiruvi — kesh barcha agentlar orasida bo'linadi.
        self.qidiruv = qidiruv_manbasi if qidiruv_manbasi is not None else qidiruv()
        # Reja tuzuvchi ham "rol" hisoblanadi: uning ishi 15 ta nomdan
        # bittasini tanlash, ya'ni yengil — tez modelga o'tkazilishi mumkin.
        self.router = Router(
            llm=self._llm_uchun("router"),
            kontraktlar=self.kontraktlar,
            kompaniya=self.kompaniya,
        )

    def _llm_uchun(self, rol: str) -> Llm:
        """Shu rol qaysi modelda ishlashi kerak.

        `TEZ_ROLLAR_ROYXATI` dagilar arzon/tez modelga o'tadi, qolganlari
        umumiy `LLM_MODEL` da qoladi. Testlardagi soxta LLM da model
        tushunchasi yo'q — u o'zgarishsiz qaytariladi.
        """
        s = sozlama()
        # SEKIN ro'yxati ustun: `*` bo'lsa ham bu rollar qimmat
        # modelda qoladi (`app/config.py` da nega shundayligi yozilgan).
        if rol in s.sekin_rollar:
            return self.llm
        if not s.hamma_rol_tezmi and rol not in s.tez_rollar:
            return self.llm
        # Soxta (test) LLM berilgan bo'lsa — tegilmaydi. Aks holda
        # testlar `.env` dagi sozlamaga qarab tarmoqqa chiqib ketardi.
        if not isinstance(self.llm, AnthropicLlm):
            return self.llm
        return tez_llm(s.tez_modellar, self.llm)

    async def bajar(
        self,
        sorov: str,
        kontekst: dict[str, Any] | None = None,
        reja_tekshiruvi: RejaTekshiruvi | None = None,
        kuzatuvchi: QadamKuzatuvchisi | None = None,
    ) -> Natija:
        """So'rovni bajaradi.

        `reja_tekshiruvi` — reja tuzilgach, bajarishdan OLDIN chaqiriladi.
        Chaqiruvchi rejani ko'rib (masalan foydalanuvchiga xabar berish uchun)
        va kerak bo'lsa rad etib qaytarishi mumkin: sabab qaytarilsa zanjir
        umuman ishga tushmaydi. Bot ruxsatlarni shu yerda tekshiradi.
        """
        boshlandi = time.perf_counter()

        # NARX TAHRIRI — routersiz.
        #
        # "n1 tovarga 12 mln so'm qilib ber" — bu YANGI ish emas, tayyor
        # KP ning tahriri. Router baribir Rustam→Temur zanjirini tuzadi va
        # butun ventilyatsiya hisobi qaytadan ishlaydi: ~15 sekund va bir
        # necha ming token, natija esa o'sha-o'sha. Bu yerda faqat Temur
        # chaqiriladi — u tahrirni MODELSIZ bajaradi (`kp/qol_narx.py`).
        reja = self._narx_tahriri_rejasi(sorov, kontekst)
        if reja is None:
            # 1-3 qadam: router reja tuzadi (niyat -> agent -> xavf tekshiruvi).
            try:
                with rol_bilan("router"):
                    reja = await self.router.reja_tuz(sorov, kontekst)
            except RouterXatosi as xato:
                return await self._yakunla(
                    sorov=sorov,
                    reja=None,
                    qadamlar=[],
                    yakuniy=xato_konvert("router", str(xato)),
                    boshlandi=boshlandi,
                )
            except anthropic.APIError as xato:
                # API yiqilsa ham foydalanuvchi konvert oladi va sabab logga
                # tushadi (500 bo'lib chiqmaydi — nima bo'lganini ko'rsatamiz).
                return await self._yakunla(
                    sorov=sorov,
                    reja=None,
                    qadamlar=[],
                    yakuniy=xato_konvert("router", llm_xato_matni(xato)),
                    boshlandi=boshlandi,
                )

        # Tizim haqidagi savol — router o'zi javob beradi, agent chaqirilmaydi.
        if reja.tizim_savoli and reja.javob.strip():
            return await self._yakunla(
                sorov=sorov,
                reja=reja,
                qadamlar=[],
                yakuniy=tizim_javobi_konverti(reja.javob.strip()),
                boshlandi=boshlandi,
            )

        # Zarur ma'lumot yetishmasa — agentlar chaqirilmaydi, savol qaytadi.
        if reja.aniqlik_kerak and reja.savollar:
            return await self._yakunla(
                sorov=sorov,
                reja=reja,
                qadamlar=[],
                yakuniy=aniqlik_kerak_konvert(reja.savollar, reja.izoh),
                boshlandi=boshlandi,
            )

        if reja.mos_agent_yoq or not reja.qadamlar:
            # Konstruktiv rad etish: taklif bo'lsa, asosiy javob o'sha bo'ladi.
            izoh = reja.taklif.strip() or reja.izoh or "Bu so'rov uchun mos agent topilmadi."
            return await self._yakunla(
                sorov=sorov,
                reja=reja,
                qadamlar=[],
                yakuniy=mos_agent_yoq_konvert(
                    izoh, {"niyat": reja.niyat, "taklif": reja.taklif}
                ),
                boshlandi=boshlandi,
            )

        if reja_tekshiruvi is not None:
            rad_sababi = await reja_tekshiruvi(reja)
            if rad_sababi:
                return await self._yakunla(
                    sorov=sorov,
                    reja=reja,
                    qadamlar=[],
                    yakuniy=xato_konvert("router", rad_sababi, {"niyat": reja.niyat}),
                    boshlandi=boshlandi,
                )

        # Iz shu yerda ochiladi: `yakuniy` bo'sh bo'lgani "hali ishlayapti"
        # degani — panel zanjirni jonli ko'rsatishi uchun.
        iz_id: int | None = None
        try:
            iz_id = await self.baza.iz_boshla(sorov, reja.model_dump(mode="json"))
        except Exception:  # log yozilmasa ham ish davom etadi
            iz_id = None

        # ASL SO'ROV zanjirga uzatiladi.
        #
        # Router har qadam uchun `vazifa` ni QAYTA YOZADI va qisqartirganda
        # muhim ko'rsatma yo'qolishi mumkin. Jonli misol: foydalanuvchi
        # "…ruschada qilib ber" dedi, router Temurga "Tolibjon MCHJ uchun KP
        # tayyorla" deb yozdi va til ko'rsatmasi yo'qoldi — Temur qaytadan
        # so'radi.
        #
        # Shuning uchun agent kerak bo'lganda ASL matnga qaray oladi.
        zanjir_konteksti = dict(kontekst or {})
        zanjir_konteksti["asl_sorov"] = sorov

        # Rejani bajarish (zanjir).
        qadamlar = await self._zanjirni_yurgiz(
            reja, zanjir_konteksti, boshlangich_indeks=0, oldingi=None, iz_id=iz_id,
            kuzatuvchi=kuzatuvchi,
        )
        yakuniy = qadamlar[-1].konvert if qadamlar else xato_konvert(
            "router", "Birorta qadam bajarilmadi"
        )
        return await self._yakunla(
            sorov=sorov,
            reja=reja,
            qadamlar=qadamlar,
            yakuniy=yakuniy,
            boshlandi=boshlandi,
            iz_id=iz_id,
        )

    @staticmethod
    def _narx_tahriri_rejasi(
        sorov: str, kontekst: dict[str, Any] | None
    ) -> Reja | None:
        """Sof narx tahriri bo'lsa — bitta qadamli reja (routersiz).

        Uch shart ham bajarilishi kerak, aks holda `None`:
          1) oxirgi xabarda narx bor ("n1 tovarga 12 mln");
          2) xabarda YANGI obyekt tavsifi yo'q (aks holda bu yangi KP);
          3) `proposal-builder` kontrakti ulangan.

        Tahrirning o'zini Temur bajaradi va u yerda ham model ishtirok
        etmaydi — raqam matndan kod bilan ajratiladi.
        """
        matn = str((kontekst or {}).get("yangi_xabar") or "").strip()
        if not matn:
            return None
        if YANGI_OBYEKT.search(matn) or not narx_ajrat(matn).bormi:
            return None
        return Reja(
            niyat="KP narxini tahrirlash",
            qadamlar=[
                RejaQadam(
                    agent="proposal-builder",
                    vazifa=sorov,
                    tasdiq_kerak=True,
                    tasdiq_sababi="KP mijozga ketadi",
                )
            ],
            izoh="Narx tahriri — router chaqirilmadi.",
        )

    async def _zanjirni_yurgiz(
        self,
        reja: Reja,
        kontekst: dict[str, Any] | None,
        boshlangich_indeks: int,
        oldingi: Konvert | None,
        iz_id: int | None = None,
        oldingi_qadamlar: list[QadamIzi] | None = None,
        kuzatuvchi: QadamKuzatuvchisi | None = None,
    ) -> list[QadamIzi]:
        """Rejaning qadamlarini ketma-ket bajaradi.

        `boshlangich_indeks` — tasdiqdan keyin davom ettirish uchun: allaqachon
        bajarilgan qadamlar qayta ishga tushmaydi.

        `kuzatuvchi` — har qadam boshida va oxirida chaqiriladi. Bot shu orqali
        "Rustam hisoblayapti…" degan xabarni yangilab turadi: zanjir 60-80
        soniya olishi mumkin va jimlik menejerni bezovta qiladi.
        """
        qadamlar: list[QadamIzi] = []
        maks = sozlama().maks_qadam

        # ZANJIR XOTIRASI. Ilgari faqat ENG OXIRGI qadamning natijasi
        # uzatilardi. Rustam → Sardor → Temur zanjirida bu Rustamning
        # hisobini yo'qotardi: Temurga faqat Sardorning javobi yetib
        # borardi, Sardor esa bo'sh qaytarsa — KP umuman tuzilmasdi.
        zanjir_natijalari: dict[str, Any] = {
            oldin.agent: oldin.konvert.natija
            for oldin in (oldingi_qadamlar or [])
            if oldin.konvert.natija
        }

        for tartib, qadam in enumerate(reja.qadamlar[:maks], start=1):
            if tartib <= boshlangich_indeks:
                continue

            kontrakt = self.kontraktlar[qadam.agent]
            qadam_kontekst: dict[str, Any] = dict(kontekst or {})
            if oldingi is not None:
                qadam_kontekst["oldingi_agent"] = oldingi.kim
                qadam_kontekst["oldingi_natija"] = oldingi.natija
            if zanjir_natijalari:
                qadam_kontekst["zanjir_natijalari"] = dict(zanjir_natijalari)

            qadam_boshi = time.perf_counter()
            await _xabar_ber(kuzatuvchi, qadam.agent, None)
            konvert = await self._qadamni_bajar(kontrakt, qadam.vazifa, qadam_kontekst)
            await _xabar_ber(kuzatuvchi, qadam.agent, konvert)

            # Xavf tekshiruvi: tasdiq kerak bo'lsa natija tasdiqsiz chiqmaydi.
            if qadam.tasdiq_kerak and konvert.holat is Holat.TUGADI:
                konvert = konvert.model_copy(
                    update={
                        "holat": Holat.TASDIQ_KUTILMOQDA,
                        "tasdiq_kerak": True,
                        "izoh": " | ".join(
                            filter(None, [konvert.izoh, f"TASDIQ KERAK: {qadam.tasdiq_sababi}"])
                        ),
                    }
                )

            qadamlar.append(
                QadamIzi(
                    tartib=tartib,
                    agent=kontrakt.rol,
                    korinish=kontrakt.korinish,
                    vazifa=qadam.vazifa,
                    kirish_kontekst=qadam_kontekst,
                    konvert=konvert,
                    davomiylik_ms=int((time.perf_counter() - qadam_boshi) * 1000),
                )
            )
            oldingi = konvert
            if konvert.natija:
                zanjir_natijalari[kontrakt.rol] = konvert.natija

            # Jonli ko'rinish: har qadamdan keyin iz yangilanadi.
            if iz_id is not None:
                try:
                    hammasi = (oldingi_qadamlar or []) + qadamlar
                    await self.baza.iz_qadamlarni_yangila(
                        iz_id, [q.model_dump(mode="json") for q in hammasi]
                    )
                except Exception:
                    pass

            # Zanjir qoidalari: xato/ulanmagan -> to'xtaydi; tasdiq -> insonni kutadi.
            if konvert.holat in TOXTATUVCHI:
                break

        return qadamlar

    async def _qadamni_bajar(
        self, kontrakt: Kontrakt, vazifa: str, kontekst: dict[str, Any]
    ) -> Konvert:
        agent = agent_yasa(
            kontrakt, self._llm_uchun(kontrakt.rol), self.baza,
            self.kompaniya, self.api, self.qidiruv,
        )
        if agent is None:
            return ulanmagan_konvert(
                kontrakt.rol,
                f"{kontrakt.korinish} kontrakti mavjud, lekin agent hali kodda ulanmagan. "
                f"Router uni to'g'ri tanladi.",
            )
        try:
            # Rol nomi shu yerda bog'lanadi: LLM qatlami zanjirning
            # tubida turadi va kim chaqirayotganini bilmaydi. Har
            # bosqichga `rol` parametrini o'tkazish har bir agentga
            # tegishni talab qilardi — `ContextVar` esa asyncio ichida
            # o'zi ko'chadi (`app/sarf.py`).
            with rol_bilan(kontrakt.rol):
                return await agent.ishla(vazifa, kontekst)
        except Exception as xato:  # agent buzilsa ham zanjir tushib ketmasin
            return xato_konvert(kontrakt.rol, f"Agent ichki xatosi: {xato!r}")

    async def agentni_chaqir(
        self, rol: str, vazifa: str, kontekst: dict[str, Any] | None = None
    ) -> Konvert:
        """Bitta agentni ROUTERSIZ chaqiradi.

        Rejali ish uchun: qaysi agent kerakligi oldindan ma'lum, router
        chaqiruvi ortiqcha xarajat va noaniqlik qo'shadi. Foydalanuvchi
        so'rovlari baribir `bajar()` orqali, router bilan ketadi.
        """
        kontrakt = self.kontraktlar.get(rol)
        if kontrakt is None:
            return xato_konvert("orkestr", f"Noma'lum agent: {rol}")
        return await self._qadamni_bajar(kontrakt, vazifa, kontekst)

    async def _yakunla(
        self,
        sorov: str,
        reja: Reja | None,
        qadamlar: list[QadamIzi],
        yakuniy: Konvert,
        boshlandi: float,
        iz_id: int | None = None,
    ) -> Natija:
        davomiylik = int((time.perf_counter() - boshlandi) * 1000)
        natija = Natija(
            iz_id=iz_id,
            sorov=sorov,
            reja=reja,
            qadamlar=qadamlar,
            yakuniy=yakuniy,
            davomiylik_ms=davomiylik,
        )
        yozuv = {
            "qadamlar": [q.model_dump(mode="json") for q in qadamlar],
            "yakuniy": yakuniy.model_dump(mode="json"),
            "davomiylik_ms": davomiylik,
            "xato": yakuniy.izoh if yakuniy.holat is Holat.XATO else None,
        }
        try:
            if iz_id is None:
                # Router bosqichida to'xtagan so'rov — iz hali ochilmagan.
                natija.iz_id = await self.baza.iz_yoz(
                    yozuv | {"sorov": sorov, "reja": reja.model_dump(mode="json") if reja else None}
                )
            else:
                await self.baza.iz_yangila(iz_id, yozuv)
        except Exception:  # log yozilmasa ham javob qaytadi
            natija.iz_id = iz_id

        await self._tasdiqni_qayd_et(natija)
        return natija

    async def _tasdiqni_qayd_et(self, natija: Natija) -> None:
        """Zanjir tasdiq kutib to'xtagan bo'lsa — buni bazaga yozadi.

        Xotirada emas, bazada: server qayta ishga tushsa ham kutilayotgan
        tasdiq yo'qolmaydi.
        """
        if natija.yakuniy.holat is not Holat.TASDIQ_KUTILMOQDA or natija.iz_id is None:
            return
        oxirgi = natija.qadamlar[-1] if natija.qadamlar else None
        if oxirgi is None:
            return
        try:
            await self.baza.tasdiq_yoz(
                {
                    "iz_id": natija.iz_id,
                    "qadam_tartib": oxirgi.tartib,
                    "agent": oxirgi.agent,
                    "korinish": oxirgi.korinish,
                    "sorov": natija.sorov,
                    "izoh": natija.yakuniy.izoh,
                }
            )
        except Exception:  # tasdiq yozilmasa ham javob qaytadi
            pass

    # --- tasdiqdan keyin davom ettirish --------------------------------------

    async def davom_ettir(self, iz_id: int, tasdiqlaymi: bool, izoh: str = "") -> Natija:
        """Inson tasdiqlagach (yoki rad etgach) zanjirni yakunlaydi.

        Butun holat bazadan o'qiladi — bu metod so'rovni boshlagan jarayondan
        boshqa jarayonda ham ishlaydi.
        """
        boshlandi = time.perf_counter()

        tasdiq = await self.baza.tasdiq(iz_id)
        if tasdiq is None:
            raise TasdiqXatosi(f"Bu so'rov uchun tasdiq so'ralmagan: iz_id={iz_id}")
        if tasdiq["holat"] != "kutilmoqda":
            raise TasdiqXatosi(
                f"Tasdiq allaqachon hal qilingan: {tasdiq['holat']} ({tasdiq['hal_qilindi']})"
            )

        iz = await self.baza.iz(iz_id)
        if iz is None:
            raise TasdiqXatosi(f"Iz topilmadi: {iz_id}")

        reja = Reja.model_validate(iz["reja"]) if iz.get("reja") else None
        qadamlar = [QadamIzi.model_validate(q) for q in (iz.get("qadamlar") or [])]
        if reja is None or not qadamlar:
            raise TasdiqXatosi(f"Iz to'liq emas, davom ettirib bo'lmaydi: {iz_id}")

        await self.baza.tasdiq_hal_qil(iz_id, tasdiqlaymi, izoh)
        kutgan = qadamlar[-1]

        if not tasdiqlaymi:
            sabab = izoh or "sabab ko'rsatilmadi"
            kutgan.konvert = xato_konvert(
                kutgan.agent,
                f"Inson rad etdi: {sabab}",
                kutgan.konvert.natija,
            )
            return await self._davomni_yakunla(iz_id, iz, reja, qadamlar, boshlandi)

        # Tasdiqlandi: kutayotgan qadamni yakunlaymiz.
        kutgan.konvert = await self._tasdiqlangan_qadam(kutgan, izoh)

        if kutgan.konvert.holat is Holat.TUGADI:
            # Zanjirning qolgan qismi davom etadi.
            qadamlar.extend(
                await self._zanjirni_yurgiz(
                    reja,
                    kontekst=None,
                    boshlangich_indeks=kutgan.tartib,
                    oldingi=kutgan.konvert,
                    iz_id=iz_id,
                    oldingi_qadamlar=qadamlar,
                )
            )

        return await self._davomni_yakunla(iz_id, iz, reja, qadamlar, boshlandi)

    async def _tasdiqlangan_qadam(self, qadam: QadamIzi, izoh: str) -> Konvert:
        """Tasdiqlangan qadamni yakuniy holatga keltiradi.

        Agentlarning ikki xili bor:
          - natijani TAYYORLAB qo'ygan (Malika, Laziz, Hilola, Temur) — tasdiq
            shunchaki natijani ochadi, qayta ishlatish shart emas;
          - harakatni KUTIB turgan (Doston, Nodira) — tasdiqdan keyin harakat
            endi bajariladi.

        Ikkinchi xilini `TAKLIF_MAYDONLARI` aniqlaydi: konvertda shu maydon
        bo'lsa, agent tegishli kontekst bilan QAYTA chaqiriladi va harakat
        aynan shu yerda — inson "ha" degandan keyin — sodir bo'ladi.
        """
        for taklif_maydoni, kontekst_kaliti in TAKLIF_MAYDONLARI.items():
            taklif = qadam.konvert.natija.get(taklif_maydoni)
            if not taklif:
                continue
            kontrakt = self.kontraktlar.get(qadam.agent)
            if kontrakt is None:
                continue
            return await self._qadamni_bajar(
                kontrakt,
                qadam.vazifa,
                {"tasdiqlandi": True, kontekst_kaliti: taklif},
            )

        belgi = f"INSON TASDIQLADI: {izoh}" if izoh else "INSON TASDIQLADI"
        return qadam.konvert.model_copy(
            update={
                "holat": Holat.TUGADI,
                "tasdiq_kerak": False,
                "izoh": " | ".join(filter(None, [qadam.konvert.izoh, belgi])),
            }
        )

    async def _davomni_yakunla(
        self,
        iz_id: int,
        iz: dict[str, Any],
        reja: Reja,
        qadamlar: list[QadamIzi],
        boshlandi: float,
    ) -> Natija:
        yakuniy = qadamlar[-1].konvert
        # Umumiy vaqt: dastlabki ijro + tasdiqdan keyingi davom.
        davomiylik = int(iz.get("davomiylik_ms") or 0) + int(
            (time.perf_counter() - boshlandi) * 1000
        )
        natija = Natija(
            iz_id=iz_id,
            sorov=iz["sorov"],
            reja=reja,
            qadamlar=qadamlar,
            yakuniy=yakuniy,
            davomiylik_ms=davomiylik,
        )
        await self.baza.iz_yangila(
            iz_id,
            {
                "qadamlar": [q.model_dump(mode="json") for q in qadamlar],
                "yakuniy": yakuniy.model_dump(mode="json"),
                "davomiylik_ms": davomiylik,
                "xato": yakuniy.izoh if yakuniy.holat is Holat.XATO else None,
            },
        )
        # Zanjir yana tasdiq kutib to'xtagan bo'lishi mumkin (ko'p bosqichli reja).
        await self._tasdiqni_qayd_et(natija)
        return natija


class TasdiqXatosi(RuntimeError):
    """Tasdiqni davom ettirib bo'lmadi."""
