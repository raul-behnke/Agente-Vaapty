"""Leitura de Custom Values (ex.: FAQ YAML)."""
from __future__ import annotations

from ..config import settings
from .client import get_client


async def get_custom_value(custom_value_id: str) -> dict:
    return await get_client().get(
        f"/locations/{settings.ghl_location_id}/customValues/{custom_value_id}",
        operation="get_custom_value",
    )


def extract_value(payload: dict) -> str:
    cv = payload.get("customValue") or {}
    return cv.get("value", "") or ""
