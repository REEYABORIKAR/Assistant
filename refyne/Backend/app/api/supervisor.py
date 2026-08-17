"""
Supervisor API endpoint.

Endpoint:
    POST /api/projects/{project_id}/supervisor

Security:
  - Requires valid JWT (authenticated user)
  - project_id ownership verified against authenticated user
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.project import Project
from app.agents.supervisor.service import (
    handle_request,
    SupervisorRequest,
    SupervisorResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["supervisor"])


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
    "/api/projects/{project_id}/supervisor",
    response_model=SupervisorResponse,
    summary="Classify user intent and determine routing",
    description=(
        "Processes a user query through the Supervisor Agent. "
        "Classifies the intent using LLM, determines the appropriate route, "
        "and returns a routing decision. Does NOT execute downstream agents."
    ),
)
def classify_and_route(
    project_id: str,
    body: SupervisorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SupervisorResponse:
    # --- Ownership check ---
    _get_project_for_user(db, project_id, current_user.id)

    # --- Input validation ---
    query = body.user_query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="user_query must not be empty or whitespace-only")

    if body.confidence_threshold < 0.0 or body.confidence_threshold > 1.0:
        raise HTTPException(status_code=422, detail="confidence_threshold must be between 0.0 and 1.0")

    # --- Run supervisor ---
    try:
        response = handle_request(
            user_id=current_user.id,
            project_id=project_id,
            user_query=query,
            session_id=body.session_id,
            confidence_threshold=body.confidence_threshold,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Supervisor classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Classification failed due to an internal error")
