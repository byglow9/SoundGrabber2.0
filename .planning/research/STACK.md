# Technology Stack — YouTube Pipeline Fix (v1.2 Update)

**Project:** SoundGrabber — v1.2 YouTube Pipeline Fix
**Researched:** 2026-05-10 (supersedes 2026-04-29 for YouTube download section)
**Scope:** Targeted research for Railway datacenter IP reliability fixes.
  Does NOT re-examine librosa, essentia, FastAPI, Celery, Redis — those are validated.

---

## Summary

The current pipeline (yt-dlp 2026.3.17 on Railway) has four distinct failure modes on
Railway's datacenter IPs. Each has a specific, addressable root cause. The fix is a
client-strategy change plus a confirmed ffprobe path approach — no full rewrite needed.

**Verdict:** All four failures are fixable without adding heavy new dependencies.
The bgutil PO Token provider works technically but requires a separate Node.js/Deno
sidecar service, which has already been proven unreliable in this project's Railway
environment (STATE.md). The simpler path is a client fallback chain that avoids
PO Tokens entirely for the common case.

---

## yt-dlp Version

### Recommended: `yt-dlp==2026.3.17` (keep current pin)

**Latest stable on PyPI as of 2026-05-10:** `2026.3.17` (released March 17, 2026).
A nightly `2026.05.05` exists but is NOT on PyPI stable and should not be used in
production — no stability guarantees.

**Why keep the current pin rather than upgrade to nightly:**
- Nightly builds require a custom install step (not `pip install yt-dlp`).
- The `2026.3.17` stable release includes the `2026.03.03` YouTube forced player
  update and the `2026.03.13` android_vr + web_embedded client fixes, which are
  the most relevant changes for this milestone.
- The failures seen on Railway are NOT caused by the yt-dlp version per se — they
  are caused by client selection and ffprobe path. Upgrading yt-dlp does not fix them.

**nsig extraction root cause — and the fix:**
The nsig failure (local `2024.12.03` vs Railway `2026.3.17` discrepancy) is a stale
player JS cache problem. yt-dlp caches the YouTube player JavaScript to extract the
n-signature parameter. When YouTube rotates the player (every few weeks), a cached
version from a previous deploy produces "nsig extraction failed" warnings.

Fix: set `"no_cache_dir": True` in yt-dlp opts. Railway containers are ephemeral per
deploy. Without this flag, a stale cache written during an earlier deploy's warmup
can persist within the same container lifetime. Disabling the cache means every run
fetches fresh player JS — slightly slower per request but eliminates the entire class
of nsig failures.

**Confidence:** HIGH — verified via PyPI, yt-dlp release notes, nsig cache
invalidation PR #10401.

---

## Client Strategy

### The Problem: Per-Client Failure Modes on Datacenter IPs

YouTube applies per-IP experiments. Datacenter IPs (Railway's shared infrastructure)
get SABR (Secure Audio/Video Bitstream Restriction) enforcement and bot-detection
at a higher rate than residential IPs. No single client is universally reliable;
the strategy must be a ranked fallback chain.

### Client Evaluation Matrix (yt-dlp 2026.3.17, as of 2026-05)

| Client | PO Token Required | Cookies Work | Audio Quality | DC IP Reliability | Notes |
|--------|-------------------|--------------|---------------|-------------------|-------|
| `web` | Yes (GVS + SABR) | Yes | High (DASH) | LOW — SABR forces missing URLs; 403 on format fetch | Broken on DC IPs even with PO Token (issue #16082) |
| `web_safari` | Yes (GVS) | Yes | Medium (HLS 91-96) | LOW-MEDIUM — SABR limits to muxed HLS | Issue #16229 confirms cookies trigger SABR on this client |
| `mweb` | Yes (GVS) | Yes | Medium | LOW without bgutil | PO Token mandatory for any URL access |
| `ios` | Yes (GVS) | No — ignored | High (m4a HLS) | MEDIUM — bypasses some SABR experiments | HLS m4a formats exempt from GVS PO Token at GVS level |
| `android` | Yes (GVS) | No — ignored | Low (format 18, ~360p) | MEDIUM | Most bot-detection resilient; unacceptable audio quality for WAV |
| `android_vr` | Not required | No | Variable | LOW — A/B experiment returns only format 18 randomly (issue #16150) | Was reliable pre-2026; now erratic |
| `tv` | Not required | Yes (required) | High (DASH) | MEDIUM-HIGH — no PO Token; cookies provide auth | Some TV-client formats are DRM'd but audio-only formats are not |
| `web_embedded` | Not required | No | Variable | MEDIUM — embeddable videos only (covers most public videos) | Fallback when all else fails; no PO Token |

**Key insight from issue #16229:** Passing cookies to `web_safari` CAUSES SABR to be
enforced — fewer formats with cookies than without. This counterintuitive behavior
means the current `android`-with-cookies pattern is architecturally broken: cookies
help with `tv` and `web` clients, but hurt or do nothing for `android`/`ios`/`android_vr`.

### Recommended Client Chain for Railway

**Primary recommendation:** `tv,ios,web_embedded`

**Rationale:**

1. **`tv` (primary):** No PO Token required. Accepts cookies. When cookies are valid
   and fresh, the `tv` client gets DASH audio-only streams (high quality for WAV).
   DRM warning from issue #13001 applies only to DRM-protected videos — public
   YouTube beats/instrumentals are not DRM'd.

2. **`ios` (fallback):** Cookies are not used by this client (YouTube ignores the
   cookiefile for `ios`), but it provides HLS m4a audio streams that are exempt from
   the GVS PO Token requirement at the CDN level. Bypasses many SABR experiments.
   Acceptable quality for WAV conversion.

3. **`web_embedded` (last resort):** No PO Token required. Works for embeddable
   videos — the default for all public YouTube videos not explicitly disabled. Lower
   quality ceiling but zero auth-related failures.

**Configuration in pipeline.py (correct Python API format):**

```python
# CORRECT: nested dict with list values
extractor_args = {
    "youtube": {
        "player_client": ["tv,ios,web_embedded"],
    }
}

# INCORRECT (current code): list-of-strings format
# extractor_args = {"youtube": ["player_client=tv,ios,web_embedded"]}
# This works for the CLI parser but is unreliable in the Python API per issue #13451
```

**Note on extractor_args formats:** Issue #13451 documents that `{"youtube": ["player_client=mweb"]}` (list-of-strings) does not take effect in the Python API in some versions, while `{"youtube": {"player_client": ["mweb"]}}` (nested dict) is the officially documented form in `yt_dlp/extractor/common.py`. Use nested dict.

**What to REMOVE:**

- Remove `android` as primary client. Format 18 (~360p progressive) produces
  ~128kbps audio — degrades WAV output quality for musicians.
- Remove the `bgutil_base_url`-conditional logic (`web` if bgutil / `android` if
  not). The `web` client fails on datacenter IPs even WITH valid PO Tokens (issue
  #16082). The conditional adds complexity for zero benefit.
- Remove `po_token` injection in the hot path. The recommended `tv,ios,web_embedded`
  chain does not require PO Tokens for normal public videos.

**Confidence:** HIGH for `tv` no-PO-token claim (PO Token Guide official wiki);
MEDIUM for real-world Railway reliability of `tv` client (confirmed in theory,
needs validation after deploy; YouTube's per-session experiments may affect it).

---

## PO Token Approach

### Decision: Defer bgutil Sidecar; Use Token-Free Clients for v1.2

**bgutil-ytdlp-pot-provider current status (2026-05-10):**
- Latest version: `1.3.1` (released March 7, 2026). Actively maintained.
- Requires Node.js (>=20) OR Deno (>=2.0.0) running OUTSIDE Python. No pure-Python
  implementation. The JS dependency is non-negotiable — it wraps LuanRT's Botguard
  library.
- HTTP server mode (Docker image `brainicism/bgutil-ytdlp-pot-provider`) is the
  recommended deployment mode; script mode spawns a Node process per yt-dlp call
  (unsuitable for concurrency).

**Why NOT deploy bgutil as Railway sidecar for v1.2:**

1. This project's STATE.md already records empirical failure: "bgutil não conecta no
   Railway." The sidecar connectivity issue is known and unresolved.
2. Issue #16082 ("SABR streaming + bgutil PO Token being generated") shows that even
   with a valid bgutil token, YouTube enforces SABR at the client level on datacenter
   IPs. The PO Token alone does not unblock format access.
3. Operational complexity: Railway does not support multi-container stacks natively.
   bgutil must be a separate service with its own deploy lifecycle, health checks, and
   internal networking. This is v1.3 work, not v1.2.
4. The `tv` and `ios` clients bypass PO Token requirements entirely for the common
   case (public, non-DRM content).

**Keep `bgutil-ytdlp-pot-provider>=0.11.0` in requirements.txt** — it installs a
yt-dlp plugin that is a no-op when no bgutil HTTP server is configured. Removing it
now and re-adding it in v1.3 adds churn.

**Manual `YTDLP_PO_TOKEN` env var:** PO Tokens expire every ~6 hours. Manual rotation
is not operational. Remove the `po_token` parameter injection from `download_audio`
for v1.2; it provides no value without an automated provider.

**Alternative providers evaluated:**

| Provider | Dependency | Cloud Viable? | Verdict |
|----------|------------|---------------|---------|
| `bgutil` (HTTP server) | Node.js/Deno + Docker | Yes but complex | Defer to v1.3 |
| `bgutil` (Rust impl.) | Rust binary | Theoretically yes | Same JS botguard core; no advantage |
| `yt-dlp-getpot-wpc` | Headless browser | No — needs display | REJECT |
| Manual env var `YTDLP_PO_TOKEN` | None | Yes but expires | Only for emergency fallback |

**Confidence:** HIGH for the "defer" decision (empirical failure + issue #16082);
MEDIUM for "tv/ios/web_embedded suffices" (theory confirmed in docs, not yet
re-validated on this project's Railway instance after client change).

---

## ffprobe Path

### Problem: Current Heuristic Fails on Railway

The current code:

```python
_FFPROBE_PATH = str(Path(_FFMPEG_PATH).parent / "ffprobe")
```

**Why it fails:** `imageio-ffmpeg` bundles ONLY the `ffmpeg` binary. It does not
bundle `ffprobe`. This is documented in the imageio-ffmpeg repo as an open feature
request (issue #23, "ffprobe"), unfixed as of 2026-05. The wheel ships a file like
`ffmpeg-linux-x86_64-v7.1` — there is no `ffprobe-linux-x86_64-v7.1` sibling.

So `Path(_FFMPEG_PATH).parent / "ffprobe"` resolves to a path that does not exist,
and `subprocess.run([_FFPROBE_PATH, ...])` raises `FileNotFoundError`.

### Fix: System ffprobe via nixpacks + shutil.which fallback

**Step 1: Install system ffmpeg on Railway via nixpacks.toml.**

Create `nixpacks.toml` in the project root:

```toml
[phases.setup]
nixPkgs = ["ffmpeg"]
```

When Nixpacks installs `ffmpeg` from Nix, it installs BOTH `ffmpeg` and `ffprobe`
to the Nix profile PATH. Both are available as `ffmpeg`/`ffprobe` in `$PATH` inside
the running container. Confirmed by Railway community documentation.

If Railway has migrated this service to Railpack (its successor to Nixpacks), use
environment variable `RAILPACK_DEPLOY_APT_PACKAGES=ffmpeg` in the Railway service
settings. `apt install ffmpeg` on Debian/Ubuntu installs `ffprobe` at `/usr/bin/ffprobe`.

**Step 2: Update `_FFPROBE_PATH` resolution in pipeline.py.**

```python
import shutil

_FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

def _resolve_ffprobe() -> str:
    """Locate ffprobe binary: system PATH first, imageio-ffmpeg sibling as fallback.

    On Railway (nixpacks ffmpeg installed): shutil.which("ffprobe") returns the Nix path.
    On local dev with system ffmpeg: shutil.which("ffprobe") returns /usr/bin/ffprobe.
    imageio-ffmpeg does NOT bundle ffprobe (issue #23); the sibling heuristic
    only works if user manually placed ffprobe next to imageio-ffmpeg's ffmpeg.
    """
    system = shutil.which("ffprobe")
    if system:
        return system
    sibling = str(Path(_FFMPEG_PATH).parent / "ffprobe")
    if Path(sibling).exists():
        return sibling
    raise RuntimeError(
        "ffprobe not found. Add nixpacks.toml with nixPkgs=['ffmpeg'], "
        "or install system ffmpeg, or set FFPROBE_PATH env var."
    )

_FFPROBE_PATH = _resolve_ffprobe()
```

**ffmpeg_location for yt-dlp postprocessor:**
When system ffmpeg is available, pass its PARENT DIRECTORY (not the file path) so
yt-dlp can find both `ffmpeg` and `ffprobe` in the same directory:

```python
_SYSTEM_FFMPEG = shutil.which("ffmpeg")
_FFMPEG_DIR = str(Path(_SYSTEM_FFMPEG).parent) if _SYSTEM_FFMPEG else str(Path(_FFMPEG_PATH).parent)

# in yt-dlp opts:
"ffmpeg_location": _FFMPEG_DIR,
```

**Confidence:** HIGH — imageio-ffmpeg no-ffprobe claim verified via source + issue #23;
nixpacks ffmpeg installs ffprobe confirmed in Railway community documentation.

---

## Additional Flags

### yt-dlp Options for Datacenter IP Reliability

```python
ydl_opts = {
    # Format: bestaudio prefers audio-only DASH/HLS when available.
    # /best fallback ensures muxed progressive downloads when SABR blocks DASH.
    # This already exists in the code and is correct.
    "format": "bestaudio/best",

    # CRITICAL: Disables yt-dlp's player JS cache.
    # Railway containers are ephemeral per deploy. A stale nsig cache from a
    # previous deploy causes "nsig extraction failed" on the current run.
    # Trade-off: slightly slower per-request (re-fetches player JS each time)
    # vs. reliable format extraction. Correct trade-off for Railway.
    "no_cache_dir": True,

    # Already present — keep. 10MB chunks reduce mid-stream throttling.
    "http_chunk_size": 10485760,

    # Already present — keep. 30s socket timeout is appropriate for Railway.
    "socket_timeout": 30,

    # ADD: Retry on transient network errors. Bot-detection temporary blocks
    # often resolve on a second attempt from the same IP.
    "retries": 3,

    # ADD: Fragment retries for HLS/DASH streams. Datacenter IPs sometimes get
    # 403s on individual TS/DASH fragments during bot checks; retrying works.
    "fragment_retries": 5,
}
```

**`no_cache_dir` is the highest-value addition.** It directly addresses the nsig
failure class. All other additions are defensive improvements.

**format string `"bestaudio/best"` — keep as-is.** The `/best` fallback is essential
for when SABR forces muxed-only formats (documented in issue #16128 for 2026.03.03
clients). The WAV conversion works equally well from a muxed progressive stream.

**Confidence:** HIGH for `no_cache_dir` (documented yt-dlp option, directly addresses
nsig class); MEDIUM for retry values (community-reported; not officially benchmarked
for Railway specifically).

---

## What NOT to Add

| Item | Reason |
|------|--------|
| bgutil HTTP sidecar in hot path | Node.js/Deno infra; empirically failed on this Railway env; `tv` client removes the need for v1.2 |
| Residential proxy routing | Cost + latency; overkill for public audio-only downloads at community scale |
| `yt-dlp-getpot-wpc` | Requires headless browser; impossible on headless Railway |
| `android` as primary client | Format 18 (~360p) produces ~128kbps audio; degrades WAV output for musicians |
| `web` as primary client | SABR enforced even with valid cookies + PO Token on DC IPs (issue #16082) |
| `android_vr` as primary client | A/B test returns only format 18 randomly (issue #16150); unreliable in production |
| `imageio-ffmpeg` for ffprobe path | Library does not bundle ffprobe (issue #23 is an unfixed feature request) |
| Manual `YTDLP_PO_TOKEN` env var rotation | PO Tokens expire every ~6 hours; manual rotation is not operational at scale |
| yt-dlp nightly pinned in requirements.txt | Not on PyPI; requires custom install step; no stability guarantees |
| `web_creator` or `web_music` clients | Both require GVS PO Token and account cookies — wrong for public, unauthenticated tool |

---

## Required Changes Summary

| File | Change | Rationale |
|------|--------|-----------|
| `requirements.txt` | Keep `yt-dlp==2026.3.17` | Latest stable PyPI; version is not the root cause of failures |
| `pipeline.py` | Change `player_client` to `tv,ios,web_embedded` | Avoids PO Token requirement; see Client Strategy section |
| `pipeline.py` | Change `extractor_args` to nested dict format | List-of-strings may not take effect per issue #13451 |
| `pipeline.py` | Replace `_FFPROBE_PATH` derivation with `shutil.which("ffprobe")` + sibling fallback | imageio-ffmpeg does not bundle ffprobe |
| `pipeline.py` | Add `"no_cache_dir": True` to all yt-dlp opts dicts | Eliminates nsig cache staleness between deploys |
| `pipeline.py` | Add `"retries": 3, "fragment_retries": 5` | Resilience to transient datacenter bot-check 403s |
| `pipeline.py` | Remove `bgutil_base_url` parameter and related conditional logic | Dead code path; proven unreliable in this environment |
| `pipeline.py` | Remove `po_token` injection in `download_audio` | `tv/ios/web_embedded` chain doesn't need it |
| `nixpacks.toml` | Create with `[phases.setup] nixPkgs = ["ffmpeg"]` | Makes system `ffprobe` and `ffmpeg` available on PATH in Railway |

---

## Sources

| Source | Confidence | URL |
|--------|------------|-----|
| yt-dlp PO Token Guide (official wiki) | HIGH | https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide |
| PyPI yt-dlp current version | HIGH | https://pypi.org/project/yt-dlp/ |
| imageio-ffmpeg issue: ffprobe not bundled | HIGH | https://github.com/imageio/imageio-ffmpeg/issues/23 |
| bgutil-ytdlp-pot-provider GitHub | HIGH | https://github.com/Brainicism/bgutil-ytdlp-pot-provider |
| yt-dlp issue: SABR + bgutil token insufficient | MEDIUM | https://github.com/yt-dlp/yt-dlp/issues/16082 |
| yt-dlp issue: android_vr erratic (returns format 18 only) | HIGH | https://github.com/yt-dlp/yt-dlp/issues/16150 |
| yt-dlp issue: DASH audio missing in 2026.03.03 | HIGH | https://github.com/yt-dlp/yt-dlp/issues/16128 |
| yt-dlp issue: cookies causing SABR on web_safari | HIGH | https://github.com/yt-dlp/yt-dlp/issues/16229 |
| yt-dlp issue: extractor_args mweb Python API | MEDIUM | https://github.com/yt-dlp/yt-dlp/issues/13451 |
| nsig cache invalidation PR | HIGH | https://github.com/yt-dlp/yt-dlp/pull/10401 |
| yt-dlp release 2026.03.17 notes | HIGH | https://github.com/yt-dlp/yt-dlp/releases/tag/2026.03.17 |
| Railpack package installation docs | HIGH | https://railpack.com/guides/installing-packages/ |
| Railway nixpacks ffmpeg community examples | MEDIUM | https://station.railway.com/questions/adding-ffmpeg-to-railway-project-ac99f551 |

---

## Pre-existing Stack Research (2026-04-29)

The sections below are unchanged from the initial research and remain valid for
layers not touched by the v1.2 milestone. See SUMMARY.md for overall architecture.

### Core Framework (Validated)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | yt-dlp dropped <3.10; 3.11 perf gains |
| FastAPI | 0.136.x | HTTP API | Async-native; Pydantic validation; background tasks |
| Uvicorn | 0.46.x | ASGI server | Standard prod server for FastAPI |
| Celery + Redis | 5.6.x / 6.4.x | Task queue | Persistent jobs, retries, cross-worker state |
| imageio-ffmpeg | 0.5.x | FFmpeg binary (ffmpeg only) | Ships ffmpeg binary; does NOT ship ffprobe (critical) |
| librosa | 0.11.x | BPM detection | Single pip install; proven at community scale |
| essentia | 2.1b6.dev | Key + BPM detection | C++ accuracy; RhythmExtractor2013 + KeyExtractor |
| soundfile | 0.13.x | WAV I/O | Required by librosa |

### System Packages Required on Railway

| Package | Why | How to Install on Railway |
|---------|-----|--------------------------|
| `ffmpeg` + `ffprobe` | yt-dlp postprocessor + WAV validation | `nixpacks.toml`: `nixPkgs = ["ffmpeg"]` |
| `libsndfile1` | soundfile/librosa WAV I/O on Linux | Typically included with nixpacks Python build |

---

---

# Raspberry Pi 3B Hosting Stack (v1.3 Addendum)

**Researched:** 2026-05-14
**Scope:** What changes when the same FastAPI + Celery + Redis + yt-dlp + librosa stack
moves from Railway (x86_64 datacenter) to Raspberry Pi 3B (ARM, 1GB RAM, residential IP).
Does NOT re-research the application layer — only infrastructure and ARM compatibility.

---

## Critical Architecture Decision: ARM64 (64-bit OS) vs ARM32 (armhf/armv7)

**Recommendation: Run Raspberry Pi OS 64-bit (aarch64/linux/arm64) — NOT 32-bit.**

This is the most consequential decision for the entire milestone. Everything else
depends on it.

**Why 64-bit wins despite 1GB RAM:**

| Factor | arm32 (armhf/linux/arm/v7) | arm64 (aarch64/linux/arm64) | Winner |
|--------|----------------------------|------------------------------|--------|
| essentia pip wheel | NOT AVAILABLE — no PyPI wheel, no piwheels wheel; must compile from C++ source (hours) | NOT AVAILABLE on PyPI for Linux arm64 either — same problem | Tie (both bad) |
| numpy pip wheel | Available via piwheels (armv7l, cp311) | Available via PyPI (manylinux aarch64, cp311) | arm64 (no piwheels needed) |
| librosa pip wheel | Available via piwheels (py3-none-any — pure Python) | Available via PyPI (pure Python) | Tie |
| Docker image ecosystem | Many modern images arm64-only; armhf deprecated by linuxserver since 2023 | Full range of Docker Hub images available | arm64 |
| bgutil Docker image | Architecture unknown; likely x86-only per Docker Hub inspection | arm64 support more probable for Node.js images | arm64 |
| mwader/static-ffmpeg | NOT available (amd64 + arm64 only) | Available | arm64 |
| Redis official image | Available (arm32v7/redis) | Available (arm64v8/redis) | Tie |
| Python official image | Available (arm32v7/python:3.11-slim-bookworm) | Available (python:3.11-slim-bookworm multi-arch) | Tie |
| RAM overhead | Lower pointer size — saves ~50-100MB in practice | 64-bit pointers, slightly larger kernel footprint | arm32 (marginal) |

**The essentia problem is the same on both architectures.** There are no Linux ARM
binary wheels for essentia on PyPI or piwheels. This is the biggest stack risk for
the Pi milestone regardless of which ARM variant you choose.

**The 50-100MB RAM advantage of 32-bit is not worth the ecosystem friction** of
arm32-only images, piwheels dependency, and missing mwader/static-ffmpeg. Use 64-bit.

**Confidence:** HIGH for essentia no-ARM-wheel claim (verified PyPI page: only x86_64
Linux and macOS ARM64 wheels); HIGH for mwader/static-ffmpeg arm64 availability;
MEDIUM for RAM delta claim (community consensus, not benchmarked on this stack).

---

## Docker Base Image

### Python Application Container

**Recommended:** `python:3.11-slim-bookworm` (multi-arch, pulls arm64 automatically on 64-bit Pi OS)

```dockerfile
FROM python:3.11-slim-bookworm
```

**Why slim-bookworm:**
- Official Python image, multi-arch manifest. On arm64 host pulls `linux/arm64` variant automatically.
- Bookworm (Debian 12) aligns with Raspberry Pi OS 64-bit current stable.
- `slim` variant removes locale data and documentation, saving ~50MB vs full image.
- Python 3.11.15 is the current 3.11 patch — same minor version as Railway deploy.

**Do NOT use alpine:** alpine uses musl libc. librosa's native deps (libsndfile, LAPACK)
have musl compatibility issues on ARM. Bookworm uses glibc — same as piwheels and
PyPI manylinux wheels.

**Confidence:** HIGH — arm32v7/python:3.11-slim-bookworm confirmed on Docker Hub;
arm64 pulls automatically via manifest on 64-bit OS.

---

## Redis Container

**Recommended:** `redis:7-alpine` (official image, multi-arch, pulls arm64 automatically)

```yaml
redis:
  image: redis:7-alpine
  platform: linux/arm64
```

**Why redis:7 not redis:8:**
- Redis 8.0 was released recently. The project currently uses `redis==6.4.0` Python
  client, which is compatible with Redis 7.x. Staying on Redis 7 avoids any potential
  protocol changes until the client library is validated with Redis 8.
- The alpine variant saves ~30MB vs the debian variant — meaningful on Pi's SD card.

**Confidence:** HIGH — official Redis image confirmed multi-arch including arm32v7 and arm64v8.

---

## FFmpeg in the Container

**Recommended approach: Install system `ffmpeg` from Debian package inside the app container.**

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

**Why apt-get instead of mwader/static-ffmpeg COPY --from:**
- `mwader/static-ffmpeg` supports amd64 and arm64 only — works on 64-bit Pi.
- However, Debian bookworm's `ffmpeg` package is ARM-native and includes both
  `ffmpeg` and `ffprobe` at the same path, keeping the existing `shutil.which`
  resolution logic working unchanged.
- `apt-get install ffmpeg` on bookworm ARM installs FFmpeg 5.x (stable Debian release),
  which is sufficient for audio extraction and WAV conversion.
- The mwader approach is better for x86 production builds (newer FFmpeg version);
  for Pi it adds complexity with no material benefit for audio-only workloads.

**Alternative (mwader COPY --from) — valid if you want FFmpeg 7/8:**

```dockerfile
COPY --from=mwader/static-ffmpeg:8.1 /ffmpeg /usr/local/bin/
COPY --from=mwader/static-ffmpeg:8.1 /ffprobe /usr/local/bin/
```

This works on arm64. The static binary has no external dependencies. If you need
a newer FFmpeg (8.x for modern codec support), use this. For audio extraction
from YouTube's HLS/DASH streams, FFmpeg 5.x suffices.

**Confidence:** HIGH for apt-get approach; HIGH for mwader arm64 compatibility.

---

## The essentia Problem — Critical Blocker

**essentia has NO binary wheels for Linux ARM (32-bit or 64-bit).** PyPI provides:
- Linux x86_64 (manylinux)
- macOS x86_64
- macOS ARM64 (Apple Silicon)

**There is no `linux/arm64` wheel for essentia on PyPI.** piwheels also does not have it.

### Options for Running essentia on the Pi

**Option A: Compile essentia from source inside Docker (HIGH effort, HIGH risk)**

The build requires: `cmake`, `swig`, `libfftw3-dev`, `libsamplerate-dev`,
`libyaml-dev`, `libavcodec-dev`, `libavformat-dev`, `libavresample-dev`,
`libavutil-dev`, `python3-dev`, plus Eigen, TNT, Gaia, and other C++ deps.

Build time on Pi 3B (1.2GHz quad-core): estimated 45-90 minutes for first build.
Docker layer caching helps on rebuilds but the initial setup is painful.

**Option B: Drop essentia, keep librosa for both BPM and key detection (RECOMMENDED)**

librosa 0.11.0 provides:
- `librosa.beat.beat_track()` — BPM detection
- `librosa.key.key_to_notes()` + `librosa.feature.chroma_cqt()` — key estimation
- Both are pure Python + numpy/scipy — no C++ compilation required

librosa's key detection (via chroma features) is less accurate than essentia's
KeyExtractor algorithm, but is adequate for the use case (beat/instrumental reference).

**This is the recommended path for the Pi milestone.** Remove essentia from the Pi
compose stack. If essentia accuracy is needed later, run a cross-compiled Docker
image built on x86 with `--platform linux/arm64` (requires Docker buildx on a dev machine).

**Option C: Cross-compile wheel on x86 with buildx (MEDIUM effort)**

```bash
docker buildx build --platform linux/arm64 -t soundgrabber-arm64 .
```

Build essentia inside a linux/arm64 QEMU environment on your x86 laptop/CI. Produces
a wheel or an image layer. Slower than native but achievable. This is the right
long-term approach if essentia accuracy matters.

**Confidence:** HIGH for "no PyPI wheel" claim (verified PyPI page directly); MEDIUM for
"librosa key detection adequate" (functional claim, not accuracy-benchmarked for music production).

---

## librosa + numpy on ARM

**librosa 0.11.0:** Pure Python wheel (`py3-none-any`). Available on PyPI and piwheels.
Installs without compilation on any Python 3.11 ARM environment.

**numpy 2.x on arm64:** Available via PyPI manylinux wheels for aarch64 (no piwheels
needed on 64-bit OS). Latest: numpy 2.4.4 (March 2026). The project's `numpy>=2.0,<3.0`
constraint is satisfied by the PyPI arm64 wheel.

**scipy on arm64:** Available via PyPI manylinux wheels for aarch64. Installs cleanly.

**numba (librosa optional dependency):** numba provides JIT acceleration for some
librosa functions. On ARM it is harder to install (LLVM dependency). However, numba
is NOT required by librosa — it gracefully degrades to pure Python implementations
when numba is not present. **Do not install numba on the Pi.** Set:

```dockerfile
ENV NUMBA_DISABLE_JIT=1
```

This tells numba (if somehow installed) to skip JIT compilation. Combined with
not installing numba at all, this prevents any import-time JIT stall.

**libsndfile:** Required by soundfile (librosa dependency). Bookworm package:
`libsndfile1`. Add to `apt-get install`.

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
```

**Confidence:** HIGH for librosa pure-Python claim (piwheels page confirmed `py3-none-any`);
HIGH for numpy arm64 manylinux availability (piwheels page lists cp311 armv7l wheel, implying
arm64 available natively via PyPI manylinux); MEDIUM for numba degradation claim (librosa
changelog and community reports, not verified on this specific version in ARM Docker).

---

## bgutil PO Token Sidecar on ARM

**bgutil-ytdlp-pot-provider Docker image architecture:** Not explicitly listed on Docker Hub.
The image is Node.js/Deno based. Official Node.js Docker images support arm64.
The bgutil Python plugin package is available on piwheels (pure Python pip install).

**Recommendation:** Run bgutil as a separate container in `docker-compose.yml` using the
official image. If the image does not pull on arm64, use the Node.js base directly:

```dockerfile
# Fallback: custom bgutil container
FROM node:20-slim
RUN npm install -g @imputnet/bgutil-ytdlp-pot-provider
EXPOSE 4416
CMD ["npx", "bgutil-ytdlp-pot-provider"]
```

The Pi's residential IP is the primary YouTube bot-detection defense. The client
chain `tv,ios,web_embedded` (from v1.2) may work WITHOUT bgutil on a residential IP.
**Validate the client chain first before deploying bgutil on the Pi.** bgutil adds
~100MB of Node.js runtime to an already RAM-constrained environment.

**If bgutil is needed:** Pin `brainicism/bgutil-ytdlp-pot-provider:0.8.1` (the version
in requirements.txt), specify `platform: linux/arm64` in compose, and verify it pulls.

**Confidence:** LOW for bgutil ARM Docker image architecture (not confirmed from Docker Hub);
MEDIUM for "residential IP may not need bgutil" (hypothesis based on project's core goal).

---

## Memory Budget: 1GB RAM

The Pi 3B has 1024MB RAM shared between OS, Docker daemon, and all containers.
The GPU memory split (default 64MB for headless) can be reduced to 16MB via
`/boot/firmware/config.txt`: `gpu_mem=16`.

**Realistic memory budget:**

| Component | Estimated RAM | Notes |
|-----------|--------------|-------|
| Raspberry Pi OS (headless) | 150-200MB | Base OS with Docker daemon |
| GPU memory (reduced) | 16MB | Set `gpu_mem=16` in config.txt |
| Redis container | 20-30MB | Minimal with no large datasets |
| FastAPI + Uvicorn (1 worker) | 80-120MB | Python runtime + app code |
| Celery worker (1 process) | 120-200MB | Idle; spikes to 400MB+ during librosa analysis |
| librosa analysis peak | +200-300MB | numpy array allocations for audio FFT |
| WAV file in memory | +50-150MB | 5-min WAV at 44.1kHz stereo = ~120MB |
| **Total peak** | **~800-900MB** | Tight; leaves 100-200MB headroom |
| **With essentia removed** | **No change** | essentia removed for ARM compatibility |
| **With swap (2GB)** | **Safe** | Swap absorbs librosa peak; slower but stable |

**The stack is viable on 1GB + swap. Without swap it will OOM on every librosa call.**

### Required Memory Configuration Changes

**1. Enable swap (2GB recommended):**

```bash
# On the Pi host (not inside Docker)
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

Using a swap file on SD card is acceptable for this workload — audio analysis is
intermittent, not continuous. If the Pi uses an SSD (USB3), swap is much faster.

**2. Celery worker: concurrency=1, max-tasks-per-child=10:**

```yaml
celery:
  command: celery -A celery_app worker --concurrency=1 --max-tasks-per-child=10 --loglevel=info
```

`--concurrency=1` means one audio job at a time. This is correct for the Pi —
parallel jobs would OOM immediately. `--max-tasks-per-child=10` recycles the worker
process every 10 tasks, releasing any leaked memory from librosa/numpy.

**3. Enable Docker memory cgroup support:**

By default on Raspberry Pi OS, Docker's `--memory` limit flag is silently ignored
because memory cgroups are not enabled in the kernel boot parameters.

```bash
# Edit /boot/firmware/cmdline.txt — add to existing line (do NOT add a newline):
cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1
```

After reboot, `docker stats` will show memory limits and Docker will enforce container
memory caps. This allows the Celery container to be killed (not OOM the whole Pi)
if it exceeds limits.

**4. Docker resource limits in compose:**

```yaml
services:
  celery:
    mem_limit: 512m
    memswap_limit: 768m
  api:
    mem_limit: 192m
  redis:
    mem_limit: 64m
```

**Confidence:** HIGH for memory estimates (based on librosa numpy allocation patterns,
community reports for similar stacks); HIGH for cgroup fix (documented Pi-specific issue);
MEDIUM for exact numbers (not benchmarked on this specific codebase on Pi hardware).

---

## Docker Compose Changes for Pi

**Key changes from a hypothetical Railway-equivalent compose:**

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    platform: linux/arm64
    restart: unless-stopped
    mem_limit: 64m
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

  api:
    build:
      context: .
      dockerfile: Dockerfile
    platform: linux/arm64
    restart: unless-stopped
    mem_limit: 192m
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - NUMBA_DISABLE_JIT=1
    volumes:
      - ./cookies.txt:/app/cookies.txt:ro
      - tmp_files:/tmp
    depends_on:
      - redis

  celery:
    build:
      context: .
      dockerfile: Dockerfile
    platform: linux/arm64
    restart: unless-stopped
    mem_limit: 512m
    memswap_limit: 768m
    command: celery -A celery_app worker --concurrency=1 --max-tasks-per-child=10 --loglevel=info
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - NUMBA_DISABLE_JIT=1
    volumes:
      - ./cookies.txt:/app/cookies.txt:ro
      - tmp_files:/tmp
    depends_on:
      - redis

volumes:
  redis_data:
  tmp_files:
```

**restart: unless-stopped** — correct policy for Pi. Containers restart on crash or
reboot unless explicitly stopped by `docker stop`. `always` is equivalent but
`unless-stopped` allows manual stop for maintenance without the container auto-restarting.

**Confidence:** MEDIUM — compose structure is based on known patterns; exact env var
names and volume paths must be aligned with the actual codebase during implementation.

---

## Dockerfile Changes for Pi

The Dockerfile must remove imageio-ffmpeg (x86-bundled binary) and use system FFmpeg.

**Key Dockerfile sections:**

```dockerfile
FROM python:3.11-slim-bookworm

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements-pi.txt .
RUN pip install --no-cache-dir -r requirements-pi.txt

# Application
COPY . /app
WORKDIR /app

ENV NUMBA_DISABLE_JIT=1
```

**requirements-pi.txt** should be identical to `requirements.txt` with these changes:
- REMOVE: `essentia==2.1b6.dev1389` — no ARM wheel available
- REMOVE: `imageio-ffmpeg>=0.5.1` — bundled x86 binary; system FFmpeg replaces it
- KEEP: everything else

The pipeline.py `_resolve_ffprobe()` function (using `shutil.which`) already handles
system-installed ffprobe correctly — no code changes needed there.

**Confidence:** HIGH for removing imageio-ffmpeg (x86 binary confirmed; system apt install works);
HIGH for removing essentia (no ARM wheel confirmed); MEDIUM for requirements-pi.txt approach
(separate requirements file is one option; env var gating is another).

---

## What NOT to Change

| Item | Reason |
|------|--------|
| FastAPI + Celery + Redis application code | Validated stack, runs on any Python 3.11; no ARM-specific changes |
| yt-dlp client chain (`tv,ios,web_embedded`) | Carried forward from v1.2; IP change (residential) is the variable |
| cookies.txt approach | Same mechanism, mounted via Docker volume |
| Rate limiting, security gate controls | All Python/FastAPI; no ARM impact |
| Redis auth | No change |
| The 15-minute video length limit | No change |
| librosa BPM detection logic | No change in pipeline.py; just remove essentia calls |

---

## Pi-Specific Pi Setup Commands (for setup script)

```bash
# 1. Reduce GPU memory
echo 'gpu_mem=16' | sudo tee -a /boot/firmware/config.txt

# 2. Enable cgroups memory for Docker memory limits
sudo sed -i '$ s/$/ cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1/' \
    /boot/firmware/cmdline.txt

# 3. Enable swap (2GB)
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup && sudo dphys-swapfile swapon

# 4. Install Docker (official script for Raspberry Pi OS)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 5. Reboot required after steps 1-3
sudo reboot
```

**Confidence:** HIGH for GPU memory and cgroup steps (official Pi documentation patterns);
HIGH for swap steps (standard dphys-swapfile tool); HIGH for Docker install script
(official Docker docs for Raspberry Pi OS).

---

## Summary of Stack Changes for Pi

| Layer | Railway | Raspberry Pi 3B | Change Required |
|-------|---------|-----------------|-----------------|
| OS/Platform | Linux x86_64 | Linux arm64 (64-bit Pi OS) | OS install decision |
| Python runtime | Railway-managed | `python:3.11-slim-bookworm` Docker | Dockerfile |
| FFmpeg + ffprobe | nixpacks system install | `apt-get install ffmpeg` in Dockerfile | Dockerfile |
| imageio-ffmpeg | Installed (x86 bundled binary) | REMOVE | requirements-pi.txt |
| essentia | Installed (x86 wheel) | REMOVE — no ARM wheel | requirements-pi.txt |
| librosa | Installed (pure Python) | Keep — pure Python, works on ARM | No change |
| numpy | Installed (x86 wheel) | Keep — arm64 manylinux wheel on PyPI | No change |
| Redis | Railway Redis service | `redis:7-alpine` container | docker-compose.yml |
| Celery concurrency | Not explicitly set (Railway scales) | `--concurrency=1` mandatory | docker-compose.yml |
| Memory limits | Not needed (Railway manages) | All containers capped; swap enabled | Pi OS + compose |
| Restart policy | Railway handles | `restart: unless-stopped` | docker-compose.yml |
| bgutil sidecar | Optional (had connectivity issues) | Defer — test client chain first | Validate first |

---

## Sources (v1.3 Addendum)

| Source | Confidence | URL |
|--------|------------|-----|
| essentia PyPI — no Linux ARM wheel | HIGH | https://pypi.org/project/essentia/ |
| piwheels librosa 0.11.0 — py3-none-any | HIGH | https://www.piwheels.org/project/librosa/ |
| piwheels numpy 2.4.4 cp311 armv7l | HIGH | https://www.piwheels.org/project/numpy/ |
| arm32v7/python Docker Hub tags | HIGH | https://hub.docker.com/r/arm32v7/python/ |
| arm64v8/redis Docker Hub | HIGH | https://hub.docker.com/r/arm64v8/redis/ |
| mwader/static-ffmpeg — amd64 + arm64 only | HIGH | https://hub.docker.com/r/mwader/static-ffmpeg/ |
| linuxserver/ffmpeg — armhf deprecated since 2023 | HIGH | https://docs.linuxserver.io/images/docker-ffmpeg/ |
| Docker cgroup memory Pi fix | HIGH | https://dalwar23.com/how-to-fix-no-memory-limit-support-for-docker-in-raspberry-pi/ |
| bgutil Docker Hub | LOW | https://hub.docker.com/r/brainicism/bgutil-ytdlp-pot-provider |
| Celery --max-tasks-per-child docs | HIGH | https://docs.celeryq.dev/en/stable/userguide/workers.html |
