---
phase: 13-docker-compose
plan: "04"
subsystem: infra
tags: [docker-compose, redis, celery, bgutil, tmpfs, volume]

requires:
  - phase: 13-03
    provides: imagem soundgrabber:latest construída e validada (Gate D-07)

provides:
  - docker-compose.yml com 4 serviços (api, worker, redis, bgutil) + rede soundgrabber_net + volume tmpfs sg_tmp
  - .env.example atualizado com hostnames do compose (redis://redis, http://bgutil:4416, DEV_MODE=true)
  - Stack validada: DEPLOY-05 (restart: unless-stopped × 4) e DEPLOY-06 (tmpfs compartilhado) GREEN

affects: [14-cookies-deploy, deploy]

tech-stack:
  added: [docker-compose v2, redis:7-alpine, jim60105/bgutil-pot]
  patterns: [named volume com driver_opts type=tmpfs para compartilhamento entre containers, env_file consolidado, depends_on com service_healthy]

key-files:
  created:
    - docker-compose.yml
  modified:
    - .env.example

key-decisions:
  - "Named volume sg_tmp com driver_opts type=tmpfs (não tmpfs: /tmp por serviço) — único modo de compartilhar tmpfs entre containers (Pitfall 1 RESEARCH.md)"
  - "env_file: .env em api e worker — config consolidada, sem duplicação de vars no compose"
  - "mem_limit: 128m/128m/512m/1g — baseado em footprint de cada serviço no i5-3210M/4GB"
  - "DEV_MODE=true no .env — Redis sem auth em deploy interno privado (Pitfall 4)"

patterns-established:
  - "docker compose port redis/bgutil retorna :0 quando sem ports: — confirma portas não expostas ao host"
  - ".env separado de .env.example — operador copia e ajusta sem risco de commitar segredos"

requirements-completed:
  - DEPLOY-05
  - DEPLOY-06

duration: 30min
completed: 2026-05-15
---

# Plan 13-04: docker-compose.yml + .env.example Summary

**Stack de 4 serviços (api, worker, redis, bgutil) com rede bridge isolada e volume tmpfs compartilhado — DEPLOY-05 e DEPLOY-06 gates verdes**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-05-15
- **Tasks:** 3 (2 auto + 1 human-verify)
- **Files modified:** 2

## Accomplishments

- `.env.example` atualizado: hostnames compose (`redis://redis:6379/0`, `http://bgutil:4416`), `DEV_MODE=true`, legado `YTDLP_COOKIES_FILE`/`YTDLP_PO_TOKEN` removido
- `docker-compose.yml` com 4 serviços + rede `soundgrabber_net` + volume `sg_tmp` (tmpfs compartilhado) + `restart: unless-stopped` em todos
- **Gate DEPLOY-05:** `docker compose config | grep -c "unless-stopped"` = **4** ✓
- **Gate DEPLOY-06:** worker escreve `/tmp/sg_test.txt`; api lê o mesmo arquivo ✓
- api responde HTTP 200 em `localhost:8000` ✓
- Redis ping retorna `True` de dentro do container api ✓
- Redis e bgutil sem portas expostas ao host (`docker compose port` retorna `:0`) ✓

## Task Commits

1. **Task 1: Criar .env.example** — `04c358f` (config(13-04): update .env.example for docker-compose local deploy)
2. **Task 2: Criar docker-compose.yml** — `6215b24` (build(13-04): add docker-compose with 4 services and shared tmpfs volume)
3. **Task 3: docker compose up + Gates manuais** — validação humana (sem commit de código; resultado registrado aqui)

## Files Created/Modified

- `docker-compose.yml` — 4 serviços + rede soundgrabber_net + volume sg_tmp (driver=local, type=tmpfs, size=512m)
- `.env.example` — template atualizado para deploy compose local

## docker compose ps (estado final)

```
NAME                      IMAGE                 COMMAND                  SERVICE   STATUS
soundgrabber20-api-1      soundgrabber:latest   "uvicorn api.main:ap…"   api       Up 5 minutes       0.0.0.0:8000->8000/tcp
soundgrabber20-bgutil-1   jim60105/bgutil-pot   "/dumb-init -- /bgut…"   bgutil    Up 5 minutes       4416/tcp
soundgrabber20-redis-1    redis:7-alpine        "docker-entrypoint.s…"   redis     Up 5 minutes (healthy)  6379/tcp
soundgrabber20-worker-1   soundgrabber:latest   "celery -A api.tasks…"   worker    Up 5 minutes       8000/tcp
```

## Gate DEPLOY-05

```
$ docker compose config | grep -c "unless-stopped"
4
```

## Gate DEPLOY-06

```
$ docker compose exec worker touch /tmp/sg_test.txt   # exit 0
$ docker compose exec api ls -la /tmp/sg_test.txt
-rw-r--r-- 1 root root 0 May 15 18:10 /tmp/sg_test.txt   # arquivo visível na api ✓
$ docker compose exec worker rm -f /tmp/sg_test.txt   # limpeza
```

## Verificações Complementares

| Verificação | Comando | Resultado |
|-------------|---------|-----------|
| Redis sem porta host | `docker compose port redis 6379` | `:0` (sem binding real) ✓ |
| bgutil sem porta host | `docker compose port bgutil 4416` | `:0` (sem binding real) ✓ |
| api HTTP | `curl -w "%{http_code}" http://localhost:8000/` | `200` ✓ |
| Redis ping | `redis.Redis(host='redis').ping()` de dentro de api | `True` ✓ |
| Restart policy | `docker inspect ... RestartPolicy.Name` | `unless-stopped` ✓ |

## Logs relevantes

- `worker`: `Connected to redis://redis:6379/0` → `celery@... ready.` — sem erros
- `api`: `Application startup complete.` — aviso esperado sobre YTDLP_CACHE_DIR (Phase 14 resolve)
- `bgutil`: `POT server v0.8.1 listening on 0.0.0.0:4416` — pronto para PO Tokens
- `redis`: `Ready to accept connections tcp` — Healthy

## Decisões Feitas

- `docker compose port redis/bgutil` retorna `:0` (não erro explícito) quando sem `ports:` — comportamento normal do Docker Compose v2, confirma ausência de binding no host
- Warning `YTDLP_CACHE_DIR não configurado` é esperado em Phase 13 — cookies são configurados na Phase 14 via bind mount

## Deviações do Plano

Nenhuma — plano executado exatamente como especificado.

## Issues Encontrados

Nenhum.

## Resumo Phase 13 — Cobertura de Requisitos

| Requisito | Plano | Status |
|-----------|-------|--------|
| DEPLOY-04 — imagem python:3.11-slim sem imageio-ffmpeg/librosa | Plans 02 + 03 | ✓ GREEN |
| DEPLOY-05 — restart: unless-stopped nos 4 serviços | Plan 04 | ✓ GREEN |
| DEPLOY-06 — volume tmpfs compartilhado entre api e worker | Plan 04 | ✓ GREEN |

## Next Phase Readiness

- Stack local validada — Phase 14 pode iniciar: cookies.txt via bind mount + deploy.sh para o notebook i5 + E2E com YouTube real
- Warning `YTDLP_CACHE_DIR não configurado` será resolvido na Phase 14 (bind mount `/data/yt-dlp-cache`)
- Para parar a stack local: `docker compose down` (ou `docker compose down -v` para remover volume)

---
*Phase: 13-docker-compose*
*Completed: 2026-05-15*
