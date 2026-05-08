---
phase: 4
plan: 4
subsystem: frontend-integration
tags: [fastapi, staticfiles, static-serving, frontend, integration]
dependency_graph:
  requires: [04-02, 04-03]
  provides: [GET /, GET /static/app.js, full-browser-workflow]
  affects: [api/main.py]
tech_stack:
  added: [fastapi.staticfiles.StaticFiles]
  patterns: [FileResponse for index.html, StaticFiles mount after API routes]
key_files:
  modified:
    - api/main.py
decisions:
  - "StaticFiles import added adjacent to existing FastAPI response imports"
  - "STATIC_DIR defined as Path(__file__).parent.parent / 'static' — relative to api/main.py"
  - "serve_index() route and app.mount() placed after all existing API routes to preserve GET /jobs/* and GET /files/* priority"
  - "app.mount placed last — after serve_index — to prevent shadowing GET /"
metrics:
  duration: 5min
  completed: "2026-05-08"
  tasks_completed: 1
  tasks_total: 2
  files_modified: 1
---

# Phase 4 Plan 4: FastAPI Static Files Integration Summary

**One-liner:** FastAPI serve_index() + StaticFiles mount wired to static/index.html and static/app.js — all 4 frontend tests GREEN, no API regression.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add GET / and StaticFiles mount to api/main.py | 34b11cf | api/main.py |

---

## What Was Built

Added two targeted additions to `api/main.py` (no existing code modified — append only):

1. **Import:** `from fastapi.staticfiles import StaticFiles` added to the FastAPI imports block.

2. **Static block** appended after `download_file()` (last existing route):
   - `STATIC_DIR = Path(__file__).parent.parent / "static"` — resolves to the `static/` directory at project root.
   - `@app.get("/") def serve_index()` — returns `FileResponse(str(STATIC_DIR / "index.html"))`.
   - `app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")` — placed after `serve_index` to avoid shadowing `GET /`.

**Route priority verified:** FastAPI 0.136.1 + Starlette 1.0.0 — routes defined before the StaticFiles mount take precedence. `GET /jobs/{id}` and `GET /files/{id}` are unaffected.

**RuntimeError prevention:** `static/index.html` and `static/app.js` were created by Plans 02 and 03 (Wave 2-3) before this Plan (Wave 4) adds the mount — Starlette's startup check passes cleanly.

---

## Verification Results

```
tests/test_frontend.py::test_index_html_served           PASSED
tests/test_frontend.py::test_app_js_served               PASSED
tests/test_frontend.py::test_html_required_ids_present   PASSED
tests/test_frontend.py::test_wav_size_formula            PASSED

Full suite (not e2e): 34 passed, 1 skipped, 0 failed
python -c "from api.main import app; print('import OK')" → import OK
```

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Checkpoint: Human Verify (Pending)

The plan includes a `type="checkpoint:human-verify"` task after Task 1. This checkpoint requires manual browser verification:

1. Start `uvicorn api.main:app --reload --port 8000` (with Celery + Redis)
2. Open http://localhost:8000/ — expect "SoundGrabber" title + URL input
3. Verify 15-minute hint is visible
4. Submit a YouTube URL and verify the full polling → result flow
5. Click "Baixar WAV" — verify browser saves `soundgrabber_XXXXXXXX.wav`
6. Submit an invalid URL — verify inline validation error
7. Verify `curl POST /jobs` returns JSON (not HTML)

This checkpoint requires user action and a running Celery worker + Redis stack.

---

## Threat Surface Scan

No new security-relevant surface introduced beyond what is in the plan's threat model.

| Threat | Disposition | Notes |
|--------|-------------|-------|
| T-04-07: StaticFiles mount order | Mitigated | app.mount() placed after all API routes |
| T-04-08: StaticFiles startup RuntimeError | Mitigated | static/ directory exists (Plans 02-03 prerequisite) |
| T-04-09: STATIC_DIR path disclosure | Accepted | Path relative to api/main.py, only serves static/ |

---

## Known Stubs

None. `static/index.html` and `static/app.js` are fully wired. The GET / and /static/app.js routes serve real files.

---

## Self-Check

## Self-Check: PASSED

- FOUND: api/main.py
- FOUND commit: 34b11cf (feat(04-04): add GET / and StaticFiles mount to api/main.py)
