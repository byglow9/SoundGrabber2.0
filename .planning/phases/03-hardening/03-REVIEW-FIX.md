---
phase: 03-hardening
fixed_at: 2026-05-04T00:00:00Z
review_path: .planning/phases/03-hardening/03-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-05-04
**Source review:** .planning/phases/03-hardening/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, WR-01, WR-02, WR-03, WR-04)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Rate limiter trusts X-Forwarded-For without proxy verification

**Files modified:** `api/main.py`
**Commit:** 6d97583
**Applied fix:** Removido import de `get_ipaddr` (slowapi.util). Adicionada função `_real_ip(request)` que retorna `request.client.host` — IP definido pelo ASGI layer a partir da conexão TCP, não spoofável via header. O `Limiter` agora usa `key_func=_real_ip`.

---

### WR-01: `app.add_exception_handler` sem `SlowAPIMiddleware` — handler pode não disparar

**Files modified:** `api/main.py`
**Commit:** c3ef6b2
**Applied fix:** Adicionado `from slowapi.middleware import SlowAPIMiddleware` e `app.add_middleware(SlowAPIMiddleware)` após o registro do exception handler. Adicionado guard `if hasattr(request.state, "view_rate_limit"):` antes de chamar `_inject_headers`, evitando `AttributeError` defensivamente.

---

### WR-02: `Settings` campos avaliados em tempo de importação — env vars tardias ignoradas

**Files modified:** `api/config.py`
**Commit:** 4e2d418
**Applied fix:** Adicionado `field` ao import de `dataclasses`. Todos os campos da classe `Settings` convertidos de valores padrão diretos (`os.environ.get(...)`) para `field(default_factory=lambda: os.environ.get(...))`. A factory é avaliada em tempo de instanciação (`Settings()`), não de definição da classe — elimina dependência frágil de ordem de import.

---

### WR-03: `_redis.expire(JOB_REGISTRY_KEY, wav_ttl)` reseta TTL do set inteiro

**Files modified:** `api/main.py`
**Commit:** e466e8f
**Applied fix:** Substituído `_redis.sadd(JOB_REGISTRY_KEY, task.id)` + `_redis.expire(JOB_REGISTRY_KEY, settings.wav_ttl)` por `_redis.set(f"sg:job:{task.id}", "1", ex=settings.wav_ttl)` — TTL individual por job. Em `get_job`, substituído `_redis.sismember(JOB_REGISTRY_KEY, job_id)` por `_redis.exists(f"sg:job:{job_id}")`. Constante `JOB_REGISTRY_KEY` removida e substituída por comentário explicativo do novo padrão de chave.

---

### WR-04: `conftest.py` usa `KEYS` sem `decode_responses` — bloqueante e falha silenciosa

**Files modified:** `tests/conftest.py`
**Commit:** b086c1c
**Applied fix:** Substituído `redis_lib.from_url(...)` sem opções por cliente com `decode_responses=True`. Substituído loop `for key in _r.keys("LIMITS:LIMITER*")` por loop SCAN não-bloqueante (`cursor, keys = _r.scan(cursor, match="LIMITS:LIMITER*", count=100)`) que itera até `cursor == 0`. Elimina bloqueio O(N) e garante que chaves retornadas são strings, não bytes.

---

## Skipped Issues

Nenhum finding foi pulado — todos os 5 findings em escopo foram corrigidos com sucesso.

---

_Fixed: 2026-05-04_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
