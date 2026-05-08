---
phase: 04-frontend
reviewed: 2026-05-08T16:08:32Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tests/test_frontend.py
  - static/index.html
  - static/app.js
  - api/main.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-08T16:08:32Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Revisao do frontend Phase 4: `static/index.html`, `static/app.js`, `api/main.py` e `tests/test_frontend.py`.

O HTML e o fluxo de estado JS estao corretos nas linhas gerais — XSS mitigation via `textContent`, open redirect defense no `download-link`, timer management com `clearAllTimers()` e guard de path traversal no backend estao todos implementados conforme o design. A logica de polling e as transicoes de estado sao coerentes.

Foram encontrados um bug critico (crash em producao no rate limiter quando `request.client` e `None`) e quatro warnings de qualidade/corretude que afetam a consistencia visual da UI e a seguranca do fluxo de polling. Dois itens info complementam.

---

## Critical Issues

### CR-01: `request.client` pode ser `None` — crash em producao no rate limiter

**File:** `api/main.py:44`

**Issue:** `_real_ip()` acessa `request.client.host` diretamente. Em FastAPI/Starlette, `request.client` e `None` quando a conexao nao tem peer address — isso acontece com alguns proxies reversos mal configurados, com certos setups ASGI e, conforme verificado, tambem pode ocorrer na suite de testes com `TestClient`. Quando `client` e `None`, a linha levanta `AttributeError: 'NoneType' object has no attribute 'host'`, derrubando a requisicao com 500 em vez de aplicar o rate limit ou retornar 429.

**Impacto:** Qualquer requisicao `POST /jobs` com `request.client == None` resulta em 500. Em producao com Nginx/Caddy sem `proxy_set_header` correto, isso pode afetar todos os usuarios.

**Fix:**
```python
def _real_ip(request: Request) -> str:
    """Retorna o IP real do cliente via conexao TCP — nao spoofavel."""
    if request.client is None:
        # Fallback seguro: retorna string fixa para nao quebrar o rate limiter.
        # Isso e raro (proxy mal configurado) mas nao deve causar 500.
        return "unknown"
    return request.client.host
```

---

## Warnings

### WR-01: `showSubmitting()` nao oculta painel de resultado, erro e progresso anteriores

**File:** `static/app.js:172-178`

**Issue:** `showSubmitting()` apenas desabilita o input e muda o texto do botao. Nao chama `.hidden = true` em `result-card`, `error-area`, `progress-area` e `validation-error`. Se o usuario clicar novamente em "Baixar Beat" enquanto um resultado ou erro esta visivel (estados `DONE`, `ERROR_JOB`, `ERROR_TIMEOUT`), esses paineis permanecem na tela durante o envio, criando uma UI inconsistente onde o botao diz "Enviando..." mas o resultado anterior ainda aparece.

**Fix:**
```javascript
function showSubmitting() {
  $('url-input').classList.remove('sg-url-input--error');
  $('url-input').disabled = true;
  $('submit-btn').disabled = true;
  $('submit-btn').textContent = 'Enviando...';
  $('submit-btn').hidden = false;
  // Ocultar todas as areas de conteudo durante o envio
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('error-area').hidden = true;
  $('validation-error').hidden = true;
}
```

### WR-02: `showErrorJob()` nao remove a classe de erro do input — borda vermelha persiste

**File:** `static/app.js:265-274`

**Issue:** `showErrorJob()` nao chama `$('url-input').classList.remove('sg-url-input--error')`. Se o fluxo transitar de `ERROR_VALIDATION` (que adiciona a classe `sg-url-input--error` na linha 220) para `ERROR_JOB` (por exemplo, o usuario tenta de novo e o job falha), a borda vermelha do input permanece ativa mesmo que o erro nao seja mais de validacao de URL.

**Fix:**
```javascript
function showErrorJob(msg) {
  $('url-input').classList.remove('sg-url-input--error');  // remover highlight de validacao
  $('url-input').disabled = false;
  $('submit-btn').hidden = true;
  $('retry-btn').hidden = false;
  $('error-area').hidden = false;
  $('error-message').textContent = msg;
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('validation-error').hidden = true;
}
```

### WR-03: `pollStatus()` pode executar concorrentemente — race condition de estado

**File:** `static/app.js:100-154`

**Issue:** `startPolling()` usa `setInterval(pollStatus, 2000)`. Se uma chamada a `pollStatus()` demorar mais de 2 segundos (timeout de rede lento, servidor lento), o intervalo dispara novamente antes da primeira `fetch` concluir. Duas chamadas simultaneas podem chamar `stopPolling()` + `setState()` em ordens diferentes, resultando em transicao de estado inconsistente. O estado `DONE` ou `ERROR_JOB` pode ser sobrescrito por uma resposta atrasada de uma chamada anterior.

**Fix:**
```javascript
let isPolling = false;  // flag de guarda — adicionar junto as outras variaveis de estado (linha 7)

async function pollStatus() {
  if (isPolling) return;  // prevenir chamada concorrente
  isPolling = true;
  try {
    const response = await fetch(`/jobs/${jobId}`);
    // ... resto do codigo sem alteracao
  } catch (err) {
    stopPolling();
    setState('ERROR_JOB', { message: 'Erro de conexao. Verifique sua internet e tente novamente.' });
  } finally {
    isPolling = false;
  }
}

// Resetar flag no stopPolling() tambem:
function stopPolling() {
  clearInterval(pollTimer);
  clearTimeout(timeoutTimer);
  pollTimer = null;
  timeoutTimer = null;
  isPolling = false;
}
```

### WR-04: `data.job_id` nao e validado antes de ser passado a `startPolling()`

**File:** `static/app.js:62`

**Issue:** Se `POST /jobs` retornar 202 mas o JSON nao contiver `job_id` (resposta malformada, middleware interceptando, etc.), `startPolling(undefined)` e chamado. `jobId` fica `undefined` e a URL de polling vira `/jobs/undefined`, retornando 404. O usuario nao ve mensagem de erro — fica preso no estado `POLLING` ate o timeout de 3 minutos.

**Fix:**
```javascript
if (response.status === 202) {
  const data = await response.json();
  if (!data.job_id) {
    setState('ERROR_JOB', { message: 'Algo deu errado. Tente novamente.' });
    return;
  }
  setState('POLLING', { label: 'Processando...' });
  startPolling(data.job_id);
  return;
}
```

---

## Info

### IN-01: `test_wav_size_formula` nao testa o codigo JS — testa uma reimplementacao Python

**File:** `tests/test_frontend.py:75-103`

**Issue:** O teste reimplementa a formula `duration_sec * 44100 * 2 * 2 / 1_000_000` em Python e a testa de forma isolada. Isso valida matematica pura, mas nao detecta se a funcao `estimateSizeMB()` em `app.js` foi alterada para uma formula diferente. A derivacao entre JS e Python passaria despercebida. O comentario "Equivalente Python da formula JS" documenta a intencao, mas a validacao e indireta.

**Sugestao:** Considerar um teste de integracao E2E (Playwright/Selenium) que renderize o HTML real e verifique o valor exibido em `#size-value` para uma duracao conhecida, ou ao menos adicionar um comentario explicando que mudancas em `estimateSizeMB()` requerem atualizacao manual deste teste.

### IN-02: `index.html` usa `<div>` para layout em vez de `<table>` — viola restricao do projeto

**File:** `static/index.html:10-104`

**Issue:** A restricao critica do projeto (CLAUDE.md) especifica "Tabelas para layout, sem flexbox/grid". O HTML atual usa exclusivamente `<div>` para toda a estrutura de layout (`sg-app`, `sg-header`, `sg-form-area`, `sg-result-card`, etc.). Nenhum `<table>`, `<tr>` ou `<td>` e usado. Isso nao e um bug funcional, mas e uma violacao direta da estetica Y2K autenticidade mandatoria do projeto, que sera perceptivel na fase de identidade visual (Phase 5).

**Sugestao:** Converter o layout principal para `<table>`-based conforme a restricao. O `<div>` pode ser mantido para elementos atomicos (botoes, labels), mas a estrutura de grade deve usar tabelas.

---

_Reviewed: 2026-05-08T16:08:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
