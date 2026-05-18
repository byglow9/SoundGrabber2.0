'use strict';

document.addEventListener('DOMContentLoaded', function () {
  var sobreSections    = ['section-projeto', 'section-aviso-legal', 'section-contato'];
  var privSections     = ['section-privacidade'];
  var allSections      = sobreSections.concat(privSections);

  function setSections(visible) {
    allSections.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.hidden = visible.indexOf(id) === -1;
    });
  }

  function sgNav(page) {
    var wrapper     = document.getElementById('wrapper');
    var pageContent = document.getElementById('page-content');
    var sidebar     = document.getElementById('featured-sidebar');
    var sep         = document.getElementById('featured-separator');

    if (page === 'home') {
      wrapper.hidden     = false;
      pageContent.hidden = true;
      document.documentElement.style.overflow = '';
      document.body.style.overflow            = '';
      if (sidebar) sidebar.hidden = false;
      if (sep)     sep.hidden     = false;
    } else {
      wrapper.hidden     = true;
      if (sidebar) sidebar.hidden = true;
      if (sep)     sep.hidden     = true;
      if (page === 'sobre')       setSections(sobreSections);
      if (page === 'privacidade') setSections(privSections);
      pageContent.hidden = false;
      pageContent.scrollTop = 0;
      document.documentElement.style.overflow = 'hidden';
      document.body.style.overflow            = 'hidden';
    }
  }

  document.addEventListener('click', function (e) {
    var link = e.target;
    while (link && link.tagName !== 'A') link = link.parentNode;
    if (!link || !link.getAttribute('data-page')) return;
    e.preventDefault();
    sgNav(link.getAttribute('data-page'));
  });
});
