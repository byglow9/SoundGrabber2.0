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

echo "AUTH_BOOTSTRAP: node_version=$(node --version 2>/dev/null || echo missing)"
echo "AUTH_BOOTSTRAP: ytdlp_version=$(python -m yt_dlp --version 2>/dev/null || echo missing)"
echo "AUTH_BOOTSTRAP: ytdlp_plugins=$(python - <<'PY' 2>/dev/null || echo check_failed
import pkgutil
mods = [m.name for m in pkgutil.iter_modules() if m.name == 'yt_dlp_plugins']
print('present' if mods else 'missing')
PY
)"

# Phase 10.1 D-06/D-07: bootstrap seguro dos cookies no Railway Volume.
# Usa YTDLP_CACHE_DIR como fonte unica para evitar divergencia entre env var e mount real.
CACHE_DIR="${YTDLP_CACHE_DIR:-}"
COOKIES_FILE=""

if [ -z "$CACHE_DIR" ]; then
    echo "AUTH_BOOTSTRAP: YTDLP_CACHE_DIR=missing"
else
    COOKIES_FILE="$CACHE_DIR/cookies.txt"
    echo "AUTH_BOOTSTRAP: YTDLP_CACHE_DIR=present path=$CACHE_DIR"

    if [ ! -d "$CACHE_DIR" ]; then
        echo "AUTH_BOOTSTRAP: cache_dir_missing path=$CACHE_DIR"
    else
        chmod 700 "$CACHE_DIR" || true

        if [ -n "${YTDLP_COOKIES_B64:-}" ]; then
            if printf '%s' "$YTDLP_COOKIES_B64" | base64 -d > "$COOKIES_FILE"; then
                chmod 600 "$COOKIES_FILE"
                cookie_bytes="$(wc -c < "$COOKIES_FILE" 2>/dev/null || echo 0)"
                sentinel_lines="$(grep -c "__Secure-3PSID" "$COOKIES_FILE" 2>/dev/null || echo 0)"
                echo "AUTH_BOOTSTRAP: cookies_written path=$COOKIES_FILE bytes=$cookie_bytes secure_3psid_lines=$sentinel_lines"
            else
                echo "AUTH_BOOTSTRAP: cookies_decode_failed path=$COOKIES_FILE"
                rm -f "$COOKIES_FILE"
            fi
        elif [ -f "$COOKIES_FILE" ]; then
            cookie_bytes="$(wc -c < "$COOKIES_FILE" 2>/dev/null || echo 0)"
            sentinel_lines="$(grep -c "__Secure-3PSID" "$COOKIES_FILE" 2>/dev/null || echo 0)"
            echo "AUTH_BOOTSTRAP: cookies_existing path=$COOKIES_FILE bytes=$cookie_bytes secure_3psid_lines=$sentinel_lines"
        else
            echo "AUTH_BOOTSTRAP: cookies_missing path=$COOKIES_FILE"
        fi
    fi
fi

celery -A api.tasks worker --loglevel=info --concurrency=3 &

exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --limit-concurrency 100 \
    --timeout-keep-alive 5
