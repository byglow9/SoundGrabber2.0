# Architecture Patterns — SoundGrabber

**Domain:** YouTube audio downloader + audio analysis web utility
**Researched:** 2026-04-29
**Confidence:** HIGH (stack well-established; YouTube blocking is the one HIGH-risk unknown)

---

## System Overview

SoundGrabber is a stateless, no-auth public utility. A user submits a YouTube URL, a backend
pipeline downloads the audio, converts it to WAV, runs BPM/key detection, then serves the
WAV file for direct browser download. The analysis results (BPM, key) accompany the file.

There are no user accounts, no persistent records of jobs, and no long-term storage.
Everything lives in temporary files that are deleted after the download completes.

---

## Component Boundaries

```
┌──────────────────────────────────────────────────────────────────┐
│  BROWSER (React + Vite)                                          │
│                                                                  │
│  ┌──────────────┐   POST /jobs        ┌────────────────────┐    │
│  │  URL input   │ ─────────────────►  │  Job status poller │    │
│  └──────────────┘                     │  (SSE or polling)  │    │
│                                       └────────┬───────────┘    │
│                                                │ GET /jobs/{id} │
└────────────────────────────────────────────────┼───────────────-┘
                                                 │
                          HTTPS / same-origin    │
                                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  API LAYER  (FastAPI + Uvicorn, 2-4 workers)                     │
│                                                                  │
│  POST /jobs       → enqueue task, return job_id                  │
│  GET  /jobs/{id}  → return status + result metadata             │
│  GET  /files/{id} → StreamingResponse of WAV, then cleanup      │
│  Rate limiter middleware (IP + Redis sliding window)             │
└────────────────────────┬─────────────────────────────────────────┘
                         │  task publish / result read
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  MESSAGE BROKER  (Redis)                                         │
│                                                                  │
│  - Celery task queue                                             │
│  - Rate-limit counters (IP sliding window, TTL-keyed)           │
│  - Job result store (job_id → {status, bpm, key, file_path})    │
│    TTL: 10 minutes per job entry                                 │
└────────────────────────┬─────────────────────────────────────────┘
                         │  consume tasks
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  PROCESSING WORKERS  (Celery, 2-4 processes)                     │
│                                                                  │
│  Task: process_youtube_url(job_id, url)                          │
│    1. yt-dlp  → download best audio stream                       │
│    2. ffmpeg  → convert to WAV (via yt-dlp postprocessor)       │
│    3. librosa → beat_track() for BPM                            │
│    4. librosa → chroma_cqt() + key profile for musical key      │
│    5. Write result to Redis; temp file path stored               │
│                                                                  │
│  Workers are separate OS processes — CPU-bound librosa work      │
│  does NOT block the FastAPI event loop.                          │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  TEMP FILE STORAGE  (/tmp/soundgrabber/{job_id}/)                │
│                                                                  │
│  - WAV files live here until download completes                  │
│  - Each job owns an isolated subdirectory                        │
│  - Cleanup: BackgroundTask fires after StreamingResponse ends   │
│  - Fallback sweeper: cron every 15 min, deletes dirs > 20 min   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Async Processing: Why Celery + Redis, Not FastAPI BackgroundTasks

FastAPI's built-in `BackgroundTasks` runs in the same process as the API server. yt-dlp and
librosa are both CPU/IO-heavy and blocking — they will freeze the event loop and starve other
requests. This is the most common mistake in apps that do media processing.

The correct split:

| Concern | Solution | Why |
|---------|----------|-----|
| Accept request fast | FastAPI endpoint returns job_id immediately | Keeps API responsive |
| Long download + conversion | Celery worker (separate process) | Doesn't block event loop |
| CPU-bound audio analysis | Celery worker (separate process, bypasses GIL) | librosa is pure CPU |
| Job state | Redis key with TTL | Fast reads, no DB needed for a stateless tool |
| File persistence across processes | Shared /tmp path stored in Redis | Simple, no object storage needed |

Celery workers run with `--concurrency=2` per machine initially. Each worker handles one job
at a time (download → convert → analyze is sequential per job). This prevents disk I/O
saturation from multiple simultaneous downloads.

---

## Status Communication: Polling Over SSE

For this use case, **polling every 2 seconds** is the right call over SSE or WebSockets:

- Jobs take 15-60 seconds. A 2s poll interval means at most ~30 status checks — negligible.
- SSE requires a persistent HTTP connection per client. At hundreds of concurrent users this
  becomes a connection-count problem for a small server.
- WebSockets add bidirectional complexity for a one-way notification use case.
- Polling is trivially retryable and works correctly behind any CDN or proxy.

Status endpoint response shape:

```json
{
  "job_id": "abc123",
  "status": "queued | processing | done | error",
  "progress": "downloading | converting | analyzing",
  "bpm": 138.5,
  "key": "F# minor",
  "download_url": "/files/abc123",
  "error": null
}
```

Frontend polls `GET /jobs/{id}` every 2s until `status === "done"` or `"error"`, then
presents the WAV download link and BPM/key results.

---

## Data Flow: URL Input to WAV in Browser

```
1. User pastes YouTube URL, clicks "Grab"
   └─► POST /jobs  { url: "https://youtube.com/watch?v=..." }
       └─► Rate limiter checks IP counter in Redis
           - Over limit? → 429 response, no job created
           - Under limit? → increment counter, proceed
       └─► Generate job_id (UUID4)
       └─► Push task to Celery queue via Redis
       └─► Store job_id → { status: "queued" } in Redis (TTL 10min)
       └─► Return { job_id } to browser immediately (~50ms)

2. Browser polls GET /jobs/{job_id} every 2 seconds
   └─► Returns current status from Redis

3. Celery worker picks up task
   └─► Update Redis: status = "processing", progress = "downloading"
   └─► yt-dlp downloads best audio stream into /tmp/soundgrabber/{job_id}/
       - Format: bestaudio (usually opus/webm from YouTube)
       - yt-dlp postprocessor converts to WAV via ffmpeg
       - Output: /tmp/soundgrabber/{job_id}/audio.wav
   └─► Update Redis: progress = "analyzing"
   └─► librosa loads audio.wav
       - tempo, _ = librosa.beat.beat_track(y=y, sr=sr)  → BPM
       - chroma = librosa.feature.chroma_cqt(y=y, sr=sr) → key detection
   └─► Update Redis: status = "done", bpm = X, key = "...", file_path = "..."

4. Browser sees status = "done"
   └─► Displays BPM + key immediately
   └─► User clicks "Download WAV"
       └─► GET /files/{job_id}
           └─► FastAPI reads /tmp/soundgrabber/{job_id}/audio.wav
           └─► Returns StreamingResponse (chunked, 64KB chunks)
               headers: Content-Disposition: attachment; filename="soundgrabber-{job_id}.wav"
           └─► BackgroundTask registered: delete /tmp/soundgrabber/{job_id}/ after stream ends
           └─► WAV arrives in browser's Downloads folder

5. Cleanup
   └─► BackgroundTask runs after response fully sent: shutil.rmtree(job_dir)
   └─► Fallback cron every 15min: find /tmp/soundgrabber/ -mmin +20 -type d → delete
   └─► Redis key expires automatically (10min TTL)
```

---

## File Handling

**Storage location:** `/tmp/soundgrabber/{job_id}/`

Each job gets an isolated directory. This prevents any filename collision between concurrent
jobs and makes cleanup atomic (delete the whole directory).

**WAV size estimate:** A 4-minute YouTube beat at 44.1kHz stereo 16-bit PCM = ~42MB.
A 10-minute track = ~105MB. This is well within what a single server disk can buffer during
the streaming download, provided disk is monitored.

**Serving:** FastAPI `StreamingResponse` with a generator that yields 64KB chunks. This
avoids loading the entire WAV into memory on the API server.

```python
async def wav_generator(path: str):
    async with aiofiles.open(path, "rb") as f:
        while chunk := await f.read(65536):
            yield chunk

return StreamingResponse(
    wav_generator(file_path),
    media_type="audio/wav",
    headers={"Content-Disposition": f'attachment; filename="beat-{job_id}.wav"'},
    background=BackgroundTask(shutil.rmtree, job_dir, ignore_errors=True),
)
```

**Disk safety:** A cron-based sweeper (or APScheduler task at startup) deletes any job
directory older than 20 minutes. This catches jobs where the user never clicked Download.

---

## Rate Limiting Without User Accounts

Since there are no user accounts, the primary identifier is client IP address. Use a Redis
sliding window counter per IP.

**Recommended limits (starting point, tune after observing traffic):**

| Window | Limit | Rationale |
|--------|-------|-----------|
| 1 minute | 3 jobs | Prevents burst abuse |
| 1 hour | 20 jobs | Reasonable producer workflow |

Implementation: `fastapi-limiter` library (backed by Redis) applied as a FastAPI dependency
on `POST /jobs`. It defaults to `ip + path` as the key.

Additional hardening:

- **URL validation on ingress:** Reject anything that isn't a well-formed YouTube watch URL
  before it touches the queue. Prevents queue pollution.
- **Video duration cap:** Use yt-dlp's `--match-filter "duration <= 1800"` (30 minutes max).
  Rejects live streams and lecture videos that would create enormous WAV files.
- **Concurrent job cap:** Redis INCR/DECR counter for total active jobs. If the system-wide
  active job count exceeds capacity (e.g., 20), return 503 with a retry hint rather than
  silently queuing indefinitely.

No CAPTCHA needed at launch. Underground music producers are a small, focused audience.
Add CAPTCHA only if automated abuse is observed.

---

## YouTube Download Layer: The Highest-Risk Component

yt-dlp is the only viable option for this use case (youtube-dl is abandoned). However,
YouTube actively works to block non-browser clients.

**Known issues in 2025-2026:**

- YouTube uses Cloudflare bot fingerprinting. Datacenter IPs are frequently blocked.
- The `--cookies-from-browser` flag works locally but is impractical on a server (no browser
  running on the host).
- Cookies exported from a residential browser session work but expire within hours and must
  be rotated — this is operationally painful.
- yt-dlp releases updates frequently to keep pace with YouTube's countermeasures. Pinning
  the version is dangerous; staying near HEAD is safer but introduces instability risk.

**Architectural decision:** Isolate yt-dlp behind an abstraction in the worker code so the
download strategy can be swapped without touching the rest of the pipeline. Keep yt-dlp
version unpinned (or pinned to a recent release, refreshed weekly via CI).

**Mitigation strategy for bot detection:**
1. Use a VPS on a residential ISP rather than a cloud datacenter where possible.
2. Pass `--user-agent` mimicking a real browser.
3. Keep a `cookies.txt` file refreshed periodically from a real logged-in browser session.
4. Monitor the worker error rate — if yt-dlp starts failing consistently, it is almost always
   a YouTube countermeasure, not a code bug.

---

## Suggested Build Order (Dependency-First)

Build in this sequence to validate the hardest dependency (yt-dlp) earliest and avoid
building UI against a processing layer that doesn't work yet.

```
Phase 1: Processing pipeline (no server, just a script)
   ├── yt-dlp downloads audio to /tmp
   ├── ffmpeg converts to WAV (via yt-dlp postprocessor)
   └── librosa detects BPM + key
   Validate: end-to-end pipeline works for 10 representative YouTube URLs

Phase 2: API layer
   ├── FastAPI POST /jobs → Celery task → Redis job state
   ├── GET /jobs/{id} → status polling endpoint
   └── GET /files/{id} → StreamingResponse + cleanup
   Validate: curl workflow works without a browser

Phase 3: Rate limiting + hardening
   ├── fastapi-limiter on POST /jobs
   ├── URL validation + duration cap in worker
   └── Disk sweeper (APScheduler or cron)
   Validate: abuse scenarios don't crash the server

Phase 4: Frontend
   ├── URL input form → POST /jobs
   ├── Polling loop → status display
   ├── BPM + key display on completion
   └── Download button (links to /files/{id})
   Validate: full user flow in browser

Phase 5: Visual identity
   └── Y2K / phpBB / Tibia aesthetic applied to the working frontend
```

Build Phase 1 as a standalone Python script with no web framework. If yt-dlp cannot reliably
download from your hosting environment, no amount of frontend polish matters.

---

## Scalability Envelope

This architecture handles the stated "hundreds of concurrent users" target on modest
infrastructure (a single VPS with 4 cores and 8GB RAM). Beyond that:

| Concern | At current scale | At 10x scale |
|---------|-----------------|--------------|
| API throughput | 2-4 Uvicorn workers, handles ~200 concurrent polling connections easily | Add Uvicorn workers; put Nginx in front |
| Job processing | 2-4 Celery workers (CPU + disk I/O bound) | Add more Celery workers; separate worker hosts |
| Disk | ~2GB peak if 20 concurrent 5-min downloads in flight | Mount larger /tmp or use /var partition |
| Redis | Single instance easily handles counters + job state at this scale | Redis Sentinel only if Redis becomes a concern |
| YouTube blocking | Single IP, manageable | Multiple IPs or proxy rotation needed |

---

## Anti-Patterns to Avoid

### Running yt-dlp inside the FastAPI process
**What goes wrong:** yt-dlp + ffmpeg are blocking and CPU/IO heavy. Running them in an async
FastAPI route — even in a ThreadPoolExecutor — starves the event loop under load.
**Instead:** Always run in a Celery worker (separate process).

### Storing WAV files indefinitely
**What goes wrong:** Disk fills up. No account system means no user-triggered cleanup.
**Instead:** TTL on Redis keys + post-download BackgroundTask deletion + periodic sweeper.

### Serving WAV via FileResponse without streaming
**What goes wrong:** For a 50MB WAV, FastAPI loads the whole file into memory before sending.
Under concurrent downloads this spikes RAM.
**Instead:** Use StreamingResponse with an async file generator.

### Pinning yt-dlp to a specific version
**What goes wrong:** YouTube patches their bot detection; old yt-dlp versions stop working
within weeks, sometimes days.
**Instead:** Keep yt-dlp at latest or near-latest; automate weekly dependency refresh in CI.

### Using `asyncio.create_task` for librosa analysis
**What goes wrong:** librosa is CPU-bound (NumPy/SciPy under the hood). Running it in the
async event loop blocks all other coroutines even with `await`.
**Instead:** Celery worker process; if not using Celery, `loop.run_in_executor` with
`ProcessPoolExecutor`.

---

## Sources

- [FastAPI BackgroundTasks documentation](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [FastAPI StreamingResponse discussion — large files](https://github.com/fastapi/fastapi/discussions/8229)
- [Celery + Redis + FastAPI production guide 2025](https://medium.com/@dewasheesh.rana/celery-redis-fastapi-the-ultimate-2025-production-guide-broker-vs-backend-explained-5b84ef508fa7)
- [Async tasks with FastAPI and Celery — TestDriven.io](https://testdriven.io/blog/fastapi-and-celery/)
- [SSE vs WebSockets vs Long Polling 2025 — DEV Community](https://dev.to/haraf/server-sent-events-sse-vs-websockets-vs-long-polling-whats-best-in-2025-5ep8)
- [FastAPI IP-based rate limiting with Redis](https://medium.com/@2nick2patel2/fastapi-rate-limiting-with-redis-fair-use-apis-without-user-rage-dbf8ed370c72)
- [fastapi-limiter library](https://github.com/long2ice/fastapi-limiter)
- [Handling CPU-bound tasks in FastAPI](https://medium.com/@rameshkannanyt0078/handling-cpu-bound-tasks-in-fastapi-without-killing-performance-32cd70c61d5a)
- [yt-dlp bot detection issue tracker](https://github.com/yt-dlp/yt-dlp/issues/13067)
- [6 ways to get YouTube cookies for yt-dlp in 2026](https://dev.to/osovsky/6-ways-to-get-youtube-cookies-for-yt-dlp-in-2026-only-1-works-2cnb)
- [Audet — librosa + Essentia BPM/key tool](https://github.com/makalin/Audet)
- [FFmpeg with yt-dlp — Rendi guide](https://www.rendi.dev/post/using-ffmpeg-with-yt-dlp)
