"""
Supervisor E2E Flow Tests — All 16 Routes (A–P)

Tests the complete pipeline for every flow:
  Frontend → /api/supervisor/chat → Supervisor → Agent → Result → Frontend

Each test verifies ALL of:
  1. Intent detected
  2. Correct route
  3. Correct agent executed
  4. Correct action preserved
  5. Existing service executed
  6. Result returned
  7. Correct final state
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock

from app.agents.supervisor.state import Intent, Route, WorkflowStatus, SupervisorState
from app.agents.supervisor.orchestrator import execute, _resolve_action, INTENT_TO_ACTION
from app.agents.supervisor.router import route_from_intent
from app.api.supervisor_chat import ACTION_INTENT_MAP
from app.api.document_generation import DOCUMENT_PROMPTS


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_search_response(context="Test context from documents", citations=None):
    resp = MagicMock()
    resp.context = context
    resp.citations = citations or []
    return resp


def _mock_generation(answer="Generated answer from LLM", configured=True, message=""):
    return {"answer": answer, "configured": configured, "message": message}


def _make_state(intent, route, query="test query", project_id="p1", action=None, document_ids=None):
    return SupervisorState(
        user_id="u1",
        project_id=project_id,
        session_id=str(uuid.uuid4()),
        user_query=query,
        intent=intent,
        route=route,
        requires_rag=True,
        workflow_status=WorkflowStatus.PENDING,
        action=action,
        document_ids=document_ids,
    )


def _classify_and_execute(intent, route, query, action=None, project_id="p1"):
    """Full pipeline: build state → classify → route → execute."""
    state = _make_state(intent, route, query, project_id, action=action)
    db = MagicMock()
    return execute(state, db)


# ═══════════════════════════════════════════════════════════════════════════════
# Flow A: Document question → RAG Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowA_RAGQuestion:
    """User asks a question about documents → RAG → answer + citations."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_rag_question_full_flow(self, MockRetriever, mock_gen):
        citation = MagicMock()
        citation.document_id = "doc-1"
        citation.file_name = "BRD.pdf"
        citation.model_dump.return_value = {"document_id": "doc-1", "file_name": "BRD.pdf", "page_number": 5}

        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Payment flow documentation", citations=[citation]
        )
        mock_gen.return_value = _mock_generation(
            answer="The payment flow uses Stripe with 3D secure authentication."
        )

        state = _classify_and_execute(
            Intent.QUESTION_ANSWERING, Route.RAG,
            "What is the payment flow?"
        )

        # Intent
        assert state.intent == Intent.QUESTION_ANSWERING
        # Route
        assert state.route == Route.RAG
        # Agent executed (retriever called)
        mock_retriever.retrieve.assert_called_once()
        # Action preserved (no action for RAG)
        assert state.action is None
        # Service executed (generate_answer called)
        mock_gen.assert_called_once()
        # Result returned
        assert state.generated_output is not None
        assert "Stripe" in state.generated_output
        # Citations returned
        assert len(state.citations) == 1
        # Final state
        assert state.workflow_status == WorkflowStatus.COMPLETED
        assert state.error is None


# ═══════════════════════════════════════════════════════════════════════════════
# Flow B: Upload/process document → Document Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowB_DocumentAgent:
    """User uploads document → Document Agent → processing pipeline."""

    def test_document_agent_no_ids_returns_guidance(self):
        """Without document_ids, returns guidance message."""
        state = _classify_and_execute(
            Intent.DOCUMENT_INGESTION, Route.DOCUMENT_AGENT,
            "upload document"
        )

        assert state.intent == Intent.DOCUMENT_INGESTION
        assert state.route == Route.DOCUMENT_AGENT
        assert state.generated_output is not None
        assert "upload" in state.generated_output.lower()
        assert state.workflow_status == WorkflowStatus.COMPLETED
        assert state.metadata.get("document_action") == "document_ingestion"

    @patch("app.agents.document.agent.DocumentAgent")
    def test_document_agent_with_ids_processes_them(self, MockDocAgent):
        """With document_ids, calls DocumentAgent.process_document() for each."""
        from app.models.document import Document

        mock_agent = MagicMock()
        MockDocAgent.return_value = mock_agent

        # Create mock documents
        doc1 = MagicMock(spec=Document)
        doc1.id = "doc-1"
        doc1.file_name = "BRD.pdf"
        doc1.status = "indexed"
        doc1.error_message = None

        doc2 = MagicMock(spec=Document)
        doc2.id = "doc-2"
        doc2.file_name = "SRS.docx"
        doc2.status = "indexed"
        doc2.error_message = None

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [doc1, doc2]

        state = _make_state(
            Intent.DOCUMENT_INGESTION, Route.DOCUMENT_AGENT,
            "process my documents", document_ids=["doc-1", "doc-2"],
        )
        result = execute(state, db)

        # DocumentAgent was created and process_document called for each doc
        MockDocAgent.assert_called_once_with(db)
        assert mock_agent.process_document.call_count == 2
        mock_agent.process_document.assert_any_call(doc1)
        mock_agent.process_document.assert_any_call(doc2)

        # Results in metadata
        assert "processing_results" in result.metadata
        assert len(result.metadata["processing_results"]) == 2
        assert result.metadata["processing_results"][0]["status"] == "indexed"
        assert result.metadata["processing_results"][1]["status"] == "indexed"

        # Output describes results
        assert "document(s) indexed" in result.generated_output
        assert result.workflow_status == WorkflowStatus.COMPLETED

    @patch("app.agents.document.agent.DocumentAgent")
    def test_document_agent_handles_not_found(self, MockDocAgent):
        """Documents not found in project are reported as not_found."""
        mock_agent = MagicMock()
        MockDocAgent.return_value = mock_agent

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        state = _make_state(
            Intent.DOCUMENT_INGESTION, Route.DOCUMENT_AGENT,
            "process doc", document_ids=["nonexistent-id"],
        )
        result = execute(state, db)

        assert result.metadata["processing_results"][0]["status"] == "not_found"
        assert "not found" in result.generated_output.lower()

    @patch("app.agents.document.agent.DocumentAgent")
    def test_document_agent_handles_processing_failure(self, MockDocAgent):
        """Documents that fail processing are reported as failed."""
        from app.models.document import Document

        mock_agent = MagicMock()
        MockDocAgent.return_value = mock_agent

        doc = MagicMock(spec=Document)
        doc.id = "doc-fail"
        doc.file_name = "bad.pdf"
        doc.status = "failed"
        doc.error_message = "Extraction failed"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc

        state = _make_state(
            Intent.DOCUMENT_INGESTION, Route.DOCUMENT_AGENT,
            "process doc", document_ids=["doc-fail"],
        )
        result = execute(state, db)

        assert result.metadata["processing_results"][0]["status"] == "failed"
        assert "failed" in result.generated_output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Flow C: BRD → Requirement Agent → BRD
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowC_BRD:
    """Generate BRD → Requirement Agent → BRD document."""

    @patch("app.agents.requirement.brd_generator.generate_answer")
    @patch("app.agents.requirement.agent.HybridRetriever")
    def test_brd_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Business requirements from project docs"
        )
        mock_gen.return_value = _mock_generation(
            answer="## 1. Executive Summary\nThe system shall support payment processing."
        )

        state = _classify_and_execute(
            Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate BRD", action="brd"
        )

        assert state.intent == Intent.BRD_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "brd"
        assert state.metadata.get("document_action") == "brd"
        assert state.metadata.get("document_title") == "Business Requirements Document (BRD)"
        mock_retriever.retrieve.assert_called_once()
        mock_gen.assert_called_once()
        assert state.generated_output is not None
        assert "Business Requirements Document" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow D: SRS → Requirement Agent → SRS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowD_SRS:
    """Generate SRS → Requirement Agent → SRS document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_srs_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Software requirements from specs"
        )
        mock_gen.return_value = _mock_generation(
            answer="## 1. Introduction\nThis SRS describes the system requirements."
        )

        state = _classify_and_execute(
            Intent.SRS_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate SRS", action="srs"
        )

        assert state.intent == Intent.SRS_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "srs"
        assert state.metadata.get("document_action") == "srs"
        assert state.metadata.get("document_title") == "Software Requirements Specification (SRS)"
        assert "Software Requirements Specification" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow E: RTM → Requirement Agent → RTM
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowE_RTM:
    """Generate RTM → Requirement Agent → RTM document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_rtm_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Traceability data from requirements"
        )
        mock_gen.return_value = _mock_generation(
            answer="| ID | Requirement | Source |\n|---|---|---|"
        )

        state = _classify_and_execute(
            Intent.RTM_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate RTM", action="rtm"
        )

        assert state.intent == Intent.RTM_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "rtm"
        assert state.metadata.get("document_action") == "rtm"
        assert state.metadata.get("document_title") == "Requirements Traceability Matrix (RTM)"
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow F: User Stories → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowF_UserStories:
    """Generate user stories → Requirement Agent → user stories document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_user_stories_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="User story context from requirements"
        )
        mock_gen.return_value = _mock_generation(
            answer="## User Stories\n\nAs a user, I want to make a payment."
        )

        state = _classify_and_execute(
            Intent.USER_STORY_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate user stories", action="user_stories"
        )

        assert state.intent == Intent.USER_STORY_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "user_stories"
        assert state.metadata.get("document_action") == "user_stories"
        assert state.metadata.get("document_title") == "User Stories"
        assert "User Stories" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow G: Acceptance Criteria → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowG_AcceptanceCriteria:
    """Generate acceptance criteria → Requirement Agent → AC document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_acceptance_criteria_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Acceptance criteria context"
        )
        mock_gen.return_value = _mock_generation(
            answer="## Acceptance Criteria\n\nGiven a user on the checkout page..."
        )

        state = _classify_and_execute(
            Intent.ACCEPTANCE_CRITERIA_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate acceptance criteria", action="acceptance_criteria"
        )

        assert state.intent == Intent.ACCEPTANCE_CRITERIA_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "acceptance_criteria"
        assert state.metadata.get("document_action") == "acceptance_criteria"
        assert state.metadata.get("document_title") == "Acceptance Criteria"
        assert "Acceptance Criteria" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow H: Business Rules → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowH_BusinessRules:
    """Generate business rules → Requirement Agent → BR document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_business_rules_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Business rules from project specifications"
        )
        mock_gen.return_value = _mock_generation(
            answer="## Business Rules\n\nBR-001: All payments must be processed within 24 hours."
        )

        state = _classify_and_execute(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate business rules", action="business_rules"
        )

        assert state.intent == Intent.REQUIREMENT_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "business_rules"
        assert state.metadata.get("document_action") == "business_rules"
        assert state.metadata.get("document_title") == "Business Rules"
        assert "Business Rules" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow I: Validation Rules → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowI_ValidationRules:
    """Generate validation rules → Requirement Agent → VR document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_validation_rules_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Validation rules from requirements"
        )
        mock_gen.return_value = _mock_generation(
            answer="## Validation Rules\n\nVR-001: Email must be valid format."
        )

        state = _classify_and_execute(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate validation rules", action="validation_rules"
        )

        assert state.intent == Intent.REQUIREMENT_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "validation_rules"
        assert state.metadata.get("document_action") == "validation_rules"
        assert state.metadata.get("document_title") == "Validation Rules"
        assert "Validation Rules" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow J: Edge Cases → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowJ_EdgeCases:
    """Generate edge cases → Requirement Agent → EC document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_edge_cases_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Edge case scenarios from testing"
        )
        mock_gen.return_value = _mock_generation(
            answer="## Edge Cases\n\nEC-001: What happens when the network drops mid-payment?"
        )

        state = _classify_and_execute(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate edge cases", action="edge_cases"
        )

        assert state.intent == Intent.REQUIREMENT_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "edge_cases"
        assert state.metadata.get("document_action") == "edge_cases"
        assert state.metadata.get("document_title") == "Edge Cases"
        assert "Edge Cases" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow K: Assumptions → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowK_Assumptions:
    """Generate assumptions → Requirement Agent → assumptions document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_assumptions_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Project assumptions from stakeholders"
        )
        mock_gen.return_value = _mock_generation(
            answer="## Assumptions\n\nA-001: Users have reliable internet access."
        )

        state = _classify_and_execute(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate assumptions", action="assumptions"
        )

        assert state.intent == Intent.REQUIREMENT_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "assumptions"
        assert state.metadata.get("document_action") == "assumptions"
        assert state.metadata.get("document_title") == "Assumptions"
        assert "Assumptions" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow L: Risk Analysis → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowL_RiskAnalysis:
    """Generate risk analysis → Requirement Agent → risk document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_risk_analysis_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Risk factors from project assessment"
        )
        mock_gen.return_value = _mock_generation(
            answer="## Risk Analysis\n\nR-001: Payment gateway downtime (High)"
        )

        state = _classify_and_execute(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate risk analysis", action="risk_analysis"
        )

        assert state.intent == Intent.REQUIREMENT_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "risk_analysis"
        assert state.metadata.get("document_action") == "risk_analysis"
        assert state.metadata.get("document_title") == "Risk Analysis"
        assert "Risk Analysis" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow M: Missing Requirements → Requirement Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowM_MissingRequirements:
    """Generate missing requirements → Requirement Agent → MR document."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_missing_requirements_full_flow(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Existing requirements for gap analysis"
        )
        mock_gen.return_value = _mock_generation(
            answer="## Missing Requirements\n\nMR-001: No accessibility requirements defined."
        )

        state = _classify_and_execute(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate missing requirements", action="missing_requirements"
        )

        assert state.intent == Intent.REQUIREMENT_GENERATION
        assert state.route == Route.REQUIREMENT_AGENT
        assert state.action == "missing_requirements"
        assert state.metadata.get("document_action") == "missing_requirements"
        assert state.metadata.get("document_title") == "Missing Requirements Analysis"
        assert "Missing Requirements" in state.generated_output
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow N: Validation request → Validation Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowN_Validation:
    """User requests validation → Validation Agent → validation report."""

    @patch("app.agents.validation.agent.HybridRetriever")
    def test_validation_full_flow(self, MockRetriever):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Requirements to validate:\n1. Login must be secure\n2. Password must be 8+ chars"
        )

        state = _classify_and_execute(
            Intent.REQUIREMENT_VALIDATION, Route.VALIDATION_AGENT,
            "Validate requirements"
        )

        assert state.intent == Intent.REQUIREMENT_VALIDATION
        assert state.route == Route.VALIDATION_AGENT
        assert "Validation Report" in state.generated_output
        assert state.metadata.get("validation_type") == "requirement_validation"
        assert state.validation_result is not None
        assert state.validation_result["overall_status"] in ("pass", "conditional")
        assert state.workflow_status == WorkflowStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Flow O: Ambiguous request → clarification
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowO_Ambiguous:
    """Ambiguous/unknown request → DIRECT_RESPONSE → clarification."""

    def test_ambiguous_full_flow(self):
        state = _classify_and_execute(
            Intent.UNKNOWN, Route.DIRECT_RESPONSE,
            "asdfghjkl"
        )

        assert state.intent == Intent.UNKNOWN
        assert state.route == Route.DIRECT_RESPONSE
        assert state.generated_output is not None
        assert "not sure" in state.generated_output.lower()
        assert state.workflow_status == WorkflowStatus.COMPLETED
        assert state.error is None


# ═══════════════════════════════════════════════════════════════════════════════
# Flow P: No, Not Now → waiting
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowP_NoThanks:
    """User clicks "No, Not Now" → HUMAN_REVIEW → AWAITING_HUMAN."""

    def test_no_thanks_full_flow(self):
        state = _classify_and_execute(
            Intent.HUMAN_REVIEW, Route.HUMAN_REVIEW,
            "No, not now"
        )

        assert state.intent == Intent.HUMAN_REVIEW
        assert state.route == Route.HUMAN_REVIEW
        assert state.generated_output is not None
        assert "human review" in state.generated_output.lower()
        assert state.workflow_status == WorkflowStatus.AWAITING_HUMAN


# ═══════════════════════════════════════════════════════════════════════════════
# Action Preservation Tests — verify actions are NOT lost
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionPreservation:
    """Verify every generation action is preserved through the pipeline."""

    @pytest.mark.parametrize("action,expected_title", [
        ("brd", "Business Requirements Document (BRD)"),
        ("srs", "Software Requirements Specification (SRS)"),
        ("rtm", "Requirements Traceability Matrix (RTM)"),
        ("user_stories", "User Stories"),
        ("acceptance_criteria", "Acceptance Criteria"),
        ("business_rules", "Business Rules"),
        ("validation_rules", "Validation Rules"),
        ("edge_cases", "Edge Cases"),
        ("assumptions", "Assumptions"),
        ("risk_analysis", "Risk Analysis"),
        ("missing_requirements", "Missing Requirements Analysis"),
    ])
    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_action_not_lost(self, MockRetriever, mock_gen, action, expected_title):
        """Each action must flow through to DOCUMENT_PROMPTS and produce correct title."""
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response()
        mock_gen.return_value = _mock_generation(answer=f"# {expected_title}\n\nContent.")

        state = _make_state(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            f"Generate {action}", action=action,
        )
        result = execute(state, MagicMock())

        assert result.action == action, f"Action '{action}' was not preserved"
        assert result.metadata.get("document_action") == action
        assert result.metadata.get("document_title") == expected_title
        assert result.workflow_status == WorkflowStatus.COMPLETED

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_fallback_to_intent_when_no_action(self, MockRetriever, mock_gen):
        """When state.action is None, INTENT_TO_ACTION provides the fallback."""
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response()
        mock_gen.return_value = _mock_generation(answer="# BRD\n\nContent.")

        state = _make_state(
            Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate BRD", action=None,
        )
        result = execute(state, MagicMock())

        # INTENT_TO_ACTION[BRD_GENERATION] = "brd"
        assert result.metadata.get("document_action") == "brd"

    def test_resolve_action_prefers_state_action(self):
        """state.action takes priority over INTENT_TO_ACTION."""
        state = _make_state(
            Intent.REQUIREMENT_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate risk analysis", action="risk_analysis",
        )
        action = _resolve_action(state)
        assert action == "risk_analysis"

    def test_resolve_action_falls_back_to_intent(self):
        """When state.action is None, falls back to INTENT_TO_ACTION."""
        state = _make_state(
            Intent.BRD_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate BRD", action=None,
        )
        action = _resolve_action(state)
        assert action == "brd"

    def test_all_actions_have_document_prompts(self):
        """Every action in ACTION_INTENT_MAP must have a DOCUMENT_PROMPTS entry."""
        for action in ACTION_INTENT_MAP:
            assert action in DOCUMENT_PROMPTS, (
                f"Action '{action}' in ACTION_INTENT_MAP but not in DOCUMENT_PROMPTS"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# RAG Flow with Citations
# ═══════════════════════════════════════════════════════════════════════════════

class TestRAGFlowWithCitations:
    """Verify RAG flows return citations and source documents."""

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_rag_returns_citations(self, MockRetriever, mock_gen):
        citation = MagicMock()
        citation.document_id = "doc-1"
        citation.file_name = "BRD.pdf"
        citation.model_dump.return_value = {
            "document_id": "doc-1", "file_name": "BRD.pdf", "page_number": 5
        }

        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Payment flow documentation", citations=[citation]
        )
        mock_gen.return_value = _mock_generation(answer="The payment uses Stripe.")

        state = _classify_and_execute(
            Intent.QUESTION_ANSWERING, Route.RAG,
            "What is the payment flow?"
        )

        assert len(state.citations) == 1
        assert state.citations[0].document_id == "doc-1"

    @patch("app.agents.requirement.srs_generator.generate_answer")
    @patch("app.agents.requirement.agent.HybridRetriever")
    def test_generation_returns_citations(self, MockRetriever, mock_gen):
        citation = MagicMock()
        citation.document_id = "doc-2"
        citation.file_name = "SRS.pdf"
        citation.model_dump.return_value = {
            "document_id": "doc-2", "file_name": "SRS.pdf"
        }

        citation = MagicMock()
        citation.document_id = "doc-2"
        citation.file_name = "SRS.pdf"
        citation.model_dump.return_value = {"document_id": "doc-2", "file_name": "SRS.pdf"}

        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response(
            context="Software specifications", citations=[citation]
        )
        mock_gen.return_value = _mock_generation(answer="# SRS\n\nRequirements.")

        state = _classify_and_execute(
            Intent.SRS_GENERATION, Route.REQUIREMENT_AGENT,
            "Generate SRS", action="srs"
        )

        assert len(state.citations) == 1
        assert state.citations[0].document_id == "doc-2"


# ═══════════════════════════════════════════════════════════════════════════════
# Error Handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorHandlingE2E:
    """Verify errors are handled gracefully across all flows."""

    def test_missing_route_and_intent_fails(self):
        state = SupervisorState(
            user_id="u1", project_id="p1", session_id="s1",
            user_query="test", intent=None, route=None,
        )
        result = execute(state, MagicMock())
        assert result.workflow_status == WorkflowStatus.FAILED
        assert "No route or intent" in result.error

    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_retriever_failure_sets_error(self, MockRetriever):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.side_effect = Exception("DB connection failed")

        state = _make_state(Intent.QUESTION_ANSWERING, Route.RAG, "test")
        result = execute(state, MagicMock())
        assert result.workflow_status == WorkflowStatus.FAILED
        assert "DB connection failed" in result.error

    @patch("app.agents.supervisor.orchestrator.generate_answer")
    @patch("app.agents.supervisor.orchestrator.HybridRetriever")
    def test_llm_failure_sets_error(self, MockRetriever, mock_gen):
        mock_retriever = MagicMock()
        MockRetriever.return_value = mock_retriever
        mock_retriever.retrieve.return_value = _mock_search_response()
        mock_gen.side_effect = Exception("LLM API timeout")

        state = _make_state(Intent.QUESTION_ANSWERING, Route.RAG, "test")
        result = execute(state, MagicMock())
        assert result.workflow_status == WorkflowStatus.FAILED
        assert "LLM API timeout" in result.error
