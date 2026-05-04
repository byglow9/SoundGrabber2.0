# Phase 3: Hardening - Research

**Researched:** 2026-05-04
**Domain:** FastAPI rate limiting (slowapi), exception normalization, yt-dlp partial file cleanup
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Implementar com **slowapi** (biblioteca de rate limiting nativa FastAPI). Decorator direto na rota.
- **D-02:** Limite aplicado **somente no POST /jobs**. GET /jobs/{id} e GET /files/{id} nao sao limitados.
- **D-03:** Valor padrao: **3 jobs por minuto por IP**, configuravel via env var `RATE_LIMIT_PER_MINUTE`.
- **D-04:** Resposta 429 inclui **header `Retry-After`**. Body: `{error: "Too many requests. Try again in N seconds.", error_type: "rate_limit_error"}`.
- **D-05:** Ampliar `sweep_expired_wavs` para limpar arquivos `.part` e `.ytdl` mais velhos que o TTL.
- **D-06:** Glob do sweeper: `sg_*.wav`, `sg_*.part`, `sg_*.ytdl`.
- **D-07:** Exception handler customizado para `RequestValidationError` -> formato unificado `{error, error_type: "validation_error"}`, status 422.

### Claude's Discretion
- Estrategia de identificacao de IP (X-Forwarded-For vs request.client.host)
- Storage backend do slowapi (in-memory ou Redis)
- Nome exato da string de rate limit (`"3/minute"` vs `"3 per minute"`)
- Mensagem exata do 429 em portugues vs ingles

### Deferred Ideas (OUT OF SCOPE)
- Limite por hora (20/hr) — adiado para tunagem pos-lancamento
- Autenticacao / API keys — fora do escopo do projeto
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-03 | Mensagens de erro claras quando YouTube bloqueia ou URL e invalida | D-07 (RequestValidationError handler) garante 422 com corpo normalizado; erros de job ja cobertos pelo formato JobFailure |
| UX-04 | Sistema informa limite de duracao de 15 minutos antes do usuario submeter | D-01/D-02/D-04 (rate limiting); o limite de duracao ja e rejeitado sincrono no worker — UX-04 e satisfeito pelo erro normalizado que retorna descricao do limite |
</phase_requirements>

---

## Summary

Phase 3 adiciona tres protecoes pontuais ao servidor FastAPI existente: rate limiting por IP via slowapi (D-01 a D-04), normalizacao dos erros de validacao sincrona (D-07), e extensao do sweeper de arquivos temporarios para limpar residuos de workers mortos (D-05, D-06).

Toda a logica de protecao fica em `api/main.py` e `api/config.py`. Nenhuma nova rota e criada. A fase e concluida quando os 4 success criteria do ROADMAP.md passam por `curl`.

**Decisao critica de infraestrutura:** slowapi com in-memory storage NAO funciona em producao com multiplos workers Uvicorn. Como o projeto ja tem Redis disponivel (`settings.redis_url`), o Limiter DEVE usar `storage_uri=settings.redis_url`. Esta e a recomendacao do ecosistema e foi confirmada por issue #226 do repositorio slowapi.

**Recomendacao primaria:** Use `get_ipaddr` (slowapi.util) em vez de `get_remote_address` em producao — `get_remote_address` ignora `X-Forwarded-For`, tornando rate limiting ineficaz atras de nginx. Para dev local sem proxy, ambas as funcoes sao equivalentes.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Rate limiting (429) | API / Backend (FastAPI) | Redis (storage) | slowapi intercepta antes do handler da rota; Redis guarda contadores compartilhados entre workers |
| Validacao de URL (422) | API / Backend (FastAPI) | — | Pydantic field_validator ja existe em JobRequest; apenas normalizar o formato da resposta |
| Limpeza de arquivos parciais | API / Backend (sweeper thread) | /tmp filesystem | sweep_expired_wavs roda em daemon thread ja existente; mudanca e isolada na funcao |
| Identificacao de IP | API / Backend (FastAPI middleware) | Nginx (proxy headers) | get_ipaddr le X-Forwarded-For; Uvicorn ProxyHeadersMiddleware e alternativa mais robusta |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slowapi | 0.1.9 | Rate limiting para FastAPI/Starlette | Port direto do flask-limiter; unica biblioteca de rate limiting com suporte nativo a decorators FastAPI |
| limits | (dep de slowapi) | Backend de armazenamento dos contadores | Dependencia direta do slowapi; suporta Redis, Memcached, memory |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fastapi.exceptions.RequestValidationError | (fastapi 0.136.1) | Interceptar erros de validacao Pydantic | Ja disponivel — sem instalacao adicional |
| slowapi.util.get_ipaddr | (slowapi 0.1.9) | Identificar IP do cliente com suporte a X-Forwarded-For | Producao atras de proxy/nginx |
| slowapi.util.get_remote_address | (slowapi 0.1.9) | Identificar IP por request.client.host | Dev local apenas; NAO usar em producao com nginx |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slowapi | fastapi-limiter | fastapi-limiter usa async Redis (aioredis); exige lifespan async para conexao — mais codigo para mesma funcionalidade |
| slowapi | implementacao manual com Redis INCR/EXPIRE | Reinvencao de rodas; requer lidar com race conditions, janelas de tempo, sliding window |

**Installation:**
```bash
pip install slowapi==0.1.9
```

**Version verification:** [VERIFIED: pip3 index versions slowapi] — versao 0.1.9 e a mais recente disponivel no PyPI (confirmado em 2026-05-04).

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request
    |
    v
[FastAPI Request Pipeline]
    |
    +---> [slowapi Limiter middleware check]
    |          |
    |          +-- OK (< 3/min) --> continua
    |          |
    |          +-- EXCEEDED -----> [custom_rate_limit_handler]
    |                                     |
    |                                     v
    |                              429 + Retry-After header
    |                              {error, error_type: "rate_limit_error"}
    |
    v
[POST /jobs route handler]
    |
    +---> [JobRequest Pydantic validation]
    |          |
    |          +-- VALID ------> [process_job.delay()] --> 202
    |          |
    |          +-- INVALID ----> [validation_exception_handler]
    |                                     |
    |                                     v
    |                              422
    |                              {error, error_type: "validation_error"}
    |
[Redis] <-- slowapi contadores de rate limit (compartilhado entre workers Uvicorn)

[Daemon Thread: sweeper (60s interval)]
    |
    +---> glob /tmp/sg_*.wav  --> delete if mtime > wav_ttl
    +---> glob /tmp/sg_*.part --> delete if mtime > wav_ttl
    +---> glob /tmp/sg_*.ytdl --> delete if mtime > wav_ttl
```

### Recommended Project Structure
```
api/
├── config.py        # Adicionar rate_limit_per_minute: int
└── main.py          # Adicionar: limiter, handlers, sweeper glob extensions
tests/
└── test_api.py      # Adicionar: test_rate_limit_*, test_sweeper_partial_files,
                     #             test_validation_error_format
```

### Pattern 1: slowapi Integration com Redis Backend

**What:** Inicializar o Limiter com Redis como backend, registrar como `app.state.limiter`, e aplicar decorator na rota.
**When to use:** Sempre que houver mais de 1 worker Uvicorn (producao). In-memory falha em multi-process.

```python
# Source: https://slowapi.readthedocs.io/en/latest/ e context7.com/laurents/slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_ipaddr
from slowapi.errors import RateLimitExceeded
from api.config import settings

limiter = Limiter(
    key_func=get_ipaddr,                    # Le X-Forwarded-For; fallback para client.host
    storage_uri=settings.redis_url,         # Redis compartilhado entre workers
    headers_enabled=True,                   # Injeta X-RateLimit-* e Retry-After automaticamente
)

app = FastAPI(title="SoundGrabber API", version="0.3.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

@app.post("/jobs", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def submit_job(request: Request, request_body: JobRequest) -> dict:
    # ...
```

**CRITICO — ordem dos decorators:** `@app.post(...)` DEVE ficar ACIMA de `@limiter.limit(...)`. Caso contrario, o rate limit nao e aplicado. Confirmado pela documentacao oficial do slowapi.

**CRITICO — parametro `request`:** A rota DEVE aceitar `request: Request` como parametro explicitamente para o slowapi funcionar. Sem ele, o decorator de limite nao consegue inspecionar o IP.

### Pattern 2: Custom RateLimitExceeded Handler com Retry-After

**What:** Substituir o handler padrao do slowapi (`_rate_limit_exceeded_handler`) por um que retorna o formato unificado `{error, error_type}`.
**When to use:** Sempre — o formato padrao retorna `{"error": "Rate limit exceeded: ..."}` sem `error_type`.

```python
# Source: github.com/laurentS/slowapi/blob/master/slowapi/extension.py (inspecao direta)
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Retorna formato unificado {error, error_type} com Retry-After header (D-04)."""
    # exc.detail contem a descricao do limite (ex: "3 per 1 minute")
    response = JSONResponse(
        status_code=429,
        content={
            "error": f"Too many requests. Try again in a moment.",
            "error_type": "rate_limit_error",
        },
    )
    # _inject_headers adiciona Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response
```

**Nota sobre Retry-After:** Com `headers_enabled=True` no Limiter, `_inject_headers` injeta automaticamente o header `Retry-After` em segundos. Nao e necessario calcular manualmente.

### Pattern 3: RequestValidationError Handler (D-07)

**What:** Capturar o 422 padrao do FastAPI/Pydantic e reformatar para `{error, error_type}`.
**When to use:** Para qualquer erro de validacao de entrada (URL invalida, campo ausente, tipo errado).

```python
# Source: https://fastapi.tiangolo.com/tutorial/handling-errors/
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Converte 422 Pydantic para formato unificado {error, error_type} (D-07)."""
    # exc.errors() e uma lista de dicts Pydantic; pegar a primeira mensagem humanizada
    errors = exc.errors()
    if errors:
        # msg ja e a mensagem do field_validator (ex: "URL must be a YouTube link (got: vimeo.com)")
        msg = errors[0].get("msg", "Invalid request")
        # Remover prefixo "Value error, " que Pydantic v2 adiciona automaticamente
        msg = msg.removeprefix("Value error, ")
    else:
        msg = "Invalid request"
    return JSONResponse(
        status_code=422,
        content={"error": msg, "error_type": "validation_error"},
    )
```

**Nota sobre Pydantic v2:** Em Pydantic v2 (usado pelo FastAPI >= 0.100), mensagens de `field_validator` sao prefixadas com `"Value error, "` automaticamente. `removeprefix` remove esse prefixo sem fazer strip de outros conteudos.

### Pattern 4: Sweeper Estendido (D-05, D-06)

**What:** Ampliar `sweep_expired_wavs` para tambem limpar `.part` e `.ytdl`.
**When to use:** Esta e a unica mudanca necessaria — o loop daemon ja existe e chama esta funcao.

```python
# Source: api/main.py existente — extensao direta
def sweep_expired_wavs(directory: Path, ttl_seconds: int) -> int:
    """Delete sg_*.wav, sg_*.part, sg_*.ytdl em `directory` mais velhos que ttl_seconds."""
    deleted = 0
    now = time.time()
    patterns = ["sg_*.wav", "sg_*.part", "sg_*.ytdl"]
    for pattern in patterns:
        for f in Path(directory).glob(pattern):
            try:
                if now - f.stat().st_mtime > ttl_seconds:
                    f.unlink(missing_ok=True)
                    deleted += 1
            except OSError:
                continue
    return deleted
```

**Por que `.part` e `.ytdl`:** Confirmado pelo codigo-fonte do yt-dlp (`downloader/common.py`):
- `.part` — arquivo de download parcial; `temp_name(filename)` retorna `filename + '.part'`
- `.ytdl` — arquivo de estado/progresso; `ytdl_filename(filename)` retorna `filename + '.ytdl'`

Quando o worker Celery recebe SIGKILL durante `yt_dlp.download([url])`, esses arquivos ficam em `/tmp` e NAO sao deletados pelo `try/finally` de `pipeline.py` (o finally so roda se o processo nao for SIGKILL'd). O sweeper e a unica defesa.

### Anti-Patterns to Avoid

- **In-memory storage com multiplos workers:** `Limiter(key_func=get_remote_address)` sem `storage_uri` usa memoria local do processo. Com 2+ workers Uvicorn, cada processo tem contador separado — o limite efetivo multiplica pelo numero de workers. [VERIFIED: github.com/laurentS/slowapi/issues/226]
- **`get_remote_address` em producao com nginx:** Esta funcao usa apenas `request.client.host`, que sera o IP do nginx (ex: `127.0.0.1`) e nao o IP real do cliente. Use `get_ipaddr` que le `X-Forwarded-For`.
- **Decorator order errado:** `@limiter.limit(...)` ACIMA de `@app.post(...)` faz o rate limit ser ignorado silenciosamente.
- **Rota sem `request: Request`:** O slowapi nao consegue ler o IP se `Request` nao for parametro explicito da rota.
- **Custom handler sem `_inject_headers`:** Se o handler customizado nao chamar `_inject_headers`, o header `Retry-After` nao e incluido mesmo com `headers_enabled=True`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limit counters | Redis INCR + EXPIRE manual | slowapi com Redis backend | Race conditions em sliding window, reset de janela, multi-key por endpoint — tudo ja resolvido |
| Retry-After calculation | Calcular segundos ate reset manualmente | `limiter._inject_headers(response, request.state.view_rate_limit)` | O Limiter ja sabe exatamente quando a janela reseta |
| Validacao de formato de erro 429 | Parsing manual do exc.detail | `exc.detail` ja contem a string do limite | Usar a propriedade existente da excecao |

**Key insight:** Toda a complexidade de rate limiting (janela deslizante, reset atomico, multi-worker) ja esta encapsulada no slowapi + limits library. O projeto so precisa de 4 linhas de configuracao.

---

## Common Pitfalls

### Pitfall 1: Decorator Order em FastAPI
**What goes wrong:** `@limiter.limit("3/minute")` acima de `@app.post("/jobs")` — o rate limit e silenciosamente ignorado.
**Why it happens:** O decorator de rota do FastAPI precisa estar mais proximo da funcao para registra-la; o slowapi envolve o handler registrado.
**How to avoid:** Sempre: `@app.post(...)` primeiro (mais longe da funcao), `@limiter.limit(...)` segundo (mais proximo da funcao).
**Warning signs:** 429 nunca retornado mesmo com muitas requisicoes rapidas.

### Pitfall 2: Parametro `request` Ausente na Rota
**What goes wrong:** `def submit_job(request_body: JobRequest)` sem `request: Request` — slowapi lanca `AttributeError: 'NoneType' has no attribute ...`
**Why it happens:** slowapi precisa do objeto `Request` para extrair o IP via `key_func`.
**How to avoid:** Sempre incluir `request: Request` como primeiro parametro das rotas com rate limit.
**Warning signs:** `AttributeError` em producao na primeira requisicao.

### Pitfall 3: In-memory Storage com Multi-Worker
**What goes wrong:** Rate limit nao funciona — cliente consegue fazer 30+ requisicoes/minuto com 10 workers.
**Why it happens:** Cada processo Uvicorn tem seu proprio dicionario de contadores em memoria.
**How to avoid:** Sempre usar `storage_uri=settings.redis_url` — Redis e compartilhado entre todos os workers.
**Warning signs:** Rate limit parece funcionar localmente (1 worker) mas falha em producao.

### Pitfall 4: Pydantic v2 Prefixo "Value error, "
**What goes wrong:** Mensagem de erro retorna `"Value error, URL must be a YouTube link..."` em vez de `"URL must be a YouTube link..."`.
**Why it happens:** Pydantic v2 prefixa mensagens de `field_validator` com `"Value error, "` automaticamente.
**How to avoid:** `msg.removeprefix("Value error, ")` no handler de `RequestValidationError`.
**Warning signs:** Mensagens de erro no body da resposta 422 comecam com "Value error, ".

### Pitfall 5: `.part` vs `.part.ytdl` — Extensoes Corretas
**What goes wrong:** Glob `sg_*.ytdl-part` ou `sg_*.temp` — arquivos nao sao encontrados.
**Why it happens:** As extensoes exatas sao `.part` (download parcial) e `.ytdl` (estado), confirmadas pelo codigo-fonte de `yt_dlp/downloader/common.py`.
**How to avoid:** Usar exatamente `sg_*.part` e `sg_*.ytdl` conforme D-06.
**Warning signs:** Arquivos de download interrompido acumulam em `/tmp` sem serem deletados.

---

## Code Examples

### Configuracao completa de slowapi em `api/main.py`

```python
# Source: context7.com/laurents/slowapi + inspecao de slowapi/extension.py
from slowapi import Limiter
from slowapi.util import get_ipaddr
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# 1. Inicializar Limiter (acima de app = FastAPI(...))
limiter = Limiter(
    key_func=get_ipaddr,
    storage_uri=settings.redis_url,
    headers_enabled=True,           # Injeta Retry-After automaticamente
)

# 2. Registrar no app
app.state.limiter = limiter

# 3. Handler 429 customizado
def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Try again in a moment.", "error_type": "rate_limit_error"},
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# 4. Handler 422 customizado
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    msg = errors[0].get("msg", "Invalid request") if errors else "Invalid request"
    msg = msg.removeprefix("Value error, ")
    return JSONResponse(status_code=422, content={"error": msg, "error_type": "validation_error"})

# 5. Rota com rate limit (ordem dos decorators e CRITICA)
@app.post("/jobs", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def submit_job(request: Request, request_body: JobRequest) -> dict:
    # request: Request OBRIGATORIO como primeiro parametro
    task = process_job.delay(request_body.youtube_url)
    ...
```

### Adicionar `rate_limit_per_minute` em `api/config.py`

```python
# Source: padrao existente em api/config.py
@dataclass(frozen=True)
class Settings:
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    cookies_path: str = os.environ.get("YTDLP_COOKIES_FILE", "")
    po_token: str = os.environ.get("YTDLP_PO_TOKEN", "")
    wav_ttl: int = int(os.environ.get("WAV_TTL_SECONDS", "900"))
    rate_limit_per_minute: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "3"))
```

### Teste do sweeper estendido

```python
# Source: padrao de test_sweeper_deletes_expired_wavs em tests/test_api.py
def test_sweeper_deletes_partial_files(tmp_path):
    """sweep_expired_wavs deleta sg_*.part e sg_*.ytdl mais velhos que ttl."""
    from api.main import sweep_expired_wavs

    old_part = tmp_path / "sg_abc.part"
    old_ytdl = tmp_path / "sg_abc.ytdl"
    new_part  = tmp_path / "sg_xyz.part"

    old_part.write_bytes(b"partial")
    old_ytdl.write_bytes(b"state")
    new_part.write_bytes(b"inprogress")

    past = time.time() - 1200  # 20 min ago
    os.utime(old_part, (past, past))
    os.utime(old_ytdl, (past, past))
    # new_part: mtime atual (fresco)

    sweep_expired_wavs(tmp_path, ttl_seconds=900)

    assert not old_part.exists(), "sweeper deve deletar .part expirado"
    assert not old_ytdl.exists(), "sweeper deve deletar .ytdl expirado"
    assert new_part.exists(),     "sweeper NAO deve deletar .part fresco"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| flask-limiter (Flask) | slowapi (FastAPI-native) | slowapi criado 2020 | API de decorator equivalente, mas integrada com Starlette Request |
| In-memory rate limit | Redis backend | — | Obrigatorio para multi-worker; in-memory e inseguro em producao |
| Pydantic v1 field validators | Pydantic v2 `field_validator` decorator | FastAPI 0.100+ | Mensagens prefixadas com "Value error, " — requer removeprefix() |

**Deprecated/outdated:**
- `get_remote_address`: Funcional mas inadequado para producao com proxy reverso. Use `get_ipaddr` que le `X-Forwarded-For`.
- `override_http_exception_handler`: Nao existe no FastAPI. O metodo correto e `app.add_exception_handler()` ou `@app.exception_handler()`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_inject_headers` e um metodo publico/estavel do Limiter que aceita `(response, view_rate_limit)` | Pattern 2 | Se a assinatura mudar em versoes futuras do slowapi, o handler quebraria. Mitigacao: pin `slowapi==0.1.9` em requirements.txt |
| A2 | `.ytdl` e produzido em todos os downloads yt-dlp com `--continue` habilitado (padrao) | Pitfall 5 | Se yt-dlp apenas gerar `.part` sem `.ytdl` em algumas configuracoes, o glob seria inofensivo (sem matches) |

**Todos os outros claims foram verificados via Context7 (slowapi), documentacao oficial FastAPI, ou codigo-fonte do yt-dlp.**

---

## Open Questions

1. **Assinatura exata da rota `submit_job` apos adicao de `request: Request`**
   - What we know: JobRequest era o unico parametro. Com slowapi, `request: Request` precisa ser adicionado.
   - What's unclear: Se isso quebra o test_post_jobs_returns_job_id (que chama `api_client.post("/jobs", json=...)`) — provavelmente nao, pois Request e injetado pelo FastAPI internamente e nao afeta o contrato JSON da rota.
   - Recommendation: Renomear o parametro de body para `request_body: JobRequest` para evitar conflito de nome com `request: Request`.

2. **comportamento de `get_ipaddr` com Redis em producao**
   - What we know: `get_ipaddr` le o header `X-Forwarded-For` se presente, caso contrario usa `request.client.host`.
   - What's unclear: Se `X-Forwarded-For` pode ser forjado por um cliente malicioso (IP spoofing para bypass de rate limit).
   - Recommendation: Para v1, `get_ipaddr` e suficiente. Para protecao mais rigorosa em producao, considerar `uvicorn --proxy-headers` + `ProxyHeadersMiddleware` que valida o IP do proxy confiavel antes de ler o header.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | slowapi storage backend | disponivel (autenticado) | 7.0.15 | in-memory (apenas dev/test) |
| Python 3.11+ | runtime | disponivel (3.12.3 no sistema) | 3.12.3 | — |
| slowapi 0.1.9 | rate limiting | NAO instalado | — | Instalar via pip |
| FastAPI | ja instalado | 0.136.1 | 0.136.1 | — |
| ffmpeg/ffprobe | pipeline (pre-existente) | 6.1.1 | 6.1.1 | — |

**Missing dependencies with no fallback:**
- `slowapi==0.1.9` — requer `pip install slowapi==0.1.9` no Wave 0 da fase.

**Nota sobre Redis:** Redis esta disponivel no host mas requer autenticacao (`NOAUTH Authentication required`). O `settings.redis_url` deve incluir a senha correta. Para testes unitarios, o conftest.py ja aponta para `redis://localhost:6380/0` (porta alternativa sem auth).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | nenhum detectado — usar `pytest tests/` |
| Quick run command | `pytest tests/test_api.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-03 | URL invalida retorna 422 com `{error, error_type}` normalizado | unit | `pytest tests/test_api.py::test_invalid_url_rejected -x` | Parcial (testa status 422, nao o body format) |
| UX-03 | URL invalida retorna body com `error_type: "validation_error"` | unit | `pytest tests/test_api.py::test_validation_error_format -x` | ❌ Wave 0 |
| UX-04 | Rate limit 429 retornado apos 3 requests/min por IP | unit | `pytest tests/test_api.py::test_rate_limit_returns_429 -x` | ❌ Wave 0 |
| UX-04 | 429 inclui header `Retry-After` | unit | `pytest tests/test_api.py::test_rate_limit_retry_after_header -x` | ❌ Wave 0 |
| SC-4 | Sweeper deleta .part e .ytdl expirados | unit | `pytest tests/test_api.py::test_sweeper_deletes_partial_files -x` | ❌ Wave 0 |
| SC-4 | Sweeper NAO deleta arquivos recentes | unit | (incluido no teste acima) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_api.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green antes de `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_api.py::test_validation_error_format` — verifica body `{error, error_type}` na resposta 422
- [ ] `tests/test_api.py::test_rate_limit_returns_429` — verifica que 4a requisicao em 60s retorna 429
- [ ] `tests/test_api.py::test_rate_limit_retry_after_header` — verifica header `Retry-After` presente no 429
- [ ] `tests/test_api.py::test_sweeper_deletes_partial_files` — verifica delecao de `.part` e `.ytdl` expirados
- [ ] `requirements.txt` — adicionar `slowapi==0.1.9`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nao | Projeto stateless, sem auth |
| V3 Session Management | nao | Sem sessions |
| V4 Access Control | sim (rate limiting) | slowapi 3/min por IP |
| V5 Input Validation | sim | Pydantic field_validator + exception handler normalizado |
| V6 Cryptography | nao | Nenhuma criptografia nesta fase |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Abuso de recursos (job flood) | Denial of Service | slowapi 3/min por IP com Redis backend |
| IP spoofing via X-Forwarded-For | Elevation of Privilege | get_ipaddr + ProxyHeadersMiddleware para v1.1 |
| Path traversal via job_id | Tampering | Ja implementado no Phase 2 (JOB_ID_PATTERN regex) |
| Stack trace exposto em 422 | Information Disclosure | D-07: exception handler normalizado remove internals |
| Disco cheio por arquivos .part/.ytdl | Denial of Service | D-05/D-06: sweeper limpa em <= 20 min |

---

## Sources

### Primary (HIGH confidence)
- `context7.com/laurents/slowapi` — Limiter init, storage backends, decorator syntax, headers, get_ipaddr
- `slowapi.readthedocs.io/en/latest/` — FastAPI integration pattern, Redis storage, `_rate_limit_exceeded_handler`
- `fastapi.tiangolo.com/tutorial/handling-errors` — RequestValidationError handler, `@app.exception_handler`
- `github.com/laurentS/slowapi/blob/master/slowapi/extension.py` — `_rate_limit_exceeded_handler`, `_inject_headers`, `view_rate_limit`
- `github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/downloader/common.py` — `.part` e `.ytdl` extensoes

### Secondary (MEDIUM confidence)
- `github.com/laurentS/slowapi/issues/226` — confirmacao de que in-memory nao funciona com multiplos workers
- WebSearch: padrao de custom RateLimitExceeded handler com `_inject_headers`

### Tertiary (LOW confidence)
- Nenhum

---

## Project Constraints (from CLAUDE.md)

- **Backend:** Python 3.11 + FastAPI (projeto usa 3.12.3 no sistema, compativel)
- **Task queue:** Celery + Redis
- **Frontend:** Vanilla HTML + CSS + JS — zero frameworks (sem impacto nesta fase)
- **Sem contas de usuario** — stateless, sem auth
- **WAV apenas** — sem impacto nesta fase
- **Limite de 15 minutos** — ja implementado no Phase 1; esta fase apenas normaliza o erro retornado
- **Estética Y2K** — sem impacto nesta fase (backend only)
- **YouTube bot detection** — sem impacto nesta fase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — slowapi 0.1.9 verificado no PyPI; versao unica disponivel
- Architecture: HIGH — padroes verificados via Context7 e documentacao oficial slowapi/FastAPI
- Pitfalls: HIGH — Pitfalls 1/2/3 verificados via documentacao oficial e issue #226 do repositorio
- yt-dlp file extensions: HIGH — verificado diretamente em yt_dlp/downloader/common.py

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (slowapi 0.1.9 e a versao atual; API e estavele desde 0.1.x)
