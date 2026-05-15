---
phase: 14
slug: pipeline-e2e-on-notebook
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (confirmado em `pytest.ini`) |
| **Config file** | `pytest.ini` na raiz |
| **Quick run command** | `pytest tests/test_deploy_sh.py -x -q` |
| **Full suite command** | `pytest tests/ -ra --strict-markers -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_deploy_sh.py -x -q`
- **After every plan wave:** Run `pytest tests/ -ra --strict-markers -q`
- **Before `/gsd-verify-work`:** Full suite must be green + checkpoint AUTH-04 (logs sem CRITICAL) + 3 jobs PIPE-08 verificados manualmente
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 0 | AUTH-04, AUTH-05 | T-deploy-01 | Stubs RED criam arquivo de teste | unit | `pytest tests/test_deploy_sh.py -x -q` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 1 | AUTH-04 | T-deploy-02 | Bind mount `:ro` presente em api e worker | unit (YAML) | `pytest tests/test_deploy_sh.py::test_bind_mount_in_compose -x` | ❌ W0 | ⬜ pending |
| 14-02-02 | 02 | 1 | AUTH-04 | T-deploy-03 | `.env.example` contém `YTDLP_CACHE_DIR=/data/yt-dlp-cache` | unit | `pytest tests/test_deploy_sh.py::test_env_example_ytdlp_cache_dir -x` | ❌ W0 | ⬜ pending |
| 14-02-03 | 02 | 1 | AUTH-04 | T-deploy-04 | `.env.example` tem `BGUTIL_BASE_URL=` vazio | unit | `pytest tests/test_deploy_sh.py::test_env_example_bgutil_empty -x` | ❌ W0 | ⬜ pending |
| 14-03-01 | 03 | 1 | AUTH-05 | T-deploy-05 | `scripts/deploy.sh` existe com `set -e` | unit (file content) | `pytest tests/test_deploy_sh.py::test_deploy_sh_exists_with_set_e -x` | ❌ W0 | ⬜ pending |
| 14-03-02 | 03 | 1 | AUTH-05 | T-deploy-06 | `scripts/deploy.sh` tem `chmod 750 "$(realpath "$0")"` | unit | `pytest tests/test_deploy_sh.py::test_deploy_sh_security_gate -x` | ❌ W0 | ⬜ pending |
| 14-03-03 | 03 | 1 | AUTH-05 | T-deploy-07 | `scripts/deploy.sh` tem `git pull` + `docker compose up --build -d` | unit | `pytest tests/test_deploy_sh.py::test_deploy_sh_commands -x` | ❌ W0 | ⬜ pending |
| 14-03-04 | 03 | 1 | AUTH-05 | T-deploy-08 | `scripts/deploy.sh` NÃO contém `eval` | unit | `pytest tests/test_deploy_sh.py::test_deploy_sh_no_eval -x` | ❌ W0 | ⬜ pending |
| 14-04-01 | 04 | 2 | AUTH-04, PIPE-08 | — | Cookies carregados: logs sem CRITICAL | manual | `docker compose logs api \| grep -E "CRITICAL\|AUTH:"` no notebook | manual-only | ⬜ pending |
| 14-04-02 | 04 | 2 | PIPE-08 | — | 3 beats E2E: status=done + WAV + BPM + key | manual | POST /jobs × 3 + poll status no notebook via curl | manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_deploy_sh.py` — 8 stubs RED cobrindo AUTH-04 (bind mount, .env.example) e AUTH-05 (deploy.sh: set -e, chmod 750, git pull, docker compose up, sem eval)

*Infraestrutura existente (pytest.ini, conftest.py) cobre todos os outros requisitos. Apenas o arquivo de teste específico desta fase precisa ser criado.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cookies carregados no startup sem CRITICAL | AUTH-04 | Requer hardware do notebook + bind mount ativo + cookies frescos | `docker compose logs api \| grep -E "CRITICAL\|AUTH:"` — ausência de CRITICAL = OK |
| 3 beats E2E status=done com WAV/BPM/key | PIPE-08 | Requer IP residencial real, cookies frescos, YouTube live | POST /jobs × 3 URLs de beats distintos; poll até done; verificar BPM > 0 e key em standard notation |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
