# Phase 11: Som da Semana — Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Painel curado de lançamentos underground: o operador (dono do site) cadastra um "Som da Semana" via mini painel `/yonkou` e todos os visitantes veem o card na sidebar direita do site. A fase entrega o painel frontend, o mini painel operador-only, a rota de API e o armazenamento do conteúdo curado.

</domain>

<decisions>
## Implementation Decisions

### D-01 — Gestão do conteúdo
- **D-01a:** Mini painel `/yonkou` com formulário HTML visual — o operador preenche os campos e salva via submit.
- **D-01b:** Autenticação via senha simples: variável de ambiente `ADMIN_PASSWORD`. Ao fazer login, gera cookie de sessão assinado. Sem dependências extras de auth.
- **D-01c:** Controle de troca manual — o operador atualiza quando quiser, sem expiração automática por data.
- **D-01d:** Armazenamento em Redis (já disponível na stack) sob chave `featured:current`. Fallback para arquivo JSON se Redis estiver indisponível (graceful degradation).
- **D-01e:** Não haverá botão, link, menu ou affordance pública apontando para o painel. A rota canônica é `/yonkou`. Isso reduz descoberta casual, mas NÃO substitui autenticação, cookie assinado e rate limit.

### D-02 — Layout e posição no site
- **D-02a:** Sidebar à direita da tabela `#app` (640px). Implementada como coluna adicional na tabela HTML raiz — sem flexbox/grid, fiel à estética Y2K.
- **D-02b:** O sidebar só renderiza quando há conteúdo cadastrado. Se `GET /featured` retornar vazio (204 ou `{}`), o JS não injeta a coluna e o layout volta ao `#app` centralizado.
- **D-02c:** Largura da sidebar: ~220px. Separação visual por borda `1px solid #ff8800` no lado esquerdo do card.

### D-03 — Campos do card
Campos cadastrados via `/yonkou` e exibidos no card da sidebar:
- **artista** — nome do artista/projeto
- **titulo** — título da obra/release
- **genero** — estilo musical em texto livre (ex: phonk, trap, boom bap)
- **descricao** — nota editorial do operador (voz curatorial, 1-3 frases)
- **data_adicao** — preenchida automaticamente pelo backend no momento do cadastro (ISO date → exibida como DD/MM/YYYY)
- **links** — até 3 pares `{label, url}` definidos pelo operador (ex: `["Spotify", "https://..."]`, `["Instagram", "https://..."]`). Labels ficam nos botões do card.

### D-04 — Comportamento dos links
- **D-04a:** Todos os links do card abrem em nova aba (`target="_blank" rel="noopener"`). Sem integração especial com o campo de download.
- **D-04b:** Não há detecção de plataforma (YouTube vs Spotify vs Instagram) — todos tratados igualmente.

### D-05 — Estética do card (Y2K / phpBB)
- Fundo `#000000`, texto `#ff8800`, borda `1px solid #ff8800` — mesma paleta do restante do site.
- Header do card: `:: SOM DA SEMANA ::` em fonte Sligoil uppercase.
- Linha separadora `----` entre o header e o conteúdo (estilo assinatura de fórum).
- Botões de link: estilo dos botões existentes — borda laranja, fundo preto, hover inverte.
- Data exibida em 11px laranja escuro (`#804400`), estilo metadata de fórum.
- Sem imagens, sem artwork, sem embeds — só texto e links.

### D-06 — Security Gate (obrigatório pelo CLAUDE.md)
Todo endpoint novo DEVE seguir o Security Gate:
- `GET /featured` — rate limit 60/min, `request: Request, response: Response` na assinatura.
- `POST /featured` (operador) — rate limit 10/min, Pydantic BaseModel para o body, autenticação via cookie de sessão.
- `POST /yonkou/login` — rate limit 5/min para mitigar brute force.
- Testes em `tests/test_security.py` para rate limit e validação do endpoint operador-only.

### Claude's Discretion
- Estrutura interna do armazenamento Redis (hash vs string JSON serializado).
- Token/assinatura do cookie de sessão (itsdangerous ou HMAC simples).
- Organização interna do painel operador-only (HTML separado ou inline em main.py).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Segurança e convenções do projeto
- `CLAUDE.md` §Security Gate — controles obrigatórios para qualquer novo endpoint HTTP
- `.planning/SECURITY-CHECKLIST.md` — lista completa dos controles SEC-* ativos
- `api/main.py` — padrões de rota existentes (slowapi, Pydantic, lifespan)

### Estética e frontend
- `static/style.css` — paleta de cores, tipografia, padrões de botão e borda
- `static/index.html` — estrutura HTML atual da tabela `#app` e `#wrapper`
- `static/app.js` — padrões de manipulação de DOM (hidden, states, event wiring)

### Contexto do projeto
- `.planning/PROJECT.md` — restrições de arquitetura (sem contas, stateless, Y2K)
- `.planning/REQUIREMENTS.md` — requisitos VISUAL-01..05 (regras de estética)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `#info-modal` (index.html + style.css): padrão de painel flutuante com título, body e botão de ação — referência direta para o card da sidebar em termos de estilo.
- `#gh-corner` (index.html): elemento `position: fixed` com logo SVG inline — prova que elementos fora da tabela principal já existem e funcionam.
- Classe `.label` (style.css): texto 13px uppercase laranja — reutilizável como estilo para `:: SOM DA SEMANA ::`.
- Padrão de botão `#info-btn` / `#clear-btn`: border 1px #ff8800, bg #000, hover inverte — base para botões de link do card.

### Established Patterns
- **Rotas FastAPI**: sempre `request: Request, response: Response` na assinatura quando slowapi está ativo (sem isso levanta Exception em runtime).
- **Pydantic BaseModel + field_validator**: padrão para validação de body em qualquer POST.
- **Hidden sections via JS**: `element.hidden = true/false` — mesmo padrão para mostrar/esconder a coluna da sidebar com base na resposta do `GET /featured`.
- **Fetch polling no app.js**: padrão de `fetch('/jobs/{id}')` pode ser reusado para `fetch('/featured')` na inicialização da página.

### Integration Points
- `api/main.py`: novo endpoint `GET /featured` e rotas `/yonkou/*` se encaixam após as rotas de jobs e antes do mount de StaticFiles.
- `static/index.html`: a tabela raiz (`<table id="app">`) precisa receber uma coluna adicional `<td id="sidebar">` que o JS popula dinamicamente.
- `api/config.py`: nova variável `admin_password: str` + `admin_session_secret: str` seguindo o padrão de `Settings` existente.

</code_context>

<specifics>
## Specific Ideas

- O operador mencionou explicitamente querer campos de **link do Spotify** e **link do Instagram** — os 3 links genéricos cobrem isso e permitem adicionar outros no futuro sem mudar o schema.
- A data de adição deve aparecer no card para sinalizar que o conteúdo é atualizado ("adicionado em 11/05") — confere credibilidade à curadoria.
- A estética desejada é a de um **widget de fórum phpBB** — header `:: SOM DA SEMANA ::`, separador `----`, conteúdo em monospace, botões de ação no rodapé do card.

</specifics>

<deferred>
## Deferred Ideas

- **Histórico de releases anteriores** — exibir os últimos N "Sons da Semana" em uma página `/arquivo`. Pertence a uma fase futura após a fase 11 estar estável.
- **Votação / reação da comunidade** — usuários reagirem ao som curado. Exigiria persistência de estado por usuário, fora do escopo stateless atual.
- **Notificação por email/RSS quando troca** — integração de notificação para comunidade. Fase futura independente.

</deferred>

---

*Phase: 11-som-da-semana*
*Context gathered: 2026-05-11*
