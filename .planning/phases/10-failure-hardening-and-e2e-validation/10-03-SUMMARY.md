---
phase: 10-failure-hardening-and-e2e-validation
plan: "03"
subsystem: infra/railway
tags: [railway, deployment, single-container, celery, uvicorn, startup-script]
dependency_graph:
  requires: [10-02-PLAN.md]
  provides: [start-all.sh, railway.toml single-container]
  affects: [railway deploy, /tmp sharing, GET /files/{id}]
tech_stack:
  added: []
  patterns: [single-container PID-1 exec pattern, Celery background + Uvicorn foreground]
key_files:
  created:
    - start-all.sh
  modified:
    - railway.toml
    - railway-worker.toml
decisions:
  - "exec uvicorn como PID 1 para SIGTERM direto do Railway (sem intermediário bash)"
  - "Celery em background com & — Railway monitora apenas foreground"
  - "railway-worker.toml mantido no repositório (aposentado) para rastreabilidade histórica"
metrics:
  duration_minutes: 10
  completed_date: "2026-05-11"
  tasks_completed: 1
  tasks_total: 2
  files_changed: 3
---

# Phase 10 Plan 03: Single-Container Railway Startup Summary

**One-liner:** Script start-all.sh com exec uvicorn + Celery background substitui setup de dois containers Railway que isolava /tmp e causava 410 em GET /files/{id}.

---

## What Was Built

### Task 1 — start-all.sh + railway.toml + railway-worker.toml (COMPLETE)

**Commit:** `50b4e09`

**start-all.sh** criado na raiz do projeto:
- `set -e` na primeira linha operacional (Security Gate CLAUDE.md)
- Celery Worker iniciado em background com `&`
- `exec uvicorn` em foreground — Uvicorn se torna PID 1, recebe SIGTERM diretamente do Railway
- `PORT` com fallback `8000` para compatibilidade local/Railway
- `chmod 750` aplicado (Security Gate §scripts de operação)
- Sem `eval` de input externo (Security Gate confirmado)

**railway.toml** atualizado:
- `startCommand` alterado de `uvicorn api.main:app ...` para `bash start-all.sh`
- Comentário atualizado explicando a mudança single-container
- Todos os outros campos mantidos inalterados (`healthcheckPath`, `healthcheckTimeout`, `restartPolicyType`, `restartPolicyMaxRetries`)

**railway-worker.toml** aposentado:
- Conteúdo substituído por comentário de aposentadoria com data e contexto
- Bloco `[deploy]` original comentado para referência futura (caso se queira voltar a separar serviços com object storage)

### Task 2 — Deploy Railway + Validação E2E (AGUARDANDO OPERADOR)

Requer ação manual: push para disparar redeploy Railway + validação com 3 beats reais.

---

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `exec uvicorn` como PID 1 | SIGTERM do Railway chega diretamente ao Uvicorn sem intermediário; graceful shutdown correto |
| Celery em `&` (background) | Railway monitora o foreground; Celery recebe SIGTERM via grupo de processos quando o container termina |
| `chmod 750` (não 755) | Security Gate CLAUDE.md §scripts de operação: "chmod 750 para scripts de operação" |
| railway-worker.toml mantido aposentado | Histórico e facilidade de rollback para arquitetura separada se object storage for adicionado |

---

## Deviations from Plan

Nenhuma — plano executado exatamente como escrito.

---

## Security Gate Compliance

| Controle | Arquivo | Status |
|----------|---------|--------|
| `set -e` na primeira linha | start-all.sh | PASS |
| chmod 750 para scripts de operação | start-all.sh | PASS — `chmod 750 start-all.sh` aplicado em Task 1 |
| Sem `eval` de input externo | start-all.sh | PASS — apenas comandos hardcoded |

T-10-03-04 (Tampering: start-all.sh executável no repositório) — mitigado conforme threat register.

---

## Known Stubs

Nenhum — start-all.sh contém apenas comandos de startup sem dados mockados ou placeholders.

---

## Threat Flags

Nenhuma nova superfície de rede, endpoint ou caminho de auth introduzidos neste plano.

---

## Self-Check

```
[ -f "start-all.sh" ] → FOUND
[ grep "exec uvicorn" start-all.sh ] → FOUND
[ grep "bash start-all.sh" railway.toml ] → FOUND
[ grep "APOSENTADO" railway-worker.toml ] → FOUND
[ git log --oneline | grep "50b4e09" ] → FOUND
```

## Self-Check: PASSED
