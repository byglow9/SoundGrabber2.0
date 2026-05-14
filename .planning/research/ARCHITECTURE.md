# Architecture: SoundGrabber no Raspberry Pi 3B

**Milestone:** v1.3 — Raspberry Pi Hosting
**Researched:** 2026-05-14
**Confidence geral:** MEDIUM (padrões Docker/Compose HIGH; limitação Essentia no ARM confirmada HIGH; Tailscale host-network MEDIUM por falta de documentação oficial explícita para o cenário)

---

## Diagrama de Componentes

```
╔══════════════════════════════════════════════════════════════════════╗
║  Raspberry Pi 3B — linux/arm64 (Raspberry Pi OS 64-bit)              ║
║                                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐  ║
║  │  Docker Compose stack (bridge network: sg_net)                   │  ║
║  │                                                                   │  ║
║  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │  ║
║  │  │   redis      │    │    api       │    │    worker        │   │  ║
║  │  │  (broker +   │◄───│  (FastAPI +  │    │  (Celery +       │   │  ║
║  │  │   backend)   │    │   uvicorn)   │    │   pipeline)      │   │  ║
║  │  │              │    │   :8000      │    │   concurrency=1  │   │  ║
║  │  │  mem: 128m   │    │   mem: 256m  │    │   mem: 512m      │   │  ║
║  │  └──────────────┘    └──────┬───────┘    └────────┬─────────┘   │  ║
║  │         ▲                   │                      │              │  ║
║  │         └───────────────────┴──────────────────────┘              │  ║
║  │                    redis://redis:6379/0                            │  ║
║  │                                                                   │  ║
║  │  Volumes:                                                          │  ║
║  │    sg_cookies  → /data/yt-dlp-cache  (cookies.txt)               │  ║
║  │    sg_featured → /data/featured      (.data/)                    │  ║
║  │    sg_tmp      → /tmp (tmpfs, WAV temporários compartilhados)     │  ║
║  └─────────────────────────────────────────────────────────────────┘  ║
║                                                                        ║
║  Tailscale (host, systemd)                                             ║
║    tailscale0 interface → acesso SSH pelo operador                     ║
║    porta 8000 acessível via IP Tailscale do Pi (100.x.x.x:8000)       ║
║                                                                        ║
║  [Opcional] cloudflared (container na sg_net)                          ║
║    Cloudflare Tunnel → expõe :8000 publicamente via domínio CF        ║
╚══════════════════════════════════════════════════════════════════════╝
                              │
                    internet residencial
                    (IP doméstico — não datacenter)
```

---

## Decisão Crítica de Arquitetura: ARM64, não ARM32

### Problema Central: Essentia sem wheel ARM32

A biblioteca `essentia` (usada para BPM e key detection em `pipeline.py`) **não distribui wheels para arm32/armhf no PyPI**. Confirmado na página PyPI: wheels disponíveis apenas para `manylinux x86_64`, `macOS x86_64` e `macOS ARM64`. Tentar `pip install essentia` em `linux/arm/v7` resulta em falha de compilação — sem wheel pré-compilado, pip tenta build do fonte e falha por dependências C++ complexas.

### Solução: Raspberry Pi OS 64-bit + imagens arm64

O Raspberry Pi 3B tem CPU BCM2837 (Cortex-A53, ARMv8), capaz de rodar OS 64-bit. Com Raspberry Pi OS 64-bit instalado:

- Docker usa a plataforma `linux/arm64` (aarch64)
- `essentia` tem wheel `manylinux2014_aarch64` disponível no PyPI
- Todas as outras dependências (librosa, numpy, scipy, yt-dlp) têm wheels arm64

**Instrução para o operador — verificar antes de qualquer coisa:**
```bash
uname -m   # deve retornar: aarch64
```
Se retornar `armv7l`, o OS é 32-bit e precisa ser reflashado com Raspberry Pi OS 64-bit (disponível em raspberrypi.com/software).

**Confiança:** HIGH — confirmado diretamente via PyPI da Essentia e documentação oficial do Raspberry Pi.

---

## Tailscale: Integração via Host (Sem Sidecar no Compose)

### Contexto: Tailscale já instalado no Pi como serviço systemd

O Tailscale já está no Pi. Isso simplifica radicalmente a arquitetura — não é necessário adicionar um container Tailscale ao compose.

**Como funciona:**
- O Pi tem um IP Tailscale (ex: `100.x.x.x`)
- O container `api` expõe a porta 8000 com binding `0.0.0.0:8000:8000`
- O Tailscale no host roteia `100.x.x.x:8000` para `0.0.0.0:8000` do host
- O host encaminha para o container via port mapping
- SSH para deploy: `ssh user@100.x.x.x` funciona sem nenhuma configuração Docker

```
Operador → SSH → 100.x.x.x:22 → Pi host → shell → docker exec/logs
Browser  → HTTP → 100.x.x.x:8000 → Pi host → port mapping → api:8000
```

**O que NÃO fazer:** Não adicionar container Tailscale sidecar ao compose. O sidecar requer `/dev/net/tun`, `cap_add: NET_ADMIN`, volume de estado Tailscale e `network_mode: service:ts-*` nos outros containers — complexidade desnecessária quando o Tailscale no host já resolve tudo.

**Confiança:** MEDIUM — padrão correto e lógico, mas documentação oficial do Tailscale foca no caso sidecar. O caso "Tailscale no host, containers com port binding" é o funcionamento padrão do Docker sem configuração especial de rede.

---

## docker-compose.yml Completo

```yaml
# SoundGrabber — Raspberry Pi 3B (linux/arm64)
# Pre-requisito: Raspberry Pi OS 64-bit, Tailscale instalado no host como servico systemd

services:

  redis:
    image: redis:7-alpine
    # redis:7-alpine tem suporte arm64 nativo (manifest multi-arch)
    restart: unless-stopped
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD}
      --maxmemory 128mb
      --maxmemory-policy allkeys-lru
      --save ""
      --appendonly no
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - sg_net
    deploy:
      resources:
        limits:
          memory: 160m
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    logging:
      driver: "json-file"
      options:
        max-size: "5m"
        max-file: "2"

  api:
    build:
      context: .
      dockerfile: Dockerfile
    image: soundgrabber:latest
    restart: unless-stopped
    ports:
      # 0.0.0.0 para Tailscale no host rotear 100.x.x.x:8000 para o container
      # Mudar para 127.0.0.1:8000:8000 se usar Cloudflare Tunnel (cloudflared na sg_net)
      - "0.0.0.0:8000:8000"
    environment:
      - REDIS_URL=redis://default:${REDIS_PASSWORD}@redis:6379/0
      - YTDLP_CACHE_DIR=/data/yt-dlp-cache
      - FEATURED_FALLBACK_PATH=/data/featured/featured-current.json
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - ADMIN_SESSION_SECRET=${ADMIN_SESSION_SECRET}
      - DEV_MODE=false
      - BGUTIL_BASE_URL=${BGUTIL_BASE_URL:-}
      - WAV_TTL_SECONDS=900
      - RATE_LIMIT_PER_MINUTE=3
      - MAX_QUEUE_DEPTH=20
    volumes:
      - sg_cookies:/data/yt-dlp-cache
      - sg_featured:/data/featured
      - sg_tmp:/tmp
    networks:
      - sg_net
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 256m
    command: >
      uvicorn api.main:app
      --host 0.0.0.0
      --port 8000
      --workers 1
      --limit-concurrency 20
      --timeout-keep-alive 5
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  worker:
    image: soundgrabber:latest
    restart: unless-stopped
    environment:
      - REDIS_URL=redis://default:${REDIS_PASSWORD}@redis:6379/0
      - YTDLP_CACHE_DIR=/data/yt-dlp-cache
      - DEV_MODE=false
      - BGUTIL_BASE_URL=${BGUTIL_BASE_URL:-}
      - YTDLP_DEBUG=${YTDLP_DEBUG:-false}
    volumes:
      - sg_cookies:/data/yt-dlp-cache
      - sg_tmp:/tmp
    networks:
      - sg_net
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          # librosa + essentia + numpy num WAV de 15min = ~300-400MB pico
          memory: 512m
    command: >
      celery -A api.tasks worker
      --loglevel=info
      --concurrency=1
      --max-tasks-per-child=10
    healthcheck:
      test: ["CMD", "celery", "-A", "api.tasks", "inspect", "ping",
             "-d", "celery@$$HOSTNAME", "--timeout", "5"]
      interval: 30s
      timeout: 15s
      retries: 3
      start_period: 90s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  redis_data:
    driver: local
  sg_cookies:
    driver: local
  sg_featured:
    driver: local
  sg_tmp:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
      o: "size=512m,mode=1777"

networks:
  sg_net:
    driver: bridge
```

---

## Dockerfile para ARM64

O projeto não tem Dockerfile. Ele precisa ser criado como **componente novo**.

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

# Dependencias de sistema: ffmpeg (yt-dlp + pipeline), nodejs (bgutil JS challenge)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias Python (cache layer eficiente — reconstrui so se requirements.txt mudar)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo fonte
COPY api/ api/
COPY pipeline.py .
COPY static/ static/

# Diretorios de dados (volumes montados sobrescrevem em runtime)
RUN mkdir -p /data/yt-dlp-cache /data/featured /tmp

# Usuario nao-root para SEC-FILE-01 compliance
RUN useradd -m -u 1000 sguser && chown -R sguser:sguser /app /data
USER sguser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**Por que `python:3.11-slim-bookworm`:**
- Tem manifest multi-arch incluindo `linux/arm64` no Docker Hub
- Python 3.11 = versao atual do projeto (CLAUDE.md)
- Debian 12 (bookworm) = glibc 2.36+ compativel com manylinux wheels

**Por que ffmpeg do APT e nao imageio-ffmpeg:**
Com ffmpeg no PATH do sistema, `shutil.which("ffmpeg")` e `shutil.which("ffprobe")` funcionam. O codigo em `pipeline.py` ja prefere o ffmpeg do sistema (`_system_ffmpeg = shutil.which("ffmpeg")`). Sem ambiguidade de path versionado como no Railway.

**Por que nodejs:**
`bgutil-ytdlp-pot-provider` requer Node para o JS challenge. `pipeline.py` usa `shutil.which("node")` e emite warning se ausente. Com Node na imagem, bgutil funciona se `BGUTIL_BASE_URL` for configurado.

---

## Ponto de Integracao Critico: Volume `/tmp` Compartilhado

### O Problema

No Railway, `api` e `worker` sao processos no mesmo container (start.sh sobe ambos). No Docker Compose, sao containers separados com `/tmp` isolados.

O worker escreve `/tmp/sg_{hex}.wav`. A rota `GET /files/{id}` no container `api` tenta ler o mesmo caminho. Sem `/tmp` compartilhado, o download retorna 410 (arquivo nao encontrado) sempre.

### A Solucao: Volume tmpfs compartilhado

O volume `sg_tmp` definido com `driver_opts.type: tmpfs` resolve isso:
- Ambos `api` e `worker` montam `sg_tmp:/tmp`
- Arquivos escritos pelo worker sao visiveis para o api
- tmpfs = RAM, nao SD card — preserva vida util do cartao
- 512m de limite = suficiente para ~3 WAVs de 15min simultaneos

### Implicacao de Seguranca

Com `/tmp` compartilhado entre containers, os arquivos `sg_*.wav` do worker ficam visiveis no api container. O sweeper em `api/main.py` limpa `/tmp/sg_*` — correto, pois o api e o responsavel pelo ciclo de vida (D-09). `os.chmod(wav_path, 0o600)` no worker ainda aplica — arquivos 600 dentro do tmpfs compartilhado.

**Este ponto de integracao nao tem paralelo no Railway e nao foi testado. Requer validacao E2E antes de considerar o milestone completo.**

---

## Gestao de Memoria: Orcamento do Pi 3B (1GB)

| Servico | Limite compose | Uso tipico | Pico estimado |
|---------|----------------|------------|---------------|
| redis | 160m | ~30m | ~80m |
| api | 256m | ~120m | ~200m |
| worker | 512m | ~150m idle | ~400m (librosa+essentia) |
| SO + Docker daemon | sem limite | ~150m | ~200m |
| **Total** | — | ~450m | **~880m** |

Pico de 880m cabe no 1GB com margem de ~120m. Seguro para operacao normal.

**AVISO:** Pi 3B com Raspberry Pi OS 32-bit tem kernel sem suporte a memory cgroup (`docker info` mostra "No memory limit support"). Com OS 64-bit e kernel recente, isso nao ocorre. Verificar apos setup: `docker info | grep -i memory`.

**Configurar swap como seguranca:**
```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
sudo dphys-swapfile setup && sudo dphys-swapfile swapon
```
512MB de swap no SD card como ultima linha de defesa — nao para uso regular.

---

## Racionalidade das Configuracoes Criticas

**`concurrency=1` no Celery worker:**
librosa + essentia num WAV de 15min usa ~300-400MB e satura um core por 30-60s. Com `concurrency=2`, dois jobs simultaneos excedem o limite de 512m do container e causam OOM kill. `concurrency=1` e o unico valor seguro para 1GB de RAM total.

**`--max-tasks-per-child=10` no Celery:**
Librosa e Essentia alocam buffers em C que nao sao totalmente liberados entre tasks no mesmo processo Python. Reiniciar o processo worker a cada 10 jobs previne acumulo gradual de memoria.

**`workers 1` no uvicorn:**
Com Celery como backend de processamento, uvicorn nao precisa de multiplos workers. FastAPI serve apenas requests de controle (submit, polling, download) — tudo leve. Multiplos workers uvicorn no Pi 3B desperdicam ~120m de RAM sem beneficio.

**`MAX_QUEUE_DEPTH=20`:**
Reduzido de 50 (Railway) para 20 (Pi). Com 1 worker Celery e ~60s por job, 20 jobs em queue = ~20min de espera. Acima disso, retornar 503 e melhor do que acumular backlog sem previsao de conclusao.

---

## Volumes: Estrutura e Responsabilidades

| Volume | Caminho no container | Conteudo | Persistencia |
|--------|---------------------|----------|-------------|
| `sg_cookies` | `/data/yt-dlp-cache` | `cookies.txt` | Permanente — atualizado pelo operador |
| `sg_featured` | `/data/featured` | `featured-current.json` | Permanente — painel Yonkou |
| `sg_tmp` | `/tmp` | WAVs temporarios `sg_*.wav` | Efemero — tmpfs, perdido no restart |
| `redis_data` | `/data` (Redis) | Vazio — Redis sem persistencia | Descartavel |

**Como popular `sg_cookies` no primeiro deploy:**
```bash
# Metodo 1: docker cp (requer container api rodando)
docker cp /caminho/local/cookies.txt soundgrabber-api-1:/data/yt-dlp-cache/cookies.txt

# Metodo 2: via volume diretamente (container nao precisa estar rodando)
docker run --rm -v soundgrabber_sg_cookies:/data alpine \
  sh -c "cat > /data/cookies.txt" < /caminho/local/cookies.txt
```

---

## Cloudflare Tunnel: Componente Opcional

Para exposicao publica (alem do Tailscale privado), adicionar ao compose:

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    # cloudflared tem imagem arm64 oficial no Docker Hub
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    networks:
      - sg_net
    depends_on:
      api:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 64m
    logging:
      driver: "json-file"
      options:
        max-size: "5m"
        max-file: "2"
```

**Configuracao no Cloudflare Dashboard:**
- Tunnel aponta para `http://api:8000` (DNS interno Docker na sg_net)
- cloudflared esta na mesma rede bridge, resolve o hostname `api` automaticamente

**Com Cloudflare Tunnel ativo:**
- Mudar port binding do `api` de `0.0.0.0:8000:8000` para `127.0.0.1:8000:8000`
- Acesso publico via dominio Cloudflare
- Acesso de debug/operacao via Tailscale continua funcionando
- IP residencial nunca exposto publicamente

**Orcamento com cloudflared:** +64m de RAM → total pico ~944m. Ainda dentro do 1GB.

---

## Arquivo .env do Pi

```bash
# /home/pi/soundgrabber/.env — NAO commitar no git (.gitignore)

# Redis
REDIS_PASSWORD=<gerar: openssl rand -hex 32>

# Admin painel Yonkou
ADMIN_PASSWORD=<senha-do-operador>
ADMIN_SESSION_SECRET=<gerar: openssl rand -hex 32>

# yt-dlp auth
# BGUTIL_BASE_URL so necessario se bgutil estiver rodando separado
# Com IP residencial, testar sem bgutil primeiro
BGUTIL_BASE_URL=

# Debug yt-dlp (ativar so para troubleshooting)
YTDLP_DEBUG=false

# Cloudflare (opcional)
CLOUDFLARE_TUNNEL_TOKEN=
```

---

## Fluxo de Deploy

### Deploy inicial (primeira vez)

```
1. [Pi] Confirmar SO 64-bit:    uname -m → aarch64
2. [Pi] Instalar Docker + Compose plugin
3. [Pi] Configurar swap 512MB
4. [Pi] git clone <repo> ~/soundgrabber
5. [Pi] Criar ~/soundgrabber/.env com segredos
6. [Pi] docker compose build    # ~10-20min primeira vez
7. [Pi] docker compose up -d redis
8. [Pi] docker compose ps       # aguardar redis healthy
9. [Pi] docker compose up -d api worker
10. [Pi] Popular cookies (ver secao Volumes acima)
11. [Pi] Testar local: curl http://localhost:8000/health
12. [SSH] Testar Tailscale: curl http://100.x.x.x:8000/health
13. [E2E] POST /jobs com URL de beat → GET /jobs/{id} → GET /files/{id}
```

### Script de atualizacao (deploy.sh)

```bash
#!/usr/bin/env bash
# Executar via: ssh pi@100.x.x.x 'bash ~/soundgrabber/deploy.sh'
set -e

PROJECT_DIR="${PROJECT_DIR:-$HOME/soundgrabber}"

echo "[deploy] Pulling latest code..."
git -C "$PROJECT_DIR" pull --ff-only

echo "[deploy] Building new image..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" build

echo "[deploy] Restarting api and worker..."
# Redis NAO reinicia — preserva queue e resultados de jobs em andamento
docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d --no-deps worker api

echo "[deploy] Waiting for api health..."
timeout 120 bash -c 'until curl -sf http://localhost:8000/health; do sleep 3; done'

echo "[deploy] Done."
docker compose -f "$PROJECT_DIR/docker-compose.yml" ps
```

**Ordem de restart:**
1. `redis` — NUNCA reiniciar durante deploy (jobs em andamento perdem broker)
2. `worker` — reiniciar antes do `api` para evitar fila sem consumidor durante gap
3. `api` — reiniciar por ultimo

---

## Novo vs Modificado

| Componente | Status | Descricao |
|------------|--------|-----------|
| `Dockerfile` | **NOVO** | Nao existe no projeto — criar do zero |
| `docker-compose.yml` | **NOVO** | Projeto usa `start.sh` para dev local |
| `.env` (no Pi) | **NOVO** | Fora do git — segredos de producao |
| `deploy.sh` | **NOVO** | Script de atualizacao via SSH |
| `pipeline.py` | **SEM MUDANCA** | `YTDLP_CACHE_DIR` ja lido do env |
| `api/main.py` | **SEM MUDANCA** | `DEV_MODE=false` ativa validacoes de producao |
| `api/config.py` | **SEM MUDANCA** | Settings 100% via env var |
| `requirements.txt` | **VERIFICAR** | `essentia==2.1b6.dev1389` — confirmar wheel arm64 disponivel antes do build |
| `start.sh` | **NAO USADO** | Substituido pelo compose em producao; manter para dev local |
| `nixpacks.toml`, `railway.toml` | **NAO USADO** | Railway-specific; ignorados pelo compose |

---

## Riscos e Mitigacoes

### Risco 1: Essentia wheel arm64 da versao pinada (ALTO)

`essentia==2.1b6.dev1389` e uma versao de desenvolvimento. Versoes dev podem nao ter wheel para todas as plataformas.

**Mitigacao:** Verificar antes do build:
```bash
pip download essentia==2.1b6.dev1389 \
  --platform manylinux2014_aarch64 \
  --python-version 311 \
  --only-binary :all: \
  --no-deps \
  --dry-run
```
Se falhar, atualizar para versao estavel mais recente da Essentia com wheel arm64.

### Risco 2: Build time longo no Pi (MEDIO)

Primeira build pode levar 20-40 minutos se algum wheel compilar do fonte.

**Mitigacao preferencial:** Cross-build numa maquina x86 e transferir para o Pi:
```bash
# No desktop com Docker buildx + QEMU
docker buildx build --platform linux/arm64 -t soundgrabber:latest --load .
docker save soundgrabber:latest | ssh pi@100.x.x.x docker load
```

### Risco 3: /tmp compartilhado nao testado (ALTO)

O volume tmpfs `sg_tmp` compartilhado entre `api` e `worker` e um padrao novo, sem equivalente no Railway. Se a configuracao do tmpfs falhar (ex: permissoes, tamanho), todos os downloads falham.

**Mitigacao:** Validar imediatamente apos deploy inicial com teste E2E completo. Ter fallback de bind-mount do host (`/tmp/soundgrabber:/tmp`) como plano B se tmpfs causar problemas.

### Risco 4: bgutil desnecessario com IP residencial (BAIXO)

No Railway, bgutil era critico porque datacenter IP era bloqueado. Com IP residencial, YouTube pode aceitar cookies diretos sem PO Token.

**Mitigacao:** Testar pipeline E2E sem `BGUTIL_BASE_URL` primeiro. Se funcionar, simplificar o deploy removendo a dependencia.

---

## Fontes

- Essentia PyPI — sem wheel arm32, tem aarch64: [https://pypi.org/project/essentia/](https://pypi.org/project/essentia/)
- Raspberry Pi 3B suporte a 64-bit: [https://www.raspberrypi.com/news/raspberry-pi-os-64-bit/](https://www.raspberrypi.com/news/raspberry-pi-os-64-bit/)
- Tailscale Docker sidecar pattern: [https://tailscale.com/blog/docker-tailscale-guide](https://tailscale.com/blog/docker-tailscale-guide)
- Docker Compose startup order e healthchecks: [https://docs.docker.com/compose/how-tos/startup-order/](https://docs.docker.com/compose/how-tos/startup-order/)
- Docker Compose producao — memory limits, restart, logging: [https://eastondev.com/blog/en/posts/dev/20260424-docker-compose-production/](https://eastondev.com/blog/en/posts/dev/20260424-docker-compose-production/)
- Memory limits no Pi — cgroup support: [https://dalwar23.com/how-to-fix-no-memory-limit-support-for-docker-in-raspberry-pi/](https://dalwar23.com/how-to-fix-no-memory-limit-support-for-docker-in-raspberry-pi/)
- Cloudflare Tunnel Docker Compose: [https://hub.docker.com/r/cloudflare/cloudflared](https://hub.docker.com/r/cloudflare/cloudflared)
- Redis Docker ARM multi-arch: [https://hub.docker.com/r/arm32v7/redis](https://hub.docker.com/r/arm32v7/redis) (redis:7-alpine cobre arm64 via manifest multi-arch)
