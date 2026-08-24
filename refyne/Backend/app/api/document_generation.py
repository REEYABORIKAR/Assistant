"""
Document generation API endpoints.

Provides endpoints for generating requirement documents (BRD, SRS, RTM, etc.)
using the existing RAG pipeline and LLM generation.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, require_role
from app.core.roles import ProjectRole
from app.models.membership import ProjectMember
from app.models.project import Project
from app.rag.retrieval.hybrid import HybridRetriever
from app.services.generation import generate_answer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["document-generation"])


# Document generation prompts for each action type
DOCUMENT_PROMPTS = {
    "brd": {
        "title": "Business Requirements Document (BRD)",
        "prompt": (
            "Generate a comprehensive Business Requirements Document (BRD) based on the retrieved context. "
            "Include the following sections:\n"
            "1. Executive Summary\n"
            "2. Business Objectives\n"
            "3. Scope\n"
            "4. Stakeholders\n"
            "5. Business Requirements\n"
            "6. Functional Requirements\n"
            "7. Non-Functional Requirements\n"
            "8. Assumptions and Constraints\n"
            "9. Success Criteria\n"
            "Format the document with clear headings, bullet points, and requirement IDs where applicable."
        )
    },
    "srs": {
        "title": "Software Requirements Specification (SRS)",
        "prompt": (
            "Generate a detailed Software Requirements Specification (SRS) based on the retrieved context. "
            "Include the following sections:\n"
            "1. Introduction\n"
            "   1.1 Purpose\n"
            "   1.2 Scope\n"
            "   1.3 Definitions, Acronyms, Abbreviations\n"
            "2. Overall Description\n"
            "   2.1 Product Perspective\n"
            "   2.2 Product Functions\n"
            "   2.3 User Characteristics\n"
            "   2.4 Constraints\n"
            "3. Specific Requirements\n"
            "   3.1 Functional Requirements\n"
            "   3.2 External Interface Requirements\n"
            "   3.3 Performance Requirements\n"
            "   3.4 Database Requirements\n"
            "   3.5 Design Constraints\n"
            "4. Verification and Validation\n"
            "5. Appendices\n"
            "Format with requirement IDs, priority levels, and acceptance criteria."
        )
    },
    "rtm": {
        "title": "Requirements Traceability Matrix (RTM)",
        "prompt": (
            "Generate a Requirements Traceability Matrix (RTM) based on the retrieved context. "
            "The RTM should:\n"
            "1. Map each requirement to its source\n"
            "2. Link requirements to test cases\n"
            "3. Show dependencies between requirements\n"
            "4. Include columns: Requirement ID, Description, Source, Priority, Test Case, Status\n"
            "Format as a structured table with clear traceability links."
        )
    },
    "user_stories": {
        "title": "User Stories",
        "prompt": (
            "Generate comprehensive User Stories based on the retrieved context. "
            "For each user story, include:\n"
            "1. Title\n"
            "2. User Story Statement: 'As a [role], I want [feature] so that [benefit]'\n"
            "3. Acceptance Criteria (at least 3 per story)\n"
            "4. Priority (High/Medium/Low)\n"
            "5. Story Points (1-13)\n"
            "Group related stories into Epics where appropriate.\n"
            "Follow INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)."
        )
    },
    "acceptance_criteria": {
        "title": "Acceptance Criteria",
        "prompt": (
            "Generate detailed Acceptance Criteria for each requirement found in the retrieved context. "
            "For each requirement:\n"
            "1. Requirement ID and Description\n"
            "2. Given-When-Then format acceptance criteria\n"
            "3. Test scenarios\n"
            "4. Edge cases to consider\n"
            "5. Definition of Done\n"
            "Ensure criteria are specific, measurable, and testable."
        )
    },
    "business_rules": {
        "title": "Business Rules",
        "prompt": (
            "Extract and document Business Rules from the retrieved context. "
            "For each rule:\n"
            "1. Rule ID\n"
            "2. Rule Description\n"
            "3. Rule Category (Validation, Process, Calculation, etc.)\n"
            "4. Trigger/Condition\n"
            "5. Action/Result\n"
            "6. Priority\n"
            "7. Exceptions\n"
            "Organize rules by category and show dependencies."
        )
    },
    "validation_rules": {
        "title": "Validation Rules",
        "prompt": (
            "Extract and document Validation Rules from the retrieved context. "
            "For each rule:\n"
            "1. Rule ID\n"
            "2. Field/Input being validated\n"
            "3. Validation Type (format, range, required, custom)\n"
            "4. Rule Expression/Pattern\n"
            "5. Error Message\n"
            "6. Example (valid and invalid)\n"
            "Organize by functional area and priority."
        )
    },
    "edge_cases": {
        "title": "Edge Cases",
        "prompt": (
            "Identify and document Edge Cases based on the retrieved context. "
            "For each edge case:\n"
            "1. Edge Case ID\n"
            "2. Description\n"
            "3. Scenario/Trigger\n"
            "4. Expected System Behavior\n"
            "5. Impact Level (Critical/High/Medium/Low)\n"
            "6. Recommended Handling\n"
            "Include boundary conditions, error scenarios, and unusual input combinations."
        )
    },
    "assumptions": {
        "title": "Assumptions",
        "prompt": (
            "Extract and document Assumptions from the retrieved context. "
            "For each assumption:\n"
            "1. Assumption ID\n"
            "2. Description\n"
            "3. Category (Technical, Business, Resource, Timeline)\n"
            "4. Impact if Invalid\n"
            "5. Validation Method\n"
            "6. Risk Level\n"
            "Group assumptions by category and assess overall risk."
        )
    },
    "risk_analysis": {
        "title": "Risk Analysis",
        "prompt": (
            "Conduct a Risk Analysis based on the retrieved context. "
            "For each risk:\n"
            "1. Risk ID\n"
            "2. Risk Description\n"
            "3. Category (Technical, Business, Security, Performance, etc.)\n"
            "4. Probability (High/Medium/Low)\n"
            "5. Impact (High/Medium/Low)\n"
            "6. Risk Score (Probability × Impact)\n"
            "7. Mitigation Strategy\n"
            "8. Contingency Plan\n"
            "Include a risk matrix and prioritize risks by score."
        )
    },
    "missing_requirements": {
        "title": "Missing Requirements Analysis",
        "prompt": (
            "Analyze the retrieved context to identify Missing Requirements. "
            "For each gap:\n"
            "1. Gap ID\n"
            "2. Description of Missing Requirement\n"
            "3. Category (Functional, Non-Functional, Security, Compliance, etc.)\n"
            "4. Business Impact\n"
            "5. Urgency (Critical/High/Medium/Low)\n"
            "6. Recommended Action\n"
            "7. Potential Sources for Requirements\n"
            "Prioritize gaps by business impact and urgency."
        )
    }
}


class DocumentGenerationResponse(BaseModel):
    title: str
    content: str
    action: str
    citations: list = []
    source_documents: list = []


def _get_project_for_user(db: Session, project_id: str, user_id: str) -> tuple[Project, str]:
    """Verify project access (owner or member). Returns (project, user_role)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id == user_id:
        return project, ProjectRole.ADMIN.value
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Project not found")
    return project, member.role


@router.post(
    "/api/projects/{project_id}/generate/{action}",
    response_model=DocumentGenerationResponse,
    summary="Generate a specific requirement document",
    description="Generates BRD, SRS, RTM, User Stories, and other requirement documents using RAG and LLM.",
)
def generate_document(
    project_id: str,
    action: str,
    db: SessionDep,
    current_user: CurrentUser,
    _role: None = Depends(require_role(ProjectRole.EDITOR)),
) -> DocumentGenerationResponse:
    # Validate action
    if action not in DOCUMENT_PROMPTS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action '{action}'. Valid actions: {', '.join(DOCUMENT_PROMPTS.keys())}"
        )

    # Verify project ownership
    _project, user_role = _get_project_for_user(db, project_id, current_user.id)

    # Get the prompt configuration for this action
    action_config = DOCUMENT_PROMPTS[action]

    # Use RAG to retrieve relevant context
    retriever = HybridRetriever(db)
    try:
        # First, search for relevant content
        search_response = retriever.retrieve(
            project_id=project_id,
            query=action_config["prompt"],
            top_k=10,
            user_role=user_role,
        )
    except Exception as e:
        logger.error(f"Retrieval failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Retrieval failed due to an internal error")

    # Generate the document using LLM
    generation = generate_answer(
        query=action_config["prompt"],
        context=search_response.context,
        citations=search_response.citations,
    )

    # Format the response
    if generation["configured"] and generation["answer"]:
        content = f"# {action_config['title']}\n\n{generation['answer']}"
    else:
        # Fallback: provide a structured template with retrieved context
        content = _generate_fallback_content(action, action_config, search_response)

    # Persist artifact in DB
    try:
        from app.models.artifact import Artifact
        file_name = f"{action.upper()}_{project_id[:6]}.md"
        artifact = Artifact(
            project_id=project_id,
            user_id=current_user.id,
            type=action,
            title=action_config["title"],
            file_name=file_name,
            version="v1.0",
            content=content,
            status="pending_validation",
        )
        db.add(artifact)
        db.commit()
    except Exception as err:
        logger.warning(f"Could not persist artifact: {err}")

    return DocumentGenerationResponse(
        title=action_config["title"],
        content=content,
        action=action,
        citations=search_response.citations,
        source_documents=search_response.source_documents,
    )


def _generate_fallback_content(action: str, config: dict, search_response) -> str:
    """Generate fallback content when LLM is not configured."""
    context = search_response.context if search_response.context else "No relevant content found in documents."

    fallback_templates = {
        "brd": f"""# {config['title']}

## Executive Summary
Based on the uploaded documents, the following business requirements have been identified.

## Business Objectives
{context[:500] if context else 'No objectives identified from documents.'}

## Business Requirements
{context[500:1500] if len(context) > 500 else context}

## Next Steps
- Review the identified requirements
- Validate with stakeholders
- Set GROQ_API_KEY in Backend/.env for AI-powered generation
""",
        "srs": f"""# {config['title']}

## 1. Introduction
### 1.1 Purpose
This document specifies the software requirements based on the uploaded documents.

## 2. Overall Description
{context[:1000] if context else 'No software requirements identified from documents.'}

## 3. Specific Requirements
{context[1000:2000] if len(context) > 1000 else context}

## Next Steps
- Set GROQ_API_KEY in Backend/.env for AI-powered generation
""",
        # Add more fallback templates as needed
    }

    return fallback_templates.get(action, f"""# {config['title']}

## Overview
{context[:2000] if context else 'No relevant content found in the uploaded documents.'}

## Notes
Set GROQ_API_KEY in Backend/.env for AI-powered document generation.
""")
