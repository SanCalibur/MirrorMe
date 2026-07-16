const nodes = {
  refresh: document.querySelector("#stateRefresh"),
  empty: document.querySelector("#stateEmpty"),
  content: document.querySelector("#stateContent"),
  latestDate: document.querySelector("#latestDate"),
  latestMeta: document.querySelector("#latestMeta"),
  latestDisclaimer: document.querySelector("#latestDisclaimer"),
  metricGrid: document.querySelector("#metricGrid"),
  historyCount: document.querySelector("#historyCount"),
  historyList: document.querySelector("#historyList"),
};

nodes.refresh.addEventListener("click", load);
load();

async function load() {
  nodes.refresh.disabled = true;
  try {
    const records = await getJson("/api/state-assessments?latest_per_day=1&limit=30");
    render(records);
  } finally {
    nodes.refresh.disabled = false;
  }
}

function render(records) {
  const latest = records.at(-1);
  nodes.empty.hidden = Boolean(latest);
  nodes.content.hidden = !latest;
  if (!latest) return;

  nodes.latestDate.textContent = latest.date;
  nodes.latestMeta.textContent = `v${latest.version} · ${latest.assessment.input_scope} · ${latest.assessment.source_event_count} 条来源事件`;
  nodes.latestDisclaimer.textContent = latest.assessment.disclaimer;
  nodes.metricGrid.replaceChildren();
  for (const metric of latest.assessment.metrics) nodes.metricGrid.append(metricCard(metric));

  nodes.historyCount.textContent = `${records.length} 天有记录`;
  nodes.historyList.replaceChildren();
  for (const record of [...records].reverse()) nodes.historyList.append(historyRow(record));
}

function metricCard(metric) {
  const item = document.createElement("article");
  item.className = "state-metric";
  item.dataset.key = metric.key;
  item.innerHTML = `
    <div class="state-metric-top"><span>${escapeHtml(metric.label)}</span><strong>${metric.score}</strong></div>
    <div class="state-meter"><i style="width:${metric.score}%"></i></div>
    <p>${escapeHtml(metric.detail)}</p>
  `;
  return item;
}

function historyRow(record) {
  const item = document.createElement("article");
  item.className = "history-row";
  const bars = record.assessment.metrics
    .map((metric) => `<i data-key="${escapeHtml(metric.key)}" style="height:${Math.max(4, metric.score / 4)}px" title="${escapeHtml(metric.label)} ${metric.score}"></i>`)
    .join("");
  const labels = record.assessment.metrics.map((metric) => `${metric.label} ${metric.score}`).join(" · ");
  item.innerHTML = `<strong>${escapeHtml(record.date)}</strong><span class="state-muted">v${record.version} · ${record.assessment.source_event_count} 条</span><div class="history-bars">${bars}<span class="state-muted">${escapeHtml(labels)}</span></div>`;
  return item;
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
