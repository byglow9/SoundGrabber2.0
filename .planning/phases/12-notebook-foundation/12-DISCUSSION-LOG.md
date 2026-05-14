# Phase 12: Notebook Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.
>
> **Nota histórica:** Esta discussão foi conduzida originalmente para Raspberry Pi 3B.
> Em 2026-05-14 o hardware foi trocado para notebook HP (Ubuntu Server 24.04 LTS x86_64).
> As decisões abaixo estão supersedidas — ver 12-CONTEXT.md para decisões atuais.

**Date:** 2026-05-14
**Phase:** 12-Notebook Foundation (originalmente 12-Pi Foundation)
**Areas discussed:** OS 32-bit contingência, Hardware watchdog, Proteção do cartão SD, Script de setup

---

## OS 32-bit — Plano de Contingência

| Option | Description | Selected |
|--------|-------------|----------|
| Fase 12 gera guia para Moisés reinstalar | Script detecta 32-bit e imprime instruções para flashar OS 64-bit | |
| Fase 12 para e reporta o bloqueador | Script detecta, avisa e para — reinstalação fora do scope | |
| **Trabalhar com 32-bit** | Continuar com arm/v7 — Phase 13 cuida da compilação | ✓ |

**User's choice:** Vai ter que ser em 32-bit — sem opção de reinstalar o OS.
**Notes:** O Pi provavelmente está em 32-bit (armv7l). A decisão foi trabalhar com arm/v7 desde o início. A compilação de essentia do source no arm/v7 é um risco aceito — será endereçado na Phase 13. A fase confirma a arquitetura mas não bloqueia nela.

---

## Hardware Watchdog

| Option | Description | Selected |
|--------|-------------|----------|
| **Hardware watchdog do Pi** | dtparam=watchdog=on + bcm2835-wdt. Funciona mesmo se o kernel/systemd travar | ✓ |
| Systemd watchdog | RuntimeWatchdogSec — mais simples, mas só funciona se systemd responder | |
| Os dois juntos | Hardware + systemd. Máxima segurança, mais configuração | |

**User's choice:** Hardware watchdog do Pi.
**Notes:** Usuário não conhecia o conceito — foi explicado como mecanismo de auto-reinício headless sem intervenção física. Essencial porque o Pi está na casa do Moisés sem acesso fácil.

---

## Proteção do Cartão SD

| Option | Description | Selected |
|--------|-------------|----------|
| **Instalar log2ram** | /var/log na RAM, sincroniza a cada hora. SD dura muito mais | ✓ |
| Só tmpfs em /tmp | Mais simples, SD exposto a writes contínuos de log | |

**User's choice:** Sim — vale a pena.
**Notes:** Usuário não conhecia log2ram — foi explicado o risco de queimar o SD em 6-12 meses com writes contínuos de log em servidor 24/7. Após explicação, decidiu incluir.

---

## Script de Setup

| Option | Description | Selected |
|--------|-------------|----------|
| **Bash script (scripts/pi-setup.sh)** | Executável, commitado no repo, automatiza tudo | ✓ |
| Checklist em Markdown | Passos manuais documentados, mais fácil de entender | |

**User's choice:** Bash script no repo.

| Quem executa | Description | Selected |
|--------|-------------|----------|
| Renan via SSH | Executa remotamente pelo Tailscale | |
| **Moisés no Pi dele** | Moisés roda o script com acesso local ou SSH | ✓ |

**Notes:** Script será executado pelo Moisés diretamente. Output em português, amigável. Tailscale já instalado — script não precisa configurar.

---

## Nota adicional: Cloudflare Tunnel e segurança

O Moisés expressou preocupação com o Pi ficando exposto via Cloudflare Tunnel. Foi explicado que o Tunnel usa conexão de saída do Pi para os servidores Cloudflare — o IP do Pi não fica visível, nenhuma porta é aberta no roteador. É mais seguro que port forwarding, não menos. Moisés ficou de acordo após a explicação.

---

## Claude's Discretion

- Ordem exata dos passos no script (Docker antes ou depois do swap)
- Versão do Docker (get.docker.com vs apt repository)
- Configuração de log2ram size (usar default 40MB)

## Deferred Ideas

- Docker Compose ARM e compilação de essentia → Phase 13
- deploy.sh via SSH → Phase 14
- Cloudflare Tunnel → Phase 15
- Docker com usuário não-root → planner avalia se necessário
