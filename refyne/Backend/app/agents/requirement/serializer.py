"""
Requirement Agent Serializer.

Converts structured requirement objects into markdown for frontend compatibility.
The frontend expects `content: string` as markdown text, so this module bridges
the gap between internal structured JSON and the external API shape.
"""

from app.agents.requirement.schema import (
    AcceptanceCriterion,
    BRDDocument,
    Requirement,
    RTMDocument,
    SRSDocument,
    UserStory,
)


def _format_acceptance_criteria(criteria: list[AcceptanceCriterion], indent: str = "  ") -> str:
    """Format acceptance criteria as markdown list."""
    if not criteria:
        return ""
    lines = [f"{indent}**Acceptance Criteria:**"]
    for ac in criteria:
        if ac.given or ac.when or ac.then:
            parts = []
            if ac.given:
                parts.append(f"**Given** {ac.given}")
            if ac.when:
                parts.append(f"**When** {ac.when}")
            if ac.then:
                parts.append(f"**Then** {ac.then}")
            lines.append(f"{indent}- {(' — ').join(parts)}")
        else:
            lines.append(f"{indent}- {ac.id}")
    return "\n".join(lines)


def serialize_requirement(req: Requirement, number: int = 0) -> str:
    """Serialize a single Requirement to markdown."""
    lines = []
    lines.append(f"### {req.id}: {req.title}")
    lines.append(f"**Priority:** {req.priority.value} | **Actor:** {req.actor or 'N/A'}")
    lines.append("")
    lines.append(req.description)
    if req.preconditions:
        lines.append("")
        lines.append("**Preconditions:**")
        for p in req.preconditions:
            lines.append(f"- {p}")
    ac_text = _format_acceptance_criteria(req.acceptance_criteria)
    if ac_text:
        lines.append("")
        lines.append(ac_text)
    return "\n".join(lines)


def serialize_requirements_list(requirements: list[Requirement], title: str = "Requirements") -> str:
    """Serialize a list of Requirements to markdown."""
    if not requirements:
        return f"# {title}\n\nNo requirements generated."
    lines = [f"# {title}\n"]
    for i, req in enumerate(requirements, 1):
        lines.append(serialize_requirement(req, i))
        lines.append("")
    return "\n".join(lines)


def serialize_user_story(story: UserStory) -> str:
    """Serialize a single UserStory to markdown."""
    lines = []
    lines.append(f"### {story.id}: {story.title}")
    lines.append(
        f"**Priority:** {story.priority.value}"
        + (f" | **Points:** {story.story_points}" if story.story_points else "")
        + (f" | **Epic:** {story.epic}" if story.epic else "")
    )
    lines.append("")
    lines.append(f"As a **{story.role}**, I want **{story.feature}** so that **{story.benefit}**.")
    ac_text = _format_acceptance_criteria(story.acceptance_criteria)
    if ac_text:
        lines.append("")
        lines.append(ac_text)
    return "\n".join(lines)


def serialize_user_stories_list(stories: list[UserStory], title: str = "User Stories") -> str:
    """Serialize a list of UserStories to markdown."""
    if not stories:
        return f"# {title}\n\nNo user stories generated."
    lines = [f"# {title}\n"]
    for story in stories:
        lines.append(serialize_user_story(story))
        lines.append("")
    return "\n".join(lines)


def serialize_acceptance_criteria(criteria: list[AcceptanceCriterion], title: str = "Acceptance Criteria") -> str:
    """Serialize acceptance criteria to markdown."""
    if not criteria:
        return f"# {title}\n\nNo acceptance criteria generated."
    lines = [f"# {title}\n"]
    for ac in criteria:
        lines.append(f"### {ac.id}")
        if ac.given:
            lines.append(f"**Given** {ac.given}")
        if ac.when:
            lines.append(f"**When** {ac.when}")
        if ac.then:
            lines.append(f"**Then** {ac.then}")
        lines.append("")
    return "\n".join(lines)


def serialize_brd(brd: BRDDocument) -> str:
    """Serialize a BRD to markdown."""
    lines = [f"# {brd.title}\n"]

    if brd.executive_summary:
        lines.append("## Executive Summary\n")
        lines.append(brd.executive_summary)
        lines.append("")

    if brd.business_objectives:
        lines.append("## Business Objectives\n")
        for obj in brd.business_objectives:
            lines.append(f"- {obj}")
        lines.append("")

    if brd.scope:
        lines.append("## Scope\n")
        lines.append(brd.scope)
        lines.append("")

    if brd.stakeholders:
        lines.append("## Stakeholders\n")
        for s in brd.stakeholders:
            lines.append(f"- {s}")
        lines.append("")

    if brd.business_requirements:
        lines.append("## Business Requirements\n")
        for req in brd.business_requirements:
            lines.append(serialize_requirement(req))
            lines.append("")

    if brd.functional_requirements:
        lines.append("## Functional Requirements\n")
        for req in brd.functional_requirements:
            lines.append(serialize_requirement(req))
            lines.append("")

    if brd.non_functional_requirements:
        lines.append("## Non-Functional Requirements\n")
        for req in brd.non_functional_requirements:
            lines.append(serialize_requirement(req))
            lines.append("")

    if brd.assumptions_and_constraints:
        lines.append("## Assumptions and Constraints\n")
        for ac in brd.assumptions_and_constraints:
            lines.append(f"- {ac}")
        lines.append("")

    if brd.success_criteria:
        lines.append("## Success Criteria\n")
        for sc in brd.success_criteria:
            lines.append(f"- {sc}")
        lines.append("")

    return "\n".join(lines)


def serialize_srs(srs: SRSDocument) -> str:
    """Serialize an SRS to markdown."""
    lines = [f"# {srs.title}\n"]

    if srs.introduction:
        lines.append("## 1. Introduction\n")
        for key, value in srs.introduction.items():
            lines.append(f"### 1.1 {key.title()}\n")
            lines.append(str(value))
            lines.append("")

    if srs.overall_description:
        lines.append("## 2. Overall Description\n")
        for key, value in srs.overall_description.items():
            lines.append(f"### 2.1 {key.title()}\n")
            lines.append(str(value))
            lines.append("")

    if srs.functional_requirements:
        lines.append("## 3. Specific Requirements\n")
        lines.append("### 3.1 Functional Requirements\n")
        for req in srs.functional_requirements:
            lines.append(serialize_requirement(req))
            lines.append("")

    if srs.external_interface_requirements:
        lines.append("### 3.2 External Interface Requirements\n")
        for req in srs.external_interface_requirements:
            lines.append(serialize_requirement(req))
            lines.append("")

    if srs.performance_requirements:
        lines.append("### 3.3 Performance Requirements\n")
        for req in srs.performance_requirements:
            lines.append(serialize_requirement(req))
            lines.append("")

    if srs.verification_and_validation:
        lines.append("## 4. Verification and Validation\n")
        for item in srs.verification_and_validation:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def serialize_rtm(rtm: RTMDocument) -> str:
    """Serialize an RTM to markdown."""
    lines = [f"# {rtm.title}\n"]

    if not rtm.rows:
        lines.append("No traceability data generated.\n")
        return "\n".join(lines)

    # Table header
    lines.append("| Requirement ID | Description | Source | Priority | Test Case | Status |")
    lines.append("|---|---|---|---|---|---|")

    for row in rtm.rows:
        req_id = row.get("requirement_id", "N/A")
        desc = row.get("description", "")
        source = row.get("source", "N/A")
        priority = row.get("priority", "N/A")
        test_case = row.get("test_case", "N/A")
        status = row.get("status", "N/A")
        lines.append(f"| {req_id} | {desc} | {source} | {priority} | {test_case} | {status} |")

    lines.append("")
    return "\n".join(lines)


def serialize_structured_output(
    action: str,
    requirements: list[Requirement] = None,
    user_stories: list[UserStory] = None,
    acceptance_criteria: list[AcceptanceCriterion] = None,
    brd: BRDDocument = None,
    srs: SRSDocument = None,
    rtm: RTMDocument = None,
    title: str = "",
) -> str:
    """
    Serialize any structured output to markdown based on the action type.

    This is the main entry point for converting internal structured data
    to the markdown string that goes into `generated_output` / API `content`.
    """
    if brd:
        return serialize_brd(brd)
    if srs:
        return serialize_srs(srs)
    if rtm:
        return serialize_rtm(rtm)
    if user_stories:
        return serialize_user_stories_list(user_stories, title or "User Stories")
    if acceptance_criteria:
        return serialize_acceptance_criteria(acceptance_criteria, title or "Acceptance Criteria")
    if requirements:
        return serialize_requirements_list(requirements, title or "Requirements")
    return ""
