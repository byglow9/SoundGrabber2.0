---
status: partial
phase: 04-frontend
source: [04-VERIFICATION.md]
started: 2026-05-08T13:00:00Z
updated: 2026-05-08T13:00:00Z
---

## Current Test

Verificação manual parcial realizada em 2026-05-08.

## Tests

### 1. Fluxo completo com URL real
expected: URL YouTube válida → polling → card de resultado → botão "Baixar WAV" salva arquivo `soundgrabber_XXXXXXXX.wav`
result: pendente — requer cookies yt-dlp configurados (cookies_path vazio em dev)

### 2. Error handling visual — URL inválida
expected: URL não-YouTube mostra erro inline; classe `sg-url-input--error` adicionada ao campo
result: verificado — validação client-side funciona corretamente (testado com spotify.com)

### 3. API não shadowed em produção
expected: `POST /jobs` retorna JSON 202 com uvicorn real (não shadowed por StaticFiles)
result: verificado — logs uvicorn mostram `POST /jobs HTTP/1.1" 202 Accepted` com resposta JSON

## Summary

total: 3
passed: 2
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
