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
