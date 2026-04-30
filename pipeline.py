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


# [PLAN 03] — Analysis stubs (NOT implemented here; Plan 03 fills these in)
# These stubs exist so that Plan 02 unit tests for Plan 03 behaviour can use
# patch.object() without AttributeError. Calling any of these directly will
# raise NotImplementedError.

def detect_bpm(wav_path: Path, total_duration: float) -> float:
    """Stub — implemented in Plan 03."""
    raise NotImplementedError("detect_bpm is implemented in Plan 03")


def detect_key(wav_path: Path) -> str:
    """Stub — implemented in Plan 03."""
    raise NotImplementedError("detect_key is implemented in Plan 03")


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


def analyze_audio(wav_path: Path) -> dict:
    """Run full audio analysis: ffprobe validation → BPM → key → Camelot.

    Routing skeleton wired here (Plan 02) so test stubs using patch.object on
    detect_bpm / detect_key / validate_wav can exercise the result shape.
    Real implementations of detect_bpm, detect_key, key_to_camelot are filled
    in by Plan 03.

    Args:
        wav_path: Path to a .wav file on disk.

    Returns:
        dict with keys: bpm, bpm_half, bpm_double, key, camelot,
                        duration_sec, wav_path.

    Raises:
        NotImplementedError: Until Plan 03 implements detect_bpm and detect_key.
        ValueError: If validate_wav rejects the file.
    """
    wav_path = Path(wav_path)
    duration_sec = validate_wav(wav_path)
    bpm = detect_bpm(wav_path, total_duration=duration_sec)
    key = detect_key(wav_path)
    return {
        "bpm": bpm,
        "bpm_half": round(bpm / 2, 1),
        "bpm_double": round(bpm * 2, 1),
        "key": key,
        "camelot": key_to_camelot(key),
        "duration_sec": round(duration_sec, 1),
        "wav_path": str(wav_path),
    }
