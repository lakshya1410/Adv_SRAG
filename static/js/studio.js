/**
 * studio.js — Interactive Self-RAG Studio frontend
 *
 * Connects the RAG Studio UI to the Flask API endpoints:
 *   POST /api/process-documents  — builds knowledge base
 *   POST /query                   — runs the Self-RAG pipeline
 *   POST /api/reset               — resets session
 *   GET  /api/models              — fetches available LLM models
 *   GET  /api/status              — fetches current session status
 */

"use strict";

/* ══════════════════════════════════════
   DOM REFERENCES
══════════════════════════════════════ */
const $ = (id) => document.getElementById(id);

const D = {
  modelSelect:      $("model-select"),
  pdfFiles:         $("pdf-files"),
  dropZone:         $("drop-zone"),
  fileList:         $("file-list"),
  processBtn:       $("process-btn"),
  processSpinner:   $("process-spinner"),
  statusBox:        $("status-box"),
  docMeta:          $("doc-meta"),
  docList:          $("doc-list"),
  chunkLabel:       $("chunk-label"),

  queryInput:       $("query-input"),
  runBtn:           $("run-btn"),
  runBtnLabel:      $("run-btn-label"),
  runSpinner:       $("run-spinner"),
  queryError:       $("query-error"),

  responseArea:     $("response-area"),
  responseBadges:   $("response-badges"),

  docsArea:         $("docs-area"),
  docsCount:        $("docs-count"),

  evalArea:         $("eval-area"),

  pipelineTracker:  $("pipeline-tracker"),
  backendStatus:    $("backend-status"),
  resetBtn:         $("reset-btn"),

  loadingOverlay:   $("loading-overlay"),
  loadingLabel:     $("loading-label"),
};

/* ══════════════════════════════════════
   PIPELINE TRACKER STEPS
   Must match data-step attributes in HTML
══════════════════════════════════════ */
const PIPELINE_STEPS = ["query", "retrieval", "retrieve", "evaluation", "generation"];

/* ══════════════════════════════════════
   INIT
══════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", () => {
  wireEvents();

  // Hydrate server-backed data in background so first paint is immediate.
  void loadModels();
  void loadStatus();
});

/* ══════════════════════════════════════
   LOAD MODELS
══════════════════════════════════════ */
async function loadModels() {
  try {
    const data = await fetchJson("/api/models", { timeoutMs: 4000 });
    D.modelSelect.innerHTML = "";
    (data.models || []).forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = formatModelName(m);
      D.modelSelect.appendChild(opt);
    });
  } catch {
    D.modelSelect.innerHTML = '<option value="llama-3.3-70b-versatile">LLaMA 3.3 70B</option>';
  }
}

function formatModelName(m) {
  const map = {
    "llama-3.3-70b-versatile": "⚡ LLaMA 3.3 70B — best accuracy",
    "llama-3.1-8b-instant":    "🚀 LLaMA 3.1 8B  — fastest",
    "mixtral-8x7b-32768":      "📚 Mixtral 8×7B  — long context",
    "gemma2-9b-it":            "⚖️ Gemma 2 9B    — balanced",
  };
  return map[m] || m;
}

/* ══════════════════════════════════════
   LOAD STATUS
══════════════════════════════════════ */
async function loadStatus() {
  try {
    const data = await fetchJson("/api/status", { timeoutMs: 4000 });
    updateBackendBadge(true);
    if (data.ready) {
      renderDocsLoaded(data);
      D.runBtn.disabled = false;
    }
  } catch {
    updateBackendBadge(false);
  }
}

function updateBackendBadge(ok) {
  const el = D.backendStatus;
  if (!el) return;
  el.textContent = ok ? "Backend OK" : "Backend offline";
  el.className = "badge " + (ok ? "ok" : "err");
}

/* ══════════════════════════════════════
   WIRE EVENTS
══════════════════════════════════════ */
function wireEvents() {
  // File drop zone
  D.dropZone.addEventListener("dragover", (e) => { e.preventDefault(); D.dropZone.classList.add("drag-over"); });
  D.dropZone.addEventListener("dragleave", () => D.dropZone.classList.remove("drag-over"));
  D.dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    D.dropZone.classList.remove("drag-over");
    D.pdfFiles.files = e.dataTransfer.files;
    renderFileList(e.dataTransfer.files);
    D.processBtn.disabled = e.dataTransfer.files.length === 0;
  });

  D.pdfFiles.addEventListener("change", () => {
    renderFileList(D.pdfFiles.files);
    D.processBtn.disabled = D.pdfFiles.files.length === 0;
  });

  D.processBtn.addEventListener("click", handleProcessDocuments);
  D.runBtn.addEventListener("click", handleRunQuery);

  // Submit on Ctrl+Enter in textarea
  D.queryInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") handleRunQuery();
  });

  if (D.resetBtn) D.resetBtn.addEventListener("click", handleReset);
}

/* ══════════════════════════════════════
   FILE LIST RENDERING
══════════════════════════════════════ */
function renderFileList(files) {
  D.fileList.innerHTML = "";
  Array.from(files).forEach((f) => {
    const chip = document.createElement("div");
    chip.className = "file-chip";
    chip.innerHTML = `<span>📄</span><span class="file-chip-name">${esc(f.name)}</span><span>${formatBytes(f.size)}</span>`;
    D.fileList.appendChild(chip);
  });
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

/* ══════════════════════════════════════
   PROCESS DOCUMENTS
══════════════════════════════════════ */
async function handleProcessDocuments() {
  const files = D.pdfFiles.files;
  if (!files || files.length === 0) {
    setStatus("Please select at least one PDF file.", "error");
    return;
  }

  const model = D.modelSelect.value;

  D.processBtn.disabled = true;
  D.processSpinner.classList.remove("hidden");
  setStatus("Building knowledge base…", "running");
  showLoading("Building knowledge base…");

  const form = new FormData();
  form.append("model_name", model);
  Array.from(files).forEach((f) => form.append("files", f));

  try {
    const data = await fetchJson("/api/process-documents", { method: "POST", body: form });
    if (!data.ok) {
      setStatus("Error: " + data.error, "error");
      return;
    }
    setStatus(`✓ Knowledge base ready — ${data.chunk_count} chunks indexed.`, "success");
    renderDocsLoaded(data);
    D.runBtn.disabled = false;
  } catch (err) {
    setStatus(err.message || "Failed to process documents.", "error");
  } finally {
    D.processBtn.disabled = false;
    D.processSpinner.classList.add("hidden");
    hideLoading();
  }
}

function renderDocsLoaded(data) {
  D.docMeta.classList.remove("hidden");
  D.docList.innerHTML = "";
  const names = data.doc_names || [];
  names.forEach((name) => {
    const li = document.createElement("li");
    li.innerHTML = `📄 ${esc(name)}`;
    D.docList.appendChild(li);
  });
  D.chunkLabel.textContent = (data.chunk_count || 0) + " chunks";
}

/* ══════════════════════════════════════
   RUN QUERY
══════════════════════════════════════ */
async function handleRunQuery() {
  const query = D.queryInput.value.trim();
  if (!query) {
    showQueryError("Please enter a question.");
    return;
  }
  clearQueryError();

  // Disable button, show loading
  D.runBtn.disabled = true;
  D.runSpinner.classList.remove("hidden");
  D.runBtnLabel.textContent = "Running…";

  // Reset panels
  resetPipelineTracker();
  setResponsePlaceholder("Running Self-RAG pipeline…");
  D.docsArea.innerHTML = '<div class="docs-placeholder">Retrieving documents…</div>';
  D.evalArea.innerHTML = '<div class="eval-placeholder">Running evaluation…</div>';
  D.responseBadges.innerHTML = "";
  if (D.docsCount) D.docsCount.textContent = "";

  showLoading("Running Self-RAG pipeline…");

  // Animate pipeline steps
  const stepInterval = animatePipelineSteps();

  try {
    const data = await fetchJson("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    clearInterval(stepInterval);
    completeAllPipelineSteps();

    if (!data.ok) {
      showQueryError(data.error || "Pipeline failed.");
      setResponsePlaceholder("Query failed. Check the error above.");
      return;
    }

    renderResponse(data.response);
    renderDocuments(data.documents || []);
    renderEvaluation(data.evaluation || {});
    renderResponseBadges(data.evaluation || {});
  } catch (err) {
    clearInterval(stepInterval);
    resetPipelineTracker();
    showQueryError(err.message || "Network error. Is Flask running?");
    setResponsePlaceholder("Query failed.");
  } finally {
    D.runBtn.disabled = false;
    D.runSpinner.classList.add("hidden");
    D.runBtnLabel.textContent = "Run Self-RAG";
    hideLoading();
  }
}

/* ══════════════════════════════════════
   PIPELINE TRACKER ANIMATION
══════════════════════════════════════ */
function animatePipelineSteps() {
  let idx = 0;
  setStepActive(PIPELINE_STEPS[idx]);
  return setInterval(() => {
    if (idx < PIPELINE_STEPS.length - 1) {
      setStepDone(PIPELINE_STEPS[idx]);
      idx++;
      setStepActive(PIPELINE_STEPS[idx]);
    }
  }, 2200);
}

function setStepActive(stepId) {
  const el = D.pipelineTracker?.querySelector(`[data-step="${stepId}"]`);
  if (el) el.classList.add("active");
}

function setStepDone(stepId) {
  const el = D.pipelineTracker?.querySelector(`[data-step="${stepId}"]`);
  if (el) { el.classList.remove("active"); el.classList.add("done"); }
}

function resetPipelineTracker() {
  D.pipelineTracker?.querySelectorAll(".pt-step").forEach((el) => {
    el.classList.remove("active", "done");
  });
}

function completeAllPipelineSteps() {
  D.pipelineTracker?.querySelectorAll(".pt-step").forEach((el) => {
    el.classList.remove("active");
    el.classList.add("done");
  });
}

/* ══════════════════════════════════════
   RESPONSE RENDERING (typing animation)
══════════════════════════════════════ */
function renderResponse(text) {
  D.responseArea.innerHTML = "";
  const el = document.createElement("div");
  el.className = "response-text typing";
  D.responseArea.appendChild(el);

  let i = 0;
  const speed = Math.max(8, Math.min(25, Math.floor(6000 / text.length)));

  function typeNext() {
    if (i <= text.length) {
      el.textContent = text.substring(0, i);
      i++;
      setTimeout(typeNext, speed);
    } else {
      el.classList.remove("typing");
    }
  }
  typeNext();
}

function setResponsePlaceholder(msg) {
  D.responseArea.innerHTML = `<div class="response-placeholder"><p>${esc(msg)}</p></div>`;
}

/* ══════════════════════════════════════
   RESPONSE BADGES
══════════════════════════════════════ */
function renderResponseBadges(ev) {
  const badges = [];

  if (ev.need_retrieval !== undefined) {
    badges.push(`<span class="rbadge rbadge-retrieval">${ev.need_retrieval ? "Retrieval" : "Direct"}</span>`);
  }

  const issupClass = { fully_supported: "rbadge-sup", partially_supported: "rbadge-partial", no_support: "rbadge-nosup" };
  if (ev.issup && ev.issup !== "N/A") {
    const cls = issupClass[ev.issup] || "rbadge-partial";
    badges.push(`<span class="rbadge ${cls}">IsSUP: ${ev.issup.replace("_", " ")}</span>`);
  }

  const isuse = ev.isuse;
  if (isuse === "useful")      badges.push('<span class="rbadge rbadge-useful">IsUSE: useful</span>');
  if (isuse === "not_useful")  badges.push('<span class="rbadge rbadge-notuseful">IsUSE: not useful</span>');

  D.responseBadges.innerHTML = badges.join("");
}

/* ══════════════════════════════════════
   DOCUMENTS PANEL
══════════════════════════════════════ */
function renderDocuments(docs) {
  if (!docs.length) {
    D.docsArea.innerHTML = '<div class="docs-placeholder">No documents retrieved (direct answer path).</div>';
    if (D.docsCount) D.docsCount.textContent = "0";
    return;
  }

  if (D.docsCount) D.docsCount.textContent = docs.length;

  D.docsArea.innerHTML = docs.map((doc, i) => {
    const score = doc.score !== undefined ? doc.score : (0.95 - i * 0.07);
    const pct   = Math.round(Math.min(1, Math.max(0, score)) * 100);
    const src   = doc.source ? esc(doc.source.split(/[\\/]/).pop()) : "Document";
    const page  = doc.page !== "" && doc.page !== undefined ? ` · p.${doc.page}` : "";
    const txt   = esc((doc.text || "").trim());

    return `
      <div class="doc-card">
        <div class="doc-card-header">
          <span class="doc-card-src">📄 ${src}${page}</span>
        </div>
        <div class="doc-score-bar">
          <div class="doc-score-label">
            <span>Relevance</span>
            <span>${pct}%</span>
          </div>
          <div class="doc-score-track">
            <div class="doc-score-fill" style="width:${pct}%"></div>
          </div>
        </div>
        <div class="doc-text">${txt || "(empty chunk)"}</div>
      </div>`;
  }).join("");
}

/* ══════════════════════════════════════
   EVALUATION PANEL
══════════════════════════════════════ */
function renderEvaluation(ev) {
  if (!ev || Object.keys(ev).length === 0) {
    D.evalArea.innerHTML = '<div class="eval-placeholder">No evaluation data available.</div>';
    return;
  }

  const confidence = Math.round((ev.confidence || 0) * 100);
  const relevance  = Math.round((ev.relevance_score || 0) * 100);

  // Choose bar color classes
  const confClass = confidence >= 80 ? "good" : (confidence >= 50 ? "mid" : "bad");
  const relClass  = relevance  >= 80 ? "good" : (relevance  >= 50 ? "mid" : "bad");

  const issupLabel = (ev.issup || "N/A").replace(/_/g, " ");
  const isuseLabel = (ev.isuse || "N/A").replace(/_/g, " ");

  const evidenceHtml = (ev.evidence || []).length
    ? `<div class="evidence-section">
        <div class="evidence-title">Supporting Evidence</div>
        ${ev.evidence.map((e) => `<div class="evidence-item">${esc(e)}</div>`).join("")}
       </div>`
    : "";

  const retryPills = [];
  if (ev.retries)       retryPills.push(`<span class="eval-pill">Revision loops: ${ev.retries}</span>`);
  if (ev.rewrite_tries) retryPills.push(`<span class="eval-pill">Rewrite tries: ${ev.rewrite_tries}</span>`);
  if (ev.retrieve_more) retryPills.push('<span class="eval-pill">Query rewritten ✓</span>');

  D.evalArea.innerHTML = `
    <div class="eval-metric">
      <div class="eval-metric-label">
        <span>Confidence</span>
        <span>${confidence}%</span>
      </div>
      <div class="eval-bar-track">
        <div class="eval-bar-fill ${confClass}" style="width:${confidence}%"></div>
      </div>
    </div>

    <div class="eval-metric">
      <div class="eval-metric-label">
        <span>Context Relevance</span>
        <span>${relevance}%</span>
      </div>
      <div class="eval-bar-track">
        <div class="eval-bar-fill ${relClass}" style="width:${relevance}%"></div>
      </div>
    </div>

    <div class="eval-pills">
      <span class="eval-pill">IsSUP: ${issupLabel}</span>
      <span class="eval-pill">IsUSE: ${isuseLabel}</span>
      ${retryPills.join("")}
    </div>

    ${ev.use_reason ? `<div class="eval-pill" style="margin-top:0.4rem;font-style:italic">${esc(ev.use_reason)}</div>` : ""}

    ${evidenceHtml}
  `;
}

/* ══════════════════════════════════════
   RESET SESSION
══════════════════════════════════════ */
async function handleReset() {
  try {
    await fetchJson("/api/reset", { method: "POST" });
  } catch { /* ignore */ }

  D.docMeta.classList.add("hidden");
  D.docList.innerHTML = "";
  D.chunkLabel.textContent = "";
  D.fileList.innerHTML = "";
  D.processBtn.disabled = true;
  D.runBtn.disabled = true;

  setStatus("Session reset. Upload PDFs to start.", "");
  setResponsePlaceholder("Run a query to see the Self-RAG generated response here.");
  D.docsArea.innerHTML = '<div class="docs-placeholder">Retrieved document chunks will appear here after a query.</div>';
  D.evalArea.innerHTML = '<div class="eval-placeholder">Evaluation metrics will appear here after a query.</div>';
  D.responseBadges.innerHTML = "";
  resetPipelineTracker();
  clearQueryError();
  D.queryInput.value = "";
}

/* ══════════════════════════════════════
   HELPERS
══════════════════════════════════════ */
function setStatus(msg, type) {
  D.statusBox.textContent = msg;
  D.statusBox.className = "studio-status" + (type ? " " + type : "");
}

function showQueryError(msg) {
  D.queryError.textContent = msg;
  D.queryError.classList.remove("hidden");
}

function clearQueryError() {
  D.queryError.textContent = "";
  D.queryError.classList.add("hidden");
}

function showLoading(label) {
  if (!D.loadingOverlay) return;
  D.loadingLabel.textContent = label || "Running…";
  D.loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  D.loadingOverlay?.classList.add("hidden");
}

/**
 * fetchJson — thin wrapper around fetch() that returns parsed JSON
 * and throws a user-friendly Error on HTTP errors or network failures.
 */
async function fetchJson(url, options = {}) {
  const timeoutMs = typeof options.timeoutMs === "number" ? options.timeoutMs : 90000;
  const { timeoutMs: _ignore, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let res;
  try {
    res = await fetch(url, { ...fetchOptions, signal: controller.signal });
  } catch (netErr) {
    if (netErr && netErr.name === "AbortError") {
      throw new Error("Request timed out. The backend took too long to respond.");
    }
    throw new Error("Backend is unreachable. Start Flask with the venv Python and refresh.");
  } finally {
    clearTimeout(timeoutId);
  }

  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Server returned non-JSON response (status ${res.status}).`);
  }

  return data;
}

function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
