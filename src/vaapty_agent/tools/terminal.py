"""Formatação do terminal (nota consolidada p/ CRM)."""
from __future__ import annotations


def build_consolidated_note(
    state: dict, terminal_reason: str, handoff_reason: str | None = None
) -> str:
    c = state.get("collected") or {}
    lines = [
        "🤖 Pré-atendimento Vaapty (IA) — resumo",
        f"Status: {terminal_reason}",
        f"Nome: {c.get('nome') or '-'}",
        f"Cidade: {c.get('localizacao') or '-'}",
        f"Veículo: {c.get('veiculo_modelo') or '-'} ({c.get('veiculo_ano') or '-'})",
        f"Motivo da venda: {c.get('motivo_venda') or '-'}",
    ]
    if handoff_reason:
        lines.append(f"Motivo handoff: {handoff_reason}")
    appt = state.get("appointment")
    if appt:
        lines.append(f"Agendamento: {appt}")
    return "\n".join(lines)
