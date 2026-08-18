"""
Document Query Classification Tests

Verifies that document-related questions are correctly classified and
routed to the RAG/retrieval workflow. Tests the keyword pre-check,
LLM prompt improvements, and the safety-net override logic.

Target queries:
  1. "What are the main requirements in my uploaded document?"
  2. "Summarize my uploaded document"
  3. "What requirements are mentioned in the document?"
  4. "What does the document say about authentication?"
  5. "Find all security requirements in the document"
  6. "Explain the payment workflow described in the document"
  7. "Where are the API integration requirements?"
"""
import pytest
from unittest.mock import patch, MagicMock

from app.agents.supervisor.state import Intent, Route, SupervisorState
from app.agents.supervisor.classifier import (
    ClassificationResult,
    _is_document_query,
    _parse_classification,
    classify_intent,
    classify_and_update_state,
    INTENT_ROUTE_MAP,
    RAG_REQUIRED_INTENTS,
)
from app.agents.supervisor.router import (
    route_from_intent,
    resolve_route,
    requires_rag,
    INTENT_TO_ROUTE,
    RAG_INTENTS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Keyword Pre-check Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentQueryKeywordDetection:
    """Test that _is_document_query correctly identifies document-related queries."""

    @pytest.mark.parametrize("query", [
        "What are the main requirements in my uploaded document?",
        "Summarize my uploaded document",
        "What requirements are mentioned in the document?",
        "What does the document say about authentication?",
        "Find all security requirements in the document",
        "Explain the payment workflow described in the document",
        "Where are the API integration requirements?",
        "Search for login requirements in the document",
        "Tell me about the system architecture in the document",
        "How does user authentication work according to the spec?",
        "What does the file say about payment processing?",
        "Look for error handling requirements in my upload",
        "Describe the database schema from the document",
        "What are the key features described in the document?",
    ])
    def test_document_queries_detected(self, query):
        """All document-related queries must be detected by keyword check."""
        assert _is_document_query(query) is True, (
            f"Keyword check failed to detect document query: {query}"
        )

    @pytest.mark.parametrize("query", [
        "Hello, how are you?",
        "Generate a BRD",
        "Create user stories for checkout",
        "What is 2 + 2?",
        "Help me with something",
    ])
    def test_non_document_queries_not_detected(self, query):
        """Non-document queries must NOT be flagged by keyword check."""
        assert _is_document_query(query) is False, (
            f"Keyword check false positive for: {query}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Routing Consistency Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentQueryRouting:
    """Test that document-related intents route to RAG correctly."""

    def test_document_search_routes_to_rag(self):
        """DOCUMENT_SEARCH intent must route to RAG."""
        decision = route_from_intent(Intent.DOCUMENT_SEARCH, confidence=0.9)
        assert decision.route == Route.RAG
        assert decision.requires_rag is True

    def test_question_answering_routes_to_rag(self):
        """QUESTION_ANSWERING intent must route to RAG."""
        decision = route_from_intent(Intent.QUESTION_ANSWERING, confidence=0.9)
        assert decision.route == Route.RAG
        assert decision.requires_rag is True

    def test_project_context_routes_to_rag(self):
        """PROJECT_CONTEXT intent must route to RAG."""
        decision = route_from_intent(Intent.PROJECT_CONTEXT, confidence=0.9)
        assert decision.route == Route.RAG
        assert decision.requires_rag is True

    def test_all_document_intents_require_rag(self):
        """All document-related intents must be in RAG_INTENTS."""
        document_intents = {
            Intent.DOCUMENT_SEARCH,
            Intent.QUESTION_ANSWERING,
            Intent.PROJECT_CONTEXT,
        }
        for intent in document_intents:
            assert intent in RAG_INTENTS, (
                f"Intent '{intent.value}' not in RAG_INTENTS"
            )
            assert intent in RAG_REQUIRED_INTENTS, (
                f"Intent '{intent.value}' not in RAG_REQUIRED_INTENTS"
            )

    def test_document_intents_map_to_rag_route(self):
        """All document-related intents must map to RAG route in classifier."""
        document_intents = {
            Intent.DOCUMENT_SEARCH,
            Intent.QUESTION_ANSWERING,
            Intent.PROJECT_CONTEXT,
        }
        for intent in document_intents:
            assert INTENT_ROUTE_MAP[intent] == Route.RAG, (
                f"Intent '{intent.value}' maps to '{INTENT_ROUTE_MAP[intent].value}' "
                f"instead of 'rag'"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: No-LLM Classification (Keyword Fallback)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentQueryNoLLMFallback:
    """Test classification when LLM is not available (GROQ_API_KEY empty)."""

    @pytest.mark.parametrize("query", [
        "What are the main requirements in my uploaded document?",
        "Summarize my uploaded document",
        "What requirements are mentioned in the document?",
        "What does the document say about authentication?",
        "Find all security requirements in the document",
    ])
    def test_document_queries_route_to_rag_without_llm(self, query):
        """Document queries must route to RAG even without LLM via keyword fallback."""
        result = classify_intent(
            user_query=query,
            project_id="test-project-id",
            confidence_threshold=0.0,  # Disable threshold for fallback
        )
        assert result.intent == Intent.QUESTION_ANSWERING, (
            f"Query '{query}' got intent '{result.intent.value}', expected 'question_answering'"
        )
        assert result.route == Route.RAG, (
            f"Query '{query}' got route '{result.route.value}', expected 'rag'"
        )
        assert result.requires_rag is True, (
            f"Query '{query}' has requires_rag=False, expected True"
        )
        assert result.confidence >= 0.5, (
            f"Query '{query}' has low confidence: {result.confidence}"
        )

    def test_non_document_queries_get_unknown_without_llm(self):
        """Non-document queries must get UNKNOWN without LLM."""
        result = classify_intent(
            user_query="Hello, how are you?",
            project_id="test-project-id",
        )
        assert result.intent == Intent.UNKNOWN
        assert result.requires_rag is False


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: LLM Safety-net Override Tests
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_groq_response(intent_value: str, confidence: float = 0.9, requires_rag: bool = False):
    """Create a mock Groq API response."""
    mock_message = MagicMock()
    mock_message.content = (
        f'{{"intent": "{intent_value}", "route": "unknown", '
        f'"requires_rag": {str(requires_rag).lower()}, '
        f'"confidence": {confidence}, "reasoning": "test"}}'
    )
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    return mock_completion


class TestLLMSafetyNetOverride:
    """Test that keyword pre-check overrides LLM misclassification."""

    @pytest.mark.parametrize("query,expected_doc_intent", [
        ("What are the main requirements in my uploaded document?", True),
        ("Summarize my uploaded document", True),
        ("What requirements are mentioned in the document?", True),
        ("What does the document say about authentication?", True),
        ("Find all security requirements in the document", True),
    ])
    @patch("app.agents.supervisor.classifier.settings")
    @patch("groq.Groq")
    def test_llm_misclassification_overridden_for_doc_queries(
        self, mock_groq_cls, mock_settings, query, expected_doc_intent
    ):
        """When LLM misclassifies a document query, keyword override must fix it."""
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_MODEL = "test-model"

        # Simulate LLM returning UNKNOWN for a document query
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_groq_response(
            "unknown", confidence=0.9
        )

        result = classify_intent(
            user_query=query,
            project_id="test-project-id",
        )

        # Must be overridden to question_answering
        assert result.intent == Intent.QUESTION_ANSWERING, (
            f"Query '{query}' was not overridden. Got intent: {result.intent.value}"
        )
        assert result.route == Route.RAG
        assert result.requires_rag is True

    @patch("app.agents.supervisor.classifier.settings")
    @patch("groq.Groq")
    def test_llm_correct_classification_preserved(self, mock_groq_cls, mock_settings):
        """When LLM correctly classifies a document query, no override needed."""
        mock_settings.GROQ_API_KEY = "test-key"
        mock_settings.GROQ_MODEL = "test-model"

        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_groq_response(
            "question_answering", confidence=0.95, requires_rag=True
        )

        result = classify_intent(
            user_query="What does the document say about authentication?",
            project_id="test-project-id",
        )

        assert result.intent == Intent.QUESTION_ANSWERING
        assert result.route == Route.RAG
        assert result.requires_rag is True
        assert result.confidence == 0.95


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Full Pipeline Integration Tests (5 required examples)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentQuestionPipelineIntegration:
    """
    End-to-end tests for the 5+ document question examples.
    Each test verifies the complete flow:
      query → keyword check → classification → routing → RAG required
    """

    DOCUMENT_QUERIES = [
        (
            "What are the main requirements in my uploaded document?",
            "Main requirements query",
        ),
        (
            "Summarize my uploaded document",
            "Document summary query",
        ),
        (
            "What requirements are mentioned in the document?",
            "Requirements enumeration query",
        ),
        (
            "What does the document say about authentication?",
            "Topic-specific document query",
        ),
        (
            "Find all security requirements in the document",
            "Security requirements search query",
        ),
        (
            "Explain the payment workflow described in the document",
            "Payment workflow explanation query",
        ),
        (
            "Where are the API integration requirements?",
            "API requirements location query",
        ),
    ]

    @pytest.mark.parametrize("query,description", DOCUMENT_QUERIES)
    def test_document_query_routes_to_rag(self, query, description):
        """Each document query must be detected, classified, and routed to RAG."""
        # Step 1: Keyword detection
        assert _is_document_query(query) is True, (
            f"[{description}] Keyword check failed for: {query}"
        )

        # Step 2: Classification without LLM (keyword fallback)
        result = classify_intent(
            user_query=query,
            project_id="test-project-id",
            confidence_threshold=0.0,
        )

        # Step 3: Verify classification
        assert result.intent in (
            Intent.DOCUMENT_SEARCH,
            Intent.QUESTION_ANSWERING,
        ), (
            f"[{description}] Got intent '{result.intent.value}', "
            f"expected 'document_search' or 'question_answering'"
        )

        # Step 4: Verify routing
        assert result.route == Route.RAG, (
            f"[{description}] Got route '{result.route.value}', expected 'rag'"
        )

        # Step 5: Verify RAG flag
        assert result.requires_rag is True, (
            f"[{description}] requires_rag is False, expected True"
        )

        # Step 6: Verify router agrees
        decision = route_from_intent(
            intent=result.intent,
            confidence=result.confidence,
            confidence_threshold=0.0,
        )
        assert decision.route == Route.RAG, (
            f"[{description}] Router disagrees: got '{decision.route.value}'"
        )
        assert decision.requires_rag is True, (
            f"[{description}] Router says requires_rag=False"
        )

    @pytest.mark.parametrize("query,description", DOCUMENT_QUERIES)
    def test_document_query_via_classify_and_update_state(self, query, description):
        """classify_and_update_state must set RAG routing on SupervisorState."""
        state = SupervisorState(
            user_id="test-user",
            project_id="test-project",
            session_id="test-session",
            user_query=query,
        )

        updated = classify_and_update_state(state, confidence_threshold=0.0)

        assert updated.route == Route.RAG, (
            f"[{description}] State route is '{updated.route.value}', expected 'rag'"
        )
        assert updated.requires_rag is True, (
            f"[{description}] State requires_rag is False"
        )
        assert updated.intent in (
            Intent.DOCUMENT_SEARCH,
            Intent.QUESTION_ANSWERING,
        ), (
            f"[{description}] State intent is '{updated.intent.value}'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Regression Tests — Document Generation Unchanged
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentGenerationUnchanged:
    """Verify that document-generation button routing is not affected."""

    @pytest.mark.parametrize("intent,expected_route", [
        (Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.SRS_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.RTM_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.USER_STORY_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.ACCEPTANCE_CRITERIA_GENERATION, Route.REQUIREMENT_AGENT),
        (Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT),
    ])
    def test_generation_intents_still_route_to_requirement_agent(self, intent, expected_route):
        """Document generation intents must still route to REQUIREMENT_AGENT."""
        decision = route_from_intent(intent, confidence=1.0)
        assert decision.route == expected_route
        assert decision.requires_rag is True  # Generation also needs RAG

    def test_explicit_action_bypass_unchanged(self):
        """Explicit action override must still bypass LLM classification."""
        from app.api.supervisor_chat import ACTION_INTENT_MAP

        assert ACTION_INTENT_MAP["brd"] == Intent.BRD_GENERATION
        assert ACTION_INTENT_MAP["srs"] == Intent.SRS_GENERATION
        assert ACTION_INTENT_MAP["rtm"] == Intent.RTM_GENERATION
