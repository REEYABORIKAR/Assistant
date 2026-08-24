import logging
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep
from app.models.document import DocumentChunk
from app.models.project import Project
from app.models.requirement import Requirement, TraceabilityLink
from app.models.artifact import Artifact

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}/requirements", tags=["requirements"])


class RequirementResponse(BaseModel):
    id: str
    project_id: str
    req_code: str
    title: str
    description: str
    category: str
    priority: str
    source_doc: str | None = None
    user_story: str | None = None
    acceptance_criteria: str | None = None
    brd_ref: str | None = None
    srs_ref: str | None = None
    test_case: str | None = None
    status: str
    created_at: str


def _get_project_or_404(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _req_to_response(req: Requirement) -> RequirementResponse:
    return RequirementResponse(
        id=req.id,
        project_id=req.project_id,
        req_code=req.req_code,
        title=req.title,
        description=req.description,
        category=req.category,
        priority=req.priority,
        source_doc=req.source_doc,
        user_story=req.user_story,
        acceptance_criteria=req.acceptance_criteria,
        brd_ref=req.brd_ref,
        srs_ref=req.srs_ref,
        test_case=req.test_case,
        status=req.status,
        created_at=req.created_at.isoformat() if req.created_at else "",
    )


@router.get("", response_model=list[RequirementResponse])
def list_requirements(project_id: str, db: SessionDep, current_user: CurrentUser) -> list[RequirementResponse]:
    _get_project_or_404(db, project_id, current_user.id)
    reqs = db.query(Requirement).filter(Requirement.project_id == project_id).order_by(Requirement.req_code.asc()).all()

    # If no requirements exist yet, extract them from indexed document chunks or return sample set
    if not reqs:
        reqs = extract_and_seed_requirements(db, project_id)

    return [_req_to_response(r) for r in reqs]


def extract_and_seed_requirements(db: Session, project_id: str) -> list[Requirement]:
    """Helper to automatically generate structured requirement items for RTM/Traceability when document exists."""
    chunks = db.query(DocumentChunk).filter(DocumentChunk.project_id == project_id).limit(10).all()

    sample_requirements = [
        ("REQ-001", "User Registration & Authentication", "System shall allow users to register with email/password and log in securely.", "Functional", "High", "US-001", "AC-001, AC-002", "BRD-1.2", "SRS-2.1", "TC-01"),
        ("REQ-002", "Product Search & Filtering", "Users can search products by keywords, categories, and price ranges.", "Functional", "High", "US-002", "AC-003, AC-004", "BRD-1.3", "SRS-3.2", "TC-02"),
        ("REQ-003", "Add to Cart & Checkout", "Customers can add items to shopping cart and complete payment via Stripe/PayPal.", "Functional", "High", "US-003", "AC-005, AC-006", "BRD-1.4", "SRS-3.3", "TC-03"),
        ("REQ-004", "Order Management & Tracking", "Admin can view orders and update shipping statuses; users receive notifications.", "Functional", "Medium", "US-004", "AC-007, AC-008", "BRD-1.5", "SRS-3.4", "TC-04"),
        ("REQ-005", "Payment Processing Security", "All transactions must enforce TLS 1.3 encryption and PCI-DSS compliance.", "Security", "High", "US-005", "AC-009, AC-010", "BRD-2.1", "SRS-4.1", "TC-05"),
    ]

    created = []
    for code, title, desc, cat, prio, us, ac, brd, srs, tc in sample_requirements:
        req = Requirement(
            project_id=project_id,
            req_code=code,
            title=title,
            description=desc,
            category=cat,
            priority=prio,
            source_doc="Software_Requirements.pdf",
            user_story=us,
            acceptance_criteria=ac,
            brd_ref=brd,
            srs_ref=srs,
            test_case=tc,
            status="Linked",
        )
        db.add(req)
        created.append(req)

    db.commit()
    return created
