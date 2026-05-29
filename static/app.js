'use strict';

// =============================================================================
// Section 1: State variables
// =============================================================================

let state = 'IDLE';
let jobId = null;
let pollTimer = null;
let timeoutTimer = null;
let countdownTimer = null;
let isPolling = false;  // WR-03: flag de guarda contra chamadas concorrentes ao pollStatus
let currentMode = 'baixar'; // 'baixar' | 'analisar'

// =============================================================================
// Section 2: DOM refs
// =============================================================================

const $ = id => document.getElementById(id);

// =============================================================================
// Section 3: setState(newState, payload)
// Central dispatcher — calls the appropriate show*() function.
// =============================================================================

function setState(newState, payload = {}) {
  state = newState;
  switch (newState) {
    case 'IDLE':              showIdle(); break;
    case 'SUBMITTING':        showSubmitting(); break;
    case 'POLLING':           showPolling(payload.label || 'Processando...'); break;
    case 'DONE':              showDone(payload); break;
    case 'ERROR_VALIDATION':  showErrorValidation(payload.message || ''); break;
    case 'ERROR_RATE_LIMIT':  showErrorRateLimit(payload.retryAfter || 60); break;
    case 'ERROR_JOB':         showErrorJob(payload.message || 'Algo deu errado. Tente novamente.'); break;
    case 'ERROR_TIMEOUT':     showErrorTimeout(); break;
  }
}

// =============================================================================
// Section 4: API functions
// =============================================================================

function switchMode(mode) {
  currentMode = mode;
  setState('IDLE');
  $('mode-btn').textContent = mode === 'baixar' ? 'ANALISAR' : 'BAIXAR';
}

async function uploadFile(file) {
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (!['wav', 'mp3', 'flac', 'm4a'].includes(ext)) {
    setState('ERROR_VALIDATION', { message: 'Formato inválido. Use WAV, MP3, FLAC ou M4A.' });
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    setState('ERROR_VALIDATION', { message: 'Arquivo muito grande. Máximo 50 MB.' });
    return;
  }

  $('selected-file').textContent = file.name;
  clearAllTimers();
  setState('SUBMITTING');

  try {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch('/analyze', { method: 'POST', body: formData });

    if (response.status === 202) {
      const data = await response.json();
      if (!data.job_id) { setState('ERROR_JOB', { message: 'Algo deu errado. Tente novamente.' }); return; }
      setState('POLLING', { label: 'Processando...' });
      startPolling(data.job_id);
      return;
    }
    if (response.status === 413) { setState('ERROR_VALIDATION', { message: 'Arquivo muito grande. Máximo 50 MB.' }); return; }
    if (response.status === 422) {
      const data = await response.json();
      setState('ERROR_VALIDATION', { message: data.error || 'Formato inválido.' });
      return;
    }
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('retry-after') || '60', 10);
      setState('ERROR_RATE_LIMIT', { retryAfter });
      return;
    }
    setState('ERROR_JOB', { message: 'Algo deu errado. Tente novamente.' });
  } catch (err) {
    setState('ERROR_JOB', { message: 'Erro de conexão. Verifique sua internet e tente novamente.' });
  }
}

// clearAllTimers() — called at start of submitJob() to prevent ghost timers (Pitfall 4)
function clearAllTimers() {
  stopPolling();
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
}

async function submitJob(url) {
  // Clear ALL timers before anything else (Pitfall 4)
  clearAllTimers();

  try {
    const response = await fetch('/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ youtube_url: url })  // FIELD: youtube_url, NOT "url" (Pitfall 1)
    });

    if (response.status === 202) {
      const data = await response.json();
      if (!data.job_id) {
        // WR-04: resposta malformada sem job_id — evitar polling em /jobs/undefined
        setState('ERROR_JOB', { message: 'Algo deu errado. Tente novamente.' });
        return;
      }
      setState('POLLING', { label: 'Processando...' });
      startPolling(data.job_id);
      return;
    }

    if (response.status === 422) {
      const data = await response.json();
      let message;
      if (data.error_type === 'validation_error') {
        if (data.error && data.error.includes('YouTube')) {
          message = 'URL inválida. Use um link do YouTube (youtube.com ou youtu.be).';
        } else if (data.error && (data.error.includes('too long') || data.error.includes('15'))) {
          message = 'Vídeo com mais de 15 minutos. Escolha um vídeo mais curto.';
        } else {
          message = 'URL inválida. Verifique o link e tente novamente.';
        }
      } else {
        message = 'URL inválida. Verifique o link e tente novamente.';
      }
      setState('ERROR_VALIDATION', { message });
      return;
    }

    if (response.status === 429) {
      // Pitfall 6: parseInt with fallback in case header is null or filtered by proxy
      const retryAfter = parseInt(response.headers.get('retry-after') || '60', 10);
      setState('ERROR_RATE_LIMIT', { retryAfter });
      return;
    }

    // Unexpected HTTP status
    setState('ERROR_JOB', { message: 'Algo deu errado. Tente novamente.' });

  } catch (err) {
    // Pitfall 5: fetch() throws TypeError for network failures — not caught by response.ok check
    setState('ERROR_JOB', { message: 'Erro de conexão. Verifique sua internet e tente novamente.' });
  }
}

function startPolling(id) {
  jobId = id;
  pollTimer = setInterval(pollStatus, 2000);
  timeoutTimer = setTimeout(() => {
    stopPolling();
    setState('ERROR_TIMEOUT');
  }, 180 * 1000);
}

function stopPolling() {
  clearInterval(pollTimer);
  clearTimeout(timeoutTimer);
  pollTimer = null;
  timeoutTimer = null;
  isPolling = false;  // WR-03: resetar flag ao parar o polling
}

async function pollStatus() {
  if (isPolling) return;  // WR-03: prevenir chamada concorrente
  isPolling = true;
  try {
    const response = await fetch(`/jobs/${jobId}`);
    if (!response.ok) {
      stopPolling();
      setState('ERROR_JOB', { message: 'Erro ao consultar status do job.' });
      return;
    }
    const data = await response.json();
    const { status, stage } = data;

    if (status === 'done') {
      stopPolling();
      setState('DONE', data);
      return;
    }

    if (status === 'failed') {
      stopPolling();
      let message;
      if (data.error_type === 'download_error') {
        message = 'Não foi possível baixar o vídeo. O YouTube pode ter bloqueado o acesso. Tente novamente.';
      } else if (data.error_type === 'internal_error') {
        message = 'Erro interno. Tente novamente.';
      } else {
        message = 'Algo deu errado. Tente novamente.';
      }
      setState('ERROR_JOB', { message });
      return;
    }

    // queued / downloading / converting / analyzing — update progress label, continue polling
    setState('POLLING', { label: stageLabel(status, stage) });

  } catch (err) {
    stopPolling();
    setState('ERROR_JOB', { message: 'Erro de conexão. Verifique sua internet e tente novamente.' });
  } finally {
    isPolling = false;  // WR-03: sempre liberar a flag ao concluir
  }
}

// =============================================================================
// Section 5: UI updaters (one per state)
// =============================================================================

function showIdle() {
  $('url-input').classList.remove('sg-url-input--error');  // D-04: remove error highlight
  $('url-input').disabled = false;
  $('url-input').value = '';
  $('submit-btn').disabled = false;
  $('submit-btn').textContent = 'Baixar Beat';
  $('submit-btn').hidden = currentMode === 'analisar';
  $('form-area').hidden = currentMode === 'analisar';
  $('dropzone-area').hidden = currentMode === 'baixar';
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('error-area').hidden = true;
  $('validation-error').hidden = true;
  $('dropzone').classList.remove('sg-dropzone--active');
  $('selected-file').textContent = '';
}

function showSubmitting() {
  $('url-input').classList.remove('sg-url-input--error');  // D-04: remove error highlight
  $('url-input').disabled = true;
  $('submit-btn').disabled = true;
  $('submit-btn').textContent = 'Enviando...';
  $('submit-btn').hidden = currentMode === 'analisar';
  if (currentMode === 'analisar') {
    $('progress-area').hidden = false;
    $('progress-label').textContent = 'Enviando arquivo...';
  } else {
    $('progress-area').hidden = true;
  }
  $('result-card').hidden = true;
  $('error-area').hidden = true;
  $('validation-error').hidden = true;
}

function showPolling(label) {
  $('url-input').disabled = true;
  $('submit-btn').disabled = true;
  $('submit-btn').textContent = 'Processando...';
  $('submit-btn').hidden = false;
  $('progress-area').hidden = false;
  $('progress-label').textContent = label;
  $('result-card').hidden = true;
  $('error-area').hidden = true;
  $('validation-error').hidden = true;
}

function showDone(data) {
  $('form-area').hidden = currentMode === 'analisar';
  $('dropzone-area').hidden = currentMode === 'baixar';
  if (currentMode === 'baixar') {
    $('submit-btn').hidden = false;
    $('submit-btn').disabled = true;
    $('submit-btn').textContent = 'Concluído';
  } else {
    $('submit-btn').hidden = true;
  }
  $('progress-area').hidden = true;
  $('result-card').hidden = false;
  $('error-area').hidden = true;
  $('validation-error').hidden = true;

  // Populate result values using textContent — XSS mitigation (T-04-04)
  $('bpm-value').textContent = data.bpm ?? '';
  $('bpm-half-value').textContent = data.bpm_half ?? '';
  $('bpm-double-value').textContent = data.bpm_double ?? '';
  $('key-value').textContent = data.key ?? '';
  $('camelot-value').textContent = data.camelot ?? '';
  $('size-value').textContent = formatSizeMB(estimateSizeMB(data.duration_sec ?? 0));

  if (data.download_url) {
    const downloadHref = data.download_url.startsWith('/files/') ? data.download_url : '/files/' + jobId;
    $('download-link').href = downloadHref;
    $('download-area').hidden = false;
  } else {
    $('download-area').hidden = true;
  }
}

function showErrorValidation(msg) {
  if (currentMode === 'analisar') {
    $('error-area').hidden = false;
    $('retry-btn').hidden = true;
    $('error-message').textContent = msg;
    $('progress-area').hidden = true;
    $('result-card').hidden = true;
    $('validation-error').hidden = true;
    return;
  }
  // D-04: highlight input field visually
  $('url-input').classList.add('sg-url-input--error');
  $('url-input').disabled = false;
  $('submit-btn').disabled = false;
  $('submit-btn').textContent = 'Baixar Beat';
  $('submit-btn').hidden = false;
  $('validation-error').hidden = false;
  $('validation-error').textContent = msg;  // textContent — XSS mitigation (T-04-04)
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('error-area').hidden = true;
}

function showErrorRateLimit(retryAfter) {
  $('url-input').disabled = true;
  $('submit-btn').disabled = true;
  $('error-area').hidden = false;
  $('retry-btn').hidden = true;
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('validation-error').hidden = true;

  // Countdown: clear any existing countdownTimer first (Pitfall 4)
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }

  let remaining = retryAfter;

  function updateCountdown() {
    $('error-message').textContent = `Limite atingido. Tente novamente em ${remaining}s.`;
    $('submit-btn').textContent = `Tente novamente em ${remaining}s`;
  }

  updateCountdown();

  countdownTimer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(countdownTimer);
      countdownTimer = null;
      setState('IDLE');
    } else {
      updateCountdown();
    }
  }, 1000);
}

function showErrorJob(msg) {
  $('url-input').classList.remove('sg-url-input--error');  // remover highlight de validacao
  $('url-input').disabled = false;
  $('submit-btn').hidden = true;
  $('retry-btn').hidden = currentMode === 'analisar'; // no analyze mode, just drop a new file
  $('error-area').hidden = false;
  $('error-message').textContent = msg;  // textContent — XSS mitigation (T-04-04)
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('validation-error').hidden = true;
}

function showErrorTimeout() {
  $('url-input').disabled = false;
  $('submit-btn').disabled = false;
  $('submit-btn').textContent = 'Baixar Beat';
  $('submit-btn').hidden = currentMode === 'analisar';
  $('error-area').hidden = false;
  $('retry-btn').hidden = true;
  $('error-message').textContent = 'Processamento demorou mais que o esperado. Tente novamente.';
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('validation-error').hidden = true;
}

// =============================================================================
// Section 6: Helper functions
// =============================================================================

// D-08: WAV size estimate — 44100 Hz × 2 channels × 2 bytes (16-bit PCM)
function estimateSizeMB(durationSec) {
  return durationSec * 44100 * 2 * 2 / 1_000_000;
}

// D-08: Human-readable format with ~ prefix to indicate estimate
function formatSizeMB(mb) {
  if (mb >= 10) return `~${Math.round(mb)} MB`;
  return `~${mb.toFixed(1)} MB`;
}

function formatFeaturedDate(value) {
  if (!value) return '';
  const parts = String(value).split('-');
  if (parts.length !== 3) return String(value);
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

function clearFeaturedSidebar() {
  ensureFeaturedSidebar();
  const sidebar = $('featured-sidebar');
  const separator = $('featured-separator');
  if (sidebar) { sidebar.textContent = ''; sidebar.hidden = true; }
  if (separator) separator.hidden = true;
}

function ensureFeaturedSidebar() {
  const existing = $('featured-sidebar');
  if (existing) return existing;

  const wrapper = $('wrapper');
  const app = $('app');
  if (!wrapper || !app) return null;

  const shell = document.createElement('table');
  shell.id = 'featured-shell';
  shell.setAttribute('align', 'center');
  shell.setAttribute('cellpadding', '0');
  shell.setAttribute('cellspacing', '0');

  const row = document.createElement('tr');
  const appCell = document.createElement('td');
  appCell.id = 'featured-main-cell';
  appCell.setAttribute('valign', 'top');
  const sidebar = document.createElement('td');
  sidebar.id = 'featured-sidebar';
  sidebar.setAttribute('valign', 'top');

  const separator = document.createElement('td');
  separator.id = 'featured-separator';
  separator.setAttribute('valign', 'top');
  const sepImg = document.createElement('img');
  sepImg.src = '/static/bordas/borda7.png';
  sepImg.alt = '';
  separator.appendChild(sepImg);

  shell.appendChild(row);
  row.appendChild(appCell);
  row.appendChild(separator);
  row.appendChild(sidebar);
  wrapper.insertBefore(shell, app);
  appCell.appendChild(app);

  return sidebar;
}

function appendFeaturedField(card, label, value) {
  if (!value) return;

  const labelNode = document.createElement('div');
  labelNode.className = 'featured-field-label';
  labelNode.textContent = label;

  const valueNode = document.createElement('div');
  valueNode.className = 'featured-field-value';
  valueNode.textContent = value;

  card.appendChild(labelNode);
  card.appendChild(valueNode);
}

function safeHttpUrl(value) {
  try {
    const parsed = new URL(String(value || ''), window.location.origin);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return parsed.href;
  } catch (err) {
    return '';
  }
  return '';
}

function extractYoutubeId(url) {
  const m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

function renderFeatured(data) {
  if (!data || Object.keys(data).length === 0) {
    clearFeaturedSidebar();
    return;
  }

  const sidebar = ensureFeaturedSidebar();
  if (!sidebar) return;
  const separator = $('featured-separator');
  if (separator) separator.hidden = false;
  sidebar.hidden = false;
  sidebar.textContent = '';

  const card = document.createElement('div');
  card.id = 'featured-card';

  // kicker
  const kicker = document.createElement('div');
  kicker.id = 'featured-kicker';
  kicker.textContent = 'SOM DA SEMANA';
  card.appendChild(kicker);

  const titleBlock = document.createElement('div');
  titleBlock.id = 'featured-title-block';
  let titleLine = null;

  if (data.titulo) {
    titleLine = document.createElement('div');
    titleLine.id = 'featured-title-line';

    const tituloNode = document.createElement('span');
    tituloNode.id = 'featured-titulo';
    tituloNode.textContent = data.titulo;
    titleLine.appendChild(tituloNode);

    titleBlock.appendChild(titleLine);
  }

  const artistas = Array.isArray(data.artistas)
    ? data.artistas
    : (data.artista ? [{ nome: data.artista, url: '' }] : []);
  if (artistas.length > 0) {
    const artistRow = document.createElement('span');
    artistRow.id = 'featured-artist-row';
    artistRow.appendChild(document.createTextNode('de '));

    const artistNode = document.createElement('span');
    artistNode.id = 'featured-artist';
    artistas.forEach((a, i) => {
      if (i > 0) {
        const comma = (i === artistas.length - 1) ? ' & ' : ', ';
        artistNode.appendChild(document.createTextNode(comma));
      }
      if (a.url) {
        const safeUrl = safeHttpUrl(a.url);
        if (!safeUrl) {
          artistNode.appendChild(document.createTextNode(a.nome));
          return;
        }
        const anchor = document.createElement('a');
        anchor.href = safeUrl;
        anchor.target = '_blank';
        anchor.rel = 'noopener';
        anchor.textContent = a.nome;
        anchor.className = 'featured-artist-link';
        artistNode.appendChild(anchor);
      } else {
        artistNode.appendChild(document.createTextNode(a.nome));
      }
    });
    artistRow.appendChild(artistNode);
    if (!titleLine) {
      titleLine = document.createElement('div');
      titleLine.id = 'featured-title-line';
      titleBlock.appendChild(titleLine);
    }
    titleLine.appendChild(artistRow);
  }

  const produtores = Array.isArray(data.produtores) ? data.produtores.filter(p => p && p.nome) : [];
  if (produtores.length > 0) {
    const prodNode = document.createElement('div');
    prodNode.id = 'featured-prod';
    prodNode.appendChild(document.createTextNode('(prod. '));
    produtores.forEach((p, i) => {
      if (i > 0) prodNode.appendChild(document.createTextNode(i === produtores.length - 1 ? ' & ' : ', '));
      if (p.url) {
        const safeUrl = safeHttpUrl(p.url);
        if (!safeUrl) {
          prodNode.appendChild(document.createTextNode(p.nome));
          return;
        }
        const a = document.createElement('a');
        a.href = safeUrl;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = p.nome;
        a.className = 'featured-artist-link';
        prodNode.appendChild(a);
      } else {
        prodNode.appendChild(document.createTextNode(p.nome));
      }
    });
    prodNode.appendChild(document.createTextNode(')'));
    titleBlock.appendChild(prodNode);
  }

  card.appendChild(titleBlock);

  // player YouTube — entre artistas e gênero
  const ytLink = (data.links || []).find(l => l.label === 'Youtube');
  if (ytLink) {
    const videoId = extractYoutubeId(ytLink.url);
    if (videoId) {
      const playerWrap = document.createElement('div');
      playerWrap.id = 'featured-player';
      const iframe = document.createElement('iframe');
      iframe.src = `https://www.youtube.com/embed/${videoId}`;
      iframe.setAttribute('frameborder', '0');
      iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
      iframe.setAttribute('allowfullscreen', '');
      playerWrap.appendChild(iframe);
      card.appendChild(playerWrap);
    }
  }

  // divider
  const divider = document.createElement('div');
  divider.id = 'featured-divider';
  card.appendChild(divider);

  // genero tag
  if (data.genero) {
    const generoNode = document.createElement('div');
    generoNode.id = 'featured-genero';
    generoNode.textContent = data.genero;
    card.appendChild(generoNode);
  }

  // descricao
  if (data.descricao) {
    const descNode = document.createElement('div');
    descNode.id = 'featured-descricao';
    descNode.textContent = data.descricao;
    card.appendChild(descNode);
  }

  // data
  const dateNode = document.createElement('div');
  dateNode.className = 'featured-date';
  dateNode.textContent = formatFeaturedDate(data.data_adicao);
  card.appendChild(dateNode);

  const LINK_ICONS = {
    Youtube: `<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1C24 15.9 24 12 24 12s0-3.9-.5-5.8zM9.7 15.5v-7l6.3 3.5-6.3 3.5z"/></svg>`,
    Soundcloud: `<svg viewBox="0 0 24 16" width="18" height="12" fill="currentColor" aria-hidden="true"><path d="M1.5 10.3C.7 10.3 0 11 0 11.8s.7 1.5 1.5 1.5H20c2.2 0 4-1.8 4-4a4 4 0 0 0-3.3-3.9A6 6 0 0 0 15 1a6 6 0 0 0-2.6.6A7 7 0 0 0 1.5 10.3z"/></svg>`,
    Spotify: `<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.7 0 12 0zm5.5 17.3c-.2.4-.7.5-1 .2-2.8-1.7-6.4-2.1-10.6-1.1-.4.1-.8-.2-.9-.5-.1-.4.2-.8.6-.9 4.5-1 8.5-.6 11.6 1.3.3.2.5.6.3 1zm1.5-3.3c-.3.4-.8.6-1.3.3-3.2-2-8.2-2.6-11.9-1.4-.5.1-1-.1-1.1-.6-.1-.5.1-1 .6-1.1 4.2-1.3 9.6-.6 13.3 1.5.4.3.6.9.4 1.3zm.1-3.4C15.2 8.4 8.8 8.2 5.2 9.3c-.6.2-1.2-.2-1.4-.7-.2-.6.2-1.2.7-1.4 4.3-1.3 11.3-1 15.7 1.6.6.3.7 1 .4 1.5-.3.5-1 .6-1.5.3z"/></svg>`,
    Instagram: `<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M12 2.2c3.2 0 3.6 0 4.9.1 3.2.1 4.7 1.7 4.8 4.8.1 1.3.1 1.7.1 4.9s0 3.6-.1 4.9c-.1 3.1-1.6 4.7-4.8 4.8-1.3.1-1.7.1-4.9.1s-3.6 0-4.9-.1C3.9 21.6 2.4 20 2.3 16.9 2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.9C2.4 3.9 4 2.4 7.1 2.3 8.4 2.2 8.8 2.2 12 2.2zM12 0C8.7 0 8.3 0 7.1.1 2.7.3.3 2.7.1 7.1 0 8.3 0 8.7 0 12s0 3.7.1 4.9c.2 4.4 2.6 6.8 7 7C8.3 24 8.7 24 12 24s3.7 0 4.9-.1c4.4-.2 6.8-2.6 7-7 .1-1.2.1-1.6.1-4.9s0-3.7-.1-4.9c-.2-4.4-2.6-6.8-7-7C15.7 0 15.3 0 12 0zm0 5.8a6.2 6.2 0 1 0 0 12.4A6.2 6.2 0 0 0 12 5.8zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.4-11.8a1.44 1.44 0 1 0 0 2.88 1.44 1.44 0 0 0 0-2.88z"/></svg>`,
    Outros: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 3 21 3 21 9"/><path d="M10 14L21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>`,
  };

  const links = Array.isArray(data.links) ? data.links.slice(0, 4) : [];
  if (links.some(item => item && item.label && item.url)) {
    const linksRow = document.createElement('div');
    linksRow.className = 'featured-links-row';
    links.forEach(item => {
      if (!item || !item.label || !item.url) return;
      const link = document.createElement('a');
      const safeUrl = safeHttpUrl(item.url);
      if (!safeUrl) return;
      link.className = 'featured-link';
      link.href = safeUrl;
      link.target = '_blank';
      link.rel = 'noopener';

      const iconKey = Object.keys(LINK_ICONS).find(k => k.toLowerCase() === item.label.toLowerCase()) || 'Outros';
      const iconWrap = document.createElement('span');
      iconWrap.className = 'featured-link-icon';
      iconWrap.textContent = iconKey === 'Outros' ? '↗' : item.label.charAt(0).toUpperCase();
      link.appendChild(iconWrap);
      link.appendChild(document.createTextNode(item.label));

      linksRow.appendChild(link);
    });
    card.appendChild(linksRow);
  }

  sidebar.appendChild(card);
}

async function loadFeatured() {
  try {
    const response = await fetch('/featured');
    if (response.status === 204) {
      clearFeaturedSidebar();
      return;
    }
    if (!response.ok) return;
    const data = await response.json();
    renderFeatured(data);
  } catch (err) {
    clearFeaturedSidebar();
  }
}

function renderLatestUpdate(entries) {
  const shell = $('updates-teaser-shell');
  if (!shell) return;
  if (!Array.isArray(entries) || entries.length === 0) {
    shell.hidden = true;
    return;
  }
  const latest = entries[0];
  $('updates-teaser-title').textContent = latest.titulo || '';
  $('updates-teaser-summary').textContent = latest.resumo || '';
  shell.hidden = false;
}

async function loadLatestUpdate() {
  try {
    const response = await fetch('/updates?limit=1');
    if (response.status === 204) {
      renderLatestUpdate([]);
      return;
    }
    if (!response.ok) return;
    const data = await response.json();
    renderLatestUpdate(data);
  } catch (err) {
    renderLatestUpdate([]);
  }
}

// Stage labels per UI-SPEC.md Copywriting Contract (Progress Stage Labels)
function stageLabel(status, stage) {
  if (status === 'queued') return 'Na fila...';
  if (status === 'downloading') {
    if (stage === 'checking_duration') return 'Verificando duração...';
    if (stage === 'downloading') return 'Baixando áudio...';
    return 'Baixando...';
  }
  if (status === 'converting') return 'Convertendo para WAV...';
  if (status === 'analyzing') return 'Analisando BPM e tonalidade...';
  return 'Processando...';
}

// =============================================================================
// Section 7: Event listeners and init
// =============================================================================

function init() {
  loadFeatured();
  loadLatestUpdate();

  // Wire submit button
  $('submit-btn').addEventListener('click', () => {
    const url = $('url-input').value.trim();
    if (!url) return;
    setState('SUBMITTING');
    submitJob(url);
  });

  // Wire clear button — reset to IDLE
  $('clear-btn').addEventListener('click', () => {
    setState('IDLE');
  });

  // Wire retry button (ERROR_JOB state — D-06: reuse URL already in field, resubmit directly)
  $('retry-btn').addEventListener('click', () => {
    const url = $('url-input').value.trim();
    if (!url) return;
    setState('SUBMITTING');
    submitJob(url);
  });

  // Enter key on input field triggers submit
  $('url-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') $('submit-btn').click();
  });

  // Mode toggle button
  $('mode-btn').addEventListener('click', () => {
    switchMode(currentMode === 'baixar' ? 'analisar' : 'baixar');
  });

  // Dropzone click → file picker
  $('dropzone').addEventListener('click', () => $('file-input').click());

  // Drag & drop
  $('dropzone').addEventListener('dragover', (e) => {
    e.preventDefault();
    $('dropzone').classList.add('sg-dropzone--active');
  });
  $('dropzone').addEventListener('dragleave', () => {
    $('dropzone').classList.remove('sg-dropzone--active');
  });
  $('dropzone').addEventListener('drop', (e) => {
    e.preventDefault();
    $('dropzone').classList.remove('sg-dropzone--active');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  // File input change
  $('file-input').addEventListener('change', () => {
    const file = $('file-input').files[0];
    if (file) uploadFile(file);
    $('file-input').value = '';  // reset so same file can be re-selected
  });
}

document.addEventListener('DOMContentLoaded', init);
