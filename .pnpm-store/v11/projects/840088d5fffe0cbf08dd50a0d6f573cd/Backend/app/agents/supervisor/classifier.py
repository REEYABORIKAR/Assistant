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
import re
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
    Intent.PROJECT_CONTEXT,
    Intent.REQUIREMENT_GENERATION,
    Intent.USER_STORY_GENERATION,
    Intent.ACCEPTANCE_CRITERIA_GENERATION,
    Intent.BRD_GENERATION,
    Intent.SRS_GENERATION,
    Intent.RTM_GENERATION,
}


# ── Document-Keyword Pre-check ────────────────────────────────────────────────
# Regex patterns that strongly indicate a document-related query.
# Used as a safety net: if the query matches these patterns, we ensure
# it routes to RAG even if the LLM misclassifies it.

_DOCUMENT_QUERY_PATTERNS: list[re.Pattern] = [
    # "What does the document say about X?"
    re.compile(r"what(?:'s| is| does| are| do)\b.{0,30}(?:document|file|upload)", re.IGNORECASE),
    # "Summarize my uploaded document"
    re.compile(r"summar(?:ize|ise|y|izing)\b.{0,30}(?:document|file|upload)", re.IGNORECASE),
    # "What are the main requirements in my uploaded document?"
    re.compile(r"(?:main |key |primary )?requirements?\b.{0,30}(?:document|file|upload|my)", re.IGNORECASE),
    # "What requirements are mentioned in the document?"
    re.compile(r"requirements?\b.{0,20}mentioned?.{0,20}(?:document|file|upload)", re.IGNORECASE),
    # General "in the document" / "from the document" / "about the document"
    re.compile(r"(?:in|from|about|within|regarding)\b.{0,15}(?:the|my|this|uploaded)\s+document", re.IGNORECASE),
    # "Search the document for X" / "Find X in the document"
    re.compile(r"(?:search|find|look|check|scan)\b.{0,30}(?:document|file|upload)", re.IGNORECASE),
    # "What is in the document" / "Tell me about the document"
    re.compile(r"(?:what is|what's|tell me|explain|describe)\b.{0,20}(?:document|file|upload)", re.IGNORECASE),
    # Direct document reference with question words
    re.compile(r"(?:how|why|when|where|who|which)\b.{0,30}(?:document|file|upload)", re.IGNORECASE),
    # References to "the spec" / "the specification"
    re.compile(r"(?:the|this|my)\s+(?:spec|specification|requirements?\s+doc)", re.IGNORECASE),
    # "Where are the X requirements?" (implicit document reference)
    re.compile(r"where\s+(?:are|is|can|do)\b.{0,30}requirements?", re.IGNORECASE),
    # "What are the X requirements?" without explicit document mention
    re.compile(r"what\s+(?:are|is|does|do)\b.{0,40}requirements?\b", re.IGNORECASE),
]

# Strong signals that the query is about document content
_DOCUMENT_CONTENT_KEYWORDS = re.compile(
    r"\b(?:document|file|upload(?:ed)?)\b.{0,40}\b(?:requirement|specification|auth(?:entication)?|payment|login|system|feature|workflow|process|rule|policy|constraint|interface|api|database|security|performance|integration)\b",
    re.IGNORECASE,
)


# ── Classification Prompt ──────────────────────────────────────────────────────

_INTENT_LIST = ", ".join(i.value for i in Intent)
_ROUTE_LIST = ", ".join(r.value for r in Route)

# Fallback models if the primary model is unavailable (e.g., 404, access denied)
_FALLBACK_MODELS = ["qwen/qwen3.6-27b", "openai/gpt-oss-20b"]

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
- project_context → rag
- unknown → unknown

INTENT DEFINITIONS (important distinctions):

- document_search: Finding or locating specific content, keywords, patterns, or sections in uploaded documents.
  ALWAYS use this for queries that SEARCH, FIND, or LOCATE content in documents.
  Examples:
    "Search for login requirements"
    "Find all payment references"
    "Search my BRD for authentication"
    "Where are the security requirements?"
    "Look for error handling in the document"
    "What are the main requirements in my uploaded document?"
    "What requirements are mentioned in the document?"

- question_answering: Asking questions about the MEANING, CONTENT, or DETAILS of uploaded documents.
  ALWAYS use this for queries that ASK, EXPLAIN, DESCRIBE, or SUMMARIZE document content.
  Examples:
    "What does the document say about payment?"
    "How does authentication work according to the spec?"
    "Explain the refund policy from the document"
    "Summarize my uploaded document"
    "What does the document say about authentication?"
    "Tell me about the system architecture in the document"
    "What are the key features described in the document?"
    "How is user registration handled?"

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
- true if the query references, searches, asks about, or needs content from uploaded documents
- false for greetings, validation-only, revision without context, or general chat
- When in doubt about whether documents are needed, set to true

CRITICAL: If the query mentions "document", "file", "uploaded", or asks about content that would be in a requirements document, it MUST be classified as document_search or question_answering with requires_rag=true.

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


def _is_document_query(user_query: str) -> bool:
    """
    Quick keyword-based check for document-related queries.

    Returns True if the query clearly references document content,
    serving as a safety net for cases where the LLM might misclassify.
    """
    for pattern in _DOCUMENT_QUERY_PATTERNS:
        if pattern.search(user_query):
            return True
    if _DOCUMENT_CONTENT_KEYWORDS.search(user_query):
        return True
    return False


def _parse_classification(raw: str) -> ClassificationResult:
    """
    Parse LLM JSON output into ClassificationResult.
    Handles common LLM formatting issues including chain-of-thought blocks.
    """
    text = raw.strip()

    # Strip <think>...</think> blocks (Qwen and similar models)
    # Handle both closed and unclosed think blocks (truncated responses)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # If there's an unclosed <think> block, strip everything from it onward
    if "<think>" in text:
        text = text[:text.index("<think>")].strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try to extract JSON object from the text (may have trailing text)
    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

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
    # Quick keyword pre-check for document-related queries
    is_doc_query = _is_document_query(user_query)

    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not configured, returning UNKNOWN")
        # If keywords indicate a document query, still route to RAG
        if is_doc_query:
            logger.info(f"Document query detected (no LLM): {user_query[:80]}")
            return ClassificationResult(
                intent=Intent.QUESTION_ANSWERING,
                route=Route.RAG,
                requires_rag=True,
                confidence=0.7,
                reasoning="Document query detected via keyword matching (LLM not configured)",
            )
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

        # Try primary model, then fallbacks if it fails with a model-related error
        models_to_try = [effective_model] + [
            m for m in _FALLBACK_MODELS if m != effective_model
        ]
        last_error = None

        for model_name in models_to_try:
            try:
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,  # Deterministic classification
                    max_tokens=1024,
                )
                raw = completion.choices[0].message.content.strip()
                result = _parse_classification(raw)
                logger.info(
                    f"Classified query with model '{model_name}': "
                    f"intent={result.intent.value}, confidence={result.confidence:.2f}"
                )
                break  # Success — exit the retry loop
            except Exception as model_error:
                last_error = model_error
                error_str = str(model_error)
                # Only retry on model-not-found or access errors (404/403)
                if "404" in error_str or "model_not_found" in error_str or "403" in error_str:
                    logger.warning(
                        f"Model '{model_name}' unavailable: {model_error}. "
                        f"Trying next fallback model."
                    )
                    continue
                # For other errors (rate limit, auth, network), don't retry
                raise
        else:
            # All models failed — raise the last error to be caught below
            raise last_error

        # Safety net: if keyword check detected a document query but LLM
        # misclassified it, override to QUESTION_ANSWERING with RAG
        if is_doc_query and result.intent not in (
            Intent.DOCUMENT_SEARCH,
            Intent.QUESTION_ANSWERING,
            Intent.PROJECT_CONTEXT,
            Intent.DOCUMENT_INGESTION,
        ):
            logger.info(
                f"Keyword pre-check detected document query but LLM classified as "
                f"{result.intent.value}. Overriding to question_answering."
            )
            result = ClassificationResult(
                intent=Intent.QUESTION_ANSWERING,
                route=Route.RAG,
                requires_rag=True,
                confidence=max(result.confidence, 0.7),
                reasoning=f"Override: keyword pre-check detected document query "
                         f"(LLM said {result.intent.value})",
            )

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
        # Safety net: if keywords indicate a document query, still route to RAG
        # even when the LLM call fails (e.g., API error, model not found).
        if is_doc_query:
            logger.warning(
                f"LLM classification failed but keyword pre-check detected document "
                f"query. Routing to question_answering with RAG. Error: {e}"
            )
            return ClassificationResult(
                intent=Intent.QUESTION_ANSWERING,
                route=Route.RAG,
                requires_rag=True,
                confidence=0.6,
                reasoning=f"LLM failed ({type(e).__name__}), keyword pre-check "
                         f"detected document query",
            )
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
