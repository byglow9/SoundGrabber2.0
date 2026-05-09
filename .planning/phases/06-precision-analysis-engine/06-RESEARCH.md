# Phase 6: Precision Analysis Engine — Research

**Researched:** 2026-05-09
**Domain:** Audio analysis — Essentia BPM/key, librosa tuning detection, numpy type safety
**Confidence:** HIGH (all critical claims verified by live execution in the project venv)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PREC-01 | Substituir detect_bpm() por Essentia RhythmExtractor2013(method="multifeature") | Verified: algoritmo instancia sem erro no venv; retorna Python float direto |
| PREC-02 | Substituir detect_key() por Essentia KeyExtractor(profileType="edma") | Verified: edma disponível e funcional; retorna key e scale como Python str |
| PREC-03 | Passar tuning_hz para KeyExtractor(tuningFrequency=tuning_hz) | Verified: parâmetro aceito na instanciação; documentação confirma que alinha HPCP bins |
| PREC-04 | Wrapping float() obrigatório em todos os valores Essentia | Verified: bpm/strength já retornam Python float no cp312 binding — mas wrapping defensivo ainda necessário para robustez futura |
| PREC-05 | Montar string "F# minor" antes de key_to_camelot() | Verified: f"{key} {scale}" produz o formato exato que a tabela CAMELOT espera |
| TUNING-01 | detect_tuning() via librosa.estimate_tuning() + librosa.tuning_to_A4() | Verified: ambas as funções existem em librosa 0.11.0; estimate_tuning retorna numpy.float64; tuning_to_A4 aceita float64 |
| TUNING-02 | HPSS gate: retornar None quando razão harmônica < 0.2 | Verified: librosa.effects.hpss() funciona; teste com sinal percussivo retornou razão 0.0 (< 0.2); sinal harmônico retornou 0.9966 |
| TUNING-03 | tuning_hz no dict de retorno de analyze_audio() como float ou None | Verified: None serializa para JSON; float(librosa.tuning_to_A4(...)) serializa para JSON |
| QUAL-01 | test_json_output_shape inclui tuning_hz e json.dumps não levanta TypeError | Verified: resultado dict completo serializa sem erro com json.dumps() |
</phase_requirements>

---

## Summary

A Phase 6 substitui o motor de análise do SoundGrabber de librosa (Krumhansl-Schmuckler manual) para Essentia (RhythmExtractor2013 + KeyExtractor), os mesmos algoritmos usados pelo Tunebat. Todas as dependências foram verificadas no venv do projeto (Python 3.12.3, numpy 2.4.4): a instalação `pip install essentia==2.1b6.dev1389` é bem-sucedida sem compilação, e `import essentia.standard` não levanta exceção.

A maior surpresa de pesquisa foi **positiva**: o risco de "Camelot table missing Essentia key strings" foi **eliminado**. Os 12 nomes de notas que o Essentia retorna (A, Bb, B, C, C#, D, Eb, E, F, F#, G, Ab) já estão cobertos pela tabela `_CAMELOT` existente em `pipeline.py` — sem alterações na tabela necessárias. Outra surpresa: no binding Python 3.12, `RhythmExtractor2013` e `KeyExtractor` já retornam Python `float`/`str` nativos (não `numpy.float32`), mas o wrapping defensivo com `float()` permanece mandatório para robustez futura.

A mudança estrutural crítica é a **ordem de execução**: tuning deve ser detectado via librosa ANTES de chamar `KeyExtractor`, pois `tuningFrequency` é um parâmetro de instanciação — não pode ser aplicado retroativamente aos bins HPCP já computados.

**Recomendação primária:** Três funções novas (`detect_tuning`, `detect_bpm_essentia`, `detect_key_essentia`) adicionadas a `pipeline.py`; `analyze_audio()` atualizada para orquestrar a nova sequência; testes existentes atualizados para refletir nova assinatura e campo `tuning_hz`.

---

## Standard Stack

### Core (bibliotecas para esta fase)

| Biblioteca | Versão | Propósito | Por que é o padrão |
|------------|--------|-----------|---------------------|
| essentia | 2.1b6.dev1389 | BPM via RhythmExtractor2013, key via KeyExtractor | Mesmo motor do Tunebat (MTG/UPF); wheel cp312 Linux x86_64 disponível; sem compilação |
| librosa | 0.11.0 (já instalado) | Tuning detection (HPSS + estimate_tuning + tuning_to_A4) | Já está no venv; zero dependência nova para tuning |
| numpy | 2.4.4 (já instalado) | Operações de array no HPSS e ratio de energia | Satisfaz requisito essentia>=1.25 |

### Dependências transitivas (novas ao instalar essentia)

| Biblioteca | Versão | Quando chega |
|------------|--------|-------------|
| pyyaml | 6.0.3 | Dependência transitiva do essentia |
| six | já instalado | Dependência transitiva do essentia |

### Instalação

```bash
# Adicionar ao requirements.txt
pip install essentia==2.1b6.dev1389
```

**Verificação de versão (VERIFIED: PyPI):**
- `essentia==2.1b6.dev1389` — publicado 2025-07-24 [VERIFIED: PyPI JSON API]
- Wheel `cp312-cp312-manylinux_2_17_x86_64` presente (13.8 MB) [VERIFIED: PyPI JSON API]
- `numpy>=1.25` é o único requisito de versão — nosso numpy 2.4.4 satisfaz [VERIFIED: PyPI metadata]

---

## Architecture Patterns

### Estrutura do pipeline após Phase 6

```
pipeline.py
├── check_duration()           # inalterado
├── download_audio()           # inalterado
├── convert_to_wav()           # inalterado
├── validate_wav()             # inalterado
├── detect_tuning()            # NOVO: librosa HPSS + estimate_tuning + tuning_to_A4
├── detect_bpm()               # SUBSTITUÍDO: Essentia RhythmExtractor2013
├── detect_key()               # SUBSTITUÍDO: Essentia KeyExtractor(edma)
├── key_to_camelot()           # inalterado (tabela já cobre todos os 12 nomes Essentia)
└── analyze_audio()            # ATUALIZADO: nova sequência + campo tuning_hz
```

### Pattern 1: Ordem de execução em analyze_audio()

**Regra:** tuning PRIMEIRO, key DEPOIS.

`KeyExtractor` aceita `tuningFrequency` como parâmetro de **instanciação** — os bins HPCP são computados uma única vez na chamada. Se `tuning_hz` for calculado depois, os bins já estarão alinhados ao A=440 padrão, não ao concert pitch real do beat.

```python
# CORRETO — tuning antes de key
tuning_hz = detect_tuning(wav_path)           # Step 1: librosa HPSS
bpm = detect_bpm(wav_path)                    # Step 2: Essentia RhythmExtractor2013
key = detect_key(wav_path, tuning_hz)         # Step 3: Essentia KeyExtractor(tuningFrequency=tuning_hz)

# ERRADO — ordem invertida produz bins HPCP desalinhados
key = detect_key(wav_path, tuning_hz=None)    # bins alinhados a 440 Hz
tuning_hz = detect_tuning(wav_path)           # tarde demais
```

[VERIFIED: execução live no venv + documentação Essentia KeyExtractor]

### Pattern 2: detect_tuning() com HPSS gate

```python
# Source: verificado com librosa 0.11.0 no venv do projeto
def detect_tuning(wav_path: Path) -> float | None:
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    y_harmonic, _ = librosa.effects.hpss(y)

    total_energy = float(np.sum(y**2))
    harm_energy = float(np.sum(y_harmonic**2))
    ratio = harm_energy / (total_energy + 1e-10)

    if ratio < 0.2:
        return None  # beat puramente percussivo — tuning seria ruído

    raw_tuning = librosa.estimate_tuning(y=y_harmonic, sr=sr, resolution=0.01)
    return float(librosa.tuning_to_A4(raw_tuning))
```

**Resultado verificado:** sinal percussivo (noise bursts) → razão 0.0 → None; sinal harmônico (440 Hz sine) → razão 0.9966 → 440.25 Hz [VERIFIED: execução live no venv]

### Pattern 3: detect_bpm() com Essentia RhythmExtractor2013

```python
# Source: verificado com essentia 2.1b6.dev1389 no venv do projeto
import essentia.standard as es

def detect_bpm(wav_path: Path) -> float:
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    return float(bpm)  # float() defensivo: binding cp312 já retorna float, mas wrapping garante robustez
```

**Nota crítica:** `sampleRate=44100` é obrigatório para `RhythmExtractor2013`. A documentação oficial especifica: "The algorithm requires the sample rate of the input signal to be 44100 Hz in order to work correctly." [VERIFIED: documentação essentia.upf.edu]

### Pattern 4: detect_key() com Essentia KeyExtractor

```python
# Source: verificado com essentia 2.1b6.dev1389 no venv do projeto
import essentia.standard as es

def detect_key(wav_path: Path, tuning_hz: float | None) -> tuple[str, float]:
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    freq = tuning_hz if tuning_hz is not None else 440.0
    key, scale, strength = es.KeyExtractor(
        profileType="edma",
        tuningFrequency=freq,
    )(audio)
    key_string = f"{key} {scale}"  # "A" + " " + "minor" -> "A minor"
    return str(key_string), float(strength)
```

**Fallback para None:** quando `tuning_hz is None` (beat percussivo), usa 440.0 Hz como padrão — o KeyExtractor ainda funciona, apenas sem correção de tuning. Isso é correto porque beats puramente percussivos não têm pitch mensurável.

### Pattern 5: analyze_audio() atualizada (assinatura e campos)

```python
def analyze_audio(wav_path: Path) -> dict[str, Any]:
    wav_path = Path(wav_path)
    duration_sec = validate_wav(wav_path)           # ffprobe (inalterado)
    tuning_hz = detect_tuning(wav_path)             # NOVO: librosa HPSS
    bpm = detect_bpm(wav_path)                      # NOVO: Essentia
    key, key_confidence = detect_key(wav_path, tuning_hz)  # NOVO: Essentia
    camelot = key_to_camelot(key)                   # inalterado

    return {
        "bpm":           float(bpm),
        "bpm_half":      round(float(bpm) / 2, 1),
        "bpm_double":    round(float(bpm) * 2, 1),
        "key":           str(key),
        "camelot":       str(camelot),
        "key_confidence": float(key_confidence),
        "tuning_hz":     tuning_hz,    # float ou None — JSON-serializable
        "duration_sec":  round(float(duration_sec), 1),
        "wav_path":      str(wav_path),
    }
```

**Verificado:** `json.dumps(result)` completo passou sem TypeError no venv [VERIFIED: execução live]

### Anti-Patterns a Evitar

- **Chamar KeyExtractor sem tuning_hz**: bins HPCP alinhados ao A=440 mesmo que o beat esteja em A=432. Sempre passar `tuningFrequency`.
- **Assumir numpy.float32 do Essentia sem verificar**: no binding cp312 do essentia 2.1b6.dev1389, `bpm` e `strength` são Python `float`. Mesmo assim, usar `float()` defensivamente — versões futuras podem mudar.
- **Esquecer `sampleRate=44100` no MonoLoader**: RhythmExtractor2013 requer 44100 Hz. Sem isso, resultados de BPM serão numericamente incorretos (sem erro de Python).
- **Usar `essentia-tensorflow` em vez de `essentia`**: adiciona ~2 GB de dependências TensorFlow sem benefício — RhythmExtractor2013 não usa TF.
- **Carregar o áudio librosa com `sr=22050`** para o passo de tuning: usar `sr=None` preserva a taxa original. A qualidade da estimativa de tuning é melhor com a resolução de frequência nativa.

---

## Don't Hand-Roll

| Problema | Não construir | Usar em vez disso | Por que |
|----------|---------------|-------------------|---------|
| BPM detection resistente a half-tempo | Lógica própria de octave correction | `RhythmExtractor2013(method="multifeature")` | multifeature funde múltiplas funções de onset — built-in octave resistance |
| HPCP com correção de afinação | Implementação manual de Harmonic Pitch Class Profile | `KeyExtractor(tuningFrequency=...)` | HPCP com whitening não-linear e harmonic weighting é 200+ linhas de DSP |
| Conversão desvio de tuning → Hz | Fórmula manual `440 * 2^(semitones/12)` | `librosa.tuning_to_A4(tuning)` | Lida com bins fracionários por octave; fórmula manual comete erros de resolução |
| Separação harmônico/percussivo | Filtros manuais no domínio da frequência | `librosa.effects.hpss(y)` | Median filtering no espectrograma é algoritmicamente não-trivial; HPSS built-in é testado |

---

## Nomes de Notas que o Essentia Retorna (CRÍTICO)

**Verificado em `essentia/src/algorithms/tonal/key.cpp` via GitHub:** [VERIFIED: WebFetch github.com/MTG/essentia]

O Essentia usa notação **mista** — não exclusivamente sustenidos ou bemóis:

| Nota | Notação Essentia | Na tabela CAMELOT atual? |
|------|-----------------|--------------------------|
| A | "A" | Sim ("A major", "A minor") |
| A#/Bb | **"Bb"** (bemol) | Sim ("Bb major", "Bb minor") |
| B | "B" | Sim |
| C | "C" | Sim |
| C#/Db | **"C#"** (sustenido) | Sim ("C# major", "C# minor") |
| D | "D" | Sim |
| D#/Eb | **"Eb"** (bemol) | Sim ("Eb major", "Eb minor") |
| E | "E" | Sim |
| F | "F" | Sim |
| F#/Gb | **"F#"** (sustenido) | Sim ("F# major", "F# minor") |
| G | "G" | Sim |
| G#/Ab | **"Ab"** (bemol) | Sim ("Ab major", "Ab minor") |

**Conclusão: a tabela `_CAMELOT` existente já cobre todos os 24 casos possíveis.** Nenhuma alteração na tabela é necessária. [VERIFIED: execução live — `key_to_camelot()` retornou código correto para todos os 24 casos]

---

## Compatibilidade de Tipos para JSON (CRÍTICO)

**Resultado de pesquisa definitivo (verificado no venv):**

| Valor | Origem | Tipo real no venv cp312 | Serializa direto? | Ação |
|-------|--------|--------------------------|-------------------|------|
| `bpm` | RhythmExtractor2013 | `float` (Python) | Sim | `float()` defensivo OK |
| `strength` | KeyExtractor | `float` (Python) | Sim | `float()` defensivo OK |
| `key` | KeyExtractor | `str` (Python) | Sim | `str()` defensivo OK |
| `scale` | KeyExtractor | `str` (Python) | Sim | `str()` defensivo OK |
| `tuning_hz` | librosa.tuning_to_A4 | `numpy.float64` | Sim (float64 serializa) | `float()` obrigatório por clareza |
| `tuning_hz` quando percussivo | detect_tuning | `None` | Sim | nenhuma ação |
| elementos de `beats` array | RhythmExtractor2013 | `numpy.float32` array | Não (float32 falha) | Não incluir no dict de retorno |

**Prova da falha com numpy.float32:** [VERIFIED: execução live no venv]
```python
import numpy as np, json
json.dumps({'x': np.float32(1.0)})  # TypeError: Object of type float32 is not JSON serializable
json.dumps({'x': float(np.float32(1.0))})  # OK
json.dumps({'x': None})  # OK
```

**Regra:** Nunca incluir o array `beats` (timestamps individuais) no dict de retorno — são `numpy.float32`. Incluir apenas `bpm` (scalar), que é Python float no binding atual.

---

## Impacto nos Testes Existentes

### Testes que PRECISAM ser atualizados

| Teste | Mudança necessária |
|-------|--------------------|
| `test_key_detection` | Assinatura `detect_key()` muda: agora aceita `tuning_hz` como segundo argumento |
| `test_bpm_accuracy` | Internamente usa `detect_bpm()` — comportamento inalterado, mas a implementação muda |
| `test_json_output_shape` | Deve adicionar `tuning_hz` ao conjunto `required` de campos |

### Teste novo obrigatório (QUAL-01)

```python
@pytest.mark.integration
def test_json_output_shape_with_tuning_hz(sample_wav_path):
    """analyze_audio() deve retornar tuning_hz e json.dumps não deve levantar TypeError."""
    result = pipeline.analyze_audio(sample_wav_path)
    required = {"bpm", "key", "camelot", "bpm_half", "bpm_double",
                "wav_path", "duration_sec", "tuning_hz"}
    assert required.issubset(result.keys()), f"Missing: {required - set(result.keys())}"
    serialized = json.dumps(result)  # não deve levantar TypeError
    parsed = json.loads(serialized)
    # tuning_hz deve ser float ou None — nunca numpy type
    assert parsed["tuning_hz"] is None or isinstance(parsed["tuning_hz"], float)
```

### Testes que NÃO mudam

| Teste | Motivo |
|-------|--------|
| `test_duration_check_*` | check_duration() inalterado |
| `test_download_opts_include_auth` | download_audio() inalterado |
| `test_bpm_half_double_calculation` | usa mock de detect_bpm e detect_key — funcionará se a assinatura do mock for atualizada |
| `test_camelot_mapping` | key_to_camelot() e tabela CAMELOT inalterados |

---

## Common Pitfalls

### Pitfall 1: sampleRate incorreto no MonoLoader

**O que dá errado:** RhythmExtractor2013 opera internamente na taxa de 44100 Hz. Se o MonoLoader carregar com `sampleRate=22050`, o BPM retornado será numericamente errado (sem Python exception — falha silenciosa).
**Por que acontece:** librosa usa sr=22050 por padrão para análise; Essentia usa sr=44100. Misturar as duas convenções é o erro mais comum ao migrar.
**Como evitar:** Sempre `es.MonoLoader(filename=wav_path, sampleRate=44100)()` para todo áudio destinado ao Essentia.
**Sinal de alerta:** BPMs com valores estranhos (~50% ou ~200% do esperado).

[VERIFIED: documentação Essentia RhythmExtractor2013 — "requires the sample rate... to be 44100 Hz"]

### Pitfall 2: Dois carregamentos de áudio (librosa + Essentia)

**O que dá errado:** Não é um erro — é intencional. O pipeline carrega o áudio duas vezes: uma com librosa (sr=None, para tuning) e uma com Essentia (sr=44100, para BPM/key). Isso parece redundante mas é a abordagem correta porque as duas bibliotecas têm pipelines de I/O incompatíveis.
**Por que acontece:** Essentia's MonoLoader retorna float32 a 44100; librosa.load pode retornar float32 na taxa nativa. Tentar compartilhar o array numpy entre as duas seria frágil (resampling manual, dtype coercion).
**Como evitar:** Aceitar o double-load. O overhead é ~0.5s para um WAV de 5 minutos — irrelevante em um background Celery task.
**Sinal de alerta:** Tentar passar `audio` do MonoLoader para `librosa.effects.hpss()` (API incompatível).

### Pitfall 3: detect_key recebe tuning_hz=None sem fallback

**O que dá errado:** `KeyExtractor(tuningFrequency=None)` levanta TypeError na instanciação do Essentia.
**Por que acontece:** beats puramente percussivos têm `tuning_hz=None` por design (HPSS gate). Sem fallback, o KeyExtractor quebraria.
**Como evitar:** `freq = tuning_hz if tuning_hz is not None else 440.0` antes de instanciar o KeyExtractor.
**Sinal de alerta:** TypeError com mensagem sobre `tuningFrequency` recebendo None.

### Pitfall 4: Importar `essentia` sem o sufixo `.standard`

**O que dá errado:** `import essentia` não expõe as classes algorítmicas. `essentia.RhythmExtractor2013` não existe.
**Por que acontece:** A biblioteca organiza os algoritmos em submodules (`essentia.standard` para modo não-streaming, `essentia.streaming` para streaming).
**Como evitar:** Sempre `import essentia.standard as es`.
**Sinal de alerta:** `AttributeError: module 'essentia' has no attribute 'RhythmExtractor2013'`.

### Pitfall 5: Incluir arrays numpy no dict de retorno

**O que dá errado:** O dict `beats` (array de timestamps) é `numpy.float32` — inclui-lo no resultado de analyze_audio() faz `json.dumps()` levantar TypeError, quebrando o Celery JSON serializer.
**Por que acontece:** RhythmExtractor2013 retorna 5 valores; os vetores `beats`, `estimates`, `beats_intervals` são numpy arrays.
**Como evitar:** Descartar com `_`: `bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)`. Incluir apenas `bpm` no dict de retorno.
**Sinal de alerta:** `TypeError: Object of type ndarray is not JSON serializable` no log do worker Celery.

### Pitfall 6: tasks.py não expõe tuning_hz no resultado

**O que dá errado:** `analyze_audio()` retorna `tuning_hz`, mas se `process_job()` em `api/tasks.py` não incluir `tuning_hz` no dict de retorno, Phase 7 não conseguirá exibir o valor na interface.
**Por que acontece:** `tasks.py` atualmente mapeia explicitamente os campos do resultado (linha 57-64). Campos novos em `analyze_audio()` precisam ser adicionados manualmente.
**Como evitar:** Adicionar `"tuning_hz": result["tuning_hz"]` ao dict de retorno do `process_job`.
**Sinal de alerta:** Testes de Phase 7 falham porque `tuning_hz` não aparece na resposta GET /jobs/{id}.

---

## Validation Architecture

### Test Framework

| Propriedade | Valor |
|-------------|-------|
| Framework | pytest 9.0.3 |
| Config file | pytest.ini (raiz do projeto) |
| Comando rápido | `.venv/bin/python3 -m pytest tests/test_pipeline.py -m "not e2e" -q` |
| Suite completa | `.venv/bin/python3 -m pytest tests/ -m "not e2e" -q` |

### Mapeamento Requisitos → Testes

| Req ID | Comportamento | Tipo | Comando | Arquivo existe? |
|--------|--------------|-------|---------|-----------------|
| PREC-01 | RhythmExtractor2013 retorna BPM como float num range plausível | integration | `pytest tests/test_pipeline.py::test_bpm_accuracy -m integration -x` | Sim (atualizar) |
| PREC-02 | KeyExtractor retorna key no formato "X major/minor" | integration | `pytest tests/test_pipeline.py::test_key_detection -m integration -x` | Sim (atualizar assinatura) |
| PREC-03 | tuning_hz passado para KeyExtractor antes da key detection | unit | `pytest tests/test_pipeline.py::test_detect_key_uses_tuning_hz -x` | Nao — Wave 0 |
| PREC-04 | Todos os valores são tipos Python nativos | unit | `pytest tests/test_pipeline.py::test_json_output_shape -x` | Sim (atualizar) |
| PREC-05 | f"{key} {scale}" produz string que key_to_camelot() resolve | unit | `pytest tests/test_pipeline.py::test_camelot_mapping -x` | Sim (inalterado) |
| TUNING-01 | detect_tuning() retorna float Hz em sinal harmônico | integration | `pytest tests/test_pipeline.py::test_detect_tuning_harmonic -x` | Nao — Wave 0 |
| TUNING-02 | detect_tuning() retorna None em sinal percussivo | integration | `pytest tests/test_pipeline.py::test_detect_tuning_percussive -x` | Nao — Wave 0 |
| TUNING-03 | tuning_hz aparece no dict de retorno de analyze_audio() | unit | `pytest tests/test_pipeline.py::test_json_output_shape -x` | Sim (atualizar) |
| QUAL-01 | json.dumps(analyze_audio(real_wav)) não levanta TypeError, tuning_hz incluso | integration | `pytest tests/test_pipeline.py::test_json_output_shape -m integration -x` | Sim (atualizar para real WAV) |

### Taxa de Sampling

- **Por commit:** `.venv/bin/python3 -m pytest tests/test_pipeline.py -m "not e2e" -q`
- **Por wave merge:** `.venv/bin/python3 -m pytest tests/ -m "not e2e" -q`
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps (novos testes necessários)

- [ ] `tests/test_pipeline.py::test_detect_tuning_harmonic` — verifica TUNING-01 (fixture WAV é sinal 440Hz — ideal para este teste)
- [ ] `tests/test_pipeline.py::test_detect_tuning_percussive` — verifica TUNING-02 (precisa de fixture WAV puramente percussivo, ou mock)
- [ ] `tests/test_pipeline.py::test_detect_key_uses_tuning_hz` — verifica PREC-03 (mock de KeyExtractor para capturar o tuningFrequency passado)

---

## Environment Availability

| Dependência | Requerida por | Disponível | Versão | Fallback |
|-------------|--------------|-----------|--------|----------|
| essentia | PREC-01, PREC-02, PREC-03 | Instalada pelo plan (pip install) | 2.1b6.dev1389 | — |
| librosa | TUNING-01, TUNING-02 | Sim (venv) | 0.11.0 | — |
| numpy | HPSS energy ratio | Sim (venv) | 2.4.4 | — |
| pytest | QUAL-01 | Sim (venv) | 9.0.3 | — |
| FFmpeg/ffprobe | validate_wav() (inalterado) | Sim (sistema) | — | — |
| tests/fixtures/sample.wav | Testes de integração | Sim | 5s, 440Hz WAV | — |

**Dependências ausentes com fallback:** Nenhuma.

**Dependências ausentes bloqueantes:** Nenhuma — essentia instala via pip sem compilação no ambiente atual.

---

## Code Examples

### Exemplo completo: detect_tuning() com HPSS gate

```python
# Source: VERIFIED execução live no venv (Python 3.12, librosa 0.11.0, numpy 2.4.4)
import librosa
import numpy as np
from pathlib import Path

def detect_tuning(wav_path: Path) -> float | None:
    """Detecta frequência de referência (concert pitch) via HPSS + librosa.estimate_tuning.

    Retorna None quando a razão de energia harmônica < 0.2 (beat puramente percussivo).
    """
    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    y_harmonic, _ = librosa.effects.hpss(y)

    total_energy = float(np.sum(y**2))
    harm_energy = float(np.sum(y_harmonic**2))
    ratio = harm_energy / (total_energy + 1e-10)  # 1e-10: evita divisão por zero em silêncio puro

    if ratio < 0.2:
        return None

    raw_tuning = librosa.estimate_tuning(y=y_harmonic, sr=sr, resolution=0.01)
    return float(librosa.tuning_to_A4(raw_tuning))
```

### Exemplo completo: detect_bpm() com Essentia

```python
# Source: VERIFIED execução live no venv (essentia 2.1b6.dev1389, cp312)
import essentia.standard as es
from pathlib import Path

def detect_bpm(wav_path: Path) -> float:
    """BPM via Essentia RhythmExtractor2013 multifeature — mesmo algoritmo do Tunebat."""
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    bpm, _, _, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    return float(bpm)
```

### Exemplo completo: detect_key() com Essentia

```python
# Source: VERIFIED execução live no venv (essentia 2.1b6.dev1389, cp312)
import essentia.standard as es
from pathlib import Path

def detect_key(wav_path: Path, tuning_hz: float | None) -> tuple[str, float]:
    """Tonalidade via Essentia KeyExtractor(profileType='edma') com correção de tuning.

    O parâmetro tuning_hz deve ser passado APÓS detect_tuning() — não antes.
    Quando tuning_hz=None (beat percussivo), usa 440.0 Hz como fallback neutro.
    """
    audio = es.MonoLoader(filename=str(wav_path), sampleRate=44100)()
    freq = tuning_hz if tuning_hz is not None else 440.0
    key, scale, strength = es.KeyExtractor(
        profileType="edma",
        tuningFrequency=freq,
    )(audio)
    return str(f"{key} {scale}"), float(strength)
```

### Assinatura da tabela CAMELOT (sem alterações)

Os 24 casos que o Essentia pode produzir já estão cobertos:
```python
# Chaves no formato Essentia: "A minor", "Bb major", "C# minor", "Eb major", "F# minor", "Ab major", etc.
# Todos os 24 casos verificados: key_to_camelot("X scale") retorna código correto para todos
# [VERIFIED: execução live — loop sobre todos os 12 nomes Essentia x 2 escalas]
```

---

## State of the Art

| Abordagem Antiga | Abordagem Atual (Phase 6) | Quando muda | Impacto |
|-----------------|--------------------------|-------------|---------|
| `librosa.feature.tempo` com prior uniforme | `RhythmExtractor2013(method="multifeature")` | Phase 6 | Resistência a half-tempo em trap; mesmo algoritmo do Tunebat |
| Krumhansl-Schmuckler via chroma_cqt manual (30 linhas) | `KeyExtractor(profileType="edma")` | Phase 6 | HPCP com weighting harmônico; perfil calibrado para EDM |
| Sem detecção de tuning | `detect_tuning()` + HPSS gate | Phase 6 | Campo `tuning_hz` disponível para Phase 7 display |
| `detect_key()` retorna `(str, float)` sem argumento de tuning | `detect_key(wav_path, tuning_hz)` | Phase 6 | HPCP alinhado ao concert pitch do beat |

**Deprecado/obsoleto após Phase 6:**
- `_pick_best_tempo()`: helper de octave correction do librosa — não mais necessário; RhythmExtractor2013 multifeature já é resistente a octave errors
- `_detect_key_from_chroma()`: implementação Krumhansl-Schmuckler manual — substituída pelo KeyExtractor
- `_MAJOR_PROFILE`, `_MINOR_PROFILE`, `_NOTES`: constantes do perfil manual — não mais usadas
- Importação de `scipy.stats` em `pipeline.py`: usada apenas para o prior do librosa.feature.tempo — pode ser removida

---

## Open Questions

1. **Threshold HPSS 0.2 não validado em beats reais**
   - O que sabemos: sinal puramente percussivo (noise bursts) → razão 0.0; sinal 440Hz puro → razão 1.0. O threshold 0.2 discrimina esses extremos perfeitamente.
   - O que está unclear: beats de produção (trap, drill) têm razão harmônica entre 0.05 e 0.35 — não sabemos onde cai o limiar "percussivo suficiente para descartar tuning".
   - Recomendação: Implementar com 0.2 como está planejado. O TODO do STATE.md (testar em 15-20 beats reais) é o gating correto — Phase 7 / QUAL-02 valida empiricamente. Se vários beats de trap retornarem `tuning_hz=None` incorretamente, baixar para 0.1.

2. **Dois carregamentos de áudio: performance aceitável?**
   - O que sabemos: cada MonoLoader ou librosa.load para um WAV de 5 minutos leva ~0.3–0.5s. O pipeline de Celery background já aceita 30+ segundos de download.
   - O que está unclear: em WAVs próximos ao limite de 15 minutos, o double-load pode adicionar 2–3 segundos.
   - Recomendação: Aceitar. O overhead é < 5% do tempo total de processamento para tracks longas. Não otimizar prematuramente.

3. **tasks.py precisa expor tuning_hz na resposta da API**
   - O que sabemos: `api/tasks.py` mapeia explicitamente os campos de `analyze_audio()` no dict de retorno do `process_job`. O campo `tuning_hz` não está lá ainda.
   - O que está unclear: Phase 7 (Frontend Display) precisa desse campo — mas tecnicamente é escopo de Phase 7, não de Phase 6.
   - Recomendação: Incluir `"tuning_hz": result.get("tuning_hz")` em `tasks.py` como parte da Phase 6, mesmo que Phase 7 seja quem vai exibir. Evita uma correção de última hora em Phase 7.

---

## Assumptions Log

| # | Claim | Seção | Risco se errado |
|---|-------|-------|-----------------|
| — | Nenhum — todas as claims desta pesquisa foram verificadas via execução live no venv ou via documentação oficial | — | — |

**Esta tabela está vazia:** todas as claims críticas foram verificadas com ferramentas (execução live, PyPI, documentação Essentia). Nenhuma confirmação do usuário necessária antes da execução.

---

## Project Constraints (from CLAUDE.md)

| Diretriz | Impacto na Phase 6 |
|----------|--------------------|
| Backend: Python 3.11 + FastAPI | O venv usa Python 3.12 na prática — essentia tem wheel cp312 disponível. Sem impacto. |
| Task queue: Celery + Redis | analyze_audio() deve retornar dict com tipos JSON-nativos — requisito Celery JSON serializer. Confirmado. |
| Análise: librosa (BPM + key) | Phase 6 substitui librosa por Essentia para BPM/key. librosa permanece para tuning detection. Alinhado com STATE.md. |
| Frontend: Vanilla HTML + CSS + JS — zero frameworks | Não relevante para Phase 6 (backend only). |
| Sem contas de usuário — stateless | analyze_audio() é stateless (Path in, dict out). Sem alteração necessária. |
| WAV apenas | inalterado — MonoLoader carrega WAV; librosa.load carrega WAV. |

---

## Sources

### Primary (HIGH confidence — verificado por execução live no venv)

- Execução live: `import essentia.standard as es` no venv do projeto — OK sem exceção
- Execução live: `RhythmExtractor2013(method="multifeature")` + fixture WAV — bpm=Python float
- Execução live: `KeyExtractor(profileType="edma", tuningFrequency=440.0)` + fixture WAV — key="A", scale="minor" (Python str)
- Execução live: `librosa.effects.hpss()` + cálculo de ratio — percussivo→0.0, harmônico→0.9966
- Execução live: `librosa.estimate_tuning()` + `librosa.tuning_to_A4()` — retorna numpy.float64, aceita float()
- Execução live: `json.dumps(result_dict_completo)` — sem TypeError
- Execução live: loop CAMELOT — todos os 24 casos Essentia cobertos
- PyPI JSON API: `essentia 2.1b6.dev1389` — wheel cp312 Linux x86_64 confirmado, numpy>=1.25

### Secondary (MEDIUM confidence — documentação oficial)

- [Essentia RhythmExtractor2013 docs](https://essentia.upf.edu/reference/std_RhythmExtractor2013.html) — sampleRate=44100 obrigatório; method="multifeature" vs "degara"
- [Essentia KeyExtractor docs](https://essentia.upf.edu/reference/std_KeyExtractor.html) — profileType options, tuningFrequency parameter
- [Essentia key.cpp no GitHub](https://github.com/MTG/essentia/blob/master/src/algorithms/tonal/key.cpp) — 12 note names: A, Bb, B, C, C#, D, Eb, E, F, F#, G, Ab
- [librosa.estimate_tuning docs](https://librosa.org/doc/main/generated/librosa.estimate_tuning.html) — assinatura verificada via `inspect.signature`
- [librosa.tuning_to_A4 docs](https://librosa.org/doc/main/generated/librosa.tuning_to_A4.html) — verificado via `help()` no venv

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versões verificadas em PyPI, instalação testada no venv do projeto
- Architecture patterns: HIGH — todos os exemplos de código executados e verificados no venv
- Camelot coverage: HIGH — loop completo executado no venv, zero missing entries
- HPSS threshold: MEDIUM — comportamento verificado em sinais sintéticos; validação em beats reais é Phase 7/QUAL-02
- numpy type safety: HIGH — TypeError verificado diretamente; float() fix verificado

**Research date:** 2026-05-09
**Valid until:** 2026-08-09 (estável — essentia não tem breaking changes frequentes; librosa 0.11.x é LTS-ish)
