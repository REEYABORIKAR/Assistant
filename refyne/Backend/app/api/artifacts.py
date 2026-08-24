import logging
from datetime import UTC, datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep
from app.models.artifact import Artifact
from app.models.project import Project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}/artifacts", tags=["artifacts"])


class ArtifactResponse(BaseModel):
    id: str
    project_id: str
    type: str
    title: str
    file_name: str
    version: str
    content: str
    status: str
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str
    updated_at: str


class ArtifactCreateRequest(BaseModel):
    type: str = Field(..., description="Document type, e.g. brd, srs, rtm, user_stories")
    title: str = Field(..., description="Display title")
    file_name: str = Field(..., description="File name e.g. BRD_E-Commerce_Platform.md")
    content: str = Field(..., description="Markdown or structured document content")
    version: str = Field(default="v1.0")


class ArtifactStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Status: approved, changes_requested, rejected, pending_validation")
    comments: str | None = None


def _get_project_or_404(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _artifact_to_response(art: Artifact) -> ArtifactResponse:
    return ArtifactResponse(
        id=art.id,
        project_id=art.project_id,
        type=art.type,
        title=art.title,
        file_name=art.file_name,
        version=art.version,
        content=art.content,
        status=art.status,
        approved_by=art.approved_by,
        approved_at=art.approved_at.isoformat() if art.approved_at else None,
        created_at=art.created_at.isoformat() if art.created_at else "",
        updated_at=art.updated_at.isoformat() if art.updated_at else "",
    )


@router.get("", response_model=list[ArtifactResponse])
def list_artifacts(project_id: str, db: SessionDep, current_user: CurrentUser, type: str | None = None) -> list[ArtifactResponse]:
    _get_project_or_404(db, project_id, current_user.id)
    query = db.query(Artifact).filter(Artifact.project_id == project_id)
    if type:
        query = query.filter(Artifact.type == type)
    artifacts = query.order_by(Artifact.created_at.desc()).all()
    return [_artifact_to_response(art) for art in artifacts]


@router.post("", response_model=ArtifactResponse, status_code=201)
def create_artifact(project_id: str, body: ArtifactCreateRequest, db: SessionDep, current_user: CurrentUser) -> ArtifactResponse:
    _get_project_or_404(db, project_id, current_user.id)
    artifact = Artifact(
        project_id=project_id,
        user_id=current_user.id,
        type=body.type,
        title=body.title,
        file_name=body.file_name,
        version=body.version,
        content=body.content,
        status="pending_validation",
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return _artifact_to_response(artifact)


@router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(project_id: str, artifact_id: str, db: SessionDep, current_user: CurrentUser) -> ArtifactResponse:
    _get_project_or_404(db, project_id, current_user.id)
    art = db.query(Artifact).filter(Artifact.id == artifact_id, Artifact.project_id == project_id).first()
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _artifact_to_response(art)


@router.put("/{artifact_id}/status", response_model=ArtifactResponse)
def update_artifact_status(
    project_id: str,
    artifact_id: str,
    body: ArtifactStatusUpdateRequest,
    db: SessionDep,
    current_user: CurrentUser
) -> ArtifactResponse:
    _get_project_or_404(db, project_id, current_user.id)
    art = db.query(Artifact).filter(Artifact.id == artifact_id, Artifact.project_id == project_id).first()
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")

    art.status = body.status
    if body.status == "approved":
        art.approved_by = current_user.full_name or current_user.email
        art.approved_at = datetime.now(UTC)

    db.commit()
    db.refresh(art)
    return _artifact_to_response(art)
