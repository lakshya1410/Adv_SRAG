const modelSelect = document.getElementById("model-select");
const pdfFilesInput = document.getElementById("pdf-files");
const processBtn = document.getElementById("process-btn");
const resetBtn = document.getElementById("reset-btn");
const statusBox = document.getElementById("status-box");
const backendStatus = document.getElementById("backend-status");
const docMeta = document.getElementById("doc-meta");
const docList = document.getElementById("doc-list");
const chunkLabel = document.getElementById("chunk-label");

const chatFeed = document.getElementById("chat-feed");
const chatForm = document.getElementById("chat-form");
const questionInput = document.getElementById("question-input");
const askBtn = document.getElementById("ask-btn");
const pipelineDetails = document.getElementById("pipeline-details");

function setStatus(text) {
  statusBox.textContent = text;
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  chatFeed.appendChild(div);
  chatFeed.scrollTop = chatFeed.scrollHeight;
}

function renderDetails(details) {
  const evidence = (details.evidence || [])
    .map((e) => `<li>${e}</li>`)
    .join("");
  const previews = (details.doc_previews || [])
    .map((p) => `<li>${p}</li>`)
    .join("");

  pipelineDetails.innerHTML = `
    <div class="kv"><span>Retrieval Needed</span><strong>${details.need_retrieval ? "Yes" : "No"}</strong></div>
    <div class="kv"><span>Docs Retrieved</span><strong>${details.docs_retrieved}</strong></div>
    <div class="kv"><span>Relevant Docs</span><strong>${details.relevant_docs}</strong></div>
    <div class="kv"><span>IsSUP</span><strong>${details.issup}</strong></div>
    <div class="kv"><span>IsUSE</span><strong>${details.isuse}</strong></div>
    <div class="kv"><span>Revise Loops</span><strong>${details.retries}</strong></div>
    <div class="kv"><span>Rewrite Tries</span><strong>${details.rewrite_tries}</strong></div>
    <div class="kv"><span>Usefulness Reason</span><strong>${details.use_reason || "N/A"}</strong></div>
    <p><strong>Evidence</strong></p>
    <ul class="list-small">${evidence || "<li>No evidence returned.</li>"}</ul>
    <p><strong>Doc Preview</strong></p>
    <ul class="list-small">${previews || "<li>No preview available.</li>"}</ul>
  `;
}

function renderLoadedDocs(docNames, chunkCount, modelName) {
  docList.innerHTML = "";
  for (const name of docNames) {
    const li = document.createElement("li");
    li.textContent = name;
    docList.appendChild(li);
  }
  chunkLabel.textContent = `${chunkCount} chunk(s) indexed using ${modelName}.`;
  docMeta.classList.remove("hidden");
}

async function fetchJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    throw new Error("Backend is unreachable. Start Flask with the project venv Python and refresh.");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

async function initialize() {
  try {
    const [modelsData, statusData] = await Promise.all([
      fetchJson("/api/models"),
      fetchJson("/api/status"),
    ]);

    modelSelect.innerHTML = "";
    for (const model of modelsData.models || []) {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      if (model === statusData.model_name) {
        option.selected = true;
      }
      modelSelect.appendChild(option);
    }

    backendStatus.textContent = "Backend ready";
    if (statusData.ready) {
      renderLoadedDocs(statusData.doc_names || [], statusData.chunk_count || 0, statusData.model_name || "model");
      setStatus("Knowledge base already loaded. You can ask questions.");
    } else {
      setStatus("Upload PDFs and click Process Documents.");
    }
  } catch (error) {
    backendStatus.textContent = "Backend error";
    setStatus(error.message);
  }
}

processBtn.addEventListener("click", async () => {
  const files = pdfFilesInput.files;
  if (!files || files.length === 0) {
    setStatus("Please choose at least one PDF file.");
    return;
  }

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("model_name", modelSelect.value);

  processBtn.disabled = true;
  setStatus("Processing documents. This may take a while...");

  try {
    const data = await fetchJson("/api/process-documents", {
      method: "POST",
      body: formData,
    });
    renderLoadedDocs(data.doc_names || [], data.chunk_count || 0, data.model_name || modelSelect.value);
    setStatus(data.message || "Documents processed.");
    addMessage("system", "Knowledge base ready. Ask your first question.");
  } catch (error) {
    setStatus(error.message);
  } finally {
    processBtn.disabled = false;
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = (questionInput.value || "").trim();
  if (!question) {
    return;
  }

  addMessage("user", question);
  questionInput.value = "";
  askBtn.disabled = true;

  try {
    const data = await fetchJson("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    addMessage("assistant", data.answer || "No answer found.");
    renderDetails(data.pipeline_details || {});
  } catch (error) {
    addMessage("system", error.message);
  } finally {
    askBtn.disabled = false;
  }
});

resetBtn.addEventListener("click", async () => {
  try {
    await fetchJson("/api/reset", { method: "POST" });
    docMeta.classList.add("hidden");
    docList.innerHTML = "";
    chunkLabel.textContent = "";
    pipelineDetails.textContent = "Run a query to see retrieval, grounding, and usefulness diagnostics.";
    chatFeed.innerHTML = "";
    setStatus("Session reset. Upload PDFs again.");
  } catch (error) {
    setStatus(error.message);
  }
});

initialize();
