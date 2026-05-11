---
phase: 09-railway-bgutil-deployment
verified: 2026-05-11T19:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
deferred:
  - truth: "GET /files/{id} streams WAV que pode ser aberto num DAW (Phase 10 SC #3)"
    addressed_in: "Phase 10"
    evidence: "Phase 10 success criteria #3: 'GET /files/{id} on a completed Railway job streams a WAV that can be opened in a DAW (not a 0-byte file or an HTML error page)'"
---

# Phase 9: Railway bgutil Deployment — Verification Report

**Phase Goal:** Deploy bgutil service no Railway e configurar BGUTIL_BASE_URL em ambos os servicos (Uvicorn e Celery Worker), completando o setup de autenticacao YouTube para o pipeline de producao.
**Verified:** 2026-05-11T19:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

Esta fase foi de **verificacao**, nao de configuracao. Todo o escopo de DEPLOY-02 e DEPLOY-03 era
confirmar que o bgutil esta rodando e que BGUTIL_BASE_URL esta injetado em ambos os servicos.
A evidencia primaria esta em `09-01-SMOKE-TEST.md`.

### Observable Truths

| #  | Truth                                                                                          | Status     | Evidence                                                                                                     |
|----|-----------------------------------------------------------------------------------------------|------------|--------------------------------------------------------------------------------------------------------------|
| 1  | Deployment do Celery Worker atingiu SUCCESS no Railway                                         | VERIFIED   | deployment_status: SUCCESS, id 2d871c8e, confirmado no SMOKE-TEST Task 1                                     |
| 2  | Deployment do Uvicorn atingiu SUCCESS no Railway                                               | VERIFIED   | deployment_status: SUCCESS, id 498fa759, confirmado no SMOKE-TEST Task 2                                     |
| 3  | Logs de startup do Uvicorn sem strings proibidas de bgutil                                     | VERIFIED   | Gate checks Task 2: "BGUTIL_BASE_URL not set", "connection refused", "ConnectionRefusedError" ausentes nos logs de startup |
| 4  | Logs de startup do Celery Worker sem strings proibidas de bgutil                               | VERIFIED   | Gate checks Task 1: todas as 5 strings proibidas ausentes nos logs de startup                                |
| 5  | URL publica do Uvicorn conhecida e /health responde HTTP 200                                   | VERIFIED   | https://soundgrabber-test.up.railway.app — curl /health retornou 200 {"status":"ok"} (SMOKE-TEST Task 3)     |
| 6  | POST /jobs com URL real do YouTube retorna status=done com bpm e key em ate 5 minutos          | VERIFIED   | job a4e8e300: status=done em ~22s, bpm=116, key=G major, camelot=9B (SMOKE-TEST Task 4)                     |
| 7  | BGUTIL_BASE_URL=http://bgutil.railway.internal:4416 configurado em Uvicorn e Celery Worker     | VERIFIED   | Provado indiretamente: yt-dlp baixou 2.88MiB via bgutil/PO Token sem erros; logs de startup limpos em ambos |

**Score:** 7/7 truths verified

---

### Roadmap Success Criteria (Phase 9)

| SC | Criterio                                                                              | Status   | Evidence                                                                                      |
|----|--------------------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------|
| 1  | bgutil healthy na porta 4416 interna                                                  | VERIFIED | Pipeline baixou 2.88MiB; download logs mostram yt-dlp usando bgutil/PO Token sem erro        |
| 2  | BGUTIL_BASE_URL setado em web-service e celery-worker                                 | VERIFIED | api/config.py le BGUTIL_BASE_URL; api/tasks.py passa para check_duration e download_audio; pipeline funcional prova injecao correta |
| 3  | Logs sem "BGUTIL_BASE_URL not set" ou connection-refused em ambos os servicos         | VERIFIED | Gate checks explicitamente documentados em Tasks 1 e 2 do SMOKE-TEST, todos PASS             |

---

### Required Artifacts

| Artifact                                                              | Expected                                                               | Status   | Details                                                                                       |
|-----------------------------------------------------------------------|------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------|
| `.planning/phases/09-railway-bgutil-deployment/09-01-SMOKE-TEST.md`  | Log estruturado com status dos 4 tasks, trechos de log, job_id, bpm   | VERIFIED | Arquivo existe, 216 linhas, contém todas as 4 secoes de task com evidencias concretas         |

---

### Key Link Verification

| From                                      | To                                      | Via                                                  | Status   | Details                                                                                     |
|-------------------------------------------|-----------------------------------------|------------------------------------------------------|----------|---------------------------------------------------------------------------------------------|
| Uvicorn service (248e8eaf)                | bgutil service (2fc3a8a5)               | BGUTIL_BASE_URL=http://bgutil.railway.internal:4416  | VERIFIED | api/config.py:52 le env var; api/tasks.py:57,61 passa para pipeline; download bem-sucedido |
| Celery Worker service (145135bf)          | bgutil service (2fc3a8a5)               | BGUTIL_BASE_URL=http://bgutil.railway.internal:4416  | VERIFIED | Mesmo codigo de configuracao; logs de startup limpos; download 2.88MiB confirma conexao     |
| POST /jobs no Uvicorn                     | GET /jobs/{id} status=done via polling  | Celery worker consome fila Redis, executa pipeline   | VERIFIED | job a4e8e300: 4 polls de 5s, transicao para status=done em 22s                             |

---

### Data-Flow Trace (Level 4)

| Artifact      | Data Variable      | Source                                | Produces Real Data | Status   |
|---------------|--------------------|---------------------------------------|--------------------|----------|
| api/tasks.py  | bgutil_base_url    | settings.bgutil_base_url (config.py)  | Sim — env var Railway preenchida | FLOWING  |
| pipeline.py   | bgutil_base_url    | parametro passado por tasks.py        | Sim — usado em extractor_args youtube | FLOWING  |

---

### Behavioral Spot-Checks

| Behavior                                                    | Command                                                                                      | Result                                        | Status |
|-------------------------------------------------------------|----------------------------------------------------------------------------------------------|-----------------------------------------------|--------|
| /health retorna 200                                         | curl /health (documentado no smoke test Task 3)                                              | HTTP 200 {"status":"ok"}                      | PASS   |
| Pipeline E2E: POST /jobs → status=done                     | POST /jobs + polling (documentado no smoke test Task 4)                                      | status=done em 22s, bpm=116, key=G major      | PASS   |
| bgutil operacional (download via PO Token)                  | Logs Celery: [download] 100% of 2.88MiB (documentado no smoke test Task 4 — logs RUN)       | 2.88MiB baixados sem erro                     | PASS   |

---

### Probe Execution

Nao aplicavel — esta fase nao possui scripts de probe. Verificacao foi realizada via MCP Railway e documentada em 09-01-SMOKE-TEST.md.

---

### Requirements Coverage

| Requirement | Source Plan  | Descricao                                                        | Status     | Evidence                                                                                                 |
|-------------|-------------|------------------------------------------------------------------|------------|----------------------------------------------------------------------------------------------------------|
| DEPLOY-02   | 09-01-PLAN  | bgutil rodando na porta 4416 interna, acessivel via private net  | SATISFIED  | yt-dlp baixou 2.88MiB sem erro usando bgutil; smoke test status=done confirma bgutil operacional        |
| DEPLOY-03   | 09-01-PLAN  | BGUTIL_BASE_URL configurado em celery-worker e web-service       | SATISFIED  | api/config.py:52 le env var; api/tasks.py:57,61 passa para pipeline; logs de startup sem "not set"      |

---

### Deferred Items

Itens nao cobertos por esta fase, explicitamente endereçados em fases posteriores do milestone.

| # | Item                                                                      | Addressed In | Evidence                                                                                                                     |
|---|---------------------------------------------------------------------------|-------------|------------------------------------------------------------------------------------------------------------------------------|
| 1 | GET /files/{id} retorna 410 (containers separados com /tmp isolados)       | Phase 10    | Phase 10 SC #3: "GET /files/{id} on a completed Railway job streams a WAV that can be opened in a DAW (not a 0-byte file)" |

---

### Anti-Patterns Found

| File                          | Line | Pattern                   | Severity | Impact |
|-------------------------------|------|---------------------------|----------|--------|
| 09-01-SMOKE-TEST.md (Task 4)  | 208  | WAV download BLOQUEADO 410 | INFO     | Bug arquitetural documentado; nao e requisito de Phase 9; deferred para Phase 10 (SC #3). Nao afeta DEPLOY-02/DEPLOY-03. |

Nenhum marcador TBD/FIXME/XXX encontrado em arquivos modificados pela fase.

---

### Human Verification Required

Nenhuma verificacao humana necessaria. O smoke test end-to-end (Task 4) foi executado pelo operador humano (forneceu URL real do YouTube) e o resultado foi documentado em 09-01-SMOKE-TEST.md. Todos os gates foram verificados programaticamente com evidencias concretas no arquivo de smoke test.

---

### Gaps Summary

Nenhum gap identificado. Os 3 success criteria do ROADMAP para Phase 9 foram todos verificados com evidencia direta em 09-01-SMOKE-TEST.md.

O WAV download (HTTP 410) nao e um gap da Phase 9 — DEPLOY-02 e DEPLOY-03 sao sobre bgutil e BGUTIL_BASE_URL, nao sobre o endpoint de download. O pipeline internamente funcionou: Celery Worker logs confirmam download de 2.88MiB via bgutil/PO Token e criacao de WAV em /tmp/sg_*.wav. O problema de /tmp isolado entre containers e explicitamente coberto pela Phase 10 SC #3.

---

**Nota sobre o automated verify do PLAN (Task 4):** O comando grep do plano tinha dois problemas de design: (a) as strings proibidas aparecem na propria secao de gate checklist do smoke test (em linhas como `"BGUTIL_BASE_URL not set" → ausente ✓`), causando falso-positivo no grep negativo; (b) esperava campo `wav_url:` mas a API retorna `download_url:`, e esperava `file_size_bytes:` que nao foi registrado porque o download retornou 410. Estas sao falhas no design do grep de verificacao automatica do plano, nao falhas nos requisitos da fase. Os success criteria do ROADMAP (que sao o contrato nao-negociavel) estao todos satisfeitos.

---

_Verified: 2026-05-11T19:00:00Z_
_Verifier: Claude (gsd-verifier)_
