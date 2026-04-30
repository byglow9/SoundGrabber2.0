# Phase 2: API Layer - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Expor o pipeline (`pipeline.py`) via HTTP com fila de jobs. Três endpoints exercitáveis por `curl`:
- `POST /jobs` — aceita URL do YouTube, enfileira job, retorna job ID imediatamente
- `GET /jobs/{id}` — polling de status (queued → downloading → converting → analyzing → done) + resultado quando completo
- `GET /files/{id}` — streaming do WAV sem carregar o arquivo inteiro na memória

Sem UI, sem autenticação, sem hardening de produção (Fase 3). A fase termina quando três jobs concorrentes via `curl` completam sem o servidor travar.

</domain>

<decisions>
## Implementation Decisions

### Ciclo de vida do WAV
- **D-01:** TTL fixo de **15 minutos** após o job completar — arquivo `/tmp/sg_*.wav` é deletado após esse prazo por um background sweeper, independente de download ter ocorrido.
- **D-02:** Metadados do job no Redis têm o **mesmo TTL de 15 minutos** que o WAV. `GET /jobs/{id}` após expiração retorna 404 — simples e previsível.

### Estrutura do projeto
- **D-03:** Código da API em pasta `api/` com três módulos:
  - `api/main.py` — FastAPI app + rotas (POST /jobs, GET /jobs/{id}, GET /files/{id})
  - `api/tasks.py` — Celery tasks (download → convert → analyze)
  - `api/config.py` — Settings via env vars (Redis URL, TTL, concurrency cap)
  - `pipeline.py` permanece na raiz (Fase 1 não muda)
- **D-04:** Dependências da Fase 2 (fastapi, uvicorn, celery[redis], redis) adicionadas no mesmo `requirements.txt` existente — ambiente único, sem arquivo separado.

### Contrato de falha de job
- **D-05:** Quando um job falha, `GET /jobs/{id}` retorna `status: "failed"` com **mensagem sanitizada** no campo `error` (amigável para o usuário, não expõe internals do yt-dlp).
- **D-06:** Campo `error_type` incluído para distinguir categorias de falha sem parsear texto:
  - `"validation_error"` — URL inválida, vídeo muito longo, metadados ausentes
  - `"download_error"` — yt-dlp bloqueado, rede, token expirado
  - `"internal_error"` — falha inesperada no worker

  Exemplo de resposta de falha:
  ```json
  {
    "status": "failed",
    "error": "Video is too long (max 15 minutes).",
    "error_type": "validation_error"
  }
  ```

### Ambiente de desenvolvimento
- **D-07:** Setup **manual sem Docker** documentado no README:
  - Redis via `apt install redis-server` (ou equivalente no OS do dev)
  - Worker Celery em um terminal: `celery -A api.tasks worker --loglevel=info`
  - API em outro terminal: `uvicorn api.main:app --reload`
  - Docker Compose pode vir como opcional futuro, mas não é requisito da Fase 2

### Claude's Discretion
- Número exato de workers Celery concorrentes (STATE.md sugere cap de 3 — planner confirma)
- Prefetch multiplier e autoscale do Celery
- Redis connection pool settings
- Versões exatas dos pacotes (fastapi, celery, redis-py)
- Formato exato dos status intermediários além dos 5 definidos no ROADMAP.md

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Projeto
- `.planning/PROJECT.md` — visão, princípios, restrições críticas
- `.planning/REQUIREMENTS.md` — CORE-01, CORE-02, CORE-06 são os requisitos desta fase
- `.planning/ROADMAP.md` — success criteria exatos para Phase 2 (seção "Phase Details")
- `.planning/STATE.md` — riscos conhecidos (cap de 3 workers, yt-dlp drift, temp files) e todos pendentes

### Fase anterior
- `.planning/phases/01-processing-pipeline/01-CONTEXT.md` — todas as decisões da Fase 1 que esta fase herda (D-01 a D-10: auth env vars, contrato de funções importáveis, JSON shape, WAV path, responsabilidade de deleção)

### Código existente
- `pipeline.py` — módulo a ser importado diretamente (não reimplementar); funções: `check_duration`, `download_audio`, `convert_to_wav`, `validate_wav`, `analyze_audio`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline.py:download_audio(url, cookies_path, po_token) -> Path` — Stage 1 completo, Celery task chama diretamente
- `pipeline.py:analyze_audio(wav_path) -> dict` — retorna o JSON shape D-05 completo; `api/tasks.py` usa o dict para popular o job result no Redis
- `pipeline.py:check_duration(url, cookies_path) -> dict` — deve ser chamado antes do download para rejeitar vídeos longos antes de consumir banda

### Established Patterns
- Env vars como fonte de config: `YTDLP_COOKIES_FILE`, `YTDLP_PO_TOKEN` já estabelecidos — `api/config.py` segue o mesmo padrão 12-factor
- Erros como exceções tipadas: `ValueError` (validação), `RuntimeError` (download), `FileNotFoundError` (WAV ausente) — `api/tasks.py` captura cada tipo e mapeia para `error_type` correspondente (D-06)
- WAV path: `/tmp/sg_{uuid}.wav` — pipeline já produz esse nome; Fase 2 usa o mesmo prefixo `sg_` para o sweeper de limpeza

### Integration Points
- `api/tasks.py` importa `from pipeline import check_duration, download_audio, analyze_audio`
- Celery usa Redis como broker E backend (mesmo serviço Redis para fila + armazenamento de resultados)
- `GET /files/{id}` usa `FileResponse` ou streaming manual — não carrega WAV inteiro em memória (success criteria #3 do ROADMAP)

</code_context>

<specifics>
## Specific Ideas

- WAV lifecycle: TTL de 15 min escolhido por ser igual ao limite de duração máxima de vídeo aceito — fácil de lembrar e defensível
- Ambiente de dev: usuário prefere terminais manuais a Docker porque Docker é lento para buildar, reiniciar e ocupa armazenamento

</specifics>

<deferred>
## Deferred Ideas

Nenhuma — discussão manteve-se dentro do escopo da Fase 2.

</deferred>

---

*Phase: 02-api-layer*
*Context gathered: 2026-04-30*
