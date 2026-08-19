"""
Validation Agent.

Public entrypoint for requirement validation. Orchestrates the full pipeline:
1. Extract requirements from state (structured or from context)
2. Run all validators (rule, LLM, duplicate, traceability)
3. Merge into a single ValidationReport
4. Serialize report to markdown for API compatibility
5. Write results back to state

The orchestrator calls only `execute(state, db)`.
"""
import json
import logging

from sqlalchemy.orm import Session

from app.agents.validation.final_validator import run_full_validation
from app.agents.validation.schema import ValidationReport
from app.agents.supervisor.state import SupervisorState, WorkflowStatus
from app.rag.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)


def _serialize_report_to_markdown(report: ValidationReport) -> str:
    """Serialize a ValidationReport to markdown for frontend display."""
    lines = ["# Requirements Validation Report\n"]

    # Overall status
    status_emoji = {
        "pass": "PASS",
        "conditional": "CONDITIONAL",
        "fail": "FAIL",
        "pending": "PENDING",
    }
    status_display = status_emoji.get(report.overall_status, report.overall_status.upper())
    lines.append(f"**Validation Status:** {status_display}")
    lines.append(f"**Overall Score:** {report.overall_score:.1%}")
    lines.append("")

    # Recommendations
    if report.recommendations:
        lines.append("## Recommendations\n")
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # Issues by severity
    if report.issues:
        lines.append("## Issues Found\n")

        critical = [i for i in report.issues if i.severity.value == "critical"]
        high = [i for i in report.issues if i.severity.value == "high"]
        medium = [i for i in report.issues if i.severity.value == "medium"]
        low = [i for i in report.issues if i.severity.value == "low"]

        if critical:
            lines.append("### Critical Issues\n")
            for issue in critical:
                lines.append(f"- **[{issue.id}]** {issue.message}")
                if issue.recommendation:
                    lines.append(f"  - Recommendation: {issue.recommendation}")
            lines.append("")

        if high:
            lines.append("### High Priority Issues\n")
            for issue in high:
                lines.append(f"- **[{issue.id}]** {issue.message}")
                if issue.recommendation:
                    lines.append(f"  - Recommendation: {issue.recommendation}")
            lines.append("")

        if medium:
            lines.append("### Medium Priority Issues\n")
            for issue in medium:
                lines.append(f"- **[{issue.id}]** {issue.message}")
                if issue.recommendation:
                    lines.append(f"  - Recommendation: {issue.recommendation}")
            lines.append("")

        if low:
            lines.append("### Low Priority Issues\n")
            for issue in low:
                lines.append(f"- **[{issue.id}]** {issue.message}")
                if issue.recommendation:
                    lines.append(f"  - Recommendation: {issue.recommendation}")
            lines.append("")
    else:
        lines.append("## Issues Found\n")
        lines.append("No issues found. All validation checks passed.\n")

    # Summary tables
    lines.append("## Validation Summary\n")
    lines.append("| Check Type | Issues Found |")
    lines.append("|---|---|")
    lines.append(f"| Rule-based | {report.rule_check_summary.get('issues_found', 0)} |")
    lines.append(f"| Semantic (LLM) | {report.llm_check_summary.get('issues_found', 0)} |")
    lines.append(f"| Duplicate Detection | {report.duplicate_summary.get('issues_found', 0)} |")
    lines.append(f"| Traceability | {report.traceability_summary.get('issues_found', 0)} |")
    lines.append("")

    return "\n".join(lines)


def execute(state: SupervisorState, db: Session) -> SupervisorState:
    """
    Execute the Validation Agent for the given state.

    This is the single public entrypoint. The orchestrator calls only this function.

    Args:
        state: SupervisorState with retrieved_context and requirements.
        db: SQLAlchemy session for database access.

    Returns:
        Updated SupervisorState with validation results.
    """
    state.workflow_status = WorkflowStatus.VALIDATING

    # 1. Extract requirements from state
    requirements = state.requirements or []

    # If no structured requirements, try to extract from context via RAG
    if not requirements and state.retrieved_context:
        # Use retrieved context as the basis for validation
        logger.info("No structured requirements in state, validating from context")
        # Create a synthetic requirement from context for validation
        requirements = [{
            "id": "CTX-001",
            "title": "Context-based Requirement",
            "description": state.retrieved_context[:1000],
            "priority": "MEDIUM",
            "acceptance_criteria": [],
            "source_citations": [],
        }]
    elif not requirements:
        # No context either — retrieve it
        retriever = HybridRetriever(db)
        try:
            search_response = retriever.retrieve(
                project_id=state.project_id,
                query=state.user_query,
                top_k=10,
                document_ids=state.document_ids,
            )
            state.retrieved_context = search_response.context
            state.citations = search_response.citations

            if search_response.context:
                requirements = [{
                    "id": "CTX-001",
                    "title": "Context-based Requirement",
                    "description": search_response.context[:1000],
                    "priority": "MEDIUM",
                    "acceptance_criteria": [],
                    "source_citations": [],
                }]
        except Exception as e:
            logger.error(f"RAG retrieval for validation failed: {e}")

    # 2. Run full validation
    report = run_full_validation(
        requirements=requirements,
        context=state.retrieved_context,
        citations=state.citations,
        include_llm_checks=True,
    )

    # 3. Serialize to markdown
    content = _serialize_report_to_markdown(report)

    # 4. Write results back to state
    state.generated_output = content
    state.validation_result = report.model_dump()
    state.validation_score = report.overall_score
    state.metadata["validation_type"] = "requirement_validation"
    state.metadata["validation_status"] = report.overall_status
    state.metadata["validation_issues_count"] = len(report.issues)
    state.workflow_status = WorkflowStatus.COMPLETED

    logger.info(
        f"Validation Agent completed: status={report.overall_status}, "
        f"score={report.overall_score:.3f}, issues={len(report.issues)}"
    )
    return state
