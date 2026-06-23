"""add-contact-to-workflow."""
from __future__ import annotations

from .client import get_client


async def add_to_workflow(contact_id: str, workflow_id: str) -> dict:
    return await get_client().post(
        f"/contacts/{contact_id}/workflow/{workflow_id}", operation="add_to_workflow"
    )
