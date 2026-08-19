"""
BRD (Business Requirements Document) Generator.

Generates structured BRD content from retrieved context.
"""
import json
import logging
import re
from typing import Optional

from app.agents.requirement.schema import (
    BRDDocument,
    GenerationPlan,
    Requirement,
)
from app.agents.requirement.generator import _normalize_requirement
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)


def _parse_brd_json(raw: str) -> dict:
    """Parse LLM JSON output into a BRD structure dict."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try to extract JSON object
    object_match = re.search(r"\{.*\}", text, re.DOTALL)
    if object_match:
        text = object_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse BRD JSON: {text[:200]}")
        return {}


def generate_brd(
    plan: GenerationPlan,
    context: str,
    citations: Optional[list] = None,
) -> BRDDocument:
    """
    Generate a structured BRD from context.

    Returns:
        BRDDocument with all sections populated.
    """
    structured_prompt = (
        f"{plan.prompt}\n\n"
        "IMPORTANT: Return your output as a JSON object with these fields: "
        "executive_summary (string), business_objectives (array of strings), "
        "scope (string), stakeholders (array of strings), "
        "business_requirements (array of objects with id, title, description, priority, actor), "
        "functional_requirements (array of objects with id, title, description, priority, actor), "
        "non_functional_requirements (array of objects with id, title, description, priority, actor), "
        "assumptions_and_constraints (array of strings), success_criteria (array of strings). "
        "Return ONLY the JSON object, no other text."
    )

    generation = generate_answer(
        query=structured_prompt,
        context=context,
        citations=citations,
    )

    brd = BRDDocument(title=plan.title)

    if not generation["configured"] or not generation["answer"]:
        logger.warning("LLM not configured for BRD generation")
        return brd

    raw = _parse_brd_json(generation["answer"])
    if not raw:
        return brd

    brd.executive_summary = raw.get("executive_summary", "")
    brd.business_objectives = raw.get("business_objectives", [])
    brd.scope = raw.get("scope", "")
    brd.stakeholders = raw.get("stakeholders", [])
    brd.assumptions_and_constraints = raw.get("assumptions_and_constraints", [])
    brd.success_criteria = raw.get("success_criteria", [])

    for i, req in enumerate(raw.get("business_requirements", [])):
        brd.business_requirements.append(_normalize_requirement(req, i))
    for i, req in enumerate(raw.get("functional_requirements", [])):
        brd.functional_requirements.append(_normalize_requirement(req, i))
    for i, req in enumerate(raw.get("non_functional_requirements", [])):
        brd.non_functional_requirements.append(_normalize_requirement(req, i))

    logger.info(
        f"Generated BRD: {len(brd.business_requirements)} business, "
        f"{len(brd.functional_requirements)} functional, "
        f"{len(brd.non_functional_requirements)} non-functional requirements"
    )
    return brd
