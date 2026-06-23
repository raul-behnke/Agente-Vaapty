"""Webhook inbound do GHL. Tag-gate + extração de burst + dedup → process_turn."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request

from ..config import settings
from ..ghl.contacts import get_contact, has_tag
from ..ghl.conversations import get_messages, search_conversations
from ..logging import get_logger
from ..orchestrator import process_turn
from ..security import require_secret

log = get_logger("endpoints.inbound")
router = APIRouter()

_RECEIVED_ON = re.compile(r"received on\s*📱?\s*\[?.*?\]?$", re.IGNORECASE | re.MULTILINE)
_QUOTE_PREFIX = re.compile(r"^>.*$", re.MULTILINE)
_VOICE_NOTE = re.compile(r">?\s*voice note\s*<?", re.IGNORECASE)


def _extract_contact_id(payload: dict) -> str | None:
    return (
        payload.get("contact_id")
        or payload.get("contactId")
        or (payload.get("contact") or {}).get("id")
    )


def _payload_tags(payload: dict) -> list[str] | None:
    tags = payload.get("tags")
    if tags is None:
        return None
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    return list(tags)


def _clean_body(text: str) -> str:
    text = _RECEIVED_ON.sub("", text)
    text = _QUOTE_PREFIX.sub("", text)
    text = _VOICE_NOTE.sub("", text)
    return text.strip()


def _is_real_message(m: dict) -> bool:
    # filtra eventos de atividade do GHL (ex.: opportunity-created)
    mtype = (m.get("messageType") or m.get("type") or "").lower()
    return "activity" not in mtype and bool(m.get("body") or m.get("message"))


def _extract_inbound_burst(msgs: list[dict]) -> tuple[str, bool]:
    """Concatena inbound consecutivos desde o último outbound real. Retorna (texto, superseded)."""
    burst: list[str] = []
    superseded = False
    for m in reversed(msgs):
        if not _is_real_message(m):
            continue
        direction = (m.get("direction") or "").lower()
        is_inbound = direction == "inbound" or m.get("inbound") is True
        if is_inbound:
            burst.append(_clean_body(m.get("body") or m.get("message") or ""))
        else:
            # outbound mais novo que o burst → mensagem já respondida
            if not burst:
                superseded = True
            break
    burst.reverse()
    return "\n".join(b for b in burst if b).strip(), superseded


@router.post("/webhook/inbound", dependencies=[Depends(require_secret)])
async def inbound(request: Request) -> dict:
    payload = await request.json()
    contact_id = _extract_contact_id(payload)
    if not contact_id:
        return {"status": "ignored", "reason": "no_contact_id"}

    # tag-gate: agent-ia presente?
    tags = _payload_tags(payload)
    if tags is None:
        contact = await get_contact(contact_id)
        if not has_tag(contact, settings.tag_agent_ia):
            return {"status": "ignored", "reason": "no_gate_tag"}
    elif settings.tag_agent_ia.lower() not in {t.lower() for t in tags}:
        return {"status": "ignored", "reason": "no_gate_tag"}

    # extrai burst da conversa
    convs = await search_conversations(contact_id)
    if not convs:
        return {"status": "ignored", "reason": "no_conversation"}
    msgs = await get_messages(convs[0].get("id"), limit=settings.conversation_history_limit)
    text, superseded = _extract_inbound_burst(msgs)
    if superseded or not text:
        return {"status": "ignored", "reason": "superseded_or_empty"}

    process_turn(contact_id, text)  # fire-and-forget (preempção no orchestrator)
    return {"status": "accepted"}
