"""Guardrail de preço (camada C): filtro regex pré-envio. NUNCA deixar valor passar.

Camadas (spec §2 item 9):
  (a) system prompt proíbe   -> prompts/responder_persona.py
  (b) detector de intenção   -> updater StateUpdate.asked_price
  (c) filtro regex pré-envio -> ESTE módulo
"""
from __future__ import annotations

import re

from ..metrics import PRICE_GUARD_HITS

# R$ 12.345,67 | 12 mil | 50k | "vinte mil" (subset) | percentuais de comissão
_PATTERNS = [
    re.compile(r"r\$\s*\d", re.IGNORECASE),
    re.compile(r"\b\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?\b"),       # 12.000 / 12 000
    re.compile(r"\b\d+\s*mil\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*k\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s*%", re.IGNORECASE),                # comissão %
    re.compile(r"\bvale\s+(?:cerca|em torno|uns|aproximadamente)", re.IGNORECASE),
]

# Frase de deflexão. TODO: substituir pelo script VAPT oficial (§8 item 2).
DEFLECTION = (
    "Sobre valores, a avaliação é feita pela nossa equipe depois que eu finalizo seu "
    "cadastro — assim você recebe um número certo, não um chute. Posso seguir com os dados?"
)


def has_price(text: str) -> bool:
    return any(p.search(text) for p in _PATTERNS)


def scrub_bubble(text: str) -> str:
    """Se a bolha contém valor, substitui inteira pela deflexão."""
    if has_price(text):
        PRICE_GUARD_HITS.inc()
        return DEFLECTION
    return text


def scrub_bubbles(bubbles: list[str]) -> list[str]:
    out, deflected = [], False
    for b in bubbles:
        if has_price(b):
            if not deflected:
                out.append(DEFLECTION)
                deflected = True
                PRICE_GUARD_HITS.inc()
            # demais bolhas com preço são descartadas
        else:
            out.append(b)
    return out or [DEFLECTION]
