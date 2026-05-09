# Phase 7 — Deploy Log (Railway)

**Data:** 2026-05-09
**Operador:** Renan Cavenaghi

## Serviços provisionados

| Serviço | Tipo | Status | Notas |
|---------|------|--------|-------|
| web | uvicorn via Procfile | Active | URL: https://soundgrabber-test.up.railway.app |
| celery-worker | GitHub repo + start command override | Active | `celery -A api.tasks worker --loglevel=info --concurrency=3` |
| Redis | Railway Redis | Active | REDIS_URL injetado com senha via `${{Redis.REDIS_URL}}` |

## Variáveis de ambiente

**web service:**
- `REDIS_URL` = `${{Redis.REDIS_URL}}` (resolvido em runtime com senha)
- `WAV_TTL_SECONDS` = `900`
- `RATE_LIMIT_PER_MINUTE` = `3`
- `MAX_QUEUE_DEPTH` = `50`
- `JOB_POLL_RATE_LIMIT_PER_MINUTE` = `60`
- `FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE` = `10`
- `DEV_MODE` = (NÃO definido — D-14)

**celery-worker service:** mesmas variáveis do web service.

## Smoke test outputs

### SEC-INFRA-01 (Redis auth enforcement)
App iniciou com sucesso — sem RuntimeError no startup. Confirmado pelo `/health` retornando `{"status":"ok"}`. O `_check_redis_auth` passou porque o Railway injetou REDIS_URL com credenciais via `${{Redis.REDIS_URL}}`.

### SEC-INFRA-02 (uvicorn não exposto diretamente)
Railway expõe apenas HTTPS público (porta 443). A porta interna `$PORT` (8080 no Railway) é isolada pelo edge proxy — não acessível diretamente da internet.

### SEC-INFRA-03 (HTTP → HTTPS 301)
```
$ curl -s -o /dev/null -w "HTTP code: %{http_code}\nLocation: %{redirect_url}\n" "http://soundgrabber-test.up.railway.app/"
HTTP code: 301
Location: https://soundgrabber-test.up.railway.app/
```

### SEC-INFRA-04 (HSTS)
```
$ curl -sI https://soundgrabber-test.up.railway.app/health | grep -i strict-transport-security
strict-transport-security: max-age=31536000; includeSubDomains
```

### /health (HTTPS)
```
$ curl -s https://soundgrabber-test.up.railway.app/health
{"status":"ok"}
```

## Notas operacionais

- Build falhou inicialmente com Railpack `No start command detected` — resolvido adicionando `Procfile` na raiz (Railpack substituiu Nixpacks como builder padrão do Railway).
- Primeiro deploy falhou com `RuntimeError: REDIS_URL does not contain a password` porque as variáveis de ambiente ainda não tinham sido configuradas no web service — resolvido configurando `REDIS_URL = ${{Redis.REDIS_URL}}` nas Variables.
- `builder = "NIXPACKS"` removido do `railway.toml` pois o builder atual do Railway é Railpack.
