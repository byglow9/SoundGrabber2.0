---
status: partial
phase: 08-pipeline-code-fixes
source: [08-VERIFICATION.md]
started: 2026-05-11T00:00:00Z
updated: 2026-05-11T00:00:00Z
---

## Current Test

[aguardando verificação humana no Railway]

## Tests

### 1. nixpacks.toml instala ffmpeg no container Railway (DEPLOY-01 / Critério 2)
expected: Após deploy com nixpacks.toml atual, `ffprobe -version` funciona dentro do container Railway. O log do worker não mostra FileNotFoundError para ffprobe. `shutil.which("ffprobe")` retorna `/usr/bin/ffprobe` no ambiente Railway.
result: [pending]

### 2. Download sem erros nsig em instância Railway recém-deployada (PIPE-03 / Critério 4)
expected: Submeter um beat URL para instância Railway sem cache de JS do yt-dlp (fresh deploy ou `--no-cache-dir` ativo) resulta em job `status=done` sem mensagens de `nsig extraction` nos logs do Celery worker.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
