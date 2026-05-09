#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

source "$VENV/bin/activate"

if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Cores
C_RESET='\033[0m'
C_CELERY='\033[36m'   # ciano
C_SERVER='\033[32m'   # verde
C_START='\033[33m'    # amarelo

log() { echo -e "${C_START}[start]${C_RESET} $1"; }

if ! redis-cli ping &>/dev/null; then
    log "Iniciando Redis..."
    sudo service redis-server start
else
    log "Redis já está rodando."
fi

pkill -f "celery -A api.tasks" 2>/dev/null || true

log "Iniciando Celery..."
celery -A api.tasks worker --loglevel=info --concurrency=3 2>&1 \
    | sed "s/^/$(printf "${C_CELERY}")[celery]$(printf "${C_RESET}") /" &

log "Iniciando servidor em http://localhost:8000"
log "Pressione Ctrl+C para encerrar tudo."

cleanup() {
    echo ""
    log "Encerrando..."
    pkill -f "celery -A api.tasks" 2>/dev/null || true
    log "Encerrado."
}
trap cleanup EXIT

uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 2>&1 \
    | sed "s/^/$(printf "${C_SERVER}")[server]$(printf "${C_RESET}") /"
