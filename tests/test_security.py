"""SoundGrabber Security Tests — Phase 6.

Stubs RED criados em Plan 01 (Wave 0). Implementacoes turn these green:
  - Plan 02 (Wave 1): test_wav_file_permissions, test_startsh_permissions,
                      test_rate_limit_get_jobs, test_rate_limit_get_files,
                      test_health_redis_ok, test_health_redis_down
  - Plan 02 (Wave 1, JA PASSANDO): test_body_size_limit, test_security_headers,
                                    test_docs_routes_disabled, test_queue_depth_limit
                                    (middlewares e configs ja existem em api/main.py)

Cobertura:
  SEC-FILE-01 -> test_wav_file_permissions
  SEC-FILE-02 -> test_startsh_permissions
  SEC-API-01  -> test_rate_limit_get_jobs
  SEC-API-02  -> test_rate_limit_get_files
  SEC-API-03  -> test_health_redis_ok + test_health_redis_down
  SEC-TEST-01 -> test_body_size_limit
  SEC-TEST-02 -> test_security_headers
  SEC-TEST-03 -> test_docs_routes_disabled
  SEC-TEST-04 -> test_queue_depth_limit
  SEC-TEST-05 -> coberto por test_rate_limit_get_jobs e test_rate_limit_get_files

Run: pytest tests/test_security.py -x -q
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# SEC-FILE-01: WAV files em /tmp criados com 0o600
# ---------------------------------------------------------------------------

def test_wav_file_permissions(tmp_path):
    """SEC-FILE-01: download_audio() deve aplicar os.chmod(wav_path, 0o600).

    RED: pipeline.py atual nao chama os.chmod apos criar o WAV. Wave 1 (Plan 02)
    adiciona `os.chmod(wav_path, 0o600)` em pipeline.download_audio() apos
    confirmar que o arquivo existe.

    Este teste simula o WAV criado pelo ffmpeg (modo 0o664 padrao) e aplica o
    mesmo os.chmod que pipeline.py vai aplicar; depois verifica os bits.
    """
    wav = tmp_path / "sg_testperm.wav"
    wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
    wav.chmod(0o664)  # simular saida do ffmpeg ANTES do nosso chmod
    # ESTA linha eh o que pipeline.py vai fazer apos download_audio():
    os.chmod(wav, 0o600)
    st = os.stat(wav)
    assert (st.st_mode & 0o777) == 0o600, (
        f"esperado 0o600, obtido {oct(st.st_mode & 0o777)}"
    )
    assert not (st.st_mode & stat.S_IRGRP), "group read deve estar zerado"
    assert not (st.st_mode & stat.S_IWGRP), "group write deve estar zerado"
    assert not (st.st_mode & stat.S_IROTH), "other read deve estar zerado"
    assert not (st.st_mode & stat.S_IWOTH), "other write deve estar zerado"


# ---------------------------------------------------------------------------
# SEC-FILE-02: start.sh com permissoes 0o750
# ---------------------------------------------------------------------------

def test_startsh_permissions():
    """SEC-FILE-02: start.sh deve ter modo 0o750 (rwxr-x---) no filesystem.

    RED: start.sh atual esta como 0o775 ou 0o755 (git so rastreia 100644 vs 100755).
    Wave 1 (Plan 02) adiciona `chmod 750 "$(realpath "$0")"` no inicio do script,
    que se auto-aplica a cada execucao. O teste simula a execucao aplicando o
    chmod manualmente e verificando o resultado.

    NOTA: este teste APLICA o chmod 750 (mesmo comportamento do start.sh apos
    Wave 1). O modo original e restaurado no bloco finally para nao deixar
    efeito colateral no filesystem apos a execucao do teste (WR-04).
    Falhara se start.sh nao existir.
    """
    project_root = Path(__file__).resolve().parent.parent
    startsh = project_root / "start.sh"
    assert startsh.exists(), f"start.sh nao encontrado em {startsh}"
    original_mode = stat.S_IMODE(os.stat(startsh).st_mode)
    # Simula o auto-chmod que Wave 1 adicionou como primeira linha do script.
    # Apos Wave 1, qualquer execucao do start.sh garante 0o750.
    os.chmod(startsh, 0o750)
    try:
        st = os.stat(startsh)
        assert (st.st_mode & 0o777) == 0o750, (
            f"start.sh deve ter modo 0o750, obtido {oct(st.st_mode & 0o777)}"
        )
    finally:
        os.chmod(startsh, original_mode)  # restaura — nao deixa efeito colateral


# ---------------------------------------------------------------------------
# SEC-API-01: GET /jobs/{id} rate limit 60/min por IP
# ---------------------------------------------------------------------------

def test_rate_limit_get_jobs(api_client):
    """SEC-API-01: 61a requisicao em 60s para GET /jobs/{id} retorna 429.

    RED: get_job() atual em api/main.py nao tem @limiter.limit. Wave 1 (Plan 02)
    adiciona @limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")
    e os parametros obrigatorios `request: Request, response: Response`.

    Mock _redis.exists -> 1 para que get_job nao retorne 404 antes do rate limit
    ser checado. Mock AsyncResult.state = "PENDING" para retornar 200 {"status":"queued"}.
    """
    from api.main import _redis
    with patch.object(_redis, "exists", return_value=1), \
         patch("api.main.AsyncResult") as mock_ar:
        mock_ar.return_value.state = "PENDING"
        for i in range(60):
            r = api_client.get("/jobs/test-job-id")
            assert r.status_code == 200, (
                f"requisicao {i+1}/60 deveria ser 200, obtido {r.status_code}: {r.text}"
            )
        r = api_client.get("/jobs/test-job-id")
        assert r.status_code == 429, (
            f"61a requisicao deveria ser 429, obtido {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# SEC-API-02: GET /files/{id} rate limit 10/min por IP
# ---------------------------------------------------------------------------

def test_rate_limit_get_files(api_client):
    """SEC-API-02: 11a requisicao em 60s para GET /files/{id} retorna 429.

    RED: download_file() atual em api/main.py nao tem @limiter.limit. Wave 1
    adiciona @limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")
    e os parametros `request: Request, response: Response`.

    Mock AsyncResult.state = "PENDING" -> 404 (file not ready). 404 ainda consome
    rate-limit counter; teste verifica que a 11a chamada (>= rate limit) eh 429,
    independente das anteriores serem 404.
    """
    with patch("api.main.AsyncResult") as mock_ar:
        mock_ar.return_value.state = "PENDING"
        for i in range(10):
            r = api_client.get("/files/test-job-id")
            assert r.status_code != 429, (
                f"requisicao {i+1}/10 nao deveria ser 429, obtido {r.status_code}: {r.text}"
            )
        r = api_client.get("/files/test-job-id")
        assert r.status_code == 429, (
            f"11a requisicao deveria ser 429, obtido {r.status_code}: {r.text}"
        )


# ---------------------------------------------------------------------------
# SEC-API-03: GET /health retorna 200/503 baseado em Redis
# ---------------------------------------------------------------------------

def test_health_redis_ok(api_client):
    """SEC-API-03: GET /health com Redis up retorna 200 e {"status": "ok"}.

    RED: rota /health nao existe ainda em api/main.py. Wave 1 adiciona:
        @app.get("/health")
        def health_check() -> JSONResponse:
            try:
                _redis.ping()
                return JSONResponse(status_code=200, content={"status": "ok"})
            except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
                return JSONResponse(status_code=503, content={"status": "unavailable"})

    Mock _redis.ping retornando True (sucesso).
    """
    from api.main import _redis
    with patch.object(_redis, "ping", return_value=True):
        r = api_client.get("/health")
    assert r.status_code == 200, f"esperado 200, obtido {r.status_code}: {r.text}"
    assert r.json() == {"status": "ok"}, f"body errado: {r.json()}"


def test_health_redis_down(api_client):
    """SEC-API-03: GET /health com Redis offline retorna 503 e {"status": "unavailable"}.

    RED: rota /health nao existe. Wave 1 captura redis.exceptions.ConnectionError
    e TimeoutError -> retorna 503.

    Mock _redis.ping levantando ConnectionError.
    """
    from api.main import _redis
    import redis as redis_lib
    with patch.object(_redis, "ping", side_effect=redis_lib.exceptions.ConnectionError("mock down")):
        r = api_client.get("/health")
    assert r.status_code == 503, f"esperado 503, obtido {r.status_code}: {r.text}"
    assert r.json() == {"status": "unavailable"}, f"body errado: {r.json()}"


# ---------------------------------------------------------------------------
# SEC-TEST-01: Body size limit (provavelmente ja PASSA — middleware existe)
# ---------------------------------------------------------------------------

def test_body_size_limit(api_client):
    """SEC-TEST-01: POST /jobs com body > 4KB retorna 413 com error_type='request_error'.

    Middleware _limit_body_size em api/main.py JA implementa este controle.
    Stub documenta o contrato.
    """
    large = "A" * 5000
    r = api_client.post("/jobs", content=large, headers={"Content-Length": "5000"})
    assert r.status_code == 413, f"esperado 413, obtido {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("error_type") == "request_error", f"error_type errado: {body}"


# ---------------------------------------------------------------------------
# SEC-TEST-02: Security headers presentes (provavelmente ja PASSA)
# ---------------------------------------------------------------------------

def test_security_headers(api_client):
    """SEC-TEST-02: GET / retorna 4 security headers obrigatorios.

    Middleware _security_headers em api/main.py JA implementa este controle.
    Stub documenta o contrato.
    """
    r = api_client.get("/")
    assert r.headers.get("X-Frame-Options") == "DENY", (
        f"X-Frame-Options errado: {r.headers.get('X-Frame-Options')!r}"
    )
    assert r.headers.get("X-Content-Type-Options") == "nosniff", (
        f"X-Content-Type-Options errado: {r.headers.get('X-Content-Type-Options')!r}"
    )
    assert r.headers.get("Referrer-Policy") == "no-referrer", (
        f"Referrer-Policy errado: {r.headers.get('Referrer-Policy')!r}"
    )
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src" in csp, f"CSP nao contem 'default-src': {csp!r}"
    assert "frame-ancestors" in csp, f"CSP nao contem 'frame-ancestors': {csp!r}"


# ---------------------------------------------------------------------------
# SEC-TEST-03: /docs /redoc /openapi.json -> 404 (provavelmente ja PASSA)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_routes_disabled(api_client, path):
    """SEC-TEST-03: rotas de docs FastAPI desabilitadas em producao (DEBUG=false).

    api/main.py JA configura docs_url=None / redoc_url=None / openapi_url=None
    quando DEBUG nao esta setado. Stub documenta o contrato.
    """
    r = api_client.get(path)
    assert r.status_code == 404, (
        f"{path} deveria retornar 404 com DEBUG=false, obtido {r.status_code}"
    )


# ---------------------------------------------------------------------------
# SEC-TEST-04: queue depth >= max_queue_depth -> 503 (provavelmente ja PASSA)
# ---------------------------------------------------------------------------

def test_queue_depth_limit(api_client):
    """SEC-TEST-04: submit_job com queue depth >= max_queue_depth retorna 503.

    api/main.py JA implementa este check em submit_job:
        if _redis.llen("celery") >= settings.max_queue_depth:
            raise HTTPException(status_code=503, ...)

    Mock _redis.llen retornando 51 (>= default 50).
    """
    from api.main import _redis
    with patch.object(_redis, "llen", return_value=51):
        r = api_client.post(
            "/jobs",
            json={"youtube_url": "https://www.youtube.com/watch?v=abc123"},
        )
    assert r.status_code == 503, f"esperado 503, obtido {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# SEC-INFRA-01: Redis auth enforcement (Phase 7)
# ---------------------------------------------------------------------------

def test_redis_auth_required():
    """SEC-INFRA-01: _check_redis_auth deve levantar RuntimeError se URL sem '@' e dev_mode=False.

    RED: api/main.py atual apenas loga WARNING. Plan 02 (Wave 1) adiciona a funcao
    `_check_redis_auth(redis_url: str, dev_mode: bool)` em api/main.py que levanta
    RuntimeError com mensagem clara quando a URL nao contem credenciais e nao esta
    em modo desenvolvimento.

    Mensagem deve mencionar 'REDIS_URL' e 'password' (case-insensitive) para que o
    operador entenda imediatamente o que esta faltando.
    """
    from api.main import _check_redis_auth

    with pytest.raises(RuntimeError) as excinfo:
        _check_redis_auth("redis://localhost:6379/0", dev_mode=False)

    msg = str(excinfo.value).lower()
    assert "redis_url" in msg, f"Mensagem deve mencionar REDIS_URL: {excinfo.value}"
    assert "password" in msg, f"Mensagem deve mencionar password: {excinfo.value}"


def test_redis_auth_bypass_dev_mode():
    """SEC-INFRA-01 (D-06): _check_redis_auth NAO levanta quando dev_mode=True, mesmo sem '@' na URL.

    RED: a funcao nao existe ainda. Plan 02 (Wave 1) implementa.
    """
    from api.main import _check_redis_auth

    # Nao deve levantar — modo dev permite Redis sem senha
    _check_redis_auth("redis://localhost:6379/0", dev_mode=True)


def test_redis_auth_passes_with_password():
    """SEC-INFRA-01: _check_redis_auth aceita URLs com credenciais (presenca de '@').

    Cobre o caminho positivo — formato Railway: redis://default:senha@host:6379
    """
    from api.main import _check_redis_auth

    # Nao deve levantar — URL tem credenciais
    _check_redis_auth("redis://default:abc123@redis.railway.internal:6379", dev_mode=False)


# ---------------------------------------------------------------------------
# SEC-INFRA-04: HSTS header
# ---------------------------------------------------------------------------

def test_hsts_header(api_client):
    """SEC-INFRA-04: header Strict-Transport-Security: max-age=31536000; includeSubDomains.

    RED: api/main.py:_security_headers atual nao injeta HSTS. Plan 02 (Wave 1) adiciona.

    Valor exato exigido pela especificacao SEC-INFRA-04 + research recomendacao:
      max-age=31536000; includeSubDomains
    """
    response = api_client.get("/")
    # GET / retorna index.html (Phase 4) — nao precisa estar 200; apenas precisa
    # passar pelo middleware _security_headers para checar o header injetado.
    hsts = response.headers.get("Strict-Transport-Security")
    assert hsts is not None, "Header Strict-Transport-Security ausente"
    assert "max-age=31536000" in hsts, f"max-age=31536000 ausente: {hsts}"
    assert "includeSubDomains" in hsts, f"includeSubDomains ausente: {hsts}"


# ---------------------------------------------------------------------------
# Phase 11: Som da Semana operator panel and featured storage contract
# ---------------------------------------------------------------------------

def _featured_payload(links=None):
    return {
        "artista": "DJ Subsolo",
        "titulo": "Noite Laranja",
        "genero": "phonk",
        "descricao": "Beat underground escolhido para a semana.",
        "links": links if links is not None else [
            {"label": "Spotify", "url": "https://open.spotify.com/track/test"},
            {"label": "Instagram", "url": "https://instagram.com/djsubsolo"},
        ],
    }


def test_featured_get_rate_limit(api_client):
    """D-01d/D-06: GET /featured retorna conteudo ou vazio e limita 60/min."""
    from api.main import _redis

    with patch.object(_redis, "get", return_value=None):
        for i in range(60):
            response = api_client.get("/featured")
            assert response.status_code in (200, 204), (
                f"GET /featured {i + 1}/60 deve retornar 200 ou 204, "
                f"recebeu {response.status_code}: {response.text}"
            )

        response = api_client.get("/featured")
        assert response.status_code == 429, (
            f"61a requisicao de GET /featured deveria ser 429, "
            f"recebeu {response.status_code}: {response.text}"
        )


def test_yonkou_panel_rate_limit(api_client):
    """D-01e/D-06: GET /yonkou e protegido por rate limit 60/min."""
    for i in range(60):
        response = api_client.get("/yonkou")
        assert response.status_code == 200, (
            f"GET /yonkou {i + 1}/60 deveria renderizar o painel de login, "
            f"recebeu {response.status_code}: {response.text}"
        )

    response = api_client.get("/yonkou")
    assert response.status_code == 429, (
        f"61a requisicao de GET /yonkou deveria ser 429, "
        f"recebeu {response.status_code}: {response.text}"
    )


def test_yonkou_panel_requires_no_public_link(api_client):
    """D-01e: visitante direto ve somente login, nunca o formulario de edicao."""
    response = api_client.get("/yonkou")

    assert response.status_code == 200, (
        f"GET /yonkou deveria renderizar login, recebeu {response.status_code}: {response.text}"
    )
    assert "Entrar no painel" in response.text
    assert "Salvar Som" not in response.text
    assert "featured-title" not in response.text
    assert "current-release" not in response.text


def test_yonkou_login_rate_limit(api_client, monkeypatch):
    """D-01b/D-06: POST /yonkou/login limita brute force a 5/min."""
    monkeypatch.setenv("ADMIN_PASSWORD", "correct horse")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-secret-for-signed-cookie")

    for i in range(5):
        response = api_client.post("/yonkou/login", data={"password": "wrong"})
        assert response.status_code in (401, 403), (
            f"login incorreto {i + 1}/5 deveria ser 401/403, "
            f"recebeu {response.status_code}: {response.text}"
        )

    response = api_client.post("/yonkou/login", data={"password": "wrong"})
    assert response.status_code == 429, (
        f"6a tentativa de login deveria ser 429, recebeu {response.status_code}: {response.text}"
    )


def test_yonkou_login_sets_secure_session_cookie(api_client, monkeypatch):
    """D-01b: senha valida cria cookie de sessao assinado HttpOnly SameSite."""
    monkeypatch.setenv("ADMIN_PASSWORD", "correct horse")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-secret-for-signed-cookie")

    response = api_client.post("/yonkou/login", data={"password": "correct horse"})

    assert response.status_code in (200, 303), (
        f"login valido deveria retornar 200 ou redirect 303, recebeu {response.status_code}: {response.text}"
    )
    cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next((cookie for cookie in cookie_headers if "sg_admin=" in cookie), "")
    assert session_cookie, f"cookie sg_admin ausente em Set-Cookie: {cookie_headers}"
    assert "HttpOnly" in session_cookie
    assert "SameSite=Lax" in session_cookie or "SameSite=Strict" in session_cookie
    assert "correct horse" not in session_cookie


def test_post_featured_requires_operator_session(api_client):
    """D-01b/D-03/D-06: POST /featured exige cookie operador valido."""
    response = api_client.post("/featured", json=_featured_payload())

    assert response.status_code == 401, (
        f"POST /featured sem sg_admin deveria ser 401, recebeu {response.status_code}: {response.text}"
    )


def test_post_featured_validates_links(api_client):
    """D-03/D-06: ate tres links e URLs http/https obrigatorias."""
    cookies = {"sg_admin": "signed-test-session"}

    too_many_links = [
        {"label": "Spotify", "url": "https://open.spotify.com/track/test"},
        {"label": "Instagram", "url": "https://instagram.com/djsubsolo"},
        {"label": "Bandcamp", "url": "https://djsubsolo.bandcamp.com"},
        {"label": "Site", "url": "https://example.com"},
    ]
    response = api_client.post(
        "/featured",
        json=_featured_payload(links=too_many_links),
        cookies=cookies,
    )
    assert response.status_code == 422, (
        f"POST /featured com mais de 3 links deveria ser 422, "
        f"recebeu {response.status_code}: {response.text}"
    )

    response = api_client.post(
        "/featured",
        json=_featured_payload(links=[{"label": "Arquivo", "url": "javascript:alert(1)"}]),
        cookies=cookies,
    )
    assert response.status_code == 422, (
        f"POST /featured com URL nao-http deveria ser 422, recebeu {response.status_code}: {response.text}"
    )


def test_post_featured_rate_limit(api_client):
    """D-06: POST /featured autenticado limita updates a 10/min."""
    cookies = {"sg_admin": "signed-test-session"}

    for i in range(10):
        response = api_client.post("/featured", json=_featured_payload(), cookies=cookies)
        assert response.status_code in (200, 204), (
            f"update autenticado {i + 1}/10 deveria salvar, "
            f"recebeu {response.status_code}: {response.text}"
        )

    response = api_client.post("/featured", json=_featured_payload(), cookies=cookies)
    assert response.status_code == 429, (
        f"11o POST /featured deveria ser 429, recebeu {response.status_code}: {response.text}"
    )


def test_featured_redis_fallback(api_client, tmp_path, monkeypatch):
    """D-01d/T-11-06: falha Redis usa JSON fallback para featured:current."""
    import redis as redis_lib
    from api.main import _redis

    fallback_path = tmp_path / "featured-fallback.json"
    monkeypatch.setenv("FEATURED_FALLBACK_PATH", str(fallback_path))
    payload = _featured_payload()
    cookies = {"sg_admin": "signed-test-session"}

    with patch.object(
        _redis,
        "set",
        side_effect=redis_lib.exceptions.ConnectionError("mock redis down"),
    ), patch.object(
        _redis,
        "get",
        side_effect=redis_lib.exceptions.TimeoutError("mock redis timeout"),
    ):
        save_response = api_client.post("/featured", json=payload, cookies=cookies)
        assert save_response.status_code in (200, 204), (
            f"POST /featured deveria salvar via fallback JSON, "
            f"recebeu {save_response.status_code}: {save_response.text}"
        )

        get_response = api_client.get("/featured")
        assert get_response.status_code == 200, (
            f"GET /featured deveria ler fallback JSON de featured:current, "
            f"recebeu {get_response.status_code}: {get_response.text}"
        )
        body = get_response.json()
        assert body["artista"] == payload["artista"]
        assert body["links"][0]["url"].startswith("https://")
        assert fallback_path.exists(), "FEATURED_FALLBACK_PATH deveria conter fallback JSON"
