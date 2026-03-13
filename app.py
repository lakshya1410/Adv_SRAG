"""
app.py  –  Streamlit UI for the Self-RAG pipeline
──────────────────────────────────────────────────
Run:
    streamlit run app.py
"""

import os
import tempfile

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from self_rag_pipeline import SelfRAGPipeline

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Self-RAG · Groq",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f0f1a 0%, #1a1a2e 100%);
    border-right: 1px solid #2a2a4a;
}
[data-testid="stSidebar"] .stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99,102,241,0.4);
}

/* ── Main header ── */
.main-header {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.6rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}
.sub-caption {
    color: #94a3b8;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* ── Status bar ── */
.status-bar {
    background: linear-gradient(90deg, #1e1b4b 0%, #1e3a5f 100%);
    border: 1px solid #3730a3;
    border-radius: 12px;
    padding: 0.75rem 1.2rem;
    display: flex;
    gap: 1.5rem;
    align-items: center;
    margin-bottom: 1rem;
    font-size: 0.9rem;
}
.status-pill {
    background: rgba(99,102,241,0.2);
    border: 1px solid #6366f1;
    border-radius: 20px;
    padding: 0.2rem 0.75rem;
    color: #a5b4fc;
    font-weight: 600;
}

/* ── Pipeline detail cards ── */
.metric-card {
    background: #1e1e2e;
    border: 1px solid #2d2d4e;
    border-radius: 10px;
    padding: 0.6rem 1rem;
    text-align: center;
}

/* ── Welcome cards ── */
.node-card {
    background: #1a1a2e;
    border-left: 3px solid #6366f1;
    border-radius: 0 8px 8px 0;
    padding: 0.5rem 1rem;
    margin-bottom: 0.4rem;
    font-size: 0.88rem;
}

/* ── Chat bubbles ── */
[data-testid="stChatMessage"] {
    border-radius: 12px;
    margin-bottom: 0.5rem;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    font-weight: 600;
    color: #a5b4fc !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
for key, default in {
    "messages": [],
    "pipeline": None,
    "docs_loaded": False,
    "doc_names": [],
    "chunk_count": 0,
    "show_graph": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helper – render pipeline execution details ────────────────────────────────
def show_pipeline_details(details: dict):
    with st.expander("🔍 Pipeline Execution Details", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Retrieval", "Yes ✅" if details.get("need_retrieval") else "No ⛔")
        c2.metric("Docs Retrieved", len(details.get("docs") or []))
        c3.metric("Relevant Docs",  len(details.get("relevant_docs") or []))
        c4.metric("Revise Loops",   details.get("retries", 0))

        issup_val = details.get("issup") or "N/A"
        isuse_val = details.get("isuse") or "N/A"
        issup_color = {"fully_supported": "✅", "partially_supported": "⚠️", "no_support": "❌"}.get(issup_val, "")
        isuse_color = {"useful": "✅", "not_useful": "❌"}.get(isuse_val, "")

        d1, d2, d3 = st.columns(3)
        d1.metric("IsSUP", f"{issup_color} {issup_val}")
        d2.metric("IsUSE", f"{isuse_color} {isuse_val}")
        d3.metric("Rewrite Tries", details.get("rewrite_tries", 0))

        if details.get("evidence"):
            st.markdown("**📎 Supporting Evidence**")
            for e in details["evidence"]:
                st.markdown(
                    f'<div style="border-left:3px solid #6366f1;padding:0.4rem 0.8rem;'
                    f'background:#1e1b4b;border-radius:0 6px 6px 0;margin:0.3rem 0;'
                    f'font-size:0.85rem;color:#c7d2fe">{e}</div>',
                    unsafe_allow_html=True,
                )

        if details.get("use_reason"):
            st.markdown(
                f'<div style="background:#1e2d1e;border:1px solid #166534;border-radius:8px;'
                f'padding:0.5rem 1rem;color:#86efac;font-size:0.85rem;margin-top:0.5rem">'
                f'💬 <b>Usefulness reason:</b> {details["use_reason"]}</div>',
                unsafe_allow_html=True,
            )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        st.error("GROQ_API_KEY environment variable is not set.")
        st.stop()

    st.markdown(
        '<div style="background:#1e2d1e;border:1px solid #166534;border-radius:8px;'
        'padding:0.4rem 0.8rem;color:#86efac;font-size:0.8rem;margin-bottom:0.8rem">'
        '🔑 Groq API key loaded from environment</div>',
        unsafe_allow_html=True,
    )

    model_labels = {
        "llama-3.3-70b-versatile": "⚡ LLaMA 3.3 70B — best accuracy",
        "llama-3.1-8b-instant":    "🚀 LLaMA 3.1 8B  — fastest",
        "mixtral-8x7b-32768":      "📚 Mixtral 8×7B  — long context",
        "gemma2-9b-it":            "⚖️ Gemma 2 9B    — balanced",
    }
    selected_model: str = st.selectbox(
        "🧠 Groq Model",
        options=list(model_labels.keys()),
        format_func=lambda k: model_labels[k],
    )

    st.divider()
    st.markdown("### 📄 Knowledge Base")
    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more PDFs to build the knowledge base.",
        label_visibility="collapsed",
    )

    can_process = bool(uploaded_files)
    process_btn = st.button(
        "🔄 Process Documents",
        type="primary",
        use_container_width=True,
        disabled=not can_process,
    )

    if process_btn and can_process:
        temp_dir = tempfile.mkdtemp()
        file_paths = []
        for uf in uploaded_files:
            dest = os.path.join(temp_dir, uf.name)
            with open(dest, "wb") as fh:
                fh.write(uf.getbuffer())
            file_paths.append(dest)

        with st.spinner("🔧 Initialising pipeline…"):
            try:
                pipeline = SelfRAGPipeline(groq_api_key=groq_api_key, model_name=selected_model)
            except Exception as exc:
                st.error(f"Pipeline init failed: {exc}")
                st.stop()

        with st.spinner("🧮 Embedding documents…"):
            try:
                chunk_count = pipeline.load_documents(file_paths)
            except Exception as exc:
                st.error(f"Document indexing failed: {exc}")
                st.stop()

        st.session_state.pipeline    = pipeline
        st.session_state.docs_loaded = True
        st.session_state.doc_names   = [uf.name for uf in uploaded_files]
        st.session_state.chunk_count = chunk_count
        st.session_state.messages    = []
        st.session_state.show_graph  = False
        st.success(f"✅ Indexed **{chunk_count}** chunks from **{len(uploaded_files)}** file(s).")

    if st.session_state.docs_loaded:
        st.markdown("---")
        st.markdown("**📚 Loaded files**")
        for name in st.session_state.doc_names:
            st.markdown(
                f'<div style="background:#1a1a2e;border-radius:6px;padding:0.35rem 0.7rem;'
                f'margin:0.25rem 0;font-size:0.82rem;color:#a5b4fc">📄 {name}</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div style="text-align:center;color:#64748b;font-size:0.78rem;margin-top:0.3rem">'
            f'{st.session_state.chunk_count} chunks · {selected_model.split("-")[0].upper()}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        with col_b:
            graph_label = "🗺️ Hide Graph" if st.session_state.get("show_graph") else "🗺️ Show Graph"
            if st.button(graph_label, use_container_width=True):
                st.session_state["show_graph"] = not st.session_state.get("show_graph", False)
                st.rerun()


# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🤖 Self-RAG Pipeline</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-caption">Adaptive RAG &nbsp;·&nbsp; IsSUP grounding verification &nbsp;·&nbsp; '
    'IsUSE usefulness check &nbsp;·&nbsp; automatic query rewriting &nbsp;·&nbsp; Powered by Groq</div>',
    unsafe_allow_html=True,
)

# ── Welcome screen ────────────────────────────────────────────────────────────
if not st.session_state.docs_loaded:
    st.markdown("---")
    cols = st.columns([1, 1])
    with cols[0]:
        st.markdown("### 🚀 Get Started")
        st.markdown(
            "1. **Select** a Groq model in the sidebar\n"
            "2. **Upload** one or more PDF files\n"
            "3. Click **Process Documents**\n"
            "4. **Ask** anything about your documents"
        )
    with cols[1]:
        st.markdown("### 🔄 Pipeline Nodes")
        nodes = [
            ("1", "Decide Retrieval", "Is external context needed?"),
            ("2", "Generate Direct",  "Answer from LLM knowledge"),
            ("3", "Retrieve",         "FAISS top-k chunk search"),
            ("4", "Relevance Filter", "Keep only on-topic chunks"),
            ("5", "Generate",         "Grounded answer from context"),
            ("6", "IsSUP",            "Verify every claim is supported"),
            ("7", "Revise",           "Quote-only revision if needed"),
            ("8", "IsUSE",            "Did we actually answer?"),
            ("9", "Rewrite & Retry",  "Smarter query + re-retrieve"),
        ]
        for num, name, desc in nodes:
            st.markdown(
                f'<div class="node-card"><span style="color:#6366f1;font-weight:700">{num}.</span> '
                f'<b>{name}</b> <span style="color:#64748b">— {desc}</span></div>',
                unsafe_allow_html=True,
            )
    st.stop()

# ── Status bar ────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="status-bar">'
    f'<span class="status-pill">📚 {len(st.session_state.doc_names)} doc(s)</span>'
    f'<span class="status-pill">🧩 {st.session_state.chunk_count} chunks</span>'
    f'<span class="status-pill">🧠 {selected_model}</span>'
    f'<span class="status-pill">💬 {len(st.session_state.messages)//2} turns</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Pipeline graph ────────────────────────────────────────────────────────────
if st.session_state.get("show_graph") and st.session_state.pipeline:
    with st.expander("🗺️ Pipeline State Graph", expanded=True):
        try:
            mermaid_src = st.session_state.pipeline.app.get_graph().draw_mermaid()
            html = f"""
            <html><body style="background:#0f0f1a;margin:0;padding:12px;">
            <pre class="mermaid" style="background:transparent;">{mermaid_src}</pre>
            <script type="module">
              import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
              mermaid.initialize({{startOnLoad:true, theme:'dark',
                themeVariables:{{primaryColor:'#6366f1',primaryTextColor:'#e2e8f0',
                  primaryBorderColor:'#4f46e5',lineColor:'#94a3b8',
                  secondaryColor:'#1e1b4b',tertiaryColor:'#0f0f1a'}}}});
            </script>
            </body></html>
            """
            st.components.v1.html(html, height=720, scrolling=True)
        except Exception as exc:
            st.warning(f"Could not render graph: {exc}")

# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("pipeline_details"):
            show_pipeline_details(msg["pipeline_details"])

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask a question about your documents…")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown(
            '<div style="color:#94a3b8;font-size:0.9rem">⏳ Running Self-RAG pipeline…</div>',
            unsafe_allow_html=True,
        )

        try:
            result = st.session_state.pipeline.run(user_input)
            answer = result.get("answer") or "No answer found."

            pipeline_details = {
                "need_retrieval": result.get("need_retrieval"),
                "docs":           result.get("docs",          []),
                "relevant_docs":  result.get("relevant_docs", []),
                "issup":          result.get("issup",         ""),
                "isuse":          result.get("isuse",         ""),
                "retries":        result.get("retries",        0),
                "rewrite_tries":  result.get("rewrite_tries",  0),
                "evidence":       result.get("evidence",       []),
                "use_reason":     result.get("use_reason",    ""),
            }

            placeholder.empty()
            st.write(answer)
            show_pipeline_details(pipeline_details)

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "pipeline_details": pipeline_details,
            })

        except Exception as exc:
            placeholder.empty()
            err = f"⚠️ Pipeline error: {exc}"
            st.error(err)
            st.session_state.messages.append({"role": "assistant", "content": err})


# ── Session state defaults ────────────────────────────────────────────────────
for key, default in {
    "messages": [],
    "pipeline": None,
    "docs_loaded": False,
    "doc_names": [],
    "chunk_count": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helper – render pipeline execution details ────────────────────────────────
def show_pipeline_details(details: dict):
    with st.expander("🔍 Pipeline Execution Details", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Retrieval Needed",   "✅ Yes" if details.get("need_retrieval") else "⛔ No")
            st.metric("Docs Retrieved",     len(details.get("docs")          or []))
            st.metric("Relevant Docs",      len(details.get("relevant_docs") or []))

        with col2:
            issup_val = details.get("issup") or "N/A"
            isuse_val = details.get("isuse") or "N/A"
            issup_icon = {
                "fully_supported":     "✅",
                "partially_supported": "⚠️",
                "no_support":          "❌",
            }.get(issup_val, "")
            isuse_icon = {"useful": "✅", "not_useful": "❌"}.get(isuse_val, "")

            st.metric("IsSUP",          f"{issup_icon} {issup_val}")
            st.metric("IsUSE",          f"{isuse_icon} {isuse_val}")
            st.metric("Revise Retries", details.get("retries",       0))
            st.metric("Rewrite Tries",  details.get("rewrite_tries", 0))

        if details.get("evidence"):
            st.markdown("**Supporting Evidence:**")
            for e in details["evidence"]:
                st.markdown(f"> {e}")

        if details.get("use_reason"):
            st.markdown(f"**Usefulness Reason:** {details['use_reason']}")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")

    # Use key from environment variable
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        st.error("GROQ_API_KEY environment variable is not set.")
        st.stop()

    model_labels = {
        "llama-3.3-70b-versatile": "LLaMA 3.3 70B  (best accuracy)",
        "llama-3.1-8b-instant":    "LLaMA 3.1 8B   (fastest)",
        "mixtral-8x7b-32768":      "Mixtral 8×7B   (long context)",
        "gemma2-9b-it":            "Gemma 2 9B     (balanced)",
    }
    selected_model: str = st.selectbox(
        "Groq Model",
        options=list(model_labels.keys()),
        format_func=lambda k: model_labels[k],
    )

    st.divider()

    # ── Document upload ───────────────────────────────────────────────────────
    st.subheader("📄 Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more company PDFs to build the knowledge base.",
    )

    can_process = bool(uploaded_files)
    process_btn = st.button(
        "🔄 Process Documents",
        type="primary",
        use_container_width=True,
        disabled=not can_process,
    )

    if process_btn and can_process:
        # ── Step 1: save uploads to a temp directory ──────────────────────────
        temp_dir = tempfile.mkdtemp()
        file_paths = []
        for uf in uploaded_files:
            dest = os.path.join(temp_dir, uf.name)
            with open(dest, "wb") as fh:
                fh.write(uf.getbuffer())
            file_paths.append(dest)

        # ── Step 2: initialise pipeline (loads LLM chains) ────────────────────
        with st.spinner("Initialising Groq pipeline..."):
            try:
                pipeline = SelfRAGPipeline(
                    groq_api_key=groq_api_key,
                    model_name=selected_model,
                )
            except Exception as exc:
                st.error(f"Pipeline init failed: {exc}")
                st.stop()

        # ── Step 3: embed & index documents ───────────────────────────────────
        with st.spinner("Embedding documents (sentence-transformer)…"):
            try:
                chunk_count = pipeline.load_documents(file_paths)
            except Exception as exc:
                st.error(f"Document indexing failed: {exc}")
                st.stop()

        # ── Persist in session state ───────────────────────────────────────────
        st.session_state.pipeline    = pipeline
        st.session_state.docs_loaded = True
        st.session_state.doc_names   = [uf.name for uf in uploaded_files]
        st.session_state.chunk_count = chunk_count
        st.session_state.messages    = []   # reset chat on new knowledge base

        st.success(
            f"✅ Indexed **{chunk_count}** chunks from **{len(uploaded_files)}** document(s)."
        )

    # ── Loaded-docs summary + clear-chat ──────────────────────────────────────
    if st.session_state.docs_loaded:
        st.divider()
        st.success(
            "📚 **Loaded documents:**\n\n"
            + "\n".join(f"- {n}" for n in st.session_state.doc_names)
        )
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.divider()
        if st.button("🗺️ Show Pipeline Graph", use_container_width=True):
            st.session_state["show_graph"] = not st.session_state.get("show_graph", False)


# ── Main area ─────────────────────────────────────────────────────────────────
st.title("🤖 Self-RAG Pipeline with Groq")
st.caption(
    "Adaptive RAG · self-grounding verification (IsSUP) · "
    "usefulness check (IsUSE) · automatic query rewriting"
)

# ── Welcome / instructions (shown before documents are loaded) ────────────────
if not st.session_state.docs_loaded:
    st.info(
        "👈 **Get started:** enter your Groq API key, upload PDF documents, "
        "then click **Process Documents**."
    )
    st.markdown(
        """
        ---
        ### How the pipeline works

        | # | Node | What it does |
        |---|------|-------------|
        | 1 | **Decide Retrieval** | Decides if external docs are needed for the question |
        | 2 | **Generate Direct** | Answers from Groq's general knowledge (no-retrieval path) |
        | 3 | **Retrieve** | Fetches top-4 chunks from the FAISS vector store |
        | 4 | **Relevance Filter** | Keeps only chunks topically relevant to the question |
        | 5 | **Generate from Context** | Produces a grounded answer from filtered chunks |
        | 6 | **IsSUP** | Verifies every claim is supported by the context |
        | 7 | **Revise** | If partially/un-supported, rewrites answer as direct quotes |
        | 8 | **IsUSE** | Checks whether the answer actually addresses the question |
        | 9 | **Rewrite & Retry** | If not useful, rewrites the retrieval query and re-retrieves |

        **Embeddings** are generated locally via `sentence-transformers/all-MiniLM-L6-v2`
        (no OpenAI key required).  
        **LLM** uses your chosen Groq model for all reasoning steps.
        """
    )
    st.stop()

# ── Knowledge base status bar ─────────────────────────────────────────────────
st.info(
    f"📚 **{len(st.session_state.doc_names)}** document(s) · "
    f"**{st.session_state.chunk_count}** chunks · "
    f"Model: **{selected_model}**"
)

# ── Pipeline graph visualisation ──────────────────────────────────────────────
if st.session_state.get("show_graph") and st.session_state.pipeline:
    with st.expander("🗺️ Pipeline State Graph", expanded=True):
        try:
            mermaid_src = st.session_state.pipeline.app.get_graph().draw_mermaid()
            html = f"""
            <html><body style="background:#0e1117; margin:0; padding:8px;">
            <pre class="mermaid" style="background:#0e1117;">{mermaid_src}</pre>
            <script type="module">
              import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
              mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
            </script>
            </body></html>
            """
            st.components.v1.html(html, height=700, scrolling=True)
        except Exception as exc:
            st.warning(f"Could not render graph: {exc}")

# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("pipeline_details"):
            show_pipeline_details(msg["pipeline_details"])

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask a question about your documents…")

if user_input:
    # Render + store user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Run pipeline + render assistant message
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.write("⏳ Running Self-RAG pipeline…")

        try:
            result = st.session_state.pipeline.run(user_input)
            answer = result.get("answer") or "No answer found."

            pipeline_details = {
                "need_retrieval":  result.get("need_retrieval"),
                "docs":            result.get("docs",          []),
                "relevant_docs":   result.get("relevant_docs", []),
                "issup":           result.get("issup",         ""),
                "isuse":           result.get("isuse",         ""),
                "retries":         result.get("retries",        0),
                "rewrite_tries":   result.get("rewrite_tries",  0),
                "evidence":        result.get("evidence",       []),
                "use_reason":      result.get("use_reason",    ""),
            }

            placeholder.empty()
            st.write(answer)
            show_pipeline_details(pipeline_details)

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "pipeline_details": pipeline_details,
            })

        except Exception as exc:
            placeholder.empty()
            err = f"⚠️ Pipeline error: {exc}"
            st.error(err)
            st.session_state.messages.append({"role": "assistant", "content": err})
