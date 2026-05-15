# Phase 15: Cloudflare Tunnel - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Expor temporariamente o SoundGrabber pela internet usando Cloudflare Tunnel, sem abrir portas no roteador e sem expor o IP residencial. Esta fase valida uma URL HTTPS publica `.trycloudflare.com` apontando para `http://localhost:8000` no notebook, prova `/health` via rede externa e executa 3 downloads E2E pelo frontend publico.

Esta fase NAO entrega dominio customizado persistente nem `cloudflared` como servico systemd permanente. Esses itens entram como backlog apos a validacao tecnica com tunnel temporario.

</domain>

<decisions>
## Implementation Decisions

### URL publica temporaria

- **D-01:** Usar `.trycloudflare.com` primeiro. O operador roda `cloudflared tunnel --url http://localhost:8000`, copia manualmente a URL exibida no terminal e usa essa URL nos gates de validacao.
- **D-02:** A Phase 15 pode fechar tecnicamente com a URL `.trycloudflare.com` se `/health` e os 3 E2E pelo frontend passarem. Dominio customizado estavel nao bloqueia esta fase.
- **D-03:** A URL gerada pelo quick tunnel nao precisa ser persistida em arquivo pelo plano. O operador copia a URL do terminal e cola nos comandos/checklists de validacao.
- **D-04:** Os 3 E2E publicos devem usar o frontend, nao apenas API direta: abrir a URL publica no navegador, colar 3 links de beats, acompanhar o status e baixar os WAVs. API/curl pode ser usado apenas para diagnostico se o frontend falhar.

### Execucao do cloudflared

- **D-05:** Comecar manualmente e depois transformar em servico somente se tudo passar. O comando inicial da fase e `cloudflared tunnel --url http://localhost:8000`.
- **D-06:** A instalacao do `cloudflared` no notebook e checkpoint humano. O plano deve explicar os passos de instalacao, pausar para o operador executar e depois validar `cloudflared --version`.
- **D-07:** O tunnel so deve ser iniciado depois do Compose estar saudavel: `docker compose up -d`, `docker compose ps` OK e `/health` local em `http://localhost:8000/health` retornando 200.
- **D-08:** Nao adicionar `cloudflared` ao `docker-compose.yml` nesta fase. O compose continua responsavel pela aplicacao; o tunnel temporario roda como processo operacional separado no host.

### Politica de exposicao publica

- **D-09:** Durante o quick tunnel, tudo que a aplicacao expõe hoje fica acessivel pela URL publica, incluindo `/yonkou`. Isso e aceito para a janela temporaria de teste.
- **D-10:** Antes de ligar o tunnel publico, o plano deve aplicar gate bloqueante: `ADMIN_PASSWORD` e `ADMIN_SESSION_SECRET` no `.env` do notebook nao podem estar com valores de exemplo. Se estiverem, parar e pedir ao operador para trocar.
- **D-11:** O plano nao deve encerrar automaticamente o tunnel apos os testes. O tunnel permanece ativo ate o operador mandar parar.
- **D-12:** Ao final, o plano deve avisar explicitamente que a URL publica continua ativa, que `/yonkou` tambem esta exposto enquanto `cloudflared` estiver rodando, e mostrar o comando/acao para encerrar o processo.

### the agent's Discretion

- O planner pode escolher o formato exato do checklist operacional, desde que inclua: Compose saudavel, `/health` local OK, senha/secret fortes, `cloudflared --version`, URL publica copiada, `/health` publico OK e 3 E2E pelo frontend.
- O planner pode usar API/curl como diagnostico adicional, mas nao pode substituir a prova principal via frontend publico.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos e roadmap

- `.planning/ROADMAP.md` §Phase 15 — objetivo, dependencia da Phase 14 e criterios de sucesso da exposicao publica.
- `.planning/REQUIREMENTS.md` §TUNNEL — TUNNEL-01 (`cloudflared` rodando e route para `localhost:8000`) e TUNNEL-02 (URL HTTPS publica com 3 E2E).
- `.planning/PROJECT.md` §Current Milestone v1.3 — Cloudflare Tunnel como exposicao publica opcional apos validar notebook.

### Contexto de fases anteriores

- `.planning/phases/14-pipeline-e2e-on-notebook/14-CONTEXT.md` — deploy no notebook, cookies em `/data/yt-dlp-cache`, `scripts/deploy.sh`, E2E privado antes da exposicao publica.
- `.planning/phases/13-docker-compose/13-CONTEXT.md` — estrutura do `docker-compose.yml`, porta `8000`, rede interna, Redis/bgutil sem ports e restricoes de container.
- `.planning/phases/12-notebook-foundation/12-CONTEXT.md` — administracao via Tailscale, sem port-forward residencial, sem `network_mode: host`, sem containers privileged, UFW/DOCKER-USER como hardening futuro.

### Codigo e operacao local

- `docker-compose.yml` — `api` publica `8000:8000`; Redis e bgutil permanecem internos; api/worker usam `.env`.
- `scripts/deploy.sh` — fluxo remoto existente: `git pull` e `sudo docker compose up --build -d`.
- `.env.example` — valores de referencia para `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, `YTDLP_CACHE_DIR`, `BGUTIL_BASE_URL`.
- `api/main.py` — rota `GET /health` usada como smoke test local e publico.
- `CLAUDE.md` §Security Gate — controles para scripts shell e cuidado com segredos.

### Cloudflare docs

- `https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/` — Quick Tunnels e comando `cloudflared tunnel --url`.
- `https://developers.cloudflare.com/tunnel/advanced/local-management/as-a-service/` — referencia para backlog de rodar `cloudflared` como servico persistente.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `docker-compose.yml` — ja sobe a aplicacao em `localhost:8000`; Phase 15 deve consumir essa porta, nao reestruturar a stack.
- `scripts/deploy.sh` — ja existe como caminho operacional para atualizar o notebook antes de ligar o tunnel.
- `api/main.py` `/health` — liveness probe simples, retorna 200 quando Redis responde.
- `.env.example` — fonte para conferir se `ADMIN_PASSWORD` e `ADMIN_SESSION_SECRET` foram trocados no `.env` real do notebook.

### Established Patterns

- Infra do notebook deve evitar port-forward residencial; Cloudflare Tunnel e o caminho publico.
- Operacoes sensiveis no host devem usar checkpoints humanos quando exigem acao do operador.
- Segredos ficam no `.env` ou no host, nunca em arquivos de planejamento ou commits.
- Fases anteriores evitam ampliar escopo de seguranca no meio de entrega: quick tunnel temporario aceita checklist operacional; hardening permanente fica para fase futura.

### Integration Points

- `cloudflared tunnel --url http://localhost:8000` conecta a Cloudflare ao `api` exposto pelo Compose.
- Gate local: `curl http://localhost:8000/health` antes de iniciar o tunnel.
- Gate publico: `curl https://<trycloudflare-url>/health` de fora da rede/Tailscale.
- E2E publico: frontend em `https://<trycloudflare-url>/` com 3 links reais de beats.

</code_context>

<specifics>
## Specific Ideas

- Comando principal: `cloudflared tunnel --url http://localhost:8000`.
- O operador copia manualmente a URL `.trycloudflare.com` do terminal.
- O tunnel fica ativo ate o operador encerrar manualmente.
- O plano deve avisar que `/yonkou` fica publico durante o tunnel e deve exigir `ADMIN_PASSWORD` / `ADMIN_SESSION_SECRET` fortes antes de ligar.
- Validacao principal: frontend publico, 3 downloads completos, WAVs baixaveis, BPM e tonalidade exibidos.

</specifics>

<deferred>
## Deferred Ideas

- Dominio customizado estavel no Cloudflare apos a validacao tecnica com `.trycloudflare.com`.
- Converter `cloudflared` para servico systemd persistente apos validacao manual e/ou quando houver dominio customizado.
- Bloquear ou proteger `/yonkou` com Cloudflare Access, middleware, rota separada ou regra de proxy antes de uma exposicao permanente.

</deferred>

---

*Phase: 15-Cloudflare Tunnel*
*Context gathered: 2026-05-15*
