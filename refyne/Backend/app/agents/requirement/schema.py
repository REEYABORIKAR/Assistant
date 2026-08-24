"""
Structured output models for the Requirement Agent.

These Pydantic models define the internal structured representation of
generated requirements. The serializer converts these to markdown for
the API response (frontend compatibility).
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AcceptanceCriterion(BaseModel):
    """A single acceptance criterion in Given/When/Then format."""
    id: str = Field(..., description="Unique criterion ID (e.g. AC-001)")
    given: str = Field(..., description="Precondition or context")
    when: str = Field(..., description="Action or event")
    then: str = Field(..., description="Expected outcome")


class Requirement(BaseModel):
    """A single structured requirement."""
    id: str = Field(..., description="Unique requirement ID (e.g. FR-001)")
    title: str = Field(..., description="Short requirement title")
    description: str = Field(..., description="Detailed description")
    priority: Priority = Field(default=Priority.MEDIUM, description="Priority level")
    actor: str = Field(default="", description="Primary actor or stakeholder")
    preconditions: list[str] = Field(default_factory=list, description="Prerequisites")
    acceptance_criteria: list[AcceptanceCriterion] = Field(
        default_factory=list,
        description="Acceptance criteria in Given/When/Then format",
    )
    source_citations: list[str] = Field(
        default_factory=list,
        description="Source references (e.g. doc_id#chunk_id)",
    )


class UserStory(BaseModel):
    """A single user story."""
    id: str = Field(..., description="Unique user story ID (e.g. US-001)")
    title: str = Field(..., description="Short story title")
    role: str = Field(..., description="The user role")
    feature: str = Field(..., description="What the user wants")
    benefit: str = Field(..., description="Why the user wants it")
    priority: Priority = Field(default=Priority.MEDIUM, description="Priority level")
    story_points: int | None = Field(default=None, description="Estimated story points (1-13)")
    acceptance_criteria: list[AcceptanceCriterion] = Field(
        default_factory=list,
        description="Acceptance criteria for this story",
    )
    epic: str | None = Field(default=None, description="Parent epic name")
    source_citations: list[str] = Field(default_factory=list)


class BRDDocument(BaseModel):
    """Business Requirements Document structure."""
    title: str = Field(default="Business Requirements Document (BRD)")
    executive_summary: str = Field(default="")
    business_objectives: list[str] = Field(default_factory=list)
    scope: str = Field(default="")
    stakeholders: list[str] = Field(default_factory=list)
    business_requirements: list[Requirement] = Field(default_factory=list)
    functional_requirements: list[Requirement] = Field(default_factory=list)
    non_functional_requirements: list[Requirement] = Field(default_factory=list)
    assumptions_and_constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class SRSDocument(BaseModel):
    """Software Requirements Specification structure."""
    title: str = Field(default="Software Requirements Specification (SRS)")
    introduction: dict[str, str] = Field(default_factory=dict)
    overall_description: dict[str, str] = Field(default_factory=dict)
    functional_requirements: list[Requirement] = Field(default_factory=list)
    external_interface_requirements: list[Requirement] = Field(default_factory=list)
    performance_requirements: list[Requirement] = Field(default_factory=list)
    verification_and_validation: list[str] = Field(default_factory=list)


class RTMDocument(BaseModel):
    """Requirements Traceability Matrix structure."""
    title: str = Field(default="Requirements Traceability Matrix (RTM)")
    rows: list[dict[str, Any]] = Field(
        default_factory=list,
        description="RTM rows with requirement_id, description, source, priority, test_case, status",
    )


class GenerationPlan(BaseModel):
    """Plan for what to generate based on the request and context."""
    action: str = Field(..., description="Document action (brd, srs, rtm, etc.)")
    title: str = Field(..., description="Document title")
    prompt: str = Field(..., description="The generation prompt to use")
    top_k: int = Field(default=10, description="Number of context chunks to retrieve")
    output_type: str = Field(
        default="generic",
        description="Output type: generic, brd, srs, rtm, user_stories, acceptance_criteria",
    )
