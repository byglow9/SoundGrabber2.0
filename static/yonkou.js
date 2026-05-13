'use strict';

function yonkouMessage(text) {
  const node = document.getElementById('yonkou-message');
  if (node) node.textContent = text;
}

function getLinkLabel(i) {
  const select = document.getElementById(`featured-link-label-${i}`);
  if (!select) return '';
  if (select.value === 'Outros') {
    const custom = document.getElementById(`featured-link-label-custom-${i}`);
    return custom ? custom.value.trim() : '';
  }
  return select.value;
}

function featuredLinksFromForm() {
  const links = [];
  for (let i = 1; i <= 4; i += 1) {
    const url = document.getElementById(`featured-link-url-${i}`);
    if (!url) continue;
    const labelValue = getLinkLabel(i);
    const urlValue = url.value.trim();
    if (labelValue || urlValue) {
      links.push({ label: labelValue, url: urlValue });
    }
  }
  return links;
}

function wireSelectLabels() {
  for (let i = 1; i <= 4; i += 1) {
    const select = document.getElementById(`featured-link-label-${i}`);
    const custom = document.getElementById(`featured-link-label-custom-${i}`);
    if (!select || !custom) continue;
    select.addEventListener('change', () => {
      custom.style.display = select.value === 'Outros' ? '' : 'none';
      if (select.value !== 'Outros') custom.value = '';
    });
  }
}

function createArtistaRow(nome, url) {
  const row = document.createElement('div');
  row.className = 'artista-row';

  const nomeInput = document.createElement('input');
  nomeInput.className = 'yonkou-input artista-nome';
  nomeInput.placeholder = 'nome';
  nomeInput.value = nome || '';

  const urlInput = document.createElement('input');
  urlInput.className = 'yonkou-input artista-url';
  urlInput.placeholder = 'link (opcional)';
  urlInput.value = url || '';

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'artista-remove';
  removeBtn.textContent = '×';
  removeBtn.addEventListener('click', () => {
    const list = document.getElementById('artistas-list');
    if (list && list.querySelectorAll('.artista-row').length > 1) row.remove();
  });

  row.appendChild(nomeInput);
  row.appendChild(urlInput);
  row.appendChild(removeBtn);
  return row;
}

function initArtistasList() {
  const list = document.getElementById('artistas-list');
  if (!list) return;
  const artistas = window.YONKOU_ARTISTAS || [];
  if (artistas.length === 0) {
    list.appendChild(createArtistaRow('', ''));
  } else {
    artistas.forEach(a => list.appendChild(createArtistaRow(a.nome || '', a.url || '')));
  }
}

function wireArtistasList() {
  const addBtn = document.getElementById('add-artista-btn');
  const list = document.getElementById('artistas-list');
  if (!addBtn || !list) return;
  addBtn.addEventListener('click', () => list.appendChild(createArtistaRow('', '')));
}

function artistasFromForm() {
  const artistas = [];
  document.querySelectorAll('.artista-row').forEach(row => {
    const nome = row.querySelector('.artista-nome').value.trim();
    const url = row.querySelector('.artista-url').value.trim();
    if (nome || url) artistas.push({ nome, url });
  });
  return artistas;
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
    yonkouMessage('erro');
  });
}

function wireFeaturedEditor() {
  const form = document.getElementById('featured-editor');
  if (!form) return;

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const payload = {
      artistas: artistasFromForm(),
      titulo: document.getElementById('featured-titulo').value.trim(),
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
  initArtistasList();
  wireArtistasList();
  wireFeaturedEditor();
  wireSelectLabels();
});
