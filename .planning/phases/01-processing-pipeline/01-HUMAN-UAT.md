---
status: partial
phase: 01-processing-pipeline
source: [01-VERIFICATION.md]
started: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
---

## Current Test

[aguardando verificação manual no VPS]

## Tests

### 1. E2E pipeline contra as 3 URLs de referência (D-07)
expected: Cada URL produz JSON de sucesso com todos os campos D-05 e BPM plausível para o gênero
result: [pending]

### 2. Rejeição de vídeo longo em produção
expected: URL com >15min retorna {"type": "validation_error", ...} e exit code 1
result: [pending]

### 3. Limpeza de arquivos intermediários (D-09)
expected: Nenhum arquivo .webm/.m4a/.opus sobrevive após 3 downloads; apenas .wav permanece
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
