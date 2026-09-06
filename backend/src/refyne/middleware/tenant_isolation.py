import uuid
import json
from typing import Callable, Dict, Any
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import Response
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy import select
import refyne.db.session as db_session
from refyne.db.models import Project, Conversation, File, Requirement, WorkflowDefinition
from refyne.auth.service import get_authenticated_session, AuthenticationError
from refyne.auth.tokens import decode_access_token
from refyne.config import get_settings

settings = get_settings()


# Mapping of parameter names to checker functions
# Each checker function takes (db: Session, tenant_id: uuid.UUID, resource_id: uuid.UUID) -> Model | None
PARAM_CHECKERS: Dict[str, Callable[[Session, uuid.UUID, uuid.UUID], Any]] = {
    "project_id": lambda db, tenant_id, resource_id: db.scalar(
        select(Project).where(
            Project.id == resource_id,
            Project.tenant_id == tenant_id,
            Project.deleted_at.is_(None),
        )
    ),
    "conversation_id": lambda db, tenant_id, resource_id: db.scalar(
        select(Conversation).where(
            Conversation.id == resource_id,
            Conversation.tenant_id == tenant_id,
            Conversation.deleted_at.is_(None),
        )
    ),
    "file_id": lambda db, tenant_id, resource_id: db.scalar(
        select(File).where(
            File.id == resource_id,
            File.tenant_id == tenant_id,
            File.deleted_at.is_(None),
        )
    ),
    "requirement_id": lambda db, tenant_id, resource_id: db.scalar(
        select(Requirement).where(
            Requirement.id == resource_id,
            Requirement.tenant_id == tenant_id,
        )
    ),
    "workflow_definition_id": lambda db, tenant_id, resource_id: db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == resource_id,
            WorkflowDefinition.tenant_id == tenant_id,
        )
    ),
}


class TenantIsolationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        active_receive = receive
        request = Request(scope, receive)
        authorization: str | None = request.headers.get("Authorization")

        # If no authorization, skip tenant isolation (let auth middleware handle)
        if not authorization or not authorization.startswith("Bearer "):
            await self.app(scope, receive, send)
            return

        token = authorization[7:]  # Remove "Bearer "

        # Create a new DB session for this middleware
        db: Session = db_session.SessionLocal()
        try:
            # Get the authenticated user and session
            try:
                from refyne.main import _authenticated_context
                _, session = _authenticated_context(authorization, db)
            except Exception:
                # Invalid authentication, skip tenant isolation (auth middleware will return 401)
                await self.app(scope, receive, send)
                return

            tenant_id = session.tenant_id

            # Extract resource IDs from path and query parameters
            resource_ids: Dict[str, uuid.UUID] = {}
            # Path parameters from request URL path
            path_segments = [seg for seg in request.url.path.split("/") if seg]
            param_name_map = {
                "projects": "project_id",
                "conversations": "conversation_id",
                "files": "file_id",
                "requirements": "requirement_id",
                "workflows": "workflow_definition_id",
                "workflow_definitions": "workflow_definition_id",
            }
            for i in range(len(path_segments) - 1):
                res_name = path_segments[i]
                if res_name in param_name_map:
                    try:
                        resource_ids[param_name_map[res_name]] = uuid.UUID(path_segments[i + 1])
                    except (ValueError, TypeError):
                        pass
            if "path_params" in scope:
                for param_name, param_value in scope["path_params"].items():
                    if param_name in PARAM_CHECKERS:
                        try:
                            resource_ids[param_name] = uuid.UUID(param_value)
                        except ValueError:
                            pass  # Not a UUID, skip
            # Query parameters
            query_params = request.query_params
            for param_name in PARAM_CHECKERS:
                if param_name in query_params:
                    try:
                        resource_ids[param_name] = uuid.UUID(query_params[param_name])
                    except (ValueError, TypeError):
                        pass  # Not a UUID or missing, skip

            # Extract resource IDs from JSON body if present (skipping stream consumption on chat and file upload endpoints)
            if (
                request.method in ("POST", "PUT", "PATCH")
                and request.headers.get("content-type") == "application/json"
                and not request.url.path.startswith("/api/v1/chat/")
                and not request.url.path.startswith("/api/v1/files/upload")
                and not request.url.path.startswith("/api/v1/documents")
                and not request.url.path.startswith("/api/v1/conversations")
                and not request.url.path.startswith("/api/v1/projects")
            ):
                body = await request.body()
                if body:
                    try:
                        json_body = json.loads(body)
                        # Look for known resource ID keys in the JSON body
                        for param_name in PARAM_CHECKERS:
                            if param_name in json_body and json_body[param_name] is not None:
                                try:
                                    resource_ids[param_name] = uuid.UUID(str(json_body[param_name]))
                                except (ValueError, TypeError, json.JSONDecodeError):
                                    pass  # Not a UUID or invalid, skip
                    except json.JSONDecodeError:
                        pass  # Not JSON, skip

                    has_sent = False

                    async def receive_wrapper() -> dict:
                        nonlocal has_sent
                        if not has_sent:
                            has_sent = True
                            return {"type": "http.request", "body": body, "more_body": False}
                        return await receive()

                    active_receive = receive_wrapper

            # Check each resource ID
            for param_name, resource_id in resource_ids.items():
                checker = PARAM_CHECKERS[param_name]
                resource = checker(db, tenant_id, resource_id)
                if resource is None:
                    # Resource not found in tenant (or doesn't exist)
                    response = Response(
                        content='{"detail": "Access to resource is forbidden"}',
                        status_code=403,
                        media_type="application/json",
                    )
                    await response(scope, active_receive, send)
                    return

        finally:
            db.close()

        # If all checks pass, proceed to the app
        await self.app(scope, active_receive, send)