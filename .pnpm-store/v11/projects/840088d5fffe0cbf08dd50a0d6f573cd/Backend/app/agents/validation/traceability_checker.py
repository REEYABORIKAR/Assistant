"""
Traceability Checker.

Validates requirement traceability:
- Each requirement traces back to a source
- Citations are valid and non-empty
- No orphan requirements (no source reference)
"""
import logging
from typing import Any

from app.agents.validation.schema import Severity, ValidationIssue

logger = logging.getLogger(__name__)


def check_traceability(
    requirements: list[dict[str, Any]],
    citations: list[Any] = None,
) -> tuple[list[ValidationIssue], dict[str, Any]]:
    """
    Check traceability of requirements to sources.

    Args:
        requirements: List of requirement dicts.
        citations: List of citation objects from retrieval.

    Returns:
        Tuple of (list of issues, summary dict).
    """
    issues: list[ValidationIssue] = []
    issue_counter = 0

    def _next_id() -> str:
        nonlocal issue_counter
        issue_counter += 1
        return f"TC-{issue_counter:03d}"

    total_requirements = len(requirements)
    requirements_with_citations = 0
    requirements_without_citations = 0

    for req in requirements:
        req_id = req.get("id", "")
        source_citations = req.get("source_citations", [])

        if source_citations:
            requirements_with_citations += 1
        else:
            requirements_without_citations += 1
            issues.append(ValidationIssue(
                id=_next_id(),
                requirement_id=req_id or None,
                check_type="traceability",
                severity=Severity.MEDIUM,
                category="source_traceability",
                message=f"Requirement '{req_id or '(no ID)'}' has no source citations",
                recommendation="Add source references to trace requirements back to documents",
            ))

    # Check if there are any citations at all in the context
    has_context_citations = bool(citations)

    summary = {
        "total_requirements": total_requirements,
        "with_citations": requirements_with_citations,
        "without_citations": requirements_without_citations,
        "coverage": (
            requirements_with_citations / total_requirements
            if total_requirements > 0
            else 0.0
        ),
        "has_context_citations": has_context_citations,
        "issues_found": len(issues),
    }

    logger.info(
        f"Traceability check: {requirements_with_citations}/{total_requirements} "
        f"requirements have citations"
    )
    return issues, summary
