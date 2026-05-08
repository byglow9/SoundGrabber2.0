---
phase: 05-visual-identity
created: 2026-05-08
---

# Discussion Log — Phase 5: Visual Identity

## Session: 2026-05-08

### Gray areas discussed

**1. Referências visuais**
- Apresentadas 4 opções de estilo (phpBB light, phpBB dark, warez boards, ANSI art)
- Usuário escolheu: phpBB dark + warez boards (opções 1 e 3 da escala)
- Usuário enviou 4 imagens de referência: neoworlds.online, tibia.com/forum, ANSI art collection, NFO BeatMasters International 2000
- Decisão: NFO/warez como referência primária. Preto puro, laranja/amber monocromático, densidade informacional alta

**2. Paleta de cores**
- Background: usuário escolheu `#000000` puro (sem tint)
- Texto: direção laranja/amber confirmada pelo usuário; finalizado em `#ff8800`
- Bordas: `#ff8800` (mesmo laranja do texto)
- Resultado: paleta monoclromática radical — `#ff8800` para tudo, `#000000` fundo

**3. Tipografia**
- Pesquisa realizada: fontes bitmap tradicionais (VT323, Press Start 2P, Courier New) rejeitadas pelo usuário como "manjadas"
- Pesquisa bitmap única: Cordata PPC-21 + Spleen 8x16 (encontrado antes da compactação de contexto)
- Usuário enviou imagem com fontes bold/geométricas (Fatso, DR-GAN, Gikit-BB Bureau, GNE Boolean) como referência de estética desejada
- Três caminhos apresentados: (A) bold geométrico, (B) pixel único, (C) híbrido
- Usuário escolheu: **Caminho A — Bold geométrico**
- Par final: **Dela Gothic One** (headers) + **Sligoil** (body/valores)
  - Pela Velvetyne: Sligoil é SIL OFL, criada para interface de jogo indie, muito incomum
  - Pela Google Fonts: Dela Gothic One, SIL OFL, ultra pesada, sem CDN — self-hosted

**4. Layout/estrutura de tabelas**
- Confirmado: HTML `<table>` para layout (sem flexbox/grid — decisão já travada no roadmap)
- Estrutura: coluna única centralizada 640px
- Result card: 2 colunas (BPM esquerda | Key direita)

### Deferred ideas (fora do escopo da fase)

- Nenhum item deferido nesta sessão

### Outcome

`05-CONTEXT.md` escrito com todas as decisões. Fase pronta para planejamento.
