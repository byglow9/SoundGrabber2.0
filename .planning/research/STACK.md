# Technology Stack — SoundGrabber

**Project:** SoundGrabber (YouTube audio downloader + BPM/key detector)
**Researched:** 2026-04-29
**Research confidence:** MEDIUM-HIGH (most claims verified against official docs or multiple sources; YouTube download reliability is structurally uncertain)

---

## Recommended Stack

### Backend Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | Ships with asyncio, widely supported on all PaaS targets; 3.11 has meaningful performance improvements over 3.10; yt-dlp dropped Python <3.10 support as of late 2025 |
| FastAPI | 0.115+ (latest: ~0.136) | HTTP API + file serving | Async-native, excellent for long-running background tasks, minimal boilerplate, native Pydantic validation for URL inputs, easy streaming file responses |
| Uvicorn | 0.30+ | ASGI server | Standard production server for FastAPI; use with `--workers N` or Gunicorn+uvicorn workers for multi-process |

**Why FastAPI over Flask/Django:** Flask is sync-by-default (bad for I/O-heavy downloads); Django carries ORM/auth overhead this app will never use. FastAPI's `BackgroundTasks` or direct asyncio integration is the right primitive for the download-then-process-then-serve pattern.

**Why NOT Node.js/Express:** Python is the lingua franca for audio DSP. librosa, Essentia, and every other audio analysis library target Python. A Node backend would require spawning Python child processes for analysis — an unnecessary seam.

---

### Task Execution Model

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI BackgroundTasks | built-in | Fire-off download+process job | Sufficient for the traffic profile (hundreds of concurrent users, not thousands of simultaneous downloads); no Redis/broker dependency |

**Architecture decision:** For this scale (underground producer community, not viral SaaS), FastAPI's built-in `BackgroundTasks` is the correct choice. The flow is:

1. POST `/process` → validate URL → enqueue background task → return `job_id` immediately
2. Background task: download → convert → analyze → write result to in-memory dict keyed by `job_id`
3. GET `/status/{job_id}` → client polls until complete
4. GET `/download/{job_id}` → stream WAV file, then clean up temp file

**When to upgrade to Celery/ARQ + Redis:** If the app needs persistent job queues across server restarts, retries on failure, or sustained queue depths of 100+ concurrent jobs. At launch, this is premature. The complexity of a Redis broker is not justified by the scale described in PROJECT.md.

**Why NOT Celery at launch:** Celery requires a Redis/RabbitMQ broker, a separate worker process, and monitoring tooling (Flower). For a stateless public tool at community scale, this is significant operational overhead with no proportional benefit.

**ARQ as the upgrade path:** If BackgroundTasks proves insufficient, ARQ (async-native Redis queue, ~700 LOC) is the right step before Celery. It integrates cleanly with FastAPI's asyncio event loop and avoids Celery's sync-world impedance mismatch.

---

### YouTube Download

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| yt-dlp | 2026.03.17 (date-versioned) | YouTube audio download | The definitive fork of youtube-dl; actively maintained with near-weekly releases; only viable maintained option in 2025-2026 |

**Confidence: MEDIUM** — yt-dlp works reliably but YouTube's bot detection creates ongoing operational risk (see below).

**Python API configuration for audio-only WAV:**

```python
import yt_dlp

def download_audio(url: str, output_path: str) -> str:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path + '/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'quiet': True,
        'no_warnings': True,
        'http_chunk_size': 10485760,  # 10MB — avoids YouTube throttling trigger
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info['id']
```

**Critical known issues with yt-dlp on servers (2025-2026):**

1. **PO Token / bot detection:** YouTube introduced Proof-of-Origin Tokens (PO tokens) that bind to each video ID. On server IPs (especially shared PaaS), YouTube fingerprints requests as bots and returns HTTP 429 or demands CAPTCHA. PO tokens now expire per-video — there is no persistent server-side bypass. The `mweb` client with manual PO token setup is the current recommended workaround, but it requires ongoing maintenance.

2. **Cookie-based auth:** Passing `--cookies-from-browser chrome` works locally but fails on headless servers (no browser binary). Cookie files degrade quickly. There is no safe automated server-side cookie refresh.

3. **IP reputation:** Shared PaaS IPs (Render, Railway free tiers) are heavily flagged. Residential proxies or dedicated server IPs significantly improve success rate.

4. **Throttling trigger:** YouTube throttles requests with HTTP chunk sizes > 10MB. Always set `http_chunk_size` in yt-dlp config.

**Mitigation strategy:**
- Keep yt-dlp pinned to latest (`pip install -U yt-dlp` as part of deployment)
- Handle `DownloadError` gracefully and surface a user-facing "Video unavailable" message
- Accept that ~5-15% of requests may fail due to YouTube restrictions; do not treat this as a bug to fix at launch

**What NOT to use:**
- `youtube-dl` (unmaintained since 2021 — GitHub takedown aftermath effectively killed it)
- `pytube` (brittle, frequently broken by YouTube cipher changes, no active maintainer parity with yt-dlp)
- YouTube Data API v3 (does not provide download access — only metadata)

---

### Audio Conversion

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FFmpeg | 6.x or 7.x (system package) | Audio decode/encode/convert | The gold standard; yt-dlp uses it internally for post-processing; no Python wrapper needed for this use case |

**Confidence: HIGH**

yt-dlp's `FFmpegExtractAudio` postprocessor with `preferredcodec: 'wav'` handles the full conversion pipeline — there is no need to call FFmpeg separately. The audio arrives from YouTube in its native format (usually Opus/WebM or AAC/M4A) and yt-dlp invokes FFmpeg automatically to decode and re-encode as WAV.

**Do NOT use for conversion:**
- `pydub`: Wraps FFmpeg with an extra Python layer; useful for audio editing, not needed here since yt-dlp already handles conversion. Adds a dependency for zero benefit.
- `soundfile`: Excellent for reading/writing already-decoded PCM, but cannot decode Opus/AAC source formats — pointless without FFmpeg.
- `ffmpeg-python`: A Python FFmpeg binding. Use only if you need programmatic control over the FFmpeg pipeline beyond what yt-dlp exposes (e.g., resampling to a specific sample rate before analysis). Not needed at launch.

**Output format:** 16-bit PCM WAV at 44100 Hz (CD quality). This is the WAV default from FFmpeg and is appropriate for producer workflows. No custom FFmpeg flags needed beyond the yt-dlp postprocessor.

---

### BPM Detection

**Recommendation: librosa `beat_track` / `feature.tempo` as primary; Essentia `RhythmExtractor2013` as optional upgrade**

**Confidence: MEDIUM** (no definitive published accuracy benchmark for beats/electronic music found; recommendation is based on ecosystem analysis and production usage evidence)

| Library | Approach | Accuracy (electronic/hip-hop) | Speed | Install complexity | Verdict |
|---------|----------|-------------------------------|-------|--------------------|---------|
| **librosa 0.11** | Ellis (2007) dynamic programming beat tracking | "Within ±1 BPM for most commercial music" (StemSplit production data); relies on onset detection | Moderate (~2-5s for 3min audio) | `pip install librosa` — pure Python + numpy/scipy | **Recommended for launch** |
| **Essentia 2.1** | RhythmExtractor2013 — multifeature or degara mode | Generally considered comparable or better than librosa for rhythmically complex material | ~2x faster than librosa | C++ extension — larger Docker image, `pip install essentia` works but adds ~500MB compiled deps | Upgrade path if librosa proves inaccurate |
| **aubio** | Phase vocoder + HFC onset detection | Known accuracy problems reported in community comparisons | Fast | `pip install aubio` — C extension | Do NOT use — accuracy reputation is poor |

**Why librosa at launch:**
- Single `pip install` with no native compilation surprises
- Proven in production at StemSplit (same use case)
- 85-95% accuracy on pop/rock/electronic covers the SoundGrabber target audience (underground beats are rhythmically regular)
- The Ellis algorithm works well for 4/4 material which dominates the use case

**librosa usage pattern:**

```python
import librosa

def detect_bpm(wav_path: str) -> float:
    # Load 60 seconds — sufficient for tempo; >60s adds latency without accuracy gain
    y, sr = librosa.load(wav_path, duration=60.0)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    # beat_track returns ndarray; extract scalar
    return float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
```

**Known limitation:** librosa assumes a single global tempo. For tracks with significant tempo changes, PLP (Predominant Local Pulse) mode is more reliable:

```python
pulse = librosa.beat.plp(onset_envelope=librosa.onset.onset_strength(y=y, sr=sr))
tempo_estimate = librosa.feature.tempo(y=y, sr=sr)[0]
```

**What NOT to use:**
- `aubio` — accuracy reputation is the weakest of the three options
- `music21` for BPM — music21 is a symbolic music toolkit (MIDI/MusicXML), not an audio signal analyzer; it has no BPM detection from raw audio

---

### Musical Key Detection

**Recommendation: librosa chroma + Krumhansl-Schmuckler correlation for launch; Essentia KeyExtractor as upgrade**

**Confidence: MEDIUM** (85-95% accuracy on commercial/electronic music per StemSplit; modal/atonal music excluded)

| Library | Algorithm | Accuracy | Notes |
|---------|-----------|----------|-------|
| **librosa** (chroma_cqt + correlation) | Krumhansl-Schmuckler key profiles | 85-95% for pop/rock/electronic (StemSplit) | Requires manual profile matching implementation (~30 lines) |
| **Essentia KeyExtractor** | HPCP + 16 key profiles (default: bgate) | Comparable; supports 16 profiles including 'temperley', 'edma', 'bgate' | Returns key + scale + strength confidence score; single function call; more production-ready |
| **music21** | Symbolic analysis (Krumhansl-Schmuckler on MIDI) | N/A for raw audio | music21 works on symbolic music notation, NOT audio signals — completely wrong tool for this |

**Decision:** Use Essentia's `KeyExtractor` rather than librosa's raw chroma if you already have Essentia installed for RhythmExtractor2013. The Essentia API is cleaner (one call returns key, scale, and confidence), supports more key profiles, and includes built-in tuning correction. If only librosa is installed, implement chroma correlation manually.

**If using librosa only (simpler dependency tree):**

```python
import librosa
import numpy as np

# Key profiles (Krumhansl-Schmuckler)
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def detect_key(wav_path: str) -> str:
    y, sr = librosa.load(wav_path, duration=120.0)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    major_corrs = [np.corrcoef(np.roll(_MAJOR, i), chroma_mean)[0, 1] for i in range(12)]
    minor_corrs = [np.corrcoef(np.roll(_MINOR, i), chroma_mean)[0, 1] for i in range(12)]
    best_major = np.argmax(major_corrs)
    best_minor = np.argmax(minor_corrs)
    if major_corrs[best_major] >= minor_corrs[best_minor]:
        return f"{_NOTES[best_major]} major"
    return f"{_NOTES[best_minor]} minor"
```

**If using Essentia (better for production, higher accuracy on edge cases):**

```python
import essentia.standard as es

def detect_key(wav_path: str) -> tuple[str, str, float]:
    loader = es.MonoLoader(filename=wav_path)
    audio = loader()
    key_extractor = es.KeyExtractor()
    key, scale, strength = key_extractor(audio)
    return key, scale, strength  # e.g. ("F#", "minor", 0.84)
```

**music21 verdict — DO NOT USE for audio key detection.** music21 is a computational musicology library for working with symbolic representations (MIDI, MusicXML, ABC notation). It has zero capability to analyze a WAV file's key from audio signals. Its Krumhansl-Schmuckler implementation operates on MIDI pitch sequences, not waveforms.

---

### Frontend

**Recommendation: Plain HTML + Vanilla JS (no framework)**

**Confidence: HIGH**

| Option | Size | DX | Appropriate for SoundGrabber? |
|--------|------|----|-------------------------------|
| **Vanilla HTML/CSS/JS** | ~0KB framework overhead | Simple | YES — single page, 2 states (input / result) |
| HTMX | 14KB | Good for server-rendered partials | Overkill — no multi-step navigation |
| React / Vue / Svelte | 80-200KB+ | Good for complex state | Gross overkill — 2 interactive elements |

**Rationale:** SoundGrabber has one screen: a URL input box, a submit button, a status indicator (polling), and a result card (BPM, key, download button). This is three DOM mutations total. React, Vue, and Svelte are category errors here. HTMX is elegant for CRUD interfaces with server-rendered partials but adds complexity to a simple polling pattern.

**The right tool:** A single `index.html` + `static/app.js` (< 100 lines) served directly by FastAPI's `StaticFiles` mount. The 2000s aesthetic (phpBB/Orkut/Tibia) is best built in raw CSS anyway — no component library will have those retro patterns.

**JS pattern:** `fetch('/process', {method: 'POST', body: formData})` → receive `job_id` → `setInterval` poll `/status/{job_id}` → on complete, reveal result card and download link. This is ~60 lines of vanilla JS.

**CSS:** Hand-written. The retro aesthetic (table-based layouts, pixel fonts, gradient backgrounds, bordered boxes with `#c0c0c0` chrome) is only achievable with deliberate raw CSS. Tailwind or Bootstrap will actively fight this aesthetic.

**What NOT to use:**
- React — no stateful component graph exists; entire app is one form + one result display
- Next.js / Nuxt — server-side rendering framework for a tool this simple is architectural malpractice
- HTMX — the polling pattern is simpler in vanilla JS than as an HTMX extension

---

### Deployment and Hosting

**Confidence: MEDIUM** (free tiers are volatile; pricing/features change; information reflects 2025-2026 state)

**Primary recommendation: Render (Web Service, Starter plan ~$7/mo) or Railway (Hobby plan ~$5/mo) with Docker**

| Platform | Free Tier | Suitable? | Notes |
|----------|-----------|-----------|-------|
| **Render** | 750 hrs/mo, sleeps after 15min idle | Dev/testing only | Starter plan ($7/mo) for always-on; supports Docker natively |
| **Railway** | No free tier (removed Aug 2023) | Paid from day 1 | Hobby plan ~$5/mo; excellent DX; native Dockerfile support |
| **Fly.io** | No free tier for new accounts (one-time $5 credit) | Paid from day 1 | Good for Docker; requires `fly.toml` config |
| **VPS (Hetzner/DigitalOcean)** | €3-5/mo (CX11/Droplet) | Best value at scale | Full control; install ffmpeg/Python directly; no cold-starts; best IP reputation for yt-dlp |
| **AWS/GCP/Azure** | Free tiers with limits | Over-engineered for v1 | Lambda cold starts are hostile to audio processing latency; ECS adds operational complexity |

**Recommended for launch:** Render Starter ($7/mo) — simplest deployment path. Push a Dockerfile, connect GitHub repo, done. No DevOps knowledge required.

**Recommended at scale:** Hetzner CX21 VPS (~€5/mo, 2 vCPU, 4GB RAM) — better IP reputation for yt-dlp (shared PaaS IPs are heavily bot-flagged by YouTube), full control over ffmpeg/Python versions, no cold-start latency, cost-effective.

**Containerization strategy:**

```dockerfile
FROM python:3.11-slim

# Install ffmpeg (system dep)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Image size note:** `python:3.11-slim` + ffmpeg + librosa + FastAPI + yt-dlp is approximately 800MB-1.2GB. If Essentia is added, expect 1.5-2GB due to C++ compiled extensions. Use multi-stage builds to reduce further. This is acceptable for a VPS/PaaS deployment; it would be problematic for Lambda.

**Serverless (Lambda/Cloud Run) — DO NOT use:** Audio processing is compute and memory intensive. The 512MB-1GB Lambda memory cap makes librosa analysis of a 3-minute WAV marginal. Cold starts of 5-15 seconds are hostile to the UX. WAV files can be 50-200MB — Lambda's ephemeral `/tmp` cap is 512MB-10GB (configurable but adds cost). The stateless PaaS model is far more appropriate.

---

### Storage and State

**No database required.** This is a stateless processing tool.

| Concern | Approach |
|---------|----------|
| Job state | In-memory dict in the FastAPI process (`{job_id: {status, bpm, key, wav_path}}`) |
| WAV files | Written to `tempfile.mkdtemp()` on server; deleted after download completes or after TTL (e.g., 5 minutes) |
| Concurrent job tracking | Python `asyncio.Lock` on the job dict for thread safety |
| Persistence across restarts | Not needed — jobs are ephemeral |

**Why not Redis for state:** The job lifecycle is short (< 60 seconds from submit to download). Redis adds a broker dependency with zero benefit at this scale. A dict works; if the server restarts mid-job, the client sees a timeout and retries.

---

### Key Versions (2026-04 snapshot)

| Package | Pinned version | Notes |
|---------|---------------|-------|
| `yt-dlp` | `>=2026.3.0` or latest | Date-versioned; pin to latest at deploy time; update frequently |
| `fastapi` | `>=0.115,<1.0` | Stable API; avoid unpinned pre-1.0 |
| `uvicorn[standard]` | `>=0.30` | Includes websockets and httptools extras |
| `librosa` | `>=0.11.0` | 0.11 introduced `beat.plp` improvements |
| `soundfile` | `>=0.12` | Required by librosa for WAV I/O |
| `numpy` | `>=1.24,<2.0` | librosa 0.11 numpy 2.x compatibility is partial; pin <2.0 to be safe |
| `scipy` | `>=1.10` | librosa dependency |
| `httpx` | `>=0.27` | If you add any outbound HTTP calls |
| `python-multipart` | `>=0.0.9` | FastAPI form data parsing |

**System packages (apt/brew):**
- `ffmpeg` >= 6.0 (required by yt-dlp postprocessor)
- `libsndfile1` (required by soundfile/librosa on Linux)

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Backend | FastAPI | Flask | Sync-first; no background task primitives |
| Backend | FastAPI | Django | ORM/auth overhead; no async audio task primitives |
| Backend | FastAPI | Node.js + Express | No audio analysis libraries; subprocess seam to Python |
| Download | yt-dlp | pytube | Brittle; frequently broken; no active parity with yt-dlp |
| Download | yt-dlp | youtube-dl | Unmaintained since 2021 |
| Download | yt-dlp | YouTube Data API | No download capability; metadata only |
| BPM | librosa | aubio | Known accuracy issues; smaller ecosystem |
| BPM | librosa | music21 | Symbolic music toolkit; cannot analyze audio signals |
| Key | librosa chroma | music21 | Works on MIDI/notation only, not audio waveforms |
| Conversion | yt-dlp+FFmpeg | pydub | Redundant wrapper; yt-dlp already handles conversion |
| Frontend | Vanilla JS | React | No component graph exists; single form + result card |
| Frontend | Vanilla JS | HTMX | Polling pattern is simpler in vanilla JS |
| Task queue | BackgroundTasks | Celery | Broker dependency unjustified at this scale |
| Hosting | Render/VPS | Lambda/Cloud Run | Serverless hostile to audio processing latency + memory |

---

## Critical Risk: YouTube Download Reliability

**This is the highest-risk dependency in the stack.** YouTube actively works against automated downloading. The situation in 2025-2026:

- PO tokens now bind to individual video IDs — no persistent server-side bypass exists
- Shared PaaS IPs are heavily flagged; YouTube returns 429 more readily than residential IPs
- Cookie-based auth breaks on headless servers and degrades over time
- yt-dlp releases patches frequently — running outdated versions dramatically increases failure rate

**Mitigation (incorporated into stack):**
1. Always run latest yt-dlp (auto-update on deploy)
2. Handle `DownloadError` gracefully with user-friendly error messages
3. Prefer a VPS with a dedicated IP over shared PaaS for production
4. Accept a ~10-20% failure rate as a structural constraint, not a bug
5. Do not attempt to bypass bot detection with proxy rotation at v1 — complexity not worth it for community scale

---

## Milestone v1.1 Stack Additions: Audio Analysis Precision

**Researched:** 2026-05-09
**Scope:** New library additions only for BPM precision, key precision, and tuning (A = X Hz) detection.

### What Tunebat Actually Uses — Confirmed

**Confidence: HIGH** (verified from Tunebat's own analyzer page + official essentia.js documentation)

Tunebat's analyzer is "powered by industry leading technology developed by the Music Technology Group at UPF." The browser-based tool uses **essentia.js** — the WebAssembly port of Essentia's C++ library that runs entirely client-side. Files are never uploaded to a server.

For our server-side Python pipeline, the direct equivalent is **Essentia's Python bindings** (`pip install essentia`). Same algorithms, same MTG origin, same accuracy profile. This is confirmed, not guessed.

---

### New Library: Essentia (replaces librosa for BPM + key)

**pip install:** `pip install essentia`
**Version:** 2.1b6.dev1389 (released July 2025 — this is the standard distribution; Essentia ships as beta dev releases by convention but is production-stable)
**Python 3.11 on Linux x86_64:** YES — pre-built manylinux wheel confirmed: `essentia-2.1b6.dev1389-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` (13.8 MB). No compilation required.
**Coexistence with librosa:** No dependency conflicts. Both use numpy. Can be imported in the same process.

**Do NOT install:** `essentia-tensorflow` — that variant adds TempoCNN (neural BPM) which requires TensorFlow. Not needed; `RhythmExtractor2013` does not require TF.

#### BPM: RhythmExtractor2013 (multifeature mode)

Essentia's primary recommendation for beat and tempo estimation. Uses multiple onset detection functions fused together, which makes it resistant to the half-tempo / double-tempo octave errors that are librosa's main failure mode on syncopated beats and trap music. Returns BPM, individual beat timestamps, and a confidence score.

```python
import essentia.standard as es

audio = es.MonoLoader(filename=wav_path, sampleRate=44100)()
rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
bpm, beats, beats_confidence, _, beats_intervals = rhythm_extractor(audio)
```

`method="multifeature"` is slower but more accurate than `"degara"`. For a background Celery task the extra 1-2 seconds is irrelevant.

#### Key: KeyExtractor with edma profile

Essentia's `KeyExtractor` computes HPCP (Harmonic Pitch Class Profile) across the full audio then correlates against a key template. HPCP uses spectral peaks with harmonic weighting and non-linear whitening, which is more robust than librosa's chroma_cqt for polyphonic material that does not follow classical voice-leading conventions (electronic, hip-hop, trap).

**Profile selection for SoundGrabber's target domain (beats, electronic, hip-hop):**

| Profile | Description | Use |
|---------|-------------|-----|
| `edma` | Extracted from corpus of electronic dance music. Outperforms generic profiles on EDM. | **Use this as primary** |
| `edmm` | Same EDM corpus, manually tweaked. Reports poorly-represented major modes as minor. | Fallback if edma produces many false majors |
| `bgate` | Default; generic. Less tuned for electronic music. | Do not use |
| `krumhansl` | Classic academic profile; good for tonal Western. | Not EDM-optimized |

Feed the tuning frequency (from the step below) into `KeyExtractor` so HPCP bins align to the actual concert pitch of the audio, not assumed A=440Hz. This matters for A=432Hz content.

```python
import essentia.standard as es

# tuning_hz comes from the tuning detection step below
audio = es.MonoLoader(filename=wav_path, sampleRate=44100)()
key_extractor = es.KeyExtractor(profileType='edma', tuningFrequency=tuning_hz)
key, scale, strength = key_extractor(audio)
# key: "F#", scale: "minor", strength: 0.84 (0-1 confidence)
```

---

### Tuning Detection: librosa (no new library needed)

**Confidence: HIGH** (verified against official librosa 0.11.0 docs)

librosa already has the exact functions needed. No new dependency required.

The pipeline is two function calls:

```python
import librosa

y, sr = librosa.load(wav_path, sr=None, mono=True)

# Step 1: estimate tuning deviation in fractions of a bin (resolution=0.01 = cents)
tuning = librosa.estimate_tuning(y=y, sr=sr, resolution=0.01)

# Step 2: convert deviation to A4 reference frequency in Hz
tuning_hz = librosa.tuning_to_A4(tuning)
# tuning_hz is float, e.g. 440.0, 431.8, 444.2

# For display: round to nearest integer
a4_display = round(tuning_hz)  # e.g. "A = 432 Hz"
```

`librosa.tuning_to_A4` is confirmed present in librosa 0.10.2+ and 0.11.0. It converts a fractional bin deviation (what `estimate_tuning` returns) directly to the A4 reference frequency in Hz, assuming equal temperament. Example: tuning input of -0.318 returns approximately 431.992 Hz.

**Execution order in the analysis task:** Run tuning detection FIRST, then pass `tuning_hz` to `KeyExtractor`. This ensures HPCP computation uses the audio's actual concert pitch.

**Essentia TuningFrequency as a future upgrade:** Essentia has its own `TuningFrequency` algorithm that processes spectral peaks frame-by-frame and returns Hz + cents offset from 440. It is more rigorous for truly non-standard tunings. For v1.1, librosa's one-liner is sufficient. If testing shows tuning detection is unreliable on heavily percussive beats (sparse harmonic content), switch to Essentia's algorithm using the spectral peaks already computed during key detection.

---

### Libraries Evaluated and Rejected for v1.1

| Library | Reason for rejection |
|---------|----------------------|
| madmom | PyPI release (0.16.1) declares `python<3.10`. Dev version from GitHub requires manual patches to `processors.py` for `MutableSequence`. Largely unmaintained (last PyPI release 2018). Not worth the maintenance debt. |
| aubio | Last PyPI release: version 0.4.9, February 2019. Source distribution only — no wheels. Requires aubio C library as a system dependency. Unmaintained for 6+ years. |
| beat_this (CPJKU) | Requires PyTorch >= 2 + torchaudio + einops + soxr + rotary-embedding-torch. A 2–3 GB dependency chain for a web service. The project's own issue tracker confirms its madmom dependency blocks Python 3.10+. Overkill for this use case. |
| CREPE | Monophonic pitch tracker — estimates the fundamental frequency of a single melodic line. Cannot estimate concert pitch (A = X Hz) for polyphonic audio. Wrong category of tool entirely. |
| KeyFinder (libKeyFinder) | No official Python bindings on PyPI. The `shaath` key profile from its author (Ibrahim Shaath) is available directly in Essentia's KeyExtractor. No integration complexity justified. |
| essentia-tensorflow | TempoCNN variant requiring TensorFlow. RhythmExtractor2013 does not need TF. Adds ~2GB of dependencies for zero benefit in this use case. |

---

### v1.1 Integration: Revised Analysis Task Structure

The existing Celery analysis task loads audio with librosa once. After v1.1 changes, the task flow is:

1. FFmpeg produces WAV from download (unchanged)
2. Load audio with librosa for tuning: `librosa.load(wav_path, sr=None, mono=True)`
3. Detect tuning: `librosa.estimate_tuning()` → `librosa.tuning_to_A4()` → `tuning_hz`
4. Load audio with Essentia: `es.MonoLoader(filename=wav_path, sampleRate=44100)()`
5. Detect BPM: `es.RhythmExtractor2013(method="multifeature")(audio)` → `bpm`
6. Detect key: `es.KeyExtractor(profileType='edma', tuningFrequency=tuning_hz)(audio)` → `key, scale, strength`
7. Return: `{bpm, key, scale, strength, tuning_hz}` to the job result dict

**Fallback principle:** If Essentia import fails at runtime (unlikely but defensive), fall back to the existing librosa-based BPM and key logic rather than returning no result.

---

## Sources

- [yt-dlp GitHub repository](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [yt-dlp GitHub issue #13067 — bot detection](https://github.com/yt-dlp/yt-dlp/issues/13067)
- [yt-dlp GitHub issue #13891 — VPS cookie auth](https://github.com/yt-dlp/yt-dlp/issues/13891)
- [librosa 0.11 beat_track documentation](https://librosa.org/doc/main/generated/librosa.beat.beat_track.html)
- [librosa 0.11 beat and tempo module](https://librosa.org/doc/0.11.0/beat.html)
- [Essentia KeyExtractor algorithm reference](https://essentia.upf.edu/reference/std_KeyExtractor.html)
- [Essentia RhythmExtractor2013 reference](https://essentia.upf.edu/reference/std_RhythmExtractor2013.html)
- [Essentia beat detection tutorial](https://essentia.upf.edu/tutorial_rhythm_beatdetection.html)
- [FastAPI background tasks documentation](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [StemSplit BPM/key detection feature article (2025)](https://stemsplit.io/blog/bpm-key-detection-feature)
- [Audet — librosa + Essentia BPM/key tool on GitHub](https://github.com/makalin/Audet)
- [Tunebat Analyzer (essentia.js confirmation)](https://tunebat.com/Analyzer)
- [essentia.js project page](https://mtg.github.io/essentia.js/)
- [Essentia PyPI — Python 3.11 wheels confirmed](https://pypi.org/project/essentia/)
- [Essentia installing docs](https://essentia.upf.edu/installing.html)
- [Essentia TuningFrequency streaming reference](https://essentia.upf.edu/reference/streaming_TuningFrequency.html)
- [librosa.estimate_tuning docs](https://librosa.org/doc/main/generated/librosa.estimate_tuning.html)
- [librosa.tuning_to_A4 docs](https://librosa.org/doc/main/generated/librosa.tuning_to_A4.html)
- [madmom Python 3.10+ issue (beat_this #9)](https://github.com/CPJKU/beat_this/issues/9)
- [aubio PyPI — 2019, no wheels](https://pypi.org/project/aubio/)
- [Essentia edma/edmm profile — MTG issue #744](https://github.com/MTG/essentia/issues/744)
- [ARQ vs Celery comparison](https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications)
- [FastAPI BackgroundTasks vs ARQ + Redis](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/)
- [Render FastAPI deployment](https://render.com/articles/fastapi-deployment-options)
- [Railway FastAPI guide](https://docs.railway.com/guides/fastapi)
- [Python hosting comparison 2025](https://www.nandann.com/blog/python-hosting-options-comparison)
- [HTMX vs React 2025](https://cssauthor.com/htmx-vs-react-which-is-better-for-your-next-project/)
