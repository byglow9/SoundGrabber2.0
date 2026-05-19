'use strict';

var _submitMethod = 'POST';
var _KNOWN_LABELS = ['Youtube', 'Soundcloud', 'Spotify', 'Instagram'];

function yonkouMessage(text) {
  var node = document.getElementById('yonkou-message');
  if (node) node.textContent = text;
}

function csrfToken() {
  var wrapper = document.getElementById('yonkou-wrapper');
  return wrapper && wrapper.dataset ? wrapper.dataset.csrfToken || '' : '';
}

function csrfHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken()
  };
}

function initialFeaturedList(key) {
  var form = document.getElementById('featured-editor');
  if (!form || !form.dataset || !form.dataset[key]) return [];
  try {
    var data = JSON.parse(form.dataset[key]);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    return [];
  }
}

// ── Link helpers ──────────────────────────────────────────────────────────────

function getLinkLabel(i) {
  var select = document.getElementById('featured-link-label-' + i);
  if (!select) return '';
  if (select.value === 'Outros') {
    var custom = document.getElementById('featured-link-label-custom-' + i);
    return custom ? custom.value.trim() : '';
  }
  return select.value;
}

function featuredLinksFromForm() {
  var links = [];
  for (var i = 1; i <= 4; i++) {
    var url = document.getElementById('featured-link-url-' + i);
    if (!url) continue;
    var labelValue = getLinkLabel(i);
    var urlValue = url.value.trim();
    if (labelValue || urlValue) {
      links.push({ label: labelValue, url: urlValue });
    }
  }
  return links;
}

function wireSelectLabels() {
  for (var i = 1; i <= 4; i++) {
    (function(idx) {
      var select = document.getElementById('featured-link-label-' + idx);
      var custom = document.getElementById('featured-link-label-custom-' + idx);
      if (!select || !custom) return;
      select.addEventListener('change', function() {
        custom.style.display = select.value === 'Outros' ? '' : 'none';
        if (select.value !== 'Outros') custom.value = '';
      });
    })(i);
  }
}

function clearLinkInputs() {
  for (var i = 1; i <= 4; i++) {
    var select = document.getElementById('featured-link-label-' + i);
    var custom = document.getElementById('featured-link-label-custom-' + i);
    var urlInput = document.getElementById('featured-link-url-' + i);
    if (select) select.value = '';
    if (custom) { custom.style.display = 'none'; custom.value = ''; }
    if (urlInput) urlInput.value = '';
  }
}

// ── Artistas helpers ──────────────────────────────────────────────────────────

function createArtistaRow(nome, url) {
  var row = document.createElement('div');
  row.className = 'artista-row';

  var nomeInput = document.createElement('input');
  nomeInput.className = 'yonkou-input artista-nome';
  nomeInput.placeholder = 'nome';
  nomeInput.value = nome || '';

  var urlInput = document.createElement('input');
  urlInput.className = 'yonkou-input artista-url';
  urlInput.placeholder = 'link (opcional)';
  urlInput.value = url || '';

  var removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'artista-remove';
  removeBtn.textContent = '×';
  removeBtn.addEventListener('click', function() {
    var list = document.getElementById('artistas-list');
    if (list && list.querySelectorAll('.artista-row').length > 1) row.remove();
  });

  row.appendChild(nomeInput);
  row.appendChild(urlInput);
  row.appendChild(removeBtn);
  return row;
}

function initArtistasList() {
  var list = document.getElementById('artistas-list');
  if (!list) return;
  var artistas = initialFeaturedList('artistas');
  list.innerHTML = '';
  if (artistas.length === 0) {
    list.appendChild(createArtistaRow('', ''));
  } else {
    artistas.forEach(function(a) {
      list.appendChild(createArtistaRow(a.nome || '', a.url || ''));
    });
  }
}

function clearArtistasList() {
  var list = document.getElementById('artistas-list');
  if (!list) return;
  list.innerHTML = '';
  list.appendChild(createArtistaRow('', ''));
}

function wireArtistasList() {
  var addBtn = document.getElementById('add-artista-btn');
  var list = document.getElementById('artistas-list');
  if (!addBtn || !list) return;
  addBtn.addEventListener('click', function() {
    list.appendChild(createArtistaRow('', ''));
  });
}

function artistasFromForm() {
  var artistas = [];
  document.querySelectorAll('#artistas-list .artista-row').forEach(function(row) {
    var nomeInput = row.querySelector('.artista-nome');
    var urlInput = row.querySelector('.artista-url');
    if (!nomeInput || !urlInput) return;
    var nome = nomeInput.value.trim();
    var url = urlInput.value.trim();
    if (nome || url) artistas.push({ nome: nome, url: url });
  });
  return artistas;
}

// ── Produtores helpers ────────────────────────────────────────────────────────

function createProdutorRow(nome, url) {
  var row = document.createElement('div');
  row.className = 'produtor-row';

  var nomeInput = document.createElement('input');
  nomeInput.className = 'yonkou-input produtor-nome';
  nomeInput.placeholder = 'nome';
  nomeInput.value = nome || '';

  var urlInput = document.createElement('input');
  urlInput.className = 'yonkou-input produtor-url';
  urlInput.placeholder = 'link (opcional)';
  urlInput.value = url || '';

  var removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'artista-remove';
  removeBtn.textContent = '×';
  removeBtn.addEventListener('click', function() {
    var list = document.getElementById('produtores-list');
    if (list && list.querySelectorAll('.produtor-row').length > 1) row.remove();
  });

  row.appendChild(nomeInput);
  row.appendChild(urlInput);
  row.appendChild(removeBtn);
  return row;
}

function initProdutoresList() {
  var list = document.getElementById('produtores-list');
  if (!list) return;
  var produtores = initialFeaturedList('produtores');
  list.innerHTML = '';
  if (produtores.length === 0) {
    list.appendChild(createProdutorRow('', ''));
  } else {
    produtores.forEach(function(p) {
      list.appendChild(createProdutorRow(p.nome || '', p.url || ''));
    });
  }
}

function clearProdutoresList() {
  var list = document.getElementById('produtores-list');
  if (!list) return;
  list.innerHTML = '';
  list.appendChild(createProdutorRow('', ''));
}

function wireProdutoresList() {
  var addBtn = document.getElementById('add-produtor-btn');
  var list = document.getElementById('produtores-list');
  if (!addBtn || !list) return;
  addBtn.addEventListener('click', function() {
    list.appendChild(createProdutorRow('', ''));
  });
}

function produtoresFromForm() {
  var produtores = [];
  document.querySelectorAll('#produtores-list .produtor-nome').forEach(function(nomeInput) {
    var row = nomeInput.closest('.produtor-row');
    var urlInput = row ? row.querySelector('.produtor-url') : null;
    var nome = nomeInput.value.trim();
    var url = urlInput ? urlInput.value.trim() : '';
    if (nome || url) produtores.push({ nome: nome, url: url });
  });
  return produtores;
}

// ── Modos EDITAR / NOVO SOM ───────────────────────────────────────────────────

function showFormSection() {
  var dashboard = document.getElementById('yonkou-dashboard');
  var section = document.getElementById('form-section');
  if (dashboard) dashboard.style.display = 'none';
  if (section) section.style.display = '';
}

function hideFormSection() {
  var dashboard = document.getElementById('yonkou-dashboard');
  var section = document.getElementById('form-section');
  if (section) section.style.display = 'none';
  if (dashboard) dashboard.style.display = '';
  yonkouMessage('');
}

function wireVoltarButton() {
  var btn = document.getElementById('voltar-btn');
  if (!btn) return;
  btn.addEventListener('click', hideFormSection);
}

function wireLogoutButton() {
  var btn = document.getElementById('logout-btn');
  if (!btn) return;
  btn.addEventListener('click', function() {
    fetch('/yonkou/logout', {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ logout: true })
    }).then(function() {
      window.location.href = '/yonkou';
    }).catch(function() {
      window.location.href = '/yonkou';
    });
  });
}

function wireEditButton() {
  var btn = document.getElementById('edit-btn');
  if (!btn) return;
  btn.addEventListener('click', function() {
    _submitMethod = 'PATCH';
    var title = document.getElementById('form-title');
    if (title) title.textContent = 'Editar Som Atual';
    initArtistasList();
    initProdutoresList();
    showFormSection();
    yonkouMessage('');
  });
}

function wireNewButton() {
  var btn = document.getElementById('new-btn');
  if (!btn) return;
  btn.addEventListener('click', function() {
    _submitMethod = 'POST';
    var title = document.getElementById('form-title');
    if (title) title.textContent = 'Novo Som da Semana';
    var tituloEl = document.getElementById('featured-titulo');
    var generoEl = document.getElementById('featured-genero');
    var descricaoEl = document.getElementById('featured-descricao');
    if (tituloEl) tituloEl.value = '';
    if (generoEl) generoEl.value = '';
    if (descricaoEl) descricaoEl.value = '';
    clearLinkInputs();
    clearArtistasList();
    clearProdutoresList();
    showFormSection();
    yonkouMessage('');
  });
}

// ── Login form ────────────────────────────────────────────────────────────────

function wireLoginForm() {
  var form = document.getElementById('yonkou-login');
  if (!form) return;

  form.addEventListener('submit', function(event) {
    event.preventDefault();
    var password = document.getElementById('password').value;
    fetch('/yonkou/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password })
    }).then(function(response) {
      if (response.ok) {
        window.location.href = '/yonkou';
        return;
      }
      yonkouMessage('erro');
    });
  });
}

// ── Featured editor form ──────────────────────────────────────────────────────

function wireFeaturedEditor() {
  var form = document.getElementById('featured-editor');
  if (!form) return;

  form.addEventListener('submit', function(event) {
    event.preventDefault();
    try {
      var payload = {
        artistas: artistasFromForm(),
        produtores: produtoresFromForm(),
        titulo: document.getElementById('featured-titulo').value.trim(),
        genero: document.getElementById('featured-genero').value.trim(),
        descricao: document.getElementById('featured-descricao').value.trim(),
        links: featuredLinksFromForm()
      };

      var endpoint = _submitMethod === 'PATCH'
        ? '/yonkou/releases/current'
        : '/yonkou/releases';
      fetch(endpoint, {
        method: _submitMethod,
        headers: csrfHeaders(),
        body: JSON.stringify(payload)
      }).then(function(response) {
        if (response.ok) {
          window.location.reload();
          return;
        }
        return response.json().catch(function() { return {}; }).then(function(data) {
          yonkouMessage(data.error || data.detail || 'Nao foi possivel salvar.');
        });
      }).catch(function(err) {
        yonkouMessage('Erro de rede: ' + err.message);
      });
    } catch(err) {
      yonkouMessage('Erro ao preparar dados: ' + err.message);
    }
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  wireLoginForm();
  initArtistasList();
  wireArtistasList();
  initProdutoresList();
  wireProdutoresList();
  wireEditButton();
  wireNewButton();
  wireVoltarButton();
  wireLogoutButton();
  wireFeaturedEditor();
  wireSelectLabels();
});
