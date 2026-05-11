# Phase 10: Failure Hardening and E2E Validation — Research

**Researched:** 2026-05-11
**Domain:** Python process management, httpx probe patterns, Celery + Uvicorn co-location, Railway deployment
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Arquitetura Railway — /tmp compartilhado (bug containers separados)**
- D-01: Migrar para serviço único no Railway — Uvicorn + Celery Worker no mesmo container. Um único `railway.toml` com `startCommand` que inicia ambos (via `start-all.sh` com supervisord ou honcho). `railway-worker.toml` é aposentado.
- D-02: Compartilhamento de `/tmp` é nativo — os dois processos veem o mesmo sistema de arquivos. Nenhuma mudança de código em `pipeline.py` ou `api/main.py` é necessária para o file serving.
- D-03: Escala independente (worker vs web) é sacrificada. Aceitável para comunidade underground (centenas de usuários — STATE.md).

**Detecção de bgutil inacessível (PIPE-06)**
- D-04: Probe HTTP explícito em `pipeline.py::download_audio` antes de chamar yt-dlp, somente quando `bgutil_base_url` está não-vazio. Timeout de 2 segundos.
- D-05: Probe apenas em `download_audio` — não em `check_duration`. Um probe por job, no ponto crítico antes do download.
- D-06: Se o probe falhar (ConnectionError, timeout, qualquer non-2xx) → lançar exceção com mensagem de bgutil ANTES de tentar yt-dlp. Nunca fazer silent fallback para android client quando `bgutil_base_url` está configurado.

**Mensagem de erro e error_type (PIPE-06)**
- D-07: Mensagem: `"PO Token service unavailable (bgutil at {bgutil_base_url}). Download requires bgutil to be running."`
- D-08: `error_type`: `"bgutil_unavailable"` — novo tipo distinto de `"download_error"`.
- D-09: O novo `error_type` é lançado via `JobFailure(error=..., error_type="bgutil_unavailable")` em `api/tasks.py` — capturando a exceção específica do probe em `pipeline.py`.

**Cobertura de testes (PIPE-06)**
- D-10: Teste automatizado mockado em `tests/test_pipeline_fixes.py`. Mock de `requests.get` (ou `httpx.get`) retornando `ConnectionError` quando `bgutil_base_url` está setado.
- D-11: Arquivo `tests/test_pipeline_fixes.py` — mesmo arquivo que PIPE-01..05 e testes de bgutil 0.8.x.

**Validação E2E Railway (PIPE-07)**
- D-12: Checkpoint humano documentado — plano inclui task com sequência de curl commands.
- D-13: Critérios para as 3 URLs de teste: beats instrumentais de 3-7 minutos de gêneros diferentes.
- D-14: Resultado registrado em `10-SMOKE-TEST.md` — mesmo padrão de `09-01-SMOKE-TEST.md`.

### Claude's Discretion
- Escolha de ferramenta HTTP para o probe (`requests` ou `httpx`): usar o que já estiver em `requirements.txt`.
- Nome do script de startup (`start-all.sh` vs `Procfile` + honcho): usar o que for mais legível e tiver menos deps externas.
- Número de processos Celery no container único: manter `concurrency=3` como está.

### Deferred Ideas (OUT OF SCOPE)
- Fallback estático com YTDLP_PO_TOKEN quando bgutil cai.
- Health endpoint do bgutil (bgutil não expõe `/health` HTTP documentado).
- Escala independente de worker vs web.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-06 | Pipeline falha com mensagem de erro explícita e clara quando bgutil não está disponível, sem tentar client alternativo silenciosamente | httpx probe pattern, exception hierarchy, tasks.py catch chain documented below |
| PIPE-07 | Pipeline completo (download → WAV → BPM/key) executa com sucesso no Railway para pelo menos 3 URLs de beats do YouTube | start-all.sh pattern for single-container deploy, /tmp sharing confirmed, smoke test format documented |
</phase_requirements>

---

## Summary

Phase 10 tem dois entregáveis independentes que precisam acontecer em ordem: primeiro o hardening de código (PIPE-06), depois a validação E2E no Railway (PIPE-07). O hardening é 100% testável localmente — mock de `httpx.get` + novo `except` em `tasks.py`. A validação E2E requer a migração de arquitetura Railway (D-01) para que Uvicorn e Celery Worker compartilhem `/tmp` no mesmo container.

O projeto já tem `httpx>=0.27` explicitamente em `requirements.txt` (versão local: 0.28.1). Nenhuma dependência nova é necessária. O `httpx.get()` com `timeout=2.0` é o mecanismo correto para o probe de bgutil — `httpx.RequestError` captura tanto `ConnectError` quanto `TimeoutException` (e `ConnectTimeout`) em uma única cláusula. Respostas non-2xx são detectadas via `response.is_success`.

A migração para container único no Railway é um `start-all.sh` simples (bash puro, sem supervisord ou honcho — nenhum dos dois está disponível na máquina de desenvolvimento nem como dependência Python). O padrão exato já existe em `start.sh` local: Celery em background com `&`, Uvicorn em foreground com `exec`. O `railway.toml` recebe o novo `startCommand = "bash start-all.sh"` e o `railway-worker.toml` é aposentado (removido ou documentado como inativo).

**Recomendação primária:** Use `httpx.get(f"{bgutil_base_url}/", timeout=2.0)` no início de `download_audio`. Capture `httpx.RequestError` e respostas `not response.is_success` juntos. Raise `RuntimeError` com a mensagem exata de D-07. Em `tasks.py`, adicione `except RuntimeError as e` com filtro de string `"bgutil"` antes do catch genérico de RuntimeError existente.

---

## Standard Stack

### Core (sem mudanças — verificado no requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.27 (local: 0.28.1) | Probe HTTP para bgutil | Já em requirements.txt como dependência direta; API síncrona limpa; exceções granulares |
| celery[redis] | 5.6.3 | Task queue | Já em uso |
| uvicorn | 0.46.0 | ASGI server | Já em uso |

[VERIFIED: requirements.txt do projeto — `httpx>=0.27` está na linha 13]

### Nenhuma dependência nova necessária

`requests` está disponível como dependência transitiva (via yt-dlp), mas NÃO está em `requirements.txt` diretamente. `httpx` está. A escolha é clara: usar `httpx`. [VERIFIED: grep requirements.txt — `httpx>=0.27` presente, `requests` ausente]

---

## Architecture Patterns

### Padrão 1: bgutil Probe em download_audio

**Onde inserir:** Logo no início de `download_audio`, depois de definir `wav_id` e `outtmpl_base`, antes de montar `ydl_opts`. Somente quando `bgutil_base_url` não está vazio.

**Estrutura:**

```python
# Source: análise direta de pipeline.py + httpx docs [VERIFIED: httpx.RequestError hierarchy]
import httpx  # adicionar no topo do arquivo

# Em download_audio, antes de ydl_opts:
if bgutil_base_url:
    try:
        resp = httpx.get(f"{bgutil_base_url}/", timeout=2.0)
        if not resp.is_success:
            raise RuntimeError(
                f"PO Token service unavailable (bgutil at {bgutil_base_url}). "
                f"Download requires bgutil to be running."
            )
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"PO Token service unavailable (bgutil at {bgutil_base_url}). "
            f"Download requires bgutil to be running."
        ) from exc
```

**Por que `httpx.RequestError`:**
- `httpx.ConnectError` (connection refused) → subclasse de `httpx.RequestError` [VERIFIED: MRO local]
- `httpx.TimeoutException` (timeout) → subclasse de `httpx.RequestError` [VERIFIED: MRO local]
- `httpx.ConnectTimeout` (connect timeout) → subclasse de `httpx.RequestError` [VERIFIED: MRO local]
- Uma única cláusula `except httpx.RequestError` captura todos os casos de falha de rede

**Por que `resp.is_success`:**
- `httpx.Response(200).is_success == True` [VERIFIED: local]
- `httpx.Response(503).is_success == False` [VERIFIED: local]
- Cobertura de BGutil que responde mas retorna erro (reiniciando, etc.)

**Endpoint do probe:** `GET {bgutil_base_url}/` (raiz). O bgutil v0.8.1 escuta em `0.0.0.0:4416` — qualquer GET na raiz devolve resposta HTTP. Alternativa TCP connect seria mais robusta mas requer `socket` e é menos legível. GET na raiz é suficiente conforme D-04. [ASSUMED — bgutil raiz responde HTTP válido; confirmado por D-01 do 09-CONTEXT.md que diz "POT server v0.8.1 listening on 0.0.0.0:4416"]

### Padrão 2: Captura em tasks.py com error_type Distinto

**Problema:** O `except RuntimeError` existente em `tasks.py` (linha 104) capturaria a nova exceção do probe e produziria `error_type="download_error"` — misturando falha de infra com vídeo bloqueado pelo YouTube. Isso viola D-08 e D-09.

**Solução:** Adicionar um `except RuntimeError` específico ANTES do genérico, com filtro por string `"bgutil"` na mensagem:

```python
# Source: análise de api/tasks.py estrutura de exceções existente [VERIFIED: codebase]
# Inserir ANTES do 'except RuntimeError as e' existente (linha 104):
except RuntimeError as e:
    if "bgutil" in str(e).lower():
        logger.warning("Job %s bgutil_unavailable: %s", self.request.id, e)
        raise JobFailure(
            error=str(e),  # mensagem exata de D-07 gerada pelo probe
            error_type="bgutil_unavailable",
        ) from e
    # não-bgutil RuntimeError: cai no próximo except RuntimeError abaixo
    raise  # re-raise para o catch genérico existente
```

**Alternativa mais limpa:** Criar exceção customizada `BgutilUnavailable(RuntimeError)` em `pipeline.py` — o probe levanta `BgutilUnavailable`, o `tasks.py` captura `BgutilUnavailable` diretamente sem filtro por string. Isso evita fragilidade de detecção por string. Recomendado se o planner concordar com a adição de um tipo de exceção.

**Exceção customizada (recomendado):**

```python
# pipeline.py — adicionar perto do topo do módulo
class BgutilUnavailable(RuntimeError):
    """Raised when the bgutil PO Token service is unreachable."""
    pass
```

```python
# api/tasks.py — novo except ANTES de 'except RuntimeError'
except BgutilUnavailable as e:
    logger.warning("Job %s bgutil_unavailable: %s", self.request.id, e)
    raise JobFailure(
        error=str(e),
        error_type="bgutil_unavailable",
    ) from e
```

E em `tasks.py` adicionar import: `from pipeline import check_duration, download_audio, analyze_audio, BgutilUnavailable`

### Padrão 3: start-all.sh para Container Único Railway

**Contexto:** `start.sh` local já usa o padrão correto. `start-all.sh` é uma versão simplificada para Railway (sem venv activation, sem .env sourcing, sem Redis startup — Railway injeta env vars e Redis está no private network).

```bash
#!/usr/bin/env bash
# start-all.sh — Railway single-container startup (Uvicorn + Celery Worker)
# Source: start.sh local [VERIFIED: codebase] + Railway container conventions [ASSUMED]
set -e

# SEC-FILE-02 compatible: script sem chmod self (Railway não precisa)
# Celery em background — Railway monitora o processo foreground (Uvicorn)
celery -A api.tasks worker --loglevel=info --concurrency=3 &

# Uvicorn em foreground — Railway usa este processo para health checks
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
    --limit-concurrency 100 --timeout-keep-alive 5
```

**Por que `exec`:** Substitui o processo bash pelo uvicorn. Railway (e Docker) rastreiam o PID 1. Com `exec`, o Uvicorn vira PID 1 do grupo de processos no foreground — os sinais SIGTERM chegam diretamente a ele, permitindo graceful shutdown. Sem `exec`, o bash seria PID 1 e precisaria repassar sinais manualmente. [ASSUMED — padrão Docker/Railway amplamente documentado; consistente com start.sh local que usa exec implicitamente via `set -e` + uvicorn como último comando]

**Por que sem supervisord/honcho:** Nenhum dos dois está disponível como instalação de sistema ou como dependência Python no projeto. Bash puro com `&` + `exec` é a solução mais simples e sem deps extras. [VERIFIED: `which supervisord`, `which honcho` — ambos "not found" na máquina de desenvolvimento]

**Sinal de encerramento (SIGTERM):** Quando Railway para o container, envia SIGTERM ao PID 1 (uvicorn após `exec`). O Celery worker em background recebe SIGTERM do kernel quando o processo pai (bash antes do exec) termina — o comportamento padrão é encerrar após terminar o job corrente (`task_acks_late=True` já está configurado). [ASSUMED — comportamento padrão de Celery SIGTERM com task_acks_late]

### Padrão 4: railway.toml Atualizado

```toml
# Source: railway.toml atual [VERIFIED: codebase]
[deploy]
startCommand = "bash start-all.sh"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

`railway-worker.toml` é aposentado: o arquivo pode ser deletado ou mantido com comentário explicando que está obsoleto. Recomendação: deletar para evitar confusão — o Railway só usa o arquivo especificado em "Config-as-code" do serviço.

### Padrão 5: Mock de httpx no teste (D-10)

**Caminho do mock correto:** Quando `pipeline.py` adiciona `import httpx` no topo, o mock target em `test_pipeline_fixes.py` é `"pipeline.httpx.get"`. [VERIFIED: `hasattr(pipeline, 'httpx')` retorna False antes da mudança — após adicionar `import httpx` em pipeline.py, retornará True e o patch path será `pipeline.httpx.get`]

```python
# Source: padrão unittest.mock.patch + análise do módulo pipeline [VERIFIED: codebase]
from unittest.mock import patch, MagicMock
import pytest
import httpx

def test_pipe06_bgutil_probe_fails_raises_with_bgutil_message():
    """PIPE-06: download_audio deve falhar com mensagem 'bgutil' quando probe falha."""
    with patch("pipeline.httpx.get", side_effect=httpx.ConnectError("Connection refused")):
        import pipeline
        with pytest.raises((RuntimeError, pipeline.BgutilUnavailable)) as exc_info:
            pipeline.download_audio(
                url="https://www.youtube.com/watch?v=fake",
                cookies_path="",
                po_token="",
                bgutil_base_url="http://bgutil.railway.internal:4416",
            )
        assert "bgutil" in str(exc_info.value).lower()

def test_pipe06_bgutil_probe_timeout_raises():
    """PIPE-06: ConnectTimeout também deve disparar a exceção de bgutil."""
    with patch("pipeline.httpx.get", side_effect=httpx.ConnectTimeout("timed out")):
        import pipeline
        with pytest.raises((RuntimeError, pipeline.BgutilUnavailable)) as exc_info:
            pipeline.download_audio(
                url="https://www.youtube.com/watch?v=fake",
                cookies_path="",
                po_token="",
                bgutil_base_url="http://bgutil.railway.internal:4416",
            )
        assert "bgutil" in str(exc_info.value).lower()

def test_pipe06_bgutil_not_called_without_bgutil_base_url():
    """PIPE-06: quando bgutil_base_url está vazio, probe NÃO é executado."""
    with patch("pipeline.httpx.get") as mock_get:
        import pipeline
        # Sem bgutil_base_url, yt-dlp é chamado diretamente (sem probe)
        # O teste verifica apenas que httpx.get NÃO foi chamado
        try:
            pipeline.download_audio(
                url="https://www.youtube.com/watch?v=fake",
                cookies_path="",
                po_token="",
                bgutil_base_url="",  # vazio — sem probe
            )
        except Exception:
            pass  # yt-dlp vai falhar — não importa
        mock_get.assert_not_called()
```

**Atenção:** O terceiro teste (`assert_not_called`) é frágil se yt-dlp internamente usar httpx. Alternativa mais robusta: usar `inspect.getsource(pipeline.download_audio)` para verificar estrutura do código (padrão já usado nos testes PIPE-01..04). [ASSUMED — yt-dlp usa requests internamente, não httpx; mas verificar]

### Anti-Patterns a Evitar

- **Inserir probe em `check_duration`:** D-05 proíbe. Um probe por job, em `download_audio`.
- **Silent fallback para android client:** D-06 proíbe explicitamente. Se `bgutil_base_url` está configurado e probe falha, o job DEVE falhar — nunca tentar android silenciosamente.
- **Usar `except Exception` para capturar a exceção do bgutil:** O catch genérico em `tasks.py` já existe e produziria `error_type="internal_error"`. A nova exceção DEVE ser capturada ANTES, em handler específico.
- **Usar `requests.get` em vez de `httpx.get`:** `requests` não está em `requirements.txt` como dependência direta. `httpx` está. [VERIFIED: requirements.txt]
- **`start-all.sh` sem `exec` antes do uvicorn:** Sem `exec`, SIGTERM do Railway não chega ao uvicorn — graceful shutdown não funciona.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Probe de disponibilidade HTTP | Custom socket TCP check | `httpx.get(..., timeout=2.0)` | httpx já é dependência; API limpa; exceções tipadas; `is_success` cobre non-2xx |
| Process management em container | supervisord config file | bash `&` + `exec` | Sem deps extras; Railway monitora PID 1 naturalmente; já funciona em `start.sh` |
| Detecção de tipo de falha do bgutil | Parsing de stderr/stdout | Exceção customizada `BgutilUnavailable(RuntimeError)` | Captura tipada em `tasks.py`; sem fragilidade de string matching |

---

## Common Pitfalls

### Pitfall 1: Mock path errado para httpx em tests

**O que dá errado:** `patch("httpx.get")` não intercepta chamadas em `pipeline.py` porque `pipeline` tem sua própria referência ao módulo `httpx` após `import httpx`.
**Por que acontece:** O `patch` substitui o atributo no namespace correto — precisa ser `"pipeline.httpx.get"`, não `"httpx.get"`.
**Como evitar:** Sempre usar `patch("pipeline.httpx.get")` nos testes de `test_pipeline_fixes.py`.
**Sinais de alerta:** Mock retorna `MagicMock()` sem ser chamado; exceção real de rede é levantada no teste.

### Pitfall 2: Celery worker captura SIGTERM durante job em andamento

**O que dá errado:** Railway envia SIGTERM quando faz deploy/restart. Se Celery está processando um job (análise librosa leva ~10-30s), pode ser morto no meio.
**Por que acontece:** `task_acks_late=True` (já configurado) + `SIGTERM` triggering warm shutdown — Celery termina o worker após completar o job atual. Mas `SIGKILL` (enviado após timeout) mata sem aviso.
**Como evitar:** O `healthcheckTimeout = 60` em `railway.toml` é suficiente — Railway aguarda 60s antes de SIGKILL. Jobs duram no máximo ~60-90s no pior caso (15min video). [ASSUMED — Railway default SIGKILL timeout após SIGTERM; confirmar se necessário]
**Sinais de alerta:** Jobs ficam `status=processing` para sempre após redeploy.

### Pitfall 3: Probe de bgutil falha em DEV_MODE (local sem bgutil)

**O que dá errado:** Com `BGUTIL_BASE_URL` setado no `.env` local mas sem bgutil rodando, `download_audio` falha imediatamente antes de tentar yt-dlp — mesmo localmente.
**Por que acontece:** O probe é ativado por `bgutil_base_url != ""` — sem verificar ambiente.
**Como evitar:** Em desenvolvimento local, deixar `BGUTIL_BASE_URL` vazio no `.env` (android client é usado). A função opera corretamente com `bgutil_base_url=""`. Documentar no plano.
**Sinais de alerta:** Jobs locais falham com "PO Token service unavailable" sem bgutil rodando.

### Pitfall 4: railway-worker.toml ainda referenciado por serviço Railway

**O que dá errado:** Após migrar para serviço único, se o serviço Celery Worker ainda aponta para `railway-worker.toml`, ele continua sendo deployado separadamente — duplicando workers e desperdiçando recursos.
**Por que acontece:** O arquivo de config de cada serviço Railway é configurado manualmente no dashboard (Settings → Config-as-code → Railway Config File). Deletar o arquivo do repo não desativa o serviço.
**Como evitar:** O plano DEVE incluir task explícita de desativação do serviço Celery Worker no dashboard Railway ou remoção da referência ao `railway-worker.toml`. [ASSUMED — comportamento do Railway dashboard; verificar com operador]

### Pitfall 5: Ordem dos excepts em tasks.py

**O que dá errado:** Se `BgutilUnavailable` (subclasse de `RuntimeError`) for adicionada mas o `except RuntimeError` genérico vier primeiro no bloco try/except, `BgutilUnavailable` é capturada pelo handler genérico — producindo `error_type="download_error"`.
**Por que acontece:** Python processa `except` em ordem — o primeiro match vence.
**Como evitar:** `except BgutilUnavailable` DEVE aparecer ANTES de `except RuntimeError` em `tasks.py`. [VERIFIED: comportamento Python — subclasse deve vir antes da classe base]

---

## Code Examples

### Download Audio — ponto de inserção do probe

O probe entra nas linhas 148-165 de `pipeline.py` (antes de `ydl_opts`):

```python
# Inserir após linha 150 (outtmpl_base/wav_path definitions), antes de linha 157 (dl_player)
# Source: análise de pipeline.py [VERIFIED: codebase]

if bgutil_base_url:
    logger.info("Probing bgutil availability at %s", bgutil_base_url)
    try:
        resp = httpx.get(f"{bgutil_base_url}/", timeout=2.0)
        if not resp.is_success:
            logger.warning("bgutil probe returned HTTP %s", resp.status_code)
            raise BgutilUnavailable(
                f"PO Token service unavailable (bgutil at {bgutil_base_url}). "
                f"Download requires bgutil to be running."
            )
        logger.info("bgutil probe OK (HTTP %s)", resp.status_code)
    except httpx.RequestError as exc:
        logger.warning("bgutil probe failed: %s", exc)
        raise BgutilUnavailable(
            f"PO Token service unavailable (bgutil at {bgutil_base_url}). "
            f"Download requires bgutil to be running."
        ) from exc
```

### tasks.py — novo except antes do RuntimeError genérico

```python
# Source: análise de api/tasks.py [VERIFIED: codebase]
# Inserir entre 'except FileNotFoundError' (linha 96) e 'except RuntimeError' (linha 104)

from pipeline import check_duration, download_audio, analyze_audio, BgutilUnavailable

# ... dentro do process_job try/except:

    except BgutilUnavailable as e:
        logger.warning("Job %s bgutil_unavailable: %s", self.request.id, e)
        raise JobFailure(
            error=str(e),
            error_type="bgutil_unavailable",
        ) from e

    except RuntimeError as e:  # RuntimeError genérico — yt-dlp errors (já existente)
        logger.info("Job %s download_error: %s", self.request.id, e)
        raise JobFailure(
            error="Download failed. The video may be unavailable or blocked.",
            error_type="download_error",
        ) from e
```

### start-all.sh (completo)

```bash
#!/usr/bin/env bash
# start-all.sh — Railway single-container startup
# Inicia Celery Worker em background e Uvicorn em foreground (PID monitorado pelo Railway).
# Source: padrão de start.sh local [VERIFIED: codebase] + convenção Docker exec
set -e

celery -A api.tasks worker --loglevel=info --concurrency=3 &

exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --limit-concurrency 100 \
    --timeout-keep-alive 5
```

### railway.toml (atualizado)

```toml
[deploy]
startCommand = "bash start-all.sh"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

### Smoke test (formato de 10-SMOKE-TEST.md)

Seguir exatamente o padrão de `09-01-SMOKE-TEST.md` — tabela de gate checks por critério de sucesso, resultado `PASS/FAIL/BLOQUEADO`, assinatura de data. Critérios do ROADMAP.md:
1. Job com bgutil inacessível → `status=failed`, `error_type="bgutil_unavailable"`, mensagem nomeia bgutil
2. 3 beat URLs → `status=done`, BPM numérico plausível, key em notação padrão
3. `GET /files/{id}` → WAV >100KB, abrível em DAW

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Dois containers Railway (web + worker) | Único container com start-all.sh | Phase 10 (D-01) | `/tmp` compartilhado — WAV produzido pelo worker é acessível ao web server |
| `RuntimeError` genérico para falha de bgutil | `BgutilUnavailable(RuntimeError)` específico | Phase 10 (D-08/D-09) | `error_type="bgutil_unavailable"` distinto de `"download_error"` |
| Sem probe de bgutil — falha obscura no yt-dlp | Probe HTTP 2s antes de chamar yt-dlp | Phase 10 (D-04/D-06) | Erro imediato e claro; sem silent fallback para android client |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | bgutil v0.8.1 responde HTTP na raiz `GET /` com status 2xx quando saudável | Padrão 1 (probe endpoint) | Probe sempre falha mesmo com bgutil funcionando → jobs falham em produção. Mitigation: testar manualmente `curl http://bgutil.railway.internal:4416/` após deploy |
| A2 | Railway envia SIGTERM ao PID 1 com timeout suficiente antes de SIGKILL | Pitfall 2 | Jobs interrompidos no meio durante redeploys |
| A3 | Serviço Celery Worker Railway precisa ser desativado manualmente no dashboard após migração para container único | Pitfall 4 | Workers duplicados em produção — dois containers processando jobs do mesmo Redis |
| A4 | yt-dlp internamente não usa httpx (usa urllib3/requests) — `patch("pipeline.httpx.get")` não intercepta calls internas do yt-dlp | Pitfall 1, Padrão 5 | Mock insuficiente; yt-dlp chamado antes do probe | 

---

## Open Questions

1. **bgutil GET / responde 2xx ou retorna algo diferente?**
   - O que sabemos: bgutil v0.8.1 escuta na porta 4416 (confirmado em 09-CONTEXT.md D-01); é um servidor HTTP (não gRPC puro, pois o yt-dlp plugin se comunica via HTTP)
   - O que está incerto: o endpoint raiz `/` retorna 200, 404, ou outro status?
   - Recomendação: o probe pode usar `not resp.is_error` em vez de `resp.is_success` — `is_error` é True apenas para 5xx. Isso aceita 2xx e 4xx (404 significa "servidor up, rota não existe" — bgutil está funcionando). Alternativamente, capturar apenas `httpx.RequestError` (sem verificar status) é mais robusto: se o servidor responde qualquer coisa, está up.

2. **Celery Worker Railway precisa ser desativado explicitamente?**
   - O que sabemos: após D-01, o single-container usa `railway.toml` com o novo `startCommand`
   - O que está incerto: se o dashboard Railway ainda tem o Celery Worker como serviço separado, ele continuará deployando `railway-worker.toml` — duplicando workers
   - Recomendação: o plano deve incluir task de checkpoint humano para desativar o serviço `celery-worker` no dashboard Railway

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| httpx | bgutil probe | ✓ | 0.28.1 | — |
| Python 3.11 | runtime | ✓ | local | — |
| pytest | test suite | ✓ | 9.0.3 | — |
| Railway MCP | deploy + smoke test | ✓ | — (sessão anterior confirmou uso) | Dashboard manual |
| bgutil service (Railway) | PIPE-07 E2E | ✓ (deployado em Phase 9) | v0.8.1 | — |

**Nenhuma dependência bloqueante identificada.**

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none (pytest.ini / pyproject.toml não existem) |
| Quick run command | `pytest tests/test_pipeline_fixes.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-06 | probe falha (ConnectError) → RuntimeError com "bgutil" na msg | unit (mock) | `pytest tests/test_pipeline_fixes.py::test_pipe06_bgutil_probe_fails_raises_with_bgutil_message -x` | ❌ Wave 0 |
| PIPE-06 | probe timeout → RuntimeError com "bgutil" na msg | unit (mock) | `pytest tests/test_pipeline_fixes.py::test_pipe06_bgutil_probe_timeout_raises -x` | ❌ Wave 0 |
| PIPE-06 | bgutil_base_url="" → probe NÃO executado | unit (mock) | `pytest tests/test_pipeline_fixes.py::test_pipe06_no_probe_without_bgutil_url -x` | ❌ Wave 0 |
| PIPE-06 | tasks.py: BgutilUnavailable → error_type="bgutil_unavailable" | unit (mock) | `pytest tests/test_pipeline_fixes.py::test_pipe06_tasks_bgutil_error_type -x` | ❌ Wave 0 |
| PIPE-07 | 3 beat URLs → status=done com WAV, BPM, key | manual + smoke test | `10-SMOKE-TEST.md` (checkpoint humano) | ❌ Wave 0 (template) |

### Sampling Rate

- **Por task commit:** `pytest tests/test_pipeline_fixes.py -x -q`
- **Por wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green + smoke test `10-SMOKE-TEST.md` preenchido antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline_fixes.py` — 4 novos testes PIPE-06 (mocks httpx)
- [ ] `.planning/phases/10-failure-hardening-and-e2e-validation/10-SMOKE-TEST.md` — template do smoke test E2E (preenchido pelo operador na task de checkpoint humano)

*(Infraestrutura de testes já existe — apenas novos casos de teste precisam ser adicionados ao arquivo existente)*

---

## Security Domain

> Phase 10 não introduz novos endpoints HTTP. Security Gate do CLAUDE.md não é acionado para este escopo.

**Controles existentes mantidos:**
- `os.chmod(wav_path, 0o600)` em `download_audio` — não afetado pelo probe
- Rate limiting nos endpoints existentes — não afetado por start-all.sh
- Path traversal defense em `GET /files/{id}` — não afetado

**ASVS V5 (Input Validation):** O probe usa a URL de `bgutil_base_url` (variável de ambiente configurada pelo operador, não input de usuário). Sem risco de path traversal ou injection via esse probe.

---

## Sources

### Primary (HIGH confidence)
- `pipeline.py` (codebase) — estrutura atual de `download_audio`, ponto de inserção do probe, imports disponíveis
- `api/tasks.py` (codebase) — exception chain existente; ordem e tipos de excepts
- `railway.toml` + `railway-worker.toml` (codebase) — startCommands atuais
- `tests/test_pipeline_fixes.py` (codebase) — padrões de mock existentes (unittest.mock.patch)
- `requirements.txt` (codebase) — `httpx>=0.27` presente, `requests` ausente como dependência direta
- `api/config.py` (codebase) — `settings.bgutil_base_url` lido de `BGUTIL_BASE_URL`
- `.planning/phases/09-railway-bgutil-deployment/09-01-SMOKE-TEST.md` (codebase) — bug /tmp isolados documentado, formato do smoke test

### Secondary (MEDIUM confidence)
- httpx exception MRO verificado localmente: `httpx.RequestError` captura `ConnectError`, `TimeoutException`, `ConnectTimeout`
- `httpx.Response.is_success` verificado localmente: `True` para 2xx, `False` para 5xx
- `which supervisord`, `which honcho` — confirmados "not found" localmente

### Tertiary (LOW confidence)
- Comportamento Railway SIGTERM/SIGKILL para container single-process com `exec` [ASSUMED — baseado em convenção Docker]
- bgutil `GET /` retorna HTTP 2xx quando saudável [ASSUMED — não verificado com instance real]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — httpx em requirements.txt verificado, versão local confirmada
- Architecture (probe pattern): HIGH — código verificado, MRO de exceções confirmado localmente
- Architecture (start-all.sh): HIGH — padrão existente em start.sh, exec + background já documentado no projeto
- Architecture (tasks.py exception order): HIGH — comportamento Python determinístico, código verificado
- Mock patch paths: HIGH — verificado comportamento de `hasattr(pipeline, 'httpx')`
- bgutil probe endpoint: MEDIUM — PORT confirmada (4416), resposta da raiz HTTP não testada diretamente
- Railway SIGTERM behavior: LOW — convenção padrão mas não verificada com Railway específico

**Research date:** 2026-05-11
**Valid until:** 2026-06-10 (httpx estável; railway.toml schema estável)
