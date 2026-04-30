# Phase 1: Processing Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 01-processing-pipeline
**Areas discussed:** Auth yt-dlp, Contrato de saída, BPM trap beats, Output WAV + limpeza

---

## Auth yt-dlp

| Option | Description | Selected |
|--------|-------------|----------|
| Arquivo cookies.txt | Netscape format via YTDLP_COOKIES_FILE env var — funciona em qualquer host sem browser | ✓ |
| --cookies-from-browser | yt-dlp lê direto do perfil Chrome/Firefox — não funciona em servidor | |
| Hardcoded no script | Caminho fixo — má prática para repositório | |

**User's choice:** Arquivo cookies.txt via YTDLP_COOKIES_FILE

| Option | Description | Selected |
|--------|-------------|----------|
| Variável de ambiente | YTDLP_PO_TOKEN — padrão 12-factor, não entra no repo | ✓ |
| Arquivo .env | python-dotenv — conveniente para dev | |
| Argumento CLI --po-token | Fica no histórico do shell | |

**User's choice:** YTDLP_PO_TOKEN env var

---

## Contrato de saída

| Option | Description | Selected |
|--------|-------------|----------|
| Módulo importável | pipeline.py com funções separadas — Fase 2 importa diretamente | ✓ |
| Script monolítico | Tudo num arquivo linear — Fase 2 reimplementa | |

**User's choice:** Módulo importável (pipeline.py)

| Option | Description | Selected |
|--------|-------------|----------|
| JSON | {bpm, key, camelot, bpm_half, bpm_double, wav_path, duration_sec} | ✓ |
| Humano legível | Texto formatado para terminal | |

**User's choice:** JSON no stdout

---

## BPM trap beats

| Option | Description | Selected |
|--------|-------------|----------|
| Half/double automático | Sempre exibir os 3 valores — cobre trap sem heurísticas | ✓ |
| start_bpm customizado | Forçar librosa na faixa do trap — pode quebrar outros gêneros | |
| Dois algoritmos + voto | Mais robusto, mais complexo | |

**User's choice:** Half/double automático

**URLs de teste fornecidas pelo usuário:**
- `https://www.youtube.com/watch?v=b1f6o0GMT8c` — estilo rock/lo-fi
- `https://www.youtube.com/watch?v=npoTcSToYTc` — estilo trap
- Planner escolhe o 3º (house ou lo-fi)

---

## Output WAV + limpeza

| Option | Description | Selected |
|--------|-------------|----------|
| /tmp com nome único | /tmp/sg_{uuid}.wav — limpeza automática previne acúmulo | ✓ |
| Diretório configurável | OUTPUT_DIR env var — mais flexível, mais config | |

**User's choice:** /tmp/sg_{uuid}.wav

| Option | Description | Selected |
|--------|-------------|----------|
| try/finally no pipeline | Cada função limpa seus intermediários — WAV final fica para Fase 2 | ✓ |
| Sweeper periódico apenas | Background process varre /tmp — depósito de lixo em falhas | |

**User's choice:** try/finally no pipeline

---

## Claude's Discretion

- Parâmetros internos do librosa (sr, hop_length, etc.)
- Biblioteca ou tabela estática para Camelot notation
- Nome exato do arquivo de cookies e variáveis de ambiente adicionais

## Deferred Ideas

Nenhuma — discussão manteve-se dentro do escopo da Fase 1.
