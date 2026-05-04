# Phase 3: Hardening - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 4 (2 modified, 1 extended, 1 with new stubs)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `api/config.py` | config | — | `api/config.py` itself (extend) | exact |
| `api/main.py` | controller + middleware | request-response | `api/main.py` itself (extend) | exact |
| `requirements.txt` | config | — | `requirements.txt` itself (extend) | exact |
| `tests/test_api.py` | test | request-response | `tests/test_api.py` itself (extend) | exact |

---

## Pattern Assignments

### `api/config.py` — adicionar campo `rate_limit_per_minute`

**Analog:** `api/config.py` (o próprio arquivo — adição de campo)

**Padrão existente** (linhas 8–16, ler completo):
```python
@dataclass(frozen=True)
class Settings:
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    cookies_path: str = os.environ.get("YTDLP_COOKIES_FILE", "")
    po_token: str = os.environ.get("YTDLP_PO_TOKEN", "")
    wav_ttl: int = int(os.environ.get("WAV_TTL_SECONDS", "900"))


settings = Settings()
```

**Novo campo a inserir** após `wav_ttl` (linha 13), seguindo exatamente o mesmo padrão de `int(os.environ.get(...))`:
```python
    rate_limit_per_minute: int = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "3"))
```

**Regras do padrão:**
- `dataclass(frozen=True)` — imutável; não usar `__post_init__` nem property
- Tipo explícito na anotação (`int`, `str`) — sem `Optional`, sem `Union`
- `os.environ.get("VAR_NAME", "default_as_string")` — default como string, cast fora
- Cast de int envolve o `os.environ.get(...)` inteiro: `int(os.environ.get(..., "3"))`
- Ordem convencional: conexões externas → paths → TTLs → limites de negócio

---

### `api/main.py` — três mudanças independentes

**Analog:** `api/main.py` (o próprio arquivo — três extensões pontuais)

#### A) Bloco de imports (linhas 1–19 atuais)

Imports atuais relevantes que serão ampliados:
```python
import redis as redis_lib
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from api.config import settings
from api.tasks import celery_app, process_job, JobFailure
```

Novos imports a adicionar (inserir em bloco, após os `from fastapi` existentes):
```python
from fastapi import FastAPI, HTTPException, Request          # adicionar Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse     # adicionar JSONResponse
from slowapi import Limiter
from slowapi.util import get_ipaddr
from slowapi.errors import RateLimitExceeded
```

**Regra:** manter ordem — stdlib → third-party → local. Dentro de third-party, manter `fastapi.*` agrupado.

---

#### B) Rate limiting: inicialização do Limiter + registro no app

**Padrão de inicialização** — inserir entre o `_redis = ...` (linha 27) e a classe `JobRequest` (linha 31):
```python
# Rate limiting — D-01/D-02/D-03 (Phase 3)
limiter = Limiter(
    key_func=get_ipaddr,                   # lê X-Forwarded-For; fallback para client.host
    storage_uri=settings.redis_url,        # Redis compartilhado entre workers (obrigatório multi-worker)
    headers_enabled=True,                  # injeta Retry-After, X-RateLimit-* automaticamente
)
```

**Registro no app e handler 429** — inserir logo após `app = FastAPI(...)` (linha 89 atual):
```python
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Formato unificado {error, error_type} com Retry-After header (D-04).

    int(exc.limit.get_expiry()) retorna os segundos reais até o reset da janela.
    """
    seconds = int(exc.limit.get_expiry())
    response = JSONResponse(
        status_code=429,
        content={
            "error": f"Too many requests. Try again in {seconds} seconds.",
            "error_type": "rate_limit_error",
        },
    )
    response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return response


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
```

**Decorator na rota POST /jobs** — substituir assinatura atual (linha 92–93):
```python
# ANTES:
@app.post("/jobs", status_code=202)
def submit_job(request: JobRequest) -> dict:
    task = process_job.delay(request.youtube_url)

# DEPOIS (ordem dos decorators é crítica — @app.post acima de @limiter.limit):
@app.post("/jobs", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def submit_job(request: Request, request_body: JobRequest) -> dict:
    task = process_job.delay(request_body.youtube_url)
```

**Atenção:** renomear o parâmetro body de `request` para `request_body` para evitar colisão com `request: Request`. Atualizar todas as referências de `request.youtube_url` para `request_body.youtube_url` (apenas dentro da função `submit_job`).

---

#### C) Handler 422 normalizado (D-07)

**Padrão de exception handler existente** no projeto — não há handler customizado ainda. O padrão de referência é o bloco `FAILURE` do `get_job` (linhas 141–149) que já extrai `error` e `error_type`:
```python
# Padrão de referência (api/main.py linhas 141–149):
if state == "FAILURE":
    exc = result.result
    error = getattr(exc, "error", None)
    error_type = getattr(exc, "error_type", None)
    if error is None or error_type is None:
        error = "An internal error occurred. Please try again."
        error_type = "internal_error"
    return {"status": "failed", "error": error, "error_type": error_type}
```

Handler a adicionar logo após o registro do `_rate_limit_handler`:
```python
@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Converte 422 Pydantic para formato {error, error_type} (D-07).

    Pydantic v2 prefixa mensagens de field_validator com "Value error, " — removeprefix remove.
    """
    errors = exc.errors()
    msg = errors[0].get("msg", "Invalid request") if errors else "Invalid request"
    msg = msg.removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content={"error": msg, "error_type": "validation_error"},
    )
```

---

#### D) Sweeper estendido (D-05/D-06)

**Função atual** (linhas 47–62 — ler completo antes de modificar):
```python
def sweep_expired_wavs(directory: Path, ttl_seconds: int) -> int:
    """Delete sg_*.wav files in `directory` older than `ttl_seconds`. Returns count deleted.

    Pure function — testable without threads. The daemon loop calls this every 60 seconds.
    D-01: TTL matches the 15-minute WAV lifecycle decision.
    """
    deleted = 0
    now = time.time()
    for wav in Path(directory).glob("sg_*.wav"):
        try:
            if now - wav.stat().st_mtime > ttl_seconds:
                wav.unlink(missing_ok=True)
                deleted += 1
        except OSError:
            continue
    return deleted
```

**Substituição** — mesmo corpo, loop agora itera sobre lista de padrões:
```python
def sweep_expired_wavs(directory: Path, ttl_seconds: int) -> int:
    """Delete sg_*.wav, sg_*.part, sg_*.ytdl in `directory` older than `ttl_seconds`.

    Returns count deleted. Pure function — testable without threads.
    D-01: TTL matches the 15-minute WAV lifecycle decision.
    D-05/D-06 (Phase 3): also cleans partial yt-dlp files left by SIGKILL'd workers.
    """
    deleted = 0
    now = time.time()
    for pattern in ("sg_*.wav", "sg_*.part", "sg_*.ytdl"):
        for f in Path(directory).glob(pattern):
            try:
                if now - f.stat().st_mtime > ttl_seconds:
                    f.unlink(missing_ok=True)
                    deleted += 1
            except OSError:
                continue
    return deleted
```

**Padrão de loop:** `for pattern in (...)` sobre tupla de strings — não usar lista para evitar mutabilidade acidental. Renomear variável interna de `wav` para `f` para refletir que agora lida com múltiplos tipos.

O `_run_sweeper_loop` (linhas 65–74) e o `lifespan` (linhas 77–86) não mudam.

---

### `requirements.txt` — adicionar slowapi

**Padrão existente** (arquivo completo, 12 linhas):
```
yt-dlp==2026.3.17
librosa==0.11.0
soundfile==0.13.1
numpy>=2.0,<3.0
scipy>=1.10
pytest==9.0.3
pytest-subprocess>=1.5
fastapi==0.136.1
uvicorn==0.46.0
celery[redis]==5.6.3
redis==6.4.0
httpx>=0.27
```

**Linha a adicionar** — inserir após `fastapi==0.136.1` (linha 8), pois slowapi é middleware de FastAPI:
```
slowapi==0.1.9
```

**Convenção do arquivo:** dependências pinadas com `==` para bibliotecas de aplicação; `>=` apenas para transitive deps com restrição de compatibilidade (numpy, scipy). `slowapi` é dependência de aplicação — usar `==`.

---

### `tests/test_api.py` — quatro novos stubs Wave 0

**Analog:** testes existentes no mesmo arquivo — copiar estrutura exata.

**Padrão dos stubs existentes** (referência: `test_sweeper_deletes_expired_wavs`, linhas 148–166):
```python
def test_sweeper_deletes_expired_wavs(tmp_path, monkeypatch):
    """The sweeper helper deletes /tmp/sg_*.wav files older than wav_ttl."""
    sweeper_module = pytest.importorskip("api.main", reason="api.main not available")
    sweep_once = getattr(sweeper_module, "sweep_expired_wavs", None)
    if sweep_once is None:
        pytest.skip("sweep_expired_wavs not yet implemented (Plan 03)")

    old = tmp_path / "sg_oldfile.wav"
    new = tmp_path / "sg_newfile.wav"
    old.write_bytes(b"RIFFold ")
    new.write_bytes(b"RIFFnew ")
    past = time.time() - 1200
    import os
    os.utime(old, (past, past))

    sweep_once(tmp_path, ttl_seconds=900)

    assert not old.exists(), "sweeper must delete WAVs older than ttl"
    assert new.exists(), "sweeper must NOT delete fresh WAVs"
```

**Padrão dos testes de rota** (referência: `test_invalid_url_rejected`, linhas 44–55):
```python
def test_invalid_url_rejected(api_client, url):
    """Non-YouTube or malformed URLs return 422 (Pydantic validation)."""
    response = api_client.post("/jobs", json={"youtube_url": url})
    assert response.status_code == 422, f"URL {url!r} should be rejected; ..."
```

**Quatro novos testes a adicionar** ao final do arquivo (após `test_concurrent_jobs`):

```python
# -----------------------------------------------------------------------
# UX-03: 422 body normalizado (Phase 3, Wave 1)
# -----------------------------------------------------------------------

def test_validation_error_format(api_client):
    """422 body segue formato unificado {error, error_type: 'validation_error'} (D-07)."""
    response = api_client.post("/jobs", json={"youtube_url": "https://vimeo.com/12345"})
    assert response.status_code == 422
    body = response.json()
    assert "error" in body, f"body deve ter 'error': {body}"
    assert body.get("error_type") == "validation_error", f"error_type errado: {body}"
    assert "detail" not in body, f"chave 'detail' nao deve existir no body: {body}"
    assert not body["error"].startswith("Value error,"), "prefixo Pydantic v2 não deve vazar"


# -----------------------------------------------------------------------
# UX-04: Rate limiting 429 (Phase 3, Wave 1)
# -----------------------------------------------------------------------

def test_rate_limit_returns_429(api_client):
    """4ª requisição em 60s pelo mesmo IP retorna 429 (D-01/D-03)."""
    url = "https://www.youtube.com/watch?v=abc123"
    # 3 primeiras devem passar (202); a 4ª deve ser bloqueada (429)
    for _ in range(3):
        r = api_client.post("/jobs", json={"youtube_url": url})
        assert r.status_code == 202, f"esperado 202 nas 3 primeiras: {r.status_code}"
    r = api_client.post("/jobs", json={"youtube_url": url})
    assert r.status_code == 429, f"4ª requisição deve retornar 429: {r.status_code}"
    body = r.json()
    assert body.get("error_type") == "rate_limit_error", f"error_type errado: {body}"


def test_rate_limit_retry_after_header(api_client):
    """429 inclui header Retry-After com valor inteiro (D-04)."""
    url = "https://www.youtube.com/watch?v=abc123"
    for _ in range(3):
        api_client.post("/jobs", json={"youtube_url": url})
    r = api_client.post("/jobs", json={"youtube_url": url})
    assert r.status_code == 429
    assert "retry-after" in r.headers, f"header Retry-After ausente: {dict(r.headers)}"
    retry_val = r.headers["retry-after"]
    assert retry_val.isdigit(), f"Retry-After deve ser inteiro em segundos: {retry_val!r}"


# -----------------------------------------------------------------------
# SC-4: Sweeper limpa .part e .ytdl expirados (Phase 3, Wave 1)
# -----------------------------------------------------------------------

def test_sweeper_deletes_partial_files(tmp_path):
    """sweep_expired_wavs deleta sg_*.part e sg_*.ytdl mais velhos que ttl (D-05/D-06)."""
    import os
    from api.main import sweep_expired_wavs

    old_part = tmp_path / "sg_abc.part"
    old_ytdl = tmp_path / "sg_abc.ytdl"
    new_part  = tmp_path / "sg_xyz.part"

    old_part.write_bytes(b"partial")
    old_ytdl.write_bytes(b"state")
    new_part.write_bytes(b"inprogress")

    past = time.time() - 1200  # 20 min atrás
    os.utime(old_part, (past, past))
    os.utime(old_ytdl, (past, past))
    # new_part: mtime atual (fresco — não deve ser deletado)

    sweep_expired_wavs(tmp_path, ttl_seconds=900)

    assert not old_part.exists(), "sweeper deve deletar .part expirado"
    assert not old_ytdl.exists(), "sweeper deve deletar .ytdl expirado"
    assert new_part.exists(), "sweeper NAO deve deletar .part fresco"
```

**Convenções de teste do projeto:**
- `api_client` fixture: FastAPI TestClient com Celery em eager mode; não requer broker
- `tmp_path` fixture: diretório temporário do pytest; não usar `/tmp` diretamente em testes unitários
- `import os` dentro da função: padrão já usado em `test_sweeper_deletes_expired_wavs` (linha 162)
- Assertivas com mensagem: `assert cond, f"mensagem: {var}"` — padrão do projeto
- Sem `pytest.mark` nos testes unitários: apenas testes de rede recebem `@pytest.mark.e2e`

---

## Shared Patterns

### Formato de erro unificado `{error, error_type}`
**Fonte:** `api/tasks.py` — classe `JobFailure` (linhas 15–27) + `api/main.py` bloco `FAILURE` (linhas 141–149)
**Aplicar em:** handler de `RateLimitExceeded` e handler de `RequestValidationError`
```python
# Estrutura canônica do body de erro — NUNCA expor internals, stack trace ou paths
{
    "error": "<mensagem humanizada em inglês>",
    "error_type": "<snake_case: rate_limit_error | validation_error | download_error | internal_error>"
}
```

### Padrão 12-factor config
**Fonte:** `api/config.py` (arquivo completo, 17 linhas)
**Aplicar em:** novo campo `rate_limit_per_minute`
```python
# Cast direto: int(os.environ.get("VAR", "default"))
# Nunca: int(os.environ.get("VAR") or "default") — mascararia variável vazia como default
wav_ttl: int = int(os.environ.get("WAV_TTL_SECONDS", "900"))
```

### Padrão de registro de exception handler no FastAPI
**Fonte:** não existe ainda em `api/main.py` — padrão vem do RESEARCH.md (Pattern 3, verificado na doc oficial FastAPI)
**Aplicar em:** `RequestValidationError` e `RateLimitExceeded`
```python
# Dois estilos válidos no FastAPI — usar consistentemente:
# Estilo 1 (decorator): para handlers assíncronos (RequestValidationError)
@app.exception_handler(RequestValidationError)
async def handler(request: Request, exc: ...) -> JSONResponse: ...

# Estilo 2 (add_exception_handler): para handlers síncronos de libs externas (RateLimitExceeded)
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
```

### Padrão de fixture de testes de sweeper
**Fonte:** `tests/test_api.py` linhas 148–166 (`test_sweeper_deletes_expired_wavs`)
**Aplicar em:** `test_sweeper_deletes_partial_files`
```python
# Estrutura: criar arquivo → setar mtime no passado → chamar sweep → assert exists()/not exists()
past = time.time() - 1200  # 20 min atrás > ttl de 900s
os.utime(arquivo, (past, past))
```

---

## Alertas de Integração

### Colisão de nome de parâmetro em `submit_job`
O parâmetro body da rota atual se chama `request: JobRequest`. Com a adição de `request: Request` do slowapi, há colisão de nome. A mudança obrigatória é:
- Renomear parâmetro body: `request: JobRequest` → `request_body: JobRequest`
- Atualizar referência interna: `request.youtube_url` → `request_body.youtube_url`
- O teste `test_post_jobs_returns_job_id` (linha 31) não quebra — ele passa `json={"youtube_url": ...}` e não depende do nome do parâmetro Python

### Ordem dos decorators em `submit_job` (crítico)
```python
# CORRETO — @app.post mais longe da função, @limiter.limit mais próximo:
@app.post("/jobs", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def submit_job(request: Request, request_body: JobRequest) -> dict:

# ERRADO — rate limit é silenciosamente ignorado:
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
@app.post("/jobs", status_code=202)
def submit_job(...):
```

### Testes de rate limit em ambiente de teste
Os testes `test_rate_limit_returns_429` e `test_rate_limit_retry_after_header` requerem que o slowapi esteja inicializado com `storage_uri` apontando para o Redis de teste (`redis://localhost:6380/0` via `conftest.py`). Se o Redis não estiver disponível, os testes vão falhar com conexão recusada — não com falha de lógica. Esses testes são unitários (sem `@pytest.mark.e2e`) mas precisam de Redis no ambiente de CI.

---

## No Analog Found

Nenhum arquivo desta fase está sem analog. Todas as mudanças são extensões de arquivos existentes.

---

## Metadata

**Analog search scope:** `api/`, `tests/`
**Files scanned:** 5 (`api/config.py`, `api/main.py`, `api/tasks.py`, `tests/test_api.py`, `tests/conftest.py`)
**Pattern extraction date:** 2026-05-04
