"""FastAPI app — POST /jobs, GET /jobs/{id}, GET /files/{id}."""
from __future__ import annotations

import json
import logging
import os as _os
import re
import threading
import time
from html import escape
from datetime import date
from hmac import compare_digest
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import redis as redis_lib
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel, field_validator

from api.config import settings
from api.tasks import celery_app, process_job, JobFailure

logger = logging.getLogger(__name__)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
JOB_ID_PATTERN = re.compile(r"^[a-zA-Z0-9-]{1,64}$")
FEATURED_KEY = "featured:current"
ADMIN_COOKIE_NAME = "sg_admin"
ADMIN_SESSION_MAX_AGE = 60 * 60 * 24 * 7

# Module-level Redis client — connection pool reused across requests.
_redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
# WR-03: JOB_REGISTRY_KEY (shared set) substituído por chaves individuais sg:job:{id}.
# Padrão de chave: sg:job:{job_id} — valor "1", TTL = wav_ttl segundos.

# Rate limiting — D-01/D-02/D-03 (Phase 3)
# Redis backend obrigatorio: in-memory falha com multiplos workers Uvicorn (issue #226)
# CR-01: usa request.client.host (IP real da conexão TCP) em vez de get_ipaddr, que lê
# X-Forwarded-For sem verificação — qualquer cliente poderia rotacionar esse header e
# burlar o limite. client.host é setado pelo ASGI layer a partir da conexão TCP e não
# pode ser forjado pelo cliente.
def _real_ip(request: Request) -> str:
    """Retorna o IP real do cliente via conexão TCP — não spoofável."""
    if request.client is None:
        # Fallback seguro: retorna string fixa para não quebrar o rate limiter.
        # Isso é raro (proxy mal configurado) mas não deve causar 500.
        return "unknown"
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
        parsed = urlparse(v.strip())
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https")
        if parsed.netloc not in YOUTUBE_HOSTS:
            raise ValueError(
                f"URL must be a YouTube link (got: {parsed.netloc or '(empty)'})"
            )

        # Normaliza para https://www.youtube.com/watch?v=ID — descarta list=, si=,
        # start_radio= e quaisquer outros parâmetros que causam rejeição no yt-dlp
        # quando noplaylist=True está ativo.
        if parsed.netloc == "youtu.be":
            # youtu.be/VIDEO_ID[?qualquer_coisa]
            video_id = parsed.path.lstrip("/").split("/")[0]
        else:
            # youtube.com/watch?v=VIDEO_ID[&list=...&outros]
            video_id = parse_qs(parsed.query).get("v", [None])[0]

        if not video_id or len(video_id) != 11:
            raise ValueError(
                "Não foi possível identificar o vídeo na URL. "
                "Use o link direto do vídeo (ex: youtube.com/watch?v=ID)."
            )

        return f"https://www.youtube.com/watch?v={video_id}"


class FeaturedArtist(BaseModel):
    nome: str
    url: str = ""

    @field_validator("nome")
    @classmethod
    def nome_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Artist name is required")
        if len(value) > 200:
            raise ValueError("Artist name must be 200 characters or less")
        return value

    @field_validator("url")
    @classmethod
    def url_optional_http(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Artist URL must use http or https")
        if len(value) > 500:
            raise ValueError("Artist URL must be 500 characters or less")
        return value


class FeaturedLink(BaseModel):
    label: str
    url: str

    @field_validator("label")
    @classmethod
    def label_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Link label is required")
        if len(value) > 40:
            raise ValueError("Link label must be 40 characters or less")
        return value

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Link URL must use http or https")
        if len(value) > 500:
            raise ValueError("Link URL must be 500 characters or less")
        return value


class FeaturedReleaseRequest(BaseModel):
    artistas: list[FeaturedArtist]
    titulo: str
    genero: str
    descricao: str
    links: list[FeaturedLink] = []

    @field_validator("titulo", "genero", "descricao")
    @classmethod
    def text_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Featured fields cannot be empty")
        if len(value) > 500:
            raise ValueError("Featured text fields must be 500 characters or less")
        return value

    @field_validator("artistas")
    @classmethod
    def artistas_required(cls, value: list) -> list:
        if not value:
            raise ValueError("At least one artist is required")
        if len(value) > 10:
            raise ValueError("Featured release supports at most 10 artists")
        return value

    @field_validator("links")
    @classmethod
    def max_four_links(cls, value: list[FeaturedLink]) -> list[FeaturedLink]:
        if len(value) > 4:
            raise ValueError("Featured release supports at most four links")
        return value


class AdminLoginRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def password_required(cls, value: str) -> str:
        if not value:
            raise ValueError("Password is required")
        return value


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


def _check_redis_auth(redis_url: str, dev_mode: bool) -> None:
    """SEC-INFRA-01: Falha cedo se Redis sem senha em producao (D-06, D-07).

    Em producao (Railway), o servico Railway Redis injeta REDIS_URL com formato
    `redis://default:<senha>@redis.railway.internal:6379` (ver D-08), entao o
    check `"@" in redis_url` confirma a presenca de credenciais.

    DEV_MODE=true bypassa a checagem para desenvolvimento local com Redis sem auth.
    DEV_MODE NAO eh definido em producao Railway (D-14).

    Args:
        redis_url: A URL completa do Redis (ex: redis://:senha@host:6379/0).
        dev_mode: True para bypassar a validacao (apenas em dev local).

    Raises:
        RuntimeError: quando dev_mode=False e a URL nao contem '@' (sem credenciais).
            Mensagem clara, sem stack trace, suficiente para o operador corrigir.
    """
    if dev_mode:
        return
    if "@" not in redis_url:
        raise RuntimeError(
            "REDIS_URL does not contain a password. "
            "Set a Redis URL with credentials: redis://:password@host:port/db. "
            "For local development only, set DEV_MODE=true."
        )


def _featured_fallback_path() -> Path:
    return Path(_os.environ.get("FEATURED_FALLBACK_PATH", settings.featured_fallback_path))


def _read_featured_fallback() -> dict | None:
    fallback_path = _featured_fallback_path()
    if not fallback_path.exists():
        return None
    try:
        data = json.loads(fallback_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("featured fallback read failed")
        return None
    return data if isinstance(data, dict) and data else None


def _write_featured_fallback(payload: dict) -> None:
    fallback_path = _featured_fallback_path()
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = fallback_path.with_suffix(f"{fallback_path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(fallback_path)


def _load_featured() -> dict | None:
    try:
        raw = _redis.get(FEATURED_KEY)
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        return _read_featured_fallback()

    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("featured redis payload is invalid JSON")
        return None
    return data if isinstance(data, dict) and data else None


def _save_featured(payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    try:
        _redis.set(FEATURED_KEY, raw)
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        _write_featured_fallback(payload)
        return
    _write_featured_fallback(payload)


def _admin_serializer() -> URLSafeTimedSerializer:
    secret = settings.admin_session_secret
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Operator authentication is not configured.",
        )
    return URLSafeTimedSerializer(secret_key=secret, salt="soundgrabber-admin")


def _sign_admin_session() -> str:
    return _admin_serializer().dumps({"admin": True})


def _require_admin(request: Request) -> None:
    cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Admin login required")
    try:
        payload = _admin_serializer().loads(cookie, max_age=ADMIN_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Admin login required") from None
    if not isinstance(payload, dict) or payload.get("admin") is not True:
        raise HTTPException(status_code=401, detail="Admin login required")


def _normalize_artistas(current: dict) -> list:
    if "artistas" in current and isinstance(current["artistas"], list):
        return [a for a in current["artistas"] if isinstance(a, dict)]
    old = str(current.get("artista", "")).strip()
    return [{"nome": old, "url": ""}] if old else []


def _featured_document(request_body: FeaturedReleaseRequest) -> dict:
    return {
        "artistas": [a.model_dump() for a in request_body.artistas],
        "titulo": request_body.titulo,
        "genero": request_body.genero,
        "descricao": request_body.descricao,
        "data_adicao": date.today().isoformat(),
        "links": [link.model_dump() for link in request_body.links],
    }


_KNOWN_LINK_LABELS = ["Youtube", "Soundcloud", "Spotify", "Instagram"]


def _link_label_html(link: dict, index: int) -> str:
    raw = str(link.get("label", ""))
    is_known = raw in _KNOWN_LINK_LABELS
    select_val = raw if is_known else ("Outros" if raw else "")
    custom_val = escape(raw) if not is_known else ""
    options = '<option value=""></option>'
    for cat in _KNOWN_LINK_LABELS + ["Outros"]:
        sel = " selected" if cat == select_val else ""
        options += f'<option value="{cat}"{sel}>{cat}</option>'
    hide = "" if select_val == "Outros" else ' style="display:none"'
    return (
        f'<select id="featured-link-label-{index}" class="yonkou-input yonkou-select">{options}</select>'
        f'<input id="featured-link-label-custom-{index}" value="{custom_val}"'
        f' class="yonkou-input yonkou-label-custom"{hide} placeholder="nome">'
    )


def _operator_panel_html(authenticated: bool, featured: dict | None = None) -> str:
    if not authenticated:
        return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Yonkou - SoundGrabber</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<link rel="stylesheet" href="/static/style.css">
</head>
<body class="yonkou-page yonkou-login-page">
<div id="yonkou-wrapper" class="yonkou-login-wrapper">
<table id="yonkou-panel" class="yonkou-login-panel" width="420" align="center" cellpadding="0" cellspacing="0">
<tr><td id="yonkou-card">
<form id="yonkou-login" action="/yonkou/login" method="post" class="yonkou-form yonkou-login-form">
<input id="password" name="password" type="password" autocomplete="current-password" class="yonkou-input">
<button type="submit" class="yonkou-primary">&#x25B6;</button>
</form>
<div id="yonkou-message"></div>
<script src="/static/yonkou.js"></script>
</td></tr>
</table>
</div>
</body>
</html>"""

    current = featured or {}
    links = current.get("links") if isinstance(current.get("links"), list) else []
    link_1 = links[0] if len(links) > 0 and isinstance(links[0], dict) else {}
    link_2 = links[1] if len(links) > 1 and isinstance(links[1], dict) else {}
    link_3 = links[2] if len(links) > 2 and isinstance(links[2], dict) else {}
    link_4 = links[3] if len(links) > 3 and isinstance(links[3], dict) else {}
    artistas_data = _normalize_artistas(current)
    artistas_display = escape(", ".join(a.get("nome", "") for a in artistas_data) or "-")
    current_title = escape(str(current.get("titulo", "")))
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Yonkou - SoundGrabber</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<link rel="stylesheet" href="/static/style.css">
</head>
<body class="yonkou-page">
<div id="yonkou-wrapper">
<table id="yonkou-panel" width="700" align="center" cellpadding="0" cellspacing="0">
<tr><td id="yonkou-header">
<div id="site-title">SoundGrabber</div>
<div id="site-tagline">painel operador / yonkou</div>
</td></tr>
<tr><td id="yonkou-card">
<div class="yonkou-kicker">SOM DA SEMANA</div>
<h1>Painel Yonkou</h1>
<div id="current-release">Atual: {artistas_display} - {current_title or "-"}</div>
<form id="featured-editor" class="yonkou-form">
<table id="yonkou-form-table" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td class="yonkou-label-cell" style="vertical-align:top;padding-top:10px">Artistas</td>
<td>
<div id="artistas-list"></div>
<button type="button" id="add-artista-btn" class="yonkou-secondary">+ artista</button>
</td>
</tr>
<tr>
<td class="yonkou-label-cell"><label for="featured-titulo">Titulo</label></td>
<td><input id="featured-titulo" name="titulo" value="{escape(str(current.get("titulo", "")))}" class="yonkou-input"></td>
</tr>
<tr>
<td class="yonkou-label-cell"><label for="featured-genero">Genero</label></td>
<td><input id="featured-genero" name="genero" value="{escape(str(current.get("genero", "")))}" class="yonkou-input"></td>
</tr>
<tr>
<td class="yonkou-label-cell"><label for="featured-descricao">Descricao</label></td>
<td><textarea id="featured-descricao" name="descricao" rows="4" class="yonkou-input yonkou-textarea">{escape(str(current.get("descricao", "")))}</textarea></td>
</tr>
</table>
<fieldset id="yonkou-links">
<legend>Links externos</legend>
<table id="yonkou-links-table" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td class="yonkou-links-cell yonkou-links-label">
<label for="featured-link-label-1">Label 1</label>
{_link_label_html(link_1, 1)}
</td>
<td class="yonkou-links-cell yonkou-links-url">
<label>URL 1 <input id="featured-link-url-1" value="{escape(str(link_1.get("url", "")))}" class="yonkou-input"></label>
</td>
</tr>
<tr>
<td class="yonkou-links-cell yonkou-links-label">
<label for="featured-link-label-2">Label 2</label>
{_link_label_html(link_2, 2)}
</td>
<td class="yonkou-links-cell yonkou-links-url">
<label>URL 2 <input id="featured-link-url-2" value="{escape(str(link_2.get("url", "")))}" class="yonkou-input"></label>
</td>
</tr>
<tr>
<td class="yonkou-links-cell yonkou-links-label">
<label for="featured-link-label-3">Label 3</label>
{_link_label_html(link_3, 3)}
</td>
<td class="yonkou-links-cell yonkou-links-url">
<label>URL 3 <input id="featured-link-url-3" value="{escape(str(link_3.get("url", "")))}" class="yonkou-input"></label>
</td>
</tr>
<tr>
<td class="yonkou-links-cell yonkou-links-label">
<label for="featured-link-label-4">Label 4</label>
{_link_label_html(link_4, 4)}
</td>
<td class="yonkou-links-cell yonkou-links-url">
<label>URL 4 <input id="featured-link-url-4" value="{escape(str(link_4.get("url", "")))}" class="yonkou-input"></label>
</td>
</tr>
</table>
</fieldset>
<button type="submit" class="yonkou-primary">Salvar Som</button>
</form>
<div id="yonkou-message"></div>
<script>var YONKOU_ARTISTAS = {json.dumps(artistas_data, ensure_ascii=False)};</script>
<script src="/static/yonkou.js"></script>
</td></tr>
</table>
</div>
</body>
</html>"""


def _check_oauth_cache(cache_dir: str) -> None:
    """AUTH: Valida cookies.txt no Railway Volume — substitui _check_cookies() (PIPE-05).

    Non-blocking — logs CRITICAL e retorna. Nao levanta excecao. Nao bloqueia startup.
    Mesmo padrao de PIPE-05: aviso visivel nos Railway logs antes do primeiro job.
    (Phase 10.1 D-08 — adaptacao de D-03 para cookies no Volume)

    Args:
        cache_dir: Path do Railway Volume (YTDLP_CACHE_DIR). Cookies em cache_dir/cookies.txt.
                   String vazia = Volume nao configurado.
    """
    if not cache_dir:
        logger.critical(
            "AUTH: YTDLP_CACHE_DIR nao configurado. Downloads podem falhar com bot detection. "
            "Monte um Railway Volume em /data/yt-dlp-cache e configure YTDLP_CACHE_DIR. "
            "Para popular o Volume: railway run -- cp /local/cookies.txt /data/yt-dlp-cache/cookies.txt"
        )
        return

    cookies_file = Path(cache_dir) / "cookies.txt"
    if not cookies_file.exists():
        logger.critical(
            "AUTH: cookies.txt nao encontrado em %s. "
            "Copie cookies validos do YouTube para o Railway Volume. "
            "Exports podem ser feitos via extensao 'Get cookies.txt LOCALLY' no browser.",
            cookies_file,
        )
        return

    try:
        content = cookies_file.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logger.critical("AUTH: Nao foi possivel ler %s: %s", cookies_file, e)
        return

    try:
        stat = cookies_file.stat()
        logger.info(
            "AUTH: cookies.txt encontrado path=%s bytes=%s mode=%s secure_3psid_lines=%s",
            cookies_file,
            stat.st_size,
            oct(stat.st_mode & 0o777),
            content.count("__Secure-3PSID"),
        )
    except OSError as e:
        logger.warning("AUTH: Nao foi possivel stat %s: %s", cookies_file, e)

    if "__Secure-3PSID" not in content:
        logger.critical(
            "AUTH: cookies.txt em %s nao contem '__Secure-3PSID'. "
            "Cookie pode estar expirado ou invalido. "
            "Re-exporte do browser apos login no YouTube.",
            cookies_file,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SEC-INFRA-01: Redis auth enforcement (D-06, D-07).
    # _check_redis_auth levanta RuntimeError se sem senha e nao em DEV_MODE — startup falha cedo.
    _check_redis_auth(settings.redis_url, settings.dev_mode)
    # AUTH: cookies validation no Railway Volume — non-blocking, log only (Phase 10.1 D-08).
    _check_oauth_cache(settings.cache_dir)
    sweeper = threading.Thread(
        target=_run_sweeper_loop,
        daemon=True,
        name="wav-sweeper",
    )
    sweeper.start()
    logger.info("wav-sweeper thread started (TTL=%ds)", settings.wav_ttl)
    yield


_debug = _os.getenv("DEBUG", "false").lower() == "true"
app = FastAPI(
    title="SoundGrabber API",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

app.state.limiter = limiter

_MAX_BODY_BYTES = 4 * 1024  # 4 KB — far exceeds any valid YouTube URL POST body


@app.middleware("http")
async def _limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > _MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request body too large.", "error_type": "request_error"},
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid Content-Length header.", "error_type": "request_error"},
            )
    return await call_next(request)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://www.googletagmanager.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://www.google-analytics.com https://www.googletagmanager.com; "
        "connect-src 'self' https://www.google-analytics.com https://analytics.google.com https://region1.google-analytics.com; "
        "frame-src https://www.youtube.com; "
        "frame-ancestors 'none';"
    )
    # SEC-INFRA-04: HSTS — Railway entrega TLS, mas nao adiciona o header. (D-09)
    # Browsers ignoram este header em conexoes HTTP (RFC 6797), entao eh seguro em local.
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


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
    # WR-01: guard para evitar AttributeError se view_rate_limit não estiver presente
    if hasattr(request.state, "view_rate_limit"):
        response = request.app.state.limiter._inject_headers(
            response, request.state.view_rate_limit
        )
    return response


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
# WR-01: SlowAPIMiddleware necessário para que request.state.view_rate_limit seja
# populado antes de _inject_headers ser chamado no handler de 429.
app.add_middleware(SlowAPIMiddleware)


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
    if _redis.llen("celery") >= settings.max_queue_depth:
        raise HTTPException(status_code=503, detail="Service busy. Please try again later.")
    task = process_job.delay(request_body.youtube_url)
    # WR-03: chave por job com TTL individual em vez de set compartilhado.
    # _redis.expire(JOB_REGISTRY_KEY, ...) resetava o TTL do set inteiro a cada
    # submit — jobs antigos podiam expirar prematuramente com alta carga, e jobs
    # em andamento ficavam sem registro se o set expirasse por inatividade.
    _redis.set(f"sg:job:{task.id}", "1", ex=settings.wav_ttl)
    return {"job_id": task.id}


@app.get("/jobs/{job_id}")
@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")
def get_job(job_id: str, request: Request, response: Response) -> dict:
    if not JOB_ID_PATTERN.match(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    # Pitfall 1 / D-02: PENDING is ambiguous between "in queue" and "never existed".
    # WR-03: verifica chave por job em vez de sismember no set compartilhado.
    if not _redis.exists(f"sg:job:{job_id}"):
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
            "tuning_hz": data.get("tuning_hz"),
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
@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")
def download_file(job_id: str, request: Request, response: Response):
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

    title = data.get("video_title") or ""
    bpm = data.get("bpm") or ""
    key = data.get("key") or ""
    slug = re.sub(r"[^\w\s-]", "", title).strip()
    slug = re.sub(r"[\s]+", "_", slug)[:60]
    key_slug = key.replace(" ", "_").replace("#", "s")
    filename = f"{slug}_{bpm}bpm_{key_slug}.wav" if slug else f"soundgrabber_{job_id[:8]}.wav"

    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        filename=filename,
    )


@app.get("/health")
@limiter.limit("60/minute")
def health_check(request: Request, response: Response) -> JSONResponse:
    """SEC-API-03: liveness probe — 200 se Redis OK, 503 se offline."""
    try:
        _redis.ping()
        return JSONResponse(status_code=200, content={"status": "ok"})
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})


@app.get("/featured")
@limiter.limit("60/minute")
def get_featured(request: Request, response: Response):
    featured = _load_featured()
    if not featured:
        return Response(status_code=204)
    return featured


@app.get("/yonkou")
@limiter.limit("60/minute")
def yonkou_panel(request: Request, response: Response) -> HTMLResponse:
    try:
        _require_admin(request)
    except HTTPException:
        return HTMLResponse(_operator_panel_html(authenticated=False))
    return HTMLResponse(_operator_panel_html(authenticated=True, featured=_load_featured()))


@app.post("/yonkou/login")
@limiter.limit("5/minute")
def yonkou_login(
    request: Request,
    request_body: AdminLoginRequest,
    response: Response,
) -> JSONResponse:
    if not settings.admin_password:
        raise HTTPException(
            status_code=503,
            detail="Operator authentication is not configured.",
        )
    if not compare_digest(request_body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Invalid operator credentials")

    token = _sign_admin_session()
    response = JSONResponse(status_code=200, content={"status": "ok"})
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        token,
        httponly=True,
        secure=not settings.dev_mode,
        samesite="lax",
        max_age=ADMIN_SESSION_MAX_AGE,
    )
    return response


@app.post("/featured")
@limiter.limit("10/minute")
def post_featured(
    request: Request,
    request_body: FeaturedReleaseRequest,
    response: Response,
) -> dict:
    _require_admin(request)
    payload = _featured_document(request_body)
    _save_featured(payload)
    return payload


# ── Static files ──────────────────────────────────────────────────────────────
# Phase 4: serve index.html and app.js.
# CRITICAL: define AFTER all API routes so GET /, GET /jobs/*, GET /files/*
# take precedence. StaticFiles mount at "/static" does not shadow /jobs or /files.
# VERIFIED: FastAPI 0.136.1 + Starlette 1.0.0 — routes defined before mount win.
STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/")
def serve_index():
    """Serve index.html — browser entry point for Phase 4 frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/sobre")
def serve_about():
    """Serve the public about, legal notice, and privacy page."""
    return FileResponse(str(STATIC_DIR / "about.html"))


# Mount after serve_index to avoid shadowing GET /.
# StaticFiles lança RuntimeError se STATIC_DIR não existir ao iniciar.
# static/ é criado no Plan 02; este Plan (04) deve ser executado depois.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
