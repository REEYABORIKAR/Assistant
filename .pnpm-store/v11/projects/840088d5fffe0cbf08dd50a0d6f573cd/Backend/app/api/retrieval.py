"""
Retrieval API endpoints for Phase 3 Hybrid RAG.

Endpoint:
    POST /api/projects/{project_id}/search

Security:
  - Requires valid JWT (authenticated user)
  - project_id ownership verified against authenticated user
  - document_ids verified to belong to the project (inside HybridRetriever)

No internal Chroma collection names, BM25 index paths, or filesystem paths
are exposed in the response.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.project import Project
from app.rag.retrieval.schemas import (
    SearchRequest,
    SearchResponse,
    GenerateRequest,
    GenerateResponse,
)
from app.rag.retrieval.hybrid import HybridRetriever
from app.services.generation import generate_answer
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["retrieval"])


def _get_project_for_user(db: Session, project_id: str, user_id: str) -> Project:
    """
    Verify that project_id exists AND belongs to the authenticated user.
    Returns 404 for both missing and unauthorized projects (no existence leak).
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/api/projects/{project_id}/search",
    response_model=SearchResponse,
    summary="Hybrid RAG search within a project",
    description=(
        "Performs hybrid retrieval (semantic + BM25) over the project's indexed documents. "
        "Optionally restrict search to specific document IDs. "
        "Returns ranked results, citations, context, and retrieval metadata."
    ),
)
def search_project(
    project_id: str,
    body: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    # --- Ownership check ---
    _get_project_for_user(db, project_id, current_user.id)

    # --- Input validation ---
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be empty or whitespace-only")

    # top_k bounds
    if body.top_k < 1:
        raise HTTPException(status_code=422, detail="top_k must be at least 1")
    if body.top_k > settings.RETRIEVAL_MAX_TOP_K:
        raise HTTPException(
            status_code=422,
            detail=f"top_k exceeds maximum allowed value of {settings.RETRIEVAL_MAX_TOP_K}",
        )

    # --- Run retrieval ---
    retriever = HybridRetriever(db)
    try:
        response = retriever.retrieve(
            project_id=project_id,
            query=query,
            top_k=body.top_k,
            document_ids=body.document_ids or None,
        )
    except ValueError as e:
        # document_id verification failure
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Retrieval failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Retrieval failed due to an internal error")

    return response


def _validate_generation_input(body: GenerateRequest, db: Session, project_id: str, user_id: str) -> None:
    """Shared ownership + input validation for the generate endpoint."""
    _get_project_for_user(db, project_id, user_id)
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be empty or whitespace-only")
    if body.top_k < 1:
        raise HTTPException(status_code=422, detail="top_k must be at least 1")
    if body.top_k > settings.RETRIEVAL_MAX_TOP_K:
        raise HTTPException(
            status_code=422,
            detail=f"top_k exceeds maximum allowed value of {settings.RETRIEVAL_MAX_TOP_K}",
        )


@router.post(
    "/api/projects/{project_id}/generate",
    response_model=GenerateResponse,
    summary="Generate a grounded answer from the project's documents",
    description=(
        "Runs the hybrid retrieval pipeline (semantic + BM25 + reranking) over the "
        "project's indexed documents, then asks a configured LLM (Groq) to answer "
        "the question strictly from the retrieved context. If no GROQ_API_KEY is "
        "configured, returns configured=false so clients can fall back gracefully."
    ),
)
def generate_answer_for_project(
    project_id: str,
    body: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerateResponse:
    _validate_generation_input(body, db, project_id, current_user.id)

    retriever = HybridRetriever(db)
    try:
        response = retriever.retrieve(
            project_id=project_id,
            query=body.query.strip(),
            top_k=body.top_k,
            document_ids=body.document_ids or None,
        )
    except ValueError as e:
        # document_id verification failure
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Retrieval failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Retrieval failed due to an internal error")

    generation = generate_answer(
        query=body.query.strip(),
        context=response.context,
        citations=response.citations,
    )

    return GenerateResponse(
        query=body.query.strip(),
        project_id=project_id,
        answer=generation["answer"],
        configured=generation["configured"],
        message=generation["message"],
        citations=response.citations,
        source_documents=response.source_documents,
        context=response.context,
        metadata=response.metadata,
    )
