# 12-SETUP-LOG — Notebook Foundation Setup Log

**Data:** 2026-05-15
**Hardware:** Notebook HP (i5-3210M @ 2.50GHz, 4GB DDR3, HDD 700GB)
**OS:** Ubuntu Server 26.04 LTS (codename: resolute, kernel 7.0.0-15-generic)
**Executado por:** Renan

## Hardware Real

### lscpu
Architecture: x86_64
CPU(s): 4
Thread(s) per core: 2
Core(s) per socket: 2
Model name: Intel(R) Core(TM) i5-3210M CPU @ 2.50GHz
CPU max MHz: 2500.0000
CPU min MHz: 1200.0000
Virtualization: VT-x

### free -h
```
               total        used        free      shared  buff/cache   available
Mem:           3.2Gi       444Mi       2.4Gi       1.4Mi       581Mi       2.8Gi
Swap:          3.7Gi          0B       3.7Gi
```

### lsblk
```
NAME                      MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
sda                         8:0    0 698.6G  0 disk
├─sda1                      8:1    0     1M  0 part
├─sda2                      8:2    0     2G  0 part /boot
└─sda3                      8:3    0 696.6G  0 part
  └─ubuntu--vg-ubuntu--lv 252:0    0   100G  0 lvm  /
```

## Outputs de Verificação

### uname -m (SVR-01 — arquitetura)
```
x86_64
```

### lsb_release -rs (SVR-01 — versão do OS)
```
26.04
```

### docker --version (SVR-02 — Docker)
```
Docker version 29.5.0, build 98f1464
```

### sudo docker run --rm hello-world (SVR-02 — Docker funcional)
```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

### sudo docker info | grep "Cgroup Version" (SVR-02 — cgroups v2)
```
Cgroup Version: 2
```

### /sys/fs/cgroup/cgroup.controllers (SVR-02 — kernel cgroups v2)
```
cpuset cpu io memory hugetlb pids rdma misc dmem
```

### swapon --show (SVR-02 — swap)
```
NAME      TYPE SIZE USED PRIO
/swapfile file   4G   0B   -1
```
Nota: /swap.img (3.7G criado pelo installer) foi removido com swapoff + rm + sed /etc/fstab.

### /etc/fstab e swappiness (SVR-02 — swap persistente)
- `/swapfile none swap sw 0 0` adicionado ao fstab
- `vm.swappiness=10` em /etc/sysctl.d/99-swappiness.conf

### sudo ufw status verbose (host firewall)
```
Status: active
Default: deny (incoming), allow (outgoing)
22/tcp ALLOW IN Anywhere  # SSH admin access
tailscale0 ALLOW IN Anywhere  # Tailscale private access
```

### cat /etc/systemd/logind.conf.d/nosleep.conf (SVR-03 — lid close)
```
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
IdleAction=ignore
IdleActionSec=0
```

### cat /etc/systemd/sleep.conf.d/nosleep.conf
```
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
```

### Teste real de tampa fechada (SVR-03 — operação headless)
Tampa fechada por ~3 minutos. SSH via IP local (192.168.100.244) reconectou com sucesso.
uptime e tailscale status confirmaram que o notebook permaneceu online durante todo o período.

### cat /etc/systemd/system.conf.d/10-watchdog.conf (SVR-03 — watchdog)
```
[Manager]
RuntimeWatchdogSec=15
ShutdownWatchdogSec=2min
```

### Tailscale
Instalado (v1.96.4) e conectado. IP Tailscale: 100.90.251.75
SSH via 100.90.251.75 testado e funcional do PC do operador (corazon).

## Resultado

- [x] SVR-01: uname -m retornou x86_64 e lsb_release retornou 26.04
- [x] SVR-02: Docker 29.5.0 instalado e funcional via sudo + Cgroup Version: 2 + swap /swapfile 4G
- [x] Host firewall: UFW ativo com deny incoming, allow outgoing, SSH e Tailscale preservados
- [x] SVR-03: HandleLidSwitch=ignore confirmado + teste real de tampa fechada aprovado
- [x] SVR-03: RuntimeWatchdogSec=15 configurado
- [x] SVR-04: Script executou sem erros manuais adicionais

## Decisões / Limitações de Hardware

- Tampa fechada: **aprovado** — notebook permaneceu acessível via SSH durante 3 minutos com tampa fechada
- Watchdog hardware: não verificado /dev/watchdog — não bloqueante conforme D-04a
- Concorrência Phase 13: baseline Celery concurrency=1, testar rampa para 2 com 4GB RAM + HDD
- Ubuntu 26.04 "resolute": Docker já tem pacotes nativos para esse codename — sem fallback necessário
- /swap.img (3.7G do installer) removido; apenas /swapfile (4G) ativo

## Observações

- Ubuntu 26.04 LTS (resolute) tem suporte oficial Docker — packages disponíveis em download.docker.com/linux/ubuntu resolute
- Tailscale 1.96.4 instalado após o script de setup; regra UFW tailscale0 adicionada manualmente conforme instrução do script
- Hostname configurado como "nagi" (referência ao Nagi Nagi no Mi do Corazon — One Piece)
- IP local: 192.168.100.244 | IP Tailscale: 100.90.251.75
