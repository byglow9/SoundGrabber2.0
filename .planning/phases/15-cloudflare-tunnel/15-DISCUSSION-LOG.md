# Phase 15: Cloudflare Tunnel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 15-Cloudflare Tunnel
**Areas discussed:** Tipo de URL publica, Como rodar cloudflared, Politica de exposicao publica

---

## Tipo de URL publica

| Option | Description | Selected |
|--------|-------------|----------|
| Dominio customizado | URL estavel, melhor para uso real; exige DNS/Cloudflare configurado. | |
| `.trycloudflare.com` temporario | Mais rapido para validar, mas a URL muda e nao serve bem como producao. | |
| Comecar temporario | Valida com `trycloudflare` agora e deixa dominio customizado como passo futuro. | ✓ |

**User's choice:** Comecar com `.trycloudflare.com` temporario.
**Notes:** A URL temporaria conta como conclusao tecnica da fase se os gates passarem; dominio customizado fica como backlog.

| Option | Description | Selected |
|--------|-------------|----------|
| Manual no terminal | Operador copia a URL exibida pelo `cloudflared`. | ✓ |
| Registrar em arquivo | Salvar URL em arquivo local para comandos reutilizarem. | |
| Voce decide | Planner escolhe a forma mais simples. | |

**User's choice:** Manual no terminal.
**Notes:** O operador copia a URL do terminal e usa na validacao.

| Option | Description | Selected |
|--------|-------------|----------|
| Frontend manual | Abrir a URL publica no navegador, colar 3 links e baixar os WAVs. | ✓ |
| API via curl/script | Testar `POST /jobs`, polling e download por comandos. | |
| Ambos | Frontend como prova principal, API como diagnostico. | |

**User's choice:** Frontend manual.
**Notes:** O usuario perguntou se era possivel testar pelo frontend; ficou decidido que sim e que esta sera a prova principal dos 3 E2E.

---

## Como rodar cloudflared

| Option | Description | Selected |
|--------|-------------|----------|
| `cloudflared` via systemd no host | Mais alinhado ao requisito persistente; sobe independente do Compose. | |
| `cloudflared` como servico no Docker Compose | Fica junto da stack, mas exige editar compose e gerenciar token/env. | |
| Comecar manual e depois service | Rodar `cloudflared tunnel --url http://localhost:8000` para validar; transformar em servico se passar. | ✓ |

**User's choice:** Comecar manual e depois service.
**Notes:** Recomendacao aceita: quick tunnel manual nesta fase; service fica deferred junto com dominio customizado.

| Option | Description | Selected |
|--------|-------------|----------|
| Plano instala no notebook | Incluir comandos oficiais e verificar `cloudflared --version`. | |
| Operador instala antes | A fase assume `cloudflared` ja existente. | |
| Checkpoint humano | Plano explica instalacao, pausa para operador executar e valida depois. | ✓ |

**User's choice:** Checkpoint humano.
**Notes:** Instalacao de ferramenta no host deve ser acao operacional confirmada pelo operador.

| Option | Description | Selected |
|--------|-------------|----------|
| Depois do Compose estar saudavel | Primeiro Compose e `/health` local OK; depois tunnel. | ✓ |
| Junto com o deploy | Deploy e tunnel no mesmo roteiro. | |
| Independente | Operador decide quando ligar/desligar. | |

**User's choice:** Depois do Compose estar saudavel.
**Notes:** Evita expor uma aplicacao quebrada ou sem Redis saudavel.

---

## Politica de exposicao publica

| Option | Description | Selected |
|--------|-------------|----------|
| Tudo como esta por pouco tempo | Simples; `/yonkou` tambem fica acessivel e protegido por senha/admin cookie. | |
| So fluxo publico principal | Tentar bloquear `/yonkou`; provavelmente exige novo escopo de app/proxy. | |
| Tudo como esta, mas com checklist operacional | Tunnel temporario, senha forte, desligar/gerenciar conscientemente. | ✓ |

**User's choice:** Tudo como esta, mas com checklist operacional.
**Notes:** Foi esclarecido que `/yonkou` fica acessivel via URL publica enquanto o tunnel estiver ativo.

| Option | Description | Selected |
|--------|-------------|----------|
| Desligar imediatamente | Encerrar `cloudflared` depois dos 3 E2E. | |
| Deixar ativo ate voce mandar parar | O plano avisa que a URL segue ativa e mostra como encerrar. | ✓ |
| Voce decide durante execucao | Checkpoint final pergunta se mantem ou encerra. | |

**User's choice:** Deixar ativo ate o operador mandar parar.
**Notes:** O plano nao deve matar automaticamente o processo ao final.

| Option | Description | Selected |
|--------|-------------|----------|
| Senha forte obrigatoria | Bloquear se `ADMIN_PASSWORD` ou `ADMIN_SESSION_SECRET` usam valores de exemplo. | ✓ |
| So checklist visual | Lembrar de conferir, sem bloquear. | |
| Sem gate extra | Ligar tunnel assim que `/health` local estiver OK. | |

**User's choice:** Senha forte obrigatoria.
**Notes:** Gate bloqueante antes da exposicao publica.

## the agent's Discretion

- O planner pode escolher o formato exato do checklist operacional.
- API/curl pode ser usado como diagnostico, mas nao substitui o E2E principal pelo frontend.

## Deferred Ideas

- Dominio customizado estavel no Cloudflare.
- `cloudflared` como servico systemd persistente.
- Protecao especifica para `/yonkou` antes de exposicao permanente.
