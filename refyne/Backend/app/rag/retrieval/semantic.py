"""
Semantic retrieval wrapper.

Queries the project-specific vector store using the existing singleton
embedding model from Phase 2. Returns a candidate pool larger than top_k for
downstream fusion.

Authorization: chunks are filtered by allowed_roles at the vector store level.
"""
import logging
import time

from app.rag.embeddings.model import get_embedding_model
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def semantic_search(
    project_id: str,
    query: str,
    n_candidates: int,
    document_ids: list[str] | None = None,
    user_role: str | None = None,
    trace_id: str | None = None,
) -> tuple[list[dict], float]:
    """
    Run semantic search against the project vector store.

    Args:
        user_role: If provided, only chunks with this role in allowed_roles are returned.
        trace_id: Request trace ID for logging correlation.

    Returns:
        (results, elapsed_ms)
    """
    t0 = time.perf_counter()

    embedding_model = get_embedding_model()
    vector_store = get_vector_store()

    query_embedding = embedding_model.embed_text(query)

    filters = {}
    if document_ids:
        if len(document_ids) == 1:
            filters["document_id"] = document_ids[0]

    try:
        results = vector_store.query(
            project_id=project_id,
            embedding=query_embedding,
            top_k=n_candidates,
            filters=filters if filters else None,
        )
    except Exception as e:
        logger.warning(
            "Vector store query failed",
            extra={"project_id": project_id, "trace_id": trace_id, "error": str(e)},
        )
        return [], (time.perf_counter() - t0) * 1000

    # Post-query authorization filter
    if user_role:
        filtered = []
        for r in results:
            meta = r.get("metadata", {})
            allowed = meta.get("allowed_roles", [])
            if user_role in allowed:
                filtered.append(r)
        results = filtered

    output = []
    for r in results:
        meta = r.get("metadata", {})
        output.append({
            "chunk_id": f"{meta.get('document_id', '')}_{meta.get('chunk_index', 0)}",
            "document_id": meta.get("document_id", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "text": r.get("text", ""),
            "metadata": meta,
            "raw_distance": 1.0 - r.get("score", 0.0),
            "similarity": r.get("score", 0.0),
        })

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "Semantic search completed",
        extra={
            "project_id": project_id,
            "trace_id": trace_id,
            "candidates": len(output),
            "duration_ms": round(elapsed_ms, 1),
            "event": "semantic_search",
        },
    )
    return output, elapsed_ms
