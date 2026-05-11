# Phase 10: Failure Hardening and E2E Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 10-failure-hardening-and-e2e-validation
**Areas discussed:** WAV entre containers, Detecção de bgutil down, Mensagem de erro explícita, Cobertura de testes PIPE-06, Estratégia E2E Railway (PIPE-07)

---

## WAV entre containers (bug arquitetural identificado em Phase 9)

*Esta área surgiu do freeform do usuário durante a seleção de áreas — não estava no menu inicial.*

| Option | Description | Selected |
|--------|-------------|----------|
| Redis como store de bytes | Worker armazena bytes do WAV no Redis (mesma TTL). Web service lê do Redis na hora de servir. Zero novas deps, mas aumenta uso de memória do Redis (beats = 20-50MB cada). | |
| Railway Volume compartilhado | Montar um Volume Railway em /tmp de AMBOS os serviços. | descartada (inviável — Railway Volumes são por serviço, não compartilháveis) |
| Serviço único (web + worker juntos) | Mesclar Uvicorn e Celery Worker em UM container Railway. Compartilham /tmp nativamente. | ✓ |

**User's choice:** Serviço único
**Notes:** Usuário perguntou qual alternativa é melhor pensando em vários usuários simultâneos. Claude explicou que Railway Volume é inviável (por serviço, não compartilhável), Redis tem risco de OOM em picos (20-50MB por WAV), e serviço único é a melhor opção para o scale do SoundGrabber (comunidade underground, STATE.md). Usuário confirmou que a opção é boa e viável para o Railway.

---

## Detecção de bgutil inacessível (PIPE-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Probe HTTP antes do download | Antes de chamar yt-dlp, fazer GET no bgutil_base_url. Se falhar → erro explícito. Fail-fast. | ✓ |
| Parsear erro do yt-dlp | Inspecionar DownloadError buscando padrões como "Sign in to confirm". Frágil — yt-dlp muda mensagens. | |
| Ambos: probe + captura de erro | Probe rápido + segunda captura se yt-dlp falhar com erro de PO Token. | |

**User's choice:** Probe HTTP antes do download

---

### Localização do probe

| Option | Description | Selected |
|--------|-------------|----------|
| pipeline.py — dentro de download_audio | Probe junto da lógica que usa bgutil. download_audio já recebe bgutil_base_url. | ✓ |
| api/tasks.py — antes de chamar download_audio | Probe na camada de orquestração. pipeline.py permanece puro. | |

**User's choice:** pipeline.py — dentro de download_audio

---

### Escopo do probe (check_duration ou só download_audio)

| Option | Description | Selected |
|--------|-------------|----------|
| Só em download_audio | Um probe por job, no ponto crítico. check_duration usa skip_download=True de qualquer forma. | ✓ |
| Nos dois | Fail ainda mais rápido, mas 2x probes HTTP por job. | |

**User's choice:** Só em download_audio

---

## Mensagem de erro explícita (PIPE-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Explícita com URL | "PO Token service unavailable (bgutil at {url}). Download requires bgutil to be running." | ✓ |
| Explícita sem URL | "Download failed: PO Token service (bgutil) is unreachable. Check BGUTIL_BASE_URL." | |

**User's choice:** Explícita com URL
**Notes:** Exposição da URL configurada facilita debug do operador.

---

### error_type para bgutil indisponível

| Option | Description | Selected |
|--------|-------------|----------|
| Novo: "bgutil_unavailable" | Tipo distinto de download_error. Permite monitorar falhas de infra vs. vídeos bloqueados. | ✓ |
| Reusa "download_error" | Sem mudança no contrato da API. Menos tipos no frontend. | |

**User's choice:** Novo "bgutil_unavailable"

---

## Cobertura de testes PIPE-06

| Option | Description | Selected |
|--------|-------------|----------|
| Teste automatizado mockado | Mock de requests.get retornando ConnectionError. Roda em CI. | ✓ |
| Só validação manual no Railway | Desligar bgutil e submeter job. Rápido mas não fica no CI. | |

**User's choice:** Teste automatizado mockado

---

### Arquivo de teste

| Option | Description | Selected |
|--------|-------------|----------|
| tests/test_pipeline_fixes.py | Já contém PIPE-01..05 e bgutil 0.8.x. Padrão consistente. | ✓ |
| tests/test_security.py | Security Gate sugere aqui, mas PIPE-06 é reliability/hardening. | |

**User's choice:** tests/test_pipeline_fixes.py

---

## Estratégia E2E Railway (PIPE-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Checkpoint humano documentado | Como Phase 9 — task com curl commands, operador executa, registra em SMOKE-TEST.md. | ✓ |
| Script automatizado Python | Script smoke_test.py com httpx. Mais elegante mas roda manualmente mesmo. | |

**User's choice:** Checkpoint humano documentado

---

### URLs de teste

| Option | Description | Selected |
|--------|-------------|----------|
| Plano define critérios, URLs na hora | 3 beats instrumentais 3-7 min, gêneros diferentes. Operador escolhe na hora. | ✓ |
| URLs fixas no plano | Reproduzível mas URLs podem expirar. | |

**User's choice:** Plano define critérios, URLs na hora

---

## Claude's Discretion

- Escolha de lib HTTP para o probe (`requests` vs `httpx`): usar o que já estiver em requirements.txt
- Nome do script de startup (`start-all.sh` vs `Procfile` + honcho): usar o mais legível com menos deps
- Número de processos Celery: manter `concurrency=3` (STATE.md Known Risks)

## Deferred Ideas

- Fallback estático com YTDLP_PO_TOKEN quando bgutil cai — descartado em Phase 9, continua fora de escopo
- Health endpoint do bgutil — bgutil não expõe `/health` documentado
- Escala independente worker/web — sacrificada para resolver /tmp; pode retornar em v2 com object storage
