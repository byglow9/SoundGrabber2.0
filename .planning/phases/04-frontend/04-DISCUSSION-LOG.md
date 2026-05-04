# Phase 4: Frontend - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 04-frontend
**Areas discussed:** Polling de progresso, Recovery de erros, Estimativa de tamanho WAV, Limite Phase 4 vs Phase 5

---

## Polling de progresso

| Option | Description | Selected |
|--------|-------------|----------|
| 2 segundos fixo | Simples, previsível, alinhado com ROADMAP.md success criteria | ✓ |
| Adaptativo: rápido depois lento | 1s nos primeiros 10s, depois 3s | |
| Adaptativo: lento depois rápido | 5s no início, 1s quando 'analyzing' | |

**User's choice:** 2 segundos fixo

| Option | Description | Selected |
|--------|-------------|----------|
| 3 minutos | Margem confortável acima do limite de 15 min de vídeo | ✓ |
| 5 minutos | Mais conservador para servidores lentos | |
| Sem timeout fixo | Apenas detecta erro via status 'failed' ou 404 | |

**User's choice:** 3 minutos

---

## Recovery de erros

| Option | Description | Selected |
|--------|-------------|----------|
| Mantém a URL + destaca o campo | Usuário vê o que colou e pode editar | ✓ |
| Limpa o campo | Usuário precisa colar de novo | |

**User's choice (422 URL inválida):** Mantém a URL + destaca o campo

| Option | Description | Selected |
|--------|-------------|----------|
| Countdown ao vivo | Usa header Retry-After, botão desabilitado durante espera | ✓ |
| Mensagem estática | "Tente em 1 minuto" sem countdown | |

**User's choice (429 rate limit):** Countdown ao vivo com Retry-After

| Option | Description | Selected |
|--------|-------------|----------|
| Botão explícito 'Tentar novamente' | Reutiliza URL já no campo, um clique reinicia o fluxo | ✓ |
| Só mensagem de erro | Usuário clica no botão principal para tentar de novo | |

**User's choice (job failed):** Botão explícito 'Tentar novamente'

---

## Estimativa de tamanho WAV

| Option | Description | Selected |
|--------|-------------|----------|
| Frontend calcula de duration_sec | JS usa fórmula 44100×2×2, zero mudança na API | ✓ |
| API adiciona wav_size_bytes | stat() no arquivo WAV, mais preciso mas acoplado ao filesystem | |
| Exibir apenas duração, sem estimativa | Não atende UX-02 literalmente | |

**User's choice:** Frontend calcula de duration_sec

| Option | Description | Selected |
|--------|-------------|----------|
| 44100 Hz estéreo (CD quality) | Padrão FFmpegExtractAudio com codec wav | ✓ |
| Não sei, Claude decide | Planner verifica a saída real do FFmpeg | |

**User's choice:** 44100 Hz estéreo (CD quality)

---

## Limite Phase 4 vs Phase 5

**User's response ao invés de escolher uma opção:** forneceu URL `https://www.neoworlds.online/` como referência visual para Phase 5.

**Clarificação:** Phase 5 usa neoworlds.online como inspiração. Phase 4 entrega funcional sem estilo.

| Option | Description | Selected |
|--------|-------------|----------|
| Div-based genérico | Phase 4 usa divs simples, Phase 5 reescreve estrutura para Y2K | ✓ |
| Já com estrutura Y2K (tabelas) | Constrói tabelas desde o início, risco de misturar responsabilidades | |

**User's choice (estrutura HTML):** Div-based genérico

---

## Claude's Discretion

- Como FastAPI serve o index.html (StaticFiles, Jinja2 ou rota GET /)
- Estrutura interna do JS: state machine, event listeners, organização vanilla JS
- Classes/IDs no HTML para Phase 5 conectar estilos
- Se download_url precisa ser construído no frontend ou já vem da task Celery

## Deferred Ideas

- Estética Y2K/neoworlds.online — Phase 5 integralmente
- CORS configuration — fora do escopo v1
- Waveform visualization — v2 (já no REQUIREMENTS.md)
- Progressive enhancement (versão sem JS) — fora do escopo v1
