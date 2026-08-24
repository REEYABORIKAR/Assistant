"""
Audit Log API endpoint.

Admin-only endpoint for querying the immutable audit trail.

Endpoint:
    GET /api/projects/{project_id}/audit-log

Security:
  - Requires valid JWT
  - Only ADMIN role (project owner or ADMIN member) can query audit logs
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.roles import ProjectRole
from app.models.audit_log import AuditLog
from app.models.membership import ProjectMember
from app.models.project import Project
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audit-log"])


# ── Response Schema ───────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    id: str
    timestamp: str
    user_id: str
    project_id: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    trace_id: str | None = None
    details: str | None = None
    status: str | None = None


class AuditLogResponse(BaseModel):
    """Audit log query response."""
    entries: list[AuditLogEntry]
    total: int
    project_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_admin_user(db: Session, project_id: str, user_id: str) -> None:
    """Verify user is ADMIN of this project. Raises 403 if not."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id == user_id:
        return  # Owner is always ADMIN

    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if membership and membership.role == ProjectRole.ADMIN.value:
        return

    raise HTTPException(status_code=403, detail="Only project admins can view audit logs")


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/api/projects/{project_id}/audit-log",
    response_model=AuditLogResponse,
    summary="Query audit log (admin only)",
    description="Returns immutable audit trail entries for the project. Admin-only.",
)
def query_audit_log(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    action: str | None = Query(None, description="Filter by action type"),
    user_id: str | None = Query(None, description="Filter by user_id"),
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> AuditLogResponse:
    # --- Admin check ---
    _get_admin_user(db, project_id, current_user.id)

    # --- Build query ---
    query = db.query(AuditLog).filter(AuditLog.project_id == project_id)

    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    total = query.count()
    entries = (
        query
        .order_by(desc(AuditLog.timestamp))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return AuditLogResponse(
        entries=[
            AuditLogEntry(
                id=e.id,
                timestamp=e.timestamp.isoformat(),
                user_id=e.user_id,
                project_id=e.project_id,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                trace_id=e.trace_id,
                details=e.details,
                status=e.status,
            )
            for e in entries
        ],
        total=total,
        project_id=project_id,
    )
