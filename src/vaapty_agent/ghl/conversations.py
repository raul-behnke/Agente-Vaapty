"""Conversas e mensagens GHL (histórico + envio pelo número de entrada)."""
from __future__ import annotations

from ..config import settings
from .client import get_client


async def search_conversations(contact_id: str) -> list[dict]:
    d = await get_client().get(
        "/conversations/search",
        operation="search_conversations",
        params={"locationId": settings.ghl_location_id, "contactId": contact_id},
    )
    return d.get("conversations", []) or []


async def get_messages(conversation_id: str, limit: int = 100) -> list[dict]:
    d = await get_client().get(
        f"/conversations/{conversation_id}/messages",
        operation="get_messages",
        params={"limit": limit},
    )
    # GHL aninha em messages.messages
    msgs = d.get("messages", d)
    if isinstance(msgs, dict):
        msgs = msgs.get("messages", [])
    return msgs or []


async def send_message(
    *,
    contact_id: str,
    message: str | None = None,
    conversation_id: str | None = None,
    attachments: list[str] | None = None,
    message_type: str = "WhatsApp",
) -> dict:
    payload: dict = {
        "type": message_type,
        "contactId": contact_id,
    }
    if conversation_id:
        payload["conversationId"] = conversation_id
    if message:
        payload["message"] = message
    if attachments:
        payload["attachments"] = attachments
    return await get_client().post(
        "/conversations/messages", operation="send_message", json=payload
    )
