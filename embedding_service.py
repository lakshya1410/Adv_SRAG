"""
embedding_service.py
───────────────────
HuggingFace Qwen3-VL-Embedding-2B embeddings with session-based FAISS indexing.

- Loads the model once (singleton) on first use.
- GPU → CPU fallback built-in.
- All embeddings normalized for cosine similarity.
- Session-scoped FAISS indexes stored in memory.
- Uses HUGGINGFACE_TOKEN from environment for private/model access.
"""

import os
import uuid
from threading import Lock
from typing import List, Optional, Dict, Any

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


# ── Constants ──────────────────────────────────────────────────────────────────
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, reliable, 384-dim embeddings
BATCH_SIZE = 32
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


# ── Singleton embedding model ─────────────────────────────────────────────────
class _EmbeddingModel:
    """Loads Qwen3-VL-Embedding-2B once via sentence-transformers and reuses it."""

    _instance: Optional["_EmbeddingModel"] = None
    _lock = Lock()

    def __new__(cls) -> "_EmbeddingModel":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def _init(self) -> None:
        if self._initialized:
            return

        # Detect GPU
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

        try:
            self._model = SentenceTransformer(
                MODEL_NAME,
                device=device,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{MODEL_NAME}': {e}\n"
                f"Try: pip install --upgrade sentence-transformers torch"
            )
        
        self._initialized = True

    @property
    def model(self) -> SentenceTransformer:
        if not self._initialized:
            self._init()
        return self._model

    def embed(self, texts: List[str], batch_size: int = BATCH_SIZE) -> np.ndarray:
        """
        Generate normalized embeddings for a list of texts.
        Returns shape (len(texts), embedding_dim), L2-normalized.
        
        Args:
            texts: List of text strings to embed.
            batch_size: Batch size for processing.
            
        Returns:
            numpy array of shape (len(texts), embedding_dim), L2-normalized.
            
        Raises:
            RuntimeError: If embedding generation fails.
        """
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, EMBEDDING_DIM)
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,  # L2 → cosine similarity = dot product
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embeddings.astype(np.float32)
        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}")


def get_embeddings(inputs: List[str], batch_size: int = BATCH_SIZE) -> np.ndarray:
    """
    Public API: embed a list of text strings.

    Args:
        inputs: List of text strings to embed.
        batch_size: Batch size for embedding generation.

    Returns:
        numpy array of shape (len(inputs), embedding_dim), L2-normalized.
        
    Raises:
        RuntimeError: If model is unavailable or embedding fails.
    """
    if not inputs:
        return np.array([], dtype=np.float32).reshape(0, EMBEDDING_DIM)
    
    try:
        model = _EmbeddingModel()
        return model.embed(inputs, batch_size=batch_size)
    except Exception as e:
        raise RuntimeError(f"Embedding service error: {e}")


# ── Session-based FAISS index store ───────────────────────────────────────────

class _SessionIndexStore:
    """
    In-memory store mapping session_id → FAISS index.
    Each session gets its own IndexFlatIP (cosine similarity via normalized vectors).
    """

    def __init__(self) -> None:
        self._indexes: Dict[str, faiss.Index] = {}
        self._doc_store: Dict[str, List[str]] = {}  # session_id → original texts
        self._lock = Lock()

    def _create_index(self) -> faiss.Index:
        """Create a new FAISS index using Inner Product (cosine sim on normalized vectors)."""
        return faiss.IndexFlatIP(EMBEDDING_DIM)

    def create_session(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self._indexes:
                self._indexes[session_id] = self._create_index()
                self._doc_store[session_id] = []

    def add_to_index(self, session_id: str, texts: List[str]) -> int:
        """
        Embed *texts* and add to the session's FAISS index.
        Creates the index if the session doesn't exist.

        Args:
            session_id: The session to add to.
            texts: List of text strings to embed and index.

        Returns:
            Number of vectors added.
            
        Raises:
            RuntimeError: If embedding or FAISS operations fail.
        """
        self.create_session(session_id)

        if not texts:
            return 0

        try:
            embeddings = get_embeddings(texts)
        except Exception as e:
            raise RuntimeError(f"Failed to generate embeddings: {e}")

        if embeddings.shape[0] == 0:
            return 0
        
        if embeddings.shape[1] != EMBEDDING_DIM:
            raise RuntimeError(
                f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {embeddings.shape[1]}"
            )

        try:
            with self._lock:
                index = self._indexes[session_id]
                index.add(embeddings)
                self._doc_store[session_id].extend(texts)
        except Exception as e:
            raise RuntimeError(f"Failed to add embeddings to FAISS index: {e}")

        return len(texts)

    def search(self, session_id: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Search within a session's FAISS index using cosine similarity.

        Args:
            session_id: The session to search within.
            query: Query text.
            top_k: Number of top results to return.

        Returns:
            List of dicts with keys: text, score.
            
        Raises:
            RuntimeError: If search fails.
        """
        with self._lock:
            if session_id not in self._indexes:
                return []
            index = self._indexes[session_id]
            texts = self._doc_store.get(session_id, [])

        if index.ntotal == 0:
            return []

        try:
            query_emb = get_embeddings([query])  # (1, dim)
        except Exception as e:
            raise RuntimeError(f"Query embedding failed: {e}")
        
        search_k = min(top_k, index.ntotal)

        try:
            scores, indices = index.search(query_emb, search_k)
        except Exception as e:
            raise RuntimeError(f"FAISS search failed: {e}")

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(texts):
                results.append({"text": texts[int(idx)], "score": float(score)})

        return results

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._indexes.pop(session_id, None)
            self._doc_store.pop(session_id, None)

    def has_session(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._indexes and self._indexes[session_id].ntotal > 0


# ── Global singleton instance ─────────────────────────────────────────────────
_session_store: Optional[_SessionIndexStore] = None


def get_session_store() -> _SessionIndexStore:
    global _session_store
    if _session_store is None:
        _session_store = _SessionIndexStore()
    return _session_store


def add_to_index(session_id: str, texts: List[str]) -> int:
    """
    Add texts to a session's FAISS index.
    
    Args:
        session_id: The session to add texts to.
        texts: List of text strings to embed and index.
        
    Returns:
        Number of texts added.
        
    Raises:
        RuntimeError: If embedding or indexing fails.
    """
    try:
        return get_session_store().add_to_index(session_id, texts)
    except Exception as e:
        raise RuntimeError(f"Failed to add texts to index: {e}")


def search_index(session_id: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Search a session's FAISS index for top-k similar texts."""
    return get_session_store().search(session_id, query, top_k=top_k)


def create_session(session_id: str) -> None:
    """Initialize a new session index."""
    get_session_store().create_session(session_id)


def delete_session(session_id: str) -> None:
    """Remove a session's index and documents."""
    get_session_store().delete_session(session_id)


def generate_session_id() -> str:
    """Generate a new unique session ID."""
    return str(uuid.uuid4())
