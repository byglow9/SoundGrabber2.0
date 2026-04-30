"""Generate tests/fixtures/sample.wav: 5-second 440Hz (A4) tone, mono, 22050 Hz, PCM 16-bit.

Run: python scripts/generate_sample_wav.py
Used by tests/conftest.py fixture `sample_wav_path` for offline analysis tests.
"""
import numpy as np
import soundfile as sf
from pathlib import Path

SAMPLE_RATE = 22050
DURATION_SEC = 5.0
FREQUENCY_HZ = 440.0  # A4 — exact pitch class A; key detection should return 'A major' or 'A minor'
OUTPUT = Path(__file__).parent.parent / "tests" / "fixtures" / "sample.wav"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, DURATION_SEC, int(SAMPLE_RATE * DURATION_SEC), endpoint=False)
    # Pure tone with mild fade-in/fade-out to avoid clicks
    samples = 0.5 * np.sin(2 * np.pi * FREQUENCY_HZ * t)
    fade_len = int(0.05 * SAMPLE_RATE)
    fade = np.linspace(0, 1, fade_len)
    samples[:fade_len] *= fade
    samples[-fade_len:] *= fade[::-1]
    sf.write(str(OUTPUT), samples.astype(np.float32), SAMPLE_RATE, subtype="PCM_16")
    print(f"Wrote {OUTPUT} ({DURATION_SEC}s @ {SAMPLE_RATE}Hz, {FREQUENCY_HZ}Hz tone)")


if __name__ == "__main__":
    main()
