"""
Supervisor Chat API endpoint.

Single entry point for all user interactions through the Supervisor workflow.
Classifies intent, routes to the correct agent, executes it, and returns results.

Endpoint:
    POST /api/supervisor/chat

Security:
  - Requires valid JWT (authenticated user)
  - project_id ownership verified against authenticated user
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.project import Project
from app.agents.supervisor.service import handle_request_with_state
from app.agents.supervisor.orchestrator import execute
from app.agents.supervisor.state import (
    Intent,
    Route,
    SupervisorState,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["supervisor-chat"])


# ── Request/Response Schemas ───────────────────────────────────────────────────

class SupervisorChatRequest(BaseModel):
    """Input for the Supervisor chat endpoint."""
    project_id: str = Field(..., description="Active project ID")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Frontend conversation ID. Auto-generated if missing.",
    )
    user_message: str = Field(..., min_length=1, description="User message or command")
    action: Optional[str] = Field(
        default=None,
        description="Explicit action override (e.g. 'brd', 'srs'). "
                    "When provided, bypasses LLM classification and routes directly.",
    )
    document_ids: Optional[list[str]] = Field(
        default=None,
        description="Optional document IDs to restrict retrieval to",
    )


class SupervisorChatResponse(BaseModel):
    """Output from the Supervisor chat endpoint."""
    intent: str = Field(..., description="Classified intent value")
    route: str = Field(..., description="Resolved route value")
    requires_rag: bool = Field(..., description="Whether RAG retrieval was needed")
    confidence: float = Field(..., description="Classification confidence 0.0-1.0")
    workflow_status: str = Field(..., description="Final workflow status")
    session_id: str = Field(..., description="Supervisor session ID")
    conversation_id: str = Field(..., description="Frontend conversation ID")

    # Agent output
    content: Optional[str] = Field(
        default=None,
        description="Generated answer or document content",
    )
    title: Optional[str] = Field(
        default=None,
        description="Document title (for generation routes)",
    )
    action: Optional[str] = Field(
        default=None,
        description="Action that was executed (for generation routes)",
    )
    citations: list = Field(
        default_factory=list,
        description="Source citations from retrieval",
    )
    source_documents: list = Field(
        default_factory=list,
        description="Documents that contributed to the result",
    )

    # Error handling
    error: Optional[str] = Field(
        default=None,
        description="Error message if workflow failed",
    )


# ── Action → Intent Mapping ───────────────────────────────────────────────────
# Maps explicit action overrides to intents (bypasses LLM classification).

ACTION_INTENT_MAP: dict[str, Intent] = {
    "brd": Intent.BRD_GENERATION,
    "srs": Intent.SRS_GENERATION,
    "rtm": Intent.RTM_GENERATION,
    "user_stories": Intent.USER_STORY_GENERATION,
    "acceptance_criteria": Intent.ACCEPTANCE_CRITERIA_GENERATION,
    "business_rules": Intent.REQUIREMENT_GENERATION,
    "validation_rules": Intent.REQUIREMENT_GENERATION,
    "edge_cases": Intent.REQUIREMENT_GENERATION,
    "assumptions": Intent.REQUIREMENT_GENERATION,
    "risk_analysis": Intent.REQUIREMENT_GENERATION,
    "missing_requirements": Intent.REQUIREMENT_GENERATION,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_project_for_user(db: Session, project_id: str, user_id: str) -> Project:
    """Verify project ownership."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/api/supervisor/chat",
    response_model=SupervisorChatResponse,
    summary="Supervisor chat: classify, route, and execute",
    description=(
        "Processes a user message through the complete Supervisor workflow: "
        "classify intent, route to the correct agent, execute the agent, "
        "and return the result. Supports explicit action overrides for "
        "document generation buttons."
    ),
)
def supervisor_chat(
    body: SupervisorChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SupervisorChatResponse:
    # --- Ownership check ---
    _get_project_for_user(db, body.project_id, current_user.id)

    # --- Input validation ---
    query = body.user_message.strip()
    if not query:
        raise HTTPException(status_code=422, detail="user_message must not be empty")

    session_id = str(uuid.uuid4())
    conversation_id = body.conversation_id or str(uuid.uuid4())

    try:
        # --- If explicit action is provided, bypass LLM classification ---
        if body.action and body.action in ACTION_INTENT_MAP:
            intent = ACTION_INTENT_MAP[body.action]
            from app.agents.supervisor.router import route_from_intent
            decision = route_from_intent(intent=intent, confidence=1.0)

            # Build state directly — action is preserved for the orchestrator
            state = SupervisorState(
                user_id=current_user.id,
                project_id=body.project_id,
                session_id=session_id,
                user_query=query,
                intent=intent,
                route=decision.route,
                requires_rag=decision.requires_rag,
                document_ids=body.document_ids,
                workflow_status=decision.workflow_status,
                action=body.action,
            )
            state.metadata["classification_confidence"] = 1.0
            state.metadata["classification_reasoning"] = f"Explicit action override: {body.action}"

        else:
            # --- Classify and route via LLM ---
            response, state = handle_request_with_state(
                user_id=current_user.id,
                project_id=body.project_id,
                user_query=query,
                session_id=session_id,
            )
            state.document_ids = body.document_ids
            # If the LLM-classified intent maps to a generation action, set it
            if state.action is None and body.action:
                state.action = body.action

        # --- Execute the downstream agent ---
        state = execute(state, db)

        # --- Build source documents from citations ---
        source_docs = []
        seen = set()
        for c in (state.citations or []):
            doc_id = getattr(c, "document_id", None) or (c.get("document_id") if isinstance(c, dict) else None)
            doc_name = getattr(c, "file_name", None) or (c.get("file_name") if isinstance(c, dict) else None)
            if doc_id and doc_id not in seen:
                source_docs.append({"document_id": doc_id, "file_name": doc_name})
                seen.add(doc_id)

        # --- Build response ---
        return SupervisorChatResponse(
            intent=state.intent.value if state.intent else "unknown",
            route=state.route.value if state.route else "unknown",
            requires_rag=state.requires_rag,
            confidence=state.metadata.get("classification_confidence", 0.0),
            workflow_status=state.workflow_status.value,
            session_id=session_id,
            conversation_id=conversation_id,
            content=state.generated_output,
            title=state.metadata.get("document_title"),
            action=state.metadata.get("document_action") or state.action,
            citations=[c.model_dump() for c in state.citations] if state.citations else [],
            source_documents=source_docs,
            error=state.error,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Supervisor chat failed: {e}")
        return SupervisorChatResponse(
            intent="unknown",
            route="unknown",
            requires_rag=False,
            confidence=0.0,
            workflow_status=WorkflowStatus.FAILED.value,
            session_id=session_id,
            conversation_id=conversation_id,
            error=str(e),
        )
