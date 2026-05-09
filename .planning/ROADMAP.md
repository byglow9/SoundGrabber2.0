# Roadmap — SoundGrabber

**Project:** SoundGrabber
**Milestone:** v1 — Public launch
**Granularity:** Standard
**Coverage:** 19/19 requirements mapped
**Last updated:** 2026-05-08

---

## Phases

- [ ] **Phase 1: Processing Pipeline** - Prove yt-dlp + FFmpeg + librosa work end-to-end from the target host before building anything else
- [ ] **Phase 2: API Layer** - Wrap the working pipeline in FastAPI + Celery + Redis with a job-queue HTTP contract
- [x] **Phase 3: Hardening** - Rate limiting, URL validation, duration caps, and disk safety before public exposure
- [x] **Phase 4: Frontend** - Browser-based user flow built against the real, hardened API
- [x] **Phase 5: Visual Identity** - Y2K / phpBB / Tibia authentic 2000s aesthetic applied to the complete frontend
- [ ] **Phase 6: Application Security** - File permissions, API rate limits, health endpoint, security tests, and policy documentation locked in
- [ ] **Phase 7: Infrastructure Security** - nginx reverse proxy, HTTPS with Let's Encrypt, HSTS, and Redis auth enforcement at the deployment boundary

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
**Goal**: The application is only reachable over HTTPS via nginx and Redis requires a password in all non-dev environments
**Depends on**: Phase 6
**Requirements**: SEC-INFRA-01, SEC-INFRA-02, SEC-INFRA-03, SEC-INFRA-04
**Success Criteria** (what must be TRUE):
  1. Attempting to start the application with a Redis URL that has no password (and DEV_MODE not set) causes startup to fail immediately with a clear error message naming the missing credential
  2. curl http://soundgrabber.example.com/ returns a 301 redirect to the HTTPS URL; no content is served over plain HTTP
  3. curl -I https://soundgrabber.example.com/ shows Strict-Transport-Security: max-age=31536000 in the response headers
  4. Uvicorn is bound to 127.0.0.1 and is unreachable directly from the internet; all traffic passes through nginx on ports 80 and 443

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
| 7. Infrastructure Security | 0/? | Not started | - |

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

**Mapped: 35/35 (19 v1 + 16 v1.1)**

---

*Roadmap created: 2026-04-29*
*v1.1 phases appended: 2026-05-09*
