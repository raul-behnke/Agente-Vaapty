#!/usr/bin/env python3
"""Smoke: lê FAQ Custom Value e lista calendars (valida token + conectividade)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vaapty_agent.ghl.client import close_client, get_client  # noqa: E402
from vaapty_agent.ghl.custom_values import extract_value, get_custom_value  # noqa: E402
from vaapty_agent.config import settings  # noqa: E402


async def main() -> None:
    raw = extract_value(await get_custom_value(settings.cv_faq))
    print(f"[faq] {len(raw)} chars do Custom Value FAQ_YAML")
    d = await get_client().get("/calendars/", operation="list", params={"locationId": settings.ghl_location_id})
    for c in d.get("calendars", []):
        print(f"  calendar: {c.get('name')!r} -> {c.get('id')}")
    await close_client()


if __name__ == "__main__":
    asyncio.run(main())
