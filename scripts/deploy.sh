#!/usr/bin/env bash
# scripts/deploy.sh — Deploy completo do SoundGrabber no servidor (notebook/nagi)
#
# Uso (da máquina local via SSH):
#   ssh glow@<tailscale-ip> 'bash ~/soundgrabber/scripts/deploy.sh'
#
# Ou diretamente no servidor:
#   bash ~/soundgrabber/scripts/deploy.sh
#
# O que faz:
#   1. git pull — atualiza o código (incluindo este script)
#   2. docker compose up --build -d — reconstrói a imagem e reinicia os containers
#   3. Aguarda o health check ficar verde
#   4. Exibe status final dos containers
#
# Referências: D-04, D-05, D-06 (14-CONTEXT.md); Security Gate (CLAUDE.md)
set -e

chmod 750 "$(realpath "$0")"

C_RESET='\033[0m'
C_OK='\033[32m'
C_ERR='\033[31m'
C_INFO='\033[33m'

log()  { echo -e "${C_INFO}[deploy]${C_RESET} $1"; }
ok()   { echo -e "${C_OK}[deploy]${C_RESET} $1"; }
fail() { echo -e "${C_ERR}[deploy]${C_RESET} $1"; exit 1; }

cd ~/soundgrabber

# 1. Atualizar código
log "Atualizando código..."
git pull

# 2. Rebuild e restart dos containers
log "Rebuilding imagem e reiniciando containers..."
sudo docker compose up --build -d

# 3. Aguardar health check
log "Aguardando aplicação ficar saudável..."
ATTEMPTS=0
MAX=30
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX" ]; then
        fail "Health check não passou após ${MAX} tentativas. Verifique: sudo docker compose logs api"
    fi
    sleep 2
done

ok "Aplicação saudável após $((ATTEMPTS * 2))s"

# 4. Status final
echo ""
sudo docker compose ps
echo ""
ok "Deploy concluído. Site disponível em http://localhost:8000"
