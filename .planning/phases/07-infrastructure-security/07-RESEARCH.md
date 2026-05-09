# Phase 7: Infrastructure Security - Research

**Researched:** 2026-05-09
**Domain:** Railway PaaS deployment, Redis auth startup enforcement, HSTS middleware, Uvicorn binding
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Plataforma de Deploy**
- D-01: Deploy no Railway (PaaS) — nao VPS com nginx manual.
- D-02: Usuario ja tem conta Railway criada. A fase comeca na criacao do projeto/servicos, nao no cadastro.
- D-03: URL de acesso sera subdomain Railway (`*.up.railway.app`) — sem dominio customizado nesta fase.
- D-04: HTTPS e automatico via Railway — nao requer nginx.conf nem certbot/Let's Encrypt.
- D-05: HTTP→HTTPS redirect e automatico via Railway para o subdomain gerado.

**Redis Auth (SEC-INFRA-01)**
- D-06: `DEV_MODE=true` no `.env` local faz o startup skip a validacao de senha do Redis. Em producao (Railway), `DEV_MODE` nao e definido e a validacao e obrigatoria.
- D-07: A validacao de `REDIS_URL` deve acontecer no startup da aplicacao — verificar que a URL contem senha antes de aceitar trafego. Falha com mensagem clara (nao stack trace).
- D-08: Redis no Railway e provisionado como servico Railway Redis — tem senha por padrao no `REDIS_URL` injetado automaticamente.

**HTTPS/HSTS (SEC-INFRA-03 e SEC-INFRA-04)**
- D-09: `Strict-Transport-Security: max-age=31536000` entregue via middleware Starlette no FastAPI — nao via nginx.
- D-10: Railway garante SEC-INFRA-03 (HTTP→HTTPS redirect + TLS) nativamente.

**Uvicorn Binding (SEC-INFRA-02)**
- D-11: Uvicorn deve escutar em `0.0.0.0:$PORT` no Railway. Railway gerencia o isolamento externamente. Criterio de seguranca de SEC-INFRA-02 e satisfeito pela arquitetura Railway.
- D-12: `start.sh` e para desenvolvimento local. O Railway usa o comando de startup definido em `railway.toml` — separar as configuracoes de host/port entre os dois ambientes.

**Configuracao de Deploy Railway**
- D-13: Criar `railway.toml` na raiz do projeto com o comando de startup do uvicorn para producao.
- D-14: Variaveis de ambiente no Railway: `REDIS_URL` (injetado pelo Railway Redis), `WAV_TTL_SECONDS`, `RATE_LIMIT_PER_MINUTE`, `MAX_QUEUE_DEPTH` — sem `DEV_MODE`.
- D-15: O servico Celery precisa de um segundo servico Railway com acesso ao mesmo Redis.

### Claude's Discretion

- Estrutura exata do `railway.toml` (startCommand, healthcheck path, restart policy)
- Como o Celery worker e configurado no Railway (segundo servico vs Procfile multi-process)
- Timeout de startup para a validacao de Redis antes de aceitar conexoes

### Deferred Ideas (OUT OF SCOPE)

- Dominio customizado (soundgrabber.com)
- nginx manual em VPS
- Let's Encrypt certbot
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-INFRA-01 | Redis exige autenticacao obrigatoria; startup falha com mensagem clara se REDIS_URL nao contiver senha (exceto quando DEV_MODE=true) | Validacao de URL no lifespan FastAPI; padrao `redis://:password@host` verificado via Celery docs |
| SEC-INFRA-02 | Uvicorn configurado para nao ser exposto diretamente; satisfeito por Railway isolar o container externamente (bind 0.0.0.0:$PORT) | Railway arquitetura PaaS; PORT injetado automaticamente; start local (127.0.0.1) vs producao (0.0.0.0) separados |
| SEC-INFRA-03 | HTTPS configurado; HTTP redireciona para HTTPS | Railway faz 301 automatico para GET; confirmado via docs Railway networking |
| SEC-INFRA-04 | Header HSTS (Strict-Transport-Security: max-age=31536000) presente em todas as respostas HTTPS | Starlette BaseHTTPMiddleware; padrao ja usado em `_security_headers` em api/main.py |
</phase_requirements>

---

## Summary

Esta fase entrega quatro controles de seguranca de infraestrutura (SEC-INFRA-01..04) usando Railway PaaS, sem nginx manual. O Railway automaticamente fornece HTTPS com redirect 301 HTTP→HTTPS (SEC-INFRA-03) e isola o container do acesso direto da internet (SEC-INFRA-02). O que precisa ser implementado em codigo e: (1) middleware HSTS no FastAPI para injetar o header `Strict-Transport-Security` em todas as respostas (SEC-INFRA-04), (2) validacao de REDIS_URL no startup para falhar cedo se a URL nao contem senha em producao (SEC-INFRA-01), e (3) arquivo `railway.toml` com startCommand correto para producao com `$PORT` injetado pelo Railway e segundo servico Railway para o Celery worker.

A maior parte do trabalho e codigo Python puro — nenhuma dependencia nova e necessaria. O padrao de middleware HSTS e identico ao `_security_headers` ja existente em `api/main.py`. A validacao de Redis URL entra no `lifespan` em `api/main.py`, com o campo `dev_mode: bool` adicionado ao `Settings` dataclass em `api/config.py`. O `railway.toml` e um arquivo TOML de ~10 linhas.

**Recomendacao primaria:** Implementar tudo em tres arquivos: `api/config.py` (campo `dev_mode`), `api/main.py` (validacao Redis no lifespan + middleware HSTS), `railway.toml` (startCommand para producao).

---

## Project Constraints (from CLAUDE.md)

Diretivas obrigatorias que o planejador deve verificar:

| Diretiva | Aplicabilidade a Fase 7 |
|----------|------------------------|
| Rate limiting em toda rota nova (`@limiter.limit`) | Nao aplicavel — nenhuma rota nova nesta fase |
| Request body validation com Pydantic BaseModel | Nao aplicavel — nenhuma rota nova |
| Body size limit (middleware `_limit_body_size` 4KB) | Ja existe; nao alterar |
| Sync routes com `request: Request, response: Response` | Nao aplicavel — nenhuma rota nova |
| Arquivos em /tmp com permissoes 0o600, prefixo `sg_` | Nao aplicavel — nenhum novo arquivo /tmp |
| Shell scripts: `set -e`, `chmod 750`, sem `eval` de input externo | Aplicavel — qualquer script auxiliar de deploy deve seguir esta regra |
| `tests/test_security.py` DEVE estar verde antes de commit em main | Aplicavel — os testes existentes devem continuar passando apos as mudancas |
| `.planning/SECURITY-CHECKLIST.md` deve ser atualizado com novos controles | OBRIGATORIO — SEC-INFRA-01..04 devem ser adicionados ao checklist |

---

## Standard Stack

### Core

| Biblioteca | Versao | Proposito | Por que padrao |
|------------|--------|-----------|----------------|
| FastAPI / Starlette | 0.136.1 / 1.0.0 (ja instalado) | Middleware HSTS via `add_middleware` ou `@app.middleware("http")` | Ja em uso; `BaseHTTPMiddleware` e o padrao estabelecido no projeto |
| railway CLI | 3.19.1 (instalado na maquina) | Criar projeto, servicos, injetar variaveis de ambiente | Ferramenta oficial Railway |

**Nenhuma dependencia nova em requirements.txt e necessaria para esta fase.** [VERIFIED: grep requirements.txt — todos os controles usam stdlib (os, re, urllib.parse) e bibliotecas ja instaladas]

### Alternativas Consideradas

| Em vez de | Poderia usar | Tradeoff |
|-----------|-------------|----------|
| Middleware `@app.middleware("http")` customizado para HSTS | `secweb` ou `secure.py` (libs terceiras) | Libs terceiras adicionam dependencia sem necessidade — uma linha de header nao justifica |
| Validacao de REDIS_URL em `lifespan` | Validacao em `Settings.__post_init__` | `__post_init__` quebraria os testes que usam `REDIS_URL=redis://localhost:6380/0` sem senha; lifespan com `dev_mode` check e mais cirurgico |

---

## Architecture Patterns

### Estrutura de Arquivos Afetados

```
/                       (raiz do projeto)
├── railway.toml        # NOVO — startCommand para producao
├── api/
│   ├── config.py       # MODIFICAR — adicionar campo dev_mode: bool
│   └── main.py         # MODIFICAR — validacao Redis em lifespan + middleware HSTS
└── .planning/
    └── SECURITY-CHECKLIST.md  # MODIFICAR — adicionar secao 6 com SEC-INFRA-01..04
```

### Pattern 1: HSTS via middleware `@app.middleware("http")`

**O que e:** Adicionar header `Strict-Transport-Security` em todas as respostas HTTP usando o mesmo padrao ja aplicado em `_security_headers`.

**Quando usar:** Sempre que o header precisa aparecer em 100% das respostas, independente de rota.

**Exemplo:**
```python
# Source: padrao existente em api/main.py (_security_headers)
# Starlette docs: https://www.starlette.dev/middleware/
@app.middleware("http")
async def _hsts(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response
```

**Decisao do planner:** Integrar em `_security_headers` existente (uma linha a mais) OU criar middleware separado `_hsts`. Recomendacao: integrar em `_security_headers` para manter um unico ponto de manutencao dos headers de seguranca.

**Aviso importante:** O header HSTS nao causa dano em ambiente local (HTTP), porque browsers so processam HSTS em respostas recebidas via HTTPS. Em local com HTTP, o header e enviado mas ignorado pelo browser. [ASSUMED — comportamento de browser padrao; nao ha risco de "HSTS pin" local]

### Pattern 2: Validacao de Redis URL no lifespan

**O que e:** Checagem early-fail no startup que levanta `RuntimeError` se a URL nao contem senha e `DEV_MODE` nao esta ativo.

**Formato de URL Redis com senha (padrão):** `redis://:password@host:port/db` [VERIFIED: Celery docs — https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html]

**Deteccao de senha na URL:** Presenca de `@` no URL indica credenciais no formato `user:pass@host` ou `:pass@host`. A URL sem senha tem formato `redis://host:port/db` — sem `@`.

**Exemplo:**
```python
# Source: api/main.py lifespan — ponto de insercao confirmado pelo CONTEXT.md
@asynccontextmanager
async def lifespan(app: FastAPI):
    # SEC-INFRA-01: Redis auth enforcement
    if not settings.dev_mode:
        if "@" not in settings.redis_url:
            raise RuntimeError(
                "REDIS_URL does not contain a password. "
                "Set REDIS_URL=redis://:password@host:port/db or enable DEV_MODE=true "
                "for local development only."
            )
    # ... resto do lifespan
```

**Nota sobre o codigo atual:** `api/main.py` linha 112 ja tem `if "@" not in settings.redis_url` — mas apenas loga um WARNING. A mudanca e substituir o `logger.warning` por `raise RuntimeError` quando `not settings.dev_mode`. [VERIFIED: leitura de api/main.py]

### Pattern 3: Campo `dev_mode` em Settings

**O que e:** Adicionar `dev_mode: bool` ao dataclass `Settings` em `api/config.py`, lido de `DEV_MODE` env var.

**Exemplo:**
```python
# Source: padrao existente em api/config.py
@dataclass(frozen=True)
class Settings:
    # ... campos existentes ...
    dev_mode: bool = field(
        default_factory=lambda: os.environ.get("DEV_MODE", "false").lower() == "true"
    )
```

**Interacao com conftest.py:** `conftest.py` define `REDIS_URL=redis://localhost:6380/0` (sem senha). Para que os testes existentes continuem passando, o conftest tambem precisa definir `DEV_MODE=true`. [VERIFIED: leitura de tests/conftest.py linha 13]

### Pattern 4: railway.toml

**O que e:** Arquivo de configuracao Railway que define o startCommand para producao.

**Formato TOML verificado:** [VERIFIED: docs.railway.com/config-as-code/reference]

```toml
# Source: docs.railway.com/config-as-code/reference
[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT --limit-concurrency 100 --timeout-keep-alive 5"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
```

**Por que `$PORT` e nao `8000`:** Railway injeta a variavel `PORT` em cada deploy com o valor correto para o container. Hardcodar `8000` causaria conflito se Railway alocar porta diferente. [VERIFIED: multiplas fontes — docs.railway.com, station.railway.com]

**Por que `0.0.0.0`:** Railway gerencia o isolamento de rede externamente (o container nao e exposto diretamente). Dentro do container, uvicorn precisa de `0.0.0.0` para aceitar conexoes do proxy Railway. Bind em `127.0.0.1` quebraria o deploy. [VERIFIED: D-11 do CONTEXT.md + arquitetura PaaS padrao]

**Healthcheck path:** `/health` ja existe em `api/main.py` e retorna 200 quando Redis esta saudavel (SEC-API-03). [VERIFIED: leitura de api/main.py]

### Pattern 5: Segundo Servico Railway para Celery Worker

**O que e:** No Railway, um worker Celery e implementado como um segundo servico no mesmo projeto, deployado do mesmo repositorio, com startCommand diferente.

**Configuracao:** O segundo servico nao precisa de `railway.toml` diferente — pode ter o startCommand configurado diretamente no dashboard Railway ou via variavel de ambiente `RAILWAY_SERVICE_START_COMMAND`. O padrao recomendado para projetos simples e configurar via dashboard. [VERIFIED: comunidade Railway — dev.to/techbychoiceorg/django-celery-and-redis-on-railway-214h]

**StartCommand do worker:**
```
celery -A api.tasks worker --loglevel=info --concurrency=3
```

**Variaveis compartilhadas:** Ambos os servicos (uvicorn e celery) usam o mesmo `REDIS_URL` injetado pelo servico Railway Redis. No Railway, variaveis de um servico podem ser referenciadas por outros servicos do mesmo projeto via sintaxe `${{NomeDoServico.VARIAVEL}}`. [VERIFIED: docs Railway Redis — docs.railway.com/guides/redis]

### Anti-Patterns a Evitar

- **Hardcodar porta `8000` no railway.toml startCommand:** Railway injeta `$PORT` — hardcodar causa falha silenciosa se Railway alocar porta diferente.
- **Aplicar HSTS via `HTTPSRedirectMiddleware` do Starlette:** Esta middleware faz redirect interno (util se o FastAPI recebe HTTP diretamente) — no Railway o redirect ja acontece no edge, entao o middleware geraria redirects duplos ou seria ineficaz. Usar apenas o `@app.middleware("http")` para o header.
- **Substituir o `@` check por regex complexo:** `"@" not in redis_url` e suficiente para detectar ausencia de credenciais. URLs com `@` no path sao invalidas para Redis. Regex nao adiciona valor aqui.
- **Colocar `DEV_MODE=true` nas variaveis de ambiente do Railway (producao):** Isso desativaria a verificacao de seguranca em producao. O `DEV_MODE` so existe no `.env` local.
- **Adicionar `DEV_MODE=true` ao `.env` em vez de ao conftest.py:** O `.env` e carregado em desenvolvimento local pelo `start.sh`. Se um desenvolvedor nao executar via `start.sh`, a variavel nao estara setada. Mais robusto: conftest.py seta `os.environ["DEV_MODE"] = "true"` diretamente antes dos imports.

---

## Don't Hand-Roll

| Problema | Nao construir | Usar | Por que |
|----------|--------------|------|---------|
| HTTPS/TLS + renovacao de certificado | nginx + certbot manual | Railway PaaS (automatico) | Railway gerencia LetsEncrypt com renovacao automatica de 90 dias; certbot cron e fonte de downtime se mal configurado |
| HTTP→HTTPS redirect | nginx `return 301` | Railway edge (automatico) | Confirmado: Railway faz 301 automatico para GET requests em HTTP [VERIFIED: docs.railway.com/networking/public-networking/specs-and-limits] |
| HSTS via third-party lib | `secweb`, `secure.py` | Uma linha em middleware existente | Overhead de dependencia sem beneficio para uma unica linha de header |

---

## Common Pitfalls

### Pitfall 1: Testes quebrando por Redis URL sem senha

**O que acontece:** Apos adicionar `raise RuntimeError` no lifespan quando `"@" not in redis_url`, todos os testes unitarios que usam `api_client` falham com `RuntimeError` no startup.

**Por que acontece:** `conftest.py` define `REDIS_URL=redis://localhost:6380/0` (sem senha, sem `@`). O lifespan e executado pelo `TestClient` ao inicializar. Com a validacao nova e sem `DEV_MODE=true`, o lifespan levanta `RuntimeError` antes de qualquer teste.

**Como evitar:** Adicionar `os.environ.setdefault("DEV_MODE", "true")` em `conftest.py` antes dos imports de `api.*`, na mesma linha que o `setdefault("REDIS_URL", ...)` ja existente. [VERIFIED: leitura de tests/conftest.py]

**Sinais de aviso:** Todos os testes do `api_client` fixture falham com `RuntimeError: REDIS_URL does not contain a password`.

### Pitfall 2: `$PORT` nao expandido no railway.toml

**O que acontece:** Uvicorn inicia na porta errada e o healthcheck nunca passa; deploy e marcado como falho.

**Por que acontece:** No TOML, `$PORT` dentro de string e interpolado pelo shell quando o `startCommand` e executado. Mas se a string for mal formatada (ex: aspas simples no TOML que previnem expansao), a variavel nao e expandida.

**Como evitar:** Usar aspas duplas no TOML e testar o startCommand localmente com `PORT=8000 uvicorn api.main:app --host 0.0.0.0 --port $PORT`. [ASSUMED — comportamento de expansao de variaveis no shell; padrao Unix]

### Pitfall 3: Segundo servico Celery sem REDIS_URL configurado

**O que acontece:** O worker Celery inicia mas nao consegue conectar ao broker Redis, ficando em estado de erro silencioso.

**Por que acontece:** No Railway, variaveis de ambiente de um servico nao sao automaticamente herdadas por outros servicos. O `REDIS_URL` precisa ser adicionado explicitamente ao segundo servico (worker), ou configurado como referencia `${{Redis.REDIS_URL}}`.

**Como evitar:** No dashboard Railway, adicionar `REDIS_URL = ${{Redis.REDIS_URL}}` (referencia de variavel Railway) nas configuracoes do servico Celery, assim como as demais variaveis necessarias (`WAV_TTL_SECONDS`, etc.). [VERIFIED: docs.railway.com/guides/redis — "Services within your project can connect to the Redis server by referencing the environment variables"]

### Pitfall 4: HSTS header causando lock em HTTP local

**O que acontece:** Developer acessa `http://localhost:8000` e o browser processa o header HSTS, passando a redirecionar automaticamente para HTTPS para todos os acessos futuros ao localhost.

**Por que acontece:** O browser processa HSTS headers mesmo em HTTP (embora a RFC 6797 recomende ignorar em HTTP). Alguns browsers modernos podem processar o header mesmo sem HTTPS.

**Como evitar:** O risco e baixo — HSTS pin em `localhost` afeta apenas `localhost`, nao outros dominios. Se for problema, o planner pode adicionar condicional: `if request.url.scheme == "https"` antes de adicionar o header. [ASSUMED — comportamento de browser; a RFC 6797 sec 7.2 recomenda que clientes ignorem HSTS de conexoes HTTP, mas implementacoes variam]

### Pitfall 5: `Settings` frozen=True impede adicao de campo

**O que acontece:** `TypeError` ao tentar instanciar `Settings` com o novo campo se a assinatura do `__init__` nao for compativel.

**Por que acontece:** `Settings` usa `@dataclass(frozen=True)`. Adicionar um campo novo com `default_factory` e compativel com `frozen=True` — nao ha problema. [VERIFIED: leitura de api/config.py — frozen=True e compativel com novos campos com default]

---

## Code Examples

Padroes verificados nas fontes:

### railway.toml completo (producao)

```toml
# Source: docs.railway.com/config-as-code/reference
[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT --limit-concurrency 100 --timeout-keep-alive 5"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
```

### Campo `dev_mode` em api/config.py

```python
# Source: padrao existente em api/config.py
dev_mode: bool = field(
    default_factory=lambda: os.environ.get("DEV_MODE", "false").lower() == "true"
)
```

### Validacao Redis no lifespan em api/main.py

```python
# Source: api/main.py linhas 111-117 (substituicao do logger.warning atual)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # SEC-INFRA-01: Redis auth enforcement
    if not settings.dev_mode:
        if "@" not in settings.redis_url:
            raise RuntimeError(
                "REDIS_URL does not contain a password. "
                "Set a Redis URL with credentials: redis://:password@host:port/db. "
                "For local development only, set DEV_MODE=true."
            )
    # sweeper thread (codigo existente)
    sweeper = threading.Thread(...)
    sweeper.start()
    yield
```

### Middleware HSTS integrado em `_security_headers`

```python
# Source: padrao existente em api/main.py (_security_headers middleware)
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none';"
    )
    # SEC-INFRA-04: HSTS — entregue via FastAPI porque Railway nao adiciona automaticamente
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

### conftest.py — adicionar DEV_MODE antes dos imports

```python
# Source: tests/conftest.py linha 13 (adicao ao bloco existente)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("DEV_MODE", "true")  # NOVO — evita RuntimeError no lifespan
```

---

## State of the Art

| Abordagem antiga | Abordagem atual | Mudanca | Impacto |
|-----------------|-----------------|---------|---------|
| nginx + certbot em VPS | Railway PaaS (TLS automatico) | CONTEXT.md D-01..05 | Elimina toda configuracao manual de nginx, certbot, renovacao de certs |
| Uvicorn bind 127.0.0.1 | Uvicorn bind 0.0.0.0:$PORT | CONTEXT.md D-11 | Necessario para Railway; isolamento e feito pela plataforma |
| `logger.warning` para Redis sem senha | `raise RuntimeError` quando `not dev_mode` | Esta fase | Early-fail real vs aviso silencioso ignorado |

**Deprecado/desatualizado em STATE.md:**
- "Let's Encrypt cert renewal automation" listado como risco (linha 99 de STATE.md): nao aplicavel — Railway gerencia renovacao automaticamente. Este risco pode ser removido do STATE.md.
- Todos os todos de VPS em STATE.md (linha 109-114) sao pre-Railway e devem ser atualizados ou removidos.

---

## Assumptions Log

| # | Claim | Secao | Risco se errado |
|---|-------|-------|-----------------|
| A1 | HSTS header em resposta HTTP e ignorado por browsers modernos (sem risco de pin em localhost) | Common Pitfalls #4 | Baixo — se browser pinar localhost em HSTS, developer perde acesso HTTP local; resolvido limpando HSTS no browser |
| A2 | `$PORT` dentro de string em `startCommand` no TOML e expandido pelo shell no Railway | Common Pitfalls #2 | Medio — se nao expandir, deploy falha; detectavel no primeiro deploy |
| A3 | `includeSubDomains` no HSTS nao causa problema no subdomain `*.up.railway.app` (Railway controla o dominio) | Code Examples | Baixo — Railway controla o dominio; sem risco de pinar subdomains de terceiros |

**Claims verificadas (nao assumidas):**
- Formato de URL Redis com senha: `redis://:password@host:port/db` [VERIFIED: Celery docs]
- Railway faz 301 HTTP→HTTPS automatico para GET [VERIFIED: docs.railway.com/networking]
- `@` como indicador de credenciais em Redis URL [VERIFIED: padrao ja existente em api/main.py linha 112]
- `railway.toml` schema (startCommand, healthcheckPath, healthcheckTimeout, restartPolicyType) [VERIFIED: docs.railway.com/config-as-code/reference]
- Railway Railway Redis injeta `REDIS_URL` com senha automaticamente [VERIFIED: docs.railway.com/guides/redis]
- `Settings` dataclass em api/config.py usa `frozen=True` com `default_factory` [VERIFIED: leitura de api/config.py]
- Lifespan ja tem `if "@" not in settings.redis_url` como logger.warning [VERIFIED: leitura de api/main.py linha 112]

---

## Open Questions (RESOLVED)

1. **O Railway Railway Redis inclui o `@` no REDIS_URL injetado automaticamente?**
   - O que sabemos: Railway Redis injeta `REDIS_URL` e tem senha por padrao (D-08). Formato documentado: `redis://default:${{REDIS_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:6379`.
   - O que e incerto: Se o URL injetado segue exatamente este formato ou pode variar.
   - RESOLVED: A validacao `"@" not in redis_url` e robusta para qualquer URL com credenciais no formato `user:pass@host` ou `:pass@host`. O primeiro deploy em Railway confirmara isso imediatamente via healthcheck.

2. **Celery worker como segundo servico ou via `railway.toml` multi-servico?**
   - O que sabemos: Railway nao tem suporte nativo a multi-process em um unico servico via Procfile equivalente no `railway.toml`. A abordagem padrao da comunidade e dois servicos Railway no mesmo projeto.
   - O que e incerto: Se Railway tem algum mecanismo de "worker service" nativo que simplificaria a configuracao.
   - RESOLVED: Segundo servico Railway — esta e a abordagem documentada e testada pela comunidade (Django + Celery + Redis no Railway). Configurar via dashboard Railway Dashboard com startCommand `celery -A api.tasks worker --loglevel=info --concurrency=3`.

---

## Environment Availability

| Dependencia | Requerida por | Disponivel | Versao | Fallback |
|-------------|--------------|-----------|--------|----------|
| Railway CLI | Deploy, configuracao de servicos | Sim | 3.19.1 | Dashboard Railway (manual) |
| Python 3.11 (Railway buildpack) | Uvicorn + FastAPI em producao | Sim (Railway detecta automaticamente via requirements.txt) | 3.11+ | Especificar `.python-version` se necessario |
| Redis (Railway servico) | Celery broker + rate limiting | Necessita provisionamento no Railway | — | — |

**Dependencias ausentes sem fallback:**
- Conta Railway com projeto criado (usuario ja tem conta — D-02; projeto precisa ser criado como primeira tarefa)

**Dependencias ausentes com fallback:**
- Nenhuma.

---

## Validation Architecture

### Test Framework

| Propriedade | Valor |
|-------------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (raiz do projeto) |
| Comando rapido | `pytest tests/test_security.py -x -q` |
| Suite completa | `pytest tests/ -v -m "not e2e and not integration"` |

### Phase Requirements → Test Map

| Req ID | Comportamento | Tipo de Teste | Comando Automatizado | Arquivo Existe? |
|--------|--------------|---------------|---------------------|-----------------|
| SEC-INFRA-01 | Startup falha com RuntimeError se REDIS_URL sem senha e DEV_MODE nao ativo | unit | `pytest tests/test_security.py::test_redis_auth_required -x` | Nao — Wave 0 |
| SEC-INFRA-01 | Startup passa quando DEV_MODE=true mesmo sem senha na URL | unit | `pytest tests/test_security.py::test_redis_auth_bypass_dev_mode -x` | Nao — Wave 0 |
| SEC-INFRA-02 | Uvicorn em 0.0.0.0:$PORT (verificacao de configuracao) | manual | Verificar railway.toml startCommand via `grep` | N/A — arquivo |
| SEC-INFRA-03 | HTTP→HTTPS redirect (Railway automatico) | smoke/manual | `curl -s -o /dev/null -w "%{http_code}" http://app.up.railway.app/` esperado 301 | N/A — infra |
| SEC-INFRA-04 | Header HSTS presente em todas as respostas | unit | `pytest tests/test_security.py::test_hsts_header -x` | Nao — Wave 0 |

**Nota importante para SEC-INFRA-01:** O teste unit DEVE usar `monkeypatch` ou `patch` para controlar `settings.dev_mode` e `settings.redis_url` sem depender de variaveis de ambiente globais. O `lifespan` e invocado pelo `TestClient`; para testar o comportamento de startup, o teste deve criar um `TestClient` fresco com settings mockados. Alternativa: testar a funcao de validacao diretamente (extrair logica de validacao para funcao `_check_redis_auth(redis_url, dev_mode)` chamada no lifespan).

### Sampling Rate

- **Por commit de tarefa:** `pytest tests/test_security.py -x -q`
- **Por merge de wave:** `pytest tests/ -v -m "not e2e and not integration"`
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_security.py::test_redis_auth_required` — cobre SEC-INFRA-01 (startup falha sem senha)
- [ ] `tests/test_security.py::test_redis_auth_bypass_dev_mode` — cobre SEC-INFRA-01 (DEV_MODE=true bypassa)
- [ ] `tests/test_security.py::test_hsts_header` — cobre SEC-INFRA-04 (header HSTS presente)
- [ ] `tests/conftest.py` — adicionar `os.environ.setdefault("DEV_MODE", "true")` para evitar falha nos testes existentes apos a mudanca de `logger.warning` para `raise RuntimeError`

---

## Security Domain

### Applicable ASVS Categories

| Categoria ASVS | Aplica | Controle Padrao |
|---------------|--------|-----------------|
| V2 Authentication | nao | — |
| V3 Session Management | nao | — |
| V4 Access Control | nao | — |
| V5 Input Validation | nao (nenhuma rota nova) | — |
| V6 Cryptography | parcial | TLS gerenciado pelo Railway (LetsEncrypt RSA 2048) |
| V9 Communications (Transport Layer Security) | sim | Railway TLS 1.2+; HSTS max-age=31536000 via middleware |
| V14 Configuration | sim | Redis auth obrigatoria em producao; DEV_MODE bypass documentado |

### Known Threat Patterns

| Pattern | STRIDE | Mitigacao Padrao |
|---------|--------|-----------------|
| Redis sem senha exposto na rede | Elevation of Privilege | Startup check: `raise RuntimeError` se URL sem `@` e `dev_mode=False` |
| Downgrade de HTTPS para HTTP (MITM) | Tampering | HSTS header `max-age=31536000`; Railway TLS obrigatorio |
| Redis broker exposto publicamente | Spoofing / Tampering | Railway Redis: acesso por internal hostname apenas (private network) |

---

## Sources

### Primary (HIGH confidence)
- `api/main.py` — lido diretamente; lifespan existente, middleware `_security_headers`, padrao de validacao linha 112
- `api/config.py` — lido diretamente; estrutura do dataclass `Settings` com `frozen=True` e `default_factory`
- `tests/conftest.py` — lido diretamente; `REDIS_URL` sem senha para testes
- `tests/test_security.py` — lido diretamente; testes existentes para Phase 6
- `docs.railway.com/config-as-code/reference` — schema completo do railway.toml (startCommand, healthcheckPath, healthcheckTimeout, restartPolicyType)
- `docs.railway.com/networking/public-networking/specs-and-limits` — Railway faz 301 automatico para HTTP GET
- `docs.railway.com/guides/redis` — Railway Redis injeta REDIS_URL; variaveis disponiveis (REDISHOST, REDISPASSWORD, REDIS_URL, etc.)

### Secondary (MEDIUM confidence)
- `docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html` — formato Redis URL com senha: `redis://:password@host:port/db`
- `starlette.dev/middleware/` — BaseHTTPMiddleware e HTTPSRedirectMiddleware; padrao para headers customizados
- `dev.to/techbychoiceorg/django-celery-and-redis-on-railway-214h` — Celery worker como segundo servico Railway; variaveis compartilhadas

### Tertiary (LOW confidence)
- Comportamento HSTS em HTTP (RFC 6797 sec 7.2) — browsers devem ignorar HSTS headers recebidos via HTTP; implementacao varia por browser

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — nenhuma lib nova; padrao existente do projeto
- Architecture: HIGH — baseada em codigo existente lido diretamente e docs Railway verificadas
- Pitfalls: HIGH para Pitfalls 1-3 (verificados no codigo); MEDIUM para Pitfall 4 (comportamento browser)
- Railway behavior: HIGH para HTTP→HTTPS 301 (verificado em docs oficiais); MEDIUM para formato exato de REDIS_URL injetado

**Research date:** 2026-05-09
**Valid until:** 2026-06-09 (Railway docs estaveis; stdlib Python estaveis; risk: Railway pode mudar formato de injecao de variaveis)
