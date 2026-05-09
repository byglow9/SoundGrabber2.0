# Requirements — SoundGrabber

## v1 Requirements

### CORE — Pipeline de Processamento

- [ ] **CORE-01**: Usuário pode colar um link do YouTube em um campo de texto e iniciar o processamento
- [ ] **CORE-02**: Sistema valida que a URL fornecida é um link válido do YouTube antes de processar
- [ ] **CORE-03**: Sistema baixa o áudio do vídeo do YouTube server-side usando yt-dlp com autenticação via cookies + PO Token
- [ ] **CORE-04**: Sistema converte o áudio baixado para formato WAV lossless usando FFmpeg
- [ ] **CORE-05**: Sistema recusa vídeos com duração acima de 15 minutos e exibe mensagem explicativa ao usuário
- [ ] **CORE-06**: Usuário pode baixar o arquivo WAV diretamente na página via botão de download após processamento

### ANALYSIS — Análise Musical

- [ ] **ANALYSIS-01**: Sistema detecta e exibe o BPM do beat usando librosa
- [ ] **ANALYSIS-02**: Sistema detecta e exibe a tonalidade musical (ex: F# minor, A major)
- [ ] **ANALYSIS-03**: Interface exibe também os valores de BPM na metade (÷2) e no dobro (×2) sem re-análise
- [ ] **ANALYSIS-04**: Sistema exibe a nota Camelot correspondente à tonalidade detectada (ex: 4A, 11B)

## v1.1 Requirements — Análise Musical de Precisão

### PRECISION — BPM e Tonalidade de Nível Profissional

- [ ] **PREC-01**: Sistema substitui detect_bpm() pelo algoritmo Essentia RhythmExtractor2013(method="multifeature") — mesmo algoritmo usado pelo Tunebat
- [ ] **PREC-02**: Sistema substitui detect_key() pelo algoritmo Essentia KeyExtractor(profileType="edma") com HPCP — perfil calibrado para música eletrônica
- [ ] **PREC-03**: detect_key() passa o tuning_hz detectado para KeyExtractor(tuningFrequency=tuning_hz) garantindo que os bins HPCP alinhem ao concert pitch real do beat
- [ ] **PREC-04**: Todos os valores retornados pelo Essentia são convertidos para float() nativo antes de entrar no dict de retorno de analyze_audio() — prevenindo TypeError no Celery JSON serializer
- [ ] **PREC-05**: KeyExtractor retorna key e scale como strings separadas; sistema monta "F# minor" antes de chamar key_to_camelot(), preservando a tabela Camelot existente

### TUNING — Detecção de Afinação

- [ ] **TUNING-01**: Sistema detecta a frequência de afinação de referência do beat (concert pitch) via librosa.estimate_tuning() + librosa.tuning_to_A4() e retorna como tuning_hz (float ou None)
- [ ] **TUNING-02**: detect_tuning() aplica HPSS antes de estimar o tuning e retorna None quando a razão de energia harmônica é insuficiente (beat muito percussivo, resultado seria ruído)
- [ ] **TUNING-03**: analyze_audio() inclui o campo tuning_hz no dict de retorno (float ou None) — serializable via JSON
- [ ] **TUNING-04**: Interface exibe "A = X Hz" no card de resultado quando tuning_hz não é None (ex: A = 432 Hz, A = 440 Hz)

### QUALITY — Testes e Validação

- [ ] **QUAL-01**: test_json_output_shape inclui tuning_hz no required fields set e valida que json.dumps(result) não levanta TypeError
- [ ] **QUAL-02**: Resultados de BPM e tonalidade são validados manualmente contra Tunebat com no mínimo 3 beats de referência (trap, house, lo-fi) antes do milestone ser considerado completo

### UX — Feedback e Experiência

- [ ] **UX-01**: Barra de progresso exibe a etapa atual do processamento (baixando → convertendo → analisando)
- [ ] **UX-02**: Sistema exibe o tamanho estimado do arquivo WAV antes do download
- [x] **UX-03**: Sistema exibe mensagens de erro claras e compreensíveis quando o YouTube bloqueia o download ou a URL é inválida
- [x] **UX-04**: Sistema informa o limite de duração de vídeo aceito (15 minutos) antes de o usuário submeter

### VISUAL — Identidade e Estética

- [ ] **VISUAL-01**: Interface segue estética autêntica dos anos 2000 — construída como um site que literalmente saiu naquela época (não uma releitura moderna)
- [ ] **VISUAL-02**: Design usa dark mode por padrão com paleta de cores hexadecimais brutas típicas da época
- [ ] **VISUAL-03**: Tipografia usa fontes bitmap/pixel (ex: Courier New, Fixedsys, VT323) sem font-smoothing moderno
- [ ] **VISUAL-04**: HTML/CSS estrutural usa padrões da época (tabelas para layout, bordas sólidas, sem flexbox/grid, sem variáveis CSS, sem animações modernas)
- [ ] **VISUAL-05**: Fase de UI inclui pesquisa de autenticidade sobre como sites reais de 2000-2005 eram construídos antes de implementar

---

## v2 Requirements (deferred)

- Waveform visualization — tecnicamente complexo, valor marginal vs. análise musical
- Suporte a outras plataformas além do YouTube (SoundCloud, Bandcamp)
- Outros formatos de export (MP3, FLAC)
- Sistema de contas / histórico de downloads
- API pública para integração com DAWs

---

## Out of Scope

- **Login / cadastro** — sem fricção é o valor central; qualquer barreira reduz adoção
- **Monetização / paywall** — v1 totalmente gratuito
- **Multi-plataforma** — foco no caso de uso YouTube que é onde a cena underground vive
- **Análise avançada** — stem separation, detecção de instrumentos, etc. — fora do escopo da ferramenta simples
- **Componentes UI modernos** — Tailwind, shadcn, React, qualquer framework — contraria a autenticidade Y2K

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| CORE-01 | Phase 2 | Pending |
| CORE-02 | Phase 2 | Pending |
| CORE-03 | Phase 1 | Pending |
| CORE-04 | Phase 1 | Pending |
| CORE-05 | Phase 1 | Pending |
| CORE-06 | Phase 2 | Pending |
| ANALYSIS-01 | Phase 1 | Pending |
| ANALYSIS-02 | Phase 1 | Pending |
| ANALYSIS-03 | Phase 1 | Pending |
| ANALYSIS-04 | Phase 1 | Pending |
| UX-01 | Phase 4 | Pending |
| UX-02 | Phase 4 | Pending |
| UX-03 | Phase 3 | Complete |
| UX-04 | Phase 3 | Complete |
| VISUAL-01 | Phase 5 | Pending |
| VISUAL-02 | Phase 5 | Pending |
| VISUAL-03 | Phase 5 | Pending |
| VISUAL-04 | Phase 5 | Pending |
| VISUAL-05 | Phase 5 | Pending |
| PREC-01 | Phase 6 | Pending |
| PREC-02 | Phase 6 | Pending |
| PREC-03 | Phase 6 | Pending |
| PREC-04 | Phase 6 | Pending |
| PREC-05 | Phase 6 | Pending |
| TUNING-01 | Phase 6 | Pending |
| TUNING-02 | Phase 6 | Pending |
| TUNING-03 | Phase 6 | Pending |
| TUNING-04 | Phase 7 | Pending |
| QUAL-01 | Phase 6 | Pending |
| QUAL-02 | Phase 7 | Pending |

---

*Last updated: 2026-05-09 — v1.1 requirements added: PREC-01..05, TUNING-01..04, QUAL-01..02*
