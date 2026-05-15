---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Raspberry Pi Hosting
status: planning
last_updated: "2026-05-15T18:51:39.826Z"
last_activity: 2026-05-15
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 6
  completed_plans: 5
  percent: 83
---

# State — SoundGrabber

*Project memory. Updated at every phase transition and plan completion.*

---

## Project Reference

**Core value:** O produtor cola um link do YouTube e recebe o beat em WAV com BPM e nota identificados em menos de um minuto, sem nenhuma conta ou instalação.

**Current milestone:** v1.3 — Raspberry Pi Hosting

**Current focus:** Phase 13 — docker-compose

---

## Current Position

Phase: 14
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-15

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.3) | TBD |
| Phases complete (v1.3) | 0 |
| Requirements covered (v1.3) | 0/TBD |
| Plans written (v1.3) | 0 |
| Plans complete (v1.3) | 0 |

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

### Roadmap Evolution

- Phase 11 added: Som da Semana — painel lateral curado com lançamentos da cena underground, atualizado pelo operador via endpoint autenticado
- Phase 10.1 inserted after Phase 10 (URGENT): OAuth2 + Railway Volume auth migration — elimina expiração de cookies e dependência do bgutil
- Phase 12 hardware confirmed (2026-05-14): i5-3210M @ 2.50GHz (Ivy Bridge, 2c/4t), 4GB DDR3, 700GB HDD, Intel HD 4000; chipset Panther Point → iTCO_wdt disponível para watchdog; baseline Celery concurrency=1

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
| ffprobe path no Railway | imageio-ffmpeg não no PATH do sistema Railway | Resolvido em Phase 8 (PIPE-01, DEPLOY-01) |
| nsig extraction failure | Diferença de versão yt-dlp (local vs Railway) | Resolvido por atualização yt-dlp |
| `YTDLP_NO_PLUGINS=1` bloqueava GetPOT silenciosamente | Adicionado em fase anterior para "limpar plugins antigos" | Resolvido em 10.1-06 (`c1e5657`) |
| extractor_args formato CLI vs Python API | yt-dlp 2026 Python API exige nested dict, não lista de strings | Resolvido em 10.1-06 (`4d88510`) |
| bgutil plugin version mismatch (0.8.5 vs servidor 0.8.1) | Plugin PyPI não alinhado com servidor Railway | Resolvido em 10.1-06 (`3635498`) |
| LOGIN_REQUIRED no Railway com GetPOT funcionando (2026-05-13) | Cookies no Volume expirados/rotacionados — YouTube rejeita sessão mesmo com PO Token válido | **BLOQUEADOR ATUAL** |

### Todos

- [x] Implementar Phase 8: correções em pipeline.py + nixpacks.toml
- [x] Deploy bgutil no Railway (Phase 9 — ação humana)
- [x] Configurar BGUTIL_BASE_URL nos serviços Railway (Phase 9 — ação humana)
- [x] Reintroduzir bgutil como PO Token provider (10.1-06 Task 1 — 6 commits)
- [x] Corrigir 4 bugs descobertos durante execução (YTDLP_NO_PLUGINS, extractor_args format, version mismatch, player_clients)
- [ ] **Renovar cookies no Volume Railway** — `YTDLP_COOKIES_B64` com arquivo fresco, redeploy, re-run E2E
- [ ] Validar pipeline E2E com 3 URLs de beats (Task 2 do plano 10.1-06)
- [ ] Cleanup YTDLP_COOKIES_B64 após E2E aprovado (Task 3 do plano 10.1-06)

### Blockers

**CRÍTICO (2026-05-13):** YouTube retorna `LOGIN_REQUIRED` mesmo com GetPOT funcionando e PO Token gerado com sucesso. Stack técnico completo e correto: cookies chegam, Node ativo, bgutil gera PO Token (HTTP 200), extractor_args no formato certo, player_clients `web_safari,web`. YouTube rejeita na camada de autenticação. Diagnóstico aponta para **cookies expirados no Volume** — bytes caíram de 2987 para ~1600 durante tentativas (yt-dlp sobrescreve jar ao detectar sessão inválida). Próximo passo: exportar cookies frescos de conta Google autenticada e atualizar `YTDLP_COOKIES_B64`.

---

## Session Continuity

**To resume after a break:**

1. Read `.planning/ROADMAP.md` — fases 8, 9, 10 com critérios de sucesso
2. Read `.planning/REQUIREMENTS.md` — seção v1.2 com PIPE-01..07 e DEPLOY-01..03
3. Read este arquivo para contexto e riscos conhecidos
4. Próximo comando: `/gsd-plan-phase 8`

**Last session:** 2026-05-15T18:51:39.821Z

---

*Last updated: 2026-05-10 — v1.2 roadmap definido; Phase 8 pronta para planejamento*
