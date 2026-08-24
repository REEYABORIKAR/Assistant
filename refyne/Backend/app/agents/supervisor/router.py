"""
Supervisor Routing Layer.

Converts classified intent + workflow state into a routing decision.
Does NOT execute agents — only determines where to route.

The router enforces valid routes and handles edge cases like
missing intent, failed classification, or workflow state conflicts.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.agents.supervisor.state import Intent, Route, SupervisorState, WorkflowStatus

logger = logging.getLogger(__name__)


# ── Routing Decision ───────────────────────────────────────────────────────────

class RouteDecision(BaseModel):
    """
    Immutable routing decision returned by the router.
    This is what the Supervisor emits before dispatching to an agent.
    """
    intent: Intent = Field(..., description="The classified intent")
    route: Route = Field(..., description="The resolved route to dispatch to")
    requires_rag: bool = Field(..., description="Whether RAG retrieval is needed")
    workflow_status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING,
        description="Updated workflow status after routing",
    )
    reason: str = Field(default="", description="Brief explanation of routing decision")


# ── Intent → Route Mapping ────────────────────────────────────────────────────
# Canonical routing table. Each intent maps to exactly one route.
# This is the single source of truth for routing decisions.

INTENT_TO_ROUTE: dict[Intent, Route] = {
    # Document operations
    Intent.DOCUMENT_INGESTION: Route.DOCUMENT_AGENT,
    Intent.DOCUMENT_SEARCH: Route.RAG,

    # Question answering
    Intent.QUESTION_ANSWERING: Route.RAG,

    # Requirement generation (all go to REQUIREMENT_AGENT)
    Intent.REQUIREMENT_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.USER_STORY_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.ACCEPTANCE_CRITERIA_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.BRD_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.SRS_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.RTM_GENERATION: Route.REQUIREMENT_AGENT,

    # Validation
    Intent.REQUIREMENT_VALIDATION: Route.VALIDATION_AGENT,

    # Human review
    Intent.HUMAN_REVIEW: Route.HUMAN_REVIEW,

    # Revision → back to REQUIREMENT_AGENT for regeneration
    Intent.REVISION: Route.REQUIREMENT_AGENT,

    # Project context → RAG for document-based answers
    Intent.PROJECT_CONTEXT: Route.RAG,

    # Fallback
    Intent.UNKNOWN: Route.DIRECT_RESPONSE,
}

# Intents that require RAG retrieval before processing
RAG_INTENTS: set[Intent] = {
    Intent.DOCUMENT_SEARCH,
    Intent.QUESTION_ANSWERING,
    Intent.REQUIREMENT_GENERATION,
    Intent.USER_STORY_GENERATION,
    Intent.ACCEPTANCE_CRITERIA_GENERATION,
    Intent.BRD_GENERATION,
    Intent.SRS_GENERATION,
    Intent.RTM_GENERATION,
    Intent.PROJECT_CONTEXT,
    Intent.REVISION,
}

# Intents that skip RAG (no document context needed)
NO_RAG_INTENTS: set[Intent] = {
    Intent.REQUIREMENT_VALIDATION,
    Intent.HUMAN_REVIEW,
    Intent.DOCUMENT_INGESTION,
    Intent.UNKNOWN,
}


# ── Workflow Status Mapping ────────────────────────────────────────────────────
# Maps intent to the appropriate workflow status after routing.

INTENT_TO_STATUS: dict[Intent, WorkflowStatus] = {
    Intent.DOCUMENT_INGESTION: WorkflowStatus.GENERATING,
    Intent.DOCUMENT_SEARCH: WorkflowStatus.RETRIEVING,
    Intent.QUESTION_ANSWERING: WorkflowStatus.RETRIEVING,
    Intent.REQUIREMENT_GENERATION: WorkflowStatus.GENERATING,
    Intent.USER_STORY_GENERATION: WorkflowStatus.GENERATING,
    Intent.ACCEPTANCE_CRITERIA_GENERATION: WorkflowStatus.GENERATING,
    Intent.BRD_GENERATION: WorkflowStatus.GENERATING,
    Intent.SRS_GENERATION: WorkflowStatus.GENERATING,
    Intent.RTM_GENERATION: WorkflowStatus.GENERATING,
    Intent.REQUIREMENT_VALIDATION: WorkflowStatus.VALIDATING,
    Intent.HUMAN_REVIEW: WorkflowStatus.AWAITING_HUMAN,
    Intent.REVISION: WorkflowStatus.GENERATING,
    Intent.PROJECT_CONTEXT: WorkflowStatus.RETRIEVING,
    Intent.UNKNOWN: WorkflowStatus.PENDING,
}


# ── Routing Functions ──────────────────────────────────────────────────────────

def resolve_route(intent: Intent) -> Route:
    """
    Resolve an intent to its canonical route.
    Always returns a valid Route — never raises.
    """
    route = INTENT_TO_ROUTE.get(intent)
    if route is None:
        logger.warning(f"No route mapping for intent: {intent}. Falling back to DIRECT_RESPONSE.")
        return Route.DIRECT_RESPONSE
    return route


def requires_rag(intent: Intent) -> bool:
    """Determine if an intent requires RAG retrieval."""
    return intent in RAG_INTENTS


def resolve_status(intent: Intent) -> WorkflowStatus:
    """Resolve the workflow status for a given intent."""
    return INTENT_TO_STATUS.get(intent, WorkflowStatus.PENDING)


def route_intent(
    state: SupervisorState,
    confidence_threshold: float = 0.5,
) -> RouteDecision:
    """
    Route a workflow state to the appropriate agent.

    This is the main routing entry point. It reads the intent from state,
    resolves the route, determines RAG requirements, and returns an
    immutable RouteDecision.

    Args:
        state: Current workflow state (must have intent set by classifier).
        confidence_threshold: Minimum confidence to accept routing.
                              Below this, routes to DIRECT_RESPONSE.

    Returns:
        RouteDecision with intent, route, requires_rag, workflow_status.
    """
    intent = state.intent

    # Handle missing intent
    if intent is None:
        logger.info("No intent classified. Routing to DIRECT_RESPONSE.")
        return RouteDecision(
            intent=Intent.UNKNOWN,
            route=Route.DIRECT_RESPONSE,
            requires_rag=False,
            workflow_status=WorkflowStatus.PENDING,
            reason="No intent classified",
        )

    # Check confidence threshold
    confidence = state.metadata.get("classification_confidence", 1.0)
    if confidence < confidence_threshold:
        logger.info(
            f"Low confidence ({confidence:.2f} < {confidence_threshold}). "
            f"Routing to DIRECT_RESPONSE."
        )
        return RouteDecision(
            intent=intent,
            route=Route.DIRECT_RESPONSE,
            requires_rag=False,
            workflow_status=WorkflowStatus.PENDING,
            reason=f"Below confidence threshold ({confidence:.2f} < {confidence_threshold})",
        )

    # Resolve route and status
    route = resolve_route(intent)
    status = resolve_status(intent)
    rag = requires_rag(intent)

    return RouteDecision(
        intent=intent,
        route=route,
        requires_rag=rag,
        workflow_status=status,
        reason=f"Routed {intent.value} -> {route.value}",
    )


def route_from_intent(
    intent: Intent,
    confidence: float = 1.0,
    confidence_threshold: float = 0.5,
) -> RouteDecision:
    """
    Convenience function to route directly from an intent.
    Useful when you have the intent but not a full SupervisorState.

    Args:
        intent: The classified intent.
        confidence: Classification confidence (0.0-1.0).
        confidence_threshold: Minimum confidence to accept.

    Returns:
        RouteDecision with routing decision.
    """
    if confidence < confidence_threshold:
        return RouteDecision(
            intent=intent,
            route=Route.DIRECT_RESPONSE,
            requires_rag=False,
            workflow_status=WorkflowStatus.PENDING,
            reason=f"Below confidence threshold ({confidence:.2f} < {confidence_threshold})",
        )

    route = resolve_route(intent)
    status = resolve_status(intent)
    rag = requires_rag(intent)

    return RouteDecision(
        intent=intent,
        route=route,
        requires_rag=rag,
        workflow_status=status,
        reason=f"Routed {intent.value} -> {route.value}",
    )
