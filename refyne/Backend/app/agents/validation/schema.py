"""
Validation Agent schema models.

Defines the structured output for requirement validation reports.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity level for validation issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ValidationIssue(BaseModel):
    """A single validation issue found during checks."""
    id: str = Field(..., description="Unique issue ID")
    requirement_id: str | None = Field(
        default=None,
        description="ID of the requirement with this issue, if applicable",
    )
    check_type: str = Field(
        ...,
        description="Type of check that found this issue (rule, llm, duplicate, traceability)",
    )
    severity: Severity = Field(..., description="Issue severity")
    category: str = Field(..., description="Issue category (ambiguity, completeness, etc.)")
    message: str = Field(..., description="Human-readable issue description")
    recommendation: str = Field(default="", description="Suggested fix")


class ValidationReport(BaseModel):
    """Complete validation report from all validators."""
    overall_status: str = Field(
        default="pending",
        description="Overall status: pass, conditional, fail, pending",
    )
    overall_score: float = Field(
        default=0.0,
        description="Overall validation score 0.0-1.0",
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="All validation issues found",
    )
    rule_check_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of deterministic rule checks",
    )
    llm_check_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of LLM-based semantic checks",
    )
    duplicate_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of duplicate detection results",
    )
    traceability_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of traceability check results",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="High-level recommendations",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the validation run",
    )
