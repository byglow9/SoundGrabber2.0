'use strict';

function yonkouMessage(text) {
  const node = document.getElementById('yonkou-message');
  if (node) node.textContent = text;
}

function featuredLinksFromForm() {
  const links = [];
  for (let i = 1; i <= 3; i += 1) {
    const label = document.getElementById(`featured-link-label-${i}`);
    const url = document.getElementById(`featured-link-url-${i}`);
    if (!label || !url) continue;
    const labelValue = label.value.trim();
    const urlValue = url.value.trim();
    if (labelValue || urlValue) {
      links.push({ label: labelValue, url: urlValue });
    }
  }
  return links;
}

function wireLoginForm() {
  const form = document.getElementById('yonkou-login');
  if (!form) return;

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const password = document.getElementById('password').value;
    const response = await fetch('/yonkou/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });

    if (response.ok) {
      window.location.href = '/yonkou';
      return;
    }
    yonkouMessage('Senha incorreta ou limite atingido.');
  });
}

function wireFeaturedEditor() {
  const form = document.getElementById('featured-editor');
  if (!form) return;

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const payload = {
      artista: document.getElementById('featured-artista').value.trim(),
      titulo: document.getElementById('featured-title').value.trim(),
      genero: document.getElementById('featured-genero').value.trim(),
      descricao: document.getElementById('featured-descricao').value.trim(),
      links: featuredLinksFromForm()
    };

    const response = await fetch('/featured', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (response.ok) {
      yonkouMessage('Som da Semana salvo.');
      return;
    }
    const data = await response.json().catch(() => ({}));
    yonkouMessage(data.error || data.detail || 'Nao foi possivel salvar.');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  wireLoginForm();
  wireFeaturedEditor();
});
