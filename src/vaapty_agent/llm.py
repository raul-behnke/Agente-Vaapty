"""Cliente OpenAI cru: parse estruturado (updater) + texto livre."""
from __future__ import annotations

import time
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from .config import settings
from .metrics import LLM_LATENCY

T = TypeVar("T", bound=BaseModel)

_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def parse_structured(
    *,
    model: str,
    schema: type[T],
    system: str,
    user: str,
    role: str = "updater",
    temperature: float = 0.0,
) -> T:
    """Structured output via beta.chat.completions.parse. Levanta se houver refusal."""
    t0 = time.perf_counter()
    try:
        completion = await get_openai().beta.chat.completions.parse(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=schema,
        )
    finally:
        LLM_LATENCY.labels(role=role).observe(time.perf_counter() - t0)

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError(f"LLM refusal/empty parse (role={role})")
    return parsed


async def chat_text(
    *,
    model: str,
    system: str,
    user: str,
    role: str = "responder",
    temperature: float = 0.4,
) -> str:
    t0 = time.perf_counter()
    try:
        completion = await get_openai().chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    finally:
        LLM_LATENCY.labels(role=role).observe(time.perf_counter() - t0)
    return (completion.choices[0].message.content or "").strip()
