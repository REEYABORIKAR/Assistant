"""
Query expansion via Pseudo-Relevance Feedback (PRF) for Phase 4 Advanced RAG.

Approach:
  1. The initial retrieval pass returns a fused candidate pool.
  2. We assume the TOP results of that pass are relevant ("pseudo-relevant").
  3. We extract the most discriminating terms from those top chunks and append
     them to the original query.
  4. The expanded query is used for a second, refined retrieval pass.

This is a classic advanced-RAG technique that recovers terms an author used
even when the user phrased the question differently (no LLM required).

Design:
  - Stopwords are excluded.
  - Terms already present in the original query are excluded (no redundancy).
  - Terms are scored by total frequency across the pseudo-relevant chunks,
    which favors terms that consistently appear in relevant content.
"""
import logging
import re
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

# Conservative English stopword list (lowercase). Kept intentionally small.
_STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with", "what", "when", "where", "which", "who", "whom", "whose", "why", "how", "not", "no", "but", "all", "any", "can", "could", "do", "does", "did", "should", "would", "may", "might", "must", "our", "your", "their", "they", "we", "you", "i", "he", "she", "them", "there", "here", "into", "over", "under", "about", "than", "then", "so", "also", "between", "through", "during", "before", "after", "above", "below", "again", "further", "once", "such", "these", "those", "each", "few", "more", "most", "other", "some", "same", "only", "own"]
)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


def _tokenize(text: str) -> list[str]:
    """Lowercase, split into alphanumeric tokens, drop stopwords."""
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]


def extract_expansion_terms(
    query: str,
    candidates: list[dict],
    top_terms: int | None = None,
    source_chunks: int | None = None,
) -> list[str]:
    """
    Extract discriminating terms from the top pseudo-relevant chunks.

    Args:
        query:      Original user query (used to avoid redundant terms).
        candidates: Fused candidate dicts, ranked best-first.
        top_terms:  Number of terms to return (defaults to config).
        source_chunks: How many top chunks to mine (defaults to config).

    Returns:
        List of up to `top_terms` terms, ordered by descending frequency.
    """
    limit_terms = top_terms if top_terms is not None else settings.QUERY_EXPANSION_TERMS
    n_chunks = source_chunks if source_chunks is not None else settings.QUERY_EXPANSION_SOURCE_CHUNKS

    if not candidates or limit_terms <= 0:
        return []

    query_terms = set(_tokenize(query))

    counts: dict[str, int] = {}
    for candidate in candidates[:n_chunks]:
        text = candidate.get("text", "")
        for term in _tokenize(text):
            if term in query_terms or len(term) < 3:
                continue
            counts[term] = counts.get(term, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    return [term for term, _ in ranked[:limit_terms]]


def expand_query(
    query: str,
    candidates: list[dict],
    top_terms: int | None = None,
    source_chunks: int | None = None,
) -> tuple[str, list[str]]:
    """
    Build an expanded query string by appending PRF terms.

    Returns:
        (expanded_query, added_terms)
        If no terms can be mined, expanded_query == query.
    """
    t0 = time.perf_counter()

    terms = extract_expansion_terms(query, candidates, top_terms, source_chunks)
    if not terms:
        return query, []

    expanded = f"{query} {' '.join(terms)}".strip()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        f"Query expansion: added {len(terms)} terms ({', '.join(terms)}) in {elapsed_ms:.1f}ms"
    )
    return expanded, terms
