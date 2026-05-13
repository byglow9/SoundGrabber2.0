---
phase: 11
slug: som-da-semana-curated-sidebar-panel-featuring-underground-mu
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-12
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/test_security.py -x -q` |
| **Full suite command** | `pytest tests/test_security.py tests/test_frontend.py -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every backend/security task commit:** Run `pytest tests/test_security.py -x -q`
- **After every frontend/static task commit:** Run `pytest tests/test_frontend.py -x -q`
- **After every plan wave:** Run `pytest tests/test_security.py tests/test_frontend.py -q`
- **Before `$gsd-verify-work`:** Run `pytest tests/ -m "not e2e" -q`
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | D-01/D-06 | T-11-01 | `/yonkou` and `/yonkou/login` are rate-limited; unauthenticated `/yonkou` renders only the login panel; valid `ADMIN_PASSWORD` sets only signed HttpOnly session cookies | security | `pytest tests/test_security.py -x -q` | existing + W0 stubs | pending |
| 11-01-02 | 01 | 1 | D-03/D-06 | T-11-02 | `POST /featured` rejects missing/invalid operator session and invalid link payloads | security | `pytest tests/test_security.py -x -q` | existing + W0 stubs | pending |
| 11-01-03 | 01 | 1 | D-01/D-06 | T-11-03 | Redis outage falls back gracefully to JSON storage for featured content | security/integration | `pytest tests/test_security.py -x -q` | existing + W0 stubs | pending |
| 11-01-04 | 01 | 1 | D-02/D-04/D-05 | — | Public page has no visible `/yonkou` link, renders no sidebar when empty, and renders up to 3 safe external links when content exists | frontend/static | `pytest tests/test_frontend.py -x -q` | existing + W0 stubs | pending |
| 11-02-01 | 02 | 2 | D-01/D-03/D-06 | T-11-01/T-11-02 | FastAPI routes, Pydantic models, signed cookie helpers, Redis JSON storage, and fallback path satisfy Wave 1 security tests | security | `pytest tests/test_security.py -x -q` | existing | pending |
| 11-03-01 | 03 | 2 | D-02/D-04/D-05 | — | `static/index.html`, `static/app.js`, and `static/style.css` satisfy sidebar/UI tests without flexbox/grid/CSS variables | frontend/static | `pytest tests/test_frontend.py -x -q` | existing | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_security.py` — add `test_featured_get_rate_limit`, `test_yonkou_panel_rate_limit`, `test_yonkou_panel_requires_no_public_link`, `test_yonkou_login_rate_limit`, `test_post_featured_requires_operator_session`, `test_post_featured_validates_links`, `test_featured_redis_fallback`.
- [ ] `tests/test_frontend.py` — add sidebar tests for no public `/yonkou` link, empty/non-empty rendering behavior, link attributes, and forbidden CSS preservation.
- [ ] `requirements.txt` — add `itsdangerous==2.2.0` only if the implementation uses the recommended serializer.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator knows the hidden route | D-01e | The route is intentionally not linked from the public UI | Visit `/yonkou` directly in a browser and confirm the login panel renders. |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-12
