"""
Audit Log Model.

Immutable append-only log for all significant actions:
upload, generate, validate, review, chat.

No UPDATE or DELETE operations are allowed on this table.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)
    tenant_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # upload, generate, validate, review, chat
    resource_type = Column(String(50), nullable=True)  # document, requirement, etc.
    resource_id = Column(String(36), nullable=True)
    trace_id = Column(String(16), nullable=True)
    details = Column(Text, nullable=True)  # JSON blob of action-specific details
    status = Column(String(20), nullable=True)  # success, failure
    model = Column(String(100), nullable=True)  # LLM model used, if applicable
    model_version = Column(String(50), nullable=True)  # model version
    prompt_version = Column(String(50), nullable=True)  # prompt version (nullable for now)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    old_value = Column(Text, nullable=True)  # previous state for changes
    new_value = Column(Text, nullable=True)  # new state for changes

    def __repr__(self):
        return f"<AuditLog id={self.id} action={self.action} user={self.user_id}>"
