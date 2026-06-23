# Vaapty — Agente de Pré-Atendimento

Qualificação receptiva de leads (vendedores de carro) no WhatsApp, integrada ao
GoHighLevel. Stack: **Agno** + **gpt-4o** + **FastAPI** + **Postgres**.

Spec completa: [`plan/ESPECIFICACAO_MVP.md`](plan/ESPECIFICACAO_MVP.md).

## Arquitetura

```
WhatsApp 5003 → workflow CRM (atribui dono Pré-Vendas + tag agent-ia)
  → POST /webhook/inbound (?secret=)               endpoints/inbound.py
     ├ tag-gate (agent-ia) + burst/dedup            ghl/conversations.py
     └ orchestrator.process_turn (preempção/contato) orchestrator.py
        ├ updater LLM (raw OpenAI .parse)  → StateUpdate   agent/updater.py
        ├ merge_into_state + is_qualified                  agent/schemas.py
        ├ dispatch determinístico (terminal/agenda)        orchestrator.py
        ├ responder = Agno Agent (output_schema bolhas)    agent/responder.py
        ├ guardrail de preço (regex pré-envio)             tools/price_guard.py
        ├ envio blindado (asyncio.shield)                  ghl/conversations.py
        └ terminal: remove tag + status_ia + workflow      tools/handoff.py
```

## Decisões-chave (vs. AMC/Patricia)

- **1 Agno Agent** (sem Team de inventário — Vaapty é venda do carro do lead).
- **Qualifica** se: no raio (Guarulhos/região via `QUALIFY_CITIES`) **E** tem carro p/ vender.
- **Guardrail de preço**: 3 camadas (prompt, detector `asked_price`, regex pré-envio). NUNCA cita valor.
- **Terminal**: remove tag `agent-ia` + seta CF `status_ia` + `add-to-workflow` (diff vs AMC: AMC não setava status field).
- **Horário** (§5): dentro do horário PARA antes de agendar (Pré-Vendas assume); fora do horário tenta agendar nas agendas dos negociadores.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # preencher (IDs já vêm do provision_ghl.py)
python scripts/provision_ghl.py   # garante CFs/tag/CV no GHL
python scripts/smoke_ghl.py       # valida token + conectividade
pytest                            # testes unitários (sem rede)
vaapty-agent                      # sobe FastAPI
```

## Pendências (bloqueadores §8 da spec)

- FAQ preenchido (YAML no Custom Value `FAQ_YAML`) + script de deflexão de preço oficial.
- Persona/tom final (VEG) → `prompts/responder_persona.py`.
- Credencial WABA/API do número 5003 (envio WhatsApp).
- Workflow IDs qualificado/desqualificado + Calendar IDs (no `.env`).
- Definição de "insistência extrema" (limiar `HUMAN_REQUEST_THRESHOLD`).
- Comportamento terminal desqualificado / pedido de humano (§8 itens 16-17).
