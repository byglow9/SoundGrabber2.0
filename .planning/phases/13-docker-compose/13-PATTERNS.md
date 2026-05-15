# Phase 13: Docker Compose - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 6 (4 novos, 2 modificados)
**Analogs found:** 6 / 6

---

## File Classification

| Arquivo Novo/Modificado | Role | Data Flow | Analog Mais Próximo | Qualidade |
|-------------------------|------|-----------|---------------------|-----------|
| `Dockerfile` | config | file-I/O | `nixpacks.toml` + `start.sh` | partial-match |
| `docker-compose.yml` | config | event-driven | `railway.toml` + `railpack.json` | partial-match |
| `.dockerignore` | config | file-I/O | `.gitignore` | role-match |
| `.env.example` | config | request-response | `.env.example` (existente) | exact |
| `pipeline.py` (modificar) | service | transform | `pipeline.py` (si mesmo — remoção cirúrgica) | exact |
| `requirements.txt` (modificar) | config | — | `requirements.txt` (si mesmo) | exact |
| `tests/test_pipeline_docker.py` | test | request-response | `tests/test_security.py` | role-match |

---

## Pattern Assignments

### `Dockerfile` (config, file-I/O)

**Analog primário:** `nixpacks.toml` — lista de aptPkgs do Railway é a base exata para o apt-get do Dockerfile.
**Analog secundário:** `start.sh` linhas 61-64 — validação de import essentia é o mesmo gate que o D-07 exige no container.

**Pattern de aptPkgs do nixpacks** (`nixpacks.toml` linhas 7-8):
```toml
[phases.setup]
aptPkgs = ["ffmpeg", "nodejs"]
```
Esse é o ponto de partida do `RUN apt-get install` no Dockerfile — mesma lista, mais `curl` (para NodeSource) e `libsndfile1`.

**Pattern de layer caching (ordem COPY):**
Copiar `requirements.txt` antes do código-fonte. A cada mudança de `.py`, a camada de `pip install` permanece cacheada. Copiar `COPY . .` apenas após `pip install`.

**Pattern de validação de binário no startup** (`start.sh` linhas 61-63):
```bash
if ! "$VENV/bin/python" -c "import essentia.standard" &>/dev/null; then
    log "Instalando essentia (necessário para BPM/key Essentia)..."
fi
```
O gate D-07 é a versão Docker desse mesmo pattern: `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"`. Mesmo conceito, contexto diferente.

**CMD do uvicorn** (`start.sh` linha 99 e `start-all.sh` linha 65-69):
```bash
# start-all.sh — parâmetros canônicos do projeto
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --limit-concurrency 100 \
    --timeout-keep-alive 5
```
O `CMD` do Dockerfile usa os mesmos flags: `--host 0.0.0.0`, `--port 8000`, `--limit-concurrency 100`, `--timeout-keep-alive 5`.

**NodeSource — pattern do notebook-setup.sh** (`scripts/notebook-setup.sh`):
O projeto já tem experiência com NodeSource no `notebook-setup.sh`. No Dockerfile a mesma abordagem se aplica via `curl -fsSL https://deb.nodesource.com/setup_20.x | bash -` antes do `apt-get install nodejs`.

---

### `docker-compose.yml` (config, event-driven)

**Analog primário:** `railway.toml` + `railway-worker.toml` — definem os dois serviços que o compose unifica e separa de novo.
**Analog secundário:** `start-all.sh` — comando celery canônico do projeto.

**Comando Celery canônico** (`start-all.sh` linha 63):
```bash
celery -A api.tasks worker --loglevel=info --concurrency=3 &
```
No compose, o worker usa `--concurrency=1` (DEPLOY-05) e `--max-tasks-per-child=10`. O módulo `api.tasks` e o `--loglevel=info` são idênticos.

**Healthcheck path do Railway** (`railway.toml` linha 15):
```toml
healthcheckPath = "/health"
healthcheckTimeout = 60
```
No compose, Redis usa `healthcheck` com `redis-cli ping`. A API não precisa de healthcheck no compose v1 — `depends_on: condition: service_healthy` no redis é suficiente.

**Padrão de variáveis de ambiente** (`api/config.py` linhas 25-44):
```python
redis_url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
dev_mode: bool = field(default_factory=lambda: os.environ.get("DEV_MODE", "false").lower() == "true")
bgutil_base_url: str = field(default_factory=lambda: os.environ.get("BGUTIL_BASE_URL", ""))
cache_dir: str = field(default_factory=lambda: os.environ.get("YTDLP_CACHE_DIR", ""))
```
O compose expõe exatamente essas variáveis via `env_file: .env`. As chaves são `REDIS_URL`, `DEV_MODE`, `BGUTIL_BASE_URL`, `YTDLP_CACHE_DIR`.

**Concurrency e limites do worker** (`start.sh` linha 83):
```bash
"$VENV/bin/python" -m celery -A api.tasks worker --loglevel=info --concurrency=3
```
No compose, reduzir para `--concurrency=1` conforme DEPLOY-05 (i5-3210M/4GB RAM — hardware limitado).

---

### `.dockerignore` (config, file-I/O)

**Analog:** `.gitignore` do projeto — as entradas críticas são um superconjunto das do `.gitignore`.

**Pattern do .gitignore** (`.gitignore` linhas 1-25):
```
# Secrets - NEVER commit
cookies.txt
.env
*.cookies

# Python
__pycache__/
*.py[cod]
.venv/
venv/
```
O `.dockerignore` replica essas entradas e adiciona as específicas de Docker:
- `.venv/` — 681MB, crítico para evitar build context enorme
- `.git/` — não presente no `.gitignore` mas obrigatório no `.dockerignore`
- `.claude/` — diretório de configuração local
- `.planning/` — contexto de planejamento não necessário no container
- `dump.rdb` — arquivo Redis local
- `*.png`, `bordas/` — assets de design
- `scripts/12-SETUP-LOG.md` — log de setup do host

---

### `.env.example` (config, request-response)

**Analog:** `.env.example` existente na raiz do projeto.

**Pattern atual do .env.example** (linhas 1-19):
```bash
# yt-dlp authentication for YouTube
YTDLP_COOKIES_FILE=./cookies.txt
YTDLP_PO_TOKEN=

# API + Celery (Phase 2)
REDIS_URL=redis://localhost:6379/0
WAV_TTL_SECONDS=900

# Som da Semana operator panel (Phase 11)
ADMIN_PASSWORD=change-me-locally
ADMIN_SESSION_SECRET=change-me-to-a-long-random-secret
FEATURED_FALLBACK_PATH=.data/featured-current.json
```

O novo `.env.example` (para compose) **substitui** o existente ou é um arquivo separado (`.env.compose.example`). Diferenças chave:
- `REDIS_URL=redis://redis:6379/0` — hostname `redis` (nome do serviço no compose), não `localhost`
- `DEV_MODE=true` — bypass do Redis auth check (Pitfall 4 do RESEARCH.md)
- `BGUTIL_BASE_URL=http://bgutil:4416` — hostname `bgutil` (nome do serviço no compose)
- Rate limits e WAV TTL permanecem os mesmos

**Pattern de DEV_MODE** (`start.sh` linha 34):
```bash
export DEV_MODE="${DEV_MODE:-true}"
```
O `start.sh` já define `DEV_MODE=true` como default local. O compose segue o mesmo padrão.

---

### `pipeline.py` — modificação (service, transform)

**Analog:** `pipeline.py` si mesmo — remoção cirúrgica de três blocos.

**Bloco a remover — import imageio_ffmpeg** (`pipeline.py` linha 38):
```python
import imageio_ffmpeg
```

**Bloco a remover — inicialização via imageio_ffmpeg** (`pipeline.py` linhas 46-68):
```python
_FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
_FFMPEG_DIR = str(Path(_FFMPEG_PATH).parent)
_system_ffprobe = shutil.which("ffprobe")
if _system_ffprobe is None:
    logger.warning(
        "System ffprobe not found via shutil.which(); falling back to imageio-ffmpeg "
        "path: %s. Install ffmpeg system package for reliable ffprobe resolution.",
        str(Path(_FFMPEG_PATH).parent / "ffprobe"),
    )
_FFPROBE_PATH = _system_ffprobe or str(Path(_FFMPEG_PATH).parent / "ffprobe")
# ...
_system_ffmpeg = shutil.which("ffmpeg")
_YTDLP_FFMPEG_LOCATION = _system_ffmpeg if _system_ffmpeg else _FFMPEG_PATH
```

**Substituição — fail-fast sem fallback** (padrão a introduzir):
```python
_system_ffprobe = shutil.which("ffprobe")
if _system_ffprobe is None:
    raise RuntimeError(
        "ffprobe not found in PATH. Install ffmpeg system package: apt-get install ffmpeg"
    )
_FFPROBE_PATH = _system_ffprobe

_system_ffmpeg = shutil.which("ffmpeg")
if _system_ffmpeg is None:
    raise RuntimeError(
        "ffmpeg not found in PATH. Install ffmpeg system package: apt-get install ffmpeg"
    )
_YTDLP_FFMPEG_LOCATION = _system_ffmpeg
```

**Bloco a remover — detect_tuning com librosa** (`pipeline.py` linhas 412-439):
```python
def detect_tuning(wav_path: Path) -> float | None:
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    y_harmonic, _ = librosa.effects.hpss(y, margin=2.0)
    total_energy = float(np.sum(y**2))
    harm_energy = float(np.sum(y_harmonic**2))
    ratio = harm_energy / (total_energy + 1e-10)
    if ratio < 0.2:
        return None
    raw_tuning = librosa.estimate_tuning(y=y_harmonic, sr=sr, resolution=0.01)
    return float(librosa.tuning_to_A4(raw_tuning))
```

**Substituição — detect_tuning com Essentia** (pattern de `detect_bpm` e `detect_key`, linhas 443-487):
```python
# detect_bpm usa o mesmo padrão: MonoLoader + algoritmo Essentia
def detect_bpm(wav_path: Path) -> float:
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    return float(bpm)

# detect_key usa o mesmo padrão: MonoLoader + algoritmo Essentia
def detect_key(wav_path: Path, tuning_hz: float | None) -> tuple[str, float]:
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    freq = tuning_hz if tuning_hz is not None else 440.0
    key, scale, strength = es.KeyExtractor(profileType="edma", tuningFrequency=freq)(audio)
    return str(f"{key} {scale}"), float(strength)
```

A reescrita de `detect_tuning` segue o mesmo padrão: `es.MonoLoader` → algoritmo Essentia (`es.SpectralPeaks` + `es.TuningFrequency`) → `return float(...)`.

**Import numpy** (`pipeline.py` linha 40):
```python
import numpy as np
```
Verificar se `np` ainda é usado após remover `detect_tuning`. Se o único uso for o `np.sum` nessa função, remover também o import de numpy.

---

### `requirements.txt` — modificação (config)

**Analog:** `requirements.txt` si mesmo.

**Linhas a remover:**
```
librosa==0.11.0
imageio-ffmpeg>=0.5.1
```

**Linhas a manter (verificar antes de remover numpy/scipy):**
```
soundfile==0.13.1   # usado em tests/test_pipeline.py e scripts/generate_sample_wav.py — MANTER
numpy>=2.0,<3.0     # verificar uso restante em pipeline.py após remoção de detect_tuning
scipy>=1.10         # verificar se ainda é dep de essentia ou outro módulo
```

---

### `tests/test_pipeline_docker.py` (test, request-response)

**Analog:** `tests/test_security.py` — mesmo padrão de estrutura de testes unitários do projeto.

**Pattern de header de arquivo de teste** (`tests/test_security.py` linhas 1-24):
```python
"""SoundGrabber Security Tests — Phase 6.

Stubs RED criados em Plan 01 (Wave 0). ...

Run: pytest tests/test_security.py -x -q
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest
```

**Pattern de docstring de teste** (`tests/test_security.py` linhas 39-57):
```python
def test_wav_file_permissions(tmp_path):
    """SEC-FILE-01: download_audio() deve aplicar os.chmod(wav_path, 0o600).

    RED: pipeline.py atual nao chama os.chmod apos criar o WAV. Wave 1 (Plan 02)
    adiciona `os.chmod(wav_path, 0o600)` ...
    """
```

**Testes a implementar em `test_pipeline_docker.py`:**
- `test_no_imageio_ffmpeg_import` — `import pipeline` não deve importar `imageio_ffmpeg`
- `test_no_librosa_import` — `import pipeline` não deve importar `librosa`
- `test_detect_tuning_essentia` — `detect_tuning()` funciona com Essentia (marcado `@pytest.mark.integration`)

**Pattern de verificação de import** (adaptar de `test_security.py`):
```python
def test_no_imageio_ffmpeg_import():
    """DEPLOY-04: pipeline.py não deve importar imageio_ffmpeg."""
    import ast
    import importlib.util
    source = Path("pipeline.py").read_text()
    tree = ast.parse(source)
    imports = [
        node.names[0].name if isinstance(node, ast.Import) else node.module
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert "imageio_ffmpeg" not in imports, "imageio_ffmpeg encontrado em pipeline.py"
```

---

## Shared Patterns

### Pattern de set -e em scripts shell

**Fonte:** `start.sh` linha 2, `start-all.sh` linha 17, `scripts/notebook-setup.sh` linha 2
**Aplica a:** Nenhum script shell novo nesta fase. Se o planner decidir criar um script de build/up, deve iniciar com `set -e` e `chmod 750 "$(realpath "$0")"`.

```bash
#!/usr/bin/env bash
set -e
chmod 750 "$(realpath "$0")"
```

### Pattern de variáveis de ambiente 12-factor

**Fonte:** `api/config.py` linhas 23-47
**Aplica a:** `.env.example`, `docker-compose.yml` (bloco `environment:` ou `env_file:`)

As chaves canônicas do projeto são:
```
REDIS_URL          — broker Celery
DEV_MODE           — bypass Redis auth check
BGUTIL_BASE_URL    — PO Token provider
YTDLP_CACHE_DIR    — diretório de cookies yt-dlp
RATE_LIMIT_PER_MINUTE
JOB_POLL_RATE_LIMIT_PER_MINUTE
FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE
WAV_TTL_SECONDS
ADMIN_PASSWORD
ADMIN_SESSION_SECRET
FEATURED_FALLBACK_PATH
```

### Pattern de segurança de arquivos em /tmp

**Fonte:** `pipeline.py` (existente), `tests/test_security.py` linhas 39-60
**Aplica a:** Comportamento inalterado — `os.chmod(path, 0o600)` já está em `download_audio()`. O tmpfs montado em `/tmp` no compose não altera esse comportamento.

---

## No Analog Found

Nenhum arquivo desta fase está totalmente sem analog. Todos têm pelo menos partial-match na base de código existente.

---

## Notas para o Planner

### Ordem de execução recomendada

A ordem importa por causa das dependências:

1. **Modificar `requirements.txt`** — remover `imageio-ffmpeg` e `librosa` antes de qualquer coisa
2. **Modificar `pipeline.py`** — remover imports e blocos que usam esses pacotes; reescrever `detect_tuning`
3. **Criar `tests/test_pipeline_docker.py`** — confirmar que nenhuma referência a imageio_ffmpeg/librosa permanece
4. **Criar `.dockerignore`** — antes do `docker build` para evitar context de 681MB
5. **Criar `Dockerfile`** — imagem `soundgrabber:latest`
6. **Gate D-07** — `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"`
7. **Criar `.env.example`** e `docker-compose.yml` — após imagem validada
8. **Gate final** — `docker compose up -d` + smoke test manual

### Armadilhas críticas (resumo das 6 do RESEARCH.md)

- **tmpfs NÃO é compartilhado entre containers** — usar named volume `sg_tmp` com `driver: local` + `driver_opts: type: tmpfs`
- **detect_tuning quebra** se librosa for removida sem reescrever a função
- **Build context de 681MB** sem `.dockerignore` — criar ANTES do `docker build`
- **Redis auth check bloqueia startup** — definir `DEV_MODE=true` no `.env` do compose
- **Node.js 18.x** no apt do bookworm — usar NodeSource `setup_20.x`
- **Volume sg_tmp imutável** após criação — `docker compose down -v` se driver_opts mudar

---

## Metadata

**Escopo de busca:** `/home/glow/Documentos/projetos/SoundGrabber2.0/` (raiz, `api/`, `scripts/`, `tests/`)
**Arquivos escaneados:** 12
**Data do mapeamento:** 2026-05-15
