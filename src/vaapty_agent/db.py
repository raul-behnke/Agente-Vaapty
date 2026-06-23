"""Persistência de sessão por contactId (Postgres, JSONB)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import settings
from .logging import get_logger

log = get_logger("db")

_engine: AsyncEngine | None = None


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _engine


async def ping() -> bool:
    try:
        async with engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover
        log.warning("db_ping_failed", error=str(exc))
        return False


async def init_schema() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS sessions (
        contact_id   TEXT PRIMARY KEY,
        state        JSONB NOT NULL DEFAULT '{}'::jsonb,
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """
    async with engine().begin() as conn:
        await conn.execute(text(ddl))


async def close() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


class SessionRepo:
    """load_or_new / save do estado JSONB por contato."""

    async def load(self, contact_id: str) -> dict[str, Any] | None:
        async with engine().connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT state FROM sessions WHERE contact_id = :cid"),
                    {"cid": contact_id},
                )
            ).first()
        return dict(row[0]) if row else None

    async def load_or_new(self, contact_id: str) -> dict[str, Any]:
        existing = await self.load(contact_id)
        if existing is not None:
            return existing
        return {"contact_id": contact_id, "collected": {}, "counters": {}, "terminal_reason": None}

    async def save(self, contact_id: str, state: dict[str, Any]) -> None:
        import json

        async with engine().begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO sessions (contact_id, state, updated_at)
                    VALUES (:cid, CAST(:state AS jsonb), now())
                    ON CONFLICT (contact_id)
                    DO UPDATE SET state = EXCLUDED.state, updated_at = now()
                    """
                ),
                {"cid": contact_id, "state": json.dumps(state, ensure_ascii=False)},
            )


session_repo = SessionRepo()
