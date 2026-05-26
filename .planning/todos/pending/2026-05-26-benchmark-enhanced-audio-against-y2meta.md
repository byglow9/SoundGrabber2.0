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

Second measured beat, SoundGrabber only so far:

- SoundGrabber WAV: 44.1 kHz, 16-bit PCM, 1411 kbps, 21.52 MB, duration 2:07, cutoff 15.2 kHz, bandwidth usage 68.8%, RMS -14.93 dBFS, peak 0.00 dBFS, crest 14.9 dB, clipping none, noise floor -120.0 dB, spectral rolloff 388 Hz, stereo correlation 0.8124, stereo width narrow, mid energy 76.5193, side energy 24.6229, M/S ratio 3.11.
- This sample already has a lossy-source cutoff around 15.2 kHz and no clipping in SoundGrabber output, so any future enhanced mode must be conditional/source-aware rather than applying the first sample's fixes globally.

Second measured beat, y2meta comparison:

- y2meta MP3: 44.1 kHz, 320 kbps MP3, 4.88 MB, duration 2:08, cutoff 16.1 kHz, bandwidth usage 72.8%, RMS -14.93 dBFS, peak 0.00 dBFS, crest 14.9 dB, clipping none, noise floor -120.0 dB, spectral rolloff 388 Hz, stereo correlation 0.8132, stereo width narrow, mid energy 76.7423, side energy 24.6364, M/S ratio 3.11.
- Beat 2 conclusion: SoundGrabber and y2meta are effectively identical on loudness, dynamics, clipping, noise floor, rolloff, and stereo. The only material measured differences are container/size/codec and frequency cutoff (SoundGrabber 15.2 kHz vs y2meta 16.1 kHz). This weakens any global rule to reduce clipping, low-pass, or alter stereo width for every download.

## Solution

Before changing production behavior, test at least one more identical beat across SoundGrabber and y2meta and record the same metrics. If the pattern repeats, plan an optional enhanced export mode that can:

- apply anti-clipping/limiting only when clipping is detected;
- apply optional high-cut/high-frequency smoothing only when the source has excessive or harsh high-frequency content;
- leave already clean/cut sources untouched;
- avoid global stereo widening/narrowing unless repeated measurements show a consistent need;
- preserve the current unprocessed WAV path as the clean/default workflow.

Target enhancement policy:

- If clipping is present, apply an anti-clipping/limiter stage with conservative headroom.
- If high-frequency content is excessive or harsh, offer/apply a controlled high-cut stage.
- If the source is already clean, dynamically limited, or spectrally cut, do not process it further.
- Treat enhancement as source-aware polish, not as a claim of restoring lost quality.
