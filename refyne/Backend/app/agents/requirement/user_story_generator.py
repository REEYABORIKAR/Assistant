"""
User Story Generator.

Generates structured user stories from retrieved context using LLM.
"""
import json
import logging
import re
from typing import Optional

from app.agents.requirement.schema import (
    AcceptanceCriterion,
    GenerationPlan,
    Priority,
    UserStory,
)
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)


def _parse_stories_json(raw: str) -> list[dict]:
    """Parse LLM JSON output into a list of user story dicts."""
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
            for key in ("stories", "user_stories", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse user stories JSON: {text[:200]}")
    return []


def _normalize_story(raw: dict, index: int) -> UserStory:
    """Convert a raw dict from LLM into a UserStory object."""
    story_id = raw.get("id", f"US-{index + 1:03d}")
    title = raw.get("title", raw.get("name", f"User Story {index + 1}"))

    role = raw.get("role", raw.get("actor", ""))
    feature = raw.get("feature", raw.get("description", raw.get("want", "")))
    benefit = raw.get("benefit", raw.get("so_that", raw.get("goal", "")))

    priority_str = raw.get("priority", "MEDIUM").upper()
    try:
        priority = Priority(priority_str)
    except ValueError:
        priority = Priority.MEDIUM

    story_points = raw.get("story_points", raw.get("points"))
    if story_points is not None:
        try:
            story_points = int(story_points)
        except (ValueError, TypeError):
            story_points = None

    epic = raw.get("epic", None)
    source_citations = raw.get("source_citations", raw.get("citations", []))

    ac_list = raw.get("acceptance_criteria", raw.get("acceptance", []))
    acceptance_criteria = []
    for i, ac in enumerate(ac_list):
        if isinstance(ac, str):
            acceptance_criteria.append(
                AcceptanceCriterion(
                    id=f"AC-{story_id}-{i + 1:03d}",
                    given=ac,
                    when="",
                    then="",
                )
            )
        elif isinstance(ac, dict):
            acceptance_criteria.append(
                AcceptanceCriterion(
                    id=ac.get("id", f"AC-{story_id}-{i + 1:03d}"),
                    given=ac.get("given", ac.get("precondition", "")),
                    when=ac.get("when", ac.get("action", "")),
                    then=ac.get("then", ac.get("expected", ac.get("outcome", ""))),
                )
            )

    return UserStory(
        id=story_id,
        title=str(title),
        role=str(role),
        feature=str(feature),
        benefit=str(benefit),
        priority=priority,
        story_points=story_points,
        acceptance_criteria=acceptance_criteria,
        epic=epic,
        source_citations=source_citations,
    )


def generate_user_stories(
    plan: GenerationPlan,
    context: str,
    citations: Optional[list] = None,
) -> list[UserStory]:
    """
    Generate structured user stories using LLM.

    Returns:
        List of structured UserStory objects.
    """
    structured_prompt = (
        f"{plan.prompt}\n\n"
        "IMPORTANT: Return your output as a JSON array of user story objects. "
        "Each object must have: id, title, role, feature, benefit, priority (HIGH/MEDIUM/LOW), "
        "story_points (1-13), acceptance_criteria (array of objects with id, given, when, then), "
        "epic (optional). Return ONLY the JSON array, no other text."
    )

    generation = generate_answer(
        query=structured_prompt,
        context=context,
        citations=citations,
    )

    if not generation["configured"] or not generation["answer"]:
        logger.warning("LLM not configured or no answer for user stories")
        return []

    raw_stories = _parse_stories_json(generation["answer"])
    stories = [_normalize_story(s, i) for i, s in enumerate(raw_stories)]

    logger.info(f"Generated {len(stories)} structured user stories")
    return stories
