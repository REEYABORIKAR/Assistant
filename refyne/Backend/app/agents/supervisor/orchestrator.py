"""
Supervisor Orchestrator.

Thin coordinator that dispatches to the correct agent based on the route.
Contains no generation/validation logic — only routing and delegation.

Reuses existing services — no duplicate implementations.
"""
import logging
import time

from opentelemetry import trace
from sqlalchemy.orm import Session

from app.agents.supervisor.state import (
    Route,
    SupervisorState,
    WorkflowStatus,
)
from app.core.audit import write_audit_log
from app.core.config import settings
from app.core.metrics import (
    incr_generation,
    observe_generation_latency,
    observe_retrieval_latency,
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

    tracer = trace.get_tracer("refyne.orchestrator")
    with tracer.start_as_current_span(
        "orchestrator.execute",
        attributes={"route": route.value, "trace_id": state.trace_id, "project_id": state.project_id},
    ) as span:
        try:
            if route == Route.RAG:
                state = _execute_rag(state, db)
            elif route == Route.REQUIREMENT_AGENT:
                from app.agents.requirement import execute as requirement_execute
                state = requirement_execute(state, db)
                _write_audit_for_generation(state, db)
            elif route == Route.VALIDATION_AGENT:
                from app.agents.validation import execute as validation_execute
                state = validation_execute(state, db)
                _write_audit_for_validation(state, db)
            elif route == Route.DOCUMENT_AGENT:
                state = _execute_document_agent(state, db)
            elif route == Route.DIRECT_RESPONSE:
                state = _execute_direct_response(state)
            elif route == Route.HUMAN_REVIEW:
                state = _execute_human_review(state)
            else:
                state.workflow_status = WorkflowStatus.FAILED
                state.error = f"Unknown route: {route.value}"
            span.set_attribute("workflow_status", state.workflow_status.value)
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("error", True)
            logger.exception(
                "Orchestrator failed",
                extra={"route": route.value, "trace_id": state.trace_id, "project_id": state.project_id, "error": str(e)},
            )
            state.workflow_status = WorkflowStatus.FAILED
            state.error = str(e)

    return state


# ── Agent Executors ───────────────────────────────────────────────────────────

def _execute_rag(state: SupervisorState, db: Session) -> SupervisorState:
    """RAG route: hybrid retrieval + LLM answer generation."""
    state.workflow_status = WorkflowStatus.RETRIEVING
    t_start = time.perf_counter()

    tracer = trace.get_tracer("refyne.rag")

    with tracer.start_as_current_span(
        "rag.retrieve",
        attributes={"project_id": state.project_id, "trace_id": state.trace_id},
    ) as span:
        retriever = HybridRetriever(db)
        search_response = retriever.retrieve(
            project_id=state.project_id,
            query=state.user_query,
            top_k=8,
            document_ids=state.document_ids,
            user_role=state.user_role,
            trace_id=state.trace_id,
        )
        span.set_attribute("results_count", len(search_response.results))
        span.set_attribute("context_length", len(search_response.context or ""))

    retrieval_ms = (time.perf_counter() - t_start) * 1000
    observe_retrieval_latency(retrieval_ms, project_id=state.project_id)

    state.retrieved_context = search_response.context
    state.citations = search_response.citations

    # Fail-closed: refuse generation when no context found
    if not search_response.context or not search_response.context.strip():
        if not settings.ALLOW_GENERATION_WITHOUT_CONTEXT:
            state.workflow_status = WorkflowStatus.COMPLETED
            state.generated_output = (
                "No relevant context found in the project documents for this query. "
                "I cannot provide an answer without relevant source material. "
                "Please try rephrasing your question or upload more documents to the project."
            )
            state.metadata["no_context"] = True
            return state

    state.workflow_status = WorkflowStatus.GENERATING

    t_gen = time.perf_counter()
    with tracer.start_as_current_span(
        "rag.generate",
        attributes={"project_id": state.project_id, "trace_id": state.trace_id},
    ) as span:
        generation = generate_answer(
            query=state.user_query,
            context=search_response.context,
            citations=search_response.citations,
            trace_id=state.trace_id,
        )
        span.set_attribute("configured", generation["configured"])
        span.set_attribute("answer_length", len(generation["answer"] or ""))

    generation_ms = (time.perf_counter() - t_gen) * 1000
    observe_generation_latency(generation_ms, project_id=state.project_id)
    incr_generation(project_id=state.project_id, configured=generation["configured"])

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
        from app.agents.document.agent import DocumentAgent
        from app.models.document import Document

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


# ── Audit Helpers ────────────────────────────────────────────────────────────

def _write_audit_for_generation(state: SupervisorState, db: Session) -> None:
    """Write audit entry after requirement generation completes."""
    try:
        write_audit_log(
            db,
            user_id=state.user_id,
            project_id=state.project_id,
            action="GENERATE_REQUIREMENTS",
            resource_type="requirement",
            resource_id=state.session_id,
            trace_id=state.trace_id,
            details={
                "action": state.action,
                "requirements_count": len(state.requirements or []),
                "user_stories_count": len(state.user_stories or []),
                "acceptance_criteria_count": len(state.acceptance_criteria or []),
            },
            status="success" if state.workflow_status != WorkflowStatus.FAILED else "failure",
        )
    except Exception:
        logger.warning("Failed to write audit log for generation", extra={"trace_id": state.trace_id})


def _write_audit_for_validation(state: SupervisorState, db: Session) -> None:
    """Write audit entry after validation completes."""
    try:
        validation_result = state.validation_result or {}
        write_audit_log(
            db,
            user_id=state.user_id,
            project_id=state.project_id,
            action="VALIDATE_REQUIREMENTS",
            resource_type="validation_report",
            resource_id=state.session_id,
            trace_id=state.trace_id,
            details={
                "status": state.metadata.get("validation_status"),
                "score": state.validation_score,
                "issues_count": state.metadata.get("validation_issues_count", 0),
            },
            status="success" if state.workflow_status != WorkflowStatus.FAILED else "failure",
        )
    except Exception:
        logger.warning("Failed to write audit log for validation", extra={"trace_id": state.trace_id})
