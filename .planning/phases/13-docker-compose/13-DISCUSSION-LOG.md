# Phase 13: Docker Compose - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 13-docker-compose
**Areas discussed:** imageio-ffmpeg e librosa, Essentia no container slim, tmpfs path (/tmp vs /data/tmp), bgutil no Docker Compose

---

## imageio-ffmpeg e librosa

| Option | Description | Selected |
|--------|-------------|----------|
| Remover imageio-ffmpeg do req + alterar pipeline.py | Remove de requirements.txt e limpa código para usar apenas shutil.which('ffmpeg') | ✓ |
| Remover imageio-ffmpeg do req, adicionar assert no startup | Remove de requirements.txt, coloca assert em api/main.py | |
| Manter imageio-ffmpeg no req por compatibilidade Railway | Não remove de requirements.txt, imageio-ffmpeg presente mas não usado no container | |

**User's choice:** Remover imageio-ffmpeg do req + alterar pipeline.py

---

| Option | Description | Selected |
|--------|-------------|----------|
| Remover librosa nesta fase junto com imageio-ffmpeg | Remove librosa==0.11.0 de requirements.txt agora | ✓ |
| Remover librosa em fase separada | Não mistura com esta fase | |

**User's choice:** Remover librosa nesta fase junto com imageio-ffmpeg
**Notes:** Librosa não é aceita no projeto — Essentia é o padrão obrigatório. Faz sentido limpar junto.

---

## Essentia no container slim

| Option | Description | Selected |
|--------|-------------|----------|
| Instalar deps via apt + pip install normal | apt install ffmpeg libsndfile1; pip install essentia; ajustar até funcionar | ✓ |
| Usar python:3.11 full como base | Imagem full tem mais libs, mas ~200MB extra; mudaria DEPLOY-04 | |

**User's choice:** Instalar deps via apt + pip install normal

---

| Option | Description | Selected |
|--------|-------------|----------|
| Bloquear: executor roda o docker run e confirma OK antes de continuar | Validação obrigatória antes de avançar no plano | ✓ |
| Iterar: tarefa inclui troubleshooting steps se o import falhar | Lista de erros comuns e ações de correção | |

**User's choice:** Bloquear — executor confirma OK antes de continuar
**Notes:** Gate obrigatório alinhado com D-15 da Phase 12 (Essentia é bloqueador).

---

## tmpfs path (/tmp vs /data/tmp)

| Option | Description | Selected |
|--------|-------------|----------|
| /tmp (seguir DEPLOY-06 literalmente) | tmpfs em /tmp; sem mudança de código | ✓ |
| /data/tmp (seguir D-17 da Phase 12) | SG_TMP_DIR=/data/tmp; mudança em pipeline.py | |

**User's choice:** /tmp (seguir DEPLOY-06 literalmente)
**Notes:** D-17 da Phase 12 foi descartada. DEPLOY-06 é mais recente e explícito.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Não — tmpfs compartilhado resolve automaticamente | Sem mudança de código | ✓ |
| Verificar: garantir que api/main.py não usa path diferente | Checar TMPDIR env var | |

**User's choice:** Não — sem mudança de código necessária

---

## bgutil no Docker Compose

| Option | Description | Selected |
|--------|-------------|----------|
| Incluir bgutil como 4º serviço no compose | jim60105/bgutil-pot na rede interna; BGUTIL_BASE_URL=http://bgutil:4416 | ✓ |
| Omitir bgutil — BGUTIL_BASE_URL vazio | IP residencial tem menos bot detection; adiciona depois se precisar | |
| Incluir bgutil desabilitado por default | Presente no compose mas URL vazia; operador ativa se precisar | |

**User's choice:** Incluir bgutil como 4º serviço no compose

---

| Option | Description | Selected |
|--------|-------------|----------|
| Adicionar bgutil no compose (estende DEPLOY-05) | 4º serviço na rede interna, sem porta exposta | ✓ |
| bgutil externo ao compose (systemd service no host) | Mais complexo; separa concerns mas adiciona overhead de configuração | |

**User's choice:** Adicionar bgutil no compose (estende DEPLOY-05)

---

## Claude's Discretion

- Limites de memória/CPU no compose (valores razoáveis para i5-3210M/4GB RAM)
- Estrutura de variáveis de ambiente (env_file vs environment block)
- Health checks no compose (pode adicionar ou deixar para fase posterior)
- Nome da rede interna do compose

## Deferred Ideas

- SG_TMP_DIR=/data/tmp (D-17 Phase 12): descartada nesta fase
- SSH hardening / deploy.sh via SSH: Phase 14
- Cloudflare Tunnel: Phase 15
- DOCKER-USER rules no UFW: após compose publicar portas em produção
