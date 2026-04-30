# Phase 2: API Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — este log preserva as alternativas consideradas.

**Date:** 2026-04-30
**Phase:** 02-api-layer
**Areas discussed:** Ciclo de vida do WAV, Estrutura do projeto, Contrato de falha, Ambiente de dev

---

## Ciclo de vida do WAV

| Option | Description | Selected |
|--------|-------------|----------|
| TTL fixo de 15 min | Arquivo fica disponível por 15 min após job terminar; sweeper deleta ao expirar | ✓ |
| Delete após primeiro download | GET /files/{id} deleta WAV imediatamente após stream terminar | |
| TTL + delete após download | Combina os dois: deleta no primeiro download OU após 15 min | |

**User's choice:** TTL fixo de 15 minutos

---

| Option | Description | Selected |
|--------|-------------|----------|
| Mesmo TTL (15 min) para ambos | Job expira do Redis junto com o WAV; GET /jobs/{id} após 15 min retorna 404 | ✓ |
| Job fica mais tempo que o WAV | Metadados ficam mais tempo; GET /jobs/{id} pode retornar status 'expired' | |

**User's choice:** Mesmo TTL de 15 min para WAV e metadados do job no Redis

---

## Estrutura do projeto

| Option | Description | Selected |
|--------|-------------|----------|
| Pasta api/ com módulos | api/main.py + api/tasks.py + api/config.py | ✓ |
| Módulo único app.py | Tudo em um único arquivo na raiz | |

**User's choice:** Pasta `api/` com separação de módulos

---

| Option | Description | Selected |
|--------|-------------|----------|
| Adicionar no mesmo requirements.txt | fastapi, uvicorn, celery[redis], redis no arquivo existente | ✓ |
| requirements-api.txt separado | Dependências da API em arquivo separado | |

**User's choice:** Mesmo requirements.txt

---

## Contrato de falha

| Option | Description | Selected |
|--------|-------------|----------|
| Mensagem sanitizada | status: failed + error: mensagem amigável | ✓ |
| Mensagem original + sanitizada | error (amigável) + error_detail (raw) | |

**User's choice:** Mensagem sanitizada — error amigável, sem expor internals do yt-dlp

---

| Option | Description | Selected |
|--------|-------------|----------|
| Sim — campo error_type | 'download_error' \| 'validation_error' \| 'internal_error' | ✓ |
| Não — só mensagem de texto | Fase 4 parseia texto se precisar diferenciar | |

**User's choice:** Sim, campo error_type para distinguir categorias sem parsear texto

---

## Ambiente de dev

| Option | Description | Selected |
|--------|-------------|----------|
| Docker Compose | docker-compose.yml com redis + api + worker | |
| Setup manual no README | apt install redis, dois terminais separados | ✓ |

**User's choice:** Setup manual — Docker é lento para buildar, reiniciar e ocupa armazenamento. README documenta comandos para Redis local, worker e uvicorn.

---

## Claude's Discretion

- Número exato de workers Celery (STATE.md sugere cap 3 — planner confirma)
- Redis connection pool settings
- Versões exatas dos novos pacotes

## Deferred Ideas

Nenhuma.
