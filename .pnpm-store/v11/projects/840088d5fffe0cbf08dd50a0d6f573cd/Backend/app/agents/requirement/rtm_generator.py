"""
RTM (Requirements Traceability Matrix) Generator.

Generates structured RTM content from retrieved context.
"""
import json
import logging
import re
from typing import Any, Optional

from app.agents.requirement.schema import (
    GenerationPlan,
    RTMDocument,
)
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)


def _parse_rtm_json(raw: str) -> list[dict]:
    """Parse LLM JSON output into RTM rows."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    array_match = re.search(r"\[.*\]", text, re.DOTALL)
    if array_match:
        text = array_match.group(0)

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("rows", "traceability", "matrix", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse RTM JSON: {text[:200]}")
    return []


def generate_rtm(
    plan: GenerationPlan,
    context: str,
    citations: Optional[list] = None,
) -> RTMDocument:
    """
    Generate a structured RTM from context.

    Returns:
        RTMDocument with rows populated.
    """
    structured_prompt = (
        f"{plan.prompt}\n\n"
        "IMPORTANT: Return your output as a JSON array of row objects. "
        "Each object must have: requirement_id, description, source, priority, "
        "test_case, status, dependencies (array of requirement IDs). "
        "Return ONLY the JSON array, no other text."
    )

    generation = generate_answer(
        query=structured_prompt,
        context=context,
        citations=citations,
    )

    rtm = RTMDocument(title=plan.title)

    if not generation["configured"] or not generation["answer"]:
        logger.warning("LLM not configured for RTM generation")
        return rtm

    raw_rows = _parse_rtm_json(generation["answer"])
    rtm.rows = raw_rows

    logger.info(f"Generated RTM with {len(rtm.rows)} traceability rows")
    return rtm
