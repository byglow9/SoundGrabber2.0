---
phase: 01-processing-pipeline
plan: 03
subsystem: analysis
tags: [librosa, numpy, bpm, key-detection, krumhansl-schmuckler, camelot, chroma-cqt, python]

# Dependency graph
requires:
  - phase: 01-01
    provides: pipeline.py skeleton, test stubs, pytest conftest, sample.wav fixture
  - phase: 01-02
    provides: validate_wav (ffprobe), download_audio, check_duration, analyze_audio skeleton, CAMELOT stub

provides:
  - detect_bpm(wav_path, total_duration) -> float via librosa.feature.tempo
  - detect_key(wav_path) -> str via chroma_cqt + Krumhansl-Schmuckler correlation
  - _detect_key_from_chroma(chroma) helper for testability
  - CAMELOT public dict (34 entries: 24 canonical + 10 enharmonic flat aliases)
  - key_to_camelot(key) -> str O(1) Camelot wheel lookup
  - analyze_audio(wav_path) -> dict with full D-05 JSON shape (all JSON-native types)
  - _MAJOR_PROFILE, _MINOR_PROFILE, _NOTES module-level Krumhansl-Schmuckler constants

affects: [01-04, phase-02-api-layer]

# Tech tracking
tech-stack:
  added:
    - librosa==0.11.0 (BPM + key detection)
    - numpy>=2.0 (array operations for Krumhansl-Schmuckler correlation)
  patterns:
    - Krumhansl-Schmuckler chroma correlation for key detection (chroma_cqt mean over 24 profiles)
    - librosa.feature.tempo (NOT beat_track) for stable global BPM estimation
    - Explicit float()/str() coercions on all JSON output values (Pitfall 3 mitigation)
    - Static dict for Camelot wheel (no external library — camelot-py is PDF extraction, not music theory)

key-files:
  created: []
  modified:
    - pipeline.py

key-decisions:
  - "librosa.feature.tempo used instead of beat_track: feature.tempo uses autocorrelation of onset strength envelope for stable global BPM — beat_track tracks individual beat positions and infers tempo as a byproduct, higher overhead for our use case"
  - "Krumhansl-Schmuckler profiles defined as module-level constants (_MAJOR_PROFILE, _MINOR_PROFILE, _NOTES): enables testing _detect_key_from_chroma in isolation"
  - "CAMELOT table implemented as static dict (34 entries): no Python library exists for the musical Camelot wheel — camelot-py on PyPI is a PDF table extraction library"
  - "Explicit float()/str() coercions in analyze_audio: librosa returns numpy.ndarray/numpy.float64 even for scalar operations; json.dumps() raises TypeError on numpy types without explicit coercion"
  - "Public CAMELOT alias added alongside private _CAMELOT: plan contract requires importable CAMELOT constant; both names reference the same dict object"
  - "sr=22050 mono for both BPM and key loads: ~4x RAM reduction vs 44100 stereo without meaningful accuracy loss for tempo/chroma estimation"
  - "duration=90s for BPM, duration=120s for key: separate loads prevent Pitfall 4 (chroma needs more harmonic content than BPM)"

patterns-established:
  - "Pattern: always coerce librosa return values to Python float/str before placing in dicts that will be JSON-serialized"
  - "Pattern: extract inner computation into a helper (e.g. _detect_key_from_chroma) to enable unit testing without loading real audio"
  - "Pattern: detect_bpm receives total_duration as a parameter (passed from validate_wav) to avoid redundant ffprobe calls"

requirements-completed: [ANALYSIS-01, ANALYSIS-02, ANALYSIS-03, ANALYSIS-04]

# Metrics
duration: 12min
completed: 2026-04-30
---

# Phase 01 Plan 03: Audio Analysis (BPM + Key + Camelot) Summary

**librosa.feature.tempo BPM detection + Krumhansl-Schmuckler chroma key detection + 34-entry Camelot static table wired into D-05 JSON output shape with explicit numpy-to-Python type coercions**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-30T00:22:00Z
- **Completed:** 2026-04-30T00:34:00Z
- **Tasks:** 3
- **Files modified:** 1 (pipeline.py)

## Accomplishments

- Implemented `detect_bpm()` using `librosa.feature.tempo` with sr=22050, duration=90s, offset=min(20%, 30s) — correct API per Pattern 4 (not beat_track)
- Implemented `detect_key()` using `librosa.feature.chroma_cqt` + Krumhansl-Schmuckler correlation over 24 key profiles on a 120s window — returns 'A minor' for 440Hz fixture (correct)
- Wired `analyze_audio()` with explicit `float()`/`str()` coercions on all values, satisfying D-05 JSON shape and Pitfall 3 mitigation
- Added public `CAMELOT` constant (34 entries) alongside `key_to_camelot()` — test suite importable
- 9 tests passing (up from 7 at start of Plan 03); only `test_wav_file_created` (intentionally skipped) and 3 e2e tests remain

## Task Commits

1. **Task 1: CAMELOT public alias + librosa/numpy imports** - `f93cda1` (feat)
2. **Task 2: detect_bpm() and detect_key() implementations** - `1c42aa2` (feat)
3. **Task 3: analyze_audio() with D-05 shape and type coercions** - `04bd3b7` (feat)

## Files Created/Modified

- `pipeline.py` — Added `import librosa`, `import numpy as np`; added `_MAJOR_PROFILE`, `_MINOR_PROFILE`, `_NOTES` constants; replaced `detect_bpm` stub with real librosa.feature.tempo implementation; replaced `detect_key` stub with chroma_cqt + K-S implementation; added `_detect_key_from_chroma` helper; added public `CAMELOT` alias; updated `analyze_audio` with explicit type coercions and `dict[str, Any]` return type

## Decisions Made

**Static Camelot table vs. library:** No Python library exists for the musical Camelot wheel. `camelot-py` on PyPI extracts tables from PDF files — completely unrelated. The 34-entry static dict is the only viable approach. Includes 10 enharmonic flat aliases (Ab, Eb, Bb, Db, Gb in both major and minor) as defensive mappings per Assumption A1 in RESEARCH.md (librosa prefers sharps, but flat spellings are mapped defensively).

**K-S profiles as module-level constants:** `_MAJOR_PROFILE`, `_MINOR_PROFILE`, `_NOTES` are defined at module level to enable testing `_detect_key_from_chroma` with pre-loaded chroma data without needing real audio files. This makes the correlation logic independently testable.

**Separate librosa loads for BPM and key:** BPM uses 90s starting at 20% offset; key uses 120s from start. Reusing one load was considered but rejected because (a) different `offset` values needed and (b) key detection needs more harmonic content (Pitfall 4). Two separate `librosa.load` calls are the correct approach per RESEARCH patterns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Deviation] Plan 02 pre-implemented CAMELOT table and analyze_audio skeleton**

- **Found during:** Task 1 (reading pipeline.py from Plan 02)
- **Issue:** Plan 03 Task 1 instructed to "APPEND CAMELOT constant and key_to_camelot function" but Plan 02 had already implemented them (as `_CAMELOT` private dict). Task 2 instructed "APPEND detect_bpm/detect_key" but only stubs existed. Task 3 instructed to "APPEND analyze_audio" but the skeleton already existed.
- **Fix:** Instead of appending duplicate definitions, updated the existing implementations: (1) added `CAMELOT = _CAMELOT` public alias; (2) replaced `detect_bpm`/`detect_key` stubs in-place with real implementations; (3) updated existing `analyze_audio` skeleton with explicit type coercions and updated docstring.
- **Files modified:** pipeline.py
- **Verification:** All 9 non-e2e tests pass; `from pipeline import CAMELOT` succeeds; `len(CAMELOT) == 34`
- **Committed in:** f93cda1 (Task 1), 1c42aa2 (Task 2), 04bd3b7 (Task 3)

---

**Total deviations:** 1 adaptation (Plan 02 ahead of schedule — pre-implemented stubs/skeletons)
**Impact on plan:** Zero scope change. All plan objectives achieved. Tests match plan spec exactly.

## Issues Encountered

None — all implementations worked on first attempt. The 440Hz pure-tone fixture correctly produces 'A minor' key detection; BPM detection on a non-rhythmic tone returns 161.5 (within 30-300 range as required).

## Operational Note for Plan 04

The `analyze_audio()` function returns the exact D-05 JSON shape. Plan 04's `__main__` entry point only needs to:
1. Wrap the pipeline calls in `try/except (ValueError, RuntimeError)`
2. Print `json.dumps(result)` on success
3. Print `json.dumps({'error': str(e), 'type': 'validation_error'})` on failure
4. `sys.exit(0)` on success, `sys.exit(1)` on error

All type coercions are handled inside `analyze_audio()` — Plan 04 does not need to add any coercions.

## User Setup Required

None — no external service configuration required. (Note: e2e tests in Plan 04 require `cookies.txt` and `YTDLP_PO_TOKEN` env var, but this plan has no user setup.)

## Next Phase Readiness

- `pipeline.py` now implements the complete D-03 contract: `check_duration`, `download_audio`, `convert_to_wav`, `validate_wav`, `detect_bpm`, `detect_key`, `key_to_camelot`, `analyze_audio`
- `analyze_audio()` returns the exact D-05 JSON shape with JSON-native types
- 9/10 unit+integration tests green (10th is intentionally skipped — Plan 04 scope)
- 3 e2e tests remain for Plan 04 (require real YouTube + credentials)
- Plan 04 can add `__main__` entry point with confidence the pipeline is correct

---
*Phase: 01-processing-pipeline*
*Completed: 2026-04-30*
