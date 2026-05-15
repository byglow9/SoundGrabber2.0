---
phase: 13
slug: docker-compose
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-15
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/test_pipeline_docker.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds (unit) + manual Docker gates |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline_docker.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite green + manual Docker gates (D-07, DEPLOY-05, DEPLOY-06)
- **Max feedback latency:** ~15 seconds (unit tests only)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-xx-01 | refactor | 1 | DEPLOY-04 / D-02 | — | pipeline.py não importa imageio_ffmpeg | unit | `pytest tests/test_pipeline_docker.py::test_no_imageio_ffmpeg_import -x -q` | ❌ Wave 0 | ⬜ pending |
| 13-xx-02 | refactor | 1 | DEPLOY-04 / D-03 | — | pipeline.py não importa librosa | unit | `pytest tests/test_pipeline_docker.py::test_no_librosa_import -x -q` | ❌ Wave 0 | ⬜ pending |
| 13-xx-03 | refactor | 1 | D-03 | — | detect_tuning com Essentia retorna float ou None | integration | `pytest tests/test_pipeline_docker.py::test_detect_tuning_essentia -x -q -m integration` | ❌ Wave 0 | ⬜ pending |
| 13-xx-04 | dockerfile | 2 | DEPLOY-04 / D-07 | — | Gate de validação de imports no container | manual | `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"` | N/A | ⬜ pending |
| 13-xx-05 | compose | 2 | DEPLOY-05 | — | Todos os serviços com restart: unless-stopped | manual | `docker compose config \| grep "unless-stopped" \| wc -l` (espera: 4) | N/A | ⬜ pending |
| 13-xx-06 | compose | 2 | DEPLOY-06 | — | sg_tmp compartilhado: worker escreve, api lê | manual | `docker exec worker touch /tmp/sg_test.txt && docker exec api ls /tmp/sg_test.txt` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline_docker.py` — stubs para DEPLOY-04/D-02/D-03: `test_no_imageio_ffmpeg_import`, `test_no_librosa_import`, `test_detect_tuning_essentia`

*Existing infrastructure (pytest.ini, tests/conftest.py) cobre a fase — apenas o novo arquivo de testes precisa ser criado.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `import essentia.standard, yt_dlp, fastapi, celery` no container | DEPLOY-04 / D-07 | Requer Docker runtime; não testável via pytest sem Docker-in-Docker | `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"` — esperado exit 0 + output `OK` |
| restart: unless-stopped em todos os 4 serviços | DEPLOY-05 / D-15 | Verificação de config YAML e comportamento de runtime Docker | `docker compose config \| grep "unless-stopped"` — deve aparecer 4 vezes |
| Volume sg_tmp compartilhado entre api e worker | DEPLOY-06 / D-12 | Requer dois containers rodando simultaneamente | `docker exec worker touch /tmp/sg_test.txt && docker exec api cat /tmp/sg_test.txt` |
| Redis acessível apenas internamente (sem ports no host) | D-14 / D-10 | Verificação de config de rede | `docker compose port redis 6379` — deve retornar vazio ou erro |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit) / manual for Docker runtime gates
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
