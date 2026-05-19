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
    # Phase 10.1 D-02/D-06: Railway Volume path com cookies.txt para autenticação yt-dlp
    cache_dir: str = field(default_factory=lambda: os.environ.get("YTDLP_CACHE_DIR", ""))
    # Phase 10.1 gap closure (plan 06): PO Token provider URL para hybrid auth
    # (cookies do Volume + bgutil JS challenge — ambos passados a yt-dlp simultaneamente)
    bgutil_base_url: str = field(default_factory=lambda: os.environ.get("BGUTIL_BASE_URL", ""))
    admin_password: str = field(default_factory=lambda: os.environ.get("ADMIN_PASSWORD", ""))
    admin_session_secret: str = field(default_factory=lambda: os.environ.get("ADMIN_SESSION_SECRET", ""))
    featured_fallback_path: str = field(default_factory=lambda: os.environ.get("FEATURED_FALLBACK_PATH", ".data/featured-current.json"))
    featured_history_path: str = field(default_factory=lambda: os.environ.get("FEATURED_HISTORY_PATH", ".data/featured-history.json"))


settings = Settings()
