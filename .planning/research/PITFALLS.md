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

### What NOT to Do in Testing

- Do not commit a real `cookies.txt` to the repo (contains session tokens)
- Do not run yt-dlp against real YouTube in PR CI — this will eventually trigger a ban on the CI IP
- Do not mock at the ffmpeg/subprocess level for security tests — the security controls (chmod, path validation) must run against the real filesystem
- Do not test bgutil availability in unit tests — mock the `bgutil_base_url` parameter instead

---

## Prevention Checklist

For the v1.2 milestone before closing:

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
- [ ] System `ffmpeg` (includes `ffprobe`) installed in Railway Nixpacks/Dockerfile
- [ ] Resolution order: `shutil.which("ffprobe")` first, then imageio-ffmpeg parent path fallback

**File cleanup:**
- [ ] Startup sweep for orphaned `sg_*` files older than 1 hour
- [ ] `outtmpl` includes `%(ext)s` to prevent postprocessor confusion
- [ ] `.temp` and `.part` files included in cleanup glob (not just `suffix != ".wav"`)

**yt-dlp version:**
- [ ] `requirements.txt` pins yt-dlp to latest stable (not >3 months old)
- [ ] Railway redeploy does not use cached yt-dlp pip layer (add version bump or `--no-cache`)

**bgutil (if deployed):**
- [ ] Use Rust image (`jim60105/bgutil-pot`), not TypeScript image
- [ ] Railway restart policy configured for bgutil service
- [ ] Pipeline gracefully falls back to `android` client if bgutil unreachable (startup health check)

**Rate limiting:**
- [ ] `fragment_retries` set to 3 in yt-dlp options (default 10 risks IP ban)
- [ ] Celery `rate_limit="10/m"` on the download task

**Testing:**
- [ ] `tests/test_pipeline_unit.py` added with mocked YoutubeDL covering bot detection, format unavailable, and cleanup paths
- [ ] Cookie age test added with `pytest.mark.skipif` for CI
- [ ] Canary test marked `@pytest.mark.canary` and excluded from PR CI (gated by `RUN_CANARY_TESTS`)

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
| Railway /tmp cleanup | P1-05: Disk exhaustion | Startup orphan sweep |
| CI test pipeline | Testing: real YouTube hits | Mock YoutubeDL; canary tests gated |
| Fragment download | P2-02: IP ban on retries | Set fragment_retries=3 |
| Chrome cookie export | P2-04: Invalid cookies | Enforce Firefox; validate __Secure-3PSID presence |

---

## Sources

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
- [Railway Docs: Ephemeral storage limits](https://docs.railway.com/reference/services) — HIGH confidence
- [yt-dlp issue #15689: android sdkless bypasses SABR at extraction but 403 on download](https://github.com/yt-dlp/yt-dlp/issues/15689) — MEDIUM confidence
- [yt-dlp issue #11674: Temporary file cleanup on interrupted download](https://github.com/yt-dlp/yt-dlp/issues/11674) — HIGH confidence
