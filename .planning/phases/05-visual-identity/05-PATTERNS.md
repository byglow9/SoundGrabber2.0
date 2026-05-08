# Phase 5: Visual Identity — Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 5 (2 create, 2 modify, 1 asset-create via shell)
**Analogs found:** 4 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `static/style.css` | config (stylesheet) | — | none in codebase | no-analog |
| `static/index.html` | component (markup) | request-response | `static/index.html` itself (current div structure) | exact (self) |
| `static/fonts/DelaGothicOne-Regular.woff2` | asset (binary) | file-I/O | none | no-analog |
| `static/fonts/Sligoil-Micro.woff2` | asset (binary) | file-I/O | none | no-analog |
| `tests/test_frontend.py` | test | request-response | `tests/test_frontend.py` itself (existing 4 tests) | exact (self) |

---

## Pattern Assignments

### `static/index.html` (component, request-response)

**Analog:** `static/index.html` — current file being converted (lines 1–108)

**Current `<head>` block** (lines 1–7):
```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SoundGrabber</title>
</head>
```

The planner must replace `<meta charset="UTF-8">` with `<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">` for Y2K authenticity, drop the viewport meta (mobile-first is post-2005), and add `<link rel="stylesheet" href="/static/style.css">` before `</head>`.

**Current outer container** (line 10):
```html
<div id="app" class="sg-app">
```
Convert to:
```html
<table id="app" width="640" align="center" cellpadding="0" cellspacing="0" border="1" bordercolor="#ff8800">
```

**Current header row** (lines 12–18):
```html
<div id="header" class="sg-header">
  <div id="site-title" class="sg-title">SoundGrabber</div>
  <div id="site-tagline" class="sg-tagline">
    Cole um link do YouTube. Baixe o beat em WAV.
  </div>
</div>
```
Convert to a `<tr><td id="header">` row. `site-title` and `site-tagline` stay as `<div>` or `<span>` inside the `<td>` — their IDs must survive.

**Current form area** (lines 21–48):
```html
<div id="form-area" class="sg-form-area">
  <div id="duration-hint" class="sg-hint">...</div>
  <div id="input-group" class="sg-input-group">
    <input type="text" id="url-input" class="sg-url-input" ... />
    <button type="button" id="submit-btn" class="sg-submit-btn">Baixar Beat</button>
  </div>
  <div id="validation-error" class="sg-error sg-error--inline" hidden>...</div>
</div>
```
`form-area` becomes `<td id="form-area">`. The `<input id="url-input">` and `<button id="submit-btn">` MUST NOT change element type — JS uses `.classList`, `.disabled`, `.value`, `.textContent`, `.hidden`, and `addEventListener` directly on these elements.

**Current progress row** (lines 51–55):
```html
<div id="progress-area" class="sg-progress-area" hidden>
  <div id="progress-label" class="sg-progress-label"></div>
</div>
```
`progress-area` becomes `<td id="progress-area" hidden>`. JS sets `$('progress-area').hidden` — the `hidden` attribute must remain functional (do not override with CSS `display` property).

**Current result card** (lines 58–91):
```html
<div id="result-card" class="sg-result-card" hidden>
  <div id="result-bpm" ...>
    <div class="sg-result-label">BPM</div>
    <div id="bpm-value" ...></div>
    <div class="sg-result-label">Metade (÷2)</div>
    <div id="bpm-half-value" ...></div>
    <div class="sg-result-label">Dobro (×2)</div>
    <div id="bpm-double-value" ...></div>
  </div>
  <div id="result-key" ...>
    <div class="sg-result-label">Tonalidade</div>
    <div id="key-value" ...></div>
    <div class="sg-result-label">Camelot</div>
    <div id="camelot-value" ...></div>
  </div>
  <div id="result-size" ...>
    <div class="sg-result-label">Tamanho estimado</div>
    <div id="size-value" ...></div>
  </div>
  <div id="download-area" class="sg-download-area">
    <a id="download-link" class="sg-download-btn" download>Baixar WAV</a>
  </div>
</div>
```

The result card becomes a 2-column inner `<table id="result-card" hidden width="100%">`. The inner table structure per CONTEXT.md §3:
- Row 1, `<td id="result-bpm" width="50%">` — BPM column with `bpm-value`, `bpm-half-value`, `bpm-double-value`
- Row 1, `<td id="result-key" width="50%">` — Key column with `key-value`, `camelot-value`
- Row 2, `<td id="result-size" colspan="2">` — size + download; `download-area` ID must also survive, placed on a child element inside this `<td>`

**Current error row** (lines 93–103):
```html
<div id="error-area" class="sg-error-area" hidden>
  <div id="error-message" class="sg-error-message"></div>
  <button type="button" id="retry-btn" class="sg-retry-btn" hidden>Tentar novamente</button>
</div>
```
`error-area` becomes `<td id="error-area" hidden>`. `retry-btn` MUST stay a `<button>` — JS uses `.hidden` and `addEventListener` on it.

**Complete ID checklist (27 IDs, all must survive conversion):**
`app`, `header`, `site-title`, `site-tagline`, `form-area`, `duration-hint`, `input-group`, `url-input`, `submit-btn`, `validation-error`, `progress-area`, `progress-label`, `result-card`, `result-bpm`, `result-key`, `result-size`, `download-area`, `bpm-value`, `bpm-half-value`, `bpm-double-value`, `key-value`, `camelot-value`, `size-value`, `download-link`, `error-area`, `error-message`, `retry-btn`

**JS-critical element types that must NOT change:**
- `#url-input` — must remain `<input>` (JS: `.classList`, `.disabled`, `.value`, `.style.borderColor`)
- `#submit-btn` — must remain `<button>` (JS: `.disabled`, `.textContent`, `.hidden`, `addEventListener`)
- `#retry-btn` — must remain `<button>` (JS: `.hidden`, `addEventListener`)
- `#download-link` — must remain `<a>` (JS: `.href`, implicit via `$('download-link')`)

---

### `static/style.css` (config/stylesheet)

**Analog:** No existing stylesheet in the codebase. Patterns come from CONTEXT.md and RESEARCH.md.

**@font-face block** (from RESEARCH.md §CSS):
```css
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
```

**Body reset** (from CONTEXT.md §2 and §6):
```css
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

**Typography scale** (from CONTEXT.md §2):
```css
#site-title      { font-family: 'Dela Gothic One', sans-serif; font-size: 48px; color: #ff8800; }
#site-tagline    { font-family: 'Sligoil', monospace; font-size: 14px; color: #ff8800; }
#submit-btn      { font-family: 'Dela Gothic One', sans-serif; font-size: 16px; }
#download-link   { font-family: 'Dela Gothic One', sans-serif; font-size: 16px; }
/* BPM/Key primary values */
#bpm-value, #key-value { font-size: 32px; }
/* Labels (BPM, Tonalidade, etc.) */
.sg-result-label { font-size: 11px; text-transform: uppercase; }
```

**Button pattern** (from CONTEXT.md §1 and §5):
```css
#submit-btn {
  background-color: #ff8800;
  color: #000000;
  border: 1px solid #ff8800;
  cursor: pointer;
}
#submit-btn:hover {
  background-color: #ff6600;
  border-color: #ff6600;
  color: #000000;
}
```

**Input pattern** (from CONTEXT.md §1 and §5):
```css
#url-input {
  background-color: #000000;
  color: #ff8800;
  border: 1px solid #ff8800;
}
#url-input:focus {
  border-color: #ff6600;
}
::-webkit-input-placeholder { color: #804400; }
::placeholder               { color: #804400; }
```

**Error class required by app.js** (from RESEARCH.md §CSS — CRITICAL):
```css
/* Usado pelo app.js via classList.add('sg-url-input--error') — NÃO REMOVER */
.sg-url-input--error {
  border-color: #ff3300 !important;
}
```

**Retry button pattern** (from CONTEXT.md §5):
```css
#retry-btn {
  background-color: #000000;
  color: #ff8800;
  border: 1px solid #ff8800;
  cursor: pointer;
}
#retry-btn:hover {
  background-color: #ff8800;
  color: #000000;
}
```

**Download link pattern** (from CONTEXT.md §5):
```css
#download-link {
  background-color: #ff8800;
  color: #000000;
  border: 1px solid #ff8800;
  cursor: pointer;
  text-decoration: none;
}
#download-link:hover {
  background-color: #ff6600;
  border-color: #ff6600;
}
```

**Prohibited properties** — must not appear anywhere in style.css:
- `display: flex` / `display: grid`
- `var(--` (CSS custom properties)
- `border-radius`
- `box-shadow`
- `transition`
- `animation`
- `transform`
- `box-sizing`
- `rgba(`
- `hsl(`

---

### `tests/test_frontend.py` (test, request-response)

**Analog:** `tests/test_frontend.py` itself — existing 4 tests (lines 1–104)

**Fixture pattern** (lines 7–18) — all new tests reuse `api_client` the same way:
```python
def test_index_html_served(api_client):
    response = api_client.get("/")
    assert response.status_code == 200, (
        f"GET / esperava 200, recebeu {response.status_code}. "
        "Certifique-se de que GET / está montado em api/main.py (Plan 04)."
    )
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/html"), (...)
    html_text = response.text
```

**HTTP GET pattern for static files** (lines 23–33) — pattern for `test_style_css_served` and `test_fonts_selfhosted`:
```python
def test_app_js_served(api_client):
    response = api_client.get("/static/app.js")
    assert response.status_code == 200, (
        f"GET /static/app.js esperava 200, recebeu {response.status_code}. "
        "Certifique-se de que StaticFiles está montado e static/app.js existe (Plans 02 e 04)."
    )
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("application/javascript") or content_type.startswith("text/javascript"), (...)
```

**ID list iteration pattern** (lines 36–72) — pattern for expanded `test_html_required_ids_present` (16→27 IDs):
```python
def test_html_required_ids_present(api_client):
    response = api_client.get("/")
    assert response.status_code == 200, (...)
    html_text = response.text

    required_ids = [
        "url-input", "submit-btn", "progress-area", "progress-label",
        "result-card", "bpm-value", "bpm-half-value", "bpm-double-value",
        "key-value", "camelot-value", "size-value", "download-link",
        "error-area", "error-message", "retry-btn", "validation-error",
        # Phase 5 additions — 11 new IDs:
        "app", "header", "site-title", "site-tagline", "form-area",
        "duration-hint", "input-group", "result-bpm", "result-key",
        "download-area", "result-size",
    ]

    missing = []
    for element_id in required_ids:
        if f'id="{element_id}"' not in html_text:
            missing.append(element_id)

    assert not missing, (
        f"IDs ausentes no HTML: {missing}. "
        "Certifique-se de que static/index.html contém todos os IDs do UI-SPEC."
    )
```

**Pure-Python / filesystem test pattern** (lines 75–103) — pattern for `test_css_no_modern_properties` (reads file directly, no HTTP):
```python
def test_wav_size_formula():
    """UX-02: Fórmula de estimativa de tamanho WAV — pure Python, sem HTTP."""
    def estimate_size_mb(duration_sec: float) -> float:
        return duration_sec * 44100 * 2 * 2 / 1_000_000
    assert abs(estimate_size_mb(300) - 52.92) < 0.01, (...)
```

**5 new test stubs to add** (from RESEARCH.md §Wave 0 Gaps):

1. `test_style_css_served(api_client)` — GET /static/style.css → 200, Content-Type text/css, body contains `#000000` and `#ff8800`, does NOT contain `var(`
2. `test_css_no_modern_properties()` — pure Python, reads `static/style.css` directly via `Path`, asserts absence of `flex`, `grid`, `var(--`, `border-radius`, `box-shadow`, `transition`, `animation`, `transform`
3. `test_fonts_selfhosted(api_client)` — GET /static/fonts/DelaGothicOne-Regular.woff2 → 200; GET /static/fonts/Sligoil-Micro.woff2 → 200
4. `test_html_table_layout(api_client)` — GET / HTML contains `<table` and does NOT contain `display: flex` or `display: grid`
5. Expand `test_html_required_ids_present` from 16 to 27 IDs (add the 11 IDs listed above)

Path resolution for filesystem test:
```python
from pathlib import Path
CSS_PATH = Path(__file__).parent.parent / "static" / "style.css"
```

---

## Shared Patterns

### `hidden` attribute — do not override with CSS

**Source:** `static/app.js` lines 177–180, 201–203, 214–215, 241–245, 252–255, 283–290, 296–303
**Apply to:** `static/style.css`

The JS machine controls visibility of `#progress-area`, `#result-card`, `#error-area`, `#validation-error`, `#submit-btn`, `#retry-btn` exclusively via `.hidden = true/false`. CSS must NOT set `display` on any of these elements. The browser's native `[hidden] { display: none }` rule handles all visibility.

```javascript
// Pattern repeated throughout app.js:
$('progress-area').hidden = false;   // show
$('result-card').hidden = true;      // hide
$('error-area').hidden = true;       // hide
```

If CSS adds `#progress-area { display: block; }`, it overrides `[hidden]` and breaks the state machine.

### JS class hook — sg-url-input--error

**Source:** `static/app.js` lines 172, 184, 236 (`showIdle`, `showSubmitting`, `showErrorValidation`)
**Apply to:** `static/style.css`

```javascript
// app.js line 172 (showIdle):
$('url-input').classList.remove('sg-url-input--error');
// app.js line 236 (showErrorValidation):
$('url-input').classList.add('sg-url-input--error');
```

The CSS rule for this class is mandatory:
```css
.sg-url-input--error {
  border-color: #ff3300 !important;
}
```

### `api_client` fixture — conftest.py

**Source:** `tests/conftest.py` lines 67–111
**Apply to:** `tests/test_frontend.py` (all 5 new tests that need HTTP)

All HTTP-based tests receive `api_client` as a parameter. The fixture:
- Sets `task_always_eager = True` (Celery runs inline, no broker needed)
- Flushes rate-limit Redis keys before each test
- Patches `api.tasks.check_duration` to prevent real network calls
- Yields a `fastapi.testclient.TestClient` instance

The filesystem-only test (`test_css_no_modern_properties`) does NOT receive `api_client` — it reads the file directly with `pathlib.Path`.

### Color palette constants (for tests)

**Source:** CONTEXT.md §1
**Apply to:** `tests/test_frontend.py::test_style_css_served`

Substrings to assert presence of in style.css body:
- `#000000` — page background
- `#ff8800` — primary accent

Substrings to assert absence of:
- `var(` — no CSS custom properties

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `static/style.css` | config (stylesheet) | — | No CSS file exists yet; no prior stylesheet in the project. Patterns come entirely from CONTEXT.md and RESEARCH.md. |
| `static/fonts/DelaGothicOne-Regular.woff2` | asset (binary) | file-I/O | Binary font asset — no code pattern applies; created via `curl` (see RESEARCH.md §Download Procedures). |
| `static/fonts/Sligoil-Micro.woff2` | asset (binary) | file-I/O | Binary font asset — no code pattern applies; created via `unzip` from GitLab zip (see RESEARCH.md §Download Procedures). |

---

## Metadata

**Analog search scope:** `static/`, `tests/`
**Files scanned:** 4 (`static/index.html`, `static/app.js`, `tests/test_frontend.py`, `tests/conftest.py`)
**Pattern extraction date:** 2026-05-08
