"""
Shared workflow state for the Supervisor Agent.

This module defines the single source of truth for all data flowing through
the Supervisor → RAG → Requirement Agent → Validation Agent → Human Review
pipeline. Every component reads from and writes to this state.

Designed for LangGraph StateGraph compatibility (Pydantic-based state).
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

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

class ReviewStatus(str, Enum):
    """Status of a human review task."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class StructuredError(BaseModel):
    """Structured error object for the errors list."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    field: str | None = Field(default=None, description="Field that caused the error, if applicable")


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
    user_role: str | None = Field(
        default=None,
        description="User's role in the project (ADMIN, EDITOR, REVIEWER, VIEWER)",
    )
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique trace ID for this request lifecycle",
    )

    # ── User Input ─────────────────────────────────────────────────────────
    user_query: str = Field(..., description="Raw user query or command")
    intent: Intent | None = Field(
        default=None,
        description="Classified intent after supervisor routing",
    )
    route: Route | None = Field(
        default=None,
        description="Which agent path processes this request",
    )
    action: str | None = Field(
        default=None,
        description="Explicit document generation action (e.g. 'brd', 'srs', 'risk_analysis'). "
                    "Preserved from frontend through to the requirement agent.",
    )

    # ── RAG Pipeline ───────────────────────────────────────────────────────
    requires_rag: bool = Field(
        default=False,
        description="Whether this query needs document retrieval",
    )
    document_ids: list[str] | None = Field(
        default=None,
        description="Specific document IDs to restrict retrieval to",
    )
    retrieved_context: str | None = Field(
        default=None,
        description="LLM-ready context string from RAG retrieval",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source citations from retrieved chunks",
    )

    # ── Generation ─────────────────────────────────────────────────────────
    generated_output: str | None = Field(
        default=None,
        description="Generated answer or document content (markdown for frontend)",
    )

    # ── Structured Requirement Output ──────────────────────────────────────
    requirements: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured requirement objects (internal, not markdown)",
    )
    user_stories: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured user story objects",
    )
    acceptance_criteria: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured acceptance criteria objects",
    )

    # ── Validation ─────────────────────────────────────────────────────────
    validation_result: dict[str, Any] | None = Field(
        default=None,
        description="Validation output (pass/fail, issues, suggestions)",
    )
    validation_score: float | None = Field(
        default=None,
        description="Overall validation score 0.0-1.0",
    )

    # ── Human Review ───────────────────────────────────────────────────────
    human_feedback: str | None = Field(
        default=None,
        description="Feedback or edits from human reviewer",
    )
    review_status: ReviewStatus = Field(
        default=ReviewStatus.PENDING,
        description="Current review status",
    )

    # ── Artifact Tracking ──────────────────────────────────────────────────
    artifact_id: str | None = Field(
        default=None,
        description="ID of the generated artifact, if persisted",
    )
    artifact_version: int | None = Field(
        default=None,
        description="Version number of the artifact",
    )

    # ── Workflow Control ───────────────────────────────────────────────────
    workflow_status: WorkflowStatus = Field(
        default=WorkflowStatus.PENDING,
        description="Current execution status",
    )
    error: str | None = Field(
        default=None,
        description="Error message if workflow failed",
    )
    errors: list[StructuredError] = Field(
        default_factory=list,
        description="Structured list of errors encountered during processing",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata (timing, debug info, etc.)",
    )
