# Phase 14: Pipeline E2E on Notebook - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 14-pipeline-e2e-on-notebook
**Areas discussed:** Cookie mount no compose, deploy.sh design, bgutil no notebook, Fonte dos cookies frescos

---

## Cookie mount no compose

| Option | Description | Selected |
|--------|-------------|----------|
| Bind mount (host path) | Path fixo no host mapeado :ro nos containers | ✓ |
| Docker volume nomeado | Volume sg_cookies gerenciado pelo Docker | |
| Embutir na imagem | Copiar cookies.txt no Dockerfile | |

**User's choice:** Bind mount `:ro` em `/data/yt-dlp-cache`

| Option | Description | Selected |
|--------|-------------|----------|
| /data/yt-dlp-cache | Paridade com Railway Volume, YTDLP_CACHE_DIR sem mudança de código | ✓ |
| ~/soundgrabber/cookies | Path relativo ao home, mais fácil de lembrar | |

**User's choice:** `/data/yt-dlp-cache` — paridade com Railway Volume

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only :ro | Impede yt-dlp de sobrescrever e corromper cookies | ✓ |
| Read-write | yt-dlp pode atualizar o jar | |

**User's choice:** `:ro` — previne o mesmo bug que corrompeu cookies no Railway

| Option | Description | Selected |
|--------|-------------|----------|
| YTDLP_CACHE_DIR=/data/yt-dlp-cache | Valor fixo no .env | ✓ |
| --cookiesfrombrowser | Abordagem diferente, incompatível com slim container | |

**User's choice:** `YTDLP_CACHE_DIR=/data/yt-dlp-cache` no `.env`

---

## deploy.sh design

| Option | Description | Selected |
|--------|-------------|----------|
| Rodar no notebook, chamado via SSH | Script em ~/soundgrabber no notebook | ✓ |
| Rodar na máquina do operador | Script local com SSH + rsync | |

**User's choice:** Script no notebook, invocado via SSH

| Option | Description | Selected |
|--------|-------------|----------|
| ~/soundgrabber | Clone do repo no home, caminho previsível | ✓ |
| /opt/soundgrabber | Diretório de sistema, requer sudo | |

**User's choice:** `~/soundgrabber`

| Option | Description | Selected |
|--------|-------------|----------|
| Sempre rebuildar (--build) | Garante imagem atualizada após git pull | ✓ |
| Pull image, só rebuildar manualmente | Mais rápido, mas risco de imagem stale | |

**User's choice:** `docker compose up --build -d` sempre

| Option | Description | Selected |
|--------|-------------|----------|
| Não incluir migração de cookies | Separação de responsabilidades | ✓ |
| Incluir scp de cookies | Automatiza mas mistura código e credenciais | |

**User's choice:** deploy.sh é só `git pull + build + up` — cookies gerenciados separadamente

---

## bgutil no notebook

| Option | Description | Selected |
|--------|-------------|----------|
| Manter no compose, testar sem ele primeiro | bgutil disponível como fallback | ✓ |
| Remover bgutil do compose para notebook | Criar arquivo override | |
| Remover do compose principal | Quebra paridade com Railway | |

**User's choice:** Manter bgutil no compose, `BGUTIL_BASE_URL=` vazio no .env

| Option | Description | Selected |
|--------|-------------|----------|
| BGUTIL_BASE_URL vazio no .env | Pipeline usa só cookies, bgutil inativo | ✓ |
| Docker profile 'bgutil' | Mais explícito mas adiciona complexidade | |

**User's choice:** `BGUTIL_BASE_URL=` vazio no `.env` do notebook

| Option | Description | Selected |
|--------|-------------|----------|
| Ativar bgutil como Plano B | Setar BGUTIL_BASE_URL e repetir E2E | ✓ |
| Bloquear a fase e investigar cookies | LOGIN_REQUIRED = problema de cookies, não PO Token | |

**User's choice:** Plano B documentado: ativar bgutil se E2E falhar com cookies sozinhos

---

## Fonte dos cookies frescos

| Option | Description | Selected |
|--------|-------------|----------|
| Exportar direto do browser local | Independente do Railway, cookies frescos | ✓ |
| Renovar Railway primeiro, depois copiar | Dois passos, Railway cookies expirados | |

**User's choice:** Exportar do browser via extensão (ex: "Get cookies.txt LOCALLY")

| Option | Description | Selected |
|--------|-------------|----------|
| scp via Tailscale | Um comando, direto ao notebook | ✓ |
| USB / arquivo compartilhado | Mais trabalhoso, fora do workflow Tailscale | |

**User's choice:** `scp cookies.txt moisés@100.x.x.x:/data/yt-dlp-cache/cookies.txt`

| Option | Description | Selected |
|--------|-------------|----------|
| Checkpoint humano: grep CRITICAL nos logs | Simples, sem novo código | ✓ |
| Validação automática no deploy.sh | Mais complexo, propenso a falsos negativos | |

**User's choice:** Checkpoint humano com `docker compose logs api | grep -E "CRITICAL|cookies"`

| Option | Description | Selected |
|--------|-------------|----------|
| chmod 700 + chown para operador | Security Gate aplicado a credenciais | ✓ |
| chmod padrão | Cookies world-readable para outros usuários | |

**User's choice:** `chmod 700` com `chown $USER` no diretório `/data/yt-dlp-cache`

---

## Claude's Discretion

Nenhuma área foi delegada ao Claude — todas as decisões principais foram capturadas explicitamente.

## Deferred Ideas

- **Cloudflare Tunnel** — Phase 15
- **Renovação de cookies no Railway** — fora do escopo da Phase 14; Railway continua com LOGIN_REQUIRED
- **SSH hardening** — não é requisito explícito
- **Log rotation / monitoramento de cookies** — v2 ou fase futura
