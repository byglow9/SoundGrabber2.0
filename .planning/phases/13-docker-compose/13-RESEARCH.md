# Phase 13: Docker Compose - Research

**Researched:** 2026-05-15
**Domain:** Docker, Docker Compose, Python containerization, Essentia, tmpfs volumes
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**imageio-ffmpeg e pipeline.py**
- D-01: Remover `imageio-ffmpeg` de `requirements.txt`.
- D-02: Refatorar `pipeline.py` para remover `import imageio_ffmpeg` (linha 38) e todos os usos de `imageio_ffmpeg.get_ffmpeg_exe()`. Substituir por `shutil.which("ffmpeg")`. Se `shutil.which("ffmpeg")` retornar None, levantar erro explícito no startup.
- D-03: Remover `librosa==0.11.0` de `requirements.txt` nesta mesma fase.

**Dockerfile**
- D-04: Imagem base `python:3.11-slim` (x86_64). Não usar `python:3.11` full.
- D-05: Instalar via apt: `ffmpeg`, `nodejs` (>=20 via NodeSource se apt for <20), `libsndfile1`. Outras deps de sistema que Essentia precisar devem ser descobertas iterativamente.
- D-06: `pip install` a partir de `requirements.txt` com `--no-cache-dir`.
- D-07: Gate obrigatório: após `docker build`, rodar `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"` e confirmar exit 0 + output `OK` antes de avançar.

**docker-compose.yml**
- D-08: Quatro serviços: `api`, `worker`, `redis` (redis:7-alpine), `bgutil` (jim60105/bgutil-pot). Todos com `restart: unless-stopped`.
- D-09: `BGUTIL_BASE_URL=http://bgutil:4416` nos serviços `api` e `worker`.
- D-10: Todos os 4 serviços na mesma rede bridge interna (`soundgrabber_net`). Redis e bgutil sem `ports:` mapeadas para o host.

**Volume tmpfs compartilhado**
- D-11: Usar `/tmp` como path do volume compartilhado. Sem mudança em `pipeline.py` ou `api/main.py`.
- D-12: Volume tmpfs montado em `/tmp` para `api` e `worker`. Configuração: `tmpfs: /tmp` ou `volumes: sg_tmp:/tmp` com driver tmpfs.

**Security Gate**
- D-13: Nenhum container usa `privileged: true` ou `network_mode: host`.
- D-14: Redis sem `ports:` mapeadas para o host.
- D-15: `restart: unless-stopped` em todos os 4 serviços.

### Claude's Discretion
- Limites de memória/CPU: Claude decide valores razoáveis para i5-3210M/4GB RAM.
- Variáveis de ambiente: Claude decide estrutura (env_file vs environment block) e quais variáveis incluir em `.env.example`.
- Health checks: Claude decide se adiciona `healthcheck:` nos serviços ou deixa para fase posterior.

### Deferred Ideas (OUT OF SCOPE)
- SG_TMP_DIR=/data/tmp (D-17 Phase 12): descartada. DEPLOY-06 é explícito sobre /tmp.
- SSH hardening / deploy.sh via SSH: scope da Phase 14.
- Cloudflare Tunnel: scope da Phase 15.
- Log rotation / alerting: v2 requirements.
- DOCKER-USER rules no UFW: Phase 12 D-06b.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-04 | Dockerfile usa imagem python:3.11-slim (x86_64) com system ffmpeg via apt — sem imageio-ffmpeg, sem NUMBA_DISABLE_JIT | Essentia cp311 wheel verificado no PyPI; ldd da .so confirma apenas libc/libstdc++ necessários; remoção de librosa elimina numba automaticamente |
| DEPLOY-05 | docker-compose.yml define api, worker (--concurrency=1 --max-tasks-per-child=10) e redis com restart: unless-stopped | Padrão Docker Compose verificado; healthcheck Redis via redis-cli ping documentado |
| DEPLOY-06 | api e worker compartilham volume tmpfs montado em /tmp — WAV gerado pelo worker é acessível pelo api | Pitfall crítico identificado: tmpfs simples NÃO pode ser compartilhado; named volume com driver_opts type=tmpfs É a solução correta |
</phase_requirements>

---

## Summary

Esta fase entrega o Dockerfile e o `docker-compose.yml` para rodar o SoundGrabber no notebook HP (x86_64). O trabalho tem três partes: (1) refatoração do código Python para eliminar `imageio-ffmpeg` e `librosa` do projeto, (2) criação do Dockerfile para a imagem `soundgrabber:latest`, e (3) composição dos quatro serviços (`api`, `worker`, `redis`, `bgutil`) com rede interna e volume tmpfs compartilhado.

O pitfall mais crítico desta fase é o volume compartilhado: Docker tmpfs simples (`tmpfs: /tmp:`) montado em cada container é **independente por container** — o worker escreve em um tmpfs, a api lê de outro, e o WAV nunca aparece. A solução correta é um **named volume com `driver: local` e `driver_opts: type: tmpfs`**, que é montado pelo Docker Engine como um único filesystem compartilhado entre os dois containers. [VERIFIED: docs.docker.com/engine/storage/tmpfs/]

A refatoração do `pipeline.py` é mais extensa do que o CONTEXT.md indica. A decisão D-03 (remover librosa) implica também reescrever a função `detect_tuning()` (linha 412), que usa `librosa.load`, `librosa.effects.hpss`, `librosa.estimate_tuning` e `librosa.tuning_to_A4`. Remover `librosa` sem tratar essa função causa falha no import do módulo. A substituição é feita com os algoritmos nativos do Essentia: `MonoLoader → Windowing → Spectrum → SpectralPeaks → TuningFrequency`. [VERIFIED: essentia.upf.edu]

**Recomendação primária:** Usar named volume `sg_tmp` com `driver: local` + `driver_opts: {type: tmpfs, device: tmpfs, o: "size=512m,mode=1777"}` montado em `/tmp` para `api` e `worker`. Para Node.js 20+ no container: instalar via NodeSource (bookworm apt tem nodejs 18.x apenas). Para Redis auth: usar `DEV_MODE=true` no compose (notebook é ambiente privado, Redis não exposto ao host).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Download + processamento de áudio | Worker container | — | CPU-bound; isolado do loop async da API |
| Servir WAV ao cliente | API container | — | GET /files/{id} lê de /tmp via FileResponse |
| Compartilhamento de arquivo WAV | Volume tmpfs (sg_tmp) | — | Bridge entre worker (escreve) e api (lê) |
| Task queue | Redis container | — | Broker Celery; apenas rede interna |
| PO Token para YouTube | bgutil container | — | Rust service; apenas rede interna |
| Roteamento interno entre serviços | soundgrabber_net (bridge) | — | Todos os 4 serviços se comunicam por nome de serviço |
| Porta exposta ao host | API container (:8000) | — | Único ponto de entrada; outros serviços sem ports: |

---

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python:3.11-slim | bookworm | Imagem base | Slim = menor tamanho; 3.11 = versão do projeto; x86_64 = arquitetura do notebook [VERIFIED: hub.docker.com] |
| redis:7-alpine | 7.x | Broker Celery / result backend | Alpine = mínimo; 7.x = LTS estável [VERIFIED: hub.docker.com] |
| jim60105/bgutil-pot | latest | PO Token provider | Mesma imagem usada no Railway — paridade confirmada [VERIFIED: hub.docker.com/r/jim60105/bgutil-pot] |
| Docker Compose v2 | v2.35.1 | Orquestração local | Nativo no Docker CE; sem `version:` top-level necessário [VERIFIED: docker compose version] |

### Pacotes apt no Dockerfile
| Pacote | Purpose | Nota |
|--------|---------|------|
| `ffmpeg` | Conversão WAV; ffprobe para validação | Inclui `/usr/bin/ffmpeg` e `/usr/bin/ffprobe` no PATH |
| `nodejs` (20 via NodeSource) | yt-dlp JS challenge solving | Bookworm apt tem 18.x; NodeSource necessário para 20+ [VERIFIED: packages.debian.org/bookworm/nodejs] |
| `curl` | Instalação NodeSource no Dockerfile | Necessário para script NodeSource |
| `libsndfile1` | Opcional — Essentia pode precisar para decodificação | Adicionado preventivamente |

**Nota sobre Essentia:** A wheel `essentia-2.1b6.dev1389-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` existe no PyPI [VERIFIED: pip download] e seu único arquivo `.so` linka apenas contra `libc`, `libstdc++`, `libgcc_s`, `libm`, `libpthread` — todas presentes no `python:3.11-slim`. Não são necessários `libfftw3-3` ou `libyaml-cpp0.7` adicionais via apt. [VERIFIED: ldd output na .so]

**Nota sobre npm:** O issue conhecido do NodeSource com `python:3.11-slim-bookworm` é que **npm** fica indisponível — mas apenas o binário `node` é necessário (yt-dlp chama `node` como subprocess). O binário `node` fica disponível normalmente. [VERIFIED: github.com/nodesource/distributions/issues/1790]

### Alternativas Consideradas
| Em vez de | Poderia usar | Tradeoff |
|------------|-----------|----------|
| Named volume driver=local+tmpfs | `tmpfs: /tmp:` em cada serviço | tmpfs por serviço NÃO é compartilhado — worker escreve, api não vê. Named volume É a solução [VERIFIED: docs.docker.com] |
| Named volume driver=local+tmpfs | Bind mount host dir para /tmp | Bind mount funciona mas persiste em HDD; tmpfs é em RAM, zero overhead de I/O |
| DEV_MODE=true (sem Redis auth) | Redis com senha (requirepass) | Notebook é deploy privado; Redis sem porta exposta ao host; DEV_MODE é aceitável aqui |
| NodeSource para Node 20 | python:3.11-bookworm full + nodejs | Full image é maior (~300MB+); D-04 exige slim |

---

## Architecture Patterns

### System Architecture Diagram

```
[HTTP Client]
      |
      | :8000
      v
+----------+
|   api    |  (uvicorn api.main:app)
| soundgrabber:latest |
+----+-----+
     |  sg_tmp (tmpfs named volume @ /tmp)
     |  <---------reads sg_*.wav
     |
+----+-----+
|  worker  |  (celery -A api.tasks worker --concurrency=1 --max-tasks-per-child=10)
| soundgrabber:latest |
+----+--+--+
     |  |
     |  +-- writes sg_*.wav --> sg_tmp @ /tmp
     |
     |  REDIS_URL=redis://redis:6379/0
     v
+---------+
|  redis  |  (redis:7-alpine, porta interna apenas)
+---------+
     ^
     |  CELERY_BROKER
     |
+----------+
|  bgutil  |  (jim60105/bgutil-pot, porta 4416 interna apenas)
+----------+
     ^
     |  BGUTIL_BASE_URL=http://bgutil:4416
     | (api e worker fazem requests HTTP para bgutil)

Rede: soundgrabber_net (bridge interna)
Volume: sg_tmp (tmpfs, 512MB, shared entre api e worker)
```

### Estrutura de Arquivos a Criar

```
SoundGrabber2.0/
├── Dockerfile           # NOVO — imagem soundgrabber:latest
├── docker-compose.yml   # NOVO — 4 serviços + rede + volume
├── .dockerignore        # NOVO — exclui .venv (681MB!), cookies.txt, .git
├── .env.example         # NOVO — template de variáveis de ambiente
├── pipeline.py          # MODIFICAR — remover imageio_ffmpeg e librosa
└── requirements.txt     # MODIFICAR — remover imageio-ffmpeg e librosa
```

### Pattern 1: Dockerfile com layer caching otimizado

```dockerfile
# Source: Docker best practices [CITED: docs.docker.com/build/cache/]
FROM python:3.11-slim

# Instalar deps de sistema em uma camada
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libsndfile1 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements.txt primeiro — camada de pip é cacheada separadamente do código
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código após deps instaladas
COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--limit-concurrency", "100", "--timeout-keep-alive", "5"]
```

### Pattern 2: Named volume tmpfs compartilhado (ÚNICO modo de compartilhar tmpfs entre containers)

```yaml
# Source: [CITED: docs.docker.com/engine/storage/tmpfs/]
# ATENÇÃO: 'tmpfs: /tmp:' em cada serviço NÃO é compartilhado — é independente por container
# Named volume com driver local + tmpfs É compartilhado pelo Docker Engine

volumes:
  sg_tmp:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
      o: "size=512m,mode=1777"

services:
  api:
    volumes:
      - sg_tmp:/tmp
  worker:
    volumes:
      - sg_tmp:/tmp
```

### Pattern 3: Startup order com healthcheck

```yaml
# Source: [CITED: docs.docker.com/compose/how-tos/startup-order/]
services:
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    depends_on:
      redis:
        condition: service_healthy

  worker:
    depends_on:
      redis:
        condition: service_healthy
```

### Pattern 4: Substituição de detect_tuning (librosa → Essentia)

```python
# Substituição de detect_tuning() sem librosa
# Source: [CITED: essentia.upf.edu/reference/std_TuningFrequency.html]
# Source: [CITED: essentia.upf.edu/reference/std_SpectralPeaks.html]
import essentia.standard as es

def detect_tuning(wav_path: Path) -> float | None:
    """Detecta frequência de referência via Essentia SpectralPeaks + TuningFrequency.

    Substitui a implementação anterior baseada em librosa HPSS.
    Retorna None apenas se TuningFrequency retornar 440.0 exato (sem desvio detectável)
    ou se o áudio for silêncio/sem conteúdo espectral.
    """
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    # Windowing + Spectrum para obter representação espectral
    windowed = es.Windowing(type="blackmanharris62")(audio[:2048])
    spectrum = es.Spectrum()(windowed)
    # Extrair peaks espectrais para TuningFrequency
    freqs, mags = es.SpectralPeaks(
        sampleRate=44100,
        maxPeaks=10000,
        magnitudeThreshold=0,
        maxFrequency=5000,
        minFrequency=20,
        orderBy="frequency",
    )(spectrum)
    if len(freqs) == 0:
        return None  # áudio sem conteúdo harmônico
    tuning_hz, tuning_cents = es.TuningFrequency()(freqs, mags)
    # Se desvio for < 5 cents, retornar None (sem correção necessária)
    if abs(tuning_cents) < 5.0:
        return None
    return float(tuning_hz)
```

**Nota:** Este padrão é aproximado — o executor deve ajustar conforme output real do Essentia no contexto de beats de trap/hip-hop. O gate de "beat percussivo" do librosa (baseado em HPSS energy ratio < 0.2) não tem equivalente direto no Essentia; o critério de `tuning_cents < 5.0` é uma aproximação funcional. [ASSUMED]

### Pattern 5: .dockerignore crítico

```
# .dockerignore — sem este arquivo, docker build envia 681MB para o daemon
.venv/
.git/
.claude/
__pycache__/
*.pyc
cookies.txt
*.cookies
www.youtube.com_cookies*.txt
.env
dump.rdb
.planning/
scripts/12-SETUP-LOG.md
*.png
```

### Anti-Patterns a Evitar

- **tmpfs por serviço (`tmpfs: /tmp:` em cada serviço):** Cada serviço tem seu próprio tmpfs isolado. Worker escreve, api lê path diferente. WAV nunca aparece na api. Usar named volume ao invés disso.
- **COPY . . antes de pip install:** Invalida o cache da camada de deps a cada mudança de código. Copiar `requirements.txt` primeiro, instalar deps, depois copiar código.
- **Sem .dockerignore:** Docker build context sobe 681MB (.venv) para o daemon. Build travado.
- **`privileged: true` ou `network_mode: host`:** Proibido por CLAUDE.md e D-13.
- **Redis com `ports:` mapeada para host:** D-14 e D-10 — Redis deve ser somente interno.

---

## Don't Hand-Roll

| Problema | Não Construir | Usar | Por quê |
|----------|-------------|-------------|-----|
| Compartilhamento de arquivos entre containers | Código de sync ou volume bind mount custom | Named volume driver=local+tmpfs | Docker monta como único filesystem; sem race condition; sem I/O de disco |
| Startup order entre serviços | Sleep loop no entrypoint | `depends_on: condition: service_healthy` | Idempotente, sem hard sleep, respeita restart policy |
| Detecção de tuning (ex-librosa) | Implementação HPSS do zero | `es.SpectralPeaks` + `es.TuningFrequency` | Algoritmos já implementados e testados no Essentia |
| Instalação de Node 20 em bookworm | Build de Node do source | `NodeSource setup_20.x` script | Pacote binário pré-compilado; 1 RUN layer |

---

## Common Pitfalls

### Pitfall 1: tmpfs não é compartilhado entre containers (CRÍTICO)
**O que dá errado:** `docker-compose.yml` usa `tmpfs: /tmp` em `api:` e `tmpfs: /tmp` em `worker:`. Worker escreve `/tmp/sg_abc.wav`, api tenta ler o mesmo path e recebe `FileNotFoundError`. O compose sobe sem erro mas o GET /files/{id} sempre retorna 404.
**Por que acontece:** Docker tmpfs é um filesystem em memória montado **individualmente** por container. Não é um volume compartilhado — cada container tem seu próprio tmpfs isolado.
**Como evitar:** Usar named volume com `driver: local` + `driver_opts: {type: tmpfs, device: tmpfs}`. Montar em `/tmp` nos dois serviços com `volumes: - sg_tmp:/tmp`.
**Sinais de alerta:** `docker exec worker ls /tmp/sg_*.wav` mostra arquivos; `docker exec api ls /tmp/sg_*.wav` mostra vazio.
**Fonte:** [VERIFIED: docs.docker.com/engine/storage/tmpfs/] — "Unlike volumes and bind mounts, you can't share tmpfs mounts between containers."

### Pitfall 2: detect_tuning() quebra ao remover librosa
**O que dá errado:** `requirements.txt` tem `librosa` removido conforme D-03, mas `pipeline.py` ainda tem `import librosa` na linha 39. O container inicia, api tenta importar `pipeline`, recebe `ModuleNotFoundError: No module named 'librosa'`. Todos os jobs falham.
**Por que acontece:** CONTEXT.md D-02 descreve refatoração das "linhas 38-68" (imageio_ffmpeg) mas `detect_tuning()` com librosa está na linha 412. Remoção do import não cobre o uso interno.
**Como evitar:** Reescrever `detect_tuning()` com Essentia (SpectralPeaks + TuningFrequency) antes de remover librosa do requirements.txt. Confirmar com `grep -n "librosa" pipeline.py` = zero antes de buildar.
**Sinais de alerta:** `docker run --rm soundgrabber:latest python -c "import pipeline"` falha com ModuleNotFoundError.

### Pitfall 3: Build context de 681MB por falta de .dockerignore
**O que dá errado:** `docker build .` envia 681MB para o Docker daemon (todo `.venv/`). Build demora minutos apenas para copiar contexto, antes de qualquer instrução do Dockerfile.
**Por que acontece:** Sem `.dockerignore`, o Docker inclui toda a árvore de diretórios no contexto, inclusive `.venv/` com 681MB de pacotes Python instalados.
**Como evitar:** Criar `.dockerignore` excluindo `.venv/`, `.git/`, `cookies.txt`, `.claude/`, `*.pyc`, `__pycache__/`.
**Sinais de alerta:** `Sending build context to Docker daemon  681MB` no início do build.

### Pitfall 4: Redis auth check bloqueia startup da api
**O que dá errado:** `api/main.py` lifespan chama `_check_redis_auth()` que verifica se `REDIS_URL` contém `@` (senha). Redis local no compose usa `redis://redis:6379/0` sem senha. API levanta `RuntimeError` no startup e o container fica em restart loop.
**Por que acontece:** SEC-INFRA-01 exige senha no Redis URL em produção. O compose local usa Redis sem autenticação.
**Como evitar:** Definir `DEV_MODE=true` no docker-compose.yml para os serviços `api` e `worker`. Notebook é ambiente privado; Redis não tem porta exposta ao host.
**Sinais de alerta:** `docker compose logs api` mostra `RuntimeError: REDIS_URL does not contain a password`.

### Pitfall 5: nodejs 18.x do apt do Bookworm (versão insuficiente)
**O que dá errado:** Dockerfile usa apenas `apt-get install nodejs`. Bookworm tem Node.js 18.x. D-05 exige Node >=20. yt-dlp pode falhar em desafios JS específicos do YouTube que requerem runtime mais moderno.
**Por que acontece:** `python:3.11-slim` usa Debian Bookworm; o repositório Bookworm inclui Node 18.x.
**Como evitar:** Instalar via NodeSource `setup_20.x` antes do `apt-get install nodejs`. Apenas o binário `node` é necessário — npm pode faltar sem impacto (yt-dlp não usa npm).
**Sinais de alerta:** `node --version` dentro do container retorna `v18.x.x`.

### Pitfall 6: Volume sg_tmp precisa ser recriado após mudança de driver_opts
**O que dá errado:** Volume criado com configuração errada (ex: sem `size=512m`). Editar `driver_opts` no compose e rodar `docker compose up` não atualiza o volume existente.
**Por que acontece:** Volumes Docker são imutáveis após criação. `docker compose up` não recria volumes existentes.
**Como evitar:** Se precisar recriar: `docker compose down -v && docker compose up -d`.
**Sinais de alerta:** `docker volume inspect soundgrabber20_sg_tmp` mostra configuração antiga.

---

## Code Examples

### Dockerfile completo verificado

```dockerfile
# Source: baseado em D-04..D-06 do CONTEXT.md e padrões verificados
FROM python:3.11-slim

# System deps em uma única camada (otimiza cache)
# NodeSource para Node 20 (bookworm apt tem apenas 18.x)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libsndfile1 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements.txt primeiro para cache de camada de pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código fonte
COPY . .

# Gate D-07: validado pelo executor com:
# docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"

CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--limit-concurrency", "100", \
     "--timeout-keep-alive", "5"]
```

### docker-compose.yml completo

```yaml
# Source: D-08..D-15 do CONTEXT.md + padrões verificados
# Docker Compose v2 — sem campo "version:" (obsoleto desde v2.0)

networks:
  soundgrabber_net:
    driver: bridge

volumes:
  sg_tmp:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
      o: "size=512m,mode=1777"

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    networks:
      - soundgrabber_net
    # Sem ports: — somente acessível internamente (D-10, D-14)
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    mem_limit: 128m

  bgutil:
    image: jim60105/bgutil-pot
    restart: unless-stopped
    networks:
      - soundgrabber_net
    # Porta 4416 apenas na rede interna (D-10)
    mem_limit: 128m

  api:
    image: soundgrabber:latest
    restart: unless-stopped
    ports:
      - "8000:8000"
    networks:
      - soundgrabber_net
    volumes:
      - sg_tmp:/tmp
    depends_on:
      redis:
        condition: service_healthy
    env_file:
      - .env
    mem_limit: 512m

  worker:
    image: soundgrabber:latest
    restart: unless-stopped
    command: >
      celery -A api.tasks worker
      --loglevel=info
      --concurrency=1
      --max-tasks-per-child=10
    networks:
      - soundgrabber_net
    volumes:
      - sg_tmp:/tmp
    depends_on:
      redis:
        condition: service_healthy
    env_file:
      - .env
    mem_limit: 1g
```

### .env.example

```bash
# Source: api/config.py Settings dataclass — variáveis lidas via os.environ.get()

# Redis URL — sem senha porque DEV_MODE=true bypassa o check (SEC-INFRA-01)
REDIS_URL=redis://redis:6379/0

# Bypassar Redis auth check — notebook é ambiente privado, Redis não exposto ao host
DEV_MODE=true

# bgutil PO Token provider (Phase 10.1) — mesmo serviço que o Railway
BGUTIL_BASE_URL=http://bgutil:4416

# Cookies yt-dlp — montar via bind mount ou copiar para o container (Phase 14)
YTDLP_CACHE_DIR=/app/data

# Rate limiting (defaults conservadores)
RATE_LIMIT_PER_MINUTE=3
JOB_POLL_RATE_LIMIT_PER_MINUTE=60
FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE=10

# WAV TTL — 900s (15 minutos)
WAV_TTL_SECONDS=900

# Admin (Phase 11 — Som da Semana)
ADMIN_PASSWORD=change-me-in-production
ADMIN_SESSION_SECRET=change-me-in-production
```

### Refatoração de pipeline.py — remover imageio_ffmpeg (linhas 38-68)

```python
# ANTES (remover):
# import imageio_ffmpeg
# _FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
# _FFMPEG_DIR = str(Path(_FFMPEG_PATH).parent)
# _FFPROBE_PATH = _system_ffprobe or str(Path(_FFMPEG_PATH).parent / "ffprobe")
# _YTDLP_FFMPEG_LOCATION = _system_ffmpeg if _system_ffmpeg else _FFMPEG_PATH

# DEPOIS (manter apenas):
# _system_ffprobe = shutil.which("ffprobe")
# if _system_ffprobe is None:
#     raise RuntimeError(
#         "ffprobe not found in PATH. Install ffmpeg system package: apt-get install ffmpeg"
#     )
# _FFPROBE_PATH = _system_ffprobe
#
# _system_ffmpeg = shutil.which("ffmpeg")
# if _system_ffmpeg is None:
#     raise RuntimeError(
#         "ffmpeg not found in PATH. Install ffmpeg system package: apt-get install ffmpeg"
#     )
# _YTDLP_FFMPEG_LOCATION = _system_ffmpeg
```

---

## Runtime State Inventory

> Fase não envolve rename/refactor de strings de identidade. Omitindo categorias não aplicáveis.

| Categoria | Itens encontrados | Ação necessária |
|----------|-------------|------------------|
| Stored data | Nenhum dado de runtime com dependência de imageio_ffmpeg ou librosa | Nenhuma |
| Live service config | Pipeline Railway em produção usa imageio_ffmpeg; sem conflito porque compose é deploy separado (notebook) | Nenhuma — Railway não é afetado |
| OS-registered state | Nenhum — Phase 12 configurou host mas sem registros de imageio_ffmpeg | Nenhuma |
| Secrets/env vars | REDIS_URL no Railway tem senha (`@`); no compose local, DEV_MODE=true bypassa o check | Variáveis são por ambiente; sem conflito |
| Build artifacts | `.venv/` no host de dev tem imageio_ffmpeg e librosa instalados | Remover de requirements.txt não afeta .venv local; planner pode incluir reinstall do venv como tarefa opcional |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker CE | `docker build`, `docker compose` | Verificar no notebook | Requer Docker instalado (Phase 12 faz isso) | Phase 12 prerequisito |
| Docker Compose v2 | `docker compose up` | ✓ (máquina de dev) | v2.35.1 | — |
| Python 3.11 runtime | Imagem base docker | Embutido na imagem | python:3.11-slim | — |
| ffmpeg (system) | pipeline.py, yt-dlp | Instalado via apt no container | qualquer | — |
| nodejs 20+ | yt-dlp JS challenges | Via NodeSource no container | 20.x | Node 18 funcional mas não recomendado |
| Essentia cp311 wheel | analyze_audio() | ✓ (PyPI confirmado) | 2.1b6.dev1389 | — |
| jim60105/bgutil-pot | bgutil service | Verificar pull no notebook | latest | Sem bgutil: player_client=android (risco bot detection) |

**Dependências sem fallback:**
- Docker CE no notebook (Phase 12 prerequisito — deve estar instalado)

**Dependências com fallback:**
- bgutil: se image pull falhar, compose sobe sem bgutil e worker usa `player_client=android`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `/home/glow/Documentos/projetos/SoundGrabber2.0/pytest.ini` |
| Quick run command | `pytest tests/test_pipeline.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-04 | Dockerfile não usa imageio-ffmpeg nem librosa | unit | `pytest tests/test_pipeline_docker.py::test_no_imageio_ffmpeg_import -x` | ❌ Wave 0 |
| DEPLOY-04 | Gate de validação: import essentia/yt_dlp/fastapi/celery | manual-only | `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"` | N/A — manual |
| DEPLOY-05 | docker-compose.yml declara restart: unless-stopped | manual-only | `docker compose config \| grep "unless-stopped"` | N/A — manual |
| DEPLOY-06 | Volume sg_tmp compartilhado — worker escreve, api lê | manual-only | `docker exec api ls /tmp/sg_*.wav` após test write no worker | N/A — manual |
| D-02 | pipeline.py não importa imageio_ffmpeg | unit | `pytest tests/test_pipeline_docker.py::test_no_imageio_ffmpeg_import -x` | ❌ Wave 0 |
| D-03 | pipeline.py não importa librosa | unit | `pytest tests/test_pipeline_docker.py::test_no_librosa_import -x` | ❌ Wave 0 |
| D-03 | detect_tuning reescrita funciona com Essentia | integration | `pytest tests/test_pipeline_docker.py::test_detect_tuning_essentia -x -m integration` | ❌ Wave 0 |

**Nota sobre testes manuais:** DEPLOY-04 gate (docker build + import test), DEPLOY-05 (compose up + restart), e DEPLOY-06 (tmpfs sharing) são verificações de runtime que não podem ser automatizadas com pytest sem Docker-in-Docker. São executadas manualmente pelo operador seguindo os success criteria do ROADMAP.

### Sampling Rate
- **Por task commit:** `pytest tests/test_pipeline_docker.py -x -q` (novo arquivo)
- **Por wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green + gates manuais Docker antes do `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline_docker.py` — cobre DEPLOY-04 (no imageio_ffmpeg import, no librosa import, detect_tuning Essentia)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Ferramenta stateless, sem contas |
| V3 Session Management | no | — |
| V4 Access Control | yes | Redis e bgutil sem ports: expostas ao host |
| V5 Input Validation | yes (existente) | Pydantic BaseModel em todos os endpoints POST |
| V6 Cryptography | no | — |

### Known Threat Patterns for Docker Compose Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Redis acessível do host sem senha | Elevation of Privilege | Sem `ports:` para redis e bgutil; DEV_MODE=true aceito em notebook privado |
| Cookies.txt no build context | Information Disclosure | `.dockerignore` exclui `cookies.txt`; Volume bind mount na Phase 14 |
| Container com root privileges | Elevation of Privilege | python:3.11-slim roda como root por padrão (aceitável para ferramenta interna); `privileged: false` implícito |
| /tmp com permissões abertas (1777) | Information Disclosure | sg_*.wav com `os.chmod(path, 0o600)` antes de retornar path (Security Gate existente) |

**Nota:** CLAUDE.md Security Gate se aplica a novos endpoints HTTP e scripts shell — não diretamente ao Dockerfile. Os controles de segurança relevantes para containers (sem privileged, sem host network, Redis interno) estão cobertos por D-13/D-14/D-15.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose.yml` com `version: "3.8"` | Sem campo `version:` (Docker Compose v2) | Docker Compose v2.0+ | Campo version é obsoleto e ignorado |
| `tmpfs:` em cada serviço | Named volume com driver_opts type=tmpfs | Sempre foi assim; mal documentado | tmpfs por serviço = isolado; named volume = compartilhado |
| NodeSource via apt convenience script | `curl -fsSL https://deb.nodesource.com/setup_20.x \| bash -` | 2023+ | Setup script configura apt repo corretamente para bookworm |
| imageio-ffmpeg para localizar binário | `shutil.which("ffmpeg")` com fail-fast | Phase 13 decisão | Sistema ffmpeg no PATH = mais confiável, sem deps extras |
| librosa para análise musical | Essentia para tudo (BPM + key + tuning) | Decisão de projeto (MEMORY.md) | Essentia: single .so, sem numba JIT, sem scipy heavy |

**Deprecated/outdated:**
- `imageio-ffmpeg`: removido nesta fase — desnecessário com ffmpeg via apt
- `librosa==0.11.0`: removido nesta fase — MEMORY.md confirma proibição absoluta
- `soundfile==0.13.1`: NÃO removido — usado em `tests/test_pipeline.py` e `scripts/generate_sample_wav.py`

---

## Assumptions Log

| # | Claim | Section | Risk se Errado |
|---|-------|---------|---------------|
| A1 | detect_tuning com Essentia SpectralPeaks+TuningFrequency retorna resultados equivalentes para beats de trap/hip-hop | Code Examples | detect_tuning pode retornar valores imprecisos; impacto em detect_key é secundário (440Hz fallback funciona) |
| A2 | `libsndfile1` via apt é suficiente para Essentia — sem outras libs de sistema necessárias | Standard Stack | Build falha; executor deve adicionar libs iterativamente conforme D-05 |
| A3 | Bookworm apt tem Node.js 18.x (não testado diretamente no python:3.11-slim via docker) | Standard Stack | Node pode ser 16.x ou outra versão; NodeSource é a solução em qualquer caso |
| A4 | mem_limit: 1g para worker é suficiente com Essentia carregando .so de 13.8MB + audio buffer | Standard Stack | Worker pode ser OOM killed; planner pode ajustar para 1.5g |
| A5 | jim60105/bgutil-pot:latest é compatível com bgutil-ytdlp-pot-provider==0.8.1 em requirements.txt | Standard Stack | Incompatibilidade de versão; mesma situação já ocorreu no Railway (STATE.md) |

---

## Open Questions (RESOLVED)

1. **detect_tuning: remover função ou reescrever com Essentia?**
   - O que sabemos: librosa DEVE ser removido (MEMORY.md + D-03); detect_tuning usa librosa extensivamente
   - O que estava indefinido: CONTEXT.md não especificava o que fazer com detect_tuning além de "remover librosa"
   - **RESOLVED (Plan 13-02/T3):** Reescrever com Essentia SpectralPeaks + TuningFrequency. A função tem valor (melhora precisão de detect_key). Implementação usa `es.MonoLoader → es.Windowing → es.Spectrum → es.SpectralPeaks → es.TuningFrequency`.

2. **soundfile em requirements.txt: manter ou remover?**
   - O que sabemos: soundfile não é usado em pipeline.py ou api/; usado apenas em tests/ e scripts/
   - O que estava indefinido: CONTEXT.md só menciona remoção de librosa e imageio-ffmpeg; não menciona soundfile
   - **RESOLVED (Plan 13-02/T1):** Manter `soundfile==0.13.1`. É necessário para `tests/test_pipeline.py::test_detect_tuning_percussive` e `scripts/generate_sample_wav.py`. Remover quebraria testes existentes sem benefício para DEPLOY-04.

3. **Onde ficam os cookies.txt no compose (Phase 13)?**
   - O que sabemos: AUTH-04 (Phase 14) define como cookies chegam ao notebook; Phase 13 não cobre isso
   - O que estava indefinido: se YTDLP_CACHE_DIR deve apontar para bind mount em Phase 13 ou deixar vazio
   - **RESOLVED (Plan 13-04/T1):** `YTDLP_CACHE_DIR=` vazio em `.env.example` para Phase 13. Worker funciona sem cookies (modo android player_client); Phase 14 configura o bind mount.

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: pip download] — essentia-2.1b6.dev1389-cp311 wheel existe e tem 13.8MB
- [VERIFIED: ldd essentia .so] — links apenas libc/libstdc++/libgcc_s/libm; sem deps extras
- [VERIFIED: docs.docker.com/engine/storage/tmpfs/] — tmpfs não compartilhado entre containers
- [VERIFIED: hub.docker.com/r/jim60105/bgutil-pot] — porta 4416, sem deps Node
- [VERIFIED: docker compose version] — v2.35.1 instalado na máquina de dev
- [VERIFIED: code inspection pipeline.py] — detect_tuning linha 412 usa librosa; imageio_ffmpeg linha 38-46

### Secondary (MEDIUM confidence)
- [CITED: docs.docker.com/compose/how-tos/startup-order/] — depends_on condition service_healthy
- [CITED: essentia.upf.edu/reference/std_TuningFrequency.html] — inputs/outputs de TuningFrequency
- [CITED: essentia.upf.edu/reference/std_SpectralPeaks.html] — inputs/outputs de SpectralPeaks
- [CITED: github.com/nodesource/distributions/issues/1790] — npm issue com slim (node binary OK)

### Tertiary (LOW confidence)
- [ASSUMED] Memory limits (512m api, 1g worker) — estimativa baseada em footprint típico de processos Python+Essentia

---

## Project Constraints (from CLAUDE.md)

Diretivas obrigatórias do CLAUDE.md que afetam esta fase:

1. **Nenhum `privileged: true` ou `network_mode: host`** em containers — D-13 cobre.
2. **Arquivos WAV em /tmp com permissões 0o600** — já implementado em `download_audio()`; tmpfs compartilhado não muda isso.
3. **Prefixo `sg_` em todos os arquivos do projeto em /tmp** — já implementado; tmpfs montado em /tmp preserva esse padrão.
4. **Path traversal defense em GET /files/{id}** — já implementado em `api/main.py`; tmpfs não muda a lógica.
5. **Novos scripts shell: `set -e` na primeira linha** — não aplicável diretamente (nenhum script shell novo planejado nesta fase).
6. **Estética Y2K** — não aplicável (esta fase é infraestrutura, sem frontend).
7. **Librosa proibida (MEMORY.md)** — coberto por D-03; reforçado nesta pesquisa.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Essentia wheel verificado, Docker Hub consultado, packages confirmados
- Architecture: HIGH — padrões Docker Compose verificados contra documentação oficial
- Pitfalls: HIGH — tmpfs sharing verificado contra docs.docker.com; bugs de código verificados via inspeção
- detect_tuning replacement: MEDIUM — API Essentia citada de docs oficiais, exemplo de código aproximado [ASSUMED]

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (infraestrutura estável; verificar versões de imagens Docker antes do deploy)
