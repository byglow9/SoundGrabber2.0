# Domain Pitfalls — SoundGrabber

**Domain:** YouTube audio downloader + BPM/key detection web app
**Researched:** 2026-04-29 (original) | Updated: 2026-05-09 (v1.1 milestone: precision analysis)
**Confidence:** HIGH for YouTube blocking, MEDIUM for audio analysis accuracy, HIGH for file handling/deployment, MEDIUM for Essentia integration specifics

---

## v1.1 Milestone Pitfalls — BPM/Key/Tuning Precision Analysis

These pitfalls are specific to the milestone that replaces/augments librosa with Essentia
and adds `tuning_hz` detection. They supplement (not replace) the original pitfalls below.

---

### PITFALL M1: Essentia Wheel ABI Mismatch With numpy>=2.0

**What goes wrong:**
The venv uses Python 3.12 and `numpy>=2.0` (currently 2.2.6 based on system state).
Essentia's pre-built wheels on PyPI are compiled against specific NumPy C ABI versions.
NumPy 2.0 introduced a major ABI break in June 2024 — any compiled C extension built
against NumPy 1.x that is installed into a NumPy 2.x environment will fail on import with:

```
RuntimeError: module compiled against ABI version 0x1000009 but this version of numpy is 0x2000000
```

or silently produce wrong numerical results in rare cases.

**Why it happens:**
NumPy changed its C API surface in 2.0. Packages compiled with the old ABI cannot
interoperate with the new ABI without recompilation. Essentia releases new dev wheels
frequently (latest: 2.1b6.dev1389, July 2025) and the PyPI page confirms wheels exist
for Python 3.9–3.13 on manylinux2014 x86-64. However, if the installed wheel was built
against numpy 1.x and your venv has numpy 2.x, the failure is immediate.

**Consequences:**
`import essentia` raises on startup. Celery workers crash at import time. Nothing runs.

**Prevention:**
1. After `pip install essentia`, immediately run:
   `python -c "import essentia; import essentia.standard; print('OK')"`.
   This surfaces the ABI error before any other code depends on it.
2. Pin to the most recent dev release explicitly rather than taking the default:
   `pip install essentia==2.1b6.dev1389` (latest as of July 2025). Newer wheels
   are more likely to be compiled against numpy 2.x.
3. If the import fails, pin numpy to `<2.0` as a fallback only — check first whether a
   newer essentia wheel resolves it. Pinning numpy down would require auditing librosa's
   numpy 2.x support (librosa 0.11.0 supports numpy 2.x — confirmed via librosa GitHub
   issue #1848, so downgrading numpy would not be needed if the essentia wheel is current).
4. Add an import smoke test to CI: `python -m pytest tests/ -k "import"` to catch ABI
   failures on every dependency change.

**Detection:** `pip install essentia && python -c "import essentia.standard"` failing
immediately after install with RuntimeError about ABI or with ImportError about shared
objects.

---

### PITFALL M2: Essentia Output Types Are Not JSON-Serializable by Default

**What goes wrong:**
Essentia algorithms return `essentia.array` objects, which are `numpy.ndarray` of
`dtype=float32`. When RhythmExtractor2013 returns `bpm` (a numpy float32) and you
place it into the `analyze_audio()` dict, Celery's JSON serializer raises:

```
TypeError: Object of type float32 is not JSON serializable
```

This error surfaces in the Celery task layer, not in pipeline.py directly. The existing
`analyze_audio()` contract explicitly states "all JSON-native types" — Pitfall 3 in the
existing docstring. Essentia makes this constraint harder to maintain because every single
output field must be explicitly converted.

**Why it happens:**
Unlike librosa which returns Python floats or numpy float64 (which json.dumps accepts),
Essentia returns numpy float32 scalars and numpy arrays throughout. `numpy.float32` is
not a Python `float` subclass — it is registered as `numpy.floating` and the standard
`json` module does not accept it.

**Specific affected fields:**
- `bpm` — RhythmExtractor2013 returns a numpy float32
- `tuning_hz` — TuningFrequency returns a numpy float32 (real output)
- `key_confidence` — KeyExtractor `strength` is a numpy float32
- Beat positions array (if ever passed to Celery) — essentia.array, never JSON-serializable

**Consequences:**
Celery task result silently fails to store in Redis. The frontend poll returns an error
envelope. The analyze_audio() unit test `test_json_output_shape` will catch this if it
runs `json.dumps(result)` — and it does (line 209 in test_pipeline.py). But if the
conversion is missed only for `tuning_hz`, the existing test may still pass because it
does not assert on `tuning_hz`.

**Prevention:**
1. Wrap every Essentia output at the point of extraction with explicit Python type
   conversion. Never pass raw Essentia/numpy output into the return dict:
   ```python
   bpm = float(rhythm_extractor(audio)[0])          # NOT: rhythm_extractor(...)[0]
   tuning_hz = float(tuning_extractor(...)[0])       # NOT: tuning_extractor(...)[0]
   key_strength = float(key_extractor(...)[2])       # NOT: key_extractor(...)[2]
   ```
2. After adding `tuning_hz` to `analyze_audio()`, add it to the `required` set in
   `test_json_output_shape` (line 211 in test_pipeline.py) so the JSON round-trip
   test covers the new field.
3. Add a dedicated unit test that calls `json.dumps(analyze_audio(...))` and checks
   every value type: `assert all(isinstance(v, (str, int, float, type(None))) for v in result.values())`.

---

### PITFALL M3: Essentia KeyExtractor Returns Key and Scale Separately — Camelot Mapping Will Silently Return "?"

**What goes wrong:**
The existing `key_to_camelot()` function expects a combined string like `"F# minor"` or
`"C major"`. Essentia's `KeyExtractor` returns `key` and `scale` as two separate strings:
`key = "F#"`, `scale = "minor"`. If you pass either the `key` string alone (`"F#"`) or
an Essentia-formatted string without assembly into the pipeline's format, `key_to_camelot()`
silently returns `"?"` (the fallback).

Additionally, Essentia's Key algorithm has a hardcoded mixed-notation output
(confirmed from source code `key.cpp`):
```c
const char* keyNames[] = { "A", "Bb", "B", "C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab" };
```

Essentia uses flats for `Bb`, `Eb`, `Ab` and sharps for `C#`, `F#`. The existing Camelot
table already covers `Ab minor`, `Eb minor`, `Bb minor`, `Ab major`, `Eb major`,
`Bb major` — so the mappings exist. But the assembly logic must be:
```python
key_str = f"{essentia_key} {essentia_scale}"  # e.g. "Bb minor", "C# major"
```

**Why it happens:**
Essentia's API design separates key name from scale/mode as two outputs. The existing
pipeline's Camelot table was designed around librosa's single-string output. The
interface mismatch is silent — no exception, just wrong Camelot codes.

**Consequences:**
All Camelot codes return `"?"`. Frontend displays `"?"` for every result. `test_camelot_mapping`
will still pass (it tests `key_to_camelot()` in isolation with manually passed strings, not
through `analyze_audio()`). The regression is invisible to current unit tests.

**Prevention:**
1. After calling Essentia's KeyExtractor, always assemble the combined string:
   `key = f"{essentia_key} {essentia_scale}"` before passing to `key_to_camelot()`.
2. Add a new integration test that calls the full `analyze_audio()` pipeline on a real
   WAV and asserts `result["camelot"] != "?"`. This covers the assembly step end-to-end.
3. The existing `test_camelot_mapping` is not sufficient — it bypasses `analyze_audio()`.
   A companion test that patches `detect_key` to return Essentia-style `("Bb", "minor")`
   and checks the camelot output should be added.

---

### PITFALL M4: Essentia RhythmExtractor2013 Returns BPM as a Float With Many Decimals — Rounding Contract Must Be Explicit

**What goes wrong:**
RhythmExtractor2013 returns raw BPM values like `139.98114013671875`. The existing
pipeline rounds to 1 decimal (`round(bpm, 1)`). Essentia's output is a numpy float32,
so the round() call succeeds, but the rounding may produce `140.0` or `140.0` depending
on float32 precision loss. This is not a bug, but the test `test_bpm_half_double_calculation`
patches `detect_bpm` to return `140.0` exactly — if the real function is called, the
rounding behavior must be explicitly documented and tested with a tolerance.

The more dangerous case: RhythmExtractor2013 with method `'degara'` returns
`beats_confidence = 0` always (by design — the degara method does not compute confidence).
If confidence is used downstream as a quality gate, degara silently always passes.

**Why it happens:**
Two method options exist in RhythmExtractor2013: `'multifeature'` (slower, accurate,
returns real confidence) and `'degara'` (faster, no confidence). The default is
`'multifeature'` in documentation examples but this must be explicitly set — the Python
API default may differ.

**Consequences:**
Using `'degara'` by mistake means `beats_confidence` is always 0, making confidence-
gated logic useless. Wrong method is silent — BPM values still come out.

**Prevention:**
1. Always explicitly specify `method='multifeature'` when constructing RhythmExtractor2013:
   ```python
   rhythm_extractor = essentia.standard.RhythmExtractor2013(method='multifeature')
   ```
2. Document in a comment adjacent to the call that `'degara'` returns confidence=0.
3. Add a test that verifies the returned confidence is > 0 when using a real WAV with
   clear rhythmic content (e.g., the existing `sample_wav_path` fixture).

---

### PITFALL M5: Tuning Detection Is Unreliable on Percussive-Only or Bass-Heavy Audio

**What goes wrong:**
Both `librosa.estimate_tuning()` and Essentia's `TuningFrequency` detect concert pitch
by analyzing spectral peaks in the harmonic content of the audio. For the SoundGrabber
use case (YouTube beats, often trap/hip-hop), the audio may be:
- Primarily percussive (kick, snare, hi-hats dominate — no tonal harmonic content)
- Heavily distorted or saturated bass (no clear fundamental to track)
- Pitched samples with chorus/vibrato effects (frequency wobble masks the pitch center)

In all these cases, `tuning_hz` will be returned as a float (e.g., `441.3 Hz`) with no
signal to the user that it is meaningless. There is no confidence metric for tuning
detection in either library's standard implementation.

**Why it happens:**
`librosa.estimate_tuning()` returns a value in [-0.5, 0.5] cents (fractions of a bin).
It uses `piptrack` (pitch tracking) internally, which detects pitches in every frame.
For percussive audio, pitches are detected from partials and noise, producing a
distribution of detected pitches that averages to approximately 0 (i.e., A=440 Hz).
The output looks confident but is noise.

Essentia's `TuningFrequency` takes spectral peak frequencies and magnitudes as input.
On a drum kit, spectral peaks exist (kick at ~60 Hz, snare at 200 Hz, etc.) but they
are percussive, not harmonic. The algorithm will compute a tuning estimate from these
peaks, but the result is meaningless.

The output range constraint for Essentia `TuningFrequency` is -35 to 65 cents. If the
true deviation is outside this range (unusual but possible for heavily pitch-shifted
YouTube content), the algorithm clips or returns a boundary value without warning.

**Consequences:**
The UI displays "A = 441 Hz" on a track that is pure drums, misleading the user.
Producers who know the track tune their samples to 441 Hz for nothing, wasting time.

**Prevention:**
1. Before reporting `tuning_hz`, compute a harmonic/percussive separation (HPSS) as
   already done in `detect_key()`. Only run tuning detection on the harmonic component.
   This is already a solved pattern in the codebase.
2. Compute a tuning confidence proxy: measure the energy ratio of the harmonic vs.
   percussive signal. If `harmonic_energy / total_energy < 0.2`, set
   `tuning_hz = None` and display "Tuning: N/A — insufficient harmonic content".
3. Cross-validate `tuning_hz` against a plausible range. Any result outside
   `[400, 480]` Hz is almost certainly noise — clamp and flag it.
4. Do not surface `tuning_hz` as a primary metric. Position it as a secondary/
   supplementary field with a tooltip explaining its limitations.

**Detection:** Run on 20 known-BPM trap beats that are drum-heavy. If > 50% return
values within 2 Hz of 440 Hz on tracks known to be tuned to 432 Hz or 444 Hz, the
algorithm is returning noise (coincidentally near 440 Hz for percussive content).

---

### PITFALL M6: `tuning_hz` Field Addition Breaks `test_json_output_shape` If Not Added to `required`

**What goes wrong:**
Adding `tuning_hz` to `analyze_audio()`'s return dict is an additive change, not a
breaking change — existing consumers reading known fields will still work. However:

1. The `test_json_output_shape` test (line 211 in test_pipeline.py) has a hardcoded
   `required` set. If `tuning_hz` is not added there, the test continues to pass but
   does not assert that tuning is present. A regression that accidentally drops `tuning_hz`
   from the return dict will be invisible.

2. The `_run_pipeline_e2e` function (line 261) also has a hardcoded `required` set.
   Same problem.

3. The frontend JavaScript accesses fields by name. If `tuning_hz` is `None` (for
   percussive tracks — see M5), the frontend must handle `null` gracefully. If it uses
   `result.tuning_hz.toFixed(1)` on a null value, it raises a TypeError in the browser.

**Why it happens:**
Test coverage for the output contract is by explicit enumeration, not by schema. Adding
a new field to the output contract requires updating every place that enumerates the
fields. This is a systemic test debt pattern.

**Consequences:**
- Silent test coverage gap: a future regression drops `tuning_hz` and CI stays green.
- Frontend TypeError if `tuning_hz` is `null` and JS does not guard for it.
- Celery task store/retrieve round-trip: if `tuning_hz = None` is stored in Redis,
  it deserializes to Python `None`. The frontend must check for `null` in the JSON.

**Prevention:**
1. Add `"tuning_hz"` to the `required` set in `test_json_output_shape` and `_run_pipeline_e2e`.
2. Add a type assertion: `assert isinstance(result.get("tuning_hz"), (float, type(None)))`.
3. In the frontend: `const tuning = data.tuning_hz != null ? data.tuning_hz.toFixed(1) + ' Hz' : 'N/A'`.
4. In `analyze_audio()`'s docstring, add `tuning_hz (float | None)` to the return
   description so the contract is explicit.

---

### PITFALL M7: Switching Key Algorithm Causes Silent Accuracy Regression With No Baseline

**What goes wrong:**
The existing `detect_key()` uses Krumhansl-Schmuckler correlation (librosa + manual
profile). Essentia's `KeyExtractor` uses a different algorithm with 16 profile options
(default: `bgate`). The `bgate` profile is Essentia's internal "beat-gate" profile
tuned for electronic music. Switching from Krumhansl to `bgate` may improve results on
some genres and regress on others, but there is currently no ground-truth test to detect
this regression.

The existing key detection test (`test_key_detection`) only checks:
- That the result starts with `"A "` for a 440 Hz pure tone fixture
- That `0.0 <= confidence <= 1.0`

It does not test key detection accuracy on real-world musical content or verify that
previously-correct results are still correct after the algorithm swap.

**Why it happens:**
The `sample_wav_path` fixture is a synthetic 440 Hz sine wave — not a real beat. It is
designed to be deterministic, not representative. Any algorithm will detect "A something"
from a pure 440 Hz tone. The test proves the function runs, not that it is accurate.

**Consequences:**
Replacing librosa key detection with Essentia `bgate` may be better or worse for trap
beats — there is no test to tell. The team ships with false confidence and users notice
accuracy regressions through feedback, not CI.

**Prevention:**
1. Before switching algorithms, capture the output of the current `detect_key()` on 5–10
   real representative WAV files and record the expected keys as a test fixture (golden
   files or hardcoded expected values).
2. Run both the old and new algorithm on the same set and compare. Only adopt the new
   algorithm if it matches or improves on the golden set.
3. Consider keeping both algorithms available and routing: use Essentia as primary,
   fall back to librosa if Essentia returns confidence below a threshold. This hybrid
   approach allows measuring accuracy difference in production.
4. Add at least one real-music integration test with a known key (e.g., a Creative
   Commons licensed beat with a documented key) to the `integration` marker group.

---

### PITFALL M8: Essentia Requires Audio as float32 at 44100 Hz — Pipeline Loads at 22050 Hz

**What goes wrong:**
The existing pipeline loads audio at `sr=22050` (mono) for librosa analysis. Essentia's
algorithms expect audio as a `numpy.float32` array — but many algorithms (especially
`RhythmExtractor2013` and `TuningFrequency`) are designed and validated at 44100 Hz.
Passing audio at 22050 Hz does not raise an error, but tempo estimation at half the
expected sample rate changes the behavior of the internal onset strength detection
and can introduce systematic BPM errors.

Additionally, the existing code loads with `librosa.load()` which returns float32 in
(-1.0, 1.0) range — which happens to be what Essentia expects. However, Essentia's
`MonoLoader` (its own audio loader) produces float32 at 44100 Hz by default and should
be used for Essentia analysis paths to ensure validated behavior.

**Why it happens:**
The 22050 Hz rate was chosen for librosa (standard for MIR tasks, halves memory usage).
Essentia documentation and benchmark papers assume 44100 Hz. The two pipelines have
different default sample rate assumptions that are not obvious from the API.

**Consequences:**
- BPM estimates from Essentia at 22050 Hz may be systematically off for certain algorithms
- Using `librosa.load()` output fed into Essentia bypasses Essentia's own loading/
  resampling validation path

**Prevention:**
1. For Essentia analysis paths, use `essentia.standard.MonoLoader(filename=str(wav_path), sampleRate=44100)()` to load audio.
2. If memory is a constraint, keep the librosa load at 22050 Hz for librosa functions and
   add a separate Essentia load at 44100 Hz only for Essentia-specific algorithms. The
   memory cost is: 90 seconds × 44100 × 4 bytes ≈ 15.8 MB per Essentia analysis window.
3. Verify the sample rate assumption by checking RhythmExtractor2013's documentation:
   it states input should be audio at the sample rate specified in its constructor
   (default 44100 Hz).

---

### PITFALL M9: Installing Essentia Does Not Automatically Resolve — The PyPI Wheel May Not Exist for the Exact Python Version

**What goes wrong:**
The venv uses Python 3.12. PyPI currently has Essentia wheels for 3.9, 3.10, 3.11, 3.12,
and 3.13 (confirmed from pypi.org/project/essentia as of July 2025). However, dev builds
are released frequently and older dev builds only had wheels for 3.9–3.11. If you pin
an older dev version (e.g., `essentia==2.1b6.dev857`) without verifying 3.12 wheel
availability, pip will attempt a source build, which requires C++ build tools, eigen3,
fftw, TagLib, and a full Essentia build environment — not present in a standard venv.

**Why it happens:**
Essentia publishes no stable release. All versions are `2.1b6.devXXXX`. The dev numbers
are sequential but not all dev versions ship wheels for all Python versions. If you pin
to an old dev version that has no 3.12 wheel, pip falls back to source compilation
silently (if build tools are present) or fails with "No matching distribution" (if not).

**Consequences:**
`pip install essentia==2.1b6.dev857` fails with a cryptic error on Python 3.12 because
that specific dev release pre-dates 3.12 wheel support.

**Prevention:**
1. Do not pin to an old dev version. Use `pip install essentia` (latest) or pin to a
   recent dev version that is confirmed to have 3.12 wheels:
   `pip install essentia==2.1b6.dev1389`.
2. Verify wheel availability before pinning: check pypi.org/project/essentia/VERSION
   and look for `cp312` in the filenames.
3. Add `essentia` to `requirements.txt` with a minimum version constraint:
   `essentia>=2.1b6.dev1000` to avoid accidentally pulling an old wheel-less version.

---

### PITFALL M10: Essentia and librosa Co-existing in the Same Venv — Potential numba Conflict

**What goes wrong:**
librosa uses `numba` for JIT-compiled onset strength computation. numba has strict
numpy version upper bounds in older releases (e.g., numba 0.56 requires numpy < 1.24).
The current requirements pin `numpy>=2.0,<3.0`. If adding Essentia causes pip to
downgrade numpy as a side-effect of resolving its dependencies, numba may break. The
reverse is also possible: if numba refuses to update past a certain numpy version, pip's
resolver may block the numpy upgrade needed for Essentia.

Current state check: `numpy 2.2.6` is installed. librosa 0.11.0 declares numpy 2.x
support (confirmed via librosa GitHub #1831). numba (used internally by librosa) must
also support numpy 2.x — numba 0.60+ added numpy 2.0 support released late 2024.

**Why it happens:**
Three-way dependency constraint: essentia (numpy compatibility), librosa (numpy + numba),
numba (numpy upper bound). If any of these pins conflict, pip's resolver fails silently
by downgrading one of them.

**Prevention:**
1. After `pip install essentia`, run `pip check` to verify no dependency conflicts.
2. Verify numba version: `python -c "import numba; print(numba.__version__)"`. Ensure
   it is ≥ 0.60 to support numpy 2.x.
3. If there is a conflict, resolve by pinning in `requirements.txt`:
   `numba>=0.60` and `numpy>=2.0,<3.0`. Do not leave these unconstrained.
4. Test the full import chain after installation:
   ```python
   import librosa, essentia, essentia.standard, numpy
   print(numpy.__version__, librosa.__version__)
   ```

---

## Original Phase Pitfalls (v1.0 Baseline)

The pitfalls below were researched for the original v1.0 build. They remain valid.

---

### Pitfall 1: Datacenter IP Flagging by YouTube

**What goes wrong:**
YouTube aggressively flags datacenter IP ranges (AWS, GCP, DigitalOcean, Hetzner, etc.) as bot traffic. Requests from these IPs receive HTTP 403 or silent failures — the download call appears to succeed but returns an error page or corrupted data. This is not a soft block; datacenter IPs get permanently deprioritized. Residential proxies achieve 85–95% success rate on YouTube while datacenter proxies achieve only 20–40%.

**Why it happens:**
YouTube cross-references the originating IP against known datacenter CIDR ranges. Any server hosting a web app is, by definition, a datacenter IP. The app's server is the worst possible machine from which to call YouTube.

**Consequences:**
Downloads stop working entirely on production within days or weeks of launch. Locally everything works because the developer's residential IP is fine. This is the most common "works on my machine" failure for this class of app.

**Warning signs:**
- Downloads fail in production but succeed locally
- HTTP 403 or `Sign in to confirm you're not a bot` errors
- yt-dlp returns exit code 1 with `HTTP Error 403: Forbidden`
- Error rate climbs over the first 2–4 weeks without code changes

**Prevention strategy:**
1. Use yt-dlp's `--cookies` flag with a valid YouTube session cookie obtained from a real browser. Cookies from a logged-in account attached to a real identity substantially reduce bot-detection signals.
2. Implement PO Token (Proof of Origin Token) support via a `yt-dlp-youtube-po-token-provider` plugin — YouTube's 2025/2026 anti-bot system requires this token per video.
3. Keep yt-dlp pinned to the latest version in `requirements.txt` and set up a weekly auto-update check — YouTube frequently changes its extraction protocol and yt-dlp patches typically follow within days.
4. Design the download pipeline to be swappable: abstract the download function behind an interface so the underlying tool (yt-dlp flags, proxy configuration, fallback strategies) can be changed without touching the rest of the codebase.
5. Do NOT set `--fragment-retries` to a high value (default 10 is dangerous) — excessive retries on 429 responses accelerate IP bans. Set `--fragment-retries 3` with exponential backoff logic at the app level.

**Which build phase:** Phase 1 (core download pipeline). The abstraction layer for swappability is a design decision that cannot be retrofitted cheaply.

---

### Pitfall 2: yt-dlp Version Drift Causing Silent Failures

**What goes wrong:**
YouTube regularly deploys protocol changes that break yt-dlp's extraction logic. If yt-dlp is pinned to an old version, downloads silently fail or return corrupted files. The failure mode is often not an exception but a downloaded file that is actually an HTML error page.

**Why it happens:**
The YouTube extraction module in yt-dlp is among the most actively maintained extractors precisely because YouTube fights back continuously. A version that worked last month may be broken today.

**Consequences:**
Users see 100% failure rate with no useful error message unless the app explicitly validates that the downloaded file is valid audio before returning it.

**Warning signs:**
- Downloaded "audio" files are 10–50KB (HTML error pages)
- ffmpeg reports `Invalid data found when processing input`
- yt-dlp error log contains `youtube: This video is not available` when the video clearly exists

**Prevention strategy:**
1. After every yt-dlp download, verify the output file with ffprobe (`ffprobe -v error -show_entries format=duration`). If the probe fails, treat the download as failed and return an error to the user.
2. Run yt-dlp in verbose mode (`-v`) in staging and capture stderr to a log — YouTube's bot detection messages appear in stderr, not stdout.
3. Pin yt-dlp to a minor version range (`yt-dlp>=2025.01,<2026.01`) and automate weekly dependency updates with a CI check.
4. Monitor the yt-dlp GitHub issues page for YouTube-specific breakages as a health signal for the app.

**Which build phase:** Phase 1 (core pipeline). File validation with ffprobe is non-negotiable from the first working version.

---

### Pitfall 3: Half-Tempo / Double-Tempo BPM Detection Error

**What goes wrong:**
Librosa's `beat_track` and `tempo` functions return the wrong BPM for a significant fraction of beats that underground producers actually use. The most common failure is returning exactly half the correct BPM (e.g., 70 BPM instead of 140 BPM for trap) or exactly double (e.g., 170 BPM instead of 85 BPM for boom bap). This is not a random error — it is a systematic failure of the onset-detection algorithm on half-time rhythmic patterns.

**Why it happens:**
Trap music at 140 BPM is typically programmed with a half-time drum pattern where the snare lands on beat 3 rather than beats 2 and 4. The rhythmic energy of the kick and snare pattern presents to the algorithm as 70 BPM. The algorithm is technically correct (70 BPM is a valid rhythmic division) but wrong by the producer's mental model of the track's tempo.

Lo-fi and boom bap have swung, quantized, or deliberately loose timing that confuses onset strength estimation. Tracks with no clear percussive transients (ambient pads, long sustained notes) may return 0 BPM or wildly incorrect values.

**Consequences:**
Producers see wrong BPM data and distrust the entire tool. BPM is one of the two core value propositions — getting it wrong consistently destroys credibility.

**Warning signs:**
- Test a set of 20 known-BPM trap beats; more than 30% return half the expected value
- Librosa returns 0.0 for ambient or pad-heavy tracks
- Results vary dramatically (±20 BPM) depending on which 60-second segment of the track is analyzed

**Prevention strategy:**
1. Always present BPM alongside a "also try: [half tempo]" or "also try: [double tempo]" value displayed as a secondary result. This turns a wrong answer into a useful answer. Example display: `140 BPM (or 70 BPM half-time)`.
2. Use librosa's `tempo` function (which returns a float) rather than `beat_track` (which tracks individual beats) for the primary BPM estimate — it is more stable for tempo-only detection.
3. Analyze the full track, not just the first 30 seconds. The intro of a trap beat is often atypical (no drums). Analyze a window starting at 20% of track duration.
4. Run analysis at multiple `start_bpm` hints (60, 90, 120, 170) and select the result with the highest onset strength correlation — this significantly reduces half-tempo errors on trap.
5. For key detection, use librosa's `chroma_cqt` with a `krumhansl` key profile. For BPM, consider using `essentia` as a supplementary check if librosa returns 0 or a suspiciously low value.
6. Always surface a confidence indicator to the user (e.g., "BPM: 140 — high confidence" vs "BPM: 72 — low confidence, verify manually").

**Which build phase:** Phase 2 (audio analysis). The multiple-hint strategy and half/double display are architecture decisions that need to be built in from the start of the analysis module.

---

### Pitfall 4: Temp File Accumulation and Disk Exhaustion

**What goes wrong:**
Every download creates at minimum three files on disk: the raw YouTube audio container (WebM/M4A), the intermediate decoded PCM, and the final WAV. If any step fails — or if the cleanup logic runs after the HTTP response is already sent — these files are never deleted. On a small VPS (20–50GB disk), 500 failed or abandoned downloads can consume the entire disk, causing the next write to fail silently and the server to crash or return 500 errors.

**Why it happens:**
- Python's `after_this_request` in Flask raises `PermissionError` because the file is still open when the framework tries to delete it during streaming
- Exceptions in the download pipeline that are caught at the top level skip the finally/cleanup block
- Users who close the browser mid-download leave orphaned files because the server cannot detect the client disconnect in time
- `tempfile.NamedTemporaryFile` with `delete=True` deletes on close, but if the file handle leaks, the file persists

**Consequences:**
Server disk fills up. All writes fail. Database (if any), logging, and the OS itself break. The app serves 500 errors until someone manually clears `/tmp`.

**Warning signs:**
- `df -h` on the server shows `/tmp` or the app working directory at 80%+ utilization
- `ls -la /tmp | wc -l` grows over time without shrinking
- Server alerts for disk I/O errors
- Users report 500 errors during peak usage

**Prevention strategy:**
1. Use `tempfile.mkdtemp()` to create a unique working directory per request. Wrap all processing in a `try/finally` block that calls `shutil.rmtree(tmpdir)` — the `finally` block runs even if an exception is raised.
2. Set a separate background cleanup job (e.g., a simple cron or APScheduler task) that deletes any file in the working directory older than 30 minutes. This is the safety net for the cases where `finally` does not run (process kill, OOM, etc.).
3. Limit concurrent downloads to a maximum of 5 at a time (use a semaphore or a task queue with a fixed worker count) to bound total in-flight disk usage at any moment.
4. Calculate WAV file size before download: `WAV size (MB) = duration_seconds × 0.176` for 44.1kHz 16-bit stereo. At 10 minutes, that is ~106 MB per download. Reject videos longer than a configurable limit (suggest 15 minutes) to cap per-request disk usage at ~160 MB.
5. Stream the WAV file to the client using HTTP chunked transfer rather than writing it to disk and then serving it — this eliminates the final output file entirely.

**Which build phase:** Phase 1 (core pipeline). The try/finally pattern and temp directory approach must be established before the first working endpoint.

---

## Moderate Pitfalls

---

### Pitfall 5: Concurrent Download Memory Spikes

**What goes wrong:**
Librosa loads the entire audio file into a NumPy array in memory before any analysis begins. A 10-minute WAV at 44.1kHz stereo is ~106 MB on disk, but NumPy stores it as float32 arrays that can consume 200–400 MB of RAM. With 5 concurrent users running analysis simultaneously, the Python process needs 1–2 GB of RAM just for audio data — not counting the web framework, yt-dlp subprocess, or ffmpeg.

**Why it happens:**
NumPy's `ndarray` is a fixed-length contiguous memory block. Librosa has no streaming analysis path for beat/key detection — the entire file must be loaded before the algorithm starts. This is a documented architectural limitation.

**Consequences:**
On a 2GB VPS (common for small projects), OOM killer terminates the gunicorn worker or the Python process mid-request. Users see connection resets, not useful error messages.

**Warning signs:**
- `free -m` shows available RAM below 200 MB under load
- `dmesg | grep oom` shows OOM killer events
- Gunicorn workers restart unexpectedly under concurrent load
- Analysis works fine for a single request but fails under 3+ simultaneous requests

**Prevention strategy:**
1. Cap concurrent analysis jobs at 3 using a `threading.Semaphore(3)` or a bounded task queue. Return an HTTP 503 with a "Processing at capacity, try again in a moment" message rather than queuing indefinitely.
2. Downsample to mono at 22050 Hz before analysis (librosa's default). This reduces memory footprint by ~4x. Producers do not need stereo or high sample rate for BPM/key detection — they need it for the WAV download, not the analysis.
3. Analyze a 90-second segment of the track rather than the full file for analysis purposes. Select the segment starting at 20% of the track duration (skips intros). This caps analysis memory at ~60 MB per request regardless of track length.
4. Set `gunicorn --workers 2 --threads 4` rather than multiple workers, to share the memory space and avoid duplicating the librosa/NumPy import overhead across worker processes.

**Which build phase:** Phase 2 (audio analysis) with infrastructure decisions in Phase 3 (deployment).

---

### Pitfall 6: WAV File Size Mismatch vs. User Expectations

**What goes wrong:**
Users conditioned by MP3 downloaders expect audio files to be 5–15 MB. A 10-minute beat in WAV at 44.1kHz 16-bit stereo is ~106 MB. YouTube's source audio is Opus at ~160kbps (48kHz), and when decoded to WAV, the file is 30–40x larger than the compressed source. Users on mobile connections or with data caps will abandon the download or think the app is broken when they see a 100MB file.

**Why it happens:**
WAV is uncompressed PCM. There is no way around the physics: `size_MB = duration_minutes × 10.6`. The project spec mandates WAV for quality, which is correct for professional use, but the size implication is rarely communicated to the user.

**Consequences:**
User abandonment mid-download, bandwidth costs on the server (outbound transfer fees), and mobile users being unable to use the app.

**Warning signs:**
- User feedback saying "the download is too slow" or "the file seems stuck"
- Server outbound bandwidth bills higher than expected
- Browser download progress bars showing 10+ minutes for a single file on a residential connection

**Prevention strategy:**
1. Display the estimated file size before the user clicks download: "Estimated size: ~106 MB (10:02 duration × WAV lossless)". Calculate from the video metadata duration before any download begins.
2. Show the download progress as a percentage with transfer speed, not just a spinner. Users on slow connections need feedback that the download is happening.
3. Set an explicit video duration limit (suggest 15 minutes, ~160 MB max WAV) and display it clearly on the UI: "Supports videos up to 15 minutes". Reject longer videos with a clear explanation.
4. Consider offering WAV as the primary format (per spec) but with an informational tooltip explaining why WAV is large and why it's the right format for production use. This educates the user rather than surprising them.

**Which build phase:** Phase 1 (UI/UX design). File size communication must be part of the initial UI, not added after user complaints.

---

### Pitfall 7: Key Detection Failure on Atonal and Complex Material

**What goes wrong:**
Chroma-based key detection (librosa's default approach) fails on material that is not tonally clear: drums-only passages, heavily distorted bass, highly compressed dynamic range, or tracks with no harmonic content. The algorithm will return a key, but it will be meaningless. Additionally, enharmonic equivalents (F# minor vs. Gb minor) may be returned inconsistently depending on the frame analyzed.

**Why it happens:**
Chroma features are extracted from the constant-Q transform, which smears spectral energy across pitch classes. If the signal has no harmonic content (pure noise, drums), all chroma bins receive roughly equal energy and the key profile correlation becomes meaningless.

**Warning signs:**
- The same track analyzed twice returns different keys
- Confidence scores (if implemented) near 0.5 for all keys
- Tracks with heavily compressed or distorted bass return keys that don't match what the producer knows

**Prevention strategy:**
1. Implement a chroma confidence score: compute the ratio of the maximum chroma correlation to the mean. If the ratio is below a threshold (empirically ~1.5–2.0), display "Key: Uncertain — verify manually" rather than a confident wrong answer.
2. High-pass filter the audio at 300 Hz before chroma extraction to remove bass frequencies that distort the harmonic estimation (sub-bass and bass lines can overwhelm chroma in trap/hip-hop).
3. Display both the most likely key and the second most likely key when confidence is low.
4. Use Camelot wheel notation alongside standard notation (e.g., "F# minor / 11A") — this is what underground producers actually use for mixing.

**Which build phase:** Phase 2 (audio analysis).

---

## Minor Pitfalls

---

### Pitfall 8: ffmpeg Not Found in Production Environment

**What goes wrong:**
yt-dlp requires ffmpeg to merge audio/video streams and to re-encode audio. Librosa requires ffmpeg (via audioread) as a fallback for reading certain audio formats. If ffmpeg is not installed as a system package, both tools fail with unhelpful errors like `NoBackendError` or `postprocessor ffmpeg not found`.

**Prevention strategy:**
1. In the Dockerfile (or server setup script), explicitly install ffmpeg as a system package: `apt-get install -y ffmpeg`. Do not rely on Python packages to install ffmpeg.
2. Add a startup health check that runs `ffmpeg -version` and fails fast with a clear error if it is missing.
3. Pin ffmpeg to a specific version or document the minimum version required.

**Which build phase:** Phase 3 (deployment/infrastructure).

---

### Pitfall 9: libsndfile Missing Breaks soundfile/librosa on Linux

**What goes wrong:**
librosa uses `soundfile` as its primary audio backend, which requires `libsndfile` — a C library that must be installed at the OS level. On minimal Linux containers (Alpine, slim Debian images), `libsndfile` is not present. pip installing librosa succeeds, but the first `librosa.load()` call raises `OSError: cannot load library 'libsndfile'`.

**Prevention strategy:**
1. In the Dockerfile: `apt-get install -y libsndfile1 ffmpeg` before `pip install librosa`.
2. Use `python:3.11-slim-bookworm` as the base Docker image rather than Alpine — Alpine uses musl libc which causes additional binary compatibility issues with audio libraries.
3. Run a test audio load during the Docker build step to catch missing system dependencies before the image is pushed.

**Which build phase:** Phase 3 (deployment/infrastructure).

---

### Pitfall 10: Synchronous Download Blocking the Web Server

**What goes wrong:**
If the download and analysis pipeline runs synchronously in the request handler, a single download (which takes 30–120 seconds) blocks an entire gunicorn worker thread for its entire duration. With 2 workers and 3 concurrent users, the third user's request waits until one of the first two finishes.

**Prevention strategy:**
1. Run the download + analysis pipeline in a background thread or process immediately, return a job ID to the client, and have the client poll for status. This is simpler than Celery for this scale.
2. For the target scale (hundreds of users, not thousands), `concurrent.futures.ThreadPoolExecutor` with 5 workers is sufficient. Full Celery + Redis is over-engineering for v1.
3. Use Server-Sent Events (SSE) or WebSocket to push progress updates to the client rather than polling. This gives the 2000s aesthetic a "live" feel that fits the retro UI identity.

**Which build phase:** Phase 1 (core architecture). The synchronous vs. async decision must be made before the first endpoint is built — retrofitting async is expensive.

---

### Pitfall 11: Legal/ToS Risk Assessment

**What goes wrong (mischaracterization of the risk):**
Developers either dismiss ToS risk entirely ("everyone does it") or over-index on it and never ship. The actual risk profile for SoundGrabber is nuanced.

**Actual risk breakdown:**

| Risk | Likelihood | Severity | Notes |
|------|-----------|----------|-------|
| YouTube ToS violation | Certain | Low for v1 | YouTube's ToS prohibits automated downloads. Enforcement against small apps is rare but not zero. Primary mechanism is service disruption (blocking), not legal action. |
| DMCA takedown of the app | Low | High | A 2026 US court ruling found that bypassing YouTube's technical measures may violate DMCA §1201. This is a legal gray area. Risk rises with scale and visibility. |
| Copyright infringement of content | Very low for reference/production use | High if monetized | Users downloading beats for production/reference is analogous to private use. The app itself does not host or redistribute content — it facilitates a download from YouTube's own servers. |
| YouTube blocking the server IP | High | Medium | This is a technical enforcement, not legal. Expected to happen. Mitigation is the technical strategy in Pitfall 1. |

**Prevention strategy:**
1. Add a clear terms of use on the app stating: "For personal and production reference use only. Do not redistribute downloaded content." This shifts responsibility to the user and demonstrates good faith.
2. Do not cache, store, or re-serve YouTube audio on the server. Process and immediately stream or delete. Storing a copy is the clearest path to infringement liability.
3. At scale (if the app grows significantly), consult a lawyer about DMCA §1201 exposure. For v1 at underground community scale, the practical risk is YouTube blocking the server IP, not a lawsuit.
4. Monitor the yt-dlp GitHub for any legal developments that affect the tool's status.

**Which build phase:** Phase 1 (architecture). The "no server-side storage" principle must be a design constraint from day one.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Core download pipeline | Datacenter IP immediately blocked in production | Cookie authentication + PO token from phase 1; design abstraction layer |
| File management | Orphaned temp files if cleanup runs after response | `try/finally` with `shutil.rmtree` from the first working handler |
| BPM/key analysis | Half-tempo error on trap, zero-BPM on ambient tracks | Multiple `start_bpm` hints + half/double display from phase 2 start |
| Concurrent users | Memory spike from multiple simultaneous librosa loads | Semaphore + mono/22050Hz downsampling for analysis before phase 2 ships |
| User expectations | WAV size surprises users expecting MP3-sized files | Show estimated size before download from first UI version |
| Deployment | ffmpeg and libsndfile missing in container | Dockerfile health check; use `python:3.11-slim-bookworm` not Alpine |
| Legal | Server-side audio caching creates infringement risk | Never persist audio beyond the request lifecycle |
| Scaling past v1 | yt-dlp fragility requires operational attention ongoing | Weekly yt-dlp update check + monitoring on download failure rate |
| v1.1: Essentia install | ABI mismatch with numpy 2.x | Pin to latest dev wheel; smoke test `import essentia.standard` immediately |
| v1.1: Essentia outputs | float32 breaks Celery JSON serialization | Wrap every Essentia output in `float()` before adding to return dict |
| v1.1: Key format change | Essentia returns key+scale separately, breaks Camelot lookup | Always assemble `f"{key} {scale}"` before calling `key_to_camelot()` |
| v1.1: Tuning detection | Percussive tracks return meaningless tuning values | HPSS before tuning; return `None` if harmonic energy too low |
| v1.1: Test coverage | `tuning_hz` field not in test's required set | Add `tuning_hz` to every `required` set in existing tests |
| v1.1: Key accuracy regression | No ground-truth baseline, switch is invisible in CI | Capture golden outputs before switching; add real-music integration test |
| v1.1: Sample rate mismatch | Essentia expects 44100 Hz, librosa loads at 22050 Hz | Use `essentia.standard.MonoLoader` at 44100 Hz for Essentia paths |

---

## Sources

**v1.1 Milestone Sources:**
- [Essentia PyPI page — wheel availability by Python version](https://pypi.org/project/essentia/)
- [Essentia installing docs](https://essentia.upf.edu/installing.html)
- [Essentia pip install fail on Linux — GitHub issue #1415](https://github.com/MTG/essentia/issues/1415)
- [Essentia RhythmExtractor2013 reference](https://essentia.upf.edu/reference/std_RhythmExtractor2013.html)
- [Essentia beat detection tutorial](https://essentia.upf.edu/tutorial_rhythm_beatdetection.html)
- [Essentia KeyExtractor reference](https://essentia.upf.edu/reference/std_KeyExtractor.html)
- [Essentia Key algorithm source (note names)](https://github.com/MTG/essentia/blob/master/src/algorithms/tonal/key.cpp)
- [Essentia TuningFrequency streaming reference](https://essentia.upf.edu/reference/streaming_TuningFrequency.html)
- [librosa estimate_tuning docs — return type, resolution](https://librosa.org/doc/main/generated/librosa.estimate_tuning.html)
- [librosa tuning_to_A4 — cents to Hz conversion](https://librosa.org/doc/main/generated/librosa.tuning_to_A4.html)
- [NumPy 2.0 ABI break — downstream package guide](https://numpy.org/doc/2.0/dev/depending_on_numpy.html)
- [numpy.float64 is JSON serializable but float32 is not](https://ellisvalentiner.com/post/numpyfloat64-is-json-serializable-but-numpyfloat32-is-not/)
- [Essentia array = numpy float32 (snyk advisor)](https://snyk.io/advisor/python/essentia/functions/essentia.array)
- [Kombu JSON serializer — numpy types issue #1067](https://github.com/celery/kombu/issues/1067)
- [librosa numpy 2.0 compatibility — issue #1831](https://github.com/librosa/librosa/issues/1848)

**v1.0 Baseline Sources:**
- [yt-dlp YouTube bot detection issue #13067](https://github.com/yt-dlp/yt-dlp/issues/13067)
- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [librosa memory usage growing with iterations — issue #1286](https://github.com/librosa/librosa/issues/1286)
- [librosa streaming for large files — official blog](https://librosa.org/blog/2019/07/29/stream-processing/)
- [librosa beat.beat_track documentation](https://librosa.org/doc/main/generated/librosa.beat.beat_track.html)
