"""
Context builder for Phase 3 Hybrid RAG.

Transforms a ranked list of SearchResult objects into an LLM-ready context string
and structured citations. This module is completely independent of any LLM —
it does NOT call Groq or any generation model.

Context format:
    SOURCE 1
    File: payments_requirements.pdf
    Page: 8
    Chunk: 21

    [chunk text]

    SOURCE 2
    File: auth_requirements.docx
    Chunk: 4

    [chunk text]

Rules:
  - Source boundaries are always preserved (no merging across chunks)
  - Truncation stops BEFORE adding a new chunk that would exceed MAX_CONTEXT_CHARS
  - Source metadata lines for included chunks are never cut
  - If no chunks are included, context = ""
"""
import logging
import os
from typing import Optional

from app.core.config import settings
from app.rag.retrieval.schemas import SearchResult, Citation, SourceDocument

logger = logging.getLogger(__name__)


def _build_citation_display(result: SearchResult) -> str:
    """
    Produce a human-readable citation string for a result.

    Examples:
      [Source: requirements.pdf, Page 8]
      [Source: requirements.docx, Chunk 12]
      [Source: data.xlsx, Sheet: Payments, Chunk 3]
      [Source: notes.txt, Chunk 7]
    """
    parts = [f"File: {result.file_name}"]
    if result.metadata.page_number is not None:
        parts.append(f"Page: {result.metadata.page_number}")
    if result.metadata.sheet_name:
        parts.append(f"Sheet: {result.metadata.sheet_name}")
    parts.append(f"Chunk: {result.chunk_index}")

    inner = ", ".join(parts)
    return f"[Source: {inner}]"


def _source_header(source_num: int, result: SearchResult) -> str:
    """
    Build the header block for a single source in the context string.
    """
    lines = [f"SOURCE {source_num}", f"File: {result.file_name}"]

    if result.metadata.page_number is not None:
        lines.append(f"Page: {result.metadata.page_number}")
    if result.metadata.sheet_name:
        lines.append(f"Sheet: {result.metadata.sheet_name}")
    lines.append(f"Chunk: {result.chunk_index}")

    return "\n".join(lines)


def _infer_source_type(file_name: str) -> str:
    """Derive source_type from file extension."""
    ext = os.path.splitext(file_name)[-1].lower().lstrip(".")
    return ext if ext else "unknown"


def build_context(
    results: list[SearchResult],
    max_chars: Optional[int] = None,
) -> tuple[str, list[Citation], list[SourceDocument]]:
    """
    Build an LLM-ready context string, citations, and source_documents from
    a ranked list of SearchResults.

    Truncation:
      - We stop adding chunks once adding the next header + text would exceed max_chars.
      - We never cut a header mid-way; either the full chunk is included or it's skipped.

    Returns:
        (context_text, citations, source_documents)
    """
    limit = max_chars if max_chars is not None else settings.MAX_CONTEXT_CHARS

    context_parts: list[str] = []
    citations: list[Citation] = []
    seen_docs: dict[str, str] = {}  # document_id -> file_name
    total_chars = 0

    for i, result in enumerate(results, start=1):
        header = _source_header(i, result)
        block = f"{header}\n\n{result.text}"
        block_chars = len(block)

        # Check if adding this block would exceed limit
        # (account for separator between blocks: "\n\n")
        separator = "\n\n" if context_parts else ""
        if total_chars + len(separator) + block_chars > limit:
            logger.debug(
                f"Context truncated at source {i} ({total_chars} chars used, limit={limit})"
            )
            break

        context_parts.append(block)
        total_chars += len(separator) + block_chars

        # Build citation for this chunk
        source_type = _infer_source_type(result.file_name)
        display_text = _build_citation_display(result)
        citation = Citation(
            document_id=result.document_id,
            file_name=result.file_name,
            source_type=source_type,
            chunk_index=result.chunk_index,
            page_number=result.metadata.page_number,
            sheet_name=result.metadata.sheet_name,
            display_text=display_text,
        )
        citations.append(citation)

        # Track contributing source documents (deduplicated)
        if result.document_id not in seen_docs:
            seen_docs[result.document_id] = result.file_name

    context_text = "\n\n".join(context_parts)
    source_documents = [
        SourceDocument(document_id=doc_id, file_name=fname)
        for doc_id, fname in seen_docs.items()
    ]

    logger.debug(
        f"Context built: {len(context_parts)} chunks, {total_chars} chars, "
        f"{len(source_documents)} source documents"
    )
    return context_text, citations, source_documents
