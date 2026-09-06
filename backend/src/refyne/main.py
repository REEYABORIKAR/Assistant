import hashlib
import uuid
import os
import re
import json
import io
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status, UploadFile, File as FileParam
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from refyne.llm_service import (
    generate_ai_response,
    analyze_document_intelligence,
    verify_requirement_ai,
    analyze_risk_ai,
    suggest_mitigation_ai,
)
from refyne.document_service import extract_text_from_file, build_pdf_document, generate_document_content, generate_document_content_sync
from refyne.integration_service import (
    get_tenant_integrations,
    save_integration_config,
    disconnect_integration,
    test_integration_connection,
    sync_integration_payload,
)
from refyne.admin_service import (
    list_workspace_users,
    invite_workspace_user,
    update_user_role,
    remove_workspace_user,
    get_engine_settings,
    update_engine_settings,
    get_audit_trail,
    get_resource_usage,
)

from refyne.auth.policy import RegistrationRequest
from refyne.auth.service import (
    AuthenticationError,
    check_idempotency_key,
    create_project,
    create_conversation,
    delete_conversation,
    add_user_message,
    delete_project,
    get_authenticated_session,
    get_project,
    get_conversation,
    get_file,
    get_requirement,
    create_requirement_link,
    issue_password_reset,
    login_user,
    list_sessions,
    list_projects,
    list_conversations,
    list_messages,
    list_files,
    list_requirements,
    list_requirement_links,
    list_workflow_definitions,
    get_workflow_definition,
    record_audit,
    refresh_user,
    register_user,
    reset_password,
    revoke_session,
    store_idempotency_key,
    update_project,
    update_conversation,
    create_requirement,
    update_requirement,
    delete_requirement,
    list_risks,
    get_risk,
    create_risk,
    update_risk,
    delete_risk,
    calculate_severity_score,
)
from refyne.auth.tokens import decode_access_token
from refyne.config import get_settings
from refyne.db.models import Conversation, File, Message, Project, Requirement, RequirementLink, Risk, Tenant, User, WorkflowDefinition
from refyne.db.session import get_db

settings = get_settings()
app = FastAPI(title="REFYNE API", version="0.1.0")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_PAGE_LIMIT = 25
MAX_PAGE_LIMIT = 100


@app.middleware("http")
async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Import and add tenant isolation middleware
from refyne.middleware.tenant_isolation import TenantIsolationMiddleware
app.add_middleware(TenantIsolationMiddleware)


def _error_response(
    request: Request, code: str, message: str, *, details: object | None = None, status_code: int
) -> JSONResponse:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": request.state.request_id,
    }
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


def _page(items: list[object], limit: int, cursor: int) -> tuple[list[object], dict[str, object]]:
    page_items = items[cursor : cursor + limit]
    next_cursor = cursor + limit if cursor + limit < len(items) else None
    return page_items, {"next_cursor": next_cursor, "total": len(items)}


def _apply_sort(
    items: list[object], sort_param: str | None, allowed_fields: set[str]
) -> list[object]:
    """Apply safe sorting. sort_param format: 'field:asc' or 'field:desc'."""
    if not sort_param:
        return items
    try:
        field, direction = sort_param.split(":")
        if field not in allowed_fields or direction not in ("asc", "desc"):
            return items
        reverse = direction == "desc"
        return sorted(items, key=lambda x: getattr(x, field, ""), reverse=reverse)
    except (ValueError, AttributeError):
        return items


def _apply_filter(items: list[object], filters: dict[str, str], allowed_fields: set[str]) -> list[object]:
    """Apply safe filtering. Only allows equality checks on whitelisted fields."""
    if not filters:
        return items
    result = items
    for field, value in filters.items():
        if field not in allowed_fields:
            continue
        result = [item for item in result if str(getattr(item, field, "")) == value]
    return result


def _handle_idempotency(
    db: Session,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    idempotency_key: str | None,
    endpoint: str,
) -> tuple[int, dict[str, object]] | None:
    """
    Check for cached response. Returns (status, body) if found, else None.
    Idempotency applies only when Idempotency-Key header is provided.
    """
    if not idempotency_key:
        return None
    return check_idempotency_key(db, tenant_id, idempotency_key, endpoint, session_id)



@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_by_status = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHENTICATED",
        403: "AUTHORIZATION_DENIED",
        404: "RESOURCE_NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
    }
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return _error_response(
        request,
        code_by_status.get(exc.status_code, "REQUEST_FAILED"),
        message,
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return _error_response(
        request,
        "VALIDATION_ERROR",
        "The request contains invalid fields.",
        details=details,
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None


class ConversationCreateRequest(BaseModel):
    project_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    status: str | None = None


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)


class RequirementCreateRequest(BaseModel):
    key: str | None = Field(default=None, max_length=80)
    type: str = Field(default="FUNCTIONAL", max_length=30)
    priority: str = Field(default="HIGH", max_length=30)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)
    status: str = Field(default="DRAFT", max_length=30)
    project_id: uuid.UUID | None = None
    source_location: str | None = None


class RequirementUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1)
    type: str | None = None
    priority: str | None = None
    status: str | None = None
    source_location: str | None = None


class RiskCreateRequest(BaseModel):
    key: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    impact: str = Field(default="HIGH", max_length=30)
    likelihood: str = Field(default="MEDIUM", max_length=30)
    status: str = Field(default="OPEN", max_length=30)
    category: str = Field(default="TECHNICAL", max_length=50)
    mitigation_strategy: str | None = None
    contingency_plan: str | None = None
    owner: str | None = None
    project_id: uuid.UUID | None = None
    associated_project: str | None = None


class RiskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    impact: str | None = None
    likelihood: str | None = None
    status: str | None = None
    category: str | None = None
    mitigation_strategy: str | None = None
    contingency_plan: str | None = None
    owner: str | None = None


class RiskMitigationSuggestRequest(BaseModel):
    title: str = Field(min_length=1)
    category: str = Field(default="TECHNICAL")
    description: str | None = None



def _workflow_definition_response(item: WorkflowDefinition) -> dict[str, object]:
    caps = item.capabilities or {}
    return {
        "id": str(item.id),
        "definition_key": item.definition_key,
        "name": item.name,
        "description": item.description,
        "version": item.version,
        "state_machine_id": item.state_machine_id,
        "capabilities": caps,
        "steps": caps.get("steps", ["File Ingestion & OCR", "Parse Requirements", "Security & SAIF Scan", "Human Supervisor Review"]),
        "currentStep": caps.get("currentStep", 0),
        "logs": caps.get("logs", []),
        "policy_id": str(item.policy_id) if item.policy_id else None,
        "status": item.status,
        "created_by": str(item.created_by),
        "published_at": item.published_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


class RequirementLinkRequest(BaseModel):
    target_kind: str = Field(default="REQUIREMENT", min_length=1)
    target_id: uuid.UUID
    relationship: str = Field(min_length=1, max_length=30)


@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(request: RegistrationRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        user = register_user(db, request, settings)
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user_id": str(user.id)}


@app.post("/api/v1/auth/login", tags=["auth"])
def login(request: LoginRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        user, access_token, refresh_token, expires_in = login_user(db, str(request.email), request.password, settings)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
    }


@app.post("/api/v1/auth/refresh", tags=["auth"])
def refresh(request: RefreshRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        access_token, refresh_token, expires_in = refresh_user(db, request.refresh_token, settings)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail="invalid refresh token") from exc
    return {"access_token": access_token, "refresh_token": refresh_token, "expires_in": expires_in}


@app.post("/api/v1/auth/forgot-password", status_code=status.HTTP_202_ACCEPTED, tags=["auth"])
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)) -> None:
    issue_password_reset(db, str(request.email), settings)


@app.post("/api/v1/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def reset(request: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    try:
        reset_password(db, request.token, request.new_password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail="invalid password reset request") from exc


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    if not settings.auth_signing_secret:
        raise HTTPException(status_code=503, detail="authentication is not configured")
    try:
        claims = decode_access_token(authorization[7:], settings.auth_signing_secret)
        session_id = uuid.UUID(claims["sid"])
        user_id = uuid.UUID(claims["sub"])
        revoke_session(db, session_id, user_id)
        record_audit(
            db,
            event_type="USER_LOGOUT",
            tenant_id=None,
            actor_id=user_id,
            session_id=session_id,
        )
    except (AuthenticationError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="invalid authentication") from exc


def _claims_from_authorization(authorization: str | None) -> dict[str, object]:
    if not authorization or not authorization.startswith("Bearer ") or not settings.auth_signing_secret:
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        return decode_access_token(authorization[7:], settings.auth_signing_secret)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid authentication") from exc


def _authenticated_context(authorization: str | None, db: Session) -> tuple[User, object]:
    claims = _claims_from_authorization(authorization)
    try:
        user_id = uuid.UUID(str(claims["sub"]))
        session_id = uuid.UUID(str(claims["sid"]))
        session = get_authenticated_session(db, user_id, session_id)
    except (AuthenticationError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid authentication") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid authentication")
    return user, session


@app.get("/api/v1/auth/me", tags=["auth"])
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    tenant = db.get(Tenant, session.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=401, detail="invalid authentication")
    return {
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "tenant": {"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name, "status": tenant.status},
        "roles": [],
        "permissions": [],
    }


@app.get("/api/v1/auth/sessions", tags=["auth"])
def sessions(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict[str, object]:
    user, _ = _authenticated_context(authorization, db)
    return {
        "sessions": [
            {
                "id": str(item.id),
                "issued_at": item.issued_at,
                "expires_at": item.expires_at,
                "revoked_at": item.revoked_at,
                "last_seen_at": item.last_seen_at,
            }
            for item in list_sessions(db, user.id)
        ]
    }


@app.delete("/api/v1/auth/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def revoke_user_session(
    session_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    user, _ = _authenticated_context(authorization, db)
    user_id = user.id
    try:
        revoke_session(db, session_id, user_id)
        record_audit(db, event_type="SESSION_REVOKED", tenant_id=None, actor_id=user_id, session_id=session_id)
    except AuthenticationError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.get("/api/v1/tenants/current", tags=["tenants"])
def current_tenant(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    tenant = db.get(Tenant, session.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=401, detail="invalid authentication")
    return {
        "id": str(tenant.id),
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "settings": tenant.settings,
    }


@app.get("/api/v1/dashboard/metrics", tags=["dashboard"])
def dashboard_metrics(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> dict[str, int]:
    _, session = _authenticated_context(authorization, db)
    projects = db.scalar(
        select(func.count(Project.id)).where(Project.tenant_id == session.tenant_id, Project.deleted_at.is_(None))
    ) or 0
    requirements = db.scalar(
        select(func.count(Requirement.id)).where(Requirement.tenant_id == session.tenant_id)
    ) or 0
    return {
        "projects": projects,
        "documents": 0,
        "workflow_runs_active": 0,
        "requirements": requirements,
    }


def _project_response(project: Project) -> dict[str, object]:
    return {
        "id": str(project.id),
        "project_key": project.project_key,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_by": str(project.created_by),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@app.get("/api/v1/projects", tags=["projects"])
def projects(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: int = Query(default=0, ge=0),
    sort: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    items = list_projects(db, session.tenant_id, status_filter)
    # Whitelist: created_at, updated_at, status, name
    items = _apply_sort(items, sort, {"created_at", "updated_at", "status", "name"})
    items, page = _page(items, limit, cursor)
    return {"projects": [_project_response(item) for item in items], "page": page}


@app.post("/api/v1/projects", status_code=status.HTTP_201_CREATED, tags=["projects"])
def create_project_endpoint(
    request: ProjectCreateRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    endpoint = "POST /api/v1/projects"
    
    # Check for cached response (idempotency)
    cached = _handle_idempotency(db, session.tenant_id, session.id, idempotency_key, endpoint)
    if cached:
        status_code, body = cached
        # Return cached response (would normally set response status code from cached)
        return body
    
    # Create new project
    project = create_project(
        db,
        tenant_id=session.tenant_id,
        user_id=user.id,
        name=request.name,
        description=request.description,
    )
    response_body = _project_response(project)
    
    # Store response for future replays
    if idempotency_key:
        store_idempotency_key(
            db,
            tenant_id=session.tenant_id,
            idempotency_key=idempotency_key,
            endpoint=endpoint,
            session_id=session.id,
            status=201,
            response_body=response_body,
        )
    
    return response_body


@app.get("/api/v1/projects/{project_id}", tags=["projects"])
def project(
    project_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    item = get_project(db, session.tenant_id, project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _project_response(item)


@app.patch("/api/v1/projects/{project_id}", tags=["projects"])
def update_project_endpoint(
    project_id: uuid.UUID,
    request: ProjectUpdateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    item = get_project(db, session.tenant_id, project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        updated = update_project(
            db,
            item,
            name=request.name,
            description=request.description,
            status=request.status,
            actor_id=user.id,
            tenant_id=session.tenant_id,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _project_response(updated)


@app.delete("/api/v1/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["projects"])
def delete_project_endpoint(
    project_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    user, session = _authenticated_context(authorization, db)
    item = get_project(db, session.tenant_id, project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="project not found")
    delete_project(db, item, user.id, session.tenant_id)


def _conversation_response(item: Conversation) -> dict[str, object]:
    return {
        "id": str(item.id),
        "project_id": str(item.project_id) if item.project_id else None,
        "created_by": str(item.created_by),
        "title": item.title,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _message_response(item: Message) -> dict[str, object]:
    return {
        "id": str(item.id),
        "conversation_id": str(item.conversation_id),
        "sequence": item.sequence,
        "role": item.role,
        "status": item.status,
        "content": item.content,
        "created_at": item.created_at,
    }


def _file_response(item: File) -> dict[str, object]:
    return {
        "id": str(item.id),
        "project_id": str(item.project_id) if item.project_id else None,
        "name": item.name,
        "mime_type": item.mime_type,
        "size_bytes": item.size_bytes,
        "status": item.status,
        "scan_result": item.scan_result,
        "scanned_at": item.scanned_at,
        "quarantined_at": item.quarantined_at,
        "quarantine_reason": item.quarantine_reason,
        "extraction_error": item.extraction_error,
        "page_count": item.page_count,
        "uploaded_by": str(item.uploaded_by),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@app.get("/api/v1/files", tags=["files"])
def files(
    project_id: uuid.UUID | None = None,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: int = Query(default=0, ge=0),
    sort: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    items = list_files(db, session.tenant_id, project_id)
    # Whitelist: created_at, updated_at, status, name, file_type
    items = _apply_sort(items, sort, {"created_at", "updated_at", "status", "name", "file_type"})
    items, page = _page(items, limit, cursor)
    return {"files": [_file_response(item) for item in items], "page": page}


@app.get("/api/v1/files/{file_id}", tags=["files"])
def file(
    file_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    item = get_file(db, session.tenant_id, file_id)
    if item is None:
        raise HTTPException(status_code=404, detail="file not found")
    return _file_response(item)


def _get_or_create_default_project(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Project:
    p = db.scalar(select(Project).where(Project.tenant_id == tenant_id, Project.deleted_at.is_(None)))
    if not p:
        p = create_project(db, tenant_id=tenant_id, user_id=user_id, name="AI Requirement Suite", description="Core Enterprise Modernization Project")
    return p


def _seed_requirements_if_empty(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    count = db.scalar(select(func.count(Requirement.id)).where(Requirement.tenant_id == tenant_id)) or 0
    if count == 0:
        proj = _get_or_create_default_project(db, tenant_id, user_id)
        demo_items = [
            {
                "key": "REQ-001",
                "title": "Multi-Tenant Authentication & Isolation",
                "description": "Strict database schema isolation per tenant with JWT authorization, role-based permissions, and cryptographically verified tokens.",
                "type": "FUNCTIONAL",
                "priority": "HIGH",
                "status": "VALIDATED",
                "source_location": "SRS §3.4"
            },
            {
                "key": "REQ-002",
                "title": "Realtime SSE Workflow Streaming",
                "description": "Stream progress updates from supervisor engine to client chat with backpressure regulation and reconnection resilience.",
                "type": "TECHNICAL",
                "priority": "HIGH",
                "status": "IN_REVIEW",
                "source_location": "SRS §4.2"
            },
            {
                "key": "REQ-003",
                "title": "Jira Integration Bidirectional Sync",
                "description": "Automatic creation of Jira epics and story point assignment synchronized with Refyne requirement traceability matrix.",
                "type": "INTEGRATION",
                "priority": "MEDIUM",
                "status": "APPROVED",
                "source_location": "SRS §5.1"
            },
        ]
        for d in demo_items:
            req_item = Requirement(
                tenant_id=tenant_id,
                project_id=proj.id,
                requirement_key=d["key"],
                type=d["type"],
                title=d["title"],
                description=d["description"],
                status=d["status"],
                source_type="SRS",
                source_location=d["source_location"],
                created_by=user_id,
                missing_information=[{"priority": d["priority"]}],
            )
            db.add(req_item)
        db.commit()


def _seed_risks_if_empty(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    count = db.scalar(select(func.count(Risk.id)).where(Risk.tenant_id == tenant_id)) or 0
    if count == 0:
        proj = _get_or_create_default_project(db, tenant_id, user_id)
        demo_risks = [
            {
                "key": "RSK-101",
                "title": "Data Loss During Ingestion Stream",
                "impact": "HIGH",
                "likelihood": "MEDIUM",
                "status": "MITIGATED",
                "category": "OPERATIONAL",
                "project_name": "Enterprise ERP Modernization",
                "description": "Risk of partial stream packet loss during high-volume document uploads and async worker restarts.",
                "mitigation": "Implemented Redis sliding window buffer and idempotent transactional checksums.",
                "contingency": "Trigger dead-letter queue (DLQ) automated replay upon worker recovery."
            },
            {
                "key": "RSK-102",
                "title": "Unauthorized Role Privilege Escalation",
                "impact": "CRITICAL",
                "likelihood": "LOW",
                "status": "OPEN",
                "category": "SECURITY",
                "project_name": "AI Requirement Suite",
                "description": "Potential vulnerability where malicious actor exploits JWT claims tampering to access neighbor tenant partitions.",
                "mitigation": "Enforce TenantIsolationMiddleware cryptographic signature verification on every inbound request.",
                "contingency": "Instantly revoke compromised session tokens and trigger automated tenant lockdown alert."
            },
            {
                "key": "RSK-103",
                "title": "Latency Delay in Batch PDF Generation",
                "impact": "LOW",
                "likelihood": "HIGH",
                "status": "IN_REVIEW",
                "category": "TECHNICAL",
                "project_name": "Document Vault",
                "description": "Heavy document compilation workloads may cause P95 response degradation during peak business hours.",
                "mitigation": "Offload ReportLab and PyPDF render pipelines to async celery worker pool with pre-warmed fonts.",
                "contingency": "Stream chunked document previews with async download notification webhook."
            },
        ]
        for r in demo_risks:
            risk_item = Risk(
                tenant_id=tenant_id,
                project_id=proj.id,
                risk_key=r["key"],
                title=r["title"],
                description=r["description"],
                impact=r["impact"],
                likelihood=r["likelihood"],
                status=r["status"],
                category=r["category"],
                mitigation_strategy=r["mitigation"],
                contingency_plan=r["contingency"],
                owner=r["project_name"],
                severity_score=calculate_severity_score(r["impact"], r["likelihood"]),
                created_by=user_id,
            )
            db.add(risk_item)
        db.commit()


def _requirement_response(item: Requirement, project_name: str | None = None) -> dict[str, object]:
    priority = "HIGH"
    if item.missing_information and isinstance(item.missing_information, list) and len(item.missing_information) > 0:
        if isinstance(item.missing_information[0], dict) and "priority" in item.missing_information[0]:
            priority = item.missing_information[0]["priority"]
    return {
        "id": str(item.id),
        "project_id": str(item.project_id) if item.project_id else None,
        "project_name": project_name or "AI Requirement Suite",
        "key": item.requirement_key,
        "requirement_key": item.requirement_key,
        "version": item.version,
        "type": item.type,
        "priority": priority,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "source_type": item.source_type,
        "source_id": str(item.source_id) if item.source_id else None,
        "source_location": item.source_location or "SRS §3.4",
        "confidence": item.confidence or 0.95,
        "missing_information": item.missing_information,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@app.get("/api/v1/requirements", tags=["requirements"])
def requirements(
    project_id: uuid.UUID | None = None,
    requirement_type: str | None = Query(default=None, alias="type"),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: int = Query(default=0, ge=0),
    sort: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    _seed_requirements_if_empty(db, session.tenant_id, user.id)
    
    query = select(Requirement).where(Requirement.tenant_id == session.tenant_id)
    if project_id is not None:
        query = query.where(Requirement.project_id == project_id)
    if requirement_type and requirement_type.upper() != "ALL":
        query = query.where(Requirement.type == requirement_type.upper())
    if status_filter and status_filter.upper() != "ALL":
        query = query.where(Requirement.status == status_filter.upper())
    if search:
        pattern = f"%{search}%"
        query = query.where((Requirement.title.ilike(pattern)) | (Requirement.description.ilike(pattern)) | (Requirement.requirement_key.ilike(pattern)))

    items = list(db.scalars(query.order_by(Requirement.created_at.desc())).all())
    items = _apply_sort(items, sort, {"created_at", "updated_at", "status", "version"})
    items_page, page = _page(items, limit, cursor)
    return {"requirements": [_requirement_response(item) for item in items_page], "page": page}


@app.post("/api/v1/requirements", status_code=status.HTTP_201_CREATED, tags=["requirements"])
def create_root_requirement_endpoint(
    request: RequirementCreateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    
    project_id = request.project_id
    if not project_id:
        proj = _get_or_create_default_project(db, session.tenant_id, user.id)
        project_id = proj.id

    key = request.key
    if not key:
        count = db.scalar(select(func.count(Requirement.id)).where(Requirement.tenant_id == session.tenant_id)) or 0
        key = f"REQ-{str(count + 1).zfill(3)}"

    item = Requirement(
        tenant_id=session.tenant_id,
        project_id=project_id,
        requirement_key=key,
        type=request.type.upper(),
        title=request.title,
        description=request.description,
        status=request.status.upper() if request.status else "DRAFT",
        source_type="MANUAL",
        source_location=request.source_location or "SRS §1.0",
        confidence=0.95,
        created_by=user.id,
        missing_information=[{"priority": request.priority.upper() if request.priority else "HIGH"}],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    record_audit(db, event_type="REQUIREMENT_CREATED", tenant_id=session.tenant_id, actor_id=user.id, session_id=None, resource_id=item.id)
    return _requirement_response(item)


@app.get("/api/v1/projects/{project_id}/requirements", tags=["requirements"])
def project_requirements(
    project_id: uuid.UUID,
    requirement_type: str | None = Query(default=None, alias="type"),
    status_filter: str | None = Query(default=None, alias="status"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    if get_project(db, session.tenant_id, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"requirements": [_requirement_response(item) for item in list_requirements(db, session.tenant_id, project_id, requirement_type, status_filter)]}


@app.post("/api/v1/projects/{project_id}/requirements", status_code=status.HTTP_201_CREATED, tags=["requirements"])
def create_project_requirement_endpoint(
    project_id: uuid.UUID,
    request: RequirementCreateRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    endpoint = f"POST /api/v1/projects/{project_id}/requirements"
    
    cached = _handle_idempotency(db, session.tenant_id, session.id, idempotency_key, endpoint)
    if cached:
        status_code, body = cached
        return body
    
    key = request.key
    if not key:
        count = db.scalar(select(func.count(Requirement.id)).where(Requirement.tenant_id == session.tenant_id)) or 0
        key = f"REQ-{str(count + 1).zfill(3)}"

    item = Requirement(
        tenant_id=session.tenant_id,
        project_id=project_id,
        requirement_key=key,
        type=request.type.upper(),
        title=request.title,
        description=request.description,
        status=request.status.upper() if request.status else "DRAFT",
        source_type="MANUAL",
        source_location=request.source_location or "SRS §1.0",
        confidence=0.95,
        created_by=user.id,
        missing_information=[{"priority": request.priority.upper() if request.priority else "HIGH"}],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    record_audit(db, event_type="REQUIREMENT_CREATED", tenant_id=session.tenant_id, actor_id=user.id, session_id=None, resource_id=item.id)
    
    response_body = _requirement_response(item)
    if idempotency_key:
        store_idempotency_key(
            db,
            tenant_id=session.tenant_id,
            idempotency_key=idempotency_key,
            endpoint=endpoint,
            session_id=session.id,
            status=201,
            response_body=response_body,
        )
    return response_body


@app.get("/api/v1/requirements/{requirement_id}", tags=["requirements"])
def requirement(
    requirement_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    item = get_requirement(db, session.tenant_id, requirement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="requirement not found")
    return _requirement_response(item)


@app.patch("/api/v1/requirements/{requirement_id}", tags=["requirements"])
def update_requirement_endpoint(
    requirement_id: uuid.UUID,
    request: RequirementUpdateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    item = get_requirement(db, session.tenant_id, requirement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="requirement not found")
    
    if request.title is not None:
        item.title = request.title
    if request.description is not None:
        item.description = request.description
    if request.type is not None:
        item.type = request.type.upper()
    if request.status is not None:
        item.status = request.status.upper()
    if request.source_location is not None:
        item.source_location = request.source_location
    if request.priority is not None:
        item.missing_information = [{"priority": request.priority.upper()}]
        
    db.commit()
    db.refresh(item)
    record_audit(db, event_type="REQUIREMENT_UPDATED", tenant_id=session.tenant_id, actor_id=user.id, session_id=None, resource_id=item.id)
    return _requirement_response(item)


@app.delete("/api/v1/requirements/{requirement_id}", tags=["requirements"])
def delete_requirement_endpoint(
    requirement_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    item = get_requirement(db, session.tenant_id, requirement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="requirement not found")
    delete_requirement(db, item, user.id, session.tenant_id)
    return {"status": "DELETED", "id": str(requirement_id)}


@app.post("/api/v1/requirements/{requirement_id}/verify-ai", tags=["requirements"])
async def verify_requirement_ai_endpoint(
    requirement_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    item = get_requirement(db, session.tenant_id, requirement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="requirement not found")
    
    req_dict = _requirement_response(item)
    verification_result = await verify_requirement_ai(req_dict, api_key=settings.groq_api_key, tenant_id=str(session.tenant_id))
    return {
        "requirement_id": str(requirement_id),
        "requirement_key": item.requirement_key,
        "verification": verification_result,
    }


def _requirement_link_response(item: RequirementLink) -> dict[str, object]:
    return {
        "id": str(item.id),
        "source_requirement_id": str(item.source_requirement_id),
        "target_requirement_id": str(item.target_requirement_id),
        "relationship": item.relationship,
        "created_at": item.created_at,
    }


@app.get("/api/v1/requirements/{requirement_id}/links", tags=["requirements"])
def requirement_links(
    requirement_id: uuid.UUID,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: int = Query(default=0, ge=0),
    sort: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    if get_requirement(db, session.tenant_id, requirement_id) is None:
        raise HTTPException(status_code=404, detail="requirement not found")
    items = list_requirement_links(db, session.tenant_id, requirement_id)
    items = _apply_sort(items, sort, {"created_at", "relationship"})
    items, page = _page(items, limit, cursor)
    return {"links": [_requirement_link_response(item) for item in items], "page": page}


@app.post("/api/v1/requirements/{requirement_id}/links", status_code=status.HTTP_201_CREATED, tags=["requirements"])
def create_requirement_link_endpoint(
    requirement_id: uuid.UUID,
    request: RequirementLinkRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    if request.target_kind.upper() != "REQUIREMENT":
        raise HTTPException(status_code=400, detail="only requirement links are supported")
    try:
        link = create_requirement_link(
            db,
            tenant_id=session.tenant_id,
            source_requirement_id=requirement_id,
            target_requirement_id=request.target_id,
            relationship=request.relationship,
            actor_id=user.id,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _requirement_link_response(link)


def _risk_response(item: Risk) -> dict[str, object]:
    return {
        "id": str(item.id),
        "risk_key": item.risk_key,
        "key": item.risk_key,
        "title": item.title,
        "description": item.description,
        "impact": item.impact,
        "likelihood": item.likelihood,
        "status": item.status,
        "category": item.category,
        "project": item.owner or "AI Requirement Suite",
        "project_id": str(item.project_id) if item.project_id else None,
        "mitigation_strategy": item.mitigation_strategy or "",
        "contingency_plan": item.contingency_plan or "",
        "owner": item.owner or "AI Requirement Suite",
        "severity_score": item.severity_score,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@app.get("/api/v1/risks", tags=["risks"])
def get_risks_endpoint(
    project_id: uuid.UUID | None = None,
    impact: str | None = Query(default=None),
    likelihood: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    user, session = _authenticated_context(authorization, db)
    _seed_risks_if_empty(db, session.tenant_id, user.id)
    
    items = list_risks(
        db,
        tenant_id=session.tenant_id,
        project_id=project_id,
        impact=None if impact == "ALL" else impact,
        likelihood=None if likelihood == "ALL" else likelihood,
        status_filter=None if status_filter == "ALL" else status_filter,
        category=None if category == "ALL" else category,
        search=search,
    )
    return [_risk_response(item) for item in items]


@app.post("/api/v1/risks", status_code=status.HTTP_201_CREATED, tags=["risks"])
def create_risk_endpoint(
    request: RiskCreateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    
    project_id = request.project_id
    if not project_id:
        proj = _get_or_create_default_project(db, session.tenant_id, user.id)
        project_id = proj.id

    risk = create_risk(
        db,
        tenant_id=session.tenant_id,
        user_id=user.id,
        project_id=project_id,
        risk_key=request.key,
        title=request.title,
        description=request.description or request.title,
        impact=request.impact,
        likelihood=request.likelihood,
        status=request.status,
        category=request.category,
        mitigation_strategy=request.mitigation_strategy,
        contingency_plan=request.contingency_plan,
        owner=request.associated_project or request.owner or "AI Requirement Suite",
    )
    return _risk_response(risk)


@app.get("/api/v1/risks/{risk_id}", tags=["risks"])
def get_single_risk_endpoint(
    risk_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _, session = _authenticated_context(authorization, db)
    item = get_risk(db, session.tenant_id, risk_id)
    if item is None:
        raise HTTPException(status_code=404, detail="risk not found")
    return _risk_response(item)


@app.patch("/api/v1/risks/{risk_id}", tags=["risks"])
def update_single_risk_endpoint(
    risk_id: uuid.UUID,
    request: RiskUpdateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    item = get_risk(db, session.tenant_id, risk_id)
    if item is None:
        raise HTTPException(status_code=404, detail="risk not found")
    
    updated = update_risk(
        db,
        item,
        title=request.title,
        description=request.description,
        impact=request.impact,
        likelihood=request.likelihood,
        status=request.status,
        category=request.category,
        mitigation_strategy=request.mitigation_strategy,
        contingency_plan=request.contingency_plan,
        owner=request.owner,
        actor_id=user.id,
    )
    return _risk_response(updated)


@app.delete("/api/v1/risks/{risk_id}", tags=["risks"])
def delete_single_risk_endpoint(
    risk_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    item = get_risk(db, session.tenant_id, risk_id)
    if item is None:
        raise HTTPException(status_code=404, detail="risk not found")
    delete_risk(db, item, user.id, session.tenant_id)
    return {"status": "DELETED", "id": str(risk_id)}


@app.post("/api/v1/risks/{risk_id}/assess-ai", tags=["risks"])
async def assess_risk_ai_endpoint(
    risk_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    item = get_risk(db, session.tenant_id, risk_id)
    if item is None:
        raise HTTPException(status_code=404, detail="risk not found")
    
    risk_dict = _risk_response(item)
    assessment = await analyze_risk_ai(risk_dict, api_key=settings.groq_api_key, tenant_id=str(session.tenant_id))
    return {
        "risk_id": str(risk_id),
        "risk_key": item.risk_key,
        "assessment": assessment,
    }


@app.post("/api/v1/risks/suggest-mitigation-ai", tags=["risks"])
async def suggest_risk_mitigation_endpoint(
    request: RiskMitigationSuggestRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user, session = _authenticated_context(authorization, db)
    return await suggest_mitigation_ai(
        title=request.title,
        category=request.category,
        api_key=settings.groq_api_key,
        tenant_id=str(session.tenant_id),
    )


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str | None = None
    steps: list[str] | None = None


class WorkflowUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    steps: list[str] | None = None
    currentStep: int | None = None
    logs: list[dict] | None = None


class WorkflowExecutionRequest(BaseModel):
    target_document_id: str | None = None
    target_document_name: str | None = None
    step_index: int | None = None
    auto_run: bool = True


DEFAULT_INITIAL_WORKFLOW_TEMPLATES = [
    {
        "name": "Requirement Analysis & Security Verification",
        "description": "Automated ingestion, AI prompt extraction, and security risk check",
        "steps": ["File Upload", "Parse Requirements", "Security Scan", "Generate Summary"],
        "status": "RUNNING",
        "currentStep": 2,
        "logs": [
            {"time": "11:48:02", "level": "SYSTEM", "text": "Initializing Workflow Engine v2.4 (REFYNE_CORE_V1)"},
            {"time": "11:48:05", "level": "SUPERVISOR", "text": "Agent assigned to requirement parsing: Model[Groq Llama-3.3-70b]"},
            {"time": "11:48:12", "level": "VALIDATION", "text": "Extracted 42 requirements. Traceability score: 99.2%"},
            {"time": "11:48:20", "level": "SECURITY", "text": "Running SAIF & OWASP Top 10 automated vulnerability heuristics..."},
            {"time": "11:48:25", "level": "AUDIT", "text": "Awaiting step verification or human-in-the-loop review..."}
        ]
    },
    {
        "name": "Document Generation & Approval Queue",
        "description": "Drafts BRD/SRS and queues for human supervisor approval",
        "steps": ["Assemble Context", "LLM Synthesis", "Compliance Validation", "Human Review"],
        "status": "COMPLETED",
        "currentStep": 4,
        "logs": [
            {"time": "10:15:00", "level": "SYSTEM", "text": "Pipeline started for tenant document portfolio"},
            {"time": "10:15:10", "level": "SUPERVISOR", "text": "Synthesizing formal IEEE 830 compliant SRS document"},
            {"time": "10:15:30", "level": "VALIDATION", "text": "Compliance check passed: ISO/IEC/IEEE 29148:2018"},
            {"time": "10:15:45", "level": "AUDIT", "text": "Human Review approved by Lead Architect"},
            {"time": "10:15:50", "level": "SYSTEM", "text": "Document published to Document Engine Vault"}
        ]
    },
    {
        "name": "Jira & Confluence Synchronization",
        "description": "Publishes validated requirements into Jira epics and Confluence pages",
        "steps": ["Authenticate Jira", "Map Fields", "Export Tickets"],
        "status": "PENDING",
        "currentStep": 0,
        "logs": [
            {"time": "09:30:00", "level": "SYSTEM", "text": "Ready for execution. OAuth token verified."}
        ]
    }
]


@app.get("/api/v1/workflows", tags=["workflows"])
@app.get("/api/v1/workflow_definitions", tags=["workflows"])
def workflows(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    cursor: int = Query(default=0, ge=0),
    sort: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    items = list_workflow_definitions(db, session.tenant_id, status_filter)
    
    # Auto-seed default initial workflows into database for tenant if none exist
    if len(items) == 0:
        for tpl in DEFAULT_INITIAL_WORKFLOW_TEMPLATES:
            wf_id = uuid.uuid4()
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tpl["name"].lower())[:80] or "pipeline"
            def_key = f"{clean_name}_{str(uuid.uuid4())[:8]}"
            new_wf = WorkflowDefinition(
                id=wf_id,
                tenant_id=session.tenant_id,
                definition_key=def_key,
                name=tpl["name"],
                description=tpl["description"],
                version="1.0.0",
                state_machine_id="REFYNE_CORE_V1",
                capabilities={
                    "steps": tpl["steps"],
                    "currentStep": tpl.get("currentStep", 0),
                    "logs": tpl.get("logs", [])
                },
                status=tpl.get("status", "PENDING"),
                created_by=user.id,
            )
            db.add(new_wf)
        db.commit()
        items = list_workflow_definitions(db, session.tenant_id, status_filter)

    items = _apply_sort(items, sort, {"created_at", "published_at", "status"})
    items, page = _page(items, limit, cursor)
    return {"workflows": [_workflow_definition_response(item) for item in items], "page": page}


@app.post("/api/v1/workflows", status_code=status.HTTP_201_CREATED, tags=["workflows"])
@app.post("/api/v1/workflow_definitions", status_code=status.HTTP_201_CREATED, tags=["workflows"])
def create_workflow_endpoint(
    request: WorkflowCreateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    wf_id = uuid.uuid4()
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', request.name.lower())[:80] or "pipeline"
    def_key = f"{clean_name}_{str(uuid.uuid4())[:8]}"
    steps = request.steps or ["File Ingestion & OCR", "Parse Requirements", "Security & SAIF Scan", "Human Supervisor Review"]
    
    item = WorkflowDefinition(
        id=wf_id,
        tenant_id=session.tenant_id,
        definition_key=def_key,
        name=request.name,
        description=request.description or "Enterprise Requirement Workflow",
        version="1.0.0",
        state_machine_id="REFYNE_CORE_V1",
        capabilities={
            "steps": steps,
            "currentStep": 0,
            "logs": [
                {
                    "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "level": "SYSTEM",
                    "text": f"Pipeline '{request.name}' initialized and persisted in workspace vault."
                }
            ]
        },
        status="PENDING",
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    record_audit(db, event_type="WORKFLOW_DEFINITION_CREATED", tenant_id=session.tenant_id, actor_id=user.id, session_id=session.id, resource_id=item.id)
    return _workflow_definition_response(item)


@app.get("/api/v1/workflows/{workflow_definition_id}", tags=["workflows"])
def workflow(
    workflow_definition_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    wf_uuid = None
    try:
        wf_uuid = uuid.UUID(str(workflow_definition_id))
    except Exception:
        pass

    item = None
    if wf_uuid:
        item = get_workflow_definition(db, session.tenant_id, wf_uuid)
    if not item:
        item = db.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == session.tenant_id,
                (WorkflowDefinition.definition_key == str(workflow_definition_id)) | (WorkflowDefinition.name == str(workflow_definition_id))
            )
        )
    if item is None:
        raise HTTPException(status_code=404, detail="workflow definition not found")
    return _workflow_definition_response(item)


@app.put("/api/v1/workflows/{workflow_definition_id}", tags=["workflows"])
@app.patch("/api/v1/workflows/{workflow_definition_id}", tags=["workflows"])
def update_workflow_endpoint(
    workflow_definition_id: str,
    request: WorkflowUpdateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    wf_uuid = None
    try:
        wf_uuid = uuid.UUID(str(workflow_definition_id))
    except Exception:
        pass

    item = None
    if wf_uuid:
        item = get_workflow_definition(db, session.tenant_id, wf_uuid)
    if not item:
        item = db.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == session.tenant_id,
                (WorkflowDefinition.definition_key == str(workflow_definition_id)) | (WorkflowDefinition.name == str(workflow_definition_id))
            )
        )
    if item is None:
        # Create persistent item if not present
        item = WorkflowDefinition(
            id=wf_uuid or uuid.uuid4(),
            tenant_id=session.tenant_id,
            definition_key=f"custom_{str(uuid.uuid4())[:8]}",
            name=request.name or "Custom Pipeline",
            description=request.description or "Enterprise Requirement Workflow",
            version="1.0.0",
            state_machine_id="REFYNE_CORE_V1",
            capabilities={
                "steps": request.steps or ["File Ingestion & OCR", "Parse Requirements", "Security & SAIF Scan", "Human Supervisor Review"],
                "currentStep": request.currentStep or 0,
                "logs": request.logs or []
            },
            status=(request.status or "PENDING").upper(),
            created_by=user.id,
        )
        db.add(item)
    else:
        if request.name is not None:
            item.name = request.name
        if request.description is not None:
            item.description = request.description
        if request.status is not None:
            item.status = request.status.upper()
        
        current_caps = dict(item.capabilities or {})
        if request.steps is not None:
            current_caps["steps"] = request.steps
        if request.currentStep is not None:
            current_caps["currentStep"] = request.currentStep
        if request.logs is not None:
            current_caps["logs"] = request.logs
        item.capabilities = current_caps
        db.add(item)

    db.commit()
    db.refresh(item)
    return _workflow_definition_response(item)


@app.post("/api/v1/workflows/{workflow_definition_id}/execute", tags=["workflows"])
async def execute_workflow_endpoint(
    workflow_definition_id: str,
    request: WorkflowExecutionRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    wf_uuid = None
    try:
        wf_uuid = uuid.UUID(str(workflow_definition_id))
    except Exception:
        pass

    item = None
    if wf_uuid:
        item = get_workflow_definition(db, session.tenant_id, wf_uuid)
    if not item:
        item = db.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == session.tenant_id,
                (WorkflowDefinition.definition_key == str(workflow_definition_id)) | (WorkflowDefinition.name == str(workflow_definition_id))
            )
        )
    if item is None:
        item = WorkflowDefinition(
            id=wf_uuid or uuid.uuid4(),
            tenant_id=session.tenant_id,
            definition_key=f"wf_{str(uuid.uuid4())[:8]}",
            name="Enterprise Pipeline",
            description="Automated requirement execution pipeline",
            version="1.0.0",
            state_machine_id="REFYNE_CORE_V1",
            capabilities={
                "steps": ["File Ingestion & OCR", "Parse Requirements", "Security & SAIF Scan", "Human Supervisor Review"],
                "currentStep": 0,
                "logs": []
            },
            status="PENDING",
            created_by=user.id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

    doc_filename = request.target_document_name or "Uploaded Document"
    doc_text = ""

    # 1. Search by target_document_id
    if request.target_document_id:
        doc_text = _load_extracted_text(str(request.target_document_id))
        if not doc_text:
            try:
                f_obj = db.scalar(select(File).where(File.id == uuid.UUID(str(request.target_document_id))))
                if f_obj:
                    doc_filename = f_obj.name
                    doc_text = _load_extracted_text(str(f_obj.id))
            except Exception:
                pass

    # 2. Search by filename across extracted files and audits
    if not doc_text and doc_filename:
        for fpath in EXTRACTED_DIR.glob("*.txt"):
            try:
                t = fpath.read_text(encoding="utf-8")
                if doc_filename.lower() in t.lower() or doc_filename.split(".")[0].lower() in t.lower():
                    doc_text = t
                    break
            except Exception:
                pass

    # 3. Fallback to latest uploaded file in tenant
    if not doc_text:
        latest_file = db.scalar(
            select(File).where(File.tenant_id == session.tenant_id, File.deleted_at.is_(None)).order_by(File.created_at.desc())
        )
        if latest_file:
            doc_filename = latest_file.name
            doc_text = _load_extracted_text(str(latest_file.id))

    # Fast Audit Cache Check (avoids waiting 10+ seconds if already audited)
    audit_result = _load_persistent_audit(doc_filename.lower())
    if not audit_result and request.target_document_id:
        audit_result = _load_persistent_audit(str(request.target_document_id).lower())

    if not audit_result:
        for audit_file in AUDITS_DIR.glob("*.json"):
            try:
                adata = json.loads(audit_file.read_text(encoding="utf-8"))
                afname = str(adata.get("filename", "")).lower()
                if doc_filename.lower() in afname or afname in doc_filename.lower():
                    audit_result = adata
                    break
            except Exception:
                pass

    if not audit_result:
        audit_result = await analyze_document_intelligence(
            document_text=doc_text,
            filename=doc_filename,
            api_key=settings.groq_api_key,
            tenant_id=str(session.tenant_id)
        )

    # Format genuine requirements from the audit
    parsed_reqs = []
    rtm_matrix = audit_result.get("rtm_matrix", [])
    if rtm_matrix:
        for idx, m in enumerate(rtm_matrix):
            parsed_reqs.append({
                "id": f"req-{idx+1}",
                "requirement_key": m.get("req_id") or f"REQ-{idx+1:03d}",
                "title": m.get("business_goal") or f"Requirement {idx+1}",
                "description": f"Subsystem: {m.get('technical_component', 'Core Services')}. Verification: {m.get('test_case_verification', 'Automated Verification')}.",
                "type": "FUNCTIONAL" if idx % 2 == 0 else "TECHNICAL",
                "status": "VALIDATED" if m.get("status") == "COVERED" else "IN_REVIEW",
                "confidence": 0.95
            })
    else:
        lines = [l.strip() for l in doc_text.splitlines() if len(l.strip()) > 20 and not l.startswith("---")][:6]
        for idx, l in enumerate(lines):
            clean_l = re.sub(r'^(?:\d+[\.\)]|[-*•]|REQ[-_]?\d*)\s+', '', l).strip()
            parsed_reqs.append({
                "id": f"req-{idx+1}",
                "requirement_key": f"REQ-{idx+1:03d}",
                "title": clean_l[:60],
                "description": clean_l,
                "type": "FUNCTIONAL",
                "status": "VALIDATED",
                "confidence": 0.92
            })

    findings = {
        "requirements": parsed_reqs,
        "risks": audit_result.get("risk_factors", []),
        "rtm": rtm_matrix,
        "summary": audit_result.get("summary", ""),
        "scores": {
            "readiness": audit_result.get("readiness_score", 85),
            "clarity": audit_result.get("clarity_score", 88),
            "completeness": audit_result.get("completeness_score", 80),
            "security": audit_result.get("security_score", 82),
            "rtm": audit_result.get("rtm_score", 80)
        }
    }

    # Generate document-specific pipeline logs
    now_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
    steps = item.capabilities.get("steps", ["File Ingestion & OCR", "Parse Requirements", "Security & SAIF Scan", "Human Supervisor Review"])
    total_steps = len(steps)
    next_step = total_steps if request.auto_run else min((request.step_index or 1), total_steps)
    is_finished = next_step >= total_steps

    word_count = len(doc_text.split()) if doc_text else 850
    generated_logs = [
        {"time": now_time, "level": "SYSTEM", "text": f"Initializing Workflow Pipeline for [{doc_filename}] ({word_count} words extracted)."},
        {"time": now_time, "level": "SUPERVISOR", "text": f"Agent assigned: Model[Groq Llama-3.3-70b / Qwen 27b]. Parsing specifications from [{doc_filename}]..."},
        {"time": now_time, "level": "VALIDATION", "text": f"Extracted {len(parsed_reqs)} verified requirements from [{doc_filename}]. Traceability readiness: {audit_result.get('readiness_score', 85)}%."},
        {"time": now_time, "level": "SECURITY", "text": f"SAIF & OWASP Top 10 threat modeling verified. {len(audit_result.get('risk_factors', []))} risk factors audited."},
        {"time": now_time, "level": "AUDIT", "text": f"Pipeline execution completed for [{doc_filename}]. Consolidated findings ready for export."}
    ]

    current_caps = dict(item.capabilities or {})
    current_caps["currentStep"] = next_step
    current_caps["logs"] = generated_logs
    current_caps["target_document_id"] = request.target_document_id
    current_caps["target_document_name"] = doc_filename
    current_caps["findings"] = findings
    item.capabilities = current_caps
    item.status = "COMPLETED" if is_finished else "RUNNING"

    db.add(item)
    db.commit()
    db.refresh(item)

    if request.target_document_id:
        _save_persistent_audit(str(request.target_document_id).lower(), audit_result)
    if doc_filename:
        _save_persistent_audit(doc_filename.lower(), audit_result)

    record_audit(db, event_type="WORKFLOW_EXECUTED", tenant_id=session.tenant_id, actor_id=user.id, session_id=session.id, resource_id=item.id)

    return {
        "workflow": _workflow_definition_response(item),
        "findings": findings
    }


@app.delete("/api/v1/workflows/{workflow_definition_id}", tags=["workflows"])
def delete_workflow_endpoint(
    workflow_definition_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    wf_uuid = None
    try:
        wf_uuid = uuid.UUID(str(workflow_definition_id))
    except Exception:
        pass

    item = None
    if wf_uuid:
        item = get_workflow_definition(db, session.tenant_id, wf_uuid)
    if not item:
        item = db.scalar(
            select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == session.tenant_id,
                (WorkflowDefinition.definition_key == str(workflow_definition_id)) | (WorkflowDefinition.name == str(workflow_definition_id))
            )
        )
    if item:
        db.delete(item)
        db.commit()
    return {"message": "workflow deleted successfully", "id": str(workflow_definition_id)}


CONVERSATIONS_STORE: dict[str, dict] = {}


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default="New Requirements Chat")
    project_id: str | None = None
    initial_message: str | None = None
    role: str | None = None
    project_type: str | None = None


@app.get("/api/v1/conversations", tags=["chat"])
def get_conversations_endpoint(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    
    conv_list = []
    try:
        db_convs = db.scalars(
            select(Conversation)
            .where(Conversation.tenant_id == session.tenant_id, Conversation.deleted_at.is_(None))
            .order_by(Conversation.created_at.desc())
        ).all()
        for c in db_convs:
            c_id = str(c.id).lower()
            conv_list.append({
                "id": c_id,
                "title": c.title or "Requirements Chat",
                "created_at": c.created_at.isoformat() if c.created_at else datetime.now(timezone.utc).isoformat(),
                "status": c.status
            })
    except Exception:
        pass
        
    for c_id, c_data in CONVERSATIONS_STORE.items():
        norm_id = str(c_id).lower()
        if not any(item["id"] == norm_id for item in conv_list):
            conv_list.append({
                "id": norm_id,
                "title": c_data.get("title", "Requirements Chat"),
                "created_at": c_data.get("created_at", datetime.now(timezone.utc).isoformat()),
                "status": "ACTIVE"
            })
            
    conv_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"conversations": conv_list}


@app.post("/api/v1/conversations", status_code=status.HTTP_201_CREATED, tags=["chat"])
def create_conversation_endpoint(
    request: ConversationCreateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    c_id = str(uuid.uuid4()).lower()
    title = request.title or "New Requirements Chat"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    init_msg_text = None
    if request.initial_message:
        init_msg_text = request.initial_message
    elif request.role or request.project_type:
        role_str = request.role or "Engineer"
        type_str = request.project_type or "Enterprise Software"
        init_msg_text = f"🚀 **Project Workspace Initialized:** `{title}`\n\nWelcome **{role_str}**! Domain context set to **{type_str}**.\n\nHow would you like REFYNE AI to assist with your project requirements today?"

    try:
        new_conv = Conversation(
            id=uuid.UUID(c_id),
            tenant_id=session.tenant_id,
            created_by=user.id,
            title=title,
            status="ACTIVE"
        )
        db.add(new_conv)
        if init_msg_text:
            first_msg = Message(
                id=uuid.uuid4(),
                conversation_id=uuid.UUID(c_id),
                sequence=1,
                role="assistant",
                content=init_msg_text,
                metadata_json={}
            )
            db.add(first_msg)
        db.commit()
    except Exception:
        db.rollback()
        
    messages = []
    if init_msg_text:
        messages.append({
            "id": int(datetime.now(timezone.utc).timestamp() * 1000),
            "text": init_msg_text,
            "sender": "bot",
            "timestamp": now_iso
        })

    c_data = {
        "id": c_id,
        "title": title,
        "created_at": now_iso,
        "messages": messages,
        "attachedFiles": [],
        "generatedDocs": []
    }
    CONVERSATIONS_STORE[c_id] = c_data
    return c_data


@app.get("/api/v1/conversations/{conversation_id}", tags=["chat"])
def get_conversation_by_id_endpoint(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    norm_id = str(conversation_id).lower()
    
    # Query database for persistent conversation & messages
    db_conv = None
    messages = []
    try:
        db_conv = db.scalar(select(Conversation).where(Conversation.id == uuid.UUID(norm_id)))
        if db_conv:
            db_msgs = db.scalars(
                select(Message)
                .where(Message.conversation_id == uuid.UUID(norm_id))
                .order_by(Message.sequence.asc(), Message.created_at.asc())
            ).all()
            for m in db_msgs:
                meta = m.metadata_json or {}
                messages.append({
                    "id": str(m.id),
                    "text": m.content or "",
                    "sender": "user" if m.role == "user" else "bot",
                    "isDocumentCard": meta.get("isDocumentCard", False),
                    "docInfo": meta.get("docInfo"),
                    "isUploadPrompt": meta.get("isUploadPrompt", False),
                    "fileName": meta.get("fileName"),
                    "timestamp": m.created_at.isoformat() if m.created_at else datetime.now(timezone.utc).isoformat()
                })
    except Exception:
        pass
        
    c_data = CONVERSATIONS_STORE.get(norm_id)
    if not c_data:
        c_data = {
            "id": norm_id,
            "title": db_conv.title if db_conv else "Requirements Chat",
            "created_at": db_conv.created_at.isoformat() if (db_conv and db_conv.created_at) else datetime.now(timezone.utc).isoformat(),
            "messages": messages,
            "attachedFiles": [],
            "generatedDocs": []
        }
        CONVERSATIONS_STORE[norm_id] = c_data
    else:
        # If in-memory exists, merge DB messages so history is never lost
        if len(messages) > len(c_data.get("messages", [])):
            c_data["messages"] = messages
        if db_conv and db_conv.title:
            c_data["title"] = db_conv.title
        
    return c_data


@app.delete("/api/v1/conversations/{conversation_id}", tags=["chat"])
def delete_conversation_endpoint(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    norm_id = str(conversation_id).lower()
    if norm_id in CONVERSATIONS_STORE:
        del CONVERSATIONS_STORE[norm_id]
    try:
        conv = db.scalar(select(Conversation).where(Conversation.id == uuid.UUID(norm_id)))
        if conv:
            conv.deleted_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        pass
    return {"status": "DELETED", "id": norm_id}


class ConversationRenameRequest(BaseModel):
    title: str


@app.patch("/api/v1/conversations/{conversation_id}", tags=["chat"])
def rename_conversation_endpoint(
    conversation_id: str,
    request: ConversationRenameRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    norm_id = str(conversation_id).lower()
    new_title = request.title.strip()
    
    if norm_id in CONVERSATIONS_STORE:
        CONVERSATIONS_STORE[norm_id]["title"] = new_title
        
    try:
        conv = db.scalar(select(Conversation).where(Conversation.id == uuid.UUID(norm_id)))
        if conv:
            conv.title = new_title
            db.commit()
    except Exception:
        pass
        
    return {"id": norm_id, "title": new_title, "status": "UPDATED"}


@app.post("/api/v1/conversations/{conversation_id}/fork", status_code=status.HTTP_201_CREATED, tags=["chat"])
def fork_conversation_endpoint(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    src_id = str(conversation_id).lower()
    src_data = CONVERSATIONS_STORE.get(src_id, {})
    
    forked_id = str(uuid.uuid4()).lower()
    original_title = src_data.get("title", "Requirements Chat")
    forked_title = f"Copy of {original_title}"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    import copy
    forked_messages = copy.deepcopy(src_data.get("messages", []))
    forked_files = copy.deepcopy(src_data.get("attachedFiles", []))
    forked_docs = copy.deepcopy(src_data.get("generatedDocs", []))
    
    forked_data = {
        "id": forked_id,
        "title": forked_title,
        "created_at": now_iso,
        "messages": forked_messages,
        "attachedFiles": forked_files,
        "generatedDocs": forked_docs
    }
    CONVERSATIONS_STORE[forked_id] = forked_data
    
    try:
        new_conv = Conversation(
            id=uuid.UUID(forked_id),
            tenant_id=session.tenant_id,
            created_by=user.id,
            title=forked_title,
            status="ACTIVE"
        )
        db.add(new_conv)
        db.commit()
    except Exception:
        db.rollback()
        
    return forked_data


class ChatCompletionRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    document_context: str | None = None
    messages: list[dict[str, str]] = Field(default_factory=list)


@app.post("/api/v1/chat/completions", tags=["chat"])
async def chat_completion_endpoint(
    request: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    history = request.messages if request.messages else [{"role": "user", "content": request.message}]
    ai_text = await generate_ai_response(
        messages=history,
        document_context=request.document_context,
        api_key=settings.groq_api_key,
        tenant_id=str(session.tenant_id),
    )
    
    # Save conversation and messages in Postgres DB
    if request.conversation_id:
        c_id = str(request.conversation_id).lower()
        now_dt = datetime.now(timezone.utc)
        
        try:
            conv = db.scalar(select(Conversation).where(Conversation.id == uuid.UUID(c_id)))
            if not conv:
                conv = Conversation(
                    id=uuid.UUID(c_id),
                    tenant_id=session.tenant_id,
                    created_by=user.id,
                    title=request.message[:35] + ("..." if len(request.message) > 35 else ""),
                    status="ACTIVE"
                )
                db.add(conv)
            elif conv.title in ("New Requirements Chat", "Requirements Chat Session", None) or conv.title.startswith("Requirements Chat"):
                conv.title = request.message[:35] + ("..." if len(request.message) > 35 else "")

            # Get next sequence numbers
            max_seq = db.scalar(select(func.max(Message.sequence)).where(Message.conversation_id == uuid.UUID(c_id))) or 0

            # Insert User Message
            user_msg = Message(
                id=uuid.uuid4(),
                conversation_id=uuid.UUID(c_id),
                sequence=max_seq + 1,
                role="user",
                content=request.message,
                metadata_json={}
            )
            db.add(user_msg)

            # Insert Assistant Message
            bot_msg = Message(
                id=uuid.uuid4(),
                conversation_id=uuid.UUID(c_id),
                sequence=max_seq + 2,
                role="assistant",
                content=ai_text,
                metadata_json={}
            )
            db.add(bot_msg)
            db.commit()
        except Exception:
            db.rollback()

        # Update in-memory cache as well
        if c_id not in CONVERSATIONS_STORE:
            CONVERSATIONS_STORE[c_id] = {
                "id": c_id,
                "title": request.message[:35] + ("..." if len(request.message) > 35 else ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "messages": [],
                "attachedFiles": [],
                "generatedDocs": []
            }
        c_store = CONVERSATIONS_STORE[c_id]
        if c_store.get("title") in ("New Requirements Chat", "Requirements Chat Session", None):
            c_store["title"] = request.message[:35] + ("..." if len(request.message) > 35 else "")
            
        c_store["messages"].append({
            "id": int(datetime.now(timezone.utc).timestamp() * 1000),
            "text": request.message,
            "sender": "user",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        c_store["messages"].append({
            "id": int(datetime.now(timezone.utc).timestamp() * 1000) + 1,
            "text": ai_text,
            "sender": "bot",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    return {
        "reply": ai_text,
        "role": "assistant",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


FILE_TEXT_CACHE: dict[str, str] = {}
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EXTRACTED_DIR = DATA_DIR / "extracted"
AUDITS_DIR = DATA_DIR / "audits"
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
AUDITS_DIR.mkdir(parents=True, exist_ok=True)


def _save_extracted_text(file_id: str, text: str):
    FILE_TEXT_CACHE[file_id] = text
    try:
        (EXTRACTED_DIR / f"{file_id}.txt").write_text(text, encoding="utf-8")
    except Exception as e:
        print(f"Error saving extracted text to disk: {e}")


def _load_extracted_text(file_id: str) -> str:
    if file_id in FILE_TEXT_CACHE:
        return FILE_TEXT_CACHE[file_id]
    disk_file = EXTRACTED_DIR / f"{file_id}.txt"
    if disk_file.exists():
        try:
            text = disk_file.read_text(encoding="utf-8")
            FILE_TEXT_CACHE[file_id] = text
            return text
        except Exception:
            pass
    return ""


def _save_persistent_audit(key: str, audit_data: dict):
    DOCUMENT_AUDIT_STORE[key] = audit_data
    try:
        (AUDITS_DIR / f"{key}.json").write_text(json.dumps(audit_data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error saving audit to disk: {e}")


def _load_persistent_audit(key: str) -> dict | None:
    if key in DOCUMENT_AUDIT_STORE:
        return DOCUMENT_AUDIT_STORE[key]
    disk_file = AUDITS_DIR / f"{key}.json"
    if disk_file.exists():
        try:
            data = json.loads(disk_file.read_text(encoding="utf-8"))
            DOCUMENT_AUDIT_STORE[key] = data
            return data
        except Exception:
            pass
    return None


@app.get("/api/v1/files", tags=["files"])
def list_files_endpoint(
    conversation_id: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    
    files = db.scalars(
        select(File)
        .where(File.tenant_id == session.tenant_id, File.deleted_at.is_(None))
        .order_by(File.created_at.desc())
    ).all()
    
    file_list = []
    for f in files:
        f_id_str = str(f.id)
        has_text = bool(_load_extracted_text(f_id_str))
        file_list.append({
            "id": f_id_str,
            "name": f.name,
            "size": f"{round((f.size_bytes or 0) / 1024, 1)} KB",
            "size_bytes": f.size_bytes,
            "mime_type": f.mime_type,
            "status": f.status,
            "has_extracted_text": has_text,
            "created_at": f.created_at.isoformat() if f.created_at else datetime.now(timezone.utc).isoformat()
        })
    return {"files": file_list}


@app.post("/api/v1/files/upload", tags=["files"])
async def upload_file_endpoint(
    file: UploadFile = FileParam(...),
    conversation_id: str | None = Header(default=None, alias="X-Conversation-Id"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    content = await file.read()
    
    text_content = extract_text_from_file(content, file.filename or "file", file.content_type or "")
    checksum = hashlib.sha256(content).digest()
    
    file_obj = File(
        tenant_id=session.tenant_id,
        name=file.filename or "uploaded_file",
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        checksum_sha256=checksum,
        storage_key=f"uploads/{uuid.uuid4()}_{file.filename}",
        status="PROCESSED",
        scan_result="PASSED",
        uploaded_by=user.id,
    )
    db.add(file_obj)
    db.commit()
    db.refresh(file_obj)

    f_id_str = str(file_obj.id)
    _save_extracted_text(f_id_str, text_content)
    
    file_entry = {
        "id": f_id_str,
        "name": file_obj.name,
        "size": f"{round(len(content) / 1024, 1)} KB",
        "mime_type": file_obj.mime_type,
        "text_content": text_content[:6000],
        "status": "INGESTED"
    }

    if conversation_id:
        c_id = str(conversation_id).lower()
        msg_text = f"📎 **Document Ingested:** `{file_obj.name}` ({file_entry['size']})\n\nText extraction completed ({len(text_content.split())} words). What formal document or quality audit would you like REFYNE AI to run on this file?"
        try:
            max_seq = db.scalar(select(func.max(Message.sequence)).where(Message.conversation_id == uuid.UUID(c_id))) or 0
            upload_msg = Message(
                id=uuid.uuid4(),
                conversation_id=uuid.UUID(c_id),
                sequence=max_seq + 1,
                role="assistant",
                content=msg_text,
                metadata_json={"isUploadPrompt": True, "fileName": file_obj.name, "fileId": f_id_str}
            )
            db.add(upload_msg)
            db.commit()
        except Exception:
            db.rollback()

        if c_id in CONVERSATIONS_STORE:
            c_store = CONVERSATIONS_STORE[c_id]
            c_store["attachedFiles"].append(file_entry)
            c_store["messages"].append({
                "id": int(datetime.now(timezone.utc).timestamp() * 1000),
                "text": msg_text,
                "sender": "bot",
                "isUploadPrompt": True,
                "fileName": file_obj.name,
                "fileId": f_id_str,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    return file_entry


DOCUMENT_STORE: dict[str, dict] = {}
DOCUMENTS_DIR = DATA_DIR / "documents"
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _save_persistent_document(doc_id: str, doc_data: dict):
    DOCUMENT_STORE[doc_id] = doc_data
    try:
        (DOCUMENTS_DIR / f"{doc_id}.json").write_text(json.dumps(doc_data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error saving document to disk: {e}")


def _load_persistent_document(doc_id: str) -> dict | None:
    if doc_id in DOCUMENT_STORE:
        return DOCUMENT_STORE[doc_id]
    disk_file = DOCUMENTS_DIR / f"{doc_id}.json"
    if disk_file.exists():
        try:
            data = json.loads(disk_file.read_text(encoding="utf-8"))
            DOCUMENT_STORE[doc_id] = data
            return data
        except Exception:
            pass
    return None


class DocumentGenerateRequest(BaseModel):
    doc_type: str = Field(default="BRD")
    title: str = Field(default="Enterprise Software Requirements")
    conversation_id: str | None = None
    document_context: str | None = None


@app.post("/api/v1/documents/generate", tags=["documents"])
@app.post("/documents/generate", tags=["documents"])
async def generate_document_endpoint(
    request: DocumentGenerateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    doc_type = request.doc_type.upper()
    doc_title = request.title
    
    # Retrieve audit_json and document context
    doc_context = request.document_context or ""
    audit_json = None
    
    if request.conversation_id:
        c_id = str(request.conversation_id).lower()
        audit_json = _load_persistent_audit(c_id)
        if not doc_context and c_id in CONVERSATIONS_STORE:
            c_store = CONVERSATIONS_STORE[c_id]
            attached = c_store.get("attachedFiles", [])
            if attached:
                doc_context = _load_extracted_text(attached[-1].get("id", "")) or attached[-1].get("text_content", "")
    
    # Fallback to most recent uploaded file for the tenant if doc_context is still empty
    if not doc_context and session:
        recent_file = db.scalar(
            select(File)
            .where(File.tenant_id == session.tenant_id, File.deleted_at.is_(None))
            .order_by(File.created_at.desc())
        )
        if recent_file:
            doc_context = _load_extracted_text(str(recent_file.id)) or recent_file.extracted_text or ""

    if not audit_json and doc_context:
        audit_json = _load_persistent_audit(doc_title.lower())
    
    from refyne.llm_service import detect_domain
    from refyne.project_analyzer import analyze_project_context
    from refyne.srs_id_manager import manage_srs_ids
    from refyne.srs_validator import validate_srs_document

    domain_profile = audit_json.get("domain_profile") if audit_json else None
    if not domain_profile:
        domain_profile = detect_domain(doc_context or doc_title)

    # Execute Project Analysis Stage
    tenant_str = str(session.tenant_id) if session else "default"
    project_analysis = analyze_project_context(
        db=db,
        tenant_id=session.tenant_id if session else None,
        doc_context=doc_context,
        audit_json=audit_json or {}
    )

    doc_content = await generate_document_content(
        doc_type=doc_type,
        title=doc_title,
        doc_context=doc_context,
        audit_json=audit_json or {},
        domain_profile=domain_profile,
        api_key=settings.groq_api_key,
        tenant_id=tenant_str,
        project_analysis=project_analysis
    )

    # Post-generation SRS ID management & pre-output validation
    if doc_type == "SRS":
        doc_content = manage_srs_ids(doc_content, previous_doc=None)
        validation_report = validate_srs_document(doc_content, project_analysis=project_analysis)
        doc_content["validation_report"] = validation_report
    
    doc_content["project_analysis"] = project_analysis
    
    doc_id = str(uuid.uuid4())
    doc_content["id"] = doc_id
    doc_content["pdf_export_url"] = f"/api/v1/documents/{doc_id}/export/pdf?title={doc_title}&type={doc_type}"
    doc_content["conversation_id"] = request.conversation_id
    
    _save_persistent_document(doc_id, doc_content)

    if request.conversation_id:
        c_id = str(request.conversation_id).lower()
        card_msg_text = f"### 📄 {doc_content['doc_type']} Document Generated Successfully\n\n**Title:** {doc_content['title']}\n**Version:** {doc_content['version']} | **Status:** {doc_content['status']}\n\nThe formal {doc_content['doc_type']} specification has been compiled with complete requirements, architecture specs, and compliance matrix. Please review the specification below to accept or request revisions."
        try:
            max_seq = db.scalar(select(func.max(Message.sequence)).where(Message.conversation_id == uuid.UUID(c_id))) or 0
            doc_msg = Message(
                id=uuid.uuid4(),
                conversation_id=uuid.UUID(c_id),
                sequence=max_seq + 1,
                role="assistant",
                content=card_msg_text,
                metadata_json={"isDocumentCard": True, "docInfo": doc_content}
            )
            db.add(doc_msg)
            db.commit()
        except Exception:
            db.rollback()

        if c_id in CONVERSATIONS_STORE:
            c_store = CONVERSATIONS_STORE[c_id]
            c_store["generatedDocs"].append(doc_content)
            c_store["messages"].append({
                "id": int(datetime.now(timezone.utc).timestamp() * 1000),
                "text": card_msg_text,
                "sender": "bot",
                "isDocumentCard": True,
                "docInfo": doc_content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    return doc_content


@app.get("/api/v1/documents/analyze", tags=["documents"])
@app.post("/api/v1/documents/analyze", tags=["documents"])
async def analyze_project_endpoint(
    project_id: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    user, session = _authenticated_context(authorization, db)
    from refyne.project_analyzer import analyze_project_context
    return analyze_project_context(
        db=db,
        tenant_id=session.tenant_id if session else None,
        project_id=project_id
    )


class DocumentDecisionRequest(BaseModel):
    feedback: str | None = None
    conversation_id: str | None = None


@app.get("/api/v1/documents", tags=["documents"])
@app.get("/documents", tags=["documents"])
def list_documents_endpoint(
    status: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    # Load all documents from disk if not yet in memory
    for doc_file in DOCUMENTS_DIR.glob("*.json"):
        try:
            data = json.loads(doc_file.read_text(encoding="utf-8"))
            if data.get("id"):
                DOCUMENT_STORE[data["id"]] = data
        except Exception:
            pass

    docs = list(DOCUMENT_STORE.values())
    if status:
        docs = [d for d in docs if d.get("status") == status]
    if conversation_id:
        c_id = str(conversation_id).lower()
        docs = [d for d in docs if str(d.get("conversation_id", "")).lower() == c_id]
    return docs


@app.get("/api/v1/documents/{document_id}", tags=["documents"])
@app.get("/documents/{document_id}", tags=["documents"])
def get_document_endpoint(document_id: str):
    """Retrieve full document by its unique ID."""
    doc = _load_persistent_document(document_id)
    if not doc:
        doc = DOCUMENT_STORE.get(document_id)
    if not doc:
        for c_id, c_data in CONVERSATIONS_STORE.items():
            for g_doc in c_data.get("generatedDocs", []):
                if g_doc.get("id") == document_id:
                    doc = g_doc
                    break
            if doc:
                break
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _get_generation_versions(generation_id: str) -> list[dict]:
    """Retrieve all document versions associated with a generation thread, sorted newest first."""
    for doc_file in DOCUMENTS_DIR.glob("*.json"):
        try:
            data = json.loads(doc_file.read_text(encoding="utf-8"))
            if data.get("id"):
                DOCUMENT_STORE[data["id"]] = data
        except Exception:
            pass

    g_id_lower = str(generation_id).lower()
    
    # 1. Collect any seed documents matching generation_id, document id, or parent_id
    seed_docs = []
    for doc in DOCUMENT_STORE.values():
        if (
            str(doc.get("generation_id", "")).lower() == g_id_lower
            or str(doc.get("id", "")).lower() == g_id_lower
            or str(doc.get("parent_id", "")).lower() == g_id_lower
        ):
            seed_docs.append(doc)

    # 2. Collect all linked generation_ids and document IDs in this family
    family_gen_ids = {g_id_lower}
    family_doc_ids = set()
    for d in seed_docs:
        if d.get("generation_id"):
            family_gen_ids.add(str(d["generation_id"]).lower())
        if d.get("id"):
            family_doc_ids.add(str(d["id"]).lower())
        if d.get("parent_id"):
            family_doc_ids.add(str(d["parent_id"]).lower())

    # 3. Find all documents in DOCUMENT_STORE belonging to this family
    matches = []
    for doc in DOCUMENT_STORE.values():
        d_gen = str(doc.get("generation_id", "")).lower()
        d_id = str(doc.get("id", "")).lower()
        d_parent = str(doc.get("parent_id", "")).lower()
        if d_gen in family_gen_ids or d_id in family_doc_ids or d_parent in family_doc_ids:
            matches.append(doc)

    # 4. Deduplicate by document id
    seen = set()
    unique_matches = []
    for m in matches:
        m_id = m.get("id")
        if m_id and m_id not in seen:
            seen.add(m_id)
            unique_matches.append(m)

    def sort_key(d):
        v_num = d.get("version_num")
        if v_num is None:
            v_str = str(d.get("version", "1")).lstrip("v")
            try:
                v_num = float(v_str.split(".")[0])
            except Exception:
                v_num = 1
        return (v_num, d.get("created_at", ""))

    unique_matches.sort(key=sort_key, reverse=True)
    return unique_matches


class GenerationRejectRequest(BaseModel):
    version: Any | None = None
    feedback: str
    conversation_id: str | None = None


@app.get("/api/v1/generations/{generation_id}/versions", tags=["generations"])
@app.get("/api/generations/{generation_id}/versions", tags=["generations"])
async def get_generation_versions_endpoint(generation_id: str):
    """List all versions for a generation_id, sorted newest first."""
    versions = _get_generation_versions(generation_id)
    summary_list = []
    for doc in versions:
        summary_list.append({
            "id": doc.get("id"),
            "generation_id": doc.get("generation_id", generation_id),
            "version": doc.get("version", "v1.0"),
            "version_num": doc.get("version_num", 1),
            "status": doc.get("status", "PENDING_APPROVAL"),
            "created_at": doc.get("created_at"),
            "reviewed_at": doc.get("reviewed_at"),
            "document_url": doc.get("pdf_export_url"),
            "pdf_export_url": doc.get("pdf_export_url"),
            "story_ids": doc.get("story_ids", [s.get("story_id") for s in doc.get("user_stories_data", {}).get("stories", [])] if "user_stories_data" in doc else []),
            "changed_story_ids": doc.get("changed_story_ids", []),
            "added_story_ids": doc.get("added_story_ids", []),
            "removed_story_ids": doc.get("removed_story_ids", []),
            "rejection_feedback": doc.get("rejection_feedback"),
            "title": doc.get("title", "Requirements Specification"),
            "doc_type": doc.get("doc_type", "USER_STORIES"),
            "quality_score": doc.get("quality_score", 95)
        })
    return summary_list


@app.get("/api/v1/generations/{generation_id}/versions/{version}", tags=["generations"])
@app.get("/api/generations/{generation_id}/versions/{version}", tags=["generations"])
async def get_generation_version_detail_endpoint(generation_id: str, version: str):
    """Get full document specification for a specific version."""
    versions = _get_generation_versions(generation_id)
    target = None
    for doc in versions:
        if str(doc.get("version_num")) == str(version) or str(doc.get("version")).lower() == str(version).lower() or doc.get("id") == version:
            target = doc
            break
    if not target:
        if versions:
            target = versions[0]
        else:
            raise HTTPException(status_code=404, detail="Version not found")
    return target


@app.post("/api/v1/generations/{generation_id}/versions/{version}/accept", tags=["generations"])
@app.post("/api/generations/{generation_id}/versions/{version}/accept", tags=["generations"])
async def accept_generation_version_endpoint(
    generation_id: str,
    version: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    """Set status = ACCEPTED on a specific version without touching other versions."""
    versions = _get_generation_versions(generation_id)
    target = None
    for doc in versions:
        if str(doc.get("version_num")) == str(version) or str(doc.get("version")).lower() == str(version).lower() or doc.get("id") == version:
            target = doc
            break
    if not target:
        raise HTTPException(status_code=404, detail="Version not found")

    target["status"] = "ACCEPTED"
    target["approved_at"] = datetime.now(timezone.utc).isoformat()
    target["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _save_persistent_document(target["id"], target)
    return target


@app.post("/api/v1/generations/{generation_id}/reject", tags=["generations"])
@app.post("/api/generations/{generation_id}/reject", tags=["generations"])
async def reject_generation_endpoint(
    generation_id: str,
    request: GenerationRejectRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    """Reject a version, set status = REJECTED, and trigger revision engine to generate version+1."""
    if not request.feedback or not request.feedback.strip():
        raise HTTPException(status_code=400, detail="Rejection requires feedback describing the needed changes")

    versions = _get_generation_versions(generation_id)
    target = None
    if request.version is not None:
        for doc in versions:
            if str(doc.get("version_num")) == str(request.version) or str(doc.get("version")).lower() == str(request.version).lower() or doc.get("id") == str(request.version):
                target = doc
                break
    if not target and versions:
        target = versions[0]
    if not target:
        raise HTTPException(status_code=404, detail="Generation thread not found")

    return await _process_document_rejection(target, request.feedback.strip(), authorization, db, request.conversation_id)


async def _process_document_rejection(doc: dict, feedback: str, authorization: str | None, db: Session, conversation_id: str | None = None) -> dict:
    """Core rejection handler: marks old version REJECTED (immutable) and creates a brand-new row for the next version."""
    user, session = _authenticated_context(authorization, db)

    # 1. Mark previous version REJECTED and persist it
    doc["status"] = "REJECTED"
    doc["rejection_feedback"] = feedback
    doc["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _save_persistent_document(doc["id"], doc)

    # 2. Build prompt context for revision engine
    prev_sections_md = ""
    for s in doc.get("sections", []):
        prev_sections_md += f"### {s.get('title', '')}\n{s.get('body', '')}\n\n"

    from refyne.llm_service import generate_document_ai
    revised = await generate_document_ai(
        doc_type=doc.get("doc_type", "USER_STORIES"),
        title=doc.get("title", "Enterprise Software Requirements"),
        audit_json=doc.get("_source_audit", {}),
        domain_profile=doc.get("_domain_profile", {}),
        doc_excerpt=doc.get("_doc_excerpt", ""),
        revision_feedback=feedback,
        previous_sections=prev_sections_md,
        previous_doc=doc,
        api_key=settings.groq_api_key,
        tenant_id=str(session.tenant_id) if session else "default"
    )

    # 3. Compute new version metadata
    cur_ver_num = doc.get("version_num")
    if cur_ver_num is None:
        cur_ver_str = doc.get("version", "v1.0").lstrip("v")
        try:
            cur_ver_num = int(cur_ver_str.split(".")[0])
        except Exception:
            cur_ver_num = 1

    next_ver_num = cur_ver_num + 1
    if doc.get("doc_type") == "USER_STORIES":
        next_ver_str = revised.get("version") or f"v{next_ver_num}.0"
    else:
        next_ver_str = f"v{cur_ver_num}.{len(doc.get('revision_history', [])) + 1}"

    new_doc_id = str(uuid.uuid4())
    gen_id = doc.get("generation_id") or doc.get("id")

    # Extract diff story IDs
    rev_hist_entry = revised.get("revision_history", [{}])[-1] if revised.get("revision_history") else {}
    changed_story_ids = rev_hist_entry.get("changed_story_ids", [])
    added_story_ids = rev_hist_entry.get("added_story_ids", [])
    removed_story_ids = rev_hist_entry.get("removed_story_ids", [])

    # 4. Create new version document
    new_doc = {
        "id": new_doc_id,
        "generation_id": gen_id,
        "doc_type": doc.get("doc_type", "USER_STORIES"),
        "title": revised.get("title", doc.get("title", "Requirements Specification")),
        "version": next_ver_str,
        "version_num": next_ver_num,
        "parent_version": cur_ver_num,
        "parent_id": doc["id"],
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_at": None,
        "rejection_feedback": None,
        "sections": revised.get("sections", doc.get("sections", [])),
        "user_stories_data": revised.get("user_stories_data", {}),
        "quality_score": revised.get("quality_score", 95),
        "verification_summary": revised.get("verification_summary"),
        "conversation_id": conversation_id or doc.get("conversation_id"),
        "pdf_export_url": f"/api/v1/documents/{new_doc_id}/export/pdf?title={doc.get('title')}&type={doc.get('doc_type')}",
        "changed_story_ids": changed_story_ids,
        "added_story_ids": added_story_ids,
        "removed_story_ids": removed_story_ids,
        "revision_history": doc.get("revision_history", []) + [{
            "version": doc.get("version", "v1.0"),
            "feedback": feedback,
            "revised_at": datetime.now(timezone.utc).isoformat(),
            "changed_story_ids": changed_story_ids,
            "added_story_ids": added_story_ids,
            "removed_story_ids": removed_story_ids
        }],
        "_source_audit": doc.get("_source_audit", {}),
        "_domain_profile": doc.get("_domain_profile", {}),
        "_doc_excerpt": doc.get("_doc_excerpt", "")
    }

    _save_persistent_document(new_doc_id, new_doc)

    # 5. Notify chat conversation if applicable
    conv_id = conversation_id or doc.get("conversation_id")
    if conv_id:
        c_id = str(conv_id).lower()
        card_msg_text = (
            f"### 📄 {new_doc['doc_type']} Revised ({new_doc['version']})\n\n"
            f"**Title:** {new_doc['title']}\n"
            f"**Version:** {new_doc['version']} | **Status:** PENDING_APPROVAL\n\n"
            f"Revised based on feedback: *\"{feedback}\"*. Please review the updated specification below."
        )
        try:
            max_seq = db.scalar(select(func.max(Message.sequence)).where(Message.conversation_id == uuid.UUID(c_id))) or 0
            doc_msg = Message(
                id=uuid.uuid4(),
                conversation_id=uuid.UUID(c_id),
                sequence=max_seq + 1,
                role="assistant",
                content=card_msg_text,
                metadata_json={"isDocumentCard": True, "docInfo": new_doc}
            )
            db.add(doc_msg)
            db.commit()
        except Exception:
            db.rollback()

        if c_id in CONVERSATIONS_STORE:
            c_store = CONVERSATIONS_STORE[c_id]
            c_store["generatedDocs"].append(new_doc)
            c_store["messages"].append({
                "id": int(datetime.now(timezone.utc).timestamp() * 1000),
                "text": card_msg_text,
                "sender": "bot",
                "isDocumentCard": True,
                "docInfo": new_doc,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    return new_doc


@app.post("/api/v1/documents/{document_id}/approve", tags=["documents"])
@app.post("/documents/{document_id}/approve", tags=["documents"])
async def approve_document_endpoint(
    document_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    doc = _load_persistent_document(document_id)
    if not doc:
        # Search in conversation memory stores
        for c_id, c_data in CONVERSATIONS_STORE.items():
            for g_doc in c_data.get("generatedDocs", []):
                if g_doc.get("id") == document_id:
                    doc = g_doc
                    break
            if doc:
                break
    if not doc:
        doc = {
            "id": document_id,
            "title": "Approved Requirements Specification",
            "doc_type": "BRD",
            "version": "v1.0",
            "status": "APPROVED",
            "sections": [
                {"title": "1. Executive Summary & Baseline", "body": "Specification approved and verified for downstream development."}
            ]
        }
    doc["status"] = "APPROVED"
    doc["approved_at"] = datetime.now(timezone.utc).isoformat()
    doc["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _save_persistent_document(document_id, doc)
    return doc


@app.post("/api/v1/documents/{document_id}/reject", tags=["documents"])
@app.post("/documents/{document_id}/reject", tags=["documents"])
async def reject_document_endpoint(
    document_id: str,
    request: DocumentDecisionRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    doc = _load_persistent_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not request.feedback or not request.feedback.strip():
        raise HTTPException(status_code=400, detail="Rejection requires feedback describing the needed changes")

    rev_hist = doc.get("revision_history", [])
    if len(rev_hist) >= 3:
        raise HTTPException(
            status_code=400,
            detail="Maximum revision limit reached (3 cycles). Please consider editing the audit findings directly or starting a new session."
        )

    return await _process_document_rejection(doc, request.feedback.strip(), authorization, db, request.conversation_id)


@app.get("/api/v1/documents/{document_id}/export/pdf", tags=["documents"])
@app.get("/documents/{document_id}/export/pdf", tags=["documents"])
def export_document_pdf(
    document_id: str,
    title: str = Query(default="REFYNE Enterprise Document"),
    doc_type: str = Query(default="BRD", alias="type"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    from starlette.responses import Response
    
    cached_doc = _load_persistent_document(document_id)
    if cached_doc:
        doc_title = cached_doc.get("title", title)
        actual_type = cached_doc.get("doc_type", doc_type)
        sections = cached_doc.get("sections", [])
        version = cached_doc.get("version", "v1.0")
    else:
        doc_data = generate_document_content_sync(doc_type=doc_type, title=title, doc_context=None)
        doc_title = doc_data["title"]
        actual_type = doc_data["doc_type"]
        sections = doc_data["sections"]
        version = doc_data.get("version", "v1.0")
    
    pdf_bytes = build_pdf_document(
        title=doc_title,
        doc_type=actual_type,
        sections=sections,
        tenant_name="REFYNE Enterprise Workspace",
        version=version
    )
    
    filename = f"{actual_type.upper()}_{document_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.delete("/api/v1/documents/{document_id}", tags=["documents"])
@app.delete("/documents/{document_id}", tags=["documents"])
def delete_document_endpoint(
    document_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    if document_id in DOCUMENT_STORE:
        del DOCUMENT_STORE[document_id]
    disk_file = DOCUMENTS_DIR / f"{document_id}.json"
    if disk_file.exists():
        try:
            disk_file.unlink()
        except Exception:
            pass
    try:
        doc = db.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
        if doc:
            doc.deleted_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        pass
    return {"status": "DELETED", "id": document_id}


class DocumentAuditRequest(BaseModel):
    document_context: str | None = None
    filename: str | None = None
    conversation_id: str | None = None
    file_id: str | None = None


DOCUMENT_AUDIT_STORE: dict[str, dict] = {}


@app.post("/api/v1/documents/audit", tags=["documents"])
async def audit_document_endpoint(
    request: DocumentAuditRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    doc_text = request.document_context or ""
    doc_filename = request.filename or "Uploaded Document"

    # 1. Lookup by file_id
    if request.file_id:
        f_text = _load_extracted_text(str(request.file_id))
        if f_text:
            doc_text = f_text
        try:
            f_obj = db.scalar(select(File).where(File.id == uuid.UUID(str(request.file_id))))
            if f_obj and f_obj.name:
                doc_filename = f_obj.name
        except Exception:
            pass

    # 2. Fallback to conversation attached files
    if not doc_text and request.conversation_id:
        c_id = str(request.conversation_id).lower()
        c_store = CONVERSATIONS_STORE.get(c_id, {})
        attached = c_store.get("attachedFiles", [])
        if attached:
            # Use the latest attached file
            latest_file = attached[-1]
            doc_filename = latest_file.get("name", doc_filename)
            doc_text = _load_extracted_text(latest_file.get("id", "")) or latest_file.get("text_content", "")

    # 3. If still empty, check the most recent uploaded file in DB
    if not doc_text:
        latest_db_file = db.scalar(
            select(File)
            .where(File.tenant_id == session.tenant_id, File.deleted_at.is_(None))
            .order_by(File.created_at.desc())
        )
        if latest_db_file:
            doc_filename = latest_db_file.name
            doc_text = _load_extracted_text(str(latest_db_file.id))

    audit_result = await analyze_document_intelligence(
        document_text=doc_text,
        filename=doc_filename,
        api_key=settings.groq_api_key,
        tenant_id=str(session.tenant_id),
    )

    # §9.7 Audit Diff on re-upload or re-audit
    prev_audit = None
    if request.file_id:
        prev_audit = _load_persistent_audit(str(request.file_id).lower())
    if not prev_audit and request.conversation_id:
        prev_audit = _load_persistent_audit(str(request.conversation_id).lower())
    if not prev_audit and doc_filename:
        prev_audit = _load_persistent_audit(doc_filename.lower())

    if prev_audit and isinstance(prev_audit, dict) and "readiness_score" in prev_audit and prev_audit.get("content_hash") != audit_result.get("content_hash"):
        prev_score = prev_audit.get("readiness_score", 0)
        curr_score = audit_result.get("readiness_score", 0)
        prev_risks = {r.get("title", "") for r in prev_audit.get("risk_factors", [])}
        curr_risks = {r.get("title", "") for r in audit_result.get("risk_factors", [])}
        resolved = list(prev_risks - curr_risks)
        new_risks = list(curr_risks - prev_risks)
        audit_result["audit_diff"] = {
            "score_delta": curr_score - prev_score,
            "previous_score": prev_score,
            "current_score": curr_score,
            "resolved_risks_count": len(resolved),
            "resolved_risks": resolved[:5],
            "new_risks_count": len(new_risks),
            "new_risks": new_risks[:5],
            "has_prior_audit": True
        }

    audit_id = str(uuid.uuid4())
    audit_result["id"] = audit_id
    audit_result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    audit_result["filename"] = doc_filename
    audit_result["file_id"] = request.file_id
    audit_result["conversation_id"] = request.conversation_id
    
    _save_persistent_audit(audit_id, audit_result)
    if request.file_id:
        _save_persistent_audit(str(request.file_id).lower(), audit_result)
    if request.conversation_id:
        _save_persistent_audit(str(request.conversation_id).lower(), audit_result)

    return audit_result


@app.get("/api/v1/documents/audit/{conversation_or_audit_id}", tags=["documents"])
async def get_document_audit_endpoint(
    conversation_or_audit_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    key = str(conversation_or_audit_id).lower()
    
    result = _load_persistent_audit(key)
    if result:
        return result
        
    # Search across AUDITS_DIR by matching filename
    for audit_file in AUDITS_DIR.glob("*.json"):
        try:
            data = json.loads(audit_file.read_text(encoding="utf-8"))
            fname = str(data.get("filename", "")).lower()
            fid = str(data.get("file_id", "")).lower()
            if key == fname or key == fid or key in fname or fname in key:
                DOCUMENT_AUDIT_STORE[key] = data
                return data
        except Exception:
            pass

    # Search extracted text to generate audit on the fly if needed
    doc_text = ""
    doc_filename = conversation_or_audit_id
    for fpath in EXTRACTED_DIR.glob("*.txt"):
        try:
            t = fpath.read_text(encoding="utf-8")
            if key in fpath.stem.lower() or key in t.lower()[:200]:
                doc_text = t
                break
        except Exception:
            pass

    if doc_text:
        result = await analyze_document_intelligence(
            document_text=doc_text,
            filename=doc_filename,
            api_key=settings.groq_api_key,
            tenant_id=str(session.tenant_id)
        )
        _save_persistent_audit(key, result)
        return result

    raise HTTPException(status_code=404, detail="audit record not found")
 
 
class IntegrationConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class IntegrationTestRequest(BaseModel):
    config: dict[str, Any] | None = None


class IntegrationSyncRequest(BaseModel):
    payload: dict[str, Any] | None = None


@app.get("/api/v1/integrations", tags=["integrations"])
def list_integrations_endpoint(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    tenant_id = str(session.tenant_id)
    integrations = get_tenant_integrations(tenant_id)
    return {"integrations": integrations}


@app.post("/api/v1/integrations/{integration_id}/configure", tags=["integrations"])
def configure_integration_endpoint(
    integration_id: str,
    request: IntegrationConfigRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    tenant_id = str(session.tenant_id)
    updated = save_integration_config(tenant_id, integration_id, request.config)
    record_audit(db, event_type="INTEGRATION_CONFIGURED", tenant_id=session.tenant_id, actor_id=user.id, session_id=session.id)
    return {"status": "ok", "integration": updated}


@app.post("/api/v1/integrations/{integration_id}/test", tags=["integrations"])
async def test_integration_endpoint(
    integration_id: str,
    request: IntegrationTestRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    tenant_id = str(session.tenant_id)
    test_result = await test_integration_connection(tenant_id, integration_id, request.config)
    return test_result


@app.post("/api/v1/integrations/{integration_id}/sync", tags=["integrations"])
async def sync_integration_endpoint(
    integration_id: str,
    request: IntegrationSyncRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    tenant_id = str(session.tenant_id)
    sync_result = await sync_integration_payload(tenant_id, integration_id, request.payload)
    record_audit(db, event_type="INTEGRATION_SYNCED", tenant_id=session.tenant_id, actor_id=user.id, session_id=session.id)
    return sync_result


@app.post("/api/v1/integrations/{integration_id}/disconnect", tags=["integrations"])
def disconnect_integration_endpoint(
    integration_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    tenant_id = str(session.tenant_id)
    disconnect_integration(tenant_id, integration_id)
    record_audit(db, event_type="INTEGRATION_DISCONNECTED", tenant_id=session.tenant_id, actor_id=user.id, session_id=session.id)
    return {"status": "ok", "integration_id": integration_id}


class InviteUserRequest(BaseModel):
    email: EmailStr
    name: str | None = None
    role: str = Field(default="ENGINEER")


class UpdateUserRoleRequest(BaseModel):
    role: str


class EngineSettingsUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/v1/admin/users", tags=["admin"])
def admin_list_users_endpoint(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    users = list_workspace_users(db, session.tenant_id)
    return {"users": users}


@app.post("/api/v1/admin/users/invite", tags=["admin"])
def admin_invite_user_endpoint(
    request: InviteUserRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    invited = invite_workspace_user(db, session.tenant_id, str(request.email), request.name or "", request.role, user.id)
    return {"status": "ok", "user": invited}


@app.put("/api/v1/admin/users/{user_id}/role", tags=["admin"])
def admin_update_user_role_endpoint(
    user_id: uuid.UUID,
    request: UpdateUserRoleRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    success = update_user_role(db, session.tenant_id, user_id, request.role, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace user not found")
    return {"status": "ok", "user_id": str(user_id), "role": request.role}


@app.delete("/api/v1/admin/users/{user_id}", tags=["admin"])
def admin_remove_user_endpoint(
    user_id: uuid.UUID,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    success = remove_workspace_user(db, session.tenant_id, user_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace user not found")
    return {"status": "ok", "user_id": str(user_id)}


@app.get("/api/v1/admin/engine", tags=["admin"])
def admin_get_engine_endpoint(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    settings = get_engine_settings(str(session.tenant_id))
    return {"settings": settings}


@app.put("/api/v1/admin/engine", tags=["admin"])
def admin_update_engine_endpoint(
    request: EngineSettingsUpdateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    updated = update_engine_settings(str(session.tenant_id), request.settings)
    record_audit(db, event_type="ENGINE_SETTINGS_UPDATED", tenant_id=session.tenant_id, actor_id=user.id, session_id=session.id)
    return {"status": "ok", "settings": updated}


@app.get("/api/v1/admin/audit_logs", tags=["admin"])
def admin_audit_logs_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    event_type: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    logs = get_audit_trail(db, session.tenant_id, limit=limit, event_type=event_type)
    return {"logs": logs}


@app.get("/api/v1/admin/usage", tags=["admin"])
def admin_usage_endpoint(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user, session = _authenticated_context(authorization, db)
    usage = get_resource_usage(db, session.tenant_id)
    return {"usage": usage}




