# Phase 10: Failure Hardening and E2E Validation - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Dois entregáveis concretos:

1. **PIPE-06 — Falha explícita de bgutil:** quando `BGUTIL_BASE_URL` está configurado mas o serviço bgutil está inacessível, o job falha com mensagem que nomeia o bgutil explicitamente e um `error_type` distinto. Sem silent fallback para android client.

2. **Correção arquitetural de /tmp entre containers:** Uvicorn e Celery Worker migram para um único serviço Railway (mesmo container), eliminando o bug onde WAVs produzidos pelo worker não eram acessíveis ao web service.

3. **PIPE-07 — Validação E2E no Railway:** após as correções acima, submeter 3 beats reais ao Railway e confirmar que todos chegam a `status=done` com WAV válido, BPM plausível e key em notação padrão.

</domain>

<decisions>
## Implementation Decisions

### Arquitetura Railway — /tmp compartilhado (bug containers separados)

- **D-01:** Migrar para serviço único no Railway — Uvicorn + Celery Worker no mesmo container. Um único `railway.toml` com `startCommand` que inicia ambos (via `start-all.sh` com supervisord ou honcho). `railway-worker.toml` é aposentado.
- **D-02:** Compartilhamento de `/tmp` é nativo — os dois processos veem o mesmo sistema de arquivos. Nenhuma mudança de código em `pipeline.py` ou `api/main.py` é necessária para o file serving.
- **D-03:** Escala independente (worker vs web) é sacrificada. Aceitável para comunidade underground (centenas de usuários — STATE.md).

### Detecção de bgutil inacessível (PIPE-06)

- **D-04:** Probe HTTP explícito em `pipeline.py::download_audio` antes de chamar yt-dlp, somente quando `bgutil_base_url` está não-vazio. Timeout de 2 segundos.
- **D-05:** Probe apenas em `download_audio` — não em `check_duration`. Um probe por job, no ponto crítico antes do download.
- **D-06:** Se o probe falhar (ConnectionError, timeout, qualquer non-2xx) → lançar exceção com mensagem de bgutil **antes** de tentar yt-dlp. Nunca fazer silent fallback para android client quando `bgutil_base_url` está configurado.

### Mensagem de erro e error_type (PIPE-06)

- **D-07:** Mensagem: `"PO Token service unavailable (bgutil at {bgutil_base_url}). Download requires bgutil to be running."` — nomeia o serviço e expõe a URL configurada para facilitar debug do operador.
- **D-08:** `error_type`: `"bgutil_unavailable"` — novo tipo distinto de `"download_error"`. Permite monitorar falhas de infra separadamente de vídeos bloqueados pelo YouTube.
- **D-09:** O novo `error_type` é lançado via `JobFailure(error=..., error_type="bgutil_unavailable")` em `api/tasks.py` — capturando a exceção específica do probe em `pipeline.py`.

### Cobertura de testes (PIPE-06)

- **D-10:** Teste automatizado mockado em `tests/test_pipeline_fixes.py`. Mock de `requests.get` (ou `httpx.get`) retornando `ConnectionError` quando `bgutil_base_url` está setado. Verifica que a exceção lançada tem a mensagem com "bgutil" e que não há tentativa de yt-dlp após o probe falhar.
- **D-11:** Arquivo `tests/test_pipeline_fixes.py` — mesmo arquivo que PIPE-01..05 e testes de bgutil 0.8.x. Padrão consistente.

### Validação E2E Railway (PIPE-07)

- **D-12:** Checkpoint humano documentado — plano inclui task com sequência de curl commands para submeter 3 beats, poll até `done`, verificar `bpm`/`key`/`camelot`, baixar WAV e confirmar que não é 0-byte.
- **D-13:** Critérios para as 3 URLs de teste (escolhidas pelo operador na hora): beats instrumentais de 3-7 minutos de gêneros diferentes (ex: trap, lo-fi, house). Sem URLs fixas no contexto para evitar links expirados.
- **D-14:** Resultado registrado em `10-SMOKE-TEST.md` — mesmo padrão de `09-01-SMOKE-TEST.md`.

### Claude's Discretion

- Escolha de ferramenta HTTP para o probe (`requests` ou `httpx`): `requests` já é dependência indireta via yt-dlp; `httpx` é mais moderno. Usar o que já estiver em `requirements.txt`.
- Nome do script de startup (`start-all.sh` vs `Procfile` + honcho): usar o que for mais legível e tiver menos deps externas.
- Número de processos Celery no container único: manter `concurrency=3` como está (STATE.md Known Risks).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos desta fase
- `.planning/REQUIREMENTS.md` §v1.2 — PIPE-06 e PIPE-07 definidos aqui; ler antes de planejar
- `.planning/ROADMAP.md` §Phase 10 — 3 success criteria detalhados

### Código a modificar
- `pipeline.py` linhas 125-200 (`download_audio`) — onde o probe HTTP de bgutil entra (D-04/D-05)
- `api/tasks.py` linhas 85-117 — exception handling; novo `except` para capturar exceção de bgutil probe (D-09)
- `railway.toml` — startCommand atual do Uvicorn; vai receber o novo startCommand que inicia ambos (D-01)
- `railway-worker.toml` — será aposentado após migração para serviço único (D-01)

### Testes existentes (referência de padrão)
- `tests/test_pipeline_fixes.py` — PIPE-01..05 e bgutil 0.8.x tests; PIPE-06 entra aqui (D-10/D-11)
- `tests/test_security.py` — referência de padrão para mocks e fixtures

### Contexto das fases anteriores
- `.planning/phases/09-railway-bgutil-deployment/09-01-SMOKE-TEST.md` linhas 184-215 — documenta o bug arquitetural de /tmp isolados que D-01 resolve
- `.planning/phases/09-railway-bgutil-deployment/09-CONTEXT.md` — D-01..D-09 sobre bgutil/Railway; especialmente D-04 (confiar exclusivamente no bgutil, sem fallback estático)
- `.planning/STATE.md` §Key Decisions — "No silent fallback when bgutil unavailable" é uma decisão travada do projeto

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline.py::download_audio(url, cookies_path, po_token, bgutil_base_url)` — já recebe `bgutil_base_url`; probe entra no início da função, antes de montar `ydl_opts`
- `api/tasks.py::JobFailure` — já suporta `error` + `error_type` arbitrários; adicionar novo `error_type="bgutil_unavailable"` sem mudar a classe
- `api/tasks.py::process_job` exception chain — padrão já estabelecido: `except SomeError as e → raise JobFailure(...) from e`
- `railway.toml` — startCommand atual é `uvicorn api.main:app --host 0.0.0.0 --port $PORT`; vai ser substituído por script que inicia ambos

### Established Patterns
- Module-level constants para paths (`_FFPROBE_PATH`, `_FFMPEG_DIR`): probe pode usar o mesmo estilo de configuração no nível de módulo
- Logs com `logger.info/WARNING/CRITICAL` em pipeline.py — probe de bgutil deve logar o resultado antes de lançar a exceção
- Testes com `unittest.mock.patch` em test_pipeline_fixes.py — padrão para mockar dependências externas

### Integration Points
- `pipeline.py` → `api/tasks.py`: a exceção do probe (ex: `RuntimeError("bgutil unavailable...")`) precisa ser capturada em `process_job` e convertida para `JobFailure(error_type="bgutil_unavailable")`
- `railway.toml` → container startup: novo startCommand deve aguardar que Celery registre workers antes de aceitar jobs (ou usar `--wait-for` / health check)

</code_context>

<specifics>
## Specific Ideas

- **Probe simples:** `requests.get(f"{bgutil_base_url}/", timeout=2)` ou TCP connect na porta. Se o bgutil não tiver endpoint HTTP acessível, TCP connect é mais robusto. O bgutil v0.8.1 escuta em `0.0.0.0:4416` (confirmado em 09-CONTEXT.md D-01) — um GET simples na raiz deve funcionar.
- **start-all.sh:** iniciar Celery worker em background (`celery -A api.tasks.celery_app worker &`) e depois Uvicorn em foreground (`exec uvicorn ...`). O Railway monitora o processo foreground para health checks.
- **Smoke test E2E:** seguir mesmo formato de `09-01-SMOKE-TEST.md` — tabela de gate checks, resultado por critério, assinatura de data.

</specifics>

<deferred>
## Deferred Ideas

- **Fallback estático com YTDLP_PO_TOKEN quando bgutil cai** — discutido e descartado em Phase 9 (09-CONTEXT.md deferred). Continua fora de escopo: bgutil é o mecanismo correto; fallback estático esconde problemas de infra.
- **Health endpoint do bgutil** — bgutil não expõe `/health` HTTP documentado; verificação via probe genérico é suficiente.
- **Escala independente de worker vs web** — sacrificada para resolver o bug de /tmp. Pode ser retomada em v2 com object storage (S3/R2) como camada de compartilhamento de arquivos.

</deferred>

---

*Phase: 10-failure-hardening-and-e2e-validation*
*Context gathered: 2026-05-11*
