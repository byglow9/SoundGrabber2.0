#!/usr/bin/env bash
set -e

# SEC-SCRIPT: permissões restritivas auto-aplicadas a cada execução (Security Gate).
chmod 750 "$(realpath "$0")"

# Executar como root — Docker install, systemd drop-ins e swap exigem root.
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] Execute como root: sudo bash scripts/notebook-setup.sh"
    exit 1
fi

# Funções de log com cores ANSI simples
C_RESET='\033[0m'
C_INFO='\033[36m'
C_OK='\033[32m'
C_WARN='\033[33m'
C_ERR='\033[31m'

log_info()  { echo -e "${C_INFO}[INFO]${C_RESET}  $*"; }
log_ok()    { echo -e "${C_OK}[OK]${C_RESET}    $*"; }
log_warn()  { echo -e "${C_WARN}[WARN]${C_RESET}  $*"; }
log_error() { echo -e "${C_ERR}[ERROR]${C_RESET} $*"; }

# Utilitários idempotentes
file_contains() { grep -qF "$2" "$1" 2>/dev/null; }
ensure_dir()    { [ -d "$1" ] || mkdir -p "$1"; }
command_exists(){ command -v "$1" &>/dev/null; }

# ========================================
# --- [1] Preflight (read-only) ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — PREFLIGHT"
echo "========================================"

ARCH=$(uname -m)
log_info "Arquitetura: $ARCH"
if [ "$ARCH" != "x86_64" ]; then
    log_warn "Arquitetura não é x86_64 — Ubuntu Server 24.04 só suporta amd64. Continuando para diagnóstico."
fi

OS_VERSION=$(lsb_release -rs 2>/dev/null || echo "desconhecido")
log_info "Ubuntu Server: $OS_VERSION"
# Script testado em 24.04 LTS e 26.04 LTS — avisa apenas para versões mais antigas.
MAJOR=$(echo "$OS_VERSION" | cut -d. -f1)
if [ "$MAJOR" -lt 24 ] 2>/dev/null; then
    log_warn "Versão $OS_VERSION é mais antiga que 24.04 — algumas seções podem precisar de ajuste."
fi

DISK_FREE=$(df -h / | awk 'NR==2 {print $4}')
log_info "Espaço disponível em /: $DISK_FREE"
# Aviso se provavelmente < 10GB (comparação aproximada)
DISK_FREE_GB=$(df / | awk 'NR==2 {print int($4/1024/1024)}')
if [ "$DISK_FREE_GB" -lt 10 ]; then
    log_warn "Menos de 10GB disponíveis em / ($DISK_FREE). Docker images podem não caber."
fi

log_info "RAM disponível:"
free -h

log_info "CPU:"
lscpu | head -20

log_info "Discos (lsblk):"
lsblk

log_info "Swap atual:"
swapon --show || echo "(nenhum swap ativo)"

# ========================================
# --- [2] Prevenção de sleep/hibernate ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — [2] SLEEP PREVENTION"
echo "========================================"
log_info "Configurando drop-ins systemd para prevenir sleep/hibernate com tampa fechada..."

# Notebook como servidor não pode sumir quando a tampa fecha ou o sistema fica idle.
ensure_dir /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/nosleep.conf << 'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
IdleAction=ignore
IdleActionSec=0
EOF
log_ok "Criado /etc/systemd/logind.conf.d/nosleep.conf"

ensure_dir /etc/systemd/sleep.conf.d
cat > /etc/systemd/sleep.conf.d/nosleep.conf << 'EOF'
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
EOF
log_ok "Criado /etc/systemd/sleep.conf.d/nosleep.conf"

systemctl daemon-reload
log_ok "systemctl daemon-reload executado"
# Não reiniciamos systemd-logind durante sessão SSH ativa — reboot aplica de forma previsível.
log_info "Reboot ao final aplicará as configurações de lid-close."

# ========================================
# --- [3] Docker via apt repo oficial ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — [3] DOCKER"
echo "========================================"
log_info "Instalando Docker via apt repo oficial da Docker (apt repo, não convenience script)."

apt-get update -qq
apt-get install -y ca-certificates curl gnupg lsb-release

# Remover pacotes Docker conflitantes recomendados pela documentação oficial.
# '|| true' tolera ausência dos pacotes (idempotente).
apt-get remove -y docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc 2>/dev/null || true
log_ok "Pacotes conflitantes removidos (ou ausentes)."

# Adicionar chave GPG oficial da Docker.
ensure_dir /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    log_ok "Chave GPG Docker instalada em /etc/apt/keyrings/docker.asc"
else
    log_info "Chave GPG Docker já existe — pulando download."
fi

# Detectar arquitetura e codename.
DOCKER_ARCH=$(dpkg --print-architecture)
. /etc/os-release

# Verificar que é Ubuntu LTS — script foi testado em 24.04 e 26.04.
# Aborta apenas se não for Ubuntu (VERSION_ID presente em /etc/os-release).
if [ -z "$VERSION_CODENAME" ]; then
    log_error "VERSION_CODENAME não detectado — sistema pode não ser Ubuntu. Abortando."
    exit 1
fi
if [ "$ID" != "ubuntu" ]; then
    log_error "Sistema não é Ubuntu (ID=$ID). Abortando."
    exit 1
fi
log_info "Ubuntu detectado: $PRETTY_NAME (codename: $VERSION_CODENAME)"

# Aviso se for versão muito antiga (< 24.04) — não aborta, mas alerta.
MAJOR_VER=$(echo "$VERSION_ID" | cut -d. -f1)
if [ "$MAJOR_VER" -lt 24 ]; then
    log_warn "Ubuntu $VERSION_ID é mais antigo que 24.04 — cgroups v2 e Docker podem não se comportar como esperado."
fi

# Adicionar repositório Docker.
if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
    echo "deb [arch=${DOCKER_ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    log_ok "Repositório Docker adicionado em /etc/apt/sources.list.d/docker.list"
else
    log_info "Repositório Docker já configurado — pulando."
fi

apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
log_ok "Docker instalado e serviço habilitado."

# Não adicionar usuário ao grupo docker — grupo docker equivale a root.
# Operação futura usa 'sudo docker' ou serviços systemd root-owned.
log_warn "Usuário NÃO foi adicionado ao grupo 'docker'. Use 'sudo docker' para operar Docker."

# ========================================
# --- [4] Firewall UFW básico ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — [4] FIREWALL UFW"
echo "========================================"
# Proteção básica de host. Nota: UFW não cobre portas publicadas pelo Docker;
# Phase 15 deve considerar a cadeia DOCKER-USER para exposição pública.

apt-get install -y ufw

ufw default deny incoming
ufw default allow outgoing

# Garantir acesso SSH antes de ativar o firewall para evitar lockout.
ufw allow 22/tcp comment 'SSH admin access'
log_ok "Regra SSH (22/tcp) adicionada."

# Permitir Tailscale se a interface já existir.
if ip link show tailscale0 &>/dev/null; then
    ufw allow in on tailscale0 comment 'Tailscale private access'
    log_ok "Regra Tailscale (tailscale0) adicionada."
else
    log_info "Interface tailscale0 não encontrada — regra Tailscale não adicionada agora."
    log_info "Se Tailscale for instalado depois, execute: sudo ufw allow in on tailscale0 comment 'Tailscale private access'"
fi

# Ativar UFW após garantir rota administrativa segura.
ufw --force enable
log_ok "UFW ativado com default deny incoming."

# ========================================
# --- [5] Swap 4GB ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — [5] SWAP 4GB"
echo "========================================"
# 4GB de swap com fallocate; fallback dd para filesystems sem suporte a fallocate.

if [ ! -f /swapfile ]; then
    log_info "Criando /swapfile (4GB)..."
    if fallocate -l 4G /swapfile 2>/dev/null; then
        log_ok "Swap criado com fallocate."
    else
        log_warn "fallocate falhou — usando dd como fallback (pode demorar)."
        dd if=/dev/zero of=/swapfile bs=1M count=4096 status=progress
    fi
else
    log_info "/swapfile já existe — pulando criação."
fi

# Permissões restritas: swap é lido pelo kernel, nenhum outro usuário deve ter acesso.
chmod 600 /swapfile

# Formatar como área de swap apenas se ainda não estiver formatada.
if ! blkid /swapfile 2>/dev/null | grep -q "swap"; then
    mkswap /swapfile
    log_ok "Swap formatado com mkswap."
else
    log_info "/swapfile já formatado como swap."
fi

# Ativar swap se ainda não estiver ativo.
if ! swapon --show | grep -q /swapfile; then
    swapon /swapfile
    log_ok "Swap ativado."
else
    log_info "Swap já está ativo."
fi

# Persistência no fstab — apenas se entrada ainda não existir.
if ! file_contains /etc/fstab "/swapfile"; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    log_ok "Entrada /swapfile adicionada ao /etc/fstab."
else
    log_info "Entrada /swapfile já existe no /etc/fstab."
fi

# Reduzir swappiness para 10 — notebook com HDD: swap só em último caso.
sysctl vm.swappiness=10 > /dev/null
ensure_dir /etc/sysctl.d
if ! file_contains /etc/sysctl.d/99-swappiness.conf "vm.swappiness"; then
    echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
    log_ok "vm.swappiness=10 persistido em /etc/sysctl.d/99-swappiness.conf."
else
    log_info "vm.swappiness já configurado."
fi

# ========================================
# --- [6] Cgroups v2 (verificação) ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — [6] CGROUPS V2"
echo "========================================"
# Ubuntu Server 24.04 usa cgroups v2 por padrão — sem modificação necessária.
# Só verificamos que o subsistema memory está disponível.

if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
    CGROUP_CONTROLLERS=$(cat /sys/fs/cgroup/cgroup.controllers)
    log_info "cgroup.controllers: $CGROUP_CONTROLLERS"
    if echo "$CGROUP_CONTROLLERS" | grep -q "memory"; then
        log_ok "Cgroups v2 ativo com subsistema memory."
    else
        log_warn "Subsistema 'memory' não encontrado em cgroup.controllers — incomum no Ubuntu 24.04."
    fi
else
    log_warn "/sys/fs/cgroup/cgroup.controllers não encontrado — cgroups v2 pode não estar ativo."
fi

# ========================================
# --- [7] Watchdog systemd ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — [7] WATCHDOG"
echo "========================================"
# Systemd watchdog protege contra travamentos permanentes do sistema.
# O kernel expõe /dev/watchdog via módulo iTCO_wdt (Intel) ou sp5100_tco (AMD).
# systemd faz feed automático via /dev/watchdog se disponível; não exigimos o módulo aqui.

ensure_dir /etc/systemd/system.conf.d
cat > /etc/systemd/system.conf.d/10-watchdog.conf << 'EOF'
[Manager]
RuntimeWatchdogSec=15
ShutdownWatchdogSec=2min
EOF
log_ok "Criado /etc/systemd/system.conf.d/10-watchdog.conf (RuntimeWatchdogSec=15)."

systemctl daemon-reload
log_ok "systemctl daemon-reload executado."
log_info "Watchdog hardware (/dev/watchdog) depende de suporte do kernel/ACPI — verificado no Plan 02."

# ========================================
# --- [8] Verificação final ---
# ========================================
echo ""
echo "========================================"
echo "  NOTEBOOK SETUP — VERIFICAÇÃO FINAL"
echo "========================================"

ARCH_OUT=$(uname -m)
OS_OUT=$(lsb_release -ds 2>/dev/null || echo "N/A")
CPU_OUT=$(lscpu | grep "^Model name" | head -1 | cut -d: -f2 | xargs || echo "N/A")
CORES_OUT=$(lscpu | grep "^CPU(s):" | head -1 | awk '{print $2}' || echo "N/A")
RAM_OUT=$(free -h | awk '/^Mem:/{print $2}' || echo "N/A")
DISK_OUT=$(lsblk -d -o NAME,SIZE,TYPE | grep disk | head -3 | tr '\n' ' ' || echo "N/A")

DOCKER_VER=$(docker --version 2>/dev/null || echo "ERRO")
UFW_STATUS=$(ufw status | head -1 || echo "ERRO")
SWAP_STATUS=$(swapon --show --noheadings 2>/dev/null || echo "(nenhum)")
CGROUP_VER=$(cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null | grep -o "memory" || echo "N/A")
LID_STATUS=$(systemctl show logind 2>/dev/null | grep HandleLidSwitch | head -1 || echo "ERRO")
WATCHDOG_CFG=$(grep RuntimeWatchdogSec /etc/systemd/system.conf.d/10-watchdog.conf 2>/dev/null || echo "AUSENTE")

echo ""
echo "========================================"
echo "  RESULTADO"
echo "========================================"
echo "Arquitetura:    $ARCH_OUT"
echo "OS:             $OS_OUT"
echo "CPU:            $CPU_OUT ($CORES_OUT cores)"
echo "RAM:            $RAM_OUT"
echo "Disco:          $DISK_OUT"
echo "Docker:         $DOCKER_VER"
echo "Docker run:     validar com 'sudo docker run --rm hello-world' após reboot"
echo "UFW:            $UFW_STATUS"
echo "Swap:           $SWAP_STATUS"
echo "Cgroups v2:     memory=$CGROUP_VER"
echo "Lid Switch:     $LID_STATUS"
echo "Watchdog conf:  $WATCHDOG_CFG"
echo "========================================"
echo ""
echo "PRÓXIMO PASSO: sudo reboot"
echo "Após reboot, conectar via Tailscale SSH e reportar outputs ao Claude:"
echo "  - Plan 02 (checkpoint humano) documenta SVR-01, SVR-02 e SVR-03"
echo "========================================"
