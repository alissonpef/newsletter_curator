function $(id) {
  return document.getElementById(id);
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function readInitialState() {
  return window.__HERMES_STATE__ || {
    entries: [],
    calendarWeeks: [],
    selectedEntry: null,
    selectedJob: null,
    daysBack: 28,
    generatedAtLabel: "-",
    kindle: { configured: false, defaultEmail: "" },
    stats: { ready: 0, running: 0, pending: 0 },
  };
}

const initialState = readInitialState();

const PIPELINE_STEPS = [
  { key: "queued", label: "Fila" },
  { key: "bootstrap", label: "Preparação" },
  { key: "ingest", label: "Coleta" },
  { key: "synthesis", label: "Síntese" },
  { key: "market", label: "Mercado" },
  { key: "pdf", label: "PDF" },
  { key: "audio", label: "Áudio" },
  { key: "done", label: "Pronto" },
];

const STATUS_VARIANTS = {
  ready: "ready",
  succeeded: "ready",
  running: "running",
  queued: "running",
  failed: "failed",
  missing: "missing",
  idle: "missing",
};

const state = {
  overview: initialState,
  selectedEntry: initialState.selectedEntry,
  selectedJob: initialState.selectedJob,
  pollingId: null,
  flash: null,
  kindleSending: false,
};

function statusVariant(status) {
  return STATUS_VARIANTS[status] || "missing";
}

function setFlash(type, message) {
  state.flash = { type, message };
  renderHero();
  window.clearTimeout(setFlash.timeoutId);
  setFlash.timeoutId = window.setTimeout(() => {
    state.flash = null;
    renderHero();
  }, 5000);
}

function selectedDigest() {
  return state.selectedEntry || state.overview.selectedEntry;
}

function selectedSummaryData() {
  return selectedDigest()?.summaryData || null;
}

function renderCalendar() {
  const container = $("calendar-weeks");
  const stats = $("calendar-stats");
  if (!container || !stats) return;

  stats.innerHTML = `
    <span><strong>${state.overview.stats.ready}</strong> prontas</span>
    <span><strong>${state.overview.stats.pending}</strong> pendentes</span>
  `;

  container.innerHTML = (state.overview.calendarWeeks || []).map((week) => `
    <section class="week-block">
      <header>
        <span class="week-label">${esc(week.label)}</span>
      </header>
      <div class="week-days">
        ${week.days.map((entry) => `
          <button
            type="button"
            class="day-chip ${entry.dateRef === selectedDigest()?.dateRef ? "active" : ""} ${statusVariant(entry.status)}"
            data-date="${entry.dateRef}"
          >
            <span class="day-chip-top">
              <span>${esc(entry.shortWeekday)}</span>
              <span class="status-dot ${statusVariant(entry.status)}"></span>
            </span>
            <strong>${esc(entry.dayNumber)}</strong>
            <small>${entry.hasContent ? "Processado" : "Pendente"}</small>
          </button>
        `).join("")}
      </div>
    </section>
  `).join("");

  container.querySelectorAll("[data-date]").forEach((element) => {
    element.addEventListener("click", () => {
      selectDate(element.dataset.date, true).catch((error) => window.alert(error.message));
    });
  });
}

function renderHero() {
  const hero = $("hero-strip");
  const entry = selectedDigest();
  const job = state.selectedJob;
  if (!hero) return;

  if (!entry) {
    hero.innerHTML = `
      <article class="card hero-card">
        <p class="eyebrow">Seleção</p>
        <h2>Escolha uma data para abrir um digest.</h2>
      </article>
    `;
    return;
  }

  const summaryData = entry.summaryData || {};
  const sourceCount = summaryData.sourceCount || entry.sourceCount || 0;
  const warningHtml = (entry.warnings || []).length
    ? `<div class="inline-alert warning">${entry.warnings.map((warning) => esc(warning)).join(" · ")}</div>`
    : "";
  const flashHtml = state.flash
    ? `<div class="inline-alert ${esc(state.flash.type)}">${esc(state.flash.message)}</div>`
    : "";

  hero.innerHTML = `
    <article class="card hero-card">
      <div class="hero-main">
        <div>
          <p class="eyebrow">${esc(entry.dateLabel)}</p>
          <h2>${esc(entry.fullDateLabel)}</h2>
          <p class="hero-summary">${esc(summaryData.thesis || entry.summary || "Nenhuma síntese gerada para esta data.")}</p>
        </div>
        <span class="status-badge ${statusVariant(entry.status)}">${esc(entry.statusLabel)}</span>
      </div>
      <div class="hero-metrics">
        <div class="metric-box">
          <span>Fontes</span>
          <strong>${esc(sourceCount || "-")}</strong>
        </div>
        <div class="metric-box">
          <span>PDF</span>
          <strong>${entry.pdfCount || 0}</strong>
        </div>
        <div class="metric-box">
          <span>Áudio</span>
          <strong>${entry.audioCount || 0}</strong>
        </div>
      </div>
      ${flashHtml}
      ${warningHtml}
      ${job && ["queued", "running"].includes(job.status) ? `
        <div class="inline-alert info">
          ${esc(job.currentStepLabel || job.statusLabel)} · ${esc(job.message || "Processando...")}
        </div>
      ` : ""}
    </article>
  `;
}

function renderDigest() {
  const container = $("digest-content");
  const entry = selectedDigest();
  const summaryData = selectedSummaryData();
  const job = state.selectedJob;
  if (!container) return;

  if (!entry) {
    container.innerHTML = "";
    return;
  }

  if (!entry.hasContent && job && ["queued", "running"].includes(job.status)) {
    container.innerHTML = `
      <article class="card empty-card">
        <p class="eyebrow">Em progresso</p>
        <h3>${esc(job.currentStepLabel || "Preparando o digest")}</h3>
        <p>${esc(job.message || "A execução está em andamento.")}</p>
      </article>
    `;
    return;
  }

  if (!entry.hasContent) {
    container.innerHTML = `
      <article class="card empty-card">
        <p class="eyebrow">${esc(entry.dateLabel)}</p>
        <h3>Sem digest disponível</h3>
        <p>${entry.status === "failed" ? "A última tentativa falhou. Você pode regenerar esta edição." : "Ainda não existe conteúdo consolidado para esta data."}</p>
      </article>
      ${renderHistory(entry)}
    `;
    return;
  }

  const keyPoints = (summaryData?.keyPoints || []).map((item) => `
    <li>${esc(item)}</li>
  `).join("");

  const topics = (summaryData?.topics || []).map((topic) => `
    <article class="topic-card">
      <div class="topic-head">
        <h4>${esc(topic.title)}</h4>
        <span class="signal-pill ${signalVariant(topic.signal)}">${esc(topic.signal)}</span>
      </div>
      <p>${esc(topic.summary)}</p>
      <div class="topic-impact">
        <strong>Impacto</strong>
        <span>${esc(topic.impact)}</span>
      </div>
    </article>
  `).join("");

  const sections = [];

  sections.push(`
    <article class="card prose-card">
      <div class="section-head">
        <p class="eyebrow">Panorama</p>
        <h3>Resumo executivo</h3>
      </div>
      <p class="lead-copy">${esc(summaryData?.executiveSummary || entry.summary || "")}</p>
      ${summaryData?.closing ? `<div class="closing-note"><strong>Fechamento</strong><p>${esc(summaryData.closing)}</p></div>` : ""}
    </article>
  `);

  if (keyPoints) {
    sections.push(`
      <article class="card">
        <div class="section-head">
          <p class="eyebrow">Ação</p>
          <h3>Leituras prioritárias</h3>
        </div>
        <ul class="key-list">${keyPoints}</ul>
      </article>
    `);
  }

  if (topics) {
    sections.push(`
      <article class="card topics-wrap">
        <div class="section-head">
          <p class="eyebrow">Mapa do dia</p>
          <h3>Temas em foco</h3>
        </div>
        <div class="topic-grid">${topics}</div>
      </article>
    `);
  }

  sections.push(renderHistory(entry));
  container.innerHTML = sections.join("");
}

function renderHistory(entry) {
  const history = entry?.runHistory || [];
  if (!history.length) {
    return "";
  }
  return `
    <article class="card">
      <div class="section-head">
        <p class="eyebrow">Rastro</p>
        <h3>Histórico de execução</h3>
      </div>
      <div class="timeline">
        ${history.map((item) => `
          <div class="timeline-row">
            <span class="status-badge ${statusVariant(item.status)}">${esc(item.statusLabel)}</span>
            <div>
              <strong>${esc(item.checkpointLabel)}</strong>
              <small>${esc(item.startedAtLabel || "-")}</small>
            </div>
          </div>
        `).join("")}
      </div>
    </article>
  `;
}

function renderMarket() {
  const container = $("market-radar");
  const entry = selectedDigest();
  if (!container) return;

  const marketData = entry?.marketData || {};
  const items = Object.entries(marketData);
  if (!items.length) {
    container.innerHTML = `<div class="empty-block">Os indicadores de mercado aparecem depois da geração.</div>`;
    return;
  }

  container.innerHTML = items.map(([name, payload]) => {
    const normalized = typeof payload === "string"
      ? { display: payload, direction: payload.includes("+") ? "up" : (payload.includes("-") ? "down" : "flat") }
      : payload;
    return `
      <div class="market-row">
        <div>
          <strong>${esc(name)}</strong>
          ${normalized.value ? `<small>${esc(normalized.value)}</small>` : ""}
        </div>
        <span class="market-value ${normalized.direction || "flat"}">${esc(normalized.changePct || normalized.display || "")}</span>
      </div>
    `;
  }).join("");
}

function renderMedia() {
  const entry = selectedDigest();
  const playerPanel = $("player-panel");
  const downloadsPanel = $("downloads-panel");
  const audioPlayer = $("audio-player");
  const downloadLinks = $("download-links");

  if (!entry) {
    playerPanel.hidden = true;
    downloadsPanel.hidden = true;
    return;
  }

  const firstAudio = entry.audioArtifacts?.[0];
  if (firstAudio) {
    playerPanel.hidden = false;
    audioPlayer.src = firstAudio.url;
  } else {
    playerPanel.hidden = true;
    audioPlayer.removeAttribute("src");
    audioPlayer.load();
  }

  const links = [];
  for (const pdf of (entry.pdfArtifacts || [])) {
    links.push(`<a class="download-link" href="${pdf.url}" target="_blank" rel="noreferrer">Abrir PDF · ${esc(pdf.sizeLabel)}</a>`);
  }
  for (const audio of (entry.audioArtifacts || [])) {
    links.push(`<a class="download-link" href="${audio.url}" target="_blank" rel="noreferrer">Baixar áudio · ${esc(audio.sizeLabel)}</a>`);
  }

  if (links.length) {
    downloadsPanel.hidden = false;
    downloadLinks.innerHTML = links.join("");
  } else {
    downloadsPanel.hidden = true;
    downloadLinks.innerHTML = "";
  }
}

function renderJobBanner() {
  const banner = $("job-banner");
  const progressWrap = $("job-progress");
  const job = state.selectedJob;
  if (!banner || !progressWrap) return;

  if (!job) {
    banner.className = "job-banner";
    banner.textContent = "";
    progressWrap.innerHTML = "";
    return;
  }

  const extra = [];
  if (job.message) extra.push(job.message);
  if (job.error) extra.push(job.error);
  if (job.warnings?.length) extra.push(job.warnings.join(" · "));

  banner.className = `job-banner visible ${statusVariant(job.status)}`;
  banner.textContent = [job.statusLabel, ...extra].join(" · ");

  const currentIndex = PIPELINE_STEPS.findIndex((step) => step.key === job.currentStepKey);
  progressWrap.innerHTML = `
    <div class="progress-bar">
      <span style="width:${Number(job.progressPct || 0)}%"></span>
    </div>
    <div class="progress-meta">
      <strong>${Number(job.progressPct || 0)}%</strong>
      <span>${esc(job.currentStepLabel || "Aguardando")}</span>
    </div>
    <div class="step-row">
      ${PIPELINE_STEPS.map((step, index) => {
        const isDone = job.status === "succeeded" ? index <= currentIndex : index < currentIndex;
        const isCurrent = index === currentIndex;
        return `
          <span class="step-pill ${isDone ? "done" : ""} ${isCurrent ? "current" : ""}">${esc(step.label)}</span>
        `;
      }).join("")}
    </div>
  `;
}

function renderMeta() {
  const generatedAt = $("generated-at");
  const datePicker = $("date-picker");
  const kindleInput = $("kindle-email");
  const kindleHint = $("kindle-hint");
  const kindleButton = $("kindle-button");
  const entry = selectedDigest();

  if (generatedAt) {
    generatedAt.textContent = state.overview.generatedAtLabel;
  }
  if (datePicker) {
    datePicker.value = entry?.dateRef || state.overview.selectedDate || "";
  }
  if (kindleInput && !kindleInput.value) {
    kindleInput.value = state.overview.kindle?.defaultEmail || "";
  }
  if (kindleHint) {
    kindleHint.textContent = state.overview.kindle?.configured
      ? "Use o e-mail aprovado na Amazon. O PDF atual será enviado como anexo."
      : "Configure SMTP e o endereço padrão do Kindle no servidor para habilitar esta ação.";
  }
  if (kindleButton) {
    kindleButton.disabled = !state.overview.kindle?.configured || state.kindleSending || !(entry?.pdfArtifacts?.length);
  }
}

function signalVariant(signal) {
  const value = String(signal || "").toLowerCase();
  if (value.startsWith("alta")) return "high";
  if (value.startsWith("baixa")) return "low";
  return "medium";
}

function updateUrl() {
  const params = new URLSearchParams();
  params.set("days", String(state.overview.daysBack));
  if (selectedDigest()?.dateRef) {
    params.set("date", selectedDigest().dateRef);
  }
  window.history.replaceState({}, "", `/?${params.toString()}`);
}

function renderAll() {
  renderCalendar();
  renderHero();
  renderDigest();
  renderMarket();
  renderMedia();
  renderJobBanner();
  renderMeta();
  updateUrl();
  updatePolling();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || "Falha ao conversar com o servidor.");
  }
  return payload;
}

async function refreshOverview(daysBack = state.overview.daysBack, selectedDate = selectedDigest()?.dateRef) {
  const params = new URLSearchParams({ days: String(daysBack) });
  if (selectedDate) params.set("date", selectedDate);
  const payload = await fetchJson(`/api/overview?${params.toString()}`);
  state.overview = payload;
  state.selectedEntry = payload.selectedEntry;
  state.selectedJob = payload.selectedJob;
  renderAll();
}

async function selectDate(dateRef, refresh = false) {
  const localEntry = state.overview.entries.find((entry) => entry.dateRef === dateRef);
  if (localEntry) {
    state.selectedEntry = localEntry;
    state.selectedJob = state.selectedJob?.dateRef === dateRef ? state.selectedJob : null;
    renderAll();
  }

  if (!refresh) return;
  const payload = await fetchJson(`/api/days/${dateRef}`);
  state.selectedEntry = payload.entry;
  state.selectedJob = payload.job;
  renderAll();
}

async function triggerGeneration(force = false) {
  const dateRef = $("date-picker").value || selectedDigest()?.dateRef;
  if (!dateRef) {
    window.alert("Escolha uma data para gerar o digest.");
    return;
  }

  const generateButton = $("generate-button");
  const forceButton = $("force-button");
  generateButton.disabled = true;
  forceButton.disabled = true;

  try {
    const payload = await fetchJson("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date_ref: dateRef, force }),
    });
    state.selectedEntry = payload.entry;
    state.selectedJob = payload.job;
    renderAll();
    await refreshOverview(state.overview.daysBack, dateRef);
  } catch (error) {
    window.alert(error.message);
  } finally {
    generateButton.disabled = false;
    forceButton.disabled = false;
  }
}

async function sendToKindle() {
  const entry = selectedDigest();
  if (!entry?.pdfArtifacts?.length) {
    window.alert("Gere o PDF antes de enviar para o Kindle.");
    return;
  }

  const kindleEmail = $("kindle-email").value.trim();
  state.kindleSending = true;
  renderMeta();

  try {
    const payload = await fetchJson("/api/kindle/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date_ref: entry.dateRef, kindle_email: kindleEmail || null }),
    });
    setFlash("success", `PDF enviado para ${payload.kindleEmail}.`);
    await refreshOverview(state.overview.daysBack, entry.dateRef);
  } catch (error) {
    setFlash("warning", error.message);
  } finally {
    state.kindleSending = false;
    renderMeta();
  }
}

function updatePolling() {
  if (state.pollingId) {
    window.clearInterval(state.pollingId);
    state.pollingId = null;
  }

  if (!state.selectedJob || !["queued", "running"].includes(state.selectedJob.status)) {
    return;
  }

  state.pollingId = window.setInterval(async () => {
    try {
      await refreshOverview(state.overview.daysBack, selectedDigest()?.dateRef);
    } catch (error) {
      console.error(error);
    }
  }, 2500);
}

document.addEventListener("DOMContentLoaded", () => {
  $("generate-button").addEventListener("click", () => triggerGeneration(false));
  $("force-button").addEventListener("click", () => triggerGeneration(true));
  $("kindle-button").addEventListener("click", () => sendToKindle());
  $("date-picker").addEventListener("change", (event) => {
    if (event.target.value) {
      selectDate(event.target.value, true).catch((error) => window.alert(error.message));
    }
  });

  renderAll();
  refreshOverview(state.overview.daysBack, state.overview.selectedDate).catch((error) => {
    console.error(error);
  });
});
