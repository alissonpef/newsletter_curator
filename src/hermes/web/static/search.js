"use strict";

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function $(id) {
  return document.getElementById(id);
}

function scoreClass(score) {
  if (score >= 0.75) return "high";
  if (score >= 0.5) return "med";
  return "low";
}

function signalClass(signal) {
  const v = String(signal || "").toLowerCase();
  if (v.startsWith("alta")) return "high";
  if (v.startsWith("baixa")) return "low";
  return "med";
}

function sectionLabel(section) {
  const map = {
    thesis: "Tese do dia",
    executiveSummary: "Panorama executivo",
    keyPoint: "Leitura prioritária",
    topic: "Tema em foco",
    closing: "Fechamento",
  };
  return map[section] || section;
}

async function fetchJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Erro na comunicação com o servidor.");
  }
  return resp.json();
}

const state = {
  activeTab: "results",
  lastQuery: "",
  loading: false,
};

window.addEventListener("DOMContentLoaded", () => {
  const today = new Date().toISOString().split("T")[0];
  const filterTo = $("filter-to");
  if (filterTo && !filterTo.value) {
    filterTo.value = today;
  }
});

function buildResultCard(result) {
  const isNewsletter = result.type === "newsletter";
  const scoreNum = Number(result.score || 0);
  const cls = scoreClass(scoreNum);
  const typePillClass = isNewsletter ? "newsletter" : "digest";
  const typeLabel = isNewsletter ? "Newsletter" : "Digest";

  let titleHtml;
  if (isNewsletter) {
    titleHtml = esc(result.subject || "(sem assunto)");
  } else {
    const section = sectionLabel(result.section);
    titleHtml = result.topic_title
      ? `${esc(result.topic_title)} <small class="section-suffix">· ${esc(section)}</small>`
      : esc(section);
  }

  const signalHtml = result.signal
    ? `<span class="result-signal ${signalClass(result.signal)}">${esc(result.signal)}</span>`
    : "";

  const senderHtml = isNewsletter && result.sender
    ? `<span class="result-sender">${esc(result.sender)}</span>`
    : "";

  return `
    <a class="result-card type-${esc(result.type)}" href="${esc(result.dashboard_url || "/")}" target="_blank" rel="noreferrer">
      <div class="result-header">
        <span class="result-title">${titleHtml}</span>
        <span class="result-score ${cls}">${Math.round(scoreNum * 100)}% rel.</span>
      </div>
      <div class="result-meta">
        <span class="result-type-pill ${typePillClass}">${typeLabel}</span>
        <span class="result-date">${esc(result.date_label || result.date_ref)}</span>
        ${senderHtml}
        ${signalHtml}
      </div>
      <p class="result-snippet">${esc(result.snippet || "")}</p>
    </a>
  `;
}

function buildTimelineChart(byDate) {
  if (!byDate || !byDate.length) return "";

  const maxCount = Math.max(...byDate.map((d) => d.count), 1);
  const chartItems = byDate.slice(0, 30).reverse();

  const bars = chartItems.map((item) => {
    const pct = Math.max(8, (item.count / maxCount) * 100);
    const [yyyy, mm, dd] = (item.date_ref || "").split("-");
    return `
      <div class="chart-bar-wrap" title="${esc(item.date_label || item.date_ref)} · ${item.count} ocorrência(s)">
        <span class="chart-bar-count">${item.count}</span>
        <div class="chart-bar" style="height:${pct}%"></div>
        <span class="chart-bar-label">${esc(dd ? `${dd}/${mm}` : (item.date_ref || ""))}</span>
      </div>
    `;
  }).join("");

  return `<div class="chart-bars">${bars}</div>`;
}

function buildTimelineList(byDate) {
  return (byDate || []).map((item) => {
    const [yyyy, mm, dd] = (item.date_ref || "").split("-");
    const monthNames = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"];
    const monthShort = mm ? monthNames[parseInt(mm) - 1] || mm : "";
    return `
      <div class="timeline-item">
        <div class="timeline-date-block">
          <div class="timeline-day">${esc(dd || "—")}</div>
          <div class="timeline-month">${esc(monthShort)}</div>
        </div>
        <div class="timeline-content">
          <div class="timeline-count-badge">
            ${item.count} ${item.count === 1 ? "ocorrência" : "ocorrências"}
          </div>
          <p class="timeline-snippet">${esc(item.top_snippet || "")}</p>
          <a class="timeline-link" href="/?date=${esc(item.date_ref)}" target="_blank" rel="noreferrer">
            Ver digest →
          </a>
        </div>
      </div>
    `;
  }).join("");
}

function setLoading(on) {
  state.loading = on;
  $("results-loading").hidden = !on;
  $("search-btn").disabled = on;
  $("search-input").disabled = on;
}

function clearResults() {
  $("results-grid").innerHTML = "";
  $("results-meta").hidden = true;
  $("results-empty").hidden = true;
  $("results-loading").hidden = true;
  $("timeline-chart").innerHTML = "";
  $("timeline-list").innerHTML = "";
  $("timeline-meta").hidden = true;
  $("timeline-empty").hidden = true;
}

async function doSearch() {
  const query = ($("search-input").value || "").trim();
  if (!query) return;

  const dateFrom = ($("filter-from").value || "").trim() || null;
  const dateTo = ($("filter-to").value || "").trim() || null;
  const nResults = parseInt($("filter-n").value) || 20;

  state.lastQuery = query;

  clearResults();
  setLoading(true);

  try {
    if (state.activeTab === "results") {
      await runResultsSearch(query, nResults, dateFrom, dateTo);
    } else {
      const days = computeDays(dateFrom);
      await runTimelineSearch(query, days);
    }
  } catch (err) {
    $("results-empty").hidden = false;
    $("results-empty").querySelector("h3").textContent = "Erro na busca";
    $("results-empty").querySelector("p").textContent = err.message;
  } finally {
    setLoading(false);
  }

  const params = new URLSearchParams({ q: query });
  if (dateFrom) params.set("from", dateFrom);
  if (dateTo) params.set("to", dateTo);
  window.history.replaceState({}, "", `/search?${params}`);
}

async function runResultsSearch(query, nResults, dateFrom, dateTo) {
  let url = `/api/search?q=${encodeURIComponent(query)}&n=${nResults}`;
  if (dateFrom) url += `&date_from=${dateFrom}`;
  if (dateTo) url += `&date_to=${dateTo}`;

  const data = await fetchJson(url);
  const results = data.results || [];

  const meta = $("results-meta");
  meta.hidden = false;
  meta.innerHTML = `
    <strong>${results.length}</strong> resultado${results.length !== 1 ? "s" : ""}
    para <strong>"${esc(query)}"</strong>
    ${dateFrom || dateTo ? `· período: ${esc(dateFrom || "início")} → ${esc(dateTo || "hoje")}` : ""}
  `;

  if (!results.length) {
    $("results-empty").hidden = false;
    return;
  }

  $("results-grid").innerHTML = results.map(buildResultCard).join("");
}

async function runTimelineSearch(query, days) {
  const url = `/api/search/timeline?q=${encodeURIComponent(query)}&days=${days}`;
  const data = await fetchJson(url);
  const byDate = data.by_date || [];

  const meta = $("timeline-meta");
  meta.hidden = false;
  meta.innerHTML = `
    <strong>${data.total_occurrences}</strong> ocorrência${data.total_occurrences !== 1 ? "s" : ""}
    de <strong>"${esc(query)}"</strong> nos últimos <strong>${days}</strong> dias
  `;

  if (!byDate.length) {
    $("timeline-empty").hidden = false;
    return;
  }

  $("timeline-chart").innerHTML = buildTimelineChart(byDate);
  $("timeline-list").innerHTML = buildTimelineList(byDate);
}

function computeDays(dateFrom) {
  if (!dateFrom) return 30;
  const from = new Date(dateFrom);
  const now = new Date();
  const diff = Math.ceil((now - from) / (1000 * 60 * 60 * 24));
  return Math.max(1, Math.min(diff, 365));
}

function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  const isResults = tab === "results";
  $("results-panel").hidden = !isResults;
  $("timeline-panel").hidden = isResults;

  if (state.lastQuery) {
    doSearch();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const filterTo = $("filter-to");
  if (filterTo && !filterTo.value) {
    filterTo.value = new Date().toISOString().split("T")[0];
  }

  const searchBtn = $("search-btn");
  const searchInput = $("search-input");
 
  if (!searchBtn || !searchInput) {
    return;
  }

  searchBtn.addEventListener("click", () => doSearch());
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  const params = new URLSearchParams(window.location.search);
  const qParam = params.get("q");
  if (qParam) {
    searchInput.value = qParam;
    const fromParam = params.get("from");
    const toParam = params.get("to");
    if (fromParam) $("filter-from").value = fromParam;
    if (toParam) $("filter-to").value = toParam;
    doSearch();
  }
});
