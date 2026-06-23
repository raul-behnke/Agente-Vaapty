"""Sequência terminal de handoff (cada passo isolado/tolerante a falha).

Spec §2 item 15 + §8 diff vs AMC:
  1. remove tag agent-ia
  2. set custom field status_ia
  3. add note consolidada
  4. add-to-workflow (qualificado | desqualificado)
"""
from __future__ import annotations

from ..config import settings
from ..ghl.contacts import add_note, remove_tag, update_custom_field
from ..ghl.workflows import add_to_workflow
from ..logging import get_logger
from ..metrics import TERMINALS
from .terminal import build_consolidated_note

log = get_logger("tools.handoff")

# terminal_reason -> (valor status_ia, workflow alvo)
_ROUTING = {
    "qualificado": ("qualificado", settings.workflow_qualificado_id),
    "qualificado_agendado": ("qualificado_agendado", settings.workflow_qualificado_id),
    "desqualificado": ("desqualificado", settings.workflow_desqualificado_id),
    "handoff_solicitado": ("escalado", settings.workflow_qualificado_id),
    "handoff_erro": ("erro", settings.workflow_qualificado_id),
}


async def _safe(step: str, coro):
    try:
        await coro
    except Exception as exc:  # cada passo é isolado
        log.warning("handoff_step_failed", step=step, error=str(exc))


async def encaminhar_para_vendedor(
    *, contact_id: str, state: dict, terminal_reason: str, handoff_reason: str | None = None
) -> None:
    status_value, workflow_id = _ROUTING.get(terminal_reason, ("erro", settings.workflow_qualificado_id))

    await _safe("remove_tag", remove_tag(contact_id, [settings.tag_agent_ia]))
    await _safe("set_status_ia", update_custom_field(contact_id, settings.cf_status_ia, status_value))
    await _safe(
        "add_note",
        add_note(contact_id, build_consolidated_note(state, terminal_reason, handoff_reason)),
    )
    if workflow_id:
        await _safe("add_to_workflow", add_to_workflow(contact_id, workflow_id))
    else:
        log.warning("handoff_no_workflow", terminal_reason=terminal_reason)

    TERMINALS.labels(reason=terminal_reason).inc()
    log.info("handoff_done", contact_id=contact_id, terminal_reason=terminal_reason)
