"""Settings via environment variables (12-factor). D-04 — single requirements.txt; D-07 — no Docker."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# WR-02: default_factory lê os.environ no momento da instanciação (Settings()),
# não no momento da definição da classe. Isso garante que variáveis de ambiente
# definidas antes de Settings() — inclusive em conftest.py antes de importar api.* —
# sejam lidas corretamente, sem dependência frágil de ordem de importação.
@dataclass(frozen=True)
class Settings:
    redis_url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    cookies_path: str = field(default_factory=lambda: os.environ.get("YTDLP_COOKIES_FILE", ""))
    po_token: str = field(default_factory=lambda: os.environ.get("YTDLP_PO_TOKEN", ""))
    wav_ttl: int = field(default_factory=lambda: int(os.environ.get("WAV_TTL_SECONDS", "900")))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.environ.get("RATE_LIMIT_PER_MINUTE", "3")))


settings = Settings()
