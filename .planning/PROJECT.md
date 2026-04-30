# SoundGrabber

## What This Is

Ferramenta web para produtores e artistas underground colarem o link de um vídeo do YouTube (normalmente um beat), baixarem o áudio em formato WAV e visualizarem o BPM e a tonalidade musical detectados automaticamente. Sem cadastro, sem fricção — entra, cola o link, baixa. A identidade visual segue a estética nostálgica da internet dos anos 2000: fóruns phpBB, Tibia/sites RPG, Orkut.

## Core Value

O produtor cola um link do YouTube e recebe o beat em WAV com BPM e nota identificados em menos de um minuto, sem nenhuma conta ou instalação.

## Requirements

### Validated

- [x] Sistema baixa o áudio do vídeo do YouTube via yt-dlp com cookies + PO Token — Validado na Fase 1
- [x] Sistema converte o áudio para formato WAV via FFmpeg — Validado na Fase 1
- [x] Sistema detecta e exibe o BPM do beat (librosa.feature.tempo) — Validado na Fase 1
- [x] Sistema detecta e exibe a tonalidade musical em notação padrão e Camelot — Validado na Fase 1
- [x] Sistema rejeita vídeos com mais de 15 minutos — Validado na Fase 1

### Active

- [ ] Usuário pode colar um link do YouTube e iniciar o processamento
- [ ] Sistema baixa o áudio do vídeo do YouTube
- [ ] Sistema converte o áudio para formato WAV
- [ ] Usuário pode baixar o arquivo WAV diretamente na página (sem email, sem conta)
- [ ] Sistema detecta e exibe o BPM do beat
- [ ] Sistema detecta e exibe a tonalidade musical (ex: F# minor)
- [ ] Interface visual com estética anos 2000 (fórum/RPG/Orkut)
- [ ] Aplicação funciona sem cadastro ou login

### Out of Scope

- Contas de usuário / histórico de downloads — sem fricção é o princípio central
- Monetização / paywall — versão v1 totalmente gratuita
- Outros formatos de export (MP3, FLAC) — WAV é o foco para qualidade máxima
- Integração com outras plataformas além do YouTube (SoundCloud, etc.) — foco no caso de uso principal

## Context

Produtores underground frequentemente usam o YouTube como biblioteca de referência de beats e instrumentais. As ferramentas existentes de download de YouTube são genéricas, cheias de ads e não oferecem análise musical. O SoundGrabber resolve esse workflow específico em um lugar só: download em qualidade + dados musicais úteis.

A estética retro dos anos 2000 (Tibia, phpBB, Orkut) é parte da identidade — não apenas visual, mas cultural: conecta com a origem da cena underground que cresceu nessa era da internet.

## Constraints

- **Acesso**: Totalmente aberto, sem autenticação — mantém a experiência sem fricção
- **Escala**: Comunidade underground, centenas de usuários simultâneos — não precisa ser massivamente distribuído mas deve aguentar picos
- **Formato de saída**: WAV (lossless) como padrão — qualidade é prioridade para produtores
- **Dependências externas**: YouTube pode bloquear ou mudar APIs — sistema de download deve ser robusto e atualizável
- **Legalidade**: Uso para fins de produção/referência musical — comum na comunidade, mas yt-dlp terms of service devem ser respeitados

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| WAV como único formato de exportação | Produtores precisam de qualidade lossless para trabalhar | — Pending |
| Sem sistema de contas | Sem fricção é o valor central — qualquer barreira reduz adoção | — Pending |
| Estética Y2K/2000s internet | Identidade cultural da cena underground, diferenciação forte de ferramentas genéricas | — Pending |
| Detecção de BPM e tonalidade inline | Informação crítica para produtores sem precisar abrir outro app | — Pending |

## Evolution

Este documento evolui a cada transição de fase e marco de milestone.

**Após cada transição de fase** (via `/gsd-transition`):
1. Requisitos invalidados? → Mover para Out of Scope com motivo
2. Requisitos validados? → Mover para Validated com referência da fase
3. Novos requisitos surgiram? → Adicionar em Active
4. Decisões a registrar? → Adicionar em Key Decisions
5. "What This Is" ainda preciso? → Atualizar se derivou

**Após cada milestone** (via `/gsd-complete-milestone`):
1. Revisão completa de todas as seções
2. Core Value check — ainda a prioridade certa?
3. Auditoria de Out of Scope — motivos ainda válidos?
4. Atualizar Context com o estado atual

---
*Last updated: 2026-04-30 — Fase 1 completa (pipeline de processamento implementado)*
