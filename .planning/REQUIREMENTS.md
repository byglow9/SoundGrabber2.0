# Requirements — SoundGrabber

## v1 Requirements

### CORE — Pipeline de Processamento

- [x] **CORE-01**: Usuário pode colar um link do YouTube em um campo de texto e iniciar o processamento
- [x] **CORE-02**: Sistema valida que a URL fornecida é um link válido do YouTube antes de processar
- [x] **CORE-03**: Sistema baixa o áudio do vídeo do YouTube server-side usando yt-dlp com autenticação via cookies + PO Token
- [x] **CORE-04**: Sistema converte o áudio baixado para formato WAV lossless usando FFmpeg
- [x] **CORE-05**: Sistema recusa vídeos com duração acima de 15 minutos e exibe mensagem explicativa ao usuário
- [x] **CORE-06**: Usuário pode baixar o arquivo WAV diretamente na página via botão de download após processamento

### ANALYSIS — Análise Musical

- [x] **ANALYSIS-01**: Sistema detecta e exibe o BPM do beat usando librosa
- [x] **ANALYSIS-02**: Sistema detecta e exibe a tonalidade musical (ex: F# minor, A major)
- [x] **ANALYSIS-03**: Interface exibe também os valores de BPM na metade (÷2) e no dobro (×2) sem re-análise
- [x] **ANALYSIS-04**: Sistema exibe a nota Camelot correspondente à tonalidade detectada (ex: 4A, 11B)

### UX — Feedback e Experiência

- [x] **UX-01**: Barra de progresso exibe a etapa atual do processamento (baixando → convertendo → analisando)
- [x] **UX-02**: Sistema exibe o tamanho estimado do arquivo WAV antes do download
- [x] **UX-03**: Sistema exibe mensagens de erro claras e compreensíveis quando o YouTube bloqueia o download ou a URL é inválida
- [x] **UX-04**: Sistema informa o limite de duração de vídeo aceito (15 minutos) antes de o usuário submeter

### VISUAL — Identidade e Estética

- [x] **VISUAL-01**: Interface segue estética autêntica dos anos 2000 — construída como um site que literalmente saiu naquela época (não uma releitura moderna)
- [x] **VISUAL-02**: Design usa dark mode por padrão com paleta de cores hexadecimais brutas típicas da época
- [x] **VISUAL-03**: Tipografia usa fontes bitmap/pixel (ex: Courier New, Fixedsys, VT323) sem font-smoothing moderno
- [x] **VISUAL-04**: HTML/CSS estrutural usa padrões da época (tabelas para layout, bordas sólidas, sem flexbox/grid, sem variáveis CSS, sem animações modernas)
- [x] **VISUAL-05**: Fase de UI inclui pesquisa de autenticidade sobre como sites reais de 2000-2005 eram construídos antes de implementar

---

## v1.1 Requirements — Security Hardening

### SEC-FILE — Segurança de Arquivos

- [ ] **SEC-FILE-01**: Arquivos WAV em /tmp são criados com permissões 0o600 (não legíveis por outros usuários do sistema)
- [ ] **SEC-FILE-02**: Script start.sh tem permissões 750 (não world-executable)

### SEC-INFRA — Infraestrutura

- [ ] **SEC-INFRA-01**: Redis exige autenticação obrigatória; startup falha com mensagem clara se REDIS_URL não contiver senha (exceto quando DEV_MODE=true)
- [ ] **SEC-INFRA-02**: Uvicorn configurado para escutar em 127.0.0.1 (não 0.0.0.0) com nginx como reverse proxy
- [ ] **SEC-INFRA-03**: HTTPS configurado via nginx com certificado Let's Encrypt; HTTP redireciona para HTTPS
- [ ] **SEC-INFRA-04**: Header HSTS (Strict-Transport-Security: max-age=31536000) presente em todas as respostas HTTPS

### SEC-API — Rate Limiting e Controles de API

- [ ] **SEC-API-01**: GET /jobs/{id} tem rate limit de 60/minuto por IP
- [ ] **SEC-API-02**: GET /files/{id} tem rate limit de 10/minuto por IP
- [ ] **SEC-API-03**: GET /health retorna status do Redis e responde 200 quando saudável, 503 quando Redis indisponível

### SEC-TEST — Testes de Segurança

- [ ] **SEC-TEST-01**: tests/test_security.py cobre body size limit (413 em body > 4KB)
- [ ] **SEC-TEST-02**: tests/test_security.py cobre presença de todos os security headers (X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy)
- [ ] **SEC-TEST-03**: tests/test_security.py confirma que /docs, /redoc e /openapi.json retornam 404
- [ ] **SEC-TEST-04**: tests/test_security.py confirma que queue depth limit retorna 503
- [ ] **SEC-TEST-05**: tests/test_security.py confirma que rate limit em GET /jobs e GET /files funciona
- [ ] **SEC-TEST-06**: pip-audit documentado em README como verificação obrigatória pré-deploy

### SEC-POLICY — Política de Segurança

- [ ] **SEC-POLICY-01**: Security Gate documentado em CLAUDE.md como regra obrigatória para novas funcionalidades
- [ ] **SEC-POLICY-02**: Checklist de segurança do projeto documentada em .planning/SECURITY-CHECKLIST.md

---

## v2 Requirements (deferred)

- Waveform visualization — tecnicamente complexo, valor marginal vs. análise musical
- Suporte a outras plataformas além do YouTube (SoundCloud, Bandcamp)
- Outros formatos de export (MP3, FLAC)
- Sistema de contas / histórico de downloads
- API pública para integração com DAWs
- Redis TLS para deployments multi-servidor
- Job cancellation endpoint (DELETE /jobs/{id})
- Private /tmp directory por job (em vez de /tmp global)
- Log rotation configurado
- Alerting automático (queue depth, taxa de erros)

---

## Out of Scope

- **Login / cadastro** — sem fricção é o valor central; qualquer barreira reduz adoção
- **Monetização / paywall** — v1 totalmente gratuito
- **Multi-plataforma** — foco no caso de uso YouTube que é onde a cena underground vive
- **Análise avançada** — stem separation, detecção de instrumentos, etc. — fora do escopo da ferramenta simples
- **Componentes UI modernos** — Tailwind, shadcn, React, qualquer framework — contraria a autenticidade Y2K
- **SRI (Subresource Integrity)** para assets locais — overhead sem ganho real para assets self-hosted
- **Remoção de 'unsafe-inline' do CSP** — requer migrar todos inline styles do HTML Y2K, scope v1.2

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| CORE-01..06 | Phase 2 | Complete |
| ANALYSIS-01..04 | Phase 1 | Complete |
| UX-01..04 | Phase 3/4 | Complete |
| VISUAL-01..05 | Phase 5 | Complete |
| SEC-FILE-01 | Phase 6 | Pending |
| SEC-FILE-02 | Phase 6 | Pending |
| SEC-INFRA-01 | Phase 6 | Pending |
| SEC-INFRA-02 | Phase 7 | Pending |
| SEC-INFRA-03 | Phase 7 | Pending |
| SEC-INFRA-04 | Phase 7 | Pending |
| SEC-API-01 | Phase 6 | Pending |
| SEC-API-02 | Phase 6 | Pending |
| SEC-API-03 | Phase 6 | Pending |
| SEC-TEST-01..06 | Phase 6 | Pending |
| SEC-POLICY-01 | Phase 6 | Pending |
| SEC-POLICY-02 | Phase 6 | Pending |

---

*Last updated: 2026-05-09 — v1.1 Security Hardening requirements defined*
