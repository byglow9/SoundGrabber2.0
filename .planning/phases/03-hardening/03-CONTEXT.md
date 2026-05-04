# Phase 3: Hardening - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Proteger a API contra abuso, input malformado e esgotamento de recursos antes da exposição pública.
Três proteções concretas:
- Rate limiting por IP no POST /jobs (429 com Retry-After)
- Sweeper ampliado para limpar arquivos parciais de workers mortos
- Respostas de erro síncronas (422) normalizadas para o mesmo formato dos erros de job

Sem UI, sem novas rotas, sem autenticação. A fase termina quando os 4 success criteria do ROADMAP.md forem atendidos por curl.

</domain>

<decisions>
## Implementation Decisions

### Rate Limiting
- **D-01:** Implementar com **slowapi** (biblioteca de rate limiting nativa FastAPI). Decorator direto na rota — mínimo de código, sem dependency nova relevante pois slowapi é o padrão do ecossistema FastAPI.
- **D-02:** Limite aplicado **somente no POST /jobs**. GET /jobs/{id} e GET /files/{id} são leves e não representam abuse surface.
- **D-03:** Valor padrão: **3 jobs por minuto por IP**, configurável via env var `RATE_LIMIT_PER_MINUTE`. Consistente com o padrão 12-factor do projeto (REDIS_URL, WAV_TTL_SECONDS em api/config.py). Sem limite por hora por enquanto — tunar conforme tráfego observado.
- **D-04:** Resposta 429 inclui **header `Retry-After`** com segundos até reset (RFC 9110). Body no formato `{error: "Too many requests. Try again in N seconds.", error_type: "rate_limit_error"}` — alinhado com D-07 abaixo.

### Sweeper de Arquivos Temporários
- **D-05:** Ampliar `sweep_expired_wavs` para **também limpar arquivos `.part` e `.ytdl`** em `/tmp` mais velhos que o TTL (15 min). Esses arquivos são deixados pelo yt-dlp quando o processo worker é morto via SIGKILL durante o download. O critério é o mesmo: mtime > wav_ttl.
- **D-06:** O padrão de glob do sweeper ampliado: `sg_*.wav`, `sg_*.part`, `sg_*.ytdl`. Prefixo `sg_` já garante que só arquivos do SoundGrabber são afetados.

### Formato de Erros Síncronos
- **D-07:** Adicionar **exception handler customizado** em `api/main.py` para `RequestValidationError` do Pydantic. Converte o 422 padrão do FastAPI para o formato unificado:
  ```json
  {
    "error": "URL must be a YouTube link (got: example.com)",
    "error_type": "validation_error"
  }
  ```
  Status HTTP permanece 422. O frontend tem um único formato para tratar erros síncronos e assíncronos.

### Claude's Discretion
- Estratégia de identificação de IP (X-Forwarded-For vs request.client.host) — planner decide baseado na configuração do proxy
- Storage backend do slowapi (in-memory ou Redis) — Redis é mais robusto se múltiplos workers forem usados
- Nome exato da string de rate limit do slowapi (ex: "3/minute" vs "3 per minute")
- Mensagem exata do 429 em português vs inglês — alinhada com o resto da API (que hoje está em inglês)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Projeto
- `.planning/PROJECT.md` — visão, princípios, restrições críticas
- `.planning/REQUIREMENTS.md` — UX-03 e UX-04 são os requisitos desta fase
- `.planning/ROADMAP.md` — 4 success criteria exatos para Phase 3 (seção "Phase Details")
- `.planning/STATE.md` — riscos conhecidos (IP flagging, temp file accumulation) e nota sobre rate limit numbers serem estimativas

### Fases anteriores
- `.planning/phases/02-api-layer/02-CONTEXT.md` — D-01 a D-07: TTL de 15min, estrutura api/, formato de erros de job, sweeper daemon, padrão 12-factor config
- `.planning/phases/01-processing-pipeline/01-CONTEXT.md` — D-08/D-09: convenção sg_*.wav em /tmp, responsabilidade de deleção

### Código existente
- `api/main.py` — sweep_expired_wavs() (função a ampliar para .part/.ytdl), lifespan (onde sweeper thread inicia), JobRequest validator (onde 422 é gerado)
- `api/config.py` — Settings dataclass (adicionar RATE_LIMIT_PER_MINUTE aqui)
- `api/tasks.py` — JobFailure (modelo de referência para o formato de erro a normalizar)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/main.py:sweep_expired_wavs(directory, ttl_seconds)` — função pura já testável; ampliar o glob para incluir `.part` e `.ytdl`
- `api/main.py:_run_sweeper_loop()` — daemon thread a cada 60s; sem mudança no loop, só na função chamada
- `api/config.py:Settings` — dataclass frozen; adicionar `rate_limit_per_minute: int` seguindo o mesmo padrão

### Established Patterns
- 12-factor config via env vars (`os.environ.get("...", default)`) — D-03 segue este padrão
- Formato de erro `{error: str, error_type: str}` já estabelecido nos job failures (D-05/D-06 do Phase 2) — D-07 normaliza os erros síncronos para o mesmo formato
- Redis já disponível (`redis_lib.from_url(settings.redis_url)`) — slowapi pode usar o mesmo Redis como storage backend

### Integration Points
- slowapi se integra via `Limiter(key_func=get_remote_address)` + `@limiter.limit(...)` no `@app.post("/jobs")`
- Exception handler registrado via `app.add_exception_handler(RequestValidationError, handler)` no mesmo `api/main.py`
- Sweeper ampliado: mudança isolada em `sweep_expired_wavs()` — zero impacto em rotas ou tasks

</code_context>

<specifics>
## Specific Ideas

- Rate limit string do slowapi: `f"{settings.rate_limit_per_minute}/minute"` — gerada dinamicamente a partir da env var
- Identificação de IP: usar `X-Forwarded-For` se estiver atrás de proxy/nginx, `request.client.host` para dev local — slowapi's `get_remote_address` já lida com isso por padrão
- Sweeper glob ampliado: `["sg_*.wav", "sg_*.part", "sg_*.ytdl"]` — prefixo sg_ como filtro de segurança

</specifics>

<deferred>
## Deferred Ideas

- **Limite por hora (20/hr):** Mencionado no STATE.md como estimativa. Adiado para tunagem pós-lançamento conforme tráfego observado.
- **Autenticação / API keys:** Out of scope por decisão do projeto (sem cadastro, sem fricção).

</deferred>

---

*Phase: 03-hardening*
*Context gathered: 2026-05-04*
