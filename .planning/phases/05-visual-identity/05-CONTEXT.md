---
phase: 05-visual-identity
status: ready
created: 2026-05-08
source: gsd-discuss-phase 5
---

# Phase 5 Context — Visual Identity

Decisions captured from user discussion. Researcher and planner should treat every item here as locked — do not re-ask the user about these choices.

---

## 1. Color Palette

All colors expressed in raw hex only. No hsl(), no rgba() with floats, no CSS custom properties.

| Role | Hex | Notes |
|------|-----|-------|
| Page background | `#000000` | Pure black — no tint |
| All text (titles, labels, values, body) | `#ff8800` | Monochromatic — same color for everything |
| All borders | `#ff8800` | Same orange-amber as text |
| Button background (primary / download) | `#ff8800` | Inverted: bg orange, text black |
| Button text | `#000000` | High contrast against #ff8800 bg |
| Input field background | `#000000` | Same as page |
| Input field border | `#ff8800` | 1px solid |
| Input field text | `#ff8800` | Consistent with palette |

**Palette rationale:** Monochromatic radical — single accent color for everything. NFO/warez scene aesthetic (BeatMasters International 2000 reference). No secondary palette colors.

---

## 2. Typography

### Fonts selected
**Dela Gothic One** — headers, site title, button labels
- Style: Ultra heavy, flat Gothic display. Dramatic Japanese-influenced boldness.
- Weight available: Regular (single weight, already ultra heavy by design)
- License: SIL OFL — free for production, self-hostable
- Source: Google Fonts (download woff2 to static/fonts/, no CDN call)

**Sligoil** — body text, labels, BPM values, key values, numeric data
- Style: Funky monospace with large inktraps. Created for an indie game interface.
- License: SIL OFL — Velvetyne Type Foundry
- Source: gitlab.com/velvetyne/sligoil (download woff2 to static/fonts/)

### Font loading rules
- Both fonts served from `static/fonts/` — no external CDN calls
- `@font-face` declarations in `static/style.css`
- `font-display: block` — text stays invisible until font loads (prevents FOUT mid-paint)
- Font smoothing: explicitly disabled site-wide
  ```css
  body {
    -webkit-font-smoothing: none;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeSpeed;
  }
  ```

### Font size scale (raw px, no rem/em/variable)
- Site title (`#site-title`): 48px Dela Gothic One
- Tagline (`#site-tagline`): 14px Sligoil
- BPM / Key values (primary): 32px Sligoil
- Labels (BPM, Tonalidade, etc.): 11px Sligoil uppercase
- Body / UI text: 13px Sligoil
- Button text: 16px Dela Gothic One

---

## 3. Layout Structure

### Rules (locked, non-negotiable)
- Layout built with HTML `<table>` elements — no `display: flex`, no `display: grid` anywhere in the stylesheet
- No CSS variables (`--anything`) anywhere in style.css
- Width: 640px centered via `align="center"` attribute on the outer table (HTML attribute, not CSS)
- Cell spacing/padding via `cellpadding` and `cellspacing` HTML attributes where possible, supplemented by inline `style` attributes only where attributes are insufficient

### Table hierarchy
```
<table width="640" align="center">  ← outer container
  <tr>
    <td>  ← header row (title + tagline)
  <tr>
    <td>  ← form row (input + button)
  <tr>
    <td>  ← duration hint row
  <tr>
    <td>  ← progress row (hidden when not polling)
  <tr>
    <td>  ← result card row (2-column inner table)
  <tr>
    <td>  ← error row (hidden)
```

### Result card — 2-column inner table
```
<table width="100%">
  <tr>
    <td width="50%">        ← BPM column
      BPM: 128
      Metade: 64
      Dobro: 256
    <td width="50%">        ← Key column
      Tonalidade: F# minor
      Camelot: 11A
  <tr>
    <td colspan="2">        ← Size + Download (full width)
      Tamanho: ~42 MB
      [BAIXAR WAV]
```

---

## 4. Visual References

Images provided by user during discussion:

1. **NFO BeatMasters International 2000** — primary aesthetic reference
   - Pure black background
   - Monochromatic orange/amber ASCII art and text
   - Box-drawing characters for borders
   - All-caps section headers
   - Dense information density

2. **neoworlds.online** — table layout and border style reference
   - Narrow centered column
   - 1px solid borders on all containers
   - Minimal spacing, information-first layout

3. **Tibia forum** — dark theme, section structure
4. **ANSI art collection** — color and character density inspiration

### Research step
The aesthetic is already defined via user-provided references. The researcher does NOT need to do Wayback Machine research. Instead:
- Reference the 4 images above
- Read existing `static/index.html` to understand current DOM structure
- Research Sligoil and Dela Gothic One download/self-hosting process

---

## 5. Interactive States

Hover and focus in raw CSS only. No transitions (CSS transitions are a post-2005 feature — excluded for authenticity).

| Element | Default | Hover / Focus |
|---------|---------|---------------|
| Submit button | bg `#ff8800`, text `#000000` | bg `#ff6600`, text `#000000` (slightly brighter on hover) |
| Download link | same as submit button | same hover behavior |
| URL input | border `#ff8800` | border `#ff6600` on focus (`:focus` selector) |
| Retry button | border `1px solid #ff8800`, bg `#000000`, text `#ff8800` | bg `#ff8800`, text `#000000` |

No `transition`, no `animation`, no `transform`. Color changes only.

---

## 6. Additional Style Rules

- `box-sizing: border-box` NOT used (it's a modern property — old sites used content-box default)
- No `border-radius` (round corners are post-2005 aesthetics)
- No `box-shadow` (same reason)
- `cursor: pointer` on buttons (acceptable as it was supported in IE6)
- Input `placeholder` color via `::-webkit-input-placeholder` and `::placeholder` — `#ff8800` at 50% opacity expressed as `#804400` in hex (no rgba)
- Error state on input: add inline `border-color: #ff3300` via JS (direct style, no class toggle needed)

---

## 7. Scope of CSS Work

Phase 5 creates one new file:
- `static/style.css` — the entire stylesheet, linked from `static/index.html` via `<link rel="stylesheet">`

Phase 5 modifies:
- `static/index.html` — add `<link>` tag for style.css; convert `<div>` layout to `<table>` layout while preserving all 16 required DOM IDs (JS must not break)
- `static/fonts/` — new directory containing Dela Gothic One and Sligoil woff2 files

Phase 5 does NOT touch:
- `api/` — backend is complete
- `static/app.js` — 8-state machine is complete; only DOM IDs matter, not container elements
- Any Python or test files

---

## 8. JS Compatibility Constraint

The 8-state machine in `static/app.js` references elements by ID only (e.g., `document.getElementById('bpm-value')`). When converting `<div>` to `<table>` layout in index.html, all 16 required DOM IDs must survive the conversion intact.

The 16 required IDs:
`app`, `header`, `site-title`, `site-tagline`, `form-area`, `duration-hint`, `input-group`, `url-input`, `submit-btn`, `validation-error`, `progress-area`, `progress-label`, `result-card`, `result-bpm`, `result-key`, `result-size`, `download-area`, `bpm-value`, `bpm-half-value`, `bpm-double-value`, `key-value`, `camelot-value`, `size-value`, `download-link`, `error-area`, `error-message`, `retry-btn`

IDs can live on `<td>`, `<tr>`, or `<table>` elements — the JS doesn't care about the element type, only the ID.

---

## Decisions NOT Made Here (Left to Planner)

- Exact font-size for each breakpoint (N/A — no responsive design, fixed 640px)
- Whether to add a `<meta http-equiv="Content-Type">` for old-browser compatibility (planner decides)
- Number of `<table>` nesting levels (planner decides based on layout needs)
- Order of plans/waves (planner decides)
