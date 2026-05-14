# Pitfalls: YouTube Download on Datacenter IPs with yt-dlp

**Domain:** YouTube download pipeline on Railway PaaS (datacenter IP)
**Researched:** 2026-05-10
**Context:** SoundGrabber v1.2 — fixing yt-dlp pipeline on Railway

---

## Summary

YouTube's anti-bot countermeasures have intensified significantly through 2025-2026. Three overlapping crises compound each other on datacenter IPs: (1) cookies now expire every 2 weeks instead of months, and Chrome-extracted cookies no longer work at all since July 2024; (2) the `web` client is being pushed onto SABR-only streaming, progressively stripping away standard HTTPS DASH audio formats that yt-dlp historically relied on; and (3) the `android` client — currently the most reliable fallback for datacenter IPs without PO tokens — is still functional but YouTube is actively deprecating `android_sdkless`, making the medium-term picture uncertain.

The team has already encountered nsig failures, bot detection, format unavailability, and ffprobe path issues. The research below maps each of these into a structured failure taxonomy with specific prevention strategies. The most critical risk going forward is the "silent failure" mode: expired cookies do not produce clear errors — downloads either return garbled content or silently fall back to lower-quality formats with no exception raised.

---

## Critical Pitfalls (P0)

These cause silent data corruption or complete production outages with no obvious error.

---

### P0-01: Cookie Expiration — Silent Failure, Not Clear Error

**What goes wrong:**
YouTube session cookies (Netscape-format `cookies.txt`) expire approximately every 2 weeks. When they expire on a datacenter IP, yt-dlp does not raise a clean exception. Instead, one of three things happens silently:
- The request proceeds unauthenticated and hits the bot-detection wall ("Sign in to confirm you're not a bot")
- The authenticated session is demoted: fewer formats are returned (10 instead of 29+)
- The download appears to complete but returns garbled content

There is a documented case where YouTube returned "too many requests" with no error message at all and yt-dlp exited zero. The WAV file in /tmp would exist but contain invalid audio, which pipeline.py's `validate_wav` would catch — but only if the `duration < 1.0s` check triggers.

**Why it happens:**
YouTube binds session cookies to IP reputation. Datacenter IPs are flagged higher-risk (~9% bot-detection rate vs <1% for residential IPs), so cookies bound to those IPs are rotated more aggressively. Previous behavior was ~1 month expiry; current behavior is 2 weeks or faster.

Chrome cookies cannot be used at all since July 2024 (app-bound encryption in Chrome 127+). Only Firefox cookies remain viable.

**Consequences:**
- Production breaks silently every ~2 weeks with no monitoring alert
- `validate_wav` may catch the symptom (corrupted file) but the error message points to the wrong cause
- Users see "download failed" with internal errors referencing ffprobe, not cookie expiry

**Prevention:**
1. Add a `cookies_health_check()` function that calls yt-dlp with `skip_download=True` on a known short public video and verifies the returned format count is above a minimum threshold (>5 formats). Run this at service startup.
2. Store cookie creation timestamp as an env var or Railway variable. Alert (log CRITICAL level) if `now - cookie_created_at > 10 days`.
3. Document the refresh procedure in a RUNBOOK: open Firefox on local machine, visit youtube.com, close Firefox, export via `yt-dlp --cookies-from-browser firefox --skip-download <any-url> --cookies /path/to/cookies.txt`.

**Detection:**
- Format count drops below threshold in health check
- `validate_wav` raises `ValueError` with duration < 1.0s on a successful yt-dlp exit
- Sentry/log spike on `RuntimeError: yt-dlp failed` with "Sign in to confirm"

**Confidence:** HIGH — Multiple GitHub issues (#13964, #8227) and 2026 community reports confirm 2-week expiry window.

---

### P0-02: SABR Streaming — Web Client Losing HTTPS Audio Formats

**What goes wrong:**
YouTube is progressively rolling out SABR (Server-side Adaptive Bitrate), a proprietary streaming protocol that replaces standard HTTPS DASH `adaptiveFormats`. When SABR is forced, the `web` client returns zero audio-only HTTPS formats. yt-dlp falls back to muxed HLS formats (format IDs 91-96) or progressive format 18 — these are lower-quality, and format 18 is 360p video+audio, not audio-only.

The symptom on the `web` client is the warning:
```
Some web client https formats have been skipped as they are missing a url.
YouTube is forcing SABR streaming for this client.
```

This is a WARNING, not an error. yt-dlp continues and selects the fallback format silently. The resulting WAV will be PCM-encoded audio transcoded from a 128kbps muxed stream instead of from 160kbps Opus (format 251) — quality degradation without any exception.

**Why it happens:**
YouTube is phasing out DASH adaptive streaming URLs in `web` client responses in favor of SABR, which requires a live session to stream and cannot be downloaded in chunks. As of yt-dlp 2026.03.03, `web` client no longer shows DASH audio-only formats for many videos.

**Consequences:**
- Producers receive lower-quality WAV (muxed stream source vs DASH audio-only source)
- No error raised; pipeline considers it a success
- Quality difference: format 251 (Opus 160kbps, 48kHz) vs format 18 (AAC 128kbps, muxed)

**Prevention:**
1. Use `android` client as primary, not `web`. The android sdkless player still returns standard HTTPS DASH audio formats (including format 251, Opus 160kbps) as of 2026.
2. Add format validation after download: check that `validate_wav` returns `duration > 5.0s` AND log the source format ID if accessible.
3. Do not rely on `bestaudio/best` to select a high-quality audio-only stream when `web` client is active — SABR will silently degrade it.

**Detection:**
- Warning string "YouTube is forcing SABR streaming" in yt-dlp output (requires `quiet=False` or log capture)
- Result WAV file size unexpectedly small for the video duration
- Format ID in yt-dlp verbose output is 18 or 91-96 instead of 251/140/249

**Confidence:** HIGH — Documented in yt-dlp issues #12482, #16128, #13968 with exact version regression (2025.12.08 vs 2026.03.03).

---

### P0-03: bgutil as Single Point of Failure

**What goes wrong:**
If bgutil is deployed as a separate Railway service and it crashes, becomes OOMed, or is deleted (as happened in the v1.1 incident at 23:39), the entire pipeline fails for `web` client flows. The `pipeline.py` code falls back to `android` when `bgutil_base_url` is empty, but if the config still points to a dead bgutil URL, the `web` client is attempted with an unreachable token provider — yt-dlp then hangs on the HTTP request to bgutil with a connection timeout.

The TypeScript/Node.js version of bgutil has a documented memory leak: ~25MB of RSS growth per request (V8 isolate not disposed). After ~100 requests, the service reaches 2.5GB RSS and on Railway's free tier (512MB container limit) is OOM-killed. This matches the team's observation.

**Why it happens:**
The `bgutil-ytdlp-pot-provider` TypeScript implementation creates a new `BotGuardClient` per request. Each client spawns a V8 isolate that is never properly disposed. The Rust rewrite (`jim60105/bgutil-ytdlp-pot-provider-rs`) fixes this with a single persistent worker thread, stable at ~80MB baseline with zero growth per request.

**Consequences:**
- Complete pipeline failure for all `web` client requests
- Timeout instead of fast-fail (yt-dlp waits for bgutil HTTP response)
- No automatic recovery without manual intervention or Railway auto-restart

**Prevention:**
1. If deploying bgutil, use the **Rust image** (`jim60105/bgutil-pot`) not the TypeScript one. Startup time: ~100ms vs ~800ms; memory: stable 80MB vs leaking 25MB/request.
2. Add a `socket_timeout` on bgutil requests specifically, or set `bgutil_base_url=""` as fallback when bgutil is unreachable (health check at startup).
3. Implement a Railway health check for the bgutil service with `railway.toml` restart policy.
4. Consider whether bgutil is worth the operational complexity — `android` client with cookies works without bgutil and has no SABR issue.

**Detection:**
- Pipeline timeout at `extract_info` step rather than download step
- Railway memory metrics for bgutil service approaching container limit
- Error: `Failed to connect to bgutil` in yt-dlp verbose output

**Confidence:** HIGH — Memory leak confirmed in bgutil-ytdlp-pot-provider-rs DeepWiki migration doc. Single-point-of-failure confirmed by team's own incident log.

---

## High Severity Pitfalls (P1)

These cause hard production errors that are diagnosable but require intervention.

---

### P1-01: nsig Extraction Failure — Throttled Formats, Not Clean Error

**What goes wrong:**
YouTube periodically updates the JavaScript obfuscation of its player (`base.js`). When the update changes the function name or structure of the `n` parameter decoder, yt-dlp's nsig extractor fails with:
```
WARNING: [youtube] <video_id>: nsig extraction failed: Some formats may be missing
```

This is a WARNING, not an error. yt-dlp continues using the "generic n function search" fallback. The result: some format URLs cannot be unthrottled. Download speed drops from several MB/s to ~50KB/s (YouTube throttles requests with invalid `n` parameters). For a 10-minute beat at 160kbps, this increases download time from ~1s to ~4 minutes — triggering the Celery task timeout.

**Why it happens:**
The nsig function in `base.js` is re-obfuscated with each YouTube player rollout. yt-dlp must be updated to recognize the new pattern. Fix timeline is typically 1-7 days after YouTube's player update. The team experienced this with yt-dlp pinned at 2024.12.03, which lacked the fix that landed in 2025.x releases.

**Consequences:**
- Downloads don't fail immediately — they appear to start but take 5-10x longer
- If Celery task has a `time_limit`, the job times out and the WAV is not produced
- Timed-out partial files in /tmp are not cleaned up unless the `try/finally` in `pipeline.py` runs

**Prevention:**
1. Pin yt-dlp version to the latest stable release in `requirements.txt`. Do not pin to a version older than the current quarter.
2. In Railway deployment, always rebuild the image on deploy (do not use cached pip layers for yt-dlp specifically).
3. Log yt-dlp warnings to a captured stream: set `quiet=False` but redirect to a captured logger, and treat nsig warnings as a monitoring signal.
4. Set Celery `soft_time_limit` at 120s to raise `SoftTimeLimitExceeded` before the hard kill, allowing cleanup code to run.

**Detection:**
- Download step takes >60s for a 3-minute video
- Log contains "nsig extraction failed" WARNING
- `validate_wav` raises FileNotFoundError if Celery timed out during download

**Confidence:** HIGH — Confirmed by team's own production encounter (2024.12.03 vs 2026.3.17 behavior difference). GitHub issues #14707, #10455, #13249 document the pattern.

---

### P1-02: ffprobe Binary Resolution — PATH vs imageio-ffmpeg Mismatch

**What goes wrong:**
`pipeline.py` resolves ffprobe as `Path(_FFMPEG_PATH).parent / "ffprobe"`. `_FFMPEG_PATH` comes from `imageio_ffmpeg.get_ffmpeg_exe()`, which returns the path to a bundled ffmpeg binary. The bundled binary's parent directory does NOT include a bundled `ffprobe` binary — imageio-ffmpeg bundles only `ffmpeg`, not `ffprobe`.

The constructed path resolves to a file that does not exist. `validate_wav` then catches `FileNotFoundError` and re-raises as `ValueError("ffprobe binary not found on PATH...")` — misleading, because PATH is not the issue.

This was the exact failure mode in the team's production incident: "download succeeded but ffprobe step failed because binary wasn't accessible."

**Why it happens:**
imageio-ffmpeg ships only the `ffmpeg` binary, not `ffprobe`. The assumption `ffprobe` lives next to `ffmpeg` is only true for system-installed FFmpeg (`/usr/bin/ffmpeg` → `/usr/bin/ffprobe`), not for bundled binary packages.

**Consequences:**
- Every successful download fails at the `validate_wav` step
- Users receive `internal_error` despite the WAV file being valid
- WAV files accumulate in /tmp because cleanup only runs on `YoutubeDLError`, not on `ValueError` from `validate_wav`

**Prevention:**
1. Do not derive `_FFPROBE_PATH` from `_FFMPEG_PATH` parent alone. Use two independent resolution strategies:
   ```python
   import shutil
   _FFPROBE_PATH = shutil.which("ffprobe") or str(Path(_FFMPEG_PATH).parent / "ffprobe")
   ```
2. At startup (not at call time), verify the resolved binary actually exists:
   ```python
   if not Path(_FFPROBE_PATH).exists():
       raise RuntimeError(f"ffprobe not found at {_FFPROBE_PATH}. Install system ffmpeg.")
   ```
3. In Railway Nixpacks config, explicitly install the `ffmpeg` system package (which includes `ffprobe`). Do not rely solely on imageio-ffmpeg for production.

**Detection:**
- `validate_wav` raises `ValueError` with "ffprobe binary not found"
- Subprocess `FileNotFoundError` in `validate_wav`
- /tmp accumulating `sg_*.wav` files (cleanup not triggered)

**Confidence:** HIGH — Direct match to team's production incident description.

---

### P1-03: extractor_args Format — List of Strings, Not Nested Dict

**What goes wrong:**
yt-dlp's `extractor_args` option requires the Python API format `{"youtube": ["player_client=android"]}` (list of strings). Using a nested dict (`{"youtube": {"player_client": "android"}}`) silently produces "Requested format is not available" — yt-dlp receives the option but cannot parse it, falls back to default web client, which then hits SABR or bot detection.

**Why it happens:**
yt-dlp's internal parser for `extractor_args` expects the `=`-delimited string list format. Nested dicts are not documented as valid; yt-dlp issue #14307 explicitly states the list format is required.

**Consequences:**
- `android` client is never actually used — the option is silently ignored
- Pipeline falls back to web client behavior (SABR, bot detection)
- Error message "Requested format is not available" does not mention extractor_args

**Prevention:**
The current `pipeline.py` already uses the correct format: `{"youtube": [f"player_client={dl_player}"]}`. Do not change this. Any future addition of extractor_args must use the same list-of-strings pattern.

**Detection:**
- "Requested format is not available" error
- Verbose output shows web client being used despite `android` in config

**Confidence:** HIGH — Confirmed by yt-dlp issue #14307; already documented as a comment in `pipeline.py`.

---

### P1-04: outtmpl Without %(ext)s — Postprocessor Filename Confusion

**What goes wrong:**
The current `pipeline.py` sets `outtmpl` to `outtmpl_base` (no extension), relying on the `FFmpegExtractAudio` postprocessor to append `.wav`. This works in the happy path. However, yt-dlp issue #15327 (December 2025) documents that when an audio-only format is selected and `outtmpl` lacks `%(ext)s`, the FFmpeg postprocessor cannot determine the intermediate format and raises:
```
Unable to choose an output format for 'file:sg_abc123.temp'; use a standard extension
```

This failure mode is triggered specifically when yt-dlp selects an audio-only format (e.g., format 251, webm/Opus) as the intermediate download before WAV conversion. It does NOT trigger for muxed formats. If YouTube's format selection moves exclusively to audio-only (the desired quality behavior), this bug becomes active.

**Why it happens:**
yt-dlp's postprocessor pipeline uses the outtmpl extension to determine the intermediate container format before transcoding. With no extension, the heuristic fails for audio-only containers.

**Consequences:**
- RuntimeError in postprocessor step; WAV not produced
- Partial `.temp` file left in /tmp (not cleaned by the current `suffix != ".wav"` filter)

**Prevention:**
Change `outtmpl` to include `%(ext)s`, then recover the final `.wav` path explicitly:
```python
outtmpl = str(WAV_TMP_DIR / f"{TMP_PREFIX}{wav_id}.%(ext)s")
# After download, find the .wav:
candidates = list(WAV_TMP_DIR.glob(f"{TMP_PREFIX}{wav_id}*.wav"))
```
The current `download_audio` already has the `candidates` fallback — this prevention strengthens it.

**Detection:**
- RuntimeError from yt-dlp containing "Unable to choose an output format"
- `.temp` files in /tmp matching `sg_*` that are not `.wav`

**Confidence:** MEDIUM — Issue #15327 confirms this pattern for audio-only formats; current code works but is fragile against format selection changes.

---

### P1-05: Railway Ephemeral /tmp — Partial Files on Container Restart

**What goes wrong:**
Railway containers have ephemeral storage (1GB on free tier, 100GB on paid). When a container restarts mid-download — due to deploy, OOM, or Railway infrastructure event — partial `.part` files and non-.wav intermediates from yt-dlp remain in /tmp on the next container boot. On free tier, two concurrent interrupted downloads of 15-minute videos can exhaust the 1GB limit before cleanup runs.

**Why it happens:**
yt-dlp writes intermediate `.part` files during download. The `try/finally` cleanup in `pipeline.py` only runs within the same process lifetime. Container restart kills the process before finally executes.

**Consequences:**
- Disk exhaustion causes Railway to forcibly stop and redeploy the service
- Users see 503 during the redeploy window

**Prevention:**
1. Add a startup sweep in `api/main.py` at app init:
   ```python
   import time
   for f in Path("/tmp").glob("sg_*"):
       if f.stat().st_mtime < time.time() - 3600:  # older than 1 hour
           f.unlink(missing_ok=True)
   ```
2. Set Celery task `time_limit=300` (5 min) and `soft_time_limit=240`. The `SoftTimeLimitExceeded` exception allows cleanup code to run before hard kill.
3. Prefer Railway paid tier or monitor disk usage via health check.

**Detection:**
- `/tmp` usage approaching Railway's ephemeral limit
- Jobs failing with `FileNotFoundError` on files that should not exist

**Confidence:** HIGH — Railway docs confirm ephemeral storage is wiped on redeploy. yt-dlp issue #11674 confirms partial file accumulation is a known operational problem.

---

## Medium Severity Pitfalls (P2)

These cause degraded behavior, increased operational costs, or friction but do not cause immediate data loss.

---

### P2-01: PO Token Lifetime — Short and Session-Bound

**What goes wrong:**
PO Tokens generated by bgutil have a default cache TTL of 6 hours (configurable via `TOKEN_TTL` env var). The actual token validity may be shorter — some reports indicate 12 hours, others suggest they can last several months — but behavior is highly dependent on whether the token is session-bound or video-bound.

If a PO Token expires mid-download (during a 15-minute video download that takes 30-60 seconds), the download may partially fail or silently degrade. yt-dlp does not retry with a fresh token mid-stream.

**Prevention:**
1. Regenerate PO Token before each job rather than caching across requests when bgutil is available. The Rust bgutil generates tokens in ~100ms.
2. If caching, set `TOKEN_TTL=1` (1 hour) rather than the 6-hour default.
3. Treat PO Token unavailability as a fallback condition, not a hard error — android client without PO token is the default path.

**Confidence:** MEDIUM — PO Token lifetime documentation is contradictory across sources.

---

### P2-02: YouTube Rate Limiting on Datacenter IPs

**What goes wrong:**
YouTube applies more aggressive rate limiting to datacenter IP ranges. Community reports indicate:
- A single IP downloading >50-100 videos/hour starts seeing elevated bot-detection rates
- `--fragment-retries 10` (yt-dlp default) on a broken connection triggers rapid retries that can temporarily block the IP for up to 1 hour
- The block manifests as 403 errors on fragment URLs, not on the initial request — yt-dlp may have already selected formats and started downloading when the block hits

All SoundGrabber users share the same Railway egress IP, so multiple concurrent users compound the request rate from YouTube's perspective.

**Prevention:**
1. Add `"fragment_retries": 3` to yt-dlp options (lower than the default 10).
2. Add Celery rate limiting: `@shared_task(rate_limit="10/m")` to cap concurrent download rate.
3. The existing application-level rate limiting (3/min per IP) helps but all users share the same Railway egress IP for the outbound YouTube requests.

**Confidence:** MEDIUM — GitHub issue #15899 confirms fragment retries trigger IP bans; exact threshold unverified.

---

### P2-03: Android Client Deprecation Risk (Medium-Term)

**What goes wrong:**
YouTube is actively deprecating `android_sdkless` (the client variant that most yt-dlp datacenter workflows relied on). Multiple 2026 reports note that `android_vr` returns `UNPLAYABLE` for some videos. The standard `android` client (non-vr, non-sdkless) is still functional as of the research date, but the trend is toward SABR enforcement across all clients.

**Prevention:**
1. Monitor yt-dlp release notes for android client deprecation notices.
2. Have a tested fallback sequence: `android` → `mweb` → `web` (with bgutil). `mweb` currently still returns HTTPS formats.
3. Pin a specific `player_client` in config rather than relying on yt-dlp's default client selection, so yt-dlp version changes do not silently change the client used.

**Confidence:** MEDIUM — Issue #16128 documents 2026.03.03 regression for android_vr; standard android client still works.

---

### P2-04: Chrome Cookies — Silently Invalid Since July 2024

**What goes wrong:**
Chrome 127+ introduced app-bound encryption for cookie storage. Any `cookies.txt` exported from Chrome after July 2024 is invalid — the encrypted values cannot be decoded outside the Chrome binary. yt-dlp will load the file without error (it is syntactically valid Netscape format) but the cookie values are garbage, providing no authentication benefit. The download then proceeds as unauthenticated on a datacenter IP, guaranteed to hit bot detection.

**Prevention:**
1. Always export cookies from Firefox. Chrome-exported cookies look valid but provide no auth.
2. Add a sanity check: the exported `cookies.txt` must contain `youtube.com` entries with `__Secure-3PSID` cookie present. If missing, fail fast with a config error at startup.

**Confidence:** HIGH — Confirmed by multiple 2026 sources and Chrome security release notes.

---

### P2-05: Concurrent Workers Sharing /tmp — Orphaned Partial Files

**What goes wrong:**
Multiple Celery workers share the same `/tmp` directory. If a worker crashes mid-job and is retried, the retry creates a new UUID and the first partial file is never cleaned. The `finally` block in `download_audio` only cleans up based on its own `wav_id`. Orphaned files from crashed workers accumulate.

**Prevention:**
Use the startup sweep from P1-05. Additionally, deduplicate jobs at the API layer: before enqueuing a Celery task, check Redis for an existing in-progress job for the same YouTube video ID (extracted from URL). Return the existing job ID rather than creating a duplicate.

**Confidence:** MEDIUM — Standard concurrency pattern; inherent in current architecture.

---

## ARM / Raspberry Pi 3B Pitfalls (P-ARM)

These pitfalls are specific to migrating the stack from Railway x86 to Raspberry Pi 3B (ARM Cortex-A53, 1GB RAM). They are **additive** to the pitfalls above — all of the railway pitfalls still apply.

---

### P-ARM-01: numba/llvmlite — The Librosa ARM Dependency That Breaks Everything

**Severity:** CRITICAL

**What goes wrong:**
librosa uses numba (a JIT compiler) for performance-critical paths including beat tracking. numba depends on llvmlite, which requires a matching LLVM installation. On ARM/Raspberry Pi, this creates a multi-layer dependency failure:

- PyPI does not ship `manylinux` wheels for `armv7l` or `aarch64` for numba/llvmlite
- piwheels provides prebuilt wheels for Raspberry Pi OS (32-bit armv7l) but these are the *32-bit Raspbian OS* wheels, not Docker-compatible Linux wheels
- Inside a Docker container using a generic `arm32v7/python:3.11` base image, pip will attempt to compile numba from source
- Source compilation requires a matching LLVM C++ toolchain version; getting version compatibility right between LLVM, llvmlite, and numba on ARM is a known multi-hour debugging exercise

The failure modes are layered:
1. `pip install librosa` inside the ARM Docker container triggers C compilation of numba/llvmlite
2. If LLVM apt package version mismatches what llvmlite expects, build fails with a cryptic C++ linker error
3. Even if llvmlite builds, importing librosa can trigger `LLVM ERROR: inconsistency in registered CommandLine options` — a fatal process abort
4. If `--no-deps librosa` is used to skip numba, librosa falls back to pure-Python implementations of beat tracking, which are 10-100x slower

**Why it happens:**
numba/llvmlite is not just a Python dependency — it embeds LLVM bitcode and compiles machine code at runtime. The ARM ISA support in older numba builds is incomplete. The conda-forge aarch64 build of numba exists (and works), but pip-installable ARM wheels do not exist as of 2026.

**Consequences:**
- Docker build fails entirely, blocking the entire deployment
- Or: Docker build succeeds but librosa silently falls back to slow pure-Python paths
- Or: `import librosa` crashes the Celery worker process on first import
- Silent fallback means BPM/key detection takes 45-90 seconds per track on Cortex-A53 vs 2-5s on Railway x86

**Prevention:**
1. **Option A (Recommended): Use Raspberry Pi OS 64-bit + arm64v8 Docker image.** Run `uname -m` on the Pi — if it shows `aarch64`, the OS is 64-bit. Use `FROM python:3.11-slim` with `--platform linux/arm64`. numba provides conda-forge aarch64 wheels; piwheels is working on aarch64 support as of 2025.
2. **Option B: Install via system packages instead of pip inside Docker.** `apt-get install python3-librosa python3-numba` inside the container uses Debian-packaged wheels that are compiled for the target architecture. Version will lag PyPI but avoids the wheel gap.
3. **Option C: Skip numba entirely.** Install librosa with `pip install librosa[display] --no-deps` then install all other deps individually except numba. librosa will work without JIT acceleration. Set `NUMBA_DISABLE_JIT=1` environment variable. BPM and key detection still work, just slower (acceptable if concurrency is capped at 1).
4. **Option D: conda/mamba.** Use a `continuumio/miniconda3` ARM base image. conda-forge has prebuilt numba for aarch64. This adds ~500MB to the image but eliminates the build complexity.

**Validation test:**
```bash
docker run --rm --platform linux/arm64 python:3.11-slim \
  python -c "import librosa; y, sr = librosa.load(librosa.ex('trumpet')); print(librosa.beat.beat_track(y=y, sr=sr))"
```
If this exits cleanly, the ARM librosa install is functional.

**Confidence:** HIGH — Confirmed by numba issue #6723, piwheels issue #50, librosa issue #1854, and multiple community reports through 2025.

---

### P-ARM-02: 1GB RAM — librosa OOM Kill With No Warning

**Severity:** CRITICAL

**What goes wrong:**
A single librosa analysis job on a 5-minute beat can consume 400-600MB of RAM during peak usage:
- `librosa.load()` with default sr=22050: 5 min × 22050 × 4 bytes (float32) = ~26MB audio buffer
- `librosa.beat.beat_track()` allocates intermediate spectrograms: 2-5x audio size in working memory (~130MB)
- `librosa.feature.chroma_cqt()` for key detection allocates separately: another 50-150MB
- `librosa.cqt()` internally: can spike to 400MB for a complex track

On 1GB RAM with the full stack running (Redis ~50MB, FastAPI ~80MB, Celery master ~50MB, Celery worker ~150MB at idle), the system has ~600MB free before the first job. A 5-minute beat analysis at peak allocation can exceed this. The Linux OOM Killer terminates the Celery worker process with no Python exception — the job simply disappears from the worker's perspective.

**Why it happens:**
numpy/scipy allocate large intermediate arrays during FFT operations. The CQT (Constant-Q Transform) for key detection is particularly memory-intensive because it performs multiple FFTs at different frequency resolutions. These allocations cannot be avoided with the current librosa API without switching to streaming analysis.

**Consequences:**
- Celery worker killed mid-analysis; WAV file exists but job stuck in `processing` state forever
- No exception raised; Redis job entry never transitions to `failed` or `done`
- Next reboot of the worker brings back a clean state, but the "stuck" job never resolves

**Prevention:**
1. **Hard cap on audio duration at load time:** `librosa.load(path, mono=True, sr=22050, duration=90)` — analyze only the first 90 seconds for BPM/key. For most beats, the first 90s contains all relevant musical information.
2. **Celery concurrency = 1:** Only one librosa analysis at a time. Default Celery spawns N workers = N CPU cores = 4 on Pi 3B. Four simultaneous analyses = guaranteed OOM.
   ```
   CELERY_WORKER_CONCURRENCY=1
   ```
3. **Add swap to the Pi:** `sudo dphys-swapfile` with CONF_SWAPSIZE=1024 (1GB swap on SD card). Swap on SD card is slow (~20 MB/s read) but prevents OOM kills. This trades OOM risk for slowdown. Set the Celery task `soft_time_limit` generously (180s) to tolerate swap thrashing.
4. **worker_max_memory_per_child:** Set `CELERY_WORKER_MAX_MEMORY_PER_CHILD=400000` (400MB in KB). Celery will recycle the worker process after a job if it used more than 400MB. This prevents memory fragmentation buildup across multiple jobs.
5. **Enable memory cgroup in Pi OS boot:** Without this, Docker's `--memory` flag is silently ignored. Add to `/boot/firmware/cmdline.txt`:
   ```
   cgroup_enable=memory cgroup_memory=1 swapaccount=1
   ```
   Then `docker-compose.yml` can enforce: `mem_limit: 600m` on the worker container.

**Confidence:** HIGH — Librosa issues #1286, #1385, #406 confirm memory growth patterns. Docker cgroup silent-ignore confirmed by dalwar23.com Raspberry Pi Docker memory documentation.

---

### P-ARM-03: CPU Time — librosa Takes 30-90s on Cortex-A53

**Severity:** HIGH

**What goes wrong:**
The Pi 3B's ARM Cortex-A53 at 1.2GHz is roughly 10-15x slower than a modern x86 server CPU for numpy/scipy FFT workloads. Without numba JIT (which may not be available — see P-ARM-01), librosa's beat tracking relies on pure-Python loops.

Estimated times on Cortex-A53 without numba:
- `librosa.load()` + resample: 8-15s for a 5-minute beat
- `librosa.beat.beat_track()`: 20-45s
- `librosa.feature.chroma_cqt()`: 15-30s
- Total analysis pipeline: 45-90 seconds per job

With the Celery task `soft_time_limit` currently set for Railway speeds (~30s), the Pi will time out on every analysis job.

**Why it happens:**
Railway runs on multi-core x86_64 with AVX2 SIMD instructions. numpy/scipy are compiled with AVX2 support on x86. On ARM, numpy is compiled with NEON SIMD, which is weaker per cycle. The Pi 3B's 1.2GHz clock is also significantly below server CPUs. There is no hardware acceleration path for pure FFT workloads on the Pi's GPU.

**Consequences:**
- All analysis jobs time out if `soft_time_limit` is not adjusted for ARM speed
- Users wait 60-90 seconds vs. the <30s target in the product requirements
- If `soft_time_limit` is not increased, `SoftTimeLimitExceeded` is raised during analysis, producing a WAV file with no BPM/key data

**Prevention:**
1. **Increase Celery timeouts for ARM:** `soft_time_limit=180, time_limit=240`
2. **Cap audio duration for analysis:** `duration=90` seconds in `librosa.load()` significantly reduces processing time without meaningful quality loss for BPM/key detection
3. **Use `hop_length=512` (the default) or larger:** A larger hop reduces the number of frames to analyze. For beat tracking on 90s of audio, hop_length=1024 is acceptable and halves processing time
4. **Profile the actual Pi performance** before setting timeouts: run a single analysis job manually and measure wall time before deploying

**Confidence:** MEDIUM — ARM vs x86 numpy benchmark data is not directly available for this specific workload; estimates from general SIMD performance comparisons and librosa community reports on slow machines.

---

### P-ARM-04: Docker Image Build Time — Hours on QEMU, Never on Pi Directly

**Severity:** HIGH

**What goes wrong:**
Building the Docker image on the Pi itself is not viable for this stack. `pip install numpy scipy librosa` on the Pi's CPU:
- Without prebuilt wheels (source compilation): 4-8 hours
- With piwheels or prebuilt ARM wheels: 15-30 minutes

Building via `docker buildx` from a laptop with QEMU arm32v7/arm64 emulation:
- QEMU emulation of ARM for C extension compilation: 45-90 minutes per build
- This is per build, meaning every `requirements.txt` change triggers a 45-90 minute CI cycle

Neither path is acceptable for iterative development.

**Why it happens:**
Docker's `buildx` for cross-platform builds uses QEMU binary translation when native ARM hardware is not available. QEMU is not hardware-level virtualization — it translates every instruction. For compute-heavy compilation (numpy, scipy involve significant C/Fortran compilation), QEMU overhead is 10-20x native speed.

**Consequences:**
- Each Dockerfile change during iteration takes 45-90 minutes to validate
- If CI/CD is set up on GitHub Actions with QEMU, every merge to main blocks for 90 minutes before deploy

**Prevention:**
1. **Build the image natively on the Pi.** SSH into the Pi, `docker build` runs natively in ARM. With piwheels integration via `--extra-index-url https://www.piwheels.org/simple`, prebuilt ARM wheels are fetched directly. Build time: 15-30 minutes. Painful but a one-time cost per requirements change.
2. **Separate the heavy dependencies from the app code.** Use a two-stage Dockerfile:
   - Stage 1 (`deps`): Install all Python packages. Tag and push this as `soundgrabber-deps:arm64-vX`. Only rebuilt when `requirements.txt` changes.
   - Stage 2 (`app`): `FROM soundgrabber-deps:arm64-vX`, copy app code. Rebuilt on every code change in seconds.
3. **Use GitHub Actions with native ARM runners.** GitHub has ARM64 runners (via `runs-on: ubuntu-24.04-arm`). Build there, push to GHCR, pull on Pi. No QEMU penalty.
4. **Do not use `--platform linux/arm/v7` in the `FROM` line** on a 64-bit Pi OS. Use `--platform linux/arm64` to avoid the 32-bit/64-bit mismatch that causes binary incompatibility.

**Confidence:** HIGH — QEMU overhead for ARM cross-compilation is well-documented across Docker community forums and the Photonix project build documentation.

---

### P-ARM-05: 32-bit vs 64-bit OS — Silent Binary Incompatibility

**Severity:** HIGH

**What goes wrong:**
The Raspberry Pi 3B's CPU (ARM Cortex-A53) is 64-bit capable. However, the default Raspberry Pi OS installation is **32-bit (armv7l)**. This creates a critical mismatch:

- The milestone context specifies `linux/arm/v7` (32-bit)
- If the Pi is actually running a 64-bit OS (Raspberry Pi OS 64-bit, or Ubuntu Server 64-bit), `arm/v7` Docker containers will fail to start with: `exec /usr/local/bin/python: exec format error`
- Conversely, if the Pi is 32-bit and a `linux/arm64` image is pulled, same error

Additionally, the Python package ecosystem has **better support for 64-bit ARM** than 32-bit:
- numba has conda-forge aarch64 wheels (no 32-bit ARM wheels)
- Many Python scientific packages stopped providing armv7 wheels after 2022
- piwheels supports 32-bit Raspbian but this only works when pip is invoked with piwheels as extra index AND the host is actually Raspbian (not Debian in Docker)

**Why it happens:**
`uname -m` on a Pi 3B with default OS returns `armv7l`. With 64-bit OS, it returns `aarch64`. The Docker `--platform` flag must match the running OS, not just the hardware capability. Mixing them produces the format error.

**Prevention:**
1. **Before writing any Dockerfile or compose file, determine the Pi's actual OS bitness:**
   ```bash
   ssh pi@<tailscale-ip> "uname -m && cat /etc/os-release | head -5"
   ```
2. **If the Pi is running 32-bit (armv7l):** Use `--platform linux/arm/v7` in docker-compose. Use piwheels as extra pip index. Expect numba/llvmlite issues.
3. **If the Pi is running 64-bit (aarch64):** Use `--platform linux/arm64`. Use conda-forge for numba. Better overall package support. **This is the recommended path** — if the Pi is currently on 32-bit, consider reinstalling with 64-bit OS before starting the Docker setup.
4. **If unsure, install Raspberry Pi OS 64-bit (bookworm)** from scratch. It supports Pi 3B as of the 2022 release. This is the cleaner starting point.

**Confidence:** HIGH — Docker exec format error is a direct consequence of platform mismatch; architecture detection is standard Linux tooling.

---

### P-ARM-06: SD Card Corruption — The Unattended Server's Silent Killer

**Severity:** HIGH

**What goes wrong:**
Consumer microSD cards have limited write endurance (typically 10,000-100,000 P/E cycles for TLC NAND). Docker + Celery + Redis on a Pi create an unusually write-heavy workload:
- Docker overlay2 writes layer diffs on every container start
- Redis AOF persistence writes continuously
- Celery task logs write on every job
- /tmp audio files write during every download

On a cheap microSD card (Class 10, 32GB TLC), the card can fail within months of continuous use. The failure mode is silent: the filesystem becomes read-only or corrupted, writes silently fail, and the application appears to run but produces no output. Diagnosis over SSH (no physical access) is extremely difficult because log writes may also be failing.

**Why it happens:**
Consumer SD cards optimize for sequential read speed (marked on the card). Random write endurance is not advertised but is 10-50x worse than sequential write endurance. Docker's overlay filesystem performs many small random writes. Running a Redis server with AOF enabled is particularly damaging.

**Consequences:**
- Application stops producing results silently (writes fail silently in many filesystems when the card goes read-only)
- SSH access may still work (reads succeed) but the application fails
- Recovery requires physical SD card access — impossible without physical access

**Prevention:**
1. **Use a high-endurance microSD card:** Samsung Endurance Pro, SanDisk High Endurance, Kingston Canvas Go Plus. These are designed for dashcam/surveillance use and have 10-40x better write endurance than consumer cards.
2. **Redis: disable AOF, use RDB snapshots only.** In `redis.conf`: `appendonly no`, `save 900 1 300 10 60 10000`. This dramatically reduces write frequency. For SoundGrabber (queue state, not persistent data), AOF durability is unnecessary.
3. **log2ram:** Install on the Pi host before Docker. Routes system log writes to a RAM disk (syncs to SD periodically on clean shutdown). Eliminates the majority of OS-level SD writes.
   ```bash
   echo "deb [signed-by=/usr/share/keyrings/azlux-archive-keyring.gpg] http://packages.azlux.fr/debian/ bookworm main" | sudo tee /etc/apt/sources.list.d/azlux.list
   sudo apt install log2ram
   ```
4. **Move /tmp to tmpfs (RAM disk):** Celery's audio temp files write to /tmp. Map /tmp to RAM in `/etc/fstab`:
   ```
   tmpfs /tmp tmpfs defaults,noatime,nosuid,size=300m 0 0
   ```
   This eliminates ALL /tmp SD writes. 300MB is sufficient for one queued job at a time.
5. **Docker volumes on external USB drive:** For production, move Docker's data root (`/var/lib/docker`) to a USB flash drive or SSD. USB drives have significantly better write endurance than microSD. Requires: `sudo systemctl stop docker`, edit `/etc/docker/daemon.json` to set `"data-root": "/mnt/usb/docker"`, move existing data.

**Confidence:** HIGH — SD card corruption on headless Pi servers is a well-documented failure mode. Hackaday and Raspberry Pi Forums have documented dozens of cases. log2ram and tmpfs are standard mitigations.

---

### P-ARM-07: Pi Freeze Without Physical Access — Recovery Protocol

**Severity:** HIGH

**What goes wrong:**
A Pi 3B running headless over Tailscale can become unrecoverable if:
- An OOM kill takes down the networking subsystem
- A kernel panic occurs (less common but real)
- The SD card filesystem becomes read-only mid-session
- A Docker container consumes all memory and the kernel hangs before OOM killer acts
- The Tailscale service itself OOMs and the Pi becomes unreachable

Without physical access, any of these produces a "disappeared" server. The Pi is plugged in, LED shows activity, but SSH via Tailscale returns "Connection refused" or times out. The only traditional recovery is a physical hard reset (power cycle). Without physical access, there is no recovery.

**Why it happens:**
The Pi 3B has no BMC (Baseboard Management Controller), IPMI, or out-of-band management interface. Unlike cloud VMs, there is no "force restart" button available remotely.

**Prevention:**
1. **Hardware watchdog (mandatory):** The Pi 3B has a built-in hardware watchdog timer. Enable it:
   ```bash
   # In /boot/firmware/config.txt (or /boot/config.txt on older Pi OS):
   dtparam=watchdog=on
   ```
   Then configure systemd to feed it:
   ```bash
   # /etc/systemd/system.conf
   RuntimeWatchdogSec=15
   ShutdownWatchdogSec=2min
   ```
   With this configured, if systemd stops responding for 15 seconds, the hardware watchdog triggers a hard reset. This handles kernel hangs and zombie states but NOT cases where systemd itself is running but the Pi is in a degraded state.

2. **Docker restart policies:** All containers must use `restart: unless-stopped` (not `restart: always`, which can create restart loops). This ensures containers come back after a watchdog reboot without manual intervention.

3. **Tailscale persistence:** Tailscale must be configured to start before Docker (it is a systemd service, dependency ordering matters). After a watchdog reboot, Tailscale must be available before Docker tries to start — otherwise Docker containers start with no network and the SSH entry point is gone.
   ```bash
   # Check Tailscale service starts before Docker:
   sudo systemctl cat docker | grep After  # should include tailscaled or network-online.target
   ```

4. **Test the full restart cycle before going live:** Pull the power on the Pi while containers are running. Confirm that after power restoration: (1) Pi boots, (2) Tailscale connects, (3) Docker containers start, (4) Application is accessible via Tailscale IP. This must be tested with physical access BEFORE deploying remotely.

5. **Monitoring ping:** Set up an external health check (free tier UptimeRobot, Better Stack, or a cron job from a separate machine via Tailscale) that pings `GET /health` every 5 minutes. Alert when it fails. Without this, a frozen Pi can go unnoticed for hours.

6. **Smart plug as last resort:** A remotely controllable smart plug (e.g., TP-Link Kasa, Shelly) on the Pi's power outlet provides a true "power cycle from anywhere" escape hatch. At $15-25, this is worth the investment for a headless production server.

**Confidence:** HIGH — Watchdog configuration verified via Raspberry Pi Forums. Docker restart policy behavior well-documented. Tailscale startup ordering is an operational requirement.

---

### P-ARM-08: Docker Memory Limits Silently Ignored Without cgroup Configuration

**Severity:** MEDIUM

**What goes wrong:**
On a fresh Raspberry Pi OS installation, Docker reports:
```
WARNING: No memory limit support
WARNING: No swap limit support
```

This means `mem_limit: 600m` in docker-compose.yml is silently ignored — the container can consume all available RAM. If the librosa worker (see P-ARM-02) needs to be hard-capped to prevent OOM killing the host, this cap does not work without explicit kernel configuration.

**Why it happens:**
Raspberry Pi OS does not enable memory cgroup by default to reduce boot overhead. Docker requires memory cgroups to enforce `--memory` limits.

**Prevention:**
Add these parameters to `/boot/firmware/cmdline.txt` (all on one line, space-separated):
```
cgroup_enable=memory cgroup_memory=1 swapaccount=1
```
Reboot. Verify with: `docker info 2>&1 | grep -i memory`

After this change, `mem_limit` in docker-compose works as expected. Set:
```yaml
worker:
  mem_limit: 600m
  memswap_limit: 900m  # 300m of swap allowed
```

**Confidence:** HIGH — dalwar23.com documents exact cmdline.txt change. Docker moby issue #35587 confirms cgroup memory warning means limits are ignored.

---

## Testing Strategy

### The Core Problem

Testing the YouTube download pipeline in CI without hitting real YouTube is necessary because:
1. Real YouTube requests from CI IP (GitHub Actions, etc.) hit bot detection almost immediately
2. Hitting real YouTube in CI constitutes a ToS risk at scale
3. CI failures due to YouTube-side changes would block all production deploys

### Layer 1: Unit Tests — Mock YoutubeDL at the Python Boundary

```python
# tests/test_pipeline_unit.py
from unittest.mock import patch, MagicMock
import pytest
import yt_dlp

def test_download_audio_bot_detection(tmp_path):
    """Verify bot detection error is wrapped in RuntimeError."""
    with patch("pipeline.yt_dlp.YoutubeDL") as MockYDL:
        instance = MockYDL.return_value.__enter__.return_value
        instance.download.side_effect = yt_dlp.utils.DownloadError(
            "Sign in to confirm you're not a bot"
        )
        with pytest.raises(RuntimeError, match="Sign in to confirm"):
            pipeline.download_audio(
                "https://youtube.com/watch?v=test",
                cookies_path=str(tmp_path / "cookies.txt"),
                po_token=""
            )

def test_download_audio_cleanup_on_failure(tmp_path):
    """Verify /tmp partial files are removed when yt-dlp raises."""
    partial = tmp_path / "sg_abc123abc123.part"
    partial.write_bytes(b"partial data")
    # ... mock uuid to return predictable id, verify partial is deleted
```

Cover these cases with mocks:
- Bot detection ("Sign in to confirm you're not a bot")
- Format unavailable ("Requested format is not available")
- Network timeout (`socket.timeout`)
- nsig warning logged (capture yt-dlp warning output)
- WAV file not found after successful yt-dlp exit (outtmpl edge case)

### Layer 2: Integration Tests — Local HTTP Server, No YouTube

Serve a real minimal WAV file over a local HTTP server (e.g., `pytest-localserver` or Python's `http.server`) and point yt-dlp at a direct URL — not YouTube — to verify the `convert_to_wav` + `analyze_audio` chain works end-to-end without any YouTube involvement. This tests ffprobe resolution, WAV validation, BPM/key detection, and file cleanup.

### Layer 3: Cookie Expiry Detection Test

```python
def test_cookies_file_is_recent():
    """Fail in staging if cookies.txt is older than 10 days."""
    cookies_path = Path(os.environ.get("YTDLP_COOKIES_FILE", ""))
    if not cookies_path.exists():
        pytest.skip("YTDLP_COOKIES_FILE not set — skipping in CI")
    age_days = (time.time() - cookies_path.stat().st_mtime) / 86400
    assert age_days < 10, (
        f"cookies.txt is {age_days:.1f} days old — YouTube cookies expire every ~14 days. "
        "Refresh: open Firefox, visit youtube.com, export cookies."
    )
```

### Layer 4: Canary Test — Real YouTube, Manually Triggered Only

Use a known-stable YouTube URL for nightly or manual CI runs. Do NOT run this in PR CI.

```python
@pytest.mark.canary
@pytest.mark.skipif(
    not os.environ.get("RUN_CANARY_TESTS"),
    reason="Canary tests hit real YouTube — run manually or nightly only"
)
def test_real_youtube_download():
    """End-to-end smoke test against real YouTube. Requires YTDLP_COOKIES_FILE."""
    ...
```

A suitable stable video: YouTube has multiple official short test videos under 60 seconds that have been stable for years. Any video from YouTube's own channel works; prefer one under 2 minutes to minimize download time.

### Layer 5: ARM-Specific Validation (New for v1.3)

Before declaring the Pi deployment complete, run these validations manually with physical SSH access:

```bash
# 1. Verify architecture matches the Docker platform
uname -m  # must match platform in docker-compose.yml (aarch64 or armv7l)

# 2. Verify memory cgroup is active
docker info 2>&1 | grep -i memory  # must NOT show WARNING

# 3. Verify librosa import does not crash
docker exec <worker-container> python -c "import librosa; print(librosa.__version__)"

# 4. Verify hardware watchdog is active
cat /proc/sys/kernel/watchdog  # should output 1

# 5. Benchmark analysis time on a real local file
# (Use a short WAV, measure wall time, confirm < soft_time_limit)
time docker exec <worker-container> python -c "
import librosa
y, sr = librosa.load('/tmp/test.wav', mono=True, sr=22050, duration=90)
tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
print('BPM:', tempo)
"

# 6. Test full restart cycle (do this before going headless)
docker compose down && sudo reboot
# Wait ~60s, then SSH back in and verify containers are running
docker compose ps
```

### What NOT to Do in Testing

- Do not commit a real `cookies.txt` to the repo (contains session tokens)
- Do not run yt-dlp against real YouTube in PR CI — this will eventually trigger a ban on the CI IP
- Do not mock at the ffmpeg/subprocess level for security tests — the security controls (chmod, path validation) must run against the real filesystem
- Do not test bgutil availability in unit tests — mock the `bgutil_base_url` parameter instead
- Do not skip the physical restart cycle test before going fully remote — once the Pi is headless over Tailscale, testing the reboot cycle requires physical access

---

## Prevention Checklist

### Existing Railway Pitfalls (carry forward)

**Cookie management:**
- [ ] Cookie export procedure documented in RUNBOOK (Firefox only, not Chrome)
- [ ] `cookies_health_check()` startup function added to `pipeline.py` or startup script
- [ ] Cookie age monitoring in startup logs (CRITICAL if >10 days)
- [ ] `.env.example` documents `YTDLP_COOKIES_FILE` must point to Firefox-exported cookies
- [ ] Cookies file validated at startup for `__Secure-3PSID` presence

**Client selection:**
- [ ] `android` client confirmed as default for both `check_duration` and `download_audio` (already done)
- [ ] `extractor_args` format uses list-of-strings (already correct in current code)
- [ ] No path where `web` client is selected without bgutil + PO token available

**Binary resolution:**
- [ ] `_FFPROBE_PATH` verified to exist at startup (not deferred to first call)
- [ ] System `ffmpeg` (includes `ffprobe`) installed in Dockerfile
- [ ] Resolution order: `shutil.which("ffprobe")` first, then imageio-ffmpeg parent path fallback

**File cleanup:**
- [ ] Startup sweep for orphaned `sg_*` files older than 1 hour
- [ ] `outtmpl` includes `%(ext)s` to prevent postprocessor confusion
- [ ] `.temp` and `.part` files included in cleanup glob (not just `suffix != ".wav"`)

**yt-dlp version:**
- [ ] `requirements.txt` pins yt-dlp to latest stable (not >3 months old)
- [ ] Docker rebuild does not use cached yt-dlp pip layer (add version bump or `--no-cache`)

**Rate limiting:**
- [ ] `fragment_retries` set to 3 in yt-dlp options (default 10 risks IP ban)
- [ ] Celery `rate_limit="10/m"` on the download task

### New ARM / Raspberry Pi Checklist (v1.3)

**Architecture verification (do first, before any code):**
- [ ] `uname -m` on Pi confirms actual architecture (aarch64 vs armv7l)
- [ ] Docker-compose `platform:` matches Pi OS bitness
- [ ] Decision made: 32-bit or 64-bit path (recommendation: 64-bit/aarch64)

**librosa/numba strategy:**
- [ ] Strategy chosen and documented: (A) arm64 + conda-forge numba, (B) system packages, (C) numba-free librosa, or (D) conda base image
- [ ] `import librosa` tested inside the target container before writing any application code
- [ ] `NUMBA_DISABLE_JIT=1` set if using Option C
- [ ] Analysis time benchmarked on Pi before setting task timeouts

**Memory management:**
- [ ] `CELERY_WORKER_CONCURRENCY=1` in Pi deployment config
- [ ] `librosa.load(..., duration=90)` cap implemented in `analyze_audio()`
- [ ] `CELERY_WORKER_MAX_MEMORY_PER_CHILD=400000` set
- [ ] `soft_time_limit=180, time_limit=240` for ARM speed
- [ ] Swap enabled on Pi host: `sudo dphys-swapfile` with 1GB
- [ ] `/tmp` mounted as tmpfs (RAM disk) in Pi's `/etc/fstab`

**Docker memory limits:**
- [ ] cgroup memory enabled in `/boot/firmware/cmdline.txt`
- [ ] Reboot confirmed, `docker info` shows no memory limit warnings
- [ ] `mem_limit: 600m` set on worker container in docker-compose.yml

**SD card protection:**
- [ ] High-endurance SD card in use (Samsung Endurance Pro or equivalent)
- [ ] Redis AOF disabled, RDB snapshots only
- [ ] log2ram installed and active on Pi host
- [ ] `/tmp` on tmpfs to eliminate audio file writes to SD card

**Unattended recovery:**
- [ ] Hardware watchdog enabled in `/boot/firmware/config.txt`
- [ ] systemd watchdog configured (RuntimeWatchdogSec=15)
- [ ] All Docker containers use `restart: unless-stopped`
- [ ] Tailscale starts before Docker in systemd order
- [ ] Physical restart cycle tested with SSH verification BEFORE going headless
- [ ] External health check (UptimeRobot or equivalent) monitoring `GET /health`
- [ ] Smart plug considered for power cycle recovery

**Testing:**
- [ ] ARM-specific validation script run and all checks pass
- [ ] Canary test run manually from Pi (real YouTube download)
- [ ] `tests/test_pipeline_unit.py` added with mocked YoutubeDL

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Cookie injection into pipeline | P0-01: Silent expiry | Add startup health check + age monitoring |
| Client type selection | P0-02: SABR on web | Always default to android; never default to web |
| bgutil integration | P0-03: Memory leak OOM | Use Rust image; add graceful fallback to android |
| ffprobe path resolution | P1-02: imageio-ffmpeg mismatch | Install system ffmpeg; startup verification |
| yt-dlp version management | P1-01: nsig breakage | Pin to latest; rebuild on deploy |
| outtmpl configuration | P1-04: Postprocessor confusion | Include %(ext)s in outtmpl |
| Pi /tmp cleanup | P1-05 variant: SD card + tmpfs | Mount /tmp as tmpfs; startup orphan sweep |
| Fragment download | P2-02: IP ban on retries | Set fragment_retries=3 |
| Chrome cookie export | P2-04: Invalid cookies | Enforce Firefox; validate __Secure-3PSID presence |
| ARM Docker setup | P-ARM-05: 32/64-bit mismatch | Check uname -m before writing Dockerfile |
| librosa installation | P-ARM-01: numba build failure | Choose strategy before first build; test import |
| Analysis job | P-ARM-02: OOM kill | concurrency=1; duration cap; swap enabled |
| Analysis job | P-ARM-03: CPU timeout | Increase soft_time_limit to 180s; benchmark first |
| Docker build | P-ARM-04: QEMU build time | Build natively on Pi; layer-split Dockerfile |
| SD card | P-ARM-06: Corruption | High-endurance card; log2ram; tmpfs for /tmp |
| Remote recovery | P-ARM-07: Pi freeze | Hardware watchdog; smart plug; pre-test restart cycle |
| Docker limits | P-ARM-08: cgroup silent ignore | Enable cgroup_enable=memory in cmdline.txt |

---

## Sources

### YouTube/yt-dlp (v1.2)
- [yt-dlp issue #13964: YouTube cookies expire in 3-5 days](https://github.com/yt-dlp/yt-dlp/issues/13964) — HIGH confidence
- [yt-dlp issue #16229: Cookies no longer working — SABR silent failure](https://github.com/yt-dlp/yt-dlp/issues/16229) — HIGH confidence
- [yt-dlp issue #16128: DASH audio formats missing in yt-dlp 2026.03.03](https://github.com/yt-dlp/yt-dlp/issues/16128) — HIGH confidence
- [yt-dlp issue #12482: web client SABR-only formats](https://github.com/yt-dlp/yt-dlp/issues/12482) — HIGH confidence
- [yt-dlp issue #14707: nsig extraction failure — fix in 2025.11.12+](https://github.com/yt-dlp/yt-dlp/issues/14707) — HIGH confidence
- [yt-dlp issue #15899: Fragment retries trigger IP ban](https://github.com/yt-dlp/yt-dlp/issues/15899) — MEDIUM confidence (closed as not-reproducible)
- [yt-dlp issue #15327: FFmpeg postprocessor outtmpl filename confusion (December 2025)](https://github.com/yt-dlp/yt-dlp/issues/15327) — MEDIUM confidence
- [yt-dlp issue #14307: extractor_args list-of-strings format requirement](https://github.com/yt-dlp/yt-dlp/issues/14307) — HIGH confidence
- [bgutil-ytdlp-pot-provider-rs DeepWiki: TypeScript vs Rust memory comparison](https://deepwiki.com/jim60105/bgutil-ytdlp-pot-provider-rs/6.3-migration-from-typescript-to-rust) — HIGH confidence
- [DEV Community: 6 Ways to Get YouTube Cookies in 2026 — Only 1 Works](https://dev.to/osovsky/6-ways-to-get-youtube-cookies-for-yt-dlp-in-2026-only-1-works-2cnb) — HIGH confidence
- [yt-dlp PO Token Guide (wiki)](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) — HIGH confidence
- [yt-dlp issue #11674: Temporary file cleanup on interrupted download](https://github.com/yt-dlp/yt-dlp/issues/11674) — HIGH confidence
- [yt-dlp issue #15689: android sdkless bypasses SABR at extraction but 403 on download](https://github.com/yt-dlp/yt-dlp/issues/15689) — MEDIUM confidence

### ARM / Raspberry Pi (v1.3)
- [numba issue #6723: RPi3 cannot install Numba due to LLVM toolchain mismatch](https://github.com/numba/numba/issues/6723) — HIGH confidence
- [piwheels issue #50: librosa failing to install on Raspberry Pi 3](https://github.com/piwheels/packages/issues/50) — HIGH confidence
- [librosa issue #1854: Running without numba](https://github.com/librosa/librosa/issues/1854) — HIGH confidence
- [librosa issue #1286: Memory usage growing with iterations](https://github.com/librosa/librosa/issues/1286) — HIGH confidence
- [librosa issue #406: Librosa in 128MB memory or less](https://github.com/librosa/librosa/issues/406) — HIGH confidence
- [Docker moby issue #35587: cgroups memory cgroup not supported](https://github.com/moby/moby/issues/35587) — HIGH confidence
- [Docker moby issue #46185: Can't use swap memory on docker Raspberry Pi OS](https://github.com/moby/moby/issues/46185) — HIGH confidence
- [dalwar23.com: How to Fix "No memory limit support" for Docker in Raspberry Pi](https://dalwar23.com/how-to-fix-no-memory-limit-support-for-docker-in-raspberry-pi/) — HIGH confidence
- [piwheels librosa page: version availability and Python 3.11 support](https://www.piwheels.org/project/librosa/) — HIGH confidence
- [Raspberry Pi Forums: watchdog package configuration](https://forums.raspberrypi.com/viewtopic.php?t=147501) — HIGH confidence
- [Hackaday: Raspberry Pi and the Story of SD Card Corruption](https://hackaday.com/2022/03/09/raspberry-pi-and-the-story-of-sd-card-corruption/) — HIGH confidence
- [Celery issue #2011: Celery worker hangs after OOM kill of subprocess](https://github.com/celery/celery/issues/2011) — HIGH confidence
- [Zapier Engineering: Decreasing RAM usage 40% with jemalloc](https://zapier.com/engineering/celery-python-jemalloc/) — MEDIUM confidence
- [Docker Docs: Multi-platform builds](https://docs.docker.com/build/building/multi-platform/) — HIGH confidence
- [DevGuide.dev: Keep Your Raspberry Pi Online — WiFi drops and SSH disconnects](https://devguide.dev/blog/raspberry-pi-stays-online) — MEDIUM confidence
