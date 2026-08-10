"""
Score normalization and result fusion for Phase 3 Hybrid RAG.

NORMALIZATION METHOD: Min-Max Normalization
  For a set of scores S = {s_1, s_2, ..., s_n}:
    normalized_i = (s_i - min(S)) / (max(S) - min(S))

  Edge cases handled deterministically:
    - max == min (all scores equal, or single result): normalized = 1.0 for all
    - empty pool: no candidates contributed, skip normalization

MISSING POOL SCORE:
  If a chunk exists in only one candidate pool, the normalized score for the
  missing pool is 0.0. This is consistent with the design spec.

FUSION FORMULA:
  hybrid_score = semantic_weight * normalized_semantic + bm25_weight * normalized_bm25

  Default weights: semantic=0.6, bm25=0.4 (configurable via environment).

THRESHOLD:
  Results with hybrid_score < HYBRID_MIN_SCORE are discarded before ranking.
  This prevents unrelated low-relevance chunks from polluting results.
"""
import logging
import time
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _minmax_normalize(scores: list[float]) -> list[float]:
    """
    Apply Min-Max normalization to a list of scores.

    Edge cases:
      - Empty list    → []
      - All zeros     → all 0.0  (no real signal; chunk was not in this retriever pool)
      - All equal (non-zero) → all 1.0  (avoids division by zero; all candidates equally relevant)
      - Single item   → [1.0]   (only one candidate, considered maximally relevant)
                        UNLESS that single item is 0.0, in which case → [0.0]
    """
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s == 0.0:
        # All scores are zero — no signal from this pool
        return [0.0] * len(scores)
    if max_s == min_s:
        # All scores are equal and non-zero → normalize to 1.0
        return [1.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]



def fuse_results(
    semantic_results: list[dict],
    bm25_results: list[dict],
    semantic_weight: Optional[float] = None,
    bm25_weight: Optional[float] = None,
    min_score: Optional[float] = None,
) -> tuple[list[dict], float]:
    """
    Merge, normalize, fuse, and rank retrieval candidates.

    Args:
        semantic_results: Output from semantic_search()
        bm25_results:     Output from bm25_search()
        semantic_weight:  Override for HYBRID_SEMANTIC_WEIGHT
        bm25_weight:      Override for HYBRID_BM25_WEIGHT
        min_score:        Override for HYBRID_MIN_SCORE

    Returns:
        (ranked_results, elapsed_ms)
        Each result dict contains all original fields plus:
          normalized_semantic, normalized_bm25, hybrid_score, retrieval_method
    """
    t0 = time.perf_counter()

    sem_w = semantic_weight if semantic_weight is not None else settings.HYBRID_SEMANTIC_WEIGHT
    bm25_w = bm25_weight if bm25_weight is not None else settings.HYBRID_BM25_WEIGHT
    threshold = min_score if min_score is not None else settings.HYBRID_MIN_SCORE

    # --- Step 1: Index results by chunk_id, track which pool they came from ---
    candidates: dict[str, dict] = {}

    for r in semantic_results:
        cid = r["chunk_id"]
        candidates[cid] = {
            **r,
            "_has_semantic": True,
            "_has_bm25": False,
            "_raw_sim": r["similarity"],   # higher = better (post-distance conversion)
            "_raw_bm25": 0.0,
        }

    for r in bm25_results:
        cid = r["chunk_id"]
        if cid in candidates:
            # Chunk appeared in both pools — merge
            candidates[cid]["_has_bm25"] = True
            candidates[cid]["_raw_bm25"] = r["raw_bm25_score"]
        else:
            candidates[cid] = {
                **r,
                "_has_semantic": False,
                "_has_bm25": True,
                "_raw_sim": 0.0,
                "_raw_bm25": r["raw_bm25_score"],
                # Fill semantic-side fields with defaults when missing
                "raw_distance": None,
                "similarity": 0.0,
            }

    if not candidates:
        return [], (time.perf_counter() - t0) * 1000

    chunk_ids = list(candidates.keys())

    # --- Step 2: Min-Max normalize similarity scores across all candidates ---
    raw_sims = [candidates[cid]["_raw_sim"] for cid in chunk_ids]
    norm_sims = _minmax_normalize(raw_sims)

    # --- Step 3: Min-Max normalize BM25 scores across all candidates ---
    raw_bm25s = [candidates[cid]["_raw_bm25"] for cid in chunk_ids]
    norm_bm25s = _minmax_normalize(raw_bm25s)

    # --- Step 4: Compute hybrid scores and annotate candidates ---
    for cid, ns, nb in zip(chunk_ids, norm_sims, norm_bm25s):
        c = candidates[cid]
        c["normalized_semantic"] = ns
        c["normalized_bm25"] = nb

        # Weighted fusion
        # hybrid_score = semantic_weight * normalized_semantic + bm25_weight * normalized_bm25
        hybrid = sem_w * ns + bm25_w * nb
        c["hybrid_score"] = hybrid

        # Track retrieval origin — "semantic", "bm25", or "hybrid" (found in both pools)
        if c["_has_semantic"] and c["_has_bm25"]:
            c["retrieval_method"] = "hybrid"
        elif c["_has_semantic"]:
            c["retrieval_method"] = "semantic"
        else:
            c["retrieval_method"] = "bm25"

    # --- Step 5: Apply minimum relevance threshold ---
    filtered = [c for c in candidates.values() if c["hybrid_score"] >= threshold]

    if not filtered:
        logger.debug(f"All {len(candidates)} candidates fell below threshold={threshold}")

    # --- Step 6: Sort by hybrid_score descending ---
    filtered.sort(key=lambda c: c["hybrid_score"], reverse=True)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        f"Fusion: merged={len(candidates)} filtered={len(filtered)} elapsed={elapsed_ms:.1f}ms"
    )
    return filtered, elapsed_ms
