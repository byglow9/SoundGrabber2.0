# State — SoundGrabber

*Project memory. Updated at every phase transition and plan completion.*

---

## Project Reference

**Core value:** O produtor cola um link do YouTube e recebe o beat em WAV com BPM e nota identificados em menos de um minuto, sem nenhuma conta ou instalação.

**Current milestone:** v1 — Public launch (5 phases)

**Current focus:** Phase 1 — Processing Pipeline

---

## Current Position

**Phase:** 1 — Processing Pipeline
**Plan:** None started
**Status:** Not started

**Progress:**

```
[Phase 1] [Phase 2] [Phase 3] [Phase 4] [Phase 5]
[       ] [       ] [       ] [       ] [       ]
  0%
```

**Phase completion:** 0/5 phases done

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 5 |
| Phases complete | 0 |
| Requirements covered | 19/19 |
| Plans written | 0 |
| Plans complete | 0 |

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

### Known Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Datacenter IP flagging by YouTube | CRITICAL | Dedicated VPS IP + cookies + PO Token; abstract download layer |
| Half-tempo BPM misdetection on trap beats | CRITICAL | Always display half/double values alongside primary BPM |
| Temp file accumulation / disk exhaustion | CRITICAL | try/finally + shutil.rmtree + periodic sweeper; established in Phase 1 |
| yt-dlp version drift / silent failures | HIGH | ffprobe validation on every downloaded file; weekly auto-update in CI |
| Concurrent librosa OOM kills | MODERATE | Mono 22050Hz downsampling + 90s window analysis + concurrency cap of 3 |

### Research Flags

- **Phase 1:** Check yt-dlp GitHub issues for current YouTube breakages the week Phase 1 begins. Validate cookie/PO Token strategy against the actual production host before building the API layer.
- **Phase 3:** Rate limit numbers (3/min, 20/hr) are estimates. Start conservative; tune against observed traffic.

### Todos

- [ ] Provision VPS with dedicated IP before starting Phase 1
- [ ] Obtain valid YouTube session cookies for yt-dlp before running Phase 1 tests
- [ ] Verify ffmpeg >= 6.0 and libsndfile1 installed on production host

### Blockers

None.

---

## Session Continuity

**To resume after a break:**

1. Read `ROADMAP.md` for phase goals and success criteria
2. Read `REQUIREMENTS.md` coverage map to confirm current phase scope
3. Check this file for active todos and known risks
4. Run `/gsd-plan-phase` for the current phase

**Last session:** 2026-04-29 — Roadmap created, Phase 1 is next.

---

*Last updated: 2026-04-29*
