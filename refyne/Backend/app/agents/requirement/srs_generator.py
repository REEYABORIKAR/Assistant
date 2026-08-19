"""
SRS (Software Requirements Specification) Generator.

Generates structured SRS content from retrieved context.
"""
import json
import logging
import re
from typing import Optional

from app.agents.requirement.schema import (
    GenerationPlan,
    Requirement,
    SRSDocument,
)
from app.agents.requirement.generator import _normalize_requirement
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)


def _parse_srs_json(raw: str) -> dict:
    """Parse LLM JSON output into an SRS structure dict."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    object_match = re.search(r"\{.*\}", text, re.DOTALL)
    if object_match:
        text = object_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse SRS JSON: {text[:200]}")
        return {}


def generate_srs(
    plan: GenerationPlan,
    context: str,
    citations: Optional[list] = None,
) -> SRSDocument:
    """
    Generate a structured SRS from context.

    Returns:
        SRSDocument with all sections populated.
    """
    structured_prompt = (
        f"{plan.prompt}\n\n"
        "IMPORTANT: Return your output as a JSON object with these fields: "
        "introduction (object with purpose, scope, definitions), "
        "overall_description (object with perspective, functions, characteristics, constraints), "
        "functional_requirements (array of objects with id, title, description, priority, actor), "
        "external_interface_requirements (array of objects with id, title, description, priority), "
        "performance_requirements (array of objects with id, title, description, priority), "
        "verification_and_validation (array of strings). "
        "Return ONLY the JSON object, no other text."
    )

    generation = generate_answer(
        query=structured_prompt,
        context=context,
        citations=citations,
    )

    srs = SRSDocument(title=plan.title)

    if not generation["configured"] or not generation["answer"]:
        logger.warning("LLM not configured for SRS generation")
        return srs

    raw = _parse_srs_json(generation["answer"])
    if not raw:
        return srs

    srs.introduction = raw.get("introduction", {})
    srs.overall_description = raw.get("overall_description", {})
    srs.verification_and_validation = raw.get("verification_and_validation", [])

    for i, req in enumerate(raw.get("functional_requirements", [])):
        srs.functional_requirements.append(_normalize_requirement(req, i))
    for i, req in enumerate(raw.get("external_interface_requirements", [])):
        srs.external_interface_requirements.append(_normalize_requirement(req, i))
    for i, req in enumerate(raw.get("performance_requirements", [])):
        srs.performance_requirements.append(_normalize_requirement(req, i))

    logger.info(
        f"Generated SRS: {len(srs.functional_requirements)} functional, "
        f"{len(srs.external_interface_requirements)} interface, "
        f"{len(srs.performance_requirements)} performance requirements"
    )
    return srs
