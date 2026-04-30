# Phase 1: Processing Pipeline - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Script Python standalone (`pipeline.py`) que prova o pipeline yt-dlp → FFmpeg → librosa funciona a partir do host de produção. Sem API, sem UI, sem servidor — só validação funcional do núcleo do sistema. A Fase 2 importará este módulo diretamente.

</domain>

<decisions>
## Implementation Decisions

### Auth yt-dlp
- **D-01:** Cookies fornecidos via arquivo Netscape format (`cookies.txt`). Caminho configurado pela env var `YTDLP_COOKIES_FILE`. Não depende de browser instalado no servidor.
- **D-02:** PO Token fornecido via env var `YTDLP_PO_TOKEN`. Padrão 12-factor app — não entra no repositório, fácil de rotar.

### Estrutura do módulo
- **D-03:** `pipeline.py` é um módulo importável com funções separadas por estágio: `download_audio(url, cookies_path, po_token) -> Path`, `convert_to_wav(audio_path) -> Path`, `analyze_audio(wav_path) -> dict`. A Fase 2 importa diretamente — zero retrabalho.
- **D-04:** `if __name__ == '__main__':` no mesmo arquivo serve como entry point de validação na Fase 1.

### Contrato de saída (stdout)
- **D-05:** Output em JSON no stdout. Campos obrigatórios: `bpm`, `key`, `camelot`, `bpm_half`, `bpm_double`, `wav_path`, `duration_sec`. Parseável por scripts e pela Fase 2 sem transformação.

### BPM e análise musical
- **D-06:** Estratégia half/double automático — sempre exibir os 3 valores (BPM detectado pelo librosa + metade + dobro). Cobre trap sem heurísticas ou start_bpm customizado. Implementa ANALYSIS-03 diretamente.
- **D-07:** URLs de referência para validação de BPM (sucesso = dentro de 30% do feel-tempo real):
  - `https://www.youtube.com/watch?v=b1f6o0GMT8c` — estilo rock/lo-fi (fornecido pelo usuário)
  - `https://www.youtube.com/watch?v=npoTcSToYTc` — estilo trap (fornecido pelo usuário)
  - Planner escolhe o 3º URL representando house ou lo-fi

### Output WAV e limpeza de arquivos
- **D-08:** WAV final salvo em `/tmp/sg_{uuid}.wav`. Nome único por execução previne colisões. A Fase 2 serve este arquivo via HTTP e gerencia a deleção pós-download.
- **D-09:** Arquivos intermediários (áudio bruto pré-conversão) limpos com `try/finally` dentro das funções do pipeline. WAV final **não** é deletado pelo pipeline — é responsabilidade da Fase 2.
- **D-10:** Limite de 15 minutos (CORE-05): verificado antes de iniciar download usando `yt-dlp --dump-json` para obter duração. Rejeição retorna erro descritivo no JSON de saída.

### Claude's Discretion
- Parâmetros internos do librosa para detecção de BPM (sr, hop_length, etc.) — planner decide baseado em boas práticas e performance
- Biblioteca Python para Camelot notation (se existe pronta) ou implementar tabela estática — planner decide
- Nome exato do arquivo de cookies e variáveis de ambiente adicionais de configuração

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Projeto
- `.planning/PROJECT.md` — visão, princípios, restrições críticas do projeto
- `.planning/REQUIREMENTS.md` — requisitos com REQ-IDs; Phase 1 cobre CORE-03, CORE-04, CORE-05, ANALYSIS-01–04
- `.planning/ROADMAP.md` — success criteria detalhado para Phase 1 (seção "Phase Details")
- `.planning/STATE.md` — riscos conhecidos (half-tempo trap, temp files, yt-dlp drift) e todos pendentes

### Riscos críticos registrados no STATE.md
- Datacenter IP flagging → cookies + PO Token obrigatórios desde o primeiro teste
- Half-tempo BPM misdetection → mitigado por D-06 (half/double automático)
- Temp file accumulation → mitigado por D-09 (try/finally)
- yt-dlp version drift → ffprobe validation em cada arquivo baixado

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Nenhum — projeto novo sem código existente.

### Established Patterns
- Nenhum — Phase 1 estabelece os padrões que as fases seguintes seguirão.

### Integration Points
- `pipeline.py` é o ponto de integração central: Fase 2 (FastAPI + Celery) importará `download_audio`, `convert_to_wav`, `analyze_audio` diretamente sem reimplementar.

</code_context>

<specifics>
## Specific Ideas

- Preview do nome de arquivo: `/tmp/sg_{uuid}.wav` — prefixo `sg_` facilita identificação e limpeza seletiva em varreduras futuras
- Output JSON shape confirmado pelo usuário: `{"bpm": 140, "key": "F# minor", "camelot": "4A", "bpm_half": 70, "bpm_double": 280, "wav_path": "/tmp/sg_abc123.wav", "duration_sec": 183}`
- URLs de teste reais fornecidos pelo usuário — usar estes no plano de validação, não inventar outros

</specifics>

<deferred>
## Deferred Ideas

Nenhuma — discussão manteve-se dentro do escopo da Fase 1.

</deferred>

---

*Phase: 01-processing-pipeline*
*Context gathered: 2026-04-29*
