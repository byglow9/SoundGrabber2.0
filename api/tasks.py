"""Celery app + process_job task. Plan 02 fills in the pipeline calls."""
from __future__ import annotations

from celery import Celery

from api.config import settings

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
def process_job(self, url: str) -> dict:
    """STUB — Plan 02 (Wave 2) replaces this body with real pipeline calls."""
    return {"status": "stub", "url": url}
