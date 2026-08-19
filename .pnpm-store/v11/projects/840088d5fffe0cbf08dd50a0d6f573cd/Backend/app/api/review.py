"""
Review Task API endpoints.

Provides endpoints for managing human review tasks:
- GET /api/reviews - List review tasks
- GET /api/reviews/{id} - Get a specific review task
- POST /api/reviews - Create a review task
- PUT /api/reviews/{id}/approve - Approve a review
- PUT /api/reviews/{id}/reject - Reject a review
- PUT /api/reviews/{id}/request-changes - Request changes
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.review import ReviewTask

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reviews"])


# ── Request/Response Schemas ───────────────────────────────────────────────────

class ReviewTaskCreate(BaseModel):
    """Input for creating a review task."""
    project_id: str = Field(..., description="Project ID")
    artifact_id: Optional[str] = Field(default=None, description="Artifact ID")
    artifact_type: str = Field(default="requirement", description="Type of artifact")
    validation_score: Optional[float] = Field(default=None, description="Validation score")
    comments: Optional[str] = Field(default=None, description="Initial comments")
    artifact_snapshot: Optional[str] = Field(default=None, description="JSON snapshot of the artifact")


class ReviewTaskResponse(BaseModel):
    """Output for a review task."""
    id: str
    project_id: str
    artifact_id: Optional[str]
    artifact_type: str
    reviewer_id: str
    status: str
    validation_score: Optional[float]
    comments: Optional[str]
    created_at: str
    updated_at: str


class ReviewActionRequest(BaseModel):
    """Input for approve/reject/request-changes actions."""
    comments: Optional[str] = Field(default=None, description="Reviewer comments")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_project_for_user(db: Session, project_id: str, user_id: str) -> Project:
    """Verify project ownership."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_review_task(db: Session, task_id: str, user_id: str) -> ReviewTask:
    """Get a review task and verify the user has access."""
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")

    # Verify the user owns the project
    _get_project_for_user(db, task.project_id, user_id)
    return task


def _review_task_to_response(task: ReviewTask) -> ReviewTaskResponse:
    """Convert a ReviewTask model to a response schema."""
    return ReviewTaskResponse(
        id=task.id,
        project_id=task.project_id,
        artifact_id=task.artifact_id,
        artifact_type=task.artifact_type,
        reviewer_id=task.reviewer_id,
        status=task.status,
        validation_score=task.validation_score,
        comments=task.comments,
        created_at=task.created_at.isoformat() if task.created_at else "",
        updated_at=task.updated_at.isoformat() if task.updated_at else "",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/reviews",
    response_model=list[ReviewTaskResponse],
    summary="List review tasks for the current user",
)
def list_reviews(
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReviewTaskResponse]:
    query = db.query(ReviewTask).filter(
        ReviewTask.reviewer_id == current_user.id,
    )
    if status:
        query = query.filter(ReviewTask.status == status)
    if project_id:
        query = query.filter(ReviewTask.project_id == project_id)

    tasks = query.order_by(ReviewTask.created_at.desc()).all()
    return [_review_task_to_response(t) for t in tasks]


@router.get(
    "/api/reviews/{task_id}",
    response_model=ReviewTaskResponse,
    summary="Get a specific review task",
)
def get_review(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    task = _get_review_task(db, task_id, current_user.id)
    return _review_task_to_response(task)


@router.post(
    "/api/reviews",
    response_model=ReviewTaskResponse,
    status_code=201,
    summary="Create a review task",
)
def create_review(
    body: ReviewTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    # Verify project ownership
    _get_project_for_user(db, body.project_id, current_user.id)

    task = ReviewTask(
        project_id=body.project_id,
        artifact_id=body.artifact_id,
        artifact_type=body.artifact_type,
        reviewer_id=current_user.id,
        status="pending",
        validation_score=body.validation_score,
        comments=body.comments,
        artifact_snapshot=body.artifact_snapshot,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    logger.info(f"Created review task {task.id} for project {body.project_id}")
    return _review_task_to_response(task)


@router.put(
    "/api/reviews/{task_id}/approve",
    response_model=ReviewTaskResponse,
    summary="Approve a review task",
)
def approve_review(
    task_id: str,
    body: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    task = _get_review_task(db, task_id, current_user.id)

    if task.status in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail=f"Review task is already {task.status}",
        )

    task.status = "approved"
    task.comments = body.comments or task.comments
    db.commit()
    db.refresh(task)

    logger.info(f"Approved review task {task_id}")
    return _review_task_to_response(task)


@router.put(
    "/api/reviews/{task_id}/reject",
    response_model=ReviewTaskResponse,
    summary="Reject a review task",
)
def reject_review(
    task_id: str,
    body: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    task = _get_review_task(db, task_id, current_user.id)

    if task.status in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail=f"Review task is already {task.status}",
        )

    task.status = "rejected"
    task.comments = body.comments or task.comments
    db.commit()
    db.refresh(task)

    logger.info(f"Rejected review task {task_id}")
    return _review_task_to_response(task)


@router.put(
    "/api/reviews/{task_id}/request-changes",
    response_model=ReviewTaskResponse,
    summary="Request changes on a review task",
)
def request_changes(
    task_id: str,
    body: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    task = _get_review_task(db, task_id, current_user.id)

    if task.status in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail=f"Review task is already {task.status}",
        )

    task.status = "changes_requested"
    task.comments = body.comments or task.comments
    db.commit()
    db.refresh(task)

    logger.info(f"Changes requested on review task {task_id}")
    return _review_task_to_response(task)
