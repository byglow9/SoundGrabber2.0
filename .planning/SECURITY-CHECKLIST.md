# Security Checklist — SoundGrabber

**Fonte de verdade dos controles de seguranca ativos.** Atualizar sempre que um novo controle for adicionado ou removido. Esta checklist eh referenciada por `CLAUDE.md > Security Gate` e deve estar verde antes de cada deploy de producao.

**Ultima atualizacao:** Phase 7 (Infrastructure Security)
**Proxima revisao:** v1.2 (CSP sem `'unsafe-inline'`)

## Como usar

1. Antes de cada deploy de producao, percorrer este checklist do topo ao fim.
2. Cada item tem um comando de verificacao automatizada (quando aplicavel).
3. Se um item falhar, NAO fazer deploy ate corrigir ou registrar excecao em `.planning/STATE.md > Key Decisions`.
4. Ao adicionar nova feature, conferir contra `CLAUDE.md > Security Gate` antes do merge.

---

## 1. Filesystem Permissions

### SEC-FILE-01 — WAV files em /tmp criados com 0o600

- [ ] `pipeline.py::download_audio()` chama `os.chmod(wav_path, 0o600)` antes de `return wav_path`
- **Verificacao:** `pytest tests/test_security.py::test_wav_file_permissions -x`
- **Verificacao runtime:** apos rodar pipeline com URL valida, `stat -c '%a' /tmp/sg_*.wav` retorna `600`
- **Threat:** Information Disclosure — outros usuarios do OS poderiam ler WAVs sem este chmod

### SEC-FILE-02 — start.sh com permissoes 750

- [ ] `start.sh` tem `chmod 750 "$(realpath "$0")"` apos `set -e`
- **Verificacao:** `pytest tests/test_security.py::test_startsh_permissions -x`
- **Verificacao runtime:** apos `bash start.sh`, `ls -l start.sh` mostra `-rwxr-x---`
- **Threat:** Elevation of Privilege — outros usuarios poderiam executar start.sh

---

## 2. API Rate Limiting

### SEC-API-01 — GET /jobs/{id} rate limit 60/min

- [ ] `api/main.py::get_job` decorado com `@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")`
- [ ] Assinatura inclui `request: Request, response: Response`
- [ ] `JOB_POLL_RATE_LIMIT_PER_MINUTE` configuravel via env (default 60)
- **Verificacao:** `pytest tests/test_security.py::test_rate_limit_get_jobs -x`
- **Threat:** DoS via polling agressivo

### SEC-API-02 — GET /files/{id} rate limit 10/min

- [ ] `api/main.py::download_file` decorado com `@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")`
- [ ] Assinatura inclui `request: Request, response: Response`
- [ ] `FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE` configuravel via env (default 10)
- **Verificacao:** `pytest tests/test_security.py::test_rate_limit_get_files -x`
- **Threat:** DoS via download bombing (custo de I/O alto)

### SEC-API-03 — GET /health (liveness Redis)

- [ ] Rota `@app.get("/health")` existe em `api/main.py`
- [ ] Retorna 200 `{"status": "ok"}` quando `_redis.ping()` succeeds
- [ ] Retorna 503 `{"status": "unavailable"}` em `redis.exceptions.ConnectionError` ou `TimeoutError`
- [ ] NAO esta atras de rate limit (intencional — health checks de monitoring)
- **Verificacao:** `pytest tests/test_security.py::test_health_redis_ok tests/test_security.py::test_health_redis_down -x`
- **Threat:** Information Disclosure — body retorna apenas status; nao expoe versao/host/metricas

### POST /jobs rate limit 3/min (Phase 3 — pre-existente)

- [ ] `submit_job` decorado com `@limiter.limit(f"{settings.rate_limit_per_minute}/minute")`
- **Verificacao:** `pytest tests/test_api.py::test_rate_limit_returns_429 -x`

---

## 3. HTTP Hardening (controles ja implementados em api/main.py)

### SEC-TEST-01 — Body size limit 4KB

- [ ] Middleware `_limit_body_size` retorna 413 para `Content-Length > 4096`
- **Verificacao:** `pytest tests/test_security.py::test_body_size_limit -x`
- **Threat:** Memory exhaustion via body injection

### SEC-TEST-02 — Security headers

- [ ] Middleware `_security_headers` injeta em TODAS as respostas:
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: no-referrer`
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none';`
- **Verificacao:** `pytest tests/test_security.py::test_security_headers -x`
- **Nota:** `'unsafe-inline'` em style-src eh intencional (HTML Y2K usa inline styles); documentado em REQUIREMENTS.md > Out of Scope

### SEC-TEST-03 — /docs /redoc /openapi.json desabilitados em producao

- [ ] FastAPI configurado com `docs_url=None`, `redoc_url=None`, `openapi_url=None` quando `DEBUG != "true"`
- [ ] `.env` de producao NAO tem `DEBUG=true`
- **Verificacao:** `pytest tests/test_security.py::test_docs_routes_disabled -x` (3 testes via parametrize)

### SEC-TEST-04 — Queue depth limit (503)

- [ ] `submit_job` checa `_redis.llen("celery") >= settings.max_queue_depth` (default 50)
- [ ] Retorna 503 `"Service busy. Please try again later."` quando excede
- **Verificacao:** `pytest tests/test_security.py::test_queue_depth_limit -x`
- **Threat:** Queue exhaustion via job spam

### SEC-TEST-05 — Rate limits GET /jobs e GET /files

- [ ] Coberto por SEC-API-01 e SEC-API-02 acima
- **Verificacao:** `pytest tests/test_security.py::test_rate_limit_get_jobs tests/test_security.py::test_rate_limit_get_files -x`

---

## 4. Pre-Deploy Audit

### SEC-TEST-06 — pip-audit antes de cada deploy

- [ ] Documentado em `README.md > Pre-Deploy Security Audit`
- [ ] Comando exato: `pip install pip-audit && pip-audit -r requirements.txt`
- [ ] Politica para vulnerabilidades:
  - HIGH/CRITICAL sem patch -> NAO fazer deploy sem decisao explicita
  - HIGH/CRITICAL com patch -> atualizar dependencia + bump em requirements.txt
  - LOW/MEDIUM -> avaliar caso a caso
- **Verificacao:** rodar `pip-audit -r requirements.txt` e revisar output
- **Verificacao docs:** `grep -q "pip install pip-audit" README.md && grep -q "pip-audit -r requirements.txt" README.md`

---

## 5. Policy & Documentation

### SEC-POLICY-01 — Security Gate em CLAUDE.md

- [ ] Secao `## Security Gate` existe em `CLAUDE.md`
- [ ] Cobre: HTTP endpoints, /tmp files, shell scripts, testes, documentacao
- [ ] Referencia explicita a este checklist e a `tests/test_security.py`
- **Verificacao:** `grep -q "^## Security Gate$" CLAUDE.md`

### SEC-POLICY-02 — Este arquivo

- [ ] `.planning/SECURITY-CHECKLIST.md` existe (este arquivo)
- [ ] Cobre todos os SEC-* da Phase 6
- [ ] Atualizado a cada nova feature que adicione controle
- **Verificacao:** `test -f .planning/SECURITY-CHECKLIST.md`

---

## 6. Infrastructure Security (Phase 7)

### SEC-INFRA-01 — Redis exige autenticacao em producao

- [ ] `api/main.py::_check_redis_auth(redis_url, dev_mode)` levanta `RuntimeError` quando `"@" not in redis_url` e `dev_mode=False`
- [ ] `api/main.py:lifespan` chama `_check_redis_auth(settings.redis_url, settings.dev_mode)` antes de iniciar a sweeper thread
- [ ] `api/config.py::Settings` tem campo `dev_mode: bool` lido da env var `DEV_MODE` (default `False`)
- [ ] Producao Railway: `DEV_MODE` NAO eh definido nas env vars do servico (D-14)
- [ ] Producao Railway: `REDIS_URL` injetado pelo servico Railway Redis tem formato `redis://default:<senha>@redis.railway.internal:6379` (D-08)
- **Verificacao:** `pytest tests/test_security.py::test_redis_auth_required tests/test_security.py::test_redis_auth_bypass_dev_mode tests/test_security.py::test_redis_auth_passes_with_password -x`
- **Verificacao runtime:** apos deploy Railway, logs do servico nao mostram `RuntimeError`; o servico fica em estado "Active" e responde 200 em `/health`
- **Threat:** Elevation of Privilege — Redis sem senha exposto na rede privada Railway permitiria acesso de outros servicos comprometidos

### SEC-INFRA-02 — Uvicorn nao exposto diretamente a internet

- [ ] `railway.toml::[deploy]::startCommand` usa `--host 0.0.0.0 --port $PORT` (necessario para o proxy Railway acessar o container; D-11)
- [ ] Railway PaaS isola o container do acesso direto da internet — todas as requisicoes passam pelo edge proxy Railway que termina TLS e faz forwarding para o container privado
- [ ] `start.sh` (desenvolvimento local) eh separado de `railway.toml` (producao); start.sh roda em `0.0.0.0:8000` na maquina local, fora do escopo do controle de producao (D-12)
- **Verificacao:** `grep -E '^startCommand.*0\.0\.0\.0.*\$PORT' railway.toml`
- **Verificacao runtime:** apos deploy, tentar conexao TCP direta na porta interna do container falha (apenas o subdomain HTTPS Railway responde)
- **Threat:** Spoofing / Tampering — exposicao direta permitiria bypass de TLS e dos headers de seguranca aplicados pelo edge

### SEC-INFRA-03 — HTTPS via Railway (HTTP -> HTTPS 301)

- [ ] Railway PaaS faz HTTPS termination automatico para `*.up.railway.app` (D-04, D-10)
- [ ] Railway PaaS faz redirect 301 HTTP -> HTTPS automatico para GET requests (D-05)
- [ ] Nenhuma configuracao manual necessaria (sem nginx, sem certbot, sem cron de renovacao)
- **Verificacao runtime:** `curl -s -o /dev/null -w "%{http_code}\n" http://<app>.up.railway.app/` retorna `301`
- **Verificacao runtime:** `curl -sI https://<app>.up.railway.app/` retorna `200` com `Server: railway-edge` ou similar
- **Threat:** Tampering (MITM) — HTTPS obrigatorio impede injecao de conteudo em transito

### SEC-INFRA-04 — HSTS header em todas as respostas

- [ ] `api/main.py::_security_headers` injeta `Strict-Transport-Security: max-age=31536000; includeSubDomains` em todas as respostas
- [ ] Header presente em todas as rotas (testado via TestClient em test_hsts_header)
- **Verificacao:** `pytest tests/test_security.py::test_hsts_header -x`
- **Verificacao runtime:** `curl -sI https://<app>.up.railway.app/health | grep -i strict-transport-security` retorna `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- **Threat:** Tampering (downgrade HTTPS->HTTP) — apos primeira visita HTTPS, browser refuta HTTP por 1 ano

---

## 7. Threats NAO mitigados nesta fase (deferidos)

Estes itens estao escopados para v1.2 ou versoes futuras:

- **CSP sem `'unsafe-inline'`** — requer remover inline styles do HTML Y2K (v1.2)
- **Private /tmp directory por job** — `/tmp/sg_{id}/` com `os.mkdir(mode=0o700)` (v2)
- **Job cancellation endpoint** — DELETE /jobs/{id} com auth (v2)

---

## 8. Verificacao end-to-end (rodar antes de cada deploy)

Bloco de comandos shell para validar a checklist completa antes de deploy. Cada bloco em fence bash.

```bash
# 1. Suite completa de seguranca
pytest tests/test_security.py -v

# 2. Suite completa do projeto (sem regressao)
pytest tests/ -v -m "not e2e and not integration"

# 3. Audit de dependencias
pip install pip-audit
pip-audit -r requirements.txt

# 4. Permissoes filesystem (apos primeira execucao do start.sh)
ls -l start.sh                     # esperado: -rwxr-x---
stat -c '%a' /tmp/sg_*.wav 2>/dev/null | sort -u  # esperado: 600

# 4.5 Verificar railway.toml e HSTS local
test -f railway.toml && echo "railway.toml OK" || echo "railway.toml MISSING"
grep -q 'startCommand.*0.0.0.0.*$PORT' railway.toml && echo "Railway startCommand OK"
pytest tests/test_security.py::test_hsts_header -q

# 5. Smoke test do health endpoint (com server up)
curl -s http://localhost:8000/health

# 6. Smoke test rate limit POST /jobs (com server up)
for i in $(seq 1 4); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/jobs \
    -H 'Content-Type: application/json' \
    -d '{"youtube_url":"https://www.youtube.com/watch?v=abc"}'
done
# esperado: 202, 202, 202, 429
```

---

## 9. Historico de mudancas

| Data | Phase | Controles adicionados |
|------|-------|----------------------|
| Phase 3 | Hardening | Body size, security headers, docs disabled, queue depth, rate limit POST /jobs |
| Phase 6 | Application Security | WAV chmod 0o600, start.sh chmod 750, rate limit GET /jobs e /files, /health endpoint, pip-audit policy, este checklist |
| Phase 7 | Infrastructure Security | Redis auth enforcement (DEV_MODE bypass), HSTS via FastAPI middleware, Railway PaaS deploy (railway.toml), HTTPS automatico Railway |
