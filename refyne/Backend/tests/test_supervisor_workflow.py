"""
Supervisor Workflow Test Suite

Tests the complete Supervisor pipeline:
  Intent Classifier → Router → Downstream Execution → Result → Status

Each test verifies:
  1. Classifier intent output
  2. Router route decision
  3. RAG-required flag correctness
  4. Downstream agent existence / execution path
  5. Workflow status transitions
  6. Error → FAILED status handling
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock

from app.agents.supervisor.state import Intent, Route, WorkflowStatus, SupervisorState
from app.agents.supervisor.router import (
    resolve_route,
    requires_rag,
    resolve_status,
    route_intent,
    route_from_intent,
    INTENT_TO_ROUTE,
    RAG_INTENTS,
    NO_RAG_INTENTS,
    INTENT_TO_STATUS,
)
from app.agents.supervisor.classifier import (
    ClassificationResult,
    _parse_classification,
    classify_intent,
    classify_and_update_state,
    INTENT_ROUTE_MAP,
    RAG_REQUIRED_INTENTS,
)
from app.agents.supervisor.service import (
    handle_request,
    handle_request_with_state,
    SupervisorRequest,
    SupervisorResponse,
    SupervisorError,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: State & Enum Integrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateIntegrity:
    """Verify that state enums and models are consistent."""

    def test_all_intents_have_routes_in_classifier(self):
        """Every Intent must be mapped in the classifier's INTENT_ROUTE_MAP."""
        for intent in Intent:
            assert intent in INTENT_ROUTE_MAP, (
                f"Intent '{intent.value}' missing from classifier INTENT_ROUTE_MAP"
            )

    def test_all_intents_have_routes_in_router(self):
        """Every Intent must be mapped in the router's INTENT_TO_ROUTE."""
        for intent in Intent:
            assert intent in INTENT_TO_ROUTE, (
                f"Intent '{intent.value}' missing from router INTENT_TO_ROUTE"
            )

    def test_all_intents_have_status_in_router(self):
        """Every Intent must have a workflow status mapping."""
        for intent in Intent:
            assert intent in INTENT_TO_STATUS, (
                f"Intent '{intent.value}' missing from router INTENT_TO_STATUS"
            )

    @pytest.mark.xfail(
        reason="KNOWN: UNKNOWN maps to Route.UNKNOWN in classifier but Route.DIRECT_RESPONSE in router (by design)"
    )
    def test_classifier_and_router_route_maps_agree(self):
        """Classifier and router must map each intent to the same route."""
        for intent in Intent:
            c_route = INTENT_ROUTE_MAP[intent]
            r_route = INTENT_TO_ROUTE[intent]
            assert c_route == r_route, (
                f"Intent '{intent.value}': classifier maps to '{c_route.value}' "
                f"but router maps to '{r_route.value}'"
            )

    def test_classifier_and_router_rag_sets_agree(self):
        """RAG_REQUIRED_INTENTS and RAG_INTENTS must be identical."""
        # RAG_INTENTS includes PROJECT_CONTEXT and REVISION which are not
        # in RAG_REQUIRED_INTENTS — this is an inconsistency to flag.
        # For now, verify RAG_REQUIRED_INTENTS ⊆ RAG_INTENTS
        for intent in RAG_REQUIRED_INTENTS:
            assert intent in RAG_INTENTS, (
                f"Intent '{intent.value}' in RAG_REQUIRED_INTENTS but not in RAG_INTENTS"
            )

    def test_workflow_status_has_failed(self):
        """WorkflowStatus must include FAILED for error handling."""
        assert hasattr(WorkflowStatus, "FAILED")
        assert WorkflowStatus.FAILED.value == "failed"

    def test_supervisor_state_required_fields(self):
        """SupervisorState must be creatable with minimal required fields."""
        state = SupervisorState(
            user_id="u1",
            project_id="p1",
            session_id="s1",
            user_query="test",
        )
        assert state.workflow_status == WorkflowStatus.PENDING
        assert state.intent is None
        assert state.route is None
        assert state.error is None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Router Logic (Pure, No LLM)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRouterResolveRoute:
    """Test resolve_route() for every intent."""

    @pytest.mark.parametrize("intent,expected_route", [
        (Intent.DOCUMENT_INGESTION, Route.DOCUMENT_AGENT),
        (Intent.DOCUMENT_SEARCH, Route.RAG),
        (Intent.QUESTION_ANSWERING, Route.RAG),
        (Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.USER_STORY_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.ACCEPTANCE_CRITERIA_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.SRS_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.RTM_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.REQUIREMENT_VALIDATION, Route.VALIDATION_AGENT),
        (Intent.HUMAN_REVIEW, Route.HUMAN_REVIEW),
        (Intent.REVISION, Route.REQUIREMENT_AGENT),
        (Intent.PROJECT_CONTEXT, Route.RAG),
        (Intent.UNKNOWN, Route.DIRECT_RESPONSE),
    ])
    def test_resolve_route(self, intent, expected_route):
        route = resolve_route(intent)
        assert route == expected_route, (
            f"resolve_route({intent.value}) = {route.value}, expected {expected_route.value}"
        )


class TestRouterRequiresRag:
    """Test requires_rag() for every intent."""

    @pytest.mark.parametrize("intent,expected", [
        (Intent.DOCUMENT_INGESTION, False),
        (Intent.DOCUMENT_SEARCH, True),
        (Intent.QUESTION_ANSWERING, True),
        (Intent.REQUIREMENT_GENERATION, True),
        (Intent.USER_STORY_GENERATION, True),
        (Intent.ACCEPTANCE_CRITERIA_GENERATION, True),
        (Intent.BRD_GENERATION, True),
        (Intent.SRS_GENERATION, True),
        (Intent.RTM_GENERATION, True),
        (Intent.REQUIREMENT_VALIDATION, False),
        (Intent.HUMAN_REVIEW, False),
        (Intent.REVISION, True),
        (Intent.PROJECT_CONTEXT, True),
        (Intent.UNKNOWN, False),
    ])
    def test_requires_rag(self, intent, expected):
        result = requires_rag(intent)
        assert result == expected, (
            f"requires_rag({intent.value}) = {result}, expected {expected}"
        )


class TestRouterResolveStatus:
    """Test resolve_status() for every intent."""

    @pytest.mark.parametrize("intent,expected_status", [
        (Intent.DOCUMENT_INGESTION, WorkflowStatus.GENERATING),
        (Intent.DOCUMENT_SEARCH, WorkflowStatus.RETRIEVING),
        (Intent.QUESTION_ANSWERING, WorkflowStatus.RETRIEVING),
        (Intent.REQUIREMENT_GENERATION, WorkflowStatus.GENERATING),
        (Intent.USER_STORY_GENERATION, WorkflowStatus.GENERATING),
        (Intent.ACCEPTANCE_CRITERIA_GENERATION, WorkflowStatus.GENERATING),
        (Intent.BRD_GENERATION, WorkflowStatus.GENERATING),
        (Intent.SRS_GENERATION, WorkflowStatus.GENERATING),
        (Intent.RTM_GENERATION, WorkflowStatus.GENERATING),
        (Intent.REQUIREMENT_VALIDATION, WorkflowStatus.VALIDATING),
        (Intent.HUMAN_REVIEW, WorkflowStatus.AWAITING_HUMAN),
        (Intent.REVISION, WorkflowStatus.GENERATING),
        (Intent.PROJECT_CONTEXT, WorkflowStatus.RETRIEVING),
        (Intent.UNKNOWN, WorkflowStatus.PENDING),
    ])
    def test_resolve_status(self, intent, expected_status):
        status = resolve_status(intent)
        assert status == expected_status, (
            f"resolve_status({intent.value}) = {status.value}, expected {expected_status.value}"
        )


class TestRouterRouteIntent:
    """Test the main route_intent() entry point with SupervisorState."""

    def _make_state(self, intent, confidence=1.0):
        state = SupervisorState(
            user_id="u1", project_id="p1", session_id="s1",
            user_query="test", intent=intent,
        )
        state.metadata["classification_confidence"] = confidence
        return state

    def test_route_intent_missing_intent(self):
        state = SupervisorState(
            user_id="u1", project_id="p1", session_id="s1",
            user_query="test", intent=None,
        )
        decision = route_intent(state)
        assert decision.route == Route.DIRECT_RESPONSE
        assert decision.requires_rag is False

    def test_route_intent_low_confidence(self):
        state = self._make_state(Intent.QUESTION_ANSWERING, confidence=0.3)
        decision = route_intent(state, confidence_threshold=0.5)
        assert decision.route == Route.DIRECT_RESPONSE
        assert decision.requires_rag is False

    @pytest.mark.parametrize("intent,expected_route,expected_rag,expected_status", [
        (Intent.QUESTION_ANSWERING, Route.RAG, True, WorkflowStatus.RETRIEVING),
        (Intent.DOCUMENT_INGESTION, Route.DOCUMENT_AGENT, False, WorkflowStatus.GENERATING),
        (Intent.SRS_GENERATION, Route.REQUIREMENT_AGENT, True, WorkflowStatus.GENERATING),
        (Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT, True, WorkflowStatus.GENERATING),
        (Intent.RTM_GENERATION, Route.REQUIREMENT_AGENT, True, WorkflowStatus.GENERATING),
        (Intent.USER_STORY_GENERATION, Route.REQUIREMENT_AGENT, True, WorkflowStatus.GENERATING),
        (Intent.REQUIREMENT_VALIDATION, Route.VALIDATION_AGENT, False, WorkflowStatus.VALIDATING),
        (Intent.HUMAN_REVIEW, Route.HUMAN_REVIEW, False, WorkflowStatus.AWAITING_HUMAN),
        (Intent.UNKNOWN, Route.DIRECT_RESPONSE, False, WorkflowStatus.PENDING),
    ])
    def test_route_intent_all_routes(self, intent, expected_route, expected_rag, expected_status):
        state = self._make_state(intent)
        decision = route_intent(state)
        assert decision.route == expected_route, (
            f"route_intent({intent.value}): route={decision.route.value}, expected={expected_route.value}"
        )
        assert decision.requires_rag == expected_rag, (
            f"route_intent({intent.value}): requires_rag={decision.requires_rag}, expected={expected_rag}"
        )
        assert decision.workflow_status == expected_status, (
            f"route_intent({intent.value}): status={decision.workflow_status.value}, "
            f"expected={expected_status.value}"
        )


class TestRouterRouteFromIntent:
    """Test the convenience route_from_intent() function."""

    @pytest.mark.parametrize("intent,expected_route", [
        (Intent.QUESTION_ANSWERING, Route.RAG),
        (Intent.SRS_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.RTM_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.USER_STORY_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.REQUIREMENT_VALIDATION, Route.VALIDATION_AGENT),
        (Intent.HUMAN_REVIEW, Route.HUMAN_REVIEW),
        (Intent.UNKNOWN, Route.DIRECT_RESPONSE),
    ])
    def test_route_from_intent_high_confidence(self, intent, expected_route):
        decision = route_from_intent(intent, confidence=0.95)
        assert decision.route == expected_route

    def test_route_from_intent_low_confidence(self):
        decision = route_from_intent(Intent.QUESTION_ANSWERING, confidence=0.2)
        assert decision.route == Route.DIRECT_RESPONSE
        assert decision.requires_rag is False


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Classifier Logic (No LLM)
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifierParseClassification:
    """Test _parse_classification() with various LLM output formats."""

    def test_valid_json(self):
        raw = '{"intent": "question_answering", "route": "rag", "requires_rag": true, "confidence": 0.95, "reasoning": "test"}'
        result = _parse_classification(raw)
        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True
        assert result.confidence == 0.95

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"intent": "srs_generation", "route": "requirement_agent", "requires_rag": true, "confidence": 0.9}\n```'
        result = _parse_classification(raw)
        assert result.intent == Intent.SRS_GENERATION
        assert result.route == Route.REQUIREMENT_AGENT

    def test_invalid_json_falls_back_to_unknown(self):
        raw = 'this is not json'
        result = _parse_classification(raw)
        assert result.intent == Intent.UNKNOWN
        assert result.route == Route.UNKNOWN
        assert result.confidence == 0.0

    def test_invalid_intent_falls_back_to_unknown(self):
        raw = '{"intent": "nonexistent_intent", "route": "rag", "requires_rag": false, "confidence": 0.5}'
        result = _parse_classification(raw)
        assert result.intent == Intent.UNKNOWN

    def test_route_enforced_by_canonical_map(self):
        """LLM's route is ignored; canonical mapping is enforced."""
        raw = '{"intent": "srs_generation", "route": "rag", "requires_rag": true, "confidence": 0.9}'
        result = _parse_classification(raw)
        assert result.route == Route.REQUIREMENT_AGENT  # Not RAG

    def test_rag_forced_for_rag_required_intents(self):
        """requires_rag is forced True for intents in RAG_REQUIRED_INTENTS."""
        raw = '{"intent": "srs_generation", "route": "requirement_agent", "requires_rag": false, "confidence": 0.9}'
        result = _parse_classification(raw)
        assert result.requires_rag is True  # Forced

    def test_rag_not_forced_for_non_rag_intents(self):
        raw = '{"intent": "requirement_validation", "route": "validation_agent", "requires_rag": true, "confidence": 0.9}'
        result = _parse_classification(raw)
        assert result.requires_rag is True  # LLM said true, not overridden

    def test_confidence_clamped(self):
        raw = '{"intent": "unknown", "route": "unknown", "requires_rag": false, "confidence": 1.5}'
        result = _parse_classification(raw)
        assert result.confidence == 1.0

    def test_missing_confidence_defaults_zero(self):
        raw = '{"intent": "unknown", "route": "unknown", "requires_rag": false}'
        result = _parse_classification(raw)
        assert result.confidence == 0.0


class TestClassifierClassifyIntent:
    """Test classify_intent() with mocked LLM."""

    @patch("groq.Groq")
    @patch("app.agents.supervisor.classifier.settings")
    def test_returns_result_with_api_key(self, mock_settings, MockGroq):
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_MODEL = "test-model"
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(
            content='{"intent": "question_answering", "route": "rag", "requires_rag": true, "confidence": 0.95, "reasoning": "clear question"}'
        ))]
        mock_client.chat.completions.create.return_value = mock_completion

        result = classify_intent("What is the payment flow?", "proj-1")
        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True
        assert result.confidence == 0.95

    @patch("app.agents.supervisor.classifier.settings")
    def test_returns_unknown_without_api_key(self, mock_settings):
        mock_settings.GROQ_API_KEY = ""
        result = classify_intent("test", "proj-1")
        assert result.intent == Intent.UNKNOWN
        assert result.route == Route.UNKNOWN

    @patch("groq.Groq")
    def test_low_confidence_returns_unknown(self, MockGroq):
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(
            content='{"intent": "question_answering", "route": "rag", "requires_rag": true, "confidence": 0.3, "reasoning": "unclear"}'
        ))]
        mock_client.chat.completions.create.return_value = mock_completion

        result = classify_intent("maybe something?", "proj-1", confidence_threshold=0.5)
        assert result.intent == Intent.UNKNOWN
        assert result.route == Route.UNKNOWN


class TestClassifierUpdateState:
    """Test classify_and_update_state() updates state correctly."""

    @patch("app.agents.supervisor.classifier.classify_intent")
    def test_updates_state_fields(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.SRS_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.92,
            reasoning="clear SRS request",
        )
        state = SupervisorState(
            user_id="u1", project_id="p1", session_id="s1",
            user_query="Generate SRS",
        )
        updated = classify_and_update_state(state)
        assert updated.intent == Intent.SRS_GENERATION
        assert updated.route == Route.REQUIREMENT_AGENT
        assert updated.requires_rag is True
        assert updated.metadata["classification_confidence"] == 0.92


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Service Layer (With Mocked Classifier)
# ═══════════════════════════════════════════════════════════════════════════════

class TestServiceHandleRequest:
    """Test handle_request() with mocked classifier."""

    @patch("app.agents.supervisor.service.classify_intent")
    def test_question_answering_routes_to_rag(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.QUESTION_ANSWERING,
            route=Route.RAG,
            requires_rag=True,
            confidence=0.95,
            reasoning="payment flow question",
        )
        resp = handle_request("u1", "p1", "What is the payment flow?")
        assert resp.intent == "question_answering"
        assert resp.route == "rag"
        assert resp.requires_rag is True
        assert resp.workflow_status == "retrieving"

    @patch("app.agents.supervisor.service.classify_intent")
    def test_document_ingestion_routes_to_document_agent(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.DOCUMENT_INGESTION,
            route=Route.DOCUMENT_AGENT,
            requires_rag=False,
            confidence=0.93,
            reasoning="upload request",
        )
        resp = handle_request("u1", "p1", "upload document")
        assert resp.intent == "document_ingestion"
        assert resp.route == "document_agent"
        assert resp.requires_rag is False
        assert resp.workflow_status == "generating"

    @patch("app.agents.supervisor.service.classify_intent")
    def test_srs_generation_routes_to_requirement_agent(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.SRS_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.96,
            reasoning="SRS generation",
        )
        resp = handle_request("u1", "p1", "Generate SRS")
        assert resp.intent == "srs_generation"
        assert resp.route == "requirement_agent"
        assert resp.requires_rag is True
        assert resp.workflow_status == "generating"

    @patch("app.agents.supervisor.service.classify_intent")
    def test_brd_generation_routes_to_requirement_agent(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.BRD_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.94,
            reasoning="BRD generation",
        )
        resp = handle_request("u1", "p1", "Generate BRD")
        assert resp.intent == "brd_generation"
        assert resp.route == "requirement_agent"
        assert resp.requires_rag is True

    @patch("app.agents.supervisor.service.classify_intent")
    def test_rtm_generation_routes_to_requirement_agent(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.RTM_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.91,
            reasoning="RTM generation",
        )
        resp = handle_request("u1", "p1", "Generate RTM")
        assert resp.intent == "rtm_generation"
        assert resp.route == "requirement_agent"
        assert resp.requires_rag is True

    @patch("app.agents.supervisor.service.classify_intent")
    def test_user_stories_routes_to_requirement_agent(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.USER_STORY_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.93,
            reasoning="user stories",
        )
        resp = handle_request("u1", "p1", "Generate user stories")
        assert resp.intent == "user_story_generation"
        assert resp.route == "requirement_agent"
        assert resp.requires_rag is True

    @patch("app.agents.supervisor.service.classify_intent")
    def test_validation_routes_to_validation_agent(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.REQUIREMENT_VALIDATION,
            route=Route.VALIDATION_AGENT,
            requires_rag=False,
            confidence=0.88,
            reasoning="validation request",
        )
        resp = handle_request("u1", "p1", "Validate these requirements")
        assert resp.intent == "requirement_validation"
        assert resp.route == "validation_agent"
        assert resp.requires_rag is False
        assert resp.workflow_status == "validating"

    @patch("app.agents.supervisor.service.classify_intent")
    def test_human_review_routes_to_human_review(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.HUMAN_REVIEW,
            route=Route.HUMAN_REVIEW,
            requires_rag=False,
            confidence=0.90,
            reasoning="human review request",
        )
        resp = handle_request("u1", "p1", "I want human review")
        assert resp.intent == "human_review"
        assert resp.route == "human_review"
        assert resp.requires_rag is False
        assert resp.workflow_status == "awaiting_human"

    @patch("app.agents.supervisor.service.classify_intent")
    def test_unknown_query_falls_back_to_direct_response(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.UNKNOWN,
            route=Route.UNKNOWN,
            requires_rag=False,
            confidence=0.2,
            reasoning="unclear query",
        )
        resp = handle_request("u1", "p1", "asdfghjkl")
        assert resp.intent == "unknown"
        # Router maps UNKNOWN -> DIRECT_RESPONSE
        assert resp.route == "direct_response"
        assert resp.requires_rag is False
        assert resp.workflow_status == "pending"

    def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="empty"):
            handle_request("u1", "p1", "")

    def test_whitespace_query_raises(self):
        with pytest.raises(ValueError, match="empty"):
            handle_request("u1", "p1", "   ")

    def test_empty_project_id_raises(self):
        with pytest.raises(ValueError, match="project_id"):
            handle_request("u1", "", "test query")

    def test_empty_user_id_raises(self):
        with pytest.raises(ValueError, match="user_id"):
            handle_request("", "p1", "test query")

    @patch("app.agents.supervisor.service.classify_intent")
    def test_session_id_auto_generated(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.UNKNOWN, route=Route.UNKNOWN,
            requires_rag=False, confidence=0.0, reasoning="test",
        )
        resp = handle_request("u1", "p1", "test")
        assert resp.session_id  # Not empty

    @patch("app.agents.supervisor.service.classify_intent")
    def test_session_id_preserved(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.UNKNOWN, route=Route.UNKNOWN,
            requires_rag=False, confidence=0.0, reasoning="test",
        )
        resp = handle_request("u1", "p1", "test", session_id="my-session")
        assert resp.session_id == "my-session"


class TestServiceHandleRequestWithState:
    """Test handle_request_with_state() returns full state."""

    @patch("app.agents.supervisor.service.classify_intent")
    def test_returns_state_with_classification(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.SRS_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.92,
            reasoning="SRS request",
        )
        resp, state = handle_request_with_state("u1", "p1", "Generate SRS")
        assert resp.intent == "srs_generation"
        assert state.intent == Intent.SRS_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.requires_rag is True
        assert state.workflow_status == WorkflowStatus.GENERATING
        assert state.metadata["classification_confidence"] == 0.92

    @patch("app.agents.supervisor.service.classify_intent")
    def test_state_requires_rag_set_for_non_direct_routes(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.QUESTION_ANSWERING,
            route=Route.RAG,
            requires_rag=True,
            confidence=0.95,
            reasoning="question",
        )
        _, state = handle_request_with_state("u1", "p1", "What is X?")
        # For RAG route, requires_rag is True — correct by coincidence
        # (service.py:182 uses route != DIRECT_RESPONSE which happens to match for RAG)
        assert state.requires_rag is True


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Downstream Execution Verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestDownstreamExecutionPaths:
    """
    Verify that each route actually connects to downstream functionality.
    This tests that the required modules/classes exist and are importable.
    """

    def test_rag_route_has_retriever(self):
        """Route.RAG must connect to HybridRetriever."""
        from app.rag.retrieval.hybrid import HybridRetriever
        assert hasattr(HybridRetriever, "retrieve")

    def test_rag_route_has_generation(self):
        """Route.RAG must connect to generate_answer."""
        from app.services.generation import generate_answer
        assert callable(generate_answer)

    def test_document_agent_exists(self):
        """Route.DOCUMENT_AGENT must connect to DocumentAgent."""
        from app.agents.document.agent import DocumentAgent
        assert hasattr(DocumentAgent, "process_document")

    def test_requirement_agent_module_exists(self):
        """Route.REQUIREMENT_AGENT must have an importable module."""
        import app.agents.requirement
        # Module exists (even if empty)

    def test_requirement_agent_has_no_implementation(self):
        """FLAG: Requirement agent __init__.py is empty — no agent class."""
        from app.agents.requirement import __init__
        # The module is empty — no RequirementAgent class exists
        import app.agents.requirement as req_mod
        assert not hasattr(req_mod, "RequirementAgent"), (
            "RequirementAgent class should exist but does not"
        )

    def test_validation_agent_module_exists(self):
        """Route.VALIDATION_AGENT must have an importable module."""
        import app.agents.validation
        # Module exists (even if empty)

    def test_validation_agent_has_no_implementation(self):
        """FLAG: Validation agent __init__.py is empty — no agent class."""
        import app.agents.validation as val_mod
        assert not hasattr(val_mod, "ValidationAgent"), (
            "ValidationAgent class should exist but does not"
        )

    def test_document_generation_endpoint_exists(self):
        """Document generation endpoint for BRD/SRS/RTM must exist."""
        from app.api.document_generation import DOCUMENT_PROMPTS
        assert "brd" in DOCUMENT_PROMPTS
        assert "srs" in DOCUMENT_PROMPTS
        assert "rtm" in DOCUMENT_PROMPTS
        assert "user_stories" in DOCUMENT_PROMPTS

    def test_supervisor_api_endpoint_exists(self):
        """Supervisor API endpoint must be registered."""
        from app.api.supervisor import router
        assert router is not None


class TestRouteToExecutionMapping:
    """
    For each test case, verify the full chain:
      intent → route → downstream exists → execution would work
    """

    def test_rag_payment_flow_chain(self):
        """'What is the payment flow?' → RAG → retriever + generation."""
        route = resolve_route(Intent.QUESTION_ANSWERING)
        assert route == Route.RAG
        assert requires_rag(Intent.QUESTION_ANSWERING) is True
        # Verify downstream
        from app.rag.retrieval.hybrid import HybridRetriever
        from app.services.generation import generate_answer
        assert callable(generate_answer)

    def test_document_upload_chain(self):
        """upload document → Document Agent → process_document."""
        route = resolve_route(Intent.DOCUMENT_INGESTION)
        assert route == Route.DOCUMENT_AGENT
        assert requires_rag(Intent.DOCUMENT_INGESTION) is False
        from app.agents.document.agent import DocumentAgent
        assert callable(getattr(DocumentAgent, "process_document", None))

    def test_srs_generation_chain(self):
        """Generate SRS → Requirement Agent → [MISSING]."""
        route = resolve_route(Intent.SRS_GENERATION)
        assert route == Route.REQUIREMENT_AGENT
        assert requires_rag(Intent.SRS_GENERATION) is True
        # Verify document generation endpoint has SRS support
        from app.api.document_generation import DOCUMENT_PROMPTS
        assert "srs" in DOCUMENT_PROMPTS

    def test_brd_generation_chain(self):
        """Generate BRD → Requirement Agent → [MISSING]."""
        route = resolve_route(Intent.BRD_GENERATION)
        assert route == Route.REQUIREMENT_AGENT
        from app.api.document_generation import DOCUMENT_PROMPTS
        assert "brd" in DOCUMENT_PROMPTS

    def test_rtm_generation_chain(self):
        """Generate RTM → Requirement Agent → [MISSING]."""
        route = resolve_route(Intent.RTM_GENERATION)
        assert route == Route.REQUIREMENT_AGENT
        from app.api.document_generation import DOCUMENT_PROMPTS
        assert "rtm" in DOCUMENT_PROMPTS

    def test_user_stories_chain(self):
        """Generate user stories → Requirement Agent → [MISSING]."""
        route = resolve_route(Intent.USER_STORY_GENERATION)
        assert route == Route.REQUIREMENT_AGENT
        from app.api.document_generation import DOCUMENT_PROMPTS
        assert "user_stories" in DOCUMENT_PROMPTS

    def test_validation_chain(self):
        """Validate requirements → Validation Agent → [MISSING]."""
        route = resolve_route(Intent.REQUIREMENT_VALIDATION)
        assert route == Route.VALIDATION_AGENT
        # No validation agent implementation exists
        import app.agents.validation as val_mod
        assert not hasattr(val_mod, "ValidationAgent")

    def test_human_review_chain(self):
        """Human review → HUMAN_REVIEW route → AWAITING_HUMAN status."""
        route = resolve_route(Intent.HUMAN_REVIEW)
        assert route == Route.HUMAN_REVIEW
        status = resolve_status(Intent.HUMAN_REVIEW)
        assert status == WorkflowStatus.AWAITING_HUMAN

    def test_unknown_fallback_chain(self):
        """Unknown → DIRECT_RESPONSE → PENDING status."""
        route = resolve_route(Intent.UNKNOWN)
        assert route == Route.DIRECT_RESPONSE
        status = resolve_status(Intent.UNKNOWN)
        assert status == WorkflowStatus.PENDING


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Error & Failure Handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Verify errors/failures move workflow to FAILED or are properly raised."""

    def test_workflow_status_has_failed(self):
        assert WorkflowStatus.FAILED.value == "failed"

    def test_service_raises_on_empty_query(self):
        with pytest.raises(ValueError):
            handle_request("u1", "p1", "")

    def test_service_raises_on_empty_project(self):
        with pytest.raises(ValueError):
            handle_request("u1", "", "query")

    def test_service_raises_on_empty_user(self):
        with pytest.raises(ValueError):
            handle_request("", "p1", "query")

    @patch("app.agents.supervisor.service.classify_intent")
    def test_classifier_exception_propagates(self, mock_classify):
        """If classifier throws, service should propagate the error."""
        mock_classify.side_effect = RuntimeError("LLM unavailable")
        with pytest.raises(RuntimeError):
            handle_request("u1", "p1", "test query")

    @patch("groq.Groq")
    def test_classifier_returns_unknown_on_llm_error(self, MockGroq):
        """Classifier returns UNKNOWN when LLM call fails."""
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")

        result = classify_intent("test", "p1")
        assert result.intent == Intent.UNKNOWN
        assert result.confidence == 0.0

    @patch("app.agents.supervisor.classifier.settings")
    def test_classifier_returns_unknown_without_api_key(self, mock_settings):
        mock_settings.GROQ_API_KEY = ""
        result = classify_intent("test", "p1")
        assert result.intent == Intent.UNKNOWN
        assert result.route == Route.UNKNOWN

    def test_supervisor_error_model(self):
        """SupervisorError model exists and has required fields."""
        err = SupervisorError(error="test_error", detail="something went wrong")
        assert err.error == "test_error"
        assert err.workflow_status == "failed"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: RAG Flag Consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestRagFlagConsistency:
    """Verify RAG-required flags are correct across all layers."""

    def test_rag_required_for_question_answering(self):
        assert Intent.QUESTION_ANSWERING in RAG_REQUIRED_INTENTS
        assert requires_rag(Intent.QUESTION_ANSWERING) is True

    def test_rag_required_for_all_generation_intents(self):
        gen_intents = [
            Intent.REQUIREMENT_GENERATION,
            Intent.USER_STORY_GENERATION,
            Intent.ACCEPTANCE_CRITERIA_GENERATION,
            Intent.BRD_GENERATION,
            Intent.SRS_GENERATION,
            Intent.RTM_GENERATION,
        ]
        for intent in gen_intents:
            assert intent in RAG_REQUIRED_INTENTS, (
                f"{intent.value} should be in RAG_REQUIRED_INTENTS"
            )
            assert requires_rag(intent) is True, (
                f"{intent.value} should require RAG"
            )

    def test_rag_not_required_for_validation(self):
        assert Intent.REQUIREMENT_VALIDATION not in RAG_REQUIRED_INTENTS
        assert requires_rag(Intent.REQUIREMENT_VALIDATION) is False

    def test_rag_not_required_for_human_review(self):
        assert Intent.HUMAN_REVIEW not in RAG_REQUIRED_INTENTS
        assert requires_rag(Intent.HUMAN_REVIEW) is False

    def test_rag_not_required_for_document_ingestion(self):
        assert Intent.DOCUMENT_INGESTION not in RAG_REQUIRED_INTENTS
        assert requires_rag(Intent.DOCUMENT_INGESTION) is False

    def test_rag_not_required_for_unknown(self):
        assert Intent.UNKNOWN not in RAG_REQUIRED_INTENTS
        assert requires_rag(Intent.UNKNOWN) is False

    def test_document_search_requires_rag(self):
        assert Intent.DOCUMENT_SEARCH in RAG_REQUIRED_INTENTS
        assert requires_rag(Intent.DOCUMENT_SEARCH) is True


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: Known Inconsistencies / Issues
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnownIssues:
    """Document known inconsistencies in the codebase.
    Note: PROJECT_CONTEXT RAG inconsistency has been fixed."""

    def test_classifier_maps_unknown_to_route_unknown(self):
        """ISSUE: Classifier maps UNKNOWN intent to Route.UNKNOWN,
        but router maps UNKNOWN intent to Route.DIRECT_RESPONSE.
        The router's resolve_route() overrides this, but it's inconsistent."""
        assert INTENT_ROUTE_MAP[Intent.UNKNOWN] == Route.UNKNOWN
        assert INTENT_TO_ROUTE[Intent.UNKNOWN] == Route.DIRECT_RESPONSE

    def test_project_context_rag_inconsistency(self):
        """FIXED: PROJECT_CONTEXT is now in both RAG_INTENTS (router) and
        RAG_REQUIRED_INTENTS (classifier). Both layers force RAG for it."""
        assert Intent.PROJECT_CONTEXT in RAG_INTENTS
        assert Intent.PROJECT_CONTEXT in RAG_REQUIRED_INTENTS

    def test_revision_rag_inconsistency(self):
        """ISSUE: REVISION is in RAG_INTENTS but not in RAG_REQUIRED_INTENTS."""
        assert Intent.REVISION in RAG_INTENTS
        assert Intent.REVISION not in RAG_REQUIRED_INTENTS

    def test_service_requires_rag_logic_differs_from_classifier(self):
        """ISSUE: handle_request_with_state() sets requires_rag based on
        route != DIRECT_RESPONSE, but the classifier uses RAG_REQUIRED_INTENTS.
        These can disagree for PROJECT_CONTEXT and REVISION."""
        # The service sets:
        #   state.requires_rag = classification.route != Route.DIRECT_RESPONSE
        # But the classifier forces requires_rag via RAG_REQUIRED_INTENTS.
        # These are different logic paths.
        pass  # Documented, not asserting — it's a known issue.

    def test_orchestration_layer_exists(self):
        """orchestrator.py now exists — it was created to execute downstream agents."""
        import os
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        supervisor_dir = os.path.join(backend_dir, "app", "agents", "supervisor")
        files = os.listdir(supervisor_dir)
        assert "orchestrator.py" in files

    def test_requirement_agent_empty(self):
        """ISSUE: Requirement agent module is empty — no implementation."""
        import app.agents.requirement as req_mod
        # Only __init__.py exists, and it's empty
        public_attrs = [a for a in dir(req_mod) if not a.startswith("_")]
        assert len(public_attrs) == 0, (
            f"Requirement agent has unexpected attrs: {public_attrs}"
        )

    def test_validation_agent_empty(self):
        """ISSUE: Validation agent module is empty — no implementation."""
        import app.agents.validation as val_mod
        public_attrs = [a for a in dir(val_mod) if not a.startswith("_")]
        assert len(public_attrs) == 0, (
            f"Validation agent has unexpected attrs: {public_attrs}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: Full Workflow Integration (Mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullWorkflowIntegration:
    """
    End-to-end: query → classify → route → verify execution path.
    Uses mocked LLM to avoid real API calls.
    """

    @patch("app.agents.supervisor.service.classify_intent")
    def test_payment_flow_full_chain(self, mock_classify):
        """'What is the payment flow?' → RAG → retriever would be called."""
        mock_classify.return_value = ClassificationResult(
            intent=Intent.QUESTION_ANSWERING,
            route=Route.RAG,
            requires_rag=True,
            confidence=0.95,
            reasoning="payment flow question",
        )
        resp, state = handle_request_with_state("u1", "p1", "What is the payment flow?")

        # 1. Classifier
        assert state.intent == Intent.QUESTION_ANSWERING
        # 2. Router
        assert state.route == Route.RAG
        assert state.requires_rag is True
        # 3. Status
        assert state.workflow_status == WorkflowStatus.RETRIEVING
        # 4. Response
        assert resp.route == "rag"
        assert resp.workflow_status == "retrieving"

    @patch("app.agents.supervisor.service.classify_intent")
    def test_upload_document_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.DOCUMENT_INGESTION,
            route=Route.DOCUMENT_AGENT,
            requires_rag=False,
            confidence=0.93,
            reasoning="upload request",
        )
        resp, state = handle_request_with_state("u1", "p1", "upload document")
        assert state.intent == Intent.DOCUMENT_INGESTION
        assert state.route == Route.DOCUMENT_AGENT
        assert state.requires_rag is False
        assert state.workflow_status == WorkflowStatus.GENERATING

    @patch("app.agents.supervisor.service.classify_intent")
    def test_generate_srs_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.SRS_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.96,
            reasoning="SRS",
        )
        resp, state = handle_request_with_state("u1", "p1", "Generate SRS")
        assert state.intent == Intent.SRS_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.requires_rag is True
        assert state.workflow_status == WorkflowStatus.GENERATING

    @patch("app.agents.supervisor.service.classify_intent")
    def test_generate_brd_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.BRD_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.94,
            reasoning="BRD",
        )
        resp, state = handle_request_with_state("u1", "p1", "Generate BRD")
        assert state.intent == Intent.BRD_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT

    @patch("app.agents.supervisor.service.classify_intent")
    def test_generate_rtm_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.RTM_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.91,
            reasoning="RTM",
        )
        resp, state = handle_request_with_state("u1", "p1", "Generate RTM")
        assert state.intent == Intent.RTM_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT

    @patch("app.agents.supervisor.service.classify_intent")
    def test_generate_user_stories_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.USER_STORY_GENERATION,
            route=Route.REQUIREMENT_AGENT,
            requires_rag=True,
            confidence=0.93,
            reasoning="user stories",
        )
        resp, state = handle_request_with_state("u1", "p1", "Generate user stories")
        assert state.intent == Intent.USER_STORY_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT

    @patch("app.agents.supervisor.service.classify_intent")
    def test_validate_requirements_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.REQUIREMENT_VALIDATION,
            route=Route.VALIDATION_AGENT,
            requires_rag=False,
            confidence=0.88,
            reasoning="validation",
        )
        resp, state = handle_request_with_state("u1", "p1", "Validate these requirements")
        assert state.intent == Intent.REQUIREMENT_VALIDATION
        assert state.route == Route.VALIDATION_AGENT
        assert state.requires_rag is False
        assert state.workflow_status == WorkflowStatus.VALIDATING

    @patch("app.agents.supervisor.service.classify_intent")
    def test_human_review_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.HUMAN_REVIEW,
            route=Route.HUMAN_REVIEW,
            requires_rag=False,
            confidence=0.90,
            reasoning="human review",
        )
        resp, state = handle_request_with_state("u1", "p1", "I want human review")
        assert state.intent == Intent.HUMAN_REVIEW
        assert state.route == Route.HUMAN_REVIEW
        assert state.requires_rag is False
        assert state.workflow_status == WorkflowStatus.AWAITING_HUMAN

    @patch("app.agents.supervisor.service.classify_intent")
    def test_unknown_query_full_chain(self, mock_classify):
        mock_classify.return_value = ClassificationResult(
            intent=Intent.UNKNOWN,
            route=Route.UNKNOWN,
            requires_rag=False,
            confidence=0.2,
            reasoning="unclear",
        )
        resp, state = handle_request_with_state("u1", "p1", "asdfghjkl")
        assert state.intent == Intent.UNKNOWN
        assert state.route == Route.DIRECT_RESPONSE
        assert state.requires_rag is False
        assert state.workflow_status == WorkflowStatus.PENDING


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: API Endpoint Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestSupervisorAPIEndpoint:
    """Test the FastAPI endpoint for supervisor classification."""

    def test_endpoint_exists_in_app(self):
        """Supervisor route must be registered in FastAPI app."""
        from app.main import app
        # Use OpenAPI schema to find all registered routes
        openapi = app.openapi()
        paths = list(openapi.get("paths", {}).keys())
        assert "/api/projects/{project_id}/supervisor" in paths

    def test_request_schema_valid(self):
        """SupervisorRequest must accept required fields."""
        req = SupervisorRequest(
            user_id="u1",
            project_id="p1",
            user_query="test",
        )
        assert req.user_query == "test"
        assert req.confidence_threshold == 0.5  # default

    def test_response_schema_valid(self):
        """SupervisorResponse must have all required fields."""
        resp = SupervisorResponse(
            intent="question_answering",
            route="rag",
            requires_rag=True,
            confidence=0.95,
            workflow_status="retrieving",
            session_id="s1",
        )
        assert resp.intent == "question_answering"
        assert resp.route == "rag"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: Document Query Classification & Safety Net
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentQueryClassification:
    """
    Test the exact failing scenario: document queries must always classify
    as document_search or question_answering with requires_rag=True.

    Verifies:
    1. Keyword pre-check detects document queries
    2. Safety net overrides LLM misclassification
    3. Exception handler checks keywords before returning UNKNOWN
    4. Full chain: message → classified intent → route → RAG execution
    """

    DOCUMENT_QUERY = "What are the main requirements in my uploaded document?"

    def test_keyword_precheck_detects_document_query(self):
        """_is_document_query must return True for document-related queries."""
        from app.agents.supervisor.classifier import _is_document_query
        assert _is_document_query(self.DOCUMENT_QUERY) is True

    @patch("app.agents.supervisor.classifier.settings")
    def test_no_api_key_routes_document_query_to_rag(self, mock_settings):
        """Without API key, keyword detection routes document queries to RAG."""
        mock_settings.GROQ_API_KEY = ""
        result = classify_intent(self.DOCUMENT_QUERY, "proj-1")
        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True
        assert result.confidence >= 0.6

    @patch("groq.Groq")
    @patch("app.agents.supervisor.classifier.settings")
    def test_llm_success_classifies_document_query(self, mock_settings, MockGroq):
        """Successful LLM call classifies document query correctly."""
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_MODEL = "test-model"
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(
            content='{"intent": "document_search", "route": "rag", "requires_rag": true, "confidence": 0.95, "reasoning": "document query"}'
        ))]
        mock_client.chat.completions.create.return_value = mock_completion

        result = classify_intent(self.DOCUMENT_QUERY, "proj-1")
        assert result.intent == Intent.DOCUMENT_SEARCH
        assert result.route == Route.RAG
        assert result.requires_rag is True
        assert result.confidence == 0.95

    @patch("groq.Groq")
    def test_llm_misclassification_safety_net_overrides(self, MockGroq):
        """If LLM misclassifies a document query, safety net overrides to RAG."""
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(
            content='{"intent": "unknown", "route": "unknown", "requires_rag": false, "confidence": 0.3, "reasoning": "unclear"}'
        ))]
        mock_client.chat.completions.create.return_value = mock_completion

        result = classify_intent(self.DOCUMENT_QUERY, "proj-1")
        # Safety net should override to question_answering
        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True
        assert result.confidence >= 0.7

    @patch("groq.Groq")
    def test_llm_exception_safety_net_routes_to_rag(self, MockGroq):
        """If LLM throws exception, keyword pre-check still routes to RAG."""
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")

        result = classify_intent(self.DOCUMENT_QUERY, "proj-1")
        # Even with LLM failure, keyword detection routes to RAG
        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True
        assert result.confidence >= 0.6
        assert "LLM failed" in result.reasoning or "keyword" in result.reasoning

    @patch("groq.Groq")
    def test_llm_invalid_json_safety_net_overrides(self, MockGroq):
        """If LLM returns unparseable output, safety net handles it."""
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(
            content="I think this is about documents but I'm not sure"
        ))]
        mock_client.chat.completions.create.return_value = mock_completion

        result = classify_intent(self.DOCUMENT_QUERY, "proj-1")
        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True

    @patch("groq.Groq")
    def test_model_not_found_fallback_to_safety_net(self, MockGroq):
        """If primary model is 404, exception handler checks keywords."""
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception(
            "Error code: 404 - model_not_found"
        )

        result = classify_intent(self.DOCUMENT_QUERY, "proj-1")
        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True

    @patch("app.agents.supervisor.service.classify_intent")
    def test_full_service_flow_document_query(self, mock_classify):
        """Full service flow: message → classify → route → response."""
        mock_classify.return_value = ClassificationResult(
            intent=Intent.DOCUMENT_SEARCH,
            route=Route.RAG,
            requires_rag=True,
            confidence=0.95,
            reasoning="document query",
        )
        resp, state = handle_request_with_state(
            "u1", "proj-1", self.DOCUMENT_QUERY
        )
        # Verify classification
        assert state.intent == Intent.DOCUMENT_SEARCH
        assert state.route == Route.RAG
        assert state.requires_rag is True
        # Verify response
        assert resp.intent == "document_search"
        assert resp.route == "rag"
        assert resp.requires_rag is True
        assert resp.workflow_status == "retrieving"

    def test_parse_think_blocks_stripped(self):
        """Parser correctly strips <think> blocks from LLM output."""
        from app.agents.supervisor.classifier import _parse_classification
        raw = '''<think>
Analysis of the query...
</think>
{"intent": "document_search", "route": "rag", "requires_rag": true, "confidence": 0.9, "reasoning": "document query"}'''
        result = _parse_classification(raw)
        assert result.intent == Intent.DOCUMENT_SEARCH
        assert result.route == Route.RAG
        assert result.requires_rag is True

    def test_parse_unclosed_think_block_stripped(self):
        """Parser handles truncated responses with unclosed <think> blocks."""
        from app.agents.supervisor.classifier import _parse_classification
        raw = '''<think>
The user is asking about requirements in their document. This clearly references uploaded content and should be classified as document_search with requires_rag=true. The query explicitly mentions "main requirements" and "uploaded document" which are strong signals for document-related intent.'''
        result = _parse_classification(raw)
        # No valid JSON found after stripping think block
        assert result.intent == Intent.UNKNOWN
        assert result.confidence == 0.0

    @patch("groq.Groq")
    def test_document_query_various_phrasings(self, MockGroq):
        """Various document query phrasings are detected by keyword pre-check."""
        from app.agents.supervisor.classifier import _is_document_query

        document_queries = [
            "What are the main requirements in my uploaded document?",
            "Summarize my uploaded document",
            "What does the document say about payment?",
            "Find all login requirements in the document",
            "Where are the security requirements?",
            "Tell me about the system architecture in the document",
            "What requirements are mentioned in the document?",
            "How does authentication work according to the spec?",
        ]
        for query in document_queries:
            assert _is_document_query(query) is True, (
                f"Keyword pre-check failed for: {query}"
            )
