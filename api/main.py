"""FastAPI app — POST /jobs, GET /jobs/{id}, GET /files/{id}."""
from __future__ import annotations

import logging
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import redis as redis_lib
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, field_validator

from api.config import settings
from api.tasks import celery_app, process_job, JobFailure

logger = logging.getLogger(__name__)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
JOB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9-]{1,64}$")

# Module-level Redis client — connection pool reused across requests.
_redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
JOB_REGISTRY_KEY = "sg:jobs"

# Rate limiting — D-01/D-02/D-03 (Phase 3)
# Redis backend obrigatorio: in-memory falha com multiplos workers Uvicorn (issue #226)
# CR-01: usa request.client.host (IP real da conexão TCP) em vez de get_ipaddr, que lê
# X-Forwarded-For sem verificação — qualquer cliente poderia rotacionar esse header e
# burlar o limite. client.host é setado pelo ASGI layer a partir da conexão TCP e não
# pode ser forjado pelo cliente.
def _real_ip(request: Request) -> str:
    """Retorna o IP real do cliente via conexão TCP — não spoofável."""
    return request.client.host  # definido pelo ASGI layer, não pelo cliente


limiter = Limiter(
    key_func=_real_ip,               # IP da conexão TCP — não spoofável via header
    storage_uri=settings.redis_url,  # Redis compartilhado entre todos os workers
    headers_enabled=True,            # Injeta Retry-After, X-RateLimit-* automaticamente
)


class JobRequest(BaseModel):
    youtube_url: str

    @field_validator("youtube_url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https")
        if parsed.netloc not in YOUTUBE_HOSTS:
            raise ValueError(
                f"URL must be a YouTube link (got: {parsed.netloc or '(empty)'})"
            )
        return v


def sweep_expired_wavs(directory: Path, ttl_seconds: int) -> int:
    """Delete sg_*.wav, sg_*.part, sg_*.ytdl in `directory` older than `ttl_seconds`.

    Returns count deleted. Pure function — testable without threads.
    D-01: TTL matches the 15-minute WAV lifecycle decision.
    D-05/D-06 (Phase 3): also cleans yt-dlp partial files left by SIGKILL'd workers.
    Extensoes corretas confirmadas em yt_dlp/downloader/common.py:
      .part = arquivo de download parcial (temp_name)
      .ytdl = arquivo de estado/progresso (ytdl_filename)
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


def _run_sweeper_loop() -> None:
    """Daemon thread: sweep /tmp for expired sg_*.wav files every 60 seconds."""
    while True:
        try:
            count = sweep_expired_wavs(Path("/tmp"), settings.wav_ttl)
            if count > 0:
                logger.info("wav-sweeper: deleted %d expired WAV file(s)", count)
        except Exception:  # noqa: BLE001
            logger.exception("wav-sweeper iteration failed; continuing")
        time.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweeper = threading.Thread(
        target=_run_sweeper_loop,
        daemon=True,
        name="wav-sweeper",
    )
    sweeper.start()
    logger.info("wav-sweeper thread started (TTL=%ds)", settings.wav_ttl)
    yield


app = FastAPI(title="SoundGrabber API", version="0.3.0", lifespan=lifespan)

app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Formato unificado {error, error_type} com Retry-After header (D-04).

    exc.limit e o wrapper Limit do slowapi; exc.limit.limit e o RateLimitItem da lib limits.
    get_expiry() retorna o tamanho da janela em segundos (ex: 60 para "3/minute").
    _inject_headers adiciona Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining.
    headers_enabled=True no Limiter e necessario para _inject_headers funcionar.
    """
    seconds = int(exc.limit.limit.get_expiry())
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


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Converte 422 Pydantic para formato {error, error_type} unificado (D-07).

    Pydantic v2 prefixa mensagens de field_validator com "Value error, " automaticamente.
    removeprefix() remove esse prefixo sem alterar o resto da mensagem.
    """
    errors = exc.errors()
    msg = errors[0].get("msg", "Invalid request") if errors else "Invalid request"
    msg = msg.removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content={"error": msg, "error_type": "validation_error"},
    )


@app.post("/jobs", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def submit_job(request: Request, request_body: JobRequest, response: Response) -> dict:
    task = process_job.delay(request_body.youtube_url)
    _redis.sadd(JOB_REGISTRY_KEY, task.id)
    _redis.expire(JOB_REGISTRY_KEY, settings.wav_ttl)
    return {"job_id": task.id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    if not JOB_ID_PATTERN.match(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    # Pitfall 1 / D-02: PENDING is ambiguous between "in queue" and "never existed".
    if not _redis.sismember(JOB_REGISTRY_KEY, job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    result = AsyncResult(job_id, app=celery_app)
    state = result.state

    if state in ("PENDING", "STARTED"):
        return {"status": "queued"}

    if state == "DOWNLOADING":
        meta = result.info if isinstance(result.info, dict) else {}
        return {"status": "downloading", "stage": meta.get("stage")}

    if state == "CONVERTING":
        meta = result.info if isinstance(result.info, dict) else {}
        return {"status": "converting", "stage": meta.get("stage")}

    if state == "ANALYZING":
        meta = result.info if isinstance(result.info, dict) else {}
        return {"status": "analyzing", "stage": meta.get("stage")}

    if state == "SUCCESS":
        data = result.result if isinstance(result.result, dict) else {}
        # D-05: wav_path is internal — strip it before responding.
        return {
            "status": "done",
            "bpm": data.get("bpm"),
            "bpm_half": data.get("bpm_half"),
            "bpm_double": data.get("bpm_double"),
            "key": data.get("key"),
            "camelot": data.get("camelot"),
            "duration_sec": data.get("duration_sec"),
            "download_url": data.get("download_url"),
        }

    if state == "FAILURE":
        # Pitfall 3: result.result is the exception object in FAILURE state.
        exc = result.result
        error = getattr(exc, "error", None)
        error_type = getattr(exc, "error_type", None)
        if error is None or error_type is None:
            error = "An internal error occurred. Please try again."
            error_type = "internal_error"
        return {"status": "failed", "error": error, "error_type": error_type}

    return {"status": "queued"}


@app.get("/files/{job_id}")
def download_file(job_id: str):
    if not JOB_ID_PATTERN.match(job_id):
        raise HTTPException(status_code=404, detail="File not ready or job not found")

    result = AsyncResult(job_id, app=celery_app)
    if result.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="File not ready or job not found")

    data = result.result if isinstance(result.result, dict) else {}
    wav_path_str = data.get("wav_path")
    if not wav_path_str:
        raise HTTPException(status_code=410, detail="File expired")

    wav_path = Path(wav_path_str)

    # Path traversal defense: wav_path must be inside /tmp and start with sg_.
    try:
        wav_path.resolve().relative_to(Path("/tmp").resolve())
    except ValueError:
        raise HTTPException(status_code=410, detail="File expired")
    if not wav_path.name.startswith("sg_"):
        raise HTTPException(status_code=410, detail="File expired")

    if not wav_path.exists():
        raise HTTPException(status_code=410, detail="File expired")

    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=f"soundgrabber_{job_id[:8]}.wav",
    )
