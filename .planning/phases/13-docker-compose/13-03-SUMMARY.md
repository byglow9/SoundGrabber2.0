---
phase: 13-docker-compose
plan: "03"
subsystem: infra
tags: [docker, dockerfile, dockerignore, essentia, nodejs, ffmpeg]

requires:
  - phase: 13-02
    provides: requirements.txt sem librosa/imageio-ffmpeg; pipeline.py com detect_tuning via Essentia

provides:
  - Dockerfile com python:3.11-slim + ffmpeg + Node.js 20 (NodeSource) + pip install + CMD uvicorn
  - .dockerignore excluindo .venv (681MB), .git, cookies, .planning do build context
  - Imagem soundgrabber:latest construída e validada via Gate D-07

affects: [13-04-docker-compose, deploy]

tech-stack:
  added: [Docker 28.4.0, python:3.11-slim base image, NodeSource setup_20.x]
  patterns: [requirements.txt copiado antes de COPY . . para cache de layer, NodeSource para Node 20 em Debian bookworm]

key-files:
  created:
    - Dockerfile
    - .dockerignore
  modified: []

key-decisions:
  - "NodeSource setup_20.x em vez de apt nodejs — bookworm tem Node 18, gate D-05 exige >=20"
  - "COPY requirements.txt antes de COPY . . — cache de layer evita reinstalar deps em cada mudança de código"
  - "ca-certificates no apt antes do curl NodeSource — necessário para TLS do deb.nodesource.com"
  - "Container roda como root (aceito) — D-13 cobre vetores críticos via compose, non-root deferido para v2"

patterns-established:
  - "Build context limpo: .dockerignore replica .gitignore e expande com .venv/, cookies, .planning/"
  - "Imagem única soundgrabber:latest — worker override CMD via command: no compose (Plan 04)"

requirements-completed:
  - DEPLOY-04

duration: 87min (build 87s + validação manual)
completed: 2026-05-15
---

# Plan 13-03: Dockerfile + .dockerignore Summary

**Imagem soundgrabber:latest (python:3.11-slim + ffmpeg + Node 20 via NodeSource + Essentia) construída e validada via Gate D-07 com exit 0**

## Performance

- **Duration:** ~90 min (tasks auto em sessão anterior + build + validação manual)
- **Completed:** 2026-05-15
- **Tasks:** 3 (2 auto + 1 human-verify)
- **Files modified:** 2

## Accomplishments

- `.dockerignore` com 20+ entradas excluindo .venv (681MB), .git, cookies.txt, .env, .planning/ — build context enxuto
- `Dockerfile` com camada apt (ffmpeg + libsndfile1 + curl + ca-certificates + Node 20 via NodeSource), camada pip separada para cache, CMD uvicorn
- Gate D-07 aprovado: `import essentia.standard, yt_dlp, fastapi, celery` — exit 0, output `OK`
- Node.js `v20.20.2` confirmado (NodeSource funcionou corretamente)
- ffprobe em `/usr/bin/ffprobe` ✓
- `import pipeline` + `detect_tuning` funcionam dentro do container ✓
- Tamanho da imagem: **1.12 GB** (dentro da faixa esperada 1.0–1.5 GB)

## Task Commits

1. **Task 1: Criar .dockerignore** — `65ef35a` (build(13-03): add docker build ignore rules)
2. **Task 2: Criar Dockerfile** — `852e382` (build(13-03): add soundgrabber docker image)
3. **Task 3: Build + Gate D-07** — validação humana (sem commit de código; resultado registrado aqui)

## Files Created/Modified

- `Dockerfile` — imagem soundgrabber:latest com python:3.11-slim + ffmpeg + Node 20 + pip install + CMD uvicorn
- `.dockerignore` — exclui .venv, .git, cookies, .env, .planning, __pycache__, dump.rdb, bordas/, *.png

## Gate D-07 — Output Exato

```
$ docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"
[   INFO   ] MusicExtractorSVM: no classifier models were configured by default
OK
```
Exit code: 0 ✓

## Verificações Adicionais

| Verificação | Comando | Resultado |
|-------------|---------|-----------|
| Node.js >=20 | `node --version` | `v20.20.2` ✓ |
| ffprobe path | `which ffprobe` | `/usr/bin/ffprobe` ✓ |
| pipeline import | `import pipeline` | `<function detect_tuning at 0x...>` ✓ |
| Tamanho imagem | `docker images ... --format "{{.Size}}"` | `1.12GB` ✓ |

## Decisões Feitas

- Contexto Docker apontado para `default` (sistema) em vez de `desktop-linux` — Docker Desktop não instalado, daemon do sistema em uso
- Nenhuma lib apt extra necessária: Essentia importou sem erro de linker na primeira tentativa

## Deviações do Plano

Nenhuma — plano executado exatamente como especificado. Libs extras de Essentia (libfftw3-3, libyaml-cpp0.7, libtag1v5) não foram necessárias; python:3.11-slim + libsndfile1 foi suficiente.

## Issues Encontrados

- Docker CLI configurado com contexto `desktop-linux` por padrão (Docker Desktop não ativo) — resolvido com `docker context use default`

## Next Phase Readiness

- Imagem `soundgrabber:latest` disponível localmente — Plan 04 pode criar docker-compose.yml referenciando esta imagem
- Para deploy no notebook: `git pull` + `docker build -t soundgrabber:latest .` (mesma sequência, mesma arquitetura x86_64)
- Nenhum bloqueador identificado

---
*Phase: 13-docker-compose*
*Completed: 2026-05-15*
