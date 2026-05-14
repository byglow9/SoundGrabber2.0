# Phase 12: Pi Foundation - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Preparar o Raspberry Pi 3B do Moisés para rodar o SoundGrabber de forma autônoma e headless:
confirmar arquitetura, instalar Docker, configurar swap e memory cgroups, habilitar hardware
watchdog, instalar log2ram, e entregar um script `scripts/pi-setup.sh` executável e reproduzível.

Esta fase não toca em código da aplicação nem em Docker Compose — é exclusivamente infraestrutura do host.

</domain>

<decisions>
## Implementation Decisions

### Arquitetura do SO

- **D-01:** O Pi provavelmente está em 32-bit (armv7l). A fase procede com suporte a 32-bit — não há plano de reinstalar o OS. A confirmação de arquitetura via `uname -m` é o primeiro passo, mas o plano não é bloqueado por 32-bit. A Phase 13 (Docker Compose ARM) cuida da estratégia de compilação para arm/v7.
- **D-02:** Se o Pi retornar `aarch64` (64-bit), ótimo — Phase 13 tem caminho mais fácil. Se retornar `armv7l` (32-bit), documenta no log mas continua a Phase 12 normalmente.

### Hardware Watchdog

- **D-03:** Usar hardware watchdog do Pi (`dtparam=watchdog=on` em `/boot/firmware/config.txt` + módulo `bcm2835-wdt`). É o mais robusto para headless: reinicia mesmo se o kernel ou systemd travar. O systemd watchdog (`RuntimeWatchdogSec`) pode ser adicionado como camada extra, mas o hardware watchdog é o requisito mínimo.
- **D-04:** O timeout padrão do bcm2835 watchdog é 15s — adequado para o caso de uso.

### Swap e Memory Cgroups

- **D-05:** 2GB de swap via swapfile em `/swapfile`. Comando: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` + entrada permanente em `/etc/fstab`.
- **D-06:** Memory cgroups via `/boot/firmware/cmdline.txt` — adicionar `cgroup_enable=memory cgroup_memory=1` na linha existente (sem criar nova linha). Exige reboot para efetivar. Sem isso, `mem_limit` no docker-compose.yml é ignorado silenciosamente.

### Proteção do Cartão SD

- **D-07:** Instalar `log2ram` para mover `/var/log` para RAM e sincronizar periodicamente. Pi rodando 24/7 sem log2ram pode queimar o SD em 6-12 meses de operação contínua. Instalação via repositório oficial: `curl -L https://github.com/azlux/log2ram/archive/master.tar.gz | tar -xz && cd log2ram-master && sudo ./install.sh`.
- **D-08:** `/tmp` dos containers Docker vai ser volume tmpfs definido em docker-compose.yml (Phase 13) — não precisa configurar no host aqui.

### Script de Setup

- **D-09:** Script bash em `scripts/pi-setup.sh` commitado no repositório. O Moisés executa o script no Pi dele (acesso local ou SSH pelo próprio Tailscale dele). Script segue o padrão do projeto: `set -e`, comentários explicando o WHY de cada passo, sem `eval` de input externo.
- **D-10:** O script é idempotente onde possível — pode ser re-executado sem quebrar o sistema (ex: checar se swap já existe antes de criar).
- **D-11:** Script inclui passo de verificação final que imprime o status de cada componente: arch, Docker version, swap ativo, cgroups, watchdog status, log2ram status. Output legível para o Moisés confirmar que está tudo certo.

### Claude's Discretion

- Ordem exata dos passos no script (Docker antes ou depois do swap — planner decide o que faz mais sentido para idempotência)
- Versão específica do Docker a instalar (latest via get.docker.com ou apt — planner escolhe o mais reproduzível para armhf)
- Configuração de log2ram size (default 40MB vs ajustar — usar o default por ora)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos da Phase 12
- `.planning/REQUIREMENTS.md` §v1.3 — PI-01, PI-02, PI-03, PI-04 com critérios exatos
- `.planning/ROADMAP.md` §Phase 12 — success criteria observáveis (4 critérios)

### Padrões do Projeto (scripts)
- `start-all.sh` — padrão de script bash do projeto: `set -e`, comentários WHY, sem eval, chmod auto-aplicado
- `start.sh` — padrão de validação e saída de erros em scripts do projeto

### Pesquisa de Infraestrutura
- `.planning/research/STACK.md` — decisões de arquitetura ARM, restrições de memória do Pi 3B
- `.planning/research/PITFALLS.md` §ARM / Raspberry Pi 3B Pitfalls — P-ARM-01..08 com prevenção

### Security Gate
- `CLAUDE.md` §Security Gate — controles obrigatórios para novos scripts shell: `set -e`, chmod restritivo, sem eval de input externo

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `start.sh` (linhas 1-20) — template de script bash do projeto com `set -e`, validação de ambiente e saída com mensagem clara

### Established Patterns
- Scripts do projeto usam `set -e` na primeira linha após shebang (Security Gate — obrigatório)
- Scripts do projeto aplicam `chmod` restritivo em si mesmos (ex: `chmod 750 "$(realpath "$0")"`)
- Comentários em scripts explicam o WHY não o WHAT (padrão codebase)

### Integration Points
- `scripts/pi-setup.sh` (novo) → não conecta com código da aplicação — é executado uma vez no host pelo Moisés antes de qualquer deploy

</code_context>

<specifics>
## Specific Ideas

- Script executado pelo Moisés no Pi (não pelo Renan via SSH) — instruções em português, output amigável
- O Tailscale já está instalado no Pi e conectado — o script NÃO precisa instalar ou configurar o Tailscale
- Cloudflare Tunnel esclarecido: não expõe o IP do Pi, é conexão de saída — Moisés ciente e de acordo

</specifics>

<deferred>
## Deferred Ideas

- **Docker Compose ARM e compilação de essentia** — scope da Phase 13 (DEPLOY-04..06)
- **deploy.sh via SSH** — scope da Phase 14 (AUTH-05)
- **Cloudflare Tunnel** — scope da Phase 15 (TUNNEL-01..02)
- **Configuração do Docker com usuário não-root** — planner avalia se necessário (security best practice, mas não é requisito explícito)

</deferred>

---

*Phase: 12-Pi Foundation*
*Context gathered: 2026-05-14*
