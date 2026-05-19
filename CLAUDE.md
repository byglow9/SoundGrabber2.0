# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Ferramenta web para produtores e artistas underground colarem um link do YouTube, baixarem o beat em WAV e visualizarem BPM e tonalidade. Gratuito, sem cadastro, download direto. Estética autêntica dos anos 2000 (phpBB/Tibia/Orkut).

## Stack

- **Backend:** Python 3.11 + FastAPI
- **Task queue:** Celery + Redis
- **Download:** yt-dlp (com cookies + PO Token — obrigatório para YouTube)
- **Conversão:** FFmpeg
- **Análise:** Essentia (BPM via RhythmExtractor2013, key via KeyExtractor, tuning via TuningFrequency)
- **Frontend:** Vanilla HTML + CSS + JS — zero frameworks

## Dev Commands

```bash
# Ambiente local (inicia Redis + Celery + Uvicorn com --reload)
./start.sh

# Testes unitários (~5s, sem rede, sem FFmpeg)
pytest

# Testes de integração (requer FFmpeg e fixture WAV — sem rede)
pytest -m integration

# Testes de segurança (DEVE estar verde antes de qualquer commit em main)
pytest tests/test_security.py

# Testes e2e (requer YouTube ao vivo + cookies.txt + PO Token — manual)
pytest -m e2e

# Pipeline direto (saída JSON para stdout)
python pipeline.py <youtube_url>

# Docker (produção)
docker build -t soundgrabber .
docker run -p 8000:8000 --env-file .env soundgrabber
```

## Arquitetura

### Módulos principais

| Arquivo | Responsabilidade |
|---------|-----------------|
| `pipeline.py` | Pipeline completo: download → conversão → análise. Sem dependência de API. |
| `api/config.py` | `Settings` (dataclass frozen) — lê env vars via `os.environ` no momento de instanciação |
| `api/tasks.py` | Celery app + tarefa `process_job` — orquestra o pipeline com estados customizados |
| `api/main.py` | FastAPI app — endpoints HTTP, rate limiting, middlewares de segurança, sweeper de WAV |
| `static/` | Frontend: `index.html`, `app.js`, `style.css`, `yonkou.js`, fontes bitmap, bordas PNG |

### Fluxo de dados de uma requisição

1. `POST /jobs` — valida URL YouTube (Pydantic), enfileira `process_job` via Celery, grava `sg:job:{id}` no Redis (TTL = `WAV_TTL_SECONDS`)
2. Celery worker executa `process_job`:
   - `DOWNLOADING/checking_duration` → `check_duration()` (yt-dlp, sem download)
   - `DOWNLOADING/downloading` → `download_audio()` → `/tmp/sg_{12hex}.wav`
   - `CONVERTING` (marcador de estado, WAV já produzido pelo postprocessor do yt-dlp)
   - `ANALYZING` → `analyze_audio()` → BPM + key + Camelot + tuning + duração
3. `GET /jobs/{id}` — consulta `AsyncResult`; retorna estado customizado ou resultado final
4. `GET /files/{id}` — serve o WAV via `FileResponse` após validação de path traversal
5. Daemon thread `wav-sweeper` limpa `/tmp/sg_*.{wav,part,ytdl}` a cada 60s

### Estados Celery customizados

`PENDING` → `DOWNLOADING` → `CONVERTING` → `ANALYZING` → `SUCCESS` / `FAILURE`

O estado `FAILURE` usa `JobFailure(error, error_type)` — exceção serializável que chega como `result.result` no `AsyncResult`.

### Autenticação YouTube (híbrida)

- **cookies.txt** em `/data/yt-dlp-cache/cookies.txt` no host (bind mount `:ro` no notebook) — identidade autenticada; chmod 700 no diretório, 600 no arquivo
- **bgutil** (`BGUTIL_BASE_URL`) — PO Token para desafio JS; **inativo em IP residencial** (`BGUTIL_BASE_URL=` vazio no .env do notebook); Plano B se `LOGIN_REQUIRED` aparecer mesmo com cookies frescos
- Quando bgutil presente: `player_client=["web_safari", "web"]`; ausente: `["android"]` (default atual no notebook)
- `_writable_cookies()` copia o arquivo readonly para `/tmp/sg_cookies_*.txt` antes de passar ao yt-dlp (bind mount `:ro` — yt-dlp tenta `save_cookies()` no exit e quebraria sem a cópia)

### "Som da Semana" (Yonkou)

Painel operador em `/yonkou` — autenticado via cookie HMAC (`itsdangerous`). Dados do release em destaque gravados no Redis (`featured:current`) com fallback em `.data/featured-current.json`. `ADMIN_PASSWORD` e `ADMIN_SESSION_SECRET` são obrigatórios em produção.

## Variáveis de Ambiente

| Variável | Default local | Obrigatória em prod |
|----------|--------------|---------------------|
| `REDIS_URL` | `redis://localhost:6379/0` | sim (com credenciais) |
| `DEV_MODE` | `true` | não (ausência = `false`) |
| `YTDLP_CACHE_DIR` | `""` | sim |
| `BGUTIL_BASE_URL` | `""` | recomendado |
| `ADMIN_PASSWORD` | `correct horse` | sim |
| `ADMIN_SESSION_SECRET` | (string local) | sim |
| `WAV_TTL_SECONDS` | `900` | opcional |
| `RATE_LIMIT_PER_MINUTE` | `3` | opcional |

Copie `.env.example` → `.env` para desenvolvimento local.

## GSD Workflow

Este projeto usa GSD para planejamento e execução.

### Comandos principais

```
/gsd-plan-phase 1     # Planejar a próxima fase
/gsd-execute-phase 1  # Executar os planos da fase
/gsd-progress         # Ver estado atual do projeto
/gsd-discuss-phase N  # Discutir abordagem antes de planejar
```

### Arquivos de planejamento

- `.planning/PROJECT.md` — contexto e decisões do projeto
- `.planning/REQUIREMENTS.md` — requisitos v1 com REQ-IDs
- `.planning/ROADMAP.md` — 5 fases, 19 requisitos mapeados
- `.planning/STATE.md` — estado atual
- `.planning/research/` — pesquisa de domínio (stack, features, arquitetura, pitfalls)

## Fases

| # | Fase | Status |
|---|------|--------|
| 1 | Processing Pipeline | Not started |
| 2 | API Layer | Not started |
| 3 | Hardening | Not started |
| 4 | Frontend | Not started |
| 5 | Visual Identity | Not started |

## Restrições críticas

- **Sem contas de usuário** — ferramenta stateless, sem auth
- **WAV apenas** — formato lossless, qualidade para produtores
- **Limite de 15 minutos** — vídeos mais longos são recusados (`MAX_DURATION_SEC = 900`)
- **Estética Y2K autêntica** — construído COMO sites de 2000-2005, não releitura moderna. Tabelas para layout, sem flexbox/grid, fontes bitmap, hex colors brutas, sem CSS variables
- **YouTube bot detection** — yt-dlp DEVE usar cookies + PO Token desde o primeiro deploy

## Security Gate

**Regra obrigatoria para qualquer nova feature ou modificacao.** Toda mudanca em codigo de producao DEVE passar por este gate antes do merge. Esta secao tem precedencia sobre velocidade de entrega.

### Controles obrigatorios em qualquer novo endpoint HTTP

1. **Rate limiting** — qualquer rota nova (GET, POST, PUT, DELETE) DEVE ter `@limiter.limit("<N>/minute")`. Default conservador: 60/min para reads, 10/min para writes/downloads. Justificar se omitir.
2. **Request body validation** — POST/PUT DEVEM usar Pydantic `BaseModel` com `field_validator`. Sem `request.json()` cru.
3. **Body size limit** — middleware `_limit_body_size` (4KB) ja cobre globalmente. Se uma rota legitimamente precisar mais, justificar e aumentar `_MAX_BODY_BYTES` com nota explicita.
4. **Sync routes com slowapi** — SEMPRE adicionar `request: Request, response: Response` na assinatura. Sem isso, slowapi sync_wrapper levanta Exception em runtime.

### Controles obrigatorios em qualquer novo arquivo gerado em /tmp

1. **Permissoes 0o600** — `os.chmod(path, 0o600)` apos confirmar que o arquivo existe. Bloqueia leitura por outros usuarios do sistema.
2. **Prefixo `sg_`** — todos os arquivos do projeto em /tmp comecam com `sg_` para o sweeper limpar e para path-traversal defense.
3. **Path traversal defense** — qualquer endpoint que retorne arquivo DEVE validar `path.resolve().relative_to(Path("/tmp").resolve())` antes de servir.

### Controles obrigatorios em qualquer novo script shell

1. **`set -e`** na primeira linha apos shebang.
2. **Auto-chmod restritivo** — `chmod 750 "$(realpath "$0")"` para scripts de operacao; `chmod 600` para scripts contendo segredos.
3. **Sem `eval` de input externo** — uso de `eval` requer justificativa explicita.

### Testes obrigatorios

1. **Cada novo endpoint DEVE ter teste em `tests/test_security.py`** confirmando rate limit e validacoes.
2. **`pytest tests/test_security.py` DEVE estar verde** antes de qualquer commit em main.
3. **`pip-audit -r requirements.txt`** DEVE ser executado antes de cada deploy (ver `.planning/SECURITY-CHECKLIST.md`).

### Documentacao obrigatoria

1. **`.planning/SECURITY-CHECKLIST.md`** eh a fonte de verdade dos controles ativos. Nova feature que adiciona controle DEVE atualizar este arquivo.
2. **REQUIREMENTS.md** deve ter REQ-ID novo (categoria SEC-*) para qualquer novo controle de seguranca.

### Quando esta regra pode ser flexibilizada

Nunca silenciosamente. Apenas com decisao explicita registrada em `STATE.md` (Key Decisions) e justificativa que sobreviva a revisao 6 meses depois. Default eh: aplicar o controle.
