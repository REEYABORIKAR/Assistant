"""
Supervisor Agent Service.

Single entry point for processing user requests through the Supervisor workflow.
Classifies intent, determines route, and returns routing decision.

Does NOT execute downstream agents — only determines where to route.
"""
import logging
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.supervisor.classifier import classify_intent, ClassificationResult
from app.agents.supervisor.router import (
    RouteDecision,
    route_from_intent,
    resolve_route,
    requires_rag,
    resolve_status,
)
from app.agents.supervisor.state import Intent, Route, SupervisorState, WorkflowStatus

logger = logging.getLogger(__name__)


# ── Request/Response Schemas ───────────────────────────────────────────────────

class SupervisorRequest(BaseModel):
    """Input schema for supervisor.handle_request()."""
    user_id: str = Field(..., description="Authenticated user ID")
    project_id: str = Field(..., description="Active project ID")
    session_id: Optional[str] = Field(
        default=None,
        description="Conversation session ID (auto-generated if not provided)",
    )
    user_query: str = Field(..., min_length=1, description="User input to classify")
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to accept classification",
    )


class SupervisorResponse(BaseModel):
    """Output schema for supervisor.handle_request()."""
    intent: str = Field(..., description="Classified intent value")
    route: str = Field(..., description="Resolved route value")
    requires_rag: bool = Field(..., description="Whether RAG retrieval is needed")
    confidence: float = Field(..., description="Classification confidence 0.0-1.0")
    workflow_status: str = Field(..., description="Current workflow status")
    session_id: str = Field(..., description="Session ID (original or auto-generated)")
    reason: str = Field(default="", description="Routing decision reason")


# ── Error Response ─────────────────────────────────────────────────────────────

class SupervisorError(BaseModel):
    """Error response from supervisor."""
    error: str
    detail: str
    workflow_status: str = "failed"


# ── Supervisor Service ─────────────────────────────────────────────────────────

def handle_request(
    user_id: str,
    project_id: str,
    user_query: str,
    session_id: Optional[str] = None,
    confidence_threshold: float = 0.5,
) -> SupervisorResponse:
    """
    Process a user request through the Supervisor workflow.

    Flow:
        1. Validate input
        2. Classify intent (LLM)
        3. Determine route
        4. Return routing decision

    Args:
        user_id: Authenticated user ID.
        project_id: Active project ID.
        user_query: User input to classify.
        session_id: Optional session ID (auto-generated if not provided).
        confidence_threshold: Minimum confidence to accept (default 0.5).

    Returns:
        SupervisorResponse with intent, route, requires_rag, confidence, etc.

    Raises:
        ValueError: On invalid input or classification failure.
    """
    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())

    # Validate input
    query_clean = user_query.strip()
    if not query_clean:
        raise ValueError("user_query must not be empty or whitespace-only")

    if not project_id:
        raise ValueError("project_id is required")

    if not user_id:
        raise ValueError("user_id is required")

    # Classify intent
    classification = classify_intent(
        user_query=query_clean,
        project_id=project_id,
        confidence_threshold=confidence_threshold,
    )

    # Build route decision
    decision = route_from_intent(
        intent=classification.intent,
        confidence=classification.confidence,
        confidence_threshold=confidence_threshold,
    )

    return SupervisorResponse(
        intent=decision.intent.value,
        route=decision.route.value,
        requires_rag=decision.requires_rag,
        confidence=classification.confidence,
        workflow_status=decision.workflow_status.value,
        session_id=session_id,
        reason=decision.reason,
    )


def handle_request_with_state(
    user_id: str,
    project_id: str,
    user_query: str,
    session_id: Optional[str] = None,
    confidence_threshold: float = 0.5,
) -> tuple[SupervisorResponse, SupervisorState]:
    """
    Like handle_request(), but also returns the full SupervisorState.
    Useful when you need to pass state to downstream agents later.

    Returns:
        Tuple of (SupervisorResponse, SupervisorState).
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    query_clean = user_query.strip()
    if not query_clean:
        raise ValueError("user_query must not be empty or whitespace-only")

    if not project_id:
        raise ValueError("project_id is required")

    if not user_id:
        raise ValueError("user_id is required")

    # Build initial state
    state = SupervisorState(
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        user_query=query_clean,
    )

    # Classify intent
    classification = classify_intent(
        user_query=query_clean,
        project_id=project_id,
        confidence_threshold=confidence_threshold,
    )

    # Update state with classification
    state.intent = classification.intent
    state.requires_rag = classification.requires_rag
    state.metadata["classification_confidence"] = classification.confidence
    state.metadata["classification_reasoning"] = classification.reasoning

    # Build route decision
    decision = route_from_intent(
        intent=classification.intent,
        confidence=classification.confidence,
        confidence_threshold=confidence_threshold,
    )

    # Update state with routing
    state.route = decision.route
    state.workflow_status = decision.workflow_status

    response = SupervisorResponse(
        intent=decision.intent.value,
        route=decision.route.value,
        requires_rag=decision.requires_rag,
        confidence=classification.confidence,
        workflow_status=decision.workflow_status.value,
        session_id=session_id,
        reason=decision.reason,
    )

    return response, state
