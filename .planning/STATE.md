---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: YouTube Pipeline Fix
status: planning
last_updated: "2026-05-10T00:00:00.000Z"
last_activity: 2026-05-10
progress:
  total_phases: 0
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

**Current focus:** Defining requirements

---

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-10 — Milestone v1.2 started

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.2) | TBD |
| Phases complete (v1.2) | 0 |
| Requirements covered (v1.2) | TBD |
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
| ffprobe path no Railway | imageio-ffmpeg não no PATH do sistema Railway | Aberto |

### Todos

- [ ] Pesquisar estado atual das estratégias de bypass de bot detection no yt-dlp (Reddit, GitHub issues, fóruns)
- [ ] Verificar se bgutil-ytdlp-pot-provider ainda é mantido e funciona no Railway
- [ ] Testar iOS client com cookies web existentes
- [ ] Confirmar ffprobe path correto no ambiente Railway
- [ ] Validar pipeline completo end-to-end após fix

### Blockers

Nenhum.

---

## Session Continuity

**To resume after a break:**

1. Read `ROADMAP.md` para fases e critérios de sucesso (a ser criado)
2. Read `REQUIREMENTS.md` para escopo do milestone (a ser criado)
3. Read este arquivo para contexto e riscos conhecidos

**Last session:** 2026-05-10 — Milestone v1.2 iniciado

---

*Last updated: 2026-05-10 — Milestone v1.2 YouTube Pipeline Fix definido; requirements e roadmap pendentes*
