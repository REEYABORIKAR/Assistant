"""
Pydantic schemas for Phase 3 Hybrid RAG Retrieval.

These schemas define the request and response structures for the search API.
Internal implementation details (Chroma collection names, BM25 index paths, etc.)
are never exposed to the client.
"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for hybrid retrieval search."""
    query: str = Field(..., min_length=1, description="The search query (must not be empty or whitespace-only)")
    top_k: int = Field(default=8, ge=1, description="Number of final results to return")
    document_ids: list[str] | None = Field(
        default=None,
        description="Optional list of document IDs to restrict search to (must belong to the project)"
    )


class Citation(BaseModel):
    """
    Structured citation allowing the frontend or a future Requirement Agent to
    trace exactly which source supports which text.
    """
    document_id: str
    file_name: str
    source_type: str  # pdf | docx | xlsx | csv | txt | doc
    chunk_index: int
    page_number: int | None = None   # Only set if meaningfully available (PDFs)
    sheet_name: str | None = None    # Only set for xlsx/csv sources
    display_text: str                   # Human-readable citation line, e.g. "[Source: req.pdf, Page 8]"


class SourceDocument(BaseModel):
    """High-level summary of a document that contributed results."""
    document_id: str
    file_name: str


class SearchResultMetadata(BaseModel):
    """Per-result metadata, safe for client consumption."""
    chunk_index: int
    page_number: int | None = None
    sheet_name: str | None = None
    source_type: str | None = None


class SearchResult(BaseModel):
    """
    A single retrieval result from the Hybrid Retriever.
    Contains normalized scores and provenance metadata.
    retrieval_method tracks whether the chunk appeared in semantic, bm25, or both pools
    (useful for debugging, but not exposed in production by default).
    """
    chunk_id: str                          # Deterministic: {document_id}_{chunk_index}
    document_id: str
    project_id: str
    file_name: str
    chunk_index: int
    text: str
    semantic_score: float                  # Normalized 0..1, 0.0 if not in semantic pool
    bm25_score: float                      # Normalized 0..1, 0.0 if not in BM25 pool
    hybrid_score: float                    # Weighted fusion score
    rerank_score: float | None = None   # Cross-encoder logit, when reranking ran
    metadata: SearchResultMetadata
    retrieval_method: str | None = None  # "semantic" | "bm25" | "both" — only in debug mode


class RetrievalDebugInfo(BaseModel):
    """Debug timing info. Only included when RETRIEVAL_DEBUG=true."""
    semantic_search_ms: float
    bm25_search_ms: float
    fusion_ms: float
    total_retrieval_ms: float
    semantic_candidates: int
    bm25_candidates: int


class RetrievalMetadata(BaseModel):
    """Summary metadata returned with every search response."""
    semantic_results_count: int
    bm25_results_count: int
    merged_candidates_count: int
    final_results_count: int
    min_score_threshold: float
    query_expansion_enabled: bool = False
    expanded_query: str | None = None   # Populated when query expansion ran
    rerank_enabled: bool = False
    rerank_results_count: int = 0          # Number of results that were reranked
    debug: RetrievalDebugInfo | None = None  # Only populated when RETRIEVAL_DEBUG=true


class SearchResponse(BaseModel):
    """Complete response from the search endpoint."""
    query: str
    project_id: str
    results: list[SearchResult]
    citations: list[Citation]
    source_documents: list[SourceDocument]   # Documents that contributed at least one result
    context: str                             # LLM-ready context string, empty if no results
    metadata: RetrievalMetadata


class GenerateRequest(BaseModel):
    """
    Request body for LLM answer generation.

    Mirrors SearchRequest; generation internally runs the same hybrid
    retrieval pipeline and feeds the resulting context to the LLM.
    """
    query: str = Field(..., min_length=1, description="The question to answer (must not be empty or whitespace-only)")
    top_k: int = Field(default=8, ge=1, description="Number of retrieval results to use as context")
    document_ids: list[str] | None = Field(
        default=None,
        description="Optional list of document IDs to restrict retrieval to (must belong to the project)"
    )


class GenerateResponse(BaseModel):
    """Complete response from the answer-generation endpoint."""
    query: str
    project_id: str
    answer: str                              # LLM-generated answer (empty if not configured)
    configured: bool                         # False when no LLM provider is configured
    message: str | None = None            # Human-readable status when generation is unavailable
    citations: list[Citation] = []
    source_documents: list[SourceDocument] = []
    context: str = ""                        # Context actually sent to the LLM
    metadata: RetrievalMetadata | None = None
