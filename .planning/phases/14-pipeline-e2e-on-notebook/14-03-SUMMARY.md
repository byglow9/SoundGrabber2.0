---
phase: 14-pipeline-e2e-on-notebook
plan: "03"
subsystem: deploy
tags:
  - deploy
  - shell
  - security-gate
  - AUTH-05
dependency_graph:
  requires:
    - 14-01 (RED stubs — tests 7-8 defined)
  provides:
    - scripts/deploy.sh (AUTH-05 satisfied)
  affects:
    - Plan 04 (E2E checkpoint can now invoke deploy.sh via SSH)
tech_stack:
  added: []
  patterns:
    - bash Security Gate pattern (set -e + chmod 750 auto-applied)
    - single-command SSH deploy (git pull + docker compose up --build -d)
key_files:
  created:
    - scripts/deploy.sh
  modified: []
decisions:
  - "Comments mentioning 'scp' and 'cookies' removed from deploy.sh to satisfy acceptance criterion grep -c 'scp|rsync|cookies' == 0 (D-06 spirit preserved through prose that avoids those exact strings)"
  - "Git stores mode 100755 (not 100750) — git only distinguishes executable vs non-executable for regular files; chmod 750 is applied at runtime via the Security Gate auto-chmod line"
metrics:
  duration: "~2 minutes"
  completed: "2026-05-15"
---

# Phase 14 Plan 03: scripts/deploy.sh with Security Gate (AUTH-05) — Summary

`scripts/deploy.sh` implementado: operador faz `ssh moisés@100.x.x.x 'bash ~/soundgrabber/scripts/deploy.sh'` e o notebook executa `git pull + sudo docker compose up --build -d` com Security Gate completo (set -e, chmod 750 auto-aplicado, sem eval).

## What Was Built

Created `scripts/deploy.sh` (26 lines) satisfying AUTH-05 and the full Security Gate.

**File created:** `scripts/deploy.sh` (committed as mode 100755 — executable)

## scripts/deploy.sh — Conteúdo Completo

```bash
#!/usr/bin/env bash
# scripts/deploy.sh — Deploy remoto SoundGrabber no notebook via SSH/Tailscale
#
# Invocação pelo operador (máquina local):
#   ssh moisés@100.x.x.x 'bash ~/soundgrabber/scripts/deploy.sh'
#
# O que faz:
#   1. Entra no diretório ~/soundgrabber (D-05)
#   2. Faz git pull para atualizar o código (e o próprio deploy.sh — D-04)
#   3. Reconstrói e reinicia os containers com sudo docker compose up --build -d (D-05)
#
# O que NÃO faz:
#   - NÃO gerencia credenciais de autenticação (D-06 — separação de responsabilidades)
#   - Arquivos de autenticação devem ser transferidos pelo operador separadamente (AUTH-04)
#
# Referências: D-04, D-05, D-06, D-07 (14-CONTEXT.md); Security Gate (CLAUDE.md)
set -e

# Security Gate: auto-aplica permissões restritivas a cada execução (CLAUDE.md §1.2)
chmod 750 "$(realpath "$0")"

cd ~/soundgrabber

git pull

sudo docker compose up --build -d
```

## Linha → Decisão Mapping

| Linha | Conteúdo | Decisão |
|-------|----------|---------|
| 1 | `#!/usr/bin/env bash` | Padrão do projeto (start-all.sh, notebook-setup.sh) — portabilidade |
| 17 | `set -e` | D-05 (Security Gate §1) — falha imediata em qualquer erro; T-deploy-08 mitigado |
| 19-20 | `chmod 750 "$(realpath "$0")"` | D-07 (Security Gate §2) — auto-aplica permissões restritivas; T-deploy-05 mitigado |
| 22 | `cd ~/soundgrabber` | D-05 — diretório de trabalho canônico no notebook |
| 24 | `git pull` | D-04 — atualiza código E o próprio deploy.sh a cada execução |
| 26 | `sudo docker compose up --build -d` | D-05 + Phase 12 D-06 — `sudo` obrigatório (sem grupo docker); rebuild + restart em background |

## `bash -n scripts/deploy.sh` Output

```
(vazio — exit 0)
```

## pytest Output (tests 7-8 GREEN)

```
tests/test_deploy_sh.py::test_deploy_sh_exists_and_has_set_e PASSED      [ 87%]
tests/test_deploy_sh.py::test_deploy_sh_security_gate_and_commands PASSED [100%]
2 passed in 0.08s
```

Nota: Os 6 testes restantes (1-6, AUTH-04) são responsabilidade do Plan 02 (agente paralelo na mesma wave). O suite completo de 8 passed será verificável após merge de ambos os planos.

## `git ls-files --stage scripts/deploy.sh` Output

```
100755 d948af070c6c578102145fc8981661d512df678a 0	scripts/deploy.sh
```

Nota: Git suporta apenas `100644` (não-executável) e `100755` (executável) para arquivos regulares. O plano mencionava `100750` mas esse modo não é suportado pelo git index. O bit executável está presente (`100755`); o `chmod 750` é re-aplicado em cada execução pelo Security Gate auto-chmod no runtime — isso garante que grupo e outros não tenham permissão de execução no sistema de arquivos real do notebook.

## Acceptance Criteria — Verificação

| Critério | Status |
|----------|--------|
| `scripts/deploy.sh` existe | PASS |
| `bash -n scripts/deploy.sh` exit 0 | PASS |
| Primeira linha executável é `set -e` | PASS |
| `grep -F 'chmod 750 "$(realpath "$0")"' \| wc -l` == 1 | PASS |
| `grep -F 'cd ~/soundgrabber' \| wc -l` == 1 | PASS |
| `grep -cE '^git pull$'` == 1 | PASS |
| `grep -cE '^sudo docker compose up --build -d$'` == 1 | PASS |
| `grep -c 'eval'` == 0 | PASS |
| `grep -c 'scp\|rsync\|cookies'` == 0 | PASS |
| `git ls-files --stage` mostra executável (100755) | PASS |
| Testes 7-8 GREEN | PASS |

## Security Gate Compliance

| Controle | Implementação | Status |
|----------|---------------|--------|
| `set -e` após shebang (§1) | Linha 17 — primeira instrução executável | PASS |
| `chmod 750 auto-aplicado` (§2) | Linha 20 — `chmod 750 "$(realpath "$0")"` | PASS |
| Sem `eval` (§3) | `grep -c eval == 0` confirmado | PASS |

## STRIDE Threat Coverage

| Threat | Mitigação Implementada |
|--------|------------------------|
| T-deploy-05 (Elevation — world-executable) | `chmod 750` auto-aplicado; mode 100755 no git index |
| T-deploy-06 (Tampering — eval) | Proibido; 0 ocorrências confirmadas por grep |
| T-deploy-07 (Information Disclosure — credenciais) | Script não manipula credenciais; grep scp/rsync/cookies == 0 |
| T-deploy-08 (DoS — set -e ausente) | `set -e` como primeira instrução executável |

## Deviations from Plan

**1. [Rule 2 - Security] Removed 'scp' and 'cookies' strings from comment block**

- **Found during:** Task 1 acceptance criteria verification
- **Issue:** PLAN acceptance criteria specifies `grep -c 'scp\|rsync\|cookies' == 0`. Initial comment draft mentioned "scp" and "cookies" to explain D-06 (what the script does NOT do). While both were in comment lines only (not executable), they would fail the grep check.
- **Fix:** Reworded comments to convey D-06 intent without using those specific strings: "credenciais de autenticação" instead of "cookies", "transferidos pelo operador separadamente" instead of "scp".
- **Files modified:** `scripts/deploy.sh`
- **Commit:** 6a8f61b (same commit — correction applied before staging)

## Known Stubs

None — `scripts/deploy.sh` is fully functional with its 3 canonical commands.

## Threat Flags

No new threat surface introduced beyond what is already in the threat model for this plan. All STRIDE items mitigated.

## Self-Check: PASSED

- `scripts/deploy.sh` exists: FOUND
- Task commit `6a8f61b`: FOUND
- `bash -n scripts/deploy.sh`: exit 0
- Tests 7-8 PASSED: CONFIRMED
- Mode 100755 (executable): CONFIRMED
