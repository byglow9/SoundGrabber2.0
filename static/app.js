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
  $('submit-btn').disabled = false;
  $('submit-btn').textContent = 'Baixar Beat';
  $('submit-btn').hidden = false;
  $('progress-area').hidden = true;
  $('result-card').hidden = true;
  $('error-area').hidden = true;
  $('validation-error').hidden = true;
}

function showSubmitting() {
  $('url-input').classList.remove('sg-url-input--error');  // D-04: remove error highlight
  $('url-input').disabled = true;
  $('submit-btn').disabled = true;
  $('submit-btn').textContent = 'Enviando...';
  $('submit-btn').hidden = false;
  // Ocultar todas as areas de conteudo durante o envio
  $('progress-area').hidden = true;
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
  $('url-input').disabled = false;
  $('submit-btn').disabled = false;
  $('submit-btn').textContent = 'Baixar Beat';
  $('submit-btn').hidden = false;
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

  // Set download link href with open redirect defense (T-04-05, RESEARCH.md security domain)
  // Verify download_url starts with '/files/' before using it; fallback to local construction
  const downloadHref = (data.download_url && data.download_url.startsWith('/files/'))
    ? data.download_url
    : '/files/' + jobId;
  $('download-link').href = downloadHref;
}

function showErrorValidation(msg) {
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
  $('retry-btn').hidden = false;
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
  $('submit-btn').hidden = false;
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
  // Wire submit button
  $('submit-btn').addEventListener('click', () => {
    const url = $('url-input').value.trim();
    if (!url) return;
    setState('SUBMITTING');
    submitJob(url);
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
}

document.addEventListener('DOMContentLoaded', init);
