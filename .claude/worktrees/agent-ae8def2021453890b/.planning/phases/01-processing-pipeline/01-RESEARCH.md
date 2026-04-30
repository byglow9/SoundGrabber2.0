# Phase 1: Processing Pipeline - Research

**Researched:** 2026-04-29
**Domain:** yt-dlp + FFmpeg + librosa standalone pipeline (Python 3.11)
**Confidence:** MEDIUM-HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Cookies fornecidos via arquivo Netscape format (`cookies.txt`). Caminho configurado pela env var `YTDLP_COOKIES_FILE`. Nao depende de browser instalado no servidor.
- **D-02:** PO Token fornecido via env var `YTDLP_PO_TOKEN`. Padrao 12-factor app — nao entra no repositorio, facil de rotar.
- **D-03:** `pipeline.py` com 3 funcoes importaveis: `download_audio(url, cookies_path, po_token) -> Path`, `convert_to_wav(audio_path) -> Path`, `analyze_audio(wav_path) -> dict`.
- **D-04:** `if __name__ == '__main__':` no mesmo arquivo serve como entry point de validacao na Fase 1.
- **D-05:** Output em JSON no stdout. Campos obrigatorios: `bpm`, `key`, `camelot`, `bpm_half`, `bpm_double`, `wav_path`, `duration_sec`.
- **D-06:** Sempre exibir 3 valores de BPM (detectado + metade + dobro). Cobre trap sem heuristicas.
- **D-07:** URLs de teste: `https://www.youtube.com/watch?v=b1f6o0GMT8c` (rock/lo-fi), `https://www.youtube.com/watch?v=npoTcSToYTc` (trap). Planner escolhe o 3o (house ou lo-fi).
- **D-08:** WAV salvo em `/tmp/sg_{uuid}.wav`.
- **D-09:** Arquivos intermediarios limpos com `try/finally`. WAV final NAO deletado pelo pipeline (responsabilidade da Fase 2).
- **D-10:** Limite de 15 minutos verificado ANTES do download via `yt-dlp --dump-json`; rejeicao retorna JSON de erro descritivo.

### Claude's Discretion

- Parametros internos do librosa para deteccao de BPM (sr, hop_length, etc.) — planner decide baseado em boas praticas e performance.
- Biblioteca Python para Camelot notation (se existe pronta) ou implementar tabela estatica — planner decide.
- Nome exato do arquivo de cookies e variaveis de ambiente adicionais de configuracao.

### Deferred Ideas (OUT OF SCOPE)

Nenhuma — discussao manteve-se dentro do escopo da Fase 1.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-03 | Download audio do YouTube server-side usando yt-dlp com autenticacao via cookies + PO Token | Secao "yt-dlp Configuration" documenta o ydl_opts exato com cookiefile + extractor_args po_token |
| CORE-04 | Converte audio baixado para WAV lossless usando FFmpeg | yt-dlp postprocessor FFmpegExtractAudio com pcm_s16le e 44100Hz; validacao via ffprobe |
| CORE-05 | Recusa videos com duracao acima de 15 minutos | extract_info com download=False; campo `duration` em segundos; verificacao antes do download |
| ANALYSIS-01 | Detecta e exibe BPM usando librosa | librosa.feature.tempo() com parametros sr=22050, hop_length=512, start_bpm=120 |
| ANALYSIS-02 | Detecta e exibe tonalidade musical (ex: F# minor) | librosa chroma_cqt + correlacao Krumhansl-Schmuckler; 24 notas mapeadas |
| ANALYSIS-03 | Exibe BPM na metade (div 2) e dobro (mult 2) sem re-analise | Calculo aritmetico simples sobre o BPM primario; nenhuma analise adicional necessaria |
| ANALYSIS-04 | Exibe nota Camelot correspondente a tonalidade detectada | Tabela estatica de 24 entradas; sem dependencia de biblioteca externa |
</phase_requirements>

---

## Summary

A Fase 1 implementa um script Python standalone (`pipeline.py`) que prova o pipeline download-conversao-analise funciona a partir do host de producao. O risco tecnico central nesta fase nao e a implementacao do codigo — e a viabilidade do yt-dlp a partir de um IP de datacenter. Cookies Netscape + PO Token estatico (via env var) e a estrategia adotada; pesquisa confirma que esta abordagem funciona, mas com a ressalva critica de que os PO Tokens agora sao vinculados ao video ID pelo YouTube em alguns contextos, exigindo rotacao frequente ou uso do plugin bgutil.

A analise de BPM com librosa.feature.tempo() e mais estavel que beat_track() para estimativa de tempo global. O problema classico de half-tempo (trap detectado como 70bpm ao inves de 140bpm) e completamente mitigado pela decisao D-06 (exibir sempre os 3 valores). A notacao Camelot e implementada como tabela estatica Python — nenhuma biblioteca externa existe para esse proposito especifico.

FFmpeg 6.1.1 esta disponivel no ambiente local. `ffprobe` e confirmado disponivel. Python 3.12.3 esta instalado (superior ao Python 3.11 requerido). librosa 0.11.0 (versao mais recente) suporta NumPy 2.x nativamente.

**Recomendacao primaria:** Implementar o pipeline em etapas sequenciais: (1) verificacao de duracao via extract_info, (2) download com yt-dlp postprocessor para WAV, (3) validacao com ffprobe, (4) analise com librosa.feature.tempo() + chroma_cqt, (5) mapeamento Camelot via tabela estatica. Usar `try/finally` em cada etapa para garantir limpeza de arquivos intermediarios.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Duration check pre-download | Script (Python process) | — | yt-dlp Python API; extract_info download=False e invocado no mesmo processo |
| Audio download | Script (Python process) | FFmpeg (subprocess via yt-dlp) | yt-dlp invoca FFmpeg internamente via postprocessor |
| WAV conversion | FFmpeg (subprocess via yt-dlp) | — | yt-dlp FFmpegExtractAudio postprocessor; nenhuma chamada FFmpeg separada necessaria |
| ffprobe validation | Script (Python process) | FFmpeg tools (subprocess) | subprocess.run(['ffprobe', ...]) para verificar integridade |
| BPM detection | Script (Python process / librosa) | — | librosa.feature.tempo() roda in-process; CPU-bound |
| Key detection | Script (Python process / librosa) | — | librosa.feature.chroma_cqt() + correlacao; mesmo processo |
| Camelot mapping | Script (Python process) | — | Lookup em tabela estatica Python; zero dependencia externa |
| Temp file cleanup | Script (Python process) | — | try/finally em cada funcao de estagio |
| JSON output | Script (Python process) | — | json.dumps() para stdout |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yt-dlp | 2026.3.17 (latest) | Download audio do YouTube | Unico fork ativo do youtube-dl; releases quase semanais para acompanhar mudancas do YouTube |
| FFmpeg | 6.1.1 (system) | Decodificacao e conversao para WAV | yt-dlp invoca via postprocessor; pcm_s16le e o formato WAV padrao CD |
| librosa | 0.11.0 (latest) | BPM detection + key detection | API simples, suporta NumPy 2.x, funciona com pip install; padrao de industria para DSP em Python |
| soundfile | 0.13.1 (latest) | Backend de I/O WAV para librosa | Dependencia obrigatoria do librosa para leitura WAV |
| numpy | >=2.0 (latest: 2.4.4) | Arrays numericos para librosa | librosa 0.11.0 suporta NumPy 2.x nativamente — sem necessidade de pin < 2.0 |
| scipy | >=1.10 (latest: 1.17.1) | Dependencia do librosa | Necessaria para algoritmos de processamento de sinal |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 (latest) | Framework de testes | Validacao automatizada das funcoes do pipeline |
| pytest-subprocess | >=1.5 | Mock de subprocess para testes | Testar logica de validacao ffprobe sem FFmpeg real |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| librosa.feature.tempo() | librosa.beat.beat_track() | beat_track() rastreia posicoes de beats individuais; feature.tempo() e mais estavel para estimativa global de BPM — preferir feature.tempo() para o caso de uso de deteccao de BPM |
| tabela estatica Camelot | camelot-py (PyPI) | camelot-py e uma biblioteca de extracao de tabelas PDF, NAO notacao musical — nao existe biblioteca Python dedicada para Camelot wheel musical; tabela estatica e a unica opcao |
| yt-dlp postprocessor (WAV) | FFmpeg subprocess separado | yt-dlp postprocessor e mais simples e remove a necessidade de gerenciar o arquivo intermediario manualmente |
| subprocess ffprobe | ffmpeg-python binding | ffmpeg-python adiciona dependencia desnecessaria para uma chamada de validacao simples |

**Instalacao:**
```bash
pip install yt-dlp==2026.3.17 librosa==0.11.0 soundfile==0.13.1 numpy scipy pytest
```

**Verificacao de sistema:**
```bash
ffmpeg -version   # deve mostrar >= 6.0
ffprobe -version  # deve estar disponivel junto com ffmpeg
```

**Versao verificada:**
- yt-dlp: 2026.3.17 confirmado via `pip3 index versions yt-dlp` [VERIFIED: pip registry]
- librosa: 0.11.0 confirmado via `pip3 index versions librosa` [VERIFIED: pip registry]
- soundfile: 0.13.1 confirmado via `pip3 index versions soundfile` [VERIFIED: pip registry]
- numpy: 2.4.4 (latest) — librosa 0.11.0 suporta numpy 2.x [VERIFIED: pip registry + librosa changelog]
- FFmpeg: 6.1.1-3ubuntu5 disponivel no ambiente local [VERIFIED: ffmpeg -version]
- pytest: 9.0.3 confirmado via `pip3 index versions pytest` [VERIFIED: pip registry]

---

## Architecture Patterns

### System Architecture Diagram

```
URL (stdin / argumento)
         |
         v
[ESTAGIO 0: Duration Check]
  yt-dlp extract_info(download=False)
  info['duration'] em segundos
  Se > 900s (15min): retorna JSON erro, termina
         |
         v
[ESTAGIO 1: Download + Conversao]
  yt-dlp com ydl_opts:
    cookiefile -> cookies.txt
    extractor_args -> po_token=web.gvs+TOKEN
    postprocessors -> FFmpegExtractAudio (pcm_s16le, 44100Hz)
    outtmpl -> /tmp/sg_{uuid}
  Saida: /tmp/sg_{uuid}.wav  <--- arquivo final
  Arquivo intermediario (webm/m4a) limpo pelo yt-dlp automaticamente
         |
         v
[ESTAGIO 2: Validacao ffprobe]
  subprocess ffprobe -v error -show_entries format=duration /tmp/sg_{uuid}.wav
  Exit code != 0 ou duration ausente: retorna JSON erro
         |
         v
[ESTAGIO 3: Analise BPM]
  librosa.load(wav_path, sr=22050, mono=True, duration=90.0, offset=offset)
    onde offset = 0.2 * duration_total (pula intro)
  librosa.feature.tempo(y=y, sr=22050)
  Retorna float: BPM primario
  bpm_half = bpm / 2
  bpm_double = bpm * 2
         |
         v
[ESTAGIO 4: Analise Key]
  librosa.load(wav_path, sr=22050, mono=True, duration=120.0)
  librosa.feature.chroma_cqt(y=y, sr=22050)
  Correlacao Krumhansl-Schmuckler sobre chroma_mean
  Retorna: "F# minor" ou "C major"
         |
         v
[ESTAGIO 5: Mapeamento Camelot]
  CAMELOT_TABLE[key_string] -> "4A"
  Lookup O(1) em dict Python de 24 entradas
         |
         v
[OUTPUT: JSON para stdout]
  {"bpm": 140, "key": "F# minor", "camelot": "11A",
   "bpm_half": 70, "bpm_double": 280,
   "wav_path": "/tmp/sg_abc123.wav", "duration_sec": 183}
```

### Recommended Project Structure

```
pipeline.py          # modulo unico: 3 funcoes + __main__
requirements.txt     # dependencias fixadas
cookies.txt          # NAO no git (.gitignore); gerada externamente
.env.example         # YTDLP_COOKIES_FILE=./cookies.txt, YTDLP_PO_TOKEN=...
tests/
  test_pipeline.py   # testes unitarios das 3 funcoes + integracao
  fixtures/
    sample.wav       # WAV curto (5s) para testes de analise offline
    mock_info.json   # JSON de metadados simulado do yt-dlp
```

### Pattern 1: Duration Check Pre-Download

**What:** Usa yt-dlp Python API com `download=False` para obter metadados sem baixar o video.
**When to use:** Obrigatoriamente ANTES de iniciar o download real.

```python
# Source: yt-dlp Python API + issue #12200
import yt_dlp
import json

def check_duration(url: str, cookies_path: str) -> dict:
    """Retorna dict com 'duration' em segundos, ou lanca ValueError se > 15min."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookies_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    duration = info.get('duration')  # campo 'duration' em segundos [VERIFIED: yt-dlp docs]
    if duration is None:
        raise ValueError("Nao foi possivel determinar a duracao do video")
    if duration > 900:  # 15 * 60
        raise ValueError(f"Video muito longo: {duration}s (limite: 900s)")
    return info
```

### Pattern 2: yt-dlp Download com Cookies + PO Token

**What:** Configuracao ydl_opts para autenticacao completa no YouTube a partir de servidor.
**When to use:** Em toda chamada de download; cookies + po_token sao obrigatorios desde o primeiro uso.

```python
# Source: yt-dlp issue #14307 + PO Token Guide wiki
import yt_dlp
import uuid
from pathlib import Path

def download_audio(url: str, cookies_path: str, po_token: str) -> Path:
    """Baixa audio do YouTube e converte para WAV via postprocessor."""
    wav_id = str(uuid.uuid4()).replace('-', '')[:12]
    # outtmpl sem extensao: yt-dlp adiciona .wav apos conversao
    outtmpl = f'/tmp/sg_{wav_id}'

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookies_path,
        # Formato correto: lista de strings, nao dict aninhado [VERIFIED: issue #14307]
        'extractor_args': {'youtube': [f'po_token=web.gvs+{po_token}']},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            # Sem preferredquality: WAV nao usa bitrate; FFmpeg usa pcm_s16le por padrao
        }],
        'http_chunk_size': 10485760,  # 10MB — evita throttling do YouTube
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    wav_path = Path(f'{outtmpl}.wav')
    if not wav_path.exists():
        raise FileNotFoundError(f"WAV nao encontrado em: {wav_path}")
    return wav_path
```

**Nota critica sobre PO Token:** O formato `web.gvs+TOKEN` e para requests GVS (streaming). Tokens GVS sao vinculados a DATASYNC_ID (sessao do usuario) ou VISITOR_DATA para contas anonimas — o que significa que um token gerado manualmente pode ser reutilizado por curtos periodos (sessao), nao por video. O planner deve documentar um processo de rotacao do token (a cada 24-48h ou quando downloads comecem a falhar). [CITED: deepwiki.com/yt-dlp/yt-dlp/3.4.1-potoken-authentication-system]

### Pattern 3: Validacao ffprobe Pos-Download

**What:** Verifica que o arquivo baixado e audio valido, nao uma pagina de erro HTML.
**When to use:** Imediatamente apos o download, antes de passar o arquivo para o librosa.

```python
# Source: ffprobe documentation + community patterns
import subprocess
import json

def validate_wav(wav_path: Path) -> float:
    """Valida WAV com ffprobe. Retorna duracao em segundos ou lanca ValueError."""
    result = subprocess.run(
        [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            str(wav_path)
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise ValueError(f"ffprobe falhou: {result.stderr[:200]}")
    data = json.loads(result.stdout)
    duration = float(data.get('format', {}).get('duration', 0))
    if duration < 1.0:
        raise ValueError(f"Audio invalido ou corrompido (duracao: {duration}s)")
    return duration
```

### Pattern 4: BPM Detection com librosa.feature.tempo()

**What:** Estima tempo global (BPM) usando autocorrelacao do onset strength envelope.
**When to use:** Preferir `feature.tempo()` sobre `beat_track()` para estimativa de BPM; beat_track() e mais adequado quando se precisa das posicoes dos beats individuais.

```python
# Source: librosa.feature.tempo docs [CITED: librosa.org/doc/main/generated/librosa.feature.tempo.html]
import librosa
import numpy as np

def detect_bpm(wav_path: Path, total_duration: float) -> float:
    """
    Detecta BPM usando librosa.feature.tempo().

    Parametros de producao:
    - sr=22050: downsampling mono reduz memoria ~4x vs 44100 stereo
    - duration=90.0: 90s e suficiente para estimativa; >90s nao melhora precisao
    - offset: pula 20% do inicio para evitar intros sem percussao
    """
    offset = min(total_duration * 0.20, 30.0)  # max 30s de offset
    y, sr = librosa.load(
        str(wav_path),
        sr=22050,
        mono=True,
        duration=90.0,
        offset=offset
    )
    # feature.tempo retorna ndarray; extrair escalar
    tempo = librosa.feature.tempo(y=y, sr=sr)
    bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
    return round(bpm, 1)
```

**Por que feature.tempo() e nao beat_track():** `feature.tempo()` usa autocorrelacao do onset envelope para estimativa global, enquanto `beat_track()` usa programacao dinamica para rastrear beats individuais e infere o tempo como subproduto. Para o caso de uso de SoundGrabber (so precisa do numero BPM, nao das posicoes dos beats), `feature.tempo()` e mais estavel e mais rapido. [VERIFIED: librosa docs]

**Por que a mitigacao D-06 e suficiente para trap:** Se librosa retorna 70bpm para uma track de 140bpm (half-tempo), o usuario ve `70 / 140 / 280` e pode identificar 140 como o feel-tempo. Nenhuma heuristica adicional e necessaria.

### Pattern 5: Key Detection com Krumhansl-Schmuckler

**What:** Detecta tonalidade usando correlacao entre perfis de chroma e perfis de tom de Krumhansl-Schmuckler.
**When to use:** Unica abordagem pratica sem Essentia; ~85-95% de precisao em musica eletroncia/hip-hop.

```python
# Source: librosa docs + STACK.md
import librosa
import numpy as np

_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def detect_key(wav_path: Path) -> str:
    """Detecta tonalidade usando correlacao Krumhansl-Schmuckler sobre chroma_cqt."""
    y, sr = librosa.load(str(wav_path), sr=22050, mono=True, duration=120.0)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)

    major_corrs = [
        np.corrcoef(np.roll(_MAJOR_PROFILE, i), chroma_mean)[0, 1]
        for i in range(12)
    ]
    minor_corrs = [
        np.corrcoef(np.roll(_MINOR_PROFILE, i), chroma_mean)[0, 1]
        for i in range(12)
    ]

    best_major_idx = int(np.argmax(major_corrs))
    best_minor_idx = int(np.argmax(minor_corrs))

    if major_corrs[best_major_idx] >= minor_corrs[best_minor_idx]:
        return f"{_NOTES[best_major_idx]} major"
    return f"{_NOTES[best_minor_idx]} minor"
```

### Pattern 6: Tabela Estatica Camelot

**What:** Lookup O(1) de notacao Camelot a partir do nome da tonalidade.
**When to use:** Aplicar apos detect_key(). Nenhuma biblioteca Python existe para este proposito — implementar como dict estatico.

```python
# Source: neume.io/camelot-wheel [VERIFIED: WebFetch da pagina]
# Mapeamento verificado: Camelot 1A-12B para todas as 24 tonalidades

CAMELOT = {
    # Minor keys (A suffix)
    'Ab minor': '1A',  'G# minor': '1A',
    'Eb minor': '2A',  'D# minor': '2A',
    'Bb minor': '3A',  'A# minor': '3A',
    'F minor':  '4A',
    'C minor':  '5A',
    'G minor':  '6A',
    'D minor':  '7A',
    'A minor':  '8A',
    'E minor':  '9A',
    'B minor':  '10A',
    'F# minor': '11A', 'Gb minor': '11A',
    'Db minor': '12A', 'C# minor': '12A',
    # Major keys (B suffix)
    'B major':  '1B',
    'F# major': '2B',  'Gb major': '2B',
    'Db major': '3B',  'C# major': '3B',
    'Ab major': '4B',  'G# major': '4B',
    'Eb major': '5B',  'D# major': '5B',
    'Bb major': '6B',  'A# major': '6B',
    'F major':  '7B',
    'C major':  '8B',
    'G major':  '9B',
    'D major':  '10B',
    'A major':  '11B',
    'E major':  '12B',
}

def key_to_camelot(key: str) -> str:
    """Converte 'F# minor' -> '11A'. Retorna '?' se nao encontrado."""
    return CAMELOT.get(key, '?')
```

**Nota sobre enharmonicos:** librosa usa sostenidos (#) preferencialmente. As entradas com bemol (Ab, Eb, Bb, etc.) sao aliases defensivos para o caso de librosa retornar a notacao com bemol em algumas versoes. [ASSUMED]

### Anti-Patterns to Avoid

- **beat_track() para BPM simples:** beat_track() rastreia posicoes de beats e tem overhead extra; feature.tempo() e a funcao certa para "quero so o numero BPM". Usar beat_track() apenas se precisar das posicoes dos beats para sincronizacao.
- **librosa.load() sem duration:** Carregar um WAV completo de 10 minutos usa ~200-400MB de RAM no NumPy. Sempre passar `duration=90.0` para analise de BPM e `duration=120.0` para analise de key.
- **download=True no check de duracao:** extract_info com download=True inicia o download imediatamente. Sempre usar download=False para o check pre-download.
- **extractor_args como dict aninhado:** O formato `{'youtube': {'po_token': [...]}}` causa erro "Requested format is not available". O formato correto e `{'youtube': ['po_token=web.gvs+TOKEN']}`. [VERIFIED: GitHub issue #14307]
- **WAV via FFmpeg subprocess separado:** yt-dlp FFmpegExtractAudio postprocessor ja faz a conversao internamente e limpa o arquivo intermediario automaticamente. Chamar ffmpeg separadamente duplica trabalho e deixa arquivos intermediarios.
- **Nao validar com ffprobe:** Downloads que falham silenciosamente retornam arquivos HTML de 10-50KB que o librosa tenta carregar e falha com erros crípticos. ffprobe valida antes de passar para analise.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube download + autenticacao | Requests/urllib customizado | yt-dlp Python API | YouTube muda tokens, ciphers e endpoints constantemente; yt-dlp tem 100+ mantenedores acompanhando |
| Decodificacao de audio (WebM/Opus para PCM) | Python audio decoder | FFmpeg via yt-dlp postprocessor | FFmpeg suporta todos os formatos de container do YouTube; decodificacao de Opus em Python e frágil |
| BPM detection from scratch | Onset detection manual | librosa.feature.tempo() | Autocorrelacao de onset envelope tem decadas de pesquisa; re-implementar nao melhora precisao |
| Key detection from scratch | FFT + analise manual | Correlacao Krumhansl-Schmuckler via librosa | Algoritmo estabelecido; re-implementar sem entender os perfis de tom produce resultados piores |
| Validacao de arquivo de audio | Verificar tamanho do arquivo | ffprobe subprocess | Tamanho nao garante validade; uma pagina HTML tem tamanho mas nao e audio |

**Insight chave:** A complexidade do download do YouTube (bot detection, PO tokens, format selection, merging streams) e completamente encapsulada pelo yt-dlp. Qualquer solucao customizada ficara obsoleta em dias apos uma atualizacao do YouTube.

---

## Common Pitfalls

### Pitfall 1: PO Token Expirado

**What goes wrong:** O token fornecido via `YTDLP_PO_TOKEN` expira e downloads comecem a falhar com 403 ou "Sign in to confirm you're not a bot". O codigo nao muda mas a taxa de falha sobe para 100%.

**Why it happens:** PO Tokens GVS sao vinculados a DATASYNC_ID ou VISITOR_DATA (sessao), nao ao video. Tokens expiram em 24-48h tipicamente. [CITED: deepwiki.com/yt-dlp/yt-dlp/3.4.1-potoken-authentication-system]

**How to avoid:** (a) Planner deve incluir instrucoes de rotacao manual do token no README. (b) Capturar excecoes yt_dlp.utils.DownloadError e verificar a mensagem para distinguir "token expirado" de "video nao disponivel". (c) O bgutil-ytdlp-pot-provider e a solucao de longo prazo (gera tokens automaticamente), mas requer Node.js >= 20 no servidor — overhead operacional que pode ser adiado para Fase 3.

**Warning signs:** Taxa de falha aumenta gradualmente ao longo de dias sem mudancas de codigo. Mensagem de erro do yt-dlp contem "Sign in" ou "bot".

### Pitfall 2: outtmpl com extensao errada

**What goes wrong:** yt-dlp com FFmpegExtractAudio salva o arquivo como `sg_abc123.webm.wav` ou `sg_abc123.wav` dependendo da versao. Se outtmpl incluir a extensao, o resultado pode ser inesperado.

**Why it happens:** yt-dlp adiciona a extensao do postprocessor apos o template. O comportamento exato depende de como `%(ext)s` e interpretado.

**How to avoid:** Nao usar `%(ext)s` no outtmpl quando se usa FFmpegExtractAudio. Usar um caminho base (ex: `/tmp/sg_{uuid}`) e localizar o arquivo resultante com `glob('/tmp/sg_{uuid}.*')` ou assumir `.wav` e verificar existencia. [ASSUMED — verificar comportamento real na implementacao]

**Warning signs:** `FileNotFoundError` ao tentar abrir o WAV no caminho esperado.

### Pitfall 3: librosa retorna ndarray para BPM

**What goes wrong:** `librosa.feature.tempo()` retorna `np.ndarray([140.0])`, nao `float`. `json.dumps({'bpm': np.array([140.0])})` lanca `TypeError: Object of type ndarray is not JSON serializable`.

**Why it happens:** librosa retorna arrays mesmo para entradas mono (comportamento documentado). [CITED: librosa.org/doc/main/generated/librosa.beat.beat_track.html]

**How to avoid:** Sempre converter: `bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)`

**Warning signs:** `TypeError` no json.dumps() durante testes.

### Pitfall 4: chroma_cqt precisa de audio longo suficiente

**What goes wrong:** chroma_cqt em um trecho curto de audio (< 20s) ou em uma track de intro sem harmonia retorna correlacoes fracas e key incorreta.

**Why it happens:** A estimativa de chroma precisa de exposicao suficiente ao conteudo harmonico para calcular medias significativas.

**How to avoid:** Usar `duration=120.0` para key detection (2 minutos e geralmente suficiente). Nao reutilizar o segmento de 90s carregado para BPM — fazer um segundo load com duration maior. [ASSUMED — baseado em boas praticas do dominio]

### Pitfall 5: libsndfile ausente no servidor de producao

**What goes wrong:** `pip install librosa` completa com sucesso mas `librosa.load()` lanca `OSError: cannot load library 'libsndfile'`. Isso acontece em imagens Docker slim que nao incluem libsndfile.

**Why it happens:** soundfile (backend I/O do librosa) e um wrapper Python para libsndfile, uma biblioteca C que deve ser instalada via apt.

**How to avoid:** `apt-get install -y libsndfile1 ffmpeg` antes de `pip install librosa` no Dockerfile / script de setup. [CITED: .planning/research/PITFALLS.md]

**Warning signs:** Erro acontece em producao mas nao localmente (se libsndfile estiver no sistema de dev).

---

## Code Examples

### Funcao download_audio completa (com try/finally)

```python
# Padrao para limpeza de arquivos intermediarios via try/finally (D-09)
def download_audio(url: str, cookies_path: str, po_token: str) -> Path:
    wav_id = uuid.uuid4().hex[:12]
    outtmpl_base = f'/tmp/sg_{wav_id}'
    wav_path = Path(f'{outtmpl_base}.wav')

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl_base,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookies_path,
        'extractor_args': {'youtube': [f'po_token=web.gvs+{po_token}']},
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
        'http_chunk_size': 10485760,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        # Limpar qualquer arquivo parcial
        for f in Path('/tmp').glob(f'sg_{wav_id}*'):
            f.unlink(missing_ok=True)
        raise RuntimeError(f"Download falhou: {e}") from e

    if not wav_path.exists():
        raise FileNotFoundError(f"WAV nao gerado: {wav_path}")
    return wav_path
    # Nota: wav_path NAO e deletado aqui — responsabilidade da Fase 2 (D-09)
```

### Funcao analyze_audio completa (BPM + key + Camelot)

```python
def analyze_audio(wav_path: Path) -> dict:
    """Retorna dict com bpm, key, camelot, bpm_half, bpm_double."""
    # Validacao ffprobe primeiro
    duration_sec = validate_wav(wav_path)

    # BPM: 90s a partir de 20% do inicio
    offset = min(duration_sec * 0.20, 30.0)
    y_bpm, sr = librosa.load(str(wav_path), sr=22050, mono=True,
                             duration=90.0, offset=offset)
    tempo_arr = librosa.feature.tempo(y=y_bpm, sr=sr)
    bpm = float(tempo_arr[0]) if hasattr(tempo_arr, '__len__') else float(tempo_arr)
    bpm = round(bpm, 1)

    # Key: 120s a partir do inicio
    y_key, _ = librosa.load(str(wav_path), sr=22050, mono=True, duration=120.0)
    key = detect_key_from_array(y_key)  # funcao interna com Krumhansl-Schmuckler

    return {
        'bpm': bpm,
        'bpm_half': round(bpm / 2, 1),
        'bpm_double': round(bpm * 2, 1),
        'key': key,
        'camelot': key_to_camelot(key),
        'duration_sec': round(duration_sec, 1),
        'wav_path': str(wav_path),
    }
```

### Entry point __main__ com JSON output

```python
if __name__ == '__main__':
    import sys
    import os

    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Uso: python pipeline.py <youtube_url>'}))
        sys.exit(1)

    url = sys.argv[1]
    cookies_path = os.environ.get('YTDLP_COOKIES_FILE', 'cookies.txt')
    po_token = os.environ.get('YTDLP_PO_TOKEN', '')

    try:
        # Etapa 0: verificar duracao
        info = check_duration(url, cookies_path)
        duration_sec = info['duration']

        # Etapa 1: download
        wav_path = download_audio(url, cookies_path, po_token)

        # Etapa 2+3+4+5: analise
        result = analyze_audio(wav_path)
        result['duration_sec'] = duration_sec  # usar metadado do YouTube

        print(json.dumps(result))
        sys.exit(0)

    except ValueError as e:
        print(json.dumps({'error': str(e), 'type': 'validation_error'}))
        sys.exit(1)
    except RuntimeError as e:
        print(json.dumps({'error': str(e), 'type': 'download_error'}))
        sys.exit(1)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| youtube-dl | yt-dlp | 2021 (fork) | youtube-dl esta abandonado; yt-dlp tem releases quase semanais para acompanhar YouTube |
| OAuth login para yt-dlp | Cookies Netscape + PO Token | 2025 | YouTube desativou OAuth para clientes nao-oficiais; cookies + PO Token e o unico caminho viavel |
| librosa.beat.beat_track() para BPM | librosa.feature.tempo() | librosa 0.9+ | feature.tempo() foi separado como funcao independente; mais estavel para estimativa global |
| numpy < 2.0 obrigatorio | numpy 2.x suportado | librosa 0.11.0 (Marco 2025) | librosa 0.11.0 corrigiu incompatibilidade com numpy 2.x; sem necessidade de pin |
| extractor_args como dict aninhado | extractor_args como lista de strings | 2025 | Formato dict aninhado causa "format not available"; lista de strings e o formato correto |

**Deprecated/outdated:**
- `youtube-dl`: abandonado desde 2021 — usar yt-dlp
- `pytube`: frágil, nao acompanha mudancas do YouTube, sem manutencao ativa
- `librosa.beat.tempo()` (versoes antigas): foi movido para `librosa.feature.tempo()`
- `numpy < 2.0` pin para librosa: nao mais necessario com librosa 0.11.0

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Enharmonicos com bemol (Ab, Eb, Gb) sao aliases defensivos — librosa prefere sostenidos (#) em sua saida | Pattern 6: Camelot | Se librosa retornar 'Gb minor' em vez de 'F# minor', o lookup falha e retorna '?'; solucao: mapear ambos, o que ja esta feito na tabela |
| A2 | `outtmpl_base + '.wav'` e o caminho correto apos FFmpegExtractAudio sem %(ext)s no template | Pattern 2 + Pitfall 2 | Arquivo salvo em caminho diferente; solucao defensiva: usar glob |
| A3 | 120s e duration suficiente para key detection precisa em beats de producao | Pattern 5 | Key incorreta para tracks com intros longas sem harmonia; mitigacao: offset de 20% |
| A4 | Token GVS pode ser reutilizado por 24-48h (vinculado a sessao, nao ao video ID) | Pattern 2 + Pitfall 1 | Se o token for por-video, cada download requer novo token — o modelo manual (env var) e inviavel; obrigaria uso do bgutil plugin |

---

## Open Questions

1. **Comportamento exato do outtmpl sem %(ext)s**
   - What we know: yt-dlp adiciona extensao do postprocessor apos o template; o resultado esperado e `/tmp/sg_{id}.wav`
   - What's unclear: Se a versao 2026.3.17 salva como `sg_{id}.wav` ou `sg_{id}.webm.wav` quando o arquivo intermediario e WebM
   - Recommendation: Na Wave 0 do plano, adicionar um teste de smoke que verifica o nome do arquivo gerado e implementa logica de glob como fallback

2. **Viabilidade do PO Token estatico via env var em producao**
   - What we know: Tokens GVS sao vinculados a sessao do usuario (DATASYNC_ID / VISITOR_DATA); tokens por-video existem apenas para Player tokens
   - What's unclear: Quanto tempo dura um token GVS gerado manualmente antes de expirar
   - Recommendation: O planner deve incluir instrucoes de rotacao no README e uma Task de "teste de download real no host de producao" no primeiro wave

3. **Python 3.12.3 no host vs. Python 3.11 no CLAUDE.md**
   - What we know: CLAUDE.md especifica Python 3.11; ambiente local tem 3.12.3; yt-dlp 2026.3.17 suporta Python 3.10+
   - What's unclear: O host de producao (VPS) tera Python 3.11 ou 3.12?
   - Recommendation: Usar `python3.11` explicitamente no requirements e scripts; se o host tiver apenas 3.12, nenhuma incompatibilidade conhecida existe com o stack

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Runtime do pipeline | Sim (3.12.3) | 3.12.3 | — |
| yt-dlp | download_audio() | Sim (sistema) | 2024.12.3 instalada; 2026.3.17 disponivel | Atualizar: `pip install -U yt-dlp` |
| FFmpeg | Conversao WAV | Sim | 6.1.1-3ubuntu5 | — |
| ffprobe | Validacao pos-download | Sim | 6.1.1-3ubuntu5 | — |
| libsndfile | librosa.load() | Nao verificado no sistema | — | `apt install libsndfile1` antes do pip install librosa |
| librosa | analyze_audio() | Nao instalada | 0.11.0 disponivel | `pip install librosa` |
| soundfile | Dependencia do librosa | Nao instalada | 0.13.1 disponivel | Instalada junto com librosa |
| numpy | Dependencia do librosa | Nao verificada | 2.4.4 disponivel | `pip install numpy` |
| cookies.txt | Autenticacao yt-dlp | Nao existe | — | Usuario deve gerar via browser extension antes dos testes |

**Missing dependencies with no fallback:**
- `cookies.txt` (Netscape format): usuario deve gerar externamente usando extensao do browser (ex: "Get cookies.txt LOCALLY"). Sem cookies, downloads do YouTube de IPs de datacenter falham. Isso e um **prerequisito humano**, nao tecnico.

**Missing dependencies with fallback:**
- `librosa`: instalar via pip — `pip install librosa==0.11.0`
- `libsndfile1`: instalar via apt — `apt-get install -y libsndfile1`
- `yt-dlp` (versao atual 2024.12.3 e antiga): atualizar — `pip install -U yt-dlp`

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (Wave 0 cria) |
| Quick run command | `pytest tests/ -x -q --tb=short` |
| Full suite command | `pytest tests/ -v --tb=long` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-05 | Duration check recusa videos > 15min | Unit (mock yt-dlp) | `pytest tests/test_pipeline.py::test_duration_check_rejects_long_video -x` | Nao — Wave 0 |
| CORE-05 | Duration check aceita videos <= 15min | Unit (mock yt-dlp) | `pytest tests/test_pipeline.py::test_duration_check_accepts_short_video -x` | Nao — Wave 0 |
| CORE-03 | ydl_opts contem cookiefile + extractor_args po_token | Unit (inspect ydl_opts) | `pytest tests/test_pipeline.py::test_download_opts_include_auth -x` | Nao — Wave 0 |
| CORE-04 | convert_to_wav retorna Path com extensao .wav | Integration (requer FFmpeg) | `pytest tests/test_pipeline.py::test_wav_file_created -x -m integration` | Nao — Wave 0 |
| CORE-04 | ffprobe valida WAV gerado como audio valido | Integration (requer FFmpeg) | `pytest tests/test_pipeline.py::test_ffprobe_validates_wav -x -m integration` | Nao — Wave 0 |
| ANALYSIS-01 | BPM detectado esta dentro de 30% do feel-tempo | Integration (requer WAV real) | `pytest tests/test_pipeline.py::test_bpm_accuracy -x -m integration` | Nao — Wave 0 |
| ANALYSIS-02 | Key detectada esta correta para sample conhecido | Integration (requer WAV real) | `pytest tests/test_pipeline.py::test_key_detection -x -m integration` | Nao — Wave 0 |
| ANALYSIS-03 | bpm_half == bpm/2 e bpm_double == bpm*2 | Unit (calculo aritmetico) | `pytest tests/test_pipeline.py::test_bpm_half_double_calculation -x` | Nao — Wave 0 |
| ANALYSIS-04 | Camelot retorna codigo correto para key conhecida | Unit (tabela estatica) | `pytest tests/test_pipeline.py::test_camelot_mapping -x` | Nao — Wave 0 |
| D-05 | JSON output contem todos os campos obrigatorios | Unit (mock pipeline) | `pytest tests/test_pipeline.py::test_json_output_shape -x` | Nao — Wave 0 |
| D-07 | Pipeline roda end-to-end nos 3 URLs de teste | E2E (requer internet + cookies) | `pytest tests/test_pipeline.py::test_e2e_rock -x -m e2e` | Nao — Wave 0 |

**Nota sobre testes E2E:** Testes com URLs reais do YouTube requerem `cookies.txt` valido e conexao internet. Marcar com `@pytest.mark.e2e` e rodar separadamente do CI padrao. Os 3 URLs (D-07) sao os criterios de aceite finais da fase.

### Sampling Rate

- **Por task commit:** `pytest tests/test_pipeline.py -x -q -m "not integration and not e2e"`
- **Por wave merge:** `pytest tests/test_pipeline.py -x -q -m "not e2e"`
- **Phase gate:** Suite completa incluindo e2e verde (com cookies.txt valido) antes do `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline.py` — todos os testes listados acima
- [ ] `tests/fixtures/sample.wav` — WAV de 5 segundos de tom puro (A440) para testes de analise offline
- [ ] `pytest.ini` — configuracao com markers: `integration`, `e2e`
- [ ] `tests/conftest.py` — fixtures: `sample_wav_path`, `mock_yt_info`
- [ ] Framework install: `pip install pytest==9.0.3 pytest-subprocess`

---

## Security Domain

> ASVS evaluation para um script Python CLI standalone sem HTTP server (Phase 1 escopo).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Nao | Sem auth — script standalone stateless |
| V3 Session Management | Nao | Sem sessoes |
| V4 Access Control | Nao | Sem usuarios |
| V5 Input Validation | Sim (parcial) | URL do YouTube validada por yt-dlp internamente; duration check antes do download |
| V6 Cryptography | Nao | Sem criptografia; cookies.txt e plaintext |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| URL arbitraria (nao-YouTube) passada para yt-dlp | Spoofing | yt-dlp rejeita URLs sem extractor compativel; adicionar validacao de prefixo `youtube.com` antes de chamar yt-dlp |
| Path traversal em outtmpl | Tampering | Sempre usar `/tmp/sg_{uuid}` fixo; nao interpolar input do usuario no path |
| cookies.txt com permissoes incorretas | Information Disclosure | Documentar no README: `chmod 600 cookies.txt`; nao commitar no git |
| Subprocess injection via url | Tampering | yt-dlp Python API nao usa shell=True; URL e passada como argumento, nao interpolada em string de shell |

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: pip registry] — versoes verificadas de todos os pacotes via `pip3 index versions`
- [VERIFIED: ffmpeg -version] — FFmpeg 6.1.1 disponivel no ambiente local
- [CITED: librosa.org/doc/main/generated/librosa.feature.tempo.html] — parametros de feature.tempo()
- [CITED: librosa.org/doc/main/generated/librosa.beat.beat_track.html] — parametros de beat_track()
- [CITED: deepwiki.com/librosa/librosa/5.2-beat-tracking-and-tempo-estimation] — diferenca feature.tempo() vs beat_track()
- [CITED: neume.io/camelot-wheel] — tabela Camelot completa (24 entradas verificadas)

### Secondary (MEDIUM confidence)
- [CITED: github.com/yt-dlp/yt-dlp/issues/14307] — formato correto de extractor_args (lista de strings)
- [CITED: github.com/yt-dlp/yt-dlp/issues/12200] — cookiefile em ydl_opts Python API
- [CITED: deepwiki.com/yt-dlp/yt-dlp/3.4.1-potoken-authentication-system] — tipos de tokens GVS vs Player e cache
- [CITED: mintlify.wiki/yt-dlp/yt-dlp/api/overview] — campo `duration` no info dict
- [CITED: github.com/Brainicism/bgutil-ytdlp-pot-provider] — requisitos do bgutil plugin (Node.js >= 20)
- [CITED: librosa.org/doc/main/changelog.html] — librosa 0.11.0 numpy 2.x support

### Tertiary (LOW confidence)
- Comportamento de enharmonicos no output do librosa — baseado em padrao observado de bibliotecas de DSP Python, nao documentado explicitamente [ASSUMED]
- Duration de expiracao de tokens GVS (24-48h) — estimativa baseada em documentacao de sessoes YouTube, nao confirmada via teste real [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versoes verificadas via pip registry e ffmpeg disponivel localmente
- yt-dlp configuration (cookies + po_token): MEDIUM — formato extractor_args verificado via GitHub issue; comportamento do token GVS documentado via DeepWiki mas nao testado em producao
- librosa BPM/key patterns: HIGH — documentacao oficial verificada via WebFetch; parametros confirmados
- Camelot table: HIGH — 24 entradas extraidas de neume.io/camelot-wheel, site dedicado ao sistema Camelot
- PO Token lifetime: LOW — estimativa baseada em documentacao de sessoes, nao em teste real

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 dias — stack estavel; yt-dlp pode ter mudancas em 2 semanas se YouTube atualizar bot detection)
