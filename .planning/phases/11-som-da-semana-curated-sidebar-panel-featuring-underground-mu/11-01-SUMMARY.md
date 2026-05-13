---
phase: 11-som-da-semana-curated-sidebar-panel-featuring-underground-mu
plan: 01
subsystem: testing
tags: [pytest, security, frontend, red-tests]
requires: []
provides:
  - Phase 11 backend/security RED contract
  - Phase 11 public sidebar/static RED contract
affects: [api, static-ui, security-tests]
tech-stack:
  added: []
  patterns: [pytest TestClient route contract, source assertions for vanilla JS/CSS]
key-files:
  created: []
  modified: [tests/test_security.py, tests/test_frontend.py, tests/conftest.py]
key-decisions:
  - "Authenticated featured tests use the real /yonkou/login flow instead of a fake cookie."
patterns-established:
  - "Operator test defaults are set before api.main import in tests/conftest.py."
requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06]
duration: 35 min
completed: 2026-05-13
---

# Phase 11 Plan 01: Validation Contract Summary

**RED pytest contract for Som da Semana operator auth, featured storage, public sidebar rendering, and Y2K CSS constraints**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-13T11:57:00Z
- **Completed:** 2026-05-13T12:32:36Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Confirmed the Phase 11 security and frontend tests exist with the required names.
- Hardened authenticated backend tests to obtain a real `sg_admin` session through `/yonkou/login`.
- Added operator env defaults before `api.main` import so future backend tests read stable settings.

## Task Commits

1. **Task 1: Add Phase 11 security RED tests** - `cda5c3d` (test)
2. **Task 2: Add Phase 11 frontend RED tests** - `a69b264` (pre-existing test commit containing the frontend RED contract)

## Files Created/Modified
- `tests/test_security.py` - Phase 11 route, auth, validation, rate-limit, and Redis fallback tests.
- `tests/test_frontend.py` - Phase 11 sidebar/source contract tests.
- `tests/conftest.py` - Test env defaults for operator auth settings.

## Decisions Made
Use real login flow in authenticated tests so the backend can reject forged cookies without breaking the validation suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced fake authenticated cookie in tests**
- **Found during:** Task 1
- **Issue:** Tests used `sg_admin=signed-test-session`, which would force production code to accept a forged cookie.
- **Fix:** Added `_login_operator()` helper and test env defaults.
- **Files modified:** `tests/test_security.py`, `tests/conftest.py`
- **Verification:** Targeted Phase 11 tests fail RED on missing routes/DOM, not on import or syntax.
- **Committed in:** `cda5c3d`

---

**Total deviations:** 1 auto-fixed (Rule 3).
**Impact on plan:** Prevents an insecure implementation path while preserving the RED contract.

## Issues Encountered
Initial `pytest` script had a stale shebang; tests were run with `.venv/bin/python -m pytest`. Redis on `localhost:6380` was started for the test fixture.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Ready for `11-02`: backend routes can be implemented against the RED security contract.

---
*Phase: 11-som-da-semana-curated-sidebar-panel-featuring-underground-mu*
*Completed: 2026-05-13*
