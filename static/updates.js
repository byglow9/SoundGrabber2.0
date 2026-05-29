'use strict';

function updateDate(value) {
  if (!value) return '';
  var parts = String(value).split('-');
  if (parts.length !== 3) return String(value);
  return parts[2] + '/' + parts[1] + '/' + parts[0];
}

function renderUpdateItem(entry) {
  var item = document.createElement('div');
  item.className = 'system-update-item';

  var meta = document.createElement('div');
  meta.className = 'system-update-meta';
  meta.textContent = updateDate(entry.data_publicacao) + ' / ' + (entry.categoria || 'sistema');
  item.appendChild(meta);

  var title = document.createElement('h2');
  title.textContent = entry.titulo || '';
  item.appendChild(title);

  var summary = document.createElement('p');
  summary.textContent = entry.resumo || '';
  item.appendChild(summary);

  var bullets = Array.isArray(entry.bullets) ? entry.bullets : [];
  if (bullets.length > 0) {
    var list = document.createElement('ul');
    bullets.forEach(function(text) {
      var li = document.createElement('li');
      li.textContent = text;
      list.appendChild(li);
    });
    item.appendChild(list);
  }

  return item;
}

function renderUpdates(entries) {
  var list = document.getElementById('updates-list');
  if (!list) return;
  list.textContent = '';

  if (!entries || entries.length === 0) {
    var empty = document.createElement('div');
    empty.id = 'updates-empty';
    empty.textContent = 'Nenhuma atualização publicada ainda.';
    list.appendChild(empty);
    return;
  }

  entries.forEach(function(entry) {
    list.appendChild(renderUpdateItem(entry));
  });
}

function loadUpdates() {
  fetch('/updates?limit=50').then(function(response) {
    if (response.status === 204) {
      renderUpdates([]);
      return null;
    }
    if (!response.ok) throw new Error('updates unavailable');
    return response.json();
  }).then(function(data) {
    if (data) renderUpdates(Array.isArray(data) ? data : []);
  }).catch(function() {
    renderUpdates([]);
  });
}

document.addEventListener('DOMContentLoaded', loadUpdates);
