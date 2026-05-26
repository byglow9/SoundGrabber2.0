---
created: 2026-05-26T15:30:48.529Z
title: Benchmark enhanced audio against y2meta
area: api
files:
  - pipeline.py:80
  - pipeline.py:253
---

## Problem

Initial competitor comparison suggests y2meta can sound more pleasant than SoundGrabber's current WAV output even though it is MP3/lossy. The first measured beat showed:

- SoundGrabber WAV: 44.1 kHz, 16-bit PCM, 1411 kbps, cutoff 22.0 kHz, RMS -9.40 dBFS, crest 9.4 dB, clipping 0.094%, stereo correlation 0.6336, side energy 64.9904, M/S ratio 2.11.
- y2meta MP3: 44.1 kHz, 320 kbps MP3, cutoff 16.1 kHz, RMS -9.34 dBFS, crest 9.3 dB, clipping 0.023%, stereo correlation 0.6258, side energy 66.1939, M/S ratio 2.08.

Working hypothesis for future validation: y2meta may be preferred by ear because it has lower clipping and less high-frequency content above ~16 kHz, not because it preserves more source fidelity.

## Solution

Before changing production behavior, test at least one more identical beat across SoundGrabber and y2meta and record the same metrics. If the pattern repeats, plan an optional enhanced export mode that can:

- reduce clipping to roughly the y2meta range;
- apply a controlled low-pass or high-frequency shaping near the competitor's measured cutoff;
- optionally adjust stereo width toward the measured y2meta profile;
- preserve the current unprocessed WAV path as the clean/default workflow.
