"""
Retrieval API endpoints for Phase 3 Hybrid RAG.

Endpoint:
    POST /api/projects/{project_id}/search

Security:
  - Requires valid JWT (authenticated user)
  - project_id ownership verified against authenticated user OR project membership
  - document_ids verified to belong to the project (inside HybridRetriever)
  - Chunks filtered by user's role via allowed_roles metadata
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.audit import write_audit_log
from app.core.config import settings
from app.core.roles import ProjectRole
from app.models.membership import ProjectMember
from app.models.project import Project
from app.models.user import User
from app.rag.retrieval.hybrid import HybridRetriever
from app.rag.retrieval.schemas import (
    GenerateRequest,
    GenerateResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["retrieval"])


def _get_project_for_user(db: Session, project_id: str, user_id: str) -> tuple[Project, str]:
    """
    Verify that project_id exists AND user has access (owner or member).
    Returns (project, user_role).
    Raises 404 for missing or unauthorized projects.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id == user_id:
        return project, ProjectRole.ADMIN.value

    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if membership:
        return project, membership.role

    raise HTTPException(status_code=404, detail="Project not found")


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
    _project, user_role = _get_project_for_user(db, project_id, current_user.id)

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
    trace_id = uuid.uuid4().hex[:16]
    retriever = HybridRetriever(db)
    try:
        response = retriever.retrieve(
            project_id=project_id,
            query=query,
            top_k=body.top_k,
            document_ids=body.document_ids or None,
            user_role=user_role,
            trace_id=trace_id,
        )
    except ValueError as e:
        # document_id verification failure
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Retrieval failed",
            extra={"project_id": project_id, "trace_id": trace_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Retrieval failed due to an internal error")

    return response


def _validate_generation_input(body: GenerateRequest, db: Session, project_id: str, user_id: str) -> tuple[str, str]:
    """Shared ownership + input validation for the generate endpoint. Returns (project_id, user_role)."""
    _project, user_role = _get_project_for_user(db, project_id, user_id)
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
    _project, user_role = _validate_generation_input(body, db, project_id, current_user.id)

    trace_id = uuid.uuid4().hex[:16]
    retriever = HybridRetriever(db)
    try:
        response = retriever.retrieve(
            project_id=project_id,
            query=body.query.strip(),
            top_k=body.top_k,
            document_ids=body.document_ids or None,
            user_role=user_role,
            trace_id=trace_id,
        )
    except ValueError as e:
        # document_id verification failure
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Retrieval failed",
            extra={"project_id": project_id, "trace_id": trace_id, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Retrieval failed due to an internal error")

    generation = generate_answer(
        query=body.query.strip(),
        context=response.context,
        citations=response.citations,
        trace_id=trace_id,
    )

    # Write audit log
    write_audit_log(
        db,
        user_id=current_user.id,
        project_id=project_id,
        action="GENERATE_REQUIREMENTS",
        resource_type="generation",
        resource_id=None,
        trace_id=trace_id,
        details={"query": body.query.strip()[:200], "configured": generation["configured"], "results_count": len(response.results)},
        status="success",
    )
    db.commit()

    # Fail-closed: when no context and config disallows generation without context
    if (not response.context or not response.context.strip()) and not settings.ALLOW_GENERATION_WITHOUT_CONTEXT:
        return GenerateResponse(
            query=body.query.strip(),
            project_id=project_id,
            answer=None,
            configured=generation["configured"],
            message="No relevant context found. Generation refused without source material.",
            citations=response.citations,
            source_documents=response.source_documents,
            context=response.context,
            metadata=response.metadata,
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
