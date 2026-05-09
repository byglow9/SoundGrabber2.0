---
phase: 07-infrastructure-security
plan: 03
subsystem: deployment-config
tags: [security, infrastructure, railway, deployment, documentation]
dependency_graph:
  requires:
    - 07-02 (Redis auth enforcement + HSTS implementados em api/main.py)
  provides:
    - railway.toml com startCommand para producao Railway (SEC-INFRA-02..04)
    - SECURITY-CHECKLIST.md atualizado com secao 6 cobrindo SEC-INFRA-01..04
  affects:
    - railway.toml (criado)
    - .planning/SECURITY-CHECKLIST.md (atualizado)
tech_stack:
  added: []
  patterns:
    - railway.toml config-as-code: startCommand com $PORT injetado pelo Railway (D-11, D-13)
    - NIXPACKS builder declarado explicitamente para prevenir drift de buildpack
    - restartPolicyMaxRetries=3 previne loop infinito se Redis auth falha no lifespan
key_files:
  created:
    - railway.toml
  modified:
    - .planning/SECURITY-CHECKLIST.md
decisions:
  - "startCommand usa $PORT (nao 8000 hardcoded) — Railway injeta PORT por deploy; hardcodar quebra healthcheck (Pitfall 2 do RESEARCH.md)"
  - "0.0.0.0 e necessario no Railway — isolamento e feito pela plataforma; bind em 127.0.0.1 quebraria o proxy Railway (D-11)"
  - "healthcheckTimeout=60 — suficiente para lifespan rodar _check_redis_auth + sweeper thread antes do primeiro health check"
  - "restartPolicyMaxRetries=3 — evita restart loop infinito consumindo creditos se REDIS_URL sem senha em producao (D-07)"
  - "NIXPACKS builder declarado explicitamente — previne auto-deteccao errada se package.json for adicionado (T-7-NIXPACKS)"
  - "SECURITY-CHECKLIST secoes renumeradas: nova secao 6 (Infrastructure), deferidos=7, end-to-end=8, historico=9"
metrics:
  duration: "2 minutes"
  completed: "2026-05-09"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 7 Plan 03: Railway Deploy Config + Security Checklist Update Summary

railway.toml criado na raiz com startCommand uvicorn 0.0.0.0:$PORT para producao Railway (SEC-INFRA-02..04); SECURITY-CHECKLIST.md atualizado com secao 6 cobrindo SEC-INFRA-01..04 com checkboxes, comandos de verificacao e threat references — itens removidos da secao de deferidos.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Criar railway.toml na raiz do projeto | 5a52da3 | railway.toml |
| 2 | Atualizar SECURITY-CHECKLIST.md com SEC-INFRA-01..04 | 6c167b5 | .planning/SECURITY-CHECKLIST.md |

---

## What Was Built

### Task 1 — `railway.toml`

Criado na raiz do projeto com configuracao completa de deploy Railway:

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT --limit-concurrency 100 --timeout-keep-alive 5"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

Pontos criticos confirmados:
- `$PORT` em aspas duplas TOML — expandido pelo shell no Railway (A2 do RESEARCH.md)
- `0.0.0.0` — necessario para proxy Railway acessar o container (D-11)
- `/health` — rota ja existente desde Phase 6 (SEC-API-03), retorna 200/503 com Redis ping
- `healthcheckTimeout=60` — suficiente para lifespan completo (DEV_MODE check + sweeper thread)
- `restartPolicyMaxRetries=3` — Railway marca deploy como falho apos 3 tentativas; evita loop

### Task 2 — `SECURITY-CHECKLIST.md`

Tres mudancas aplicadas:

**Mudanca 1 — Nova secao 6 "Infrastructure Security (Phase 7)"** com 4 subsecoes:
- SEC-INFRA-01: checkboxes para _check_redis_auth, lifespan call, DEV_MODE campo, Railway env vars
- SEC-INFRA-02: checkboxes para railway.toml startCommand, Railway PaaS isolamento, separacao start.sh/railway.toml
- SEC-INFRA-03: checkboxes para HTTPS termination Railway, redirect 301, sem nginx/certbot
- SEC-INFRA-04: checkboxes para _security_headers HSTS header, TestClient verification

**Mudanca 2 — Secao de deferidos limpa:** SEC-INFRA-01..04 removidos; mantidos CSP unsafe-inline, /tmp privado, job cancellation endpoint.

**Mudanca 3 — Header e historico atualizados:**
- "Ultima atualizacao: Phase 7 (Infrastructure Security)"
- "Proxima revisao: v1.2 (CSP sem 'unsafe-inline')"
- Historico: "Phase 7 (planned)" substituido por entrada real com controles implementados
- Bloco 4.5 adicionado em Verificacao end-to-end (railway.toml + HSTS local)
- Secoes renumeradas: 6=Infrastructure, 7=Deferidos, 8=Verificacao, 9=Historico

---

## Verification Results

```
# railway.toml valido
python3 -c "import tomllib; tomllib.load(open('railway.toml','rb'))" && echo "OK"
# OK

# Criterios criticos
grep -E '^startCommand' railway.toml
# startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT --limit-concurrency 100 --timeout-keep-alive 5"

grep -c '8000' railway.toml  # -> 0 (sem hardcoded port)
grep -c '127.0.0.1' railway.toml  # -> 0 (sem loopback)

# SECURITY-CHECKLIST criterios
# SEC-INFRA-01..04 presentes: 1 cada
# SEC-INFRA-01..04 na secao deferidos: 0 cada
# Ultima atualizacao: Phase 7 (Infrastructure Security)
# Phase 7 (planned): 0 (removido)

# Suite de testes sem regressao
pytest tests/test_security.py -q
# 16 passed in 2.13s
```

---

## Deviations from Plan

Nenhum — plano executado exatamente como especificado.

---

## Known Stubs

Nenhum. railway.toml e SECURITY-CHECKLIST.md sao artefatos de configuracao/documentacao completos e funcionais.

---

## Threat Flags

Nenhuma nova superficie de ataque introduzida. railway.toml e um arquivo de configuracao que ativa controles existentes (SEC-INFRA-02..04) para producao.

---

## Self-Check

### Files exist:
```bash
[ -f "railway.toml" ] && echo "FOUND: railway.toml" || echo "MISSING: railway.toml"
[ -f ".planning/SECURITY-CHECKLIST.md" ] && echo "FOUND: SECURITY-CHECKLIST.md" || echo "MISSING"
```
- FOUND: railway.toml
- FOUND: .planning/SECURITY-CHECKLIST.md

### Commits exist:
```bash
git log --oneline | grep "5a52da3"  # Task 1
git log --oneline | grep "6c167b5"  # Task 2
```
- FOUND: 5a52da3 chore(07-03): add railway.toml for production deploy (SEC-INFRA-02..04)
- FOUND: 6c167b5 docs(07-03): update SECURITY-CHECKLIST with SEC-INFRA-01..04 (Phase 7)

## Self-Check: PASSED
