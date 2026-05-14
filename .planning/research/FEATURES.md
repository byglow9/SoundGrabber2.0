# Feature Landscape

**Domain:** YouTube audio downloader with music analysis (BPM + key detection) for underground/bedroom producers
**Researched:** 2026-05-14 (updated for v1.3 Raspberry Pi Hosting milestone)
**Confidence:** HIGH for table stakes (verified across multiple tools); MEDIUM for differentiators (community patterns + tool gaps); HIGH for anti-features (user complaint data); HIGH for tunnel options (verified against official docs)

---

## Milestone v1.3 Scope — Raspberry Pi Public Hosting

This file extends the original feature landscape with infrastructure features needed for the
Raspberry Pi 3B hosting migration from Railway. The core product features from v1.0–v1.2
remain valid and are preserved in the final section. The sections below cover the new domain:
**how to expose a device behind residential NAT to the public internet.**

---

## Tunnel Options — Exposing Pi to the Internet Without Port Forwarding

The Pi is behind a residential ISP that does not support port forwarding on the provided
router. Tailscale is already installed (used for SSH access). The only options that work
behind CGNAT/restricted ISP with zero router config are outbound-connection tunnel services.

### Option A: Cloudflare Tunnel (cloudflared)

**How it works:** A daemon (`cloudflared`) runs on the Pi and establishes a persistent
outbound TLS connection to Cloudflare's edge network. Incoming public HTTP/S requests to
your domain arrive at Cloudflare, which forwards them inbound through that tunnel to your
local service. No inbound port ever opens on the router.

**Requirements:**
- Own a public domain (any registrar; domain must be managed by Cloudflare DNS)
- Cloudflare account (free tier sufficient)
- `cloudflared` binary installed on Pi (ARM32/armhf supported via official apt repo)

**Setup flow:**
1. `cloudflared tunnel login` (OAuth to Cloudflare via browser on any machine)
2. `cloudflared tunnel create soundgrabber`
3. `cloudflared tunnel route dns soundgrabber yourdomain.com`
4. Write `~/.cloudflared/config.yml` with tunnel UUID + local service URL
5. `sudo cloudflared service install && sudo systemctl enable --now cloudflared`

**ARM support:** Official Cloudflare apt repository provides `linux/arm` packages. Pi 3B
(ARMv7/armhf) is explicitly supported.

**ToS concern — WAV file downloads:** The legacy Cloudflare ToS clause 2.8 restricted
"non-HTML content" served through the free CDN. Cloudflare has since revised this: the
restriction now applies only to the CDN product and only to content hosted outside
Cloudflare (Stream, R2, etc.). **Cloudflare Tunnel is a connectivity product, not the CDN.**
Community consensus (and Cloudflare staff responses in the forums) is that serving audio
file downloads through Tunnel does not violate ToS, provided it is not a primary
large-scale video/streaming use case. Serving WAV files for an on-demand download tool
(each file generated per request, then deleted) is within acceptable use. **Confidence:
MEDIUM — Cloudflare has not published explicit per-file-type tunnel guidance; monitor
for account warnings.**

**Custom domain:** Yes, full custom domain with Cloudflare DNS CNAME. This is a first-class
feature. You get a real branded URL (e.g. `soundgrabber.yourdomain.com`).

**Bandwidth:** No published limit on the free plan for Tunnel traffic. Community reports
confirm no throttling at modest scale (hundreds of users/day). Enterprise patterns differ.

**Availability/reliability:** Cloudflare's edge is globally distributed. The tunnel itself
is the single point of failure (if the Pi goes offline, the tunnel drops). Cloudflare will
return 502/503 to users automatically.

**Verdict for SoundGrabber:** Recommended option. Free, stable, custom domain, no ToS
conflict for this use case, systemd integration, ARM support confirmed.

---

### Option B: Tailscale Funnel

**How it works:** Tailscale's relay infrastructure (`DERP` nodes) forward public HTTPS
requests to your tailnet device. You run `tailscale funnel 443` and Tailscale handles cert
issuance (Let's Encrypt via ACME) and routing.

**Requirements:**
- Tailscale account (already in use on the Pi)
- Tailscale CLI v1.38+ installed
- Funnel must be enabled in the Tailscale admin console (double opt-in per device)

**Setup flow:**
```bash
# Enable Funnel in Tailscale admin console first
tailscale funnel --bg 443   # background mode, survives shell exit
```

**Ports available:** 443, 8443, 10000 only. Port 80 not supported (HTTPS only).

**Custom domain:** No. The public URL is always `<machine>.<tailnet>.ts.net`. You cannot
point your own domain to it — TLS certs are issued only for `*.ts.net` and CNAME attempts
fail with SSL_ERROR_SYSCALL because the presented cert does not match the custom domain.
This is a known open issue (GitHub issue #11563, open as of 2025).

**Bandwidth:** Non-configurable limits apply. The actual threshold is undisclosed by
Tailscale. Reports from homelab users suggest the limit is high enough for 4K video
streaming at small scale, but with no SLA or published number, production planning is risky.

**Reliability:** Beta status as of 2025. No load balancing, no failover. One DERP path.

**Verdict for SoundGrabber:** Acceptable for development/testing and quick demo shares.
Not recommended as primary production path because (a) no custom domain possible and (b)
undisclosed bandwidth limit with no SLA. Use as a backup if Cloudflare Tunnel is unavailable.

---

### Option C: frp (Fast Reverse Proxy) — Self-Hosted

**How it works:** Two components: `frps` (server) on a VPS with a public IP, `frpc` (client)
on the Pi. The Pi client opens an outbound TCP connection to the VPS server, which then
accepts public traffic and proxies it inbound through the tunnel.

**Requirements:**
- A separate public VPS (e.g. $5/month DigitalOcean, Linode, Hetzner)
- DNS pointed to that VPS IP
- frp binary on both Pi and VPS (ARM binary available from GitHub releases)

**Verdict for SoundGrabber:** Overkill for this use case. Adds a second server to manage,
a cost, and an additional failure point. Only worthwhile if Cloudflare Tunnel is unavailable
for policy reasons or if full control over the relay infrastructure is required. Reject for v1.3.

---

## Comparison Table

| Criterion | Cloudflare Tunnel | Tailscale Funnel | frp (self-hosted) |
|---|---|---|---|
| Custom domain | Yes (Cloudflare DNS) | No (`.ts.net` only) | Yes (any DNS) |
| ARM32/Pi 3B support | Yes (official apt pkg) | Yes (already installed) | Yes (GitHub release) |
| Cost | Free | Free (already paying for Tailscale if paid) | ~$5/mo VPS |
| Setup complexity | Low (5 commands + YAML) | Very low (1 command) | High (2 servers, frp config) |
| No extra server needed | Yes | Yes | No |
| Domain requires ownership | Yes | No | Yes |
| Bandwidth limit | None published | Undisclosed, non-configurable | VPS bandwidth |
| Custom SSL cert | Automatic (Cloudflare-managed) | Automatic (Let's Encrypt `.ts.net`) | Manual or Let's Encrypt |
| Production suitability | HIGH | MEDIUM (beta, no SLA) | HIGH (if VPS managed) |
| WAV download ToS risk | Low (Tunnel is not CDN) | None (own infra) | None (own infra) |
| Recommended for v1.3 | YES | Dev/backup only | Reject |

---

## Table Stakes — Infrastructure Features

Features the hosting setup MUST provide for the product to work publicly.

| Feature | Why Required | Complexity | Notes |
|---|---|---|---|
| HTTPS for all traffic | Browser security, HSTS already in place in code | Low | Cloudflare Tunnel and Tailscale Funnel both terminate TLS automatically |
| Public URL (not `ts.net`) | Users must be able to type or share a real URL | Low | Requires owning a domain; cost ~$10-15/yr |
| Systemd service for tunnel | Pi must survive reboots without manual intervention | Low | `sudo systemctl enable cloudflared` |
| Docker restart policy | App containers must restart on reboot | Low | Already `restart: unless-stopped` in compose |
| Remote SSH access via Tailscale | Deploy without physical access to Pi | Already in place | Use Tailscale IP to SSH from anywhere |
| Git-based deployment | Reproducible, auditable deploys | Low | `git pull + docker compose up` script on Pi |

---

## Differentiators — What Makes This Setup Good

| Feature | Value | Complexity | Notes |
|---|---|---|---|
| Residential IP for YouTube | Avoids Railway datacenter blocks (root cause of v1.2 failures) | None (inherent to Pi) | This is the primary reason for migrating to Pi |
| Zero CDN dependency for compute | All processing on Pi, Cloudflare only proxies HTTP | Low | WAV generation happens locally, no cloud compute cost |
| Tailscale as out-of-band access | Can always SSH into Pi even if the public tunnel breaks | Already in place | Critical for ops without physical access |

---

## Anti-Features for This Milestone

Features to explicitly NOT build in v1.3.

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Kubernetes / container orchestration | Pi 3B has 1GB RAM; k3s would consume most of it | Docker Compose is correct at this scale |
| Nginx reverse proxy layer | Cloudflare Tunnel talks directly to FastAPI; an extra Nginx hop adds latency and config surface | Point Cloudflare Tunnel directly at `localhost:8000` |
| GitHub Actions CI/CD pipeline | Adds complexity; SSH + git pull is sufficient at this scale | Simple deploy script (see deploy flow below) |
| Multiple DNS records / multi-region | Pi is a single node; multi-region is not applicable | Accept single-node; monitor uptime |
| Automatic SSL cert management beyond Cloudflare | Cloudflare Tunnel handles certs; running certbot in parallel causes conflicts | Let Cloudflare own the cert |

---

## Deploy Flow — Remote Code Updates via SSH over Tailscale

This is the recommended operational workflow for updating SoundGrabber on the Pi when
neither developer has physical access.

### SSH Access

```bash
# SSH into Pi using Tailscale IP (stable across network changes)
ssh pi@100.x.y.z          # replace with Pi's Tailscale IP
# or if MagicDNS is enabled:
ssh pi@pi-hostname.tailnet.ts.net
```

### Deploy Script (run on Pi, or invoke via SSH)

```bash
#!/bin/bash
set -e

cd /home/pi/SoundGrabber2.0
git pull origin main
docker compose pull          # pull any updated base images if pushed to registry
docker compose up -d --build --remove-orphans
docker system prune -f       # reclaim disk (Pi storage is limited)
```

Save as `/home/pi/deploy.sh`, `chmod 750 /home/pi/deploy.sh`.

### One-Liner Remote Deploy

```bash
ssh pi@100.x.y.z 'bash /home/pi/deploy.sh'
```

### Environment and Secrets Management

Secrets (`REDIS_PASSWORD`, `COOKIE_SECRET`, `cookies.txt`) are NOT in git. They live at:
- `/home/pi/SoundGrabber2.0/.env` — loaded by Docker Compose
- `/home/pi/yt-dlp-cache/cookies.txt` — mounted as Docker volume

These are set once during initial Pi setup and are not touched by the deploy script.
If secrets rotate, update manually via `scp` or `ssh` + editor.

### Architecture Note — ARMv7 (linux/arm/v7)

Pi 3B runs a 32-bit ARM kernel (ARMv7/armhf) even with a 64-bit CPU. Docker images MUST
be multi-arch or explicitly tagged `linux/arm/v7`. Base images to verify:
- `python:3.11-slim` — available for `linux/arm/v7` (confirmed on Docker Hub)
- `redis:7-alpine` — available for `linux/arm/v7`
- Custom app image — must build on Pi or use `docker buildx` cross-compilation

**Recommended:** Build the image directly on the Pi during `docker compose up --build`.
Cross-compilation on a developer machine requires `docker buildx` with QEMU emulation and
is slower. Building on Pi avoids arch mismatch entirely at the cost of longer build time
(Pi 3B is slow; first build may take 10–15 minutes).

---

## Feature Dependencies

```
Public access
  └── Own domain (DNS)
        └── Cloudflare Tunnel (cloudflared on Pi)
              └── FastAPI app (Docker Compose on Pi)
                    ├── Celery worker
                    ├── Redis
                    └── yt-dlp + librosa (existing pipeline)

Remote deploy
  └── Tailscale VPN (already in place)
        └── SSH access to Pi
              └── git pull + docker compose up
                    └── .env file (secrets, pre-placed on Pi)
```

---

## MVP Recommendation for v1.3

**Must have (milestone complete when these work):**

1. `cloudflared` installed and running as systemd service on Pi
2. Custom domain pointing to the Pi via Cloudflare DNS
3. Cloudflare Tunnel config pointing to `http://localhost:8000`
4. Docker Compose running all services with `restart: unless-stopped`
5. Deploy script at `/home/pi/deploy.sh` callable via SSH
6. 3 successful YouTube downloads via the public URL (validation gate)

**Nice to have (not blocking milestone):**

- Uptime monitoring via UptimeRobot (free, pings URL every 5 min, alerts on downtime)
- `watchtower` for automatic base image updates (low value, Pi builds locally anyway)

**Defer (out of scope for v1.3):**

- GitHub Actions automated CI/CD
- Log aggregation / remote observability
- Horizontal scaling (single Pi is the constraint)

---

## Original Product Feature Landscape (v1.0–v1.2, Preserved)

### Table Stakes

| Feature | Why Expected | Complexity | Underground Producer Relevance |
|---|---|---|---|
| Paste URL and trigger download | Every tool does this; it's the entry point | Low | Core workflow |
| Real-time processing feedback | Download + convert + analyze takes 10-60s; silence reads as broken | Low-Med | High: producers close tabs fast |
| Direct WAV file download (no account) | No-account download is standard; gating = drop-off | Low | Critical |
| BPM display after analysis | Standard output of every BPM tool | Med | Critical |
| Musical key display (F# minor, etc.) | Expected by every producer tool | Med | Critical |
| HTTPS / no sketchy redirects | Community trust signal | Low | High |

### Differentiators

| Feature | Value Proposition | Complexity |
|---|---|---|
| Y2K / 2000s internet aesthetic | Cultural identity, instant belonging | Low-Med |
| Combined download + analysis in one step | Eliminates the 2-3 tool workflow | Med |
| Camelot wheel notation | Harmonic mixing standard | Low |
| Half-time / double-time BPM toggle | Common librosa detection error for hip-hop | Low |
| Copy BPM / key buttons | Removes friction in DAW handoff | Low |

### Anti-Features

| Anti-Feature | Why Avoid |
|---|---|
| User accounts / login | Contradicts zero-friction core value |
| Multiple formats (MP3, FLAC) | WAV is the right choice; format picker adds complexity |
| Playlist / batch download | Single URL is the product |
| SoundCloud / TikTok support | YouTube only is a deliberate constraint |
| In-browser audio playback | Delays download; adds state management complexity |
| Dark mode toggle | Breaks Y2K aesthetic coherence |

---

## Sources

**Tunnel options:**
- [Tailscale Funnel official docs](https://tailscale.com/kb/1223/funnel) — HIGH confidence
- [Tailscale Funnel custom domain issue #11563](https://github.com/tailscale/tailscale/issues/11563) — HIGH confidence (open issue)
- [Tailscale Funnel bandwidth limits — HN discussion](https://news.ycombinator.com/item?id=35374302) — MEDIUM confidence
- [Cloudflare Tunnel on Raspberry Pi — Pi My Life Up](https://pimylifeup.com/raspberry-pi-cloudflare-tunnel/) — HIGH confidence
- [Cloudflare Tunnel + Raspberry Pi + Docker — peppe8o](https://peppe8o.com/cloudflare-tunnel-raspberry-pi/) — MEDIUM confidence
- [Cloudflare ToS section 2.8 update — official blog](https://blog.cloudflare.com/updated-tos/) — HIGH confidence
- [Cloudflare Tunnel media serving community thread](https://community.cloudflare.com/t/cloudflare-tunnels-and-video-based-traffic-bandwidth-restrictions/722185) — MEDIUM confidence
- [frp GitHub — fatedier/frp](https://github.com/fatedier/frp) — HIGH confidence

**Deploy workflow:**
- [Automated deployments via Tailscale GitHub Action](https://gabrielaleks.com/blog/automated-deployments-to-a-private-server-using-tailscale-github-action/) — MEDIUM confidence
- [Self-hosting API on Raspberry Pi with Tailscale and Cloudflare — wirelog.net](https://www.wirelog.net/posts/2025-02-15-api-server-on-raspberry-pi/) — MEDIUM confidence
- [GitHub Actions + Tailscale + Docker — aaronstannard.com](https://aaronstannard.com/docker-compose-tailscale/) — MEDIUM confidence
- [Docker on Raspberry Pi ARMv7 — Docker official docs](https://docs.docker.com/engine/install/raspberry-pi-os/) — HIGH confidence
