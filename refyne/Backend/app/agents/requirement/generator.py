"""
Core Requirement Generator.

Uses LLM to generate structured requirements from retrieved context.
Parses LLM output into structured Requirement objects.
"""
import json
import logging
import re

from app.agents.requirement.schema import (
    AcceptanceCriterion,
    GenerationPlan,
    Priority,
    Requirement,
)
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)


def _parse_requirements_json(raw: str) -> list[dict]:
    """Parse LLM JSON output into a list of requirement dicts."""
    text = raw.strip()

    # Strip code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try to extract JSON array
    array_match = re.search(r"\[.*\]", text, re.DOTALL)
    if array_match:
        text = array_match.group(0)

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Handle wrapped response like {"requirements": [...]}
            for key in ("requirements", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse requirements JSON: {text[:200]}")
    return []


def _normalize_requirement(raw: dict, index: int) -> Requirement:
    """Convert a raw dict from LLM into a Requirement object."""
    req_id = raw.get("id", f"FR-{index + 1:03d}")
    title = raw.get("title", raw.get("name", f"Requirement {index + 1}"))
    description = raw.get("description", raw.get("detail", ""))

    priority_str = raw.get("priority", "MEDIUM").upper()
    try:
        priority = Priority(priority_str)
    except ValueError:
        priority = Priority.MEDIUM

    actor = raw.get("actor", raw.get("stakeholder", ""))
    preconditions = raw.get("preconditions", raw.get("prerequisites", []))
    if isinstance(preconditions, str):
        preconditions = [p.strip() for p in preconditions.split(",") if p.strip()]

    source_citations = raw.get("source_citations", raw.get("citations", []))

    # Parse acceptance criteria
    ac_list = raw.get("acceptance_criteria", raw.get("acceptance", []))
    acceptance_criteria = []
    for i, ac in enumerate(ac_list):
        if isinstance(ac, str):
            acceptance_criteria.append(
                AcceptanceCriterion(
                    id=f"AC-{req_id}-{i + 1:03d}",
                    given=ac,
                    when="",
                    then="",
                )
            )
        elif isinstance(ac, dict):
            acceptance_criteria.append(
                AcceptanceCriterion(
                    id=ac.get("id", f"AC-{req_id}-{i + 1:03d}"),
                    given=ac.get("given", ac.get("precondition", "")),
                    when=ac.get("when", ac.get("action", "")),
                    then=ac.get("then", ac.get("expected", ac.get("outcome", ""))),
                )
            )

    return Requirement(
        id=req_id,
        title=str(title),
        description=str(description),
        priority=priority,
        actor=str(actor),
        preconditions=preconditions,
        acceptance_criteria=acceptance_criteria,
        source_citations=source_citations,
    )


def generate_requirements(
    plan: GenerationPlan,
    context: str,
    citations: list | None = None,
) -> list[Requirement]:
    """
    Generate structured requirements using LLM.

    Args:
        plan: The generation plan with prompt and config.
        context: Retrieved context from RAG.
        citations: Source citations.

    Returns:
        List of structured Requirement objects.
    """
    structured_prompt = (
        f"{plan.prompt}\n\n"
        "IMPORTANT: Return your output as a JSON array of requirement objects. "
        "Each object must have: id, title, description, priority (HIGH/MEDIUM/LOW), "
        "actor, preconditions (array of strings), acceptance_criteria (array of objects "
        "with id, given, when, then), source_citations (array of strings). "
        "Return ONLY the JSON array, no other text."
    )

    generation = generate_answer(
        query=structured_prompt,
        context=context,
        citations=citations,
    )

    if not generation["configured"] or not generation["answer"]:
        logger.warning("LLM not configured or no answer generated for requirements")
        return []

    raw_requirements = _parse_requirements_json(generation["answer"])
    requirements = [_normalize_requirement(r, i) for i, r in enumerate(raw_requirements)]

    logger.info(f"Generated {len(requirements)} structured requirements")
    return requirements


def generate_requirements_fallback(context: str) -> list[Requirement]:
    """
    Fallback requirement generation when LLM is unavailable.
    Extracts basic requirement structure from context text.
    """
    if not context:
        return []

    # Create a single requirement from the context
    return [
        Requirement(
            id="FR-001",
            title="Extracted Requirement",
            description=context[:500],
            priority=Priority.MEDIUM,
            source_citations=[],
        )
    ]
