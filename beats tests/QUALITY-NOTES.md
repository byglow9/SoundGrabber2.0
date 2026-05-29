# Audio Quality Notes

Local benchmark folder for comparing SoundGrabber WAV output against y2meta-style exports.

## Current Samples

| Beat | Candidate | Reference | Result |
|------|-----------|-----------|--------|
| 1 | `beat 1 soundgrabber.wav` | `beat 1 y2mtea.mp3` | SoundGrabber is loudness/stereo matched, but has more clipping and full-band 22.05 kHz content. |
| 1 | `beat 1 soundgrabber enhanced limiter.wav` | `beat 1 y2mtea.mp3` | Limiter removes clipping while preserving the full-band WAV. |
| 1 | `beat 1 soundgrabber enhanced limiter highcut.wav` | `beat 1 y2mtea.mp3` | Limiter + high-cut matches y2meta's ~16 kHz bandwidth closely. This is less faithful, but may sound smoother. |
| 2 | `beat 2 soundgrabber.wav` | `beat 2 y2meta.mp3` | SoundGrabber and y2meta are effectively matched. No processing needed. |

## Findings

- SoundGrabber already exports DAW-friendly WAV: 44.1 kHz, stereo, 16-bit PCM.
- y2meta exports MP3 320 kbps, not WAV/lossless.
- The y2meta signature in these samples is mostly a codec-style high-frequency cutoff near 16 kHz.
- A global high-cut would remove information from clean sources and should not be the default.
- A conditional limiter is safer: apply it only when clipping is detected.
- Beat 2 proves that some SoundGrabber downloads should be left untouched.

## Current Policy Hypothesis

Default export should stay as clean WAV from the best available YouTube audio stream.

Implemented baseline polish:

- If clipping is above `0.02%`, `pipeline.download_audio()` applies a conservative FFmpeg limiter (`alimiter=limit=0.98:level=false`).
- If clipping is at or below `0.02%`, the WAV is returned untouched.

Optional/source-aware polish can be added later:

- If the source has excessive full-band high-frequency content and listening tests prefer y2meta's smoother sound, offer a polished mode with high-cut.
- If the source already has low clipping and a lossy-source cutoff, do not process it.

## Limiter Validation

Validated on copies in `/tmp`:

| Beat | Before | Limiter Applied | After |
|------|--------|-----------------|-------|
| 1 | `0.05034%` clipping | yes | `0.0%` clipping |
| 2 | `0.00011%` clipping | no | unchanged |

## Commands

Analyze one file:

```bash
.venv/bin/python scripts/audio_enhancement_probe.py 'beats tests/beat 1 soundgrabber.wav'
```

Compare SoundGrabber against y2meta:

```bash
.venv/bin/python scripts/audio_enhancement_probe.py 'beats tests/beat 1 soundgrabber.wav' --compare-to 'beats tests/beat 1 y2mtea.mp3'
```

Generate a limiter-only test file when clipping is detected:

```bash
.venv/bin/python scripts/audio_enhancement_probe.py 'beats tests/beat 1 soundgrabber.wav' --enhance --highcut off
```

Generate a y2meta-like polished test file:

```bash
.venv/bin/python scripts/audio_enhancement_probe.py 'beats tests/beat 1 soundgrabber.wav' --enhance --highcut auto
```

## Next Test

Add at least one more pair:

- `beat 3 soundgrabber.wav`
- `beat 3 y2meta.mp3`

Then compare metrics and do an ear check before changing production behavior.
