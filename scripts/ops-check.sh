#!/usr/bin/env bash
# Lightweight production health snapshot for the residential notebook.
set -euo pipefail

chmod 750 "$(realpath "$0")"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

C_RESET='\033[0m'
C_INFO='\033[36m'
C_OK='\033[32m'
C_WARN='\033[33m'
C_ERR='\033[31m'

info() { echo -e "${C_INFO}[ops]${C_RESET} $1"; }
ok()   { echo -e "${C_OK}[ops]${C_RESET} $1"; }
warn() { echo -e "${C_WARN}[ops]${C_RESET} $1"; }
err()  { echo -e "${C_ERR}[ops]${C_RESET} $1"; }

[ -f .env ] && set -a && source .env && set +a

info "Docker services"
docker compose ps

info "HTTP health"
if curl -fsS --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
    ok "/health OK"
else
    err "/health falhou"
fi

info "Redis queue depth"
if [ -n "${REDIS_URL:-}" ]; then
    queue_depth="$(docker compose exec -T redis sh -c 'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning llen celery' 2>/dev/null || echo unknown)"
    echo "celery_queue_depth=$queue_depth"
    if [ "$queue_depth" != "unknown" ] && [ "$queue_depth" -gt 25 ] 2>/dev/null; then
        warn "Fila acima de 25 jobs; avalie rate limit, concorrencia e abuso."
    fi
else
    warn "REDIS_URL ausente; pulando fila."
fi

info "Disk and tmp"
df -h /
docker compose exec -T api sh -c 'df -h /tmp; find /tmp -maxdepth 1 -type f -name "sg_*" | wc -l' \
    | awk 'NR==1,NR==2 {print} NR==3 {print "sg_tmp_files="$1}'

info "CPU/RAM containers"
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}' || warn "docker stats indisponivel"

info "Recent API/worker errors"
docker compose logs --since=30m api worker 2>/dev/null \
    | rg -i 'error|exception|traceback|critical|killed|oom|no space|timeout' \
    | tail -80 || true
