# Phase 11: Som da Semana - Research

**Researched:** 2026-05-12 [VERIFIED: system date]
**Domain:** FastAPI authenticated operator endpoint, Redis-backed curated content, vanilla JS table-layout sidebar [VERIFIED: 11-CONTEXT.md, api/main.py, static/index.html]
**Confidence:** HIGH for repo patterns and route/security constraints; MEDIUM for optional session helper choice because the project has not locked a cookie implementation library [VERIFIED: CLAUDE.md, api/main.py] [ASSUMED]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### D-01 — Gestão do conteúdo
- **D-01a:** Mini painel `/yonkou` com formulário HTML visual — o operador preenche os campos e salva via submit.
- **D-01b:** Autenticação via senha simples: variável de ambiente `ADMIN_PASSWORD`. Ao fazer login, gera cookie de sessão assinado. Sem dependências extras de auth.
- **D-01c:** Controle de troca manual — o operador atualiza quando quiser, sem expiração automática por data.
- **D-01d:** Armazenamento em Redis (já disponível na stack) sob chave `featured:current`. Fallback para arquivo JSON se Redis estiver indisponível (graceful degradation).
- **D-01e:** Não haverá botão, link, menu ou affordance pública apontando para o painel. A rota canônica é `/yonkou`. Isso reduz descoberta casual, mas NÃO substitui autenticação, cookie assinado e rate limit.

### D-02 — Layout e posição no site
- **D-02a:** Sidebar à direita da tabela `#app` (640px). Implementada como coluna adicional na tabela HTML raiz — sem flexbox/grid, fiel à estética Y2K.
- **D-02b:** O sidebar só renderiza quando há conteúdo cadastrado. Se `GET /featured` retornar vazio (204 ou `{}`), o JS não injeta a coluna e o layout volta ao `#app` centralizado.
- **D-02c:** Largura da sidebar: ~220px. Separação visual por borda `1px solid #ff8800` no lado esquerdo do card.

### D-03 — Campos do card
Campos cadastrados via `/yonkou` e exibidos no card da sidebar:
- **artista** — nome do artista/projeto
- **titulo** — título da obra/release
- **genero** — estilo musical em texto livre (ex: phonk, trap, boom bap)
- **descricao** — nota editorial do operador (voz curatorial, 1-3 frases)
- **data_adicao** — preenchida automaticamente pelo backend no momento do cadastro (ISO date → exibida como DD/MM/YYYY)
- **links** — até 3 pares `{label, url}` definidos pelo operador (ex: `["Spotify", "https://..."]`, `["Instagram", "https://..."]`). Labels ficam nos botões do card.

### D-04 — Comportamento dos links
- **D-04a:** Todos os links do card abrem em nova aba (`target="_blank" rel="noopener"`). Sem integração especial com o campo de download.
- **D-04b:** Não há detecção de plataforma (YouTube vs Spotify vs Instagram) — todos tratados igualmente.

### D-05 — Estética do card (Y2K / phpBB)
- Fundo `#000000`, texto `#ff8800`, borda `1px solid #ff8800` — mesma paleta do restante do site.
- Header do card: `:: SOM DA SEMANA ::` em fonte Sligoil uppercase.
- Linha separadora `----` entre o header e o conteúdo (estilo assinatura de fórum).
- Botões de link: estilo dos botões existentes — borda laranja, fundo preto, hover inverte.
- Data exibida em 11px laranja escuro (`#804400`), estilo metadata de fórum.
- Sem imagens, sem artwork, sem embeds — só texto e links.

### D-06 — Security Gate (obrigatório pelo CLAUDE.md)
Todo endpoint novo DEVE seguir o Security Gate:
- `GET /featured` — rate limit 60/min, `request: Request, response: Response` na assinatura.
- `POST /featured` (operador) — rate limit 10/min, Pydantic BaseModel para o body, autenticação via cookie de sessão.
- `POST /yonkou/login` — rate limit 5/min para mitigar brute force.
- Testes em `tests/test_security.py` para rate limit e validação do endpoint operador.

### the agent's Discretion
- Estrutura interna do armazenamento Redis (hash vs string JSON serializado).
- Token/assinatura do cookie de sessão (itsdangerous ou HMAC simples).
- Organização interna do painel operador-only (HTML separado ou inline em main.py).

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- **Histórico de releases anteriores** — exibir os últimos N "Sons da Semana" em uma página `/arquivo`. Pertence a uma fase futura após a fase 11 estar estável.
- **Votação / reação da comunidade** — usuários reagirem ao som curado. Exigiria persistência de estado por usuário, fora do escopo stateless atual.
- **Notificação por email/RSS quando troca** — integração de notificação para comunidade. Fase futura independente.
</user_constraints>

## Summary

Phase 11 should be planned as a narrow vertical slice: add settings for `ADMIN_PASSWORD` and a session signing secret, add authenticated operator-only routes at `/yonkou` before the static mount, persist exactly one current featured release at `featured:current`, and make the static homepage fetch `GET /featured` on load before injecting the right-side table column [VERIFIED: 11-CONTEXT.md, api/main.py, static/index.html]. The public homepage must not expose a button or link to `/yonkou`; this is discovery reduction only, not a security boundary [VERIFIED: updated 11-CONTEXT.md]. The backend already has the required shape for this work: FastAPI path operations, module-level Redis client, slowapi rate limiting with Redis storage, Pydantic validation, unified 422 and 429 handlers, and security headers [VERIFIED: api/main.py].

The recommended storage shape is a single JSON string in Redis rather than a hash because the card is fetched and replaced as one document, links are a nested list, and the phase has no partial update or query requirement [VERIFIED: 11-CONTEXT.md, Redis docs]. Use `json.dumps` / `json.loads` in Python and `_redis.set("featured:current", payload)` / `_redis.get("featured:current")`; if Redis raises connection or timeout errors, read/write a local JSON fallback file in the writable app directory, not `/tmp`, because `/tmp` is governed by audio-file cleanup conventions [VERIFIED: redis-py docs, CLAUDE.md] [ASSUMED].

**Primary recommendation:** Use existing FastAPI + slowapi + Pydantic patterns, store the featured release as JSON under `featured:current`, sign an HttpOnly SameSite cookie with `itsdangerous.URLSafeTimedSerializer`, and render all visitor-facing card fields with `textContent` plus validated anchor `href` attributes [VERIFIED: api/main.py, SlowAPI docs, Pydantic docs, ItsDangerous docs, Starlette docs].

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Operator login | API / Backend [VERIFIED: 11-CONTEXT.md] | Browser / Client [VERIFIED: 11-CONTEXT.md] | Password verification, session signing, and cookie issuance belong server-side; browser only submits the form [VERIFIED: FastAPI/Starlette cookie docs]. |
| Operator content update | API / Backend [VERIFIED: 11-CONTEXT.md] | Database / Storage [VERIFIED: 11-CONTEXT.md] | Backend validates schema and auth, then writes the canonical featured document to Redis/fallback JSON [VERIFIED: api/main.py, Redis docs]. |
| Public featured card read | API / Backend [VERIFIED: 11-CONTEXT.md] | Browser / Client [VERIFIED: static/app.js] | Backend returns empty/no-content or JSON; client decides whether to inject the sidebar [VERIFIED: 11-CONTEXT.md]. |
| Sidebar rendering | Browser / Client [VERIFIED: static/index.html, static/app.js] | CDN / Static [VERIFIED: api/main.py] | DOM insertion, `hidden` state, text formatting, and `target="_blank"` link creation are static frontend responsibilities [VERIFIED: static/app.js, MDN noopener docs]. |
| Persistent current release | Database / Storage [VERIFIED: 11-CONTEXT.md] | API / Backend [VERIFIED: api/main.py] | Redis owns fast persistence when available; backend owns fallback and schema compatibility [VERIFIED: Redis docs]. |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| D-01 | Mini `/yonkou`, password login, signed cookie, manual update, Redis plus JSON fallback [VERIFIED: 11-CONTEXT.md] | Use FastAPI routes, Starlette cookie flags, Redis string JSON, and itsdangerous timed signing [VERIFIED: FastAPI docs, Starlette docs, Redis docs, ItsDangerous docs]. |
| D-02 | Right sidebar as additional root table column, hidden when no content [VERIFIED: 11-CONTEXT.md] | Modify `static/index.html` table structure conservatively and make `app.js` inject/remove the column after `GET /featured` [VERIFIED: static/index.html, static/app.js]. |
| D-03 | Artist/title/genre/description/auto date/up to 3 links [VERIFIED: 11-CONTEXT.md] | Pydantic model validators should enforce string length, max 3 links, URL schemes, and label/url pairs [VERIFIED: Pydantic docs]. |
| D-04 | External links open in new tab with `rel="noopener"` [VERIFIED: 11-CONTEXT.md] | MDN documents `noopener` as preventing the opened page from accessing `window.opener` [CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/noopener]. |
| D-05 | phpBB/Y2K card styling, no images/embeds [VERIFIED: 11-CONTEXT.md] | Extend existing raw hex CSS and table markup; existing tests forbid flex/grid/CSS variables and modern visual effects [VERIFIED: static/style.css, tests/test_frontend.py]. |
| D-06 | Security gate on all new endpoints [VERIFIED: 11-CONTEXT.md, CLAUDE.md] | Add slowapi decorators, `request: Request`, `response: Response`, Pydantic body models, auth tests, and rate-limit tests in `tests/test_security.py` [VERIFIED: SlowAPI docs, CLAUDE.md]. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Use Python 3.11 + FastAPI, Celery + Redis, yt-dlp, FFmpeg, librosa, and vanilla HTML/CSS/JS with zero frontend frameworks [VERIFIED: CLAUDE.md].
- Preserve authentic Y2K structure: tables for layout, no flexbox, no grid, no CSS variables, bitmap/pixel fonts, raw hex colors, and no modern animation styling [VERIFIED: CLAUDE.md, tests/test_frontend.py].
- Every new endpoint must use `@limiter.limit("<N>/minute")`; default is 60/min for reads and 10/min for writes/downloads unless explicitly justified [VERIFIED: CLAUDE.md].
- POST/PUT endpoints must use Pydantic `BaseModel` with `field_validator`; raw `request.json()` is forbidden by project policy [VERIFIED: CLAUDE.md].
- Slowapi-protected sync routes must include `request: Request, response: Response` in the function signature [VERIFIED: CLAUDE.md, SlowAPI docs].
- `tests/test_security.py` must cover every new endpoint's rate limit and validation behavior, and `pytest tests/test_security.py` must pass before merge [VERIFIED: CLAUDE.md].
- `.planning/SECURITY-CHECKLIST.md` is the source of truth for active controls, but Phase 11 research scope is limited to this artifact [VERIFIED: CLAUDE.md, user output constraint].

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.136.1 pinned and current on PyPI [VERIFIED: requirements.txt, pip index] | HTTP routes for `/featured`, `/yonkou`, and `/yonkou/login` [VERIFIED: api/main.py] | Existing app already uses FastAPI route functions, response objects, and exception handlers [VERIFIED: api/main.py]. |
| slowapi | 0.1.9 pinned and current on PyPI [VERIFIED: requirements.txt, pip index] | Per-route rate limits with Redis-backed counters [VERIFIED: api/main.py, SlowAPI docs] | Security Gate requires slowapi on all new routes [VERIFIED: CLAUDE.md]. |
| redis-py | 6.4.0 pinned; latest PyPI is 7.4.0 [VERIFIED: requirements.txt, pip index] | `featured:current` persistence and graceful fallback trigger on connection errors [VERIFIED: 11-CONTEXT.md, Redis docs] | Existing app has module-level `_redis = redis.from_url(..., decode_responses=True)` [VERIFIED: api/main.py]. |
| Pydantic | Transitive via FastAPI; latest PyPI is 2.13.4 [VERIFIED: pip index, api/main.py] | Validate operator login and featured payload models [VERIFIED: Pydantic docs] | Existing `JobRequest` uses `BaseModel` and `field_validator`, matching CLAUDE.md [VERIFIED: api/main.py]. |
| itsdangerous | 2.2.0 current on PyPI, not currently in requirements [VERIFIED: pip index, requirements.txt] | Signed, optionally timed session cookie payloads [VERIFIED: ItsDangerous docs] | Avoids hand-rolled signing while staying lightweight [VERIFIED: ItsDangerous docs]. |
| Vanilla JS/HTML/CSS | No package version [VERIFIED: static/app.js, static/index.html] | Fetch `/featured`, inject table sidebar, and render text safely [VERIFIED: static/app.js] | Project forbids frontend frameworks and already uses DOM APIs directly [VERIFIED: CLAUDE.md, static/app.js]. |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| pytest | 9.0.3 pinned and current on PyPI [VERIFIED: requirements.txt, pip index] | Security/frontend regression tests [VERIFIED: pytest.ini, tests/test_security.py] | Add Phase 11 tests before implementation [VERIFIED: CLAUDE.md]. |
| FastAPI TestClient | Provided by FastAPI/Starlette [VERIFIED: tests/conftest.py] | Exercise routes with cookies and mocked Redis failures [VERIFIED: tests/conftest.py] | Use the existing `api_client` fixture [VERIFIED: tests/conftest.py]. |
| JSON fallback file | Standard library [VERIFIED: Python standard library assumption] | Keep one featured release available when Redis is down [VERIFIED: 11-CONTEXT.md] | Use only for `featured:current`, with atomic write via temp file then replace [ASSUMED]. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Redis JSON string | Redis hash | Hashes are fine for flat fields, but nested links become extra serialization anyway; full-document JSON matches whole-card replacement [VERIFIED: Redis docs, 11-CONTEXT.md]. |
| `itsdangerous` | HMAC using `hmac` and `secrets` | HMAC avoids dependency but recreates timestamp, serialization, exception handling, and key-rotation concerns [VERIFIED: Python stdlib docs assumption, ItsDangerous docs] [ASSUMED]. |
| JSON POST operator API | FastAPI form model | HTML forms need `python-multipart`, which is not in `requirements.txt`; JSON POST from the operator page avoids a new parser dependency while still giving a visual HTML form [VERIFIED: FastAPI form docs, requirements.txt]. |
| Separate operator HTML file | Inline `HTMLResponse` | Separate file is cleaner for markup, but inline is acceptable for a tiny operator-only page; planner should choose based on testability and minimal file churn [ASSUMED]. |

**Installation:**
```bash
# Keep existing pinned stack; add only if choosing itsdangerous.
pip install itsdangerous==2.2.0
```

**Version verification:**
```bash
python -m pip index versions fastapi       # 0.136.1 current [VERIFIED: pip index]
python -m pip index versions slowapi       # 0.1.9 current [VERIFIED: pip index]
python -m pip index versions redis         # 7.4.0 latest, project pins 6.4.0 [VERIFIED: pip index, requirements.txt]
python -m pip index versions pydantic      # 2.13.4 latest [VERIFIED: pip index]
python -m pip index versions itsdangerous  # 2.2.0 current [VERIFIED: pip index]
python -m pip index versions pytest        # 9.0.3 current [VERIFIED: pip index]
```

## Architecture Patterns

### System Architecture Diagram

```text
Visitor browser
  -> GET /
  -> static/index.html + static/app.js
  -> app.js fetches GET /featured
      -> API validates rate limit
      -> Redis GET featured:current
          -> found: return JSON release
          -> missing: return 204 or {}
          -> Redis down: read JSON fallback
      -> browser injects right-side table column only when payload exists

Operator browser
  -> GET /yonkou
      -> if no valid signed cookie: render login form
      -> if valid cookie: render edit form with current featured data
  -> POST /yonkou/login
      -> rate limit 5/min
      -> compare ADMIN_PASSWORD using constant-time comparison
      -> set signed HttpOnly SameSite cookie
  -> POST /featured
      -> rate limit 10/min
      -> verify signed cookie
      -> validate FeaturedRelease model
      -> add current ISO date
      -> write Redis featured:current
      -> write JSON fallback copy
```

### Recommended Project Structure

```text
api/
├── main.py        # add models, helpers, /featured and /yonkou routes before StaticFiles mount [VERIFIED: api/main.py]
├── config.py      # add ADMIN_PASSWORD, ADMIN_SESSION_SECRET, FEATURED_FALLBACK_PATH [VERIFIED: api/config.py]
static/
├── index.html     # add optional sidebar anchor/column structure or JS insertion target [VERIFIED: static/index.html]
├── app.js         # fetch/render featured card with textContent and safe anchors [VERIFIED: static/app.js]
└── style.css      # add sidebar/card styles using raw hex and table-era CSS [VERIFIED: static/style.css]
tests/
├── test_security.py   # operator auth, rate limit, validation, Redis fallback tests [VERIFIED: CLAUDE.md]
└── test_frontend.py   # sidebar IDs, no modern CSS, safe link attributes [VERIFIED: tests/test_frontend.py]
```

### Pattern 1: Slowapi Route Shape

**What:** Put the FastAPI route decorator above the slowapi decorator, and include `request` plus `response` parameters [VERIFIED: SlowAPI docs, api/main.py].
**When to use:** Every new Phase 11 endpoint [VERIFIED: CLAUDE.md].
**Example:**
```python
@app.get("/featured")
@limiter.limit("60/minute")
def get_featured(request: Request, response: Response):
    payload = _load_featured()
    if payload is None:
        response.status_code = 204
        return None
    return payload
```

### Pattern 2: Pydantic Payload Validation

**What:** Define a `BaseModel` for the featured release and validate fields with `field_validator` / `model_validator` [VERIFIED: Pydantic docs].
**When to use:** `POST /featured` request body [VERIFIED: CLAUDE.md, 11-CONTEXT.md].
**Example:**
```python
class FeaturedLink(BaseModel):
    label: str
    url: str

    @field_validator("url")
    @classmethod
    def must_be_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("link url must be http or https")
        return value
```

### Pattern 3: Signed Session Cookie

**What:** Use a serializer to sign a small payload such as `{"admin": True}` and validate it on protected routes [VERIFIED: ItsDangerous docs].
**When to use:** Operator-only `/yonkou` and `POST /featured` [VERIFIED: 11-CONTEXT.md].
**Example:**
```python
serializer = URLSafeTimedSerializer(settings.admin_session_secret)
token = serializer.dumps({"admin": True}, salt="admin-session")
response.set_cookie(
    "sg_admin",
    token,
    httponly=True,
    samesite="lax",
    secure=not settings.dev_mode,
    max_age=86400,
)
```

### Anti-Patterns to Avoid

- **Hand-rolled auth framework:** The phase requires one operator password, not accounts, roles, registration, OAuth, or user storage [VERIFIED: 11-CONTEXT.md, CLAUDE.md].
- **Rendering curated text with `innerHTML`:** Artist/title/description/link labels are operator input and must use `textContent` to preserve the existing XSS-safe frontend pattern [VERIFIED: static/app.js].
- **Adding `python-multipart` just for operator forms:** JSON submission from the operator HTML keeps the dependency set smaller and still supports a visual form [VERIFIED: FastAPI form docs, requirements.txt].
- **Always reserving sidebar width:** The layout must remain centered when `GET /featured` is empty [VERIFIED: 11-CONTEXT.md].
- **Changing global CSS architecture:** Existing tests forbid modern CSS properties; sidebar CSS must use raw selectors, raw hex colors, borders, and table-compatible layout [VERIFIED: tests/test_frontend.py].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session signing | Custom token format with homegrown timestamp checks | `itsdangerous.URLSafeTimedSerializer` [VERIFIED: ItsDangerous docs] | It already signs serialized data, verifies signatures, supports timestamp age checks, and has explicit failure exceptions [VERIFIED: ItsDangerous docs]. |
| Rate limiting | In-memory counters or Redis counters manually | Existing `limiter` in `api/main.py` [VERIFIED: api/main.py] | Project already uses slowapi with Redis storage and a custom 429 response handler [VERIFIED: api/main.py]. |
| Request validation | Manual dict checks from raw JSON | Pydantic `BaseModel` validators [VERIFIED: CLAUDE.md, Pydantic docs] | Security Gate requires this and existing code follows it [VERIFIED: CLAUDE.md, api/main.py]. |
| DOM sanitization | HTML string escaping helpers | `textContent`, `createElement`, and validated `href` assignment [VERIFIED: static/app.js] | Existing frontend already uses `textContent` for API-derived values [VERIFIED: static/app.js]. |
| Redis persistence wrapper | New storage abstraction framework | Small helper functions `_load_featured` / `_save_featured` [ASSUMED] | The feature stores one document and does not need repository/service layers [VERIFIED: 11-CONTEXT.md]. |

**Key insight:** The hard parts are not data modeling; they are preserving the project’s security gate, no-framework frontend, and Y2K table constraints while adding an operator-only mutation path [VERIFIED: CLAUDE.md, 11-CONTEXT.md].

## Common Pitfalls

### Pitfall 1: Slowapi Runtime Failure
**What goes wrong:** A new route omits `request: Request` or `response: Response`, and slowapi fails or cannot inject rate-limit headers [VERIFIED: CLAUDE.md, SlowAPI docs].
**How to avoid:** Copy the exact route signature shape from `submit_job`, `get_job`, and `health_check` [VERIFIED: api/main.py].
**Warning signs:** Tests pass route import but requests fail at runtime with slowapi wrapper errors [VERIFIED: CLAUDE.md].

### Pitfall 2: Admin POST Bypasses Pydantic
**What goes wrong:** The operator page posts raw form data and code calls `request.form()` or `request.json()` directly [VERIFIED: CLAUDE.md].
**How to avoid:** Make operator JS submit JSON to `POST /featured` and validate with `FeaturedReleaseRequest` [VERIFIED: FastAPI form docs, CLAUDE.md].
**Warning signs:** No `BaseModel` for links, no tests for more than three links, and no tests for invalid URL schemes [VERIFIED: 11-CONTEXT.md].

### Pitfall 3: Redis Down Breaks Public Page
**What goes wrong:** `GET /featured` returns 500 when Redis is unavailable [VERIFIED: 11-CONTEXT.md].
**How to avoid:** Catch `redis.exceptions.ConnectionError` and `TimeoutError`, then read the fallback JSON file [VERIFIED: Redis docs, api/main.py patterns].
**Warning signs:** Tests only patch successful `_redis.get` and do not simulate Redis exceptions [VERIFIED: tests/test_security.py pattern].

### Pitfall 4: XSS via Curated Content
**What goes wrong:** Operator-entered text or link labels are inserted with `innerHTML` [VERIFIED: static/app.js safe pattern].
**How to avoid:** Use `textContent` for every text field and validate URLs as `http`/`https` before persistence [VERIFIED: static/app.js, Pydantic docs].
**Warning signs:** `rg "innerHTML" static/app.js` finds new rendering code [ASSUMED].

### Pitfall 5: Cookie Security Drift Between Local and Production
**What goes wrong:** `secure=True` blocks local HTTP tests, or `secure=False` ships to production [VERIFIED: Starlette cookie docs, api/config.py dev_mode].
**How to avoid:** Set `secure=not settings.dev_mode`, `httponly=True`, `samesite="lax"`, `path="/"`, and test cookie flags [VERIFIED: Starlette docs, api/config.py].
**Warning signs:** Cookie is readable via JavaScript, lacks SameSite, or tests cannot stay logged in over TestClient [VERIFIED: Starlette docs].

### Pitfall 6: Layout Reflow Violates Empty-State Decision
**What goes wrong:** Sidebar `<td>` always exists, leaving blank space when no featured content exists [VERIFIED: 11-CONTEXT.md].
**How to avoid:** Create/remove the sidebar column only after successful non-empty `GET /featured`, or keep the entire sidebar cell hidden and widthless before insertion [ASSUMED].
**Warning signs:** Empty `GET /featured` still shifts `#app` left [VERIFIED: 11-CONTEXT.md].

## Code Examples

### Redis JSON Storage
```python
FEATURED_KEY = "featured:current"

def _load_featured() -> dict | None:
    try:
        raw = _redis.get(FEATURED_KEY)
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError):
        raw = _read_featured_fallback()
    if not raw:
        return None
    return json.loads(raw)
```

### Admin Auth Dependency Helper
```python
def _require_admin(request: Request) -> None:
    token = request.cookies.get("sg_admin")
    if not token:
        raise HTTPException(status_code=401, detail="Admin login required")
    try:
        data = _admin_serializer().loads(token, salt="admin-session", max_age=86400)
    except BadSignature:
        raise HTTPException(status_code=401, detail="Admin login required")
    if data.get("admin") is not True:
        raise HTTPException(status_code=401, detail="Admin login required")
```

### DOM-Safe Link Rendering
```javascript
const a = document.createElement('a');
a.textContent = link.label;
a.href = link.url;
a.target = '_blank';
a.rel = 'noopener';
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom string cookies | Signed serializer or framework session middleware [VERIFIED: ItsDangerous docs, Starlette middleware docs] | Current docs as of 2026-05-12 [VERIFIED: web docs] | Planner should avoid inventing its own signature format [VERIFIED: ItsDangerous docs]. |
| Raw form handlers | Pydantic form models or JSON body models [VERIFIED: FastAPI docs, Pydantic docs] | FastAPI form models supported since 0.113.0 [CITED: https://fastapi.tiangolo.com/tutorial/request-form-models/] | JSON body avoids adding `python-multipart` in this repo [VERIFIED: requirements.txt]. |
| `target="_blank"` alone | Explicit `target="_blank" rel="noopener"` [VERIFIED: MDN docs, 11-CONTEXT.md] | Modern browsers imply noopener, but explicit attribute remains clearer [VERIFIED: MDN docs] | Implement exactly as D-04 states [VERIFIED: 11-CONTEXT.md]. |

**Deprecated/outdated:**
- Adding full user accounts for this phase is out of scope because project policy says no accounts and Phase 11 only needs one operator-only panel [VERIFIED: CLAUDE.md, 11-CONTEXT.md].
- Adding embeds, artwork, platform detection, archive pages, reactions, RSS, or email notifications is out of scope [VERIFIED: 11-CONTEXT.md].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Fallback JSON should live in the writable app directory rather than `/tmp` [ASSUMED]. | Summary | If deployment filesystem is read-only, planner must choose a writable path or make fallback read-only. |
| A2 | A small `_load_featured` / `_save_featured` helper is enough; no repository layer is needed [ASSUMED]. | Don't Hand-Roll | If Phase 11 later grows archive/history, planner may need a storage module. |
| A3 | Sidebar should be created/removed by JS instead of statically reserving a cell [ASSUMED]. | Common Pitfalls | If static HTML is preferred, tests must prove no empty-state layout shift. |

## Open Questions (RESOLVED)

1. **What exact fallback JSON path should production use?** [RESOLVED]
   - What we know: Redis fallback is required [VERIFIED: 11-CONTEXT.md].
   - Resolution: add `FEATURED_FALLBACK_PATH` and default it to `.data/featured-current.json`, a project-local non-`/tmp` path. Deployment may override the env var if Railway requires a different writable location. This matches 11-02-PLAN.md and keeps `/tmp` reserved for audio cleanup conventions [RESOLVED: 11-02-PLAN.md].

2. **Should `/yonkou` be inline HTML or `static/yonkou.html`?** [RESOLVED]
   - What we know: Context allows either [VERIFIED: 11-CONTEXT.md].
   - Resolution: implement `/yonkou` as a small inline `HTMLResponse` in `api/main.py`. This avoids adding a public static HTML artifact for a hidden operator-only route, keeps route behavior near its authentication/session helpers, and matches the minimal-surface recommendation captured in the plan [RESOLVED: 11-02-PLAN.md].

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python runtime | FastAPI app/tests [VERIFIED: requirements.txt] | Yes [VERIFIED: command probe] | 3.12.3 locally; project guide says Python 3.11 [VERIFIED: command probe, CLAUDE.md] | Use project deploy/runtime constraints when executing [ASSUMED]. |
| pytest command | Automated tests [VERIFIED: pytest.ini] | No global command found [VERIFIED: command probe] | Not installed globally [VERIFIED: command probe] | Install requirements in venv before execution [ASSUMED]. |
| Redis CLI | Local Redis checks/rate-limit tests [VERIFIED: tests/conftest.py] | Yes [VERIFIED: command probe] | redis-cli 7.0.15 [VERIFIED: command probe] | Mock Redis exceptions in unit tests [VERIFIED: tests/test_security.py pattern]. |
| Node/npm | Graph/docs helper and static lint probes [VERIFIED: local tools] | Yes [VERIFIED: command probe] | Node 22.17.1; npm present [VERIFIED: command probe] | Not required for runtime [VERIFIED: CLAUDE.md]. |
| Context7 MCP | Library documentation lookup [VERIFIED: tool availability] | No MCP tool exposed in this session [VERIFIED: active tools] | N/A | Used official docs and PyPI version probes [VERIFIED: web docs, pip index]. |
| Graphify knowledge graph | Semantic codebase context [VERIFIED: GSD instructions] | Disabled/absent [VERIFIED: graphify probe] | N/A | Used direct file inspection with `rg`/`sed` [VERIFIED: command probes]. |

**Missing dependencies with no fallback:**
- None for research writing [VERIFIED: command probes].

**Missing dependencies with fallback:**
- Global pytest is missing; planner should include environment setup or run tests through the project venv after installing `requirements.txt` [VERIFIED: command probe, requirements.txt].

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 pinned/current [VERIFIED: requirements.txt, pip index] |
| Config file | `pytest.ini` [VERIFIED: pytest.ini] |
| Quick run command | `pytest tests/test_security.py -x -q` [VERIFIED: CLAUDE.md, tests/test_security.py] |
| Full suite command | `pytest tests/ -m "not e2e" -q` [VERIFIED: README.md, pytest.ini] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| D-01 | Login sets signed cookie; Redis save/load; JSON fallback on Redis down [VERIFIED: 11-CONTEXT.md] | unit/integration | `pytest tests/test_security.py -x -q` | Existing file, new tests needed [VERIFIED: tests/test_security.py]. |
| D-02 | Empty `/featured` does not render/sidebar shift; non-empty renders right column [VERIFIED: 11-CONTEXT.md] | frontend integration | `pytest tests/test_frontend.py -x -q` | Existing file, new tests needed [VERIFIED: tests/test_frontend.py]. |
| D-03 | Featured payload validates fields and max 3 links [VERIFIED: 11-CONTEXT.md] | unit | `pytest tests/test_security.py -x -q` | Existing file, new tests needed [VERIFIED: tests/test_security.py]. |
| D-04 | Links use `target="_blank" rel="noopener"` [VERIFIED: 11-CONTEXT.md] | frontend integration | `pytest tests/test_frontend.py -x -q` | Existing file, new tests needed [VERIFIED: tests/test_frontend.py]. |
| D-05 | Card CSS uses existing Y2K palette and avoids forbidden properties [VERIFIED: 11-CONTEXT.md] | frontend static | `pytest tests/test_frontend.py -x -q` | Existing CSS tests can be extended [VERIFIED: tests/test_frontend.py]. |
| D-06 | All new endpoints have rate limits and operator validation/auth [VERIFIED: 11-CONTEXT.md, CLAUDE.md] | security | `pytest tests/test_security.py -x -q` | Existing file, new tests required [VERIFIED: tests/test_security.py]. |

### Sampling Rate

- **Per task commit:** `pytest tests/test_security.py -x -q` [VERIFIED: CLAUDE.md].
- **Per wave merge:** `pytest tests/test_security.py tests/test_frontend.py -q` [VERIFIED: phase scope].
- **Phase gate:** `pytest tests/ -m "not e2e" -q` before `$gsd-verify-work` [VERIFIED: README.md].

### Wave 0 Gaps

- [ ] `tests/test_security.py` - add `test_featured_get_rate_limit`, `test_yonkou_login_rate_limit`, `test_post_featured_requires_operator_session`, `test_post_featured_validates_links`, `test_featured_redis_fallback` [VERIFIED: CLAUDE.md, 11-CONTEXT.md].
- [ ] `tests/test_frontend.py` - add sidebar markup/style tests for empty/non-empty behavior, link attributes, and CSS forbidden-property preservation [VERIFIED: tests/test_frontend.py, 11-CONTEXT.md].
- [ ] `requirements.txt` - add `itsdangerous==2.2.0` only if planner chooses the recommended serializer [VERIFIED: pip index, requirements.txt].

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes [VERIFIED: 11-CONTEXT.md] | `ADMIN_PASSWORD`, constant-time comparison, rate-limited login, signed cookie [VERIFIED: CLAUDE.md, ItsDangerous docs] |
| V3 Session Management | yes [VERIFIED: 11-CONTEXT.md] | HttpOnly SameSite cookie with signed timed payload and explicit max age [VERIFIED: Starlette docs, ItsDangerous docs] |
| V4 Access Control | yes [VERIFIED: 11-CONTEXT.md] | Reject `POST /featured` without valid operator session cookie [VERIFIED: 11-CONTEXT.md] |
| V5 Input Validation | yes [VERIFIED: CLAUDE.md] | Pydantic `BaseModel` and validators for strings, links, max link count [VERIFIED: Pydantic docs] |
| V6 Cryptography | yes [VERIFIED: 11-CONTEXT.md] | Library-backed signing; do not implement custom crypto [VERIFIED: ItsDangerous docs] |
| V7 Error Handling | yes [VERIFIED: api/main.py] | Reuse JSON 422/429 patterns and avoid leaking password/session details [VERIFIED: api/main.py] |
| V14 Configuration | yes [VERIFIED: api/config.py] | Add env-backed settings for password and session secret [VERIFIED: api/config.py] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Login brute force | Denial of Service / Elevation [ASSUMED] | `POST /yonkou/login` rate limit 5/min and constant-time password comparison [VERIFIED: 11-CONTEXT.md]. |
| Session cookie tampering | Elevation [VERIFIED: ItsDangerous docs] | Signed serializer with `loads(..., max_age=...)`, catch `BadSignature`, return 401 [VERIFIED: ItsDangerous docs]. |
| XSS from curated fields | Tampering / Elevation [ASSUMED] | Pydantic length/url validation plus frontend `textContent` rendering [VERIFIED: Pydantic docs, static/app.js]. |
| Reverse-tabnabbing via external links | Spoofing [VERIFIED: MDN docs] | `rel="noopener"` on every `_blank` link [VERIFIED: 11-CONTEXT.md, MDN docs]. |
| Redis outage | Availability [VERIFIED: 11-CONTEXT.md] | Graceful read/write fallback to JSON file and tests that patch Redis exceptions [VERIFIED: 11-CONTEXT.md]. |

## Sources

### Primary (HIGH confidence)

- `CLAUDE.md` - project stack, Y2K constraints, Security Gate [VERIFIED: local file].
- `.planning/phases/11.../11-CONTEXT.md` - locked phase decisions D-01..D-06 [VERIFIED: local file].
- `api/main.py` - FastAPI, slowapi, Redis, Pydantic, middleware, route-order patterns [VERIFIED: local file].
- `api/config.py` - environment settings pattern [VERIFIED: local file].
- `static/index.html`, `static/app.js`, `static/style.css` - table UI, DOM state, CSS constraints [VERIFIED: local files].
- `tests/test_security.py`, `tests/test_frontend.py`, `tests/conftest.py`, `pytest.ini` - validation architecture [VERIFIED: local files].
- FastAPI response cookies - https://fastapi.tiangolo.com/advanced/response-cookies/ [CITED: official docs].
- FastAPI form models - https://fastapi.tiangolo.com/tutorial/request-form-models/ [CITED: official docs].
- SlowAPI docs - https://slowapi.readthedocs.io/en/latest/ [CITED: official docs].
- Redis redis-py guide - https://redis.io/docs/latest/develop/clients/redis-py/ [CITED: official docs].
- Pydantic validators - https://docs.pydantic.dev/latest/concepts/validators/ [CITED: official docs].
- ItsDangerous serializer/timed signing - https://itsdangerous.palletsprojects.com/en/stable/serializer/ and https://itsdangerous.palletsprojects.com/en/stable/timed/ [CITED: official docs].
- Starlette responses/cookies - https://www.starlette.dev/responses/ [CITED: official docs].
- MDN noopener - https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/noopener [CITED: MDN].

### Secondary (MEDIUM confidence)

- PyPI version checks via `python -m pip index versions ...` for FastAPI, slowapi, redis, pydantic, itsdangerous, pytest [VERIFIED: pip index].

### Tertiary (LOW confidence)

- None [VERIFIED: source review].

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions and existing dependencies were verified from `requirements.txt` and PyPI where relevant [VERIFIED: requirements.txt, pip index].
- Architecture: HIGH - phase fits directly into existing FastAPI/static/Redis shape [VERIFIED: api/main.py, static/app.js, 11-CONTEXT.md].
- Pitfalls: HIGH for slowapi, Pydantic, CSS, and DOM rendering because they are already encoded in project files/tests; MEDIUM for fallback file path because deploy filesystem details are not confirmed [VERIFIED: CLAUDE.md, tests/test_frontend.py] [ASSUMED].

**Research date:** 2026-05-12 [VERIFIED: system date]
**Valid until:** 2026-06-11 for repo-local patterns; 2026-05-19 for package-version currency [ASSUMED].
