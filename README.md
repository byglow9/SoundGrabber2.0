<div align="center">

# SoundGrabber

**Cola o link do YouTube. Baixa o beat em WAV. Vê o BPM e a tonalidade.**  
Sem cadastro. Sem mensalidade. Sem enrolação.

[![Python](https://img.shields.io/badge/Python-3.11+-ff8800?style=flat-square&logo=python&logoColor=white&labelColor=000000)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-ff8800?style=flat-square&logo=fastapi&logoColor=white&labelColor=000000)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Celery-Redis-ff8800?style=flat-square&logo=celery&logoColor=white&labelColor=000000)](https://docs.celeryq.dev/)
[![Essentia](https://img.shields.io/badge/Análise-Essentia-ff8800?style=flat-square&logoColor=white&labelColor=000000)](https://essentia.upf.edu/)
[![License](https://img.shields.io/badge/licença-open%20source-ff8800?style=flat-square&labelColor=000000)]()

**[soundgrabber.com.br](https://soundgrabber.com.br)**

</div>

---

<video src="https://github.com/user-attachments/assets/1611d0d4-da5a-426e-8fd3-2416de678e57" controls width="700"></video>

---

## Para quem é isso

Para beatmakers, produtores e artistas underground que trabalham com música de forma prática.

Você achou uma batida foda no YouTube. Quer saber o BPM exato antes de samplear, confirmar a tonalidade antes de encaixar no projeto, ter o WAV direto no computador pra abrir no DAW. O SoundGrabber faz tudo isso em menos de um minuto, sem precisar instalar nada.

## Como funciona

1. Cola o link do YouTube na caixa
2. Clica em **Baixar Beat**
3. Aguarda o processamento
4. Baixa o WAV e vê BPM, tonalidade e código Camelot na tela

Aceita vídeos de até 15 minutos. Resultado em WAV lossless (44.1 kHz, 16-bit).

## Modo ANALISAR

Já tem o arquivo no computador? Clica em **ANALISAR** na tela inicial, arrasta o áudio (WAV · MP3 · FLAC · M4A) e a ferramenta retorna BPM e tonalidade sem precisar de nenhum link.

## Som da Semana

Toda semana o SoundGrabber destaca um beat ou faixa de um artista underground brasileiro. A lógica é simples: quem produz fora do mainstream merece palco também.

Quer indicar seu projeto? → [soundgrabber.com.br/sobre#participar](https://soundgrabber.com.br/sobre#participar)

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + FastAPI |
| Fila de tarefas | Celery + Redis |
| Download | yt-dlp (cookies + PO Token) |
| Conversão | FFmpeg |
| Análise | Essentia — RhythmExtractor2013 + KeyExtractor |
| Frontend | Vanilla HTML / CSS / JS — zero frameworks |

A estética do frontend segue os anos 2000 autênticos: layout em `<table>`, fontes bitmap, hex colors brutas, sem CSS variables, sem flexbox/grid.

## Rodando localmente

```bash
cp .env.example .env
./start.sh          # inicia Redis + Celery + Uvicorn com --reload
```

Requer Redis, FFmpeg e Essentia instalados. Todas as variáveis de ambiente estão documentadas em `.env.example` e em `CLAUDE.md`.

## Testes

```bash
pytest                         # unitários (~5s, sem rede)
pytest -m integration          # integração (requer FFmpeg)
pytest tests/test_security.py  # gate de segurança — deve estar verde antes de qualquer merge
```

## Deploy

```bash
bash scripts/predeploy-check.sh   # auditoria de dependências + segurança
bash scripts/deploy.sh            # build + docker compose up
```

Documentação de deploy seguro em [`docs/DEPLOY-SECURE.md`](docs/DEPLOY-SECURE.md).

---

<div align="center">

Criado por [@divineglowboy](https://instagram.com/divineglowboy)

</div>
