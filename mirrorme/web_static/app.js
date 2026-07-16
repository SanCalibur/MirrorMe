const state = {
  date: localDate(),
  includePrivate: false,
};
let imeRequestSequence = 0;
const EVENT_WINDOW_LIMIT = 120;
const SYSTEM_IME_GROUP_GAP_MS = 8000;

const nodes = {
  dateInput: document.querySelector("#dateInput"),
  privateToggle: document.querySelector("#privateToggle"),
  captureToggleButton: document.querySelector("#captureToggleButton"),
  refreshButton: document.querySelector("#refreshButton"),
  saveSummaryButton: document.querySelector("#saveSummaryButton"),
  exportButton: document.querySelector("#exportButton"),
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
  actionStatus: document.querySelector("#actionStatus"),
  topicList: document.querySelector("#topicList"),
  projectList: document.querySelector("#projectList"),
  tagList: document.querySelector("#tagList"),
  eventDate: document.querySelector("#eventDate"),
  eventList: document.querySelector("#eventList"),
  candidateList: document.querySelector("#candidateList"),
  imeStatus: document.querySelector("#imeStatus"),
  imeMode: document.querySelector("#imeMode"),
  imeEngine: document.querySelector("#imeEngine"),
  imeLicense: document.querySelector("#imeLicense"),
  imeFit: document.querySelector("#imeFit"),
  imeSource: document.querySelector("#imeSource"),
  imePolicy: document.querySelector("#imePolicy"),
  imeReadiness: document.querySelector("#imeReadiness"),
  imeBinary: document.querySelector("#imeBinary"),
  imeInput: document.querySelector("#imeInput"),
  imeCaptureDirect: document.querySelector("#imeCaptureDirect"),
  imeCandidates: document.querySelector("#imeCandidates"),
  loadSummaryButton: document.querySelector("#loadSummaryButton"),
  processTextButton: document.querySelector("#processTextButton"),
  saveDailyAssessmentButton: document.querySelector("#saveDailyAssessmentButton"),
  workbenchInput: document.querySelector("#workbenchInput"),
  replacementRules: document.querySelector("#replacementRules"),
  deduplicateInput: document.querySelector("#deduplicateInput"),
  useLlmCleaner: document.querySelector("#useLlmCleaner"),
  llmApiUrl: document.querySelector("#llmApiUrl"),
  llmApiKey: document.querySelector("#llmApiKey"),
  llmModel: document.querySelector("#llmModel"),
  workbenchStatus: document.querySelector("#workbenchStatus"),
  workbenchResult: document.querySelector("#workbenchResult"),
  evaluationDisclaimer: document.querySelector("#evaluationDisclaimer"),
  evaluationList: document.querySelector("#evaluationList"),
  suggestionList: document.querySelector("#suggestionList"),
};

nodes.dateInput.value = state.date;

nodes.refreshButton.addEventListener("click", refresh);
nodes.loadSummaryButton.addEventListener("click", () => {
  nodes.workbenchInput.value = nodes.summaryText.textContent === "暂无内容" ? "" : nodes.summaryText.textContent;
  nodes.workbenchStatus.textContent = "已载入当前摘要，可按需修改后处理。";
});
nodes.processTextButton.addEventListener("click", async () => {
  const text = nodes.workbenchInput.value;
  if (!text.trim()) {
    nodes.workbenchStatus.textContent = "请先输入或载入要处理的文本。";
    return;
  }
  nodes.processTextButton.disabled = true;
  try {
    let textForProcessing = text;
    if (nodes.useLlmCleaner.checked) {
      const cleaned = await postJson("/api/text-workbench/llm-clean", {
        text,
        api_url: nodes.llmApiUrl.value,
        api_key: nodes.llmApiKey.value,
        model: nodes.llmModel.value,
      });
      textForProcessing = cleaned.output;
    }
    const result = await postJson("/api/text-workbench/process", {
      text: textForProcessing,
      replacements: nodes.replacementRules.value,
      deduplicate: nodes.deduplicateInput.checked,
    });
    renderWorkbenchResult(result);
    nodes.workbenchStatus.textContent = nodes.useLlmCleaner.checked
      ? "已使用 LLM 清洗并完成评估，密钥未被保存。"
      : "已完成本次手动处理与评估，未写入数据库。";
  } catch (error) {
    nodes.workbenchStatus.textContent = `处理失败：${error.message}`;
  } finally {
    nodes.processTextButton.disabled = false;
  }
});
nodes.saveDailyAssessmentButton.addEventListener("click", async () => {
  nodes.saveDailyAssessmentButton.disabled = true;
  try {
    const record = await postJson("/api/state-assessments/daily", {
      date: state.date,
      include_private: state.includePrivate,
    });
    nodes.workbenchStatus.textContent = `已保存 ${record.date} 的状态观测 v${record.version}。`;
    await loadStateHistory();
  } catch (error) {
    nodes.workbenchStatus.textContent = `保存观测失败：${error.message}`;
  } finally {
    nodes.saveDailyAssessmentButton.disabled = false;
  }
});
nodes.captureToggleButton.addEventListener("click", async () => {
  const paused = nodes.captureToggleButton.dataset.paused === "true";
  await postJson(paused ? "/api/capture/resume" : "/api/capture/pause", {});
  setActionStatus(paused ? "捕获已恢复" : "捕获已暂停");
  refresh();
});
nodes.saveSummaryButton.addEventListener("click", async () => {
  const record = await postJson("/api/summary/save", { date: state.date });
  setActionStatus(`已保存摘要 v${record.version}`);
  refresh();
});
nodes.exportButton.addEventListener("click", async () => {
  const query = new URLSearchParams({
    date: state.date,
    include_private: state.includePrivate ? "1" : "0",
    limit: "120",
    include_raw: "0",
  });
  const exported = await getJson(`/api/export?${query}`);
  const blob = new Blob([`${JSON.stringify(exported, null, 2)}\n`], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mirrorme-${state.date}.json`;
  link.click();
  URL.revokeObjectURL(url);
  setActionStatus(`已导出 ${exported.events.length} 条事件`);
});
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
  const requestSequence = ++imeRequestSequence;
  if (!text) {
    nodes.imeCandidates.replaceChildren();
    nodes.imeCandidates.append(empty("等待输入"));
    return;
  }
  try {
    const composition = await postJson("/api/ime/compose", { text });
    if (requestSequence === imeRequestSequence && text === nodes.imeInput.value.trim()) {
      renderImeCandidates(text, composition.candidates);
    }
  } catch (error) {
    if (requestSequence === imeRequestSequence) {
      nodes.imeCandidates.replaceChildren();
      nodes.imeCandidates.append(empty("输入法服务暂不可用"));
      setActionStatus(`输入法候选读取失败：${error.message}`);
    }
  }
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
  const [status, schema] = await Promise.all([
    getJson("/api/ime/status"),
    getJson("/api/ime/schema"),
  ]);
  const engine = status.selected_engine;
  nodes.imeStatus.textContent = engine.embedding_status;
  nodes.imeEngine.textContent = engine.name;
  nodes.imeLicense.textContent = `${engine.license} · ${engine.role}`;
  nodes.imeFit.textContent = engine.commercial_fit;
  nodes.imeSource.textContent = engine.source_url;
  renderCounts(nodes.imePolicy, status.capture_policy);
  const native = schema.native === true;
  nodes.imeMode.textContent = native ? "原生 librime" : "协议 stub";
  nodes.imeMode.dataset.native = native ? "true" : "false";
  nodes.imeReadiness.textContent = native ? "已验证" : "未启用";
  nodes.imeBinary.textContent =
    native
      ? `${schema.engine}${schema.librime_version ? ` ${schema.librime_version}` : ""}`
      : `${schema.engine} · ${status.native_adapter.binary_env} 未配置`;
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
  nodes.captureToggleButton.textContent = overview.capture_paused ? "恢复" : "暂停";
  nodes.captureToggleButton.dataset.paused = overview.capture_paused ? "true" : "false";
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
  const blocks = composeEventBlocks(events);
  if (!blocks.length) {
    nodes.eventList.append(empty("这一天还没有记录"));
    return;
  }
  for (const block of blocks) {
    const item = document.createElement("article");
    item.className = block.is_private ? "event private" : "event";
    item.innerHTML = `
      <div class="event-head">
        <strong>${escapeHtml(block.created_at.slice(11, 19))}</strong>
        <span class="meta">${escapeHtml(block.project || "未归档")}</span>
      </div>
      <p class="event-text">${escapeHtml(block.text)}</p>
      <div class="event-foot">
        <p class="meta">${escapeHtml((block.tags || []).join(", ") || "无标签")} · ${block.event_ids.length} 条提交</p>
        <button class="secondary compact" type="button" data-action="delete">删除</button>
      </div>
    `;
    item.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      await Promise.all(block.event_ids.map((eventId) => deleteJson(`/api/events/${encodeURIComponent(eventId)}`)));
      setActionStatus("事件已删除，相关摘要会重新生成");
      refresh();
    });
    nodes.eventList.append(item);
  }
}

function renderWorkbenchResult(result) {
  nodes.workbenchResult.textContent = result.output || "处理后文本为空";
  nodes.evaluationDisclaimer.textContent = result.evaluation.disclaimer;
  nodes.evaluationList.replaceChildren();
  for (const metric of result.evaluation.metrics) {
    const item = document.createElement("article");
    item.className = "evaluation";
    item.innerHTML = `
      <span>${escapeHtml(metric.label)}</span>
      <strong>${metric.score}</strong>
      <small>${escapeHtml(metric.detail)}</small>
    `;
    nodes.evaluationList.append(item);
  }
  nodes.suggestionList.replaceChildren();
  for (const suggestion of result.evaluation.suggestions) {
    const item = document.createElement("p");
    item.textContent = suggestion;
    nodes.suggestionList.append(item);
  }
}


function composeEventBlocks(events) {
  const blocks = [];
  for (const event of events) {
    const previous = blocks.at(-1);
    if (previous && canAppendToBlock(previous, event)) {
      previous.text += joinCommittedText(previous.text, event.redacted);
      previous.event_ids.push(event.id);
      previous.last_created_at = event.created_at;
      continue;
    }
    blocks.push({
      created_at: event.created_at,
      last_created_at: event.created_at,
      text: event.redacted,
      event_ids: [event.id],
      source_method: event.source_method,
      source_app: event.source_app,
      project: event.project,
      tags: event.tags,
      is_private: event.is_private,
    });
  }
  return blocks;
}

function canAppendToBlock(block, event) {
  if (block.source_method !== "system_ime_commit" || event.source_method !== block.source_method) return false;
  if (block.source_app !== event.source_app || block.project !== event.project || block.is_private !== event.is_private) return false;
  if (/[.!?。！？]$/.test(block.text)) return false;
  return new Date(event.created_at) - new Date(block.last_created_at) <= SYSTEM_IME_GROUP_GAP_MS;
}

function joinCommittedText(previous, next) {
  if (/[A-Za-z0-9]$/.test(previous) && /^[A-Za-z0-9]/.test(next)) return ` ${next}`;
  return next;
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
      button.disabled = true;
      try {
        if (nodes.imeCaptureDirect.checked) {
          await postJson("/api/ime/capture", {
            text: input,
            candidate_index: candidate.index,
            project: nodes.projectInput.value.trim(),
            tags: nodes.tagsInput.value.trim(),
            is_private: nodes.eventPrivateInput.checked,
          });
          nodes.imeInput.value = "";
          nodes.imeCandidates.replaceChildren();
          nodes.imeCandidates.append(empty("已提交到分析"));
          setActionStatus(`已提交候选：${candidate.text}`);
          refresh();
        } else {
          const result = await postJson("/api/ime/commit", {
            text: input,
            candidate_index: candidate.index,
          });
          if (result.committed) {
            nodes.textInput.value = `${nodes.textInput.value}${result.committed}`;
            nodes.textInput.focus();
            setActionStatus(`已写入待保存文本：${result.committed}`);
          }
        }
      } catch (error) {
        setActionStatus(`输入法提交失败：${error.message}`);
      } finally {
        button.disabled = false;
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

async function deleteJson(url) {
  const response = await fetch(url, { method: "DELETE" });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function setActionStatus(text) {
  nodes.actionStatus.textContent = text;
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
