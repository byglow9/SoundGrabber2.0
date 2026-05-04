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
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from api.config import settings
from api.tasks import celery_app, process_job, JobFailure

logger = logging.getLogger(__name__)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
JOB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9-]{1,64}$")

# Module-level Redis client — connection pool reused across requests.
_redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
JOB_REGISTRY_KEY = "sg:jobs"


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


app = FastAPI(title="SoundGrabber API", version="0.2.0", lifespan=lifespan)


@app.post("/jobs", status_code=202)
def submit_job(request: JobRequest) -> dict:
    task = process_job.delay(request.youtube_url)
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
