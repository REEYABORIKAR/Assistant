"""
Supervisor Orchestrator.

Thin coordinator that dispatches to the correct agent based on the route.
Contains no generation/validation logic — only routing and delegation.

Reuses existing services — no duplicate implementations.
"""
import logging

from sqlalchemy.orm import Session

from app.agents.supervisor.state import (
    Intent,
    Route,
    SupervisorState,
    WorkflowStatus,
)
from app.rag.retrieval.hybrid import HybridRetriever
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)

# Re-export for backward compatibility (tests import this from orchestrator)
from app.agents.requirement.analyzer import INTENT_TO_ACTION  # noqa: F401
from app.agents.requirement.analyzer import resolve_action as _resolve_action  # noqa: F401


def execute(state: SupervisorState, db: Session) -> SupervisorState:
    """
    Execute the downstream agent for the given SupervisorState.

    This is a thin coordinator. It reads state.route and dispatches
    to the correct agent module. No generation or validation logic
    lives here.

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
            from app.agents.requirement import execute as requirement_execute
            state = requirement_execute(state, db)
        elif route == Route.VALIDATION_AGENT:
            from app.agents.validation import execute as validation_execute
            state = validation_execute(state, db)
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
        msg = generation.get("message", "")
        context_text = search_response.context or "No matching content found."
        state.generated_output = f"{msg}\n\n{context_text}" if msg else context_text

    state.workflow_status = WorkflowStatus.COMPLETED
    return state


def _execute_document_agent(state: SupervisorState, db: Session) -> SupervisorState:
    """Document Agent route: process documents through the existing ingestion pipeline."""
    state.workflow_status = WorkflowStatus.GENERATING

    if state.document_ids:
        from app.models.document import Document
        from app.agents.document.agent import DocumentAgent

        results = []
        agent = DocumentAgent(db)

        for doc_id in state.document_ids:
            doc = db.query(Document).filter(
                Document.id == doc_id,
                Document.project_id == state.project_id,
            ).first()
            if not doc:
                results.append({"document_id": doc_id, "status": "not_found"})
                continue

            agent.process_document(doc)
            db.refresh(doc)
            results.append({
                "document_id": doc.id,
                "file_name": doc.file_name,
                "status": doc.status,
                "error": doc.error_message,
            })

        state.metadata["document_action"] = "document_ingestion"
        state.metadata["processing_results"] = results

        indexed = [r for r in results if r["status"] == "indexed"]
        failed = [r for r in results if r["status"] == "failed"]
        not_found = [r for r in results if r["status"] == "not_found"]

        parts = []
        if indexed:
            parts.append(f"{len(indexed)} document(s) indexed successfully")
        if failed:
            parts.append(f"{len(failed)} document(s) failed processing")
        if not_found:
            parts.append(f"{len(not_found)} document(s) not found")

        state.generated_output = (
            f"Document processing complete: {', '.join(parts)}. "
            "You can now ask questions about these documents."
        )
        state.workflow_status = WorkflowStatus.COMPLETED
        return state

    state.generated_output = (
        "Document ingestion is handled through the document upload endpoint. "
        "Please use the Upload Document button to upload your file for processing. "
        "The system will automatically extract content, chunk it, generate embeddings, "
        "and index it for search."
    )
    state.metadata["document_action"] = "document_ingestion"
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
    """Human review route: acknowledge and wait for human input."""
    state.workflow_status = WorkflowStatus.AWAITING_HUMAN
    state.generated_output = (
        "I've noted your request for human review. "
        "This feature will be available soon. "
        "In the meantime, you can continue working with other features."
    )
    return state
