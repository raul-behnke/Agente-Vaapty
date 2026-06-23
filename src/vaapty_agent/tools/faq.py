"""FAQ em YAML armazenado num GHL Custom Value (editável no CRM sem deploy)."""
from __future__ import annotations

import time
from typing import Any

import yaml

from ..config import settings
from ..ghl.custom_values import extract_value, get_custom_value
from ..logging import get_logger

log = get_logger("tools.faq")

_cache: dict[str, Any] = {"raw": None, "ts": 0.0}


async def get_faq_raw() -> str:
    now = time.time()
    if _cache["raw"] is not None and (now - _cache["ts"]) < settings.faq_cache_ttl_seconds:
        return _cache["raw"]
    payload = await get_custom_value(settings.cv_faq)
    raw = extract_value(payload)
    _cache["raw"] = raw
    _cache["ts"] = now
    return raw


async def get_faq_parsed() -> dict:
    raw = await get_faq_raw()
    try:
        data = yaml.safe_load(raw) or {}
        return data if isinstance(data, dict) else {"faq": data}
    except yaml.YAMLError as exc:
        log.warning("faq_parse_error", error=str(exc))
        return {}


async def consultar_faq() -> str:
    """Tool Agno: devolve o FAQ bruto (YAML) p/ o agente interpretar. Não inventar fora disso."""
    return await get_faq_raw()
