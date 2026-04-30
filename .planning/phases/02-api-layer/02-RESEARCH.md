# Phase 2: API Layer - Research

**Researched:** 2026-04-30
**Domain:** FastAPI + Celery + Redis — job-queue HTTP API
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** TTL fixo de 15 minutos após o job completar — arquivo `/tmp/sg_*.wav` é deletado por background sweeper.
- **D-02:** Metadados do job no Redis têm o mesmo TTL de 15 minutos. `GET /jobs/{id}` após expiração retorna 404.
- **D-03:** Código em `api/` com três módulos: `api/main.py` (FastAPI + rotas), `api/tasks.py` (Celery tasks), `api/config.py` (settings via env vars). `pipeline.py` permanece na raiz sem modificações.
- **D-04:** Dependências adicionadas ao `requirements.txt` existente — sem arquivo separado.
- **D-05:** Job falho retorna `status: "failed"` com mensagem sanitizada no campo `error`.
- **D-06:** Campo `error_type` distingue: `"validation_error"`, `"download_error"`, `"internal_error"`.
- **D-07:** Setup manual sem Docker: Redis via apt, worker Celery em terminal separado, uvicorn em outro terminal.

### Claude's Discretion

- Número exato de workers Celery concorrentes (STATE.md sugere cap de 3)
- Prefetch multiplier e autoscale do Celery
- Redis connection pool settings
- Versões exatas dos pacotes (fastapi, celery, redis-py)
- Formato exato dos status intermediários além dos 5 definidos no ROADMAP.md

### Deferred Ideas (OUT OF SCOPE)

Nenhuma — discussão manteve-se dentro do escopo da Fase 2.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Usuário pode colar um link do YouTube e iniciar o processamento | POST /jobs endpoint — `task.delay()` retorna job_id imediatamente; FastAPI + Celery integration pattern verificado |
| CORE-02 | Sistema valida que a URL fornecida é um link válido do YouTube antes de processar | Pydantic URL validation no request body; regex ou `urllib.parse` para confirmar domínio YouTube antes de enfileirar |
| CORE-06 | Usuário pode baixar o arquivo WAV diretamente via botão de download após processamento | `FileResponse` (starlette/FastAPI) transmite WAV em chunks sem carregar arquivo inteiro em memória; verificado na docs oficial |
</phase_requirements>

---

## Summary

A Fase 2 expõe o `pipeline.py` da Fase 1 via HTTP usando o trio FastAPI + Celery + Redis. O padrão central é: FastAPI recebe `POST /jobs`, chama `task.delay(url)` que retorna um `AsyncResult` com `id` (UUID gerado pelo Celery/Redis), e responde com `{"job_id": task.id}` em menos de 50ms — muito abaixo do limite de 300ms do success criteria. O worker Celery executa `check_duration → download_audio → analyze_audio` em segundo plano, atualizando o estado via `self.update_state()` a cada estágio.

O gerenciamento de estado do job usa dois mecanismos em paralelo: `self.update_state()` do Celery escreve no backend Redis com estados customizados (`DOWNLOADING`, `CONVERTING`, `ANALYZING`), e ao finalizar o resultado completo (BPM, key, download URL) fica acessível via `AsyncResult.result`. O TTL de 15 minutos no Redis é implementado via `result_expires = 900` no config do Celery — com a ressalva crítica de que para o Redis backend o TTL é setado nativamente via `EXPIRE` do Redis (sem necessidade de Celery Beat). O sweeper de arquivos `/tmp/sg_*.wav` é um loop `threading.Thread` iniciado no `lifespan` do FastAPI.

Para streaming do WAV, `FileResponse` do FastAPI/Starlette é a escolha correta: transmite em chunks sem carregar o arquivo em memória, envia automaticamente `Content-Length`, `Content-Disposition`, e `ETag`. Não é necessário `StreamingResponse` com generator manual para este caso.

**Primary recommendation:** Use `Celery 5.6.x` com `task_track_started=True`, estados customizados via `self.update_state()`, `result_expires=900`, `worker_prefetch_multiplier=1`, concorrência cap de 3. Use `FileResponse` para GET /files/{id}. Sweeper como `threading.Thread` no lifespan.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.136.1 | Framework HTTP + validação Pydantic | Async-native, rápido de escrever, integra bem com Celery via endpoints síncronos simples |
| uvicorn | 0.46.0 | ASGI server para desenvolvimento | Padrão de fato para FastAPI; `--reload` para dev |
| celery[redis] | 5.6.3 | Task queue + worker management | Suporte a estados customizados, `update_state()`, Redis como broker+backend num serviço só |
| redis | 7.4.0 | Cliente Python para Redis | Usado pelo Celery internamente; também usado diretamente por `api/main.py` para verificar existência de job (TTL check) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | (via fastapi) | Validação do request body (URL) | Validação automática de `JobRequest` com campo `youtube_url: str` |
| starlette | (via fastapi) | `FileResponse` para streaming de WAV | Já incluído no FastAPI; não instalar separado |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FileResponse | StreamingResponse + generator manual | FileResponse já faz chunked streaming; StreamingResponse só vale para fontes que não são arquivos do filesystem |
| threading.Thread sweeper | Celery Beat periodic task | Celery Beat requer processo extra; threading é mais simples para dev sem Docker |
| AsyncResult.state | Redis hash manual (`HSET`) | AsyncResult já usa Redis via backend do Celery; duplicar em hash separado seria redundante |

**Installation:**
```bash
pip install "fastapi==0.136.1" "uvicorn==0.46.0" "celery[redis]==5.6.3" "redis==7.4.0"
```

**Adicionar ao `requirements.txt` existente** (D-04):
```
fastapi==0.136.1
uvicorn==0.46.0
celery[redis]==5.6.3
redis==7.4.0
```

**Version verification:** [VERIFIED: pip3 index versions — consultado em 2026-04-30]
- fastapi: 0.136.1 (atual)
- celery: 5.6.3 (atual)
- redis: 7.4.0 (atual)
- uvicorn: 0.46.0 (atual)

---

## Architecture Patterns

### Recommended Project Structure

```
api/
├── __init__.py          # vazio — torna api/ um package importável
├── main.py              # FastAPI app + rotas + lifespan (sweeper)
├── tasks.py             # Celery app instance + task process_job()
└── config.py            # Settings via env vars (pydantic BaseSettings ou os.environ)
pipeline.py              # Fase 1 — NÃO MODIFICAR (D-03)
requirements.txt         # Fase 1 + Fase 2 juntos (D-04)
```

### Pattern 1: FastAPI + Celery — Inicialização e Submissão

**What:** Celery app definido em `api/tasks.py`; FastAPI importa a task e chama `.delay()`.
**When to use:** Sempre que o endpoint precisa retornar imediatamente enquanto trabalho pesado roda em background.

```python
# api/tasks.py
from celery import Celery
from api.config import settings

celery_app = Celery(
    "soundgrabber",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,       # ativa estado STARTED automaticamente
    result_expires=900,            # TTL 15 min no Redis backend (D-02)
    worker_prefetch_multiplier=1,  # cada worker reserva 1 task por vez (CPU-bound)
    broker_transport_options={"visibility_timeout": 1800},  # 30 min — maior que o job mais longo
)
```

```python
# api/main.py (fragmento do endpoint POST /jobs)
from api.tasks import process_job

@app.post("/jobs", status_code=202)
def submit_job(request: JobRequest):
    task = process_job.delay(request.youtube_url)
    return {"job_id": task.id}
```

Source: [CITED: testdriven.io/blog/fastapi-and-celery] + [CITED: docs.celeryq.dev/en/stable/userguide/configuration.html]

### Pattern 2: Estados Customizados com `update_state()`

**What:** Task com `bind=True` chama `self.update_state()` para emitir status intermediários que o polling de `GET /jobs/{id}` lê via `AsyncResult`.
**When to use:** Qualquer pipeline multi-estágio onde o cliente precisa de feedback de progresso.

```python
# api/tasks.py
@celery_app.task(bind=True, name="soundgrabber.process_job")
def process_job(self, url: str):
    config = get_config()

    # Stage 0: duration check
    self.update_state(state="DOWNLOADING", meta={"stage": "checking_duration"})
    info = check_duration(url, config.cookies_path)

    # Stage 1: download + convert
    self.update_state(state="DOWNLOADING", meta={"stage": "downloading"})
    wav_path = download_audio(url, config.cookies_path, config.po_token)

    self.update_state(state="CONVERTING", meta={"stage": "converting"})
    # (download_audio já produz WAV via FFmpegExtractAudio — convert_to_wav é pass-through)

    # Stage 2: analyze
    self.update_state(state="ANALYZING", meta={"stage": "analyzing"})
    result = analyze_audio(wav_path)

    # Agendar deleção do WAV após TTL (sweeper cuida, mas registrar o path)
    return {
        "status": "done",
        "bpm": result["bpm"],
        "bpm_half": result["bpm_half"],
        "bpm_double": result["bpm_double"],
        "key": result["key"],
        "camelot": result["camelot"],
        "duration_sec": result["duration_sec"],
        "wav_path": result["wav_path"],  # usado internamente por GET /files/{id}
        "download_url": f"/files/{self.request.id}",
    }
```

Source: [CITED: docs.celeryq.dev/en/stable/userguide/tasks.html#custom-states]

### Pattern 3: GET /jobs/{id} — Polling de Status

**What:** Endpoint lê `AsyncResult` e mapeia estados do Celery para o contrato HTTP da API.
**When to use:** Padrão job-queue HTTP — cliente faz polling a cada 2 segundos.

```python
# api/main.py (fragmento)
from celery.result import AsyncResult

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    result = AsyncResult(job_id, app=celery_app)

    # Estados do Celery → estados do contrato da API
    state_map = {
        "PENDING":    "queued",
        "STARTED":    "queued",     # task_track_started=True ativa este
        "DOWNLOADING": "downloading",
        "CONVERTING":  "converting",
        "ANALYZING":   "analyzing",
        "SUCCESS":    "done",
        "FAILURE":    "failed",
    }

    api_status = state_map.get(result.state, "queued")

    if result.state == "FAILURE":
        exc = result.result  # a exceção capturada
        return {
            "status": "failed",
            "error": _sanitize_error(exc),
            "error_type": _classify_error(exc),  # D-06
        }

    if result.state == "SUCCESS":
        data = result.result
        return {
            "status": "done",
            "bpm": data["bpm"],
            "bpm_half": data["bpm_half"],
            "bpm_double": data["bpm_double"],
            "key": data["key"],
            "camelot": data["camelot"],
            "duration_sec": data["duration_sec"],
            "download_url": data["download_url"],
        }

    # Estado intermediário: inclui stage se disponível no meta
    meta = result.info if isinstance(result.info, dict) else {}
    return {"status": api_status, "stage": meta.get("stage")}
```

**Importante:** Se `result.state == "PENDING"` e o job_id não existe no Redis (porque expirou ou nunca existiu), retornar 404 — não confundir com job em fila (D-02).

Source: [CITED: docs.celeryq.dev/en/stable/reference/celery.result.html] + [ASSUMED verificar se PENDING é ambíguo entre "enfileirado" e "não encontrado"]

### Pattern 4: GET /files/{id} — Streaming do WAV

**What:** `FileResponse` do FastAPI/Starlette transmite o arquivo em chunks sem carregar em memória.
**When to use:** Sempre que o arquivo existe no filesystem — mais simples que StreamingResponse.

```python
# api/main.py (fragmento)
from fastapi.responses import FileResponse
from pathlib import Path

@app.get("/files/{job_id}")
def download_file(job_id: str):
    result = AsyncResult(job_id, app=celery_app)

    if result.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="File not ready or job not found")

    wav_path = Path(result.result["wav_path"])
    if not wav_path.exists():
        raise HTTPException(status_code=410, detail="File expired")

    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=f"soundgrabber_{job_id[:8]}.wav",  # Content-Disposition: attachment
    )
```

**Por que `FileResponse` e não `StreamingResponse`:** FileResponse usa Starlette's `StaticFiles` chunking interno, envia `Content-Length` automaticamente (necessário para barra de progresso do browser), e não requer generator manual. [CITED: fastapi.tiangolo.com/advanced/custom-response]

### Pattern 5: Background Sweeper — Deleção de WAVs após TTL

**What:** Thread daemon iniciada no lifespan do FastAPI varre `/tmp/sg_*.wav` e deleta arquivos com mtime > 15 minutos.
**When to use:** Cleanup de arquivos temporários sem Celery Beat (D-07 — sem Docker).

```python
# api/main.py (fragmento)
import threading
import time
from pathlib import Path
from contextlib import asynccontextmanager

WAV_TTL_SECONDS = 900  # D-01: 15 minutos

def _run_sweeper():
    """Daemon thread: deleta /tmp/sg_*.wav com mais de TTL segundos."""
    while True:
        now = time.time()
        for wav in Path("/tmp").glob("sg_*.wav"):
            try:
                if now - wav.stat().st_mtime > WAV_TTL_SECONDS:
                    wav.unlink()
            except OSError:
                pass
        time.sleep(60)  # verificar a cada 1 minuto

@asynccontextmanager
async def lifespan(app):
    t = threading.Thread(target=_run_sweeper, daemon=True, name="wav-sweeper")
    t.start()
    yield
    # daemon=True: thread é encerrada automaticamente quando o processo morre

app = FastAPI(lifespan=lifespan)
```

Source: [CITED: fastapi.tiangolo.com/advanced/events/] + padrão threading.Thread daemon [ASSUMED — sem referência oficial específica para esse pattern]

### Pattern 6: Mapeamento de Exceções → error_type (D-06)

**What:** Task captura exceções tipadas do `pipeline.py` e mapeia para `error_type` do contrato.
**When to use:** Sempre — o worker NUNCA deve deixar exceção não tratada (o Celery captura, mas sem a mensagem sanitizada).

```python
# api/tasks.py (fragmento — dentro do task)
try:
    # ... pipeline calls ...
except ValueError as e:
    # check_duration ValueError (vídeo longo), validate_wav ValueError
    self.update_state(state="FAILURE", meta={
        "error": "Video is too long (max 15 minutes)." if "too long" in str(e).lower()
                 else "Could not validate audio file.",
        "error_type": "validation_error",
    })
    raise  # Celery precisa ver a exceção para marcar como FAILURE
except RuntimeError as e:
    # download_audio RuntimeError (yt-dlp bloqueado, rede, token expirado)
    self.update_state(state="FAILURE", meta={
        "error": "Download failed. The video may be unavailable or blocked.",
        "error_type": "download_error",
    })
    raise
except Exception as e:
    self.update_state(state="FAILURE", meta={
        "error": "An internal error occurred. Please try again.",
        "error_type": "internal_error",
    })
    raise
```

**Importante:** Quando Celery captura uma exceção, `result.result` é o objeto exception (não o dict de meta). O endpoint `GET /jobs/{id}` precisa verificar se `result.info` tem o dict com `error` e `error_type`, caso contrário inspecionar `result.result` para extrair a mensagem.

Source: [CITED: docs.celeryq.dev/en/stable/userguide/tasks.html] + [ASSUMED — comportamento exato de result.info em FAILURE precisa de teste de integração para confirmar]

### Anti-Patterns to Avoid

- **Não usar `FastAPI BackgroundTasks` para o pipeline:** librosa é CPU-bound (NumPy); `BackgroundTasks` roda na event loop do uvicorn e bloquearia requisições simultâneas. [CITED: STATE.md — decisão registrada]
- **Não chamar `task.get()` dentro de um endpoint FastAPI:** `get()` bloqueia até o task completar — anula o propósito da fila. Use `AsyncResult(id)` para polling sem bloqueio.
- **Não usar `worker_prefetch_multiplier` > 1 com tarefas longas:** O default do Celery é 4, o que significa que um worker pode reservar 4 tarefas de 15 minutos, bloqueando outros workers. Setar para 1. [CITED: docs.celeryq.dev/en/stable/userguide/optimizing.html]
- **Não confiar em `result_expires` sozinho para cleanup de WAVs:** `result_expires` controla o TTL dos metadados no Redis, não os arquivos em `/tmp`. O sweeper de arquivos é necessário separadamente.
- **Não expor `wav_path` no contrato público da API:** O campo `wav_path` é string do filesystem do servidor — não deve aparecer na resposta de `GET /jobs/{id}`. Usar apenas internamente em `GET /files/{id}`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Task queue + worker management | Sistema próprio com `subprocess` ou threads | Celery 5.x | Retry automático, estados, serialização, broker abstraction |
| Job ID generation | `uuid.uuid4()` manual + dict em memória | Celery `task.id` (gerado pelo Redis/broker) | IDs únicos garantidos, persistidos no broker, sem estado em memória do servidor |
| File chunked streaming | `open(f, 'rb')` + `read()` loop manual | `FileResponse` | Starlette gerencia chunking, backpressure, `Content-Length`, range requests |
| URL pattern matching YouTube | Regex próprio | `urllib.parse` + verificação de `netloc` | Regex de YouTube válida é complexa (youtu.be, youtube.com/shorts, mobile.youtube.com) |
| Redis connection pooling | `redis.Redis()` a cada request | Celery gerencia pool interno; redis-py pool via `ConnectionPool` | Conexões abertas/fechadas a cada request levam a file descriptor exhaustion |

**Key insight:** O Celery elimina todo o estado em memória — se o uvicorn reiniciar, os jobs em andamento e seus estados continuam no Redis. Não há nada para perder.

---

## Runtime State Inventory

> Fase 2 é greenfield (novo código em `api/`). Nenhum rename/refactor envolvido.

Não aplicável — nenhuma renomeação de strings ou migração de dados. A Fase 2 cria novos módulos, não altera os existentes.

---

## Common Pitfalls

### Pitfall 1: PENDING Ambíguo no Celery

**What goes wrong:** `AsyncResult(id).state` retorna `"PENDING"` tanto para jobs que estão na fila quanto para IDs que nunca existiram (ou expiraram do Redis). `GET /jobs/{id}` com um ID inválido retornaria `{"status": "queued"}` em vez de 404.

**Why it happens:** O Celery usa `PENDING` como estado default para qualquer ID que não está no backend. É por design — o backend não sabe se o task nunca existiu ou ainda não foi processado.

**How to avoid:** Estratégia: no `POST /jobs`, armazenar o `task.id` em um Redis Set (ou hash) com TTL de 15 minutos. Em `GET /jobs/{id}`, verificar primeiro se o ID existe nesse Set antes de consultar `AsyncResult`. Alternativamente: retornar 404 quando `state == "PENDING"` e `result is None` após um timeout razoável — mas isso tem race condition nos primeiros segundos após submissão.

**Warning signs:** Testes retornam `queued` para IDs aleatórios que nunca foram submetidos.

### Pitfall 2: visibility_timeout Menor que a Duração do Job

**What goes wrong:** O default do Redis broker é 3600s (1 hora), mas se configurado incorretamente para um valor menor que a duração do download+análise (pode levar 10+ minutos para vídeos longos), o broker reentrega a task para outro worker enquanto o primeiro ainda executa. O job é processado duas vezes, produzindo dois arquivos WAV.

**Why it happens:** Redis usa visibility timeout para detectar workers mortos. Se o worker não faz `ACK` dentro do timeout, Redis assume que o worker caiu.

**How to avoid:** Setar `broker_transport_options = {"visibility_timeout": 1800}` (30 minutos — o dobro do limite de vídeo de 15 min). [CITED: docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html]

**Warning signs:** O mesmo job aparece processado duas vezes em logs, ou dois arquivos `/tmp/sg_*.wav` com o mesmo conteúdo mas nomes diferentes.

### Pitfall 3: result.result É a Exceção, Não o Dict

**What goes wrong:** Em `result.state == "FAILURE"`, `result.result` é o objeto exception Python (ex: `RuntimeError("yt-dlp download failed: ...")`), não um dict. Tentar fazer `result.result["error"]` lança `TypeError`.

**Why it happens:** O Celery serializa a exceção, não o dict de meta passado para `update_state()` — o meta de `update_state()` no estado FAILURE pode ou não estar disponível em `result.info`.

**How to avoid:** No handler de falha, usar `result.info` (que preserva o meta dict) e fazer fallback para `str(result.result)` se `result.info` for a exceção. Validar com teste de integração usando `task_always_eager=True`. [ASSUMED — o comportamento exato de `result.info` vs `result.result` em FAILURE varia entre versões do Celery; confirmar com teste]

**Warning signs:** `TypeError: 'RuntimeError' object is not subscriptable` nos logs do servidor.

### Pitfall 4: WAV Path Expõe Filesystem do Servidor

**What goes wrong:** Se `result.result["wav_path"]` for retornado na resposta de `GET /jobs/{id}`, o cliente recebe `/tmp/sg_abc123.wav` — expõe estrutura do servidor e não é uma URL utilizável pelo browser.

**Why it happens:** O campo `wav_path` é necessário internamente para que `GET /files/{id}` saiba qual arquivo servir, mas não deve fazer parte do contrato público.

**How to avoid:** O campo `download_url` na resposta é sempre `/files/{job_id}`. O `wav_path` fica apenas no `result.result` interno e é lido apenas pelo endpoint `GET /files/{id}`.

### Pitfall 5: `result_expires` com Redis Backend — Caveats

**What goes wrong:** A documentação do Celery menciona que `result_expires` requer Celery Beat para funcionar com backends de banco de dados. Há issues abertas no GitHub relatando que o Redis backend não aplica `EXPIRE` corretamente em algumas versões.

**Why it happens:** O Redis backend do Celery usa o comando `EXPIRE` nativamente (sem Celery Beat), mas bugs históricos causaram TTL `-1` (sem expiração).

**How to avoid:** Verificar após implementação: `redis-cli TTL celery-task-meta-{job_id}` deve retornar ~900. Se retornar -1, adicionar `redis_backend_health_check_interval = 30` ou setar TTL manualmente via `redis.expire()` após escrever o resultado. [CITED: github.com/celery/celery/issues/7801]

### Pitfall 6: Concorrência do Worker e OOM com librosa

**What goes wrong:** `librosa.load()` carrega áudio NumPy em RAM. 3 jobs simultâneos com vídeos de 15 minutos a 22050Hz mono = ~3 × (22050 × 90 × 4 bytes) ≈ 225MB de arrays NumPy ativos ao mesmo tempo, mais os buffers do yt-dlp durante o download.

**Why it happens:** O pipeline usa 90 segundos de áudio (janela de 90s no `detect_bpm`), mas o yt-dlp baixa o vídeo completo primeiro.

**How to avoid:** Cap de 3 workers concorrentes como STATE.md recomenda. Usar `--concurrency 3` ao iniciar o worker: `celery -A api.tasks worker --loglevel=info --concurrency 3`. [CITED: STATE.md — risco MODERATE documentado]

---

## Code Examples

### Celery App — Configuração Completa

```python
# api/tasks.py
# Source: docs.celeryq.dev/en/stable/userguide/configuration.html [CITED]
from celery import Celery
from api.config import settings
from pipeline import check_duration, download_audio, analyze_audio

celery_app = Celery("soundgrabber")
celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=900,               # TTL 15min — D-02
    worker_prefetch_multiplier=1,     # CPU-bound: 1 task por worker por vez
    broker_transport_options={"visibility_timeout": 1800},  # 30min > max job duration
    task_acks_late=True,              # ACK após completar, não ao receber
)
```

### Settings — config.py

```python
# api/config.py
# Source: padrão 12-factor app [ASSUMED — sem referência específica]
import os
from dataclasses import dataclass

@dataclass
class Settings:
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    cookies_path: str = os.environ.get("YTDLP_COOKIES_FILE", "")
    po_token: str = os.environ.get("YTDLP_PO_TOKEN", "")
    wav_ttl: int = int(os.environ.get("WAV_TTL_SECONDS", "900"))

settings = Settings()
```

### Validação de URL YouTube — CORE-02

```python
# api/main.py (fragmento)
# Source: urllib.parse stdlib [VERIFIED: Python 3.12 docs]
from urllib.parse import urlparse
from pydantic import BaseModel, field_validator

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}

class JobRequest(BaseModel):
    youtube_url: str

    @field_validator("youtube_url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        try:
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https"):
                raise ValueError("URL must use http or https")
            if parsed.netloc not in YOUTUBE_HOSTS:
                raise ValueError(f"URL must be a YouTube link (got: {parsed.netloc})")
        except Exception as e:
            raise ValueError(str(e))
        return v
```

### Startup do Worker (linha de comando)

```bash
# Terminal 1 — Redis
sudo service redis-server start  # ou: redis-server

# Terminal 2 — Celery worker
celery -A api.tasks worker --loglevel=info --concurrency 3

# Terminal 3 — FastAPI
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Source: D-07 (CONTEXT.md) [CITED]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `@asynccontextmanager` + `FastAPI(lifespan=...)` | FastAPI 0.93+ | `on_event` ainda funciona mas é deprecated; usar lifespan |
| `task_always_eager` (testes) | `task_always_eager` ainda válido em Celery 5.x | — | Nenhuma mudança — continua o padrão para testes unitários sem Redis real |
| `celery.app.amqp` broker only | Redis como broker E backend num mesmo serviço | Celery 4+ | Simplifica dev sem RabbitMQ; Redis cuida de fila + armazenamento de resultados |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Substituir por `lifespan` context manager. [CITED: fastapi.tiangolo.com/advanced/events/]
- `CELERYD_CONCURRENCY` (maiúsculo): Substituído por `worker_concurrency` (snake_case) no Celery 4+. Usar `--concurrency` na CLI ou `worker_concurrency` no config.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PENDING ambíguo pode ser resolvido armazenando o job_id em Redis Set no POST /jobs | Pitfall 1, Pattern 3 | Se a estratégia de detecção de job inexistente for diferente, pode retornar 404 para jobs legítimos nos primeiros milissegundos |
| A2 | `result.info` preserva o meta dict passado em `update_state(state="FAILURE", meta={...})` no Celery 5.6.x | Pattern 6, Pitfall 3 | Se `result.info` for a exceção e não o meta dict, o endpoint de falha não consegue extrair `error` e `error_type` sem parsear a exceção |
| A3 | Threading daemon sweeper é suficiente para o caso de dev sem Docker | Pattern 5 | Se uvicorn rodar com múltiplos workers (--workers N > 1), cada processo teria seu próprio thread sweeper varrendo os mesmos arquivos — race condition benigna em deleção dupla, não crítica |
| A4 | `result_expires=900` aplica TTL Redis corretamente no Celery 5.6.3 sem Celery Beat | Standard Stack, Pitfall 5 | Se o bug histórico de TTL=-1 afetar esta versão, metadados de job nunca expiram no Redis — memory leak gradual |

---

## Open Questions

1. **Como diferenciar job_id inexistente de job em fila no estado PENDING?**
   - What we know: `AsyncResult(id).state == "PENDING"` para ambos os casos por design do Celery
   - What's unclear: Qual é a abordagem mais simples que não introduz overhead de Redis extra para um MVP?
   - Recommendation: Armazenar `job_ids` em Redis Set com `SADD` + `EXPIRE 900` no POST /jobs. GET /jobs/{id} faz `SISMEMBER` antes de consultar AsyncResult. Custo: 1 operação Redis extra por poll.

2. **`result.info` vs `result.result` quando state == "FAILURE" com meta dict**
   - What we know: A exceção capturada pelo Celery vai para `result.result`. O meta do `update_state()` pode ser sobrescrito pela serialização da exceção.
   - What's unclear: No Celery 5.6.x com Redis backend, `result.info` retorna o meta dict ou a exceção?
   - Recommendation: Implementar, escrever teste com `task_always_eager=True` e uma task que lança exceção com `update_state()` antes do raise. Verificar empiricamente.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis server | Celery broker + backend | ✗ | — | Instalar via `sudo apt install redis-server` (v7.0.15 disponível no apt) |
| Python 3.12 | FastAPI + Celery | ✓ | 3.12.3 | — |
| pip 24.0 | Instalação de pacotes | ✓ | 24.0 | — |
| ffmpeg | pipeline.py (Fase 1) | Não verificado nesta sessão | — | Já deveria estar instalado (Fase 1) |

**Missing dependencies with no fallback:**
- **Redis server:** DEVE ser instalado antes de iniciar o worker. Comando: `sudo apt install redis-server` (versão 7.0.15 disponível no apt do Ubuntu 24.04).

**Missing dependencies with fallback:**
- Nenhuma.

**Nota:** Redis server não está instalado na máquina de desenvolvimento atual. O planner DEVE incluir uma Wave 0 task para instalação do Redis.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (raiz do projeto) |
| Quick run command | `pytest tests/test_api.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | POST /jobs retorna job_id em < 300ms | unit (task_always_eager=False, mock task) | `pytest tests/test_api.py::test_post_jobs_returns_job_id -x` | ❌ Wave 0 |
| CORE-02 | URL não-YouTube rejeitada com 422 | unit (TestClient) | `pytest tests/test_api.py::test_invalid_url_rejected -x` | ❌ Wave 0 |
| CORE-02 | URL YouTube válida aceita | unit (TestClient) | `pytest tests/test_api.py::test_valid_youtube_url_accepted -x` | ❌ Wave 0 |
| CORE-06 | GET /files/{id} não carrega WAV em memória; responde com bytes | integration (arquivo WAV real) | `pytest tests/test_api.py::test_file_streaming -x -m integration` | ❌ Wave 0 |
| SC-4 | 3 jobs concorrentes completam sem travar | e2e (worker real + Redis real) | `pytest tests/test_api.py::test_concurrent_jobs -x -m e2e` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_api.py -x -q` (unit only, sem marcadores integration/e2e)
- **Per wave merge:** `pytest tests/ -x -q` (exclui e2e: `-m "not e2e"`)
- **Phase gate:** Suite completa verde (incluindo `-m integration`) antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_api.py` — cobre CORE-01, CORE-02, CORE-06 (unit + integration)
- [ ] `api/__init__.py` — package vazio
- [ ] `api/config.py` — settings
- [ ] `api/tasks.py` — Celery app + task process_job (stub)
- [ ] `api/main.py` — FastAPI app + 3 rotas (stub)
- [ ] Instalação do Redis: `sudo apt install redis-server`

*(Infraestrutura de testes existente: pytest.ini, tests/conftest.py, tests/fixtures/sample.wav — reutilizáveis sem modificação)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | não | API sem autenticação por design (out of scope) |
| V3 Session Management | não | Stateless — sem sessões |
| V4 Access Control | não | Sem usuários, sem roles |
| V5 Input Validation | sim | Pydantic `field_validator` para URL; verificação de netloc YouTube via `urllib.parse` |
| V6 Cryptography | não | Nenhuma criptografia nesta fase |

### Known Threat Patterns for FastAPI + Celery

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SSRF via URL arbitrária (ex: `http://localhost:6379`) | Spoofing / Tampering | Validar `netloc` contra allowlist de hosts YouTube antes de enfileirar (CORE-02) |
| Task flooding — submeter centenas de jobs simultâneos | Denial of Service | Fase 3 (rate limiting) — fora do escopo da Fase 2; cap de 3 workers mitiga parcialmente |
| Path traversal em `job_id` | Tampering | job_id é UUID gerado pelo Celery/Redis; validar formato antes de usar em `AsyncResult()` |
| Exposição de stack trace em erro | Information Disclosure | D-05/D-06: mensagem sanitizada + `error_type` enum; nunca expor exceção raw |
| Temp file disclosure via `/files/{id}` | Information Disclosure | `GET /files/{id}` valida estado do job antes de servir; job_id é opaco para o cliente |

---

## Sources

### Primary (HIGH confidence)

- [CITED: docs.celeryq.dev/en/stable/userguide/configuration.html] — result_expires, worker_prefetch_multiplier, task_track_started, task_always_eager, redis_max_connections
- [CITED: docs.celeryq.dev/en/stable/userguide/tasks.html#custom-states] — update_state(), bind=True pattern, custom state names
- [CITED: docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html] — visibility_timeout, broker_transport_options, Redis URL format
- [CITED: fastapi.tiangolo.com/advanced/custom-response/] — FileResponse vs StreamingResponse, chunked streaming, Content-Disposition
- [CITED: fastapi.tiangolo.com/advanced/events/] — lifespan context manager, startup/shutdown pattern
- [VERIFIED: pip3 index versions — 2026-04-30] — fastapi 0.136.1, celery 5.6.3, redis 7.4.0, uvicorn 0.46.0
- [VERIFIED: apt-cache show redis-server] — versão 7.0.15 disponível no Ubuntu 24.04

### Secondary (MEDIUM confidence)

- [CITED: testdriven.io/blog/fastapi-and-celery/] — padrão de integração FastAPI + Celery, task.delay(), AsyncResult status endpoint
- [CITED: github.com/celery/celery/issues/7801] — caveat sobre result_expires e TTL=-1 no Redis backend

### Tertiary (LOW confidence)

- Padrão de threading.Thread sweeper no lifespan — padrão amplamente usado mas sem referência oficial específica para este caso

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versões verificadas no PyPI em 2026-04-30
- Architecture: HIGH — padrões verificados em docs oficiais Celery + FastAPI
- Pitfalls: MEDIUM — Pitfalls 1 e 3 têm componentes [ASSUMED] que precisam de validação por teste de integração
- Environment: HIGH — verificado diretamente na máquina

**Research date:** 2026-04-30
**Valid until:** 2026-05-30 (pacotes estáveis; revisar se houver Celery 6.x ou FastAPI 1.x)
