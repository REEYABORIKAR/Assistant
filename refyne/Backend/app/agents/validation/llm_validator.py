"""
LLM-based Validator.

Uses LLM to perform semantic validation checks:
- Ambiguity detection
- Completeness assessment
- Contradictions between requirements
- Missing assumptions or unclear actors
- Missing edge cases
- Inconsistent terminology
"""
import json
import logging
import re
from typing import Any

from app.agents.validation.schema import Severity, ValidationIssue
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)

_VALIDATION_PROMPT = """Analyze the following requirements for quality issues. Check for:
1. Ambiguity - vague or unclear language
2. Completeness - missing information
3. Contradictions - conflicting requirements
4. Unclear actors - missing or ambiguous stakeholder references
5. Missing edge cases - unhandled scenarios
6. Inconsistent terminology - different terms for the same concept

Return a JSON array of issues found. Each issue object must have:
- requirement_id: the ID of the problematic requirement (or "GLOBAL" for cross-cutting issues)
- severity: "critical", "high", "medium", or "low"
- category: "ambiguity", "completeness", "contradiction", "actor", "edge_case", "terminology"
- message: human-readable description of the issue
- recommendation: suggested fix

If no issues are found, return an empty array [].
Return ONLY the JSON array, no other text."""


def _parse_llm_issues_json(raw: str) -> list[dict]:
    """Parse LLM JSON output into issue dicts."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    array_match = re.search(r"\[.*\]", text, re.DOTALL)
    if array_match:
        text = array_match.group(0)

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM validation JSON: {text[:200]}")
    return []


def validate_with_llm(
    requirements: list[dict[str, Any]],
    context: str | None = None,
) -> tuple[list[ValidationIssue], dict[str, Any]]:
    """
    Run LLM-based semantic validation on requirements.

    Args:
        requirements: List of requirement dicts.
        context: Optional retrieved context for additional grounding.

    Returns:
        Tuple of (list of issues, summary dict).
    """
    if not requirements:
        return [], {"total_requirements": 0, "issues_found": 0, "skipped": True}

    # Build a requirements text for the LLM
    req_text_parts = []
    for req in requirements:
        req_id = req.get("id", "N/A")
        title = req.get("title", "N/A")
        desc = req.get("description", "N/A")
        priority = req.get("priority", "N/A")
        req_text_parts.append(f"[{req_id}] {title} (Priority: {priority})\n{desc}")
    req_text = "\n\n".join(req_text_parts)

    if context:
        full_prompt = f"{_VALIDATION_PROMPT}\n\nContext from documents:\n{context[:2000]}\n\nRequirements:\n{req_text}"
    else:
        full_prompt = f"{_VALIDATION_PROMPT}\n\nRequirements:\n{req_text}"

    generation = generate_answer(
        query=full_prompt,
        context=context or "",
        citations=[],
    )

    if not generation["configured"] or not generation["answer"]:
        logger.info("LLM not configured, skipping semantic validation")
        return [], {"total_requirements": len(requirements), "issues_found": 0, "skipped": True}

    raw_issues = _parse_llm_issues_json(generation["answer"])

    issues = []
    for i, raw in enumerate(raw_issues):
        severity_str = raw.get("severity", "medium").upper()
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.MEDIUM

        issues.append(ValidationIssue(
            id=f"LV-{i + 1:03d}",
            requirement_id=raw.get("requirement_id"),
            check_type="llm",
            severity=severity,
            category=raw.get("category", "general"),
            message=raw.get("message", ""),
            recommendation=raw.get("recommendation", ""),
        ))

    summary = {
        "total_requirements": len(requirements),
        "issues_found": len(issues),
        "critical_count": sum(1 for i in issues if i.severity == Severity.CRITICAL),
        "high_count": sum(1 for i in issues if i.severity == Severity.HIGH),
        "medium_count": sum(1 for i in issues if i.severity == Severity.MEDIUM),
        "low_count": sum(1 for i in issues if i.severity == Severity.LOW),
    }

    logger.info(f"LLM validation: {len(issues)} semantic issues found")
    return issues, summary
