"""
Supervisor Orchestrator.

Executes the downstream agent determined by the Supervisor routing layer.
This is the missing execution layer: it takes a SupervisorState with a
resolved route and dispatches to the correct agent/service.

Reuses existing services — no duplicate implementations.
"""
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.supervisor.state import (
    Intent,
    Route,
    SupervisorState,
    WorkflowStatus,
)
from app.rag.retrieval.hybrid import HybridRetriever
from app.services.generation import generate_answer
from app.api.document_generation import DOCUMENT_PROMPTS

logger = logging.getLogger(__name__)


# ── Intent → Document Generation Action Mapping ────────────────────────────────
# Maps generation intents to the action key used by DOCUMENT_PROMPTS.

INTENT_TO_ACTION: dict[Intent, str] = {
    Intent.BRD_GENERATION: "brd",
    Intent.SRS_GENERATION: "srs",
    Intent.RTM_GENERATION: "rtm",
    Intent.USER_STORY_GENERATION: "user_stories",
    Intent.ACCEPTANCE_CRITERIA_GENERATION: "acceptance_criteria",
    Intent.REQUIREMENT_GENERATION: "brd",  # generic requirement gen defaults to BRD
    Intent.REVISION: "brd",  # revision regenerates; default to BRD
}


# ── Orchestrator ──────────────────────────────────────────────────────────────

def execute(state: SupervisorState, db: Session) -> SupervisorState:
    """
    Execute the downstream agent for the given SupervisorState.

    Reads state.route and state.intent, dispatches to the appropriate
    service, and writes results back into state.

    Args:
        state: SupervisorState with intent and route already set.
        db: SQLAlchemy session for database access.

    Returns:
        Updated SupervisorState with results or error.
    """
    route = state.route
    intent = state.intent

    if route is None or intent is None:
        state.workflow_status = WorkflowStatus.FAILED
        state.error = "No route or intent specified"
        return state

    try:
        if route == Route.RAG:
            state = _execute_rag(state, db)
        elif route == Route.REQUIREMENT_AGENT:
            state = _execute_requirement_agent(state, db)
        elif route == Route.VALIDATION_AGENT:
            state = _execute_validation_agent(state, db)
        elif route == Route.DOCUMENT_AGENT:
            state = _execute_document_agent(state, db)
        elif route == Route.DIRECT_RESPONSE:
            state = _execute_direct_response(state)
        elif route == Route.HUMAN_REVIEW:
            state = _execute_human_review(state)
        else:
            state.workflow_status = WorkflowStatus.FAILED
            state.error = f"Unknown route: {route.value}"
    except Exception as e:
        logger.exception(f"Orchestrator failed for route {route.value}: {e}")
        state.workflow_status = WorkflowStatus.FAILED
        state.error = str(e)

    return state


# ── Agent Executors ───────────────────────────────────────────────────────────

def _execute_rag(state: SupervisorState, db: Session) -> SupervisorState:
    """RAG route: hybrid retrieval + LLM answer generation."""
    state.workflow_status = WorkflowStatus.RETRIEVING

    retriever = HybridRetriever(db)
    search_response = retriever.retrieve(
        project_id=state.project_id,
        query=state.user_query,
        top_k=8,
        document_ids=state.document_ids,
    )

    state.retrieved_context = search_response.context
    state.citations = search_response.citations
    state.workflow_status = WorkflowStatus.GENERATING

    generation = generate_answer(
        query=state.user_query,
        context=search_response.context,
        citations=search_response.citations,
    )

    if generation["configured"] and generation["answer"]:
        state.generated_output = generation["answer"]
    else:
        # Fallback: return retrieval context with message
        msg = generation.get("message", "")
        context_text = search_response.context or "No matching content found."
        state.generated_output = f"{msg}\n\n{context_text}" if msg else context_text

    state.workflow_status = WorkflowStatus.COMPLETED
    return state


def _execute_requirement_agent(state: SupervisorState, db: Session) -> HybridRetriever | SupervisorState:
    """Requirement Agent route: RAG retrieval + document generation."""
    state.workflow_status = WorkflowStatus.GENERATING

    action = INTENT_TO_ACTION.get(state.intent, "brd")
    action_config = DOCUMENT_PROMPTS.get(action)

    if not action_config:
        state.workflow_status = WorkflowStatus.FAILED
        state.error = f"Unknown document action: {action}"
        return state

    # Retrieve relevant context
    retriever = HybridRetriever(db)
    search_response = retriever.retrieve(
        project_id=state.project_id,
        query=action_config["prompt"],
        top_k=10,
        document_ids=state.document_ids,
    )

    state.retrieved_context = search_response.context
    state.citations = search_response.citations

    # Generate document using LLM
    generation = generate_answer(
        query=action_config["prompt"],
        context=search_response.context,
        citations=search_response.citations,
    )

    if generation["configured"] and generation["answer"]:
        content = f"# {action_config['title']}\n\n{generation['answer']}"
    else:
        content = _build_fallback_content(action, action_config, search_response)

    state.generated_output = content
    state.metadata["document_title"] = action_config["title"]
    state.metadata["document_action"] = action
    state.workflow_status = WorkflowStatus.COMPLETED
    return state


def _execute_validation_agent(state: SupervisorState, db: Session) -> SupervisorState:
    """Validation Agent route: retrieve context and produce validation report."""
    state.workflow_status = WorkflowStatus.VALIDATING

    # Retrieve the requirements to validate
    retriever = HybridRetriever(db)
    search_response = retriever.retrieve(
        project_id=state.project_id,
        query=state.user_query,
        top_k=10,
        document_ids=state.document_ids,
    )

    state.retrieved_context = search_response.context
    state.citations = search_response.citations

    # Generate validation report
    validation_prompt = (
        "Review the following requirements and provide a validation report. "
        "For each requirement, check:\n"
        "1. Is it clear and unambiguous?\n"
        "2. Is it testable/verifiable?\n"
        "3. Is it complete (no missing information)?\n"
        "4. Are there conflicts with other requirements?\n"
        "5. Is it traceable to a source?\n\n"
        "Provide a structured validation report with:\n"
        "- Overall assessment (Pass/Conditional/Fail)\n"
        "- Per-requirement findings\n"
        "- Issues found\n"
        "- Recommendations\n\n"
        f"Requirements to validate:\n{search_response.context or 'No requirements found.'}"
    )

    generation = generate_answer(
        query=validation_prompt,
        context=search_response.context or "",
        citations=search_response.citations,
    )

    if generation["configured"] and generation["answer"]:
        state.generated_output = f"# Requirements Validation Report\n\n{generation['answer']}"
    else:
        state.generated_output = (
            "# Requirements Validation Report\n\n"
            f"**Validation Status:** Pending Review\n\n"
            f"The following requirements were found for validation:\n\n"
            f"{search_response.context or 'No requirements found in the project documents.'}\n\n"
            f"Set GROQ_API_KEY in Backend/.env for AI-powered validation."
        )

    state.metadata["validation_type"] = "requirement_validation"
    state.workflow_status = WorkflowStatus.COMPLETED
    return state


def _execute_document_agent(state: SupervisorState, db: Session) -> SupervisorState:
    """Document Agent route: acknowledge document ingestion request."""
    state.workflow_status = WorkflowStatus.GENERATING
    state.generated_output = (
        "Document ingestion is handled through the document upload endpoint. "
        "Please use the Upload Document button to upload your file for processing."
    )
    state.workflow_status = WorkflowStatus.COMPLETED
    return state


def _execute_direct_response(state: SupervisorState) -> SupervisorState:
    """Direct response route: no agent needed, answer directly."""
    state.workflow_status = WorkflowStatus.COMPLETED
    state.generated_output = (
        "I'm not sure what you'd like me to do. You can:\n"
        "- Ask a question about your documents\n"
        "- Generate a document (BRD, SRS, RTM, etc.)\n"
        "- Upload a new document\n"
        "- Validate requirements\n\n"
        "What would you like to do?"
    )
    return state


def _execute_human_review(state: SupervisorState) -> SupervisorState:
    """Human review route: acknowledge and wait."""
    state.workflow_status = WorkflowStatus.AWAITING_HUMAN
    state.generated_output = (
        "I've noted your request for human review. "
        "This feature will be available soon. "
        "In the meantime, you can continue working with other features."
    )
    state.workflow_status = WorkflowStatus.COMPLETED
    return state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_fallback_content(action: str, config: dict, search_response) -> str:
    """Build fallback content when LLM is not configured."""
    context = search_response.context if search_response.context else "No relevant content found in documents."
    return f"""# {config['title']}

## Overview
{context[:2000]}

## Notes
Set GROQ_API_KEY in Backend/.env for AI-powered generation.
"""
