import uuid
from datetime import UTC, datetime
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    type = Column(String(50), nullable=False)  # brd, srs, rtm, user_stories, acceptance_criteria, etc.
    title = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    version = Column(String(20), nullable=False, default="v1.0")
    content = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="pending_validation")  # pending_validation, approved, changes_requested, rejected

    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    project = relationship("Project", backref="artifacts")
