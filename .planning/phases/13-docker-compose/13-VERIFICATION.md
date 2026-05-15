---
phase: 13-docker-compose
verified: 2026-05-15T19:00:00Z
status: human_needed
score: 9/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Pare um dos serviços com `docker compose stop api` e aguarde 10-15 segundos. Verifique com `docker compose ps` que o serviço reiniciou automaticamente."
    expected: "O serviço api deve aparecer como `Up` ou `Restarting` em menos de 30 segundos, confirmando que restart: unless-stopped está ativo em runtime — não apenas declarado no config."
    why_human: "A ROADMAP SC 2 exige confirmação de restart automático observado após parada intencional. grep no docker-compose.yml confirma a declaração, mas o comportamento real de restart requer observação humana do daemon Docker."
---

# Phase 13: Docker Compose — Relatório de Verificação

**Phase Goal:** A three-service Docker Compose stack (api, worker, redis) runs on the notebook with a standard x86_64 image, system ffmpeg, Essentia functional, and a shared tmpfs volume so WAV files written by the worker are served by the api
**Verificado:** 2026-05-15T19:00:00Z
**Status:** human_needed
**Re-verification:** Não — verificação inicial

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                                       | Status      | Evidência                                                                                                                                        |
|----|-----------------------------------------------------------------------------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | `docker build -t soundgrabber:latest .` completa sem erro e Gate D-07 (`import essentia.standard, yt_dlp, fastapi, celery; print('OK')`) retorna exit 0 | ✓ VERIFIED  | SUMMARY 13-03 registra output exato do Gate D-07 com exit 0. Commits `65ef35a` (.dockerignore) e `852e382` (Dockerfile) existem no repositório. |
| 2  | `docker compose ps` mostra serviços em estado running/healthy com `restart: unless-stopped` — confirmado parando um serviço e observando restart automático | ? UNCERTAIN | `restart: unless-stopped` declarado para os 4 serviços no docker-compose.yml (verificado via grep). SUMMARY 13-04 documenta `docker inspect ... RestartPolicy.Name = unless-stopped`. Porém o ROADMAP SC 2 exige observação humana de restart automático após parada intencional — não verificável por grep. |
| 3  | WAV escrito pelo worker em `/tmp` é imediatamente legível pelo api no mesmo path via volume `sg_tmp` compartilhado              | ✓ VERIFIED  | SUMMARY 13-04 Gate DEPLOY-06: `docker compose exec worker touch /tmp/sg_test.txt` exit 0; `docker compose exec api ls -la /tmp/sg_test.txt` lista o arquivo com saída `-rw-r--r-- 1 root root 0 May 15 18:10 /tmp/sg_test.txt`. |

**Score parcial (truths):** 2/3 verificados automaticamente; 1 depende de confirmação humana

---

### Must-Haves dos PLANs (DEPLOY-04 / DEPLOY-05 / DEPLOY-06)

| #  | Must-Have                                                                                           | Status      | Evidência                                                                                                              |
|----|-----------------------------------------------------------------------------------------------------|-------------|------------------------------------------------------------------------------------------------------------------------|
| 1  | requirements.txt não contém `imageio-ffmpeg` nem `librosa`                                          | ✓ VERIFIED  | `grep -c "^librosa" requirements.txt` = 0; `grep -c "^imageio-ffmpeg" requirements.txt` = 0; `wc -l` = 15 linhas     |
| 2  | pipeline.py não importa `imageio_ffmpeg` nem `librosa`                                              | ✓ VERIFIED  | `grep -c "librosa" pipeline.py` = 0; `grep -c "imageio_ffmpeg" pipeline.py` = 0                                       |
| 3  | pipeline.py.detect_tuning() funciona via Essentia (SpectralPeaks + TuningFrequency)                 | ✓ VERIFIED  | `grep -c "es.SpectralPeaks" pipeline.py` = 1; `grep -c "es.TuningFrequency" pipeline.py` = 1; `grep -c "es.Windowing" pipeline.py` = 1; implement. completa em linhas 400–436 |
| 4  | Pipeline preserva contrato público: check_duration, download_audio, convert_to_wav, validate_wav, detect_tuning, detect_bpm, detect_key, key_to_camelot, analyze_audio, CAMELOT, MAX_DURATION_SEC | ✓ VERIFIED  | Todas as 9 funções e 2 constantes presentes em pipeline.py (verificado via grep de definições) |
| 5  | tests/test_pipeline_docker.py com 3 testes GREEN após refatoração                                   | ✓ VERIFIED  | Arquivo existe (66 linhas); `grep -c "^def test_"` = 3; SUMMARY 13-02 registra `pytest tests/test_pipeline_docker.py -x -q` → 3 passed in 1.37s; commits existem |
| 6  | Dockerfile usa python:3.11-slim; ffmpeg, libsndfile1, curl, nodejs (NodeSource setup_20.x) via apt; pip install --no-cache-dir; CMD uvicorn | ✓ VERIFIED  | `grep "^FROM python:3.11-slim" Dockerfile` = 1; `grep "ffmpeg" Dockerfile` = 2; `grep "libsndfile1" Dockerfile` = 1; `grep "nodesource.com/setup_20" Dockerfile` = 1; `grep "pip install --no-cache-dir -r requirements.txt" Dockerfile` = 1; CMD correto |
| 7  | .dockerignore exclui .venv/, .git/, cookies.txt, .env, .planning/                                   | ✓ VERIFIED  | Todas as entradas críticas confirmadas: .venv/(1), .git/(1), cookies.txt(1), .env(2 entradas: .env e .env.local), .planning/(1), dump.rdb(1), .claude/(1), www.youtube.com_cookies*(1); total 40 linhas |
| 8  | docker-compose.yml define 4 serviços com restart: unless-stopped, rede bridge, volume sg_tmp tmpfs compartilhado | ✓ VERIFIED  | `grep -c "restart: unless-stopped" docker-compose.yml` = 4 (diretivas — linha do comentário no header não conta como diretiva YAML); `grep -c "sg_tmp:/tmp"` = 2 (api e worker); `grep -c "type: tmpfs"` = 1; `grep -c "mode=1777"` = 1; `grep -c "soundgrabber_net"` = 5; `grep -c "privileged"` = 0; `grep -c "network_mode: host"` = 0 |
| 9  | .env.example documenta REDIS_URL, DEV_MODE=true, BGUTIL_BASE_URL com hostnames do compose; legado YTDLP_COOKIES_FILE/YTDLP_PO_TOKEN removido | ✓ VERIFIED  | Todas as variáveis presentes: REDIS_URL=redis://redis:6379/0, DEV_MODE=true, BGUTIL_BASE_URL=http://bgutil:4416, YTDLP_CACHE_DIR=, RATE_LIMIT_PER_MINUTE=, WAV_TTL_SECONDS=, ADMIN_PASSWORD=; `grep -c "YTDLP_COOKIES_FILE\|YTDLP_PO_TOKEN"` = 0 |
| 10 | restart: unless-stopped confirmado por observação de restart automático após parada intencional     | ? UNCERTAIN | Ver seção Human Verification Required |

**Score:** 9/10 must-haves verificados automaticamente

---

### Required Artifacts

| Artifact                           | Expected                                        | Status      | Detalhes                                                                                                      |
|------------------------------------|-------------------------------------------------|-------------|---------------------------------------------------------------------------------------------------------------|
| `tests/test_pipeline_docker.py`    | 3 testes RED→GREEN para DEPLOY-04               | ✓ VERIFIED  | 66 linhas; 3 funções de teste; AST import inspection implementada; integração Essentia funcional              |
| `requirements.txt`                 | Sem imageio-ffmpeg e librosa; com essentia       | ✓ VERIFIED  | 15 linhas; essentia==2.1b6.dev1389 presente; targets removidos                                               |
| `pipeline.py`                      | shutil.which fail-fast; detect_tuning via Essentia | ✓ VERIFIED | 641 linhas; fail-fast com RuntimeError em linhas 43-57; detect_tuning reescrita em linhas 400-436             |
| `Dockerfile`                       | python:3.11-slim + system ffmpeg + Node 20 + pip | ✓ VERIFIED  | 26 linhas; estrutura correta; camada de cache de requirements antes de COPY . .                               |
| `.dockerignore`                    | >= 15 entradas incluindo .venv/, cookies, .env  | ✓ VERIFIED  | 40 linhas; todas as exclusões críticas presentes                                                              |
| `docker-compose.yml`               | 4 serviços + rede bridge + volume tmpfs sg_tmp  | ✓ VERIFIED  | 73 linhas; estrutura completa; api único com ports:; worker com celery command correto                        |
| `.env.example`                     | Template com variáveis do compose               | ✓ VERIFIED  | 27 linhas; todas as 10 variáveis documentadas; legado removido                                                |

---

### Key Link Verification

| From                              | To                                   | Via                                    | Status      | Detalhes                                                                             |
|-----------------------------------|--------------------------------------|----------------------------------------|-------------|--------------------------------------------------------------------------------------|
| `tests/test_pipeline_docker.py`   | `pipeline.py`                        | ast.parse + import inspection          | ✓ WIRED     | `_pipeline_import_names()` usa ast.parse/walk; testes assertam ausência de imports  |
| `pipeline.py`                     | `shutil.which("ffmpeg")`             | _system_ffmpeg / _YTDLP_FFMPEG_LOCATION | ✓ WIRED    | Linhas 52-57; fail-fast RuntimeError; `grep -c "shutil.which" pipeline.py` = 3       |
| `pipeline.py.detect_tuning`       | `essentia.standard.TuningFrequency`  | SpectralPeaks → TuningFrequency        | ✓ WIRED     | Linhas 418-435; encadeamento completo MonoLoader→Windowing→Spectrum→SpectralPeaks→TuningFrequency |
| `Dockerfile`                      | `requirements.txt`                   | COPY requirements.txt . + pip install  | ✓ WIRED     | Linhas 19-20; COPY antes de COPY . . confirma cache layer                            |
| `Dockerfile`                      | nodejs 20 via NodeSource             | curl https://deb.nodesource.com/setup_20.x | ✓ WIRED | Linha 11; `grep -c "nodesource.com/setup_20" Dockerfile` = 1                        |
| `Dockerfile CMD`                  | `api/main.py`                        | uvicorn api.main:app                   | ✓ WIRED     | Linha 26 do Dockerfile; CMD exec form correto                                        |
| `docker-compose.yml worker`       | `docker-compose.yml api`             | Volume sg_tmp:/tmp nos dois serviços   | ✓ WIRED     | Linhas 53 (api) e 67 (worker); mesmo volume nomeado                                  |
| `docker-compose.yml api/worker`   | `docker-compose.yml redis`           | REDIS_URL=redis://redis:6379/0         | ✓ WIRED     | env_file: .env em ambos; .env.example tem REDIS_URL=redis://redis:6379/0             |
| `docker-compose.yml api/worker`   | `docker-compose.yml bgutil`          | BGUTIL_BASE_URL=http://bgutil:4416     | ✓ WIRED     | .env.example tem BGUTIL_BASE_URL=http://bgutil:4416                                  |

---

### Data-Flow Trace (Level 4)

Não aplicável — esta fase produz infraestrutura (Dockerfile, docker-compose, refactor de pipeline). Não há componente que renderize dados dinâmicos de uma fonte de dados a rastrear.

---

### Behavioral Spot-Checks

| Comportamento                                    | Comando                                                           | Resultado                                | Status   |
|--------------------------------------------------|-------------------------------------------------------------------|------------------------------------------|----------|
| pipeline.py importa sem erro                     | `python -c "import pipeline; print(pipeline.detect_tuning)"`     | Documentado em SUMMARY 13-02 (exit 0)   | ✓ PASS   |
| 3 testes Docker GREEN após Plan 02               | `pytest tests/test_pipeline_docker.py -x -q`                     | Documentado em SUMMARY 13-02 (3 passed in 1.37s) | ✓ PASS |
| Contrato público preservado (todas as funções)   | `grep "^def " pipeline.py` (9 funções + constantes)              | 9 funções + CAMELOT + MAX_DURATION_SEC presentes | ✓ PASS |
| Arquivo de compose válido                        | `grep -c "restart: unless-stopped" docker-compose.yml` = 4       | 4 (diretivas, excluindo comentário)      | ✓ PASS   |

---

### Probe Execution

Nenhum probe convencional (`scripts/*/tests/probe-*.sh`) declarado para esta fase.

---

### Requirements Coverage

| Requisito    | Plano Fonte   | Descrição                                                                  | Status      | Evidência                                                                                        |
|--------------|---------------|----------------------------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------|
| DEPLOY-04    | 13-02, 13-03  | Dockerfile usa python:3.11-slim com system ffmpeg — sem imageio-ffmpeg, sem NUMBA_DISABLE_JIT | ✓ SATISFIED | Dockerfile verificado; `grep -v '^#' Dockerfile | grep -c "imageio-ffmpeg\|NUMBA"` = 0; requirements.txt limpo |
| DEPLOY-05    | 13-04         | docker-compose.yml com api, worker, redis e `restart: unless-stopped`    | ✓ SATISFIED | 4 serviços no compose; 4 entradas restart:unless-stopped; worker com --concurrency=1 --max-tasks-per-child=10 |
| DEPLOY-06    | 13-04         | api e worker compartilham volume tmpfs em `/tmp`                          | ✓ SATISFIED | sg_tmp:/tmp em api e worker; Gate DEPLOY-06 documentado em SUMMARY 13-04 com saída do `ls -la`  |

---

### Anti-Patterns Found

| Arquivo                      | Linha | Padrão              | Severidade  | Impacto                                                      |
|------------------------------|-------|---------------------|-------------|--------------------------------------------------------------|
| Nenhum encontrado            | -     | -                   | -           | Nenhum TBD/FIXME/XXX/placeholder nos arquivos modificados    |

Scan executado em: `pipeline.py`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `requirements.txt`, `tests/test_pipeline_docker.py`. Nenhum debt marker sem referência encontrado.

---

### Human Verification Required

#### 1. Restart Automático — ROADMAP SC 2

**Test:** Com a stack rodando (`docker compose ps` mostrando 4 serviços `Up`), execute:
```
docker compose stop api
sleep 20
docker compose ps
```
**Expected:** O serviço `api` deve reaparecer no estado `Up` sem intervenção manual, demonstrando que `restart: unless-stopped` está ativo no daemon Docker (não apenas declarado na config).
**Why human:** O ROADMAP SC 2 exige confirmação de restart automático "confirmado por deliberadamente parar um serviço e observar restart automático". A declaração `restart: unless-stopped` no docker-compose.yml foi verificada programaticamente, mas o comportamento em runtime requer observação direta do operador. Nota: `docker inspect` no SUMMARY 13-04 confirmou `RestartPolicy.Name = unless-stopped`, mas não demonstrou restart real.

---

### Gaps Summary

Nenhum gap bloqueante identificado. Os 3 requisitos obrigatórios (DEPLOY-04, DEPLOY-05, DEPLOY-06) têm evidência de implementação completa no código e nos artefatos de infraestrutura. O único item pendente é uma confirmação comportamental de runtime (restart automático) que requer observação humana conforme exigido pelo ROADMAP Success Criterion 2.

**Nota sobre discrepância de nomenclatura:** O ROADMAP Phase 13 goal descreve "three-service stack (api, worker, redis)" mas o docker-compose.yml implementa 4 serviços (adicionando `bgutil`). Isso não é um gap — os PLANs 04 e o CONTEXT.md especificaram explicitamente 4 serviços, e o `bgutil` é necessário para a funcionalidade de PO Token do yt-dlp. O ROADMAP goal usa linguagem simplificada; os Success Criteria não restringem a 3 serviços.

---

_Verificado: 2026-05-15T19:00:00Z_
_Verifier: Claude (gsd-verifier)_
