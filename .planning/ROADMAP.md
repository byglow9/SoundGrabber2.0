# Roadmap — SoundGrabber

**Project:** SoundGrabber
**Milestone:** v1 — Public launch
**Granularity:** Standard
**Coverage:** 19/19 requirements mapped
**Last updated:** 2026-05-14

---

## Phases

- [ ] **Phase 1: Processing Pipeline** - Prove yt-dlp + FFmpeg + librosa work end-to-end from the target host before building anything else
- [ ] **Phase 2: API Layer** - Wrap the working pipeline in FastAPI + Celery + Redis with a job-queue HTTP contract
- [x] **Phase 3: Hardening** - Rate limiting, URL validation, duration caps, and disk safety before public exposure
- [x] **Phase 4: Frontend** - Browser-based user flow built against the real, hardened API
- [x] **Phase 5: Visual Identity** - Y2K / phpBB / Tibia authentic 2000s aesthetic applied to the complete frontend
- [ ] **Phase 6: Application Security** - File permissions, API rate limits, health endpoint, security tests, and policy documentation locked in
- [ ] **Phase 7: Infrastructure Security** - Railway PaaS deploy (railway.toml), Redis auth enforcement on startup, HSTS via FastAPI middleware, HTTPS automatic via Railway edge

---

## Phase Details

### Phase 1: Processing Pipeline
**Goal**: A standalone Python script proves the download-convert-analyze pipeline works from the production host
**Depends on**: Nothing (first phase)
**Requirements**: CORE-03, CORE-04, CORE-05, ANALYSIS-01, ANALYSIS-02, ANALYSIS-03, ANALYSIS-04
**Success Criteria** (what must be TRUE):
  1. Running the script with a YouTube URL produces a valid WAV file with no manual intervention
  2. The script correctly refuses URLs pointing to videos longer than 15 minutes and prints an explanatory message
  3. BPM is detected and printed; the value is plausible (within 30% of the track's actual feel-tempo across trap, lo-fi, and house test URLs)
  4. Musical key is detected and printed in both standard notation and Camelot notation
  5. Half-time and double-time BPM values are computed and displayed alongside the primary BPM without re-running analysis
**Plans**: TBD

### Phase 2: API Layer
**Goal**: The pipeline is accessible over HTTP via a job-queue contract exercisable by curl
**Depends on**: Phase 1
**Requirements**: CORE-01, CORE-02, CORE-06
**Success Criteria** (what must be TRUE):
  1. POST /jobs with a valid YouTube URL returns a job ID immediately (under 300ms)
  2. GET /jobs/{id} polled every 2 seconds returns status transitions (queued → downloading → converting → analyzing → done) and, when done, includes BPM, key, and a download URL
  3. GET /files/{id} streams the WAV to disk without loading the entire file into server memory
  4. Three concurrent curl jobs submitted simultaneously all complete without the API becoming unresponsive
**Plans:** 3 plans
Plans:
- [x] 02-01-PLAN.md — Wave 1 foundation: install Redis, pin FastAPI/Celery/Redis deps, scaffold `api/` package (config, tasks, main) with route stubs, and create test stubs covering CORE-01, CORE-02, CORE-06
- [ ] 02-02-PLAN.md — Wave 2: implement POST /jobs (YouTube allowlist validator + Redis Set tracking) and process_job (full pipeline orchestration with custom Celery states + sanitized JobFailure per D-05/D-06)
- [ ] 02-03-PLAN.md — Wave 3: implement GET /jobs/{id} (state mapping + 404 for unknown via Redis Set), GET /files/{id} (FileResponse streaming + path-traversal defense), sweeper daemon thread, and manual UAT for 3 concurrent jobs

### Phase 3: Hardening
**Goal**: The API safely handles abuse, malformed input, and resource exhaustion before users reach it
**Depends on**: Phase 2
**Requirements**: UX-03, UX-04
**Success Criteria** (what must be TRUE):
  1. Submitting a non-YouTube URL or a malformed URL returns a clear error response (not a 500) explaining what was wrong
  2. Submitting a YouTube URL for a video longer than 15 minutes is rejected before the download starts, with an error message stating the duration limit
  3. A single IP submitting more than 3 jobs per minute receives a 429 response with a human-readable message
  4. Killing a worker mid-job leaves no orphaned files in /tmp after the next background sweeper cycle (within 20 minutes)
**Plans:** 3 plans
Plans:
- [x] 03-01-PLAN.md — Wave 0: instalar slowapi==0.1.9 em requirements.txt e adicionar 4 stubs de teste RED (test_validation_error_format, test_rate_limit_returns_429, test_rate_limit_retry_after_header, test_sweeper_deletes_partial_files)
- [x] 03-02-PLAN.md — Wave 1: handler 422 normalizado (D-07) + sweeper estendido para .part/.ytdl (D-05/D-06) + campo rate_limit_per_minute em api/config.py (D-03)
- [x] 03-03-PLAN.md — Wave 2: rate limiting slowapi (D-01/D-02/D-03/D-04) — Limiter com Redis backend, handler 429 customizado com Retry-After, decorator @limiter.limit em POST /jobs

### Phase 4: Frontend
**Goal**: Users can complete the full workflow in a browser without using curl or reading API docs
**Depends on**: Phase 3
**Requirements**: CORE-01, UX-01, UX-02
**Success Criteria** (what must be TRUE):
  1. A user can paste a YouTube URL, click one button, and see real-time stage labels (Downloading... / Converting... / Analyzing...) update as the job progresses
  2. Before clicking download, the page displays the estimated WAV file size so the user knows what to expect
  3. BPM, key, Camelot notation, and half-time/double-time values are all visible on the result card without scrolling
  4. The download button triggers a direct WAV file save with no account, no email, and no redirect to an external site
**Plans:** 4 plans
Plans:
- [x] 04-01-PLAN.md — Wave 1: TDD RED stubs in tests/test_frontend.py (test_index_html_served, test_app_js_served, test_html_required_ids_present, test_wav_size_formula)
- [x] 04-02-PLAN.md — Wave 2: create static/index.html with all 16 required IDs and zero CSS (D-10/D-11)
- [x] 04-03-PLAN.md — Wave 3: create static/app.js — complete 8-state machine, polling, error recovery, WAV size estimation, download wiring
- [x] 04-04-PLAN.md — Wave 4: add GET / (FileResponse) + StaticFiles mount to api/main.py; human-verify browser smoke test
**UI hint**: yes

### Phase 5: Visual Identity
**Goal**: The site looks and feels like it was literally built in 2000-2005, not like a modern site imitating the past
**Depends on**: Phase 4
**Requirements**: VISUAL-01, VISUAL-02, VISUAL-03, VISUAL-04, VISUAL-05
**Success Criteria** (what must be TRUE):
  1. Before writing any CSS, the phase begins with a documented research step: inspecting Wayback Machine snapshots of real phpBB, Tibia fansites, and Orkut pages from 2000-2005 to capture exact construction patterns (table layouts, hex palettes, border styles, font stacks)
  2. The layout is built with HTML tables — not flexbox, not grid — with no CSS variables or custom properties anywhere in the stylesheet
  3. Fonts render in a bitmap/pixel face (VT323, Fixedsys, or Courier New) with font-smoothing explicitly disabled; no Google Fonts CDN call introduces modern rendering
  4. The dark-mode color palette is expressed entirely in raw hex values (no hsl(), no rgba() with floats, no CSS variables) drawn from actual period references
  5. A developer unfamiliar with the project can open the HTML source and reasonably believe it was written in 2002
**Plans:** 4 plans
Plans:
- [x] 05-01-PLAN.md — Wave 0: TDD RED stubs em tests/test_frontend.py — 4 novos testes (test_style_css_served, test_css_no_modern_properties, test_fonts_selfhosted, test_html_table_layout) + expandir test_html_required_ids_present de 16 para 27 IDs
- [x] 05-02-PLAN.md — Wave 1: download de DelaGothicOne-Regular.woff2 e Sligoil-Micro.woff2 para static/fonts/ (self-hosted, sem CDN)
- [x] 05-03-PLAN.md — Wave 2: criar static/style.css completo — @font-face, reset, tabelas, input, botões, hover/focus states, classe .sg-url-input--error; zero propriedades CSS3 proibidas
- [x] 05-04-PLAN.md — Wave 3: converter static/index.html de div para table layout preservando 27 IDs + adicionar <link> para style.css + checkpoint visual no browser
**UI hint**: yes

### Phase 6: Application Security
**Goal**: All application-level security controls are enforced in code and verified by automated tests, with policy documented as a mandatory project rule
**Depends on**: Phase 5
**Requirements**: SEC-FILE-01, SEC-FILE-02, SEC-API-01, SEC-API-02, SEC-API-03, SEC-TEST-01, SEC-TEST-02, SEC-TEST-03, SEC-TEST-04, SEC-TEST-05, SEC-TEST-06, SEC-POLICY-01, SEC-POLICY-02
**Success Criteria** (what must be TRUE):
  1. WAV files written to /tmp are created with mode 0o600; a stat() call on the file shows no read/write permission bits set for group or others
  2. start.sh cannot be executed by users other than its owner; ls -l shows permissions -rwxr-x--- (750)
  3. GET /jobs/{id} and GET /files/{id} reject a single IP after 60 and 10 requests per minute respectively with a 429 response
  4. GET /health returns 200 with Redis status "ok" when the system is healthy and returns 503 when Redis is unreachable
  5. Running pytest tests/test_security.py passes all tests for body size limit, security headers, disabled docs routes, queue depth limit, and rate limiting on /jobs and /files
**Plans:** 3 plans
Plans:
- [x] 06-01-PLAN.md — Wave 0: TDD RED stubs em tests/test_security.py — 10 stubs cobrindo SEC-FILE-01/02, SEC-API-01/02/03, SEC-TEST-01..05 (4 ja podem passar verde porque os middlewares correspondentes ja existem em api/main.py)
- [x] 06-02-PLAN.md — Wave 1: implementacao dos controles core — os.chmod(0o600) em pipeline.download_audio, chmod 750 self-aplicado em start.sh, decorators @limiter.limit em get_job (60/min) e download_file (10/min) com request/response obrigatorios, rota GET /health com _redis.ping() e tratamento de ConnectionError/TimeoutError; 6 testes RED do Plan 01 viram verdes
- [x] 06-03-PLAN.md — Wave 2: documentacao e politica — secao pip-audit pre-deploy em README.md (SEC-TEST-06), secao Security Gate em CLAUDE.md (SEC-POLICY-01), .planning/SECURITY-CHECKLIST.md cobrindo todos os 13 SEC-* controls (SEC-POLICY-02)

### Phase 7: Infrastructure Security
**Goal**: The application is deployed on Railway PaaS with HTTPS automatic, Redis auth enforced at startup, and HSTS header on all responses
**Depends on**: Phase 6
**Requirements**: SEC-INFRA-01, SEC-INFRA-02, SEC-INFRA-03, SEC-INFRA-04
**Success Criteria** (what must be TRUE):
  1. Attempting to start the application with a Redis URL that has no password (and DEV_MODE not set) causes startup to fail immediately with a clear error message naming the missing credential
  2. curl http://<app>.up.railway.app/ returns a 301 redirect to the HTTPS URL; no content is served over plain HTTP
  3. curl -I https://<app>.up.railway.app/ shows Strict-Transport-Security: max-age=31536000; includeSubDomains in the response headers
  4. Uvicorn binds to 0.0.0.0:$PORT inside the Railway container; the container is not exposed directly to the internet — all traffic passes through the Railway edge proxy
**Plans:** 4 plans
Plans:
- [x] 07-01-PLAN.md — Wave 0: TDD RED stubs em tests/test_security.py (test_redis_auth_required, test_redis_auth_bypass_dev_mode, test_redis_auth_passes_with_password, test_hsts_header) + DEV_MODE=true em conftest.py
- [x] 07-02-PLAN.md — Wave 1: campo dev_mode em api/config.py + funcao _check_redis_auth no lifespan + header HSTS no _security_headers (api/main.py); 4 testes RED viram GREEN
- [x] 07-03-PLAN.md — Wave 2: criar railway.toml na raiz com startCommand correto + atualizar SECURITY-CHECKLIST.md com SEC-INFRA-01..04
- [x] 07-04-PLAN.md — Wave 3: checkpoint humano — criar projeto Railway (web + celery-worker + Redis), configurar variaveis, deploy, smoke tests dos 4 SEC-INFRA-* e gerar 07-DEPLOY-LOG.md

---

## v1.2 Phases — YouTube Pipeline Fix

- [ ] **Phase 8: Pipeline Code Fixes** - Fix ffprobe resolution, yt-dlp hardening, cookies validation, and nixpacks.toml so the pipeline is correct and deployable
- [ ] **Phase 9: Railway bgutil Deployment** - Deploy the bgutil PO Token service on Railway and wire env vars so the worker and web service can reach it
- [ ] **Phase 10: Failure Hardening and E2E Validation** - Make pipeline failure explicit when bgutil is unavailable and validate the complete pipeline on Railway with real YouTube URLs
- [ ] **Phase 10.1: OAuth2 + Railway Volume Auth Migration** (INSERTED) - Migrate yt-dlp authentication from a base64-encoded env var (`YTDLP_COOKIES_B64`) to cookies.txt persisted in a Railway Volume at `/data/yt-dlp-cache`, eliminating redeploy-on-cookie-rotation and removing the bgutil PO Token dependency. Note: original CONTEXT.md D-03 specified OAuth2 device flow; 10.1-RESEARCH.md verified OAuth2 was removed from yt-dlp in 2024.11.18 — phase adapted to cookies-on-Volume per Plan 02 human checkpoint.

---

## Phase Details (v1.2)

### Phase 8: Pipeline Code Fixes
**Goal**: The pipeline code is correct — ffprobe resolves reliably, yt-dlp is hardened against transient failures and cache drift, cookies are validated at startup, and Railway knows to install system ffmpeg
**Depends on**: Phase 7
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, DEPLOY-01
**Success Criteria** (what must be TRUE):
  1. Running `python pipeline.py <url>` on a machine where system ffmpeg is installed uses the system ffprobe (found via shutil.which) rather than the imageio-ffmpeg path, and completes without FileNotFoundError
  2. Deploying to Railway with nixpacks.toml present results in `ffprobe -version` succeeding inside the container (system ffmpeg is on PATH)
  3. Starting the application with a cookies.txt that lacks `__Secure-3PSID` produces a CRITICAL log line visible in Railway logs before any job is processed
  4. Submitting a beat URL to a freshly deployed Railway instance (no cached JS) completes download without nsig extraction errors caused by stale yt-dlp cache
**Plans:** 3 plans
Plans:
- [x] 08-01-PLAN.md — Wave 1 (TDD): RED tests for all 6 behaviors — ffprobe resolution, ffmpeg_location directory, no_cache_dir, retries, cookies CRITICAL log, nixpacks.toml existence
- [x] 08-02-PLAN.md — Wave 2: fix pipeline.py — shutil.which ffprobe (PIPE-01), _FFMPEG_DIR variable (PIPE-02), no_cache_dir in both ydl_opts (PIPE-03), retries in download_audio (PIPE-04)
- [x] 08-03-PLAN.md — Wave 2: add _check_cookies to api/main.py lifespan (PIPE-05) + create nixpacks.toml with aptPkgs=["ffmpeg"] (DEPLOY-01)

### Phase 9: Railway bgutil Deployment
**Goal**: The bgutil PO Token service is running on Railway and both the web service and Celery worker can reach it via private networking
**Depends on**: Phase 8
**Requirements**: DEPLOY-02, DEPLOY-03
**Success Criteria** (what must be TRUE):
  1. A Railway service running `jim60105/bgutil-pot` is healthy and responds on its internal port 4416 (confirmed via Railway service health or curl from another service in the same project)
  2. The environment variable BGUTIL_BASE_URL is set in both the `web-service` and `celery-worker` Railway services and resolves to the bgutil internal URL
  3. The web service and Celery worker logs show no "BGUTIL_BASE_URL not set" or connection-refused errors at startup
**Plans:** 1 plan
Plans:
- [x] 09-01-PLAN.md — Wave 1: verify Celery Worker (10ec98b3) and Uvicorn (02cda13b) deployments, confirm clean startup logs (no BGUTIL_BASE_URL errors), discover Uvicorn public URL, and run end-to-end smoke test (POST /jobs with real beat URL → status=done with WAV)
**Note**: Human checkpoint on Task 4 — operator must supply a real YouTube beat URL for end-to-end validation

### Phase 10: Failure Hardening and E2E Validation
**Goal**: The pipeline fails loudly when bgutil is unavailable (no silent fallback), and the complete download-to-WAV-to-analysis pipeline succeeds on Railway for real beat URLs
**Depends on**: Phase 9
**Requirements**: PIPE-06, PIPE-07
**Success Criteria** (what must be TRUE):
  1. Submitting a job when BGUTIL_BASE_URL is set but bgutil is unreachable causes the job to reach status=failed with an error message that explicitly names bgutil as unavailable — not a generic download error and not a silent retry with a different client
  2. Submitting three different beat URLs via POST /jobs on the live Railway deployment results in all three jobs reaching status=done with a downloadable WAV, a plausible BPM value, and a key in standard notation
  3. GET /files/{id} on a completed Railway job streams a WAV that can be opened in a DAW (not a 0-byte file or an HTML error page)
**Plans:** 2/3 plans executed
Plans:
- [x] 10-01-PLAN.md — Wave 0 (TDD RED): 4 stubs RED para PIPE-06 em test_pipeline_fixes.py
- [x] 10-02-PLAN.md — Wave 1: BgutilUnavailable + probe HTTP em pipeline.py; except BgutilUnavailable em api/tasks.py; 4 stubs GREEN
- [ ] 10-03-PLAN.md — Wave 2: start-all.sh + railway.toml single-container; checkpoint humano E2E com 3 beats reais

### Phase 10.1: OAuth2 + Railway Volume Auth Migration (INSERTED)
**Goal**: yt-dlp authenticates via cookies.txt persisted in a Railway Volume at `/data/yt-dlp-cache` (D-03 adapted — OAuth2 was removed from yt-dlp 2024.11.18 per 10.1-RESEARCH.md), eliminating reliance on `YTDLP_COOKIES_B64` env var and removing the bgutil PO Token dependency
**Depends on**: Phase 10
**Requirements**: AUTH-01, AUTH-02, AUTH-03 (new)
**Success Criteria** (what must be TRUE):
  1. Running yt-dlp on Railway uses cookiefile from Railway Volume (`/data/yt-dlp-cache/cookies.txt`) — no `YTDLP_COOKIES_B64` env var needed — and cookies survive container restarts (persisted in Railway Volume at `/data/yt-dlp-cache`)
  2. Submitting three different beat URLs via POST /jobs results in all three reaching status=done — without `YTDLP_COOKIES_B64` env var, without bgutil, without "Sign in to confirm you're not a bot" errors
  3. After a forced Railway redeploy, the next job submission succeeds immediately (cookies loaded from Volume, no `YTDLP_COOKIES_B64` env var needed)
**Plans:** 3/5 plans executed

Plans:
- [x] 10.1-01-PLAN.md — Wave 0 (TDD RED): criar tests/test_pipeline_oauth.py com 7+ testes AUTH-01 (cookiefile do Volume, sem OAuth2, _check_oauth_cache CRITICAL logs, ausência de bgutil) + inverter testes bgutil_08x_* + remover testes PIPE-06 em tests/test_pipeline_fixes.py
- [x] 10.1-02-PLAN.md — Wave 1 (checkpoint humano BLOCKING): confirmar adaptação D-03 — OAuth2 foi removido do yt-dlp 2026.3.17; usar cookies no Railway Volume em vez de username=oauth2/cachedir
- [x] 10.1-03-PLAN.md — Wave 2 (refactor): pipeline.py (check_duration/download_audio com assinatura cache_dir, sem BgutilUnavailable/httpx probe), api/config.py (cache_dir adicionado; cookies_path/po_token/bgutil_base_url removidos), api/main.py (_check_oauth_cache substitui _check_cookies), api/tasks.py (sem BgutilUnavailable), requirements.txt (sem bgutil-ytdlp-pot-provider), start-all.sh (chmod 700 do Volume); testes Wave 0 GREEN; adicionar testes _check_oauth_cache em tests/test_security.py + atualizar .planning/SECURITY-CHECKLIST.md
- [ ] 10.1-04-PLAN.md — Wave 3 (Railway infra + checkpoint humano): criar Railway Volume em /data/yt-dlp-cache no serviço 248e8eaf, setar YTDLP_CACHE_DIR, checkpoint humano para operador popular cookies.txt via railway run, redeploy + verificar startup logs limpos
- [ ] 10.1-05-PLAN.md — Wave 4 (E2E + teardown): 3 beats reais via POST /jobs (AUTH-02), redeploy forçado validando AUTH-03, deletar serviço bgutil (2fc3a8a5), remover env vars BGUTIL_BASE_URL e YTDLP_COOKIES_B64

### Phase 11: Som da Semana
**Goal**: Visitors see a Y2K/phpBB-style Som da Semana sidebar only when curated content exists, while the operator can directly visit `/yonkou`, authenticate with `ADMIN_PASSWORD`, and replace the single featured release through signed-cookie-protected, rate-limited endpoints
**Depends on**: Phase 10
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06
**Success Criteria** (what must be TRUE):
  1. The public homepage contains no visible button, link, menu item, or copy exposing `/yonkou`.
  2. Directly visiting `/yonkou` renders the operator login panel; a valid `ADMIN_PASSWORD` sets a signed HttpOnly SameSite session cookie.
  3. `POST /featured` rejects missing/invalid operator sessions, validates artist/title/genre/description and up to 3 HTTP(S) links, and stores the single current release in Redis with JSON fallback.
  4. `GET /featured` is rate-limited and returns either the current featured release or an empty response without breaking the downloader flow.
  5. When content exists, the visitor page injects a right-side table sidebar using the locked Y2K palette and safe DOM rendering; when empty or failed, the main downloader table remains centered.
**Plans:** 4/4 plans complete

Plans:
- [x] 11-01-PLAN.md — Wave 1: RED tests for operator auth, `/yonkou`, `/featured`, Redis fallback, no public route affordance, and sidebar/static contract
- [x] 11-02-PLAN.md — Wave 2: backend settings, signed cookie auth, `/yonkou`, `/featured`, Pydantic validation, Redis JSON storage, and fallback
- [x] 11-03-PLAN.md — Wave 2: public sidebar HTML/JS/CSS implementation following the approved UI-SPEC
- [x] 11-04-PLAN.md — Wave 3: security checklist update and human direct-route verification checkpoint

---

## v1.3 Phases — HP Notebook Hosting

- [ ] **Phase 12: Notebook Foundation** - Install Ubuntu Server 24.04 LTS, configure Docker, swap, systemd watchdog, and lid-close prevention on the HP notebook, and produce a reproducible setup script
- [x] **Phase 13: Docker Compose** - Build a Docker image and a three-service Compose stack with shared tmpfs and correct memory limits (completed 2026-05-15)
- [ ] **Phase 14: Pipeline E2E on Notebook** - Migrate cookies, wire the deploy script, and validate three complete beat downloads on the notebook via Tailscale
- [ ] **Phase 15: Cloudflare Tunnel** - Expose the notebook publicly via a Cloudflare Tunnel HTTPS URL and validate three end-to-end downloads through it

---

## Phase Details (v1.3)

### Phase 12: Notebook Foundation
**Goal**: Ubuntu Server 24.04 LTS is installed on the HP notebook and hardened for unattended headless operation — Docker installed via apt, 4GB swap active, cgroups v2 enforced, systemd watchdog protecting against permanent hangs, lid-close suspend disabled, and a reproducible setup script documenting every step
**Depends on**: Phase 11
**Requirements**: SVR-01, SVR-02, SVR-03, SVR-04
**Success Criteria** (what must be TRUE):
  1. `uname -m` run via SSH over Tailscale returns `x86_64` and `lsb_release -rs` returns `24.04` — operator confirms Ubuntu Server 24.04 LTS is running before any other work proceeds
  2. `docker info | grep "Cgroup Version"` returns `2` and `swapon --show` shows `/swapfile` with Size ≥ 4G — cgroups v2 active and swap confirmed
  3. `systemctl show logind | grep HandleLidSwitch` returns `ignore` — notebook does not suspend when lid is closed — and `RuntimeWatchdogSec=15` is confirmed in `/etc/systemd/system.conf.d/10-watchdog.conf`
  4. Running `bash notebook-setup.sh` on a fresh Ubuntu Server 24.04 LTS install reproduces the full environment (Docker, swap, watchdog, lid-close prevention) without manual steps beyond providing credentials — script is documented and committed to the repo
**Plans**: 2 plans
Plans:
**Wave 1**
- [ ] 12-01-PLAN.md — Wave 1: criar scripts/notebook-setup.sh com 7 seções (preflight, lid-close prevention, Docker, swap, cgroups v2 check, systemd watchdog, verificação final)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 12-02-PLAN.md — Wave 2: checkpoint humano — Moisés executa o script no notebook e documenta outputs em scripts/12-SETUP-LOG.md

### Phase 13: Docker Compose
**Goal**: A three-service Docker Compose stack (api, worker, redis) runs on the notebook with a standard x86_64 image, system ffmpeg, Essentia functional, and a shared tmpfs volume so WAV files written by the worker are served by the api
**Depends on**: Phase 12
**Requirements**: DEPLOY-04, DEPLOY-05, DEPLOY-06
**Success Criteria** (what must be TRUE):
  1. `docker build -t soundgrabber:latest .` completes without error on the notebook and `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"` exits 0 — the image is functional
  2. `docker compose ps` shows all three services (api, worker, redis) in a running/healthy state with `restart: unless-stopped` policy — confirmed by deliberately stopping one service and observing automatic restart
  3. A WAV file written by the worker container to `/tmp` is immediately readable by the api container at the same path via the shared `sg_tmp` tmpfs volume — confirmed by `docker exec api ls /tmp/sg_*.wav` after a test write in the worker container
**Plans:** 4/4 plans complete
Plans:
**Wave 1**
- [x] 13-01-PLAN.md — Wave 0 (TDD RED): criar tests/test_pipeline_docker.py com 3 stubs RED (test_no_imageio_ffmpeg_import, test_no_librosa_import, test_detect_tuning_essentia) cobrindo DEPLOY-04 / D-02 / D-03
- [x] 13-02-PLAN.md — Wave 1: remover imageio-ffmpeg e librosa de requirements.txt; refatorar pipeline.py (shutil.which fail-fast para ffmpeg/ffprobe; reescrever detect_tuning com Essentia SpectralPeaks + TuningFrequency); 3 testes Wave 0 viram GREEN

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 13-03-PLAN.md — Wave 2: criar .dockerignore (.venv, .git, cookies, .planning excluídos) + Dockerfile (python:3.11-slim + ffmpeg + Node 20 via NodeSource + libsndfile1 + pip install --no-cache-dir + CMD uvicorn) + checkpoint humano Gate D-07 (`docker run soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery"`)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 13-04-PLAN.md — Wave 3: criar .env.example (REDIS_URL, DEV_MODE=true, BGUTIL_BASE_URL) + docker-compose.yml (4 serviços api/worker/redis/bgutil + named volume sg_tmp tmpfs compartilhado + soundgrabber_net bridge + restart: unless-stopped) + checkpoint humano gates DEPLOY-05 (4x unless-stopped) e DEPLOY-06 (worker touch /tmp, api lê)

### Phase 14: Pipeline E2E on Notebook
**Goal**: The operator can trigger a full deployment to the notebook with one SSH command, cookies are in place so yt-dlp authenticates without errors, and three real beat URLs complete the download-convert-analyze pipeline on notebook hardware without bot-detection failures
**Depends on**: Phase 13
**Requirements**: AUTH-04, AUTH-05, PIPE-08
**Success Criteria** (what must be TRUE):
  1. The notebook startup log (accessible via `docker compose logs api`) shows no CRITICAL cookie warning — `cookies.txt` is present in the `sg_cookies` volume at `/data/yt-dlp-cache/cookies.txt` and the startup health check passes
  2. Running `ssh user@100.x.x.x 'bash ~/soundgrabber/deploy.sh'` from the operator's machine completes without error, pulling the latest code and restarting the api and worker containers in the correct order — one command, no manual steps
  3. Three different YouTube beat URLs submitted to `POST /jobs` on the notebook each reach `status=done` with a downloadable WAV, a plausible BPM value, and a key in standard notation — no `LOGIN_REQUIRED` errors, no bot-detection blocks, no bgutil dependency
**Plans**: TBD

### Phase 15: Cloudflare Tunnel
**Goal**: The SoundGrabber application is publicly accessible via a stable HTTPS URL backed by a Cloudflare Tunnel running on the notebook, with no open router ports and no residential IP exposure
**Depends on**: Phase 14
**Requirements**: TUNNEL-01, TUNNEL-02
**Success Criteria** (what must be TRUE):
  1. `systemctl status cloudflared` (or `docker compose ps cloudflared`) shows the tunnel service active and running on the notebook; `curl https://<public-domain>/health` returns HTTP 200 from the operator's machine on any network — the tunnel is live and routing correctly
  2. Three complete end-to-end beat downloads executed through the public HTTPS URL (paste URL → poll status → download WAV) all succeed with valid WAV files, BPM, and key — the public tunnel does not introduce failures that do not occur on the private Tailscale URL
**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Processing Pipeline | 4/4 | Done | 2026-04-30 |
| 2. API Layer | 0/3 | Planned | - |
| 3. Hardening | 3/3 | Done | 2026-05-04 |
| 4. Frontend | 4/4 | Done | 2026-05-08 |
| 5. Visual Identity | 4/4 | Done | 2026-05-08 |
| 6. Application Security | 0/3 | Planned | - |
| 7. Infrastructure Security | 0/4 | Planned | - |
| 8. Pipeline Code Fixes | 3/3 | Done | 2026-05-11 |
| 9. Railway bgutil Deployment | 0/1 | Planned | - |
| 10. Failure Hardening and E2E Validation | 2/3 | In Progress | - |
| 10.1. OAuth2 + Railway Volume Auth Migration | 3/5 | In Progress | - |
| 11. Som da Semana | 4/4 | Done | 2026-05-14 |
| 12. Notebook Foundation | 0/2 | Planned | - |
| 13. Docker Compose | 4/4 | Complete    | 2026-05-15 |
| 14. Pipeline E2E on Notebook | 0/TBD | Not started | - |
| 15. Cloudflare Tunnel | 0/TBD | Not started | - |

---

## Coverage Map

| Requirement | Phase |
|-------------|-------|
| CORE-01 | Phase 2 |
| CORE-02 | Phase 2 |
| CORE-03 | Phase 1 |
| CORE-04 | Phase 1 |
| CORE-05 | Phase 1 |
| CORE-06 | Phase 2 |
| ANALYSIS-01 | Phase 1 |
| ANALYSIS-02 | Phase 1 |
| ANALYSIS-03 | Phase 1 |
| ANALYSIS-04 | Phase 1 |
| UX-01 | Phase 4 |
| UX-02 | Phase 4 |
| UX-03 | Phase 3 |
| UX-04 | Phase 3 |
| VISUAL-01 | Phase 5 |
| VISUAL-02 | Phase 5 |
| VISUAL-03 | Phase 5 |
| VISUAL-04 | Phase 5 |
| VISUAL-05 | Phase 5 |
| SEC-FILE-01 | Phase 6 |
| SEC-FILE-02 | Phase 6 |
| SEC-API-01 | Phase 6 |
| SEC-API-02 | Phase 6 |
| SEC-API-03 | Phase 6 |
| SEC-TEST-01 | Phase 6 |
| SEC-TEST-02 | Phase 6 |
| SEC-TEST-03 | Phase 6 |
| SEC-TEST-04 | Phase 6 |
| SEC-TEST-05 | Phase 6 |
| SEC-TEST-06 | Phase 6 |
| SEC-POLICY-01 | Phase 6 |
| SEC-POLICY-02 | Phase 6 |
| SEC-INFRA-01 | Phase 7 |
| SEC-INFRA-02 | Phase 7 |
| SEC-INFRA-03 | Phase 7 |
| SEC-INFRA-04 | Phase 7 |
| PIPE-01 | Phase 8 |
| PIPE-02 | Phase 8 |
| PIPE-03 | Phase 8 |
| PIPE-04 | Phase 8 |
| PIPE-05 | Phase 8 |
| PIPE-06 | Phase 10 |
| PIPE-07 | Phase 10 |
| DEPLOY-01 | Phase 8 |
| DEPLOY-02 | Phase 9 |
| DEPLOY-03 | Phase 9 |
| SVR-01 | Phase 12 |
| SVR-02 | Phase 12 |
| SVR-03 | Phase 12 |
| SVR-04 | Phase 12 |
| DEPLOY-04 | Phase 13 |
| DEPLOY-05 | Phase 13 |
| DEPLOY-06 | Phase 13 |
| AUTH-04 | Phase 14 |
| AUTH-05 | Phase 14 |
| PIPE-08 | Phase 14 |
| TUNNEL-01 | Phase 15 |
| TUNNEL-02 | Phase 15 |

**Mapped: 57/57 (19 v1 + 16 v1.1 + 10 v1.2 + 12 v1.3)**

---

*Roadmap created: 2026-04-29*
*v1.1 phases appended: 2026-05-09*
*v1.2 phases appended: 2026-05-10*
*v1.3 phases appended: 2026-05-14*
