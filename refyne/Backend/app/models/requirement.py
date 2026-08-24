import uuid
from datetime import UTC, datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    req_code = Column(String(50), nullable=False)  # REQ-001, REQ-002, etc.
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="Functional")  # Functional, Non-Functional, Business, Security
    priority = Column(String(20), nullable=False, default="High")  # High, Medium, Low

    source_doc = Column(String(255), nullable=True)
    user_story = Column(Text, nullable=True)
    acceptance_criteria = Column(Text, nullable=True)
    brd_ref = Column(String(50), nullable=True)
    srs_ref = Column(String(50), nullable=True)
    test_case = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="Linked")  # Linked, Unlinked, Pending

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    project = relationship("Project", backref="requirements")


class TraceabilityLink(Base):
    __tablename__ = "traceability_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False)
    artifact_id = Column(String(36), nullable=True)
    link_type = Column(String(50), nullable=False, default="BRD_TO_SRS")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    requirement = relationship("Requirement", backref="traceability_links")


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_id = Column(String(36), nullable=True)
    artifact_title = Column(String(255), nullable=False)

    status = Column(String(50), nullable=False, default="needs_review")  # approved, needs_review, changes_requested
    total_requirements = Column(Integer, default=0)
    valid_requirements = Column(Integer, default=0)
    issues_found = Column(Integer, default=0)
    ambiguities = Column(Integer, default=0)
    gaps_identified = Column(Integer, default=0)

    feedback = Column(Text, nullable=True)
    checklist_json = Column(Text, nullable=True)  # JSON string of checklist items

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    project = relationship("Project", backref="validation_runs")
