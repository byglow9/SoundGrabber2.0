---
plan: 07-04
phase: 07-infrastructure-security
status: complete
completed: 2026-05-09
self_check: PASSED
---

# Summary — Plan 07-04: Deploy Railway (Checkpoint)

## What was built

Deploy de validação em Railway com 3 serviços: web (uvicorn), celery-worker (Celery), e Redis. Todos os 4 controles SEC-INFRA-* verificados em ambiente real.

## Key files created

- `.planning/phases/07-infrastructure-security/07-DEPLOY-LOG.md` — registro completo do deploy com smoke test outputs

## Smoke tests — todos verdes

| Controle | Verificação | Resultado |
|----------|------------|-----------|
| SEC-INFRA-01 | Startup sem RuntimeError (`/health` retorna 200) | ✓ PASS |
| SEC-INFRA-02 | Apenas HTTPS público, porta interna isolada | ✓ PASS |
| SEC-INFRA-03 | `curl http://...` retorna `301` | ✓ PASS |
| SEC-INFRA-04 | Header `Strict-Transport-Security: max-age=31536000; includeSubDomains` | ✓ PASS |

## URL de produção

`https://soundgrabber-test.up.railway.app`

## Desvios e ajustes

- Adicionado `Procfile` na raiz: Railpack (novo builder do Railway) não lê `startCommand` do `railway.toml` em build-time — requer `Procfile`.
- Removido `builder = "NIXPACKS"` do `railway.toml`: Railpack é o builder padrão atual.
- Variáveis de ambiente configuradas manualmente no dashboard Railway (necessário — Railway não herda vars entre serviços).
