# Project Research Summary

**Project:** SoundGrabber — milestone v1.1 (BPM/Key/Tuning Precision Analysis)
**Domain:** YouTube audio downloader + music analysis web utility for underground producers
**Researched:** 2026-05-09
**Confidence:** HIGH for Essentia integration approach; MEDIUM for tuning accuracy on real-world beats

---

## Executive Summary

The v1.1 milestone replaces librosa BPM and key detection with Essentia — the same C++/Python library that powers Tunebat. This is not an approximation of Tunebat accuracy: Tunebat IS Essentia with a web frontend (confirmed from Tunebat's own analyzer page, which references essentia.js from the Music Technology Group at UPF). Using `pip install essentia` gives SoundGrabber the identical algorithm stack — `RhythmExtractor2013(method="multifeature")` for BPM and `KeyExtractor(profileType="edma")` for key detection on electronic/hip-hop material. No proprietary model or paid tier is required to match Tunebat-level accuracy.

Tuning detection (A = X Hz) is implemented using two existing librosa functions already in the venv: `librosa.estimate_tuning()` followed by `librosa.tuning_to_A4()`. No new library is required. The critical execution constraint is that tuning must run first, and the resulting `tuning_hz` value must be passed into `KeyExtractor` so that HPCP bins align to the audio's actual concert pitch rather than assuming A=440 Hz. This matters for beats mastered at A=432 Hz.

The main integration risks are technical and concrete: Essentia returns `numpy.float32` throughout, which breaks Celery's JSON serializer and must be wrapped with `float()` at every extraction point; Essentia returns key and scale as separate strings, which silently breaks the existing `key_to_camelot()` lookup if not assembled into `"F# minor"` format before the call; tuning detection on percussive-only beats returns meaningless values and must be gated behind HPSS harmonic energy checking. All three failure modes are silent — no exceptions, wrong output.

---

## Key Findings

### Recommended Stack

The v1.1 additions require one new library (Essentia) on top of the existing stack. Essentia 2.1b6.dev1389 ships a pre-built manylinux wheel for Python 3.11 Linux x86_64 (13.8 MB), so no C++ compilation is needed. It coexists with librosa without dependency conflicts — both use numpy. librosa is retained for tuning detection (two one-liner function calls already in the library). The existing yt-dlp + FFmpeg + FastAPI + Celery stack is unchanged.

**Core technologies for v1.1:**
- `essentia==2.1b6.dev1389`: BPM + key detection — same algorithms as Tunebat, manylinux wheel confirmed on Python 3.11
- `essentia.standard.RhythmExtractor2013(method="multifeature")`: BPM — multifeature mode is slower but resistant to half/double-tempo octave errors on trap
- `essentia.standard.KeyExtractor(profileType="edma")`: key detection — edma profile extracted from EDM corpus, outperforms generic profiles on electronic music
- `librosa.estimate_tuning()` + `librosa.tuning_to_A4()`: tuning — no new dependency, confirmed in librosa 0.10.2+ and 0.11.0
- `essentia.standard.MonoLoader(sampleRate=44100)`: Essentia audio loading — must use 44100 Hz, not the existing 22050 Hz librosa load

**Libraries evaluated and rejected for v1.1:**
- `madmom`: Python < 3.10 on PyPI; unmaintained since 2018
- `aubio`: no wheels since 2019; requires C library; unmaintained
- `beat_this` (CPJKU): requires PyTorch + torchaudio + einops — 2-3 GB chain for marginal gain
- `essentia-tensorflow`: TempoCNN requires TensorFlow; RhythmExtractor2013 does not; no benefit here
- `CREPE`: monophonic pitch tracker, cannot estimate concert pitch for polyphonic audio

### Expected Features

**Must have for v1.1 (table stakes upgraded by this milestone):**
- More accurate BPM — producers have used Tunebat; divergent values erode trust immediately
- More accurate key / Camelot — wrong key costs producers time on every chord or sample decision
- Tuning frequency display "A = X Hz" — producers layering samples need this; a 432 Hz beat in a 440 Hz project is ~32 cents flat

**Should have (differentiators available from Essentia outputs at no extra cost):**
- BPM confidence indicator — RhythmExtractor2013 multifeature already returns `beats_confidence`; surfacing it builds trust
- Key detection strength caveat — KeyExtractor returns `strength` (0–1); show a warning only when strength < 0.25
- Tuning displayed inline on existing result card — no new UI component needed, one additional field

**Defer to v2+:**
- TempoCNN (deep learning BPM) — adds 50MB+ model weight and TensorFlow; only if RhythmExtractor2013 proves insufficient in testing
- BPM histogram display (multiple tempo candidates) — engineering complexity, minimal producer value
- Essentia TuningFrequency algorithm (spectral peaks pipeline) — librosa one-liner sufficient for v1.1

**Anti-features (do not implement):**
- Tuning as binary "432 Hz mode / 440 Hz mode" — detection is continuous; rounding to presets is misleading
- Showing raw key strength as decimal (0.847) — meaningless to producers; use as internal threshold only
- Pitch-shifting / tuning correction — analysis tool, not mastering tool

### Architecture Approach

The v1.1 changes are contained entirely within the Celery analysis task. No API contract changes, no frontend routing changes. The task flow is:

1. FFmpeg WAV output (unchanged)
2. Load audio with librosa at `sr=None` for tuning
3. HPSS harmonic energy gate → `librosa.estimate_tuning()` → `librosa.tuning_to_A4()` → `tuning_hz` (float or None)
4. Load audio with `essentia.standard.MonoLoader(sampleRate=44100)` for Essentia
5. `RhythmExtractor2013(method="multifeature")` → `bpm`, `beats_confidence`
6. `KeyExtractor(profileType="edma", tuningFrequency=tuning_hz or 440.0)` → `key`, `scale`, `strength`
7. Assemble `f"{key} {scale}"` → `key_to_camelot()` → `camelot`
8. Return `{bpm: float, key: str, camelot: str, key_confidence: float, tuning_hz: float|None}` — all Python native types

**Major components affected:**
1. `pipeline.py` / `analyze_audio()` — replace algorithm calls, add tuning logic, add HPSS gate, wrap all outputs in `float()`
2. `test_pipeline.py` — add `tuning_hz` to every `required` set; add JSON round-trip type assertion; add integration test asserting `camelot != "?"`
3. `frontend result card` — add `tuning_hz` display; guard `null` with `data.tuning_hz != null ? ... : "N/A"`
4. `requirements.txt` — add `essentia>=2.1b6.dev1000`; verify `numba>=0.60` for numpy 2.x compatibility

### Critical Pitfalls

1. **Essentia returns numpy float32 — Celery JSON serialization fails silently** — wrap every Essentia output with `float()` at the point of extraction; add `json.dumps(result)` to the test suite asserting all values are Python native types

2. **KeyExtractor returns key and scale separately — key_to_camelot() silently returns "?"** — always assemble `f"{essentia_key} {essentia_scale}"` before calling `key_to_camelot()`; the existing `test_camelot_mapping` does not catch this because it bypasses `analyze_audio()`

3. **Tuning detection on percussive-only beats returns noise** — run HPSS before tuning; if `harmonic_energy / total_energy < 0.2`, set `tuning_hz = None`; cross-validate result is in `[400, 480]` Hz range

4. **Essentia expects 44100 Hz — existing librosa load is 22050 Hz** — use `essentia.standard.MonoLoader(sampleRate=44100)` for all Essentia analysis paths; do not feed librosa-loaded audio into Essentia algorithms

5. **ABI mismatch if Essentia wheel was compiled against numpy 1.x** — immediately after `pip install essentia`, run `python -c "import essentia.standard; print('OK')"` before writing any pipeline code

6. **tuning_hz field not in test required sets — regression invisible to CI** — add `"tuning_hz"` to the `required` set in `test_json_output_shape` and `_run_pipeline_e2e`

---

## Implications for Roadmap

This milestone is a contained swap of the analysis engine inside an existing Celery task. The roadmap for v1.1 is one implementation unit with a fixed dependency order.

### Step 1: Install and verify Essentia
**Rationale:** ABI failures and dependency conflicts must be resolved before writing any pipeline code.
**Delivers:** Confirmed working `import essentia.standard` in the venv; updated `requirements.txt`
**Avoids:** PITFALL M1 (ABI mismatch), PITFALL M10 (numba conflict)

### Step 2: Implement tuning detection with HPSS gate
**Rationale:** Tuning must be computed first — it is an input to KeyExtractor.
**Delivers:** `tuning_hz: float | None` with percussive-track protection
**Avoids:** PITFALL M5 (percussive tracks return meaningless tuning)

### Step 3: Replace BPM with Essentia RhythmExtractor2013
**Rationale:** Independent of key; multifeature mode resolves half/double-tempo errors.
**Delivers:** `bpm: float`, `beats_confidence: float` — both wrapped in `float()`
**Avoids:** PITFALL M2 (float32 serialization), PITFALL M4 (degara method returns confidence=0)

### Step 4: Replace key with Essentia KeyExtractor
**Rationale:** Depends on `tuning_hz` from Step 2; edma profile is EDM-optimized.
**Delivers:** `key: str` (assembled "F# minor" format), `camelot: str`, `key_confidence: float`
**Avoids:** PITFALL M3 (key+scale assembly), PITFALL M8 (sample rate mismatch)

### Step 5: Update tests and frontend
**Rationale:** Three silent failure modes are only caught by end-to-end pipeline tests with real audio.
**Delivers:** Updated test required sets, JSON type assertion, null-safe frontend display
**Avoids:** PITFALL M6 (tuning_hz not in test required sets), PITFALL M7 (key algorithm regression invisible in CI)

### Phase Ordering Rationale

- Installation verification before code: ABI failure must be discovered before writing code that depends on the import
- Tuning before key: `tuning_hz` is an input parameter to `KeyExtractor`; reversing the order produces HPCP bins misaligned to concert pitch
- BPM and key are independent after tuning: can proceed in parallel if multiple devs available
- Tests and frontend last: the output contract cannot be specified until the pipeline implementation is stable

### Research Flags

Standard patterns (no additional research needed):
- **Essentia RhythmExtractor2013 multifeature:** official docs are complete; API is stable
- **librosa tuning detection:** two confirmed functions in official docs, validated in librosa 0.10.2+
- **Essentia KeyExtractor with edma profile:** official docs + MTG issue #744 confirm edma for EDM

Needs validation during implementation:
- **HPSS harmonic energy threshold (0.2):** judgment call from research, not a published standard; test on 10-20 real trap beats before treating as fixed
- **Camelot table completeness for Essentia notation:** Essentia uses mixed Bb/Eb/Ab flats and C#/F# sharps; verify the existing lookup table covers all 12 Essentia key name strings as exact matches before assuming it does

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Essentia install on Python 3.11 Linux | HIGH | manylinux cp311 wheel confirmed on PyPI |
| RhythmExtractor2013 algorithm choice | HIGH | Essentia's own recommendation for batch processing; official tutorial |
| KeyExtractor with edma profile | HIGH | MTG issue #744 + official docs confirm edma for EDM |
| Tunebat = Essentia (confirmed) | HIGH | Verified from Tunebat's own analyzer page referencing essentia.js/MTG |
| librosa tuning detection functions | HIGH | Both functions confirmed in official librosa 0.11.0 docs |
| float32 serialization pitfall | HIGH | Confirmed in numpy docs and Kombu/Celery issue tracker |
| Execution order (tuning before key) | HIGH | Logical dependency; KeyExtractor tuningFrequency parameter |
| HPSS gate threshold for tuning | MEDIUM | 0.2 ratio is reasonable but empirically unvalidated |
| Accuracy improvement on real beats | MEDIUM | Community consensus "better for EDM" — no controlled study found |
| Camelot table completeness | MEDIUM | Mixed notation should be covered but must be verified in code |

**Overall confidence:** HIGH for the integration approach; MEDIUM for accuracy claims on production audio

### Gaps to Address During Implementation

- **HPSS threshold validation:** run tuning on 15-20 diverse real beats; confirm 0.2 threshold correctly gates percussive tracks to None while passing melodic tracks
- **Camelot table coverage audit:** enumerate all 12 key names from Essentia key.cpp and verify each is an exact string match in `key_to_camelot()` — Bb, Eb, Ab (flats) and C#, F# (sharps)
- **numba version check:** after installing Essentia, confirm `numba >= 0.60` is present; if not, pin explicitly to prevent silent numpy downgrade
- **Golden file baseline:** capture librosa key output on 5 real WAVs before removing it; compare against Essentia edma output; only switch if edma matches or improves

---

## Sources

### Primary (HIGH confidence — official documentation)
- [Essentia RhythmExtractor2013 reference](https://essentia.upf.edu/reference/std_RhythmExtractor2013.html)
- [Essentia beat detection tutorial](https://essentia.upf.edu/tutorial_rhythm_beatdetection.html)
- [Essentia KeyExtractor algorithm reference](https://essentia.upf.edu/reference/std_KeyExtractor.html)
- [Essentia HPCP Key Detection Tutorial](https://essentia.upf.edu/tutorial_tonal_hpcpkeyscale.html)
- [Essentia TuningFrequency streaming reference](https://essentia.upf.edu/reference/streaming_TuningFrequency.html)
- [Essentia installing docs + PyPI wheels](https://essentia.upf.edu/installing.html)
- [Tunebat Analyzer — essentia.js confirmation](https://tunebat.com/Analyzer)
- [essentia.js project page — MTG/UPF](https://mtg.github.io/essentia.js/)
- [librosa.estimate_tuning docs](https://librosa.org/doc/main/generated/librosa.estimate_tuning.html)
- [librosa.tuning_to_A4 docs](https://librosa.org/doc/main/generated/librosa.tuning_to_A4.html)
- [NumPy 2.0 ABI break — downstream package guide](https://numpy.org/doc/2.0/dev/depending_on_numpy.html)
- [Essentia Key algorithm source — key.cpp](https://github.com/MTG/essentia/blob/master/src/algorithms/tonal/key.cpp)

### Secondary (MEDIUM confidence — community/practitioner sources)
- [Essentia edma/edmm profile — MTG issue #744](https://github.com/MTG/essentia/issues/744)
- [BPM Finder: 300-Track Benchmark vs Tunebat](https://bpm-finder.net/posts/tunebat-bpm-alternative)
- [StemSplit: BPM and Key Detection — production usage](https://stemsplit.io/blog/bpm-key-detection-feature)
- [Kombu JSON serializer — numpy types issue #1067](https://github.com/celery/kombu/issues/1067)
- [librosa numpy 2.0 compatibility — issue #1848](https://github.com/librosa/librosa/issues/1848)
- [numpy.float64 is JSON serializable but float32 is not](https://ellisvalentiner.com/post/numpyfloat64-is-json-serializable-but-numpyfloat32-is-not/)

### Tertiary (LOW confidence — single source or observation)
- [Tunebat free tier does not show tuning](https://tunebat.com/Analyzer) — observed without account; paid tier may differ

---
*Research completed: 2026-05-09*
*Milestone: v1.1 — BPM/Key/Tuning Precision Analysis*
*Ready for implementation: yes*
