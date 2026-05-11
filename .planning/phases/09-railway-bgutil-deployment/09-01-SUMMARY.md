---
plan: 09-01
phase: 09-railway-bgutil-deployment
status: complete
completed: "2026-05-11"
requirements:
  - DEPLOY-02
  - DEPLOY-03
self_check: PASSED
---

# Summary — 09-01: Railway bgutil Deployment Verification

## What Was Built

Esta fase foi de **verificação**, não de configuração. Validou que a integração
bgutil ↔ Uvicorn ↔ Celery Worker no Railway está funcional ponta-a-ponta.

## What Was Verified

| Verificação | Resultado |
|-------------|-----------|
| Celery Worker deployment SUCCESS (2d871c8e) | ✓ PASS |
| Logs Celery: `celery@ ready.` + `soundgrabber.process_job` registrado | ✓ PASS |
| Logs Celery: sem strings proibidas de bgutil | ✓ PASS |
| Uvicorn deployment SUCCESS (498fa759) | ✓ PASS |
| Logs Uvicorn: `Application startup complete` + `Uvicorn running on` | ✓ PASS |
| Logs Uvicorn: sem strings proibidas de bgutil | ✓ PASS |
| URL pública: `https://soundgrabber-test.up.railway.app` | ✓ PASS |
| GET /health → HTTP 200 `{"status":"ok"}` | ✓ PASS |
| POST /jobs → status=done com bpm=116, key=G major | ✓ PASS |
| bgutil gerou PO Token + yt-dlp baixou 2.88MiB | ✓ PASS (confirmado por logs Celery) |
| Pipeline completo em ~22s | ✓ PASS |

## Key Files Created

- `.planning/phases/09-railway-bgutil-deployment/09-01-SMOKE-TEST.md` — evidência completa
  com logs de deployment, gates negativos confirmados e resultado do job E2E

## Deviations

**Deployment IDs atualizados:** Os deployments `10ec98b3` (Celery) e `02cda13b` (Uvicorn)
referenciados no plano foram substituídos por redeployments mais recentes (`2d871c8e` e `498fa759`).
Os IDs ativos foram verificados via `mcp__railway__list-deployments`.

**WAV download retorna 410:** O endpoint `/files/{job_id}` retorna 410 "File expired" porque
Uvicorn e Celery Worker são containers Railway separados com `/tmp` isolados. O WAV é criado
no Celery Worker mas o endpoint de download roda no Uvicorn. Este é um bug arquitetural
fora do escopo de DEPLOY-02/DEPLOY-03 — o pipeline (bgutil + download + análise) está provado
funcional pelos logs do Celery Worker.

## Requirements Coverage

- **DEPLOY-02:** bgutil rodando na porta 4416 e acessível via private network — **SATISFEITO**
  (yt-dlp+bgutil baixou 2.88MiB sem erro; Celery Worker logs confirmam download bem-sucedido)
- **DEPLOY-03:** BGUTIL_BASE_URL configurado em Uvicorn e Celery Worker — **SATISFEITO**
  (logs de startup de ambos os serviços sem "BGUTIL_BASE_URL not set"; pipeline funcional)

## Known Issue (to address in future phase)

O download do WAV (`GET /files/{id}`) retorna 410 em produção porque o arquivo existe no
container do Celery Worker mas o endpoint de download roda no container do Uvicorn. Para
resolver: compartilhar storage (volume Railway ou Redis para bytes pequenos) ou mover
o download para o próprio worker via redirect.
