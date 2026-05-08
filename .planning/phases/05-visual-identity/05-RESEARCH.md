# Phase 5: Visual Identity — Research

**Pesquisado em:** 2026-05-08
**Domínio:** CSS puro / HTML de época / self-hosting de fontes web
**Confiança geral:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Paleta de cores:**
- Background: `#000000`
- Texto / bordas / botões: `#ff8800`
- Hover: `#ff6600`
- Placeholder: `#804400`
- Erro de borda (via JS): `#ff3300`
- Sem CSS custom properties (`--qualquer-coisa`) em lugar nenhum

**Tipografia:**
- Headers / title / botões: Dela Gothic One (single weight 400)
- Body / labels / valores: Sligoil-Micro
- Ambas self-hosted em `static/fonts/` — sem chamadas a CDN externo
- `font-display: block`; font-smoothing desabilitado globalmente

**Layout:**
- `<table>` para tudo — zero flexbox, zero grid
- 640px centrado via `align="center"` no outer table (atributo HTML, não CSS)
- Sem `box-sizing: border-box`; sem `border-radius`; sem `box-shadow`
- Sem `transition`, `animation`, `transform`

**JS compatibility:**
- 27 IDs DOM obrigatórios devem sobreviver à conversão div→table intactos
- app.js referencia IDs apenas — tipo de elemento é irrelevante

### Claude's Discretion

- `<meta http-equiv="Content-Type">` para compatibilidade com browsers antigos
- Número de níveis de aninhamento de `<table>`
- Ordem dos plans/waves

### Deferred Ideas (OUT OF SCOPE)

- Design responsivo / breakpoints
- Animações ou micro-interações
- Qualquer framework frontend
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VISUAL-01 | Interface segue estética autêntica dos anos 2000 — construída como um site que literalmente saiu naquela época (não releitura moderna) | Layout via `<table>`, hex colors brutas, atributos HTML de época (`align`, `cellpadding`, `cellspacing`, `width`) — ver Padrões de Época |
| VISUAL-02 | Design usa dark mode por padrão com paleta de cores hexadecimais brutas típicas da época | Paleta travada: `#000000` bg / `#ff8800` acento — sem HSL, sem rgba, sem CSS vars |
| VISUAL-03 | Tipografia usa fontes bitmap/pixel sem font-smoothing moderno | Dela Gothic One + Sligoil-Micro ambas SIL OFL, woff2 self-hosted; smoothing desabilitado via `-webkit-font-smoothing: none` |
| VISUAL-04 | HTML/CSS estrutural usa padrões da época (tabelas para layout, bordas sólidas, sem flexbox/grid, sem variáveis CSS, sem animações modernas) | Confirmado em todo o stack de decisões; ver seção Anti-Patterns |
| VISUAL-05 | Fase de UI inclui pesquisa de autenticidade antes de implementar | Este documento é a pesquisa. Critério de autenticidade: desenvolvedor desconhecido deve acreditar razoavelmente que o HTML foi escrito em 2002 |
</phase_requirements>

---

## Summary

Phase 5 é uma fase de CSS + HTML puro: criar `static/style.css`, baixar duas fontes como woff2, e converter o `static/index.html` de div-based layout para table-based layout preservando todos os 27 IDs DOM. O `static/app.js` não é tocado.

O DOM existente (Phase 4) usa divs com classes `sg-*`. A conversão remove as divs de container e as classes `sg-*`, substituindo-as por `<table>`, `<tr>`, `<td>` com os IDs migrados. O JS usa apenas `document.getElementById()` e `classList` no `#url-input` — o tipo de elemento container é completamente irrelevante para o JS.

Uma complicação importante: `app.js` usa `classList.add('sg-url-input--error')` no `#url-input`. Essa classe não é um container div — é aplicada diretamente no `<input>`. O CSS do Phase 5 deve incluir a regra `.sg-url-input--error { border-color: #ff3300 !important; }` para que o estado de erro visual funcione.

**Recomendação primária:** Três plans em sequência — (1) download das fontes, (2) criar style.css completo com @font-face + regras + estados interativos, (3) reescrever index.html com table layout preservando os 27 IDs.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fonte Dela Gothic One | CDN/Static (self-hosted) | — | Arquivo woff2 servido pelo StaticFiles do FastAPI |
| Fonte Sligoil-Micro | CDN/Static (self-hosted) | — | Idem |
| Layout visual | Browser / Client | — | HTML + CSS puro, sem SSR envolvido |
| Estados interativos (hover, focus, error) | Browser / Client | — | CSS puro (`:hover`, `:focus`) + JS inline style para erro de borda |
| ID preservation | Browser / Client | API/Backend (teste) | test_frontend.py verifica IDs via GET / na API |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| HTML 4.01 / table layout | — | Estrutura do documento | Padrão autêntico Y2K; atributos `align`, `cellpadding`, `cellspacing`, `width` eram o mecanismo de layout primário pré-CSS |
| CSS nível 2 (sem CSS3) | — | Estilos | `color`, `font-*`, `border`, `cursor` — propriedades suportadas desde IE5/Netscape 4 |
| woff2 | — | Formato de fonte | Suportado por todos os browsers modernos; melhor compressão que woff; não quebra a autenticidade pois é transparente ao usuário |

### Fontes

| Fonte | Versão | Arquivo woff2 | Licença | Origem |
|-------|--------|---------------|---------|--------|
| Dela Gothic One | v19 (Google Fonts) | `DelaGothicOne-Regular.woff2` | SIL OFL | fonts.gstatic.com |
| Sligoil-Micro | main (2025-06-16) | `Sligoil-Micro.woff2` | SIL OFL | gitlab.com/velvetyne/sligoil |

**Versões verificadas:** [VERIFIED: curl contra fonts.googleapis.com e gitlab.com/velvetyne/sligoil em 2026-05-08]

---

## Download Procedures — Fontes

### Dela Gothic One (Google Fonts)

**Método recomendado:** Download direto do woff2 Latin via curl

```bash
# Passo 1: descobrir URL atual via API do Google Fonts
curl -s "https://fonts.googleapis.com/css2?family=Dela+Gothic+One&display=block" \
  -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  | grep -A5 "/* latin */"

# Saída verificada em 2026-05-08:
# src: url(https://fonts.gstatic.com/s/delagothicone/v19/hESp6XxvMDRA-2eD0lXpDa6QkBA2QkEI.woff2)
# unicode-range: U+0000-00FF, ...

# Passo 2: baixar o arquivo
mkdir -p static/fonts
curl -L "https://fonts.gstatic.com/s/delagothicone/v19/hESp6XxvMDRA-2eD0lXpDa6QkBA2QkEI.woff2" \
  -o static/fonts/DelaGothicOne-Regular.woff2
```

**URL verificada em 2026-05-08:** `https://fonts.gstatic.com/s/delagothicone/v19/hESp6XxvMDRA-2eD0lXpDa6QkBA2QkEI.woff2` — HTTP 200, CORS `access-control-allow-origin: *` [VERIFIED: curl HEAD em 2026-05-08]

**Nota de atualização:** A URL do woff2 inclui versão `v19`. Se o Google Fonts atualizar a fonte, a URL muda. O Passo 1 (fetch do CSS) deve ser executado na hora do plano para obter a URL atual.

### Sligoil-Micro (Velvetyne / GitLab)

**Método recomendado:** Download do zip do repositório e extração do woff2

```bash
# Passo 1: baixar o zip do repositório main
mkdir -p static/fonts
curl -L "https://gitlab.com/velvetyne/sligoil/-/archive/main/sligoil-main.zip" \
  -o /tmp/sligoil-main.zip

# Passo 2: extrair apenas o woff2 da pasta web
unzip -p /tmp/sligoil-main.zip \
  "sligoil-main/fonts/web/Sligoil-Micro.woff2" > static/fonts/Sligoil-Micro.woff2

# Passo 3: verificar
ls -lh static/fonts/Sligoil-Micro.woff2
# Esperado: ~41 KB (41944 bytes verificados no zip de 2025-06-16)
```

**Estrutura verificada no zip** [VERIFIED: curl + unzip em 2026-05-08]:
- `sligoil-main/fonts/web/Sligoil-Micro.woff2` — 41944 bytes
- `sligoil-main/fonts/web/Sligoil-MicroBold.woff2` — 44292 bytes (não necessário)
- `sligoil-main/fonts/otf/Sligoil-Micro.otf` — fallback se necessário

---

## Architecture Patterns

### System Architecture Diagram

```
Requisição do browser
        |
        v
FastAPI StaticFiles (/static)
        |
        +----> static/index.html      (HTML com table layout)
        |             |
        |             +----> static/style.css    (regras CSS + @font-face)
        |             |             |
        |             |             +----> static/fonts/DelaGothicOne-Regular.woff2
        |             |             +----> static/fonts/Sligoil-Micro.woff2
        |             |
        |             +----> static/app.js       (8-state machine — NÃO TOCADO)
        |
        +----> /jobs (API — NÃO TOCADA)
```

### Estrutura de arquivos a criar/modificar

```
static/
├── index.html          (MODIFICAR — div→table, +<link> para style.css)
├── style.css           (CRIAR — stylesheet completo)
├── app.js              (NÃO TOCAR)
└── fonts/              (CRIAR diretório)
    ├── DelaGothicOne-Regular.woff2   (CRIAR via curl)
    └── Sligoil-Micro.woff2           (CRIAR via unzip)
```

### Padrões de Época — HTML 2000-2005

Sites autênticos de 2000-2005 usavam os seguintes padrões estruturais:

**Atributos HTML de layout (não CSS):**
```html
<table width="640" align="center" cellpadding="8" cellspacing="0" border="1" bordercolor="#ff8800">
  <tr>
    <td valign="top" width="50%">...</td>
    <td valign="top" width="50%">...</td>
  </tr>
</table>
```

**Meta charset de época (aceito pelo planner):**
```html
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
```
[ASSUMED] — A especificação HTML 4.01 usava `http-equiv`, não `charset` direto. O `<meta charset="UTF-8">` é HTML5. Para máxima autenticidade, o planner pode trocar ou manter ambos.

**Hierarquia de tabelas completa (per CONTEXT.md §3):**
```html
<table width="640" align="center" cellpadding="0" cellspacing="0">
  <tr>
    <td id="header">
      <!-- título + tagline -->
    </td>
  </tr>
  <tr>
    <td id="form-area">
      <!-- input-group, duration-hint, validation-error -->
    </td>
  </tr>
  <tr>
    <td id="progress-area" hidden>
      <!-- progress-label -->
    </td>
  </tr>
  <tr>
    <td id="result-card" hidden>
      <!-- inner table 2-colunas -->
    </td>
  </tr>
  <tr>
    <td id="error-area" hidden>
      <!-- error-message + retry-btn -->
    </td>
  </tr>
</table>
```

### CSS — @font-face e reset

```css
/* Source: 05-UI-SPEC.md §Typography */
@font-face {
  font-family: 'Dela Gothic One';
  src: url('/static/fonts/DelaGothicOne-Regular.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: block;
}

@font-face {
  font-family: 'Sligoil';
  src: url('/static/fonts/Sligoil-Micro.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: block;
}

body {
  background-color: #000000;
  color: #ff8800;
  font-family: 'Sligoil', 'Courier New', monospace;
  font-size: 13px;
  margin: 0;
  padding: 0;
  -webkit-font-smoothing: none;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeSpeed;
}
```

### CSS — classe de erro que app.js exige

**CRÍTICO:** `app.js` faz `classList.add('sg-url-input--error')` no elemento `#url-input`. Esta classe DEVE estar definida em style.css:

```css
/* Usado pelo app.js — NÃO REMOVER */
.sg-url-input--error {
  border-color: #ff3300 !important;
}
```

Sem essa regra, o estado de erro visual (borda vermelha no input) não funciona. [VERIFIED: grep em static/app.js linhas 172, 184, 236, 282]

### Anti-Patterns a Evitar

- **Flexbox/Grid:** `display: flex` e `display: grid` são propriedades CSS3 (2009+). Proibidos para autenticidade.
- **CSS custom properties:** `--color-primary` etc. são CSS Level 4 (2012+). Proibidos.
- **`border-radius`:** Introduzido no Firefox 2 (2006), popularizado em 2009. Proibido.
- **`box-shadow`:** CSS3, 2009. Proibido.
- **`transition`/`animation`:** CSS3 Transitions (2009). Proibidos.
- **`rem`/`em`/`vh`:** Escala relativa é moderna em prática; usar `px` absoluto.
- **`box-sizing: border-box`:** Popularizado em 2012. Proibido.
- **`rgba()`:** Para placeholder usar `#804400` (hex puro de 50% de #ff8800).
- **CDN calls para fontes:** Nenhuma tag `<link>` para fonts.googleapis.com.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Font download | Script customizado | `curl -L` (ver seção Download Procedures) | Google Fonts e GitLab servem woff2 diretamente; curl com seguimento de redirect é suficiente |
| Cálculo de cor placeholder | Conversor rgba→hex manual | `#804400` hardcoded | 50% de #ff8800 = #804400 já calculado — não recalcular |
| Teste de ID preservation | Parser de HTML customizado | `test_html_required_ids_present` existente em test_frontend.py | Já cobre 16 IDs via FastAPI TestClient |

---

## DOM Analysis — Estado Atual (Phase 4)

### Todos os IDs presentes em static/index.html

| ID | Elemento atual | Elemento alvo | Visibilidade JS |
|----|---------------|----------------|-----------------|
| `app` | `<div>` outer | `<table>` outer container | Não referenciado pelo JS |
| `header` | `<div>` | `<td>` | Não referenciado pelo JS |
| `site-title` | `<div>` | `<div>` dentro de td | Não referenciado pelo JS |
| `site-tagline` | `<div>` | `<div>` dentro de td | Não referenciado pelo JS |
| `form-area` | `<div>` | `<td>` | Não referenciado pelo JS |
| `duration-hint` | `<div>` | `<div>` dentro de td | Não referenciado pelo JS |
| `input-group` | `<div>` | `<div>` dentro de td | Não referenciado pelo JS |
| `url-input` | `<input>` | `<input>` (não muda) | **REFERENCIADO** — `classList`, `disabled`, `value`, `style.borderColor` |
| `submit-btn` | `<button>` | `<button>` (não muda) | **REFERENCIADO** — `disabled`, `textContent`, `hidden`, `addEventListener` |
| `validation-error` | `<div>` | `<div>` dentro de td | **REFERENCIADO** — `hidden`, `textContent` |
| `progress-area` | `<div>` | `<td>` | **REFERENCIADO** — `hidden` |
| `progress-label` | `<div>` | `<div>` dentro de td | **REFERENCIADO** — `textContent` |
| `result-card` | `<div>` | `<table>` inner (2 cols) | **REFERENCIADO** — `hidden` |
| `result-bpm` | `<div>` | `<td>` col-esq | Não referenciado pelo JS |
| `result-key` | `<div>` | `<td>` col-dir | Não referenciado pelo JS |
| `result-size` | `<div>` | `<td colspan="2">` | Não referenciado pelo JS |
| `download-area` | `<div>` | pode ser removido (integrar em result-size) | Não referenciado pelo JS |
| `bpm-value` | `<div>` | `<span>` ou `<div>` | **REFERENCIADO** — `textContent` |
| `bpm-half-value` | `<div>` | `<span>` ou `<div>` | **REFERENCIADO** — `textContent` |
| `bpm-double-value` | `<div>` | `<span>` ou `<div>` | **REFERENCIADO** — `textContent` |
| `key-value` | `<div>` | `<span>` ou `<div>` | **REFERENCIADO** — `textContent` |
| `camelot-value` | `<div>` | `<span>` ou `<div>` | **REFERENCIADO** — `textContent` |
| `size-value` | `<div>` | `<span>` ou `<div>` | **REFERENCIADO** — `textContent` |
| `download-link` | `<a>` | `<a>` (não muda) | **REFERENCIADO** — `href`, `addEventListener` (indireto via `$('download-link')`) |
| `error-area` | `<div>` | `<td>` | **REFERENCIADO** — `hidden` |
| `error-message` | `<div>` | `<div>` dentro de td | **REFERENCIADO** — `textContent` |
| `retry-btn` | `<button>` | `<button>` (não muda) | **REFERENCIADO** — `hidden`, `addEventListener` |

**Contagem confirmada:** 27 IDs listados no CONTEXT.md §8 — todos presentes no index.html atual [VERIFIED: leitura direta de static/index.html]

**IDs do JS (16 referenciados diretamente):** `url-input`, `submit-btn`, `validation-error`, `result-card`, `progress-area`, `progress-label`, `error-area`, `error-message`, `retry-btn`, `size-value`, `bpm-value`, `bpm-half-value`, `bpm-double-value`, `key-value`, `camelot-value`, `download-link` [VERIFIED: grep em static/app.js]

**Classe JS:** `sg-url-input--error` — aplicada via `classList` no `#url-input`. Deve ter regra CSS em style.css.

---

## Common Pitfalls

### Pitfall 1: Quebrar o estado de erro do input

**O que dá errado:** Converter o HTML e esquecer de definir a classe `.sg-url-input--error` em style.css. O JS fará `classList.add('sg-url-input--error')` sem erro, mas a borda vermelha não aparecerá.

**Por que acontece:** A classe não existia em style.css na Phase 4 (não havia stylesheet). A conversão para table não cria o CSS automaticamente.

**Como evitar:** style.css DEVE conter `.sg-url-input--error { border-color: #ff3300 !important; }`.

**Sinais de alerta:** Teste de validação passa mas borda não muda de cor visualmente.

### Pitfall 2: Adicionar `<link>` para style.css mas não criar o arquivo

**O que dá errado:** index.html referencia `/static/style.css` mas o arquivo não existe. O browser silencia o erro 404 de CSS e a página fica sem estilo.

**Por que acontece:** Ordem errada de plans — HTML modificado antes do arquivo CSS criado.

**Como evitar:** Plan de criação do CSS deve preceder o plan de modificação do HTML. Ou fazer tudo no mesmo plan na ordem correta.

### Pitfall 3: Usar `display: none` em vez de atributo `hidden`

**O que dá errado:** O CSS adiciona `[hidden] { display: none; }` ou similar e isso sobrescreve o atributo `hidden` que o app.js usa para mostrar/esconder seções.

**Por que acontece:** O atributo HTML `hidden` foi introduzido no HTML5 e tem valor semântico de `display: none` nos browsers modernos. O JS usa `.hidden = true/false` diretamente. Se o CSS definir `.sg-progress-area { display: block; }` sem respeitar o atributo, a visibilidade quebra.

**Como evitar:** Não definir `display` explícito em elementos que são controlados via `hidden` pelo JS. Deixar o atributo `hidden` do browser cuidar da visibilidade.

### Pitfall 4: Perder `download-area` ID na conversão

**O que dá errado:** O div `#download-area` (container do `<a id="download-link">`) não é referenciado pelo JS, então parece seguro remover. Mas o CONTEXT.md lista 27 IDs obrigatórios — `download-area` é um deles. Os testes de Phase 5 precisarão verificar todos os 27.

**Por que acontece:** A lista de 27 IDs no CONTEXT.md §8 inclui `download-area` e `result-size` como IDs separados. Na conversão para table, `result-size` e `download-area` podem ser colapsados num único `<td colspan="2">` mas ambos os IDs devem permanecer acessíveis.

**Como evitar:** Manter `id="download-area"` no `<td colspan="2">` e `id="result-size"` num elemento filho (ou vice-versa). Um `<td>` pode ter vários filhos com IDs distintos.

### Pitfall 5: Fonte woff2 com caminho errado

**O que dá errado:** `@font-face` usa `url('../fonts/...')` relativo ao CSS, mas o FastAPI serve tudo de `/static/` com o CSS em `/static/style.css`. O caminho relativo funciona no filesystem mas não via HTTP se o CSS for servido de um path diferente.

**Por que acontece:** Confusão entre path relativo ao arquivo CSS (funciona em desenvolvimento com open-file) e path relativo à URL de serviço.

**Como evitar:** Usar path absoluto `/static/fonts/DelaGothicOne-Regular.woff2` no `@font-face`, ou path relativo correto `fonts/DelaGothicOne-Regular.woff2` (sem `../`) que é relativo ao diretório de onde o CSS é servido.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (raiz do projeto) |
| Comando rápido | `.venv/bin/pytest tests/test_frontend.py -v` |
| Suíte completa | `.venv/bin/pytest tests/ -v --tb=short` |

**Estado atual:** 26 testes passando (4 em test_frontend.py, 22 em test_api.py). Todos verdes antes do Phase 5. [VERIFIED: .venv/bin/pytest em 2026-05-08]

### Existência de testes de frontend

`tests/test_frontend.py` já contém:
- `test_index_html_served` — GET / retorna 200 com HTML
- `test_app_js_served` — /static/app.js retorna 200
- `test_html_required_ids_present` — verifica 16 IDs via FastAPI TestClient
- `test_wav_size_formula` — fórmula de estimativa de tamanho WAV (pure Python)

**Gap identificado:** `test_html_required_ids_present` verifica 16 IDs (os mais usados pelo JS), mas o CONTEXT.md especifica 27 IDs obrigatórios. Os 11 IDs adicionais (`app`, `header`, `site-title`, `site-tagline`, `form-area`, `duration-hint`, `input-group`, `result-bpm`, `result-key`, `download-area`, `result-size`) não são verificados pelos testes existentes.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Comando Automatizado | Arquivo Existe? |
|--------|----------|-----------|---------------------|-----------------|
| VISUAL-01 | HTML source usa table layout, sem divs de container, atributos HTML de época | unit (HTTP) | `.venv/bin/pytest tests/test_frontend.py::test_html_table_layout -x` | ❌ Wave 0 |
| VISUAL-02 | style.css servido com 200; contém `#000000` e `#ff8800`; sem `var(--` | unit (HTTP) | `.venv/bin/pytest tests/test_frontend.py::test_style_css_served -x` | ❌ Wave 0 |
| VISUAL-03 | style.css contém `@font-face` para Dela Gothic One e Sligoil; fontes woff2 existem em disco | unit (filesystem + HTTP) | `.venv/bin/pytest tests/test_frontend.py::test_fonts_selfhosted -x` | ❌ Wave 0 |
| VISUAL-04 | style.css não contém `flex`, `grid`, `var(--`, `border-radius`, `box-shadow`, `transition`, `animation` | unit (conteúdo de arquivo) | `.venv/bin/pytest tests/test_frontend.py::test_css_no_modern_properties -x` | ❌ Wave 0 |
| VISUAL-05 | Pesquisa de autenticidade documentada antes da implementação | manual | N/A — este documento é a evidência | ✅ (este arquivo) |

**Testes existentes que continuam válidos:**
- `test_html_required_ids_present` — deve continuar passando após a conversão div→table (verifica 16 IDs)
- Todos os 22 testes de API — não são tocados pelo Phase 5

### Wave 0 Gaps (testes a criar antes da implementação)

- [ ] `tests/test_frontend.py::test_style_css_served` — GET /static/style.css retorna 200 com Content-Type text/css; body contém `#000000` e `#ff8800`; não contém `var(`
- [ ] `tests/test_frontend.py::test_css_no_modern_properties` — lê arquivo static/style.css diretamente e verifica ausência de `flex`, `grid`, `var(--`, `border-radius`, `box-shadow`, `transition`, `animation`, `transform`
- [ ] `tests/test_frontend.py::test_fonts_selfhosted` — GET /static/fonts/DelaGothicOne-Regular.woff2 e /static/fonts/Sligoil-Micro.woff2 retornam 200
- [ ] `tests/test_frontend.py::test_html_table_layout` — HTML de GET / contém `<table` e não contém `display: flex` nem `display: grid`
- [ ] Expandir `test_html_required_ids_present` para verificar todos os 27 IDs (atualmente verifica apenas 16)

### Sampling Rate

- **Por commit de task:** `.venv/bin/pytest tests/test_frontend.py -v`
- **Por merge de wave:** `.venv/bin/pytest tests/ -v --tb=short`
- **Phase gate:** Suíte completa verde antes de `/gsd-verify-work`

---

## State of the Art

| Abordagem antiga | Abordagem atual do projeto | Observação |
|------------------|---------------------------|------------|
| Table layout (2000-2005) | Table layout (intencional) | Regressão proposital para autenticidade Y2K |
| CSS CDN call | woff2 self-hosted | Razões de performance e independência de CDN |
| FOUT (Flash of Unstyled Text) | `font-display: block` | Texto invisível até fonte carregar — sem flash |

---

## Assumptions Log

| # | Claim | Section | Risk se Errado |
|---|-------|---------|----------------|
| A1 | `<meta http-equiv="Content-Type">` é mais autêntico que `<meta charset="UTF-8">` para aparência Y2K | Architecture Patterns | Impacto cosmético apenas — ambos funcionam |
| A2 | `download-area` pode compartilhar `<td colspan="2">` com `result-size` usando IDs em elementos distintos (pai e filho) | DOM Analysis | Nenhum — o JS não referencia `download-area` diretamente; apenas IDs são necessários |

**Todos os outros claims foram verificados via ferramentas nesta sessão.**

---

## Open Questions

1. **Deve `<meta charset>` ser trocado para `http-equiv`?**
   - O que sabemos: `<meta charset="UTF-8">` é HTML5; `<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">` é HTML 4.01
   - O que está indefinido: impacto real na autenticidade (navegadores modernos suportam ambos)
   - Recomendação: trocar para `http-equiv` — custo zero, autenticidade máxima. CONTEXT.md §7 diz "planner decide".

2. **Fontes woff2 devem incluir subsets japoneses da Dela Gothic One?**
   - O que sabemos: o CSS do Google Fonts inclui ~70 unicode ranges para kanji. O Latin subset é suficiente para o conteúdo da UI.
   - O que está indefinido: se o nome da fonte em Dela Gothic (japonesa por design) deve ser renderizado em kanji alguma vez
   - Recomendação: baixar apenas o subset Latin (`U+0000-00FF`...); ~20KB vs ~150KB+ para todos os ranges.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| curl | Download de fontes | ✓ | sistema | wget como alternativa |
| unzip | Extração do Sligoil zip | ✓ | sistema | python3 -c "import zipfile..." |
| Python 3.12 + pytest 9.0.3 | Testes | ✓ | 3.12.3 / 9.0.3 | — |
| FastAPI TestClient | Testes HTTP | ✓ | já instalado no .venv | — |
| fonts.gstatic.com | Dela Gothic One woff2 | ✓ | HTTP 200 verificado | Mirror interno (improvável ser necessário) |
| gitlab.com/velvetyne/sligoil | Sligoil zip | ✓ | HTTP 200 verificado | Velvetyne.fr download page |

**Dependências faltando sem fallback:** Nenhuma.

---

## Security Domain

Esta fase é CSS + HTML estático puro. Nenhuma nova superfície de ataque é introduída.

| ASVS Category | Aplica | Controle |
|---------------|--------|---------|
| V5 Input Validation | não (nenhum novo input) | — |
| V6 Cryptography | não | — |
| Open Redirect (T-04-05) | não — download_link validado em app.js Phase 4 | já implementado |

**Fontes:** SIL OFL — licença permissiva, sem restrições de uso em produção. [CITED: sil.org/open-font-license]

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: curl contra fonts.googleapis.com + fonts.gstatic.com, 2026-05-08] — URL woff2 Latin da Dela Gothic One v19
- [VERIFIED: curl + unzip contra gitlab.com/velvetyne/sligoil, 2026-05-08] — estrutura de arquivos do zip, caminho `fonts/web/Sligoil-Micro.woff2`, tamanho 41944 bytes
- [VERIFIED: leitura direta de static/index.html, 2026-05-08] — estrutura DOM atual, todos os 27 IDs, classes sg-*
- [VERIFIED: grep em static/app.js, 2026-05-08] — 16 IDs referenciados, classe `sg-url-input--error`, operações JS por ID
- [VERIFIED: .venv/bin/pytest, 2026-05-08] — 26 testes passando, framework pytest 9.0.3, conftest com api_client

### Secondary (MEDIUM confidence)
- [CITED: 05-CONTEXT.md, 2026-05-08] — todas as decisões de design (paleta, tipografia, layout)
- [CITED: 05-UI-SPEC.md, 2026-05-08] — contrato visual aprovado incluindo copywriting e estados interativos

### Tertiary (LOW confidence)
- Nenhuma.

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — fontes verificadas via download real, estrutura do zip inspecionada
- Architecture: HIGH — DOM existente lido diretamente, JS inspecionado linha a linha
- Pitfalls: HIGH — derivados de análise direta do código (grep confirmou sg-url-input--error)
- Validation Architecture: HIGH — pytest executado localmente, testes existentes verificados

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (fontes SIL OFL estáveis; URLs do Google Fonts mudam a cada versão de fonte, verificar antes de executar)

---

## RESEARCH COMPLETE
