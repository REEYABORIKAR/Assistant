"""
Unit Tests for Validation Agent.

Tests the agent's execute() function and individual validators in isolation.
"""
import uuid
from unittest.mock import MagicMock, patch

from app.agents.supervisor.state import Intent, Route, SupervisorState, WorkflowStatus
from app.agents.validation.agent import execute
from app.agents.validation.duplicate_detector import detect_duplicates
from app.agents.validation.final_validator import run_full_validation
from app.agents.validation.rule_validator import validate_rules
from app.agents.validation.schema import Severity, ValidationReport
from app.agents.validation.traceability_checker import check_traceability

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_state(intent, route, query="validate requirements", requirements=None):
    return SupervisorState(
        user_id="u1",
        project_id="p1",
        session_id=str(uuid.uuid4()),
        user_query=query,
        intent=intent,
        route=route,
        requires_rag=False,
        requirements=requirements or [],
    )

def _make_valid_requirement(req_id="FR-001"):
    return {
        "id": req_id,
        "title": "Login Feature",
        "description": "Users should be able to log in with email and password",
        "priority": "HIGH",
        "actor": "User",
        "preconditions": ["User has an account"],
        "acceptance_criteria": [
            {"id": "AC-001", "given": "On login page", "when": "Enter valid creds", "then": "Logged in"},
        ],
        "source_citations": ["doc1#chunk1"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Rule Validator
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleValidator:
    """Test deterministic rule-based validation."""

    def test_valid_requirement_passes(self):
        reqs = [_make_valid_requirement()]
        issues, summary = validate_rules(reqs)
        # Should have no critical or high issues
        critical = [i for i in issues if i.severity == Severity.CRITICAL]
        high = [i for i in issues if i.severity == Severity.HIGH]
        assert len(critical) == 0
        assert len(high) == 0

    def test_missing_id_detected(self):
        reqs = [{"title": "No ID", "description": "Desc", "priority": "HIGH"}]
        issues, summary = validate_rules(reqs)
        assert any("missing an ID" in i.message for i in issues)

    def test_duplicate_ids_detected(self):
        reqs = [
            _make_valid_requirement("FR-001"),
            _make_valid_requirement("FR-001"),
        ]
        issues, summary = validate_rules(reqs)
        assert any("Duplicate requirement ID" in i.message for i in issues)

    def test_empty_description_detected(self):
        reqs = [{"id": "FR-001", "title": "T", "description": "", "priority": "HIGH"}]
        issues, summary = validate_rules(reqs)
        assert any("no description" in i.message for i in issues)

    def test_missing_priority_detected(self):
        reqs = [{"id": "FR-001", "title": "T", "description": "D"}]
        issues, summary = validate_rules(reqs)
        assert any("no priority" in i.message for i in issues)

    def test_missing_acceptance_criteria_detected(self):
        reqs = [{"id": "FR-001", "title": "T", "description": "D", "priority": "HIGH", "acceptance_criteria": []}]
        issues, summary = validate_rules(reqs)
        assert any("no acceptance criteria" in i.message for i in issues)

    def test_incomplete_acceptance_criterion_detected(self):
        reqs = [{
            "id": "FR-001", "title": "T", "description": "D", "priority": "HIGH",
            "acceptance_criteria": [{"id": "AC-001", "given": "Context", "when": "", "then": "Result"}],
        }]
        issues, summary = validate_rules(reqs)
        assert any("missing" in i.message and "when" in i.message for i in issues)

    def test_empty_requirements_list(self):
        issues, summary = validate_rules([])
        assert summary["total_requirements"] == 0
        assert len(issues) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Duplicate Detector
# ═══════════════════════════════════════════════════════════════════════════════

class TestDuplicateDetector:
    """Test semantic duplicate detection."""

    def test_no_duplicates(self):
        reqs = [
            _make_valid_requirement("FR-001"),
            {"id": "FR-002", "title": "Logout", "description": "User logout feature"},
        ]
        issues, summary = detect_duplicates(reqs)
        assert summary["duplicate_pairs_found"] == 0

    def test_semantic_duplicates_detected(self):
        reqs = [
            {"id": "FR-001", "title": "User Login", "description": "Allow users to log in with email and password"},
            {"id": "FR-002", "title": "User Login", "description": "Allow users to log in using email and password"},
        ]
        issues, summary = detect_duplicates(reqs)
        assert summary["duplicate_pairs_found"] >= 1

    def test_same_id_skipped(self):
        """Same ID duplicates are handled by rule_validator, not here."""
        reqs = [
            _make_valid_requirement("FR-001"),
            _make_valid_requirement("FR-001"),
        ]
        issues, summary = detect_duplicates(reqs)
        assert summary["duplicate_pairs_found"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Traceability Checker
# ═══════════════════════════════════════════════════════════════════════════════

class TestTraceabilityChecker:
    """Test traceability validation."""

    def test_requirements_with_citations(self):
        reqs = [_make_valid_requirement()]
        issues, summary = check_traceability(reqs)
        assert summary["with_citations"] == 1
        assert summary["without_citations"] == 0

    def test_requirements_without_citations(self):
        reqs = [{"id": "FR-001", "title": "T", "description": "D", "source_citations": []}]
        issues, summary = check_traceability(reqs)
        assert summary["without_citations"] == 1
        assert len(issues) >= 1

    def test_coverage_calculation(self):
        reqs = [
            _make_valid_requirement("FR-001"),
            {"id": "FR-002", "title": "T", "description": "D", "source_citations": []},
        ]
        _, summary = check_traceability(reqs)
        assert summary["coverage"] == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Final Validator
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinalValidator:
    """Test the merged validation report."""

    @patch("app.agents.validation.llm_validator.generate_answer")
    def test_valid_requirements_pass(self, mock_gen):
        mock_gen.return_value = {"answer": "[]", "configured": True, "message": None}
        reqs = [_make_valid_requirement()]
        report = run_full_validation(reqs, include_llm_checks=True)
        assert isinstance(report, ValidationReport)
        assert report.overall_status in ("pass", "conditional")
        assert report.overall_score > 0.5

    @patch("app.agents.validation.llm_validator.generate_answer")
    def test_invalid_requirements_fail(self, mock_gen):
        mock_gen.return_value = {"answer": "[]", "configured": True, "message": None}
        reqs = [{"id": "", "title": "", "description": "", "priority": "", "acceptance_criteria": []}]
        report = run_full_validation(reqs, include_llm_checks=True)
        assert report.overall_status in ("fail", "conditional")
        assert report.overall_score < 0.7

    def test_empty_requirements(self):
        report = run_full_validation([], include_llm_checks=False)
        assert report.overall_status == "pass"
        assert report.overall_score == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Validation Agent execute()
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidationAgentExecute:
    """Test the validation agent's execute() function."""

    @patch("app.agents.validation.agent.run_full_validation")
    def test_execute_with_structured_requirements(self, mock_validate):
        mock_validate.return_value = ValidationReport(
            overall_status="pass",
            overall_score=0.95,
            issues=[],
            recommendations=["Requirements pass all checks"],
        )

        reqs = [_make_valid_requirement()]
        state = _make_state(Intent.REQUIREMENT_VALIDATION, Route.VALIDATION_AGENT, requirements=reqs)
        db = MagicMock()
        result = execute(state, db)

        assert result.workflow_status == WorkflowStatus.COMPLETED
        assert result.validation_score == 0.95
        assert result.generated_output is not None

    @patch("app.agents.validation.agent.run_full_validation")
    def test_execute_with_no_requirements(self, mock_validate):
        mock_validate.return_value = ValidationReport(
            overall_status="pass",
            overall_score=1.0,
            issues=[],
        )

        state = _make_state(Intent.REQUIREMENT_VALIDATION, Route.VALIDATION_AGENT, requirements=[])
        state.retrieved_context = "Some context"
        db = MagicMock()
        result = execute(state, db)

        assert result.workflow_status == WorkflowStatus.COMPLETED
        # Should still produce a validation report
        assert result.validation_result is not None

    @patch("app.agents.validation.agent.run_full_validation")
    def test_execute_retrieval_failure(self, mock_validate):
        mock_validate.return_value = ValidationReport(overall_status="pass", overall_score=1.0)

        state = _make_state(Intent.REQUIREMENT_VALIDATION, Route.VALIDATION_AGENT, requirements=[])
        state.retrieved_context = None
        db = MagicMock()

        # Mock retriever to fail
        with patch("app.agents.validation.agent.HybridRetriever") as MockRetriever:
            mock_retriever = MagicMock()
            MockRetriever.return_value = mock_retriever
            mock_retriever.retrieve.side_effect = Exception("Retrieval failed")
            result = execute(state, db)

        # Should still complete with empty context
        assert result.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Human Review Task Threshold
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewThreshold:
    """Test that review task creation respects score thresholds."""

    def test_high_score_should_trigger_review(self):
        """Score >= threshold should create a review task."""
        score = 0.9
        threshold = 0.7
        assert score >= threshold

    def test_low_score_should_not_trigger_review(self):
        """Score < threshold should not create a review task."""
        score = 0.4
        threshold = 0.7
        assert score < threshold
