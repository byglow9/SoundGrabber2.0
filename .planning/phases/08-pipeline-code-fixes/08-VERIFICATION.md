---
phase: 08-pipeline-code-fixes
verified: 2026-05-11T14:30:00Z
status: human_needed
score: 2/4 must-haves verified (2 require Railway deployment)
overrides_applied: 0
human_verification:
  - test: "Deploy to Railway com nixpacks.toml presente e executar 'ffprobe -version' dentro do container"
    expected: "Comando retorna versao do ffprobe sem erro (ffprobe version 6.x ou superior)"
    why_human: "Requer build e deploy no Railway PaaS — nao e possivel simular localmente"
  - test: "Submeter URL de beat do YouTube em instancia Railway recem-deployada (sem cache de JS no yt-dlp)"
    expected: "Job completa com status=done, WAV disponivel para download, sem erro de 'nsig extraction' nos logs do worker"
    why_human: "Requer instancia Railway com cookies validos, Redis, e Celery worker ativos — nao simulavel localmente"
---

# Phase 8: Pipeline Code Fixes — Verification Report

**Phase Goal:** The pipeline code is correct — ffprobe resolves reliably, yt-dlp is hardened against transient failures and cache drift, cookies are validated at startup, and Railway knows to install system ffmpeg
**Verified:** 2026-05-11T14:30:00Z
**Status:** human_needed
**Re-verification:** No — verificacao inicial

---

## Goal Achievement

### Observable Truths (Success Criteria do ROADMAP)

| # | Verdade Observable | Status | Evidencia |
|---|-------------------|--------|-----------|
| 1 | `python pipeline.py <url>` em maquina com ffmpeg do sistema usa o ffprobe do sistema (via shutil.which), nao o path do imageio-ffmpeg, e completa sem FileNotFoundError | VERIFICADO | `pipeline._FFPROBE_PATH == shutil.which("ffprobe") == "/usr/bin/ffprobe"` confirmado em runtime; test_pipe01 PASSED |
| 2 | Deploy no Railway com nixpacks.toml presente resulta em `ffprobe -version` com sucesso dentro do container | PRECISA HUMANO | Requer deploy Railway — nao verificavel localmente |
| 3 | Iniciar a aplicacao com cookies.txt sem `__Secure-3PSID` produz linha de log CRITICAL visivel antes de qualquer job ser processado | VERIFICADO | `_check_cookies()` existe em api/main.py (linha 138), chamada no lifespan antes do sweeper (linha 192), test_pipe05 PASSED |
| 4 | Submeter URL de beat para instancia Railway recem-deployada (sem cache de JS) completa sem erros de nsig causados por cache stale do yt-dlp | PRECISA HUMANO | Requer instancia Railway com yt-dlp sem cache — nao verificavel localmente |

**Score: 2/4 verdades verificadas localmente** (critérios 2 e 4 dependem de Railway)

---

### Itens Diferidos

Nenhum item diferido — todos os requisitos desta fase (PIPE-01..05, DEPLOY-01) foram implementados. Os critérios 2 e 4 não estão diferidos para outra fase; eles requerem verificação humana com ambiente Railway.

---

### Required Artifacts

| Artefato | Esperado | Status | Detalhes |
|----------|---------|--------|----------|
| `pipeline.py` | Correcao de ffprobe resolution + hardening yt-dlp opts | VERIFICADO | `_FFMPEG_DIR`, `_FFPROBE_PATH` via shutil.which, `no_cache_dir`, `retries` presentes; sem `_FFMPEG_PATH` como ffmpeg_location |
| `api/main.py` | Validacao de cookies no lifespan | VERIFICADO | `_check_cookies()` definida (linhas 138-183), chamada na linha 192 do lifespan |
| `nixpacks.toml` | Declaracao de pacote de sistema Railway | VERIFICADO | Presente na raiz; contem `aptPkgs = ["ffmpeg"]` |
| `tests/test_pipeline_fixes.py` | 8 testes RED (Plan 01) depois GREEN | VERIFICADO | 8/8 PASSED — confirmado via pytest |

---

### Key Link Verification

| De | Para | Via | Status | Detalhes |
|----|------|-----|--------|---------|
| `pipeline._FFPROBE_PATH` | `shutil.which("ffprobe")` | atribuicao no nivel de modulo (linha 46) | WIRED | `_FFPROBE_PATH = _system_ffprobe or str(Path(_FFMPEG_PATH).parent / "ffprobe")` — sistema primeiro |
| `pipeline.check_duration` | `_FFMPEG_DIR` | chave `ffmpeg_location` em ydl_opts (linha 81) | WIRED | `"ffmpeg_location": _FFMPEG_DIR` — bug `_FFMPEG_PATH` eliminado |
| `pipeline.download_audio` | `_FFMPEG_DIR` | chave `ffmpeg_location` em ydl_opts (linha 163) | WIRED | `"ffmpeg_location": _FFMPEG_DIR` — bug `_FFMPEG_PATH` eliminado |
| `api/main.py lifespan` | `settings.cookies_path` | `_check_cookies(settings.cookies_path)` (linha 192) | WIRED | Chamada imediatamente apos `_check_redis_auth`, antes do sweeper thread |
| `nixpacks.toml` | Railway build system | diretiva `aptPkgs` (linha 7) | WIRED | `aptPkgs = ["ffmpeg"]` — instrui nixpacks a instalar ffmpeg via apt |

---

### Data-Flow Trace (Level 4)

Nao aplicavel para esta fase — os artefatos sao utilidades/configuracoes (pipeline.py opcoes de yt-dlp, api/main.py startup check, nixpacks.toml config). Nenhum componente renderiza dados dinamicos de usuario.

---

### Behavioral Spot-Checks

| Comportamento | Comando | Resultado | Status |
|---------------|---------|-----------|--------|
| `_FFPROBE_PATH` usa ffprobe do sistema | `pipeline._FFPROBE_PATH == shutil.which("ffprobe")` | `/usr/bin/ffprobe` (match) | PASSOU |
| `_FFMPEG_DIR` e diretorio valido | `os.path.isdir(pipeline._FFMPEG_DIR)` | `True` | PASSOU |
| `ffmpeg_location` nao aponta para binario (bug eliminado) | `grep "ffmpeg_location.*_FFMPEG_PATH" pipeline.py` | vazio | PASSOU |
| `no_cache_dir: True` presente em check_duration | `inspect.getsource(pipeline.check_duration)` | presente | PASSOU |
| `no_cache_dir: True` presente em download_audio | `inspect.getsource(pipeline.download_audio)` | presente | PASSOU |
| `retries: 3` apenas em download_audio (nao em check_duration) | `inspect.getsource(pipeline.check_duration)` | ausente (correto) | PASSOU |
| 8 testes da fase passam | `pytest tests/test_pipeline_fixes.py -v` | 8 PASSED em 1.50s | PASSOU |

---

### Requirements Coverage

| Requisito | Plano | Descricao | Status | Evidencia |
|-----------|-------|-----------|--------|-----------|
| PIPE-01 | 08-02 | ffprobe via PATH do sistema (shutil.which) antes de imageio-ffmpeg | SATISFEITO | `_system_ffprobe = shutil.which("ffprobe")` em pipeline.py linha 39; `_FFPROBE_PATH` usa resultado (linha 46) |
| PIPE-02 | 08-02 | `ffmpeg_location` passado ao yt-dlp e diretorio, nao binario | SATISFEITO | `_FFMPEG_DIR = str(Path(_FFMPEG_PATH).parent)` linha 38; usado em ambas as funcoes (linhas 81, 163) |
| PIPE-03 | 08-02 | `no_cache_dir=True` em todas as chamadas yt-dlp | SATISFEITO | Presente em check_duration (linha 80) e download_audio (linha 159) |
| PIPE-04 | 08-02 | `retries=3` e `fragment_retries=3` para tolerancia a falhas | SATISFEITO | Linhas 160-161 em download_audio; ausente em check_duration (correto — skip_download=True) |
| PIPE-05 | 08-03 | Startup valida `__Secure-3PSID` e loga CRITICAL se ausente (nao-bloqueante) | SATISFEITO | `_check_cookies()` linhas 138-183; nao levanta excecao; log CRITICAL sem raise; chamada no lifespan linha 192 |
| DEPLOY-01 | 08-03 | `nixpacks.toml` na raiz configura ffmpeg como dependencia do sistema Railway | SATISFEITO | Arquivo presente; `aptPkgs = ["ffmpeg"]` na linha 7 |

**Todos os 6 requisitos da fase satisfeitos (cobertura local completa).**

**Verificacao de requisitos orfaos:** PIPE-06 (Phase 10) e PIPE-07 (Phase 10), DEPLOY-02 (Phase 9) e DEPLOY-03 (Phase 9) nao sao desta fase — sem orfaos.

---

### Anti-Patterns Found

| Arquivo | Linha | Padrao | Severidade | Impacto |
|---------|-------|--------|------------|---------|
| Nenhum | — | — | — | — |

Varredura executada em `pipeline.py`, `api/main.py`, `nixpacks.toml` e `tests/test_pipeline_fixes.py`. Sem TODO/FIXME, sem return null/return [], sem handlers vazios, sem implementacoes stub.

---

### Human Verification Required

#### 1. Railway Container — ffprobe no PATH

**Test:** Fazer deploy no Railway com o nixpacks.toml atual e abrir um Railway Shell (ou adicionar uma rota de debug temporaria) e executar `ffprobe -version`
**Expected:** Comando retorna versao do ffprobe sem "command not found" (ex: `ffprobe version 6.1.x`)
**Why human:** O nixpacks.toml esta presente e correto (`aptPkgs = ["ffmpeg"]`), mas a verificacao de que o build do Railway realmente instala ffmpeg no container requer um deploy real no PaaS Railway. Nao ha como simular o build nixpacks localmente sem a plataforma Railway.

#### 2. Download de Beat sem Erros de Cache nsig

**Test:** Em uma instancia Railway recem-deployada (ou apos limpar manualmente o cache do yt-dlp com `yt-dlp --rm-cache-dir`), submeter uma URL de beat do YouTube via `POST /jobs` e aguardar conclusao
**Expected:** Job atinge `status=done` com WAV disponivel; logs do Celery worker nao mostram erros como "nsig extraction failed" ou "WARNING: nsig is too long"
**Why human:** O fix `no_cache_dir: True` previne que yt-dlp use cache de JavaScript entre deploys, mas a verificacao requer uma instancia Railway com Celery worker ativo, Redis, e cookies validos — todos servicos externos. A corretude local do codigo foi verificada via inspecao de fonte.

---

### Gaps Summary

Nenhuma lacuna bloqueante identificada. O codigo esta correto e todos os 8 testes passam. Os dois criterios de sucesso restantes (SC2 e SC4) requerem verificacao humana com ambiente Railway ativo — sao verificacoes de integracao de deploy, nao falhas de implementacao.

---

## Detalhes de Verificacao por Nivel

### pipeline.py — 4 niveis

**Nivel 1 (existe):** VERIFICADO — arquivo presente, sintaxe valida (`python -c "import pipeline"` sem erro)

**Nivel 2 (substantivo):** VERIFICADO — 544 linhas, logica de producao completa; sem stubs, placeholders ou retornos vazios nas funcoes modificadas

**Nivel 3 (conectado):** VERIFICADO — `_FFMPEG_DIR` usado em `ffmpeg_location` em ambas as funcoes; `_FFPROBE_PATH` usado em `validate_wav` via subprocess (linha 251); `shutil.which` conectado ao resultado final

**Nivel 4 (dados fluindo):** NAO APLICAVEL — nao e componente que renderiza dados dinamicos de usuario; e logica de configuracao de modulo e opcoes de yt-dlp

### api/main.py — 4 niveis

**Nivel 1 (existe):** VERIFICADO

**Nivel 2 (substantivo):** VERIFICADO — `_check_cookies` tem 46 linhas com 4 branches de validacao; nenhum e stub

**Nivel 3 (conectado):** VERIFICADO — chamada no lifespan (linha 192) apos `_check_redis_auth`, antes do sweeper thread

**Nivel 4 (dados fluindo):** NAO APLICAVEL — validacao de startup sem dados de usuario

### nixpacks.toml — 4 niveis

**Nivel 1 (existe):** VERIFICADO — arquivo na raiz do projeto

**Nivel 2 (substantivo):** VERIFICADO — conteudo correto com `aptPkgs = ["ffmpeg"]` e comentario explicativo; nao e arquivo vazio

**Nivel 3 (conectado):** VERIFICADO via design — nixpacks.toml e lido automaticamente pelo Railway durante build se presente na raiz; sem wiring adicional necessario no codigo

**Nivel 4 (dados fluindo):** REQUER HUMANO — verificacao de que Railway efetivamente instala ffmpeg so e possivel em deploy real

---

_Verified: 2026-05-11T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
