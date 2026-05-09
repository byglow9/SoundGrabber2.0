---
phase: 06-application-security
verified: 2026-05-09T19:05:34Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: null
gaps: []
deferred: []
human_verification: []
---

# Phase 6: Application Security — Relatório de Verificação

**Meta da Fase:** Todos os controles de segurança em nível de aplicação estão aplicados em código e verificados por testes automatizados, com política documentada como regra obrigatória do projeto.
**Verificado em:** 2026-05-09T19:05:34Z
**Status:** PASSED
**Re-verificação:** Não — verificação inicial

---

## Realização da Meta

### Verdades Observáveis (Success Criteria do ROADMAP)

| # | Verdade | Status | Evidência |
|---|---------|--------|-----------|
| 1 | WAV files em /tmp criados com modo 0o600; stat() não mostra bits de leitura/escrita para group ou others | VERIFICADO | `os.chmod(wav_path, 0o600)` na linha 163 de `pipeline.py`, imediatamente antes de `return wav_path`. `import os` na linha 21. `test_wav_file_permissions` PASSOU. |
| 2 | start.sh não pode ser executado por outros usuários além do dono; ls -l mostra -rwxr-x--- (750) | VERIFICADO | `chmod 750 "$(realpath "$0")"` na linha 5 de `start.sh`, após `set -e`. `bash -n start.sh` retorna 0 (sintaxe válida). `test_startsh_permissions` PASSOU. |
| 3 | GET /jobs/{id} e GET /files/{id} rejeitam IP único após 60 e 10 req/min com 429 | VERIFICADO | `@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")` na linha 237 de `api/main.py`; `@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")` na linha 294. Ambas as assinaturas incluem `request: Request, response: Response`. `test_rate_limit_get_jobs` e `test_rate_limit_get_files` PASSARAM. |
| 4 | GET /health retorna 200 com Redis ok quando saudável e 503 quando Redis inacessível | VERIFICADO | Rota `@app.get("/health")` na linha 336 de `api/main.py`. `_redis.ping()` captura `ConnectionError`/`TimeoutError` → 503. `test_health_redis_ok` e `test_health_redis_down` PASSARAM. |
| 5 | pytest tests/test_security.py passa todos os testes para body size limit, security headers, docs disabled, queue depth, rate limits em /jobs e /files | VERIFICADO | `12 passed in 2.04s` — 100% aprovado. Sem falhas. |

**Pontuação:** 5/5 verdades verificadas

---

### Artefatos Obrigatórios

| Artefato | Esperado | Status | Detalhes |
|----------|----------|--------|----------|
| `pipeline.py` | `os.chmod(wav_path, 0o600)` em `download_audio()` antes de `return wav_path`; `import os` no topo do módulo | VERIFICADO | Linha 21: `import os`; Linha 163: `os.chmod(wav_path, 0o600)`. Padrão correto: após confirmar existência do arquivo via `.exists()`. |
| `start.sh` | `chmod 750 "$(realpath "$0")"` após `set -e`; sintaxe bash válida | VERIFICADO | Linha 5: `chmod 750 "$(realpath "$0")"`. `bash -n start.sh` retorna 0. |
| `api/config.py` | Campos `job_poll_rate_limit_per_minute` (default 60) e `file_download_rate_limit_per_minute` (default 10) em `Settings` | VERIFICADO | Linhas 32-34. Env vars `JOB_POLL_RATE_LIMIT_PER_MINUTE` e `FILE_DOWNLOAD_RATE_LIMIT_PER_MINUTE` suportadas via `_safe_int`. Importação e valores padrão verificados programaticamente. |
| `api/main.py` | `@limiter.limit` em `get_job` e `download_file`; assinaturas com `request: Request, response: Response`; rota `GET /health` com `_redis.ping()` | VERIFICADO | Linhas 237-238 (`get_job`), 294-295 (`download_file`), 336-343 (`health_check`). App importado com sucesso; `/health` presente nas rotas registradas. |
| `tests/test_security.py` | 10 funções de teste cobrindo SEC-FILE-01/02, SEC-API-01/02/03, SEC-TEST-01..05; 12 testes coletados via parametrize | VERIFICADO | 10 funções `def test_*` confirmadas. `pytest --collect-only` coleta 12 testes. `12 passed in 2.04s`. |
| `README.md` | Seção `## Pre-Deploy Security Audit` com `pip install pip-audit` e `pip-audit -r requirements.txt` antes de `## License` | VERIFICADO | Linhas 176-193. Seção aparece na linha 176, `## License` na linha 194. Ordem correta confirmada via awk. |
| `CLAUDE.md` | Seção `## Security Gate` entre `## Restrições críticas` e `## Próximo passo` com 6 subseções obrigatórias | VERIFICADO | Linha 55: `## Security Gate`. Posição confirmada (entre linhas 47 e 93 da estrutura). 6 subseções presentes (grep retornou 6). Arquivo com 97 linhas (era 59). |
| `.planning/SECURITY-CHECKLIST.md` | 193+ linhas, 8 seções numeradas, todos os 13 IDs SEC-* presentes | VERIFICADO | 193 linhas. 8 seções `## N.` confirmadas. Todos 13 IDs SEC-* encontrados (OK para cada um). |

---

### Verificação de Links-Chave (Wiring)

| De | Para | Via | Status | Detalhes |
|----|------|-----|--------|---------|
| `api/main.py::get_job` | `settings.job_poll_rate_limit_per_minute` | `@limiter.limit` decorator | CONECTADO | `@limiter.limit(f"{settings.job_poll_rate_limit_per_minute}/minute")` na linha 237 |
| `api/main.py::download_file` | `settings.file_download_rate_limit_per_minute` | `@limiter.limit` decorator | CONECTADO | `@limiter.limit(f"{settings.file_download_rate_limit_per_minute}/minute")` na linha 294 |
| `api/main.py::health_check` | `_redis.ping()` | `try/except (ConnectionError, TimeoutError)` | CONECTADO | Linha 340: `_redis.ping()`. Captura `ConnectionError` e `TimeoutError`. |
| `pipeline.py::download_audio` | `os.chmod(wav_path, 0o600)` | Chamada direta após `wav_path.exists()` | CONECTADO | Linha 163: `os.chmod(wav_path, 0o600)` antes de `return wav_path` |
| `CLAUDE.md::Security Gate` | `.planning/SECURITY-CHECKLIST.md` | Referência explícita em 2 subseções | CONECTADO | Linhas 82 e 86 do CLAUDE.md referenciam `.planning/SECURITY-CHECKLIST.md` |
| `README.md::Pre-Deploy Security Audit` | `pip-audit -r requirements.txt` | Comando exato documentado | CONECTADO | Linhas 181-182 do README.md |
| `.planning/SECURITY-CHECKLIST.md` | `tests/test_security.py` | 12 referências no checklist | CONECTADO | `grep -c "tests/test_security.py"` retornou 12 |

---

### Rastreio de Fluxo de Dados (Nível 4)

Não aplicável para esta fase — os artefatos são controles de segurança (permissões de arquivo, decoradores de rate limit, documentação). Não há componentes que renderizem dados dinâmicos de fontes externas que requeiram rastreio de fluxo.

---

### Spot-Checks Comportamentais

| Comportamento | Comando | Resultado | Status |
|---------------|---------|-----------|--------|
| Todos 12 testes de segurança passam | `pytest tests/test_security.py -v` | `12 passed in 2.04s` | PASSOU |
| Settings importável com defaults corretos | `python -c "from api.config import settings; assert settings.job_poll_rate_limit_per_minute == 60"` | Saiu 0 | PASSOU |
| App importável com rota /health registrada | `python -c "from api.main import app; assert any(getattr(r,'path','') == '/health' for r in app.routes)"` | `/health` presente | PASSOU |
| pipeline.py importável | `python -c "import pipeline"` | `pipeline import OK` | PASSOU |
| start.sh com sintaxe bash válida | `bash -n start.sh` | Saiu 0 | PASSOU |
| Suite completa sem regressões em código de produção | `pytest tests/ -m "not e2e and not integration"` | `1 failed, 46 passed` — falha pré-existente em `test_html_required_ids_present` (ID `download-area` ausente, documentada em 06-02-SUMMARY e 06-03-SUMMARY como fora do escopo desta fase) | PASSOU (sem regressões por esta fase) |

---

### Cobertura de Requisitos

| Requisito | Plano de Origem | Descrição | Status | Evidência |
|-----------|-----------------|-----------|--------|-----------|
| SEC-FILE-01 | 06-01, 06-02 | WAV files com permissões 0o600 | SATISFEITO | `os.chmod(wav_path, 0o600)` em pipeline.py linha 163; teste verde |
| SEC-FILE-02 | 06-01, 06-02 | start.sh com permissões 750 | SATISFEITO | `chmod 750 "$(realpath "$0")"` em start.sh linha 5; teste verde |
| SEC-API-01 | 06-01, 06-02 | GET /jobs/{id} rate limit 60/min | SATISFEITO | `@limiter.limit` em `get_job` com `job_poll_rate_limit_per_minute`; teste verde |
| SEC-API-02 | 06-01, 06-02 | GET /files/{id} rate limit 10/min | SATISFEITO | `@limiter.limit` em `download_file` com `file_download_rate_limit_per_minute`; teste verde |
| SEC-API-03 | 06-01, 06-02 | GET /health 200/503 baseado em Redis | SATISFEITO | Rota `/health` em api/main.py com `_redis.ping()`; testes ok/down verdes |
| SEC-TEST-01 | 06-01 | Teste body size limit 413 | SATISFEITO | `test_body_size_limit` PASSOU; middleware `_limit_body_size` em api/main.py |
| SEC-TEST-02 | 06-01 | Teste security headers | SATISFEITO | `test_security_headers` PASSOU; middleware `_security_headers` em api/main.py |
| SEC-TEST-03 | 06-01 | Teste /docs /redoc desabilitados | SATISFEITO | `test_docs_routes_disabled` (3 parametrize) PASSOU; `docs_url=None` em api/main.py |
| SEC-TEST-04 | 06-01 | Teste queue depth limit 503 | SATISFEITO | `test_queue_depth_limit` PASSOU; check `llen >= max_queue_depth` em submit_job |
| SEC-TEST-05 | 06-01 | Teste rate limits GET /jobs e /files | SATISFEITO | Coberto por SEC-API-01 e SEC-API-02; testes `test_rate_limit_get_jobs` e `test_rate_limit_get_files` PASSARAM |
| SEC-TEST-06 | 06-03 | pip-audit documentado no README | SATISFEITO | Seção `## Pre-Deploy Security Audit` em README.md com comandos exatos |
| SEC-POLICY-01 | 06-03 | Security Gate em CLAUDE.md | SATISFEITO | Seção `## Security Gate` em CLAUDE.md linha 55 com 6 subseções obrigatórias |
| SEC-POLICY-02 | 06-03 | SECURITY-CHECKLIST.md existe e cobre todos os controles | SATISFEITO | `.planning/SECURITY-CHECKLIST.md` com 193 linhas, 8 seções, todos 13 IDs SEC-* |

**Cobertura: 13/13 requisitos satisfeitos.**

---

### Anti-Padrões Encontrados

Nenhum anti-padrão bloqueador identificado nos arquivos modificados pela fase.

| Arquivo | Linha | Padrão | Severidade | Impacto |
|---------|-------|--------|------------|---------|
| — | — | — | — | — |

**Observação sobre `import os` duplicado em pipeline.py:** O `import os` do bloco `if __name__ == "__main__":` (linha 453) é redundante com o `import os` do topo do módulo (linha 21), mas não é anti-padrão bloqueador — apenas código desnecessário que não afeta comportamento.

---

### Necessidades de Verificação Humana

Nenhum item requer verificação humana para confirmar o objetivo desta fase.

---

### Resumo

**Meta da fase alcançada com sucesso.**

Todos os 5 success criteria do ROADMAP foram verificados no codebase real:

1. `pipeline.py::download_audio()` aplica `os.chmod(wav_path, 0o600)` antes de retornar o caminho do WAV — protege contra leitura por outros usuários do sistema.

2. `start.sh` auto-aplica `chmod 750 "$(realpath "$0")"` como primeira instrução executável após `set -e` — garante permissões restritivas a cada execução.

3. `GET /jobs/{id}` e `GET /files/{id}` têm decoradores `@limiter.limit` com valores externalizados em `api/config.py` (`job_poll_rate_limit_per_minute=60` e `file_download_rate_limit_per_minute=10`). Assinaturas incluem `request: Request, response: Response` (requisito do slowapi).

4. `GET /health` implementada com `_redis.ping()` e tratamento de `ConnectionError`/`TimeoutError` — retorna 200/503 conforme estado do Redis.

5. `tests/test_security.py` com 12 testes (10 funções + parametrize): todos aprovados (`12 passed in 2.04s`).

Política de segurança documentada em 3 artefatos: `README.md` (pip-audit pré-deploy), `CLAUDE.md` (Security Gate com 6 categorias de controles obrigatórios), `.planning/SECURITY-CHECKLIST.md` (checklist com 8 seções cobrindo todos os 13 SEC-*).

Commits verificados: `555eb0b`, `e89581d`, `a1f9cbb`, `16a5ed1`, `ba40068` — todos existentes no histórico git.

A única falha na suite completa (`test_html_required_ids_present` — ID `download-area` ausente) é pré-existente à Phase 6, documentada explicitamente como fora do escopo nos 06-02-SUMMARY e 06-03-SUMMARY. Não é regressão introduzida por esta fase.

---

_Verificado em: 2026-05-09T19:05:34Z_
_Verificador: Claude (gsd-verifier)_
