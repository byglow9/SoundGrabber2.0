# Phase 8: Pipeline Code Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 08-pipeline-code-fixes
**Areas discussed:** Validação de cookies no startup, Fallback de ffprobe, nixpacks.toml escopo

---

## Validação de cookies no startup

| Option | Description | Selected |
|--------|-------------|----------|
| Lifespan da API (main.py) | Log CRITICAL visível nos logs do web service. Simples. | ✓ |
| Ambos (API + Celery worker via sinal) | Log nos dois processos, mais visível no Railway. Requer worker_ready hook. | |

**User's choice:** Lifespan da API (main.py) — simples, um único lugar
**Notes:** O worker inicia separadamente mas o log no web service é suficiente para o operador ver.

---

## Fallback de ffprobe

| Option | Description | Selected |
|--------|-------------|----------|
| shutil.which → imageio-ffmpeg fallback + warn | Fallback funciona local sem ffmpeg instalado. Log WARNING se fallback usado. | ✓ |
| Fail-fast se shutil.which retornar None | Mais rígido, quebra envs locais sem ffmpeg. | |

**User's choice:** Fallback com WARNING — garante compatibilidade local
**Notes:** Fix cobre PIPE-01 (ordem de resolução) e PIPE-02 (diretório, não binário).

---

## nixpacks.toml — escopo

| Option | Description | Selected |
|--------|-------------|----------|
| Só ffmpeg | aptPkgs = ["ffmpeg"]. Simples e suficiente. | ✓ |
| ffmpeg + Python 3.11 pin | Mais rígido, evita surpresas de mudança de Python no Railway. | |

**User's choice:** Só ffmpeg — mínimo necessário

---

## Claude's Discretion

- Ordem de waves no plan (fixes em pipeline.py → main.py → nixpacks.toml)
- Testes: Security Gate não se aplica (sem novos endpoints)

## Deferred Ideas

Nenhuma.
