"""
self_rag_pipeline.py
────────────────────
Self-RAG pipeline using Groq LLM + Qwen3-VL-Embedding-2B embeddings.

Pipeline nodes (in order):
  1. decide_retrieval  – is external retrieval needed?
  2. generate_direct   – answer from Groq general knowledge (no retrieval path)
  3. retrieve          – FAISS top-k chunk retrieval
  4. is_relevant       – per-chunk relevance filter
  5. generate_from_context – RAG answer generation
  6. is_sup            – grounding verification (IsSUP)
  7. revise_answer     – strict quote-only revision loop
  8. is_use            – usefulness check (IsUSE)
  9. rewrite_question  – query rewrite for better retrieval
"""

from typing import List, TypedDict, Literal, Optional
from pydantic import BaseModel, Field

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END

import embedding_service

# ── Constants ────────────────────────────────────────────────────────────────
MAX_RETRIES = 10        # max IsSUP → revise cycles
MAX_REWRITE_TRIES = 3   # max IsUSE → rewrite cycles

# ── Graph State ───────────────────────────────────────────────────────────────
class State(TypedDict):
    question: str
    retrieval_query: str        # optimised query sent to vector store
    rewrite_tries: int

    need_retrieval: bool
    docs: List[Document]
    relevant_docs: List[Document]
    context: str
    answer: str

    issup: Literal["fully_supported", "partially_supported", "no_support"]
    evidence: List[str]
    retries: int                # IsSUP revise loop counter

    isuse: Literal["useful", "not_useful"]
    use_reason: str


# ── Pydantic output schemas ───────────────────────────────────────────────────
class RetrieveDecision(BaseModel):
    should_retrieve: bool = Field(
        ..., description="True if external documents are needed to answer reliably."
    )


class RelevanceDecision(BaseModel):
    is_relevant: bool = Field(
        ..., description="True if the document discusses the same topic as the question."
    )


class IsSUPDecision(BaseModel):
    issup: Literal["fully_supported", "partially_supported", "no_support"]
    evidence: List[str] = Field(default_factory=list)


class IsUSEDecision(BaseModel):
    isuse: Literal["useful", "not_useful"]
    reason: str = Field(..., description="Short reason in 1 line.")


class RewriteDecision(BaseModel):
    retrieval_query: str = Field(
        ..., description="Rewritten query optimised for vector retrieval over company PDFs."
    )


# ── Prompts ───────────────────────────────────────────────────────────────────
decide_retrieval_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You decide whether retrieval is needed.\n"
        "Return JSON with key: should_retrieve (boolean).\n\n"
        "Guidelines:\n"
        "- should_retrieve=True  → answering requires specific facts from company documents.\n"
        "- should_retrieve=False → general explanation or definition, no company context needed.\n"
        "- If unsure, choose True.",
    ),
    ("human", "Question: {question}"),
])

direct_generation_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Answer using only your general knowledge.\n"
        "If the question requires specific company information, say exactly:\n"
        "'I don't know based on my general knowledge.'",
    ),
    ("human", "{question}"),
])

is_relevant_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are judging document relevance at a TOPIC level.\n"
        "Return JSON matching the schema.\n\n"
        "A document is relevant if it discusses the same entity or topic area as the question.\n"
        "It does NOT need to contain the exact answer.\n\n"
        "Examples:\n"
        "- HR policies → relevant to notice period, probation, termination, benefits.\n"
        "- Pricing docs → relevant to refunds, trials, billing terms.\n"
        "- Company profile → relevant to leadership, culture, size, strategy.\n\n"
        "Do NOT check whether the document fully answers the question.\n"
        "When unsure, return is_relevant=true.",
    ),
    ("human", "Question:\n{question}\n\nDocument:\n{document}"),
])

rag_generation_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a business RAG chatbot.\n\n"
        "Answer the question based solely on the CONTEXT from internal company documents.\n"
        "Do not mention that you are using a context block.",
    ),
    ("human", "Question:\n{question}\n\nContext:\n{context}"),
])

issup_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are verifying whether the ANSWER is supported by the CONTEXT.\n"
        "Return JSON with keys: issup, evidence.\n"
        "issup must be one of: fully_supported, partially_supported, no_support.\n\n"
        "Definitions:\n"
        "- fully_supported    : every claim is explicitly in CONTEXT; no unsupported qualitative words.\n"
        "- partially_supported: core facts are present but ANSWER adds abstraction/interpretation.\n"
        "- no_support         : key claims are absent from CONTEXT.\n\n"
        "Rules:\n"
        "- Be strict: any unsupported qualitative phrasing → partially_supported.\n"
        "- evidence: up to 3 short direct quotes from CONTEXT.\n"
        "- Do not use outside knowledge.",
    ),
    ("human", "Question:\n{question}\n\nAnswer:\n{answer}\n\nContext:\n{context}\n"),
])

revise_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a STRICT reviser.\n\n"
        "Output ONLY direct quotes from CONTEXT in this format:\n"
        "- <direct quote>\n"
        "- <direct quote>\n\n"
        "Rules:\n"
        "- Use ONLY the CONTEXT.\n"
        "- Do NOT add any words beyond bullet dashes and the quotes.\n"
        "- Do NOT explain, summarise, or say 'not mentioned'.",
    ),
    (
        "human",
        "Question:\n{question}\n\nCurrent Answer:\n{answer}\n\nCONTEXT:\n{context}",
    ),
])

isuse_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Judge whether the ANSWER is USEFUL for the QUESTION.\n"
        "Return JSON with keys: isuse, reason.\n"
        "isuse: 'useful' if the answer directly addresses the question, else 'not_useful'.\n"
        "reason: 1 short line.\n"
        "Do NOT re-check grounding (IsSUP already did that).",
    ),
    ("human", "Question:\n{question}\n\nAnswer:\n{answer}"),
])

rewrite_for_retrieval_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Rewrite the user QUESTION into a retrieval query optimised for FAISS over internal company PDFs.\n\n"
        "Rules:\n"
        "- Keep it 6–16 words.\n"
        "- Preserve entity names (e.g. company name, plan names).\n"
        "- Add 2–5 high-signal domain keywords (policy, pricing, HR terms).\n"
        "- Remove filler words.\n"
        "- Output JSON: {retrieval_query: '...'}",
    ),
    (
        "human",
        "QUESTION:\n{question}\n\nPrevious retrieval query:\n{retrieval_query}\n\nAnswer so far:\n{answer}",
    ),
])


# ── Pipeline class ────────────────────────────────────────────────────────────
class SelfRAGPipeline:
    """
    Self-RAG pipeline.
    Usage:
        pipeline = SelfRAGPipeline(groq_api_key="gsk_...", model_name="llama-3.3-70b-versatile")
        pipeline.load_documents(["path/to/doc.pdf"])
        result = pipeline.run("What is the refund policy?")
    """

    def __init__(self, groq_api_key: str, model_name: str = "llama-3.3-70b-versatile", session_id: Optional[str] = None):
        self.groq_api_key = groq_api_key
        self.model_name = model_name
        self.session_id = session_id or embedding_service.generate_session_id()
        self.retriever = None
        self.app = None
        self._setup_llm()

    # ── Private helpers ───────────────────────────────────────────────────────
    def _setup_llm(self):
        llm = ChatGroq(api_key=self.groq_api_key, model=self.model_name, temperature=0)
        self._llm = llm
        self._should_retrieve_llm = llm.with_structured_output(RetrieveDecision)
        self._relevance_llm = llm.with_structured_output(RelevanceDecision)
        self._issup_llm = llm.with_structured_output(IsSUPDecision)
        self._isuse_llm = llm.with_structured_output(IsUSEDecision)
        self._rewrite_llm = llm.with_structured_output(RewriteDecision)

    def _get_retriever(self):
        """Build a retriever function backed by session-scoped FAISS."""
        session_id = self.session_id

        def _retrieve(query: str) -> List[Document]:
            results = embedding_service.search_index(session_id, query, top_k=4)
            return [
                Document(page_content=r["text"], metadata={"score": r["score"]})
                for r in results
            ]

        return _retrieve

    def _build_graph(self):
        """Compile the LangGraph state machine (called after documents are indexed)."""
        pipeline = self  # captured by inner functions

        # ── Node functions ────────────────────────────────────────────────────
        def decide_retrieval(state: State):
            decision: RetrieveDecision = pipeline._should_retrieve_llm.invoke(
                decide_retrieval_prompt.format_messages(question=state["question"])
            )
            return {"need_retrieval": decision.should_retrieve}

        def route_after_decide(state: State) -> Literal["generate_direct", "retrieve"]:
            return "retrieve" if state["need_retrieval"] else "generate_direct"

        def generate_direct(state: State):
            out = pipeline._llm.invoke(
                direct_generation_prompt.format_messages(question=state["question"])
            )
            return {"answer": out.content}

        def retrieve(state: State):
            q = state.get("retrieval_query") or state["question"]
            return {"docs": pipeline.retriever(q)}

        def is_relevant(state: State):
            relevant_docs: List[Document] = []
            for doc in state.get("docs", []):
                decision: RelevanceDecision = pipeline._relevance_llm.invoke(
                    is_relevant_prompt.format_messages(
                        question=state["question"],
                        document=doc.page_content,
                    )
                )
                if decision.is_relevant:
                    relevant_docs.append(doc)
            return {"relevant_docs": relevant_docs}

        def route_after_relevance(
            state: State,
        ) -> Literal["generate_from_context", "no_answer_found"]:
            return "generate_from_context" if state.get("relevant_docs") else "no_answer_found"

        def generate_from_context(state: State):
            context = "\n\n---\n\n".join(
                d.page_content for d in state.get("relevant_docs", [])
            ).strip()
            if not context:
                return {"answer": "No answer found.", "context": ""}
            out = pipeline._llm.invoke(
                rag_generation_prompt.format_messages(
                    question=state["question"], context=context
                )
            )
            return {"answer": out.content, "context": context}

        def no_answer_found(state: State):
            return {"answer": "No answer found.", "context": ""}

        def is_sup(state: State):
            decision: IsSUPDecision = pipeline._issup_llm.invoke(
                issup_prompt.format_messages(
                    question=state["question"],
                    answer=state.get("answer", ""),
                    context=state.get("context", ""),
                )
            )
            return {"issup": decision.issup, "evidence": decision.evidence}

        def route_after_issup(
            state: State,
        ) -> Literal["accept_answer", "revise_answer"]:
            if state.get("issup") == "fully_supported":
                return "accept_answer"
            if state.get("retries", 0) >= MAX_RETRIES:
                return "accept_answer"
            return "revise_answer"

        def revise_answer(state: State):
            out = pipeline._llm.invoke(
                revise_prompt.format_messages(
                    question=state["question"],
                    answer=state.get("answer", ""),
                    context=state.get("context", ""),
                )
            )
            return {"answer": out.content, "retries": state.get("retries", 0) + 1}

        def is_use(state: State):
            decision: IsUSEDecision = pipeline._isuse_llm.invoke(
                isuse_prompt.format_messages(
                    question=state["question"],
                    answer=state.get("answer", ""),
                )
            )
            return {"isuse": decision.isuse, "use_reason": decision.reason}

        def route_after_isuse(
            state: State,
        ) -> Literal["END", "rewrite_question", "no_answer_found"]:
            if state.get("isuse") == "useful":
                return "END"
            if state.get("rewrite_tries", 0) >= MAX_REWRITE_TRIES:
                return "no_answer_found"
            return "rewrite_question"

        def rewrite_question(state: State):
            decision: RewriteDecision = pipeline._rewrite_llm.invoke(
                rewrite_for_retrieval_prompt.format_messages(
                    question=state["question"],
                    retrieval_query=state.get("retrieval_query", ""),
                    answer=state.get("answer", ""),
                )
            )
            return {
                "retrieval_query": decision.retrieval_query,
                "rewrite_tries": state.get("rewrite_tries", 0) + 1,
                "docs": [],
                "relevant_docs": [],
                "context": "",
            }

        # ── Graph assembly ────────────────────────────────────────────────────
        g = StateGraph(State)

        g.add_node("decide_retrieval", decide_retrieval)
        g.add_node("generate_direct", generate_direct)
        g.add_node("retrieve", retrieve)
        g.add_node("is_relevant", is_relevant)
        g.add_node("generate_from_context", generate_from_context)
        g.add_node("no_answer_found", no_answer_found)
        g.add_node("is_sup", is_sup)
        g.add_node("revise_answer", revise_answer)
        g.add_node("is_use", is_use)
        g.add_node("rewrite_question", rewrite_question)

        g.add_edge(START, "decide_retrieval")

        g.add_conditional_edges(
            "decide_retrieval",
            route_after_decide,
            {"generate_direct": "generate_direct", "retrieve": "retrieve"},
        )
        g.add_edge("generate_direct", END)

        g.add_edge("retrieve", "is_relevant")
        g.add_conditional_edges(
            "is_relevant",
            route_after_relevance,
            {
                "generate_from_context": "generate_from_context",
                "no_answer_found": "no_answer_found",
            },
        )
        g.add_edge("no_answer_found", END)

        g.add_edge("generate_from_context", "is_sup")
        g.add_conditional_edges(
            "is_sup",
            route_after_issup,
            # "accept_answer" label routes directly to is_use (no separate node needed)
            {"accept_answer": "is_use", "revise_answer": "revise_answer"},
        )
        g.add_edge("revise_answer", "is_sup")   # IsSUP → revise loop

        g.add_conditional_edges(
            "is_use",
            route_after_isuse,
            {"END": END, "rewrite_question": "rewrite_question", "no_answer_found": "no_answer_found"},
        )
        g.add_edge("rewrite_question", "retrieve")

        self.app = g.compile()

    # ── Public API ────────────────────────────────────────────────────────────
    def load_documents(self, file_paths: List[str]) -> int:
        """
        Load PDFs from *file_paths*, split into chunks, embed and index with FAISS.
        Returns the number of chunks created.
        """
        docs: List[Document] = []
        for path in file_paths:
            docs.extend(PyPDFLoader(path).load())

        chunks = RecursiveCharacterTextSplitter(
            chunk_size=600, chunk_overlap=150
        ).split_documents(docs)

        texts = [c.page_content for c in chunks]
        embedding_service.add_to_index(self.session_id, texts)

        self.retriever = self._get_retriever()
        self._build_graph()
        return len(chunks)

    def run(self, question: str) -> dict:
        """
        Run the Self-RAG pipeline for *question*.
        Returns the full final state dict.
        """
        if not self.is_ready():
            raise RuntimeError("Pipeline not ready. Call load_documents() first.")

        initial_state: State = {
            "question": question,
            "retrieval_query": question,
            "rewrite_tries": 0,
            "need_retrieval": False,
            "docs": [],
            "relevant_docs": [],
            "context": "",
            "answer": "",
            "issup": "no_support",
            "evidence": [],
            "retries": 0,
            "isuse": "not_useful",
            "use_reason": "",
        }
        return self.app.invoke(initial_state, config={"recursion_limit": 80})

    def update_model(self, model_name: str):
        """Switch to a different Groq model without reloading documents."""
        self.model_name = model_name
        self._setup_llm()
        if self.retriever is not None:
            self._build_graph()

    def is_ready(self) -> bool:
        """True once documents have been loaded and the graph compiled."""
        return self.retriever is not None and self.app is not None
