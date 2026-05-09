#!/usr/bin/env bash
set -e

# SEC-FILE-02: garantir permissões 750 (rwxr-x---) a cada execução.
chmod 750 "$(realpath "$0")"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

source "$VENV/bin/activate"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.env"
    set +a
fi

# Verificar dependências críticas
if ! python -c "import essentia.standard" &>/dev/null; then
    log "Instalando essentia (necessário para BPM/key Essentia)..."
    pip install -q essentia==2.1b6.dev1389
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

uvicorn api.main:app --host 0.0.0.0 --port 8000 --limit-concurrency 100 --timeout-keep-alive 5 2>&1 \
    | sed "s/^/$(printf "${C_SERVER}")[server]$(printf "${C_RESET}") /"
