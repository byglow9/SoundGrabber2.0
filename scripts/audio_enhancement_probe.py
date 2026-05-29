#!/usr/bin/env python3
"""Measure audio quality signals and optionally write a conditional enhanced WAV.

This is a local lab tool for comparing SoundGrabber output against competitors.
It does not change the production pipeline.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy import signal


EPS = 1e-12


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(float(value), EPS))


def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(str(path), dtype="float64", always_2d=True)
    if audio.size == 0:
        raise ValueError(f"Empty audio file: {path}")
    return audio, int(sample_rate)


def _mono(audio: np.ndarray) -> np.ndarray:
    return np.mean(audio, axis=1)


def _cutoff_hz(mono: np.ndarray, sample_rate: int, threshold_db: float) -> float:
    nperseg = min(8192, max(1024, len(mono) // 8))
    freqs, _, stft = signal.stft(
        mono,
        fs=sample_rate,
        window="hann",
        nperseg=nperseg,
        noverlap=nperseg // 2,
        boundary=None,
        padded=False,
    )
    if stft.size == 0:
        return 0.0
    magnitude = np.mean(np.abs(stft), axis=1)
    magnitude_db = 20.0 * np.log10(np.maximum(magnitude, EPS) / max(float(np.max(magnitude)), EPS))
    active = np.where(magnitude_db >= threshold_db)[0]
    if len(active) == 0:
        return 0.0
    return float(freqs[int(active[-1])])


def _rolloff_hz(mono: np.ndarray, sample_rate: int, ratio: float = 0.85) -> float:
    windowed = mono * np.hanning(len(mono))
    spectrum = np.abs(np.fft.rfft(windowed)) ** 2
    total = float(np.sum(spectrum))
    if total <= EPS:
        return 0.0
    cumulative = np.cumsum(spectrum)
    idx = int(np.searchsorted(cumulative, total * ratio))
    freqs = np.fft.rfftfreq(len(mono), d=1.0 / sample_rate)
    return float(freqs[min(idx, len(freqs) - 1)])


def analyze(path: Path, cutoff_threshold_db: float) -> dict[str, Any]:
    audio, sample_rate = _load_audio(path)
    mono = _mono(audio)
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio**2)))
    clipping_ratio = float(np.mean(np.abs(audio) >= 0.999999))

    mid_energy = side_energy = ms_ratio = correlation = None
    stereo_width = "mono"
    if audio.shape[1] >= 2:
        left = audio[:, 0]
        right = audio[:, 1]
        if np.std(left) > EPS and np.std(right) > EPS:
            correlation = float(np.corrcoef(left, right)[0, 1])
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        mid_energy = float(np.mean(mid**2) * 10_000)
        side_energy = float(np.mean(side**2) * 10_000)
        ms_ratio = float(mid_energy / side_energy) if side_energy > EPS else None
        stereo_width = "wide" if correlation is not None and correlation < 0.7 else "narrow"

    cutoff = _cutoff_hz(mono, sample_rate, cutoff_threshold_db)
    nyquist = sample_rate / 2.0

    return {
        "path": str(path),
        "sample_rate_hz": sample_rate,
        "channels": int(audio.shape[1]),
        "duration_sec": round(float(len(audio) / sample_rate), 3),
        "peak_dbfs": round(_dbfs(peak), 3),
        "peak_sample": round(peak, 8),
        "rms_dbfs": round(_dbfs(rms), 3),
        "crest_factor_db": round(_dbfs(peak) - _dbfs(rms), 3),
        "clipping_percent": round(clipping_ratio * 100.0, 5),
        "cutoff_hz": round(cutoff, 1),
        "bandwidth_usage_percent": round((cutoff / nyquist) * 100.0, 2) if nyquist else 0.0,
        "spectral_rolloff_85_hz": round(_rolloff_hz(mono, sample_rate), 1),
        "stereo_correlation": None if correlation is None else round(correlation, 4),
        "stereo_width": stereo_width,
        "mid_energy": None if mid_energy is None else round(mid_energy, 4),
        "side_energy": None if side_energy is None else round(side_energy, 4),
        "ms_ratio": None if ms_ratio is None else round(ms_ratio, 4),
    }


def compare(
    candidate_path: Path,
    reference_path: Path,
    cutoff_threshold_db: float,
) -> dict[str, Any]:
    candidate = analyze(candidate_path, cutoff_threshold_db)
    reference = analyze(reference_path, cutoff_threshold_db)
    delta_fields = [
        "duration_sec",
        "peak_dbfs",
        "rms_dbfs",
        "crest_factor_db",
        "clipping_percent",
        "cutoff_hz",
        "bandwidth_usage_percent",
        "spectral_rolloff_85_hz",
        "stereo_correlation",
        "mid_energy",
        "side_energy",
        "ms_ratio",
    ]
    deltas: dict[str, float | None] = {}
    for field in delta_fields:
        candidate_value = candidate.get(field)
        reference_value = reference.get(field)
        if candidate_value is None or reference_value is None:
            deltas[field] = None
        else:
            deltas[field] = round(float(candidate_value) - float(reference_value), 5)

    notes: list[str] = []
    if float(candidate["clipping_percent"]) > float(reference["clipping_percent"]) + 0.01:
        notes.append("candidate clips more than reference")
    if float(candidate["cutoff_hz"]) > float(reference["cutoff_hz"]) + 1000:
        notes.append("candidate keeps substantially more high-frequency content")
    if abs(float(candidate["rms_dbfs"]) - float(reference["rms_dbfs"])) <= 0.2:
        notes.append("loudness is effectively matched")
    if (
        candidate["stereo_correlation"] is not None
        and reference["stereo_correlation"] is not None
        and abs(float(candidate["stereo_correlation"]) - float(reference["stereo_correlation"])) <= 0.02
    ):
        notes.append("stereo image is effectively matched")

    return {
        "candidate": candidate,
        "reference": reference,
        "delta_candidate_minus_reference": deltas,
        "notes": notes,
    }


def decide_filters(
    metrics: dict[str, Any],
    clipping_threshold_percent: float,
    highcut_mode: str,
    highcut_trigger_hz: float,
    highcut_hz: float,
    highcut_passes: int,
) -> tuple[list[str], list[str]]:
    tone_filters: list[str] = []
    dynamics_filters: list[str] = []
    reasons: list[str] = []

    if highcut_mode == "auto" and float(metrics["cutoff_hz"]) >= highcut_trigger_hz:
        tone_filters.extend([f"lowpass=f={highcut_hz}:p=2"] * highcut_passes)
        reasons.append(f"cutoff {metrics['cutoff_hz']} Hz >= {highcut_trigger_hz} Hz")
    elif highcut_mode not in {"auto", "off"}:
        tone_filters.extend([f"lowpass=f={float(highcut_mode)}:p=2"] * highcut_passes)
        reasons.append(f"manual high-cut at {highcut_mode} Hz")

    if float(metrics["clipping_percent"]) > clipping_threshold_percent:
        dynamics_filters.append("alimiter=limit=0.98:level=false")
        reasons.append(
            f"clipping {metrics['clipping_percent']}% > {clipping_threshold_percent}%"
        )

    return [*tone_filters, *dynamics_filters], reasons


def enhance(input_path: Path, output_path: Path, filters: list[str]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH")
    if not filters:
        raise ValueError("No filters selected; refusing to write an unchanged enhanced file")
    cmd = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-af",
        ",".join(filters),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-sample_fmt",
        "s16",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg enhancement failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--compare-to", type=Path, help="Reference file to compare against")
    parser.add_argument("--enhance", action="store_true", help="Write a processed WAV if filters are selected")
    parser.add_argument("--output", type=Path, help="Output path for --enhance")
    parser.add_argument("--cutoff-threshold-db", type=float, default=-80.0)
    parser.add_argument("--clipping-threshold-percent", type=float, default=0.02)
    parser.add_argument("--highcut", default="off", help="'off', 'auto', or a frequency in Hz")
    parser.add_argument("--highcut-trigger-hz", type=float, default=18_000.0)
    parser.add_argument("--highcut-hz", type=float, default=16_500.0)
    parser.add_argument("--highcut-passes", type=int, default=6)
    args = parser.parse_args()

    if args.compare_to:
        print(json.dumps(compare(args.input, args.compare_to, args.cutoff_threshold_db), indent=2, sort_keys=True))
        return 0

    metrics_before = analyze(args.input, args.cutoff_threshold_db)
    filters, reasons = decide_filters(
        metrics_before,
        args.clipping_threshold_percent,
        args.highcut,
        args.highcut_trigger_hz,
        args.highcut_hz,
        max(1, args.highcut_passes),
    )

    report: dict[str, Any] = {
        "input": str(args.input),
        "metrics_before": metrics_before,
        "selected_filters": filters,
        "reasons": reasons,
    }

    if args.enhance:
        output = args.output
        if output is None:
            output = args.input.with_name(f"{args.input.stem}_enhanced_{uuid.uuid4().hex[:8]}.wav")
        if filters:
            enhance(args.input, output, filters)
            report["output"] = str(output)
            report["metrics_after"] = analyze(output, args.cutoff_threshold_db)
        else:
            report["output"] = None
            report["message"] = "No processing applied; source already matched the policy."

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
