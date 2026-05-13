#!/usr/bin/env bash
# start-all.sh — Railway single-container startup (Uvicorn + Celery Worker)
#
# Inicia Celery Worker em background e Uvicorn em foreground.
# Railway monitora o processo foreground (Uvicorn, PID 1 após exec) para health checks.
# SIGTERM do Railway chega diretamente ao Uvicorn via exec — graceful shutdown funciona.
#
# Por que exec: sem exec, o bash seria PID 1 e precisaria repassar sinais manualmente.
# Com exec, uvicorn substitui o processo bash e recebe SIGTERM diretamente.
#
# Por que & (background) para Celery: Railway monitora apenas o processo foreground.
# Celery recebe SIGTERM do kernel quando o grupo de processos termina (task_acks_late=True
# já configurado em api/tasks.py — Celery termina após completar o job atual).
#
# Substitui o padrão de dois containers separados (railway.toml + railway-worker.toml).
# Referência: D-01 de .planning/phases/10-failure-hardening-and-e2e-validation/10-CONTEXT.md
set -e

# Phase 10.1 D-06: garantir permissoes do Railway Volume antes de qualquer worker iniciar.
# Volume montado em runtime (nao em build) — chmod precisa ser no startup.
# || true evita que set -e aborte se chmod falhar por permissao herdada do Railway.
if [ -d /data/yt-dlp-cache ]; then
    chmod 700 /data/yt-dlp-cache || true
fi

celery -A api.tasks worker --loglevel=info --concurrency=3 &

exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --limit-concurrency 100 \
    --timeout-keep-alive 5
