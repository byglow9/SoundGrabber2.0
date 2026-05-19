"""Celery app + process_job task. Plan 02 fills in the pipeline calls."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from celery import Celery

from pipeline import check_duration, download_audio, analyze_audio, convert_uploaded_to_wav
from api.config import settings

logger = logging.getLogger(__name__)


class JobFailure(Exception):
    """Sanitized job failure carrying error message and error_type per D-05/D-06.

    Both args passed to super().__init__ so Celery's JSON serializer can reconstruct
    the exception fully (self.args = (error, error_type)).
    Plan 03's GET /jobs/{id} reads .error and .error_type from the exception
    object stored in AsyncResult.result when state == FAILURE.
    """

    def __init__(self, error: str, error_type: str) -> None:
        super().__init__(error, error_type)  # both args in self.args for JSON round-trip
        self.error = error
        self.error_type = error_type


celery_app = Celery("soundgrabber")
celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=settings.wav_ttl,                              # D-02: 15-min TTL on Redis backend
    worker_prefetch_multiplier=1,                                  # CPU-bound; cap of 3 workers per STATE.md
    broker_transport_options={"visibility_timeout": 1800},         # 30 min > max video duration (Pitfall 2)
    task_acks_late=True,
)


@celery_app.task(bind=True, name="soundgrabber.process_job")
def process_job(self, url: str) -> dict[str, Any]:
    """Pipeline orchestration: check_duration -> download_audio -> analyze_audio.

    Emits custom Celery states between stages so GET /jobs/{id} can report progress.
    Maps all pipeline exceptions to sanitized JobFailure per D-05/D-06.
    WAV lifecycle: pipeline.download_audio produces /tmp/sg_*.wav;
    Phase 2 sweeper deletes it after settings.wav_ttl seconds (D-01).
    """
    try:
        if settings.cache_dir:
            cookies_file = Path(settings.cache_dir) / "cookies.txt"
            if cookies_file.exists():
                content = cookies_file.read_text(encoding="utf-8", errors="ignore")
                logger.warning(
                    "AUTH: process_job cache_dir=%s cookie_exists=true bytes=%s secure_3psid_lines=%s",
                    settings.cache_dir,
                    cookies_file.stat().st_size,
                    content.count("__Secure-3PSID"),
                )
            else:
                logger.warning(
                    "AUTH: process_job cache_dir=%s cookie_exists=false path=%s",
                    settings.cache_dir,
                    cookies_file,
                )
        else:
            logger.warning("AUTH: process_job cache_dir=missing")
        # Phase 10.1 gap closure (plan 06): log presença do bgutil sem expor URL completa
        logger.warning(
            "AUTH: process_job bgutil_base_url=%s",
            "set" if settings.bgutil_base_url else "empty",
        )

        # Stage 0: duration check — raises ValueError if > 900s (CORE-05)
        self.update_state(state="DOWNLOADING", meta={"stage": "checking_duration"})
        info = check_duration(url, settings.cache_dir)

        # Stage 1: download + convert (yt-dlp FFmpegExtractAudio postprocessor produces WAV)
        self.update_state(state="DOWNLOADING", meta={"stage": "downloading"})
        wav_path = download_audio(url, settings.cache_dir)

        # Stage 2: converting — discrete contract state (yt-dlp already produced the WAV,
        # but CONVERTING is part of the 5-state API contract from ROADMAP)
        self.update_state(state="CONVERTING", meta={"stage": "converting"})

        # Stage 3: analyze — BPM, key, Camelot
        self.update_state(state="ANALYZING", meta={"stage": "analyzing"})
        result = analyze_audio(wav_path)

        return {
            "status": "done",
            "bpm": result["bpm"],
            "bpm_half": result["bpm_half"],
            "bpm_double": result["bpm_double"],
            "key": result["key"],
            "camelot": result["camelot"],
            "duration_sec": result["duration_sec"],
            "wav_path": result["wav_path"],        # internal: Plan 03 uses for FileResponse; not returned to API consumer
            "tuning_hz": result.get("tuning_hz"),
            "video_title": info.get("title", ""),
            "download_url": f"/files/{self.request.id}",
        }

    except ValueError as e:
        # check_duration: "Video too long: {N}s exceeds the 15-minute limit"
        # analyze_audio/validate_wav: "Audio invalid or corrupt: ..."
        logger.info("Job %s validation_error: %s", self.request.id, e)
        msg_lower = str(e).lower()
        if "too long" in msg_lower or "15-minute" in msg_lower or "15 minutes" in msg_lower:
            sanitized = "Video is too long (max 15 minutes)."
        else:
            sanitized = "Could not validate audio file."
        raise JobFailure(error=sanitized, error_type="validation_error") from e

    except FileNotFoundError as e:
        # download_audio: WAV not produced after successful yt-dlp run
        logger.info("Job %s download_error (file missing): %s", self.request.id, e)
        raise JobFailure(
            error="Download failed: audio file not produced.",
            error_type="download_error",
        ) from e

    except RuntimeError as e:
        # check_duration/download_audio wrap yt_dlp.utils.DownloadError as RuntimeError
        logger.info("Job %s download_error: %s", self.request.id, e)
        raise JobFailure(
            error="Download failed. The video may be unavailable or blocked.",
            error_type="download_error",
        ) from e

    except Exception as e:  # noqa: BLE001 — catch-all: sanitize, never expose internals
        logger.exception("Job %s internal_error", self.request.id)
        raise JobFailure(
            error="An internal error occurred. Please try again.",
            error_type="internal_error",
        ) from e


@celery_app.task(bind=True, name="soundgrabber.analyze_local_file")
def analyze_local_file(self, uploaded_path_str: str) -> dict[str, Any]:
    """Analyze an uploaded local audio file with Essentia (BPM, key, Camelot).

    Converts to WAV if needed, then calls analyze_audio(). Cleans up all temp
    files in the finally block — no WAV is kept after analysis (no download).
    """
    uploaded_path = Path(uploaded_path_str)
    wav_path: Path | None = None
    try:
        self.update_state(state="ANALYZING", meta={"stage": "analyzing"})

        if uploaded_path.suffix.lower() != ".wav":
            wav_path = convert_uploaded_to_wav(uploaded_path)
        else:
            wav_path = uploaded_path

        result = analyze_audio(wav_path)

        return {
            "status": "done",
            "bpm": result["bpm"],
            "bpm_half": result["bpm_half"],
            "bpm_double": result["bpm_double"],
            "key": result["key"],
            "camelot": result["camelot"],
            "duration_sec": result["duration_sec"],
        }

    except ValueError as e:
        logger.info("analyze_local_file %s validation_error: %s", self.request.id, e)
        raise JobFailure(
            error="Não foi possível analisar o arquivo. Verifique se é um arquivo de áudio válido.",
            error_type="validation_error",
        ) from e

    except Exception as e:  # noqa: BLE001
        logger.exception("analyze_local_file %s internal_error", self.request.id)
        raise JobFailure(
            error="An internal error occurred. Please try again.",
            error_type="internal_error",
        ) from e

    finally:
        if wav_path is not None and wav_path != uploaded_path:
            wav_path.unlink(missing_ok=True)
        uploaded_path.unlink(missing_ok=True)
