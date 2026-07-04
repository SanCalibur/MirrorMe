const state = {
  date: localDate(),
  includePrivate: false,
};

const nodes = {
  dateInput: document.querySelector("#dateInput"),
  privateToggle: document.querySelector("#privateToggle"),
  refreshButton: document.querySelector("#refreshButton"),
  captureForm: document.querySelector("#captureForm"),
  textInput: document.querySelector("#textInput"),
  projectInput: document.querySelector("#projectInput"),
  tagsInput: document.querySelector("#tagsInput"),
  eventPrivateInput: document.querySelector("#eventPrivateInput"),
  eventTotal: document.querySelector("#eventTotal"),
  eventSplit: document.querySelector("#eventSplit"),
  pendingTotal: document.querySelector("#pendingTotal"),
  memoryTotal: document.querySelector("#memoryTotal"),
  summaryTotal: document.querySelector("#summaryTotal"),
  latestSummary: document.querySelector("#latestSummary"),
  captureStatus: document.querySelector("#captureStatus"),
  summaryDate: document.querySelector("#summaryDate"),
  summaryText: document.querySelector("#summaryText"),
  topicList: document.querySelector("#topicList"),
  projectList: document.querySelector("#projectList"),
  tagList: document.querySelector("#tagList"),
  eventDate: document.querySelector("#eventDate"),
  eventList: document.querySelector("#eventList"),
  candidateList: document.querySelector("#candidateList"),
  imeStatus: document.querySelector("#imeStatus"),
  imeEngine: document.querySelector("#imeEngine"),
  imeLicense: document.querySelector("#imeLicense"),
  imeFit: document.querySelector("#imeFit"),
  imeSource: document.querySelector("#imeSource"),
  imePolicy: document.querySelector("#imePolicy"),
  imeReadiness: document.querySelector("#imeReadiness"),
  imeBinary: document.querySelector("#imeBinary"),
  imeInput: document.querySelector("#imeInput"),
  imeCandidates: document.querySelector("#imeCandidates"),
};

nodes.dateInput.value = state.date;

nodes.refreshButton.addEventListener("click", refresh);
nodes.dateInput.addEventListener("change", () => {
  state.date = nodes.dateInput.value || localDate();
  refresh();
});
nodes.privateToggle.addEventListener("change", () => {
  state.includePrivate = nodes.privateToggle.checked;
  refresh();
});
nodes.captureForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = nodes.textInput.value.trim();
  if (!text) return;
  await postJson("/api/events", {
    text,
    project: nodes.projectInput.value.trim(),
    tags: nodes.tagsInput.value.trim(),
    is_private: nodes.eventPrivateInput.checked,
  });
  nodes.textInput.value = "";
  refresh();
});
nodes.imeInput.addEventListener("input", async () => {
  const text = nodes.imeInput.value.trim();
  if (!text) {
    nodes.imeCandidates.replaceChildren();
    nodes.imeCandidates.append(empty("等待输入"));
    return;
  }
  const composition = await postJson("/api/ime/compose", { text });
  renderImeCandidates(text, composition.candidates);
});

refresh();

async function refresh() {
  const query = new URLSearchParams({
    date: state.date,
    include_private: state.includePrivate ? "1" : "0",
  });
  const [overview, events] = await Promise.all([
    getJson(`/api/daily?${query}`),
    getJson(`/api/events?${query}`),
  ]);
  renderOverview(overview);
  renderEvents(events);
  loadImeStatus();
}

async function loadImeStatus() {
  const status = await getJson("/api/ime/status");
  const engine = status.selected_engine;
  nodes.imeStatus.textContent = engine.embedding_status;
  nodes.imeEngine.textContent = engine.name;
  nodes.imeLicense.textContent = `${engine.license} · ${engine.role}`;
  nodes.imeFit.textContent = engine.commercial_fit;
  nodes.imeSource.textContent = engine.source_url;
  renderCounts(nodes.imePolicy, status.capture_policy);
  nodes.imeReadiness.textContent = status.native_adapter.readiness;
  nodes.imeBinary.textContent =
    status.native_adapter.binary_path || `${status.native_adapter.binary_env} 未配置`;
}

function renderOverview(overview) {
  const events = overview.events;
  const pending = overview.pending_memory_candidates;
  const memories = overview.active_memories;
  const summaries = overview.saved_summaries;
  const latest = summaries.at(-1);

  nodes.eventTotal.textContent = events.total;
  nodes.eventSplit.textContent = `公开 ${events.public} / 私密 ${events.private}`;
  nodes.pendingTotal.textContent = pending.length;
  nodes.memoryTotal.textContent = `已确认 ${memories.length}`;
  nodes.summaryTotal.textContent = summaries.length;
  nodes.latestSummary.textContent = latest ? `v${latest.version} ${latest.id}` : "尚无保存版本";
  nodes.captureStatus.textContent = overview.capture_paused ? "已暂停" : "运行中";
  nodes.summaryDate.textContent = overview.date;
  nodes.eventDate.textContent = overview.date;
  nodes.summaryText.textContent = overview.summary.summary || "暂无内容";

  renderPills(nodes.topicList, overview.summary.topics);
  renderCounts(nodes.projectList, events.projects);
  renderCounts(nodes.tagList, events.tags);
  renderCandidates(pending);
}

function renderEvents(events) {
  nodes.eventList.replaceChildren();
  if (!events.length) {
    nodes.eventList.append(empty("这一天还没有记录"));
    return;
  }
  for (const event of events) {
    const item = document.createElement("article");
    item.className = event.is_private ? "event private" : "event";
    item.innerHTML = `
      <div class="event-head">
        <strong>${escapeHtml(event.created_at.slice(11, 19))}</strong>
        <span class="meta">${escapeHtml(event.project || "未归档")}</span>
      </div>
      <p class="event-text">${escapeHtml(event.redacted)}</p>
      <p class="meta">${escapeHtml((event.tags || []).join(", ") || "无标签")}</p>
    `;
    nodes.eventList.append(item);
  }
}

function renderCandidates(candidates) {
  nodes.candidateList.replaceChildren();
  if (!candidates.length) {
    nodes.candidateList.append(empty("暂无待审核记忆"));
    return;
  }
  for (const candidate of candidates) {
    const item = document.createElement("article");
    item.className = "candidate";
    item.innerHTML = `
      <div class="candidate-head">
        <strong>${escapeHtml(candidate.kind)} · ${Number(candidate.confidence).toFixed(2)}</strong>
        <span class="meta">#${candidate.index}</span>
      </div>
      <p class="candidate-text">${escapeHtml(candidate.content)}</p>
      <div class="candidate-actions">
        <button type="button" data-action="accept">接受</button>
        <button class="secondary" type="button" data-action="reject">拒绝</button>
      </div>
    `;
    item.querySelector('[data-action="accept"]').addEventListener("click", async () => {
      await postJson("/api/review/accept", { date: state.date, index: candidate.index });
      refresh();
    });
    item.querySelector('[data-action="reject"]').addEventListener("click", async () => {
      await postJson("/api/review/reject", { date: state.date, index: candidate.index });
      refresh();
    });
    nodes.candidateList.append(item);
  }
}

function renderImeCandidates(input, candidates) {
  nodes.imeCandidates.replaceChildren();
  if (!candidates.length) {
    nodes.imeCandidates.append(empty("暂无候选"));
    return;
  }
  for (const candidate of candidates) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${candidate.index}. ${candidate.text}`;
    button.title = candidate.annotation;
    button.addEventListener("click", async () => {
      const result = await postJson("/api/ime/commit", {
        text: input,
        candidate_index: candidate.index,
      });
      if (result.committed) {
        nodes.textInput.value = `${nodes.textInput.value}${result.committed}`;
        nodes.textInput.focus();
      }
    });
    nodes.imeCandidates.append(button);
  }
}

function renderPills(container, values) {
  container.replaceChildren();
  if (!values || !values.length) {
    container.append(empty("暂无主题"));
    return;
  }
  for (const value of values) {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = value;
    container.append(pill);
  }
}

function renderCounts(container, counts) {
  container.replaceChildren();
  const entries = Object.entries(counts || {});
  if (!entries.length) {
    container.append(empty("暂无数据"));
    return;
  }
  for (const [key, value] of entries) {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = `${key}: ${value}`;
    container.append(pill);
  }
}

function empty(text) {
  const node = document.createElement("div");
  node.className = "empty";
  node.textContent = text;
  return node;
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function localDate() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
