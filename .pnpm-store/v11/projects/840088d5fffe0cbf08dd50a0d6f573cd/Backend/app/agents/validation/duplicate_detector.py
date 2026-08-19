"""
Duplicate Detector.

Detects semantic duplicates among requirements:
- Exact ID matches (already handled by rule_validator)
- Semantic similarity between requirement descriptions
- Different IDs but same or very similar meaning
"""
import logging
from difflib import SequenceMatcher
from typing import Any

from app.agents.validation.schema import Severity, ValidationIssue

logger = logging.getLogger(__name__)

# Threshold for considering two requirements as semantic duplicates
_SIMILARITY_THRESHOLD = 0.85


def _text_similarity(a: str, b: str) -> float:
    """Compute text similarity ratio between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def detect_duplicates(requirements: list[dict[str, Any]]) -> tuple[list[ValidationIssue], dict[str, Any]]:
    """
    Detect duplicate requirements by semantic similarity.

    Args:
        requirements: List of requirement dicts.

    Returns:
        Tuple of (list of issues, summary dict).
    """
    issues: list[ValidationIssue] = []
    duplicates_found: list[tuple[str, str, float]] = []
    issue_counter = 0

    def _next_id() -> str:
        nonlocal issue_counter
        issue_counter += 1
        return f"DD-{issue_counter:03d}"

    # Compare each pair of requirements
    for i in range(len(requirements)):
        for j in range(i + 1, len(requirements)):
            req_a = requirements[i]
            req_b = requirements[j]

            id_a = req_a.get("id", "")
            id_b = req_b.get("id", "")

            # Skip if same ID (already caught by rule_validator)
            if id_a == id_b:
                continue

            desc_a = str(req_a.get("description", ""))
            title_a = str(req_a.get("title", ""))
            desc_b = str(req_b.get("description", ""))
            title_b = str(req_b.get("title", ""))

            # Check title similarity
            title_sim = _text_similarity(title_a, title_b)
            # Check description similarity
            desc_sim = _text_similarity(desc_a, desc_b)

            # Combined similarity (weighted average)
            combined_sim = (title_sim * 0.3) + (desc_sim * 0.7)

            if combined_sim >= _SIMILARITY_THRESHOLD:
                duplicates_found.append((id_a, id_b, combined_sim))
                issues.append(ValidationIssue(
                    id=_next_id(),
                    requirement_id=id_a,
                    check_type="duplicate",
                    severity=Severity.HIGH,
                    category="semantic_duplicate",
                    message=(
                        f"Requirements '{id_a}' and '{id_b}' are "
                        f"{combined_sim:.0%} similar and may be duplicates"
                    ),
                    recommendation=(
                        f"Review both requirements and merge or differentiate them. "
                        f"Title similarity: {title_sim:.0%}, "
                        f"description similarity: {desc_sim:.0%}"
                    ),
                ))

    summary = {
        "total_requirements": len(requirements),
        "duplicate_pairs_found": len(duplicates_found),
        "issues_found": len(issues),
    }

    logger.info(f"Duplicate detection: {len(duplicates_found)} potential duplicate pairs")
    return issues, summary
