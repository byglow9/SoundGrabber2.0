# SoundGrabber — Project Guide

## What This Is

Ferramenta web para produtores e artistas underground colarem um link do YouTube, baixarem o beat em WAV e visualizarem BPM e tonalidade. Gratuito, sem cadastro, download direto. Estética autêntica dos anos 2000 (phpBB/Tibia/Orkut).

## Stack

- **Backend:** Python 3.11 + FastAPI
- **Task queue:** Celery + Redis
- **Download:** yt-dlp (com cookies + PO Token — obrigatório para YouTube)
- **Conversão:** FFmpeg
- **Análise:** librosa (BPM + key detection)
- **Frontend:** Vanilla HTML + CSS + JS — zero frameworks

## GSD Workflow

Este projeto usa GSD para planejamento e execução.

### Comandos principais

```
/gsd-plan-phase 1     # Planejar a próxima fase
/gsd-execute-phase 1  # Executar os planos da fase
/gsd-progress         # Ver estado atual do projeto
/gsd-discuss-phase N  # Discutir abordagem antes de planejar
```

### Arquivos de planejamento

- `.planning/PROJECT.md` — contexto e decisões do projeto
- `.planning/REQUIREMENTS.md` — requisitos v1 com REQ-IDs
- `.planning/ROADMAP.md` — 5 fases, 19 requisitos mapeados
- `.planning/STATE.md` — estado atual
- `.planning/research/` — pesquisa de domínio (stack, features, arquitetura, pitfalls)

## Fases

| # | Fase | Status |
|---|------|--------|
| 1 | Processing Pipeline | Not started |
| 2 | API Layer | Not started |
| 3 | Hardening | Not started |
| 4 | Frontend | Not started |
| 5 | Visual Identity | Not started |

## Restrições críticas

- **Sem contas de usuário** — ferramenta stateless, sem auth
- **WAV apenas** — formato lossless, qualidade para produtores
- **Limite de 15 minutos** — vídeos mais longos são recusados
- **Estética Y2K autêntica** — construído COMO sites de 2000-2005, não releitura moderna. Tabelas para layout, sem flexbox/grid, fontes bitmap, hex colors brutas, sem CSS variables
- **YouTube bot detection** — yt-dlp DEVE usar cookies + PO Token desde o primeiro deploy

## Próximo passo

```
/gsd-discuss-phase 1
```
