# Project Research Summary

**Project:** SoundGrabber
**Domain:** YouTube audio downloader + music analysis web utility for underground producers
**Researched:** 2026-04-29
**Confidence:** MEDIUM-HIGH (stack well-established; YouTube download reliability is the one structural unknown)

---

## Executive Summary

SoundGrabber is a stateless, no-auth public utility that solves a real and unmet need: no existing tool combines YouTube-to-WAV download with automatic BPM and key detection in a single zero-friction workflow. The closest competitors are either download-only (cobalt.tools) or analysis-only with file upload (TuneReveal, vocalremover.org). The product's cultural differentiation — a Y2K internet aesthetic targeting underground producers who grew up in that era — is as important as its functional gap. This is not a generic utility; it is a community artifact.

The recommended architecture is a Python/FastAPI backend with Celery workers (separate processes) handling the yt-dlp download, FFmpeg conversion, and librosa analysis pipeline. The download and analysis pipeline must run in separate OS processes from the web server because both yt-dlp and librosa are CPU/IO-heavy and blocking — running them in the FastAPI event loop will freeze the server under any meaningful load. Job state is stored in Redis with a 10-minute TTL; no database is needed. The frontend is a single HTML page with vanilla JS polling for job status. No JavaScript framework is warranted for an app with one form and one result card.

The highest-risk dependency is YouTube itself. Datacenter IPs are routinely flagged as bots, which causes download failures in production that do not reproduce locally. This is not a bug to fix — it is a structural constraint to design around from day one. The mitigation strategy is: use a VPS with a dedicated (non-PaaS) IP, pass valid YouTube session cookies with every request, keep yt-dlp updated weekly, and design the download layer as a swappable abstraction so its internals can change without touching the rest of the pipeline. Accept a 10-20% failure rate as a baseline, not a target.

---

## Key Findings

### Recommended Stack

The stack is deliberate and minimal. Python 3.11 + FastAPI + Celery + Redis covers the backend. yt-dlp (latest) + FFmpeg handles download and conversion. librosa 0.11 handles BPM and key detection at launch, with Essentia as the upgrade path if librosa accuracy proves insufficient for the producer audience. The frontend is plain HTML/CSS/JS — no framework — because the entire UI is a form, a status indicator, and a result card. The Y2K aesthetic is deliberately hand-crafted in raw CSS; no component library will produce it.

**Core technologies:**
- **Python 3.11+**: Runtime — asyncio native, audio DSP ecosystem lingua franca, yt-dlp requires >=3.10
- **FastAPI 0.115+**: API layer — async-native, streaming file responses, background task integration
- **Celery + Redis**: Task execution — separates CPU/IO-bound workers from the web process; prevents event loop starvation under load
- **yt-dlp (latest, date-versioned)**: YouTube download — the only actively maintained option; must stay near HEAD
- **FFmpeg 6+**: Audio conversion — invoked by yt-dlp postprocessor; no separate Python wrapper needed
- **librosa 0.11**: BPM + key detection — single pip install, proven in production at similar tools (StemSplit)
- **Vanilla HTML/CSS/JS**: Frontend — one page, two states; React/Vue are category errors here
- **Hetzner VPS (~5 EUR/mo) preferred over shared PaaS**: Hosting — dedicated IP dramatically improves YouTube download success rate

**Key versions:**
- `yt-dlp >= 2026.3.0` (update weekly via CI — pinning is dangerous)
- `fastapi >= 0.115, < 1.0`
- `librosa >= 0.11.0`
- `numpy >= 1.24, < 2.0` (librosa 0.11 numpy 2.x compatibility is partial)
- System packages: `ffmpeg >= 6.0`, `libsndfile1`
- Docker base: `python:3.11-slim-bookworm` (not Alpine — musl libc breaks audio libs)

### Expected Features

The feature gap SoundGrabber fills is real and validated. The competitor matrix confirms no tool currently combines download-to-WAV + BPM + key + no-account in a single workflow.

**Must have (table stakes) — missing any of these means the product feels incomplete:**
- URL paste and one-click processing — the entry point; everything else depends on this
- Real-time progress feedback (download / converting / analyzing stages) — 10-60s pipeline reads as broken without it
- Direct WAV download, no account, no email — gating creates abandonment; no-friction is non-negotiable
- BPM display — producers set DAW tempo before doing anything else; this is the core payload
- Musical key display (e.g. F# minor) — equal standing with BPM for producers writing chords or layering samples
- Mobile-usable layout — 40-60% of web traffic; producers browse YouTube on phones while working at desk
- HTTPS with no sketchy redirects — y2mate malware reputation is a known community concern; trust signals matter
- End-to-end result under 60 seconds — competing tools return in 15-30s; over 90s loses users

**Should have (differentiators) — add in v1 or v1.1:**
- Y2K / phpBB / Tibia / Orkut visual aesthetic — cultural identity; signals "made for us, not everyone"
- Combined download + analysis in one workflow — the explicit gap vs. all competitors; the core differentiator
- Copy-to-clipboard on BPM and key — removes friction when producer reaches for FL Studio / Ableton
- Camelot wheel notation alongside standard key (e.g. "F# minor / 11A") — harmonic mixing notation producers actually use
- Half-time / double-time BPM toggle — trap and lo-fi frequently detected at double the "feel" BPM; a div-2 / x2 button resolves this without re-analysis
- Estimated WAV file size shown before download — WAV is 30-40x larger than the compressed source; producers expect MP3 sizes

**Defer to v2 or never:**
- Waveform thumbnail (validate core workflow first)
- BPM/key confidence indicator (useful but adds implementation complexity)
- User accounts, download history, playlists, batch processing — anti-features that contradict no-friction
- Multi-platform support (SoundCloud, TikTok) — each platform is a separate breakage surface
- Stem separation, vocal remover — different product category
- Multiple export formats — WAV is right; MP3 producers can convert in their DAW

### Architecture Approach

SoundGrabber is a job-queue architecture: the API layer accepts requests and returns a job ID immediately, Celery workers execute the download-convert-analyze pipeline in separate OS processes, Redis stores job state with TTL, and the client polls for completion. The entire system is stateless with ephemeral file storage: WAV files are written to `/tmp/soundgrabber/{job_id}/`, streamed to the client via chunked `StreamingResponse`, then deleted by a `BackgroundTask` after the response ends. A fallback cron sweeper deletes any job directory older than 20 minutes.

**Major components:**
1. **API Layer (FastAPI + Uvicorn, 2-4 workers)** — accepts POST /jobs, serves GET /jobs/{id} status polls, serves GET /files/{id} WAV streaming; rate limiting via `fastapi-limiter` + Redis sliding window per IP
2. **Message Broker (Redis)** — Celery task queue, rate-limit counters, job state store with 10-min TTL
3. **Processing Workers (Celery, 2-4 processes)** — yt-dlp download + FFmpeg WAV conversion + librosa BPM/key analysis; runs in separate OS processes so CPU work never blocks the API event loop
4. **Temp File Storage (/tmp/soundgrabber/{job_id}/)** — isolated directory per job; deleted after download or after 20-min TTL sweep
5. **Frontend (single HTML + vanilla JS)** — URL form, polling loop, result card; Y2K aesthetic in hand-crafted CSS

**Status communication:** 2-second polling over SSE or WebSockets. Jobs take 15-60s; at most 30 status checks per job — negligible. SSE creates persistent connections that are problematic at hundreds of concurrent users. Polling is simpler, retryable, and works behind any CDN or proxy.

### Critical Pitfalls

1. **Datacenter IP flagging by YouTube (CRITICAL)** — Production downloads fail while local dev works. Shared PaaS IPs achieve 20-40% success vs. 85-95% for residential IPs. Mitigation: VPS with dedicated IP, valid session cookies via `--cookies`, PO Token support, yt-dlp at latest. Abstract the download function behind an interface from day one so strategy can change without touching the pipeline.

2. **Half-tempo / double-tempo BPM error (CRITICAL for producer trust)** — librosa systematically returns half the correct BPM for trap beats with half-time drum patterns (70 BPM instead of 140). Mitigation: always display both the detected BPM and its half/double (e.g., "140 BPM — or 70 BPM half-time"); run analysis at multiple start_bpm hints; analyze from the 20% track mark to skip drum-free intros.

3. **Temp file accumulation and disk exhaustion (CRITICAL)** — Every download creates 3+ files. Failed/abandoned jobs leave orphans. On a small VPS, ~500 orphaned downloads fill the disk and crash the server. Mitigation: `tempfile.mkdtemp()` per job + `try/finally` with `shutil.rmtree` + periodic background sweeper. Must be established in Phase 1 — cannot be retrofitted.

4. **yt-dlp version drift causing silent failures (HIGH)** — Outdated yt-dlp downloads HTML error pages that look like audio files until FFmpeg fails on them. Mitigation: validate every downloaded file with `ffprobe -v error -show_entries format=duration`; automate weekly yt-dlp updates in CI.

5. **Concurrent librosa memory spikes causing OOM kills (MODERATE)** — A 10-minute WAV at 44.1kHz stereo consumes 200-400MB RAM per analysis job as NumPy float32 arrays. At 5 concurrent users on a 2GB VPS, the OOM killer fires. Mitigation: downsample to mono 22050 Hz for analysis (4x memory reduction), analyze a 90-second window starting at 20% of track duration, cap concurrent analysis jobs at 3 via semaphore.

---

## Implications for Roadmap

### Phase 1: Processing Pipeline (Standalone Script)

**Rationale:** yt-dlp is the highest-risk dependency. Validate it works from the target hosting environment before building anything else. If YouTube blocks the server IP, no amount of API or frontend work matters. This is the existential gate.

**Delivers:** A standalone Python script: YouTube URL in, WAV file + BPM + key out. No web framework, no UI — just the pipeline working end-to-end from the target host.

**Addresses:** Table stakes — download, convert, BPM, key

**Avoids:**
- Pitfall 1 (datacenter IP blocking) — establish cookie/PO Token strategy before any other layer is built
- Pitfall 2 (yt-dlp version drift) — implement ffprobe validation from the first working version
- Pitfall 3 (temp file accumulation) — establish `try/finally` + `shutil.rmtree` as the baseline
- Pitfall 5 (librosa memory) — implement mono/22050Hz downsampling and windowed analysis from the start

**Success gate:** 9/10 representative YouTube URLs (varied genres, lengths, ages) produce a valid WAV + plausible BPM + plausible key from the production host.

---

### Phase 2: API Layer

**Rationale:** Wrap the working pipeline in a web API. The job-queue contract (POST /jobs, poll GET /jobs/{id}) must exist before the frontend is built. The frontend polls the API; the API cannot be designed after the frontend.

**Delivers:** A working HTTP API exercisable via curl. POST a URL, get a job ID, poll for status, get BPM + key + WAV download link.

**Uses:** FastAPI + Uvicorn, Celery + Redis, StreamingResponse WAV serving

**Implements:** API layer + Celery worker layer + Redis job state + temp file cleanup

**Avoids:**
- Running yt-dlp or librosa inside the FastAPI process (Celery workers handle both)
- Serving WAV via FileResponse loading whole file into memory (StreamingResponse with chunked generator)
- Pitfall 10 (synchronous download blocking the web server)

**Success gate:** `curl` workflow completes end-to-end; 3 concurrent `curl` jobs run simultaneously without API becoming unresponsive.

---

### Phase 3: Rate Limiting and Hardening

**Rationale:** Harden before exposing to users. No-auth + free + public is an abuse surface. Rate limiting, URL validation, duration caps, and disk safety must be in place before the frontend goes live.

**Delivers:** A production-safe API that rejects malformed URLs, enforces per-IP rate limits (3/min, 20/hr), caps video duration at 15 minutes (~160MB WAV max), enforces a concurrent job ceiling (20 system-wide), and survives disk pressure.

**Implements:** `fastapi-limiter` on POST /jobs, YouTube watch URL regex validation, `--match-filter "duration <= 900"` in yt-dlp, system-wide active-job counter in Redis, APScheduler disk sweeper, ffmpeg + libsndfile health check at startup

**Avoids:**
- Queue pollution from non-YouTube URLs
- Disk exhaustion from oversized videos
- IP ban acceleration from excessive retries (`--fragment-retries 3`)
- Pitfall 8 and 9 (missing ffmpeg/libsndfile in container)

---

### Phase 4: Frontend

**Rationale:** Build the UI against the working, hardened API. This prevents mismatch between polling assumptions and actual status response shapes.

**Delivers:** Complete browser-based user flow: paste URL, watch progress stages, see BPM + key, click download. Includes copy-to-clipboard buttons, estimated file size before download, half-time/double-time toggle, Camelot notation.

**Addresses:** All table stakes UX features

**Uses:** Single `index.html` + `static/app.js` (~60-80 lines vanilla JS), FastAPI `StaticFiles` mount

**Avoids:** React/HTMX/Next.js (no component graph exists), WAV size surprise (show size before download)

---

### Phase 5: Visual Identity

**Rationale:** Apply the Y2K aesthetic to the complete, working frontend. Aesthetic work done before the functional layer is validated risks rework if component layout changes.

**Delivers:** The phpBB/Tibia/Orkut visual identity that signals cultural belonging to the underground producer community. Hand-crafted CSS: pixel fonts, gradient backgrounds, bordered boxes with retro chrome. Single deliberate aesthetic — no dark mode toggle.

**Addresses:** The cultural differentiator that no competitor has. Low complexity, very high community value.

---

### Phase Ordering Rationale

- Pipeline before API: yt-dlp viability on the target host is the existential dependency — prove it before building anything else
- API before frontend: the polling contract (job state shape, error formats) must be real before the frontend consumes it
- Hardening before public launch: no-auth + free + public is an abuse surface; rate limiting is not optional
- Visual identity last: non-blocking; does not gate functional validation

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 1 (download pipeline):** YouTube bot detection countermeasures evolve rapidly. The PO Token strategy, cookie rotation approach, and specific yt-dlp flags need validation against the actual hosting environment before the API is built. Check yt-dlp GitHub issues for current YouTube breakages the week Phase 1 begins.
- **Phase 3 (rate limiting):** The specific `fastapi-limiter` + Redis integration and concurrent job ceiling numbers are estimates that need tuning against observed traffic. Start conservative and adjust.

**Phases with standard patterns (skip deep research):**
- **Phase 2 (API layer):** FastAPI + Celery + Redis is a well-documented, stable stack. Clear production guides exist. No surprises expected.
- **Phase 4 (frontend):** Vanilla JS polling against a JSON API is a 2005-era pattern. No framework decisions to make.
- **Phase 5 (visual identity):** Pure CSS/design work. Research is irrelevant — this is a creative decision.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core Python/FastAPI/librosa choices are well-established. yt-dlp download reliability is the one structural unknown — it works but YouTube actively fights it. |
| Features | HIGH | Competitor matrix is solid. The gap (download + analysis + no-account in one workflow) is verified against live tools. Feature priorities are based on verified community patterns. |
| Architecture | HIGH | The job-queue pattern (FastAPI + Celery + Redis) is industry-standard for this class of app. Component boundaries and data flow are well-understood. Anti-patterns are documented from production failures in similar tools. |
| Pitfalls | HIGH (YouTube/deployment), MEDIUM (analysis accuracy) | IP blocking and disk management pitfalls are extensively documented in yt-dlp issues. BPM accuracy numbers come from StemSplit production reports, not controlled benchmarks on underground beats. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **BPM accuracy on trap/lo-fi in practice:** The 85-95% accuracy estimate comes from StemSplit's production data on pop/rock/electronic. Underground producer beats may skew harder toward half-time patterns. The half-time display mitigates severity, but actual error rate on this genre mix is unknown until tested in Phase 1.
- **yt-dlp success rate on target hosting IP:** Failure rate estimates (10-20%) are based on community reports from PaaS. Actual rate on a dedicated Hetzner VPS is likely better but unknown until Phase 1 is run from that environment. This is the most important gap to validate first.
- **Celery vs. BackgroundTasks:** STACK.md and ARCHITECTURE.md give mildly conflicting guidance (STACK recommends BackgroundTasks for simplicity; ARCHITECTURE recommends Celery for correctness). Resolution: use Celery from the start. librosa's CPU-bound NumPy work makes BackgroundTasks a false economy — the first time 3 users submit simultaneously, the API goes unresponsive. The operational overhead of Redis is worth it.
- **Legal posture at scale:** At underground community scale the practical risk is IP blocking, not lawsuits. If the app grows significantly, DMCA §1201 exposure from bypassing YouTube's technical measures warrants a lawyer's review.

---

## Sources

### Primary (HIGH confidence)
- [yt-dlp GitHub repository + wiki](https://github.com/yt-dlp/yt-dlp) — download options, PO Token guide, bot detection issues
- [FastAPI documentation](https://fastapi.tiangolo.com/tutorial/background-tasks/) — BackgroundTasks, StreamingResponse
- [librosa 0.11 documentation](https://librosa.org/doc/0.11.0/beat.html) — beat_track, tempo, chroma_cqt
- [Essentia algorithm reference](https://essentia.upf.edu/reference/std_KeyExtractor.html) — KeyExtractor, RhythmExtractor2013
- [TuneReveal source code](https://github.com/duardodev/tunereveal) — competitor feature verification
- [DMCA ruling on third-party YouTube downloads — MediaNama 2026](https://www.medianama.com/2026/02/223-dmca-ruling-third-party-youtube-downloads-legal-risks-creators/)

### Secondary (MEDIUM confidence)
- [StemSplit BPM/key detection blog (2025)](https://stemsplit.io/blog/bpm-key-detection-feature) — accuracy estimates (85-95%) for pop/rock/electronic
- [Celery + Redis + FastAPI production guide 2025](https://medium.com/@dewasheesh.rana/celery-redis-fastapi-the-ultimate-2025-production-guide-broker-vs-backend-explained-5b84ef508fa7) — architecture validation
- [6 Ways to Get YouTube Cookies for yt-dlp in 2026](https://dev.to/osovsky/6-ways-to-get-youtube-cookies-for-yt-dlp-in-2026-only-1-works-2cnb) — cookie/PO Token mitigation strategy
- [fastapi-limiter library](https://github.com/long2ice/fastapi-limiter) — rate limiting implementation
- [Camelot Wheel Guide — DJ.Studio](https://dj.studio/blog/camelot-wheel) — notation standard for producers
- [Trap BPM guide — Producer Fury](https://producerfury.com/resources/trap-bpm-guide) — half-time pattern behavior

### Tertiary (LOW confidence)
- [BPM Finder Tunebat Alternative Benchmark](https://bpm-finder.net/posts/tunebat-bpm-alternative) — single-source benchmark; treat as directional only
- [YouTube Proxy — Prevent Server IP Blocks](https://proxy001.com/blog/youtube-proxy-prevent-server-ip-blocks-after-deploying-yt-dlp-style-server-workloads) — residential vs. datacenter success rate estimates

---

*Research completed: 2026-04-29*
*Ready for roadmap: yes*
