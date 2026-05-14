# Phase 12 Risk Review — Notebook Foundation

**Data:** 2026-05-14
**Escopo:** Revisão dos planos `12-01-PLAN.md` e `12-02-PLAN.md` para notebook HP com Ubuntu Server 24.04 LTS.
**Veredito:** Planos prontos para execução. Riscos principais mapeados e mitigados nos planos.

---

## Resumo executivo

A migração do Raspberry Pi 3B para um notebook HP x86_64 elimina a maioria dos riscos originais desta fase:
arquitetura ARM, cgroups manuais via cmdline.txt, SD card wear, log2ram, e incompatibilidade de wheels.

O maior risco desta fase agora é **o notebook sumir quando a tampa for fechada** — comportamento padrão
do Ubuntu com notebook, que derrubaria o servidor sem aviso. O Plan 01 mitiga isso com drop-ins systemd
antes de qualquer outro passo.

O segundo risco é **HDD lento para swap** — em workloads de pico o SoundGrabber pode pressionar RAM
(Essentia + FFmpeg + Celery), e o HDD é 5-10x mais lento que SSD para swap. Mitigado com swappiness=10.

---

## Riscos bloqueadores

### R-12-01 — Notebook suspende com tampa fechada (CRÍTICO para servidor headless)

**Severidade:** Crítica

**Contexto:** Ubuntu Server sem GUI ainda respeita sinais de ACPI para lid close e idle por padrão via
systemd-logind. Fechar a tampa → HandleLidSwitch=suspend → servidor some da rede.

**Mitigação no Plan 01:**
- Drop-in `/etc/systemd/logind.conf.d/nosleep.conf` com `HandleLidSwitch=ignore` e `IdleAction=ignore`
- Drop-in `/etc/systemd/sleep.conf.d/nosleep.conf` bloqueando suspend e hibernate
- Verificação no Plan 02: `systemctl show logind | grep HandleLidSwitch` deve retornar `ignore`

**Status:** Mitigado no plano. Requer validação real no Plan 02.

---

### R-12-02 — Módulo de hardware watchdog pode não estar disponível

**Severidade:** Alta

**Contexto:** O systemd watchdog funciona via `/dev/watchdog`. Em notebooks Intel, o módulo `iTCO_wdt`
expõe esse dispositivo. Em AMD, `sp5100_tco`. Algumas BIOSes desabilitam o TCO watchdog por padrão.
Se `/dev/watchdog` não existir, o systemd ignora `RuntimeWatchdogSec` silenciosamente — sem erro, sem proteção.

**Evidência:** `systemctl show -p RuntimeWatchdogUSec` retorna `0` se watchdog não estiver disponível.

**Mitigação no Plan 01:**
- Script configura o drop-in `10-watchdog.conf` (necessário de qualquer forma)
- Seção de verificação final checa `systemctl show -p RuntimeWatchdogUSec`

**Ação no Plan 02 se watchdog não disponível:**
- Documentar no 12-SETUP-LOG.md
- Aceitar como limitação de hardware (não bloqueia operação — o notebook vai reiniciar normalmente em caso de falha de energia; o watchdog protege apenas contra hangs de kernel)
- Registrar na CONTEXT.md como decisão consciente

**Status:** Parcialmente mitigado. Risco residual baixo para o caso de uso do SoundGrabber.

---

## Riscos altos — não bloqueadores

### R-12-03 — HDD lento degrada performance de swap

**Severidade:** Alta (performance, não disponibilidade)

**Contexto:** Com 4GB RAM e o stack completo (FastAPI + Celery + Redis + Essentia + FFmpeg + yt-dlp),
picos podem forçar swap. HDD (5400rpm típico em notebook antigo) entrega ~80-120 MB/s sequencial vs
~500MB/s de SSD. Swap em HDD é funcional mas visível em latência de resposta.

**Mitigação no Plan 01:**
- `vm.swappiness=10` — kernel só vai usar swap como último recurso
- Com swappiness baixo, o Redis e o Celery worker ficam na RAM em operação normal

**Status:** Aceitável para o volume esperado (uso pessoal/underground). Não bloqueia a fase.

---

### R-12-04 — Idempotência do script se executado em sistema parcialmente configurado

**Severidade:** Média

**Contexto:** Se o script for interrompido no meio e re-executado, algumas seções podem falhar (ex:
`mkswap` em arquivo que já tem swap header, `usermod` tentando adicionar usuário já no grupo).

**Mitigação no Plan 01:**
- Verificações `[ -f /swapfile ]` antes de criar swap
- `[ -f /etc/apt/keyrings/docker.asc ]` antes de baixar GPG key
- `[ -f /etc/apt/sources.list.d/docker.list ]` antes de criar repo
- `set -e` aborta em caso de falha real

**Status:** Mitigado para os caminhos mais prováveis. Aceitável.

---

### R-12-05 — Docker instalado via apt pode conflitar com docker.io do Ubuntu

**Severidade:** Média

**Contexto:** Ubuntu inclui `docker.io` nos repos oficiais. Se o Moisés tiver instalado `docker.io`
antes (via `apt install docker.io`), o script pode instalar `docker-ce` por cima criando conflito.

**Mitigação:**
- `apt-get install -y docker-ce` remove pacotes conflitantes automaticamente via apt resolver
- Se houver conflito, o script aborta com mensagem clara via `set -e`

**Ação se ocorrer:** Moisés reporta o erro; solução é `apt-get remove -y docker.io docker-compose` antes de re-executar.

**Status:** Aceitável. Pouco provável em fresh install de Ubuntu Server.

---

## Risco transversal para pesquisar antes da Phase 13

### R-13-01 — Essentia em x86_64 no Docker

**Severidade:** Média para Phase 13 (sem impacto na Phase 12)

**Contexto:** Ao contrário do ARM onde Essentia não tem wheel, no x86_64 `essentia==2.1b6.dev1389`
está disponível no PyPI para Python 3.11 / manylinux. O risco é de compatibilidade de versão com
o numpy/scipy do requirements.txt, não de ausência de wheel.

**Ação recomendada antes de escrever o Plan 13:**
1. Confirmar que `pip install essentia==2.1b6.dev1389` funciona em `python:3.11-slim`
2. Testar `python -c "import essentia.standard; print('OK')"` no container
3. Validar que `RhythmExtractor2013` e `KeyExtractor` funcionam com um WAV real

**Status:** Não bloqueia Phase 12. Pesquisa necessária antes de Phase 13.

---

## Decisão final

**Planos aprovados para execução.**

Os riscos R-12-01 (lid close) e R-12-02 (watchdog) estão mitigados no Plan 01 com configuração
explícita. R-12-03 (HDD swap) é aceito conscientemente para o volume de uso esperado.

A grande simplificação vs versão Pi: sem ARM, sem cmdline.txt, sem SD card, sem log2ram, sem
verificação de 32-bit vs 64-bit. Ubuntu Server 24.04 x86_64 é um alvo muito mais previsível.

---

*Última atualização: 2026-05-14 — migrado de Raspberry Pi 3B para notebook HP x86_64*
