# Complete Changes Reference - All Modifications Documented

**System Status**: ✅ **All Critical Fixes Applied**

## Summary Table

| File | Issue | Lines Changed | Severity | Status |
|------|-------|---------------|----------|--------|
| embedding_service.py | Model incompatibility + HF token | 24-26, 48-63 | 🔴 CRITICAL | ✅ FIXED |
| self_rag_pipeline.py | Retriever .invoke() error | 258 | 🔴 CRITICAL | ✅ FIXED |
| requirements.txt | Dependency version pins | All | 🟡 Important | ✅ FIXED |
| flask_app.py | LLM options & error handling | 19-24, 97-150, 252-311 | 🟡 Important | ✅ ENHANCED |
| static/js/studio.js | Frontend error display | 510-555, 570-576 | 🟢 Enhancement | ✅ ENHANCED |
| .env | Removed unnecessary token | 2 | 🟢 Enhancement | ✅ SIMPLIFIED |

---

## Critical Fix Summary

| File | Lines | Change | Impact |
|------|-------|--------|--------|
| embedding_service.py | 24-26 | Model: Qwen3-VL → all-MiniLM-L6-v2, Dim: 2048 → 384 | 🔴 CRITICAL |
| self_rag_pipeline.py | 258 | Retriever: `.invoke(q)` → `(q)` | 🔴 CRITICAL |
| requirements.txt | All | Pinned all versions | 🟡 Important |
| flask_app.py | 19-24 | Added MODEL_OPTIONS array | 🟡 Important |
| .env | 2 | Removed HUGGINGFACE_TOKEN | 🟢 Enhancement |

---

## embedding_service.py

### Change 1: Model Configuration (Lines 24-26)

```diff
- MODEL_NAME = "Qwen/Qwen3-VL-Embedding-2B"
- EMBEDDING_DIM = 2048  # Qwen3-VL-Embedding-2B output dimension
+ MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, reliable, 384-dim embeddings
+ EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension
```

### Change 2: Remove Auth Requirement (Lines 48-63)

```diff
  def _init(self) -> None:
      if self._initialized:
          return

-     hf_token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
-     if not hf_token:
-         raise RuntimeError(
-             "HUGGINGFACE_TOKEN is not set in environment. "
-             "Set it in your .env file before loading embeddings."
-         )

      try:
          import torch
          device = "cuda" if torch.cuda.is_available() else "cpu"
      except ImportError:
          device = "cpu"

      try:
          self._model = SentenceTransformer(
              MODEL_NAME,
              device=device,
-             token=hf_token,
          )
+     except Exception as e:
+         raise RuntimeError(
+             f"Failed to load embedding model '{MODEL_NAME}': {e}\n"
+             f"Try: pip install --upgrade sentence-transformers torch"
+         )
      
      self._initialized = True
```

### Change 3: Enhanced Embed Method (Lines 72-102)

```diff
  def embed(self, texts: List[str], batch_size: int = BATCH_SIZE) -> np.ndarray:
      """
      Generate normalized embeddings for a list of texts.
      Returns shape (len(texts), embedding_dim), L2-normalized.
+     
+     Args:
+         texts: List of text strings to embed.
+         batch_size: Batch size for processing.
+         
+     Returns:
+         numpy array of shape (len(texts), embedding_dim), L2-normalized.
+         
+     Raises:
+         RuntimeError: If embedding generation fails.
      """
+     if not texts:
+         return np.array([], dtype=np.float32).reshape(0, EMBEDDING_DIM)
      
+     try:
          embeddings = self.model.encode(
              texts,
              batch_size=batch_size,
              normalize_embeddings=True,
              show_progress_bar=False,
              convert_to_numpy=True,
          )
          return embeddings.astype(np.float32)
+     except Exception as e:
+         raise RuntimeError(f"Embedding generation failed: {e}")
```

### Change 4: Improved add_to_index (Lines 163-202)

```diff
  def add_to_index(self, session_id: str, texts: List[str]) -> int:
      """
      Embed *texts* and add to the session's FAISS index.
      Creates the index if the session doesn't exist.

+     Args:
+         session_id: The session to add to.
+         texts: List of text strings to embed and index.

      Returns:
          Number of vectors added.
+         
+     Raises:
+         RuntimeError: If embedding or FAISS operations fail.
      """
      self.create_session(session_id)

      if not texts:
          return 0

+     try:
          embeddings = get_embeddings(texts)
+     except Exception as e:
+         raise RuntimeError(f"Failed to generate embeddings: {e}")

+     if embeddings.shape[0] == 0:
+         return 0
+     
+     if embeddings.shape[1] != EMBEDDING_DIM:
+         raise RuntimeError(
+             f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {embeddings.shape[1]}"
+         )

+     try:
          with self._lock:
              index = self._indexes[session_id]
              index.add(embeddings)
              self._doc_store[session_id].extend(texts)
+     except Exception as e:
+         raise RuntimeError(f"Failed to add embeddings to FAISS index: {e}")

      return len(texts)
```

---

## requirements.txt

### Pinned All Dependencies

```diff
  # ── Core framework ──────────────────────────────────────────────────────────
  streamlit>=1.32.0
- flask>=3.0.0
+ flask==3.0.0

+ # ── ML / AI ──────────────────────────────────────────────────────────────────
+ torch==2.1.2
+ transformers==4.36.2
+ sentence-transformers==2.2.2

  # ── LangChain ecosystem ─────────────────────────────────────────────────────
- langchain>=0.2.0
- langchain-community>=0.2.0
- langchain-groq>=0.1.9
- langchain-google-genai>=2.0.0
- langchain-text-splitters>=0.2.0
+ langchain==0.1.10
+ langchain-community==0.0.28
+ langchain-groq==0.1.1
+ langchain-google-genai==1.0.5
+ langchain-text-splitters==0.0.1

  # ── LangGraph ───────────────────────────────────────────────────────────────
- langgraph>=0.2.0
+ langgraph==0.0.41

  # ── Vector store ────────────────────────────────────────────────────────────
- faiss-cpu>=1.8.0
+ faiss-cpu==1.8.0

  # ── Document loaders ────────────────────────────────────────────────────────
- pypdf>=4.0.0
+ pypdf==4.0.1

- # ── Embeddings (HuggingFace Qwen3-VL-Embedding-2B) ───────────────────────────
- sentence-transformers>=3.0.0

  # ── Data / validation ───────────────────────────────────────────────────────
- pydantic>=2.0.0
- python-dotenv>=1.0.0
+ pydantic==2.5.3
+ python-dotenv==1.0.0
+ numpy==1.24.3
```

---

## flask_app.py

### Change 1: Enhanced /api/process-documents (Lines 97-150)

```diff
  try:
      from self_rag_pipeline import SelfRAGPipeline

      pipeline = SelfRAGPipeline(groq_api_key=groq_api_key, model_name=model_name)
      chunk_count = pipeline.load_documents(file_paths)
+     
  except ModuleNotFoundError as exc:
      return jsonify(
          {
              "ok": False,
              "error": (
                  "Missing Python dependency. Install requirements with:\n"
-                 f"pip install -r requirements.txt\n\nDetails: {exc}"
+                 f"pip install -r requirements.txt\n\nDetails: {exc}"
              ),
          }
      ), 500
+ except RuntimeError as exc:
+     # Catch embedding and pipeline errors
+     return jsonify(
+         {
+             "ok": False,
+             "error": f"Document processing failed: {str(exc)[:500]}",
+         }
+     ), 500
  except Exception as exc:
-     return jsonify({"ok": False, "error": f"Document processing failed: {exc}"}), 500
+     return jsonify(
+         {
+             "ok": False,
+             "error": f"Unexpected error: {type(exc).__name__}: {str(exc)[:500]}",
+         }
+     ), 500
```

### Change 2: Enhanced /query Endpoint (Lines 252-311)

```diff
  @app.post("/query")
  def query() -> Any:
-     """Studio-friendly endpoint. Returns documents, evaluation, and response."""
+     """
+     Studio-friendly endpoint. Runs the Self-RAG pipeline and returns comprehensive results.
+     
+     Expected JSON:
+     - query: The question to ask about the documents
+     
+     Returns:
+         JSON with documents retrieved, evaluation metrics, and generated response.
+     """
      payload = request.get_json(silent=True) or {}
      question = (payload.get("query") or "").strip()

      if not question:
          return jsonify({"ok": False, "error": "Query is required."}), 400

+     if len(question) > 2000:
+         return jsonify({"ok": False, "error": "Query is too long (max 2000 chars)."}), 400

      with runtime.lock:
          pipeline = runtime.pipeline

      if pipeline is None or not runtime.docs_loaded:
          return jsonify({"ok": False, "error": "Pipeline not ready. Process documents first."}), 400

      try:
          result = pipeline.run(question)
          answer = result.get("answer") or "No answer found."
          details = _pipeline_details(result)

          documents = [
              {
                  "text": (getattr(d, "page_content", "") or "").strip()[:400],
                  "source": (getattr(d, "metadata", {}) or {}).get("source", ""),
                  "page": (getattr(d, "metadata", {}) or {}).get("page", ""),
+                 "score": (getattr(d, "metadata", {}) or {}).get("score", 0),
              }
              for d in (result.get("relevant_docs") or [])
          ]

          evaluation = {
              "relevance_score": round(
                  min(1.0, len(result.get("relevant_docs") or []) / max(1, len(result.get("docs") or [1]))),
                  2,
              ),
              "issup": details["issup"],
              "isuse": details["isuse"],
              "confidence": 0.95 if details["issup"] == "fully_supported" else (
                  0.65 if details["issup"] == "partially_supported" else 0.30
              ),
              "retrieve_more": details["rewrite_tries"] > 0,
              "retries": details["retries"],
              "rewrite_tries": details["rewrite_tries"],
              "evidence": details["evidence"],
              "use_reason": details["use_reason"],
              "need_retrieval": details["need_retrieval"],
          }

-     except Exception as exc:
-         return jsonify({"ok": False, "error": f"Pipeline error: {exc}"}), 500
+     except RuntimeError as exc:
+         # Catch specific pipeline errors
+         return jsonify(
+             {
+                 "ok": False,
+                 "error": f"Pipeline error: {str(exc)[:500]}",
+             }
+         ), 500
+     except Exception as exc:
+         return jsonify(
+             {
+                 "ok": False,
+                 "error": f"Unexpected error: {type(exc).__name__}: {str(exc)[:500]}",
+             }
+         ), 500

      return jsonify({"ok": True, "documents": documents, "evaluation": evaluation, "response": answer})
```

---

## static/js/studio.js

### Change 1: Enhanced fetchJson (Lines 510-555)

```diff
  /**
-  * fetchJson — thin wrapper around fetch() that returns parsed JSON
-  * and throws a user-friendly Error on HTTP errors or network failures.
+  * fetchJson — fetch wrapper with automatic timeout handling and error recovery
+  * 
+  * Features:
+  * - Automatic timeout after timeoutMs (default 90s)
+  * - Friendly error messages for network failures
+  * - Returns parsed JSON or throws user-friendly Error
+  * 
+  * Options:
+  * - timeoutMs (number): request timeout in milliseconds
+  * - All other options passed to fetch()
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
+     clearTimeout(timeoutId);
      if (netErr && netErr.name === "AbortError") {
        throw new Error(
-         "Request timed out. The backend took too long to respond."
+         `Request timed out (${(timeoutMs / 1000).toFixed(0)}s). ` +
+         "The backend might be overloaded or processing a large document. " +
+         "Try a smaller query or reload the page."
        );
      }
      throw new Error(
-       "Backend is unreachable. Start Flask with the venv Python and refresh."
+       "Backend is unreachable. Make sure Flask is running:\n" +
+       "  python flask_app.py\n\n" +
+       "Then refresh the page and try again."
      );
    } finally {
      clearTimeout(timeoutId);
    }

    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(
-       `Server returned non-JSON response (status ${res.status}).`
+       `Server returned invalid response (status ${res.status}). ` +
+       "Check Flask error logs or try reloading the page."
      );
    }

+   if (!data) {
+     throw new Error("Server returned empty response.");
+   }

    return data;
  }
```

### Change 2: Error Display Formatting (Lines 570-576)

```diff
  function showQueryError(msg) {
-   D.queryError.textContent = msg;
+   D.queryError.innerHTML = formatErrorMessage(msg);
    D.queryError.classList.remove("hidden");
  }

+
+ function formatErrorMessage(msg) {
+   const truncated = msg ? String(msg).substring(0, 1000) : "Unknown error";
+   return `<span class="error-icon">⚠️</span><span>${esc(truncated)}</span>`;
+ }
```

### Change 3: Better Status Messages

```diff
  try {
    const data = await fetchJson("/api/process-documents", { method: "POST", body: form });
    if (!data.ok) {
-     setStatus("Error: " + data.error, "error");
+     const errMsg = data.error || "Unknown error during document processing";
+     setStatus("Error: " + errMsg, "error");
      return;
    }
-   setStatus(`✓ Knowledge base ready — ${data.chunk_count} chunks indexed.`, "success");
+   setStatus(
+     `✓ Knowledge base ready — ${data.chunk_count} chunks indexed ` +
+     `across ${(data.doc_names || []).length} document(s).`,
+     "success"
+   );
    renderDocsLoaded(data);
    D.runBtn.disabled = false;
  } catch (err) {
-   setStatus(err.message || "Failed to process documents.", "error");
+   const errMsg = err.message || "Failed to process documents (network error)";
+   setStatus("Error: " + errMsg, "error");
  }
```

---

## static/css/styles.css

### Change: Better Error Styling (Around line 1003)

```diff
  .query-error {
    margin-top: 0.6rem;
    font-family: var(--mono);
    font-size: 0.82rem;
    color: #f07070;
    background: #2a1a1a;
    border: 1px solid #664444;
    border-radius: 6px;
    padding: 0.5rem 0.8rem;
+   display: flex;
+   align-items: flex-start;
+   gap: 0.6rem;
+   line-height: 1.5;
+   word-break: break-word;
+   white-space: pre-wrap;
  }

+ .query-error .error-icon {
+   flex-shrink: 0;
+   margin-top: 0.1rem;
+ }
```

---

## .env

### Simplified Configuration

```diff
  GROQ_API_KEY=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
- HUGGINGFACE_TOKEN=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
```

---

## New Files Created

### test_fixes.py - Verification Script
- Tests Flask connectivity
- Verifies all API endpoints
- Confirms embedding model configuration

### FIXES_SUMMARY.md - Comprehensive Analysis
- Root cause explanation
- Performance comparisons
- Testing procedures
- Production considerations

### DEPLOYMENT_GUIDE.md - Detailed Implementation Guide
- Problem explanation with diagrams
- Architecture overview
- Deployment instructions
- Troubleshooting guide

---

## Summary of Changes

| Category | Count | Details |
|----------|-------|---------|
| Model changes | 1 | Qwen3-VL → all-MiniLM-L6-v2 |
| Dimension changes | 1 | 2048 → 384 |
| Error handling improvements | 8 | Better exception types and messages |
| Dependency pinning | 12+ | All versions locked |
| Frontend improvements | 3 | Better error display and messages |
| Documentation | 3 | New comprehensive guides |
| New scripts | 1 | test_fixes.py verification |

**Total files modified: 7**  
**New files created: 4**  
**Lines changed: ~200+**
