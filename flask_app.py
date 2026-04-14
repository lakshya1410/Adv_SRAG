import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.utils import secure_filename

import embedding_service

load_dotenv()

ALLOWED_EXTENSIONS = {"pdf"}
MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # 30 MB per request

MODEL_OPTIONS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


class RuntimeState:
    def __init__(self) -> None:
        self.pipeline: Any | None = None
        self.docs_loaded = False
        self.doc_names: list[str] = []
        self.chunk_count = 0
        self.model_name = MODEL_OPTIONS[0]
        self.session_id: str | None = None
        self.lock = Lock()

    def reset(self) -> None:
        if self.session_id is not None:
            embedding_service.delete_session(self.session_id)
        self.pipeline = None
        self.docs_loaded = False
        self.doc_names = []
        self.chunk_count = 0
        self.session_id = None


runtime = RuntimeState()


def _is_allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _doc_previews(docs: list[Any], limit: int = 3) -> list[str]:
    previews: list[str] = []
    for doc in docs[:limit]:
        text = (getattr(doc, "page_content", "") or "").strip().replace("\n", " ")
        if text:
            previews.append(text[:220] + ("..." if len(text) > 220 else ""))
    return previews


def _pipeline_details(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "need_retrieval": result.get("need_retrieval"),
        "docs_retrieved": len(result.get("docs") or []),
        "relevant_docs": len(result.get("relevant_docs") or []),
        "issup": result.get("issup") or "N/A",
        "isuse": result.get("isuse") or "N/A",
        "retries": result.get("retries", 0),
        "rewrite_tries": result.get("rewrite_tries", 0),
        "evidence": result.get("evidence") or [],
        "use_reason": result.get("use_reason") or "",
        "doc_previews": _doc_previews(result.get("relevant_docs") or []),
    }


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    @app.errorhandler(RequestEntityTooLarge)
    def file_too_large(_: RequestEntityTooLarge) -> Any:
        return jsonify({"ok": False, "error": "Upload too large. Max total upload size is 30 MB."}), 413

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception) -> Any:
        # Preserve normal HTTP behavior (404/405/etc.) for non-API routes.
        if isinstance(exc, HTTPException):
            return exc

        # Keep API responses machine-readable even on unexpected failures.
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": f"Server error: {exc}"}), 500
        raise exc

    @app.route("/")
    def home() -> str:
        return render_template("index.html")

    @app.route("/studio")
    def studio() -> str:
        return render_template("studio.html")

    @app.route("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.get("/api/models")
    def models() -> Any:
        return jsonify({"models": MODEL_OPTIONS})

    @app.get("/api/status")
    def status() -> Any:
        return jsonify(
            {
                "ready": runtime.docs_loaded,
                "doc_names": runtime.doc_names,
                "chunk_count": runtime.chunk_count,
                "model_name": runtime.model_name,
            }
        )

    @app.post("/api/reset")
    def reset() -> Any:
        with runtime.lock:
            runtime.reset()
        return jsonify({"ok": True, "message": "Session reset."})

    @app.post("/api/process-documents")
    def process_documents() -> Any:
        """
        Upload and process PDF documents to build a retrieval-augmented generation knowledge base.
        
        Expected form data:
        - files: Multiple PDF files (multipart/form-data)
        - model_name: (Optional) Name of the LLM model to use
        
        Returns:
            JSON with OK status, chunk count, document names, and model name.
        """
        groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not groq_api_key:
            return jsonify({"ok": False, "error": "GROQ_API_KEY is not set in environment."}), 500

        uploaded_files = request.files.getlist("files")
        model_name = (request.form.get("model_name") or MODEL_OPTIONS[0]).strip()

        if model_name not in MODEL_OPTIONS:
            return jsonify({"ok": False, "error": f"Invalid model '{model_name}'. Allowed: {', '.join(MODEL_OPTIONS)}"}), 400

        if not uploaded_files:
            return jsonify({"ok": False, "error": "Please upload at least one PDF file."}), 400

        valid_files = [f for f in uploaded_files if f and f.filename and _is_allowed(f.filename)]
        if not valid_files:
            return jsonify({"ok": False, "error": "Only PDF files (.pdf) are supported."}), 400

        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths: list[str] = []
            doc_names: list[str] = []

            for uf in valid_files:
                safe_name = secure_filename(uf.filename)
                if not safe_name:
                    continue
                dest = Path(temp_dir) / safe_name
                try:
                    uf.save(dest)
                except Exception as e:
                    return jsonify({"ok": False, "error": f"File save error: {e}"}), 500
                file_paths.append(str(dest))
                doc_names.append(safe_name)

            if not file_paths:
                return jsonify({"ok": False, "error": "No valid files were uploaded."}), 400

            try:
                # Imported lazily so the web app can start even when AI deps are absent.
                from self_rag_pipeline import SelfRAGPipeline

                pipeline = SelfRAGPipeline(groq_api_key=groq_api_key, model_name=model_name)
                chunk_count = pipeline.load_documents(file_paths)
                
            except ModuleNotFoundError as exc:
                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "Missing Python dependency. Install requirements with:\n"
                            f"pip install -r requirements.txt\n\nDetails: {exc}"
                        ),
                    }
                ), 500
            except RuntimeError as exc:
                # Catch embedding and pipeline errors
                return jsonify(
                    {
                        "ok": False,
                        "error": f"Document processing failed: {str(exc)[:500]}",
                    }
                ), 500
            except Exception as exc:
                return jsonify(
                    {
                        "ok": False,
                        "error": f"Unexpected error: {type(exc).__name__}: {str(exc)[:500]}",
                    }
                ), 500

        with runtime.lock:
            runtime.pipeline = pipeline
            runtime.docs_loaded = True
            runtime.doc_names = doc_names
            runtime.chunk_count = chunk_count
            runtime.model_name = model_name
            runtime.session_id = pipeline.session_id

        return jsonify(
            {
                "ok": True,
                "message": "Documents processed successfully.",
                "chunk_count": chunk_count,
                "doc_names": doc_names,
                "model_name": model_name,
            }
        )

    @app.post("/api/chat")
    def chat() -> Any:
        payload = request.get_json(silent=True) or {}
        question = (payload.get("question") or "").strip()

        if not question:
            return jsonify({"ok": False, "error": "Question is required."}), 400

        with runtime.lock:
            pipeline = runtime.pipeline

        if pipeline is None or not runtime.docs_loaded:
            return jsonify({"ok": False, "error": "Pipeline not ready. Process documents first."}), 400

        try:
            result = pipeline.run(question)
            answer = result.get("answer") or "No answer found."
            details = _pipeline_details(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Pipeline error: {exc}"}), 500

        return jsonify({"ok": True, "answer": answer, "pipeline_details": details})

    @app.post("/query")
    def query() -> Any:
        """
        Studio-friendly endpoint. Runs the Self-RAG pipeline and returns comprehensive results.
        
        Expected JSON:
        - query: The question to ask about the documents
        
        Returns:
            JSON with documents retrieved, evaluation metrics, and generated response.
        """
        payload = request.get_json(silent=True) or {}
        question = (payload.get("query") or "").strip()

        if not question:
            return jsonify({"ok": False, "error": "Query is required."}), 400

        if len(question) > 2000:
            return jsonify({"ok": False, "error": "Query is too long (max 2000 chars)."}), 400

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
                    "score": (getattr(d, "metadata", {}) or {}).get("score", 0),
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

        except RuntimeError as exc:
            # Catch specific pipeline errors
            return jsonify(
                {
                    "ok": False,
                    "error": f"Pipeline error: {str(exc)[:500]}",
                }
            ), 500
        except Exception as exc:
            return jsonify(
                {
                    "ok": False,
                    "error": f"Unexpected error: {type(exc).__name__}: {str(exc)[:500]}",
                }
            ), 500

        return jsonify({"ok": True, "documents": documents, "evaluation": evaluation, "response": answer})

    return app


app = create_app()


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=5000, debug=debug_mode, use_reloader=debug_mode)
