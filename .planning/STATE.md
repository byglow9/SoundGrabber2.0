---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: milestone
status: executing
last_updated: "2026-05-09T19:06:51.224Z"
last_activity: 2026-05-09
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# State — SoundGrabber

*Project memory. Updated at every phase transition and plan completion.*

---

## Project Reference

**Core value:** O produtor cola um link do YouTube e recebe o beat em WAV com BPM e nota identificados em menos de um minuto, sem nenhuma conta ou instalação.

**Current milestone:** v1.1 — Security Hardening (2 phases: 6 and 7)

**Current focus:** Phase 06 — application-security

---

## Current Position

Phase: 7
Plan: Not started
Status: Executing Phase 06
Last activity: 2026-05-09

**Progress:**

```
v1.0 Phases:
[Phase 1] [Phase 2] [Phase 3] [Phase 4] [Phase 5]
[XXXXXXXX] [XXXXXXXX] [XXXXXXXX] [XXXXXXXX] [XXXXXXXX]
  Done (phases 3-5 complete; phases 1-2 planned but functional)

v1.1 Phases:
[Phase 6] [Phase 7]
[        ] [        ]
  0% — Not started
```

**Phase completion (v1.1):** 0/2 phases done

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.1) | 2 |
| Phases complete (v1.1) | 0 |
| Requirements covered (v1.1) | 16/16 |
| Plans written (v1.1) | 0 |
| Plans complete (v1.1) | 0 |

---

## Accumulated Context

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Pipeline validated before API | yt-dlp download viability from the target host is the existential risk — if YouTube blocks the server IP, no other phase matters |
| Celery over FastAPI BackgroundTasks | librosa is CPU-bound NumPy work; BackgroundTasks would freeze the event loop under 3+ concurrent users |
| Hardening before frontend | No-auth + free + public is an abuse surface; rate limiting cannot be deferred until after launch |
| Visual identity last | Aesthetic work does not gate functional validation and risks rework if component layout changes |
| Table-based layout (no flexbox/grid) | Authenticity requirement — the Y2K aesthetic is structural, not cosmetic; it must be built the way 2002 sites were built |
| slowapi pinned with == not >= | Application dependency convention; version pinning prevents silent breakage from upstream releases |
| TDD RED stubs before implementation | Nyquist protocol — each Phase 3 behavior has a failing test awaiting implementation in plans 02 and 03 |
| RateLimitExceeded imported early | Imported in 03-02 without immediate use so Plan 03 does not need to reopen the import block |
| sweep multi-pattern loop | for pattern in tuple of 3 globs — immutable, consistent with existing pure-function style |
| response: Response in submit_job | slowapi sync_wrapper calls _inject_headers(kwargs.get("response"), ...) for 2xx; without it raises Exception |
| exc.limit.limit.get_expiry() | exc.limit is Limit wrapper (slowapi); .limit is RateLimitItem (limits lib) with get_expiry() |
| LIMITS:LIMITER* flush in conftest | Redis rate-limit counters persist across tests; flush prevents spurious 429 on second test |
| Application security before infra security (Phase 6 before 7) | Code controls + tests can be written and verified locally; nginx/HTTPS requires a live server with a domain and DNS — unblocking the code work first lets infra work proceed without a host dependency |
| SEC-INFRA-01 in Phase 7 (not Phase 6) | Redis auth enforcement is an infra-boundary control validated at deployment time, not unit-testable in isolation; belongs with other nginx/HTTPS deployment controls |

### Known Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Datacenter IP flagging by YouTube | CRITICAL | Dedicated VPS IP + cookies + PO Token; abstract download layer |
| Half-tempo BPM misdetection on trap beats | CRITICAL | Always display half/double values alongside primary BPM |
| Temp file accumulation / disk exhaustion | CRITICAL | try/finally + shutil.rmtree + periodic sweeper; established in Phase 1 |
| yt-dlp version drift / silent failures | HIGH | ffprobe validation on every downloaded file; weekly auto-update in CI |
| Concurrent librosa OOM kills | MODERATE | Mono 22050Hz downsampling + 90s window analysis + concurrency cap of 3 |
| Let's Encrypt cert renewal automation | MODERATE | Phase 7 must configure certbot cron/systemd timer — manual renewal is a liveness risk |

### Research Flags

- **Phase 1:** Check yt-dlp GitHub issues for current YouTube breakages the week Phase 1 begins. Validate cookie/PO Token strategy against the actual production host before building the API layer.
- **Phase 3:** Rate limit numbers (3/min, 20/hr) are estimates. Start conservative; tune against observed traffic.
- **Phase 7:** Confirm Let's Encrypt rate limits for the target domain before issuing the first certificate. Staging environment cert issuance first to avoid hitting the 5 certs/week production limit.

### Todos

- [ ] Provision VPS with dedicated IP before starting Phase 1
- [ ] Obtain valid YouTube session cookies for yt-dlp before running Phase 1 tests
- [ ] Verify ffmpeg >= 6.0 and libsndfile1 installed on production host
- [ ] Confirm domain DNS points to VPS IP before starting Phase 7 (Let's Encrypt requires HTTP-01 challenge)
- [ ] Set REDIS_URL with password in production .env before Phase 7 deployment

### Blockers

None.

---

## Session Continuity

**To resume after a break:**

1. Read `ROADMAP.md` for phase goals and success criteria
2. Read `REQUIREMENTS.md` coverage map to confirm current phase scope
3. Check this file for active todos and known risks
4. Run `/gsd-plan-phase 6` to begin Application Security planning

**Last session:** 2026-05-09 — v1.1 roadmap created; Phase 6 is next

---

*Last updated: 2026-05-09 — v1.1 Security Hardening roadmap appended (Phases 6–7, 16 requirements)*
