import logging
from datetime import UTC, datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep
from app.models.document import Document
from app.models.project import Project
from app.models.requirement import Requirement, ValidationRun
from app.models.artifact import Artifact
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class RecentProjectItem(BaseModel):
    id: str
    name: str
    updated_at: str
    documents_count: int
    requirements_count: int


class RecentActivityItem(BaseModel):
    id: str
    action: str
    description: str
    timestamp: str
    project_name: str | None = None


class DashboardStatsResponse(BaseModel):
    total_projects: int
    total_documents: int
    total_requirements: int
    total_validations: int
    recent_projects: list[RecentProjectItem]
    recent_activities: list[RecentActivityItem]


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(db: SessionDep, current_user: CurrentUser) -> DashboardStatsResponse:
    # 1. Total projects for current user
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    project_ids = [p.id for p in projects]

    total_projects = len(projects)

    if not project_ids:
        return DashboardStatsResponse(
            total_projects=0,
            total_documents=0,
            total_requirements=0,
            total_validations=0,
            recent_projects=[],
            recent_activities=[],
        )

    # 2. Total documents
    total_documents = db.query(Document).filter(Document.project_id.in_(project_ids)).count()

    # 3. Total requirements
    total_requirements = db.query(Requirement).filter(Requirement.project_id.in_(project_ids)).count()

    # 4. Total validations
    total_validations = db.query(ValidationRun).filter(ValidationRun.project_id.in_(project_ids)).count()

    # 5. Recent projects list with item counts
    recent_projects_data = []
    sorted_projects = sorted(projects, key=lambda p: p.updated_at or p.created_at, reverse=True)[:5]
    for p in sorted_projects:
        doc_count = db.query(Document).filter(Document.project_id == p.id).count()
        req_count = db.query(Requirement).filter(Requirement.project_id == p.id).count()
        recent_projects_data.append(RecentProjectItem(
            id=p.id,
            name=p.name,
            updated_at=(p.updated_at or p.created_at).isoformat() if (p.updated_at or p.created_at) else "",
            documents_count=doc_count,
            requirements_count=req_count,
        ))

    # 6. Recent activity from AuditLog and Artifacts
    recent_activities = []

    # Get recent artifacts generated
    artifacts = db.query(Artifact).filter(Artifact.project_id.in_(project_ids)).order_by(Artifact.created_at.desc()).limit(5).all()
    project_map = {p.id: p.name for p in projects}

    for art in artifacts:
        p_name = project_map.get(art.project_id, "Project")
        recent_activities.append(RecentActivityItem(
            id=art.id,
            action="ARTIFACT_GENERATED",
            description=f"{art.title} generated for {p_name}",
            timestamp=art.created_at.isoformat() if art.created_at else "",
            project_name=p_name,
        ))

    # Get recent document uploads
    docs = db.query(Document).filter(Document.project_id.in_(project_ids)).order_by(Document.created_at.desc()).limit(5).all()
    for d in docs:
        p_name = project_map.get(d.project_id, "Project")
        recent_activities.append(RecentActivityItem(
            id=d.id,
            action="DOCUMENT_UPLOADED",
            description=f"Document {d.file_name} uploaded to {p_name}",
            timestamp=d.created_at.isoformat() if d.created_at else "",
            project_name=p_name,
        ))

    # Get recent validation runs
    validations = db.query(ValidationRun).filter(ValidationRun.project_id.in_(project_ids)).order_by(ValidationRun.created_at.desc()).limit(5).all()
    for v in validations:
        p_name = project_map.get(v.project_id, "Project")
        recent_activities.append(RecentActivityItem(
            id=v.id,
            action="VALIDATION_COMPLETED",
            description=f"Validation completed for {v.artifact_title}",
            timestamp=v.created_at.isoformat() if v.created_at else "",
            project_name=p_name,
        ))

    # Sort all activity items by timestamp descending
    recent_activities.sort(key=lambda x: x.timestamp, reverse=True)
    recent_activities = recent_activities[:10]

    return DashboardStatsResponse(
        total_projects=total_projects,
        total_documents=total_documents,
        total_requirements=total_requirements,
        total_validations=total_validations,
        recent_projects=recent_projects_data,
        recent_activities=recent_activities,
    )
