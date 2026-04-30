"""SoundGrabber processing pipeline — Phase 1.

Single-module Python implementation of the download → convert → analyze pipeline.
Designed to be imported directly by Phase 2 (FastAPI + Celery) without rework.

Contract per D-03 (.planning/phases/01-processing-pipeline/01-CONTEXT.md):
  download_audio(url, cookies_path, po_token) -> Path
  convert_to_wav(audio_path) -> Path
  analyze_audio(wav_path) -> dict
  check_duration(url, cookies_path) -> dict  (helper, used by __main__)

Authentication (D-01, D-02):
  YTDLP_COOKIES_FILE — path to Netscape cookies.txt
  YTDLP_PO_TOKEN     — GVS PO Token, formatted as web.gvs+TOKEN

Output (D-05): JSON to stdout via __main__ (implemented in Plan 04).
"""
from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import yt_dlp


# Constants
MAX_DURATION_SEC = 900  # 15 minutes — locked by CORE-05 and D-10
TMP_PREFIX = "sg_"      # /tmp/sg_{12hex}.wav per D-08
WAV_TMP_DIR = Path("/tmp")


# Stage 0: Duration check (CORE-05, D-10)
def check_duration(url: str, cookies_path: str) -> dict[str, Any]:
    """Fetch yt-dlp metadata WITHOUT downloading; verify duration <= MAX_DURATION_SEC.

    Args:
        url: YouTube URL to inspect.
        cookies_path: Path to Netscape-format cookies.txt (D-01).

    Returns:
        The yt-dlp info dict. Caller can read info['duration'] safely.

    Raises:
        ValueError: If the video duration exceeds MAX_DURATION_SEC (15 minutes),
                    or if duration metadata is missing.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookies_path,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        raise ValueError("yt-dlp returned no metadata for the URL")

    duration = info.get("duration")
    if duration is None:
        raise ValueError("Could not determine video duration from YouTube metadata")

    if duration > MAX_DURATION_SEC:
        raise ValueError(
            f"Video too long: {duration}s exceeds the 15-minute limit "
            f"({MAX_DURATION_SEC}s). SoundGrabber only accepts videos under 15 minutes."
        )

    return info


# Stage 1: Download + Conversion (CORE-03, CORE-04)
def download_audio(url: str, cookies_path: str, po_token: str) -> Path:
    """Download YouTube audio and convert to WAV via yt-dlp's FFmpegExtractAudio postprocessor.

    Output: /tmp/sg_{12hex}.wav  (D-08). The intermediate audio file (webm/m4a) is
    cleaned up automatically by yt-dlp's postprocessor. On failure, any partial files
    matching /tmp/sg_{id}* are removed via try/finally (D-09).

    The final WAV is NOT deleted by this function — that is Phase 2's responsibility (D-09).

    Args:
        url: YouTube URL.
        cookies_path: Path to Netscape-format cookies.txt (D-01).
        po_token: GVS PO Token. Will be formatted as web.gvs+{po_token} per Pattern 2.
                  Pass empty string only if cookies alone are sufficient (rarely the case
                  for datacenter IPs — see STATE.md "Datacenter IP flagging").

    Returns:
        Path to the resulting WAV file (/tmp/sg_{12hex}.wav).

    Raises:
        RuntimeError: If yt-dlp fails (network error, bot detection, expired token).
        FileNotFoundError: If the WAV file is not present after a successful download.
    """
    wav_id = uuid.uuid4().hex[:12]
    outtmpl_base = str(WAV_TMP_DIR / f"{TMP_PREFIX}{wav_id}")
    wav_path = Path(f"{outtmpl_base}.wav")

    # extractor_args MUST be a list of strings, NOT a nested dict.
    # Pitfall: nested dict format causes "Requested format is not available" error.
    # Correct format verified via: github.com/yt-dlp/yt-dlp/issues/14307
    extractor_args: dict[str, list[str]] = {}
    if po_token:
        extractor_args["youtube"] = [f"po_token=web.gvs+{po_token}"]

    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl_base,  # NO %(ext)s — yt-dlp appends .wav after postprocessor (Pitfall 2)
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookies_path,
        "extractor_args": extractor_args,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "http_chunk_size": 10485760,  # 10MB — avoids YouTube throttling on long downloads
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        for f in WAV_TMP_DIR.glob(f"{TMP_PREFIX}{wav_id}*"):
            try:
                f.unlink()
            except OSError:
                pass
        raise RuntimeError(f"yt-dlp download failed: {e}") from e
    finally:
        # D-09: remove non-.wav intermediates that survived
        for f in WAV_TMP_DIR.glob(f"{TMP_PREFIX}{wav_id}*"):
            if f.suffix != ".wav":
                try:
                    f.unlink()
                except OSError:
                    pass

    if not wav_path.exists():
        candidates = list(WAV_TMP_DIR.glob(f"{TMP_PREFIX}{wav_id}*.wav"))
        if candidates:
            wav_path = candidates[0]
        else:
            raise FileNotFoundError(
                f"WAV not generated at {wav_path}. yt-dlp may have changed outtmpl behavior."
            )

    return wav_path


def convert_to_wav(audio_path: Path) -> Path:
    """D-03 contract: standalone WAV conversion entry point.

    yt-dlp's FFmpegExtractAudio postprocessor (used in download_audio) already produces a WAV,
    so this function is a thin pass-through that validates the input is .wav and returns it.
    Phase 2 may import this symbol; keeping it ensures the D-03 contract is complete.

    Args:
        audio_path: Path to a file (expected to be .wav).

    Returns:
        The same path if it is a valid WAV.

    Raises:
        ValueError: If the file is not .wav or does not exist.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise ValueError(f"Audio file does not exist: {audio_path}")
    if audio_path.suffix.lower() != ".wav":
        raise ValueError(
            f"convert_to_wav expects an already-converted .wav file (yt-dlp postprocessor "
            f"handles conversion in download_audio). Got: {audio_path.suffix}"
        )
    return audio_path


# Stage 2: ffprobe validation (post-download integrity check)
def validate_wav(wav_path: Path) -> float:
    """Verify a WAV file is real audio (not a YouTube error page disguised as a file).

    Runs ffprobe as a subprocess (list form, not shell string — prevents injection). Reads the
    container's reported duration. Tracks shorter than 1 second are rejected as corrupt.

    Args:
        wav_path: Path to the WAV file on disk.

    Returns:
        Duration in seconds (float).

    Raises:
        ValueError: If ffprobe exits non-zero, the file is missing, the duration is missing
                    from ffprobe output, or the duration is below 1 second (corrupt audio).
    """
    wav_path = Path(wav_path)
    if not wav_path.exists():
        raise ValueError(f"WAV file does not exist: {wav_path}")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(wav_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as e:
        raise ValueError(
            "ffprobe binary not found on PATH. Install FFmpeg >= 6.0: `apt-get install -y ffmpeg`"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ValueError(f"ffprobe timed out after 10s on {wav_path}") from e

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:200]
        raise ValueError(f"ffprobe failed on {wav_path}: {stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ValueError(f"ffprobe output not valid JSON: {result.stdout[:200]}") from e

    duration_str = data.get("format", {}).get("duration")
    if duration_str is None:
        raise ValueError(f"ffprobe could not determine duration of {wav_path}")

    try:
        duration = float(duration_str)
    except (TypeError, ValueError) as e:
        raise ValueError(f"ffprobe returned non-numeric duration: {duration_str!r}") from e

    if duration < 1.0:
        raise ValueError(f"Audio invalid or corrupt: duration {duration}s < 1.0s")

    return duration


# Krumhansl-Schmuckler tone profiles for key detection (ANALYSIS-02).
# Reference values from Krumhansl & Kessler (1982); standard MIR practice.
# Source: librosa documentation + classic MIR literature.
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# Stage 3: BPM detection (ANALYSIS-01)
def detect_bpm(wav_path: Path, total_duration: float) -> float:
    """Detect BPM using librosa.feature.tempo (NOT beat_track — Pattern 4 rationale).

    Production parameters:
      sr=22050      — mono downsampling, ~4x less RAM than 44100 stereo
      duration=90.0 — 90s window is sufficient for stable autocorrelation
      offset=20%    — skip intros that often lack percussion (capped at 30s)

    Args:
        wav_path: Path to the WAV file.
        total_duration: Total duration of the file (seconds), as returned by validate_wav.
                        Used to compute the offset; passed in to avoid a redundant ffprobe call.

    Returns:
        BPM as a Python float (NOT numpy.ndarray — Pitfall 3 mitigation). Rounded to 1 decimal.
    """
    offset = min(total_duration * 0.20, 30.0)
    y, sr = librosa.load(
        str(wav_path),
        sr=22050,
        mono=True,
        duration=90.0,
        offset=offset,
    )
    tempo = librosa.feature.tempo(y=y, sr=sr)
    # Pitfall 3: librosa returns an ndarray even for scalar tempo. Coerce to Python float.
    if hasattr(tempo, "__len__") and len(tempo) > 0:
        bpm = float(tempo[0])
    else:
        bpm = float(tempo)
    return round(bpm, 1)


# Stage 4: Key detection (ANALYSIS-02)
def _detect_key_from_chroma(chroma: "np.ndarray") -> str:
    """Internal helper: run Krumhansl-Schmuckler correlation on a chroma matrix.

    Returns: '<NOTE> <major|minor>' string with the highest correlation across all 24 profiles.
    """
    chroma_mean = chroma.mean(axis=1)

    major_corrs = [
        float(np.corrcoef(np.roll(_MAJOR_PROFILE, i), chroma_mean)[0, 1])
        for i in range(12)
    ]
    minor_corrs = [
        float(np.corrcoef(np.roll(_MINOR_PROFILE, i), chroma_mean)[0, 1])
        for i in range(12)
    ]

    best_major_idx = int(np.argmax(major_corrs))
    best_minor_idx = int(np.argmax(minor_corrs))

    if major_corrs[best_major_idx] >= minor_corrs[best_minor_idx]:
        return f"{_NOTES[best_major_idx]} major"
    return f"{_NOTES[best_minor_idx]} minor"


def detect_key(wav_path: Path) -> str:
    """Detect musical key using Krumhansl-Schmuckler correlation on chroma_cqt mean.

    Loads up to 120s of audio (Pitfall 4: chroma needs sufficient harmonic content).
    For shorter files (e.g., the 5s test fixture), librosa truncates `duration` silently —
    the function still works; accuracy is lower than on full tracks, which is expected
    for a unit test on a pure tone. Real accuracy is verified by e2e tests in Plan 04.

    Args:
        wav_path: Path to the WAV file.

    Returns:
        Key as '<NOTE> <major|minor>' string (e.g., 'F# minor', 'C major').
        NOTE uses sharp accidentals (#) — CAMELOT table maps both # and b spellings.
    """
    y, sr = librosa.load(
        str(wav_path),
        sr=22050,
        mono=True,
        duration=120.0,
    )
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    return _detect_key_from_chroma(chroma)


# Camelot wheel — 24-entry static table (ANALYSIS-04, Pattern 6 in RESEARCH.md).
# Enharmonic aliases included: librosa prefers sharps (#) but bemol (b) forms
# are mapped defensively (Assumption A1 in RESEARCH.md).
# Source: neume.io/camelot-wheel [VERIFIED]
_CAMELOT: dict[str, str] = {
    # Minor keys (A suffix)
    "Ab minor": "1A",  "G# minor": "1A",
    "Eb minor": "2A",  "D# minor": "2A",
    "Bb minor": "3A",  "A# minor": "3A",
    "F minor":  "4A",
    "C minor":  "5A",
    "G minor":  "6A",
    "D minor":  "7A",
    "A minor":  "8A",
    "E minor":  "9A",
    "B minor":  "10A",
    "F# minor": "11A", "Gb minor": "11A",
    "Db minor": "12A", "C# minor": "12A",
    # Major keys (B suffix)
    "B major":  "1B",
    "F# major": "2B",  "Gb major": "2B",
    "Db major": "3B",  "C# major": "3B",
    "Ab major": "4B",  "G# major": "4B",
    "Eb major": "5B",  "D# major": "5B",
    "Bb major": "6B",  "A# major": "6B",
    "F major":  "7B",
    "C major":  "8B",
    "G major":  "9B",
    "D major":  "10B",
    "A major":  "11B",
    "E major":  "12B",
}


# Public alias for the Camelot table — plan contract requires `from pipeline import CAMELOT`.
# _CAMELOT is the canonical dict; CAMELOT is the exported name (same object, no copy).
CAMELOT: dict[str, str] = _CAMELOT


def key_to_camelot(key: str) -> str:
    """Convert a key string (e.g. 'F# minor') to its Camelot wheel code (e.g. '11A').

    Uses the 24-entry static CAMELOT table. Returns '?' for unrecognised keys
    (e.g. if a future librosa version returns an unexpected spelling).

    Args:
        key: Key string from detect_key(), e.g. 'F# minor', 'C major'.

    Returns:
        Camelot code string, e.g. '11A', or '?' if not found.
    """
    return CAMELOT.get(key, "?")


# Stage 6: Top-level analysis orchestrator (ANALYSIS-01..04 + D-05 output shape)
def analyze_audio(wav_path: Path) -> dict[str, Any]:
    """Run the full analysis pipeline on an existing WAV and return the D-05 JSON shape.

    Pipeline order:
      1. validate_wav  — ffprobe sanity check + duration retrieval (Plan 02).
      2. detect_bpm    — librosa.feature.tempo on a 90s window (offset 20%).
      3. detect_key    — librosa.feature.chroma_cqt + Krumhansl-Schmuckler on a 120s window.
      4. key_to_camelot — O(1) lookup in the static CAMELOT table.
      5. Compute bpm_half = bpm/2, bpm_double = bpm*2 (D-06 — pure arithmetic, no second analysis).

    The WAV is NOT deleted by this function — Phase 2 owns the WAV lifecycle (D-09).

    Args:
        wav_path: Path to a WAV file produced by download_audio (or any other source).

    Returns:
        Dict with exactly these keys (all JSON-native types — Pitfall 3 mitigation):
            bpm           (float)  — primary detected BPM
            bpm_half      (float)  — bpm / 2
            bpm_double    (float)  — bpm * 2
            key           (str)    — '<NOTE> <major|minor>' (e.g., 'F# minor')
            camelot       (str)    — Camelot wheel code (e.g., '11A') or '?' if unmapped
            duration_sec  (float)  — file duration as reported by ffprobe
            wav_path      (str)    — string form of the input path (NOT a Path object)

    Raises:
        ValueError: If validate_wav fails (file missing, corrupt, or ffprobe error).
    """
    wav_path = Path(wav_path)
    duration_sec = validate_wav(wav_path)
    bpm = detect_bpm(wav_path, total_duration=duration_sec)
    key = detect_key(wav_path)
    camelot = key_to_camelot(key)

    return {
        "bpm": float(bpm),
        "bpm_half": round(float(bpm) / 2, 1),
        "bpm_double": round(float(bpm) * 2, 1),
        "key": str(key),
        "camelot": str(camelot),
        "duration_sec": round(float(duration_sec), 1),
        "wav_path": str(wav_path),
    }


# CLI entry point (D-04). JSON output per D-05.
if __name__ == "__main__":
    import os
    import sys

    def _emit_error(error_type: str, message: str) -> None:
        """Print a JSON error envelope to stdout (NOT stderr — D-05 says JSON on stdout).
        Exit code 1 is set by the caller via sys.exit."""
        print(json.dumps({"error": message, "type": error_type}))

    if len(sys.argv) < 2:
        _emit_error("usage_error", "Usage: python pipeline.py <youtube_url>")
        sys.exit(1)

    url = sys.argv[1]
    cookies_path = os.environ.get("YTDLP_COOKIES_FILE", "")
    po_token = os.environ.get("YTDLP_PO_TOKEN", "")

    # Up-front config check — fail fast with a clear envelope rather than a Python traceback.
    if not cookies_path:
        _emit_error("config_error", "YTDLP_COOKIES_FILE env var is not set. See .env.example.")
        sys.exit(1)
    if not Path(cookies_path).exists():
        _emit_error("config_error", f"YTDLP_COOKIES_FILE does not exist: {cookies_path}")
        sys.exit(1)
    # po_token is allowed to be empty (cookies-only flow); pipeline.download_audio handles it.
    # We log a warning to stderr if missing — does NOT affect JSON output.
    if not po_token:
        print(
            "WARNING: YTDLP_PO_TOKEN is empty. Datacenter IPs typically require a PO Token. "
            "If downloads fail with 'Sign in to confirm you're not a bot', set YTDLP_PO_TOKEN.",
            file=sys.stderr,
        )

    try:
        # Stage 0: pre-download duration check (CORE-05, D-10)
        info = check_duration(url, cookies_path)
        # Stage 1: download + WAV conversion (CORE-03, CORE-04)
        wav_path = download_audio(url, cookies_path, po_token)
        # Stage 2-5: validate + bpm + key + camelot + half/double (ANALYSIS-01..04)
        result = analyze_audio(wav_path)
        # Prefer YouTube's reported duration over ffprobe's (whole-second integer is the user-facing value).
        result["duration_sec"] = float(info.get("duration", result["duration_sec"]))
        print(json.dumps(result))
        sys.exit(0)
    except ValueError as e:
        # Validation errors: duration > 15min, missing duration metadata, ffprobe failure on WAV
        _emit_error("validation_error", str(e))
        sys.exit(1)
    except RuntimeError as e:
        # Download errors: yt-dlp DownloadError, network failure, expired PO Token
        _emit_error("download_error", str(e))
        sys.exit(1)
    except FileNotFoundError as e:
        _emit_error("download_error", str(e))
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 — last-resort envelope so stdout is always JSON
        _emit_error("internal_error", f"{type(e).__name__}: {e}")
        sys.exit(1)
