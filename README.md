# SoundGrabber

Cole o link de um vídeo do YouTube, baixe o beat em WAV e veja o BPM e a tonalidade detectados — sem cadastro, direto, gratuito. Estética anos 2000.

> **Status:** Phase 1 (Processing Pipeline) — script CLI `pipeline.py` standalone. As fases 2-5 adicionam API HTTP e frontend.

## What This Phase Provides

`pipeline.py` é um script Python standalone que:

1. Recebe uma URL do YouTube como argumento.
2. Verifica que o vídeo tem 15 minutos ou menos.
3. Baixa o áudio com `yt-dlp` (autenticado com cookies + PO Token).
4. Converte para WAV lossless via FFmpeg (postprocessor do yt-dlp).
5. Analisa BPM (`librosa.feature.tempo`) e tonalidade (Krumhansl-Schmuckler sobre `chroma_cqt`).
6. Imprime um JSON em stdout com BPM, BPM/2, BPM*2, key, Camelot, duração e o caminho do WAV.

## Requirements

- **Python 3.11+** (testado em 3.12).
- **FFmpeg 6.0+** (`ffmpeg` e `ffprobe` no PATH).
- **libsndfile1** (no Linux: `sudo apt-get install -y libsndfile1`).
- **VPS com IP dedicado** para downloads do YouTube (IPs de datacenter são frequentemente bloqueados sem autenticação — ver "User Setup" abaixo).

## Install

```bash
# Sistema (Ubuntu / Debian)
sudo apt-get install -y ffmpeg libsndfile1

# Python deps
pip install -r requirements.txt
```

## User Setup (manual prerequisites)

Estes passos são humanos — não há CLI/API que os automatize.

### 1. Gerar `cookies.txt` no formato Netscape (D-01)

1. Faça login no YouTube em uma sessão de browser.
2. Instale uma extensão como [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
3. Em `youtube.com`, exporte como `cookies.txt`.
4. Coloque o arquivo na raiz do projeto (`./cookies.txt`).
5. **Importante:** `chmod 600 cookies.txt` e confirme que está no `.gitignore`.

### 2. Obter um PO Token (D-02)

PO Tokens GVS são tokens de sessão que o YouTube exige para servidores. Tipicamente expiram em 24-48h.

Caminho rápido (manual): rodar `yt-dlp -v <url>` em uma máquina local autenticada e copiar o token do output. Caminho de produção: usar [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) (requer Node.js >= 20).

### 3. Configurar variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
# Edite .env:
# YTDLP_COOKIES_FILE=./cookies.txt
# YTDLP_PO_TOKEN=<seu_token_aqui>
```

Ou exporte diretamente:

```bash
export YTDLP_COOKIES_FILE=./cookies.txt
export YTDLP_PO_TOKEN=<seu_token>
```

## Usage

```bash
python3 pipeline.py "https://www.youtube.com/watch?v=b1f6o0GMT8c"
```

### Output success (D-05)

```json
{
  "bpm": 140.0,
  "bpm_half": 70.0,
  "bpm_double": 280.0,
  "key": "F# minor",
  "camelot": "11A",
  "duration_sec": 183.0,
  "wav_path": "/tmp/sg_abc123def456.wav"
}
```

### Output errors

| `type` field | Quando ocorre | Exit code |
|--------------|---------------|-----------|
| `usage_error` | Sem argumento de URL | 1 |
| `config_error` | `YTDLP_COOKIES_FILE` não definido ou arquivo ausente | 1 |
| `validation_error` | Vídeo > 15min, ou ffprobe rejeita o arquivo | 1 |
| `download_error` | yt-dlp falha (rede, bot detection, token expirado) | 1 |

Em qualquer caso, **stdout é sempre JSON válido**.

## Tests

```bash
# Unit + integration (rápido, ~5s — sem rede)
pytest tests/ -m "not e2e" -q

# Todos os testes incluindo e2e (lento, ~3min — requer cookies + PO Token válidos)
pytest tests/ -q
```

## File Layout

| File | Role |
|------|------|
| `pipeline.py` | Único módulo do pipeline (3 funções importáveis + CLI) |
| `requirements.txt` | Versões pinadas de yt-dlp, librosa, soundfile, pytest |
| `.env.example` | Documentação dos env vars necessários |
| `.gitignore` | Exclui `cookies.txt`, `.env`, `/tmp/sg_*` |
| `tests/test_pipeline.py` | Testes unitários, integração e e2e |
| `tests/fixtures/sample.wav` | Tom de 5s @ 440Hz para testes offline |
| `scripts/generate_sample_wav.py` | Reprodução do fixture WAV |

## Known Limitations (Phase 1)

- **PO Token rotation** é manual — o token GVS expira em ~24-48h. Phase 3 adiciona detecção automática de expiração.
- **Sem rate limiting** — Phase 3 adiciona limite de 3 jobs/min/IP.
- **Sem HTTP API** — só CLI. Phase 2 adiciona FastAPI + Celery + Redis.
- **Sem frontend** — Phase 4 adiciona a UI. Phase 5 aplica a estética Y2K.

## Architecture (Phase 1 only)

```
URL (argv[1])
    │
    ▼
check_duration()         ── extract_info(download=False) — D-10
    │
    ▼
download_audio()         ── yt-dlp + cookies + PO Token + FFmpegExtractAudio postprocessor
    │
    ▼
validate_wav()           ── ffprobe sanity check
    │
    ▼
analyze_audio()
    ├─ detect_bpm()      ── librosa.feature.tempo (sr=22050, 90s window)
    ├─ detect_key()      ── librosa.feature.chroma_cqt + Krumhansl-Schmuckler
    ├─ key_to_camelot()  ── static 24-entry lookup table
    └─ bpm/2, bpm*2      ── arithmetic, no second analysis pass (D-06)
    │
    ▼
json.dumps(...) → stdout (D-05)
```

## License

Internal project. v1 ainda não é público.
