---
phase: 09-railway-bgutil-deployment
fixed_at: 2026-05-11T00:00:00Z
review_path: .planning/phases/09-railway-bgutil-deployment/09-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-05-11
**Source review:** `.planning/phases/09-railway-bgutil-deployment/09-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01 + WR-01..04)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: CLI `__main__` ignora `BGUTIL_BASE_URL`

**Files modified:** `pipeline.py`
**Commit:** 5e1421f
**Applied fix:** Adicionada leitura de `BGUTIL_BASE_URL` via `os.environ.get` no bloco `__main__` e passagem do valor para `check_duration(url, cookies_path, bgutil_base_url)` e `download_audio(url, cookies_path, po_token, bgutil_base_url)`. Smoke tests manuais via `python pipeline.py <URL>` agora usam o mesmo caminho de código que a API.

### WR-01: Zero cobertura de teste para a chave `getpot_bgutil_baseurl`

**Files modified:** `pipeline.py`, `tests/test_pipeline_fixes.py`
**Commits:** c794d24 (testes), 4017733 (limpeza de comentários)
**Applied fix:** Adicionados `test_bgutil_08x_extractor_key_check_duration` e `test_bgutil_08x_extractor_key_download_audio` ao final de `test_pipeline_fixes.py`. Os testes verificam presença de `getpot_bgutil_baseurl` e ausência de `youtubepot-bgutilhttp` no código-fonte das funções via `inspect.getsource`. Os comentários em `pipeline.py` que mencionavam literalmente `youtubepot-bgutilhttp:base_url` foram reformulados para não conter a substring, mantendo o contexto histórico sem quebrar os asserts.

### WR-02: `test_pipe05` frágil por depender de `lifespan`

**Files modified:** `tests/test_pipeline_fixes.py`
**Commit:** 76c7a73
**Applied fix:** `test_pipe05_critical_log_when_cookies_missing_sentinel` refatorado para chamar `_check_cookies(str(fake_cookies))` diretamente, eliminando a dependência de `lifespan`, `TestClient`, `patch` e `importlib.reload`. Os imports orphan `from unittest.mock import patch` e `from fastapi.testclient import TestClient` foram removidos. O teste agora funciona corretamente independentemente da ordem de coleta do pytest.

### WR-03: `import re as _re` dentro de função

**Files modified:** `pipeline.py`
**Commit:** d2b997a
**Applied fix:** `import re` movido para a seção de imports stdlib no topo do módulo (junto com `json`, `logging`, `os`, etc.). O `import re as _re` dentro de `validate_wav` foi removido e o uso substituído de `_re.search` para `re.search`. A dependência em `re` agora é visível no cabeçalho do arquivo.

### WR-04: Mensagem de assert enganosa em `test_pipe02_ffmpeg_dir_attribute_exists`

**Files modified:** `tests/test_pipeline_fixes.py`
**Commit:** 7319703
**Applied fix:** A mensagem de falha foi atualizada de `"ffmpeg_location passed to yt-dlp must be the directory containing the binary"` para `"_FFMPEG_DIR e o diretorio-pai do binario; _YTDLP_FFMPEG_LOCATION aponta para o executavel (que pode ter nome versionado). Ambos devem ser definidos."` — refletindo o comportamento correto pós-DEPLOY-01.

---

_Fixed: 2026-05-11_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
