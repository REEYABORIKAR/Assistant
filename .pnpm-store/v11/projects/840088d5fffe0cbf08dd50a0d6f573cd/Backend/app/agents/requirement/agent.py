"""
Requirement Agent.

Public entrypoint for requirement generation. Orchestrates the full pipeline:
1. Analyze request → build generation plan
2. Retrieve context via RAG
3. Generate structured output via LLM
4. Serialize to markdown for API compatibility
5. Write results back to state

The orchestrator calls only `execute(state, db)`.
"""
import logging

from sqlalchemy.orm import Session

from app.agents.requirement.analyzer import build_generation_plan
from app.agents.requirement.brd_generator import generate_brd
from app.agents.requirement.srs_generator import generate_srs
from app.agents.requirement.rtm_generator import generate_rtm
from app.agents.requirement.user_story_generator import generate_user_stories
from app.agents.requirement.acceptance_criteria_generator import generate_acceptance_criteria
from app.agents.requirement.generator import (
    generate_requirements,
    generate_requirements_fallback,
)
from app.agents.requirement.serializer import serialize_structured_output
from app.agents.supervisor.state import SupervisorState, WorkflowStatus
from app.rag.retrieval.hybrid import HybridRetriever
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)


def execute(state: SupervisorState, db: Session) -> SupervisorState:
    """
    Execute the Requirement Agent for the given state.

    This is the single public entrypoint. The orchestrator calls only this function.

    Args:
        state: SupervisorState with intent, route, and action already set.
        db: SQLAlchemy session for database access.

    Returns:
        Updated SupervisorState with generated output and structured data.
    """
    state.workflow_status = WorkflowStatus.GENERATING

    # 1. Build generation plan
    plan = build_generation_plan(state)
    if not plan:
        state.workflow_status = WorkflowStatus.FAILED
        state.error = f"Could not build generation plan for action: {state.action}"
        return state

    # 2. Retrieve context via RAG
    retriever = HybridRetriever(db)
    try:
        search_response = retriever.retrieve(
            project_id=state.project_id,
            query=plan.prompt,
            top_k=plan.top_k,
            document_ids=state.document_ids,
        )
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        state.workflow_status = WorkflowStatus.FAILED
        state.error = f"Retrieval failed: {str(e)}"
        return state

    state.retrieved_context = search_response.context
    state.citations = search_response.citations

    # 3. Generate structured output based on output type
    context = search_response.context or ""
    citations = search_response.citations

    content = ""
    structured_requirements = []
    structured_user_stories = []
    structured_acceptance_criteria = []

    if plan.output_type == "brd":
        brd = generate_brd(plan, context, citations)
        content = serialize_structured_output(plan.action, brd=brd, title=plan.title)
        # Flatten BRD requirements into the state
        structured_requirements = (
            brd.business_requirements
            + brd.functional_requirements
            + brd.non_functional_requirements
        )

    elif plan.output_type == "srs":
        srs = generate_srs(plan, context, citations)
        content = serialize_structured_output(plan.action, srs=srs, title=plan.title)
        # Check if content is just the title (LLM not configured)
        if content.strip() == f"# {plan.title}":
            content = _build_fallback_content(plan, search_response)
        else:
            structured_requirements = (
                srs.functional_requirements
                + srs.external_interface_requirements
                + srs.performance_requirements
            )

    elif plan.output_type == "rtm":
        rtm = generate_rtm(plan, context, citations)
        content = serialize_structured_output(plan.action, rtm=rtm, title=plan.title)
        # Check if content is just the title (LLM not configured)
        if content.strip().startswith(f"# {plan.title}") and "No traceability data" in content:
            content = _build_fallback_content(plan, search_response)

    elif plan.output_type == "user_stories":
        structured_user_stories = generate_user_stories(plan, context, citations)
        if structured_user_stories:
            content = serialize_structured_output(
                plan.action, user_stories=structured_user_stories, title=plan.title
            )
        else:
            content = _build_fallback_content(plan, search_response)

    elif plan.output_type == "acceptance_criteria":
        structured_acceptance_criteria = generate_acceptance_criteria(plan, context, citations)
        if structured_acceptance_criteria:
            content = serialize_structured_output(
                plan.action, acceptance_criteria=structured_acceptance_criteria, title=plan.title
            )
        else:
            content = _build_fallback_content(plan, search_response)

    else:
        # Generic requirement generation
        structured_requirements = generate_requirements(plan, context, citations)
        if structured_requirements:
            content = serialize_structured_output(
                plan.action, requirements=structured_requirements, title=plan.title
            )
        else:
            # Fallback when LLM is not configured
            content = _build_fallback_content(plan, search_response)
            structured_requirements = generate_requirements_fallback(context)

    # 4. Write results back to state
    state.generated_output = content
    state.requirements = [req.model_dump() for req in structured_requirements]
    state.user_stories = [s.model_dump() for s in structured_user_stories]
    state.acceptance_criteria = [ac.model_dump() for ac in structured_acceptance_criteria]
    state.metadata["document_title"] = plan.title
    state.metadata["document_action"] = plan.action
    state.workflow_status = WorkflowStatus.COMPLETED

    logger.info(
        f"Requirement Agent completed: action={plan.action}, "
        f"requirements={len(structured_requirements)}, "
        f"stories={len(structured_user_stories)}, "
        f"criteria={len(structured_acceptance_criteria)}"
    )
    return state


def _build_fallback_content(plan, search_response) -> str:
    """Build fallback content when LLM is not configured."""
    context = search_response.context if search_response.context else "No relevant content found in documents."
    return f"""# {plan.title}

## Overview
{context[:2000]}

## Notes
Set GROQ_API_KEY in Backend/.env for AI-powered generation.
"""
