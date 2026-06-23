"""Updater LLM: histórico + última msg → StateUpdate (structured)."""
from __future__ import annotations

import json

from ..config import settings
from ..llm import parse_structured
from ..prompts.updater_system import UPDATER_SYSTEM
from .schemas import StateUpdate


def _compact_history(history: list[dict], limit: int = 30) -> list[dict]:
    out = []
    for m in history[-limit:]:
        direction = m.get("direction") or ("inbound" if m.get("inbound") else "outbound")
        out.append({"from": direction, "text": (m.get("body") or m.get("message") or "")[:500]})
    return out


async def run_updater(history: list[dict], state: dict, last_message: str) -> StateUpdate:
    user_payload = {
        "session_state": {
            "stage": state.get("stage"),
            "collected": state.get("collected") or {},
            "counters": state.get("counters") or {},
        },
        "history": _compact_history(history),
        "last_message": last_message,
    }
    return await parse_structured(
        model=settings.openai_model_updater,
        schema=StateUpdate,
        system=UPDATER_SYSTEM,
        user=json.dumps(user_payload, ensure_ascii=False),
        role="updater",
        temperature=0.0,
    )
