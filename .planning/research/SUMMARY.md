# Project Research Summary

**Project:** SoundGrabber
**Domain:** YouTube audio downloader + music analysis web utility for underground producers
**Researched:** 2026-05-14 (v1.3 Raspberry Pi Hosting — supersedes 2026-04-29 for infrastructure sections)
**Confidence:** MEDIUM-HIGH (Pi hardware patterns HIGH; ARM package ecosystem MEDIUM; bgutil ARM behavior LOW)

---

## Executive Summary

SoundGrabber v1.3 migrates from Railway (datacenter x86_64) to a Raspberry Pi 3B (ARM Cortex-A53, 1GB RAM, residential IP). This is not a "run the same containers somewhere else" migration — it requires deliberate decisions on ARM architecture, Docker Compose structure, package compatibility, memory management, and unattended recovery. The single most important strategic insight from the research: the residential IP is the primary YouTube bot-detection defense. The IP change alone is likely to resolve the download reliability problems that required the v1.2 client-chain fix, without needing bgutil at all. Validate this first before adding any PO Token infrastructure to the Pi stack.

The most consequential pre-work decision is OS bitness. The Raspberry Pi 3B's CPU is 64-bit capable but defaults to a 32-bit OS. Essentia has no Linux ARM32 wheel and no Linux ARM64 wheel on PyPI — it must be dropped entirely for the Pi deployment. The stack replaces essentia with librosa-only BPM and key detection. If the Pi OS is 64-bit (aarch64), numpy/scipy/librosa pip wheels resolve cleanly from PyPI manylinux; if 32-bit, the team faces numba/llvmlite C++ build failures inside Docker. The research recommendation is unambiguous: run Raspberry Pi OS 64-bit (bookworm). Verify with `uname -m` before any other action.

The architecture adds four net-new components that do not exist in the current codebase: a `Dockerfile`, a `docker-compose.yml`, a `deploy.sh` script, and a Cloudflare Tunnel configuration. The core application code (`pipeline.py`, `api/main.py`, `api/config.py`) requires no changes — it reads configuration via environment variables and the v1.2 ffprobe resolution logic (`shutil.which`) already handles system-installed FFmpeg correctly. The critical integration risk is the shared `/tmp` volume between the `api` and `worker` containers: in Railway, both run in the same container; in Docker Compose, they are separate with isolated filesystems, and without a shared tmpfs volume, `GET /files/{id}` always returns 404. This pattern is untested in this codebase and must be validated E2E before the milestone is considered complete.

---

## Key Findings

### Stack Changes: Railway to Raspberry Pi 3B

The existing application stack (FastAPI, Celery, Redis, yt-dlp, librosa) is ARM-compatible at the Python layer. The changes are entirely in the infrastructure layer.

**Removed from Pi stack:**
- `essentia==2.1b6.dev1389` — no Linux ARM wheel (any architecture) on PyPI or piwheels; drop entirely, use librosa for both BPM and key detection
- `imageio-ffmpeg>=0.5.1` — ships an x86-only bundled ffmpeg binary; system `apt install ffmpeg libsndfile1` replaces it
- `nixpacks.toml` / `railway.toml` — Railway-specific; unused by Docker Compose
- `start.sh` — replaced by Docker Compose in production; keep for local dev only

**Added for Pi stack:**
- `Dockerfile` — new file; `FROM python:3.11-slim-bookworm`, `apt-get install ffmpeg libsndfile1 nodejs`, `ENV NUMBA_DISABLE_JIT=1`
- `docker-compose.yml` — new file; 3-4 services: redis, api, worker, cloudflared (optional)
- `requirements-pi.txt` — essentia + imageio-ffmpeg removed; everything else unchanged
- `deploy.sh` — SSH-callable update script; `git pull + docker compose up -d --no-deps worker api`
- Cloudflare Tunnel (`cloudflared`) — public HTTPS access behind residential NAT without port forwarding

**Docker image decisions:**
- Python container: `python:3.11-slim-bookworm` (multi-arch manifest; pulls linux/arm64 automatically on 64-bit Pi OS)
- Redis container: `redis:7-alpine` (multi-arch; specify `platform: linux/arm64` explicitly in compose)
- FFmpeg: `apt-get install ffmpeg libsndfile1` — installs both `ffmpeg` AND `ffprobe` on Debian bookworm

**yt-dlp client chain from v1.2 carries forward unchanged:** `tv,ios,web_embedded`. On a residential IP, the `tv` client without PO Token is expected to work for most public videos. Test without bgutil first; the bgutil sidecar should only be added if canary downloads fail with bot-detection errors.

**Mandatory memory-critical settings (not optional):**
- Celery: `--concurrency=1 --max-tasks-per-child=10`
- Uvicorn: `--workers 1 --limit-concurrency 20`
- Swap: 512MB on Pi host (`dphys-swapfile`, CONF_SWAPSIZE=512)
- GPU memory: `gpu_mem=16` in `/boot/firmware/config.txt`
- Docker memory cgroups: `cgroup_enable=memory cgroup_memory=1` in `/boot/firmware/cmdline.txt` (without this, `mem_limit` in compose is silently ignored)

**Memory budget at peak (Pi 3B, 1GB total):**

| Service | Typical | Peak |
|---------|---------|------|
| OS + Docker daemon | 150-200MB | 200MB |
| redis (160m limit) | 30MB | 80MB |
| api (256m limit) | 120MB | 200MB |
| worker (512m limit) | 150MB idle | 400MB during librosa |
| cloudflared (64m limit) | 40MB | 64MB |
| **Total** | ~490MB | **~944MB** |

Peak of ~944MB fits within 1GB with ~80MB headroom. Swap absorbs spikes. Without swap, OOM kill on every librosa analysis.

### Public Exposure: Cloudflare Tunnel

The Pi is behind residential NAT without port forwarding. Three options evaluated:

| Option | Custom Domain | ARM Support | Cost | Recommended |
|--------|--------------|-------------|------|-------------|
| Cloudflare Tunnel | Yes (CF DNS) | Yes (official apt) | Free | YES |
| Tailscale Funnel | No (`.ts.net` only) | Yes (installed) | Free | Dev/backup only |
| frp (self-hosted VPS) | Yes | Yes | ~$5/mo | Reject |

Cloudflare Tunnel wins on every axis: custom domain (mandatory for user trust), no published bandwidth limit, official ARM32/arm64 packages, and WAV file downloads through Tunnel do not violate ToS (Tunnel is a connectivity product, not the CDN). Tailscale Funnel's custom-domain limitation is a confirmed open GitHub issue since 2025 and is not a workaround.

Tailscale stays as the out-of-band SSH access mechanism — it is already installed on the Pi host, requires no compose configuration, and provides remote management even if the public tunnel breaks.

### Architecture: Docker Compose Structure

**Service topology:**
```
redis (redis:7-alpine)
  api (soundgrabber:latest)  -- port 127.0.0.1:8000:8000 (localhost only when cloudflared active)
  worker (soundgrabber:latest)  -- Celery, concurrency=1
  cloudflared (cloudflare/cloudflared:latest)  -- optional, routes public traffic to api:8000
```

**Critical integration: shared /tmp volume.** The `api` serves WAV files that `worker` writes. Without a shared volume these are isolated containers and file serving always fails. Solution: define `sg_tmp` as a named tmpfs volume in docker-compose.yml, mounted as `/tmp` in both `api` and `worker`. tmpfs keeps audio writes in RAM (protects SD card, fast I/O). 512MB limit handles ~3 concurrent 15-min WAVs.

**Volume inventory:**

| Volume | Container path | Contents | Persistence |
|--------|---------------|----------|-------------|
| `sg_cookies` | `/data/yt-dlp-cache` | `cookies.txt` | Permanent — operator manages |
| `sg_featured` | `/data/featured` | `featured-current.json` | Permanent — Yonkou panel |
| `sg_tmp` | `/tmp` | `sg_*.wav` temp files | Ephemeral — tmpfs, lost on restart |
| `redis_data` | `/data` | Empty — Redis runs without persistence | Discardable |

**Tailscale integration:** Tailscale is already installed on the Pi host as a systemd service. Do NOT add a Tailscale sidecar container — it requires `/dev/net/tun`, `NET_ADMIN` cap, and network_mode changes for zero benefit. The host's `tailscale0` interface routes `100.x.x.x:8000` through Docker's `0.0.0.0:8000` port mapping to the api container automatically.

**Deploy flow:** `ssh pi@100.x.x.x 'bash ~/soundgrabber/deploy.sh'`. The deploy script restarts `worker` before `api`, never restarts `redis` (would lose in-flight Celery jobs). Redis is shut down last and started first.

**Components that are NEW (do not exist in codebase):**
- `Dockerfile`
- `docker-compose.yml`
- `.env` (on Pi, not in git)
- `deploy.sh`

**Components unchanged (no code changes needed):**
- `pipeline.py` — `YTDLP_CACHE_DIR` already reads from env; `shutil.which` ffprobe resolution already works with system FFmpeg
- `api/main.py` — `DEV_MODE=false` activates production validations
- `api/config.py` — 100% env-var driven

### Feature Scope: Milestone Acceptance Criteria

v1.3 is an infrastructure milestone. Product features are unchanged. The milestone is complete when exactly these conditions hold:

**Must have (hard gate):**
1. `cloudflared` running as systemd service or compose service on Pi
2. Custom domain resolving via Cloudflare DNS to the Pi's tunnel
3. Cloudflare Tunnel config pointing to `http://api:8000` (Docker internal network)
4. All compose services with `restart: unless-stopped`
5. Deploy script callable via SSH over Tailscale
6. **3 successful end-to-end YouTube downloads via the public custom domain URL**

**Explicitly out of scope:**
- GitHub Actions CI/CD
- Log aggregation / remote observability
- Any new product features
- bgutil sidecar (validate without it first; add only if residential IP is insufficient)

### Critical Pitfalls

**P-CRITICAL-1: 32/64-bit OS mismatch (architecture-level)**
If Pi is running 32-bit OS (armv7l) and images use `linux/arm64` (or vice versa), containers fail with `exec format error` on startup. Run `uname -m` on the Pi before any other work. If the output is `armv7l` and you want 64-bit (recommended), reflash with Raspberry Pi OS 64-bit. This cannot be fixed after the fact without reflashing.

**P-CRITICAL-2: librosa/numba ARM build failure**
numba has no pip-installable ARM wheels. On ARM Docker, `pip install librosa` may trigger C++ compilation of llvmlite that either fails outright or produces an import-crashing binary. Prevention: set `ENV NUMBA_DISABLE_JIT=1` in Dockerfile and do not install numba. Verify before writing compose: `docker run --rm soundgrabber:latest python -c "import librosa; print(librosa.__version__)"`. librosa works without numba — pure-Python fallback is 10-100x slower but functional and acceptable with concurrency=1.

**P-CRITICAL-3: OOM kill during librosa analysis**
A single 5-minute WAV analysis can spike to 400-600MB RAM. On 1GB total with the full stack running, the Linux OOM killer silently terminates the Celery worker — no Python exception, job frozen in `processing` state forever. Prevention requires ALL THREE simultaneously: swap enabled (512MB minimum), `--concurrency=1`, and `librosa.load(..., duration=90)` to cap analysis audio. Any one of these missing causes OOM on every non-trivial job.

**P-CRITICAL-4: Docker memory limits silently ignored**
On fresh Raspberry Pi OS, `mem_limit` in docker-compose.yml is silently ignored. Docker reports "No memory limit support". Memory cgroups must be enabled in kernel boot parameters: add `cgroup_enable=memory cgroup_memory=1` to `/boot/firmware/cmdline.txt`, then reboot. Verify with `docker info | grep -i memory` — must show no warnings. Without this, container OOM kills affect the entire Pi, not just the container.

**P-HIGH-1: SD card corruption**
Docker overlay2 + Redis + Celery logs create unusually write-heavy workloads that wear out consumer SD cards within months. Failure is silent — filesystem goes read-only, SSH may still work but the application produces nothing. Prevention: (1) high-endurance SD card (Samsung Endurance Pro), (2) Redis AOF disabled in compose (`--appendonly no --save ""`), (3) `/tmp` as tmpfs (audio files never touch SD card), (4) log2ram on Pi host for system logs.

**P-HIGH-2: Pi freeze without physical access**
An OOM kill of the networking subsystem or kernel panic leaves the Pi unreachable over Tailscale with no remote recovery. Prevention: enable hardware watchdog (`dtparam=watchdog=on` in config.txt; `RuntimeWatchdogSec=15` in systemd). Test the full power-cycle → SSH-reconnect cycle physically BEFORE going headless. Consider a smart plug ($15-25) as the last-resort power-cycle escape hatch.

**P-HIGH-3: Celery timeouts set for x86 speed**
The Pi 3B is ~10-15x slower than Railway x86 for numpy FFT. Without numba JIT, librosa analysis takes 45-90s per track. If `soft_time_limit` is still configured for Railway speeds (~30s), every Pi job times out. Set `soft_time_limit=180, time_limit=240` and benchmark actual wall-clock time on Pi hardware before finalizing values.

**P-HIGH-4: Shared /tmp volume untested**
The `sg_tmp` tmpfs shared between `api` and `worker` is a new pattern with no Railway equivalent. If misconfigured, all file downloads return 404 silently. Fallback if tmpfs causes problems: bind-mount `/tmp/soundgrabber` from the Pi host as a plain directory.

**P-CARRY-FORWARD (from v1.2):** Cookie expiration (~2 weeks), Firefox-only export, startup `cookies_health_check()`, `no_cache_dir=True` in yt-dlp opts, `fragment_retries=3`. All carry forward unchanged.

---

## Implications for Roadmap

The v1.3 milestone has hard sequential dependencies. Each phase unblocks the next.

### Phase 1: Pi OS and Docker Foundation

**Rationale:** Architecture mismatch (32 vs 64-bit) cascades failures through every subsequent phase. Memory cgroup and watchdog configuration requires a reboot — must be done before compose work begins. Physical restart cycle test requires physical access — only opportunity is before going headless.

**Delivers:** Confirmed aarch64 OS; Docker installed; cgroups active (no memory limit warnings); swap enabled; GPU memory reduced; hardware watchdog active; physical restart cycle tested.

**Avoids:** P-CRITICAL-1, P-CRITICAL-4, P-HIGH-2, P-HIGH-1 (begins SD card protection)

**Research flag:** Standard — all steps are official Pi documentation. No deeper research needed.

---

### Phase 2: Dockerfile and Image Validation

**Rationale:** librosa on ARM is the one dependency where `pip install` success does not guarantee runtime success. Validate the image in isolation before wiring inter-container dependencies. A broken image discovered during compose debugging wastes 20-40 minutes per rebuild on Pi.

**Delivers:** Working `Dockerfile`; `requirements-pi.txt` with essentia/imageio-ffmpeg removed; image builds on Pi; all critical imports verified including librosa functional test; ffprobe resolution confirmed.

**Avoids:** P-CRITICAL-2 (numba failure); P-ARM-04 (build time surprise — build once, validate before compose)

**Research flag:** Moderate empirical risk — run `docker run` librosa validation before building compose.

---

### Phase 3: Docker Compose Stack and Private E2E Validation

**Rationale:** Wire all services together and validate the shared `/tmp` volume with a real end-to-end download over Tailscale. This is the highest-risk integration test. All configuration errors (wrong env vars, cookie injection, memory limits, Celery timeouts) surface here before any public exposure.

**Delivers:** Working `docker-compose.yml`; `.env` populated; all services healthy; `cookies.txt` in place; E2E download confirmed over Tailscale; `docker stats` confirms memory budget; analysis wall-clock time measured and `soft_time_limit` tuned; bgutil necessity determined.

**Avoids:** P-HIGH-4 (shared /tmp), P-CRITICAL-3 (OOM — confirmed by docker stats observation)

**Research flag:** The shared tmpfs volume is the key empirical validation. If it fails, use bind-mount fallback before continuing.

---

### Phase 4: Cloudflare Tunnel and Public Access

**Rationale:** Add public exposure only after private E2E is confirmed. Cloudflare Tunnel configuration is straightforward but should not be debugged simultaneously with application issues.

**Delivers:** `cloudflared` in compose or as systemd service; custom domain resolving; api port binding changed to `127.0.0.1:8000:8000`; `deploy.sh` at `~/soundgrabber/deploy.sh`; 3 successful downloads via public URL; UptimeRobot monitoring active.

**Avoids:** Premature public exposure during debugging; residential IP exposure (Cloudflare proxies it)

**Research flag:** Standard pattern — fully documented. No additional research needed.

---

### Phase Ordering Rationale

- OS/hardware first: cgroup and watchdog require reboots; physical restart test requires physical access — only one window
- Image before compose: librosa ARM behavior must be confirmed empirically before building inter-service dependencies
- Private E2E before public: validates the shared /tmp volume, cookie injection, memory budget, and Celery timing without 502s visible to users
- Tunnel last: no complexity added to debugging; can be isolated as the only new variable in Phase 4

### Research Flags

Empirical validation required during execution (not planning-time research):
- **Phase 2:** Run librosa `beat_track` validation inside the ARM Docker container before building compose
- **Phase 3:** Observe `docker stats` during first librosa analysis; adjust `soft_time_limit` based on actual timing
- **Phase 3:** Confirm bgutil not needed with residential IP on first 3 canary downloads; add bgutil service only if failures occur

Standard patterns (no additional research needed):
- Phase 1: official Raspberry Pi + Docker documentation
- Phase 4: Cloudflare Tunnel ARM setup fully documented

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (ARM package changes) | HIGH | essentia no-ARM-wheel confirmed via PyPI page; imageio-ffmpeg x86-only confirmed via source + issue #23; librosa pure-Python py3-none-any confirmed via piwheels |
| Features (tunnel selection) | HIGH | Cloudflare Tunnel ARM support and ToS confirmed; Tailscale Funnel custom-domain limitation confirmed via open GitHub issue #11563 |
| Architecture (Compose structure) | MEDIUM | Compose patterns well-established; shared tmpfs `/tmp` between api and worker is architecturally correct but empirically untested in this codebase |
| Pitfalls (ARM hardware) | HIGH | SD card, OOM, watchdog, cgroup pitfalls extensively documented; all have specific official sources |
| Pitfalls (ARM timing) | MEDIUM | librosa 45-90s estimate on Cortex-A53 is community consensus; not benchmarked on this specific codebase |
| bgutil on ARM | LOW | bgutil Docker Hub does not list arm64 architecture; behavior on residential IP hypothesis unvalidated |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address During Execution

- **Residential IP vs bgutil:** The core hypothesis of v1.3 is that residential IP removes the need for bgutil. This is unvalidated until Phase 3 canary downloads. If multiple canary downloads fail with bot-detection errors, the bgutil ARM path must be pursued before public launch.
- **librosa analysis timing:** The 45-90s estimate is from similar hardware. Measure actual time with a representative 5-minute WAV on the Pi before setting `soft_time_limit`. Do not guess.
- **essentia dev pin on arm64:** `essentia==2.1b6.dev1389` dev version — even if arm64 wheels exist for some essentia versions, dev pins may not have all platform wheels. Moot if essentia is fully removed; confirm removal is complete in requirements-pi.txt.
- **bgutil Docker image architecture:** If bgutil is needed after Phase 3 canary validation, confirm `brainicism/bgutil-ytdlp-pot-provider` pulls on arm64 before adding it. Fallback: `FROM node:20-slim` with npm install.
- **Tailscale → Docker port routing:** `0.0.0.0:8000:8000` binding makes api accessible at `100.x.x.x:8000` via Tailscale — logically correct, confirm empirically in Phase 3 before adding Cloudflare layer.

---

## Critical Pre-Deployment Checklist

### Before Writing Any Code

- [ ] `uname -m` on Pi returns `aarch64` — if `armv7l`, reflash SD card with Pi OS 64-bit first
- [ ] `docker info` confirms Docker installed and running on Pi
- [ ] Architecture decision recorded: 64-bit OS path (arm64 images, PyPI manylinux wheels)

### Pi Host Configuration (one-time, requires reboot)

- [ ] `gpu_mem=16` added to `/boot/firmware/config.txt`
- [ ] `cgroup_enable=memory cgroup_memory=1` added to `/boot/firmware/cmdline.txt` (all on one line)
- [ ] `dtparam=watchdog=on` added to `/boot/firmware/config.txt`
- [ ] `RuntimeWatchdogSec=15` added to `/etc/systemd/system.conf`
- [ ] Swap: `CONF_SWAPSIZE=512` in `/etc/dphys-swapfile`, `dphys-swapfile swapon` confirmed
- [ ] log2ram installed and active
- [ ] High-endurance SD card confirmed in use
- [ ] **Reboot performed** after all config changes
- [ ] `docker info | grep -i memory` — shows NO "No memory limit support" warnings
- [ ] `cat /proc/sys/kernel/watchdog` — outputs `1`
- [ ] **Physical restart cycle tested:** power off → power on → `ssh pi@100.x.x.x` succeeds within 90 seconds

### Dockerfile and Image Validation

- [ ] `FROM python:3.11-slim-bookworm` (not Alpine, not arm32v7/python)
- [ ] `apt-get install -y --no-install-recommends ffmpeg libsndfile1 nodejs` in Dockerfile
- [ ] `ENV NUMBA_DISABLE_JIT=1` in Dockerfile
- [ ] essentia removed from `requirements-pi.txt`
- [ ] imageio-ffmpeg removed from `requirements-pi.txt`
- [ ] `docker build -t soundgrabber:latest .` completes without error
- [ ] Import validation: `docker run --rm soundgrabber:latest python -c "import librosa, yt_dlp, fastapi, celery; print('OK')"`
- [ ] librosa functional: `docker run --rm soundgrabber:latest python -c "import librosa; y, sr = librosa.load(librosa.ex('trumpet'), duration=10); t, _ = librosa.beat.beat_track(y=y, sr=sr); print('BPM:', t)"` — prints a BPM value, no errors
- [ ] ffprobe found: `docker run --rm soundgrabber:latest python -c "import shutil; p = shutil.which('ffprobe'); assert p, 'ffprobe not found'; print(p)"`

### Docker Compose Stack

- [ ] `docker-compose.yml` created with redis, api, worker services (platform: linux/arm64 on all)
- [ ] `restart: unless-stopped` on all services
- [ ] Memory limits: redis 160m, api 256m, worker 512m, memswap_limit 768m on worker
- [ ] `sg_tmp` volume defined as tmpfs with `size=512m,mode=1777`
- [ ] Both `api` and `worker` mount `sg_tmp:/tmp`
- [ ] Celery command: `--concurrency=1 --max-tasks-per-child=10`
- [ ] `NUMBA_DISABLE_JIT=1` in environment for api and worker
- [ ] `soft_time_limit` and `time_limit` set for ARM speed (start: 180s / 240s; adjust after benchmark)
- [ ] Redis command: `--requirepass ${REDIS_PASSWORD} --maxmemory 128mb --maxmemory-policy allkeys-lru --save "" --appendonly no`
- [ ] `.env` created with `REDIS_PASSWORD`, `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET` (not in git)
- [ ] `docker compose ps` — all services show healthy status
- [ ] `cookies.txt` populated in `sg_cookies` volume (Firefox-exported, confirmed < 10 days old)

### E2E Validation via Tailscale (before public exposure)

- [ ] `curl http://100.x.x.x:8000/health` returns HTTP 200
- [ ] Full E2E: POST /jobs with a YouTube URL → poll status → GET /files returns a valid WAV file
- [ ] `docker stats` observed during analysis: total RAM stays below 950MB
- [ ] Analysis wall-clock time measured; `soft_time_limit` adjusted if needed
- [ ] Second download confirms cleanup: no `sg_*.wav` files remain in `/tmp` after download completes
- [ ] **Canary test without bgutil:** BGUTIL_BASE_URL empty; if 3/3 canary downloads succeed, bgutil is not needed

### Cloudflare Tunnel and Public Access

- [ ] Domain managed in Cloudflare DNS
- [ ] `cloudflared tunnel login` and `tunnel create soundgrabber` completed
- [ ] `tunnel route dns soundgrabber yourdomain.com` completed
- [ ] `CLOUDFLARE_TUNNEL_TOKEN` added to `.env`
- [ ] `cloudflared` service added to docker-compose.yml (or running as systemd service)
- [ ] api port binding changed to `127.0.0.1:8000:8000`
- [ ] `docker compose up -d` confirms cloudflared starts and stays running
- [ ] Public URL (`https://yourdomain.com`) returns HTTP 200

### Milestone Acceptance Gate (all 3 required)

- [ ] Download 1: short beat (< 3 min) via public domain URL — WAV + BPM + key returned within timeout
- [ ] Download 2: medium beat (5-8 min) via public domain URL — WAV + BPM + key returned
- [ ] Download 3: different genre/style than downloads 1 and 2 — WAV + BPM + key returned
- [ ] UptimeRobot or equivalent monitoring active on `GET /health`
- [ ] `deploy.sh` tested: `ssh pi@100.x.x.x 'bash ~/soundgrabber/deploy.sh'` completes without error

---

## Sources

### Primary (HIGH confidence)

- [essentia PyPI — no Linux ARM wheel](https://pypi.org/project/essentia/) — wheel list confirmed
- [piwheels librosa 0.11.0 — py3-none-any pure Python](https://www.piwheels.org/project/librosa/)
- [mwader/static-ffmpeg — amd64 + arm64 only, no arm32](https://hub.docker.com/r/mwader/static-ffmpeg/)
- [Docker cgroup memory Pi fix](https://dalwar23.com/how-to-fix-no-memory-limit-support-for-docker-in-raspberry-pi/)
- [Cloudflare Tunnel on Raspberry Pi (official ARM setup)](https://pimylifeup.com/raspberry-pi-cloudflare-tunnel/)
- [Tailscale Funnel custom domain — open issue #11563](https://github.com/tailscale/tailscale/issues/11563)
- [Celery --max-tasks-per-child docs](https://docs.celeryq.dev/en/stable/userguide/workers.html)
- [numba issue #6723 — RPi3 LLVM mismatch](https://github.com/numba/numba/issues/6723)
- [librosa issue #1854 — running without numba, NUMBA_DISABLE_JIT](https://github.com/librosa/librosa/issues/1854)
- [Docker moby issue #35587 — cgroup memory warning = limits ignored](https://github.com/moby/moby/issues/35587)
- [Hackaday: Raspberry Pi SD card corruption](https://hackaday.com/2022/03/09/raspberry-pi-and-the-story-of-sd-card-corruption/)
- [yt-dlp PO Token Guide — tv client no PO token required](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [imageio-ffmpeg issue #23 — ffprobe not bundled](https://github.com/imageio/imageio-ffmpeg/issues/23)
- [librosa issue #406 — 128MB memory constraint](https://github.com/librosa/librosa/issues/406)
- [librosa issue #1286 — memory growth across iterations](https://github.com/librosa/librosa/issues/1286)
- [Raspberry Pi Forums: watchdog configuration](https://forums.raspberrypi.com/viewtopic.php?t=147501)

### Secondary (MEDIUM confidence)

- [Cloudflare Tunnel media serving community thread — WAV ToS](https://community.cloudflare.com/t/cloudflare-tunnels-and-video-based-traffic-bandwidth-restrictions/722185)
- [Self-hosting API on Pi with Tailscale and Cloudflare](https://www.wirelog.net/posts/2025-02-15-api-server-on-raspberry-pi/)
- [yt-dlp issue #16082 — SABR enforced even with bgutil token on datacenter IP](https://github.com/yt-dlp/yt-dlp/issues/16082)
- [Zapier Engineering: jemalloc for Celery memory fragmentation](https://zapier.com/engineering/celery-python-jemalloc/)

### Tertiary (LOW confidence)

- [bgutil Docker Hub](https://hub.docker.com/r/brainicism/bgutil-ytdlp-pot-provider) — ARM architecture not listed; status on arm64 unknown
- RAM delta estimate arm32 vs arm64 (~50-100MB savings on 32-bit) — community consensus, not benchmarked

---

*Research completed: 2026-05-14 (v1.3 Raspberry Pi Hosting)*
*Supersedes: 2026-04-29 for infrastructure, hosting, and ARM-related sections*
*Product feature findings from 2026-04-29 remain valid and unchanged*
*Ready for roadmap: yes*
