"""
Cross-encoder reranking for Phase 4 Advanced RAG.

Reranking re-scores the fused candidate pool with a cross-encoder, which jointly
attends over the query AND a candidate document. This is far more accurate than
the bi-encoder similarity / BM25 scores used in the initial retrieval pass.

Design:
  - The CrossEncoder model is lazy-loaded once (singleton) and only when the
    first rerank happens, so retrieval still works without a model download.
  - If the model cannot be loaded (offline, missing weights, OOM), reranking is
    skipped gracefully and candidates pass through unchanged.
  - Original (hybrid) ranking is preserved as a tiebreaker for equal rerank
    scores, keeping results deterministic.
"""
import logging
import time
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class RerankerSingleton:
    """Lazily loaded, process-wide cross-encoder model."""

    _instance = None
    _model = None
    _load_error: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def model(self):
        if self._model is None and self._load_error is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(settings.RERANK_MODEL)
                logger.info(f"Cross-encoder reranker loaded: {settings.RERANK_MODEL}")
            except Exception as e:  # offline, missing deps, etc.
                self._load_error = str(e)
                logger.warning(
                    f"Failed to load reranker '{settings.RERANK_MODEL}': {e}. "
                    "Reranking will be skipped."
                )
        return self._model


def rerank_results(
    query: str,
    candidates: list[dict],
    top_k: Optional[int] = None,
) -> tuple[list[dict], bool, float]:
    """
    Rerank fused candidate dicts with a cross-encoder.

    Args:
        query:      The (possibly expanded) search query.
        candidates: Fused candidate dicts (each with 'text' and 'chunk_id').
        top_k:      Number of results to return (defaults to len(candidates)).

    Returns:
        (reranked_candidates, reranked_flag, elapsed_ms)
        Each candidate gains a 'rerank_score' field (raw cross-encoder logit).
        If reranking could not run, candidates are returned in original order
        with 'rerank_score' = None and reranked_flag = False.
    """
    t0 = time.perf_counter()

    if not candidates or not query:
        return candidates, False, (time.perf_counter() - t0) * 1000

    model = RerankerSingleton().model
    if model is None:
        return candidates, False, (time.perf_counter() - t0) * 1000

    limit = top_k if top_k is not None else len(candidates)

    try:
        pairs = [(query, c.get("text", "")) for c in candidates]
        scores = model.predict(pairs)
        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)
    except Exception as e:
        logger.warning(f"Reranking failed: {e}. Falling back to hybrid ranking.")
        return candidates, False, (time.perf_counter() - t0) * 1000

    # Sort by rerank score desc, then hybrid score desc as a stable tiebreaker.
    ranked = sorted(
        candidates,
        key=lambda c: (c.get("rerank_score", 0.0), c.get("hybrid_score", 0.0)),
        reverse=True,
    )[:limit]

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return ranked, True, elapsed_ms
