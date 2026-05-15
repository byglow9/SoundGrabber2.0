---
phase: 14-pipeline-e2e-on-notebook
plan: "02"
subsystem: infra
tags:
  - docker-compose
  - bind-mount
  - cookies
  - env-config
  - AUTH-04

dependency_graph:
  requires:
    - phase: 14-pipeline-e2e-on-notebook
      plan: "01"
      provides: "8 RED stubs in tests/test_deploy_sh.py — 6 turned GREEN by this plan"
  provides:
    - "docker-compose.yml com bind mount /data/yt-dlp-cache:ro em api e worker (D-01)"
    - ".env.example com YTDLP_CACHE_DIR=/data/yt-dlp-cache (D-02) e BGUTIL_BASE_URL= vazio (D-09)"
    - "6/8 testes AUTH-04 do Plan 01 GREEN"
  affects:
    - "Plan 03 (deploy.sh) — 2 testes restantes; Plan 04 (E2E checkpoint)"

tech-stack:
  added: []
  patterns:
    - "bind mount :ro para credenciais externas ao repo em docker-compose — volumes nomeados para tmpfs compartilhado, bind mounts apenas para dados do operador"
    - ".env.example como template canônico documentando decisions de contexto (D-02/D-09/D-10)"

key-files:
  created: []
  modified:
    - docker-compose.yml
    - .env.example

key-decisions:
  - "Bind mount :ro previne que yt-dlp sobrescreva e corrompa cookies.txt detectando sessão inválida (mesmo bug que corrompeu Railway — bytes 2987→1600)"
  - "sg_tmp:/tmp preservado em ambos os serviços; bind mount adicionado como segunda entrada, não substituição"
  - "BGUTIL_BASE_URL= vazio no .env.example — bgutil permanece no compose como fallback (D-08) mas inativo por padrão no notebook (D-09)"

patterns-established:
  - "Volumes docker-compose: named volumes para tmpfs compartilhado entre containers; bind mounts :ro para credenciais do operador"
  - "Comentários inline no compose e .env.example com referências D-XX para rastreabilidade"

requirements-completed:
  - AUTH-04

duration: ~2min
completed: "2026-05-15"
---

# Phase 14 Plan 02: Bind Mount :ro + .env.example Notebook Values — Summary

**Bind mount read-only `/data/yt-dlp-cache` adicionado em api e worker no docker-compose.yml, e `.env.example` atualizado com `YTDLP_CACHE_DIR=/data/yt-dlp-cache` e `BGUTIL_BASE_URL=` vazio — 6/8 testes AUTH-04 viraram GREEN.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-15T19:18:58Z
- **Completed:** 2026-05-15T19:20:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Adicionado bind mount `/data/yt-dlp-cache:/data/yt-dlp-cache:ro` nos serviços `api` e `worker` do docker-compose.yml (D-01), com comentário inline referenciando Phase 14 D-01 e o propósito do flag `:ro`
- Volume `sg_tmp:/tmp` preservado em ambos os serviços (Pitfall 1 — bind mount não pode substituir tmpfs compartilhado)
- `.env.example` atualizado: `YTDLP_CACHE_DIR=/data/yt-dlp-cache` (D-02) e `BGUTIL_BASE_URL=` vazio (D-09) com comentários documentando Plano B (D-10)
- 6/8 testes do Plan 01 viraram GREEN; 2 restantes (`deploy.sh`) são responsabilidade do Plan 03

## Diff Conceitual: docker-compose.yml

**Serviço `api` — volumes adicionados:**
```yaml
# Antes:
volumes:
  - sg_tmp:/tmp

# Depois:
volumes:
  - sg_tmp:/tmp
  # bind mount :ro — Phase 14 D-01; cookies.txt vem do host, yt-dlp não pode sobrescrever
  - /data/yt-dlp-cache:/data/yt-dlp-cache:ro
```

**Serviço `worker` — volumes adicionados (idêntico ao api):**
```yaml
volumes:
  - sg_tmp:/tmp
  # bind mount :ro — Phase 14 D-01; cookies.txt vem do host, yt-dlp não pode sobrescrever
  - /data/yt-dlp-cache:/data/yt-dlp-cache:ro
```

Demais serviços (`redis`, `bgutil`) — sem mudança.

## Diff Conceitual: .env.example

**Mudança 1 (D-09) — BGUTIL_BASE_URL:**
```ini
# Antes:
# bgutil PO Token provider (Phase 10.1)
BGUTIL_BASE_URL=http://bgutil:4416

# Depois:
# bgutil PO Token provider INATIVO no notebook (D-09) — IP residencial usa apenas cookies; setar http://bgutil:4416 apenas como Plano B se E2E falhar com LOGIN_REQUIRED (D-10)
BGUTIL_BASE_URL=
```

**Mudança 2 (D-02) — YTDLP_CACHE_DIR:**
```ini
# Antes:
# yt-dlp cache + cookies (Phase 14 popula este path via bind mount)
YTDLP_CACHE_DIR=

# Depois:
# yt-dlp cache + cookies — Phase 14 D-02; bind mount :ro no docker-compose.yml lê do host
YTDLP_CACHE_DIR=/data/yt-dlp-cache
```

## pytest Output (6 passed, 2 failed restantes — deploy.sh)

```
tests/test_deploy_sh.py::test_bind_mount_in_compose_api PASSED
tests/test_deploy_sh.py::test_bind_mount_in_compose_worker PASSED
tests/test_deploy_sh.py::test_compose_preserves_sg_tmp_in_api PASSED
tests/test_deploy_sh.py::test_compose_preserves_sg_tmp_in_worker PASSED
tests/test_deploy_sh.py::test_env_example_ytdlp_cache_dir PASSED
tests/test_deploy_sh.py::test_env_example_bgutil_empty PASSED
FAILED tests/test_deploy_sh.py::test_deploy_sh_exists_and_has_set_e - AssertionError: scripts/deploy.sh não existe
FAILED tests/test_deploy_sh.py::test_deploy_sh_security_gate_and_commands - AssertionError: scripts/deploy.sh não existe
2 failed, 6 passed in 0.05s
```

Os 2 testes com `deploy.sh` são responsabilidade do Plan 03 (AUTH-05).

## Task Commits

1. **Task 1: Bind mount /data/yt-dlp-cache:ro em api e worker** - `f8d66b1` (feat)
2. **Task 2: Atualizar .env.example para valores do notebook** - `b8f43f3` (feat)

**Plan metadata:** (docs commit — abaixo)

## Files Created/Modified

- `docker-compose.yml` — Adicionado bind mount `:ro` em `api.volumes` e `worker.volumes`; `sg_tmp:/tmp` preservado em ambos
- `.env.example` — `BGUTIL_BASE_URL=` (vazio, D-09) e `YTDLP_CACHE_DIR=/data/yt-dlp-cache` (D-02) com comentários D-09/D-10/D-02

## Decisions Made

Seguiu o plano exatamente. Nenhuma decisão arquitetural nova — todas as decisões seguem D-01/D-02/D-09 já registradas no 14-CONTEXT.md.

## Deviations from Plan

None - plano executado exatamente como escrito. O flag `:ro` no bind mount foi implementado conforme especificado (mitiga T-deploy-02 do threat model — yt-dlp não consegue sobrescrever `cookies.txt` no container).

## Threat Surface Scan

Nenhuma nova superfície de segurança introduzida. As mudanças são de configuração (compose + env template). O bind mount `:ro` fecha a ameaça T-deploy-02 (Tampering via sobrescrita de cookies). Nenhum novo endpoint, auth path, ou acesso a filesystem fora do escopo planejado.

## Issues Encountered

Nenhum. O `.venv` do projeto tem shebang com path incorreto (`/home/glow/Documentos/SoundGrabber2.0` vs `projetos/SoundGrabber2.0`), resolvido invocando `python3 -m pytest` diretamente. Não é bloqueador — o Python em si funciona corretamente.

## Next Phase Readiness

- Plan 03 pode criar `scripts/deploy.sh` imediatamente — os 2 testes RED restantes já estão definidos
- Plan 04 (checkpoint humano E2E) depende do Plan 03 estar completo
- Pré-requisito operacional ainda pendente: operador precisa criar `/data/yt-dlp-cache/` no host e copiar `cookies.txt` frescos via scp (D-11/D-12/D-13 — documentado no 14-CONTEXT.md)

---
*Phase: 14-pipeline-e2e-on-notebook*
*Completed: 2026-05-15*
