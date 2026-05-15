---
phase: 15
slug: cloudflare-tunnel
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-15
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for Cloudflare Tunnel exposure.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 for local static checks; manual browser gates for tunnel/E2E |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/test_deploy_sh.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~2s for quick checks; manual tunnel/E2E gates vary |

---

## Sampling Rate

- **After every docs/checklist task commit:** Run `pytest tests/test_deploy_sh.py -x -q` if related files changed, otherwise run source/grep acceptance criteria.
- **After every plan wave:** Run the plan-level verification commands for that wave.
- **Before `$gsd-verify-work`:** Public `/health` must pass and 3 frontend E2E downloads must be approved by the operator.
- **Max feedback latency:** ~2 seconds for static checks; manual gates are intentionally human-confirmed.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | TUNNEL-01 | T-15-01 | Compose is healthy before public exposure | CLI/manual | `sudo docker compose ps && curl -i http://localhost:8000/health` | N/A | ⬜ pending |
| 15-01-02 | 01 | 1 | TUNNEL-01 | T-15-02 | Admin credentials are not defaults before `/yonkou` is public | shell/manual | `grep -E "^(ADMIN_PASSWORD|ADMIN_SESSION_SECRET)=" .env` with human review | N/A | ⬜ pending |
| 15-01-03 | 01 | 1 | TUNNEL-01 | T-15-03 | `cloudflared` installed and quick tunnel started to localhost origin | CLI/manual | `cloudflared --version` and `cloudflared tunnel --url http://localhost:8000` | N/A | ⬜ pending |
| 15-02-01 | 02 | 2 | TUNNEL-01 | T-15-04 | Public tunnel routes to local app health endpoint | CLI/manual | `curl -i https://<trycloudflare-url>/health` | N/A | ⬜ pending |
| 15-02-02 | 02 | 2 | TUNNEL-02 | T-15-05 | Public frontend supports 3 complete beat downloads | browser/manual | Browser E2E through `https://<trycloudflare-url>/` | N/A | ⬜ pending |
| 15-02-03 | 02 | 2 | TUNNEL-02 | T-15-06 | Operator understands tunnel remains active until stopped | manual | final acknowledgement in SUMMARY.md | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers the phase requirements. No RED test stub is needed because the core deliverable is operational exposure and manual frontend E2E validation.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Install `cloudflared` on notebook | TUNNEL-01 | Host package install requires operator permission and sudo | Follow official APT commands, then run `cloudflared --version` |
| Quick tunnel public URL generation | TUNNEL-01 | URL is printed by a long-running foreground process | Run `cloudflared tunnel --url http://localhost:8000`, copy `https://*.trycloudflare.com` |
| Public frontend download flow | TUNNEL-02 | Requires browser interaction and live YouTube/cookies | Open public URL, submit 3 beat links, verify WAV download/BPM/key for each |
| Tunnel persistence warning | TUNNEL-02 | Operator controls when to stop the process | Confirm final output states `/yonkou` remains public while tunnel is active and how to stop it |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or manual gate dependencies
- [x] Sampling continuity: no 3 consecutive tasks without verification gates
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s for automated checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-15
