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
