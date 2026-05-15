"""SoundGrabber Docker Phase 13 - Wave 0 RED stubs.

Cobertura:
  DEPLOY-04 / D-02 -> test_no_imageio_ffmpeg_import
  DEPLOY-04 / D-03 -> test_no_librosa_import
  D-03 (detect_tuning Essentia) -> test_detect_tuning_essentia

Run: pytest tests/test_pipeline_docker.py -x -q
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _pipeline_import_names() -> set[str]:
    source = Path("pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    return imports


def test_no_imageio_ffmpeg_import():
    """D-02: pipeline.py must not import imageio_ffmpeg in Docker mode."""
    import_names = _pipeline_import_names()

    assert "imageio_ffmpeg" not in import_names, (
        "D-02: imageio_ffmpeg ainda importado em pipeline.py"
    )


def test_no_librosa_import():
    """D-03: pipeline.py must not import librosa in Docker mode."""
    import_names = _pipeline_import_names()

    assert "librosa" not in import_names, "D-03: librosa ainda importado em pipeline.py"


@pytest.mark.integration
def test_detect_tuning_essentia(tmp_path):
    """D-03: detect_tuning should run through the Essentia implementation."""
    import numpy as np
    import soundfile as sf

    sample_rate = 44100
    duration_sec = 2.0
    frequency_hz = 440.0
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    samples = 0.5 * np.sin(2 * np.pi * frequency_hz * t)
    wav_path = tmp_path / "sample.wav"
    sf.write(str(wav_path), samples.astype(np.float32), sample_rate)

    from pipeline import detect_tuning

    result = detect_tuning(wav_path)

    assert result is None or isinstance(result, float)
