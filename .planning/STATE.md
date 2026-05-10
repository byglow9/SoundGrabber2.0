---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: YouTube Pipeline Fix
status: planning
last_updated: "2026-05-10T00:00:00.000Z"
last_activity: 2026-05-10
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State — SoundGrabber

*Project memory. Updated at every phase transition and plan completion.*

---

## Project Reference

**Core value:** O produtor cola um link do YouTube e recebe o beat em WAV com BPM e nota identificados em menos de um minuto, sem nenhuma conta ou instalação.

**Current milestone:** v1.2 — YouTube Pipeline Fix

**Current focus:** Roadmap defined — ready to plan Phase 8

---

## Current Position

Phase: Phase 8 (not started)
Plan: —
Status: Roadmap complete, awaiting plan
Last activity: 2026-05-10 — v1.2 roadmap created (3 phases, 10 requirements)

Progress: `[ ] [ ] [ ]` (0/3 phases complete)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.2) | 3 |
| Phases complete (v1.2) | 0 |
| Requirements covered (v1.2) | 10/10 |
| Plans written (v1.2) | 0 |
| Plans complete (v1.2) | 0 |

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
| Application security before infra security (Phase 6 before 7) | Code controls + tests can be written and verified locally; nginx/HTTPS requires a live server with a domain and DNS |
| Research before implementation (v1.2) | YouTube bot detection is a moving target; picking the wrong client strategy wastes sprint — invest in research first |
| Phase 8: code fixes before Railway infra (v1.2) | All pipeline.py and nixpacks.toml changes are testable locally; no point deploying bgutil until the code that calls it is correct |
| Phase 9: human checkpoint for bgutil deploy (v1.2) | Deploying a Railway service and setting env vars requires dashboard access — this is a deliberate manual step, not automatable by Claude |
| No silent fallback when bgutil unavailable (v1.2) | Silent client switching hides configuration errors and makes failures non-deterministic; explicit failure is required by PIPE-06 |

### Known Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Datacenter IP flagging by YouTube | CRITICAL | Dedicated VPS IP + cookies + PO Token; abstract download layer |
| yt-dlp client strategy breaks silently on YouTube update | CRITICAL | Pin yt-dlp version + automated smoke test on deploy |
| Half-tempo BPM misdetection on trap beats | HIGH | Always display half/double values alongside primary BPM |
| Temp file accumulation / disk exhaustion | HIGH | try/finally + shutil.rmtree + periodic sweeper |
| yt-dlp version drift / silent failures | HIGH | ffprobe validation on every downloaded file; weekly auto-update in CI |
| Concurrent librosa OOM kills | MODERATE | Mono 22050Hz downsampling + 90s window analysis + concurrency cap of 3 |

### Known Issues (v1.2 context)

| Issue | Root Cause | Status |
|-------|------------|--------|
| Bot detection | Datacenter IP, sem auth completa | Parcialmente resolvido com cookies |
| "Requested format is not available" | Web client precisa PO Token; android client falha com cookies web | Aberto |
| nsig extraction failure | Diferença de versão yt-dlp (local 2024.12 vs Railway 2026.3) | Aberto |
| ffprobe path no Railway | imageio-ffmpeg não no PATH do sistema Railway | Aberto — endereçado em Phase 8 (PIPE-01, DEPLOY-01) |

### Todos

- [ ] Implementar Phase 8: correções em pipeline.py + nixpacks.toml
- [ ] Deploy bgutil no Railway (Phase 9 — ação humana)
- [ ] Configurar BGUTIL_BASE_URL nos serviços Railway (Phase 9 — ação humana)
- [ ] Validar pipeline end-to-end com 3 URLs de beats (Phase 10)

### Blockers

Nenhum.

---

## Session Continuity

**To resume after a break:**

1. Read `.planning/ROADMAP.md` — fases 8, 9, 10 com critérios de sucesso
2. Read `.planning/REQUIREMENTS.md` — seção v1.2 com PIPE-01..07 e DEPLOY-01..03
3. Read este arquivo para contexto e riscos conhecidos
4. Próximo comando: `/gsd-plan-phase 8`

**Last session:** 2026-05-10 — v1.2 roadmap criado (3 fases: 8, 9, 10); 10/10 requisitos mapeados

---

*Last updated: 2026-05-10 — v1.2 roadmap definido; Phase 8 pronta para planejamento*
