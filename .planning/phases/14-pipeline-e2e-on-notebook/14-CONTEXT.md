# Phase 14: Pipeline E2E on Notebook - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Entregar três coisas concretas no notebook HP (IP residencial via Tailscale):
1. **Cookie mount** — `cookies.txt` montado como bind mount `:ro` em `/data/yt-dlp-cache`
   nos containers `api` e `worker`, com `YTDLP_CACHE_DIR=/data/yt-dlp-cache` no `.env`.
2. **deploy.sh** — Script em `~/soundgrabber/deploy.sh` no notebook que executa
   `git pull + docker compose up --build -d` e é chamado com um único comando SSH do operador.
3. **Validação E2E** — Três URLs de beats reais submetidas ao `POST /jobs` no notebook
   resultam em `status=done` com WAV válido, BPM e tonalidade — sem bgutil ativo, sem
   `LOGIN_REQUIRED`.

Esta fase NÃO inclui: Cloudflare Tunnel (Phase 15), renovação de cookies no Railway, alterações
de código na lógica do pipeline.

</domain>

<decisions>
## Implementation Decisions

### Cookie mount no docker-compose.yml

- **D-01:** Adicionar bind mount `:ro` ao `docker-compose.yml` nos serviços `api` e `worker`:
  `/data/yt-dlp-cache:/data/yt-dlp-cache:ro`. O diretório `/data/yt-dlp-cache` no host do
  notebook é a fonte dos cookies. Read-only evita que yt-dlp sobrescreva e corrompa o arquivo
  ao detectar sessão inválida (o mesmo bug que corrompeu os cookies no Railway — bytes caíram de
  2987 para ~1600).
- **D-02:** `YTDLP_CACHE_DIR=/data/yt-dlp-cache` no `.env` do notebook (e no `.env.example`
  atualizado). O código em `api/config.py` já lê esta env var — sem mudança de código.
- **D-03:** O diretório `/data/yt-dlp-cache` no host deve ser criado com `chmod 700` e
  `chown` para o usuário operador antes do primeiro deploy (Security Gate — credenciais
  não world-readable). O plano deve documentar: `sudo mkdir -p /data/yt-dlp-cache &&
  sudo chown $USER: /data/yt-dlp-cache && chmod 700 /data/yt-dlp-cache`.

### deploy.sh

- **D-04:** Script em `scripts/deploy.sh` (commitado no repo) e instalado em
  `~/soundgrabber/scripts/deploy.sh` no notebook. Invocação pelo operador:
  `ssh moisés@100.x.x.x 'bash ~/soundgrabber/scripts/deploy.sh'`.
- **D-05:** Conteúdo do script: `set -e`, `cd ~/soundgrabber`, `git pull`,
  `sudo docker compose up --build -d`. AUTH-05 especifica exatamente `git pull +
  docker compose up --build -d` — sem desvio.
- **D-06:** deploy.sh NÃO inclui migração de cookies. Cookies são responsabilidade do
  operador (AUTH-04) — copiados uma vez via `scp` antes do primeiro deploy. Misturar
  gestão de código com gestão de credenciais no mesmo script é erro de separação de
  responsabilidades.
- **D-07:** deploy.sh segue Security Gate: `set -e` na primeira linha, `chmod 750
  "$(realpath "$0")"` auto-aplicado, sem `eval` de input externo.

### bgutil no notebook

- **D-08:** `docker-compose.yml` principal **mantém** o serviço `bgutil` — sem mudança.
  bgutil permanece disponível como fallback caso IP residencial também precise de PO Token.
- **D-09:** No `.env` do notebook, `BGUTIL_BASE_URL=` (vazio). Pipeline usa apenas
  cookies (IP residencial). PIPE-08 exige validação "sem bgutil" — satisfeita por
  BGUTIL_BASE_URL vazio no .env, não por remover o serviço.
- **D-10:** **Plano B explícito:** se E2E falhar com `LOGIN_REQUIRED` mesmo em IP
  residencial com cookies frescos, o executor seta `BGUTIL_BASE_URL=http://bgutil:4416`
  no `.env`, reinicia os serviços e repete o E2E. O resultado (com ou sem bgutil) deve
  ser documentado no relatório de deploy.

### Fonte dos cookies frescos (AUTH-04)

- **D-11:** Fonte dos cookies: exportar diretamente do browser local do operador via
  extensão (ex: "Get cookies.txt LOCALLY" para youtube.com com conta Google autenticada).
  **Não** depender do Railway Volume (cookies lá estão expirados — BLOCKER do STATE.md).
- **D-12:** Transferência para o notebook: `scp cookies.txt moisés@100.x.x.x:/data/yt-dlp-cache/cookies.txt`
  via Tailscale. Checkpoint humano AUTH-04 é verificado com:
  `docker compose logs api | grep -E "CRITICAL|cookies"`.
- **D-13:** O plano deve incluir checkpoint humano explícito para AUTH-04: operador confirma
  `docker compose logs api` sem linha `CRITICAL` antes de prosseguir para E2E.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos desta fase
- `.planning/REQUIREMENTS.md` §v1.3 — AUTH-04, AUTH-05, PIPE-08 com critérios exatos
- `.planning/ROADMAP.md` §Phase 14 — 3 success criteria observáveis

### Contexto de fases anteriores (decisões que impactam esta fase)
- `.planning/phases/13-docker-compose/13-CONTEXT.md` — D-08..D-15: estrutura dos serviços,
  volume sg_tmp, rede soundgrabber_net, mem_limits, bgutil no compose
- `.planning/phases/12-notebook-foundation/12-CONTEXT.md` — D-06 (sudo docker, sem grupo docker),
  D-13 (sem privileged/host network), hardware confirmado i5-3210M/4GB

### Código a modificar
- `docker-compose.yml` — adicionar bind mount `/data/yt-dlp-cache` nos serviços api e worker (D-01)
- `.env.example` — atualizar `YTDLP_CACHE_DIR=/data/yt-dlp-cache` (D-02)
- `scripts/deploy.sh` — criar novo arquivo (D-04..D-07)

### Código existente (sem mudança)
- `api/config.py` — `cache_dir` lê `YTDLP_CACHE_DIR` via env var; sem alteração necessária
- `api/main.py` — `_check_oauth_cache` valida presença de cookies no startup; sem alteração

### Security Gate
- `CLAUDE.md` §Security Gate — controles obrigatórios para novos scripts shell e permissões de arquivos

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `start-all.sh` — padrão de script bash do projeto: `set -e`, `chmod 750 "$(realpath "$0")"`,
  comentários WHY; usar como template para `scripts/deploy.sh`
- `api/config.py` linha 38 — `cache_dir: str = field(default_factory=lambda: os.environ.get("YTDLP_CACHE_DIR", ""))`
  — lê a env var corretamente, sem mudança de código necessária
- `api/main.py` — `_check_oauth_cache()` no lifespan valida `cookies.txt` presente no
  `cache_dir`; já emite CRITICAL se ausente — é o gate que AUTH-04 valida

### Established Patterns
- docker-compose.yml usa `env_file: .env` nos serviços api e worker — adicionar variáveis
  no `.env` / `.env.example`, não hardcodar no compose
- Volumes no compose seguem padrão nomeado (sg_tmp) — bind mounts para dados do operador
  são exceção deliberada por serem credenciais externas ao repo
- Scripts do projeto: `set -e`, `chmod` auto-aplicado, sem eval de input externo (Security Gate)

### Integration Points
- `docker-compose.yml` serviços `api` e `worker` — onde adicionar o bind mount (D-01)
- `.env.example` — onde documentar `YTDLP_CACHE_DIR=/data/yt-dlp-cache` (D-02)

</code_context>

<specifics>
## Specific Ideas

- Invocação SSH exata do AUTH-05: `ssh moisés@100.x.x.x 'bash ~/soundgrabber/scripts/deploy.sh'`
- Checkpoint AUTH-04: `docker compose logs api | grep -E "CRITICAL|cookies"` — ausência de CRITICAL = cookies OK
- Bind mount no compose: `/data/yt-dlp-cache:/data/yt-dlp-cache:ro` (mesmos paths host e container)
- BGUTIL_BASE_URL vazio no .env do notebook — bgutil permanece no compose mas inativo
- Plano B documentado: se E2E falhar → setar BGUTIL_BASE_URL=http://bgutil:4416 e repetir

</specifics>

<deferred>
## Deferred Ideas

- **Cloudflare Tunnel** — scope da Phase 15 (TUNNEL-01..02)
- **Renovação de cookies no Railway** — não é scope desta fase; Railway continua com problema
  de LOGIN_REQUIRED; o notebook opera com cookies frescos independentes
- **SSH hardening (key-only, fail2ban)** — boas práticas mas não são requisito explícito
- **Log rotation no notebook** — v2 ou phase futura
- **Monitoramento automático de expiração de cookies** — útil mas scope futuro

</deferred>

---

*Phase: 14-pipeline-e2e-on-notebook*
*Context gathered: 2026-05-15*
