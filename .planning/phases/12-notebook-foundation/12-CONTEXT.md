# Phase 12: Notebook Foundation - Context

**Gathered:** 2026-05-14
**Atualizado:** 2026-05-14 — migrado de Raspberry Pi 3B para notebook HP
**Status:** Ready for planning

<domain>
## Phase Boundary

Preparar o notebook HP do Moisés para rodar o SoundGrabber de forma autônoma e headless com Ubuntu
Server 24.04 LTS: confirmar arquitetura x86_64, instalar Docker via apt repo oficial, configurar
swap e cgroups v2, habilitar systemd watchdog, prevenir sleep/hibernate com tampa fechada, e entregar
um script `scripts/notebook-setup.sh` executável e reproduzível.

Esta fase não toca em código da aplicação nem em Docker Compose — é exclusivamente infraestrutura do host.

**Hardware:** Notebook HP (modelo a confirmar), ~4GB RAM, 2 núcleos x86_64, HDD
**OS alvo:** Ubuntu Server 24.04 LTS (fresh install)

</domain>

<decisions>
## Implementation Decisions

### Hardware e SO

- **D-01:** Usar Ubuntu Server 24.04 LTS — sem GUI, suporte até 2029, Docker nativo, cgroups v2 ativo
  por padrão, lightweight (~400MB RAM idle). Adequado para 4GB RAM + 2 cores + HDD.
- **D-02:** Arquitetura é x86_64. Não há verificação de 32-bit necessária — Ubuntu Server 24.04 só
  oferece amd64. `uname -m` deve retornar `x86_64` sempre.

### Prevenção de Sleep/Hibernate (crítico para notebook servidor)

- **D-03:** O risco mais específico de um notebook como servidor é sumir quando a tampa fecha ou o
  sistema fica idle. Dois arquivos de configuração via drop-ins systemd evitam isso:
  - `/etc/systemd/logind.conf.d/nosleep.conf`: HandleLidSwitch=ignore,
    HandleLidSwitchExternalPower=ignore, HandleSuspendKey=ignore, HandleHibernateKey=ignore,
    IdleAction=ignore, IdleActionSec=0
  - `/etc/systemd/sleep.conf.d/nosleep.conf`: AllowSuspend=no, AllowHibernation=no,
    AllowSuspendThenHibernate=no, AllowHybridSleep=no
  - `systemctl daemon-reload` após criar os arquivos
  - Ambos drop-ins criados de forma idempotente (verificar existência antes de criar)

### Watchdog

- **D-04:** Usar systemd watchdog via drop-in `/etc/systemd/system.conf.d/10-watchdog.conf` com
  `RuntimeWatchdogSec=15` e `ShutdownWatchdogSec=2min`. Ubuntu 24.04 suporta isso nativamente.
  O hardware watchdog bcm2835-wdt era específico do Raspberry Pi — não existe em notebook HP.
  Para notebooks: o kernel Linux expõe `/dev/watchdog` via módulo `iTCO_wdt` (Intel) ou
  `sp5100_tco` (AMD). O systemd faz feed automático via `/dev/watchdog` se disponível.

### Docker

- **D-05:** Instalar Docker via apt repo oficial da Docker (não via snap, não via convenience script
  `get.docker.com` — o convenience script tem risco de supply chain sem pinagem de versão).
  Passos: add GPG key + repo, apt install `docker-ce docker-ce-cli containerd.io
  docker-buildx-plugin docker-compose-plugin`.
- **D-06:** Adicionar o usuário operador ao grupo `docker` usando `${SUDO_USER}` (não hardcode).
  Aviso explícito no script que o grupo docker equivale a root.

### Swap

- **D-07:** 4GB de swap via swapfile em `/swapfile`. Com 4GB de RAM, um swap de 4GB é seguro para
  operação normal. HDD é mais lento que SSD para swap mas adequado para workload do SoundGrabber
  (swap raro em operação normal).
- **D-08:** Usar `fallocate -l 4G` com `dd` como fallback caso `fallocate` falhe (alguns filesystems
  não suportam fallocate). Idempotente: verificar `[ -f /swapfile ]` antes de criar.

### Cgroups v2

- **D-09:** Ubuntu Server 24.04 LTS usa cgroups v2 por padrão — sem necessidade de modificar
  cmdline.txt ou kernel parameters. Apenas verificar que `/sys/fs/cgroup/cgroup.controllers`
  contém `memory`. Se por algum motivo não estiver ativo, imprimir aviso claro.

### Script de Setup

- **D-10:** Script bash em `scripts/notebook-setup.sh` commitado no repositório. Segue o Security
  Gate do projeto: `set -e`, comentários WHY, sem `eval` de input externo.
- **D-11:** Script é idempotente — pode ser re-executado sem quebrar o sistema.
- **D-12:** Script inclui verificação final com status de todos os componentes: arch, Docker, swap,
  cgroups v2, watchdog, lid-close config. Output amigável para o Moisés confirmar.

### O que NÃO faz o script

- Não instala Tailscale (já deve estar instalado e configurado pelo Moisés antes)
- Não instala Cloudflare Tunnel (Phase 15)
- Não instala Docker Compose stacks da aplicação (Phase 13)
- Não instala log2ram — notebook usa HDD, não SD card; risco de desgaste diferente e não relevante
- Não configura UFW além do essencial — deixado para a fase de hardening de infraestrutura

</decisions>

<canonical_refs>
## Canonical References

### Requisitos da Phase 12
- `.planning/REQUIREMENTS.md` §v1.3 — SVR-01, SVR-02, SVR-03, SVR-04 com critérios exatos
- `.planning/ROADMAP.md` §Phase 12 — success criteria observáveis (4 critérios)

### Padrões do Projeto (scripts)
- `start-all.sh` — padrão de script bash do projeto: `set -e`, comentários WHY, sem eval, chmod auto-aplicado
- `start.sh` — padrão de validação e saída de erros em scripts do projeto

### Security Gate
- `CLAUDE.md` §Security Gate — controles obrigatórios para novos scripts shell: `set -e`, chmod restritivo, sem eval de input externo

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `start.sh` (linhas 1-20) — template de script bash do projeto com `set -e`, validação e saída com mensagem clara

### Established Patterns
- Scripts do projeto usam `set -e` na primeira linha após shebang (Security Gate — obrigatório)
- Scripts do projeto aplicam `chmod` restritivo em si mesmos (ex: `chmod 750 "$(realpath "$0")"`)
- Comentários em scripts explicam o WHY não o WHAT (padrão codebase)

### Integration Points
- `scripts/notebook-setup.sh` (novo) — executado uma vez no host pelo Moisés antes de qualquer deploy

</code_context>

<specifics>
## Specific Ideas

- Script executado pelo Moisés no notebook com `sudo bash notebook-setup.sh`
- O Tailscale já deve estar instalado e conectado antes de executar o script
- Reboot necessário após configurar watchdog e drop-ins de sleep — script informa explicitamente

</specifics>

<deferred>
## Deferred Ideas

- **Docker Compose e build da imagem** — scope da Phase 13 (DEPLOY-04..06)
- **deploy.sh via SSH** — scope da Phase 14 (AUTH-05)
- **Cloudflare Tunnel** — scope da Phase 15 (TUNNEL-01..02)
- **Configuração SSH hardening (key-only)** — boas práticas, mas não é requisito explícito da Phase 12

</deferred>

---

*Phase: 12-Notebook Foundation*
*Context gathered: 2026-05-14 (migrado de Pi 3B para HP Notebook)*
