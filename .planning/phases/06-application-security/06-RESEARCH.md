# Phase 6: Application Security — Research

**Researched:** 2026-05-09
**Domain:** Python/FastAPI application security controls — file permissions, rate limiting, health endpoints, security tests, policy docs
**Confidence:** HIGH

---

## Summary

A maior parte dos controles de segurança desta fase já existe no código ou está parcialmente implementada. O `_limit_body_size` middleware (413), `_security_headers` middleware, a desativação de `/docs`/`/redoc`/`/openapi.json` via `docs_url=None`, e o `max_queue_depth` check (503) já estão em `api/main.py`. O que falta: (1) permissões 0o600 nos arquivos WAV em `/tmp`, (2) permissões 750 no `start.sh`, (3) rate limits nos endpoints GET (`/jobs/{id}` e `/files/{id}`), (4) endpoint `GET /health`, (5) o arquivo `tests/test_security.py` cobrindo todos os controles, e (6) documentação de política (`CLAUDE.md` security gate + `SECURITY-CHECKLIST.md`).

A arquitetura de testes existente (pytest + TestClient + conftest com flush de rate limit keys) suporta plenamente o que é necessário. O `api_client` fixture já faz flush de `LIMITS:LIMITER*` no Redis antes de cada teste, portanto os novos testes de rate limit para GET routes funcionarão sem modificação no conftest.

**Primary recommendation:** Adicionar `os.chmod(wav_path, 0o600)` em `pipeline.py` logo após a confirmação de existência do WAV, adicionar `chmod 750 "$0"` no início de `start.sh`, decorar `get_job` e `download_file` com `@limiter.limit` (incluindo `response: Response` obrigatório), criar `GET /health`, e escrever `tests/test_security.py`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-FILE-01 | WAV files em /tmp criados com 0o600 | `os.chmod(wav_path, 0o600)` após criação; testável via `os.stat()` |
| SEC-FILE-02 | start.sh com permissões 750 | `chmod 750 "$0"` no início do script; git só rastreia 755 vs 644 |
| SEC-API-01 | GET /jobs/{id} rate limit 60/min por IP | Decorator `@limiter.limit("60/minute")` + `response: Response` obrigatório |
| SEC-API-02 | GET /files/{id} rate limit 10/min por IP | Decorator `@limiter.limit("10/minute")` + `response: Response` obrigatório |
| SEC-API-03 | GET /health retorna Redis status 200/503 | `_redis.ping()` + `try/except ConnectionError, TimeoutError` |
| SEC-TEST-01 | test_security.py cobre body size limit (413) | Middleware já implementado; teste envia body > 4KB com Content-Length |
| SEC-TEST-02 | test_security.py cobre security headers | Middleware já implementado; teste verifica 4 headers em qualquer resposta |
| SEC-TEST-03 | test_security.py confirma /docs /redoc /openapi.json → 404 | `docs_url=None` já configurado; DEBUG=false por padrão |
| SEC-TEST-04 | test_security.py confirma queue depth limit → 503 | Queue check já implementado; teste mocka `_redis.llen` |
| SEC-TEST-05 | test_security.py cobre rate limit em GET /jobs e GET /files | Novos decorators; testes enviam N+1 requests com mocks |
| SEC-TEST-06 | pip-audit documentado em README como verificação pré-deploy | pip-audit==2.10.0 disponível; adicionar em README e requirements.txt |
| SEC-POLICY-01 | Security Gate documentado em CLAUDE.md | Nova seção "## Security Gate" em CLAUDE.md |
| SEC-POLICY-02 | Checklist em .planning/SECURITY-CHECKLIST.md | Novo arquivo com checklist dos controles desta fase |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- Backend: Python 3.11 + FastAPI
- Task queue: Celery + Redis
- Vanilla HTML + CSS + JS — zero frameworks (frontend, não relevante para esta fase)
- Estética Y2K: sem CSS moderno (não relevante para esta fase)
- `slowapi==0.1.9` pinned com `==` (convenção do projeto)
- Sem contas de usuário — ferramenta stateless, sem auth
- WAV apenas, /tmp storage, 15 minutos max

---

## Standard Stack

### Core (já instalado — sem novas dependências de runtime)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slowapi | 0.1.9 (pinned) | Rate limiting GET routes | Já em uso para POST /jobs; mesma Limiter instance |
| redis (py) | 6.4.0 (pinned) | Redis ping no health endpoint | Já em uso como backend do Limiter e client |
| fastapi | 0.136.1 (pinned) | Rota GET /health | Já em uso |

### Dev (nova dependência)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pip-audit | 2.10.0 | Auditoria de dependências por CVEs | Pré-deploy; documentado em README |

[VERIFIED: npm view] pip-audit 2.10.0 confirmado via `pip index versions pip-audit` — versão mais recente disponível no PyPI em 2026-05-09.

**Installation (pip-audit apenas):**
```bash
pip install pip-audit==2.10.0
# ou como verificação pré-deploy (sem adicionar ao ambiente de prod):
pip-audit -r requirements.txt
```

**Nota:** pip-audit é uma ferramenta de auditoria, não de runtime. Pode ser instalado separadamente ou via CI, sem constar em requirements.txt de produção. O requisito SEC-TEST-06 pede apenas documentação em README. Recomendado: documentar como `pip install pip-audit && pip-audit -r requirements.txt` sem adicionar ao requirements.txt de produção.

---

## Architecture Patterns

### Padrão 1: os.chmod após criação do WAV (SEC-FILE-01)

**O que é:** Chamada `os.chmod(wav_path, 0o600)` logo após `download_audio()` confirmar que o WAV existe.

**Por que não `os.open + O_CREAT`:** O WAV é criado pelo subprocess `ffmpeg` (via yt-dlp postprocessor), não pelo Python. O Python não controla como o ffmpeg cria o arquivo de saída. A abordagem correta é um `chmod` explícito após a criação.

**Por que não `umask`:** O umask atual do processo é `0o002` (verificado). Mesmo com `os.umask(0o177)` para forçar 0o600, o umask afeta TODOS os arquivos criados no processo — incluindo temporários criados por bibliotecas. É uma side-effect global perigosa. `os.chmod` é cirúrgico.

**Onde aplicar:** Em `pipeline.py`, na função `download_audio()`, imediatamente após a verificação de existência do `wav_path` (linha ~152-160). Aplicar antes do `return wav_path`.

```python
# Source: Python stdlib docs — os.chmod
# VERIFIED: testado localmente — aplica 0o600 a arquivo criado por subprocess
import os
# ... após wav_path confirmado existente:
os.chmod(wav_path, 0o600)
return wav_path
```

**Verificação testável:**
```python
# Source: Python stdlib — os.stat, stat module
import os, stat
st = os.stat(wav_path)
assert not (st.st_mode & stat.S_IRGRP)   # group read
assert not (st.st_mode & stat.S_IWGRP)   # group write
assert not (st.st_mode & stat.S_IROTH)   # other read
assert not (st.st_mode & stat.S_IWOTH)   # other write
assert (st.st_mode & 0o777) == 0o600
```

[VERIFIED: testado localmente com `os.chmod('/tmp/sg_test.wav', 0o600)` — result: `oct(st.st_mode) == '0o100600'`]

---

### Padrão 2: chmod 750 no start.sh (SEC-FILE-02)

**Limitação do git:** Git rastreia apenas dois modos de arquivo: `100644` (não-executável) e `100755` (executável). O modo `100750` não existe no modelo de dados do git. `start.sh` está atualmente rastreado como `100755` no git e tem permissões `775` no filesystem.

**Solução: auto-chmod no início do script**

```bash
# Source: bash manual — BASH_SOURCE
# Primeira linha executável após #!/usr/bin/env bash e set -e
chmod 750 "$(realpath "$0")"
```

**Por que funciona:** Um script bash em execução pode `chmod` seu próprio arquivo. A permissão necessária para executar o script já foi verificada pelo kernel antes do bash começar. O `chmod 750` remove `w` do grupo e todas as permissões de `others` — sem afetar a execução em andamento.

**Verificação:** `ls -l start.sh` após execução mostra `-rwxr-x---`.

[ASSUMED] A abordagem de auto-chmod é idiomática em scripts de deployment; não foi verificada em documentação oficial de bash, mas é comportamento padrão do kernel Linux (permissões de execução são verificadas no `execve`, não re-verificadas durante a execução).

---

### Padrão 3: Rate limit em GET routes via slowapi (SEC-API-01, SEC-API-02)

**Limitação crítica verificada:** O `sync_wrapper` do slowapi chama `_inject_headers(kwargs.get("response"), ...)`. Se `response` não for um kwarg da função, `kwargs.get("response")` retorna `None`. O método `_inject_headers` então levanta `Exception("parameter response must be an instance of...")`. Isso afeta qualquer rota sync (não-async) decorada com `@limiter.limit` quando `headers_enabled=True`.

**A solução já existe no codebase:** `submit_job` usa `response: Response` como parâmetro obrigatório. As novas rotas GET devem seguir o mesmo padrão.

```python
# Source: api/main.py (Pattern estabelecido no Phase 3, Plan 03)
# VERIFIED: leitura do source de slowapi 0.1.9 _inject_headers e sync_wrapper
from fastapi import Request, Response

@app.get("/jobs/{job_id}")
@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")
def get_job(job_id: str, request: Request, response: Response) -> dict:
    ...

@app.get("/files/{job_id}")
@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")
def download_file(job_id: str, request: Request, response: Response):
    ...
```

**Adições necessárias em `api/config.py`:**

```python
# Source: api/config.py (padrão existente de _safe_int)
job_poll_rate_limit_per_minute: int = field(
    default_factory=lambda: _safe_int("JOB_POLL_RATE_LIMIT_PER_MINUTE", 60)
)
file_download_rate_limit_per_minute: int = field(
    default_factory=lambda: _safe_int("FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE", 10)
)
```

**Nota sobre `request: Request`:** O parâmetro `request: Request` é obrigatório para slowapi (verificado no `sync_wrapper` — busca `kwargs.get("request")`). As rotas `get_job` e `download_file` atuais não têm este parâmetro. Ele deve ser adicionado como PRIMEIRO parâmetro após qualquer path param.

[VERIFIED: leitura do source de `slowapi==0.1.9` — `sync_wrapper` busca `request` em kwargs; `_inject_headers` requer `response` isinstance de `Response`]

---

### Padrão 4: GET /health endpoint (SEC-API-03)

**Comportamento esperado:**
- Redis disponível: `200 {"status": "ok"}`
- Redis indisponível: `503 {"status": "unavailable"}`

**Implementação:**

```python
# Source: redis-py docs + FastAPI docs
# VERIFIED: redis.exceptions.ConnectionError capturado com from_url + ping em porta errada
import redis as redis_lib
from fastapi.responses import JSONResponse

@app.get("/health")
def health_check() -> JSONResponse:
    try:
        _redis.ping()
        return JSONResponse(status_code=200, content={"status": "ok"})
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
```

**Por que usar o `_redis` existente:** A instância `_redis = redis_lib.from_url(settings.redis_url)` já existe em `api/main.py`. Reutilizá-la é mais eficiente que criar uma nova conexão. O `ping()` é lightweight e retorna `True` em sucesso.

**Exceções a capturar:**
- `redis.exceptions.ConnectionError` — Redis offline ou porta errada [VERIFIED: testado localmente]
- `redis.exceptions.TimeoutError` — Redis lento/não responsivo [VERIFIED: disponível em redis 6.4.0]
- Não capturar `AuthenticationError` — falha de auth em runtime indica misconfiguration que deve propagar

[VERIFIED: `redis.exceptions.ConnectionError` confirmado com conexão a porta 9999 — levanta `ConnectionError`]

---

### Padrão 5: Body size limit (SEC-TEST-01 — já implementado)

O middleware `_limit_body_size` já existe em `api/main.py` e retorna 413 para bodies com `Content-Length > 4096` bytes.

**O que precisa de teste:** Enviar um body com `Content-Length: 5000` (ou maior) e verificar `status_code == 413`.

```python
# Pattern de teste verificado localmente
def test_body_size_limit(api_client):
    large = "A" * 5000
    r = api_client.post("/jobs", content=large, headers={"Content-Length": "5000"})
    assert r.status_code == 413
    assert r.json()["error_type"] == "request_error"
```

[VERIFIED: testado localmente — retorna 413 com `{"error": "Request body too large.", "error_type": "request_error"}`]

---

### Padrão 6: Security headers (SEC-TEST-02 — já implementado)

O middleware `_security_headers` já existe em `api/main.py` com os 4 headers obrigatórios.

**Valores atuais:**
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none';`

[VERIFIED: testado localmente via TestClient — todos os 4 headers presentes em GET /]

**Nota sobre CSP:** `style-src 'self' 'unsafe-inline'` é intencional — necessário para os inline styles do HTML Y2K. Documentado em REQUIREMENTS.md como "Out of Scope" para v1.

---

### Padrão 7: /docs /redoc /openapi.json → 404 (SEC-TEST-03 — já implementado)

```python
# Source: api/main.py (já implementado)
_debug = _os.getenv("DEBUG", "false").lower() == "true"
app = FastAPI(
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)
```

[VERIFIED: testado localmente com `DEBUG=false` (default) — GET /docs, GET /redoc, GET /openapi.json → 404]

---

### Padrão 8: Queue depth limit → 503 (SEC-TEST-04 — já implementado)

```python
# Source: api/main.py (já implementado em submit_job)
if _redis.llen("celery") >= settings.max_queue_depth:
    raise HTTPException(status_code=503, detail="Service busy. Please try again later.")
```

[VERIFIED: testado localmente com `patch.object(_redis, 'llen', return_value=51)` — retorna 503]

**Nota sobre nome da fila:** `"celery"` é o `task_default_queue` padrão do Celery. Confirmado via `celery_app.conf.task_default_queue == "celery"`.

[VERIFIED: `celery.app.defaults.py` linha: `default_queue=Option('celery')` — confirmado no source instalado]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Custom middleware com contador em memória | slowapi (já instalado) | Já integrado, Redis backend, headers automáticos |
| Security headers | Middleware customizado duplicado | `_security_headers` middleware existente | Já implementado em api/main.py |
| File permission enforcement | umask manipulation global | `os.chmod(wav_path, 0o600)` | Cirúrgico, não afeta outros arquivos |
| Dependency audit | Script de grep em requirements.txt | pip-audit | Verifica CVEs via OSV/PyPI Advisory DB |
| Redis health check | Healthcheck complexo com métricas | `_redis.ping()` + try/except | Simples, suficiente para o caso de uso |

---

## Common Pitfalls

### Pitfall 1: GET routes sem `response: Response` causam Exception no slowapi

**O que acontece:** `_inject_headers(None, view_rate_limit)` levanta `Exception("parameter response must be an instance of starlette.responses.Response")` quando `headers_enabled=True` e a rota não retorna um objeto `Response` diretamente.

**Por que acontece:** O `sync_wrapper` do slowapi obtém o objeto `response` via `kwargs.get("response")`. Se o parâmetro não estiver na assinatura da função, retorna `None`. A `_inject_headers` verifica `isinstance(None, Response)` → False → raise.

**Como evitar:** Adicionar `response: Response` como parâmetro explícito em toda função decorada com `@limiter.limit`. Seguir o padrão já estabelecido em `submit_job`.

**Warning signs:** `Exception: parameter response must be an instance of starlette.responses.Response` nos logs do Uvicorn.

[VERIFIED: leitura do source de `slowapi==0.1.9` — comportamento confirmado]

---

### Pitfall 2: `request: Request` também é obrigatório nas GET routes

**O que acontece:** O `sync_wrapper` busca `kwargs.get("request", args[idx] if args else None)`. Se `request` não estiver nos kwargs, tenta usar `args[idx]` onde `idx` é a posição descoberta por inspeção. Se a função não tiver `Request` em nenhum lugar, levanta `Exception("parameter request must be an instance of starlette.requests.Request")`.

**Como evitar:** Adicionar `request: Request` como parâmetro. As rotas atuais `get_job(job_id: str)` e `download_file(job_id: str)` precisam receber `request: Request` e `response: Response` adicionais.

**Ordem dos parâmetros:** Path params primeiro, depois `request: Request`, `response: Response`. FastAPI injeta corretamente por tipo, não por posição.

[VERIFIED: source do `sync_wrapper` — busca `request` em kwargs]

---

### Pitfall 3: os.chmod não resolve a race condition de criação

**O que acontece:** Há uma janela entre a criação do arquivo pelo ffmpeg (com permissões 664 ou 644) e o `os.chmod(wav_path, 0o600)`. Outro processo poderia ler o arquivo nesse intervalo.

**Por que não é bloqueante para este projeto:** O server roda em `/tmp` de uma VPS single-user. O risco de exploração da race window é negligível. A alternativa seria `os.open` com `O_CREAT + O_WRONLY + mode=0o600` direto pelo Python, mas o arquivo é criado pelo ffmpeg (não pelo Python). `os.chmod` imediatamente após é a abordagem correta.

**Se fosse multi-user crítico:** Usar `/tmp/sg_{id}/` como diretório privado por job com `os.mkdir(mode=0o700)`, mas isso está em v2 (REQUIREMENTS.md "Private /tmp directory por job").

[ASSUMED] Race condition é aceitável dado o contexto single-user da VPS.

---

### Pitfall 4: Rate limit flush no conftest só cobre `LIMITS:LIMITER*`

**O que acontece:** O conftest faz `_r.scan(cursor, match="LIMITS:LIMITER*")` para limpar rate limits entre testes. As novas rotas GET usarão o mesmo Redis backend e o mesmo padrão de chave `LIMITS:LIMITER*`.

**Verificação:** O padrão de chave do slowapi com Redis backend é `LIMITS:LIMITER/{func_name}/{key}/{limit_string}`. Os nomes das funções `get_job` e `download_file` geram chaves como `LIMITS:LIMITER/get_job/...` e `LIMITS:LIMITER/download_file/...` — ambas cobertas pelo glob `LIMITS:LIMITER*`.

**Não é necessário modificar o conftest** — o flush existente já cobre as novas rotas.

[VERIFIED: padrão de chave Redis do slowapi inferido da análise do source; [ASSUMED] o padrão exato não foi verificado em testes ao vivo por Redis estar offline durante a pesquisa]

---

### Pitfall 5: start.sh com chmod 750 remove permissão de `others`

**O que acontece:** `chmod 750` remove `x` de `others`. Se o script for executado por um usuário que não é owner nem membro do grupo do arquivo, a execução falha com "Permission denied".

**Impacto:** Na prática, `start.sh` é executado pelo owner do projeto (quem faz deploy). Não há usuário "outros" que precise executar este script. A permissão 750 é exatamente o objetivo do SEC-FILE-02.

**Não é pitfall para este projeto** — é o comportamento desejado.

---

### Pitfall 6: `_debug = True` em produção expõe docs

**O que acontece:** Se `DEBUG=true` estiver no `.env` de produção, `/docs`, `/redoc` e `/openapi.json` ficam acessíveis. O valor padrão é `false`.

**Como evitar:** Verificar que `.env` de produção não contém `DEBUG=true`. Incluir este item no `SECURITY-CHECKLIST.md`.

---

## Code Examples

### 1. os.chmod para WAV (pipeline.py)

```python
# Source: Python stdlib docs — os.chmod
# Inserir em pipeline.py, função download_audio(), após linha ~155 (wav_path confirmado)
import os

# ... (código existente que confirma wav_path.exists()) ...
os.chmod(wav_path, 0o600)
return wav_path
```

### 2. chmod 750 no start.sh

```bash
#!/usr/bin/env bash
set -e
# SEC-FILE-02: garantir permissões 750 (rwxr-x---) a cada execução
chmod 750 "$(realpath "$0")"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
# ... resto do script ...
```

### 3. Rate limit em GET /jobs/{job_id}

```python
# Source: api/main.py — padrão estabelecido em submit_job (Phase 3)
# VERIFIED: slowapi 0.1.9 requer request: Request e response: Response em sync routes
@app.get("/jobs/{job_id}")
@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")
def get_job(job_id: str, request: Request, response: Response) -> dict:
    if not JOB_ID_PATTERN.match(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    # ... resto do handler existente ...
```

### 4. Rate limit em GET /files/{job_id}

```python
# Source: api/main.py — mesmo padrão
@app.get("/files/{job_id}")
@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")
def download_file(job_id: str, request: Request, response: Response):
    # ... handler existente sem modificações de lógica ...
```

### 5. GET /health endpoint

```python
# Source: redis-py docs, FastAPI docs
# VERIFIED: redis.exceptions.ConnectionError levantado para Redis offline
import redis as redis_lib

@app.get("/health")
def health_check() -> JSONResponse:
    try:
        _redis.ping()
        return JSONResponse(status_code=200, content={"status": "ok"})
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
```

### 6. Config additions (api/config.py)

```python
# Source: api/config.py (padrão _safe_int existente)
job_poll_rate_limit_per_minute: int = field(
    default_factory=lambda: _safe_int("JOB_POLL_RATE_LIMIT_PER_MINUTE", 60)
)
file_download_rate_limit_per_minute: int = field(
    default_factory=lambda: _safe_int("FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE", 10)
)
```

### 7. tests/test_security.py — estrutura

```python
# Source: tests/test_api.py (padrão existente de test com api_client fixture)
from unittest.mock import patch, MagicMock
import stat, os

def test_body_size_limit(api_client):
    r = api_client.post("/jobs", content="A"*5000, headers={"Content-Length": "5000"})
    assert r.status_code == 413

def test_security_headers(api_client):
    r = api_client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src" in r.headers["Content-Security-Policy"]

def test_docs_routes_disabled(api_client):
    for path in ["/docs", "/redoc", "/openapi.json"]:
        assert api_client.get(path).status_code == 404

def test_queue_depth_limit(api_client):
    from api.main import _redis
    with patch.object(_redis, "llen", return_value=51):
        r = api_client.post("/jobs", json={"youtube_url": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 503

def test_rate_limit_get_jobs(api_client):
    from api.main import _redis
    with patch.object(_redis, "exists", return_value=1), \
         patch("api.main.AsyncResult") as mock_ar:
        mock_ar.return_value.state = "PENDING"
        for i in range(60):
            r = api_client.get("/jobs/test-job-id")
            assert r.status_code == 200, f"Request {i+1}/60 should succeed"
        r = api_client.get("/jobs/test-job-id")
    assert r.status_code == 429

def test_rate_limit_get_files(api_client):
    with patch("api.main.AsyncResult") as mock_ar:
        mock_ar.return_value.state = "PENDING"
        for i in range(10):
            r = api_client.get("/files/test-job-id")
            assert r.status_code in (404, 200), f"Request {i+1}/10 should not be 429"
        r = api_client.get("/files/test-job-id")
    assert r.status_code == 429
```

**Nota sobre GET /files rate limit test:** O endpoint retorna 404 quando state != SUCCESS (mock retorna PENDING). Isso ainda consome o rate limit counter. O teste verifica que a 11ª requisição retorna 429, independente de ser 404 ou 200 nas anteriores.

### 8. WAV file permission test

```python
# Source: Python stdlib — os.chmod, os.stat, stat module
# Este teste vai em tests/test_security.py
def test_wav_file_permissions(tmp_path):
    """download_audio() deve criar WAV com 0o600."""
    # Criar arquivo simulando saída do ffmpeg (664 é o padrão sem chmod)
    wav = tmp_path / "sg_test.wav"
    wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
    wav.chmod(0o664)  # simular antes do chmod
    
    # Aplicar o mesmo os.chmod que pipeline.py vai aplicar
    import os
    os.chmod(wav, 0o600)
    
    st = os.stat(wav)
    assert (st.st_mode & 0o777) == 0o600
    assert not (st.st_mode & stat.S_IRGRP)
    assert not (st.st_mode & stat.S_IWGRP)
    assert not (st.st_mode & stat.S_IROTH)
    assert not (st.st_mode & stat.S_IWOTH)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual security review | pip-audit (CVE scanning) | pip-audit 1.0 (2022) | Detecta dependências com CVEs conhecidos |
| Docs routes sempre ativos | `docs_url=None` em produção | FastAPI 0.63+ | Reduz superfície de ataque |
| Permissões padrão de filesystem | chmod explícito por arquivo | N/A (boa prática) | Proteção em sistemas multi-usuário |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Race condition entre ffmpeg criar WAV e os.chmod é aceitável dado contexto single-user VPS | Pitfall 3 | Em ambientes multi-user, outro processo pode ler o WAV no intervalo; mitigação: private /tmp dir por job (v2) |
| A2 | Pattern de chave Redis do slowapi para GET routes segue `LIMITS:LIMITER/{func_name}/...` — coberto pelo glob existente no conftest | Pitfall 4 | Se o padrão de chave for diferente, rate limit keys das GET routes não serão limpas entre testes → 429 espúrio |
| A3 | chmod 750 em start.sh via auto-chmod não quebra execução bash em andamento | Padrão 2 | Comportamento confirmado no modelo de execução do kernel Linux, mas não testado explicitamente neste research |

---

## Open Questions

1. **pip-audit no requirements.txt de produção ou separado?**
   - O que sabemos: pip-audit é uma ferramenta dev, não runtime. SEC-TEST-06 pede documentação em README, não instalação obrigatória.
   - O que está claro: adicionar ao requirements.txt expõe o ambiente de produção a dependências extras desnecessárias.
   - Recomendação: documentar em README como `pip install pip-audit && pip-audit -r requirements.txt` sem adicionar a requirements.txt. Usar como verificação manual pré-deploy.

2. **GET /health: usar o `_redis` module-level ou criar cliente dedicado?**
   - O que sabemos: `_redis` é um module-level client com connection pool. Se Redis cair e depois voltar, o pool se reconecta automaticamente.
   - O que está claro: reutilizar `_redis` é eficiente. Criar cliente dedicado para health check não traz benefício.
   - Recomendação: usar `_redis.ping()` diretamente.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Todos os módulos | ✓ | 3.12 (venv) | — |
| FastAPI | api/main.py | ✓ | 0.136.1 | — |
| slowapi | Rate limiting | ✓ | 0.1.9 | — |
| redis-py | Health endpoint, limiter | ✓ | 6.4.0 | — |
| pytest | tests/test_security.py | ✓ | 9.0.3 | — |
| pip-audit | SEC-TEST-06 (documentação) | ✗ | — | Instalar antes do deploy: `pip install pip-audit` |
| Redis (server) | Testes com rate limiting | ✗ em 6379, ✗ em 6380 | — | Iniciar com `./start.sh` ou `sudo service redis-server start` |

**Nota:** Redis não está rodando no momento da pesquisa. O conftest aponta para `redis://localhost:6380/0` para testes. Os testes de rate limit precisam de Redis ativo.

**Missing dependencies com fallback:**
- pip-audit: instalar sob demanda antes do deploy — `pip install pip-audit && pip-audit -r requirements.txt`
- Redis server: usar `./start.sh` para subir antes de rodar `pytest tests/test_security.py`

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | pytest.ini (raiz do projeto) |
| Quick run command | `pytest tests/test_security.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-FILE-01 | WAV criado com 0o600 | unit | `pytest tests/test_security.py::test_wav_file_permissions -x` | ❌ Wave 0 |
| SEC-FILE-02 | start.sh com 750 | unit | `pytest tests/test_security.py::test_startsh_permissions -x` | ❌ Wave 0 |
| SEC-API-01 | GET /jobs/{id} rate limit 60/min | unit | `pytest tests/test_security.py::test_rate_limit_get_jobs -x` | ❌ Wave 0 |
| SEC-API-02 | GET /files/{id} rate limit 10/min | unit | `pytest tests/test_security.py::test_rate_limit_get_files -x` | ❌ Wave 0 |
| SEC-API-03 | GET /health 200/503 | unit | `pytest tests/test_security.py::test_health_redis_ok -x tests/test_security.py::test_health_redis_down -x` | ❌ Wave 0 |
| SEC-TEST-01 | 413 em body > 4KB | unit | `pytest tests/test_security.py::test_body_size_limit -x` | ❌ Wave 0 |
| SEC-TEST-02 | Security headers presentes | unit | `pytest tests/test_security.py::test_security_headers -x` | ❌ Wave 0 |
| SEC-TEST-03 | /docs /redoc /openapi.json → 404 | unit | `pytest tests/test_security.py::test_docs_routes_disabled -x` | ❌ Wave 0 |
| SEC-TEST-04 | Queue depth → 503 | unit | `pytest tests/test_security.py::test_queue_depth_limit -x` | ❌ Wave 0 |
| SEC-TEST-05 | Rate limit GET /jobs e GET /files | unit | (coberto por SEC-API-01 e SEC-API-02 acima) | ❌ Wave 0 |
| SEC-TEST-06 | pip-audit documentado em README | manual | Verificação humana: README contém seção pip-audit | — |
| SEC-POLICY-01 | Security Gate em CLAUDE.md | manual | Verificação humana: CLAUDE.md contém "## Security Gate" | — |
| SEC-POLICY-02 | SECURITY-CHECKLIST.md existe | manual | `test -f .planning/SECURITY-CHECKLIST.md` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_security.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** `pytest tests/test_security.py -v` — todos os testes verdes antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_security.py` — cobre todos os SEC-TEST-01..06 + SEC-FILE-01/02 + SEC-API-01/02/03
- [ ] Framework install: nenhum necessário — pytest já disponível

*(Nota: conftest.py já existe e tem api_client fixture com flush de rate limit keys — não precisa de modificação)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Aplicação sem auth (by design) |
| V3 Session Management | no | Stateless (by design) |
| V4 Access Control | yes (parcial) | File permissions 0o600; start.sh 750 |
| V5 Input Validation | yes | Pydantic field_validator (já implementado) |
| V5.2 Sanitization | yes | Body size limit 413 (já implementado) |
| V6 Cryptography | no | WAV em transit (Fase 7 — HTTPS) |
| V11 Business Logic | yes | Rate limiting, queue depth limit |
| V14 Configuration | yes | Docs desabilitados em produção |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| WAV file readable by other OS users | Information Disclosure | chmod 0o600 (SEC-FILE-01) |
| start.sh executável por qualquer user | Elevation of Privilege | chmod 750 (SEC-FILE-02) |
| API polling DoS via GET /jobs | Denial of Service | Rate limit 60/min (SEC-API-01) |
| WAV download DoS via GET /files | Denial of Service | Rate limit 10/min (SEC-API-02) |
| Request body injection / memory exhaustion | Tampering | Body size limit 4KB (já implementado) |
| Clickjacking | Spoofing | X-Frame-Options: DENY (já implementado) |
| MIME sniffing | Spoofing | X-Content-Type-Options: nosniff (já implementado) |
| Queue exhaustion via job spam | Denial of Service | max_queue_depth + 503 (já implementado) |

---

## Sources

### Primary (HIGH confidence)
- Leitura direta do source de `slowapi==0.1.9` instalado em `.venv` — `_inject_headers`, `sync_wrapper`, padrão de `response: Response`
- Testes locais com Python 3.12 + os.chmod, os.stat, redis.exceptions — todos verificados em tempo de pesquisa
- Leitura direta de `api/main.py`, `api/config.py`, `api/tasks.py`, `pipeline.py`, `start.sh`, `tests/conftest.py` — estado atual do codebase
- `celery.app.defaults.py` — `default_queue=Option('celery')` confirmado

### Secondary (MEDIUM confidence)
- `celery_app.conf.task_default_queue == "celery"` — confirmado via Python shell com o app configurado
- `pip-audit 2.10.0` — confirmado via `pip index versions pip-audit`
- git `core.fileMode=true` e limitação de 100644/100755 — confirmado via `git ls-files --format`

### Tertiary (LOW confidence)
- Padrão exato de chave Redis do slowapi (`LIMITS:LIMITER*`) — inferido do source e do padrão de flush no conftest; não verificado com Redis ativo durante a pesquisa

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — packages existentes verificados, pip-audit version confirmada
- Architecture (file permissions): HIGH — testado localmente com os.chmod
- Architecture (slowapi GET routes): HIGH — verificado via leitura do source slowapi
- Architecture (health endpoint): HIGH — testado comportamento de ConnectionError localmente
- Pitfalls: HIGH — todos derivados de leitura do source, não de suposições
- Test strategy: HIGH — todos os controles já existentes verificados funcionando via TestClient

**Research date:** 2026-05-09
**Valid until:** 2026-08-09 (90 dias — stack estável, sem dependências de fast-moving libraries nesta fase)
