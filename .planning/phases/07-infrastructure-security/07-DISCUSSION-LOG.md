# Phase 7: Infrastructure Security - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 07-infrastructure-security
**Areas discussed:** Plataforma de deploy

---

## Plataforma de deploy

| Option | Description | Selected |
|--------|-------------|----------|
| Railway (PaaS) | HTTPS automático, Redis gerenciado, sem nginx manual | ✓ |
| VPS próprio | nginx + certbot + Let's Encrypt manual | |
| Outro PaaS (Fly.io, Render) | Alternativas ao Railway | |

**User's choice:** Railway

---

| Option | Description | Selected |
|--------|-------------|----------|
| Não tenho conta Railway | Setup completo: conta + projeto + Redis + deploy | |
| Já tenho conta Railway | Pula criação de conta | ✓ |
| Já tenho conta e projeto | Apenas variáveis e deploy | |

**User's choice:** Já tenho conta Railway criada

---

| Option | Description | Selected |
|--------|-------------|----------|
| Subdomínio Railway (*.up.railway.app) | Zero config DNS, HTTPS automático | ✓ |
| Domínio customizado | Requer DNS configurado | |

**User's choice:** Subdomínio Railway (*.up.railway.app) — sem domínio customizado nesta fase

---

| Option | Description | Selected |
|--------|-------------|----------|
| DEV_MODE=true no .env local | Skip validação Redis localmente | ✓ |
| Redis local com senha | Mais fiel ao prod, mais trabalhoso | |

**User's choice:** DEV_MODE=true localmente para bypass do Redis auth check

---

## Claude's Discretion

- Estrutura exata do railway.toml
- Como configurar o Celery worker no Railway (segundo serviço vs processo paralelo)
- HSTS middleware implementation details
- Uvicorn binding via $PORT no railway.toml

## Deferred Ideas

- Domínio customizado — pode ser adicionado depois sem nova fase
- nginx em VPS — não é mais o caminho escolhido
