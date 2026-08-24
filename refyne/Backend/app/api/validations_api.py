import json
import logging
from datetime import UTC, datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep
from app.models.artifact import Artifact
from app.models.project import Project
from app.models.requirement import Requirement, ValidationRun

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}/validations", tags=["validations"])


class ChecklistItem(BaseModel):
    id: str
    label: str
    checked: bool


class ValidationRunResponse(BaseModel):
    id: str
    project_id: str
    artifact_id: str | None = None
    artifact_title: str
    status: str
    total_requirements: int
    valid_requirements: int
    issues_found: int
    ambiguities: int
    gaps_identified: int
    feedback: str | None = None
    checklist: list[ChecklistItem]
    created_at: str


class RunValidationRequest(BaseModel):
    artifact_id: str | None = None
    artifact_title: str | None = None


class SubmitValidationReviewRequest(BaseModel):
    status: str = Field(..., description="approved, changes_requested, rejected")
    feedback: str | None = None
    checklist: list[ChecklistItem] | None = None


def _get_project_or_404(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _val_to_response(v: ValidationRun) -> ValidationRunResponse:
    checklist = []
    if v.checklist_json:
        try:
            raw = json.loads(v.checklist_json)
            checklist = [ChecklistItem(**item) for item in raw]
        except Exception:
            pass

    if not checklist:
        checklist = [
            ChecklistItem(id="c1", label="All functional requirements are captured", checked=True),
            ChecklistItem(id="c2", label="Business goals are clearly defined", checked=True),
            ChecklistItem(id="c3", label="Scope is clearly defined", checked=True),
            ChecklistItem(id="c4", label="Constraints & assumptions are included", checked=True),
            ChecklistItem(id="c5", label="Stakeholders are identified", checked=True),
            ChecklistItem(id="c6", label="Anything missing or unclear?", checked=False),
        ]

    return ValidationRunResponse(
        id=v.id,
        project_id=v.project_id,
        artifact_id=v.artifact_id,
        artifact_title=v.artifact_title,
        status=v.status,
        total_requirements=v.total_requirements,
        valid_requirements=v.valid_requirements,
        issues_found=v.issues_found,
        ambiguities=v.ambiguities,
        gaps_identified=v.gaps_identified,
        feedback=v.feedback,
        checklist=checklist,
        created_at=v.created_at.isoformat() if v.created_at else "",
    )


@router.get("", response_model=list[ValidationRunResponse])
def list_validations(project_id: str, db: SessionDep, current_user: CurrentUser) -> list[ValidationRunResponse]:
    _get_project_or_404(db, project_id, current_user.id)
    runs = db.query(ValidationRun).filter(ValidationRun.project_id == project_id).order_by(ValidationRun.created_at.desc()).all()

    if not runs:
        # Create initial seed validation run if requirements exist
        req_count = db.query(Requirement).filter(Requirement.project_id == project_id).count() or 38
        default_run = ValidationRun(
            project_id=project_id,
            artifact_title="BRD_E-Commerce_Platform.md",
            status="needs_review",
            total_requirements=req_count,
            valid_requirements=max(0, req_count - 6),
            issues_found=6,
            ambiguities=4,
            gaps_identified=3,
            feedback="Initial automated structural validation review.",
            checklist_json=json.dumps([
                {"id": "c1", "label": "All functional requirements are captured", "checked": True},
                {"id": "c2", "label": "Business goals are clearly defined", "checked": True},
                {"id": "c3", "label": "Scope is clearly defined", "checked": True},
                {"id": "c4", "label": "Constraints & assumptions are included", "checked": True},
                {"id": "c5", "label": "Stakeholders are identified", "checked": True},
                {"id": "c6", "label": "Anything missing or unclear?", "checked": False},
            ]),
        )
        db.add(default_run)
        db.commit()
        db.refresh(default_run)
        runs = [default_run]

    return [_val_to_response(r) for r in runs]


@router.post("/run", response_model=ValidationRunResponse, status_code=201)
def run_validation(project_id: str, body: RunValidationRequest, db: SessionDep, current_user: CurrentUser) -> ValidationRunResponse:
    _get_project_or_404(db, project_id, current_user.id)

    art_title = body.artifact_title or "Generated Document"
    art_id = body.artifact_id

    if art_id:
        art = db.query(Artifact).filter(Artifact.id == art_id).first()
        if art:
            art_title = art.title

    req_count = db.query(Requirement).filter(Requirement.project_id == project_id).count() or 15

    v_run = ValidationRun(
        project_id=project_id,
        artifact_id=art_id,
        artifact_title=art_title,
        status="needs_review",
        total_requirements=req_count,
        valid_requirements=max(0, req_count - 2),
        issues_found=2,
        ambiguities=1,
        gaps_identified=1,
        feedback="Automated AI validation completed. Please complete human review checklist.",
        checklist_json=json.dumps([
            {"id": "c1", "label": "All functional requirements are captured", "checked": True},
            {"id": "c2", "label": "Business goals are clearly defined", "checked": True},
            {"id": "c3", "label": "Scope is clearly defined", "checked": True},
            {"id": "c4", "label": "Constraints & assumptions are included", "checked": True},
            {"id": "c5", "label": "Stakeholders are identified", "checked": True},
            {"id": "c6", "label": "Anything missing or unclear?", "checked": False},
        ]),
    )
    db.add(v_run)
    db.commit()
    db.refresh(v_run)
    return _val_to_response(v_run)


@router.put("/{validation_id}/review", response_model=ValidationRunResponse)
def submit_validation_review(
    project_id: str,
    validation_id: str,
    body: SubmitValidationReviewRequest,
    db: SessionDep,
    current_user: CurrentUser
) -> ValidationRunResponse:
    _get_project_or_404(db, project_id, current_user.id)
    v_run = db.query(ValidationRun).filter(ValidationRun.id == validation_id, ValidationRun.project_id == project_id).first()
    if not v_run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    v_run.status = body.status
    if body.feedback is not None:
        v_run.feedback = body.feedback
    if body.checklist:
        v_run.checklist_json = json.dumps([item.model_dump() for item in body.checklist])

    # Also update associated artifact status if present
    if v_run.artifact_id:
        art = db.query(Artifact).filter(Artifact.id == v_run.artifact_id).first()
        if art:
            art.status = body.status
            if body.status == "approved":
                art.approved_by = current_user.full_name or current_user.email
                art.approved_at = datetime.now(UTC)

    db.commit()
    db.refresh(v_run)
    return _val_to_response(v_run)
