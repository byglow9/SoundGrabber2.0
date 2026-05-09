# Feature Landscape

**Domain:** YouTube audio downloader with music analysis (BPM + key detection) for underground/bedroom producers
**Researched:** 2026-04-29 (initial) / 2026-05-09 (updated for milestone v1.1 — precision analysis)
**Confidence:** HIGH for table stakes (verified across multiple tools); MEDIUM for differentiators (community patterns + tool gaps); HIGH for anti-features (user complaint data)

---

## Milestone v1.1 Addendum: BPM/Key/Tuning Precision Analysis

This section covers research specifically for the v1.1 milestone: upgrading analysis accuracy to Tunebat-level and adding tuning frequency detection (A = X Hz). All sections below apply to the new/upgraded features. The baseline feature landscape (table stakes, differentiators, anti-features) from initial research remains valid.

---

### 1. Tunebat Accuracy — What the Industry Standard Actually Is

**What Tunebat is built on:**
Tunebat is powered by the Music Technology Group (MTG) at Universitat Pompeu Fabra (UPF). Their backend is Essentia, an open-source C++/Python library that the MTG team developed and maintains. Tunebat's "industry-leading technology" claim is substantiated: Essentia's key detection uses HPCP (Harmonic Pitch Class Profile), and their BPM pipeline uses RhythmExtractor2013. These are the same algorithms available via `pip install essentia`.

**BPM accuracy — verified numbers from a 300-track benchmark (2026):**
- Tunebat weighted MAE: 29.53 BPM (across all genres)
- Hit4 rate (within ±4% of true BPM): 59.72%
- Severe octave error rate: 32.77%
- Performance is highly non-uniform: excellent at 70–89 BPM (87.5% Hit4), catastrophically poor above 150 BPM (17% Hit4 at 150–169, 0% above 170)

These numbers make Tunebat sound worse than marketing implies. The reason: BPM detection across all genres including jazz, live recordings, and ambient music is extremely hard. For electronically produced beats (the SoundGrabber use case — trap, drill, lo-fi, boom bap), accuracy is substantially higher because tempo is metronomic and consistent. No dataset-specific numbers for electronic beats alone were found in public literature, but the community consensus is "nearly perfect for electronic music with a consistent tempo" (MEDIUM confidence — multiple review sources, no controlled study found).

**Key accuracy — estimated range:**
- Industry-wide consensus for professional tools (Essentia, Mixed In Key): 85–95% for standard pop/rock/electronic
- Free tools average 70–85%; paid/professional tools achieve 90%+
- Mixed In Key claims 90%+ and is considered the accuracy gold standard for DJ use
- Tunebat key accuracy estimated at 90–95% for standard tonal music (MEDIUM confidence — stated in multiple reviews, no primary source with methodology)

**Critical finding:** The "Tunebat accuracy level" target is achievable by using Essentia directly. Tunebat IS Essentia with a web frontend. SoundGrabber can match Tunebat accuracy by using the same underlying library. No secret sauce or proprietary model is needed.

---

### 2. Current librosa Baseline vs Essentia Target

**librosa BPM (current):**
- Uses `beat.beat_track()` — dynamic programming beat tracker
- Based on onset detection + tempo estimation via autocorrelation
- Reasonable for most music; well-known to have half/double tempo errors
- No confidence score exposed to the caller by default

**Essentia BPM (target):**
- `RhythmExtractor2013` with `method="multifeature"` — slower but more accurate
- Also exposes beat positions and confidence score per beat
- `TempoCNN` — CNN-based deep learning model, 30–286 BPM range, outputs global + local estimates with probabilities; recommended pipeline uses `sampleRate=11025`
- Essentia itself recommends RhythmExtractor2013 as the primary algorithm for batch processing (non-realtime)

**librosa key detection (current):**
- Uses chroma features (CQT-based) correlated against Krumhansl-Schmuckler key templates
- CQT chroma has no overtone removal — lower quality than HPCP
- Returns only key+scale string, no confidence metric
- Accuracy: ~85% for standard tonal music (MEDIUM confidence)

**Essentia key detection (target):**
- HPCP (Harmonic Pitch Class Profile) — 36-bin resolution, cosine weighting, frequency range 20–3500 Hz
- Multiple profile options: `krumhansl`, `edma` (electronic dance music, corpus-extracted), `bgate` (default in Essentia, zeroes the 4 least relevant elements), `temperley` (best for classical)
- **For beats/EDM: use `edma` profile** — automatically extracted from EDM corpus, outperforms Shaath profiles for electronic music
- Returns: key (A–G), scale (major/minor), strength (confidence 0–1), firstToSecondRelativeStrength (gap to second-best estimate)
- HPCP overtone removal gives it an accuracy edge over librosa CQT chroma

**Practical upgrade path:** Replace `librosa.beat.beat_track()` with `essentia.standard.RhythmExtractor2013(method="multifeature")` and replace librosa chroma key detection with Essentia's `HPCP → KeyExtractor(profileType="edma")` pipeline.

---

### 3. Tuning Frequency Detection — "A = X Hz"

**What it is:**
Concert pitch / tuning frequency is the Hz value of the note A4 (the A above middle C). ISO standard is 440 Hz. Many producers use 432 Hz (claimed to sound "warmer"), 442 Hz (common in European classical ensembles), 443 Hz, 415 Hz (Baroque), or anywhere in between. For producers working with samples, knowing the tuning of a beat is critical: if a beat is at A=432 and your plugin is at A=440, the mix will be ~32 cents flat/sharp — audibly dissonant.

**How detection works:**
The algorithm analyzes the audio spectrum to find spectral peaks, then measures the average deviation of all detected pitches from the expected positions assuming A=440 Hz standard tuning. The deviation is expressed in cents (hundredths of a semitone).

**Essentia's TuningFrequency algorithm (recommended):**
- Input: spectral peak frequencies + magnitudes (output of SpectralPeaks algorithm)
- Output 1: `tuningFrequency` — detected reference pitch in Hz (e.g., 440.0, 432.1, 441.8)
- Output 2: `tuningCents` — deviation from 440 Hz in cents, range -35 to +65 cents
- Resolution: 1 cent by default (configurable)
- The -35 to +65 cent range covers: ~423 Hz (min) to ~457 Hz (max) — sufficient for all real-world tuning standards (432, 438, 440, 441, 442, 443, 444, 415)

**librosa alternative (secondary):**
- `librosa.estimate_tuning()` returns a float in [-0.5, 0.5) representing deviation in fractions of a bin (not cents directly)
- `librosa.pitch_tuning()` same but from frequency array input
- `librosa.A4_to_tuning()` and `librosa.tuning_to_A4()` for conversion between bin fractions and Hz
- More cumbersome to use for this purpose than Essentia's dedicated TuningFrequency algorithm

**Is the output continuous or discrete?**
Continuous. The algorithm returns a float Hz value like `440.3` or `431.8`. There is no snapping to preset values (432, 440, 442) — it returns the actual measured value. For display, round to nearest integer: "A = 432 Hz" or "A = 440 Hz". For producers, integer Hz is meaningful and sufficient.

**Accuracy caveats:**
- Works best on tonal audio with clear sustained pitches (synth pads, melodic instruments)
- Unreliable on purely percussive tracks with no tonal content (drum-only beats)
- For beats that are purely rhythmic (808s without melodic content), the result may be meaningless or misleading
- Tracks that modulate keys or have heavy pitch effects may produce averaged or incorrect results
- Range is limited to -35 to +65 cents from 440 Hz — extreme deviations (e.g. music not in 12-TET) will be outside detection range

**UX implication:** Always display the tuning value with appropriate context. "A = 440 Hz (standard)" reads more usefully to producers than a raw number. A caveat like "tuning detected from tonal content — may be imprecise for purely percussive tracks" would be honest but adds clutter. Minimum viable display: `A = 440 Hz`.

---

### 4. Beat-Specific Accuracy Challenges

**Half-time / double-time confusion (most common problem):**
- A 140 BPM trap beat may be detected as 70 BPM if the algorithm locks onto kick drums at half rate
- A 70 BPM hip-hop track with busy 16th notes may be detected as 140 BPM
- This is mathematically valid — both are "correct" depending on which rhythmic unit is the "beat"
- Genres where this is endemic: trap (typically 130–160 BPM, often "felt" as 65–80), lo-fi hip-hop (70–90 BPM), drill (140–150 BPM, felt as 70–75)
- Existing feature (half/double toggle) already addresses this at the UX level
- Essentia's RhythmExtractor2013 multifeature is better at resolving this than librosa, but still not immune

**Key detection — relative major/minor confusion:**
- The most common key detection error: detecting C major instead of A minor (they share the same notes)
- Relative major and minor have identical pitch content; the algorithm must determine the tonal center from emphasis and melodic context
- For beats (instrumental, no vocals), this is harder than for songs with vocal melodies that strongly establish the key
- Essentia's `edma` profile is specifically tuned for EDM and handles this better than generic profiles for the SoundGrabber use case
- `bgate` (default) zeroes the 4 least relevant profile elements, which also reduces relative major/minor confusion vs raw profiles
- No algorithm gets this right 100% of the time — the music theory is genuinely ambiguous in many cases

**Sparse / minimalist beats:**
- Lo-fi beats with very few instruments → fewer spectral peaks → less data for HPCP → less reliable key detection
- Ambient, cinematic, or drone-type instrumentals with slow harmonic movement confuse BPM detection (long onset intervals)
- Extremely sparse tracks (e.g. single piano + hi-hat) can fool both BPM and key algorithms

**Tempo changes:**
- Beats with live-played elements or intentional tempo drift (soul samples, jazz loops) produce averaged BPM values
- Electronic beats rarely have this issue — metronomic grid locked production is the norm in trap, drill, lo-fi

**Purely percussive tracks:**
- 808 drum loops with no tonal content → key detection produces arbitrary or garbage output
- Tuning detection is meaningless on these
- Design choice: still display the result but accept that it may be wrong for this edge case

**Genres and difficulty ranking (HIGH confidence — well-documented in MIR literature):**
1. Electronic / trap / drill with quantized grid: easiest — nearly perfect BPM, 85-95% key
2. Boom bap with swung hi-hats and live samples: harder — half/double tempo common, key ambiguous
3. Lo-fi with jazz samples: moderate — BPM usually detectable, key detection affected by sample quality
4. Ambient / cinematic: hardest — BPM unreliable, key detection unreliable

---

### 5. Camelot Wheel Accuracy with Professional Algorithms

**Camelot is derived from key, not independently detected:**
Camelot notation is a simple mathematical mapping from (key, scale) → Camelot code. If the key detection is right, Camelot is right. If key detection is wrong, Camelot is wrong. There is no independent accuracy loss at the Camelot mapping step.

**Camelot accuracy = key detection accuracy:**
- With librosa (current): ~85% correct key → ~85% correct Camelot
- With Essentia HPCP + edma profile (target): ~90–95% correct key → ~90–95% correct Camelot
- Mixed In Key (paid, industry gold standard for DJs): 90%+ claimed
- The gap between librosa and Essentia at the Camelot level is roughly 5–10 percentage points

**Practical implication:** Upgrading key detection to Essentia HPCP with `edma` profile directly upgrades Camelot accuracy with no additional code. The Camelot lookup table (12 major × 12 minor = 24 codes) remains unchanged.

---

### 6. Table Stakes (Updated for v1.1)

Building on the original table stakes, these apply to the precision analysis milestone:

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| More accurate BPM (match Tunebat) | Producers have used Tunebat; if SoundGrabber gives different/worse values, trust drops | Medium (Essentia install + pipeline rewrite) | Essentia = same backend as Tunebat; achievable |
| More accurate key/Camelot | Wrong key wastes producer time (wrong chord choices, dissonant layering) | Medium (Essentia HPCP pipeline) | `edma` profile specifically tuned for EDM |
| Tuning frequency "A = X Hz" | Producers who work with samples NEED this; sampling a 432 Hz beat into a 440 Hz project = dissonant result | Medium (Essentia TuningFrequency algorithm + SpectralPeaks) | Display as integer Hz; continuous detection |

---

### 7. Differentiators (v1.1 additions)

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Tuning detection displayed inline | No download tool does this; Tunebat itself does NOT display tuning on their free tier | Low-Med (algorithm exists in Essentia) | Novel in context of download+analysis tools |
| BPM confidence display | Essentia multifeature returns beat confidence; surfacing this builds trust | Low (data is already available) | Show as icon or percentage alongside BPM |
| Key detection strength indicator | Essentia Key algorithm returns `strength` (0–1); low strength = ambiguous key | Low (data is already available) | Show only when strength < threshold (e.g. < 0.3) as a caveat |

**Does Tunebat display tuning?**
Tunebat's free analyzer does NOT display A=X Hz tuning information in their current interface (LOW confidence — based on product page observation without creating an account; paid tier may differ). This is a differentiation opportunity: SoundGrabber can show something Tunebat's free tier does not.

---

### 8. Anti-Features (v1.1 specific)

| Anti-Feature | Why Avoid |
|---|---|
| Showing tuning as "432 Hz mode" / binary classification | Tuning is continuous — round to integer Hz and show the actual value. Binary "432 vs 440" classification throws away precision and is misleading |
| Showing key strength as a raw decimal (0.847) | Meaningless to producers; use it internally as a threshold, show only a caveat when low |
| Offering to "fix" the tuning (pitch-shift) | Out of scope; tool is for analysis, not mastering |
| Running Essentia synchronously in the web request thread | Essentia processing is CPU-intensive; must run in Celery worker (already the architecture) |

---

### 9. Feature Dependencies (v1.1 additions)

```
WAV file (from existing download pipeline)
  └── Essentia analysis pipeline (Celery worker)
        ├── MonoLoader → FrameCutter → Windowing → Spectrum → SpectralPeaks
        │     └── TuningFrequency → tuningFrequency (Hz), tuningCents
        │     └── HPCP → KeyExtractor(profileType="edma")
        │           └── key, scale, strength → Camelot mapping
        └── MonoLoader(sampleRate=11025) → RhythmExtractor2013(method="multifeature")
              └── BPM, beat positions, confidence
```

All three new outputs (BPM, key, tuning) share the same audio load step and can be computed in a single Essentia pipeline pass.

---

### 10. MVP Recommendation for v1.1

**Build:**
1. Replace librosa BPM → Essentia RhythmExtractor2013 multifeature
2. Replace librosa key → Essentia HPCP + KeyExtractor(profileType="edma")
3. Add TuningFrequency algorithm → display as "A = X Hz" on results page
4. Expose BPM confidence from RhythmExtractor2013 (already computed by the algorithm)
5. Expose key strength from KeyExtractor (already in output) — show caveat if strength < 0.25

**Defer:**
- TempoCNN (deep learning BPM): higher accuracy for edge cases but adds model weight (~50MB+), slower startup; only worth it if RhythmExtractor2013 multifeature proves insufficient in testing
- BPM histogram display (multiple tempo candidates): engineering complexity, minimal UX value for producers

---

## Original Feature Landscape (Initial Research — v1.0)

### Table Stakes

Features users expect. Missing = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Underground Producer Relevance | Dependencies |
|---|---|---|---|---|
| Paste URL and trigger download | Every tool does this; it's the entry point | Low | Core: producers find beats on YouTube, not via file upload | None |
| Real-time processing feedback (progress indicator) | Downloading + converting + analyzing takes 10-60s; silence reads as broken | Low-Med | High: producers are impatient, they close tabs fast | Download pipeline |
| Direct WAV file download (no email, no signup) | Cobalt, y2mate, snapsave — all offer no-account download; gating = drop-off | Low | Critical: underground producers distrust signup walls | Conversion pipeline |
| BPM display after analysis | TuneReveal, vocalremover.org, tunebat all show BPM as baseline output | Med | Critical: producers need BPM before setting DAW tempo | Audio analysis |
| Musical key display (e.g. F# minor) | Every key/BPM tool shows key; standard expectation in 2025 | Med | Critical: producers need key before writing chords or picking samples to layer | Audio analysis |
| Mobile-usable layout | 40-60% of web traffic is mobile; producers browse YouTube on phone | Low-Med | Medium: bedroom producers often reference YouTube on phone while working at desk | None |
| HTTPS / no sketchy redirects | y2mate, snapsave reputation destroyed by malware + redirects; users are alert to this | Low | High: underground community spreads word fast about shady tools | Infrastructure |
| Fast result (under 60 seconds end-to-end) | Competing tools can often return in 15-30s; anything over 90s loses users | High (infra) | High: producers iterate fast; waiting kills flow state | Infra + analysis pipeline |

---

### Differentiators (v1.0)

| Feature | Value Proposition | Complexity | Underground Producer Relevance | Dependencies |
|---|---|---|---|---|
| Retro Y2K / 2000s internet aesthetic (phpBB / Tibia / Orkut feel) | No other downloader does this; it's a cultural statement, not just a skin — it signals "this was made for us, not for everyone" | Low-Med (CSS/design work) | Very high: underground producers grew up in this era; the aesthetic creates instant belonging | None — pure design |
| Combined download + analysis in one workflow | Current tools are siloed: download somewhere, then upload to tunebat or vocalremover to get key/BPM; SoundGrabber collapses this into one step | Med (orchestration) | Critical differentiator: this is the exact pain point — producers go to 2-3 tools to do what SoundGrabber does in one | Download + Analysis must be coupled |
| Camelot wheel notation alongside standard key | Producers who use harmonic mixing (common in hip-hop, lo-fi, trap, house) need Camelot codes (e.g. 4A instead of just "Ab minor") — Mixed In Key popularized this | Low (mapping table, no extra analysis needed) | High: any producer doing sample-based work or layering tracks uses Camelot | Key detection result |
| Confidence indicator on BPM/key results | Librosa and Essentia can be wrong — especially on complex or unconventional beats; showing "95% confidence" or flagging low-confidence results builds trust and manages expectations | Med (expose model confidence scores) | Medium: producers who have been burned by wrong BPM detection will appreciate honesty | Audio analysis pipeline |
| Half-time / double-time BPM toggle | Many hip-hop and lo-fi beats are detected at double their "feel" BPM (e.g. a 70 BPM track detected as 140 BPM); a simple ÷2 / ×2 button solves this without re-analysis | Low (UI toggle, math only) | High: extremely common problem in hip-hop production where swing and half-time patterns confuse detectors | BPM display |
| Copy BPM / Copy key buttons | Producers immediately need these values in their clipboard to paste into FL Studio, Ableton, or their notes | Low | High: small UX detail but removes friction in the workflow handoff | Results display |

---

### Anti-Features (v1.0)

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| User accounts / login / history | Contradicts the "zero friction" core value | Stay stateless |
| Multiple format exports (MP3, FLAC, OGG) | WAV is the right choice for producers (lossless container, DAW-ready) | Export only WAV |
| Playlist / batch download | Single-URL tool is cleaner; batch adds massive infra complexity | Keep it single-URL |
| Vocal remover / stem separation | Different product, GPU-heavy | Reference stem tools in the results page if needed |
| SoundCloud / Instagram / TikTok support | Each platform = separate extraction logic, separate breakage surface | Lock to YouTube |
| Subscription / paywall | Kills viral word-of-mouth in underground communities | No monetization in v1 |
| Dark mode toggle | Y2K aesthetic is the identity — one strong look is more memorable | Commit to a single deliberate look |

---

## Competitor Feature Gap Analysis

| Tool | Download WAV | BPM | Key | Tuning (A=Hz) | No Account | No Ads | Combined UX | Y2K Aesthetic |
|---|---|---|---|---|---|---|---|---|
| y2mate | Yes (MP3/MP4 focus) | No | No | No | Yes | No (aggressive ads) | No | No |
| cobalt.tools | Yes (WAV supported) | No | No | No | Yes | Yes | No | No |
| TuneReveal | No (analysis only) | Yes | Yes | No | Yes | Yes | No | No |
| tunebat | No (DB lookup) | Yes | Yes | No (free tier) | No (pro) | Partial | No | No |
| vocalremover.org | No | Yes (upload) | Yes (upload) | No | Yes | Partial | No | No |
| **SoundGrabber v1.1** | **Yes (WAV only)** | **Yes (Essentia)** | **Yes (Essentia)** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

---

## Sources

**Tunebat / Essentia connection:**
- [Tunebat Analyzer](https://tunebat.com/Analyzer) — HIGH confidence (official product)
- [Essentia Homepage — MTG/UPF](https://essentia.upf.edu/) — HIGH confidence (official)
- [Essentia HPCP Key Detection Tutorial](https://essentia.upf.edu/tutorial_tonal_hpcpkeyscale.html) — HIGH confidence (official docs)
- [Essentia Key Algorithm Reference](https://essentia.upf.edu/reference/std_Key.html) — HIGH confidence (official docs)
- [Essentia Beat Detection Tutorial](https://essentia.upf.edu/tutorial_rhythm_beatdetection.html) — HIGH confidence (official docs)

**Tunebat accuracy benchmark:**
- [BPM Finder: Best Tunebat Alternative 2026 — 300-Track Benchmark](https://bpm-finder.net/posts/tunebat-bpm-alternative) — MEDIUM confidence (third-party benchmark, methodology not fully disclosed)
- [Tunebat Review — eathealthy365/Ultimate Guide 2025](https://eathealthy365.com/what-is-tunebat-a-deep-dive-into-the-song-key-bpm-tool/) — LOW confidence (secondary review)
- [Tunebat Review — descriptive.audio](https://descriptive.audio/tunebat-review-unveil-a-djs-secret-weapon/) — MEDIUM confidence (practitioner review)

**Tuning frequency detection:**
- [Essentia TuningFrequency Algorithm](https://essentia.upf.edu/reference/streaming_TuningFrequency.html) — HIGH confidence (official docs)
- [librosa.estimate_tuning](https://librosa.org/doc/main/generated/librosa.estimate_tuning.html) — HIGH confidence (official docs)
- [librosa.A4_to_tuning](https://librosa.org/doc/main/generated/librosa.A4_to_tuning.html) — HIGH confidence (official docs)
- [iZotope: Tuning Standards Explained](https://www.izotope.com/en/learn/tuning-standards-explained) — HIGH confidence (professional audio source)

**BPM/key accuracy and genre challenges:**
- [StemSplit: BPM and Key Detection](https://stemsplit.io/blog/bpm-key-detection-feature) — MEDIUM confidence
- [Best BPM Finder for Harmonic Mixing — djtechreviews](https://djtechreviews.com/guides/resources/best-bpm-and-key-finder) — MEDIUM confidence
- [Mixed In Key Accuracy Claims](https://mixedinkey.com/harmonic-mixing-guide/) — MEDIUM confidence (vendor claim)
- [Essentia TempoCNN Reference](https://essentia.upf.edu/reference/std_TempoCNN.html) — HIGH confidence (official docs)

**Camelot and harmonic mixing:**
- [Camelot Wheel — DJ.Studio](https://dj.studio/blog/camelot-wheel) — HIGH confidence
- [Mixed In Key Camelot Wheel](https://mixedinkey.com/camelot-wheel/) — HIGH confidence (official)
