# Google Analytics — Obrigações de Conformidade

Itens exigidos pelos Termos de Serviço do Google Analytics (atualizado em 15/05/2023)
para operar o SoundGrabber com o GA4 ativo.

---

## 1. Página de Política de Privacidade

**Obrigatório pela Seção 7 dos ToS do GA.**

Criar `/privacidade` (ou `static/privacy.html`) com no mínimo:

- Declaração de que o site usa Google Analytics para medir tráfego
- Explicação de que cookies são usados pelo GA para identificar sessões únicas
- Link para a política do Google: https://policies.google.com/privacy
- Link obrigatório pelo ToS: "Como o Google usa informações de sites que usam nossos serviços" → https://www.google.com/policies/privacy/partners/
- Informação de que nenhum dado pessoal (nome, e-mail, CPF) é coletado pelo SoundGrabber

## 2. Aviso/Link de Privacidade no Rodapé

**Obrigatório pela Seção 7 — o link precisa ser "em destaque".**

Adicionar no rodapé do `index.html`:

- Link visível para a página de Política de Privacidade
- Pode ser simples, estilo Y2K, mas tem que estar presente

## 3. Snippet do Google Analytics no HTML

Adicionar no `<head>` do `static/index.html` (após obter o Measurement ID G-XXXXXXXXXX):

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

---

## O que NÃO precisa fazer

- Aviso de cookie pop-up — não é exigido pelo GA ToS (só seria obrigado pela LGPD/GDPR
  para usuários europeus; o SoundGrabber é focado em BR por ora)
- Cadastro ou login — a ferramenta é stateless, nenhum dado pessoal é coletado
- Nada de Firebase, Ads ou outras integrações — ToS simples se aplicam

---

## Status

- [x] Criar `static/privacy.html`
- [x] Adicionar link de privacidade no rodapé do `index.html`
- [x] Inserir snippet do GA no `<head>` com o Measurement ID real (G-YZ11H44JCS)
