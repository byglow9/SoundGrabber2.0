---
phase: 06-application-security
plan: 03
subsystem: documentation
tags: [security, policy, documentation, pip-audit, checklist]
dependency_graph:
  requires: [06-01, 06-02]
  provides: [.planning/SECURITY-CHECKLIST.md, CLAUDE.md::Security Gate, README.md::Pre-Deploy Security Audit]
  affects: [future-phases-planning, deploy-process]
tech_stack:
  added: []
  patterns:
    - pip-audit para auditoria de dependencias pre-deploy
    - Security Gate como gate de processo para novas features
    - SECURITY-CHECKLIST como fonte de verdade rastreavel para controles ativos
key_files:
  created:
    - .planning/SECURITY-CHECKLIST.md
  modified:
    - README.md
    - CLAUDE.md
decisions:
  - "SECURITY-CHECKLIST.md em .planning/ (nao em raiz) — artefato de planejamento, nao instrucao operacional; raiz eh para arquivos operacionais do projeto"
  - "Security Gate inserido entre Restricoes criticas e Proximo passo em CLAUDE.md — lido por Claude antes de cada nova fase, garantindo que novos planos ja incluam controles de seguranca por default"
  - "pip-audit nao adicionado ao requirements.txt — ferramenta de auditoria, nao runtime; instalar sob demanda no deploy ou CI"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-09T18:58:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 06 Plan 03: Security Policy Documentation Summary

**One-liner:** Politica de seguranca permanente documentada em 3 artefatos: pip-audit pre-deploy no README, Security Gate no CLAUDE.md com 6 categorias de controles obrigatorios, e SECURITY-CHECKLIST.md com 8 secoes cobrindo todos os 13 controles SEC-* da Phase 6.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Adicionar secao pip-audit pre-deploy ao README.md | `a1f9cbb` | README.md |
| 2 | Adicionar secao Security Gate ao CLAUDE.md | `16a5ed1` | CLAUDE.md |
| 3 | Criar SECURITY-CHECKLIST.md cobrindo todos os controles Phase 6 | `ba40068` | .planning/SECURITY-CHECKLIST.md |

---

## What Was Built

### README.md — Secao pip-audit

Inserida secao `## Pre-Deploy Security Audit` entre `## Architecture` (linha 175) e `## License` (linha 194) com 18 linhas novas:

- Paragrafo descritivo com link para pip-audit (PyPA, OSV + PyPI Advisory DB)
- Bloco bash com os dois comandos exatos: `pip install pip-audit` + `pip-audit -r requirements.txt`
- Politica de resposta (HIGH/CRITICAL bloqueia deploy)
- Nota sobre pip-audit como ferramenta de auditoria, nao runtime

**Linhas antes:** 178 | **Linhas depois:** 196 | **Delta:** +18 linhas

### CLAUDE.md — Secao Security Gate

Inserida secao `## Security Gate` entre `## Restricoes criticas` (linha 47) e `## Proximo passo` (linha 93) com 38 linhas novas:

Subsecoes criadas:
1. `### Controles obrigatorios em qualquer novo endpoint HTTP` — 4 items (rate limit, body validation, size limit, slowapi sync)
2. `### Controles obrigatorios em qualquer novo arquivo gerado em /tmp` — 3 items (chmod 0o600, prefixo sg_, path traversal defense)
3. `### Controles obrigatorios em qualquer novo script shell` — 3 items (set -e, auto-chmod, sem eval)
4. `### Testes obrigatorios` — 3 items (test_security.py, pytest verde, pip-audit)
5. `### Documentacao obrigatoria` — 2 items (SECURITY-CHECKLIST.md, REQUIREMENTS.md)
6. `### Quando esta regra pode ser flexibilizada` — clausula de excecao explica que nunca silenciosamente

**Linhas antes:** 59 | **Linhas depois:** 97 | **Delta:** +38 linhas

### .planning/SECURITY-CHECKLIST.md — Arquivo novo

Criado com 193 linhas cobrindo 8 secoes principais:

| Secao | Conteudo |
|-------|----------|
| 1. Filesystem Permissions | SEC-FILE-01 (chmod 0o600 WAV), SEC-FILE-02 (chmod 750 start.sh) |
| 2. API Rate Limiting | SEC-API-01 (60/min jobs), SEC-API-02 (10/min files), SEC-API-03 (/health), POST /jobs (Phase 3) |
| 3. HTTP Hardening | SEC-TEST-01 (4KB limit), SEC-TEST-02 (security headers), SEC-TEST-03 (docs disabled), SEC-TEST-04 (queue depth), SEC-TEST-05 |
| 4. Pre-Deploy Audit | SEC-TEST-06 (pip-audit policy + resposta a vulnerabilidades) |
| 5. Policy & Documentation | SEC-POLICY-01 (CLAUDE.md Security Gate), SEC-POLICY-02 (este arquivo) |
| 6. Threats Deferidos | SEC-INFRA-01..04 para Phase 7; CSP inline, /tmp privado, job cancel para v2 |
| 7. Verificacao E2E | Bloco bash completo — pytest, pip-audit, filesystem, curl health + rate limit |
| 8. Historico de mudancas | Tabela Phase 3 -> Phase 6 -> Phase 7 (planned) |

**Bytes:** ~6.7KB | **Linhas:** 193 | **referencias test_security.py:** 12x | **referencias pip-audit:** 7x

---

## Coverage dos SEC-* Requirements

| ID | Controle | Documentado em |
|----|----------|----------------|
| SEC-FILE-01 | WAV chmod 0o600 | SECURITY-CHECKLIST.md §1 |
| SEC-FILE-02 | start.sh chmod 750 | SECURITY-CHECKLIST.md §1 |
| SEC-API-01 | GET /jobs rate limit 60/min | SECURITY-CHECKLIST.md §2 |
| SEC-API-02 | GET /files rate limit 10/min | SECURITY-CHECKLIST.md §2 |
| SEC-API-03 | GET /health liveness | SECURITY-CHECKLIST.md §2 |
| SEC-TEST-01 | Body size limit 4KB | SECURITY-CHECKLIST.md §3 |
| SEC-TEST-02 | Security headers | SECURITY-CHECKLIST.md §3 |
| SEC-TEST-03 | /docs /redoc desabilitados | SECURITY-CHECKLIST.md §3 |
| SEC-TEST-04 | Queue depth limit 503 | SECURITY-CHECKLIST.md §3 |
| SEC-TEST-05 | Rate limits GET endpoints | SECURITY-CHECKLIST.md §3 |
| SEC-TEST-06 | pip-audit pre-deploy | README.md + SECURITY-CHECKLIST.md §4 |
| SEC-POLICY-01 | Security Gate em CLAUDE.md | CLAUDE.md + SECURITY-CHECKLIST.md §5 |
| SEC-POLICY-02 | SECURITY-CHECKLIST.md existe | SECURITY-CHECKLIST.md §5 |

**13/13 cobertos.**

---

## pip-audit Output (momento da conclusao)

```
No known vulnerabilities found
```

Zero vulnerabilidades em `requirements.txt` na data da execucao (2026-05-09).

---

## Test Results

### pytest tests/test_security.py -q

```
............
12 passed in 2.07s
```

### pytest tests/ -m "not e2e and not integration" -q

```
1 failed, 46 passed, 12 deselected
```

Falha pre-existente: `test_html_required_ids_present` (ID `download-area` ausente em index.html — documentada em 06-02-SUMMARY.md como fora do escopo desta fase).

**Nenhuma regressao causada por este plan (zero codigo de producao modificado).**

---

## Deviations from Plan

Nenhuma. Plano executado exatamente como escrito — 3 tarefas, 3 commits, zero modificacoes em codigo de producao (`api/`, `pipeline.py`, `start.sh`).

---

## Known Stubs

Nenhum. Este plano cria apenas documentacao sem placeholders ou TODOs pendentes.

---

## Threat Flags

Nenhum. Este plano modifica apenas arquivos de documentacao sem criar novos endpoints, rotas, ou superficie de ataque.

---

## Self-Check: PASSED

- [x] README.md tem `## Pre-Deploy Security Audit` entre Architecture e License: FOUND (linha 176 < linha 194)
- [x] CLAUDE.md tem `## Security Gate` entre Restricoes criticas e Proximo passo: FOUND (linha 55, entre linhas 47 e 93)
- [x] .planning/SECURITY-CHECKLIST.md existe com 193 linhas: FOUND
- [x] Todos 13 SEC-* IDs presentes no checklist: VERIFIED
- [x] Commit a1f9cbb existe: FOUND
- [x] Commit 16a5ed1 existe: FOUND
- [x] Commit ba40068 existe: FOUND
- [x] pip-audit: No known vulnerabilities found
- [x] pytest tests/test_security.py: 12 passed
- [x] Nenhum codigo de aplicacao modificado (git diff ef5f98c HEAD -- api/ pipeline.py start.sh = 0 linhas)
