# Phase 12: Notebook Foundation - Context

**Gathered:** 2026-05-14
**Atualizado:** 2026-05-14 — hardware confirmado pelo Moisés
**Status:** Executing (Plan 01 done, Plan 02 aguardando operador)

<domain>
## Phase Boundary

Preparar o notebook HP do Moisés para rodar o SoundGrabber de forma autônoma e headless com Ubuntu
Server 24.04 LTS: confirmar arquitetura x86_64, instalar Docker via apt repo oficial, configurar
swap e cgroups v2, aplicar firewall básico seguro, habilitar systemd watchdog, prevenir
sleep/hibernate com tampa fechada, e entregar um script `scripts/notebook-setup.sh` executável e
reproduzível.

Esta fase não toca em código da aplicação nem em Docker Compose — é exclusivamente infraestrutura do host.

**Hardware (confirmado 2026-05-14):**
- CPU: Intel Core i5-3210M @ 2.50GHz — Ivy Bridge, 2 núcleos físicos / 4 threads (HT), 3MB L3 cache
- Chipset: Intel Panther Point → módulo `iTCO_wdt` disponível para watchdog de hardware
- RAM: 4GB DDR3
- Armazenamento: 700GB HDD
- GPU: Intel HD Graphics 4000 (32MB VRAM — irrelevante para servidor headless)

**OS alvo:** Ubuntu Server 24.04 LTS (fresh install)

</domain>

<decisions>
## Implementation Decisions

### Hardware e SO

- **D-01:** Usar Ubuntu Server 24.04 LTS — sem GUI, suporte até 2029, Docker nativo, cgroups v2 ativo
  por padrão, lightweight (~400MB RAM idle). Adequado para hardware confirmado: i5-3210M (Ivy Bridge,
  2c/4t), 4GB DDR3, HDD 700GB. RAM livre em idle (~3.6GB) é suficiente para api + worker + Redis.
- **D-02:** Arquitetura é x86_64 (confirmada — i5-3210M é amd64). `uname -m` retornará `x86_64`.

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
- **D-03a:** Operar com tampa fechada é gate rígido da Phase 12: após reboot, Moisés deve fechar a
  tampa por 2-5 minutos e reconectar via Tailscale/SSH. Se o notebook sumir da rede, a fase não
  passa, exceto se houver limitação comprovada de hardware/BIOS/ACPI. Nesse caso, operar com a tampa
  aberta ou semiaberta é aceito, mas a limitação deve ficar documentada em `scripts/12-SETUP-LOG.md`.

### Watchdog

- **D-04:** Usar systemd watchdog via drop-in `/etc/systemd/system.conf.d/10-watchdog.conf` com
  `RuntimeWatchdogSec=15` e `ShutdownWatchdogSec=2min`. Ubuntu 24.04 suporta isso nativamente.
  O hardware watchdog bcm2835-wdt era específico do Raspberry Pi — não existe em notebook HP.
  Para o i5-3210M (Panther Point): o kernel Linux expõe `/dev/watchdog` via módulo `iTCO_wdt`
  (Intel Panther Point é suportado). O systemd faz feed automático via `/dev/watchdog` se disponível.
- **D-04a:** Watchdog ativo não é bloqueador da Phase 12. O script deve configurar o drop-in, e o
  Plan 02 deve validar `systemctl show -p RuntimeWatchdogUSec` e `ls -l /dev/watchdog* || true`.
  Se o valor for `0` ou não houver `/dev/watchdog`, registrar como limitação de hardware e seguir.
  Só bloqueia se a configuração causar falha de boot, instabilidade ou erro de systemd.

### Docker

- **D-05:** Instalar Docker via apt repo oficial da Docker (não via snap, não via convenience script
  `get.docker.com` — o convenience script tem risco de supply chain sem pinagem de versão).
  Passos: add GPG key + repo, apt install `docker-ce docker-ce-cli containerd.io
  docker-buildx-plugin docker-compose-plugin`. Remover previamente pacotes conflitantes conforme
  recomendação oficial da Docker (`docker.io`, `docker-compose`, `containerd`, `runc`, etc.).
- **D-06:** Segurança acima de conveniência: não adicionar o usuário operador ao grupo `docker`.
  Grupo `docker` equivale a root. Operação e planos futuros devem usar `sudo docker` /
  `sudo docker compose` ou serviços systemd root-owned. Liberar grupo `docker` só pode ocorrer por
  decisão explícita futura.

### Firewall e exposição

- **D-06a:** Phase 12 aplica firewall básico de host com UFW: default deny incoming, allow outgoing,
  permitir SSH e permitir tráfego em `tailscale0` quando a interface existir. O script só deve ativar
  UFW depois de garantir uma rota de administração segura para evitar lockout.
- **D-06b:** Produção deve seguir defesa em camadas: sem port-forward residencial; administração via
  Tailscale; exposição pública via Cloudflare Tunnel na Phase 15. Se Docker Compose publicar portas
  em fases futuras, hardening deve considerar a cadeia `DOCKER-USER`; UFW sozinho não deve ser
  tratado como prova de isolamento de containers.

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
  cgroups v2, watchdog, lid-close config e UFW. Output amigável para o Moisés confirmar.

### Decisões encaminhadas para Phase 13/14

- **D-13:** Docker Compose continua sendo a melhor opção para produção local, mas com hardening:
  Docker rootful operado via `sudo`, sem usuário no grupo `docker`, sem containers privileged, sem
  `network_mode: host`, sem portas públicas diretas, limites de memória/CPU e Redis apenas na rede
  interna do Compose.
- **D-14:** Concurrency em produção validada por rampa. Hardware confirmado (i5-3210M, 4GB DDR3,
  HDD): baseline Phase 13 = Celery `--concurrency=1`. Testar 2 jobs simultâneos; promover para
  `concurrency=2` só se sem OOM, swap pesada ou perda de responsividade. HDD (não SSD) limita
  throughput de swap e I/O — testar com cautela. 4 threads HT disponíveis mas RAM é o gargalo real.
- **D-15:** Essentia é requisito obrigatório do produto. Phase 13 deve bloquear se
  `import essentia.standard` ou `analyze_audio()` no container falhar. Não aceitar fallback silencioso
  sem Essentia.
- **D-16:** Node.js >= 20 é dependência obrigatória do container da aplicação para yt-dlp/bgutil. Não
  instalar Node no host na Phase 12.
- **D-17:** Phase 13 deve migrar diretório de WAV para caminho explícito compartilhado:
  `SG_TMP_DIR=/data/tmp`, com fallback local para `/tmp`. API, worker e sweeper devem usar o mesmo
  diretório.
- **D-18:** YouTube/cookies é gate duro de produção na Phase 14. Phase 12/13 preparam host/container,
  mas só 3 downloads reais bem-sucedidos no notebook provam produção.

### O que NÃO faz o script

- Não instala Tailscale (já deve estar instalado e configurado pelo Moisés antes)
- Não instala Cloudflare Tunnel (Phase 15)
- Não instala Docker Compose stacks da aplicação (Phase 13)
- Não instala Node.js — Node pertence ao container da aplicação na Phase 13
- Não instala log2ram — notebook usa HDD, não SD card; risco de desgaste diferente e não relevante
- Não configura regras Docker `DOCKER-USER` — só após existir Compose/portas em fases futuras

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
- `scripts/12-SETUP-LOG.md` deve registrar modelo/CPU/RAM/disco (`lscpu`, `free -h`, `lsblk`) para
  dimensionar a concorrência da Phase 13
- Plan 02 deve incluir teste real de tampa fechada; se hardware impedir, registrar a exceção e operar
  com tampa aberta/semiaberta

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
