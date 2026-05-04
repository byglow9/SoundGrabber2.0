# Phase 3: Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 03-hardening
**Areas discussed:** Rate limiting, Sweeper + arquivos parciais, Formato dos erros síncronos, Limites ajustáveis

---

## Rate Limiting

| Option | Description | Selected |
|--------|-------------|----------|
| slowapi | Biblioteca nativa FastAPI, decorator direto, uma dependência nova | ✓ |
| Redis counter custom | INCR + EXPIRE manual, sem dep nova, ~20 linhas extras | |
| Middleware FastAPI | Middleware genérico, acesso só ao request | |

**User's choice:** slowapi

---

| Option | Description | Selected |
|--------|-------------|----------|
| Só POST /jobs | Abuse surface é o submit; GET endpoints são leves | ✓ |
| Todos os endpoints | Defesa em profundidade, mas bloqueia polling legítimo | |

**User's choice:** Só POST /jobs

---

| Option | Description | Selected |
|--------|-------------|----------|
| Sim, incluir Retry-After | RFC 9110 standard, frontend sabe quando tentar de novo | ✓ |
| Não, só 429 com mensagem | Mais simples | |

**User's choice:** Sim, incluir Retry-After

---

## Sweeper + Arquivos Parciais

| Option | Description | Selected |
|--------|-------------|----------|
| Ampliar o sweeper | Adicionar .part e .ytdl ao glob, com mesmo critério de TTL | ✓ |
| TTL do WAV basta | yt-dlp limpa normalmente; SIGKILL raro | |
| try/finally no task | Mais preciso mas não cobre SIGKILL | |

**User's choice:** Ampliar o sweeper

---

## Formato dos Erros Síncronos

| Option | Description | Selected |
|--------|-------------|----------|
| Normalizar 422 | Exception handler converte Pydantic para {error, error_type} | ✓ |
| Manter Pydantic padrão | Erros síncronos e assíncronos podem ter formatos diferentes | |

**User's choice:** Normalizar

---

## Limites Ajustáveis

| Option | Description | Selected |
|--------|-------------|----------|
| Env var | RATE_LIMIT_PER_MINUTE, consistente com padrão 12-factor | ✓ |
| Hardcoded | Mais simples, mudança via commit | |

**User's choice:** Env var

---

| Option | Description | Selected |
|--------|-------------|----------|
| Não por agora | Só 3/min cobre o success criteria | ✓ |
| Sim, 3/min + 20/hr | Defesa em camadas, slowapi suporta múltiplos limites | |

**User's choice:** Não por agora (só 3/min)

---

## Claude's Discretion

- Estratégia de identificação de IP (X-Forwarded-For vs client.host)
- Storage backend do slowapi (in-memory vs Redis)
- Mensagem exata do 429 (português vs inglês)

## Deferred Ideas

- Limite por hora (20/hr) — adiado para pós-lançamento
