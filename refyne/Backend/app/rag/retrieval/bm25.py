"""
BM25 retrieval wrapper for Phase 3 Hybrid RAG.

Reuses the existing Phase 2 BM25Index without duplication.
Tokenization is consistent with how the corpus was built: simple whitespace
splitting (matching BM25Index.rebuild_from_chunks / add_chunks).

Returns a candidate pool larger than top_k for downstream fusion.
"""
import logging
import time

from app.rag.bm25.index import BM25Index

logger = logging.getLogger(__name__)


def bm25_search(
    project_id: str,
    query: str,
    n_candidates: int,
    document_ids: list[str] | None = None,
    user_role: str | None = None,
    trace_id: str | None = None,
) -> tuple[list[dict], float]:
    """
    Run BM25 keyword search for the given project.

    Args:
        user_role: If provided, only chunks with this role in allowed_roles are returned.
        trace_id: Request trace ID for logging correlation.

    Returns:
        (results, elapsed_ms)
    """
    t0 = time.perf_counter()

    bm25_index = BM25Index(project_id)

    if bm25_index.bm25 is None or not bm25_index.corpus:
        logger.debug(
            "BM25 index empty",
            extra={"project_id": project_id, "trace_id": trace_id, "event": "bm25_empty"},
        )
        return [], (time.perf_counter() - t0) * 1000

    # Consistent tokenization with the corpus
    tokenized_query = query.split()
    if not tokenized_query:
        return [], (time.perf_counter() - t0) * 1000

    scores = bm25_index.bm25.get_scores(tokenized_query)

    # Build (index, score) pairs and sort descending
    indexed_scores = list(enumerate(scores))
    indexed_scores.sort(key=lambda x: x[1], reverse=True)

    results = []
    seen = 0
    for idx, score in indexed_scores:
        if seen >= n_candidates:
            break

        if idx >= len(bm25_index.corpus) or idx >= len(bm25_index.metadatas):
            continue

        meta = bm25_index.metadatas[idx]
        doc_id = meta.get("document_id", "")

        # Apply document_ids filter if provided
        if document_ids is not None and doc_id not in document_ids:
            continue

        # Apply role-based authorization filter
        if user_role:
            allowed = meta.get("allowed_roles", [])
            if user_role not in allowed:
                continue

        chunk_idx = meta.get("chunk_index", 0)
        # Deterministic chunk_id matches ChromaDB: {document_id}_{chunk_index}
        chunk_id = f"{doc_id}_{chunk_idx}"

        results.append(
            {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "chunk_index": chunk_idx,
                "text": bm25_index.corpus[idx],
                "metadata": meta,
                "raw_bm25_score": float(score),
            }
        )
        seen += 1

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "BM25 search completed",
        extra={
            "project_id": project_id,
            "trace_id": trace_id,
            "candidates": len(results),
            "duration_ms": round(elapsed_ms, 1),
            "event": "bm25_search",
        },
    )
    return results, elapsed_ms
