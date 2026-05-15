# Phase 14: Pipeline E2E on Notebook - Research

**Researched:** 2026-05-15
**Domain:** Docker Compose bind mounts, deploy scripts shell, yt-dlp cookie auth
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Bind mount `:ro` no `docker-compose.yml` nos serviços `api` e `worker`:
`/data/yt-dlp-cache:/data/yt-dlp-cache:ro`. Read-only evita que yt-dlp sobrescreva e corrompa o arquivo (mesmo bug que derrubou cookies no Railway).

**D-02:** `YTDLP_CACHE_DIR=/data/yt-dlp-cache` no `.env` do notebook e no `.env.example`. Nenhuma mudança em `api/config.py`.

**D-03:** `/data/yt-dlp-cache` no host criado com `chmod 700` e `chown` para o usuário operador antes do primeiro deploy. Plano deve documentar:
`sudo mkdir -p /data/yt-dlp-cache && sudo chown $USER: /data/yt-dlp-cache && chmod 700 /data/yt-dlp-cache`

**D-04:** Script em `scripts/deploy.sh` (commitado no repo), instalado em `~/soundgrabber/scripts/deploy.sh` no notebook. Invocação: `ssh moisés@100.x.x.x 'bash ~/soundgrabber/scripts/deploy.sh'`.

**D-05:** Conteúdo: `set -e`, `cd ~/soundgrabber`, `git pull`, `sudo docker compose up --build -d`.

**D-06:** `deploy.sh` NÃO inclui migração de cookies. Cookies são responsabilidade do operador (AUTH-04), copiados uma vez via `scp` antes do primeiro deploy.

**D-07:** `deploy.sh` segue Security Gate: `set -e` na primeira linha, `chmod 750 "$(realpath "$0")"` auto-aplicado, sem `eval` de input externo.

**D-08:** `docker-compose.yml` **mantém** o serviço `bgutil` sem mudança.

**D-09:** No `.env` do notebook, `BGUTIL_BASE_URL=` (vazio). Pipeline usa apenas cookies em IP residencial.

**D-10:** Plano B explícito: se E2E falhar com `LOGIN_REQUIRED` mesmo com cookies frescos em IP residencial, o executor seta `BGUTIL_BASE_URL=http://bgutil:4416` no `.env`, reinicia e repete. Resultado documentado no relatório de deploy.

**D-11:** Fonte dos cookies: exportar do browser local do operador via extensão ("Get cookies.txt LOCALLY") para youtube.com com conta Google autenticada. Não usar cookies do Railway Volume (expirados — BLOCKER do STATE.md).

**D-12:** Transferência via `scp cookies.txt moisés@100.x.x.x:/data/yt-dlp-cache/cookies.txt` via Tailscale. Checkpoint AUTH-04 verificado com `docker compose logs api | grep -E "CRITICAL|cookies"`.

**D-13:** Plano deve incluir checkpoint humano explícito: operador confirma `docker compose logs api` sem linha `CRITICAL` antes de prosseguir para E2E.

### Claude's Discretion

Nenhuma área explicitamente marcada como discretion nesta fase — todas as decisões foram bloqueadas.

### Deferred Ideas (OUT OF SCOPE)

- Cloudflare Tunnel — Phase 15 (TUNNEL-01..02)
- Renovação de cookies no Railway — Railway continua com LOGIN_REQUIRED; notebook opera com cookies independentes
- SSH hardening (key-only, fail2ban)
- Log rotation no notebook
- Monitoramento automático de expiração de cookies
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-04 | Operador copia `cookies.txt` do Railway Volume para o notebook via SSH/Tailscale e startup log confirma cookies presentes sem erro CRITICAL | Bind mount `:ro` em `/data/yt-dlp-cache` + `_check_oauth_cache()` já implementado em `api/main.py` — sem código novo; apenas infra (diretório host + mount no compose + variável no .env) |
| AUTH-05 | Existe `deploy.sh` que executa `git pull + docker compose up --build -d` no notebook com um comando via SSH/Tailscale | Novo arquivo `scripts/deploy.sh` com `set -e`, Security Gate, e invocação via SSH — template em `start-all.sh` disponível no repo |
| PIPE-08 | 3 URLs de beats enviadas ao `POST /jobs` no notebook resultam em `status=done` com WAV válido, BPM e tonalidade — sem bgutil, sem `LOGIN_REQUIRED` | Validação humana após infraestrutura (D-01..D-13) estar em lugar; resultado depende de cookies frescos e IP residencial via Tailscale |
</phase_requirements>

---

## Summary

A Phase 14 é puramente de infraestrutura e operações — nenhuma mudança de código de aplicação é necessária. O pipeline de download/conversão/análise já está implementado e validado (Phase 13). Esta fase conecta cookies frescos ao pipeline via bind mount Docker, cria o script de deploy SSH-invocável e realiza validação E2E no hardware do notebook (i5-3210M/4GB, IP residencial).

O stack técnico da fase envolve três domínios: (1) Docker Compose bind mounts com semântica `:ro`, (2) scripting bash com Security Gate do projeto, e (3) yt-dlp cookie auth em IP residencial. O bloqueador histórico (cookies corrompidos no Railway) é mitigado pelo bind mount read-only — yt-dlp não consegue sobrescrever o arquivo no container mesmo que detecte sessão inválida.

O risco principal é o comportamento do YouTube com IP residencial sem bgutil. A decisão D-09 (BGUTIL_BASE_URL vazio) é respaldada pela hipótese de que IPs residenciais sofrem menos bot detection que datacenters, mas isso é validado apenas em execução real. O Plano B (D-10) está documentado para o caso de falha.

**Primary recommendation:** Entregar em três tarefas sequenciais: (1) infra de cookies (diretório host + bind mount + .env), (2) `scripts/deploy.sh`, (3) validação E2E com checkpoint humano AUTH-04 obrigatório antes do E2E.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cookie storage e permissões | Host OS (notebook) | — | Credenciais vivem no host, fora do container — bind mount expõe ao container sem copiar para imagem |
| Cookie mount nos containers | Docker Compose | — | Bind mount `:ro` é responsabilidade do compose, não da aplicação |
| Cookie validation no startup | API tier (api/main.py) | — | `_check_oauth_cache()` já implementado; loga CRITICAL se cookies ausentes |
| Deploy automation (git pull + restart) | Scripts (shell) | — | `deploy.sh` é invocado no host do notebook via SSH |
| Pipeline E2E (download→WAV→BPM/key) | Worker tier (Celery) | API tier (serve) | Já implementado em Phases anteriores; esta fase apenas valida no novo hardware |
| bgutil PO Token (Plano B) | Docker Compose service | Worker tier | bgutil já no compose (D-08); ativado via BGUTIL_BASE_URL se necessário |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Docker Compose v2 | v2.35.1 (confirmado local) | Orquestração de containers | Já em uso no projeto (Phase 13) |
| bash | sistema | Script de deploy | Padrão do projeto — `start-all.sh`, `notebook-setup.sh` |
| yt-dlp | Pinado em requirements.txt | Download YouTube com cookies | Stack do projeto; suporte a cookiefile nativo |
| Essentia | Pinado em requirements.txt | BPM + key detection | Obrigatório por MEMORY.md — librosa proibida |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scp / Tailscale | sistema | Transferência segura de cookies | Uma vez antes do primeiro deploy |
| jim60105/bgutil-pot | latest | PO Token provider (Plano B) | Apenas se IP residencial falhar com cookies |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Bind mount `:ro` | Docker volume nomeado sg_cookies | Volume nomeado é gerenciado pelo Docker daemon — mais difícil de atualizar manualmente; bind mount permite `scp` direto para o path |
| `scp` para transferência | `rsync` | rsync adiciona complexidade sem ganho para arquivo único |
| `sudo docker compose up --build -d` | `docker compose up --build -d` (sem sudo) | Projeto usa `sudo docker` por decisão da Phase 12 D-06 (sem grupo docker) |

**Installation:** Nenhuma instalação necessária — stack completo já está no repo e no notebook (Phase 13).

**Version verification:** [VERIFIED: docker compose version output] `Docker Compose version v2.35.1-desktop.1`

---

## Architecture Patterns

### System Architecture Diagram

```
Operador (máquina local)
    │
    ├── [AUTH-04] scp cookies.txt ─────────────────────────────────────────┐
    │    (uma vez, via Tailscale)                                           │
    │                                                                       ▼
    └── [AUTH-05] ssh 'bash ~/soundgrabber/scripts/deploy.sh'   /data/yt-dlp-cache/
                     │                                           cookies.txt (host)
                     ▼                                                      │
              Notebook HP                                                   │
              ~/soundgrabber/                                               │ bind mount :ro
              ├── git pull                                                  │
              └── sudo docker compose up --build -d                        │
                           │                                                │
                           ▼                                                │
              ┌─────────────────────────────────────────┐                  │
              │    soundgrabber_net (bridge)             │                  │
              │                                          │                  │
              │  redis:7-alpine                          │                  │
              │       │                                  │                  │
              │  bgutil:jim60105/bgutil-pot (inativo)    │                  │
              │                                          │                  │
              │  api (soundgrabber:latest)  ◄────────────┼──────────────────┤
              │    /data/yt-dlp-cache:ro                 │                  │
              │    _check_oauth_cache() startup          │                  │
              │    POST /jobs → Celery task              │                  │
              │                                          │                  │
              │  worker (soundgrabber:latest) ◄──────────┼──────────────────┘
              │    /data/yt-dlp-cache:ro                 │
              │    yt-dlp + cookiefile                   │
              │    Essentia BPM/key                      │
              │    sg_tmp:/tmp (tmpfs compartilhado)     │
              └─────────────────────────────────────────┘

[PIPE-08] POST /jobs (3 beats) → status=done, WAV + BPM + key
```

### Recommended Project Structure

```
scripts/
├── deploy.sh          # NOVO — git pull + docker compose up --build -d
├── notebook-setup.sh  # Existente — Phase 12
└── 12-SETUP-LOG.md    # Existente — audit trail

docker-compose.yml     # Modificar — adicionar bind mount /data/yt-dlp-cache
.env.example           # Modificar — adicionar YTDLP_CACHE_DIR=/data/yt-dlp-cache
```

### Pattern 1: Docker Compose Bind Mount Read-Only

**What:** Montar diretório do host como somente-leitura em múltiplos containers.
**When to use:** Credenciais externas ao repo que precisam estar acessíveis nos containers sem serem gerenciadas pelo Docker daemon.

```yaml
# Source: Docker Compose documentation — bind mount syntax [CITED: docs.docker.com/compose/compose-file/07-volumes/]
services:
  api:
    volumes:
      - sg_tmp:/tmp                               # volume nomeado tmpfs existente
      - /data/yt-dlp-cache:/data/yt-dlp-cache:ro # bind mount :ro — D-01

  worker:
    volumes:
      - sg_tmp:/tmp                               # volume nomeado tmpfs existente
      - /data/yt-dlp-cache:/data/yt-dlp-cache:ro # bind mount :ro — D-01
```

**Nota crítica:** Bind mounts em serviços que **também** usam volumes nomeados (como `sg_tmp`) requerem que a seção `volumes:` do serviço liste ambos. Não substitui um pelo outro.

### Pattern 2: Deploy Script com Security Gate

**What:** Script bash commitado no repo, invocável via SSH, com `set -e` e `chmod` auto-aplicado.
**When to use:** Qualquer script de operação no projeto SoundGrabber (mandatório pelo Security Gate em CLAUDE.md).

```bash
#!/usr/bin/env bash
# Source: start-all.sh e notebook-setup.sh — padrão estabelecido no projeto [VERIFIED: grep repo]
set -e

# Security Gate: auto-aplica permissões restritivas a cada execução
chmod 750 "$(realpath "$0")"

cd ~/soundgrabber

git pull

sudo docker compose up --build -d
```

### Pattern 3: Checkpoint de Cookie via Logs

**What:** Verificar presença de cookies via logs do container antes de executar E2E.
**When to use:** Após `docker compose up` — valida que `_check_oauth_cache()` não emitiu CRITICAL.

```bash
# D-12, D-13: gate humano AUTH-04
docker compose logs api | grep -E "CRITICAL|AUTH:"
# Esperado: linhas "AUTH: cookies.txt encontrado" sem "CRITICAL"
# Se aparecer CRITICAL: cookies não estão no bind mount ou faltam __Secure-3PSID
```

### Anti-Patterns to Avoid

- **Misturar cookie management com deploy:** `deploy.sh` NÃO copia cookies — decisão D-06. Separação de responsabilidades: código vs. credenciais.
- **Bind mount read-write para credenciais:** yt-dlp sobrescreve o jar ao detectar sessão inválida, corrompendo o arquivo (bug documentado no STATE.md — bytes caíram de 2987 para ~1600). Sempre `:ro`.
- **Dependência de `~` em realpath:** `cd ~/soundgrabber` funciona via SSH porque bash expande `~` no contexto do usuário SSH. Não usar paths absolutos hardcoded ao usuário.
- **`docker compose` sem `sudo`:** Phase 12 D-06 decidiu não adicionar o usuário ao grupo docker. `sudo docker compose` é obrigatório no notebook.
- **Verificar E2E sem checkpoint AUTH-04:** Submeter jobs antes de confirmar que cookies foram carregados resulta em `LOGIN_REQUIRED` imediato sem diagnóstico claro.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cookie validation no startup | Nova lógica Python | `_check_oauth_cache()` em `api/main.py` (linha 488) | Já implementado, testado; logs CRITICAL com mensagem acionável |
| Transferência de credenciais | Script de sync automatizado | `scp` manual via Tailscale | D-06 — separação de responsabilidades; credenciais são responsabilidade do operador, não do código |
| PO Token sem bgutil | Implementar gerador local | `BGUTIL_BASE_URL=http://bgutil:4416` + serviço já no compose | bgutil já está no docker-compose.yml (D-08); ativar é apenas variável de ambiente |

**Key insight:** Esta fase não escreve lógica de aplicação. Toda a inteligência já existe — o trabalho é conectar peças existentes (bind mount, env var, script de deploy) e validar que funcionam no hardware alvo.

---

## Common Pitfalls

### Pitfall 1: `sg_tmp` volume perdido ao adicionar bind mount

**What goes wrong:** Ao adicionar o bind mount `/data/yt-dlp-cache` na seção `volumes:` de `api` e `worker`, o desenvolvedor inadvertidamente remove a linha `sg_tmp:/tmp`, quebrando o compartilhamento de WAV entre containers.

**Why it happens:** A seção `volumes:` de um serviço suporta múltiplas entradas; editar sem ver o estado atual resulta em substituição em vez de adição.

**How to avoid:** Verificar o docker-compose.yml atual antes de editar. A seção `volumes:` de cada serviço deve ter **ambas** as entradas:
```yaml
volumes:
  - sg_tmp:/tmp                               # existente — não remover
  - /data/yt-dlp-cache:/data/yt-dlp-cache:ro # novo — adicionar
```

**Warning signs:** `docker compose up` sem erro mas `GET /files/{id}` retornando 404 após job completo — worker criou WAV em `/tmp` isolado da api.

### Pitfall 2: `/data/yt-dlp-cache` não existe no host antes do `docker compose up`

**What goes wrong:** Docker tenta montar um diretório que não existe no host. Comportamento do Docker: cria o diretório automaticamente como `root:root` com permissões `755` — cookies copiados pelo operador ficam inacessíveis ao container (que roda como usuário não-root) ou são criados no path errado.

**Why it happens:** Bind mounts exigem que o diretório host exista previamente com as permissões corretas. Docker não emite erro se criar o diretório, mas o `chown` estará errado.

**How to avoid:** Criar e configurar o diretório **antes** do primeiro deploy (D-03):
```bash
sudo mkdir -p /data/yt-dlp-cache
sudo chown $USER: /data/yt-dlp-cache
chmod 700 /data/yt-dlp-cache
```

**Warning signs:** `docker compose logs api` mostra `AUTH: cookies.txt nao encontrado` mesmo após `scp` aparentemente bem-sucedido — verificar `ls -la /data/yt-dlp-cache/` no host.

### Pitfall 3: `scp` para path errado ou sem Tailscale conectado

**What goes wrong:** `scp cookies.txt moisés@100.x.x.x:/data/yt-dlp-cache/cookies.txt` falha silenciosamente ou copia para path incorreto se Tailscale não estiver conectado ou o IP mudou.

**Why it happens:** Tailscale IPs são estáveis mas requerem que o cliente Tailscale esteja ativo em ambas as máquinas.

**How to avoid:** Verificar conectividade antes do scp: `tailscale ping 100.x.x.x`. Após scp, verificar no notebook: `ls -la /data/yt-dlp-cache/cookies.txt` e `wc -c /data/yt-dlp-cache/cookies.txt` — deve ser > 2000 bytes com cookies frescos.

**Warning signs:** Arquivo presente mas com tamanho ~1600 bytes indica cookies corrompidos (mesmo bug do Railway). Re-exportar do browser.

### Pitfall 4: `docker compose` vs `sudo docker compose` no script

**What goes wrong:** `deploy.sh` roda `docker compose up` sem `sudo`; SSH não carrega grupos do usuário por padrão; Docker socket inacessível; erro `permission denied`.

**Why it happens:** Phase 12 D-06 decidiu usar `sudo docker` em vez de adicionar o usuário ao grupo docker. SSH não-interativo não garante membership em grupos suplementares.

**How to avoid:** `deploy.sh` sempre usa `sudo docker compose up --build -d` (D-05).

### Pitfall 5: E2E com `BGUTIL_BASE_URL` ativo quando deveria estar vazio

**What goes wrong:** `.env` no notebook tem `BGUTIL_BASE_URL=http://bgutil:4416` (valor do `.env.example` default) — PIPE-08 exige validação "sem bgutil". Se bgutil ajudar a passar, o requisito não está satisfeito.

**Why it happens:** `.env.example` original tem `BGUTIL_BASE_URL=http://bgutil:4416`. Operador copia e não altera.

**How to avoid:** `.env.example` deve ter `BGUTIL_BASE_URL=` (vazio) com comentário explicando que notebook usa apenas cookies. Verificar com `grep BGUTIL_BASE_URL .env` antes do E2E.

---

## Code Examples

### Bind mount no docker-compose.yml (diff conceitual)

```yaml
# Source: docker-compose.yml existente no repo [VERIFIED: Read tool]
# Antes (api service):
  api:
    volumes:
      - sg_tmp:/tmp

# Depois (adicionar bind mount — NÃO remover sg_tmp):
  api:
    volumes:
      - sg_tmp:/tmp
      - /data/yt-dlp-cache:/data/yt-dlp-cache:ro
```

Aplicar o mesmo ao serviço `worker`.

### scripts/deploy.sh (conteúdo completo)

```bash
#!/usr/bin/env bash
# deploy.sh — Deploy remoto do SoundGrabber no notebook HP via SSH/Tailscale
#
# Invocação pelo operador:
#   ssh moisés@100.x.x.x 'bash ~/soundgrabber/scripts/deploy.sh'
#
# O que faz: git pull + rebuild da imagem + restart dos containers
# O que NÃO faz: gerenciar cookies (responsabilidade do operador — AUTH-04)
#
# Referências: D-04..D-07 em 14-CONTEXT.md; Security Gate em CLAUDE.md
# Source: padrão estabelecido por start-all.sh e notebook-setup.sh [VERIFIED: Read tool]
set -e

# Security Gate: auto-aplica permissões restritivas a cada execução (CLAUDE.md)
chmod 750 "$(realpath "$0")"

cd ~/soundgrabber

git pull

sudo docker compose up --build -d
```

### .env para notebook (valores corretos)

```bash
# Relevante para Phase 14 — diferenças em relação ao .env.example default

# bgutil INATIVO no notebook — IP residencial usa apenas cookies (D-09, PIPE-08)
BGUTIL_BASE_URL=

# cookies.txt no bind mount — necessário para AUTH-04
YTDLP_CACHE_DIR=/data/yt-dlp-cache
```

### Verificação E2E via curl (PIPE-08)

```bash
# Submeter job
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=BEAT_URL_HERE"}')
JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# Aguardar conclusão (polling)
while true; do
  STATUS=$(curl -s http://localhost:8000/jobs/$JOB_ID | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "done" ] && break
  [ "$STATUS" = "error" ] && echo "FAILED" && break
  sleep 3
done

# Verificar resultado
curl -s http://localhost:8000/jobs/$JOB_ID | python3 -m json.tool
```

---

## Runtime State Inventory

> Esta fase modifica infra do notebook (diretório host, bind mount, .env, script) — sem rename/refactor, mas com estado de runtime relevante.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Nenhum — sem banco de dados envolvido | Nenhuma |
| Live service config | docker-compose.yml em uso no notebook (se já rodando) — containers precisam ser reiniciados após modificação do compose | `sudo docker compose up --build -d` recria containers com novo bind mount |
| OS-registered state | `/data/yt-dlp-cache` no host — não existe ainda (Phase 13 não criou este diretório) | `sudo mkdir -p + chown + chmod 700` antes do primeiro deploy |
| Secrets/env vars | `.env` no notebook — `YTDLP_CACHE_DIR=` (vazio atual); `BGUTIL_BASE_URL=http://bgutil:4416` (deve ser esvaziado para PIPE-08) | Editar `.env` no notebook: setar `YTDLP_CACHE_DIR=/data/yt-dlp-cache` e esvaziar `BGUTIL_BASE_URL` |
| Build artifacts | `soundgrabber:latest` image no notebook — será reconstruída por `docker compose up --build -d` | Nenhuma ação extra; `--build` garante imagem atualizada |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Compose v2 | D-05 (`docker compose up`) | ✓ (local) | v2.35.1 | — |
| Tailscale | AUTH-04 scp, AUTH-05 SSH | [ASSUMED] | — | Rede local direta se no mesmo segmento |
| `scp` | AUTH-04 transferência de cookies | ✓ (OpenSSH padrão Linux) | — | rsync, ou cópia física via USB |
| `git` | D-05 (`git pull`) | [ASSUMED: já instalado no notebook — notebook-setup.sh faz clone do repo] | — | — |
| `sudo` | D-05 (`sudo docker compose`) | [ASSUMED: Ubuntu 24.04 padrão] | — | — |
| Notebook HP (IP Tailscale) | Toda a fase | [ASSUMED: operador confirma antes de executar] | — | Fase bloqueada sem hardware |

**Missing dependencies com fallback:** Tailscale pode ser substituído por rede local direta se operador e notebook estiverem no mesmo segmento. `scp` pode ser substituído por USB para cópia inicial de cookies.

**Missing dependencies sem fallback:** Nenhum — todos os componentes principais estão confirmados ou têm fallback.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (confirmado em `pytest.ini`) |
| Config file | `pytest.ini` na raiz |
| Quick run command | `pytest tests/ -x -q --ignore=tests/test_pipeline_docker.py` |
| Full suite command | `pytest tests/ -ra --strict-markers` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-04 | Bind mount :ro presente em api e worker no compose | unit (AST/YAML parse) | `pytest tests/test_deploy_sh.py::test_bind_mount_in_compose -x` | ❌ Wave 0 |
| AUTH-04 | `.env.example` contém `YTDLP_CACHE_DIR=/data/yt-dlp-cache` | unit (file content) | `pytest tests/test_deploy_sh.py::test_env_example_ytdlp_cache_dir -x` | ❌ Wave 0 |
| AUTH-04 | `_check_oauth_cache` loga CRITICAL se YTDLP_CACHE_DIR vazio | unit | Já coberto em `tests/test_pipeline_fixes.py::test_pipe05_critical_log_when_cookies_missing_sentinel` | ✅ Existente |
| AUTH-05 | `scripts/deploy.sh` existe e contém `set -e` | unit (file content) | `pytest tests/test_deploy_sh.py::test_deploy_sh_exists_with_set_e -x` | ❌ Wave 0 |
| AUTH-05 | `scripts/deploy.sh` contém `chmod 750 "$(realpath "$0")"` | unit (file content) | `pytest tests/test_deploy_sh.py::test_deploy_sh_security_gate -x` | ❌ Wave 0 |
| AUTH-05 | `scripts/deploy.sh` contém `git pull` e `docker compose up --build -d` | unit (file content) | `pytest tests/test_deploy_sh.py::test_deploy_sh_commands -x` | ❌ Wave 0 |
| AUTH-05 | `scripts/deploy.sh` NÃO contém `eval` | unit (file content) | `pytest tests/test_deploy_sh.py::test_deploy_sh_no_eval -x` | ❌ Wave 0 |
| PIPE-08 | 3 URLs E2E no notebook retornam status=done com WAV/BPM/key | e2e manual | Manual — requer hardware do notebook + cookies frescos + Tailscale | manual-only |

**PIPE-08 é manual-only:** Depende de IP residencial real, cookies frescos exportados do browser e hardware físico do notebook. Não pode ser automatizado em CI sem acesso ao ambiente de produção.

### Sampling Rate

- **Per task commit:** `pytest tests/test_deploy_sh.py -x -q`
- **Per wave merge:** `pytest tests/ -ra --strict-markers -q`
- **Phase gate:** Suite verde + checkpoint humano AUTH-04 (logs sem CRITICAL) + 3 jobs PIPE-08 verificados

### Wave 0 Gaps

- [ ] `tests/test_deploy_sh.py` — cobre AUTH-04 (bind mount no compose, .env.example) e AUTH-05 (deploy.sh conteúdo + security gate)

*(Infraestrutura de teste existente — pytest.ini, conftest.py — cobre todos os outros requisitos. Apenas o arquivo de teste específico desta fase precisa ser criado.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | não | — |
| V3 Session Management | não | — |
| V4 Access Control | parcial | Permissões de arquivo no host (Security Gate) |
| V5 Input Validation | não | Sem novos endpoints |
| V6 Cryptography | não | — |

### Known Threat Patterns for esta fase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credenciais world-readable em `/data/yt-dlp-cache` | Information Disclosure | `chmod 700` no diretório host (D-03); `chmod 600` no `cookies.txt` recomendado após cópia |
| `deploy.sh` world-executable | Elevation of Privilege | `chmod 750` auto-aplicado (D-07); apenas owner + grupo podem executar |
| `eval` de input externo em scripts | Tampering | Proibido por Security Gate; `deploy.sh` usa apenas `git pull` e `docker compose` sem input externo |
| Path traversal via bind mount | Tampering | Bind mount `:ro` — containers não podem escrever no path do host; protege o arquivo de cookies |

### Project Constraints (from CLAUDE.md)

Diretrizes obrigatórias que impactam esta fase:

1. **Novos scripts shell:**
   - `set -e` na primeira linha após shebang — obrigatório em `scripts/deploy.sh`
   - `chmod 750 "$(realpath "$0")"` auto-aplicado — obrigatório em `scripts/deploy.sh`
   - Sem `eval` de input externo — verificado nos testes Wave 0

2. **Arquivos gerados em `/tmp`:** Não aplicável (fase não gera novos arquivos em /tmp)

3. **Novos endpoints HTTP:** Não aplicável (fase não adiciona endpoints)

4. **Testes de segurança:** `tests/test_deploy_sh.py` deve cobrir conteúdo do script (sem eval, com set -e, com chmod 750)

5. **Security Checklist:** `.planning/SECURITY-CHECKLIST.md` não requer atualização para esta fase (sem novos controles de segurança da aplicação — controles são de infra/operação)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| cookies + YTDLP_COOKIES_B64 (base64 env var) | cookies via bind mount `:ro` | Phase 14 | Cookies sobrevivem a redeploys sem re-injetar variável de ambiente; yt-dlp não pode corromper |
| BGUTIL_BASE_URL ativo por padrão | BGUTIL_BASE_URL vazio no notebook | Phase 14 | Valida que IP residencial não precisa de PO Token (PIPE-08); bgutil permanece como Plano B |
| `soundgrabber:latest` via Railway (sem build local) | `docker compose up --build -d` no notebook | Phase 13+ | Imagem construída localmente no notebook — sem push/pull de registry |

**Deprecated/outdated:**
- `YTDLP_COOKIES_B64`: abordagem do Railway para injetar cookies via env var; notebook usa bind mount direto — mais simples e mais seguro para hardware local
- `start-all.sh` no notebook: Railway usa start-all.sh para single-container; compose usa CMD do Dockerfile para cada serviço separado

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Tailscale está ativo e configurado no notebook com IP estável na rede `100.x.x.x` | Environment Availability | `scp` e SSH falham; fase bloqueada sem conectividade |
| A2 | `git` está instalado no notebook e `~/soundgrabber` é um clone do repo | Environment Availability | `git pull` em deploy.sh falha; solução: clonar repo antes do primeiro deploy |
| A3 | IP residencial do notebook não sofre bot detection do YouTube com cookies frescos | Common Pitfalls / PIPE-08 | E2E falha com `LOGIN_REQUIRED`; mitigado pelo Plano B (D-10): ativar bgutil |
| A4 | Cookies exportados via "Get cookies.txt LOCALLY" contêm `__Secure-3PSID` e são válidos no momento do deploy | Common Pitfalls | `_check_oauth_cache()` loga CRITICAL; solução: re-exportar cookies frescos imediatamente antes do deploy |
| A5 | Phase 13 foi completada: `docker-compose.yml`, `Dockerfile`, e imagem `soundgrabber:latest` funcionais no notebook | Architecture | Todo o pipeline falha; prerequisito obrigatório — verificar `docker compose ps` antes de iniciar |

---

## Open Questions

1. **Qual é o IP Tailscale exato do notebook?**
   - O que sabemos: IP na rede `100.x.x.x` (faixa Tailscale)
   - O que não sabemos: IP exato para o plano documentar o comando SSH preciso
   - Recomendação: Plano deve usar placeholder `<NOTEBOOK_TAILSCALE_IP>` e instruir o operador a verificar com `tailscale ip -4` no notebook

2. **`docker compose up --build` reconstrói imagem se Dockerfile não mudou?**
   - O que sabemos: `--build` força rebuild; se código do app mudou via `git pull`, rebuild é necessário
   - O que não sabemos: se o cache de layers Docker é suficientemente inteligente para evitar rebuild desnecessário quando apenas arquivos de conteúdo (não Dockerfile) mudam
   - Recomendação: `--build` é correto conforme D-05; layers de sistema (apt) serão cacheadas; apenas layer COPY . . será reconstruída — comportamento esperado e desejável

3. **Phase 13 está completa no notebook físico?**
   - O que sabemos: Phase 13 foi verificada (commit `e6efdbc`); DEPLOY-04/05/06 marcados como Complete
   - O que não sabemos: se o operador fez deploy da Phase 13 no notebook físico antes desta fase
   - Recomendação: Wave 0 do plano deve incluir verificação explícita: `docker compose ps` no notebook confirma todos os 4 serviços UP

---

## Sources

### Primary (HIGH confidence)

- `docker-compose.yml` no repo — [VERIFIED: Read tool] — estrutura atual de volumes e serviços
- `api/main.py` linhas 488-542 — [VERIFIED: Read tool] — `_check_oauth_cache()` implementado
- `api/config.py` linha 38 — [VERIFIED: Read tool] — `cache_dir` lê `YTDLP_CACHE_DIR`
- `start-all.sh` — [VERIFIED: Read tool] — padrão de script shell do projeto
- `.env.example` — [VERIFIED: Read tool] — valores atuais de `YTDLP_CACHE_DIR` e `BGUTIL_BASE_URL`
- `14-CONTEXT.md` — [VERIFIED: Read tool] — D-01..D-13 locked decisions
- `pytest.ini` — [VERIFIED: Bash] — configuração de testes existente
- `tests/test_pipeline_docker.py` e `tests/test_pipeline_fixes.py` — [VERIFIED: Read tool] — cobertura existente

### Secondary (MEDIUM confidence)

- Docker Compose v2 bind mount syntax — [CITED: docs.docker.com/compose] — `:ro` flag e path format
- STATE.md Known Issues — [VERIFIED: Read tool] — cookies corrompidos (bytes 2987 → 1600), blocker login_required

### Tertiary (LOW confidence)

- A3: IP residencial não sofre bot detection — hipótese baseada em comportamento geral do YouTube; não testado neste ambiente específico

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stack completo já em uso, nenhuma dependência nova
- Architecture: HIGH — todos os componentes existem; fase conecta peças via config
- Pitfalls: HIGH — baseado em bugs reais documentados no STATE.md e CONTEXT.md (cookies corrompidos, sudo docker, sg_tmp)
- PIPE-08 (validação E2E): MEDIUM — depende de comportamento externo (YouTube anti-bot) em IP não testado

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (yt-dlp e bot detection do YouTube mudam com frequência; cookies expiram em ~30 dias)
