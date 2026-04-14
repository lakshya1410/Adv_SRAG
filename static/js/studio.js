"use strict";

const D = {};

function initializeDOM() {
  D.sidebar = document.getElementById("sidebar-container");
  D.sidebarBackdrop = document.getElementById("sidebar-backdrop");
  D.sidebarMobileToggle = document.getElementById("sidebar-mobile-toggle");
  D.backendStatus = document.getElementById("backend-status");
  D.newSessionBtn = document.getElementById("new-session-btn");
  D.modelSelect = document.getElementById("model-select");
  D.pdfFiles = document.getElementById("pdf-files");
  D.dropZone = document.getElementById("drop-zone");
  D.fileList = document.getElementById("file-list");
  D.processBtn = document.getElementById("process-btn");
  D.processSpinner = document.getElementById("process-spinner");
  D.statusBox = document.getElementById("status-box");
  D.docMeta = document.getElementById("doc-meta");
  D.chunkLabel = document.getElementById("chunk-label");
  D.docList = document.getElementById("doc-list");
  D.resetBtn = document.getElementById("reset-btn");
  D.responseArea = document.getElementById("response-area");
  D.responsePlaceholder = document.getElementById("response-placeholder");
  D.resultsPanels = document.getElementById("results-panels");
  D.docsArea = document.getElementById("docs-area");
  D.docsCountBadge = document.getElementById("docs-count-badge");
  D.evalArea = document.getElementById("eval-area");
  D.evalNum = document.getElementById("eval-num");
  D.queryError = document.getElementById("query-error");
  D.queryInput = document.getElementById("query-input");
  D.runBtn = document.getElementById("run-btn");
  D.runSpinner = document.getElementById("run-spinner");
  D.loadingOverlay = document.getElementById("loading-overlay");
  D.loadingLabel = document.getElementById("loading-label");
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setStatus(message, type = "") {
  D.statusBox.textContent = message;
  D.statusBox.className = `sidebar-status-box${type ? ` ${type}` : ""}`;
}

function setBackendStatus(connected) {
  D.backendStatus.textContent = connected ? "Connected" : "Disconnected";
  D.backendStatus.className = `backend-status-pill ${connected ? "connected" : "disconnected"}`;
}

function showQueryError(message) {
  D.queryError.innerHTML = `<span class="error-icon">!</span><span>${esc(message)}</span>`;
  D.queryError.classList.remove("hidden");
}

function clearQueryError() {
  D.queryError.textContent = "";
  D.queryError.classList.add("hidden");
}

function showLoading(label) {
  D.loadingLabel.textContent = label;
  D.loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  D.loadingOverlay.classList.add("hidden");
}

function formatAnswer(text) {
  return esc(text || "No answer found.").replace(/\n/g, "<br>");
}

async function fetchJson(url, options = {}) {
  const timeoutMs = options.timeoutMs || 90000;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const fetchOptions = { ...options, signal: controller.signal };
  delete fetchOptions.timeoutMs;

  let response;
  try {
    response = await fetch(url, fetchOptions);
  } catch (error) {
    window.clearTimeout(timer);
    if (error.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)} seconds.`);
    }
    throw new Error("Backend is unreachable. Start Flask and refresh the page.");
  }
  window.clearTimeout(timer);

  let data = {};
  try {
    data = await response.json();
  } catch {
    throw new Error(`Server returned an invalid response (${response.status}).`);
  }

  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "Request failed.");
  }

  return data;
}

function updateRunButton() {
  const hasDocs = !D.docMeta.classList.contains("hidden");
  const hasQuestion = Boolean(D.queryInput.value.trim());
  D.runBtn.disabled = !(hasDocs && hasQuestion);
}

function renderSidebarDocs(docNames, chunkCount, modelName) {
  D.docList.innerHTML = docNames
    .map((name) => `<li>${esc(name)}</li>`)
    .join("");
  D.chunkLabel.textContent = `${chunkCount} chunk(s) indexed with ${modelName}`;
  D.docMeta.classList.remove("hidden");
}

function renderFileList() {
  const files = Array.from(D.pdfFiles.files || []);
  D.fileList.innerHTML = files.map((file) => {
    const sizeKb = Math.max(1, Math.round(file.size / 1024));
    return `<div class="sidebar-file-item"><span>${esc(file.name)}</span><span class="file-size">${sizeKb} KB</span></div>`;
  }).join("");
  D.processBtn.disabled = files.length === 0;
}

function createMessageCard(role, html) {
  const card = document.createElement("div");
  card.className = `response-message ${role}`;
  card.innerHTML = html;
  return card;
}

function appendConversation(question, answer) {
  if (D.responsePlaceholder && D.responsePlaceholder.parentNode) {
    D.responsePlaceholder.remove();
  }

  D.responseArea.appendChild(createMessageCard("user", `<div class="msg-text">${esc(question)}</div>`));
  D.responseArea.appendChild(createMessageCard("assistant", `<div class="msg-text">${formatAnswer(answer)}</div>`));
  D.responseArea.scrollTop = D.responseArea.scrollHeight;
}

function renderDocuments(documents) {
  if (!documents || documents.length === 0) {
    D.docsCountBadge.textContent = "0";
    D.docsArea.innerHTML = '<div class="docs-placeholder">No documents retrieved. The model answered directly.</div>';
    return;
  }

  D.docsCountBadge.textContent = String(documents.length);
  D.docsArea.innerHTML = documents.map((doc) => {
    const score = Math.max(0, Math.min(1, Number(doc.score || 0)));
    const pct = Math.round(score * 100);
    const source = doc.source ? doc.source.split(/[\\/]/).pop() : "Document";
    const page = doc.page === "" || doc.page === undefined ? "" : ` | p.${doc.page}`;

    return `
      <article class="doc-card">
        <div class="doc-card-header">
          <span class="doc-card-src">${esc(source)}${esc(page)}</span>
        </div>
        <div class="doc-score-bar">
          <div class="doc-score-label"><span>Relevance</span><span>${pct}%</span></div>
          <div class="doc-score-track">
            <div class="doc-score-fill" style="width:${pct}%"></div>
          </div>
        </div>
        <div class="doc-text">${esc(doc.text || "")}</div>
      </article>
    `;
  }).join("");
}

function renderEvaluation(evaluation) {
  if (!evaluation) {
    D.evalNum.textContent = "--";
    D.evalArea.innerHTML = '<div class="eval-placeholder">No evaluation data available.</div>';
    return;
  }

  const confidence = Math.round((evaluation.confidence || 0) * 100);
  const relevance = Math.round((evaluation.relevance_score || 0) * 100);
  const issup = (evaluation.issup || "N/A").replace(/_/g, " ");
  const isuse = (evaluation.isuse || "N/A").replace(/_/g, " ");
  const confClass = confidence >= 80 ? "good" : confidence >= 50 ? "mid" : "bad";
  const relClass = relevance >= 80 ? "good" : relevance >= 50 ? "mid" : "bad";

  D.evalNum.textContent = issup;

  const pills = [
    `IsSUP: ${issup}`,
    `IsUSE: ${isuse}`,
    `Revisions: ${evaluation.retries || 0}`,
    `Rewrites: ${evaluation.rewrite_tries || 0}`,
  ];

  if (evaluation.need_retrieval === false) {
    pills.push("Direct answer path");
  }

  D.evalArea.innerHTML = `
    <div class="eval-metric">
      <div class="eval-metric-label"><span>Confidence</span><span>${confidence}%</span></div>
      <div class="eval-bar-track"><div class="eval-bar-fill ${confClass}" style="width:${confidence}%"></div></div>
    </div>
    <div class="eval-metric">
      <div class="eval-metric-label"><span>Context relevance</span><span>${relevance}%</span></div>
      <div class="eval-bar-track"><div class="eval-bar-fill ${relClass}" style="width:${relevance}%"></div></div>
    </div>
    <div class="eval-pills">${pills.map((pill) => `<span class="eval-pill">${esc(pill)}</span>`).join("")}</div>
    ${evaluation.use_reason ? `<div class="eval-note">${esc(evaluation.use_reason)}</div>` : ""}
    ${(evaluation.evidence || []).length ? `
      <div class="evidence-section">
        <div class="evidence-title">Supporting Evidence</div>
        ${evaluation.evidence.map((item) => `<div class="evidence-item">${esc(item)}</div>`).join("")}
      </div>` : ""}
  `;
}

function openMobileSidebar() {
  D.sidebar.classList.add("mobile-open");
  D.sidebarBackdrop.classList.remove("hidden");
}

function closeMobileSidebar() {
  D.sidebar.classList.remove("mobile-open");
  D.sidebarBackdrop.classList.add("hidden");
}

function resetResultsPanels() {
  D.resultsPanels.classList.add("hidden");
  D.docsArea.innerHTML = '<div class="docs-placeholder">Run a query to see retrieved chunks here.</div>';
  D.docsCountBadge.textContent = "0";
  D.evalArea.innerHTML = '<div class="eval-placeholder">Evaluation metrics appear here after a query.</div>';
  D.evalNum.textContent = "--";
}

async function loadModels() {
  const { models } = await fetchJson("/api/models");
  D.modelSelect.innerHTML = models
    .map((model) => `<option value="${esc(model)}">${esc(model)}</option>`)
    .join("");
}

async function loadStatus() {
  const status = await fetchJson("/api/status");

  if (status.model_name) {
    D.modelSelect.value = status.model_name;
  }

  if (status.ready) {
    renderSidebarDocs(status.doc_names || [], status.chunk_count || 0, status.model_name || "selected model");
    setStatus("Knowledge base ready. Ask a question below.", "success");
  } else {
    setStatus("Upload PDFs and click Build Knowledge Base.");
  }

  updateRunButton();
}

async function checkBackendStatus() {
  try {
    const response = await fetch("/health", { signal: AbortSignal.timeout(5000) });
    setBackendStatus(response.ok);
  } catch {
    setBackendStatus(false);
  }
}

async function handleProcessDocuments() {
  const files = Array.from(D.pdfFiles.files || []);
  if (files.length === 0) {
    showQueryError("Please select at least one PDF file.");
    return;
  }

  clearQueryError();
  D.processBtn.disabled = true;
  D.processSpinner.classList.remove("hidden");
  setStatus("Processing documents. This can take a minute for larger PDFs.");
  showLoading("Processing documents...");

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("model_name", D.modelSelect.value);

  try {
    const response = await fetchJson("/api/process-documents", {
      method: "POST",
      body: formData,
      timeoutMs: 180000,
    });

    renderSidebarDocs(response.doc_names || [], response.chunk_count || 0, response.model_name || D.modelSelect.value);
    D.pdfFiles.value = "";
    D.fileList.innerHTML = "";
    D.processBtn.disabled = true;
    setStatus(`Ready to query. Indexed ${response.chunk_count} chunk(s) from ${response.doc_names.length} file(s).`, "success");
  } catch (error) {
    showQueryError(error.message);
    setStatus("Could not build the knowledge base.", "error");
  } finally {
    hideLoading();
    D.processSpinner.classList.add("hidden");
    updateRunButton();
  }
}

async function handleRunQuery() {
  const question = D.queryInput.value.trim();
  if (!question) {
    showQueryError("Please enter a question.");
    return;
  }

  clearQueryError();
  D.runBtn.disabled = true;
  D.runSpinner.classList.remove("hidden");
  D.resultsPanels.classList.remove("hidden");
  showLoading("Running Self-RAG pipeline...");
  setStatus("Running query...");

  try {
    const response = await fetchJson("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: question }),
      timeoutMs: 120000,
    });

    appendConversation(question, response.response);
    renderDocuments(response.documents || []);
    renderEvaluation(response.evaluation || {});

    D.queryInput.value = "";
    D.queryInput.style.height = "auto";
    setStatus("Query complete. You can ask a follow-up question.", "success");
  } catch (error) {
    showQueryError(error.message);
    setStatus("Query failed. Please try again.", "error");
  } finally {
    hideLoading();
    D.runSpinner.classList.add("hidden");
    updateRunButton();
    closeMobileSidebar();
  }
}

async function handleReset() {
  try {
    await fetchJson("/api/reset", { method: "POST", timeoutMs: 20000 });
  } catch {
    // Ignore reset failures and still clear local UI state.
  }

  D.docMeta.classList.add("hidden");
  D.docList.innerHTML = "";
  D.chunkLabel.textContent = "";
  D.fileList.innerHTML = "";
  D.pdfFiles.value = "";
  D.queryInput.value = "";
  D.queryInput.style.height = "auto";
  D.responseArea.innerHTML = "";
  D.responseArea.appendChild(D.responsePlaceholder);
  resetResultsPanels();
  clearQueryError();
  setStatus("Session reset. Upload PDFs to start again.");
  updateRunButton();
  closeMobileSidebar();
}

function setupFileUpload() {
  D.dropZone.addEventListener("click", (event) => {
    if (event.target !== D.pdfFiles) {
      D.pdfFiles.click();
    }
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    D.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      D.dropZone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    D.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      D.dropZone.classList.remove("drag-over");
    });
  });

  D.dropZone.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer.files || []).filter((file) => /\.pdf$/i.test(file.name));
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    D.pdfFiles.files = transfer.files;
    renderFileList();
  });

  D.pdfFiles.addEventListener("change", renderFileList);
}

function setupSidebarToggle() {
  D.sidebarMobileToggle.addEventListener("click", openMobileSidebar);
  D.sidebarBackdrop.addEventListener("click", closeMobileSidebar);
}

function setupQueryInput() {
  const resize = () => {
    D.queryInput.style.height = "auto";
    D.queryInput.style.height = `${Math.min(D.queryInput.scrollHeight, 220)}px`;
    updateRunButton();
  };

  D.queryInput.addEventListener("input", resize);
  D.queryInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!D.runBtn.disabled) {
        handleRunQuery();
      }
    }
  });

  resize();
}

document.addEventListener("DOMContentLoaded", async () => {
  initializeDOM();
  resetResultsPanels();

  D.newSessionBtn.addEventListener("click", handleReset);
  D.resetBtn.addEventListener("click", handleReset);
  D.processBtn.addEventListener("click", handleProcessDocuments);
  D.runBtn.addEventListener("click", handleRunQuery);

  setupFileUpload();
  setupSidebarToggle();
  setupQueryInput();

  try {
    await loadModels();
    await loadStatus();
  } catch (error) {
    showQueryError(error.message);
    setStatus("Could not load initial app state.", "error");
  }

  await checkBackendStatus();
  window.setInterval(checkBackendStatus, 10000);
});
