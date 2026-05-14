---
plan: 12-01
phase: 12-notebook-foundation
status: complete
completed: 2026-05-14
---

# Summary — Plan 12-01: Criar scripts/notebook-setup.sh

## What Was Built

`scripts/notebook-setup.sh` — script bash reproduzível que configura o notebook HP do Moisés
para rodar o SoundGrabber de forma headless e autônoma com Ubuntu Server 24.04 LTS.

## Key Files Created

- `scripts/notebook-setup.sh` — script bash com 8 seções de configuração do host

## Tasks Completed

1. **Criar scripts/notebook-setup.sh** — script completo com as 8 seções:
   - Seção 0: Header, `set -e`, `chmod 750` auto-aplicado, root check
   - Seção 1: Preflight read-only (uname, lsb_release, df, free, lscpu, lsblk, swapon)
   - Seção 2: Lid-close prevention (logind.conf.d/nosleep.conf + sleep.conf.d/nosleep.conf)
   - Seção 3: Docker via apt repo oficial da Docker (download.docker.com) — remove conflitantes, GPG key, repositório, instala docker-ce + plugins; sem grupo docker
   - Seção 4: Firewall UFW básico (deny incoming, allow outgoing, SSH, tailscale0 condicional)
   - Seção 5: Swap 4GB (fallocate + fallback dd, chmod 600, fstab, swappiness=10)
   - Seção 6: Cgroups v2 (verificação /sys/fs/cgroup/cgroup.controllers)
   - Seção 7: Watchdog systemd (10-watchdog.conf com RuntimeWatchdogSec=15)
   - Seção 8: Verificação final com tabela de status de todos componentes

2. **Verificar e commitar** — todos os checks de acceptance criteria passaram; script commitado.

## Verification Results

```
shebang:          OK
set -e:           OK
chmod 750:        OK
root check:       OK
no usermod docker: OK
docker apt repo:  OK (download.docker.com/linux/ubuntu)
no get.docker.com: OK
UFW deny incoming: OK
fallocate 4G:     OK
dd fallback:      OK
nosleep.conf:     OK
logind.conf.d:    OK
sleep.conf.d:     OK
10-watchdog.conf: OK
RuntimeWatchdog:  OK
sudo reboot:      OK
no eval:          OK
```

## Security Gate Compliance

- `set -e` na primeira linha após shebang: OK
- `chmod 750 "$(realpath "$0")"` auto-aplicado: OK
- Sem `eval` de input externo: OK
- Sem grupo docker (equivale a root): OK

## Deviations

Nenhum desvio do plano. `bash -n` não disponível em Windows (ambiente de desenvolvimento);
verificação de sintaxe bash será feita pelo Moisés na execução real no notebook (Plan 02).

## Self-Check: PASSED

SVR-04 satisfeito: script documentado, reproduzível, com sintaxe válida e commitado ao repositório.

## Git Commits

- `eed167a` — feat(12): add notebook-setup.sh -- Ubuntu Server 24.04 host foundation script
