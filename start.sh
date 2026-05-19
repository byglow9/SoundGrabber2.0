#!/usr/bin/env bash
set -e

# SEC-FILE-02: garantir permissões 750 (rwxr-x---) a cada execução.
chmod 750 "$(realpath "$0")"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/.venv"

cd "$PROJECT_DIR"

if [ "$(id -u)" -eq 0 ]; then
    echo "[start] Nao rode este script com sudo. Use: ./start.sh"
    echo "[start] O sudo faz o pip tentar instalar pacotes no Python do sistema (PEP 668)."
    exit 1
fi

if [ ! -x "$VENV/bin/python" ]; then
    echo "[start] Virtualenv nao encontrado em $VENV"
    echo "[start] Crie com: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
    exit 1
fi

source "$VENV/bin/activate"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.env"
    set +a
fi

# Defaults locais de desenvolvimento. Produção no notebook deve definir valores próprios no .env.
export DEV_MODE="${DEV_MODE:-true}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-correct horse}"
export ADMIN_SESSION_SECRET="${ADMIN_SESSION_SECRET:-local-dev-admin-session-secret}"
export FEATURED_FALLBACK_PATH="${FEATURED_FALLBACK_PATH:-$PROJECT_DIR/.data/featured-current.json}"
export SOUNDGRABBER_HOST="${SOUNDGRABBER_HOST:-127.0.0.1}"

if [ "$DEV_MODE" != "true" ]; then
    if [ "$ADMIN_PASSWORD" = "correct horse" ] || [ -z "$ADMIN_PASSWORD" ]; then
        echo "[start] DEV_MODE=false exige ADMIN_PASSWORD forte no .env."
        exit 1
    fi
    if [ "$ADMIN_SESSION_SECRET" = "local-dev-admin-session-secret" ] || [ -z "$ADMIN_SESSION_SECRET" ]; then
        echo "[start] DEV_MODE=false exige ADMIN_SESSION_SECRET aleatorio no .env."
        exit 1
    fi
    if [ "$REDIS_URL" = "redis://localhost:6379/0" ]; then
        echo "[start] DEV_MODE=false exige REDIS_URL com senha Redis."
        exit 1
    fi
fi

# Cores e log() definidos ANTES de qualquer uso (WR-03: evita crash sob set -e)
C_RESET='\033[0m'
C_CELERY='\033[36m'   # ciano
C_SERVER='\033[32m'   # verde
C_START='\033[33m'    # amarelo

log() { echo -e "${C_START}[start]${C_RESET} $1"; }

REQ_STAMP="$VENV/.requirements.stamp"
if [ ! -f "$REQ_STAMP" ] || [ "$PROJECT_DIR/requirements.txt" -nt "$REQ_STAMP" ]; then
    log "Sincronizando dependências de requirements.txt..."
    "$VENV/bin/python" -m pip install -q -r "$PROJECT_DIR/requirements.txt"
    touch "$REQ_STAMP"
fi

REDIS_CLI_ARGS=()
if [ -n "${REDIS_URL:-}" ]; then
    REDIS_CLI_ARGS=(-u "$REDIS_URL")
fi

# Verificar dependências críticas
if ! "$VENV/bin/python" -c "import essentia.standard" &>/dev/null; then
    log "Instalando essentia (necessário para BPM/key Essentia)..."
    "$VENV/bin/python" -m pip install -q essentia==2.1b6.dev1389
fi

if ! redis-cli "${REDIS_CLI_ARGS[@]}" ping &>/dev/null; then
    log "Iniciando Redis..."
    if command -v redis-server &>/dev/null; then
        redis-server --daemonize yes --save '' --appendonly no --dir /tmp
    fi
    if ! redis-cli "${REDIS_CLI_ARGS[@]}" ping &>/dev/null; then
        echo "[start] Redis nao iniciou automaticamente."
        echo "[start] Inicie em outro terminal com: sudo service redis-server start"
        exit 1
    fi
else
    log "Redis já está rodando."
fi

pkill -f "celery -A api.tasks" 2>/dev/null || true

log "Iniciando Celery..."
"$VENV/bin/python" -m celery -A api.tasks worker --loglevel=info --concurrency=3 2>&1 \
    | sed "s/^/$(printf "${C_CELERY}")[celery]$(printf "${C_RESET}") /" &

log "Iniciando servidor em http://$SOUNDGRABBER_HOST:8000"
log "Uvicorn reload ativo: alterações em Python recarregam o servidor automaticamente."
log "Painel operador local: http://localhost:8000/yonkou (senha: ADMIN_PASSWORD do .env ou default local)."
log "Pressione Ctrl+C para encerrar tudo."

cleanup() {
    echo ""
    log "Encerrando..."
    pkill -f "celery -A api.tasks" 2>/dev/null || true
    log "Encerrado."
}
trap cleanup EXIT

"$VENV/bin/python" -m uvicorn api.main:app --host "$SOUNDGRABBER_HOST" --port 8000 --reload --limit-concurrency 100 --timeout-keep-alive 5 2>&1 \
    | sed "s/^/$(printf "${C_SERVER}")[server]$(printf "${C_RESET}") /"
