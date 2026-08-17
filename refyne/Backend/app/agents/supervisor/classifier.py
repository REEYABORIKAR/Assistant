"""
Supervisor Intent Classifier.

Classifies user queries into one of the predefined intents and routes
using the project's existing Groq LLM configuration. Returns structured
output with confidence scores. No chain-of-thought is exposed.

The classifier does NOT execute routes — it only determines what the
user wants and where it should go.
"""
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.supervisor.state import Intent, Route, SupervisorState
from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Structured Output Schema ───────────────────────────────────────────────────

class ClassificationResult(BaseModel):
    """
    Structured output from the LLM classifier.
    Uses constrained values so the LLM can only pick valid options.
    """
    intent: Intent = Field(..., description="Classified user intent")
    route: Route = Field(..., description="Agent route to dispatch to")
    requires_rag: bool = Field(..., description="Whether document retrieval is needed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence 0.0-1.0")
    reasoning: str = Field(default="", description="Brief reasoning (not exposed to user)")


# ── Intent-to-Route Mapping ───────────────────────────────────────────────────
# Canonical mapping from intent to route. The LLM proposes, this map enforces.

INTENT_ROUTE_MAP: dict[Intent, Route] = {
    Intent.DOCUMENT_INGESTION: Route.DOCUMENT_AGENT,
    Intent.DOCUMENT_SEARCH: Route.RAG,
    Intent.QUESTION_ANSWERING: Route.RAG,
    Intent.REQUIREMENT_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.USER_STORY_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.ACCEPTANCE_CRITERIA_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.BRD_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.SRS_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.RTM_GENERATION: Route.REQUIREMENT_AGENT,
    Intent.REQUIREMENT_VALIDATION: Route.VALIDATION_AGENT,
    Intent.HUMAN_REVIEW: Route.HUMAN_REVIEW,
    Intent.REVISION: Route.REQUIREMENT_AGENT,
    Intent.PROJECT_CONTEXT: Route.RAG,
    Intent.UNKNOWN: Route.UNKNOWN,
}

# Intents that inherently require RAG retrieval
RAG_REQUIRED_INTENTS: set[Intent] = {
    Intent.DOCUMENT_SEARCH,
    Intent.QUESTION_ANSWERING,
    Intent.REQUIREMENT_GENERATION,
    Intent.USER_STORY_GENERATION,
    Intent.ACCEPTANCE_CRITERIA_GENERATION,
    Intent.BRD_GENERATION,
    Intent.SRS_GENERATION,
    Intent.RTM_GENERATION,
}


# ── Classification Prompt ──────────────────────────────────────────────────────

_INTENT_LIST = ", ".join(i.value for i in Intent)
_ROUTE_LIST = ", ".join(r.value for r in Route)

_SYSTEM_PROMPT = f"""You are the Supervisor Agent for Refyne, a requirements engineering platform.

Your ONLY job is to classify the user's query into exactly one intent and route.
You must respond with a single JSON object — no other text.

VALID INTENTS (pick exactly one):
{_INTENT_LIST}

VALID ROUTES (pick exactly one):
{_ROUTE_LIST}

INTENT-TO-ROUTE RULES:
- document_ingestion → document_agent
- document_search → rag
- question_answering → rag
- requirement_generation → requirement_agent
- user_story_generation → requirement_agent
- acceptance_criteria_generation → requirement_agent
- brd_generation → requirement_agent
- srs_generation → requirement_agent
- rtm_generation → requirement_agent
- requirement_validation → validation_agent
- human_review → human_review
- revision → requirement_agent
- project_context → direct_response
- unknown → unknown

INTENT DEFINITIONS (important distinctions):
- document_search: Finding specific content, keywords, or patterns in documents
  Examples: "Search for login requirements", "Find all payment references", "Search my BRD for auth"
- question_answering: Asking questions about document content or meaning
  Examples: "What does the document say about payment?", "How does authentication work?", "Explain the refund policy"
- requirement_generation: Generating generic/functional requirements (not a specific document type)
  Examples: "Generate functional requirements for login", "Write requirements for checkout"
- user_story_generation: Creating user stories specifically
  Examples: "Create user stories for checkout", "Write user stories for the payment flow"
- brd_generation: Generating a Business Requirements Document
  Examples: "Generate a BRD", "Create a BRD for the payment module"
- srs_generation: Generating a Software Requirements Specification
  Examples: "Create an SRS document", "Generate SRS for the API"
- rtm_generation: Generating a Requirements Traceability Matrix
  Examples: "Create an RTM", "Generate traceability matrix"

REQUIRES_RAG RULES:
- true if the query references, searches, or needs content from uploaded documents
- false for greetings, validation-only, revision without context, or general chat

CONFIDENCE:
- 0.9-1.0: Query clearly matches one intent
- 0.7-0.89: Likely match but some ambiguity
- 0.5-0.69: Ambiguous, could be multiple intents
- below 0.5: Too unclear, use "unknown"

OUTPUT FORMAT (JSON only, no markdown):
{{"intent": "...", "route": "...", "requires_rag": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""


def _build_user_prompt(
    user_query: str,
    project_id: str,
    conversation_context: Optional[str] = None,
) -> str:
    """Build the user message for classification."""
    parts = [f"User query: {user_query}", f"Project ID: {project_id}"]
    if conversation_context:
        parts.append(f"Conversation context: {conversation_context}")
    return "\n".join(parts)


def _parse_classification(raw: str) -> ClassificationResult:
    """
    Parse LLM JSON output into ClassificationResult.
    Handles common LLM formatting issues.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse classifier JSON: {e}\nRaw: {raw[:500]}")
        return ClassificationResult(
            intent=Intent.UNKNOWN,
            route=Route.UNKNOWN,
            requires_rag=False,
            confidence=0.0,
            reasoning=f"JSON parse error: {e}",
        )

    try:
        intent = Intent(data["intent"])
    except (KeyError, ValueError):
        logger.warning(f"Invalid intent in LLM output: {data.get('intent')}")
        intent = Intent.UNKNOWN

    # Enforce canonical route mapping (ignore LLM's route if mismatched)
    route = INTENT_ROUTE_MAP[intent]

    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))

    requires_rag = bool(data.get("requires_rag", False))
    # Override: if intent inherently needs RAG, force it
    if intent in RAG_REQUIRED_INTENTS:
        requires_rag = True

    reasoning = data.get("reasoning", "")

    return ClassificationResult(
        intent=intent,
        route=route,
        requires_rag=requires_rag,
        confidence=confidence,
        reasoning=reasoning,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def classify_intent(
    user_query: str,
    project_id: str,
    conversation_context: Optional[str] = None,
    confidence_threshold: float = 0.5,
    model: Optional[str] = None,
) -> ClassificationResult:
    """
    Classify a user query into an intent and route.

    Args:
        user_query: The raw user input.
        project_id: Active project ID for context.
        conversation_context: Optional prior conversation context.
        confidence_threshold: Minimum confidence to accept classification.
                              Below this threshold, returns UNKNOWN.
        model: Optional LLM model override.

    Returns:
        ClassificationResult with intent, route, requires_rag, confidence.
    """
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not configured, returning UNKNOWN")
        return ClassificationResult(
            intent=Intent.UNKNOWN,
            route=Route.UNKNOWN,
            requires_rag=False,
            confidence=0.0,
            reasoning="LLM not configured",
        )

    effective_model = model or settings.GROQ_MODEL
    user_prompt = _build_user_prompt(user_query, project_id, conversation_context)

    try:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=effective_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,  # Deterministic classification
            max_tokens=256,
        )
        raw = completion.choices[0].message.content.strip()
        result = _parse_classification(raw)

        # Apply confidence threshold
        if result.confidence < confidence_threshold:
            logger.info(
                f"Low confidence ({result.confidence:.2f} < {confidence_threshold}) "
                f"for query: {user_query[:80]}. Falling back to UNKNOWN."
            )
            return ClassificationResult(
                intent=Intent.UNKNOWN,
                route=Route.UNKNOWN,
                requires_rag=False,
                confidence=result.confidence,
                reasoning=f"Below confidence threshold ({result.confidence:.2f} < {confidence_threshold})",
            )

        return result

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        return ClassificationResult(
            intent=Intent.UNKNOWN,
            route=Route.UNKNOWN,
            requires_rag=False,
            confidence=0.0,
            reasoning=f"Classification error: {str(e)[:200]}",
        )


def classify_and_update_state(
    state: SupervisorState,
    confidence_threshold: float = 0.5,
    model: Optional[str] = None,
) -> SupervisorState:
    """
    Classify the user query and update the state in-place.
    Convenience wrapper around classify_intent().

    Returns the updated state.
    """
    result = classify_intent(
        user_query=state.user_query,
        project_id=state.project_id,
        confidence_threshold=confidence_threshold,
        model=model,
    )

    state.intent = result.intent
    state.route = result.route
    state.requires_rag = result.requires_rag
    state.metadata["classification_confidence"] = result.confidence
    state.metadata["classification_reasoning"] = result.reasoning

    return state
