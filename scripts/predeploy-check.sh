#!/usr/bin/env bash
# Fail-closed production deploy gate for SoundGrabber.
set -euo pipefail

chmod 750 "$(realpath "$0")"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

C_RESET='\033[0m'
C_OK='\033[32m'
C_ERR='\033[31m'
C_INFO='\033[33m'

log()  { echo -e "${C_INFO}[predeploy]${C_RESET} $1"; }
ok()   { echo -e "${C_OK}[predeploy]${C_RESET} $1"; }
fail() { echo -e "${C_ERR}[predeploy]${C_RESET} $1"; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Comando obrigatorio ausente: $1"
}

require_env_value() {
    local key="$1"
    local value="${!key:-}"
    [ -n "$value" ] || fail "$key precisa estar definido no .env"
}

require_true() {
    local key="$1"
    local value="${!key:-}"
    [ "$value" = "true" ] || fail "$key=true precisa estar confirmado no .env antes do deploy"
}

reject_placeholder() {
    local key="$1"
    local value="${!key:-}"
    case "$value" in
        change-me*|correct\ horse|local-dev-*|test-*|"")
            fail "$key ainda parece placeholder/default inseguro"
            ;;
    esac
}

require_cmd git
require_cmd docker
require_cmd curl
require_cmd rg
PIP_AUDIT_BIN="${PIP_AUDIT_BIN:-pip-audit}"
if ! command -v "$PIP_AUDIT_BIN" >/dev/null 2>&1; then
    if [ -x .venv/bin/pip-audit ]; then
        PIP_AUDIT_BIN=".venv/bin/pip-audit"
    else
        fail "pip-audit ausente. Instale com: .venv/bin/python -m pip install pip-audit"
    fi
fi

[ -f .env ] || fail ".env ausente. Copie .env.example, preencha valores reais e mantenha fora do Git."

set -a
# shellcheck source=/dev/null
source .env
set +a

log "Validando worktree e arquivos versionados..."
if [ "${ALLOW_DIRTY_DEPLOY:-false}" != "true" ]; then
    git diff --quiet || fail "Worktree tem alteracoes nao commitadas. Commit/reverta antes do deploy."
    git diff --cached --quiet || fail "Index tem alteracoes staged. Commit/reverta antes do deploy."
    if [ -n "$(git ls-files --others --exclude-standard)" ]; then
        fail "Existem arquivos nao rastreados que nao estao no .gitignore. Revise antes do deploy."
    fi
fi

tracked_sensitive="$(git ls-files \
    | rg -i '(^|/)(\.env(\..*)?|cookies?[^/]*\.txt|dump\.rdb|.*\.rdb|.*\.aof|appendonlydir|.*\.pem|.*\.key|.*\.p12|.*\.pfx|.*\.sql|.*\.sqlite3?|.*\.db|.*\.bak|.*\.backup|.*\.log|.*token.*|.*secret.*|settings\.local\.json|\.data/|\.codex/|\.claude/)' \
    | rg -v '(^|/)\.env\.example$' || true)"
[ -z "$tracked_sensitive" ] || fail "Arquivos sensiveis ainda estao rastreados pelo Git. Rode git rm --cached nos artefatos antes do deploy."

high_confidence_secrets="$(git grep -n -I -E '(__Secure-3PSID[[:space:]=]+[A-Za-z0-9._-]{20,}|LOGIN_INFO[[:space:]=]+[A-Za-z0-9._-]{20,}|SIDCC[[:space:]=]+[A-Za-z0-9._-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{20,})' -- . ':!README.md' ':!.env.example' || true)"
[ -z "$high_confidence_secrets" ] || fail "Possivel segredo real encontrado em arquivo versionado. Revise com git grep antes do deploy."
ok "Repo sem artefatos sensiveis rastreados por esta checagem."

log "Validando .env de producao..."
require_env_value DEV_MODE
[ "$DEV_MODE" = "false" ] || fail "DEV_MODE precisa ser false em producao"

require_env_value REDIS_PASSWORD
reject_placeholder REDIS_PASSWORD
require_env_value REDIS_URL
case "$REDIS_URL" in
    redis://:*@*) ;;
    *) fail "REDIS_URL precisa incluir senha Redis: redis://:<senha>@redis:6379/0" ;;
esac

require_env_value ADMIN_PASSWORD
reject_placeholder ADMIN_PASSWORD
[ "${#ADMIN_PASSWORD}" -ge 16 ] || fail "ADMIN_PASSWORD deve ter pelo menos 16 caracteres"
require_env_value ADMIN_SESSION_SECRET
reject_placeholder ADMIN_SESSION_SECRET
[ "${#ADMIN_SESSION_SECRET}" -ge 32 ] || fail "ADMIN_SESSION_SECRET deve ter pelo menos 32 caracteres"

require_env_value YTDLP_CACHE_DIR
[ -d "$YTDLP_CACHE_DIR" ] || fail "YTDLP_CACHE_DIR nao existe: $YTDLP_CACHE_DIR"
cookies_file="$YTDLP_CACHE_DIR/cookies.txt"
if [ -f "$cookies_file" ]; then
    cookie_mode="$(stat -c '%a' "$cookies_file")"
    [ "$cookie_mode" = "600" ] || fail "$cookies_file deve ter permissao 600, atual=$cookie_mode"
fi

require_true ORIGIN_LOCKDOWN_ENABLED
require_true CLOUDFLARE_ACCESS_YONKOU_ENABLED
require_true SECRETS_ROTATED_AFTER_AUDIT
require_true MONITORING_ENABLED
require_true BACKUP_ENCRYPTED_OFF_GIT
ok ".env de producao validado."

log "Validando docker-compose..."
docker compose config --quiet

redis_ports="$(docker compose config | awk '/redis:/{in_redis=1} in_redis && /ports:/{print; exit} /^  [a-zA-Z0-9_-]+:/{if ($1 != "redis:") in_redis=0}' || true)"
[ -z "$redis_ports" ] || fail "Redis nao deve expor ports no docker-compose.yml"

api_loopback="$(docker compose config | rg -n '127\.0\.0\.1:8000:8000|host_ip: 127\.0\.0\.1' || true)"
[ -n "$api_loopback" ] || fail "API precisa estar publicada apenas em 127.0.0.1:8000"
ok "docker-compose validado."

log "Rodando pip-audit..."
"$PIP_AUDIT_BIN" --cache-dir /tmp/soundgrabber-pip-audit-cache -r requirements.txt
ok "pip-audit sem achados bloqueantes reportados."

log "Rodando testes de seguranca/deploy..."
if [ -x .venv/bin/python ]; then
    .venv/bin/python -m pytest tests/test_security.py tests/test_deploy_sh.py -q
else
    python -m pytest tests/test_security.py tests/test_deploy_sh.py -q
fi
ok "Testes de seguranca/deploy passaram."

ok "Predeploy liberado."
