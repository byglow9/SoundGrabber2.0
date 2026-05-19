# SoundGrabber

Cola o link do YouTube. Baixa o beat em WAV. Vê o BPM e a tonalidade.  
Sem cadastro. Sem mensalidade. Sem enrolação.

<video src="docs/demo.mp4" controls width="100%"></video>

---

Para produtores, beatmakers e artistas underground.

Você achou uma batida no YouTube. Antes de samplear, quer saber o BPM exato, a tonalidade, o código Camelot. E quer o arquivo WAV direto, sem plataforma no meio do caminho.

É isso que o SoundGrabber faz.

→ **[soundgrabber.com.br](https://soundgrabber.com.br)**

---

## Como funciona

1. Cola o link do YouTube na caixa
2. Clica em **Baixar Beat**
3. Aguarda o processamento (menos de 1 minuto na maioria dos casos)
4. Baixa o WAV e vê BPM, tonalidade e código Camelot na tela

Aceita vídeos de até 15 minutos. Resultado em WAV lossless, pronto pra abrir no DAW.

---

## Modo ANALISAR

Já tem o arquivo no computador? Clica em **ANALISAR** na tela inicial, arrasta o áudio (WAV, MP3, FLAC ou M4A) e a ferramenta calcula BPM e tonalidade sem precisar de nenhum link.

---

## Som da Semana

Toda semana o SoundGrabber destaca um beat ou faixa de um artista underground brasileiro. A lógica é simples: quem produz fora do mainstream merece palco também.

Quer indicar seu projeto? → [soundgrabber.com.br/sobre#participar](https://soundgrabber.com.br/sobre#participar)

---

## Rodando localmente

```bash
cp .env.example .env
./start.sh
```

Requer Redis, FFmpeg e Essentia instalados. Detalhes de stack, variáveis de ambiente e arquitetura estão em `CLAUDE.md`.

---

## Testes

```bash
pytest                         # unitários (~5s, sem rede)
pytest -m integration          # integração (requer FFmpeg)
pytest tests/test_security.py  # gate de segurança obrigatório
```

---

## Licença

Projeto independente. Código aberto.  
Criado por [@divineglowboy](https://instagram.com/divineglowboy).
