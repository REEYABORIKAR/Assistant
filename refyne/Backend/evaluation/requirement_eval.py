"""
Requirement Quality Evaluation Module.

Regression tests for the Validation Agent's deterministic rule checks.
Runs known-bad samples through the validator and confirms each is caught.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.validation.rule_validator import validate_rules
from app.agents.validation.schema import Severity


def load_samples(dataset_path: str) -> list[dict]:
    """Load requirement samples from JSON dataset."""
    with open(dataset_path) as f:
        return json.load(f)


def evaluate_sample(sample: dict) -> dict:
    """
    Run rule validation on a single sample and check if expected issues are caught.

    Returns dict with sample_id, passed (bool), caught_issues, missed_issues.
    """
    requirements = sample.get("requirements", [])
    sample_id = sample.get("id", "unknown")
    expected_issues = sample.get("expected_issues", [])
    expected_rule = sample.get("expected_rule")

    # Determine if this is a valid or invalid sample
    is_valid = not expected_issues and expected_rule is None

    issues, summary = validate_rules(requirements)

    # Map detected issues to rule categories
    detected_rules = set()
    for issue in issues:
        msg_lower = issue.message.lower()
        if "missing" in msg_lower and "id" in msg_lower:
            detected_rules.add("missing_id")
        elif "duplicate" in msg_lower:
            detected_rules.add("duplicate_id")
        elif "no description" in msg_lower or "empty description" in msg_lower or "missing a description" in msg_lower:
            detected_rules.add("empty_description")
        elif "no priority" in msg_lower or "missing priority" in msg_lower or "missing a priority" in msg_lower:
            detected_rules.add("missing_priority")
        elif "no acceptance criteria" in msg_lower or "missing acceptance criteria" in msg_lower or "missing acceptance" in msg_lower:
            detected_rules.add("missing_acceptance_criteria")
        elif "missing" in msg_lower and ("given" in msg_lower or "when" in msg_lower or "then" in msg_lower):
            detected_rules.add("incomplete_acceptance_criterion")

    # For valid samples, no critical/high issues should be detected
    if is_valid:
        critical_issues = [i for i in issues if i.severity == Severity.CRITICAL]
        high_issues = [i for i in issues if i.severity == Severity.HIGH]
        passed = len(critical_issues) == 0 and len(high_issues) == 0
        return {
            "sample_id": sample_id,
            "description": sample.get("description", ""),
            "passed": passed,
            "expected_issues": [],
            "detected_issues": [i.message for i in issues],
            "caught": [],
            "missed": [],
            "is_valid_sample": True,
        }

    # For invalid samples, check which expected issues were caught
    expected_set = set(expected_issues)
    caught = expected_set & detected_rules
    missed = expected_set - detected_rules
    passed = len(missed) == 0

    return {
        "sample_id": sample_id,
        "description": sample.get("description", ""),
        "passed": passed,
        "expected_issues": list(expected_set),
        "detected_issues": [i.message for i in issues],
        "caught": list(caught),
        "missed": list(missed),
        "is_valid_sample": False,
    }


def run_requirement_eval(
    dataset_path: str | None = None,
) -> dict:
    """
    Run requirement quality evaluation over the sample dataset.

    Returns dict with per_sample results and aggregate stats.
    """
    if dataset_path is None:
        dataset_path = str(Path(__file__).resolve().parent / "datasets" / "requirements_samples.json")

    samples = load_samples(dataset_path)
    results = []

    for sample in samples:
        result = evaluate_sample(sample)
        results.append(result)

    n = len(results)
    passed = sum(1 for r in results if r["passed"])

    # Separate valid and invalid samples
    valid_samples = [r for r in results if r.get("is_valid_sample", False)]
    invalid_samples = [r for r in results if not r.get("is_valid_sample", False)]

    valid_passed = sum(1 for r in valid_samples if r["passed"])
    invalid_passed = sum(1 for r in invalid_samples if r["passed"])

    agg = {
        "total_samples": n,
        "passed": passed,
        "failed": n - passed,
        "pass_rate": passed / n if n > 0 else 0.0,
        "valid_samples": len(valid_samples),
        "valid_passed": valid_passed,
        "invalid_samples": len(invalid_samples),
        "invalid_caught": invalid_passed,
    }

    return {"per_sample": results, "aggregate": agg}


def print_requirement_report(eval_results: dict) -> str:
    """Format requirement evaluation results as a readable string."""
    agg = eval_results["aggregate"]
    lines = [
        "Requirement Quality (Validation Agent regression)",
        f"  {agg['passed']}/{agg['total_samples']} samples passed",
        f"  Valid samples correctly passed: {agg['valid_passed']}/{agg['valid_samples']}",
        f"  Invalid samples correctly caught: {agg['invalid_caught']}/{agg['invalid_samples']}",
    ]

    # List failures
    for r in eval_results.get("per_sample", []):
        if not r["passed"]:
            if r.get("is_valid_sample"):
                lines.append(f"  FAIL: {r['sample_id']} - Valid sample was incorrectly flagged")
            else:
                lines.append(f"  FAIL: {r['sample_id']} - Expected {r['missed']} but not detected")
                lines.append(f"    Description: {r['description']}")

    return "\n".join(lines)
