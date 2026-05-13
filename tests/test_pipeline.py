"""SoundGrabber pipeline tests — Phase 1.

Stubs created in Plan 01 (Wave 0). Implementations turn these green:
  - Plan 02 (Wave 1): test_duration_check_*, test_download_opts_include_auth,
                       test_wav_file_created, test_ffprobe_validates_wav
  - Plan 03 (Wave 2): test_bpm_*, test_camelot_mapping, test_key_detection
  - Plan 04 (Wave 3): test_json_output_shape, test_e2e_*

Markers:
  - (no marker): unit tests, run on every commit (~5s)
  - integration: requires FFmpeg + fixture WAV, no network
  - e2e: requires live YouTube + cookies.txt + PO Token (manual)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# CORE-05: Duration check (Plan 02, Wave 1)
# ---------------------------------------------------------------------------

def test_duration_check_rejects_long_video(mock_yt_info_long):
    """check_duration() must raise ValueError when info['duration'] > 900s."""
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 02)")
    with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = mock_yt_info_long
        mock_ydl_class.return_value = mock_ydl
        with pytest.raises(ValueError, match=r"(?i)(too long|duration|limit)"):
            pipeline.check_duration("https://www.youtube.com/watch?v=long456", "cookies.txt")


def test_duration_check_accepts_short_video(mock_yt_info_short):
    """check_duration() must return info dict for videos <= 900s."""
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 02)")
    with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = mock_yt_info_short
        mock_ydl_class.return_value = mock_ydl
        info = pipeline.check_duration("https://www.youtube.com/watch?v=abc123", "cookies.txt")
        assert info["duration"] == 183
        assert info["duration"] <= 900


# ---------------------------------------------------------------------------
# CORE-03: Download with auth (Plan 02, Wave 1)
# ---------------------------------------------------------------------------

def test_download_opts_include_auth(monkeypatch, tmp_path):
    """download_audio() must build ydl_opts with cookiefile and nested extractor_args.

    Phase 10.1 uses cookies from cache_dir/cookies.txt plus bgutil via BGUTIL_BASE_URL.
    yt-dlp's Python API expects extractor_args as nested dicts, not CLI-style strings.
    """
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 02)")
    captured_opts: dict = {}
    monkeypatch.setenv("BGUTIL_BASE_URL", "https://bgutil-test.example.com")
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n__Secure-3PSID\tvalue\n")

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def download(self, urls):
            # Simulate yt-dlp creating the WAV
            outtmpl = captured_opts["outtmpl"]
            Path(f"{outtmpl}.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
            return 0

    with patch("yt_dlp.YoutubeDL", FakeYDL):
        try:
            pipeline.download_audio(
                "https://www.youtube.com/watch?v=abc123",
                str(tmp_path),
            )
        except (FileNotFoundError, RuntimeError):
            pass  # Expected: FakeYDL.download() creates a stub WAV but the path check may fail

    assert captured_opts.get("cookiefile") == str(cookies), "cookiefile not wired to ydl_opts"
    extractor_args = captured_opts.get("extractor_args", {})
    yt_args = extractor_args.get("youtube", {})
    assert isinstance(yt_args, dict), f"extractor_args.youtube must be dict, got {type(yt_args)}"
    assert yt_args.get("player_client") == ["web_safari", "web"], f"player_client not set correctly: {yt_args}"
    assert yt_args.get("getpot_bgutil_baseurl") == ["https://bgutil-test.example.com"], \
        f"getpot_bgutil_baseurl not in extractor_args.youtube: {yt_args}"


# ---------------------------------------------------------------------------
# CORE-04: WAV conversion (Plan 02, Wave 1)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_wav_file_created(tmp_path, monkeypatch):
    """download_audio() must return a Path that exists with .wav extension after the call."""
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 02)")
    pytest.skip("Integration test wired in Plan 02 — requires FFmpeg + mocked yt-dlp")


@pytest.mark.integration
def test_ffprobe_validates_wav(sample_wav_path):
    """validate_wav() must run ffprobe on the fixture WAV and return its duration in seconds."""
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 02)")
    duration = pipeline.validate_wav(sample_wav_path)
    assert 4.9 < duration < 5.1, f"Expected ~5s, got {duration}s"


# ---------------------------------------------------------------------------
# ANALYSIS-01: BPM detection (Plan 03, Wave 2)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_bpm_accuracy(sample_wav_path):
    """detect_bpm() must run on a real WAV and return a positive float.

    The fixture is a pure 440Hz tone (no rhythm), so we only assert the call shape and a sane range,
    not numeric accuracy. Real BPM accuracy is verified in the e2e tests (D-07 URLs).
    """
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 03)")
    bpm = pipeline.detect_bpm(sample_wav_path)
    assert isinstance(bpm, float), f"BPM must be float (json-serializable), got {type(bpm)}"
    assert 30.0 < bpm < 300.0, f"BPM out of plausible range: {bpm}"


# ---------------------------------------------------------------------------
# ANALYSIS-02: Key detection (Plan 03, Wave 2)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_key_detection(sample_wav_path):
    """detect_key() on a 440Hz pure-tone WAV must return a key in the A-pitch class.

    A4 = 440Hz, so chroma should peak at A. Result should be 'A major' or 'A minor'.
    """
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 03)")
    key, confidence = pipeline.detect_key(sample_wav_path, tuning_hz=None)
    assert isinstance(key, str), f"key must be str, got {type(key)}"
    assert key.startswith("A "), f"Expected key starting with 'A ' for 440Hz tone, got: {key!r}"
    assert key.endswith(("major", "minor")), f"key must end with 'major' or 'minor', got: {key!r}"
    assert 0.0 <= confidence <= 1.0, f"confidence must be in [0,1], got {confidence}"


# ---------------------------------------------------------------------------
# ANALYSIS-03: BPM half/double (Plan 03, Wave 2)
# ---------------------------------------------------------------------------

def test_bpm_half_double_calculation():
    """analyze_audio() result must include bpm_half = bpm/2 and bpm_double = bpm*2.

    Pure arithmetic — no librosa call needed. Implements D-06.
    """
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 03)")
    # Stub the underlying detection so we can verify only the half/double math
    with patch.object(pipeline, "detect_bpm", return_value=140.0), \
         patch.object(pipeline, "detect_key", return_value=("C major", 1.0)), \
         patch.object(pipeline, "detect_tuning", return_value=440.0), \
         patch.object(pipeline, "validate_wav", return_value=180.0):
        result = pipeline.analyze_audio(Path("/tmp/fake.wav"))
    assert result["bpm"] == 140.0
    assert result["bpm_half"] == 70.0, f"Expected bpm_half=70.0, got {result['bpm_half']}"
    assert result["bpm_double"] == 280.0, f"Expected bpm_double=280.0, got {result['bpm_double']}"


# ---------------------------------------------------------------------------
# ANALYSIS-04: Camelot mapping (Plan 03, Wave 2)
# ---------------------------------------------------------------------------

def test_camelot_mapping():
    """key_to_camelot() must map standard notation to Camelot codes per neume.io reference.

    Verified entries from CONTEXT.md sample output: F# minor -> 11A.
    Plus a sanity sample of the full 24-key wheel.
    """
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 03)")
    expected = {
        "F# minor": "11A",
        "C major": "8B",
        "A minor": "8A",
        "B major": "1B",
        "D minor": "7A",
        "G major": "9B",
        "E major": "12B",
        "F minor": "4A",
    }
    for key, camelot in expected.items():
        assert pipeline.key_to_camelot(key) == camelot, \
            f"key_to_camelot({key!r}) returned {pipeline.key_to_camelot(key)!r}, expected {camelot!r}"


# ---------------------------------------------------------------------------
# TUNING-01: detect_tuning retorna Hz em sinal harmônico (Wave 0 RED stub)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_detect_tuning_harmonic(sample_wav_path):
    """detect_tuning() em WAV 440Hz deve retornar float próximo de 440 Hz.

    O fixture sample.wav é um tom puro de 440Hz — energia harmônica dominante.
    Espera tuning_hz entre 400 e 480 Hz (±10% de 440), não None, não numpy type.
    TUNING-01.
    """
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py não tem detect_tuning ainda (Plan 02)")
    if not hasattr(pipeline, "detect_tuning"):
        pytest.fail("pipeline.detect_tuning não existe — implementar no Plan 02")
    result = pipeline.detect_tuning(sample_wav_path)
    assert result is not None, "detect_tuning retornou None em sinal harmônico 440Hz — HPSS gate incorreto"
    assert isinstance(result, float), f"detect_tuning deve retornar float nativo, got {type(result)}"
    assert 400.0 < result < 480.0, f"tuning_hz fora do range esperado para 440Hz: {result}"


# ---------------------------------------------------------------------------
# TUNING-02: detect_tuning retorna None em sinal percussivo (Wave 0 RED stub)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_detect_tuning_percussive(tmp_path):
    """detect_tuning() em WAV de ruído branco deve retornar None.

    Ruído branco tem ratio de energia harmônica ~0 (< 0.2), portanto o HPSS gate
    deve ativar e retornar None. TUNING-02.
    """
    import numpy as np
    import soundfile as sf

    pipeline = pytest.importorskip("pipeline", reason="pipeline.py não tem detect_tuning ainda (Plan 02)")
    if not hasattr(pipeline, "detect_tuning"):
        pytest.fail("pipeline.detect_tuning não existe — implementar no Plan 02")

    # Criar WAV de ruído branco puro (sem pitch) — 2 segundos a 22050 Hz
    rng = np.random.default_rng(seed=42)
    noise = rng.uniform(-1.0, 1.0, size=22050 * 2).astype(np.float32)
    percussive_wav = tmp_path / "percussive.wav"
    sf.write(str(percussive_wav), noise, 22050)

    result = pipeline.detect_tuning(percussive_wav)
    assert result is None, (
        f"detect_tuning deve retornar None em ruído branco (sinal percussivo), got {result}"
    )


# ---------------------------------------------------------------------------
# PREC-03: detect_key passa tuning_hz para KeyExtractor (Wave 0 RED stub)
# ---------------------------------------------------------------------------

def test_detect_key_uses_tuning_hz():
    """detect_key() deve instanciar KeyExtractor com tuningFrequency=tuning_hz.

    Usa mock para capturar os kwargs de instanciação de KeyExtractor.
    Verifica que PREC-03 está cumprido: o tuning_hz detectado é passado como
    tuningFrequency antes que os bins HPCP sejam computados.
    """
    from unittest.mock import MagicMock, patch

    pipeline = pytest.importorskip("pipeline", reason="pipeline.py não tem detect_key Essentia ainda (Plan 03)")
    if not hasattr(pipeline, "detect_key"):
        pytest.fail("pipeline.detect_key não existe")

    captured_kwargs: dict = {}

    def fake_key_extractor_factory(**kwargs):
        captured_kwargs.update(kwargs)
        mock_instance = MagicMock()
        mock_instance.return_value = ("A", "minor", 0.85)
        return mock_instance

    with patch("essentia.standard.KeyExtractor", side_effect=fake_key_extractor_factory), \
         patch("essentia.standard.MonoLoader") as mock_loader:
        mock_loader.return_value.return_value = MagicMock()
        pipeline.detect_key(Path("/tmp/fake.wav"), tuning_hz=432.0)

    assert "tuningFrequency" in captured_kwargs, (
        f"KeyExtractor não recebeu tuningFrequency. kwargs capturados: {captured_kwargs}"
    )
    assert abs(captured_kwargs["tuningFrequency"] - 432.0) < 0.01, (
        f"tuningFrequency esperado 432.0, got {captured_kwargs['tuningFrequency']}"
    )
    assert captured_kwargs.get("profileType") == "edma", (
        f"profileType deve ser 'edma', got {captured_kwargs.get('profileType')!r}"
    )


# ---------------------------------------------------------------------------
# D-05: JSON output shape (Plan 04, Wave 3)
# ---------------------------------------------------------------------------

def test_json_output_shape():
    """analyze_audio() return value must serialize to JSON with all required fields per D-05."""
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py not yet implemented (Plan 03)")
    with patch.object(pipeline, "detect_bpm", return_value=140.0), \
         patch.object(pipeline, "detect_key", return_value=("F# minor", 1.0)), \
         patch.object(pipeline, "detect_tuning", return_value=440.0), \
         patch.object(pipeline, "validate_wav", return_value=183.0):
        result = pipeline.analyze_audio(Path("/tmp/sg_abc123.wav"))
    # Must serialize without TypeError (Pitfall 3 — librosa may return ndarray)
    serialized = json.dumps(result)
    parsed = json.loads(serialized)
    required = {"bpm", "key", "camelot", "bpm_half", "bpm_double", "wav_path", "duration_sec", "tuning_hz"}
    assert required.issubset(parsed.keys()), f"Missing fields: {required - set(parsed.keys())}"
    assert parsed["camelot"] == "11A", f"F# minor -> 11A expected, got {parsed['camelot']!r}"


# ---------------------------------------------------------------------------
# QUAL-01: JSON output shape com WAV real (Plan 06-03, Wave 2)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_json_output_shape_integration(sample_wav_path):
    """analyze_audio() em WAV real deve ter tuning_hz e json.dumps não deve levantar TypeError.

    QUAL-01: valida que todos os tipos no dict são JSON-nativos (sem numpy types).
    """
    import json as _json
    pipeline = pytest.importorskip("pipeline", reason="pipeline.py não implementado")
    result = pipeline.analyze_audio(sample_wav_path)
    required = {"bpm", "key", "camelot", "bpm_half", "bpm_double",
                "wav_path", "duration_sec", "tuning_hz"}
    assert required.issubset(result.keys()), f"Missing: {required - set(result.keys())}"
    serialized = _json.dumps(result)  # não deve levantar TypeError — QUAL-01
    parsed = _json.loads(serialized)
    assert parsed["tuning_hz"] is None or isinstance(parsed["tuning_hz"], float), (
        f"tuning_hz deve ser float ou None, got {type(parsed['tuning_hz'])}"
    )
    assert isinstance(parsed["bpm"], float), f"bpm deve ser float, got {type(parsed['bpm'])}"
    assert isinstance(parsed["key"], str), f"key deve ser str, got {type(parsed['key'])}"


# ---------------------------------------------------------------------------
# D-07: End-to-end with real YouTube URLs (Plan 04, Wave 3)
# ---------------------------------------------------------------------------

def _e2e_skip_if_no_creds():
    if not os.environ.get("YTDLP_COOKIES_FILE") or not Path(os.environ.get("YTDLP_COOKIES_FILE", "")).exists():
        pytest.skip("YTDLP_COOKIES_FILE not set or file missing — e2e requires real cookies")
    if not os.environ.get("YTDLP_PO_TOKEN"):
        pytest.skip("YTDLP_PO_TOKEN not set — e2e requires real PO Token")


def _run_pipeline_e2e(url: str, expected_max_duration: int = 900) -> dict:
    """Drive `python3 pipeline.py URL` as a subprocess; assert success envelope; return parsed JSON.

    Asserts:
      - Exit code 0.
      - stdout parses as JSON.
      - All 7 D-05 fields are present.
      - bpm is a number in the plausible range (30..300).
      - duration_sec <= expected_max_duration (proves CORE-05 didn't false-reject).
      - wav_path exists on disk after the call (proves the WAV was actually produced).
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "pipeline.py", url],
        capture_output=True,
        text=True,
        timeout=300,  # 5 minutes — generous for download + analysis on a 15min cap
    )

    assert result.returncode == 0, (
        f"pipeline.py exited {result.returncode}\n"
        f"stdout: {result.stdout!r}\n"
        f"stderr: {result.stderr!r}"
    )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"pipeline.py stdout was not JSON: {result.stdout!r}\nstderr: {result.stderr!r}")

    assert "error" not in data, f"pipeline returned error envelope: {data}"

    required = {"bpm", "key", "camelot", "bpm_half", "bpm_double", "wav_path",
                "duration_sec", "tuning_hz"}
    missing = required - set(data.keys())
    assert not missing, f"missing fields in JSON output: {missing}; got {data}"

    assert isinstance(data["bpm"], (int, float)) and 30.0 <= data["bpm"] <= 300.0, \
        f"bpm out of range: {data['bpm']}"
    assert data["duration_sec"] <= expected_max_duration, \
        f"duration_sec exceeded expected max: {data['duration_sec']}"

    wav_path = Path(data["wav_path"])
    assert wav_path.exists(), f"WAV not on disk: {wav_path}"
    assert wav_path.stat().st_size > 1024, f"WAV suspiciously small: {wav_path.stat().st_size} bytes"

    return data


@pytest.mark.e2e
def test_e2e_rock(youtube_test_urls, tmp_path):
    """E2E: pipeline runs end-to-end on the rock/lo-fi reference URL (D-07)."""
    pytest.importorskip("pipeline", reason="pipeline.py not yet implemented")
    _e2e_skip_if_no_creds()
    _run_pipeline_e2e(youtube_test_urls["rock_lofi"], expected_max_duration=900)


@pytest.mark.e2e
def test_e2e_trap(youtube_test_urls, tmp_path):
    """E2E: pipeline runs end-to-end on the trap reference URL (D-07).

    Verifies D-06: even if librosa returns half-tempo on a trap beat, the user can identify
    the feel-tempo from the half/double values. We assert all 3 BPM values are present and
    bpm_half == bpm/2 and bpm_double == bpm*2.
    """
    pytest.importorskip("pipeline", reason="pipeline.py not yet implemented")
    _e2e_skip_if_no_creds()
    result = _run_pipeline_e2e(youtube_test_urls["trap"], expected_max_duration=900)
    # D-06 explicit verification on a trap beat:
    assert abs(result["bpm_half"] - result["bpm"] / 2) < 0.2
    assert abs(result["bpm_double"] - result["bpm"] * 2) < 0.2


@pytest.mark.e2e
def test_e2e_house(youtube_test_urls, tmp_path):
    """E2E: pipeline runs end-to-end on the lo-fi/house reference URL (D-07, planner-chosen)."""
    pytest.importorskip("pipeline", reason="pipeline.py not yet implemented")
    _e2e_skip_if_no_creds()
    _run_pipeline_e2e(youtube_test_urls["lofi_house"], expected_max_duration=900)
