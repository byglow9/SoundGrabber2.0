# Phase 4: Frontend - Research

**Researched:** 2026-05-04
**Domain:** Vanilla JS state machine + FastAPI static file serving
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Intervalo fixo de **2 segundos** para `GET /jobs/{id}`. Sem lógica adaptativa.
- **D-02:** Timeout de **3 minutos** de polling sem conclusão → mensagem de erro. Polling encerrado.
- **D-03:** Parar o polling assim que o status retornar `done` ou `failed`.
- **D-04:** Erro **422** — manter conteúdo do campo URL, destacar campo visualmente, mensagem inline. Usuário pode resubmeter diretamente.
- **D-05:** Erro **429** — exibir countdown ao vivo usando `Retry-After` header. Botão desabilitado durante contagem. Exemplo: "Limite atingido. Tente novamente em 47s."
- **D-06:** Job **falhou** — mensagem clara + botão "Tentar novamente" que reutiliza URL já no campo e resubmete sem interação adicional.
- **D-07:** Cálculo de tamanho WAV **client-side** a partir de `duration_sec`. Zero mudança na API.
- **D-08:** Fórmula: `duration_sec × 44100 × 2 × 2 / 1_000_000`. Prefixo `~`. Acima de 10 MB: 0 casas decimais; abaixo: 1 casa decimal.
- **D-09:** Tamanho exibido **após job completar**, antes do download. Parte do card de resultado.
- **D-10:** Phase 4 entrega **HTML div-based sem CSS**. Sem `<style>` inline, sem arquivo CSS.
- **D-11:** Estrutura HTML usa `<div>` genérico. Phase 5 reescreve para tabelas Y2K.

### Claude's Discretion

- Como FastAPI serve o `index.html` (StaticFiles, Jinja2, ou rota `GET /` com FileResponse)
- Estrutura interna do JS: event listeners, state machine, organização em vanilla JS
- Exatamente quais classes/IDs colocar no HTML para Phase 5 conectar estilos
- Se `download_url` vem da resposta da API ou é construído no frontend como `/files/{job_id}`

### Deferred Ideas (OUT OF SCOPE)

- Estética Y2K/neoworlds.online — aplicada em Phase 5
- CORS configuration — apenas se frontend separado do backend (fora do escopo v1)
- Waveform visualization — v2
- Progressive enhancement — versão sem JS para browsers antigos (fora do escopo v1)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Usuário pode colar um link do YouTube em um campo de texto e iniciar o processamento | Campo `<input>` + botão de submit + `fetch POST /jobs` com campo `youtube_url` |
| UX-01 | Barra de progresso exibe a etapa atual do processamento (baixando → convertendo → analisando) | Polling `GET /jobs/{id}` a 2 s; labels mapeados de `status`+`stage` no UI-SPEC |
| UX-02 | Sistema exibe o tamanho estimado do arquivo WAV antes do download | `Math.round(duration_sec * 44100 * 2 * 2 / 1_000_000)` após `status === "done"` |
</phase_requirements>

---

## Summary

Phase 4 entrega uma interface web funcional sem nenhum CSS — apenas HTML semântico com IDs/classes para o JavaScript e para a Phase 5 estilizar. O design contract completo (machine de estados, estrutura HTML, copywriting) já está aprovado no `04-UI-SPEC.md` datado de 2026-05-04. O trabalho desta fase é implementar exatamente o que o spec descreve, sem variações.

A arquitetura é simples: FastAPI serve `static/index.html` via `GET /` com `FileResponse` + monta `static/` em `/static` para o `app.js`. Todos os requests de API são same-origin — sem CORS. O JavaScript é um único arquivo `static/app.js` com uma máquina de estados de 8 estados controlando visibilidade de elementos via `element.hidden`.

Um pitfall crítico identificado: o `04-UI-SPEC.md` documenta o campo do POST como `{ "url": "..." }`, mas a API (`api/main.py`) usa `{ "youtube_url": "..." }`. O JavaScript DEVE enviar `youtube_url` — caso contrário todos os submits retornarão 422. [VERIFIED: api/main.py:53 — `class JobRequest(BaseModel): youtube_url: str`]

**Recomendação primária:** Usar `GET /` com `FileResponse` para `index.html` + `app.mount("/static", StaticFiles(directory="static"))` para `app.js`. Padrão verificado em produção — API routes definidas antes do mount ganham prioridade. [VERIFIED: teste funcional com FastAPI 0.136.1 / Starlette 1.0.0]

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Servir index.html | Backend (FastAPI) | — | Same-origin; evita CORS e configuração extra |
| Servir app.js | Backend (FastAPI StaticFiles) | — | Arquivo estático; montado em /static |
| State machine (8 estados) | Browser (JS) | — | Lógica de UI é client-side por definição |
| Polling GET /jobs/{id} | Browser (JS) | — | setInterval no cliente |
| Cálculo de tamanho WAV | Browser (JS) | — | D-07: zero mudança na API |
| Countdown Retry-After | Browser (JS) | — | setInterval local; não sincroniza com servidor |
| Download WAV | Browser (nativo) | — | `<a href download>` — sem JS, sem fetch |
| Validação de URL | Backend (Pydantic) | — | Validação real é no servidor; frontend apenas exibe o erro 422 |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.136.1 (pinned) | Serve index.html e app.js | Já instalado; `GET /` + `StaticFiles` é nativo |
| Starlette StaticFiles | 1.0.0 (via FastAPI) | Servir arquivos estáticos do diretório `static/` | Incluído no FastAPI sem dependência adicional |
| Vanilla JS (ES2020) | Browser nativo | State machine, fetch, DOM manipulation | Restrição do projeto — zero frameworks |

[VERIFIED: requirements.txt — fastapi==0.136.1; `from fastapi.staticfiles import StaticFiles` importado OK]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `html.parser` (stdlib) | Python 3.12 | Parse HTML em testes para verificar IDs/classes | Nos testes pytest de Phase 4 |
| pytest + httpx TestClient | 9.0.3 / 0.28.1 | Testar `GET /` retorna HTML, verificar rotas coexistem | Testes automatizados de integração leve |

[VERIFIED: requirements.txt — pytest==9.0.3, httpx>=0.27]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `GET /` FileResponse + `/static` mount | `app.mount("/", StaticFiles(html=True))` | html=True também funciona (testado), mas menos explícito; `GET /` FileResponse é mais legível |
| `GET /` FileResponse | Jinja2Templates | Jinja2 é overkill para um HTML estático sem template vars; acrescenta dependência |
| `setInterval` polling | WebSocket / SSE | SSE seria mais eficiente mas acrescenta complexidade ao backend; polling a 2 s é suficiente para a UX exigida |

**Installation:** Nenhuma instalação adicional necessária. Todas as dependências já estão em `requirements.txt`.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  │  GET /                    ┌─────────────────┐
  ├──────────────────────────►│ FastAPI GET /    │
  │  ← 200 index.html         │ FileResponse     │
  │                           └─────────────────┘
  │  GET /static/app.js        ┌─────────────────┐
  ├──────────────────────────►│ StaticFiles      │
  │  ← 200 app.js             │ /static mount    │
  │                           └─────────────────┘
  │
  │ [User submits URL]
  │  POST /jobs               ┌─────────────────┐
  ├──────────────────────────►│ FastAPI POST     │
  │  {youtube_url: "..."}     │ /jobs            │
  │  ← 202 {job_id}           │ (rate-limited)   │
  │  OR ← 422 {error,         └─────────────────┘
  │           error_type}
  │  OR ← 429 + Retry-After
  │
  │ [setInterval 2000ms]
  │  GET /jobs/{id}           ┌─────────────────┐
  ├──────────────────────────►│ FastAPI GET      │
  │  ← {status, stage, ...}   │ /jobs/{job_id}   │
  │  (repeat until done/      └─────────────────┘
  │   failed/180s timeout)
  │
  │ [status === "done"]
  │  <a href="/files/{id}"    ┌─────────────────┐
  │   download>──────────────►│ FastAPI GET      │
  │  ← WAV FileResponse       │ /files/{job_id}  │
  │                           └─────────────────┘
```

### Recommended Project Structure

```
static/
├── index.html      # HTML sem CSS; IDs/classes para JS + Phase 5
└── app.js          # State machine completo; único arquivo JS

api/
└── main.py         # Adicionar: GET /, StaticFiles mount
```

### Pattern 1: FastAPI Serving Static Files (Recomendado)

**What:** `GET /` retorna `index.html` via `FileResponse`; `app.mount("/static", ...)` serve `app.js`.
**When to use:** Sempre que se quer que `/` sirva o HTML e `/static/app.js` sirva o script, sem shadowear as rotas da API.

```python
# Source: VERIFIED — teste funcional com FastAPI 0.136.1 + Starlette 1.0.0
# Adicionar em api/main.py

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent.parent / "static"

@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))

# Mount DEPOIS de definir todas as rotas da API
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
```

Regra de ouro: rotas definidas antes do mount ganham prioridade. [VERIFIED: teste mostra `GET /jobs` retorna 200 JSON com o mount ativo]

**Pitfall:** `StaticFiles` lança `RuntimeError("Directory '...' does not exist")` no startup se `static/` não existir. O diretório deve ser criado antes de montar. [VERIFIED: Starlette 1.0.0 source — `if check_dir and directory is not None and not os.path.isdir(directory): raise RuntimeError`]

### Pattern 2: Máquina de Estados JS

**What:** Variável de estado global + função `setState(newState, payload)` que chama o UI updater correspondente.
**When to use:** Sempre — o spec já define exatamente este padrão.

```javascript
// Source: 04-UI-SPEC.md (aprovado 2026-05-04)
let state = 'IDLE';
let jobId = null;
let pollTimer = null;
let timeoutTimer = null;
let countdownTimer = null;

function setState(newState, payload) {
  state = newState;
  // chama showIdle(), showPolling(label), showDone(data), etc.
}
```

**Transições de estado verificadas contra API:**

| Evento | De | Para |
|--------|----|------|
| Submit com input válido | IDLE | SUBMITTING |
| POST /jobs → 202 | SUBMITTING | POLLING |
| POST /jobs → 422 | SUBMITTING | ERROR_VALIDATION |
| POST /jobs → 429 | SUBMITTING | ERROR_RATE_LIMIT |
| GET /jobs → done | POLLING | DONE |
| GET /jobs → failed | POLLING | ERROR_JOB |
| 180s elapsed | POLLING | ERROR_TIMEOUT |
| Clique "Tentar novamente" | ERROR_JOB | SUBMITTING |
| Countdown chega a 0 | ERROR_RATE_LIMIT | SUBMITTING |

### Pattern 3: Polling com Timeout Duplo

```javascript
// Source: 04-UI-SPEC.md — D-01, D-02, D-03
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 180 * 1000; // 180s = 90 ciclos

function startPolling(id) {
  jobId = id;
  pollTimer = setInterval(pollStatus, POLL_INTERVAL_MS);
  timeoutTimer = setTimeout(() => {
    clearInterval(pollTimer);
    setState('ERROR_TIMEOUT');
  }, POLL_TIMEOUT_MS);
}

function stopPolling() {
  clearInterval(pollTimer);
  clearTimeout(timeoutTimer);
  pollTimer = null;
  timeoutTimer = null;
}
```

### Pattern 4: Download WAV sem JS

```html
<!-- Source: api/main.py:263 — FileResponse com Content-Disposition: attachment -->
<!-- href setado por JS quando status === "done": downloadLink.href = '/files/' + jobId -->
<a id="download-link" class="sg-download-btn" download>Baixar WAV</a>
```

```javascript
// JS apenas seta o href — o clique é nativo do browser
document.getElementById('download-link').href = '/files/' + jobId;
```

Não usar `fetch()` para o download — `<a download>` aciona o `Content-Disposition: attachment` que o FastAPI já seta. [VERIFIED: api/main.py — `filename=f"soundgrabber_{job_id[:8]}.wav"`]

### Pattern 5: Fetch com Content-Type obrigatório

```javascript
// Source: VERIFIED — POST sem Content-Type retorna 422 (FastAPI/Pydantic rejeita)
const response = await fetch('/jobs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ youtube_url: url })  // campo: youtube_url, NÃO "url"
});
```

**Atenção:** O `04-UI-SPEC.md` documenta incorretamente o campo como `"url"` na seção "API Consumption Contract". O campo correto é `"youtube_url"`. [VERIFIED: api/main.py:53 — `class JobRequest(BaseModel): youtube_url: str`]

### Anti-Patterns to Avoid

- **Montar `StaticFiles` antes de definir rotas:** `app.mount("/", StaticFiles(..., html=True))` antes das rotas pode shadoweá-las dependendo da versão do Starlette. Sempre definir rotas primeiro, depois montar.
- **Usar `fetch()` para o download WAV:** Carrega o arquivo inteiro em memória no browser. Usar `<a href download>`.
- **`clearInterval` dentro do callback de poll sem guard:** Se `pollTimer` já foi limpo por timeout, um `clearInterval(null)` é seguro no browser, mas o guard `if (pollTimer)` deixa a intenção clara.
- **Não limpar `countdownTimer` ao sair de ERROR_RATE_LIMIT:** Causa decremento fantasma se o usuário resubmete manualmente antes do countdown terminar.
- **Construir o campo JSON como `{ url: "..." }`:** A API rejeita com 422 — o campo é `youtube_url`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Servir arquivos estáticos | Rota `GET /static/{filename}` manual | `StaticFiles` do Starlette | Handle ETag, Last-Modified, Range requests automaticamente |
| Parse de headers de resposta | Regex em `response.headers` | `response.headers.get('retry-after')` | API nativa do Fetch — já disponível |
| Download forçado | `fetch()` + `URL.createObjectURL()` | `<a href download>` | Sem overhead de memória; filename servido pelo server via `Content-Disposition` |
| Timeout de polling | `counter++` dentro do callback | `setTimeout` separado | Mais robusto — não afetado por pausas no tab visibility |

**Key insight:** Vanilla JS + Fetch API + DOM nativo resolvem todos os problemas desta fase sem nenhum polyfill ou helper library. A complexidade está na máquina de estados, não nas APIs usadas.

---

## Common Pitfalls

### Pitfall 1: Campo JSON errado no POST /jobs

**What goes wrong:** JavaScript envia `{ "url": "..." }` em vez de `{ "youtube_url": "..." }`. API retorna 422 para todos os submits.
**Why it happens:** O `04-UI-SPEC.md` (seção "API Consumption Contract") documenta incorretamente o campo como `"url"`. O spec de interação está correto, mas essa seção específica tem erro de copy-paste.
**How to avoid:** Sempre usar `{ youtube_url: url }` no `JSON.stringify`. Verificar contra `api/main.py:53`.
**Warning signs:** Todos os submits retornam 422 com `error_type: "validation_error"` mesmo com URLs válidas do YouTube.

[VERIFIED: api/main.py linha 53 — `youtube_url: str`; teste confirmou POST sem esse campo exato retorna 422]

### Pitfall 2: StaticFiles lança RuntimeError se diretório não existe

**What goes wrong:** `app.mount("/static", StaticFiles(directory="static"))` no startup se `static/` não foi criado ainda.
**Why it happens:** Starlette verifica `os.path.isdir(directory)` no `__init__` por padrão (`check_dir=True`).
**How to avoid:** Criar `static/index.html` e `static/app.js` antes de adicionar o mount ao `main.py`. No plano, criar os arquivos estáticos em Wave 1 e o mount em Wave 2.
**Warning signs:** `RuntimeError: Directory 'static' does not exist` ao iniciar o servidor após editar `main.py`.

[VERIFIED: Starlette 1.0.0 source — `raise RuntimeError(f"Directory '{directory}' does not exist")`]

### Pitfall 3: Content-Type ausente no POST /jobs

**What goes wrong:** `fetch('/jobs', { method: 'POST', body: JSON.stringify({...}) })` sem `Content-Type: application/json` retorna 422.
**Why it happens:** FastAPI/Pydantic precisa do header para fazer o parse do body como JSON.
**How to avoid:** Sempre incluir `headers: { 'Content-Type': 'application/json' }` no fetch POST.
**Warning signs:** 422 com mensagem sobre body malformado mesmo com JSON válido.

[VERIFIED: teste com TestClient — sem Content-Type retorna 422; com application/json retorna 202]

### Pitfall 4: Timers não limpos em transição de estado

**What goes wrong:** `countdownTimer` do rate limit continua decrementando depois de o usuário resubmeter manualmente. `pollTimer` do job anterior continua rodando ao iniciar novo job.
**Why it happens:** JavaScript não tem garbage collection automático de timers — `clearInterval`/`clearTimeout` são obrigatórios.
**How to avoid:** No início de `submitJob()`, sempre limpar todos os timers ativos antes de criar novos.
**Warning signs:** Mensagem de countdown aparece sobreposta em novo job; `pollStatus()` chamado com `jobId` de job anterior.

### Pitfall 5: `fetch()` lançando exceção em erro de rede vs retornando status de erro

**What goes wrong:** Código assume que `response.ok === false` cobre todos os erros. `fetch()` lança `TypeError` para falhas de rede (servidor down, sem internet) — não retorna `Response` com status 5xx.
**Why it happens:** A Fetch API distingue entre erros de protocolo HTTP (retornam Response) e erros de rede (lançam exceção).
**How to avoid:** Envolver `fetch()` em `try/catch`. Tratar `TypeError` separadamente como `ERROR_NETWORK`:

```javascript
// Source: MDN Fetch API specification [ASSUMED]
try {
  const response = await fetch('/jobs', { ... });
  if (!response.ok) { /* handle HTTP errors */ }
} catch (err) {
  // err é TypeError para falhas de rede
  setState('ERROR_JOB', { message: 'Erro de conexão. Verifique sua internet e tente novamente.' });
}
```

### Pitfall 6: `response.headers.get('retry-after')` pode retornar null em alguns proxies

**What goes wrong:** Em same-origin sem proxy, `Retry-After` é sempre exposto. Com nginx ou proxy reverso, o header pode ser filtrado se não configurado explicitamente.
**How to avoid:** Guard `const retryAfter = parseInt(response.headers.get('retry-after') || '60', 10)` — fallback de 60s se header ausente.
**Warning signs:** `parseInt(null, 10)` retorna `NaN`, causando `NaN s` no countdown.

[VERIFIED: `headers_enabled=True` no Limiter injeta Retry-After; comportamento de proxy é [ASSUMED]]

---

## Code Examples

### Fetch POST /jobs com Content-Type correto

```javascript
// Source: VERIFIED contra api/main.py:53 (campo youtube_url) e teste funcional
async function submitJob(url) {
  try {
    const response = await fetch('/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ youtube_url: url })  // CAMPO: youtube_url, não "url"
    });

    if (response.status === 202) {
      const data = await response.json();
      return { ok: true, jobId: data.job_id };
    }

    if (response.status === 422) {
      const data = await response.json();
      return { ok: false, type: 'validation', error: data.error, errorType: data.error_type };
    }

    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('retry-after') || '60', 10);
      return { ok: false, type: 'rate_limit', retryAfter };
    }

    return { ok: false, type: 'unknown', error: 'Erro inesperado.' };
  } catch (err) {
    return { ok: false, type: 'network', error: 'Erro de conexão. Verifique sua internet e tente novamente.' };
  }
}
```

### Polling com timeout duplo

```javascript
// Source: 04-UI-SPEC.md (D-01, D-02, D-03) + VERIFIED contra api/main.py response shapes
async function pollStatus() {
  try {
    const response = await fetch(`/jobs/${jobId}`);
    if (!response.ok) {
      stopPolling();
      setState('ERROR_JOB', { message: 'Erro ao consultar status do job.' });
      return;
    }
    const data = await response.json();
    const { status, stage } = data;

    if (status === 'done') {
      stopPolling();
      setState('DONE', data);
      return;
    }

    if (status === 'failed') {
      stopPolling();
      setState('ERROR_JOB', { message: data.error, errorType: data.error_type });
      return;
    }

    // queued / downloading / converting / analyzing — atualiza label
    setState('POLLING', { label: stageLabel(status, stage) });
  } catch (err) {
    stopPolling();
    setState('ERROR_JOB', { message: 'Erro de conexão. Verifique sua internet e tente novamente.' });
  }
}
```

### Cálculo de tamanho WAV

```javascript
// Source: CONTEXT.md D-08 — fórmula exata
function estimateSizeMB(durationSec) {
  return durationSec * 44100 * 2 * 2 / 1_000_000;
}

function formatSizeMB(mb) {
  if (mb >= 10) return `~${Math.round(mb)} MB`;
  return `~${mb.toFixed(1)} MB`;
}
```

### Labels de estágio

```javascript
// Source: 04-UI-SPEC.md — Copywriting Contract (Progress Stage Labels)
function stageLabel(status, stage) {
  if (status === 'queued') return 'Na fila...';
  if (status === 'downloading') {
    if (stage === 'checking_duration') return 'Verificando duração...';
    if (stage === 'downloading') return 'Baixando áudio...';
    return 'Baixando...';
  }
  if (status === 'converting') return 'Convertendo para WAV...';
  if (status === 'analyzing') return 'Analisando BPM e tonalidade...';
  return 'Processando...';
}
```

### Countdown de rate limit

```javascript
// Source: CONTEXT.md D-05 (specific ideas) + 04-UI-SPEC.md Rate-Limit Countdown Contract
function showErrorRateLimit(retryAfterSec) {
  let remaining = retryAfterSec;
  updateCountdownUI(remaining);

  countdownTimer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(countdownTimer);
      countdownTimer = null;
      setState('IDLE');  // re-habilita submit
    } else {
      updateCountdownUI(remaining);
    }
  }, 1000);
}
```

### Mount StaticFiles em api/main.py

```python
# Source: VERIFIED — teste funcional FastAPI 0.136.1 + Starlette 1.0.0
# Adicionar após todas as rotas existentes em api/main.py

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent.parent / "static"

@app.get("/")
def serve_index():
    """Serve index.html para browsers."""
    return FileResponse(str(STATIC_DIR / "index.html"))

# Mount DEPOIS de todas as rotas da API
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| XHR (XMLHttpRequest) | `fetch()` nativo | ES2015 / Chrome 40 | Fetch é padrão desde 2015; suportado em todos os browsers modernos |
| `hidden` CSS class via JS | `element.hidden` (propriedade IDL) | HTML5 | `element.hidden = true/false` é equivalente a `display:none` sem necessitar de CSS |
| `setInterval` para countdown com data server | Decremento local de `Retry-After` | — | Padrão no projeto (CONTEXT.md specific ideas) — sem roundtrip de clock |

**Deprecated/outdated:**
- XHR: não usar — `fetch()` é suportado universalmente e tem API mais limpa.
- `jQuery.ajax()`: não usar — zero npm no projeto.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `fetch()` em same-origin expõe `Retry-After` header sem configuração adicional de CORS | Pitfall 6 | Countdown não funciona; fallback de 60s mitiga |
| A2 | `element.hidden = true` funciona como `display:none` em todos os browsers-alvo sem CSS | Code Examples | Elementos não ocultam; requer CSS `[hidden] { display: none }` mínimo ou uso de `style.display` |
| A3 | Content-Disposition `attachment` no FileResponse faz o browser baixar o WAV sem abrir preview | Pattern 4 | Browser pode tentar tocar o WAV em vez de baixar (comportamento específico do browser) |

---

## Open Questions

1. **`element.hidden` vs CSS `display:none`**
   - What we know: `element.hidden` seta o atributo HTML `hidden` que equivale a `display:none` via UA stylesheet
   - What's unclear: Alguns browsers muito antigos podem não respeitar o atributo `hidden` sem CSS explícito
   - Recommendation: Dado que Phase 5 vai adicionar CSS de qualquer forma, e o público-alvo usa browsers modernos, `element.hidden` é suficiente para Phase 4. Se houver problemas, usar `element.style.display = 'none'/'block'` é o fallback seguro.

2. **`download_url` da API vs construção local `/files/{jobId}`**
   - What we know: `GET /jobs/{id}` retorna `download_url: "/files/{job_id}"` quando `status === "done"` [VERIFIED: tasks.py:80, main.py:220]
   - What's unclear: CONTEXT.md indica que o planner decide se usa `download_url` ou constrói localmente
   - Recommendation: Usar `data.download_url` da resposta quando disponível; fallback para `/files/${jobId}` se `download_url` for null. Ambos são equivalentes na prática.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI | Servir static files | ✓ | 0.136.1 | — |
| Starlette StaticFiles | Servir app.js | ✓ | 1.0.0 | — |
| pytest + httpx TestClient | Testes de integração frontend | ✓ | 9.0.3 / 0.28.1 | — |
| html.parser (stdlib) | Parse HTML em testes | ✓ | Python 3.12 stdlib | — |
| Redis (local) | API calls nos testes | ✓ | porta 6380 (conftest.py) | — |
| BeautifulSoup | Parse HTML mais ergonômico nos testes | ✗ | — | html.parser stdlib |

**Missing dependencies with no fallback:** Nenhuma.

**Missing dependencies with fallback:**
- BeautifulSoup não disponível — `html.parser` stdlib é suficiente para verificar IDs no HTML gerado.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (existente) |
| Quick run command | `pytest tests/test_frontend.py -x -q` |
| Full suite command | `pytest tests/ -x -q -m "not e2e"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | `GET /` retorna 200 com HTML contendo `#url-input` e `#submit-btn` | unit | `pytest tests/test_frontend.py::test_index_html_served -x` | ❌ Wave 0 |
| CORE-01 | `GET /static/app.js` retorna 200 com Content-Type text/javascript | unit | `pytest tests/test_frontend.py::test_app_js_served -x` | ❌ Wave 0 |
| CORE-01 | HTML contém todos os IDs obrigatórios do UI-SPEC | unit | `pytest tests/test_frontend.py::test_html_ids_present -x` | ❌ Wave 0 |
| UX-01 | `stageLabel('downloading', 'checking_duration')` retorna string correta | unit | `pytest tests/test_frontend.py::test_stage_labels -x` (via Node ou inline string check) | ❌ Wave 0 |
| UX-02 | `estimateSizeMB(300)` = ~31.5 MB (5 min × 10.5 MB/min) | unit | `pytest tests/test_frontend.py::test_wav_size_formula -x` (Python equivalent) | ❌ Wave 0 |
| UX-01 + UX-02 | Fluxo completo: submit → polling → done → result card (smoke) | manual/e2e | Manual browser test — sem playwright instalado | N/A |

**Nota sobre testes JS:** Sem Node test runner no projeto (zero npm). Os comportamentos do JS state machine são verificados indiretamente via:
1. Testes Python que verificam o HTML estrutural (IDs corretos para que o JS funcione)
2. Teste Python que verifica as fórmulas matemáticas (equivalente em Python do `estimateSizeMB`)
3. Smoke test manual no browser para o fluxo completo (UX-01, UX-02)

### Sampling Rate

- **Per task commit:** `pytest tests/test_frontend.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q -m "not e2e"`
- **Phase gate:** Full suite green + manual browser smoke test antes do `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_frontend.py` — cobre CORE-01 (GET /), CORE-01 (app.js), CORE-01 (IDs no HTML), UX-02 (fórmula WAV size)
- [ ] Fixtures: nenhuma nova fixture necessária — `api_client` existente em `conftest.py` serve GET /

*(Não há gaps de framework — pytest + TestClient já operacionais)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Projeto stateless sem auth (CLAUDE.md) |
| V3 Session Management | no | Projeto stateless sem sessão |
| V4 Access Control | no | Sem rotas protegidas |
| V5 Input Validation | yes | Validação real está no backend (Pydantic); frontend apenas exibe erro 422 |
| V6 Cryptography | no | Sem criptografia client-side |

### Known Threat Patterns for Vanilla JS + FastAPI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via `innerHTML` com dados da API | Tampering | Usar `textContent` para inserir dados da API no DOM — nunca `innerHTML` |
| Path traversal via job_id no download link | Tampering | Já mitigado no backend (`JOB_ID_PATTERN` em main.py); frontend usa job_id da API, não da URL |
| Open redirect via `download_url` field | Spoofing | Usar `/files/${jobId}` local ou verificar que `data.download_url` começa com `/files/` antes de setar como `href` |

**XSS via textContent:** Ao popular `#bpm-value`, `#key-value`, `#error-message` etc., usar sempre `element.textContent = valor` — nunca `element.innerHTML = valor`. Dados de BPM, key e mensagens de erro vêm da API e poderiam conter HTML se o servidor fosse comprometido. [VERIFIED: padrão correto para vanilla JS sem framework]

---

## Sources

### Primary (HIGH confidence)

- `api/main.py` (verificado nesta sessão) — contratos exatos das rotas, campo `youtube_url`, FileResponse filename
- `api/tasks.py` (verificado nesta sessão) — campo `download_url` setado na task; shape do resultado done
- `.planning/phases/04-frontend/04-UI-SPEC.md` (aprovado 2026-05-04) — state machine, HTML structure, copywriting
- `.planning/phases/04-frontend/04-CONTEXT.md` — decisões travadas D-01 a D-11
- Starlette 1.0.0 source (`staticfiles.py`) — comportamento de `check_dir`, `html=True`, lookup_path
- Teste funcional (executado nesta sessão) — StaticFiles mount não shadoweia rotas API; Content-Type obrigatório; `GET /` com FileResponse funciona

### Secondary (MEDIUM confidence)

- `requirements.txt` — versões pinadas: fastapi==0.136.1, pytest==9.0.3, httpx>=0.27
- `tests/conftest.py` — padrão existente de TestClient reutilizável em `test_frontend.py`
- `pytest.ini` — marcadores existentes; `test_frontend.py` segue mesmo padrão

### Tertiary (LOW confidence)

- Comportamento do proxy reverso com header `Retry-After` — não verificado nesta sessão (marcado como [ASSUMED])

---

## Project Constraints (from CLAUDE.md)

| Diretiva | Enforcement |
|----------|-------------|
| **Vanilla HTML + CSS + JS — zero frameworks** | Sem React, Vue, jQuery, Tailwind ou qualquer npm no frontend |
| **Sem npm / bundler** | `app.js` é um arquivo JS plain sem `import`/`export` de módulos |
| **WAV apenas** | O download link aponta para `/files/{id}` que serve `audio/wav` |
| **Sem contas de usuário** | Nenhum campo de login, cookie de sessão ou localStorage com dados de usuário |
| **Estética Y2K autêntica** | Phase 4 entrega ZERO CSS intencionalmente — Phase 5 aplica a estética |
| **`<style>` proibido em Phase 4** | D-10: sem `<style>` inline, sem arquivo CSS, sem atributos `style=` |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — todas as dependências verificadas contra requirements.txt e via import test
- Architecture: HIGH — padrão de mount testado funcionalmente com FastAPI 0.136.1
- Pitfalls: HIGH (campo youtube_url, Content-Type, StaticFiles dir check) / MEDIUM (proxy headers)
- JS state machine: HIGH — spec completo e aprovado em 04-UI-SPEC.md; padrões são ES2020 padrão

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (dependências estáveis; FastAPI e Starlette mudam raramente em minor versions)
