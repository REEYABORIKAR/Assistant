"""
Shared workflow state for the Supervisor Agent.

This module defines the single source of truth for all data flowing through
the Supervisor → RAG → Requirement Agent → Validation Agent → Human Review
pipeline. Every component reads from and writes to this state.

Designed for LangGraph StateGraph compatibility (Pydantic-based state).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.rag.retrieval.schemas import Citation


# ── Supervisor Intent Definitions ──────────────────────────────────────────────
# Strongly typed intents the Supervisor can classify from user input.
# These are pure definitions — no LLM or routing logic here.

class Intent(str, Enum):
    """
    All valid user intents the Supervisor can identify.

    Each intent maps to exactly one Route. The mapping is defined
    separately in the routing logic, not here.
    """

    # Document operations
    DOCUMENT_INGESTION = "document_ingestion"
    DOCUMENT_SEARCH = "document_search"

    # Question answering
    QUESTION_ANSWERING = "question_answering"

    # Requirement generation (specific document types)
    REQUIREMENT_GENERATION = "requirement_generation"
    USER_STORY_GENERATION = "user_story_generation"
    ACCEPTANCE_CRITERIA_GENERATION = "acceptance_criteria_generation"
    BRD_GENERATION = "brd_generation"
    SRS_GENERATION = "srs_generation"
    RTM_GENERATION = "rtm_generation"

    # Validation and review
    REQUIREMENT_VALIDATION = "requirement_validation"
    HUMAN_REVIEW = "human_review"
    REVISION = "revision"

    # Context and fallback
    PROJECT_CONTEXT = "project_context"
    UNKNOWN = "unknown"


# ── Supervisor Route Definitions ──────────────────────────────────────────────
# Strongly typed routes the Supervisor can dispatch to.
# The Supervisor must only return one of these valid routes.

class Route(str, Enum):
    """
    All valid routing destinations for the Supervisor.

    Each Intent maps to exactly one Route. The Supervisor classifies
    the intent, then dispatches to the corresponding route.
    """

    RAG = "rag"                            # RAG search / question answering
    REQUIREMENT_AGENT = "requirement_agent"  # Document generation (BRD, SRS, etc.)
    VALIDATION_AGENT = "validation_agent"  # Requirement validation
    DOCUMENT_AGENT = "document_agent"      # Document upload/ingestion
    HUMAN_REVIEW = "human_review"          # Escalate to human reviewer
    REVISION = "revision"                  # Revise previously generated output
    DIRECT_RESPONSE = "direct_response"    # No agent needed, answer directly
    UNKNOWN = "unknown"                    # Unclassified, fallback


class WorkflowStatus(str, Enum):
    """Current status of the workflow execution."""
    PENDING = "pending"
    CLASSIFYING = "classifying"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    VALIDATING = "validating"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Shared Workflow State ──────────────────────────────────────────────────────

class SupervisorState(BaseModel):
    """
    Shared state passed through the entire Supervisor workflow.

    Every agent reads the fields it needs and writes its output back
    into this state. The workflow is:
        User → Supervisor (classify) → RAG → Requirement → Validation → Human Review

    LangGraph compatible: this model can be used as the state_schema
    in a StateGraph by passing it to `StateGraph(SupervisorState)`.
    """

    # ── Identity ───────────────────────────────────────────────────────────
    user_id: str = Field(..., description="ID of the authenticated user")
    project_id: str = Field(..., description="ID of the active project")
    session_id: str = Field(..., description="Unique session/conversation ID")

    # ── User Input ─────────────────────────────────────────────────────────
    user_query: str = Field(..., description="Raw user query or command")
    intent: Optional[Intent] = Field(
        default=None,
        description="Classified intent after supervisor routing",
    )
    route: Optional[Route] = Field(
        default=None,
        description="Which agent path processes this request",
    )
    action: Optional[str] = Field(
        default=None,
        description="Explicit document generation action (e.g. 'brd', 'srs', 'risk_analysis'). "
                    "Preserved from frontend through to the requirement agent.",
    )

    # ── RAG Pipeline ───────────────────────────────────────────────────────
    requires_rag: bool = Field(
        default=False,
        description="Whether this query needs document retrieval",
    )
    document_ids: Optional[list[str]] = Field(
        default=None,
        description="Specific document IDs to restrict retrieval to",
    )
    retrieved_context: Optional[str] = Field(
        default=None,
        description="LLM-ready context string from RAG retrieval",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source citations from retrieved chunks",
    )

    # ── Generation ─────────────────────────────────────────────────────────
    generated_output: Optional[str] = Field(
        default=None,
        description="Generated answer or document content",
    )

    # ── Validation ─────────────────────────────────────────────────────────
    validation_result: Optional[dict[str, Any]] = Field(
        default=None,
        description="Validation output (pass/fail, issues, suggestions)",
    )

    # ── Human Review ───────────────────────────────────────────────────────
    human_feedback: Optional[str] = Field(
        default=None,
        description="Feedback or edits from human reviewer",
    )

    # ── Workflow Control ───────────────────────────────────────────────────
    workflow_status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING,
        description="Current execution status",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if workflow failed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata (timing, debug info, etc.)",
    )
