# Domain Pitfalls — SoundGrabber

**Domain:** YouTube audio downloader + BPM/key detection web app
**Researched:** 2026-04-29
**Confidence:** HIGH for YouTube blocking, MEDIUM for audio analysis accuracy, HIGH for file handling/deployment

---

## Critical Pitfalls

Mistakes that cause rewrites, production outages, or permanent degradation.

---

### Pitfall 1: Datacenter IP Flagging by YouTube

**What goes wrong:**
YouTube aggressively flags datacenter IP ranges (AWS, GCP, DigitalOcean, Hetzner, etc.) as bot traffic. Requests from these IPs receive HTTP 403 or silent failures — the download call appears to succeed but returns an error page or corrupted data. This is not a soft block; datacenter IPs get permanently deprioritized. Residential proxies achieve 85–95% success rate on YouTube while datacenter proxies achieve only 20–40%.

**Why it happens:**
YouTube cross-references the originating IP against known datacenter CIDR ranges. Any server hosting a web app is, by definition, a datacenter IP. The app's server is the worst possible machine from which to call YouTube.

**Consequences:**
Downloads stop working entirely on production within days or weeks of launch. Locally everything works because the developer's residential IP is fine. This is the most common "works on my machine" failure for this class of app.

**Warning signs:**
- Downloads fail in production but succeed locally
- HTTP 403 or `Sign in to confirm you're not a bot` errors
- yt-dlp returns exit code 1 with `HTTP Error 403: Forbidden`
- Error rate climbs over the first 2–4 weeks without code changes

**Prevention strategy:**
1. Use yt-dlp's `--cookies` flag with a valid YouTube session cookie obtained from a real browser. Cookies from a logged-in account attached to a real identity substantially reduce bot-detection signals.
2. Implement PO Token (Proof of Origin Token) support via a `yt-dlp-youtube-po-token-provider` plugin — YouTube's 2025/2026 anti-bot system requires this token per video.
3. Keep yt-dlp pinned to the latest version in `requirements.txt` and set up a weekly auto-update check — YouTube frequently changes its extraction protocol and yt-dlp patches typically follow within days.
4. Design the download pipeline to be swappable: abstract the download function behind an interface so the underlying tool (yt-dlp flags, proxy configuration, fallback strategies) can be changed without touching the rest of the codebase.
5. Do NOT set `--fragment-retries` to a high value (default 10 is dangerous) — excessive retries on 429 responses accelerate IP bans. Set `--fragment-retries 3` with exponential backoff logic at the app level.

**Which build phase:** Phase 1 (core download pipeline). The abstraction layer for swappability is a design decision that cannot be retrofitted cheaply.

---

### Pitfall 2: yt-dlp Version Drift Causing Silent Failures

**What goes wrong:**
YouTube regularly deploys protocol changes that break yt-dlp's extraction logic. If yt-dlp is pinned to an old version, downloads silently fail or return corrupted files. The failure mode is often not an exception but a downloaded file that is actually an HTML error page.

**Why it happens:**
The YouTube extraction module in yt-dlp is among the most actively maintained extractors precisely because YouTube fights back continuously. A version that worked last month may be broken today.

**Consequences:**
Users see 100% failure rate with no useful error message unless the app explicitly validates that the downloaded file is valid audio before returning it.

**Warning signs:**
- Downloaded "audio" files are 10–50KB (HTML error pages)
- ffmpeg reports `Invalid data found when processing input`
- yt-dlp error log contains `youtube: This video is not available` when the video clearly exists

**Prevention strategy:**
1. After every yt-dlp download, verify the output file with ffprobe (`ffprobe -v error -show_entries format=duration`). If the probe fails, treat the download as failed and return an error to the user.
2. Run yt-dlp in verbose mode (`-v`) in staging and capture stderr to a log — YouTube's bot detection messages appear in stderr, not stdout.
3. Pin yt-dlp to a minor version range (`yt-dlp>=2025.01,<2026.01`) and automate weekly dependency updates with a CI check.
4. Monitor the yt-dlp GitHub issues page for YouTube-specific breakages as a health signal for the app.

**Which build phase:** Phase 1 (core pipeline). File validation with ffprobe is non-negotiable from the first working version.

---

### Pitfall 3: Half-Tempo / Double-Tempo BPM Detection Error

**What goes wrong:**
Librosa's `beat_track` and `tempo` functions return the wrong BPM for a significant fraction of beats that underground producers actually use. The most common failure is returning exactly half the correct BPM (e.g., 70 BPM instead of 140 BPM for trap) or exactly double (e.g., 170 BPM instead of 85 BPM for boom bap). This is not a random error — it is a systematic failure of the onset-detection algorithm on half-time rhythmic patterns.

**Why it happens:**
Trap music at 140 BPM is typically programmed with a half-time drum pattern where the snare lands on beat 3 rather than beats 2 and 4. The rhythmic energy of the kick and snare pattern presents to the algorithm as 70 BPM. The algorithm is technically correct (70 BPM is a valid rhythmic division) but wrong by the producer's mental model of the track's tempo.

Lo-fi and boom bap have swung, quantized, or deliberately loose timing that confuses onset strength estimation. Tracks with no clear percussive transients (ambient pads, long sustained notes) may return 0 BPM or wildly incorrect values.

**Consequences:**
Producers see wrong BPM data and distrust the entire tool. BPM is one of the two core value propositions — getting it wrong consistently destroys credibility.

**Warning signs:**
- Test a set of 20 known-BPM trap beats; more than 30% return half the expected value
- Librosa returns 0.0 for ambient or pad-heavy tracks
- Results vary dramatically (±20 BPM) depending on which 60-second segment of the track is analyzed

**Prevention strategy:**
1. Always present BPM alongside a "also try: [half tempo]" or "also try: [double tempo]" value displayed as a secondary result. This turns a wrong answer into a useful answer. Example display: `140 BPM (or 70 BPM half-time)`.
2. Use librosa's `tempo` function (which returns a float) rather than `beat_track` (which tracks individual beats) for the primary BPM estimate — it is more stable for tempo-only detection.
3. Analyze the full track, not just the first 30 seconds. The intro of a trap beat is often atypical (no drums). Analyze a window starting at 20% of track duration.
4. Run analysis at multiple `start_bpm` hints (60, 90, 120, 170) and select the result with the highest onset strength correlation — this significantly reduces half-tempo errors on trap.
5. For key detection, use librosa's `chroma_cqt` with a `krumhansl` key profile. For BPM, consider using `essentia` as a supplementary check if librosa returns 0 or a suspiciously low value.
6. Always surface a confidence indicator to the user (e.g., "BPM: 140 — high confidence" vs "BPM: 72 — low confidence, verify manually").

**Which build phase:** Phase 2 (audio analysis). The multiple-hint strategy and half/double display are architecture decisions that need to be built in from the start of the analysis module.

---

### Pitfall 4: Temp File Accumulation and Disk Exhaustion

**What goes wrong:**
Every download creates at minimum three files on disk: the raw YouTube audio container (WebM/M4A), the intermediate decoded PCM, and the final WAV. If any step fails — or if the cleanup logic runs after the HTTP response is already sent — these files are never deleted. On a small VPS (20–50GB disk), 500 failed or abandoned downloads can consume the entire disk, causing the next write to fail silently and the server to crash or return 500 errors.

**Why it happens:**
- Python's `after_this_request` in Flask raises `PermissionError` because the file is still open when the framework tries to delete it during streaming
- Exceptions in the download pipeline that are caught at the top level skip the finally/cleanup block
- Users who close the browser mid-download leave orphaned files because the server cannot detect the client disconnect in time
- `tempfile.NamedTemporaryFile` with `delete=True` deletes on close, but if the file handle leaks, the file persists

**Consequences:**
Server disk fills up. All writes fail. Database (if any), logging, and the OS itself break. The app serves 500 errors until someone manually clears `/tmp`.

**Warning signs:**
- `df -h` on the server shows `/tmp` or the app working directory at 80%+ utilization
- `ls -la /tmp | wc -l` grows over time without shrinking
- Server alerts for disk I/O errors
- Users report 500 errors during peak usage

**Prevention strategy:**
1. Use `tempfile.mkdtemp()` to create a unique working directory per request. Wrap all processing in a `try/finally` block that calls `shutil.rmtree(tmpdir)` — the `finally` block runs even if an exception is raised.
2. Set a separate background cleanup job (e.g., a simple cron or APScheduler task) that deletes any file in the working directory older than 30 minutes. This is the safety net for the cases where `finally` does not run (process kill, OOM, etc.).
3. Limit concurrent downloads to a maximum of 5 at a time (use a semaphore or a task queue with a fixed worker count) to bound total in-flight disk usage at any moment.
4. Calculate WAV file size before download: `WAV size (MB) = duration_seconds × 0.176` for 44.1kHz 16-bit stereo. At 10 minutes, that is ~106 MB per download. Reject videos longer than a configurable limit (suggest 15 minutes) to cap per-request disk usage at ~160 MB.
5. Stream the WAV file to the client using HTTP chunked transfer rather than writing it to disk and then serving it — this eliminates the final output file entirely.

**Which build phase:** Phase 1 (core pipeline). The try/finally pattern and temp directory approach must be established before the first working endpoint.

---

## Moderate Pitfalls

---

### Pitfall 5: Concurrent Download Memory Spikes

**What goes wrong:**
Librosa loads the entire audio file into a NumPy array in memory before any analysis begins. A 10-minute WAV at 44.1kHz stereo is ~106 MB on disk, but NumPy stores it as float32 arrays that can consume 200–400 MB of RAM. With 5 concurrent users running analysis simultaneously, the Python process needs 1–2 GB of RAM just for audio data — not counting the web framework, yt-dlp subprocess, or ffmpeg.

**Why it happens:**
NumPy's `ndarray` is a fixed-length contiguous memory block. Librosa has no streaming analysis path for beat/key detection — the entire file must be loaded before the algorithm starts. This is a documented architectural limitation.

**Consequences:**
On a 2GB VPS (common for small projects), OOM killer terminates the gunicorn worker or the Python process mid-request. Users see connection resets, not useful error messages.

**Warning signs:**
- `free -m` shows available RAM below 200 MB under load
- `dmesg | grep oom` shows OOM killer events
- Gunicorn workers restart unexpectedly under concurrent load
- Analysis works fine for a single request but fails under 3+ simultaneous requests

**Prevention strategy:**
1. Cap concurrent analysis jobs at 3 using a `threading.Semaphore(3)` or a bounded task queue. Return an HTTP 503 with a "Processing at capacity, try again in a moment" message rather than queuing indefinitely.
2. Downsample to mono at 22050 Hz before analysis (librosa's default). This reduces memory footprint by ~4x. Producers do not need stereo or high sample rate for BPM/key detection — they need it for the WAV download, not the analysis.
3. Analyze a 90-second segment of the track rather than the full file for analysis purposes. Select the segment starting at 20% of the track duration (skips intros). This caps analysis memory at ~60 MB per request regardless of track length.
4. Set `gunicorn --workers 2 --threads 4` rather than multiple workers, to share the memory space and avoid duplicating the librosa/NumPy import overhead across worker processes.

**Which build phase:** Phase 2 (audio analysis) with infrastructure decisions in Phase 3 (deployment).

---

### Pitfall 6: WAV File Size Mismatch vs. User Expectations

**What goes wrong:**
Users conditioned by MP3 downloaders expect audio files to be 5–15 MB. A 10-minute beat in WAV at 44.1kHz 16-bit stereo is ~106 MB. YouTube's source audio is Opus at ~160kbps (48kHz), and when decoded to WAV, the file is 30–40x larger than the compressed source. Users on mobile connections or with data caps will abandon the download or think the app is broken when they see a 100MB file.

**Why it happens:**
WAV is uncompressed PCM. There is no way around the physics: `size_MB = duration_minutes × 10.6`. The project spec mandates WAV for quality, which is correct for professional use, but the size implication is rarely communicated to the user.

**Consequences:**
User abandonment mid-download, bandwidth costs on the server (outbound transfer fees), and mobile users being unable to use the app.

**Warning signs:**
- User feedback saying "the download is too slow" or "the file seems stuck"
- Server outbound bandwidth bills higher than expected
- Browser download progress bars showing 10+ minutes for a single file on a residential connection

**Prevention strategy:**
1. Display the estimated file size before the user clicks download: "Estimated size: ~106 MB (10:02 duration × WAV lossless)". Calculate from the video metadata duration before any download begins.
2. Show the download progress as a percentage with transfer speed, not just a spinner. Users on slow connections need feedback that the download is happening.
3. Set an explicit video duration limit (suggest 15 minutes, ~160 MB max WAV) and display it clearly on the UI: "Supports videos up to 15 minutes". Reject longer videos with a clear explanation.
4. Consider offering WAV as the primary format (per spec) but with an informational tooltip explaining why WAV is large and why it's the right format for production use. This educates the user rather than surprising them.

**Which build phase:** Phase 1 (UI/UX design). File size communication must be part of the initial UI, not added after user complaints.

---

### Pitfall 7: Key Detection Failure on Atonal and Complex Material

**What goes wrong:**
Chroma-based key detection (librosa's default approach) fails on material that is not tonally clear: drums-only passages, heavily distorted bass, highly compressed dynamic range, or tracks with no harmonic content. The algorithm will return a key, but it will be meaningless. Additionally, enharmonic equivalents (F# minor vs. Gb minor) may be returned inconsistently depending on the frame analyzed.

**Why it happens:**
Chroma features are extracted from the constant-Q transform, which smears spectral energy across pitch classes. If the signal has no harmonic content (pure noise, drums), all chroma bins receive roughly equal energy and the key profile correlation becomes meaningless.

**Warning signs:**
- The same track analyzed twice returns different keys
- Confidence scores (if implemented) near 0.5 for all keys
- Tracks with heavily compressed or distorted bass return keys that don't match what the producer knows

**Prevention strategy:**
1. Implement a chroma confidence score: compute the ratio of the maximum chroma correlation to the mean. If the ratio is below a threshold (empirically ~1.5–2.0), display "Key: Uncertain — verify manually" rather than a confident wrong answer.
2. High-pass filter the audio at 300 Hz before chroma extraction to remove bass frequencies that distort the harmonic estimation (sub-bass and bass lines can overwhelm chroma in trap/hip-hop).
3. Display both the most likely key and the second most likely key when confidence is low.
4. Use Camelot wheel notation alongside standard notation (e.g., "F# minor / 11A") — this is what underground producers actually use for mixing.

**Which build phase:** Phase 2 (audio analysis).

---

## Minor Pitfalls

---

### Pitfall 8: ffmpeg Not Found in Production Environment

**What goes wrong:**
yt-dlp requires ffmpeg to merge audio/video streams and to re-encode audio. Librosa requires ffmpeg (via audioread) as a fallback for reading certain audio formats. If ffmpeg is not installed as a system package, both tools fail with unhelpful errors like `NoBackendError` or `postprocessor ffmpeg not found`.

**Prevention strategy:**
1. In the Dockerfile (or server setup script), explicitly install ffmpeg as a system package: `apt-get install -y ffmpeg`. Do not rely on Python packages to install ffmpeg.
2. Add a startup health check that runs `ffmpeg -version` and fails fast with a clear error if it is missing.
3. Pin ffmpeg to a specific version or document the minimum version required.

**Which build phase:** Phase 3 (deployment/infrastructure).

---

### Pitfall 9: libsndfile Missing Breaks soundfile/librosa on Linux

**What goes wrong:**
librosa uses `soundfile` as its primary audio backend, which requires `libsndfile` — a C library that must be installed at the OS level. On minimal Linux containers (Alpine, slim Debian images), `libsndfile` is not present. pip installing librosa succeeds, but the first `librosa.load()` call raises `OSError: cannot load library 'libsndfile'`.

**Prevention strategy:**
1. In the Dockerfile: `apt-get install -y libsndfile1 ffmpeg` before `pip install librosa`.
2. Use `python:3.11-slim-bookworm` as the base Docker image rather than Alpine — Alpine uses musl libc which causes additional binary compatibility issues with audio libraries.
3. Run a test audio load during the Docker build step to catch missing system dependencies before the image is pushed.

**Which build phase:** Phase 3 (deployment/infrastructure).

---

### Pitfall 10: Synchronous Download Blocking the Web Server

**What goes wrong:**
If the download and analysis pipeline runs synchronously in the request handler, a single download (which takes 30–120 seconds) blocks an entire gunicorn worker thread for its entire duration. With 2 workers and 3 concurrent users, the third user's request waits until one of the first two finishes.

**Prevention strategy:**
1. Run the download + analysis pipeline in a background thread or process immediately, return a job ID to the client, and have the client poll for status. This is simpler than Celery for this scale.
2. For the target scale (hundreds of users, not thousands), `concurrent.futures.ThreadPoolExecutor` with 5 workers is sufficient. Full Celery + Redis is over-engineering for v1.
3. Use Server-Sent Events (SSE) or WebSocket to push progress updates to the client rather than polling. This gives the 2000s aesthetic a "live" feel that fits the retro UI identity.

**Which build phase:** Phase 1 (core architecture). The synchronous vs. async decision must be made before the first endpoint is built — retrofitting async is expensive.

---

### Pitfall 11: Legal/ToS Risk Assessment

**What goes wrong (mischaracterization of the risk):**
Developers either dismiss ToS risk entirely ("everyone does it") or over-index on it and never ship. The actual risk profile for SoundGrabber is nuanced.

**Actual risk breakdown:**

| Risk | Likelihood | Severity | Notes |
|------|-----------|----------|-------|
| YouTube ToS violation | Certain | Low for v1 | YouTube's ToS prohibits automated downloads. Enforcement against small apps is rare but not zero. Primary mechanism is service disruption (blocking), not legal action. |
| DMCA takedown of the app | Low | High | A 2026 US court ruling found that bypassing YouTube's technical measures may violate DMCA §1201. This is a legal gray area. Risk rises with scale and visibility. |
| Copyright infringement of content | Very low for reference/production use | High if monetized | Users downloading beats for production/reference is analogous to private use. The app itself does not host or redistribute content — it facilitates a download from YouTube's own servers. |
| YouTube blocking the server IP | High | Medium | This is a technical enforcement, not legal. Expected to happen. Mitigation is the technical strategy in Pitfall 1. |

**Prevention strategy:**
1. Add a clear terms of use on the app stating: "For personal and production reference use only. Do not redistribute downloaded content." This shifts responsibility to the user and demonstrates good faith.
2. Do not cache, store, or re-serve YouTube audio on the server. Process and immediately stream or delete. Storing a copy is the clearest path to infringement liability.
3. At scale (if the app grows significantly), consult a lawyer about DMCA §1201 exposure. For v1 at underground community scale, the practical risk is YouTube blocking the server IP, not a lawsuit.
4. Monitor the yt-dlp GitHub for any legal developments that affect the tool's status.

**Which build phase:** Phase 1 (architecture). The "no server-side storage" principle must be a design constraint from day one.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Core download pipeline | Datacenter IP immediately blocked in production | Cookie authentication + PO token from phase 1; design abstraction layer |
| File management | Orphaned temp files if cleanup runs after response | `try/finally` with `shutil.rmtree` from the first working handler |
| BPM/key analysis | Half-tempo error on trap, zero-BPM on ambient tracks | Multiple `start_bpm` hints + half/double display from phase 2 start |
| Concurrent users | Memory spike from multiple simultaneous librosa loads | Semaphore + mono/22050Hz downsampling for analysis before phase 2 ships |
| User expectations | WAV size surprises users expecting MP3-sized files | Show estimated size before download from first UI version |
| Deployment | ffmpeg and libsndfile missing in container | Dockerfile health check; use `python:3.11-slim-bookworm` not Alpine |
| Legal | Server-side audio caching creates infringement risk | Never persist audio beyond the request lifecycle |
| Scaling past v1 | yt-dlp fragility requires operational attention ongoing | Weekly yt-dlp update check + monitoring on download failure rate |

---

## Sources

- [yt-dlp YouTube bot detection issue #13067](https://github.com/yt-dlp/yt-dlp/issues/13067)
- [yt-dlp fragment-retries IP ban issue #15899](https://github.com/yt-dlp/yt-dlp/issues/15899)
- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [yt-dlp FAQ — rate limiting and workarounds](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)
- [Bypassing the 2026 YouTube Great Wall — DEV Community](https://dev.to/ali_ibrahim/bypassing-the-2026-youtube-great-wall-a-guide-to-yt-dlp-v2rayng-and-sabr-blocks-1dk8)
- [YouTube Proxy — Prevent Server IP Blocks](https://proxy001.com/blog/youtube-proxy-prevent-server-ip-blocks-after-deploying-yt-dlp-style-server-workloads)
- [How to Tackle yt-dlp Challenges in AI-Scale Scraping](https://medium.com/@DataBeacon/how-to-tackle-yt-dlp-challenges-in-ai-scale-scraping-8b78242fedf0)
- [librosa memory usage growing with iterations — issue #1286](https://github.com/librosa/librosa/issues/1286)
- [librosa streaming for large files — official blog](https://librosa.org/blog/2019/07/29/stream-processing/)
- [Automatic BPM and Key Detection — StemSplit 2025](https://stemsplit.io/blog/bpm-key-detection-feature)
- [DMCA ruling on third-party YouTube downloads — MediaNama 2026](https://www.medianama.com/2026/02/223-dmca-ruling-third-party-youtube-downloads-legal-risks-creators/)
- [GitHub reinstates youtube-dl — EFF](https://www.eff.org/deeplinks/2020/11/github-reinstates-youtube-dl-after-riaas-abuse-dmca)
- [6 Ways to Get YouTube Cookies for yt-dlp in 2026](https://dev.to/osovsky/6-ways-to-get-youtube-cookies-for-yt-dlp-in-2026-only-1-works-2cnb)
- [librosa beat.beat_track documentation](https://librosa.org/doc/main/generated/librosa.beat.beat_track.html)
- [Trap BPM guide — Producer Fury](https://producerfury.com/resources/trap-bpm-guide)
- [FastAPI file upload clean patterns](https://medium.com/@ThinkingLoop/fastapi-file-uploads-clean-fast-and-foolproof-4ecf0f00404f)
- [librosa installation and dependencies — DeepWiki](https://deepwiki.com/librosa/librosa/1.1-installation-and-dependencies)
