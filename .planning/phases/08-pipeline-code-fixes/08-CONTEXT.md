# Phase 8: Pipeline Code Fixes - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Corrigir o código existente para que o pipeline seja correto e deployável no Railway.
Nenhuma nova funcionalidade — apenas fixes em pipeline.py, api/main.py, e criação de nixpacks.toml.

Escopo: ffprobe resolution (PIPE-01), ffmpeg_location como diretório (PIPE-02),
yt-dlp cache disable + retries (PIPE-03, PIPE-04), cookies probe no startup (PIPE-05),
nixpacks.toml para Railway (DEPLOY-01).

</domain>

<decisions>
## Implementation Decisions

### ffprobe Resolution (PIPE-01 + PIPE-02)

- **D-01:** Usar `shutil.which("ffprobe")` como primeira tentativa. Se retornar None, usar `Path(imageio_ffmpeg.get_ffmpeg_exe()).parent` como diretório fallback. Logar `WARNING` se o fallback for usado.
- **D-02:** `ffmpeg_location` passado ao yt-dlp DEVE ser um diretório (o diretório do binário), NÃO o caminho do binário. Bug atual: `_FFMPEG_PATH` (caminho do exe) é passado diretamente.
- **D-03:** A resolução acontece no nível de módulo (variáveis `_FFPROBE_PATH` e `_FFMPEG_DIR`) — executada uma vez no import, não por chamada.

### yt-dlp Hardening (PIPE-03 + PIPE-04)

- **D-04:** Adicionar `"no_cache_dir": True` a TODOS os dicts de `ydl_opts` em pipeline.py (tanto em `check_duration` quanto em `download_audio`). Previne nsig stale entre deploys no Railway.
- **D-05:** Adicionar `"retries": 3` e `"fragment_retries": 3` ao dict de `download_audio`. Check_duration usa `skip_download=True` então retries não são relevantes para ele.

### Cookies Validation no Startup (PIPE-05)

- **D-06:** Validação de `__Secure-3PSID` no lifespan da API (`api/main.py`), não no worker Celery. Log `CRITICAL` (não-bloqueante — não levanta exceção, não impede o startup).
- **D-07:** Validação: verificar se `settings.cookies_path` existe E se o arquivo contém a string `__Secure-3PSID`. Se ausente ou arquivo inexistente, logar CRITICAL e continuar.
- **D-08:** Não bloquear o startup — o log é aviso para o operador, não um gate de segurança.

### nixpacks.toml (DEPLOY-01)

- **D-09:** Criar `nixpacks.toml` na raiz com `aptPkgs = ["ffmpeg"]`. Sem pin de Python — requirements.txt já garante as deps Python. O nixpacks.toml da raiz aplica a ambos os serviços (web + worker) que compartilham o mesmo repo.

### Claude's Discretion

- Ordem de correções no PLAN.md: começar pelas mudanças em pipeline.py (PIPE-01..04), depois main.py (PIPE-05), depois nixpacks.toml (DEPLOY-01) — separadas em waves para commits atômicos.
- Testes: a fase não adiciona novos endpoints — o Security Gate de testes obrigatórios em test_security.py não se aplica. Verificação via success criteria locais (PIPE-01: python pipeline.py funciona, PIPE-05: log CRITICAL aparece com cookies ruim).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline e Requisitos
- `.planning/REQUIREMENTS.md` §v1.2 — PIPE-01..05, DEPLOY-01 definidos aqui; ler antes de planejar
- `.planning/ROADMAP.md` §Phase 8 — success criteria detalhados (4 critérios)
- `.planning/STATE.md` §Known Issues — contexto das falhas conhecidas no Railway

### Código existente a modificar
- `pipeline.py` — arquivo central desta fase; linhas 33-34 (_FFPROBE_PATH bug PIPE-01), linha 68/148 (ffmpeg_location bug PIPE-02), opts de yt-dlp (PIPE-03/04)
- `api/main.py` — lifespan function para PIPE-05
- `api/config.py` — settings.cookies_path disponível para o check de PIPE-05
- `nixpacks.toml` — não existe ainda; criar na raiz (DEPLOY-01)

### Infra de Deploy
- `railway.toml` — deploy config do web service (para referência de startCommand)
- `railway-worker.toml` — deploy config do celery worker

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/config.py:settings.cookies_path` — já resolve `YTDLP_COOKIES_B64` ou `YTDLP_COOKIES_FILE`; usar em PIPE-05 diretamente
- `api/main.py:lifespan` — já faz `_check_redis_auth` no startup; adicionar cookies check logo depois (mesmo padrão)
- `pipeline.py:_FFMPEG_PATH` — `imageio_ffmpeg.get_ffmpeg_exe()` já existe; usar `.parent` para o diretório fallback

### Established Patterns
- Module-level constants para paths (`_FFMPEG_PATH`, `_FFPROBE_PATH`): mesma convenção, só mudar a lógica de resolução
- yt-dlp opts como dicts explícitos com keys bem documentadas — adicionar `no_cache_dir`, `retries`, `fragment_retries` seguindo o mesmo estilo
- Logs com `logger = logging.getLogger(__name__)` em todos os módulos — usar para WARNING (ffprobe fallback) e CRITICAL (cookies)

### Integration Points
- `pipeline.py` importado diretamente por `api/tasks.py` (`from pipeline import check_duration, download_audio, analyze_audio`) — sem mudança de interface pública necessária
- Variáveis module-level (`_FFMPEG_PATH`, `_FFPROBE_PATH`) são privadas — mudança transparente para todos os importadores

</code_context>

<specifics>
## Specific Ideas

- A variável `_FFPROBE_PATH` atual é `str(Path(_FFMPEG_PATH).parent / "ffprobe")` — uma derivação do exe do imageio-ffmpeg. Com o fix de PIPE-01, deve virar: `shutil.which("ffprobe") or str(Path(_FFMPEG_PATH).parent / "ffprobe")`.
- O `ffmpeg_location` para yt-dlp deve ser `str(Path(_FFMPEG_PATH).parent)` — o diretório, não o exe (fix de PIPE-02).
- Cookies check em main.py: após `_check_redis_auth`, antes do `sweeper.start()`.

</specifics>

<deferred>
## Deferred Ideas

Nenhuma — discussão ficou dentro do escopo da fase.

</deferred>

---

*Phase: 08-pipeline-code-fixes*
*Context gathered: 2026-05-10*
