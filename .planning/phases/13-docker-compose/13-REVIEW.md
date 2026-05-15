---
phase: 13-docker-compose
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - .dockerignore
  - .env.example
  - Dockerfile
  - docker-compose.yml
  - pipeline.py
  - requirements.txt
  - tests/test_pipeline_docker.py
findings:
  critical: 3
  warning: 5
  info: 1
  total: 9
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-05-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Resumo

Revisão cobre a adição de Dockerfile, `.dockerignore`, `docker-compose.yml`, refatoração de `pipeline.py` (remoção de librosa/imageio-ffmpeg, adoção de Essentia + ffmpeg do sistema) e os testes de smoke da Phase 13. A estrutura geral é sólida: volume tmpfs compartilhado está correto, Redis sem exposição ao host, e a autenticação híbrida (cookies + bgutil) foi preservada sem regressão.

Foram encontrados **3 issues críticos** que devem ser corrigidos antes do deploy:
1. Um arquivo de cookies do YouTube com tokens de sessão reais (`SID`) está rastreado pelo git.
2. O `.gitignore` não cobre o padrão `www.youtube.com_cookies*.txt`, permitindo que futuras exportações sejam comitadas acidentalmente.
3. O container roda como `root` — sem instrução `USER` no Dockerfile.

---

## Critical Issues

### CR-01: Cookie do YouTube com token de sessão real rastreado pelo git

**File:** `www.youtube.com_cookies (1).txt:1`
**Issue:** O arquivo `www.youtube.com_cookies (1).txt` está rastreado pelo git (confirmado via `git ls-files`) e contém tokens de sessão ativos do YouTube (`SID`, `__Secure-3PSID`). Qualquer clone do repositório expõe as credenciais. O `.gitignore` cobre apenas `cookies.txt` e `*.cookies`, não o padrão `www.youtube.com_cookies*.txt` — o que é o nome padrão gerado pela extensão "Get cookies.txt LOCALLY".

**Fix:**
```bash
# 1. Remover do índice git (mantém o arquivo em disco)
git rm --cached "www.youtube.com_cookies (1).txt"
git rm --cached "www.youtube.com_cookies.txt" 2>/dev/null || true

# 2. Adicionar padrão ao .gitignore
echo 'www.youtube.com_cookies*.txt' >> .gitignore

# 3. Revogar os cookies expostos: fazer logout/login no YouTube em todos os browsers
#    e re-exportar cookies frescos APÓS o arquivo ser removido do git.

# 4. Se o repo for público ou compartilhado, fazer rewrite de histórico:
git filter-repo --path "www.youtube.com_cookies (1).txt" --invert-paths
```

---

### CR-02: .gitignore não cobre exportações de cookies do YouTube

**File:** `.gitignore:1-4`
**Issue:** O `.gitignore` cobre `cookies.txt` e `*.cookies`, mas **não** cobre `www.youtube.com_cookies*.txt` — que é o nome exato gerado pela extensão "Get cookies.txt LOCALLY" do Chrome/Firefox. O `.dockerignore` tem o padrão correto (linha 4), mas o `.gitignore` não. O CR-01 acima é consequência direta desta lacuna.

**Fix:**
```diff
# .gitignore — adicionar após a linha "*.cookies":
+www.youtube.com_cookies*.txt
```

---

### CR-03: Container roda como root — sem instrução USER no Dockerfile

**File:** `Dockerfile:1`
**Issue:** O Dockerfile não contém nenhuma instrução `USER`. O processo `uvicorn` (api) e o worker Celery rodam como `uid=0 (root)` dentro do container. Se houver path traversal ou RCE via yt-dlp/FFmpeg, o atacante obtém acesso root no container. O volume `sg_tmp` é montado como root, o que também significa que arquivos WAV são criados como root.

**Fix:**
```dockerfile
# Adicionar antes do CMD, após COPY . .

# Criar usuário não-privilegiado
RUN groupadd --gid 1001 sguser \
    && useradd --uid 1001 --gid sguser --no-create-home --shell /bin/false sguser \
    && chown -R sguser:sguser /app

USER sguser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--limit-concurrency", "100", "--timeout-keep-alive", "5"]
```

Nota: o volume `/tmp` precisará de permissão de escrita para o usuário `sguser`. Ajustar `o: "size=512m,mode=1777"` no `docker-compose.yml` já cobre isso (mode 1777 = sticky + world-writable).

---

## Warnings

### WR-01: NodeSource instalado via curl | bash sem verificação de integridade

**File:** `Dockerfile:11`
**Issue:** A linha `curl -fsSL https://deb.nodesource.com/setup_20.x | bash -` executa um script remoto sem verificar hash/assinatura. Se o CDN da NodeSource for comprometido ou sofrer MITM (menos provável com TLS, mas não impossível em ambientes corporativos com inspeção SSL), código arbitrário é executado com privilégios de root durante o build. Builds não são reproduzíveis — a mesma tag de imagem pode produzir binários diferentes em datas distintas.

**Fix:**
```dockerfile
# Opção A — verificar checksum do script de setup:
RUN curl -fsSL https://deb.nodesource.com/setup_20.x -o /tmp/nodesource_setup.sh \
    && echo "EXPECTED_SHA256  /tmp/nodesource_setup.sh" | sha256sum --check \
    && bash /tmp/nodesource_setup.sh \
    && rm /tmp/nodesource_setup.sh

# Opção B — usar a chave GPG do NodeSource diretamente (mais robusto):
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /usr/share/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] \
       https://deb.nodesource.com/node_20.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs
```

---

### WR-02: Imagem `jim60105/bgutil-pot` sem tag — unpinned

**File:** `docker-compose.yml:38`
**Issue:** `image: jim60105/bgutil-pot` sem tag equivale a `:latest`. Um `docker-compose pull` futuro pode puxar uma versão incompatível com `bgutil-ytdlp-pot-provider==0.8.1` (pinado em `requirements.txt`). A integração entre o provider Python e o servidor bgutil depende da versão da API interna.

**Fix:**
```yaml
  bgutil:
    image: jim60105/bgutil-pot:0.8.1   # ou a tag estável correspondente ao provider 0.8.1
```
Verificar a tag correta em https://hub.docker.com/r/jim60105/bgutil-pot/tags.

---

### WR-03: bgutil sem healthcheck e sem depends_on em api e worker

**File:** `docker-compose.yml:37-43`
**Issue:** O serviço `bgutil` não tem `healthcheck`. Os serviços `api` e `worker` dependem apenas do Redis (via `condition: service_healthy`), mas não declaram `depends_on: bgutil`. Se o bgutil demorar a iniciar (Node.js cold start, download de dependências), os primeiros jobs enviados após `docker-compose up` falharão silenciosamente com erro de PO Token — sem retry automático.

**Fix:**
```yaml
  bgutil:
    image: jim60105/bgutil-pot:0.8.1
    restart: unless-stopped
    networks:
      - soundgrabber_net
    mem_limit: 128m
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:4416/"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s   # Node.js precisa de tempo para iniciar

  worker:
    ...
    depends_on:
      redis:
        condition: service_healthy
      bgutil:
        condition: service_healthy   # adicionar
```

Nota: verificar o endpoint correto de liveness do bgutil (pode ser `/health` ou diferente). Consultar a documentação da imagem.

---

### WR-04: `detect_tuning` analisa apenas os primeiros 46ms do áudio

**File:** `pipeline.py:416`
**Issue:** `audio[:2048]` em 44100 Hz equivale a ~46ms. Para uma faixa que começa com intro silenciosa, fade-in, ou ruído de bateria sem pitch, `SpectralPeaks` não encontrará frequências harmônicas e a função retornará `None`. O fallback para `tuning_hz=None` usa 440.0Hz em `detect_key` — que é o padrão correto mas ignora faixas com afinação não-padrão (ex: 432Hz, 443Hz). A janela de 2048 amostras é adequada para a FFT, mas a escolha de usar **somente os primeiros** 2048 samples é incorreta para tuning detection — o transiente inicial não é representativo da afinação do track.

**Fix:**
```python
def detect_tuning(wav_path: Path) -> float | None:
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    if len(audio) < 2048:
        return None

    # Usar uma janela do meio do audio (evita intro silenciosa e fade-out)
    mid = len(audio) // 2
    start = max(0, mid - 1024)
    frame = audio[start:start + 2048]

    windowed = es.Windowing(type="blackmanharris62")(frame)
    ...
```
Alternativa mais robusta: usar `es.FrameGenerator` e agregar TuningFrequency sobre múltiplos frames.

---

### WR-05: `Path("pipeline.py")` em teste usa path relativo — falha se pytest não for executado da raiz do projeto

**File:** `tests/test_pipeline_docker.py:19`
**Issue:** `Path("pipeline.py").read_text(...)` resolve relativo ao `cwd` do processo pytest. Se o teste for executado de qualquer diretório que não seja a raiz do projeto (ex: `cd tests && pytest`), ou em um CI que defina um workdir diferente, os testes `test_no_imageio_ffmpeg_import` e `test_no_librosa_import` falham com `FileNotFoundError`.

**Fix:**
```python
def _pipeline_import_names() -> set[str]:
    # Resolve relativo ao diretório do arquivo de teste, não do cwd
    project_root = Path(__file__).parent.parent
    source = (project_root / "pipeline.py").read_text(encoding="utf-8")
    ...
```

---

## Info

### IN-01: `soundfile` em requirements.txt é dependência apenas de testes, mas instalada na imagem de produção

**File:** `requirements.txt:2`
**Issue:** `soundfile==0.13.1` é usado apenas em `tests/test_pipeline_docker.py` (linha 52) e `tests/test_pipeline.py` (linha 234). A biblioteca não é importada em `pipeline.py` nem em `api/`. Ela é instalada na imagem de produção (`pip install -r requirements.txt` no Dockerfile), aumentando o tamanho da imagem sem necessidade.

**Fix:** Separar dependências de teste em `requirements-dev.txt` ou `requirements-test.txt`:
```txt
# requirements-test.txt
soundfile==0.13.1
pytest==9.0.3
pytest-subprocess>=1.5
```
E no Dockerfile, não instalar as dependências de teste:
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# (não copiar requirements-test.txt na imagem de produção)
```

---

_Reviewed: 2026-05-15T00:00:00Z_
_Reviewer: Claude Sonnet 4.6 (gsd-code-reviewer)_
_Depth: standard_
