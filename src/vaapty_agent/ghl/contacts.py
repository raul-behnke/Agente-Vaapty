"""Operações de contato no GHL."""
from __future__ import annotations

from typing import Any

from ..config import settings
from .client import get_client


async def get_contact(contact_id: str) -> dict:
    d = await get_client().get(f"/contacts/{contact_id}", operation="get_contact")
    return d.get("contact", d)


async def update_contact(contact_id: str, payload: dict) -> dict:
    return await get_client().put(
        f"/contacts/{contact_id}", operation="update_contact", json=payload
    )


async def update_custom_field(contact_id: str, field_id: str, value: Any) -> dict:
    return await update_contact(contact_id, {"customFields": [{"id": field_id, "value": value}]})


async def add_note(contact_id: str, body: str) -> dict:
    return await get_client().post(
        f"/contacts/{contact_id}/notes", operation="add_note", json={"body": body}
    )


async def add_tag(contact_id: str, tags: list[str]) -> dict:
    return await get_client().post(
        f"/contacts/{contact_id}/tags", operation="add_tag", json={"tags": tags}
    )


async def remove_tag(contact_id: str, tags: list[str]) -> dict:
    return await get_client().delete(
        f"/contacts/{contact_id}/tags", operation="remove_tag", json={"tags": tags}
    )


def read_custom_field_value(contact: dict, field_id: str) -> Any | None:
    for f in contact.get("customFields", []) or []:
        if f.get("id") == field_id:
            return f.get("value")
    return None


def has_tag(contact: dict, tag: str) -> bool:
    tags = contact.get("tags", []) or []
    return tag.lower() in {str(t).lower() for t in tags}


def contact_location(contact: dict) -> str | None:
    """Localização declarada: custom field localizacao, senão city do contato."""
    val = read_custom_field_value(contact, settings.cf_localizacao)
    return val or contact.get("city")
