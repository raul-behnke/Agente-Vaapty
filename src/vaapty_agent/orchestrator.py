"""Núcleo do turno: preempção por contactId → updater → dispatch → responder → envio → terminal."""
from __future__ import annotations

import asyncio
import random

from .agent.responder import run_responder
from .agent.schemas import (
    TERMINAL_REASONS,
    compute_missing,
    is_qualified,
    merge_into_state,
)
from .agent.updater import run_updater
from .business_hours import is_business_hours
from .config import settings
from .db import session_repo
from .ghl.conversations import get_messages, search_conversations, send_message
from .logging import get_logger
from .metrics import TURNS
from .tools.calendar import book_appointment, propose_slots
from .tools.handoff import encaminhar_para_vendedor
from .tools.price_guard import scrub_bubbles

log = get_logger("orchestrator")

# Preempção: 1 task viva por contato. Nova mensagem cancela a anterior.
_TASKS: dict[str, asyncio.Task] = {}


def process_turn(contact_id: str, last_message: str) -> None:
    """Fire-and-forget com preempção. Cancela turno em andamento do mesmo contato."""
    old = _TASKS.get(contact_id)
    if old and not old.done():
        old.cancel()
    task = asyncio.create_task(_run_turn(contact_id, last_message), name=f"turn:{contact_id}")
    _TASKS[contact_id] = task
    task.add_done_callback(lambda t: _TASKS.pop(contact_id, None))


async def _fetch_history(contact_id: str) -> tuple[list[dict], str | None]:
    convs = await search_conversations(contact_id)
    if not convs:
        return [], None
    conv_id = convs[0].get("id")
    msgs = await get_messages(conv_id, limit=settings.conversation_history_limit)
    return msgs, conv_id


async def _run_turn(contact_id: str, last_message: str) -> None:
    try:
        await _run_turn_inner(contact_id, last_message)
    except asyncio.CancelledError:
        log.info("turn_preempted", contact_id=contact_id)
        raise
    except Exception as exc:
        log.error("turn_failed", contact_id=contact_id, error=str(exc))
        TURNS.labels(outcome="error").inc()
        state = await session_repo.load_or_new(contact_id)
        await encaminhar_para_vendedor(
            contact_id=contact_id, state=state, terminal_reason="handoff_erro",
            handoff_reason=str(exc),
        )


async def _run_turn_inner(contact_id: str, last_message: str) -> None:
    state = await session_repo.load_or_new(contact_id)
    if state.get("terminal_reason") in TERMINAL_REASONS:
        log.info("turn_skipped_terminal", contact_id=contact_id)
        return

    history, conv_id = await _fetch_history(contact_id)
    if conv_id:
        state["conversation_id"] = conv_id

    # 1) updater
    update = await run_updater(history, state, last_message)
    state = merge_into_state(state, update)
    collected = state.get("collected") or {}
    missing = compute_missing(collected)

    # 2) dispatch determinístico — decide terminal/handoff/agendamento ANTES do responder
    terminal_reason = _decide_terminal(state, update, missing)

    if terminal_reason and terminal_reason != "qualificado_agendado":
        # caminhos não-conversacionais (desqualificado / handoff): manda 1 bolha e encerra
        bubble = _terminal_bubble(terminal_reason)
        await _finalize(contact_id, state, conv_id, [bubble], terminal_reason, update.handoff_reason)
        return

    # 3) caminho fora-horário: tenta agendamento na agenda dos negociadores
    appointment_note = None
    if terminal_reason is None and is_qualified(state) and not is_business_hours():
        appointment_note = await _try_booking(contact_id, collected)
        if appointment_note:
            state["appointment"] = appointment_note
            terminal_reason = "qualificado_agendado"

    # 4) responder (Agno) — turno conversacional
    context = _build_context(state, missing, last_message, appointment_note)
    seq = await run_responder(context=context, session_id=contact_id)
    bubbles = scrub_bubbles(seq.bubbles)  # guardrail de preço (camada C)

    # 5) terminal qualificado dentro do horário: agente PARA antes de agendar (spec §5)
    if terminal_reason is None and is_qualified(state) and is_business_hours():
        terminal_reason = "qualificado"

    await _finalize(contact_id, state, conv_id, bubbles, terminal_reason, update.handoff_reason)


def _decide_terminal(state: dict, update, missing: list[str]) -> str | None:
    proposed = state.get("proposed_terminal")
    counters = state.get("counters") or {}

    # humano: escala só em insistência (spec §2 item 9 / §8 item 17 a confirmar)
    if state.get("wants_human") and counters.get("human_asks", 0) >= settings.human_request_threshold:
        return "handoff_solicitado"
    if proposed == "handoff_solicitado":
        return "handoff_solicitado"
    if proposed == "desqualificado" or state.get("out_of_scope"):
        return "desqualificado"
    return None


def _terminal_bubble(terminal_reason: str) -> str:
    if terminal_reason == "desqualificado":
        return (
            "Pelo que entendi não é bem o que a gente faz aqui — a Vaapty ajuda quem quer "
            "vender o carro. Qualquer coisa é só chamar. 🙌"
        )
    # handoff_solicitado
    return "Claro! Já estou chamando alguém da equipe pra te atender por aqui. 👍"


def _build_context(state: dict, missing: list[str], last_message: str, appointment_note) -> str:
    c = state.get("collected") or {}
    parts = [
        f"Última mensagem do lead: {last_message}",
        f"Dados já coletados: {c}",
        f"Faltam coletar (ordem de prioridade): {missing}",
    ]
    if appointment_note:
        parts.append(
            f"Já foi pré-agendada uma avaliação ({appointment_note}). Confirme com simpatia."
        )
    elif not missing:
        parts.append("Triagem completa. Agradeça e diga que a equipe dá sequência.")
    else:
        parts.append(f"Faça UMA pergunta para coletar: {missing[0]}.")
    return "\n".join(parts)


async def _try_booking(contact_id: str, collected: dict) -> str | None:
    slots = await propose_slots(limit=1)
    if not slots:
        return None
    slot = slots[0]
    try:
        await book_appointment(
            contact_id=contact_id, slot=slot,
            lead_name=collected.get("nome") or "", modelo=collected.get("veiculo_modelo") or "",
        )
        return slot.label_pt()
    except Exception as exc:
        log.warning("booking_failed", contact_id=contact_id, error=str(exc))
        return None


async def _send_bubbles(contact_id: str, conv_id: str | None, bubbles: list[str]) -> None:
    for i, b in enumerate(bubbles):
        if not b.strip():
            continue
        await send_message(contact_id=contact_id, message=b, conversation_id=conv_id)
        if i < len(bubbles) - 1:
            await asyncio.sleep(
                random.uniform(settings.responder_sleep_min, settings.responder_sleep_max)
            )


async def _finalize(
    contact_id: str, state: dict, conv_id: str | None, bubbles: list[str],
    terminal_reason: str | None, handoff_reason: str | None,
) -> None:
    # envio é blindado contra preempção (não cancela no meio)
    await asyncio.shield(_send_bubbles(contact_id, conv_id, bubbles))

    if terminal_reason:
        state["terminal_reason"] = terminal_reason
        await encaminhar_para_vendedor(
            contact_id=contact_id, state=state,
            terminal_reason=terminal_reason, handoff_reason=handoff_reason,
        )
        TURNS.labels(outcome=terminal_reason).inc()
    else:
        TURNS.labels(outcome="continue").inc()

    await session_repo.save(contact_id, state)
