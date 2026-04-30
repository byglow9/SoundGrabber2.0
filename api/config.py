"""Settings via environment variables (12-factor). D-04 — single requirements.txt; D-07 — no Docker."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    cookies_path: str = os.environ.get("YTDLP_COOKIES_FILE", "")
    po_token: str = os.environ.get("YTDLP_PO_TOKEN", "")
    wav_ttl: int = int(os.environ.get("WAV_TTL_SECONDS", "900"))


settings = Settings()
