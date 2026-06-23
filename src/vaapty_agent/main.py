"""Entrypoint FastAPI."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from .config import settings
from .db import close as db_close
from .db import init_schema, ping
from .ghl.client import close_client
from .logging import configure_logging, get_logger
from .metrics import render_metrics

configure_logging()
log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if await ping():
        try:
            await init_schema()
        except Exception as exc:  # não fatal
            log.warning("init_schema_failed", error=str(exc))
    else:
        log.warning("db_unavailable_at_startup")
    yield
    await close_client()
    await db_close()


app = FastAPI(title="Vaapty Pré-Atendimento", lifespan=lifespan)

from .endpoints.inbound import router as inbound_router  # noqa: E402

app.include_router(inbound_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "db": await ping()}


@app.get("/metrics")
async def metrics() -> Response:
    if not settings.metrics_enabled:
        return Response(status_code=404)
    return Response(content=render_metrics(), media_type="text/plain")


def run() -> None:
    import uvicorn

    uvicorn.run(
        "vaapty_agent.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,
    )


if __name__ == "__main__":
    run()
