"""
ResearchMind — shared LLM + vector store clients
Single-instance objects reused across all agents.
"""
from __future__ import annotations

import logging
import math
import os
from functools import lru_cache  # still used by get_qdrant_client

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore as Qdrant
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

# Any OpenAI-compatible provider works by setting OPENAI_BASE_URL
# (e.g. Gemini: https://generativelanguage.googleapis.com/v1beta/openai/).
BASE_URL    = os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/") or None
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
VECTOR_DIM  = int(os.getenv("EMBED_DIM", "1536"))

# ── LLM clients ──────────────────────────────────────────────────────────────

class MissingAPIKeyError(RuntimeError):
    """Raised when neither the server nor the request supplies an API key."""


def _resolve_key() -> str:
    from core.request_context import get_request_api_key
    key = get_request_api_key() or cfg.openai_api_key
    if not key:
        raise MissingAPIKeyError(
            "No API key: set OPENAI_API_KEY on the server or add your key in the app."
        )
    return key


def get_llm(fast: bool = False) -> ChatOpenAI:
    key = _resolve_key()
    model = cfg.openai_fast_model if fast else cfg.openai_model
    return ChatOpenAI(model=model, openai_api_key=key, base_url=BASE_URL,
                      temperature=0.2, streaming=True, max_retries=5)


def _fit(vec: list[float]) -> list[float]:
    """Cut to VECTOR_DIM and re-normalise (gemini-embedding-001 returns 3072)."""
    if len(vec) <= VECTOR_DIM:
        return vec
    v = vec[:VECTOR_DIM]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class FittedEmbeddings(OpenAIEmbeddings):
    """OpenAIEmbeddings that always returns VECTOR_DIM-sized vectors."""

    def embed_documents(self, texts, chunk_size=None, **kw):
        return [_fit(v) for v in super().embed_documents(texts, chunk_size, **kw)]

    def embed_query(self, text, **kw):
        return _fit(super().embed_query(text, **kw))

    async def aembed_documents(self, texts, chunk_size=None, **kw):
        return [_fit(v) for v in await super().aembed_documents(texts, chunk_size, **kw)]

    async def aembed_query(self, text, **kw):
        return _fit(await super().aembed_query(text, **kw))


def get_embeddings() -> OpenAIEmbeddings:
    key = _resolve_key()
    return FittedEmbeddings(
        model=EMBED_MODEL,
        openai_api_key=key,
        base_url=BASE_URL,
        # non-OpenAI providers reject tiktoken token arrays
        check_embedding_ctx_length=BASE_URL is None,
    )


# ── Vector store ─────────────────────────────────────────────────────────────

COLLECTION = "researchmind_papers"


@lru_cache
def get_qdrant_client() -> QdrantClient:
    url = cfg.qdrant_url
    if not url or url == ":memory:" or "YOUR-CLUSTER-ID" in url:
        log.warning("QDRANT_URL not set — using in-memory Qdrant (RAG data won't persist).")
        return QdrantClient(":memory:")
    try:
        client = QdrantClient(url=url, api_key=cfg.qdrant_api_key or None, timeout=5, check_compatibility=False)
        client.get_collections()          # fail fast if the server isn't reachable
        return client
    except Exception as e:
        log.warning("Qdrant at %s unreachable (%s) — falling back to in-memory Qdrant.", url, e)
        return QdrantClient(":memory:")


def ensure_collection() -> None:
    client = get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )


def get_vectorstore(session_id: str) -> Qdrant:
    """Return a Qdrant vectorstore scoped to a session (via metadata filter)."""
    ensure_collection()
    return Qdrant(
        client=get_qdrant_client(),
        collection_name=COLLECTION,
        embedding=get_embeddings(),      # was `embeddings=` — that crashed RAG even with OpenAI
        metadata_payload_key="metadata",
    )
