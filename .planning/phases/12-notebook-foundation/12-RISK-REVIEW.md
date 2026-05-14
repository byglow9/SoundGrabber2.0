# Phase 12 Risk Review — Pi Foundation

**Data:** 2026-05-14
**Escopo:** Revisao realista dos planos `12-01-PLAN.md` e `12-02-PLAN.md` antes de executar no Raspberry Pi 3B.
**Veredito:** Nao executar o plano 12 como esta. O plano e bom como intencao, mas tem contradicoes e lacunas que podem gerar retrabalho ou um Pi inacessivel.

---

## Resumo executivo

A Phase 12 deveria ser uma fundacao conservadora: confirmar arquitetura, instalar Docker, habilitar swap/cgroups, configurar watchdog, reduzir desgaste do SD e produzir evidencia real do Pi.

O maior risco nao e escrever `scripts/pi-setup.sh`. O maior risco e o plano aceitar um Pi `armv7l` apesar de `PI-01` e o `ROADMAP.md` exigirem `aarch64`. Isso empurra para a Phase 13 uma decisao que deveria bloquear agora. Com o stack atual (`librosa`, `essentia`, `numpy`, `scipy`, `yt-dlp`, `bgutil`) em um Pi 3B de 1GB, arquitetura errada significa build instavel, dependencias ARM problemáticas e muito retrabalho.

Minha recomendacao: **transformar a arquitetura 64-bit em gate real**. Se `uname -m` retornar `armv7l`, parar e reinstalar Raspberry Pi OS 64-bit antes de Docker, a menos que a gente decida explicitamente mudar o milestone para suportar arm/v7 com risco maior.

---

## Riscos bloqueadores

### R-12-01 — Contradicao entre requisito e plano: `aarch64` vs `armv7l`

**Severidade:** Critica

**Evidencia local:**
- `REQUIREMENTS.md` define `PI-01`: operador confirma OS 64-bit e `uname -m` retorna `aarch64`.
- `ROADMAP.md` success criterion 1 da Phase 12 tambem exige `aarch64` antes de prosseguir.
- `12-CONTEXT.md` D-01/D-02 e `12-01-PLAN.md` dizem para continuar normalmente se retornar `armv7l`.
- `.planning/research/STACK.md` recomenda 64-bit explicitamente.
- `.planning/research/PITFALLS.md` P-ARM-05 recomenda reinstalar 64-bit se o Pi estiver em 32-bit.

**Por que importa:** Phase 13 vai construir imagem ARM com deps cientificas. `armv7l` aumenta friccao com wheels, imagens Docker e possiveis builds nativos. O plano atual deixa a decisao mais importante do milestone para depois, quando ja teremos modificado o host.

**Alternativa realista:** mudar o Plan 01 para:
1. rodar preflight read-only;
2. se `uname -m != aarch64`, imprimir instrucao de reinstalar Raspberry Pi OS Lite 64-bit e sair com erro;
3. so instalar Docker/swap/cgroups/watchdog se `aarch64`.

**Decisao necessaria:** manter requisito `aarch64` como gate ou rebaixar formalmente `PI-01` para aceitar `armv7l`. Eu recomendo manter `aarch64`.

---

### R-12-02 — Watchdog configurado de forma possivelmente insuficiente no Bookworm

**Severidade:** Alta

**Evidencia local:**
- Plan 01 adiciona `dtparam=watchdog=on` e `bcm2835-wdt`.
- P-ARM-07 tambem exige configurar systemd para alimentar o watchdog: `RuntimeWatchdogSec=15`.
- O Plan 01 nao altera `/etc/systemd/system.conf` nem cria drop-in em `/etc/systemd/system.conf.d/`.

**Pesquisa externa:**
- A documentacao atual da Raspberry Pi descreve `kernel_watchdog_timeout` e diz que em Raspberry Pi OS Bookworm `RuntimeWatchdogSec` nao vem habilitado por padrao; tambem afirma que `kernel_watchdog_timeout` e preferivel a `dtparam=watchdog` porque define explicitamente o `open_timeout`.
  Fonte: https://www.raspberrypi.com/documentation/computers/config_txt.html

**Por que importa:** o plano pode passar no grep (`dtparam=watchdog=on`) e ainda assim nao entregar recuperacao confiavel em caso de travamento. Isso cria uma falsa sensacao de seguranca para operacao headless.

**Alternativa realista:** configurar:
- `/boot/firmware/config.txt`: preferir `kernel_watchdog_timeout=15`; manter `dtparam=watchdog=on` apenas como fallback se validado no Pi.
- `/etc/systemd/system.conf.d/10-watchdog.conf`:
  ```ini
  [Manager]
  RuntimeWatchdogSec=15
  ShutdownWatchdogSec=2min
  ```
- verificar depois do reboot com `cat /proc/sys/kernel/watchdog`, `dmesg | grep -i watchdog`, `systemctl show -p RuntimeWatchdogUSec`, e reconexao via SSH.

---

### R-12-03 — Instalar Docker via `get.docker.com` e log2ram via `master.tar.gz` ainda e supply-chain fraco

**Severidade:** Alta

**Evidencia local:**
- Plan 01 baixa `https://get.docker.com` para `/tmp/sg_docker-install.sh` e executa.
- Plan 01 baixa `https://github.com/azlux/log2ram/archive/master.tar.gz` e executa `install.sh`.
- O plano evita `curl | sh`, o que e bom, mas ainda executa codigo remoto como root sem pinagem de versao/hash.

**Pesquisa externa:**
- Docker Docs dizem que o convenience script existe, mas e recomendado apenas para ambientes de teste/desenvolvimento; a instalacao via repositorio apt e o caminho mais controlavel.
  Fonte: https://docs.docker.com/engine/install/debian/
- README do log2ram mostra instalacao manual via tarball e recomenda reboot antes de instalar outras coisas.
  Fonte: https://github.com/azlux/log2ram

**Por que importa:** Phase 12 vira script reprodutivel. "Baixar master atual e rodar como root" nao e totalmente reprodutivel.

**Alternativa realista:**
- Docker: usar repo apt oficial da Docker para Debian/Raspberry Pi OS, com keyring em `/etc/apt/keyrings`, e instalar `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`.
- log2ram: preferir apt repo do azlux com keyring, ou pin de commit/tag + hash se usar tarball.
- Se mantiver `get.docker.com`, usar `--dry-run` no log, salvar versao instalada e aceitar conscientemente o risco.

---

### R-12-04 — Memory cgroups estao incompletos para o que a Phase 13 precisa

**Severidade:** Alta

**Evidencia local:**
- Plan 01 adiciona apenas `cgroup_enable=memory cgroup_memory=1`.
- P-ARM-08 recomenda tambem `swapaccount=1`.
- STACK.md usa `cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1`.
- O plano verifica o arquivo de boot, mas nao verifica `/proc/cmdline` apos reboot.

**Pesquisa externa:**
- A documentacao Raspberry Pi confirma que `cmdline.txt` deve ficar em uma unica linha e que `/proc/cmdline` e a fonte do estado efetivo apos boot.
  Fonte: https://www.raspberrypi.com/documentation/computers/configuration.html
- Docker Docs tratam memoria e swap como controles separados: `--memory-swap` so tem efeito junto com `--memory`.
  Fonte: https://docs.docker.com/engine/containers/resource_constraints/

**Por que importa:** se Docker ainda mostrar warning de memory/swap limits, a Phase 13 pode colocar `mem_limit` no compose e ele ser ignorado. Em um Pi 3B de 1GB, isso pode derrubar o host.

**Alternativa realista:** adicionar:
```text
cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1 swapaccount=1
```
e depois do reboot validar:
```bash
cat /proc/cmdline
docker info 2>&1 | grep -iE 'memory|swap|cgroup'
```

---

## Riscos altos nao bloqueadores, mas devem virar ajustes

### R-12-05 — `usermod -aG docker pi` assume usuario `pi` e concede privilegio root equivalente

**Evidencia:** Docker Docs avisam que o grupo `docker` concede privilegios equivalentes a root.
Fonte: https://docs.docker.com/engine/install/linux-postinstall

**Ajuste recomendado:** usar `${SUDO_USER}` quando existir, nao hardcode `pi`, e imprimir aviso claro:
```bash
TARGET_USER="${SUDO_USER:-}"
```
Se vazio, nao adicionar ninguem ao grupo. Para um host headless simples isso pode ser aceitavel, mas deve ser explicito.

---

### R-12-06 — Swap via `fallocate` pode nao ser suficiente como logica idempotente

**Problemas:**
- Se ja existir swap menor via `dphys-swapfile`, o plano cria mais swap sem decidir se isso e desejado.
- `fallocate` pode falhar ou criar arquivo inadequado em alguns FS; `dd` fallback e prudente.
- O criterio do Plan 02 espera prioridade `-2`, mas isso pode variar.

**Ajuste recomendado:**
- detectar swap ativo com `swapon --show --bytes`;
- se `/swapfile` existe mas nao tem 2GB, abortar com instrucao em vez de sobrescrever;
- usar `dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress` como fallback;
- validar por tamanho aproximado, nao prioridade exata.

---

### R-12-07 — SD card ainda fica exposto a writes pesados do Docker

**Evidencia local:** P-ARM-06 alerta para Docker overlay, Redis e logs. Plan 12 instala log2ram, mas nao configura Docker log rotation nem move Docker data-root.

**Ajuste recomendado:** nao precisa resolver tudo na Phase 12, mas criar item obrigatorio para Phase 13:
- Docker logging driver `local` ou `json-file` com `max-size`/`max-file`;
- Redis sem AOF;
- `/tmp` dos containers em tmpfs;
- considerar USB/SSD para `/var/lib/docker` se o Pi virar host permanente.

---

### R-12-08 — Verificacao do watchdog com freeze test pode ser perigosa

**Problema:** success criterion fala em freeze test ou config confirmada. Fazer freeze remoto sem smart plug/physical access pode tornar o Pi indisponivel.

**Ajuste recomendado:** Plan 02 deve separar:
- verificacao segura obrigatoria: config + `/proc` + systemd + reboot normal;
- freeze test opcional somente com acesso fisico ou smart plug.

---

## Risco transversal para pesquisar antes da Phase 13

### R-13-01 — `essentia` e analise de audio no ARM sao o maior risco tecnico do milestone

**Severidade:** Critica para Phase 13/14

**Evidencia local:**
- `requirements.txt` fixa `essentia==2.1b6.dev1389`.
- `pipeline.py` importa `essentia.standard`, `librosa`, `numpy`, `scipy`.
- `analyze_audio()` carrega o WAV varias vezes:
  - `detect_tuning()` usa `librosa.load(..., sr=None)` e HPSS;
  - `detect_bpm()` usa `essentia.MonoLoader(..., sampleRate=44100)`;
  - `detect_key()` usa outro `essentia.MonoLoader(..., sampleRate=44100)`.
- `start-all.sh` atual ainda usa Celery `--concurrency=3`; para Pi 3B isso e agressivo.

**Por que importa:** mesmo que a Phase 12 seja perfeita, a aplicacao pode nao subir ou pode OOMar na Phase 13. Esse risco precisa de spike antes de desenhar o compose final.

**Spike recomendado antes/entre Phase 12 e Phase 13:**
1. Em Pi OS 64-bit, rodar container `python:3.11-slim-bookworm`.
2. Instalar deps minimas: `numpy scipy soundfile librosa essentia yt-dlp`.
3. Testar:
   ```bash
   python -c "import numpy, scipy, librosa, essentia.standard, yt_dlp; print('OK')"
   ```
4. Rodar `analyze_audio()` em 1 WAV real de ate 90s e medir tempo/RAM.
5. Se `essentia` falhar em ARM, decidir alternativa antes de Compose:
   - compilar essentia em imagem propria;
   - trocar BPM/key para librosa puro com menor precisao;
   - usar imagem conda/mamba;
   - mover analise para outro host e manter Pi so como gateway.

---

## Ajustes recomendados no Plan 12

### Reescrever Plan 01 em duas etapas

1. **Preflight read-only**
   - `uname -m`
   - `/etc/os-release`
   - `getconf LONG_BIT`
   - boot paths existentes: `/boot/firmware/{cmdline.txt,config.txt}` ou `/boot/{cmdline.txt,config.txt}`
   - espaco livre: `df -h /`
   - memoria: `free -h`
   - swap atual: `swapon --show`
   - Tailscale/SSH nao instalar, mas confirmar reconexao no Plan 02

2. **Setup somente se preflight passar**
   - Docker via apt repo oficial preferencialmente;
   - swap 2GB com fallback;
   - cgroups com `cpuset`, `memory`, `swapaccount`;
   - watchdog com `kernel_watchdog_timeout` + systemd `RuntimeWatchdogSec`;
   - log2ram com metodo pinado;
   - verificacao final deixando claro o que so ativa apos reboot.

### Atualizar Plan 02

- Nao exigir prioridade `-2` no `swapon --show`.
- Verificar `/proc/cmdline`, nao so arquivo em `/boot`.
- Verificar `systemctl show -p RuntimeWatchdogUSec`.
- Trocar "volta em <90s" para "volta em ate 180s" para Pi 3B + Tailscale.
- Freeze test somente opcional e com acesso fisico/smart plug.
- Incluir resultado de `docker info` completo o bastante para ver cgroup driver e warnings.

---

## Decisao recomendada

**Minha alternativa preferida:** manter Phase 12, mas revisar os planos antes de executar:

1. `aarch64` vira gate bloqueante.
2. Docker muda para apt repo oficial, ou o risco do convenience script fica explicitamente aceito.
3. Watchdog muda para configuracao Bookworm atual: `kernel_watchdog_timeout` + systemd.
4. Cgroups incluem `swapaccount=1` e validacao via `/proc/cmdline`.
5. Criar spike curto para `essentia/librosa` em ARM antes de escrever Phase 13.

Essa rota e mais lenta no primeiro dia, mas evita o pior cenario: configurar um Pi 32-bit, descobrir tarde que as deps cientificas nao fecham, e ter que reinstalar tudo quando a Phase 13 ja estiver parcialmente feita.

---

## Fontes consultadas

- Docker Engine Debian install docs: https://docs.docker.com/engine/install/debian/
- Docker Linux post-install docs: https://docs.docker.com/engine/install/linux-postinstall
- Docker resource constraints docs: https://docs.docker.com/engine/containers/resource_constraints/
- Raspberry Pi kernel command line docs: https://www.raspberrypi.com/documentation/computers/configuration.html
- Raspberry Pi config/watchdog docs: https://www.raspberrypi.com/documentation/computers/config_txt.html
- log2ram README: https://github.com/azlux/log2ram
