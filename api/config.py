"""Settings via environment variables (12-factor). D-04 — single requirements.txt; D-07 — no Docker."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _safe_int(env_key: str, default: int) -> int:
    raw = os.environ.get(env_key, str(default))
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"Invalid value for {env_key}={raw!r} — expected an integer. "
            f"Check your .env file."
        )


# WR-02: default_factory lê os.environ no momento da instanciação (Settings()),
# não no momento da definição da classe. Isso garante que variáveis de ambiente
# definidas antes de Settings() — inclusive em conftest.py antes de importar api.* —
# sejam lidas corretamente, sem dependência frágil de ordem de importação.
@dataclass(frozen=True)
class Settings:
    redis_url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    cookies_path: str = field(default_factory=lambda: os.environ.get("YTDLP_COOKIES_FILE", ""))
    po_token: str = field(default_factory=lambda: os.environ.get("YTDLP_PO_TOKEN", ""))
    wav_ttl: int = field(default_factory=lambda: _safe_int("WAV_TTL_SECONDS", 900))
    rate_limit_per_minute: int = field(default_factory=lambda: _safe_int("RATE_LIMIT_PER_MINUTE", 3))
    max_queue_depth: int = field(default_factory=lambda: _safe_int("MAX_QUEUE_DEPTH", 50))
    # SEC-API-01: rate limit para polling de status (GET /jobs/{id}) — 60/min por IP
    job_poll_rate_limit_per_minute: int = field(default_factory=lambda: _safe_int("JOB_POLL_RATE_LIMIT_PER_MINUTE", 60))
    # SEC-API-02: rate limit para download de WAV (GET /files/{id}) — 10/min por IP
    file_download_rate_limit_per_minute: int = field(default_factory=lambda: _safe_int("FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE", 10))
    # SEC-INFRA-01 (D-06): bypass para desenvolvimento local. Em producao (Railway),
    # DEV_MODE NAO eh definido, e a validacao de Redis auth eh obrigatoria no lifespan.
    # O default "false" (string) garante que esquecer de definir em producao = falha segura.
    dev_mode: bool = field(default_factory=lambda: os.environ.get("DEV_MODE", "false").lower() == "true")


settings = Settings()
