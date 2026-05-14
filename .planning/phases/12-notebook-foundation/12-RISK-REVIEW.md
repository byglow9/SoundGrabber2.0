# Phase 12 Risk Review — Notebook Foundation

**Data:** 2026-05-14
**Escopo:** Revisão completa dos planos `12-01-PLAN.md` e `12-02-PLAN.md` para o notebook HP com Ubuntu Server 24.04 LTS.
**Veredito realista:** A Phase 12 é executável, mas o plano deve ser tratado como **setup de host + validação humana forte**, não como automação 100% provada localmente. O caminho técnico é bom; os maiores riscos estão na validação operacional, no comportamento real de notebook fechado, no watchdog de hardware, no hardening Docker/firewall e na transição para Docker Compose da Phase 13.

---

## Resumo executivo

A troca do Raspberry Pi 3B por notebook HP x86_64 melhora muito o cenário: remove ARM, SD card wear, `cmdline.txt`, wheels ARM e boa parte dos problemas de cgroups. Ubuntu Server 24.04 LTS em amd64 é um alvo suportado oficialmente, e Docker Engine via repositório apt oficial é a alternativa certa.

O ponto que precisa ficar claro: a Phase 12 não prova ainda que o SoundGrabber roda bem no notebook. Ela prepara o host. A prova de carga real vem na Phase 13/14 com Docker Compose, cookies, bgutil, FFmpeg, Essentia e três downloads E2E.

Minha recomendação é executar a Phase 12, mas endurecer as verificações do Plan 02 e antecipar pesquisa da Phase 13 antes de escrever Compose. O plano atual está correto na direção, mas otimista em três lugares:

1. `RuntimeWatchdogSec=15` no arquivo não garante que existe watchdog ativo no hardware.
2. `HandleLidSwitch=ignore` no `systemctl show` não prova sozinho que o notebook continuará acessível depois de fechar a tampa.
3. 4GB RAM + HDD exige rampa de concorrência: começar em 1 job e testar 2 simultâneos antes de promover produção.

---

## Fontes externas verificadas

- Docker Docs — Ubuntu install: Ubuntu Noble 24.04 LTS e x86_64/amd64 são suportados; Docker recomenda repositório apt oficial e remoção prévia de pacotes conflitantes (`docker.io`, `docker-compose`, `containerd`, `runc`).
  Fonte: https://docs.docker.com/engine/install/ubuntu/
- Docker Docs — post-install: grupo `docker` concede privilégios equivalentes a root.
  Fonte: https://docs.docker.com/engine/install/linux-postinstall/
- Ubuntu Server docs — requisitos: para Ubuntu 24.04 Noble amd64, 3GB+ RAM e 25GB+ armazenamento são recomendados. O notebook de ~4GB RAM fica acima do mínimo, mas não sobra muito para o stack completo.
  Fonte: https://ubuntu.com/server/docs/reference/installation/system-requirements/
- systemd logind docs — `HandleLidSwitch`, `HandleLidSwitchExternalPower` e `IdleAction` são knobs corretos para eventos de tampa/idle.
  Fonte: https://www.freedesktop.org/software/systemd/man/latest/logind.conf.html
- systemd sleep docs — `AllowSuspend=no` e `AllowHibernation=no` desabilitam modos de economia de energia anunciados pelo systemd.
  Fonte: https://www.freedesktop.org/software/systemd/man/latest/systemd-sleep.conf.html
- systemd manager docs — `RuntimeWatchdogSec` só arma reboot automático se houver watchdog de hardware/dispositivo disponível.
  Fonte: https://www.freedesktop.org/software/systemd/man/256/systemd-system.conf.html
- PyPI Essentia — `essentia==2.1b6.dev1389` tem wheel CPython 3.11 manylinux x86_64, então o risco principal em x86_64 não é ausência de wheel; é compatibilidade real no container e consumo de memória.
  Fonte: https://pypi.org/project/essentia/2.1b6.dev1389/

---

## Avaliação por plano

### Plan 01 — `scripts/notebook-setup.sh`

**Status:** bom como baseline, mas eu ajustaria alguns detalhes antes de executar no notebook.

O plano cobre as seções certas: preflight, lid-close, Docker, swap, cgroups v2, watchdog e verificação final. A ordem também faz sentido. O script é idempotente nos caminhos principais, usa Docker oficial e evita `get.docker.com`, o que é a decisão correta.

**Pontos a endurecer no script:**

| Área | Risco | Ajuste recomendado |
|---|---|---|
| Docker repo | Plano hardcoda `arch=amd64` e `noble`; funciona no alvo, mas é menos robusto que o padrão atual da Docker. | Usar `dpkg --print-architecture` e `${UBUNTU_CODENAME:-$VERSION_CODENAME}` ou pelo menos validar que `VERSION_CODENAME=noble` antes de escrever o repo. |
| Pacotes Docker conflitantes | O plano assume que `apt` resolve conflito com `docker.io`; a documentação oficial manda remover conflitos antes. | Adicionar remoção explícita e tolerante: `apt-get remove -y docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc || true`. |
| `systemd-logind` via SSH | `systemctl restart systemd-logind` pode afetar sessão remota ou deixar comportamento ambíguo no meio do script. | Escrever drop-ins e validar após reboot; não reiniciar `systemd-logind` no meio da sessão SSH. |
| Watchdog config | `systemctl daemon-reload` não é a prova forte para config de PID 1. Reboot resolve, mas a verificação final antes do reboot pode enganar. | No Plan 02, validar `systemctl show -p RuntimeWatchdogUSec` após reboot. Tratar `0` como "watchdog indisponível", não como sucesso. |
| Swap idempotente | Se `/swapfile` já existe mas não está ativo, só verificar arquivo pode mascarar estado quebrado. | Separar criação, ativação e persistência: arquivo existe, `mkswap` quando necessário, `swapon` se inativo, `/etc/fstab` garantido. |
| Docker sem sudo | Grupo `docker` equivale a root. | Não adicionar usuário ao grupo `docker`; validar e operar com `sudo docker`. |
| UFW básico | Firewall pode bloquear acesso remoto se ativado sem regra de SSH/Tailscale. | Permitir SSH antes de ativar; permitir `tailscale0` quando existir; validar reconexão e `ufw status verbose` no Plan 02. |
| Node.js | Phase 12 não instala Node; Phase 14 precisa dele para yt-dlp/bgutil no fluxo atual. | Não instalar aqui para manter escopo, mas marcar como pesquisa/decisão obrigatória da Phase 13. |

### Plan 02 — execução humana e log

**Status:** necessário e bem pensado, mas o checklist precisa provar comportamento, não só configuração.

O Plan 02 é o verdadeiro gate da Phase 12. Sem ele, o Plan 01 só prova que um script existe. Eu manteria o checkpoint humano obrigatório.

**Verificações que eu adicionaria ao Plan 02:**

```bash
# prova que o Docker roda, não apenas que está instalado
sudo docker run --rm hello-world

# prova que cgroups v2 está exposto no kernel e no Docker
test -f /sys/fs/cgroup/cgroup.controllers && cat /sys/fs/cgroup/cgroup.controllers
sudo docker info --format '{{.CgroupVersion}}'

# prova de watchdog real; 0 = config não armou watchdog no hardware
systemctl show -p RuntimeWatchdogUSec
ls -l /dev/watchdog* || true

# prova operacional de tampa fechada
date
# fechar tampa por 2-5 minutos, reconectar via Tailscale SSH, rodar:
uptime
tailscale status
```

**Critério realista para aprovar a Phase 12:**

- `uname -m=x86_64`, Ubuntu `24.04`, Docker funcionando, swap ativo, cgroups v2 OK, sleep/lid configurado e notebook reconecta após reboot.
- Watchdog de hardware ativo é desejável, mas não deve bloquear a fase se `RuntimeWatchdogUSec=0`. Se isso acontecer, registrar como limitação de hardware e seguir.
- Lid-close real deve bloquear a fase se o notebook sumir da rede ao fechar a tampa. Exceção: limitação comprovada de hardware/BIOS/ACPI, documentada com decisão de operar aberto/semiaberto.
- UFW básico deve estar ativo sem quebrar SSH/Tailscale.

---

## Riscos críticos da Phase 12

### R-12-01 — Notebook suspende, hiberna ou some com a tampa fechada

**Severidade:** Crítica
**Probabilidade:** Média
**Impacto:** Servidor fica indisponível sem erro de aplicação.

O plano usa os knobs corretos (`HandleLidSwitch=ignore`, `IdleAction=ignore`, `AllowSuspend=no`, `AllowHibernation=no`). O risco residual é que configuração escrita não é o mesmo que comportamento validado em hardware real.

**Mitigação necessária:** Plan 02 deve incluir teste prático: fechar tampa por alguns minutos, reconectar via Tailscale, confirmar `uptime` e `tailscale status`. Sem esse teste, a fase não deveria ser marcada como completa.

**Decisão final:** gate rígido por padrão. Se falhar por limitação comprovada do hardware/BIOS/ACPI, operar com tampa aberta ou semiaberta é aceitável, desde que registrado no `12-SETUP-LOG.md`.

**Investigação se falhar:** deixar tampa semiaberta e desabilitar ações ACPI adicionais, investigar BIOS/UEFI e logs:

```bash
journalctl -b | grep -iE 'lid|suspend|sleep|hibernate|logind'
loginctl show-seat seat0
```

### R-12-02 — Watchdog configurado no arquivo, mas inativo no hardware

**Severidade:** Alta
**Probabilidade:** Média
**Impacto:** Menor do que lid-close; só afeta recuperação de travamentos fortes do kernel/sistema.

Em notebook, `/dev/watchdog` depende de suporte de chipset/BIOS e módulo do kernel. `RuntimeWatchdogSec=15` no arquivo é necessário, mas não suficiente.

**Mitigação necessária:** validar após reboot:

```bash
systemctl show -p RuntimeWatchdogUSec
ls -l /dev/watchdog* || true
```

**Decisão recomendada:** não bloquear Phase 12 se o watchdog não estiver disponível. Registrar no log como limitação do hardware. Para o SoundGrabber, os riscos mais prováveis são falha de app/container, IP/cookies/yt-dlp e pressão de memória, não kernel hang.

### R-12-03 — Docker instala, mas firewall futuro fica enganoso

**Severidade:** Alta para Phase 15
**Probabilidade:** Média
**Impacto:** Regras UFW podem não proteger portas publicadas por containers da forma que se espera.

A própria documentação da Docker alerta que portas expostas por containers podem contornar regras de UFW/firewalld se o hardening não usar a cadeia correta (`DOCKER-USER`). A Phase 12 configura apenas firewall básico de host; a Phase 15 não pode assumir que "UFW deny" protege Compose.

**Decisão final:** defesa em camadas. Phase 12 configura UFW básico no host. Produção não deve usar port-forward residencial; administração deve ser via Tailscale; público via Cloudflare Tunnel. Se Docker Compose publicar portas em fases futuras, regras devem considerar `DOCKER-USER`; UFW sozinho não é prova suficiente.

### R-12-04 — Grupo `docker` equivale a root

**Severidade:** Alta em segurança
**Probabilidade:** Certa se `usermod -aG docker` for usado
**Impacto:** Qualquer usuário no grupo `docker` pode controlar o host como root.

Para um notebook pessoal operado por Moisés, adicionar ao grupo poderia ser aceitável se fosse uma decisão consciente, mas a prioridade definida foi segurança.

**Decisão final:** Docker rootful continua sendo a melhor opção pragmática para o servidor, mas sem adicionar usuário ao grupo `docker`. Operação via `sudo docker` / `sudo docker compose` ou serviços systemd root-owned. Compose futuro deve evitar `privileged`, `network_mode: host`, portas públicas diretas e Redis exposto fora da rede interna.

---

## Riscos altos para pesquisar antes da Phase 13

### R-13-01 — Memória real: 4GB RAM + HDD + Celery concurrency 3

**Severidade:** Alta
**Probabilidade:** Alta se Compose repetir `concurrency=3`
**Impacto:** OOM, swap pesado, latência ruim, jobs falhando no meio.

O código atual roda Celery com `--concurrency=3` em `start.sh`, e o projeto historicamente assumiu cap de 3. Isso é agressivo para notebook com 4GB RAM e HDD, porque cada job pode envolver yt-dlp, FFmpeg, WAV em disco, NumPy/librosa/Essentia e Redis.

**Decisão final:** produção precisa suportar concorrência, mas com rampa validada. Começar com `worker --concurrency=1`, executar teste controlado com 2 jobs simultâneos, e só promover para `concurrency=2` se não houver OOM, swap pesada, reinício de containers ou perda de responsividade. `concurrency=3` fica fora do default inicial.

**Pesquisa/teste antes do Plan 13:**

```bash
sudo docker run --rm soundgrabber:latest python -c "import essentia.standard, librosa, yt_dlp, celery; print('OK')"
sudo docker stats
```

Rodar um WAV real e medir pico:

```bash
/usr/bin/time -v python -c "from pipeline import analyze_audio; print(analyze_audio('/tmp/sample.wav'))"
```

### R-13-02 — Essentia é obrigatório no container final

**Severidade:** Média
**Probabilidade:** Baixa para instalação, média para runtime
**Impacto:** Build passa, análise quebra em runtime ou consome memória demais.

PyPI tem wheel `cp311 manylinux x86_64` para `essentia==2.1b6.dev1389`, então a decisão de x86_64 remove o risco principal que existia no Raspberry Pi. Ainda assim, Essentia é requisito obrigatório do produto, não dependência opcional.

**Decisão final:** Phase 13 deve bloquear se `import essentia.standard` ou `analyze_audio()` no container falhar. Não aceitar fallback silencioso para análise sem Essentia.

### R-13-03 — Node.js é requisito operacional para yt-dlp/bgutil

**Severidade:** Alta para Phase 14
**Probabilidade:** Alta se o container não instalar Node
**Impacto:** YouTube JS challenges/PO Token podem falhar.

O `nixpacks.toml` atual instala `nodejs` no Railway. A futura imagem Docker precisa repetir isso explicitamente. Phase 12 não deve instalar Node no host se a aplicação vai rodar containerizada; o lugar certo é o Dockerfile.

**Decisão final:** Node.js >= 20 é dependência obrigatória do container da aplicação, não do host da Phase 12. Phase 13 deve bloquear se `node --version` falhar dentro do container.

### R-13-04 — `/tmp` compartilhado entre worker e API

**Severidade:** Alta
**Probabilidade:** Alta se Compose não modelar isso com cuidado
**Impacto:** Worker gera WAV, API não encontra arquivo para download.

O pipeline grava WAV em `/tmp/sg_*.wav`, e a API entrega esse arquivo depois pelo job id. Em Compose, API e worker são containers diferentes; sem volume compartilhado, o download quebra.

**Decisão final:** migrar na Phase 13 para diretório explícito compartilhado: `SG_TMP_DIR=/data/tmp`, com fallback local para `/tmp`. API, worker e sweeper devem usar o mesmo diretório. Docker Compose monta o mesmo volume em `/data/tmp` nos containers `api` e `worker`.

### R-14-01 — Cookies/YouTube continuam sendo o risco existencial

**Severidade:** Crítica
**Probabilidade:** Alta
**Impacto:** Infra perfeita, mas download falha com `LOGIN_REQUIRED` ou bot detection.

O `STATE.md` registra bloqueador atual: `LOGIN_REQUIRED` mesmo com GetPOT funcionando, provável cookies expirados no Railway Volume. Migrar para notebook residencial/Tailscale pode ajudar com IP, mas não elimina a necessidade de cookies frescos e validação E2E.

**Decisão final:** Phase 14 é o gate duro de produção para YouTube/cookies. Phase 12 não bloqueia por YouTube; Phase 13 bloqueia apenas por runtime/container pronto; Phase 14 bloqueia totalmente se não completar três downloads reais no notebook. Sem três downloads reais, não existe produção.

---

## Lacunas de planejamento

| Lacuna | Impacto | Recomendação |
|---|---|---|
| `.planning/STATE.md` ainda chama o milestone de "Raspberry Pi Hosting" | Baixo técnico, médio de confusão | Atualizar para "HP Notebook Hosting" quando a Phase 12 começar. |
| Plan 12 não exige modelo exato do notebook | Médio | Registrar CPU, RAM, disco HDD/SSD e saída de `lsblk`, `free -h`, `lscpu` no `12-SETUP-LOG.md`. |
| Não há teste térmico com tampa fechada | Médio/alto | Após setup, deixar 10-15 min com tampa fechada e observar temperatura/logs antes de passar para Compose. |
| Não há plano de recovery se notebook não volta após reboot | Médio | Antes de executar remoto, garantir acesso físico ou janela em que Moisés possa ligar manualmente. |
| Docker Compose ainda não tem plano | Esperado | Antes do Plan 13, pesquisar memória, Node, tmpfs compartilhado e healthchecks. |

---

## Decisões recomendadas

1. **Executar Phase 12 com notebook HP + Ubuntu Server 24.04 LTS.** É a alternativa mais pragmática e previsível para este projeto.
2. **Manter Docker rootful via apt oficial, sem grupo `docker`.** Operação via `sudo docker` por segurança.
3. **Aplicar UFW básico na Phase 12.** Deny incoming, allow outgoing, SSH/Tailscale preservado; `DOCKER-USER` fica para fases com Compose/portas.
4. **Não bloquear por watchdog ausente.** Bloquear por lid-close falhando, Docker não rodando, cgroups v2 ausente, swap não ativo ou UFW quebrando acesso.
5. **Fazer prova real de tampa fechada.** Gate rígido, salvo limitação comprovada de hardware com operação aberta/semiaberta documentada.
6. **Planejar concorrência em rampa na Phase 13.** Baseline 1 job, teste com 2 simultâneos, promover se medição permitir.
7. **Essentia e Node são obrigatórios no container.** Sem fallback silencioso para análise sem Essentia.
8. **Migrar WAV para `SG_TMP_DIR=/data/tmp` na Phase 13.**
9. **Tratar YouTube/cookies como gate duro da Phase 14.** Notebook resolve parte do ambiente, mas não resolve autenticação expirável.

---

## Checklist revisado para aprovação da Phase 12

```bash
uname -m
lsb_release -rs
lscpu | sed -n '1,20p'
free -h
lsblk

docker --version
sudo docker run --rm hello-world
sudo docker info --format '{{.CgroupVersion}}'
test -f /sys/fs/cgroup/cgroup.controllers && cat /sys/fs/cgroup/cgroup.controllers

swapon --show
grep -n '/swapfile' /etc/fstab
cat /etc/sysctl.d/99-swappiness.conf

systemctl show logind | grep -E 'HandleLidSwitch|IdleAction'
cat /etc/systemd/logind.conf.d/nosleep.conf
cat /etc/systemd/sleep.conf.d/nosleep.conf

cat /etc/systemd/system.conf.d/10-watchdog.conf
systemctl show -p RuntimeWatchdogUSec
ls -l /dev/watchdog* || true

# teste humano operacional:
# 1. fechar tampa por 2-5 minutos
# 2. reconectar via Tailscale SSH
uptime
tailscale status
```

---

## Conclusão

Os planos 12-01 e 12-02 estão no caminho certo e são realistas se a validação humana for fortalecida. Eu não mudaria a arquitetura principal da Phase 12.

O que eu mudaria é o rigor do gate: a fase só deve ser considerada completa quando o notebook provar que sobrevive a reboot, tampa fechada, Docker real, swap real e cgroups v2 real. Watchdog ativo é bônus dependente de hardware. A pesquisa pesada deve ir para Phase 13: memória/concurrency, Dockerfile com Node + FFmpeg + Essentia, e volume compartilhado para WAV.
