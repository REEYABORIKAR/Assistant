"""
Audit Log Writer.

Append-only writer for the immutable audit_log table.
All actions (upload, generate, validate, review, chat) write entries here.

IMPORTANT: This table is append-only. Never add UPDATE or DELETE code paths.
"""
import json
import logging

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def write_audit_log(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    trace_id: str | None = None,
    details: dict | None = None,
    status: str = "success",
    tenant_id: str | None = None,
    model: str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
    ip_address: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> AuditLog:
    """
    Write an immutable audit log entry.

    Args:
        db: SQLAlchemy session (must be committed by caller or in same transaction).
        user_id: Authenticated user who performed the action.
        project_id: Project scope of the action.
        action: Action type (upload, generate, validate, review, chat).
        resource_type: Type of resource affected (document, requirement, etc.).
        resource_id: ID of the affected resource.
        trace_id: Request trace ID for correlation.
        details: JSON-serializable dict of action-specific details.
        status: Outcome (success, failure).
        tenant_id: Tenant scope (if multi-tenant).
        model: LLM model name used for generation, if applicable.
        model_version: LLM model version, if applicable.
        prompt_version: Prompt template version, if versioning exists.
        ip_address: Client IP address (IPv4 or IPv6).
        old_value: Previous state for change events (JSON string).
        new_value: New state for change events (JSON string).

    Returns:
        The created AuditLog entry.
    """
    entry = AuditLog(
        user_id=user_id,
        project_id=project_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        trace_id=trace_id,
        details=json.dumps(details) if details else None,
        status=status,
        tenant_id=tenant_id,
        model=model,
        model_version=model_version,
        prompt_version=prompt_version,
        ip_address=ip_address,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    db.flush()  # Get the ID without committing
    logger.debug(
        "Audit log written",
        extra={"action": action, "user_id": user_id, "project_id": project_id, "trace_id": trace_id},
    )
    return entry
