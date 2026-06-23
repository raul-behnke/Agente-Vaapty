"""Schemas de qualificação Vaapty + merge de estado."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field
from unidecode import unidecode

from ..config import settings

# Ordem do funil de triagem (spec §2 item 6).
PRIORITY_FIELDS = ["nome", "localizacao", "veiculo_modelo", "veiculo_ano", "motivo_venda"]

TERMINAL_REASONS = {
    "qualificado",
    "qualificado_agendado",
    "desqualificado",
    "handoff_solicitado",
    "handoff_erro",
}


class Collected(BaseModel):
    """Dados coletados do lead (vendedor de carro)."""

    nome: Optional[str] = None
    localizacao: Optional[str] = None          # cidade declarada
    veiculo_modelo: Optional[str] = None
    veiculo_ano: Optional[str] = None
    motivo_venda: Optional[str] = None         # quitar_divida | trocar | investir | outro
    quer_vender: Optional[bool] = None         # tri-state: tem carro p/ vender?


class StateUpdate(BaseModel):
    """Saída estruturada do updater LLM."""

    stage: Literal["saudacao", "triagem", "duvida", "fechamento", "encerrado"] = "triagem"
    collected: Collected = Field(default_factory=Collected)
    sentiment: Literal["positivo", "neutro", "negativo", "hostil"] = "neutro"
    intent: Literal["qualificacao", "duvida", "preco", "humano", "fora_escopo", "spam"] = "qualificacao"
    topics: list[str] = Field(default_factory=list)
    asked_price: bool = False                  # lead perguntou valor neste turno?
    wants_human: bool = False                  # pediu humano explicitamente?
    should_handoff: bool = False
    handoff_reason: Optional[str] = None
    # Terminal: updater pode propor desqualificado/handoff; NUNCA qualificado_agendado.
    terminal_reason: Optional[
        Literal["desqualificado", "handoff_solicitado"]
    ] = None
    out_of_scope: bool = False                 # quer COMPRAR / não é venda de carro


# ── merge ──────────────────────────────────────────────────────────────────

_FILL_ONLY = {"nome", "veiculo_modelo", "veiculo_ano", "motivo_venda", "localizacao"}
_TRISTATE = {"quer_vender"}


def merge_into_state(state: dict, update: StateUpdate) -> dict:
    """Funde StateUpdate no estado persistido. fill-only p/ texto, tri-state p/ bools."""
    collected = dict(state.get("collected") or {})
    new = update.collected.model_dump()

    for k, v in new.items():
        if v is None:
            continue
        if k in _TRISTATE:
            collected[k] = v  # False é dado válido
        elif k in _FILL_ONLY:
            if not collected.get(k):
                collected[k] = v
        else:
            collected[k] = v

    state["collected"] = collected
    state["stage"] = update.stage
    state["sentiment"] = update.sentiment
    state["intent"] = update.intent
    state["topics"] = update.topics
    # counters
    counters = dict(state.get("counters") or {})
    if update.asked_price:
        counters["price_asks"] = counters.get("price_asks", 0) + 1
    if update.wants_human:
        counters["human_asks"] = counters.get("human_asks", 0) + 1
    state["counters"] = counters
    # terminal proposto pelo updater (orchestrator decide qualificado real)
    if update.terminal_reason:
        state["proposed_terminal"] = update.terminal_reason
    state["out_of_scope"] = update.out_of_scope
    state["wants_human"] = update.wants_human
    return state


def compute_missing(collected: dict) -> list[str]:
    return [f for f in PRIORITY_FIELDS if not collected.get(f)]


def is_in_radius(localizacao: str | None) -> bool:
    if not localizacao:
        return False
    norm = unidecode(localizacao).strip().lower()
    return any(city in norm or norm in city for city in settings.qualify_cities_set)


def is_qualified(state: dict) -> bool:
    """Qualifica: no raio E tem carro p/ vender (spec §2 item 7)."""
    c = state.get("collected") or {}
    if state.get("out_of_scope"):
        return False
    if c.get("quer_vender") is False:
        return False
    return is_in_radius(c.get("localizacao")) and bool(c.get("veiculo_modelo"))
