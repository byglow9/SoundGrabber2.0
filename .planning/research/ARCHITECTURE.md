# Architecture: Resilient YouTube Download Pipeline on Railway

**Project:** SoundGrabber v1.2 — YouTube Pipeline Fix
**Researched:** 2026-05-10
**Confidence:** MEDIUM — core integration patterns verified; some yt-dlp client behavior is LOW confidence due to rapid YouTube-side changes

---

## Summary

The current pipeline works end-to-end locally but fails on Railway datacenter IPs due to three independent problems: (1) no PO Token provider running, (2) ffprobe not found because `imageio_ffmpeg.get_ffmpeg_exe()` returns a file path but yt-dlp's `ffmpeg_location` option expects a directory, and (3) the `android` client does not reliably produce formats on datacenter IPs without a PO Token. The fix requires deploying bgutil as a separate Railway service, correcting the `ffmpeg_location` value, and adopting `web` client backed by bgutil's PO tokens as the primary strategy with a fallback chain for resilience.

---

## Current Architecture

```
Railway Project
├── web-service         (FastAPI + Uvicorn — api/main.py)
│   └── lifespan        → decode YTDLP_COOKIES_B64 → /tmp/sg_cookies.txt
│                       → start wav-sweeper daemon thread
├── celery-worker       (Celery — api/tasks.py)
│   └── process_job()
│       ├── check_duration()    → yt-dlp metadata fetch, no download
│       ├── download_audio()    → yt-dlp download + FFmpegExtractAudio
│       └── analyze_audio()     → ffprobe validate → librosa/Essentia
└── redis               (Railway managed Redis)
```

### Pipeline module entry points (pipeline.py)

| Function | Role | Auth params |
|----------|------|-------------|
| `check_duration(url, cookies_path, bgutil_base_url)` | Metadata-only, selects client based on bgutil presence | web if bgutil, else android |
| `download_audio(url, cookies_path, po_token, bgutil_base_url)` | Download + WAV conversion | web if bgutil, else android |
| `analyze_audio(wav_path)` | ffprobe + BPM + key | none |

### Current client selection logic (pipeline.py lines 61, 127)

```python
player_client = "web" if bgutil_base_url else "android"
```

This is correct in intent: web client when bgutil provides PO tokens, android as fallback. The problem is that the android fallback itself is unreliable on datacenter IPs without a PO Token (android also needs DroidGuard tokens for GVS in 2026).

### Current ffprobe path resolution (pipeline.py lines 33-34)

```python
_FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
_FFPROBE_PATH = str(Path(_FFMPEG_PATH).parent / "ffprobe")
```

`get_ffmpeg_exe()` returns the full path to the ffmpeg binary (e.g. `.../imageio_ffmpeg/binaries/ffmpeg-linux64-v...`). Taking `.parent` gives the directory containing the binary. This is correct for building `_FFPROBE_PATH` as a sibling binary.

However, `ffmpeg_location` in yt-dlp options must be a **directory**, not a file path. Passing the ffmpeg file path directly causes yt-dlp to fail to find ffprobe (confirmed: yt-dlp issue #7178). The correct value is `Path(_FFMPEG_PATH).parent`.

**Current code passes `_FFMPEG_PATH` (file) to `ffmpeg_location`. It should pass `str(Path(_FFMPEG_PATH).parent)` (directory).**

Additionally, imageio-ffmpeg does **not** include ffprobe in its bundled binaries. It bundles only ffmpeg. The sibling `ffprobe` at `Path(_FFMPEG_PATH).parent / "ffprobe"` will not exist unless a system ffprobe is installed or ffprobe is manually placed there. On Railway, `apt-get install -y ffmpeg` provides system ffprobe, but that is not the imageio-ffmpeg binary directory.

---

## Proposed Changes

### 1. Client Strategy: web + bgutil as primary, tv as secondary fallback

**Rationale:**
- `web` client with a bgutil-provided GVS PO Token is the most reliable combination for datacenter IPs in 2026. bgutil generates BotGuard (web) tokens on demand.
- `android` client also needs DroidGuard tokens for GVS in 2026. Without them it is nearly as unreliable as web without a PO Token.
- `android_vr` was an attractive option (no PO Token required) but became erratic in March 2026 (yt-dlp issue #16150): often returns only format 18 (360p), making it unsuitable for audio quality.
- `tv` client does not require PO tokens and is relatively stable — usable as a secondary fallback when bgutil is unavailable, accepting that format selection may be limited.

**Recommended client chain:**

| Priority | Client | Condition | Notes |
|----------|--------|-----------|-------|
| 1 (primary) | `web` | bgutil available | Requires bgutil GVS PO Token |
| 2 (fallback) | `tv` | bgutil unavailable | No PO Token needed; SABR may limit formats in some regions |
| 3 (last resort) | `android` | bgutil unavailable + tv fails | Unreliable on datacenter IPs but may work on some videos |

The fallback chain does NOT mean retrying the full Celery job. It means trying each client inside a single `download_audio()` call. If `web` raises `yt_dlp.utils.DownloadError`, try `tv`, then `android`. Wrap each attempt in a `try/except yt_dlp.utils.DownloadError`.

**Implementation pattern for `download_audio()`:**

```python
_CLIENT_CHAIN = ["web", "tv", "android"]

def download_audio(url, cookies_path, po_token, bgutil_base_url=""):
    if bgutil_base_url:
        clients_to_try = ["web"]          # bgutil available: web only, trust it
    else:
        clients_to_try = ["tv", "android"] # no bgutil: fallback chain

    last_error = None
    for client in clients_to_try:
        try:
            return _attempt_download(url, cookies_path, po_token, bgutil_base_url, client)
        except yt_dlp.utils.DownloadError as e:
            last_error = e
            logger.warning("yt-dlp client=%s failed: %s — trying next client", client, e)
            continue
    raise RuntimeError(f"yt-dlp failed all clients: {last_error}") from last_error
```

When bgutil is running, use `web` only — do not fall through to tv/android on bgutil failure, because a PO Token failure with `web` is a bgutil service issue and should surface as a clean error, not silently degrade.

### 2. bgutil as Railway service

bgutil runs as a Node.js HTTP server on port 4416. On Railway, it becomes a separate service in the same project/environment. Services in the same Railway environment communicate over `[service-name].railway.internal`.

**Architecture with bgutil:**

```
Railway Project (same environment)
├── web-service          (FastAPI)          — public HTTPS
├── celery-worker        (Celery)           — no public port
├── bgutil               (Node.js HTTP)     — internal only, port 4416
└── redis                (Railway Redis)    — internal only
```

yt-dlp connects to bgutil via:
```
BGUTIL_BASE_URL=http://bgutil.railway.internal:4416
```

This value is injected as an env var into `celery-worker` and `web-service` services. `api/config.py` already reads it: `bgutil_base_url: str = field(default_factory=lambda: os.environ.get("BGUTIL_BASE_URL", ""))`.

**bgutil Railway service configuration:**

bgutil does not have its own railway.toml since it is a separate service deployed from the Docker image `brainicism/bgutil-ytdlp-pot-provider:latest`. Configure it in the Railway dashboard:
- Source: Docker image `brainicism/bgutil-ytdlp-pot-provider:latest`
- Port: 4416 (internal only — do not expose publicly)
- No healthcheck path (bgutil does not expose `/health`)
- Restart policy: ON_FAILURE

The bgutil service does NOT need `YTDLP_COOKIES_B64`. It only generates PO tokens. Authentication (cookies) stays in the celery-worker environment.

**Requirements change:** `bgutil-ytdlp-pot-provider>=0.11.0` is already in `requirements.txt`. This installs the Python plugin that wires yt-dlp to the bgutil HTTP server. No change needed.

### 3. ffprobe path fix

Two independent problems exist:

**Problem A — `ffmpeg_location` must be a directory (HIGH confidence, verified via yt-dlp issue #7178):**

Current code: `"ffmpeg_location": _FFMPEG_PATH` — passes the ffmpeg binary file path.
yt-dlp requires: `"ffmpeg_location": str(Path(_FFMPEG_PATH).parent)` — the directory containing both ffmpeg and ffprobe.

Fix in `pipeline.py`:
```python
_FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
_FFMPEG_DIR  = str(Path(_FFMPEG_PATH).parent)   # directory — for ffmpeg_location
_FFPROBE_PATH = str(Path(_FFMPEG_DIR) / "ffprobe")  # for subprocess call in validate_wav
```

Then in yt-dlp opts: `"ffmpeg_location": _FFMPEG_DIR`

**Problem B — imageio-ffmpeg does NOT bundle ffprobe (HIGH confidence):**

imageio-ffmpeg ships one binary: ffmpeg. It has no `get_ffprobe_exe()`. The sibling `ffprobe` at `_FFMPEG_DIR/ffprobe` will not exist unless explicitly placed there.

On Railway, `ffprobe` comes from the system package `ffmpeg` installed via nixpacks or Dockerfile. The system ffprobe is at `/usr/bin/ffprobe`, not in imageio-ffmpeg's directory.

**Recommended fix for `validate_wav()`:** resolve ffprobe with a fallback chain:

```python
import shutil

def _resolve_ffprobe() -> str:
    """Find ffprobe: imageio-ffmpeg sibling first, then system PATH."""
    import imageio_ffmpeg
    sibling = Path(imageio_ffmpeg.get_ffmpeg_exe()).parent / "ffprobe"
    if sibling.exists():
        return str(sibling)
    system = shutil.which("ffprobe")
    if system:
        return system
    raise RuntimeError(
        "ffprobe not found. Install ffmpeg system package or place ffprobe "
        "alongside imageio-ffmpeg binary."
    )

_FFPROBE_PATH = _resolve_ffprobe()
```

On Railway, nixpacks detects `imageio-ffmpeg` and installs system ffmpeg (which includes ffprobe at `/usr/bin/ffprobe`). `shutil.which("ffprobe")` finds it. Locally with imageio-ffmpeg, neither path may exist — but the subprocess in `validate_wav()` will raise a clean `FileNotFoundError` that surfaces immediately.

### 4. Cookie validation at startup

The current `lifespan` in `api/main.py` only decodes `YTDLP_COOKIES_B64` to `/tmp/sg_cookies.txt` and checks Redis auth. It does not verify that cookies are accepted by YouTube.

**Recommendation: add a lightweight cookie check in `lifespan`.**

A full download is too slow for startup. Instead, fetch metadata for a known public video using `skip_download=True`. If yt-dlp raises `DownloadError` mentioning "Sign in to confirm", log a CRITICAL warning but do NOT abort startup — the operator needs to know but aborting would make the service unrecoverable until re-deploy with new cookies.

```python
async def _check_cookies_functional(cookies_path: str, bgutil_base_url: str) -> None:
    """Non-blocking startup probe: log if cookies appear expired."""
    import yt_dlp
    _TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" — first YouTube video, stable
    player_client = "web" if bgutil_base_url else "tv"
    opts = {
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 10,
        "cookiefile": cookies_path,
        "extractor_args": {"youtube": [f"player_client={player_client}"]},
    }
    if bgutil_base_url:
        opts["extractor_args"]["youtubepot-bgutilhttp"] = [f"base_url={bgutil_base_url}"]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(_TEST_URL, download=False)
        logger.info("Cookie probe: OK")
    except Exception as e:
        logger.critical("Cookie probe FAILED — cookies may be expired: %s", e)
        # Do not raise — degraded state is better than unrecoverable startup failure
```

Call this from `lifespan` in a `asyncio.get_event_loop().run_in_executor(None, ...)` or as a background thread. Do not await it synchronously (yt-dlp is blocking and would delay startup).

**Decision:** This is a SHOULD, not a MUST. It helps operations visibility but must not block startup. Add it as an async background task fired after `yield` starts.

### 5. yt-dlp version pinning strategy

Current: `yt-dlp==2026.3.17` (exact pin).

**Problem:** yt-dlp releases roughly every 2 weeks. YouTube changes bot detection continuously. A pinned version can become non-functional within days. However, blindly staying at latest risks breaking from a yt-dlp bug.

**Recommended strategy:**

- **Pin to a recent release** (not `latest` float): `yt-dlp>=2026.3.17,<2027.0`
- **Add a deploy smoke test**: before each Railway deploy, run `yt-dlp -F "https://www.youtube.com/watch?v=jNQXAC9IVRw"` against the staging environment. If it fails, rollback.
- **Update cadence**: bump the pin every 4-6 weeks or immediately after a YouTube-side breakage is reported on yt-dlp's GitHub issue tracker.
- **Do NOT auto-update on every deploy** (`yt-dlp>=2026`): a surprise breaking change during a deploy is worse than running a slightly old version that still works.

Avoid `bgutil-ytdlp-pot-provider>=0.11.0` floating upper bound risk: bgutil must be compatible with the pinned yt-dlp version. When bumping yt-dlp, verify bgutil compatibility in release notes.

---

## Component Map: New vs Modified

### Modified files

| File | Change | Scope |
|------|--------|-------|
| `pipeline.py` | Fix `ffmpeg_location` to pass directory not file | 2 lines: `_FFMPEG_DIR` + update opts dicts |
| `pipeline.py` | Replace `_FFPROBE_PATH` with `_resolve_ffprobe()` that falls back to `shutil.which` | ~10 lines: new function |
| `pipeline.py` | Refactor `download_audio()` to extract `_attempt_download()` private helper + fallback loop | ~30 lines: restructure, no API change |
| `pipeline.py` | Same client fallback logic in `check_duration()` | ~10 lines |
| `api/main.py` | Add `_check_cookies_functional()` background probe in `lifespan` | ~20 lines: new async function |
| `requirements.txt` | Change `yt-dlp==2026.3.17` to `yt-dlp>=2026.3.17,<2027.0` | 1 line |

### New components (Railway only, no code changes)

| Component | What | How |
|-----------|------|-----|
| bgutil Railway service | `brainicism/bgutil-ytdlp-pot-provider:latest` Docker image | Add service in Railway dashboard |
| `BGUTIL_BASE_URL` env var | `http://bgutil.railway.internal:4416` | Set on celery-worker and web-service in Railway dashboard |

### No changes needed

| File | Reason |
|------|--------|
| `api/tasks.py` | Already passes `settings.bgutil_base_url` to pipeline functions |
| `api/config.py` | Already reads `BGUTIL_BASE_URL` env var |
| `api/main.py` (lifespan decode) | Cookie decoding from B64 is correct |
| `railway.toml` | Web service config unchanged |

---

## Build Order

Dependencies run from bottom up. Each step must be green before the next.

```
Step 1 — ffprobe fix (no Railway needed, testable locally)
   pipeline.py: _FFMPEG_DIR + _resolve_ffprobe() + ffmpeg_location fix
   Test: python pipeline.py <youtube_url> with system ffmpeg installed
   Validates: ffprobe path resolution works; analyze_audio() passes

Step 2 — client fallback chain (no Railway needed)
   pipeline.py: _attempt_download() + fallback loop in download_audio() and check_duration()
   Test: python pipeline.py with BGUTIL_BASE_URL unset → tv client used
   Validates: fallback logic doesn't break existing android path

Step 3 — deploy bgutil on Railway
   Railway dashboard: add service from brainicism/bgutil-ytdlp-pot-provider:latest
   Set port 4416 internal, no public domain
   Test: curl http://bgutil.railway.internal:4416 from celery-worker shell
   Validates: bgutil reachable on private network

Step 4 — set BGUTIL_BASE_URL on Railway services
   Set BGUTIL_BASE_URL=http://bgutil.railway.internal:4416 on celery-worker
   Redeploy celery-worker
   Test: submit a job via POST /jobs, watch Celery logs for "web client" usage
   Validates: yt-dlp connects to bgutil and gets PO Token

Step 5 — cookie startup probe (optional, low risk)
   api/main.py: _check_cookies_functional() background task in lifespan
   Test: deploy with valid cookies → see "Cookie probe: OK" in logs
   Test: deploy with expired cookies → see "Cookie probe FAILED" warning

Step 6 — end-to-end validation
   Submit 3-5 real YouTube beat links via /jobs API
   Verify: job reaches SUCCESS state, BPM/key returned, WAV downloadable
```

Step 1 and Step 2 are independent and can be developed in parallel. Step 3 must complete before Step 4. Step 5 is independent of Steps 3-4.

---

## Railway Deployment Considerations

### No persistent filesystem

Railway containers have ephemeral `/tmp`. The WAV sweeper (daemon thread in `api/main.py`) correctly handles cleanup within the web service process. The celery-worker and web-service share no filesystem — WAV files produced by celery-worker are read by web-service via path stored in Redis. This works only because on Railway, both services run on the same host OR the path must be re-evaluated.

**Critical gap:** If Railway places `celery-worker` and `web-service` on different hosts (possible in scaling scenarios), `/tmp/sg_*.wav` produced by celery-worker will not exist on the web-service host. Railway's default is single-host for hobby/pro plans with shared volumes not guaranteed. For v1.2 scope: document this as a known constraint and note that it works when both services are on the same Railway machine. The fix for multi-host is object storage (e.g., S3), which is out of scope.

### Service-to-service networking

Railway private network: all services in the same project+environment communicate via `[service-name].railway.internal`. No public exposure needed for bgutil.

For environments created after October 16, 2025 (likely the case for new deployments): IPv4 + IPv6 both available. For legacy environments: IPv6 only — if bgutil uses Node.js, ensure it binds to `::` (all interfaces) not just `127.0.0.1`. The Docker image's default bind should handle this, but worth verifying.

### bgutil reliability as a dependency

If bgutil goes down, `BGUTIL_BASE_URL` is set but the service is unreachable. Current code falls through to `web` client which will fail without PO Token. The fallback loop described in §1 handles this: when `bgutil_base_url` is set but bgutil is down, the `web` client attempt will fail with a DownloadError. The pipeline should NOT then silently fall back to `tv` — it should surface the bgutil outage as a clean error so Railway's health monitoring can catch it.

Implementation detail: distinguish "bgutil provided but unreachable" from "bgutil not configured" by catching connection errors from the bgutil plugin separately. This is LOW priority for v1.2; acceptable to treat all `web` client failures as a download error.

### imageio-ffmpeg on Railway

Railway's nixpacks buildpack detects `imageio-ffmpeg` in `requirements.txt` and installs system ffmpeg. System ffmpeg provides ffprobe at `/usr/bin/ffprobe`. The `_resolve_ffprobe()` fallback to `shutil.which("ffprobe")` will find it. The current hardcoded sibling path will fail (imageio-ffmpeg does not bundle ffprobe). The fix is mandatory for Railway.

### Cookies management

`YTDLP_COOKIES_B64` (base64-encoded Netscape cookies.txt) is decoded to `/tmp/sg_cookies.txt` by `_resolve_cookies_path()` in `api/config.py`. This runs at Settings() instantiation, which happens at module import time in both web-service and celery-worker. The 0o600 chmod is correctly applied.

Cookies expire (typically 1-4 weeks depending on YouTube session length). The startup cookie probe (Step 5) surfaces this quickly. Rotation procedure: re-export cookies from browser, base64-encode, update `YTDLP_COOKIES_B64` env var in Railway, redeploy.

---

## Open Questions / Risks

| Question | Risk Level | Notes |
|----------|-----------|-------|
| Does Railway place celery-worker and web-service on the same host? | HIGH | WAV serving depends on shared /tmp. If split across hosts, 410 "File expired" on every download. |
| Is bgutil's Docker image compatible with Railway's arm64/amd64? | MEDIUM | brainicism/bgutil-ytdlp-pot-provider:latest is amd64. Confirm Railway build host architecture. |
| `web` client with bgutil: does SABR still block some videos on datacenter IPs? | MEDIUM | yt-dlp issue #16082 reports SABR + n-challenge failures even with bgutil PO Token on some datacenter configs. |
| `android_vr` as alternative to `tv` fallback | LOW | android_vr was erratic as of March 2026 (issue #16150). tv is safer as fallback. |
| bgutil updates vs yt-dlp version compatibility | MEDIUM | bgutil must match yt-dlp's plugin API. Verify when bumping either. |

---

## Sources

- [bgutil-ytdlp-pot-provider GitHub](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — HTTP server mode, port 4416, base_url extractor arg
- [yt-dlp PO Token Guide Wiki](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) — client matrix, PO Token requirements by client type
- [yt-dlp issue #16150: android_vr erratic March 2026](https://github.com/yt-dlp/yt-dlp/issues/16150) — android_vr unreliable for production
- [yt-dlp issue #7178: ffmpeg_location expects directory](https://github.com/yt-dlp/yt-dlp/issues/7178) — confirmed: ffmpeg_location must be a directory
- [Railway Private Networking Docs](https://docs.railway.com/private-networking) — `[service-name].railway.internal` hostname format, IPv4+IPv6 for environments post-Oct 2025
- [Railway Config as Code Reference](https://docs.railway.com/config-as-code/reference) — railway.toml fields: single service per file
- [imageio-ffmpeg GitHub](https://github.com/imageio/imageio-ffmpeg) — only bundles ffmpeg, no ffprobe, no get_ffprobe_exe()
- [bgutil Docker Hub](https://hub.docker.com/r/brainicism/bgutil-ytdlp-pot-provider) — prebuilt image, port 4416
- [yt-dlp issue #16082: SABR + n-challenge with bgutil](https://github.com/yt-dlp/yt-dlp/issues/16082) — datacenter + SABR risk even with PO Token
- [6 Ways to Get YouTube Cookies in 2026 — DEV.to](https://dev.to/osovsky/6-ways-to-get-youtube-cookies-for-yt-dlp-in-2026-only-1-works-2cnb) — cookie management context
