---
sketch: 002
name: ascii-3d
question: "Qual abordagem ASCII 3D carrega melhor o peso visual do SoundGrabber?"
winner: null
tags: [visual, ascii, nfo, terminal, 3d]
---

# Sketch 002: ASCII 3D

## Design Question
Como criar profundidade 3D usando apenas caracteres ASCII (░▒▓█ e box-drawing ╔═╗║╚╝)?

## How to View
```
open .planning/sketches/002-ascii-3d/index.html
```

## Variants
- **A: Box-Drawing + ░▒▓** — Frame ╔═══╗/╚═══╝ com 3 camadas de sombra ▓▒░ offset por JS. Título em Dela Gothic. Mais limpo.
- **B: Block Art Title** — "SOUNDGRABBER" em ASCII block art (▄▀█), sombra do painel preenchida com ▓▓▓. Visual BBS/demo scene máximo.
- **C: BBS Terminal** — Terminal completo: `C:\BEATS> soundgrabber.exe`, progress bar BBS `████░░ 64%`, cursor piscando. Mais interativo.

## What to Look For
- Qual variante parece mais "underground" e autêntica?
- O ASCII block art do título (B) legível e com peso?
- A barra de progresso BBS (C) encaixa na UX?
- A sombra de ░▒▓ lê como 3D ou só como noise?
