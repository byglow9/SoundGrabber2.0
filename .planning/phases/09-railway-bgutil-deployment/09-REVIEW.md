---
phase: 09-railway-bgutil-deployment
reviewed: 2026-05-11T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - pipeline.py
  - requirements.txt
  - tests/test_pipeline_fixes.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-05-11
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Foram revisados `pipeline.py`, `requirements.txt` e `tests/test_pipeline_fixes.py` no contexto das correções da Phase 9: resolução de caminho ffmpeg/ffprobe com imageio-ffmpeg de nome versionado, pin de `bgutil-ytdlp-pot-provider==0.8.5`, e troca de chave `extractor_args` para o formato 0.8.x (`getpot_bgutil_baseurl`).

A lógica de resolução de ffmpeg/ffprobe em si está correta: `_YTDLP_FFMPEG_LOCATION` aponta para o executável (não o diretório) e o fallback `ffmpeg -i` para inspeção de duração está bem implementado. O subprocess usa lista de argumentos, sem `shell=True`, portanto não há injeção de comando. O campo `bgutil_base_url` vem de variável de ambiente controlada pelo operador.

O problema crítico encontrado é que o bloco `__main__` do CLI em `pipeline.py` nunca lê `BGUTIL_BASE_URL` do ambiente, ignorando silenciosamente a configuração bgutil inteira ao executar o pipeline via linha de comando. Isso compromete testes manuais de smoke-test e debugging em produção no Railway.

---

## Critical Issues

### CR-01: CLI `__main__` ignora `BGUTIL_BASE_URL` — bgutil nunca ativa via linha de comando

**File:** `pipeline.py:563-567`

**Issue:** O bloco `__main__` chama `check_duration(url, cookies_path)` e `download_audio(url, cookies_path, po_token)` sem passar `bgutil_base_url`. O parâmetro tem default `""`, portanto o cliente é sempre `android` e o `getpot_bgutil_baseurl` nunca é configurado — mesmo que o operador tenha `BGUTIL_BASE_URL` definido no ambiente. Smoke tests manuais no Railway (ex: `python pipeline.py <URL>`) vão usar o cliente android, desviando do comportamento real da API, mascarando falhas de integração com o servidor bgutil.

```python
# ATUAL (lines 565-567) — ignora BGUTIL_BASE_URL:
info = check_duration(url, cookies_path)
wav_path = download_audio(url, cookies_path, po_token)

# CORRETO:
bgutil_base_url = os.environ.get("BGUTIL_BASE_URL", "")
info = check_duration(url, cookies_path, bgutil_base_url)
wav_path = download_audio(url, cookies_path, po_token, bgutil_base_url)
```

---

## Warnings

### WR-01: Zero cobertura de teste para a mudança central da Phase 9 — chave `getpot_bgutil_baseurl`

**File:** `tests/test_pipeline_fixes.py` (arquivo inteiro)

**Issue:** A correção mais crítica da Phase 9 é a troca de `youtubepot-bgutilhttp:base_url` (1.x) para `getpot_bgutil_baseurl` (0.8.x) em `extractor_args`. Não existe nenhum teste em nenhum arquivo `tests/` que verifique: (a) que a chave correta é usada com plugin 0.8.x, (b) que `check_duration` e `download_audio` injetam `getpot_bgutil_baseurl` quando `bgutil_base_url` está preenchido, ou (c) que nenhum dos dois injeta o argumento quando `bgutil_base_url` é vazio. Se o nome da chave regredir para o formato 1.x, nenhum teste quebraria.

```python
# Adicionar em tests/test_pipeline_fixes.py:
import inspect
import pipeline

def test_bgutil_08x_extractor_key_check_duration():
    """bgutil 0.8.x usa 'getpot_bgutil_baseurl', nao 'youtubepot-bgutilhttp:base_url'."""
    src = inspect.getsource(pipeline.check_duration)
    assert "getpot_bgutil_baseurl" in src, (
        "DEPLOY-02 fix missing: check_duration deve usar a chave 0.8.x 'getpot_bgutil_baseurl'. "
        "A chave 1.x era 'youtubepot-bgutilhttp:base_url'."
    )
    assert "youtubepot-bgutilhttp" not in src, (
        "check_duration contém a chave 1.x 'youtubepot-bgutilhttp'. "
        "O projeto pina bgutil==0.8.5; usar a chave 1.x silenciosamente ignora o bgutil server."
    )

def test_bgutil_08x_extractor_key_download_audio():
    src = inspect.getsource(pipeline.download_audio)
    assert "getpot_bgutil_baseurl" in src
    assert "youtubepot-bgutilhttp" not in src
```

### WR-02: `test_pipe05` é frágil quando `api.main` já foi importado por outro teste

**File:** `tests/test_pipeline_fixes.py:113-114`

**Issue:** O teste importa `from api.main import app` dentro do bloco `with patch("api.main.settings")`. Como o Python armazena módulos em `sys.modules`, se `api.main` já foi importado por um teste anterior (ex: `test_api.py`), o `from api.main import app` é um no-op — retorna o módulo cacheado. O `lifespan` já executou com os settings reais, e a janela de patch não captura o log CRITICAL esperado. O teste passa de forma isolada mas pode falhar quando executado com a suite completa dependendo da ordem dos arquivos coletados pelo pytest.

```python
# Fix: usar importlib.reload para forçar re-execucao do lifespan com settings mockados,
# ou estruturar o teste sem depender de lifespan (mockar _check_cookies diretamente):
from unittest.mock import patch, call
import pipeline_module  # evita dependencia na ordem de import de api.main

def test_pipe05_check_cookies_logs_critical_without_sentinel(caplog, tmp_path):
    fake = tmp_path / "cookies.txt"
    fake.write_text("# Netscape HTTP Cookie File\nexample.com FALSE / FALSE 0 FOO bar\n")
    with caplog.at_level(logging.CRITICAL, logger="api.main"):
        from api.main import _check_cookies
        _check_cookies(str(fake))
    assert any("3PSID" in r.message for r in caplog.records if r.levelno >= logging.CRITICAL)
```

### WR-03: `import re as _re` dentro de bloco condicional em função (linha 302)

**File:** `pipeline.py:302`

**Issue:** O módulo `re` é importado condicionalmente dentro de `validate_wav`, apenas quando o fallback ffmpeg está ativo. Python armazena o módulo em `sys.modules` após o primeiro import, portanto não há custo de performance na segunda chamada — mas o padrão de import dentro de função é não convencional, oculta a dependência no topo do arquivo, e viola a convenção PEP 8 de colocar imports no nível do módulo. Qualquer leitor do cabeçalho do arquivo não saberá que `re` é usado.

```python
# Fix: mover para o topo do arquivo, junto com os demais imports stdlib:
import re   # adicionar na secao stdlib (linha ~20-27)

# E remover linha 302:
# import re as _re   <- remover

# Substituir uso na linha 304:
dur_match = re.search(r"Duration:\s+(\d+):(\d+):([\d.]+)", stderr_text)
```

### WR-04: Mensagem de falha em `test_pipe02_ffmpeg_dir_attribute_exists` é enganosa após DEPLOY-01

**File:** `tests/test_pipeline_fixes.py:40-42`

**Issue:** A mensagem de assert diz `"ffmpeg_location passed to yt-dlp must be the directory containing the binary"`, mas o comportamento correto após o fix DEPLOY-01 é passar o **executável** (`_YTDLP_FFMPEG_LOCATION`), não o diretório. Se este teste falhar em uma futura regressão, o desenvolvedor recebe uma instrução errada sobre como corrigir o problema.

```python
# Fix: atualizar a mensagem para refletir o comportamento atual:
assert os.path.isdir(pipeline._FFMPEG_DIR), (
    f"PIPE-02: _FFMPEG_DIR={pipeline._FFMPEG_DIR!r} nao e um diretorio. "
    "_FFMPEG_DIR e o diretorio-pai do binario; _YTDLP_FFMPEG_LOCATION aponta para "
    "o executavel (que pode ter nome versionado). Ambos devem ser definidos."
)
```

---

## Info

### IN-01: `tempfile` importado mas não utilizado em `tests/test_pipeline_fixes.py`

**File:** `tests/test_pipeline_fixes.py:90`

**Issue:** `import tempfile` aparece no segundo bloco de imports mas nunca é referenciado. O `tmp_path` fixture do pytest é usado em vez disso.

**Fix:** Remover `import tempfile` da linha 90.

### IN-02: `bpm` em `analyze_audio` retorna `int` mas docstring documenta `float`

**File:** `pipeline.py:517`

**Issue:** `round(float(bpm))` sem segundo argumento retorna `int` em Python 3. A docstring de `analyze_audio` declara `bpm (float)`. JSON serializa `int` e `float` de forma idêntica (sem `.0`), portanto não há impacto em runtime, mas o tipo anotado no contrato está incorreto e pode confundir type checkers ou consumidores da API que façam `isinstance(result["bpm"], float)`.

**Fix:** Documentar como `int` ou usar `round(float(bpm), 0)` se float for requerido (retornaria `128.0`). A opção mais clara é ajustar o docstring: `bpm (int) — BPM arredondado para inteiro`.

### IN-03: `pytest` e `pytest-subprocess` em `requirements.txt` de produção

**File:** `requirements.txt:6-7`

**Issue:** Dependências de teste estão no mesmo arquivo que dependências de produção. Em produção (Railway), `pytest` e `pytest-subprocess` são instalados desnecessariamente, aumentando o tempo de build e a superfície de ataque. O projeto não possui `requirements-dev.txt` separado.

**Fix:** Mover `pytest==9.0.3` e `pytest-subprocess>=1.5` para um arquivo `requirements-dev.txt`. Atualizar `nixpacks.toml` se necessário para instalar apenas `requirements.txt` em produção.

---

_Reviewed: 2026-05-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
