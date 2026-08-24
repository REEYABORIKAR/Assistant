"""
HybridRetriever: The central coordinator for Phase 4 Advanced RAG retrieval.
...
"""
import logging
import time

from opentelemetry import trace
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.rag.retrieval.bm25 import bm25_search
from app.rag.retrieval.context_builder import _infer_source_type, build_context
from app.rag.retrieval.fusion import fuse_results
from app.rag.retrieval.query_expansion import expand_query
from app.rag.retrieval.reranker import rerank_results
from app.rag.retrieval.schemas import (
    RetrievalDebugInfo,
    RetrievalMetadata,
    SearchResponse,
    SearchResult,
    SearchResultMetadata,
)
from app.rag.retrieval.semantic import semantic_search

logger = logging.getLogger(__name__)


def _resolve_file_name(db: Session, document_id: str) -> str:
    """Fetch file_name for a document from the DB. Falls back to document_id."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    return doc.file_name if doc else document_id


def _build_search_result(
    candidate: dict,
    project_id: str,
    db: Session,
    include_debug: bool = False,
) -> SearchResult:
    """Convert a fused candidate dict into a SearchResult Pydantic model."""
    doc_id = candidate.get("document_id", "")
    file_name = _resolve_file_name(db, doc_id)
    meta = candidate.get("metadata", {})

    page_number = meta.get("page_number") or candidate.get("page_number")
    sheet_name = meta.get("sheet_name") or candidate.get("sheet_name")
    source_type = _infer_source_type(file_name)

    return SearchResult(
        chunk_id=candidate["chunk_id"],
        document_id=doc_id,
        project_id=project_id,
        file_name=file_name,
        chunk_index=candidate.get("chunk_index", 0),
        text=candidate.get("text", ""),
        semantic_score=round(candidate.get("normalized_semantic", 0.0), 6),
        bm25_score=round(candidate.get("normalized_bm25", 0.0), 6),
        hybrid_score=round(candidate.get("hybrid_score", 0.0), 6),
        rerank_score=candidate.get("rerank_score"),
        metadata=SearchResultMetadata(
            chunk_index=candidate.get("chunk_index", 0),
            page_number=int(page_number) if page_number is not None else None,
            sheet_name=str(sheet_name) if sheet_name else None,
            source_type=source_type,
        ),
        retrieval_method=candidate.get("retrieval_method"),
    )


class HybridRetriever:
    """
    Central coordinator for hybrid retrieval.

    Responsibilities:
      - Validate inputs
      - Enforce project ownership (caller must pass a verified project_id)
      - Verify document_ids belong to the project
      - Run semantic + BM25 searches with a larger candidate pool
      - Fuse, normalize, rank
      - Build context and citations
      - Return a fully populated SearchResponse
    """

    def __init__(self, db: Session):
        self.db = db

    def _verify_document_ids(self, document_ids: list[str], project_id: str) -> list[str]:
        """
        Verify that all supplied document_ids belong to this project.
        Returns only the valid, confirmed IDs.
        Raises ValueError for any ID that doesn't belong.
        """
        verified = []
        for doc_id in document_ids:
            doc = self.db.query(Document).filter(
                Document.id == doc_id,
                Document.project_id == project_id,
            ).first()
            if doc is None:
                raise ValueError(
                    f"Document '{doc_id}' does not exist in project '{project_id}'"
                )
            verified.append(doc_id)
        return verified

    def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int | None = None,
        document_ids: list[str] | None = None,
        user_role: str | None = None,
        trace_id: str | None = None,
    ) -> SearchResponse:
        """
        Execute the full hybrid retrieval pipeline.

        Args:
            project_id:   Verified project ID (ownership checked by the API layer)
            query:        User query (must not be empty/whitespace)
            top_k:        Number of results (defaults to settings.RETRIEVAL_TOP_K)
            document_ids: Optional filter; each ID is verified to belong to the project
            user_role:    User's project role for authorization filtering
            trace_id:     Request trace ID for logging correlation

        Returns:
            SearchResponse
        """
        t_total_start = time.perf_counter()
        tracer = trace.get_tracer("refyne.retrieval")

        # --- Input normalization ---
        query = query.strip()
        if not query:
            return self._empty_response(project_id, query, top_k or settings.RETRIEVAL_TOP_K)

        effective_top_k = min(
            top_k or settings.RETRIEVAL_TOP_K,
            settings.RETRIEVAL_MAX_TOP_K,
        )
        n_candidates = effective_top_k * settings.RETRIEVAL_CANDIDATE_MULTIPLIER

        with tracer.start_as_current_span(
            "retrieval.verify_doc_ids",
            attributes={"project_id": project_id, "trace_id": trace_id or ""},
        ):
            # --- Verify document_ids ---
            verified_doc_ids: list[str] | None = None
            if document_ids:
                try:
                    verified_doc_ids = self._verify_document_ids(document_ids, project_id)
                except ValueError as e:
                    raise ValueError(str(e))

        with tracer.start_as_current_span(
            "retrieval.pass1_hybrid",
            attributes={"project_id": project_id, "trace_id": trace_id or "", "n_candidates": n_candidates},
        ) as span:
            # --- Pass 1: initial hybrid retrieval ---
            sem_results, sem_ms = semantic_search(
                project_id=project_id,
                query=query,
                n_candidates=n_candidates,
                document_ids=verified_doc_ids,
                user_role=user_role,
                trace_id=trace_id,
            )
            bm25_results, bm25_ms = bm25_search(
                project_id=project_id,
                query=query,
                n_candidates=n_candidates,
                document_ids=verified_doc_ids,
                user_role=user_role,
                trace_id=trace_id,
            )
            span.set_attribute("semantic_candidates", len(sem_results))
            span.set_attribute("bm25_candidates", len(bm25_results))

        with tracer.start_as_current_span("retrieval.fuse", attributes={"project_id": project_id}):
            # --- Fusion ---
            fused, fusion_ms = fuse_results(sem_results, bm25_results)

        with tracer.start_as_current_span(
            "retrieval.query_expansion",
            attributes={"project_id": project_id, "enabled": settings.QUERY_EXPANSION_ENABLED},
        ) as span:
            # --- Query expansion (Pseudo-Relevance Feedback) ---
            expanded_query = query
            expansion_terms: list[str] = []
            expansion_ms = 0.0
            if settings.QUERY_EXPANSION_ENABLED and fused:
                t_exp = time.perf_counter()
                expanded_query, expansion_terms = expand_query(query, fused)
                expansion_ms = (time.perf_counter() - t_exp) * 1000
                if expanded_query != query:
                    # Pass 2: refined retrieval using the expanded query
                    sem_results, sem_ms = semantic_search(
                        project_id=project_id,
                        query=expanded_query,
                        n_candidates=n_candidates,
                        document_ids=verified_doc_ids,
                        user_role=user_role,
                        trace_id=trace_id,
                    )
                    bm25_results, bm25_ms = bm25_search(
                        project_id=project_id,
                        query=expanded_query,
                        n_candidates=n_candidates,
                        document_ids=verified_doc_ids,
                        user_role=user_role,
                        trace_id=trace_id,
                    )
                    fused, fusion_ms = fuse_results(sem_results, bm25_results)
            span.set_attribute("expanded", expanded_query != query)

        with tracer.start_as_current_span(
            "retrieval.rerank",
            attributes={"project_id": project_id, "enabled": settings.RERANK_ENABLED},
        ) as span:
            # --- Cross-encoder reranking ---
            reranked_flag = False
            rerank_ms = 0.0
            if settings.RERANK_ENABLED and fused:
                fused, reranked_flag, rerank_ms = rerank_results(
                    expanded_query, fused, top_k=effective_top_k
                )
            span.set_attribute("reranked", reranked_flag)

        # --- Apply threshold after reranking (fixes gap where reranked scores drop below min) ---
        if fused:
            fused = [c for c in fused if c.get("hybrid_score", 0.0) >= settings.HYBRID_MIN_SCORE]

        # --- Slice to top_k ---
        top_results_raw = fused[:effective_top_k]

        with tracer.start_as_current_span(
            "retrieval.build_results",
            attributes={"project_id": project_id, "trace_id": trace_id or ""},
        ) as span:
            # --- Build SearchResult objects ---
            include_debug = settings.RETRIEVAL_DEBUG
            search_results = [
                _build_search_result(c, project_id, self.db, include_debug)
                for c in top_results_raw
            ]

            # --- Build context, citations, source_documents ---
            context, citations, source_documents = build_context(search_results)
            span.set_attribute("final_results", len(search_results))
            span.set_attribute("context_length", len(context or ""))

        total_ms = (time.perf_counter() - t_total_start) * 1000

        logger.info(
            "Hybrid retrieval completed",
            extra={
                "project_id": project_id,
                "trace_id": trace_id,
                "query_len": len(query),
                "semantic_candidates": len(sem_results),
                "bm25_candidates": len(bm25_results),
                "final_results": len(search_results),
                "duration_ms": round(total_ms, 1),
                "event": "hybrid_retrieval",
            },
        )

        # --- Build metadata ---
        debug_info = RetrievalDebugInfo(
            semantic_search_ms=round(sem_ms, 2),
            bm25_search_ms=round(bm25_ms, 2),
            fusion_ms=round(fusion_ms, 2),
            total_retrieval_ms=round(total_ms, 2),
            semantic_candidates=len(sem_results),
            bm25_candidates=len(bm25_results),
        )

        metadata = RetrievalMetadata(
            semantic_results_count=len(sem_results),
            bm25_results_count=len(bm25_results),
            merged_candidates_count=len(fused),
            final_results_count=len(search_results),
            min_score_threshold=settings.HYBRID_MIN_SCORE,
            query_expansion_enabled=settings.QUERY_EXPANSION_ENABLED,
            expanded_query=expanded_query if expanded_query != query else None,
            rerank_enabled=settings.RERANK_ENABLED and reranked_flag,
            rerank_results_count=len(top_results_raw) if reranked_flag else 0,
            debug=debug_info,
        )

        return SearchResponse(
            query=query,
            project_id=project_id,
            results=search_results,
            citations=citations,
            source_documents=source_documents,
            context=context,
            metadata=metadata,
        )

    def _empty_response(self, project_id: str, query: str, top_k: int) -> SearchResponse:
        """Return an empty, safe SearchResponse when no results are found or query is blank."""
        return SearchResponse(
            query=query,
            project_id=project_id,
            results=[],
            citations=[],
            source_documents=[],
            context="",
            metadata=RetrievalMetadata(
                semantic_results_count=0,
                bm25_results_count=0,
                merged_candidates_count=0,
                final_results_count=0,
                min_score_threshold=settings.HYBRID_MIN_SCORE,
                query_expansion_enabled=settings.QUERY_EXPANSION_ENABLED,
                rerank_enabled=settings.RERANK_ENABLED,
            ),
        )
