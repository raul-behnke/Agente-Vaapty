"""Prometheus metrics."""
from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest

TURNS = Counter("vaapty_turns_total", "Turnos processados", ["outcome"])
TERMINALS = Counter("vaapty_terminals_total", "Terminais", ["reason"])
LLM_LATENCY = Histogram("vaapty_llm_latency_seconds", "Latência LLM", ["role"])
GHL_LATENCY = Histogram("vaapty_ghl_latency_seconds", "Latência GHL", ["operation"])
PRICE_GUARD_HITS = Counter("vaapty_price_guard_hits_total", "Bolhas filtradas pelo guardrail de preço")


def render_metrics() -> bytes:
    return generate_latest()
