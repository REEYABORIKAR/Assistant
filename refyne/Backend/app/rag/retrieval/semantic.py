"""
Semantic retrieval wrapper.

Queries the project-specific ChromaDB collection using the existing singleton
embedding model from Phase 2. Returns a candidate pool larger than top_k for
downstream fusion.

IMPORTANT — ChromaDB distance semantics:
  ChromaDB's default metric is "l2" (L2/Euclidean distance) unless specified
  otherwise at collection creation time. In L2 distance, LOWER = more similar.
  Before applying Min-Max normalization we CONVERT the distance to a similarity
  score where HIGHER = more similar using:

      similarity = 1 / (1 + distance)

  This guarantees:
    - distance 0.0  → similarity 1.0 (identical vectors)
    - distance → ∞  → similarity → 0.0 (completely dissimilar)
    - The result is always in (0, 1], strictly positive, with no risk of negatives
      or division by zero.

  The normalized score then undergoes Min-Max normalization across the candidate
  pool so scores are comparable to BM25 scores after their own normalization.
"""
import logging
import time
from typing import Optional

from app.rag.embeddings.model import get_embedding_model
from app.rag.chroma.store import get_chroma_store

logger = logging.getLogger(__name__)


def _distance_to_similarity(distance: float) -> float:
    """
    Convert an L2 distance (lower = better) to a similarity score (higher = better).
    Formula:  similarity = 1 / (1 + distance)
    Range:    (0, 1]  —  never negative, never infinite.
    """
    return 1.0 / (1.0 + distance)


def semantic_search(
    project_id: str,
    query: str,
    n_candidates: int,
    document_ids: Optional[list[str]] = None,
) -> tuple[list[dict], float]:
    """
    Run semantic search against the project ChromaDB collection.

    Returns:
        (results, elapsed_ms)
        Each result dict contains:
          chunk_id, document_id, chunk_index, text, metadata,
          raw_distance, similarity (converted, higher=better)
    """
    t0 = time.perf_counter()

    embedding_model = get_embedding_model()
    chroma_store = get_chroma_store()

    query_embedding = embedding_model.embed_text(query)
    collection = chroma_store.get_or_create_collection(project_id)

    # Build optional where clause for document_ids filter
    where = None
    if document_ids and len(document_ids) == 1:
        where = {"document_id": document_ids[0]}
    elif document_ids and len(document_ids) > 1:
        where = {"document_id": {"$in": document_ids}}

    query_kwargs = dict(
        query_embeddings=[query_embedding],
        n_results=n_candidates,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        query_kwargs["where"] = where

    try:
        chroma_result = collection.query(**query_kwargs)
    except Exception as e:
        logger.warning(f"ChromaDB query failed for project {project_id}: {e}")
        return [], (time.perf_counter() - t0) * 1000

    ids = chroma_result.get("ids", [[]])[0]
    documents = chroma_result.get("documents", [[]])[0]
    metadatas = chroma_result.get("metadatas", [[]])[0]
    distances = chroma_result.get("distances", [[]])[0]

    results = []
    for chunk_id, text, meta, dist in zip(ids, documents, metadatas, distances):
        similarity = _distance_to_similarity(dist)
        results.append(
            {
                "chunk_id": chunk_id,
                "document_id": meta.get("document_id", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "text": text,
                "metadata": meta,
                "raw_distance": dist,
                "similarity": similarity,  # higher = better
            }
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        f"Semantic search: project={project_id} candidates={len(results)} elapsed={elapsed_ms:.1f}ms"
    )
    return results, elapsed_ms
