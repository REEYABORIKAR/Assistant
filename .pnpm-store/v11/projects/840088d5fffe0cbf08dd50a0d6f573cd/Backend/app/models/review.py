"""
Review Task model.

Tracks human review tasks for generated artifacts.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    artifact_id = Column(String, nullable=True, index=True)
    artifact_type = Column(String(50), nullable=False, default="requirement")
    reviewer_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    validation_score = Column(Float, nullable=True)
    comments = Column(Text, nullable=True)
    artifact_snapshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", backref="review_tasks")
    reviewer = relationship("User", backref="review_tasks")
