"""
Final Validator.

Merges results from all validators (rule, LLM, duplicate, traceability)
into a single ValidationReport with an overall score and status.
"""
import logging
from typing import Any

from app.agents.validation.duplicate_detector import detect_duplicates
from app.agents.validation.llm_validator import validate_with_llm
from app.agents.validation.rule_validator import validate_rules
from app.agents.validation.schema import (
    Severity,
    ValidationIssue,
    ValidationReport,
)
from app.agents.validation.traceability_checker import check_traceability

logger = logging.getLogger(__name__)

# Weight for each check type in the overall score
_CHECK_WEIGHTS = {
    "rule": 0.35,
    "llm": 0.30,
    "duplicate": 0.20,
    "traceability": 0.15,
}

# Severity to penalty mapping
_SEVERITY_PENALTIES = {
    Severity.CRITICAL: 0.25,
    Severity.HIGH: 0.15,
    Severity.MEDIUM: 0.08,
    Severity.LOW: 0.03,
    Severity.INFO: 0.01,
}


def _compute_score(
    rule_summary: dict,
    llm_summary: dict,
    duplicate_summary: dict,
    traceability_summary: dict,
) -> float:
    """
    Compute overall validation score from summaries.

    Score starts at 1.0 and deductions are made based on issues found.
    """
    score = 1.0

    # Rule check deductions
    rule_issues = rule_summary.get("issues_found", 0)
    rule_total = rule_summary.get("total_requirements", 1)
    if rule_total > 0:
        rule_penalty = min(1.0, rule_issues / max(rule_total, 1))
        score -= rule_penalty * _CHECK_WEIGHTS["rule"]

    # LLM check deductions
    llm_issues = llm_summary.get("issues_found", 0)
    llm_total = llm_summary.get("total_requirements", 1)
    if llm_total > 0 and not llm_summary.get("skipped", False):
        llm_penalty = min(1.0, llm_issues / max(llm_total, 1))
        score -= llm_penalty * _CHECK_WEIGHTS["llm"]

    # Duplicate check deductions
    dup_pairs = duplicate_summary.get("duplicate_pairs_found", 0)
    dup_total = duplicate_summary.get("total_requirements", 1)
    if dup_total > 0:
        dup_penalty = min(1.0, dup_pairs / max(dup_total, 1))
        score -= dup_penalty * _CHECK_WEIGHTS["duplicate"]

    # Traceability deductions
    trace_total = traceability_summary.get("total_requirements", 1)
    trace_without = traceability_summary.get("without_citations", 0)
    if trace_total > 0:
        trace_penalty = trace_without / trace_total
        score -= trace_penalty * _CHECK_WEIGHTS["traceability"]

    return max(0.0, min(1.0, score))


def _determine_status(score: float, issues: list[ValidationIssue]) -> str:
    """Determine overall status based on score and critical issues."""
    critical_count = sum(1 for i in issues if i.severity == Severity.CRITICAL)
    high_count = sum(1 for i in issues if i.severity == Severity.HIGH)

    if critical_count > 0 or score < 0.5:
        return "fail"
    if high_count > 2 or score < 0.7:
        return "conditional"
    return "pass"


def run_full_validation(
    requirements: list[dict[str, Any]],
    context: str | None = None,
    citations: list[Any] = None,
    include_llm_checks: bool = True,
) -> ValidationReport:
    """
    Run all validators and merge into a single report.

    Args:
        requirements: List of requirement dicts from state.
        context: Retrieved context for LLM validation.
        citations: Citations from retrieval.
        include_llm_checks: Whether to run LLM-based checks.

    Returns:
        Merged ValidationReport.
    """
    all_issues: list[ValidationIssue] = []

    # 1. Rule-based checks
    rule_issues, rule_summary = validate_rules(requirements)
    all_issues.extend(rule_issues)

    # 2. LLM-based checks
    if include_llm_checks:
        llm_issues, llm_summary = validate_with_llm(requirements, context)
        all_issues.extend(llm_issues)
    else:
        llm_summary = {"total_requirements": len(requirements), "issues_found": 0, "skipped": True}

    # 3. Duplicate detection
    dup_issues, dup_summary = detect_duplicates(requirements)
    all_issues.extend(dup_issues)

    # 4. Traceability check
    trace_issues, trace_summary = check_traceability(requirements, citations)
    all_issues.extend(trace_issues)

    # 5. Compute overall score and status
    score = _compute_score(rule_summary, llm_summary, dup_summary, trace_summary)
    status = _determine_status(score, all_issues)

    # 6. Build recommendations
    recommendations = []
    if rule_summary.get("critical_count", 0) > 0:
        recommendations.append("Fix critical rule violations before proceeding")
    if rule_summary.get("duplicate_ids", 0) > 0:
        recommendations.append("Resolve duplicate requirement IDs")
    if dup_summary.get("duplicate_pairs_found", 0) > 0:
        recommendations.append("Review potential semantic duplicates")
    if trace_summary.get("without_citations", 0) > 0:
        recommendations.append("Add source citations to improve traceability")
    if not recommendations:
        recommendations.append("Requirements pass all validation checks")

    report = ValidationReport(
        overall_status=status,
        overall_score=round(score, 3),
        issues=all_issues,
        rule_check_summary=rule_summary,
        llm_check_summary=llm_summary,
        duplicate_summary=dup_summary,
        traceability_summary=trace_summary,
        recommendations=recommendations,
    )

    logger.info(
        f"Full validation complete: status={status}, score={score:.3f}, "
        f"issues={len(all_issues)}"
    )
    return report
