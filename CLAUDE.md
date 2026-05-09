# SoundGrabber — Project Guide

## What This Is

Ferramenta web para produtores e artistas underground colarem um link do YouTube, baixarem o beat em WAV e visualizarem BPM e tonalidade. Gratuito, sem cadastro, download direto. Estética autêntica dos anos 2000 (phpBB/Tibia/Orkut).

## Stack

- **Backend:** Python 3.11 + FastAPI
- **Task queue:** Celery + Redis
- **Download:** yt-dlp (com cookies + PO Token — obrigatório para YouTube)
- **Conversão:** FFmpeg
- **Análise:** librosa (BPM + key detection)
- **Frontend:** Vanilla HTML + CSS + JS — zero frameworks

## GSD Workflow

Este projeto usa GSD para planejamento e execução.

### Comandos principais

```
/gsd-plan-phase 1     # Planejar a próxima fase
/gsd-execute-phase 1  # Executar os planos da fase
/gsd-progress         # Ver estado atual do projeto
/gsd-discuss-phase N  # Discutir abordagem antes de planejar
```

### Arquivos de planejamento

- `.planning/PROJECT.md` — contexto e decisões do projeto
- `.planning/REQUIREMENTS.md` — requisitos v1 com REQ-IDs
- `.planning/ROADMAP.md` — 5 fases, 19 requisitos mapeados
- `.planning/STATE.md` — estado atual
- `.planning/research/` — pesquisa de domínio (stack, features, arquitetura, pitfalls)

## Fases

| # | Fase | Status |
|---|------|--------|
| 1 | Processing Pipeline | Not started |
| 2 | API Layer | Not started |
| 3 | Hardening | Not started |
| 4 | Frontend | Not started |
| 5 | Visual Identity | Not started |

## Restrições críticas

- **Sem contas de usuário** — ferramenta stateless, sem auth
- **WAV apenas** — formato lossless, qualidade para produtores
- **Limite de 15 minutos** — vídeos mais longos são recusados
- **Estética Y2K autêntica** — construído COMO sites de 2000-2005, não releitura moderna. Tabelas para layout, sem flexbox/grid, fontes bitmap, hex colors brutas, sem CSS variables
- **YouTube bot detection** — yt-dlp DEVE usar cookies + PO Token desde o primeiro deploy

## Security Gate

**Regra obrigatoria para qualquer nova feature ou modificacao.** Toda mudanca em codigo de producao DEVE passar por este gate antes do merge. Esta secao tem precedencia sobre velocidade de entrega.

### Controles obrigatorios em qualquer novo endpoint HTTP

1. **Rate limiting** — qualquer rota nova (GET, POST, PUT, DELETE) DEVE ter `@limiter.limit("<N>/minute")`. Default conservador: 60/min para reads, 10/min para writes/downloads. Justificar se omitir.
2. **Request body validation** — POST/PUT DEVEM usar Pydantic `BaseModel` com `field_validator`. Sem `request.json()` cru.
3. **Body size limit** — middleware `_limit_body_size` (4KB) ja cobre globalmente. Se uma rota legitimamente precisar mais, justificar e aumentar `_MAX_BODY_BYTES` com nota explicita.
4. **Sync routes com slowapi** — SEMPRE adicionar `request: Request, response: Response` na assinatura. Sem isso, slowapi sync_wrapper levanta Exception em runtime.

### Controles obrigatorios em qualquer novo arquivo gerado em /tmp

1. **Permissoes 0o600** — `os.chmod(path, 0o600)` apos confirmar que o arquivo existe. Bloqueia leitura por outros usuarios do sistema.
2. **Prefixo `sg_`** — todos os arquivos do projeto em /tmp comecam com `sg_` para o sweeper limpar e para path-traversal defense.
3. **Path traversal defense** — qualquer endpoint que retorne arquivo DEVE validar `path.resolve().relative_to(Path("/tmp").resolve())` antes de servir.

### Controles obrigatorios em qualquer novo script shell

1. **`set -e`** na primeira linha apos shebang.
2. **Auto-chmod restritivo** — `chmod 750 "$(realpath "$0")"` para scripts de operacao; `chmod 600` para scripts contendo segredos.
3. **Sem `eval` de input externo** — uso de `eval` requer justificativa explicita.

### Testes obrigatorios

1. **Cada novo endpoint DEVE ter teste em `tests/test_security.py`** confirmando rate limit e validacoes.
2. **`pytest tests/test_security.py` DEVE estar verde** antes de qualquer commit em main.
3. **`pip-audit -r requirements.txt`** DEVE ser executado antes de cada deploy (ver `.planning/SECURITY-CHECKLIST.md`).

### Documentacao obrigatoria

1. **`.planning/SECURITY-CHECKLIST.md`** eh a fonte de verdade dos controles ativos. Nova feature que adiciona controle DEVE atualizar este arquivo.
2. **REQUIREMENTS.md** deve ter REQ-ID novo (categoria SEC-*) para qualquer novo controle de seguranca.

### Quando esta regra pode ser flexibilizada

Nunca silenciosamente. Apenas com decisao explicita registrada em `STATE.md` (Key Decisions) e justificativa que sobreviva a revisao 6 meses depois. Default eh: aplicar o controle.

## Próximo passo

```
/gsd-discuss-phase 1
```
