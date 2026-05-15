---
plan: 14-04
phase: 14-pipeline-e2e-on-notebook
status: complete
date: 2026-05-15
---

# Summary — Plan 14-04: Checkpoint E2E Notebook

## O que foi feito

Checkpoint humano bloqueante executado com sucesso. Operador (glow/Moisés) validou
AUTH-04, AUTH-05 e PIPE-08 no notebook HP via Tailscale.

## Resultados

**AUTH-04 — bind mount :ro + cookies**
- /data/yt-dlp-cache criado com chmod 700, dono glow
- cookies.txt 3160 bytes copiado via scp, chmod 600
- Bind mount visível dentro do container api: `-rw------- 1000 1000 3160 bytes`
- Zero ocorrências de CRITICAL nos logs de startup

**AUTH-05 — deploy via scripts/deploy.sh**
- `bash ~/soundgrabber/scripts/deploy.sh` executou via SSH com exit 0
- git pull + docker compose up --build -d: 4 containers Started

**PIPE-08 — 3 beats E2E (Plano A — sem bgutil)**

| Beat | BPM | Key | Camelot | Duração |
|------|-----|-----|---------|---------|
| 8GTUZzFzc9k | 116.8 | G major | 9B | 180.0s |
| YQ64BRjEml0 | 150.4 | C major | 8B | 161.7s |
| YRINbEzQFSQ | 114.9 | G major | 9B | 210.8s |

## Fix aplicado durante execução

`pipeline.py` — yt-dlp tentava salvar cookies no bind mount `:ro` causando OSError.
Fix: `_writable_cookies()` copia cookies.txt para /tmp gravável antes de passar ao yt-dlp.
Commit: `fix(14): copy cookies.txt to writable /tmp before passing to yt-dlp — EROFS on :ro bind mount`

## Artefato

`.planning/phases/14-pipeline-e2e-on-notebook/14-DEPLOY-LOG.md`

## Self-Check: PASSED
