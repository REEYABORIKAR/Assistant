"""
Unit Tests for Requirement Agent.

Tests the agent's execute() function in isolation with mocked retrieval/LLM calls.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock

from app.agents.supervisor.state import Intent, Route, WorkflowStatus, SupervisorState
from app.agents.requirement.agent import execute
from app.agents.requirement.analyzer import build_generation_plan, resolve_action, INTENT_TO_ACTION
from app.agents.requirement.generator import (
    generate_requirements,
    _normalize_requirement,
    _parse_requirements_json,
)
from app.agents.requirement.serializer import (
    serialize_requirement,
    serialize_requirements_list,
    serialize_user_story,
    serialize_brd,
    serialize_srs,
    serialize_rtm,
)
from app.agents.requirement.schema import (
    AcceptanceCriterion,
    BRDDocument,
    Priority,
    Requirement,
    SRSDocument,
    RTMDocument,
    UserStory,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_state(intent, route, query="test query", action=None):
    return SupervisorState(
        user_id="u1",
        project_id="p1",
        session_id=str(uuid.uuid4()),
        user_query=query,
        intent=intent,
        route=route,
        requires_rag=True,
        action=action,
    )

def _mock_search_response(context="Test context from documents", citations=None):
    resp = MagicMock()
    resp.context = context
    resp.citations = citations or []
    return resp

def _mock_generation(answer="Generated answer", configured=True, message=""):
    return {"answer": answer, "configured": configured, "message": message}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Schema Models
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemaModels:
    """Test that schema models work correctly."""

    def test_requirement_creation(self):
        req = Requirement(
            id="FR-001",
            title="Login Feature",
            description="Users should be able to log in",
            priority=Priority.HIGH,
            actor="User",
        )
        assert req.id == "FR-001"
        assert req.priority == Priority.HIGH

    def test_acceptance_criterion_creation(self):
        ac = AcceptanceCriterion(
            id="AC-001",
            given="A user is on the login page",
            when="They enter valid credentials",
            then="They are redirected to the dashboard",
        )
        assert ac.given == "A user is on the login page"
        assert ac.when == "They enter valid credentials"
        assert ac.then == "They are redirected to the dashboard"

    def test_user_story_creation(self):
        story = UserStory(
            id="US-001",
            title="Login",
            role="User",
            feature="log in to the system",
            benefit="access my account",
            priority=Priority.HIGH,
            story_points=5,
        )
        assert story.story_points == 5

    def test_brd_document_creation(self):
        brd = BRDDocument(title="Test BRD")
        assert brd.title == "Test BRD"
        assert brd.business_requirements == []


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Analyzer
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyzer:
    """Test the analyzer module."""

    def test_resolve_action_explicit(self):
        state = _make_state(Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT, action="srs")
        assert resolve_action(state) == "srs"

    def test_resolve_action_from_intent(self):
        state = _make_state(Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT)
        assert resolve_action(state) == "brd"

    def test_resolve_action_fallback(self):
        state = _make_state(Intent.UNKNOWN, Route.UNKNOWN)
        assert resolve_action(state) == "brd"

    def test_intent_to_action_mapping(self):
        assert INTENT_TO_ACTION[Intent.BRD_GENERATION] == "brd"
        assert INTENT_TO_ACTION[Intent.SRS_GENERATION] == "srs"
        assert INTENT_TO_ACTION[Intent.RTM_GENERATION] == "rtm"
        assert INTENT_TO_ACTION[Intent.USER_STORY_GENERATION] == "user_stories"
        assert INTENT_TO_ACTION[Intent.ACCEPTANCE_CRITERIA_GENERATION] == "acceptance_criteria"

    def test_build_generation_plan(self):
        state = _make_state(Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT)
        plan = build_generation_plan(state)
        assert plan is not None
        assert plan.action == "brd"
        assert plan.output_type == "brd"

    def test_build_generation_plan_user_stories(self):
        state = _make_state(Intent.USER_STORY_GENERATION, Route.REQUIREMENT_AGENT)
        plan = build_generation_plan(state)
        assert plan.output_type == "user_stories"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Generator JSON Parsing
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeneratorParsing:
    """Test JSON parsing in the generator."""

    def test_parse_valid_json_array(self):
        raw = '[{"id": "FR-001", "title": "Test", "description": "Desc"}]'
        result = _parse_requirements_json(raw)
        assert len(result) == 1
        assert result[0]["id"] == "FR-001"

    def test_parse_json_with_code_fences(self):
        raw = '```json\n[{"id": "FR-001", "title": "Test"}]\n```'
        result = _parse_requirements_json(raw)
        assert len(result) == 1

    def test_parse_wrapped_json(self):
        raw = '{"requirements": [{"id": "FR-001"}]}'
        result = _parse_requirements_json(raw)
        assert len(result) == 1

    def test_parse_invalid_json(self):
        raw = "not valid json"
        result = _parse_requirements_json(raw)
        assert result == []

    def test_normalize_requirement(self):
        raw = {
            "id": "FR-001",
            "title": "Login",
            "description": "User login",
            "priority": "HIGH",
            "actor": "User",
            "preconditions": ["Account exists"],
            "acceptance_criteria": [
                {"id": "AC-001", "given": "On login page", "when": "Enter creds", "then": "Logged in"}
            ],
        }
        req = _normalize_requirement(raw, 0)
        assert req.id == "FR-001"
        assert req.priority == Priority.HIGH
        assert len(req.acceptance_criteria) == 1

    def test_normalize_requirement_defaults(self):
        raw = {"description": "Just a description"}
        req = _normalize_requirement(raw, 0)
        assert req.id == "FR-001"
        assert req.priority == Priority.MEDIUM


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Serializer
# ═══════════════════════════════════════════════════════════════════════════════

class TestSerializer:
    """Test markdown serialization."""

    def test_serialize_requirement(self):
        req = Requirement(
            id="FR-001", title="Login", description="User login",
            priority=Priority.HIGH, actor="User",
            acceptance_criteria=[
                AcceptanceCriterion(id="AC-001", given="On page", when="Click", then="Done"),
            ],
        )
        md = serialize_requirement(req)
        assert "FR-001" in md
        assert "Login" in md
        assert "HIGH" in md
        assert "Given" in md

    def test_serialize_requirements_list_empty(self):
        md = serialize_requirements_list([])
        assert "No requirements generated" in md

    def test_serialize_user_story(self):
        story = UserStory(
            id="US-001", title="Login", role="User",
            feature="log in", benefit="access account",
            priority=Priority.HIGH, story_points=5,
        )
        md = serialize_user_story(story)
        assert "US-001" in md
        assert "As a **User**" in md

    def test_serialize_brd(self):
        brd = BRDDocument(
            title="Test BRD",
            executive_summary="Summary text",
            business_objectives=["Obj 1", "Obj 2"],
        )
        md = serialize_brd(brd)
        assert "Test BRD" in md
        assert "Executive Summary" in md
        assert "Obj 1" in md

    def test_serialize_rtm(self):
        rtm = RTMDocument(rows=[
            {"requirement_id": "FR-001", "description": "Desc", "source": "Doc", "priority": "HIGH", "test_case": "TC-1", "status": "Pass"},
        ])
        md = serialize_rtm(rtm)
        assert "FR-001" in md
        assert "Traceability Matrix" in md


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Requirement Agent execute()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequirementAgentExecute:
    """Test the requirement agent's execute() function."""

    @patch("app.agents.requirement.brd_generator.generate_answer")
    @patch("app.agents.requirement.agent.HybridRetriever")
    def test_execute_brd_generation(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Payment documentation",
            citations=[],
        )
        mock_gen.return_value = _mock_generation(
            answer='{"executive_summary": "Summary", "business_objectives": ["Obj 1"], "scope": "Scope", "stakeholders": ["User"], "business_requirements": [{"id": "FR-001", "title": "Payment", "description": "Process payments", "priority": "HIGH"}], "functional_requirements": [], "non_functional_requirements": [], "assumptions_and_constraints": [], "success_criteria": []}'
        )

        state = _make_state(Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT)
        db = MagicMock()
        result = execute(state, db)

        assert result.workflow_status == WorkflowStatus.COMPLETED
        assert result.generated_output is not None
        assert len(result.requirements) > 0
        assert result.metadata["document_action"] == "brd"

    @patch("app.agents.requirement.user_story_generator.generate_answer")
    @patch("app.agents.requirement.agent.HybridRetriever")
    def test_execute_user_stories(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(context="Context")
        mock_gen.return_value = _mock_generation(
            answer='[{"id": "US-001", "title": "Login", "role": "User", "feature": "log in", "benefit": "access"}]'
        )

        state = _make_state(Intent.USER_STORY_GENERATION, Route.REQUIREMENT_AGENT)
        db = MagicMock()
        result = execute(state, db)

        assert result.workflow_status == WorkflowStatus.COMPLETED
        assert len(result.user_stories) > 0

    @patch("app.agents.requirement.agent.HybridRetriever")
    def test_execute_fallback_no_llm(self, MockRetriever):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(context="Some context")

        state = _make_state(Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT)
        db = MagicMock()
        result = execute(state, db)

        # Should use fallback content
        assert result.workflow_status == WorkflowStatus.COMPLETED
        assert result.generated_output is not None

    @patch("app.agents.requirement.agent.HybridRetriever")
    def test_execute_retrieval_failure(self, MockRetriever):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.side_effect = Exception("Retrieval failed")

        state = _make_state(Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT)
        db = MagicMock()
        result = execute(state, db)

        assert result.workflow_status == WorkflowStatus.FAILED
        assert "Retrieval failed" in result.error


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Empty/Missing Context Handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmptyContext:
    """Test behavior with empty or missing context."""

    @patch("app.agents.requirement.agent.HybridRetriever")
    @patch("app.agents.requirement.agent.generate_answer")
    def test_execute_empty_context(self, mock_gen, MockRetriever):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="", citations=[]
        )
        mock_gen.return_value = _mock_generation(
            answer='[{"id": "FR-001", "title": "Fallback", "description": "Generated from empty context"}]'
        )

        state = _make_state(Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT)
        db = MagicMock()
        result = execute(state, db)

        # Should still complete (flagged: fail-open behavior)
        assert result.workflow_status == WorkflowStatus.COMPLETED
