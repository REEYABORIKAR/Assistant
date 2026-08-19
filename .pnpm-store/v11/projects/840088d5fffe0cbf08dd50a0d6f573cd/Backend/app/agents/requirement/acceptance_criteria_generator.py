"""
Acceptance Criteria Generator.

Generates structured acceptance criteria from retrieved context using LLM.
"""
import json
import logging
import re
from typing import Optional

from app.agents.requirement.schema import (
    AcceptanceCriterion,
    GenerationPlan,
)
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)


def _parse_criteria_json(raw: str) -> list[dict]:
    """Parse LLM JSON output into a list of acceptance criteria dicts."""
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
            for key in ("criteria", "acceptance_criteria", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse acceptance criteria JSON: {text[:200]}")
    return []


def _normalize_criterion(raw: dict, index: int) -> AcceptanceCriterion:
    """Convert a raw dict from LLM into an AcceptanceCriterion object."""
    ac_id = raw.get("id", f"AC-{index + 1:03d}")
    given = raw.get("given", raw.get("precondition", raw.get("context", "")))
    when = raw.get("when", raw.get("action", raw.get("trigger", "")))
    then = raw.get("then", raw.get("expected", raw.get("outcome", raw.get("result", ""))))

    return AcceptanceCriterion(
        id=str(ac_id),
        given=str(given),
        when=str(when),
        then=str(then),
    )


def generate_acceptance_criteria(
    plan: GenerationPlan,
    context: str,
    citations: Optional[list] = None,
) -> list[AcceptanceCriterion]:
    """
    Generate structured acceptance criteria using LLM.

    Returns:
        List of structured AcceptanceCriterion objects.
    """
    structured_prompt = (
        f"{plan.prompt}\n\n"
        "IMPORTANT: Return your output as a JSON array of acceptance criterion objects. "
        "Each object must have: id, given (precondition), when (action), then (expected outcome). "
        "Return ONLY the JSON array, no other text."
    )

    generation = generate_answer(
        query=structured_prompt,
        context=context,
        citations=citations,
    )

    if not generation["configured"] or not generation["answer"]:
        logger.warning("LLM not configured or no answer for acceptance criteria")
        return []

    raw_criteria = _parse_criteria_json(generation["answer"])
    criteria = [_normalize_criterion(c, i) for i, c in enumerate(raw_criteria)]

    logger.info(f"Generated {len(criteria)} acceptance criteria")
    return criteria
