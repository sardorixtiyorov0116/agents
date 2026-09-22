"""Agentlar reyestri."""

from __future__ import annotations

from bilim import Qidiruv
from integrations import ClimaventKlient

from ..baza import Baza
from ..kontraktlar import Kontrakt
from ..llm import Llm
from ..profil import Profil
from .asos import Agent
from .hr_menejeri import HrMenejeri
from .katalog_admin import KatalogAdmin
from .kp_kuzatuvchi import KpKuzatuvchi
from .loyihachi import Loyihachi
from .mahsulot_mutaxassisi import MahsulotMutaxassisi
from .malumot_muhandisi import MalumotMuhandisi
from .marketolog import Marketolog
from .montaj_maslahatchi import MontajMaslahatchi
from .narx_kuzatuvchi import NarxKuzatuvchi
from .raqobat_tahlilchisi import RaqobatTahlilchisi
from .savdo_strategi import SavdoStrategi
from .smm_tahlilchi import SmmTahlilchi
from .tender_kuzatuvchi import TenderKuzatuvchi
from .tijorat_menejeri import TijoratMenejeri
from .yurist import Yurist

# Rol nomi -> agent klassi (kontraktlardagi tartibda).
AGENT_KLASSLARI: dict[str, type[Agent]] = {
    "price-monitor": NarxKuzatuvchi,
    "competitor-watch": RaqobatTahlilchisi,
    "product-spec": MahsulotMutaxassisi,
    "data-query": MalumotMuhandisi,
    "marketing": Marketolog,
    "sales-strategy": SavdoStrategi,
    "proposal-builder": TijoratMenejeri,
    "hr-assist": HrMenejeri,
    "legal-review": Yurist,
    "catalog-admin": KatalogAdmin,
    "tender-watch": TenderKuzatuvchi,
    "montaj-guide": MontajMaslahatchi,
    "smm-analyst": SmmTahlilchi,
    "kp-tracker": KpKuzatuvchi,
    "hvac-calc": Loyihachi,
}


def agent_yasa(
    kontrakt: Kontrakt,
    llm: Llm,
    baza: Baza,
    kompaniya: Profil | None = None,
    api: ClimaventKlient | None = None,
    qidiruv_manbasi: Qidiruv | None = None,
) -> Agent | None:
    """Kontrakt bo'yicha agent nusxasini yasaydi (ulanmagan bo'lsa — None)."""
    klass = AGENT_KLASSLARI.get(kontrakt.rol)
    if klass is None:
        return None
    return klass(
        kontrakt=kontrakt,
        llm=llm,
        baza=baza,
        kompaniya=kompaniya,
        api=api,
        qidiruv_manbasi=qidiruv_manbasi,
    )


__all__ = [
    "Agent",
    "HrMenejeri",
    "KatalogAdmin",
    "MahsulotMutaxassisi",
    "MalumotMuhandisi",
    "Marketolog",
    "NarxKuzatuvchi",
    "RaqobatTahlilchisi",
    "SavdoStrategi",
    "SmmTahlilchi",
    "TenderKuzatuvchi",
    "TijoratMenejeri",
    "Yurist",
    "AGENT_KLASSLARI",
    "agent_yasa",
]
