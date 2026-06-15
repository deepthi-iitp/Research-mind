"""
ResearchMind — shared LLM + vector store clients
Single-instance objects reused across all agents.
"""
from __future__ import annotations

import logging
from functools import lru_cache  # still used by get_qdrant_client

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore as Qdrant
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

# ── LLM clients ──────────────────────────────────────────────────────────────

def get_llm(fast: bool = False) -> ChatOpenAI:
    from core.request_context import get_request_api_key
    key = get_request_api_key() or cfg.openai_api_key
    model = cfg.openai_fast_model if fast else cfg.openai_model
    return ChatOpenAI(model=model, openai_api_key=key, temperature=0.2, streaming=True)


def get_embeddings() -> OpenAIEmbeddings:
    from core.request_context import get_request_api_key
    key = get_request_api_key() or cfg.openai_api_key
    return OpenAIEmbeddings(openai_api_key=key)


# ── Vector store ─────────────────────────────────────────────────────────────

COLLECTION = "researchmind_papers"
VECTOR_DIM  = 1536   # text-embedding-ada-002 / text-embedding-3-small


@lru_cache
def get_qdrant_client() -> QdrantClient:
    url = cfg.qdrant_url
    if "YOUR-CLUSTER-ID" in url:
        log.warning(
            "QDRANT_URL is still a placeholder — falling back to in-memory Qdrant. "
            "RAG context won't persist. Set a real URL in backend/.env to enable it."
        )
        return QdrantClient(":memory:")
    return QdrantClient(url=url, api_key=cfg.qdrant_api_key or None)


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
        embeddings=get_embeddings(),
        metadata_payload_key="metadata",
    )
