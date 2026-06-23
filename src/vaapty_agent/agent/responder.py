"""Responder conversacional = Agno Agent. Saída estruturada em bolhas; tool consultar_faq."""
from __future__ import annotations

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools import tool
from pydantic import BaseModel, Field

from ..config import settings
from ..prompts.responder_persona import RESPONDER_PERSONA
from ..tools.faq import consultar_faq as _consultar_faq


class BubbleSequence(BaseModel):
    """Resposta multi-bolha (WhatsApp)."""

    bubbles: list[str] = Field(default_factory=list, description="Bolhas curtas, ordem de envio")


@tool
async def consultar_faq() -> str:
    """Consulta a base de FAQ oficial da Vaapty (YAML). Use SOMENTE este conteúdo p/ dúvidas."""
    return await _consultar_faq()


def build_responder() -> Agent:
    return Agent(
        name="AtendimentoVaapty",
        model=OpenAIChat(id=settings.openai_model_responder, api_key=settings.openai_api_key),
        instructions=[RESPONDER_PERSONA.format(max_bubbles=settings.responder_max_bubbles)],
        tools=[consultar_faq],
        output_schema=BubbleSequence,
        markdown=False,
        telemetry=False,
    )


_responder: Agent | None = None


def get_responder() -> Agent:
    global _responder
    if _responder is None:
        _responder = build_responder()
    return _responder


async def run_responder(*, context: str, session_id: str) -> BubbleSequence:
    agent = get_responder()
    result = await agent.arun(context, session_id=session_id)
    content = result.content
    if isinstance(content, BubbleSequence):
        return content
    # fallback: trata texto cru como 1 bolha
    return BubbleSequence(bubbles=[str(content).strip()] if content else [])
