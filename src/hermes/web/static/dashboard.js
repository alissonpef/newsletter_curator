function readInitialState() {
  const node = document.getElementById('initial-state');
  const payloadB64 = node?.getAttribute('data-payload-b64') || '';
  if (!payloadB64) {
    throw new Error('Estado inicial da dashboard nao encontrado.');
  }

  let decoded = '';
  try {
    const binary = window.atob(payloadB64);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    decoded = new TextDecoder('utf-8').decode(bytes);
  } catch (error) {
    throw new Error('Falha ao decodificar estado inicial.');
  }

  const parsed = JSON.parse(decoded);
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Estado inicial invalido.');
  }
  return parsed;
}

const initialState = readInitialState();

const state = {
  overview: initialState,
  selectedEntry: initialState.selectedEntry,
  selectedJob: initialState.selectedJob,
  pollingId: null,
};

const filters = [7, 14, 30];

function $(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

const STATUS_BADGE_VARIANTS = Object.freeze({
  ready: 'ready',
  succeeded: 'ready',
  failed: 'failed',
  running: 'running',
  queued: 'running',
  partial: 'partial',
  missing: 'missing',
});

function resolveStatusBadgeVariant(status) {
  return STATUS_BADGE_VARIANTS[status] || 'missing';
}

function statusClass(status) {
  return `status-pill status-${resolveStatusBadgeVariant(status)}`;
}

function updateUrl() {
  const params = new URLSearchParams();
  params.set('days', String(state.overview.daysBack));
  if (state.selectedEntry?.dateRef) {
    params.set('date', state.selectedEntry.dateRef);
  }
  window.history.replaceState({}, '', `/?${params.toString()}`);
}

function renderFilters() {
  $('days-filter').innerHTML = filters
    .map((days) => {
      const active = days === state.overview.daysBack ? 'active' : '';
      return `<button class="filter-chip ${active}" data-days="${days}" type="button">Últimos ${days} dias</button>`;
    })
    .join('');

  document.querySelectorAll('[data-days]').forEach((button) => {
    button.addEventListener('click', () => refreshOverview(Number(button.dataset.days), state.selectedEntry?.dateRef));
  });
}

function renderStats() {
  const stats = state.overview.stats;
  const cards = [
    ['Dias prontos', stats.readyDays],
    ['Em processamento', stats.runningDays],
    ['Parciais', stats.partialDays],
    ['Falhas', stats.failedDays],
    ['Nao gerados', stats.missingDays],
    ['PDFs no recorte', stats.totalPdfs],
    ['Podcasts no recorte', stats.totalAudios],
    ['Dias avaliados', stats.totalDays],
  ];

  $('stats-grid').innerHTML = cards
    .map(([label, value]) => `
      <article class="stat-card">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </article>
    `)
    .join('');
}

function renderDays() {
  $('days-grid').innerHTML = state.overview.entries
    .map((entry) => {
      const active = entry.dateRef === state.selectedEntry?.dateRef ? 'active' : '';
      return `
        <article class="day-card ${active}" data-date="${entry.dateRef}">
          <div class="media-card-header">
            <div>
              <h3>${escapeHtml(entry.dateLabel)}</h3>
            </div>
            <span class="${statusClass(entry.status)}">${escapeHtml(entry.statusLabel)}</span>
          </div>
          <p>${escapeHtml(entry.summary)}</p>
          <div class="day-card-meta">
            <span>${entry.pdfCount} PDF</span>
            <span>${entry.audioCount} áudio</span>
          </div>
        </article>
      `;
    })
    .join('');

  document.querySelectorAll('[data-date]').forEach((card) => {
    card.addEventListener('click', () => selectDate(card.dataset.date, true));
  });
}

function renderJobBanner() {
  const banner = $('job-banner');
  const job = state.selectedJob;
  if (!job) {
    banner.hidden = true;
    banner.innerHTML = '';
    return;
  }

  const parts = [job.statusLabel];
  if (job.message) {
    parts.push(job.message);
  }
  if (job.error) {
    parts.push(job.error);
  }
  banner.hidden = false;
  banner.className = `job-banner status-${job.status}`;
  banner.textContent = parts.join(' • ');
}

function renderArtifacts(entry) {
  const pdfCards = entry.pdfArtifacts.map((artifact) => `
    <article class="media-card">
      <div class="media-card-header">
        <div>
          <strong>${escapeHtml(artifact.filename)}</strong>
          <small>${escapeHtml(artifact.modifiedAtLabel)} • ${escapeHtml(artifact.sizeLabel)}</small>
        </div>
        <span class="${statusClass('ready')}">PDF</span>
      </div>
      <div class="media-actions">
        <a class="inline-link" href="${artifact.url}">Baixar PDF</a>
        <a class="inline-link" href="${artifact.url}" target="_blank" rel="noreferrer">Abrir em nova aba</a>
      </div>
    </article>
  `).join('');

  const audioCards = entry.audioArtifacts.map((artifact, index) => `
    <article class="media-card">
      <div class="media-card-header">
        <div>
          <strong>${escapeHtml(artifact.filename)}</strong>
          <small>${escapeHtml(artifact.modifiedAtLabel)} • ${escapeHtml(artifact.sizeLabel)}</small>
        </div>
        <span class="${statusClass('ready')}">Podcast</span>
      </div>
      <div class="media-actions">
        <a class="inline-link" href="${artifact.url}">Baixar áudio</a>
      </div>
      ${index === 0 ? `<audio class="audio-player" controls preload="metadata" src="${artifact.url}"></audio>` : ''}
    </article>
  `).join('');

  if (!pdfCards && !audioCards) {
    $('artifact-section').innerHTML = `
      <div class="empty-state">
        <strong>Nenhum artefato encontrado</strong>
        <small>Use o botao de geracao para buscar os e-mails dessa data e produzir o PDF e o podcast.</small>
      </div>
    `;
    $('player-section').innerHTML = '';
    return;
  }

  $('artifact-section').innerHTML = `
    <div class="artifact-list">${pdfCards}${audioCards}</div>
  `;

  const firstAudio = entry.audioArtifacts[0];
  $('player-section').innerHTML = firstAudio ? `
    <div class="detail-card">
      <div class="media-card-header">
        <div>
          <strong>Player do podcast</strong>
          <small>Escute o audio principal sem sair da dashboard.</small>
        </div>
      </div>
      <audio class="audio-player" controls preload="metadata" src="${firstAudio.url}"></audio>
    </div>
  ` : '';
}

function renderHistory(entry) {
  if (!entry.runHistory.length) {
    $('history-section').innerHTML = `
      <div class="empty-state">
        <strong>Sem histórico persistido</strong>
        <small>Quando houver execuções registradas, checkpoints e erros mais recentes vão aparecer aqui.</small>
      </div>
    `;
    return;
  }

  $('history-section').innerHTML = `
    <div class="history-list">
      ${entry.runHistory.map((run) => `
        <article class="timeline-item">
          <div class="timeline-head">
            <div>
              <strong>${escapeHtml(run.statusLabel)}</strong>
              <small>${escapeHtml(run.startedAtLabel || '-')}</small>
            </div>
            <span class="${statusClass(run.status)}">${escapeHtml(run.checkpointLabel)}</span>
          </div>
          <small>Run ID: ${escapeHtml(run.runId)}</small>
          ${run.finishedAtLabel ? `<small>Finalizado em ${escapeHtml(run.finishedAtLabel)}</small>` : ''}
          ${run.error ? `<small>${escapeHtml(run.error)}</small>` : ''}
        </article>
      `).join('')}
    </div>
  `;
}

function renderDetail() {
  const entry = state.selectedEntry;
  $('detail-title').textContent = entry?.dateLabel || 'Selecione um dia';
  $('detail-summary').textContent = entry?.summary || 'Escolha uma data para ver PDFs, podcasts e histórico da execução.';
  $('detail-status').className = statusClass(entry?.status || 'missing');
  $('detail-status').textContent = entry?.statusLabel || 'Sem status';
  renderArtifacts(entry);
  renderHistory(entry);
}

function renderMeta() {
  $('window-value').textContent = `${state.overview.daysBack} dias monitorados`;
  $('generated-at').textContent = `Atualizado em ${state.overview.generatedAtLabel}`;
  $('date-picker').value = state.selectedEntry?.dateRef || state.overview.selectedDate;
}

function renderAll() {
  renderFilters();
  renderStats();
  renderDays();
  renderJobBanner();
  renderDetail();
  renderMeta();
  updateUrl();
  updatePolling();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || 'Falha na comunicação com o servidor.');
  }
  return payload;
}

async function refreshOverview(daysBack = state.overview.daysBack, selectedDate = state.selectedEntry?.dateRef) {
  const params = new URLSearchParams({ days: String(daysBack) });
  if (selectedDate) {
    params.set('date', selectedDate);
  }
  const payload = await fetchJson(`/api/overview?${params.toString()}`);
  state.overview = payload;
  state.selectedEntry = payload.selectedEntry;
  state.selectedJob = payload.selectedJob;
  renderAll();
}

async function selectDate(dateRef, refreshFromServer = false) {
  const localEntry = state.overview.entries.find((entry) => entry.dateRef === dateRef);
  if (localEntry) {
    state.selectedEntry = localEntry;
    state.selectedJob = state.selectedEntry.dateRef === state.selectedJob?.dateRef ? state.selectedJob : null;
    renderAll();
  }
  if (!refreshFromServer) {
    return;
  }
  const payload = await fetchJson(`/api/days/${dateRef}`);
  state.selectedEntry = payload.entry;
  state.selectedJob = payload.job;
  renderAll();
}

async function triggerGeneration(force = false) {
  const dateRef = $('date-picker').value || state.selectedEntry?.dateRef;
  if (!dateRef) {
    window.alert('Escolha uma data antes de iniciar a geração.');
    return;
  }

  $('generate-button').disabled = true;
  $('force-button').disabled = true;
  try {
    const payload = await fetchJson('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date_ref: dateRef, force }),
    });
    state.selectedEntry = payload.entry;
    state.selectedJob = payload.job;
    await refreshOverview(state.overview.daysBack, dateRef);
  } catch (error) {
    window.alert(error.message);
  } finally {
    $('generate-button').disabled = false;
    $('force-button').disabled = false;
  }
}

function updatePolling() {
  if (state.pollingId) {
    window.clearInterval(state.pollingId);
    state.pollingId = null;
  }
  if (!state.selectedJob || !['queued', 'running'].includes(state.selectedJob.status)) {
    return;
  }
  state.pollingId = window.setInterval(async () => {
    try {
      await refreshOverview(state.overview.daysBack, state.selectedEntry?.dateRef);
    } catch (error) {
      console.error(error);
    }
  }, 5000);
}

function bindEvents() {
  $('inspect-button').addEventListener('click', () => {
    const dateRef = $('date-picker').value;
    if (!dateRef) {
      window.alert('Escolha uma data para consultar.');
      return;
    }
    selectDate(dateRef, true).catch((error) => window.alert(error.message));
  });
  $('generate-button').addEventListener('click', () => triggerGeneration(false));
  $('force-button').addEventListener('click', () => triggerGeneration(true));
  $('date-picker').addEventListener('change', (event) => {
    const value = event.target.value;
    if (value) {
      state.selectedEntry = { ...state.selectedEntry, dateRef: value, dateLabel: value };
      updateUrl();
    }
  });
}

bindEvents();
renderAll();
