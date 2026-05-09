# Phase 7: Infrastructure Security - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the SoundGrabber application to Railway (PaaS), enforce Redis authentication on startup, deliver HSTS via FastAPI middleware, and bind Uvicorn to the Railway platform port. All four SEC-INFRA-* controls satisfied via Railway-native mechanisms rather than manual nginx/Let's Encrypt.

</domain>

<decisions>
## Implementation Decisions

### Plataforma de Deploy

- **D-01:** Deploy no **Railway** (PaaS) — não VPS com nginx manual.
- **D-02:** Usuário já tem conta Railway criada. A fase começa na criação do projeto/serviços, não no cadastro.
- **D-03:** URL de acesso será subdomínio Railway (`*.up.railway.app`) — sem domínio customizado nesta fase.
- **D-04:** HTTPS é automático via Railway — não requer nginx.conf nem certbot/Let's Encrypt.
- **D-05:** HTTP→HTTPS redirect é automático via Railway para o subdomínio gerado.

### Redis Auth (SEC-INFRA-01)

- **D-06:** `DEV_MODE=true` no `.env` local faz o startup skip a validação de senha do Redis. Em produção (Railway), `DEV_MODE` não é definido e a validação é obrigatória.
- **D-07:** A validação de `REDIS_URL` deve acontecer no startup da aplicação — verificar que a URL contém senha antes de aceitar tráfego. Falha com mensagem clara (não stack trace).
- **D-08:** Redis no Railway é provisionado como serviço Railway Redis — tem senha por padrão no `REDIS_URL` injetado automaticamente.

### HTTPS/HSTS (SEC-INFRA-03 e SEC-INFRA-04)

- **D-09:** `Strict-Transport-Security: max-age=31536000` entregue via **middleware Starlette** no FastAPI — não via nginx (não existe nginx nesta arquitetura).
- **D-10:** Railway garante SEC-INFRA-03 (HTTP→HTTPS redirect + TLS) nativamente.

### Uvicorn Binding (SEC-INFRA-02)

- **D-11:** Uvicorn deve escutar em `0.0.0.0:$PORT` no Railway (o `$PORT` é injetado pela plataforma). Railway gerencia o isolamento externamente — o critério de segurança de SEC-INFRA-02 (aplicação não exposta diretamente à internet) é satisfeito pela arquitetura Railway, não por bind em 127.0.0.1.
- **D-12:** `start.sh` é para desenvolvimento local. O Railway usa o comando de startup definido em `railway.toml` (ou `Procfile`) — separar as configurações de host/port entre os dois ambientes.

### Configuração de Deploy Railway

- **D-13:** Criar `railway.toml` na raiz do projeto com o comando de startup do uvicorn para produção.
- **D-14:** Variáveis de ambiente no Railway: `REDIS_URL` (injetado pelo Railway Redis), `WAV_TTL_SECONDS`, `RATE_LIMIT_PER_MINUTE`, `MAX_QUEUE_DEPTH` — sem `DEV_MODE`.
- **D-15:** O serviço Celery precisa de um **segundo serviço Railway** (ou worker separado no mesmo projeto) com acesso ao mesmo Redis.

### Claude's Discretion

- Estrutura exata do `railway.toml` (startCommand, healthcheck path, restart policy)
- Como o Celery worker é configurado no Railway (segundo serviço vs Procfile multi-process)
- Timeout de startup para a validação de Redis antes de aceitar conexões

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §SEC-INFRA — Definições de SEC-INFRA-01..04 com acceptance criteria
- `.planning/phases/06-application-security/06-VERIFICATION.md` — Evidências dos controles SEC-API e SEC-FILE já implementados (não reimplementar)

### Código existente relevante
- `api/config.py` — Settings dataclass; D-07 (Redis auth check) deve adicionar validação no `__post_init__` ou no lifespan do FastAPI
- `api/main.py` — Lifespan context manager; ponto de inserção para o startup check de Redis auth e o middleware HSTS
- `start.sh` — Startup local; Uvicorn roda com `--host 0.0.0.0 --port 8000` aqui — Railway usa comando separado
- `.planning/SECURITY-CHECKLIST.md` — Fonte de verdade dos controles ativos; deve ser atualizado com SEC-INFRA-01..04

### Railway
- Não há specs externas — Railway CLI e dashboard são os pontos de configuração. Sem arquivos de configuração proprietários além do `railway.toml`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/config.py` `Settings` dataclass — pode adicionar validação de Redis URL diretamente aqui (ou em lifespan)
- `api/main.py` `@asynccontextmanager lifespan` — ponto correto para startup check de Redis auth
- `api/main.py` `SlowAPIMiddleware` — padrão existente de middleware; HSTS segue o mesmo padrão

### Established Patterns
- Middlewares adicionados via `app.add_middleware()` — HSTS middleware segue esse padrão
- Configuração via env vars em `api/config.py` — qualquer nova variável (ex: `DEV_MODE`) vai aqui
- `start.sh` é desenvolvimento local; produção usa configuração separada

### Integration Points
- `api/main.py:lifespan` — startup check de Redis auth entra aqui
- `api/config.py:Settings` — `dev_mode: bool` e lógica de bypass entram aqui
- Nova `railway.toml` na raiz — ponto de entrada do deploy Railway

</code_context>

<specifics>
## Specific Ideas

- Redis URL validation: checar se `redis://` tem `:<password>@` ou se é `rediss://` com auth — se não tiver E `dev_mode` for false, levantar `RuntimeError` com mensagem clara antes de aceitar qualquer request.
- HSTS middleware: `app.add_middleware(...)` com header `Strict-Transport-Security: max-age=31536000; includeSubDomains` — simples, sem dependências extras.
- O `railway.toml` deve ter `startCommand` com uvicorn usando `$PORT`: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`.

</specifics>

<deferred>
## Deferred Ideas

- Domínio customizado (soundgrabber.com) — pode ser adicionado ao Railway depois sem nova fase
- nginx manual em VPS — não é mais o caminho escolhido, mas documentar como alternativa se Railway não atender
- Let's Encrypt certbot — não necessário com Railway

</deferred>

---

*Phase: 07-infrastructure-security*
*Context gathered: 2026-05-09*
