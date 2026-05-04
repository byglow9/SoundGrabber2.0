# Phase 4: Frontend - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Interface web funcional que permite ao usuário completar o fluxo completo no browser:
colar um link do YouTube → acompanhar progresso em tempo real → ver análise musical → baixar o WAV.

Sem estilo visual definitivo — Phase 5 aplica a estética Y2K/2000s. Phase 4 entrega HTML semântico
div-based + JavaScript de lógica funcional. A phase termina quando os 4 success criteria do ROADMAP.md
forem atendidos com o navegador (sem usar curl).

</domain>

<decisions>
## Implementation Decisions

### Polling de progresso
- **D-01:** Intervalo fixo de **2 segundos** para `GET /jobs/{id}` — alinhado com os success criteria do ROADMAP.md ("polled every 2 seconds"). Sem lógica adaptativa.
- **D-02:** Timeout de **3 minutos** de polling sem conclusão → exibir mensagem de erro ("Processamento demorou mais que o esperado. Tente novamente."). Polling encerrado após timeout.
- **D-03:** Parar o polling assim que o status retornar `done` ou `failed` — não continuar consultando após conclusão.

### Recovery de erros
- **D-04:** Erro **422** (`validation_error`) — manter o conteúdo do campo URL e destacar o campo visualmente (borda ou cor de erro). Mensagem de erro exibida próxima ao campo. Usuário pode editar e resubmeter diretamente.
- **D-05:** Erro **429** (`rate_limit_error`) — exibir countdown ao vivo usando o header `Retry-After` da resposta. Botão de submit desabilitado durante a contagem regressiva. Exemplo: "Limite atingido. Tente novamente em 47s." com o número decrementando a cada segundo.
- **D-06:** Job **falhou** (`download_error` / `internal_error`) — exibir mensagem de erro clara + botão explícito **"Tentar novamente"** que reutiliza a URL já no campo e resubmete o job sem interação adicional.

### Estimativa de tamanho WAV
- **D-07:** Cálculo **client-side em JavaScript** a partir de `duration_sec` retornado pelo job. Zero mudança na API.
- **D-08:** Fórmula: `duration_sec × 44100 Hz × 2 canais × 2 bytes ≈ 10.5 MB/min`. Exibir com prefixo `~` para indicar estimativa (ex: `~47 MB`). Formato humano: MB com 0 casas decimais acima de 10 MB, uma casa abaixo disso.
- **D-09:** Tamanho exibido **após o job completar** (quando `duration_sec` está disponível), antes de o usuário clicar em download. Parte do card de resultado, não uma etapa separada.

### Boundary Phase 4 vs Phase 5
- **D-10:** Phase 4 entrega **HTML div-based sem CSS** (estrutura semântica + IDs/classes necessários para JS e para Phase 5 estilizar). Sem `<style>` inline, sem arquivo CSS.
- **D-11:** Estrutura HTML usa `<div>` genérico — Phase 5 reescreve ou refatora a estrutura para usar tabelas e padrões Y2K. Separação limpa: Phase 4 = JavaScript + lógica, Phase 5 = HTML estrutural + CSS visual.

### Claude's Discretion
- Como FastAPI serve o `index.html` (StaticFiles, Jinja2, ou rota `GET /` com FileResponse) — planner decide
- Estrutura interna do JS: event listeners, state machine, como organizar o código em vanilla JS
- Exatamente quais classes/IDs colocar no HTML para Phase 5 conectar estilos
- Se o `download_url` já está sendo setado na task do Celery ou precisa ser construído no frontend como `/files/{job_id}`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Projeto
- `.planning/PROJECT.md` — visão, princípios, restrições críticas (sem cadastro, WAV apenas, stateless)
- `.planning/REQUIREMENTS.md` — CORE-01, UX-01, UX-02 são os requisitos desta fase
- `.planning/ROADMAP.md` — 4 success criteria exatos para Phase 4 (seção "Phase Details")
- `.planning/STATE.md` — riscos conhecidos e contexto acumulado

### Fases anteriores
- `.planning/phases/03-hardening/03-CONTEXT.md` — formato unificado de erros `{error, error_type}` (D-07 Phase 3), que o frontend deve consumir
- `.planning/phases/02-api-layer/02-CONTEXT.md` — contrato completo da API: POST /jobs, GET /jobs/{id}, GET /files/{id}; estados do job; formato da resposta `done`
- `.planning/phases/01-processing-pipeline/01-CONTEXT.md` — campos retornados pela análise: bpm, key, camelot, bpm_half, bpm_double, duration_sec

### Código existente
- `api/main.py` — rotas implementadas e contratos de resposta; estados do job: queued, downloading (stage: checking_duration/downloading), converting, analyzing, done, failed
- `api/config.py` — settings disponíveis (redis_url, wav_ttl, rate_limit_per_minute)

### Referência visual (Phase 5)
- `https://www.neoworlds.online/` — site de referência para a estética Y2K da Phase 5 (indicado pelo usuário). Phase 5 deve usar como inspiração de layout, cores e tipografia. NOTA: esta referência é para Phase 5, não Phase 4.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/main.py:get_job()` — retorna `{status, bpm, bpm_half, bpm_double, key, camelot, duration_sec, download_url}` quando `status == "done"`. Frontend consome este shape diretamente.
- `api/main.py:submit_job()` — retorna `{job_id}` no POST /jobs com status 202. Frontend usa este `job_id` para iniciar o polling.
- `api/main.py:download_file()` — `GET /files/{job_id}` retorna FileResponse com `media_type="audio/wav"` e `filename="soundgrabber_{job_id[:8]}.wav"`. Frontend pode usar `<a href="/files/{job_id}" download>` para acionar o download direto.

### Established Patterns
- Formato de erro unificado: `{error: str, error_type: str}` — todos os erros síncronos (422) e assíncronos (job failed) usam este shape. Frontend trata qualquer erro via `response.error`.
- Rate limit: resposta 429 inclui header `Retry-After` com segundos até reset — D-05 usa este header para o countdown.
- 12-factor config: API não tem CORS configurado por padrão — se frontend for servido do mesmo origin (FastAPI serve o HTML), não há problema. Se separado, planner precisa adicionar CORS.

### Integration Points
- FastAPI precisa servir o arquivo HTML estático — adicionar `StaticFiles` ou rota `GET /` em `api/main.py`
- JavaScript faz fetch para as mesmas rotas da API (mesma origin ou CORS configurado)
- `<a href="/files/{job_id}" download>` é o mecanismo mais simples para download direto via browser

</code_context>

<specifics>
## Specific Ideas

- Countdown de rate limit: usar `setInterval(1000, ...)` decrementando o valor de `Retry-After` — simples e sem dependência de relógio do servidor
- Estimativa de tamanho: `Math.round(duration_sec * 44100 * 2 * 2 / 1_000_000)` → valor em MB; exibir como `~47 MB`
- Polling: `setInterval(2000, pollStatus)` com `clearInterval` ao detectar `done` ou `failed`, e `clearInterval` após 180s (3 min timeout)
- Referência visual Phase 5: neoworlds.online — o planner de Phase 5 deve acessar este site antes de implementar

</specifics>

<deferred>
## Deferred Ideas

- **Estética Y2K/neoworlds.online** — aplicada integralmente em Phase 5, não Phase 4
- **CORS configuration** — se o projeto evoluir para frontend separado do backend (fora do escopo v1)
- **Waveform visualization** — deferred para v2 (registrado no REQUIREMENTS.md)
- **Progressive enhancement** — versão sem JS para browsers antigos (fora do escopo v1)

</deferred>

---

*Phase: 04-frontend*
*Context gathered: 2026-05-04*
