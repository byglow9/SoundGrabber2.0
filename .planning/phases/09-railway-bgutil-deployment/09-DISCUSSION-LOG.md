# Phase 9: Railway bgutil Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 9-railway-bgutil-deployment
**Areas discussed:** Porta do bgutil, YTDLP_PO_TOKEN, Verificação pós-config, Aplicação de env vars via MCP

---

## Porta do bgutil

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Porta 4416 por padrão | jim60105/bgutil-pot expõe 4416 sem env var PORT | ✓ (confirmado via logs) |
| Configurar PORT env var | Exigiria variável adicional no serviço bgutil | |

**Verificação:** Logs do deployment `1a83308d` confirmam: `POT server v0.8.1 listening on 0.0.0.0:4416`. Nenhuma configuração adicional necessária.

---

## YTDLP_PO_TOKEN

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Confiar só no bgutil | YTDLP_PO_TOKEN vazio; bgutil gera tokens dinamicamente | ✓ |
| Manter ambos (belt+suspenders) | YTDLP_PO_TOKEN estático + bgutil dinâmico simultaneamente | |

**User's choice:** Confiar só no bgutil
**Notes:** Tokens dinâmicos são superiores; token estático expira e requer rotação manual. O código já implementa fallback automático para `android` client se bgutil estiver indisponível.

---

## Verificação Pós-Config

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Logs de startup + download real | Checar logs via MCP, depois submeter beat URL real | ✓ |
| Só logs de startup | Sem download de validação (fica para Phase 10) | |
| Verificar health bgutil direto | curl interno via railway-agent antes de configurar workers | |

**User's choice:** Logs de startup + download real
**Notes:** Validação completa é parte dos success criteria desta fase (critério 3: sem erros nos logs).

---

## Aplicação de Env Vars via MCP

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Claude aplica via MCP agora | railway-agent seta variável nos dois serviços na sessão de discuss | ✓ |
| Planejar primeiro, aplicar na execução | Env vars setadas durante /gsd-execute-phase 9 | |

**User's choice:** Aplicar via MCP agora
**Notes:** Usuário quer uso integral do MCP Railway — Claude configura e analisa tudo sem abrir o dashboard. BGUTIL_BASE_URL foi setado e redeploy disparado durante esta sessão de discuss.

---

## Claude's Discretion

- O plano gerado será curto (1 plano) pois a configuração já foi aplicada; foco em verificação.
- Troubleshooting usa `mcp__railway__railway-agent` se logs mostrarem connection refused ao bgutil.

## Deferred Ideas

- **YTDLP_PO_TOKEN como fallback manual** — descartado para esta fase; bgutil é suficiente
- **Health endpoint HTTP no bgutil** — bgutil não expõe `/health`, apenas porta 4416. Fora de escopo.
