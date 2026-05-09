---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Análise Musical de Precisão
status: Ready to plan
last_updated: "2026-05-09T00:00:00.000Z"
progress:
  total_phases: 2
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

**Current milestone:** v1.1 — Análise Musical de Precisão

**Current focus:** Phase 6 — Precision Analysis Engine

---

## Current Position

Phase: 6 — Precision Analysis Engine
Plan: —
Status: Not started
Last activity: 2026-05-09 — Roadmap v1.1 criado (Phase 6 e Phase 7)

Progress: [ Phase 6: 0/? ] [ Phase 7: 0/? ]

---

## Accumulated Context

### Key Decisions (from v1.0)

| Decision | Rationale |
|----------|-----------|
| Pipeline validated before API | yt-dlp download viability from the target host is the existential risk — if YouTube blocks the server IP, no other phase matters |
| Celery over FastAPI BackgroundTasks | librosa é CPU-bound NumPy work; BackgroundTasks would freeze the event loop under 3+ concurrent users |
| Hardening before frontend | No-auth + free + public é uma superfície de abuso; rate limiting não pode ser adiado para após o launch |
| Visual identity last | Aesthetic work does not gate functional validation and risks rework if component layout changes |
| Table-based layout (no flexbox/grid) | Authenticity requirement — the Y2K aesthetic is structural, not cosmetic; it must be built the way 2002 sites were built |
| slowapi pinned with == not >= | Application dependency convention; version pinning prevents silent breakage from upstream releases |

### Key Decisions (v1.1)

| Decision | Rationale |
|----------|-----------|
| Essentia over librosa for BPM/key | Tunebat IS Essentia — usar o mesmo algoritmo elimina divergência de resultados que erode confiança do produtor |
| Tuning detection via librosa (não Essentia TuningFrequency) | librosa.estimate_tuning() + tuning_to_A4() já estão no venv — sem nova dependência |
| Tuning antes de key detection | tuning_hz é parâmetro de entrada do KeyExtractor — ordem inversa produz HPCP bins desalinhados ao concert pitch |
| HPSS gate para tuning | Beats puramente percussivos retornam ruído como tuning_hz; limiar de energia harmônica < 0.2 retorna None |
| float() wrapping obrigatório | Essentia retorna numpy.float32 que quebra o JSON serializer do Celery silenciosamente — todo valor deve ser wrapped |

### Known Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Datacenter IP flagging by YouTube | CRITICAL | Dedicated VPS IP + cookies + PO Token; abstract download layer |
| Half-tempo BPM misdetection on trap beats | HIGH | RhythmExtractor2013 multifeature mode is resistant to octave errors |
| Temp file accumulation / disk exhaustion | CRITICAL | try/finally + shutil.rmtree + periodic sweeper |
| Essentia ABI mismatch vs numpy version | MODERATE | Verificar `import essentia.standard` logo após install antes de escrever código |
| HPSS threshold 0.2 não validado empiricamente | MODERATE | Testar em 15-20 beats reais durante Phase 6; ajustar se necessário |
| Camelot table missing Essentia key strings | MODERATE | Enumerar todos os 12 key names de Essentia key.cpp e verificar cobertura exata na tabela |

### Todos

- [ ] Verificar `import essentia.standard` no venv imediatamente após install (PITFALL: ABI mismatch)
- [ ] Auditar tabela key_to_camelot() contra todos os 12 key names que Essentia pode retornar (Bb, Eb, Ab, C#, F#)
- [ ] Testar HPSS threshold 0.2 em 15-20 beats reais; ajustar limiar se necessário
- [ ] Validar resultados de BPM e tonalidade contra Tunebat com 3+ beats de referência (trap, house, lo-fi) — gate para milestone completo

### Blockers

None.

---

## Session Continuity

**To resume after a break:**

1. Read `ROADMAP.md` for phase goals and success criteria
2. Read `REQUIREMENTS.md` coverage map to confirm current phase scope
3. Check this file for active todos and known risks
4. Run `/gsd-plan-phase 6` to plan Phase 6

**Last session:** 2026-05-09

---

*Last updated: 2026-05-09 — Roadmap v1.1 criado; Phase 6 e Phase 7 definidas*
