# Agente de Pré-Atendimento Vaapty — Especificação do MVP

Derivado da call de alinhamento (12/06/2026), do chat de implantação e do grill-me.
Referência de arquitetura: `/Users/raulbehnke/agente-amc/` (agente "Patricia" / zoi_agent).
Stack-alvo: **Agno** (Python) reusando padrões da AMC + **GoHighLevel (GHL)** CRM.

---

## 1. Escopo travado (MVP)

**Apenas frente 1 — Qualificação receptiva.**
Fora do MVP (fase 2): reativação de ativos e resgate de no-shows (são outbound por scheduler, arquitetura distinta).

Fluxo de alto nível:

```
Lead novo (tráfego pago) entra no WhatsApp +55 11 92134-5003
      │  (workflow CRM já distribui dono Pré-Vendas + adiciona tag agent-ia)
      ▼
Webhook GHL inbound ──(filtro tag agent-ia)──▶ Agente Agno
      │
      ├─ lê histórico da conversa (GHL API)
      ├─ updater LLM (gpt-4o)  → atualiza estado de qualificação
      ├─ dispatch tools (FAQ YAML, guardrail preço, calendar*)
      ├─ responder LLM (gpt-4o) → resposta multi-bolha
      ├─ envia via GHL API pelo número de entrada (5003)
      └─ no terminal:
            • remove tag agent-ia  (para de receber)
            • seta custom field status_ia
            • add-contact-to-workflow (CRM envia áudio/vídeo + notifica/distribui)
```

\* Calendar só no caminho fora-horário (ver §5).

---

## 2. Decisões fechadas (grill-me)

| # | Tema | Decisão |
|---|------|---------|
| 1 | Escopo MVP | Só qualificação receptiva |
| 2 | Ordem agente↔CRM | **Opção B** — CRM atribui dono primeiro; agente roda "por baixo" no mesmo contato |
| 3 | Gate de atuação | Tag **`agent-ia`** no contato. Presente → agente responde. Removida → webhook nem chega (filtro no workflow GHL) |
| 4 | Adiciona tag | Workflow CRM de entrada de lead novo |
| 5 | Remove tag | Agente (auto, em todo terminal/escalonamento) **ou** SDR humano (override manual, sempre vence) |
| 6 | Campos de triagem | `nome`, `veiculo_modelo`, `veiculo_ano`, `localizacao`, `quitado` (quitado ou não) |
| 7 | Critério qualifica | Localização no raio (Guarulhos/região) **E** tem carro p/ vender. Fora-raio / quer comprar / spam = desqualifica |
| 8 | FAQ | Conteúdo em **YAML** (GHL Custom Value, editável sem deploy). Agente responde só da base, não inventa, escala se fora |
| 9 | Guardrail preço | NUNCA falar valor. Camadas: (a) system prompt proíbe; (b) detector intenção-preço; (c) filtro regex pré-envio. **Sem escalonamento prematuro** — deflete com script de processo. Escala só em **insistência extrema** (≈3ª cobrança direta ou hostilidade) |
| 10 | Canal de envio | Agente envia pelo número de entrada **+55 11 92134-5003** (tráfego pago), via WABA/API oficial |
| 11 | Identidade | Apresenta-se como **"Atendimento da Vaapty"**. Tom humanizado. Não afirma humano nem IA. Se perguntado direto, responde honesto curto e segue |
| 12 | Mídia (áudio/vídeo Ingrid) | **Não** é o agente que envia. Agente qualifica → add-to-workflow → workflow CRM envia áudio/vídeo |
| 13 | Horário | Agente qualifica **24h**. Comportamento de handoff varia por horário (ver §5) |
| 14 | Papéis | **Pré-Vendas** (Ingrid/Fernanda) = dono do contato + handoff comercial. **Negociadores** (Adriano/Dário) = agenda/agendamento |
| 15 | Handoff terminal | Remove tag + `add-contact-to-workflow` (GHL API) dispara distribuição/notificação/mídia |
| 16 | Modelo LLM | **gpt-4o** (updater + responder) |
| 17 | Persistência | **Postgres** — estado/sessão por `contactId` + preempção (igual AMC) |
| 18 | Calendário | GHL Calendar API: slot livre → book → add-to-workflow |
| 19 | Segurança webhook | **HMAC** `?secret=` (igual AMC) |

---

## 3. Papéis (mapa definitivo)

| Papel CRM | Pessoa | Função no fluxo | Número/contato |
|---|---|---|---|
| Pré-Vendas01 | Ingrid Silva Santos | Dono contato / handoff | +55 11 92134-5028 |
| Pré-Vendas02 | Fernanda C. de Lima Ventura | Dono contato / handoff | — |
| Negociador01 | Adriano Moreti | Agenda (booking) | +55 11 92134-5003 |
| Negociador02 | Dário O. de Santana | Agenda (booking) | — |
| Admin | Camila C. Lima de Souza | — | — |

Distribuição Pré-Vendas (alternância Ingrid/Fernanda) = **CRM**, não o agente.

---

## 4. Horário comercial

| Dia | Janela |
|---|---|
| Seg | 09:00–18:00 |
| Ter | 09:00–18:00 |
| Qua | 09:00–18:00 |
| Qui | 09:00–18:00 |
| Sex | 09:00–18:00 |
| Sáb | 09:00–13:00 |
| Dom | Fechado |

---

## 5. Comportamento por horário (terminal de qualificação)

**Dentro do horário comercial:** (DECIDIDO)
- Agente qualifica e **PARA antes do agendamento** — não oferece horário.
- Terminal `qualificado` → remove tag + status_ia=qualificado + add-to-workflow.
- **Pré-Vendas dono (Ingrid/Fernanda) assume e conduz o agendamento.**

**Fora do horário comercial:**
- Agente qualifica **e tenta o agendamento prévio** (dia/horário) na agenda dos **Negociadores** (Adriano/Dário).
- GHL Calendar API: busca slot livre → `book` → add-to-workflow.
- Se sem vaga: oferece alternativa / "amanhã a equipe te confirma".

---

## 6. Arquitetura técnica (Agno + padrões AMC)

- **Projeto novo Agno** (não fork direto). Port seletivo dos padrões AMC:
  - GHL client (`ghl/client.py`, contacts, workflows, custom_values).
  - Endpoints: `/webhook/inbound`, `/health`, `/metrics` (FastAPI).
  - FAQ YAML loader (Custom Value).
  - Estado/sessão Postgres + preempção por contactId (asyncio.Task table).
  - Terminal/handoff + métricas Prometheus.
- **Core = Agno Agent**: model gpt-4o, instructions, tools (FAQ, calendar, guardrail), structured output (estado de qualificação), session/memory.
- Pipeline 2-LLM (updater extrai estado / responder gera bolhas) — manter padrão AMC.
- **add-contact-to-workflow**: endpoint GHL `POST .../contacts/{id}/workflow/{workflowId}`.

---

## 7. PERTINENTE — já temos para começar

- Arquitetura de referência completa (AMC / zoi_agent) — reuso direto.
- Fluxo, gate (tag `agent-ia`), papéis, campos de triagem, critérios, horários.
- Stack: Agno + gpt-4o + Postgres + GHL API + HMAC.
- Subconta GHL: Location ID `WNX3O0xMtrK6Ls7w4eTx`.
- Número de entrada definido: +55 11 92134-5003.
- Padrão de mídia/distribuição/notificação = workflow CRM (fora do agente).

---

## 8. FALTA SOLICITAR (bloqueadores p/ dev)

### Conteúdo (Vaapty / VEG)
1. **FAQ preenchido** (template → YAML): perguntas respondíveis + lista de "assuntos intocáveis".
2. **Script de deflexão de preço** (texto exato do processo VAPT que o agente fala ao ser questionado sobre valor).
3. **Definição de "insistência extrema"** validada (limiar p/ escalar preço).
4. **Nome/persona final** do agente + tom (VEG).
5. **Scripts** curto/médio/longo prazo + prova social (VEG — prometidos no grupo; conferir Drive 15/06).

### Credenciais / IDs (Vaapty / ZOI)
6. **Calendar IDs** dos negociadores Adriano + Dário (usuário fornecerá em breve) + **duração do slot** + buffer.
7. **Workflow ID(s)** de destino do `add-contact-to-workflow` (qualificado; e variantes desqualificado/escalado se houver).
8. **Custom Field IDs** GHL: `status_ia`, `localizacao`, `veiculo_modelo`, `veiculo_ano`, `quitado`, `nome`.
9. **Custom Value ID** do FAQ YAML.
10. **Token API GHL (PIT)** da subconta + credencial WABA/API oficial do número 5003.
11. **WEBHOOK_SECRET** (HMAC) a definir.
12. **OPENAI_API_KEY** (gpt-4o).

### Definições de negócio a confirmar
13. Texto exato da **saudação inicial** (persona, sem revelar IA).
14. Mensagem de **fora-horário** quando não há slot.
15. **Raio geográfico** preciso de qualificação (lista de cidades/bairros aceitos além de Guarulhos).
16. O que fazer no terminal **desqualificado** (remove tag + tag motivo? notifica? descarta?).
17. Comportamento se cliente **pede humano** explicitamente (escala imediato? em horário?).

### Riscos herdados (chat de implantação)
18. **Desconexões recorrentes** do WhatsApp (5028) e **bug de áudio** — instabilidade do canal pode afetar o agente. Confirmar canal 5003 estável antes do go-live.
19. **Conflito de proprietário de contato** (msg sai como outro número) — validar que Opção B não reincide nesse bug.

---

## 9. Próximo passo sugerido

1. Coletar bloqueadores §8 (itens 6–12 destravam o scaffold).
2. Scaffold do projeto Agno + GHL client + endpoint inbound + estado Postgres.
3. Implementar updater/responder + FAQ YAML + guardrail preço.
4. Implementar caminho fora-horário (calendar) quando IDs chegarem.
5. Smokes ao vivo contra GHL real (padrão AMC).
