'use strict';

document.addEventListener('DOMContentLoaded', function () {
  var sobreSections      = ['section-projeto', 'section-aviso-legal', 'section-contato'];
  var privSections       = ['section-privacidade'];
  var participarSections = ['section-participar'];
  var allSections        = sobreSections.concat(privSections).concat(participarSections);

  var pageScroll = document.getElementById('page-scroll');
  var scrollHint = document.getElementById('scroll-hint');

  function updateScrollHint() {
    if (!scrollHint || !pageScroll) return;
    var atBottom = pageScroll.scrollTop + pageScroll.clientHeight >= pageScroll.scrollHeight - 4;
    scrollHint.hidden = atBottom;
  }

  if (pageScroll) {
    pageScroll.addEventListener('scroll', updateScrollHint);
  }

  function setSections(visible) {
    allSections.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.hidden = visible.indexOf(id) === -1;
    });
  }

  function sgNav(page) {
    var wrapper     = document.getElementById('wrapper');
    var pageContent = document.getElementById('page-content');

    if (page === 'home') {
      wrapper.hidden     = false;
      pageContent.hidden = true;
      document.documentElement.style.overflow = '';
      document.body.style.overflow            = '';
    } else {
      wrapper.hidden     = true;
      if (page === 'sobre')       setSections(sobreSections);
      if (page === 'privacidade') setSections(privSections);
      if (page === 'participar')  setSections(participarSections);
      pageContent.hidden = false;
      if (pageScroll) pageScroll.scrollTop = 0;
      document.documentElement.style.overflow = 'hidden';
      document.body.style.overflow            = 'hidden';
      window.setTimeout(updateScrollHint, 0);
    }
  }

  document.addEventListener('click', function (e) {
    var link = e.target;
    while (link && link.tagName !== 'A') link = link.parentNode;
    if (!link || !link.getAttribute('data-page')) return;
    e.preventDefault();
    sgNav(link.getAttribute('data-page'));
  });

  var copyBtn = document.getElementById('copy-template-btn');
  var status = document.getElementById('copy-template-status');
  var participarTemplate = [
    'Assunto: Som da Semana',
    '',
    'Nome do artista/grupo:',
    'Link do artista/grupo:',
    '',
    'Nome do produtor/beatmaker:',
    'Link do produtor/beatmaker:',
    '',
    'Titulo da faixa:',
    'Genero musical:',
    '',
    'Link do YouTube:',
    '',
    'Descricao da faixa/projeto:',
    '',
    'Links adicionais:',
    '1.',
    '2.',
    '3.',
    '4.'
  ].join('\n');

  function setCopyStatus(text) {
    if (!status) return;
    status.textContent = text;
    if (text) {
      window.setTimeout(function () {
        status.textContent = '';
      }, 1800);
    }
  }

  function fallbackCopy(text) {
    var temp = document.createElement('textarea');
    temp.value = text;
    temp.setAttribute('readonly', 'readonly');
    temp.style.position = 'fixed';
    temp.style.left = '-9999px';
    document.body.appendChild(temp);
    temp.focus();
    temp.select();
    var copied = false;
    try {
      copied = document.execCommand('copy');
    } catch (err) {
      copied = false;
    }
    document.body.removeChild(temp);
    return copied;
  }

  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      var text = participarTemplate;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          setCopyStatus('copiado');
        }).catch(function () {
          setCopyStatus(fallbackCopy(text) ? 'copiado' : 'erro');
        });
        return;
      }
      setCopyStatus(fallbackCopy(text) ? 'copiado' : 'erro');
    });
  }
});
