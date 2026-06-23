#!/usr/bin/env python3
"""
Provisiona recursos GHL do agente de pré-atendimento Vaapty (idempotente).

Roda na SUA máquina (precisa de internet). Lê credenciais do .env na raiz.
- Custom Fields (contato): status_ia, localizacao, veiculo_modelo, veiculo_ano, motivo_venda
- Tag: agent-ia
- Custom Value: FAQ_YAML (semente vazia, editável depois no CRM)
- Lista Calendars (imprime IDs para você identificar Adriano/Dário)

Find-or-create: nada é duplicado. Roda quantas vezes quiser.

Uso:
    python3 scripts/provision_ghl.py          # cria/garante e imprime IDs
    python3 scripts/provision_ghl.py --dry     # só lista o que existe, não cria
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = "https://services.leadconnectorhq.com"


def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith(("GHL_", "OPENAI_"))})
    return env


def api(method, path, token, version, body=None, query=None):
    url = BASE + path
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Version", version)
    req.add_header("Accept", "application/json")
    # Cloudflare (erro 1010) bloqueia UA padrao do urllib; finge browser.
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")
    except Exception as e:
        return 0, {"error": str(e)}


# Custom fields desejados: (name, dataType). nome -> usa firstName padrão (não cria).
WANTED_FIELDS = [
    ("status_ia", "TEXT"),        # qualificado | desqualificado | escalado
    ("localizacao", "TEXT"),
    ("veiculo_modelo", "TEXT"),
    ("veiculo_ano", "TEXT"),
    ("motivo_venda", "TEXT"),     # quitar_divida | trocar | investir | outro
]

FAQ_SEED = """# FAQ Vaapty - preencher com Q&A oficiais
# Formato:
# - q: pergunta do cliente
#   a: resposta oficial
#   tags: [opcional]
faq: []
# Assuntos intocáveis (sempre escala p/ humano, nunca responder):
intocaveis:
  - preco
  - valor_avaliacao
  - comissao
"""


def main():
    dry = "--dry" in sys.argv
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = load_env(os.path.join(root, ".env"))
    loc = env.get("GHL_LOCATION_ID")
    token = env.get("GHL_PIT_TOKEN")
    version = env.get("GHL_API_VERSION", "2021-07-28")
    if not loc or not token:
        sys.exit("Faltam GHL_LOCATION_ID / GHL_PIT_TOKEN no .env")

    # sanity — usa customFields (escopo que o agente realmente precisa).
    # GET /locations/{id} exige locations.readonly, que o PIT pode nao ter; nao bloqueia.
    st, _ = api("GET", f"/locations/{loc}/customFields/", token, version)
    print(f"[auth] GET /locations/{loc}/customFields/ -> HTTP {st}")
    if st in (401, 403):
        sys.exit("Token inválido/sem permissão (customFields).")

    results = {}

    # ---- CUSTOM FIELDS ----
    print("\n=== CUSTOM FIELDS ===")
    st, d = api("GET", f"/locations/{loc}/customFields/", token, version)
    existing = {f.get("name"): f.get("id") for f in (d.get("customFields") or [])}
    for name, dtype in WANTED_FIELDS:
        if name in existing:
            print(f"  ok (existe)  {name} -> {existing[name]}")
            results[f"CF_{name.upper()}"] = existing[name]
            continue
        if dry:
            print(f"  faltando     {name} (dry-run, não criado)")
            continue
        st, d2 = api("POST", f"/locations/{loc}/customFields/", token, version,
                     body={"name": name, "dataType": dtype, "model": "contact"})
        fid = (d2.get("customField") or d2).get("id")
        print(f"  criado [{st}] {name} -> {fid}")
        results[f"CF_{name.upper()}"] = fid

    # ---- TAG ----
    print("\n=== TAG ===")
    st, d = api("GET", f"/locations/{loc}/tags/", token, version)
    tags = {t.get("name"): t.get("id") for t in (d.get("tags") or [])}
    if "agent-ia" in tags:
        print(f"  ok (existe)  agent-ia -> {tags['agent-ia']}")
        results["TAG_AGENT_IA_ID"] = tags["agent-ia"]
    elif not dry:
        st, d2 = api("POST", f"/locations/{loc}/tags/", token, version, body={"name": "agent-ia"})
        tid = (d2.get("tag") or d2).get("id")
        print(f"  criado [{st}] agent-ia -> {tid}")
        results["TAG_AGENT_IA_ID"] = tid

    # ---- CUSTOM VALUE (FAQ) ----
    print("\n=== CUSTOM VALUE (FAQ) ===")
    st, d = api("GET", f"/locations/{loc}/customValues/", token, version)
    cvs = {v.get("name"): v.get("id") for v in (d.get("customValues") or [])}
    if "FAQ_YAML" in cvs:
        print(f"  ok (existe)  FAQ_YAML -> {cvs['FAQ_YAML']}")
        results["CV_FAQ"] = cvs["FAQ_YAML"]
    elif not dry:
        st, d2 = api("POST", f"/locations/{loc}/customValues/", token, version,
                     body={"name": "FAQ_YAML", "value": FAQ_SEED})
        vid = (d2.get("customValue") or d2).get("id")
        print(f"  criado [{st}] FAQ_YAML -> {vid}")
        results["CV_FAQ"] = vid

    # ---- CALENDARS (somente listar) ----
    print("\n=== CALENDARS (identifique Adriano / Dário) ===")
    st, d = api("GET", "/calendars/", token, version, query={"locationId": loc})
    for c in (d.get("calendars") or []):
        print(f"  - {c.get('name')!r:40} id={c.get('id')}")

    # ---- DUMP p/ colar no .env ----
    print("\n=== COLE NO .env ===")
    for k, v in results.items():
        print(f"{k}={v}")


if __name__ == "__main__":
    main()
