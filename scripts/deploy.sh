#!/usr/bin/env bash
# scripts/deploy.sh — Deploy remoto SoundGrabber no notebook via SSH/Tailscale
#
# Invocação pelo operador (máquina local):
#   ssh moisés@100.x.x.x 'bash ~/soundgrabber/scripts/deploy.sh'
#
# O que faz:
#   1. Entra no diretório ~/soundgrabber (D-05)
#   2. Faz git pull para atualizar o código (e o próprio deploy.sh — D-04)
#   3. Reconstrói e reinicia os containers com sudo docker compose up --build -d (D-05)
#
# O que NÃO faz:
#   - NÃO gerencia credenciais de autenticação (D-06 — separação de responsabilidades)
#   - Arquivos de autenticação devem ser transferidos pelo operador separadamente (AUTH-04)
#
# Referências: D-04, D-05, D-06, D-07 (14-CONTEXT.md); Security Gate (CLAUDE.md)
set -e

# Security Gate: auto-aplica permissões restritivas a cada execução (CLAUDE.md §1.2)
chmod 750 "$(realpath "$0")"

cd ~/soundgrabber

git pull

sudo docker compose up --build -d
