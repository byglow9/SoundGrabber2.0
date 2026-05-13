"""SoundGrabber processing pipeline — Phase 1.

Single-module Python implementation of the download → convert → analyze pipeline.
Designed to be imported directly by Phase 2 (FastAPI + Celery) without rework.

Contract per D-02 (.planning/phases/10.1-oauth2-railway-volume-auth-migration/10.1-CONTEXT.md):
  check_duration(url, cache_dir) -> dict
  download_audio(url, cache_dir) -> Path
  convert_to_wav(audio_path) -> Path
  analyze_audio(wav_path) -> dict

Authentication (Phase 10.1 gap closure — plan 06 — hybrid architecture):
  Arquitetura híbrida: cookies do Volume (identidade autenticada) + bgutil (PO Token / JS challenge).
  Ambos passados a yt-dlp simultaneamente em check_duration e download_audio.
  YTDLP_CACHE_DIR — path do Railway Volume com cookies.txt (identidade autenticada)
  BGUTIL_BASE_URL — URL do serviço bgutil para JS challenge PO Token
  cookies.txt lido de Path(cache_dir)/"cookies.txt" se existir
  bgutil URL lida de os.environ.get("BGUTIL_BASE_URL", "") — sem mudança de assinatura (D-02)
  player_client=web_safari,web quando bgutil presente (clientes suportados pelo bgutil)
  player_client=android quando bgutil ausente (fallback degradado — datacenter IP pode ser bloqueado)
  Probe PIPE-06 (httpx.get) e classe BgutilUnavailable NÃO reintroduzidos (Wave 2 decisão mantida).

Output (D-05): JSON to stdout via __main__ (implemented in Plan 04).
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import essentia.standard as es
import imageio_ffmpeg
import librosa
import numpy as np
import yt_dlp


logger = logging.getLogger(__name__)

_FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
_FFMPEG_DIR = str(Path(_FFMPEG_PATH).parent)  # directory — for subprocess calls in validate_wav
_system_ffprobe = shutil.which("ffprobe")
if _system_ffprobe is None:
    logger.warning(
        "System ffprobe not found via shutil.which(); falling back to imageio-ffmpeg "
        "path: %s. Install ffmpeg system package for reliable ffprobe resolution.",
        str(Path(_FFMPEG_PATH).parent / "ffprobe"),
    )
# D-01: system ffprobe first; if unavailable, fall back to imageio-ffmpeg dir/ffprobe path.
# Note: when the system has no ffprobe and imageio-ffmpeg only ships the ffmpeg binary,
# _FFPROBE_PATH may point to a non-existent file. validate_wav handles this by falling
# back to the ffmpeg executable via the _YTDLP_FFMPEG_LOCATION path.
_FFPROBE_PATH = _system_ffprobe or str(Path(_FFMPEG_PATH).parent / "ffprobe")

# DEPLOY-01 fix: yt-dlp ffmpeg_location must point to the executable (not directory) when the
# imageio-ffmpeg binary has a versioned name (e.g. ffmpeg-linux-x86_64-v7.0.2) rather than the
# plain 'ffmpeg' name. When a directory is passed and neither 'ffmpeg' nor 'ffprobe' exist with
# plain names, yt-dlp raises "ffprobe and ffmpeg not found". Passing the executable path lets
# yt-dlp detect the binary and use ffmpeg as a ffprobe fallback via `ffmpeg -i`.
# If the system has ffmpeg on PATH, prefer it (gives proper ffprobe too).
_system_ffmpeg = shutil.which("ffmpeg")
_YTDLP_FFMPEG_LOCATION = _system_ffmpeg if _system_ffmpeg else _FFMPEG_PATH
_NODE_PATH = shutil.which("node")


def _enable_ytdlp_debug(ydl_opts: dict[str, Any]) -> None:
    """Enable yt-dlp verbose diagnostics without changing production defaults."""
    if os.environ.get("YTDLP_DEBUG", "").lower() in {"1", "true", "yes"}:
        ydl_opts["verbose"] = True


def _configure_youtube_js_runtime(ydl_opts: dict[str, Any]) -> None:
    """Enable Node for yt-dlp YouTube JS challenges when available."""
    if _NODE_PATH:
        ydl_opts["js_runtimes"] = {"node": {"path": _NODE_PATH}}
    else:
        logger.warning("AUTH: node runtime nao encontrado no PATH; yt-dlp pode falhar em desafios JS")


# Constants
MAX_DURATION_SEC = 900  # 15 minutes — locked by CORE-05 and D-10
TMP_PREFIX = "sg_"      # /tmp/sg_{12hex}.wav per D-08
WAV_TMP_DIR = Path("/tmp")


# Stage 0: Duration check (CORE-05, D-10)
def check_duration(url: str, cache_dir: str) -> dict[str, Any]:
    """Fetch yt-dlp metadata WITHOUT downloading; verify duration <= MAX_DURATION_SEC.

    Args:
        url: YouTube URL to inspect.
        cache_dir: Railway Volume path (de YTDLP_CACHE_DIR). Cookies serão lidos de
                   Path(cache_dir)/"cookies.txt" se existir.

    Returns:
        The yt-dlp info dict. Caller can read info['duration'] safely.

    Raises:
        ValueError: If the video duration exceeds MAX_DURATION_SEC (15 minutes),
                    or if duration metadata is missing.
    """
    # Phase 10.1 gap closure (plan 06): hybrid auth — bgutil URL lida do env (sem signature change D-02)
    bgutil_base_url = os.environ.get("BGUTIL_BASE_URL", "")
    # Clientes web requerem PO Token; bgutil 0.8.x suporta web_safari e web.
    player_clients = ["web_safari", "web"] if bgutil_base_url else ["android"]
    youtube_args: dict[str, list[str]] = {"player_client": player_clients}
    if bgutil_base_url:
        youtube_args["getpot_bgutil_baseurl"] = [bgutil_base_url]
    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 30,
        "noplaylist": True,
        "no_cache_dir": True,           # D-04: prevent stale nsig between Railway deploys
        "ffmpeg_location": _YTDLP_FFMPEG_LOCATION,  # executable path — see _YTDLP_FFMPEG_LOCATION
        # yt-dlp Python API expects nested extractor args, unlike the CLI string format.
        "extractor_args": {"youtube": youtube_args},
    }
    logger.warning(
        "AUTH: check_duration bgutil_base_url=%s player_client=%s",
        "set" if bgutil_base_url else "empty",
        ",".join(player_clients),
    )
    _configure_youtube_js_runtime(ydl_opts)
    # Cookies do Railway Volume — se existirem, yt-dlp usa autenticado (web_creator+mweb)
    # Híbrido: cookiefile E getpot_bgutil_baseurl coexistem nos ydl_opts
    if cache_dir:
        cookies_file = Path(cache_dir) / "cookies.txt"
        if cookies_file.exists():
            ydl_opts["cookiefile"] = str(cookies_file)
            logger.warning(
                "AUTH: check_duration usando cookiefile path=%s bytes=%s",
                cookies_file,
                cookies_file.stat().st_size,
            )
        else:
            logger.warning("AUTH: check_duration sem cookiefile existente path=%s", cookies_file)
    else:
        logger.warning("AUTH: check_duration sem YTDLP_CACHE_DIR/cache_dir")
    _enable_ytdlp_debug(ydl_opts)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.YoutubeDLError as e:
        logger.warning(
            "AUTH: check_duration yt-dlp falhou cookiefile_set=%s error=%s",
            "cookiefile" in ydl_opts,
            e,
        )
        raise RuntimeError(f"yt-dlp metadata failed: {e}") from e

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
def download_audio(url: str, cache_dir: str) -> Path:
    """Download YouTube audio and convert to WAV via yt-dlp's FFmpegExtractAudio postprocessor.

    Output: /tmp/sg_{12hex}.wav  (D-08). The intermediate audio file (webm/m4a) is
    cleaned up automatically by yt-dlp's postprocessor. On failure, any partial files
    matching /tmp/sg_{id}* are removed via try/finally (D-09).

    The final WAV is NOT deleted by this function — that is Phase 2's responsibility (D-09).

    Args:
        url: YouTube URL.
        cache_dir: Railway Volume path. Cookies lidos de Path(cache_dir)/"cookies.txt"
                   se existir. Se vazio, downloads sem autenticação (ios/mweb clients).

    Returns:
        Path to the resulting WAV file (/tmp/sg_{12hex}.wav).

    Raises:
        RuntimeError: If yt-dlp fails (network error, bot detection, expired cookies).
        FileNotFoundError: If the WAV file is not present after a successful download.
    """
    wav_id = uuid.uuid4().hex[:12]
    outtmpl_base = str(WAV_TMP_DIR / f"{TMP_PREFIX}{wav_id}")
    wav_path = Path(f"{outtmpl_base}.wav")

    # Phase 10.1 gap closure (plan 06): hybrid auth — bgutil URL lida do env (sem signature change D-02)
    bgutil_base_url = os.environ.get("BGUTIL_BASE_URL", "")
    # Clientes web requerem PO Token; bgutil 0.8.x suporta web_safari e web.
    dl_players = ["web_safari", "web"] if bgutil_base_url else ["android"]
    youtube_args: dict[str, list[str]] = {"player_client": dl_players}
    if bgutil_base_url:
        youtube_args["getpot_bgutil_baseurl"] = [bgutil_base_url]
    extractor_args: dict[str, dict[str, list[str]]] = {"youtube": youtube_args}
    logger.warning(
        "AUTH: download_audio bgutil_base_url=%s player_client=%s",
        "set" if bgutil_base_url else "empty",
        ",".join(dl_players),
    )

    # Cookies do Railway Volume — se existirem, yt-dlp usa autenticado (web_creator+mweb)
    cookies_file_path: str | None = None
    if cache_dir:
        cookies_file = Path(cache_dir) / "cookies.txt"
        if cookies_file.exists():
            cookies_file_path = str(cookies_file)
            logger.warning(
                "AUTH: download_audio usando cookiefile path=%s bytes=%s",
                cookies_file,
                cookies_file.stat().st_size,
            )
        else:
            logger.warning("AUTH: download_audio sem cookiefile existente path=%s", cookies_file)
    else:
        logger.warning("AUTH: download_audio sem YTDLP_CACHE_DIR/cache_dir")

    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl_base,  # NO %(ext)s — yt-dlp appends .wav after postprocessor (Pitfall 2)
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "noplaylist": True,
        "extractor_args": extractor_args,  # player_client + bgutil PO Token (híbrido)
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "no_cache_dir": True,           # D-04: prevent stale nsig between Railway deploys
        "retries": 3,                   # D-05: tolerate transient connection failures
        "fragment_retries": 3,          # D-05: tolerate transient fragment failures
        "http_chunk_size": 10485760,  # 10MB — avoids YouTube throttling on long downloads
        "ffmpeg_location": _YTDLP_FFMPEG_LOCATION,  # executable path — see _YTDLP_FFMPEG_LOCATION
    }
    _configure_youtube_js_runtime(ydl_opts)
    # Híbrido: cookiefile E getpot_bgutil_baseurl coexistem nos ydl_opts
    if cookies_file_path:
        ydl_opts["cookiefile"] = cookies_file_path
    _enable_ytdlp_debug(ydl_opts)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.YoutubeDLError as e:
        for f in WAV_TMP_DIR.glob(f"{TMP_PREFIX}{wav_id}*"):
            try:
                f.unlink()
            except OSError:
                pass
        raise RuntimeError(f"yt-dlp failed: {e}") from e
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

    # SEC-FILE-01: bloqueia leitura por outros usuários do sistema.
    os.chmod(wav_path, 0o600)
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

    # DEPLOY-01 fix: when system ffprobe is unavailable and imageio-ffmpeg ships only
    # the ffmpeg binary (versioned name, no ffprobe), _FFPROBE_PATH may not exist on disk.
    # Fall back to using ffmpeg with -i flag to extract duration from stderr.
    _use_ffmpeg_fallback = not Path(_FFPROBE_PATH).exists()
    if _use_ffmpeg_fallback:
        probe_exe = _YTDLP_FFMPEG_LOCATION
        probe_cmd = [probe_exe, "-i", str(wav_path)]
    else:
        probe_exe = _FFPROBE_PATH
        probe_cmd = [
            probe_exe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(wav_path),
        ]

    try:
        result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as e:
        raise ValueError(
            f"ffprobe/ffmpeg binary not found: {probe_exe}. "
            "Install FFmpeg >= 6.0 or ensure imageio-ffmpeg is installed."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ValueError(f"ffprobe timed out after 10s on {wav_path}") from e

    if _use_ffmpeg_fallback:
        # ffmpeg -i always exits non-zero; parse duration from stderr
        # Expected line: "  Duration: HH:MM:SS.ss, start: ..."
        stderr_text = result.stderr or ""
        dur_match = re.search(r"Duration:\s+(\d+):(\d+):([\d.]+)", stderr_text)
        if not dur_match:
            raise ValueError(
                f"ffmpeg -i could not determine duration of {wav_path}. "
                f"stderr excerpt: {stderr_text[:300]}"
            )
        h, m, s = int(dur_match.group(1)), int(dur_match.group(2)), float(dur_match.group(3))
        duration_str = str(h * 3600 + m * 60 + s)
    else:
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

    if duration > MAX_DURATION_SEC:
        raise ValueError(
            f"Video too long: {duration:.0f}s exceeds the 15-minute limit "
            f"({MAX_DURATION_SEC}s). SoundGrabber only accepts videos under 15 minutes."
        )

    return duration


# Stage 3a: Tuning detection (TUNING-01, TUNING-02)
def detect_tuning(wav_path: Path) -> float | None:
    """Detecta frequência de referência (concert pitch) do beat via HPSS + librosa.estimate_tuning.

    Aplica Harmonic-Percussive Source Separation (HPSS) para isolar o componente harmônico.
    Se a razão de energia harmônica for < 0.2 (beat puramente percussivo), retorna None —
    o resultado seria ruído, não um concert pitch mensurável.

    Args:
        wav_path: Path para o arquivo WAV.

    Returns:
        Frequência de afinação em Hz (float), ou None se o beat for essencialmente percussivo.
        Exemplo: 440.0 para A=440 padrão, 432.0 para A=432, None para trap sem melodia.
    """
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    # margin=2.0: HPSS mais restritivo — ruído branco (ratio ~0.05 < 0.2) → None corretamente;
    # sinal harmônico puro (ratio ~1.0) → passa o gate sem degradação.
    y_harmonic, _ = librosa.effects.hpss(y, margin=2.0)

    total_energy = float(np.sum(y**2))
    harm_energy = float(np.sum(y_harmonic**2))
    ratio = harm_energy / (total_energy + 1e-10)  # 1e-10: evita divisão por zero em silêncio puro

    if ratio < 0.2:
        return None  # beat puramente percussivo — tuning seria ruído

    raw_tuning = librosa.estimate_tuning(y=y_harmonic, sr=sr, resolution=0.01)
    return float(librosa.tuning_to_A4(raw_tuning))


# Stage 3b: BPM detection (PREC-01)
def detect_bpm(wav_path: Path) -> float:
    """BPM via Essentia RhythmExtractor2013 multifeature — mesmo algoritmo do Tunebat.

    Resistente a erros de octave (half-tempo trap): o modo multifeature funde múltiplas
    funções de onset e é built-in octave-resistant.

    CRÍTICO: sampleRate=44100 é obrigatório para RhythmExtractor2013. Valores incorretos
    produzem BPM ~50% ou ~200% do real, sem Python exception.

    Args:
        wav_path: Path para o arquivo WAV.

    Returns:
        BPM como Python float. Nunca numpy.float32 — float() defensivo aplicado.
    """
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    return float(bpm)  # float() defensivo: binding cp312 já retorna float, mas garante robustez futura


# Stage 3c: Key detection (PREC-02, PREC-03, PREC-05)
def detect_key(wav_path: Path, tuning_hz: float | None) -> tuple[str, float]:
    """Tonalidade via Essentia KeyExtractor(profileType='edma') com correção de tuning.

    CRÍTICO: tuning_hz deve ser passado APÓS detect_tuning() — não antes.
    O parâmetro tuningFrequency é de instanciação: os bins HPCP são computados
    uma única vez. Se tuning_hz for None (beat percussivo), usa 440.0 Hz como
    fallback neutro — KeyExtractor ainda funciona, apenas sem correção de pitch.

    Args:
        wav_path: Path para o arquivo WAV.
        tuning_hz: Frequência de referência em Hz retornada por detect_tuning(),
                   ou None para beat percussivo. Nunca passar None sem verificação.

    Returns:
        Tuple de (key_string, confidence) onde key_string é '<NOTA> <major|minor>'
        (ex: 'F# minor', 'A major') e confidence é float em [0.0, 1.0].
    """
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    freq = tuning_hz if tuning_hz is not None else 440.0
    key, scale, strength = es.KeyExtractor(
        profileType="edma",
        tuningFrequency=freq,
    )(audio)
    return str(f"{key} {scale}"), float(strength)


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
    """Executa o pipeline completo de análise e retorna o dict JSON-serializable.

    Pipeline order:
      1. validate_wav  — ffprobe sanity check + duration retrieval.
      2. detect_tuning — librosa HPSS: concert pitch Hz ou None se percussivo.
      3. detect_bpm    — Essentia RhythmExtractor2013(method='multifeature').
      4. detect_key    — Essentia KeyExtractor(profileType='edma', tuningFrequency=tuning_hz).
                         tuning_hz passado ANTES dos bins HPCP serem computados (PREC-03).
      5. key_to_camelot — lookup O(1) na tabela estática.
      6. Derivar bpm_half e bpm_double (aritmética pura).

    O WAV NÃO é deletado por esta função — Phase 2 gerencia o ciclo de vida (D-09).

    Args:
        wav_path: Path para um arquivo WAV produzido por download_audio().

    Returns:
        Dict com os seguintes campos (todos tipos Python nativos — JSON-safe):
            bpm           (float)        — BPM primário detectado
            bpm_half      (float)        — bpm / 2 arredondado a 1 decimal
            bpm_double    (float)        — bpm * 2 arredondado a 1 decimal
            key           (str)          — '<NOTA> <major|minor>' (ex: 'F# minor')
            camelot       (str)          — código Camelot (ex: '11A') ou '?' se não mapeado
            key_confidence (float)       — confiança do KeyExtractor em [0.0, 1.0]
            tuning_hz     (float | None) — concert pitch em Hz, ou None se beat percussivo
            duration_sec  (float)        — duração do arquivo em segundos (via ffprobe)
            wav_path      (str)          — path do WAV como string (não Path object)

    Raises:
        ValueError: Se validate_wav falhar (arquivo ausente, corrompido, ou erro de ffprobe).
    """
    wav_path = Path(wav_path)
    duration_sec = validate_wav(wav_path)
    tuning_hz = detect_tuning(wav_path)           # Step 2: ANTES de detect_key (PREC-03)
    bpm = detect_bpm(wav_path)                    # Step 3: Essentia
    key, key_confidence = detect_key(wav_path, tuning_hz)  # Step 4: tuning_hz já calculado
    camelot = key_to_camelot(key)

    return {
        "bpm":            round(float(bpm), 1),
        "bpm_half":       round(float(bpm) / 2, 1),
        "bpm_double":     round(float(bpm) * 2, 1),
        "key":            str(key),
        "camelot":        str(camelot),
        "key_confidence": float(key_confidence),
        "tuning_hz":      tuning_hz,    # float ou None — JSON-serializable (TUNING-03)
        "duration_sec":   round(float(duration_sec), 1),
        "wav_path":       str(wav_path),
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
    cache_dir = os.environ.get("YTDLP_CACHE_DIR", "")

    if not cache_dir:
        print(
            "WARNING: YTDLP_CACHE_DIR is empty. Downloads may fail with bot detection.",
            file=sys.stderr,
        )

    try:
        # Stage 0: pre-download duration check (CORE-05, D-10)
        info = check_duration(url, cache_dir)
        # Stage 1: download + WAV conversion (CORE-03, CORE-04)
        wav_path = download_audio(url, cache_dir)
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
