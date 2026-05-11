# Phase 9: Railway bgutil Deployment - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Conectar o serviço bgutil (já deployado no Railway) aos workers Uvicorn e Celery Worker
via variável de ambiente `BGUTIL_BASE_URL`. Configuração já aplicada via MCP durante
a sessão de discuss — o que resta para o plano é verificação e validação.

**Já feito antes do plano:**
- Serviço `bgutil` (jim60105/bgutil-pot v0.8.1) deployado com status SUCCESS
- `BGUTIL_BASE_URL=http://bgutil.railway.internal:4416` setado em Uvicorn e Celery Worker
- Redeploy disparado em ambos os serviços (IDs: 02cda13b, 10ec98b3)

**Escopo restante para o plano:** verificar logs de startup dos dois serviços e
confirmar que não há erros de conexão com o bgutil. A validação completa do pipeline
(download real de beat URL) é o critério final de sucesso desta fase.

</domain>

<decisions>
## Implementation Decisions

### Porta e URL do bgutil (DEPLOY-02)

- **D-01:** `jim60105/bgutil-pot` v0.8.1 escuta em `0.0.0.0:4416` por padrão — sem env var PORT necessária. Confirmado via logs: `POT server v0.8.1 listening on 0.0.0.0:4416`.
- **D-02:** URL interna Railway para os workers: `http://bgutil.railway.internal:4416`. Railway private networking resolve o hostname internamente sem expor porta pública.
- **D-03:** Serviço bgutil Railway ID: `2fc3a8a5-b50b-48e2-b408-87167f5ac28a`. Deployment ID: `1a83308d`. Status na criação do contexto: SUCCESS.

### Estratégia de PO Token

- **D-04:** Confiar exclusivamente no bgutil para geração dinâmica de PO Tokens. `YTDLP_PO_TOKEN` permanece vazio nos serviços Railway — tokens dinâmicos do bgutil são superiores a token estático que expira.
- **D-05:** O código já implementa fallback automático: quando `bgutil_base_url` está configurado, usa `web` client; quando vazio, usa `android` client. Com bgutil ativo, o fluxo é sempre `web` + tokens dinâmicos.

### Configuração Aplicada via MCP (DEPLOY-03)

- **D-06:** `BGUTIL_BASE_URL=http://bgutil.railway.internal:4416` foi setado em:
  - Uvicorn (ID: `248e8eaf-68e1-4fb1-beb0-448bd26f317a`) — deployment `02cda13b` disparado
  - Celery Worker (ID: `145135bf-201e-4fd7-8ea2-ed790d334dbf`) — deployment `10ec98b3` disparado
- **D-07:** Ambos redeployados com a nova env var na sessão de discuss (2026-05-11).

### Verificação Pós-Config

- **D-08:** Sequência de verificação via MCP Railway:
  1. Checar status dos deployments (aguardar SUCCESS)
  2. Verificar logs de startup do Uvicorn — não deve haver erros de conexão ao bgutil
  3. Verificar logs do Celery Worker — idem
  4. Submeter um beat URL real via API para confirmar pipeline completo (download → WAV)
- **D-09:** MCP Railway deve ser usado para toda a inspeção de logs e status — sem abrir dashboard manualmente.

### Claude's Discretion

- O plano pode ser curto (1 plano) pois a configuração já foi aplicada — o trabalho restante é só verificação.
- Se os logs mostrarem erros de conexão refused ao bgutil, o troubleshooting deve usar `railway-agent` para inspecionar o estado interno do serviço bgutil.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos
- `.planning/REQUIREMENTS.md` §v1.2 — DEPLOY-02 e DEPLOY-03 são os dois requisitos desta fase
- `.planning/ROADMAP.md` §Phase 9 — 3 success criteria detalhados

### Código que consome BGUTIL_BASE_URL
- `pipeline.py` linhas 56-90 (check_duration) e 108-155 (download_audio) — lógica de seleção `web` vs `android` client baseada em `bgutil_base_url`
- `api/config.py` linha 52 — `bgutil_base_url` lido de `BGUTIL_BASE_URL` env var via `settings`
- `api/tasks.py` linhas 57, 61 — `settings.bgutil_base_url` passado para `check_duration` e `download_audio`

### Infra Railway
- `railway.toml` — config do serviço Uvicorn (startCommand, healthcheck)
- `railway-worker.toml` — config do Celery Worker (startCommand)
- IDs Railway já documentados em D-03 e D-06 acima

### Fase anterior (contexto)
- `.planning/phases/08-pipeline-code-fixes/08-CONTEXT.md` — decisions D-01..D-09, especialmente D-01/D-02 (ffprobe/ffmpeg_location) e D-04/D-05 (no_cache_dir, retries) que garantem que o pipeline está correto antes de receber os tokens do bgutil

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/config.py:settings.bgutil_base_url` — já lê `BGUTIL_BASE_URL` do ambiente; nenhuma mudança de código necessária
- `pipeline.py:check_duration` e `download_audio` — já condicionam `web` vs `android` client com base em `bgutil_base_url`; tudo pronto

### Padrões Estabelecidos
- Railway private networking: `<service-name>.railway.internal:<port>` — mesmo padrão usado para Redis (`redis.railway.internal`)
- Env vars Railway são injetadas em containers; redeploy é obrigatório após mudança para que sejam carregadas

### Pontos de Integração
- bgutil ↔ yt-dlp: via plugin `youtubepot-bgutilhttp` — configurado em `extractor_args["youtubepot-bgutilhttp"] = [f"base_url={bgutil_base_url}"]`
- bgutil ↔ Railway private network: `bgutil.railway.internal:4416` — Railway resolve internamente sem DNS externo

</code_context>

<specifics>
## Specific Ideas

- **Uso integral do MCP Railway** — toda inspeção de logs, status e troubleshooting deve usar ferramentas MCP (`mcp__railway__get-logs`, `mcp__railway__list-deployments`, `mcp__railway__railway-agent`) sem abrir dashboard.
- **Beat URL para teste:** qualquer beat no YouTube com menos de 15 minutos serve para validar o pipeline. Preferir um beat instrumental curto (3-5 min) para feedback rápido.

</specifics>

<deferred>
## Deferred Ideas

- **YTDLP_PO_TOKEN como fallback** — discutido e descartado; bgutil é o mecanismo correto para datacenter IP. Estático fica para emergência manual se bgutil cair (fora de escopo).
- **Health endpoint bgutil** — bgutil não expõe `/health` HTTP, só a porta gRPC 4416. Verificação via yt-dlp plugin é suficiente para esta fase.

None — discussão manteve-se dentro do escopo da fase.

</deferred>

---

*Phase: 9-railway-bgutil-deployment*
*Context gathered: 2026-05-11*
