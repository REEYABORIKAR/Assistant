"""
Rule-based Validator.

Performs deterministic, no-LLM validation checks on requirements:
- Requirement has a unique ID
- Requirement has a non-empty description
- Requirement has a priority
- Requirement has at least one acceptance criterion
- No duplicate requirement IDs
- No empty required fields
- Acceptance criteria follow given/when/then structure
"""
import logging
from typing import Any

from app.agents.validation.schema import Severity, ValidationIssue

logger = logging.getLogger(__name__)


def validate_rules(requirements: list[dict[str, Any]]) -> tuple[list[ValidationIssue], dict[str, Any]]:
    """
    Run all deterministic rule checks on a list of requirements.

    Args:
        requirements: List of requirement dicts (from state.requirements).

    Returns:
        Tuple of (list of issues, summary dict).
    """
    issues: list[ValidationIssue] = []
    issue_counter = 0

    def _next_id() -> str:
        nonlocal issue_counter
        issue_counter += 1
        return f"RV-{issue_counter:03d}"

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    for req in requirements:
        req_id = req.get("id", "")

        # Check: unique ID
        if not req_id:
            issues.append(ValidationIssue(
                id=_next_id(),
                check_type="rule",
                severity=Severity.CRITICAL,
                category="uniqueness",
                message="Requirement is missing an ID",
                recommendation="Add a unique identifier (e.g., FR-001)",
            ))
        elif req_id in seen_ids:
            if req_id not in duplicate_ids:
                duplicate_ids.add(req_id)
                issues.append(ValidationIssue(
                    id=_next_id(),
                    requirement_id=req_id,
                    check_type="rule",
                    severity=Severity.CRITICAL,
                    category="uniqueness",
                    message=f"Duplicate requirement ID: {req_id}",
                    recommendation=f"Assign a unique ID to replace '{req_id}'",
                ))
        else:
            seen_ids.add(req_id)

        # Check: non-empty description
        description = req.get("description", "")
        if not description or not str(description).strip():
            issues.append(ValidationIssue(
                id=_next_id(),
                requirement_id=req_id or None,
                check_type="rule",
                severity=Severity.HIGH,
                category="completeness",
                message=f"Requirement {req_id or '(no ID)'} has no description",
                recommendation="Add a clear, detailed description",
            ))

        # Check: has priority
        priority = req.get("priority", "")
        if not priority:
            issues.append(ValidationIssue(
                id=_next_id(),
                requirement_id=req_id or None,
                check_type="rule",
                severity=Severity.MEDIUM,
                category="completeness",
                message=f"Requirement {req_id or '(no ID)'} has no priority assigned",
                recommendation="Assign a priority level (HIGH, MEDIUM, LOW)",
            ))

        # Check: has at least one acceptance criterion
        ac_list = req.get("acceptance_criteria", [])
        if not ac_list:
            issues.append(ValidationIssue(
                id=_next_id(),
                requirement_id=req_id or None,
                check_type="rule",
                severity=Severity.MEDIUM,
                category="completeness",
                message=f"Requirement {req_id or '(no ID)'} has no acceptance criteria",
                recommendation="Add at least one acceptance criterion",
            ))
        else:
            # Check: acceptance criteria follow given/when/then
            for ac in ac_list:
                if isinstance(ac, dict):
                    has_given = bool(ac.get("given", "").strip())
                    has_when = bool(ac.get("when", "").strip())
                    has_then = bool(ac.get("then", "").strip())
                    if not (has_given and has_when and has_then):
                        ac_id = ac.get("id", "unknown")
                        missing = []
                        if not has_given:
                            missing.append("given")
                        if not has_when:
                            missing.append("when")
                        if not has_then:
                            missing.append("then")
                        issues.append(ValidationIssue(
                            id=_next_id(),
                            requirement_id=req_id or None,
                            check_type="rule",
                            severity=Severity.LOW,
                            category="format",
                            message=f"Acceptance criterion {ac_id} is missing: {', '.join(missing)}",
                            recommendation="Complete the Given/When/Then structure",
                        ))

    # Build summary
    summary = {
        "total_requirements": len(requirements),
        "unique_ids_found": len(seen_ids),
        "duplicate_ids": len(duplicate_ids),
        "issues_found": len(issues),
        "critical_count": sum(1 for i in issues if i.severity == Severity.CRITICAL),
        "high_count": sum(1 for i in issues if i.severity == Severity.HIGH),
        "medium_count": sum(1 for i in issues if i.severity == Severity.MEDIUM),
        "low_count": sum(1 for i in issues if i.severity == Severity.LOW),
    }

    logger.info(f"Rule validation: {len(issues)} issues in {len(requirements)} requirements")
    return issues, summary
