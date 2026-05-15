# Phase 13: Docker Compose - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Criar Dockerfile e docker-compose.yml para rodar o SoundGrabber no notebook HP (x86_64) com
quatro serviços: api, worker, redis e bgutil. A imagem usa python:3.11-slim com ffmpeg e
Node.js instalados via apt — sem imageio-ffmpeg, sem librosa. Essentia é validada como gate
obrigatório antes de avançar. Api e worker compartilham volume tmpfs em /tmp para transferência
de arquivos WAV entre containers.

Esta fase inclui refatoração do requirements.txt (remover imageio-ffmpeg e librosa) e
limpeza do pipeline.py (remover importação de imageio_ffmpeg e usar apenas shutil.which).

</domain>

<decisions>
## Implementation Decisions

### imageio-ffmpeg e pipeline.py

- **D-01:** Remover `imageio-ffmpeg` de `requirements.txt`. DEPLOY-04 é explícito: a imagem não
  deve incluir imageio-ffmpeg. Com ffmpeg instalado via apt no container, o fallback nunca seria
  necessário de qualquer forma.
- **D-02:** Refatorar `pipeline.py` para remover o `import imageio_ffmpeg` da linha 38 e todos os
  usos de `imageio_ffmpeg.get_ffmpeg_exe()`. Substituir por `shutil.which("ffmpeg")` diretamente
  — já existe em `_system_ffmpeg = shutil.which("ffmpeg")` no módulo. Se `shutil.which("ffmpeg")`
  retornar None, levantar erro explícito no startup em vez de usar fallback silencioso.
- **D-03:** Remover `librosa==0.11.0` de `requirements.txt` nesta mesma fase. Librosa não é
  aceita no projeto — Essentia é o padrão obrigatório. Remover junto com imageio-ffmpeg para
  não deixar dep morta.

### Dockerfile — imagem base e dependências de sistema

- **D-04:** Usar `python:3.11-slim` como imagem base (x86_64). Não mudar para `python:3.11` full
  — manter slim conforme DEPLOY-04. Se Essentia precisar de libs adicionais, instalá-las
  explicitamente via `apt-get install` no Dockerfile.
- **D-05:** Instalar via apt no Dockerfile: `ffmpeg`, `nodejs` (para yt-dlp/bgutil —
  compatível com Node >=20), `libsndfile1`. Outras deps de sistema que Essentia precisar
  (ex: `libfftw3-3`, `libyaml-cpp0.7`) devem ser descobertas durante o build e adicionadas
  ao Dockerfile iterativamente pelo executor até que `pip install essentia` e
  `import essentia.standard` funcionem.
- **D-06:** `pip install` a partir de `requirements.txt` com `--no-cache-dir`. Node.js pode ser
  instalado via `apt-get install nodejs` se a versão no slim for >=20, ou via NodeSource se
  a versão do apt for inferior (verificar no build).
- **D-07:** **Gate obrigatório de validação (bloqueia):** após `docker build`, o executor DEVE
  rodar `docker run --rm soundgrabber:latest python -c "import essentia.standard, yt_dlp, fastapi, celery; print('OK')"` e confirmar que o exit code é 0 e o output contém `OK` antes de
  continuar. Se falhar, o executor itera as deps de sistema até funcionar — não avança sem isso.

### docker-compose.yml — serviços e networking

- **D-08:** Quatro serviços no compose: `api`, `worker`, `redis`, `bgutil`.
  - `api`: imagem local `soundgrabber:latest`, porta 8000 exposta no host, `restart: unless-stopped`
  - `worker`: mesma imagem, command `celery -A api.tasks worker --concurrency=1 --max-tasks-per-child=10`, sem porta exposta, `restart: unless-stopped`
  - `redis`: imagem `redis:7-alpine`, apenas rede interna, `restart: unless-stopped`
  - `bgutil`: imagem `jim60105/bgutil-pot`, apenas rede interna (porta 4416), `restart: unless-stopped`
- **D-09:** `BGUTIL_BASE_URL=http://bgutil:4416` nos serviços `api` e `worker`. bgutil roda na
  rede interna do compose — sem porta exposta no host.
- **D-10:** Todos os 4 serviços na mesma rede bridge interna (`soundgrabber_net`). Redis e bgutil
  sem `ports:` mapeadas para o host (segurança — só acessíveis pelos outros containers).

### Volume tmpfs compartilhado

- **D-11:** Usar `/tmp` como path do volume compartilhado (seguir DEPLOY-06 literalmente).
  D-17 da Phase 12 (`SG_TMP_DIR=/data/tmp`) é descartada nesta fase. Sem mudança de código
  em `pipeline.py` ou `api/main.py` — o código já usa `/tmp` com prefixo `sg_` por padrão.
- **D-12:** Volume tmpfs montado em `/tmp` para os serviços `api` e `worker`. Configuração
  no compose: `tmpfs: /tmp` ou `volumes: sg_tmp:/tmp` com driver tmpfs. Arquivos `sg_*.wav`
  escritos pelo worker em `/tmp` são imediatamente legíveis pela api no mesmo path.

### Security Gate (obrigatório por CLAUDE.md)

- **D-13:** Nenhum container usa `privileged: true` ou `network_mode: host` (D-13 da Phase 12).
- **D-14:** Redis sem `ports:` mapeadas para o host — só acessível internamente.
- **D-15:** `restart: unless-stopped` em todos os 4 serviços (DEPLOY-05).

### Claude's Discretion

- Limites de memória/CPU no compose: Claude decide os valores razoáveis para i5-3210M/4GB RAM
  (ex: `mem_limit: 512m` para api, `mem_limit: 1g` para worker).
- Variáveis de ambiente no compose: Claude decide a estrutura (env_file vs environment block)
  e quais variáveis incluir no `.env.example`.
- Health checks no compose: Claude decide se adiciona `healthcheck:` nos serviços ou deixa para
  fase posterior.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos desta fase
- `.planning/REQUIREMENTS.md` §v1.3 DEPLOY — DEPLOY-04, DEPLOY-05, DEPLOY-06 com critérios exatos
- `.planning/ROADMAP.md` §Phase 13 — success criteria observáveis (3 critérios)

### Contexto da fase anterior (decisões que impactam esta fase)
- `.planning/phases/12-notebook-foundation/12-CONTEXT.md` — D-13 (sem privileged/host network),
  D-14 (concurrency=1), D-15 (Essentia gate), D-16 (Node.js no container), hardware confirmado

### Código a modificar
- `pipeline.py` — linhas 38-68: remover imageio_ffmpeg, refatorar para shutil.which apenas
- `requirements.txt` — remover imageio-ffmpeg e librosa
- `nixpacks.toml` — referência de quais apt packages o projeto já usa no Railway (ffmpeg, nodejs)

### Security Gate
- `CLAUDE.md` §Security Gate — controles obrigatórios para novos scripts shell e containers

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nixpacks.toml` — aptPkgs para Railway: `["ffmpeg", "nodejs"]`; mesma lista base para o Dockerfile
- `api/config.py` — `Settings` lê `BGUTIL_BASE_URL`, `YTDLP_CACHE_DIR`, `REDIS_URL` via env vars;
  sem mudança para suportar compose

### Established Patterns
- `pipeline.py` já usa `shutil.which("ffmpeg")` como `_system_ffmpeg` — padrão a manter e expandir
- Arquivos WAV gerados em `/tmp/sg_{uuid4()}.wav` com `os.chmod(path, 0o600)` (Security Gate)
- `api/config.py` usa `os.environ.get(...)` com defaults sensatos — 12-factor ready
- `start.sh` / `start-all.sh`: padrão de script shell com `set -e`, chmod auto-aplicado

### Integration Points
- `api/tasks.py` — onde Celery task invoca `pipeline.py`; sem mudança para compose
- `api/main.py` — `GET /files/{id}` serve de `/tmp/{job_id}.wav`; sem mudança com tmpfs em /tmp
- `Procfile` — `web: uvicorn api.main:app ...`; compose substitui o Procfile para deploy local

</code_context>

<specifics>
## Specific Ideas

- bgutil imagem: `jim60105/bgutil-pot` (mesma usada no Railway — paridade confirmada)
- Celery command explícito: `celery -A api.tasks worker --concurrency=1 --max-tasks-per-child=10`
  (DEPLOY-05 explicita esses parâmetros)
- Porta da api: 8000 (padrão uvicorn, consistente com Procfile)
- Nome da rede interna: `soundgrabber_net` (ou deixar ao padrão do compose — Claude decide)

</specifics>

<deferred>
## Deferred Ideas

- **SG_TMP_DIR=/data/tmp (D-17 Phase 12)**: descartada nesta fase. DEPLOY-06 é explícito sobre /tmp.
  Se /tmp global causar problema de colisão em produção, SG_TMP_DIR pode ser revisitado em fase futura.
- **SSH hardening / deploy.sh via SSH** — scope da Phase 14 (AUTH-05)
- **Cloudflare Tunnel** — scope da Phase 15 (TUNNEL-01..02)
- **Log rotation / alerting** — v2 requirements
- **DOCKER-USER rules no UFW** — Phase 12 D-06b; relevante quando compose publicar portas em produção

</deferred>

---

*Phase: 13-docker-compose*
*Context gathered: 2026-05-15*
