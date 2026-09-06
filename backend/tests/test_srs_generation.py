import pytest
from refyne.project_analyzer import analyze_project_context
from refyne.srs_id_manager import manage_srs_ids
from refyne.srs_validator import validate_srs_document
from refyne.document_service import build_pdf_document, generate_document_content_sync
from refyne.llm_service import _build_grounded_fallback_document

def test_project_analyzer_dynamic_extraction():
    """Verify that project analyzer dynamically extracts modules, roles, and APIs without domain hardcoding."""
    analysis = analyze_project_context(
        db=None,
        doc_context="The system is an Enterprise Requirements Assistant providing API endpoints /api/v1/documents/generate and database models for tenants, users, projects, and requirements.",
        audit_json={"summary": "Requirements platform audit baseline", "rtm_matrix": []}
    )
    
    assert "project_info" in analysis
    assert "users_and_roles" in analysis
    assert "modules" in analysis
    assert "functional_requirements" in analysis
    assert "non_functional_requirements" in analysis
    assert "database_design" in analysis
    assert "api_requirements" in analysis
    
    # Check that modules contain actual discovered modules (DOCUMENTS, USERS, REQUIREMENTS, etc.)
    module_names = [m["name"] for m in analysis["modules"]]
    assert len(module_names) > 0
    # Confirm no hardcoded Hospital or Patient modules were injected
    assert "HOSPITAL" not in module_names
    assert "PATIENT" not in module_names


def test_srs_structure_and_fallback_generation():
    """Verify ISO/IEC/IEEE 29148 21-section structure in generated SRS documents."""
    analysis = analyze_project_context(db=None, doc_context="Sample enterprise project specification")
    doc = _build_grounded_fallback_document(
        doc_type="SRS",
        title="REFYNE Requirements Engine",
        audit_json={"summary": "Grounded audit summary"},
        domain_profile={"domain": "ENTERPRISE"},
        doc_excerpt="System specification text",
        project_analysis=analysis
    )
    
    assert doc["doc_type"] == "SRS"
    assert "ISO/IEC/IEEE 29148" in doc["title"]
    assert "sections" in doc
    
    sec_titles = [s["title"] for s in doc["sections"]]
    assert any("Document Control" in t for t in sec_titles)
    assert any("Introduction" in t for t in sec_titles)
    assert any("Functional Requirements" in t for t in sec_titles)
    assert any("Non-Functional Requirements" in t for t in sec_titles)
    assert any("Requirements Traceability Matrix" in t for t in sec_titles)
    assert any("Appendices" in t for t in sec_titles)


def test_srs_id_management_and_preservation():
    """Verify deterministic requirement ID generation and preservation across document revisions."""
    initial_doc = {
        "doc_type": "SRS",
        "title": "Software Requirements Specification",
        "sections": [
            {
                "title": "3. System Features and Functional Requirements",
                "table": [
                    ["SRS Req ID", "Module", "Functional Requirement Description", "Priority", "Acceptance Criteria"],
                    ["FR-01", "CORE", "User Authentication", "HIGH", "Given valid creds, When login, Then token returned"],
                    ["FR-02", "CORE", "Project Creation", "MEDIUM", "Given valid details, When created, Then saved"]
                ]
            }
        ]
    }
    
    processed = manage_srs_ids(initial_doc, previous_doc=None)
    table = processed["sections"][0]["table"]
    assert table[1][0] == "FR-CORE-001"
    assert table[2][0] == "FR-CORE-002"
    
    # Test revision preserving IDs
    revised_doc = {
        "doc_type": "SRS",
        "title": "Software Requirements Specification (Rev 2)",
        "sections": [
            {
                "title": "3. System Features and Functional Requirements",
                "table": [
                    ["SRS Req ID", "Module", "Functional Requirement Description", "Priority", "Acceptance Criteria"],
                    ["FR-CORE-001", "CORE", "User Authentication", "HIGH", "Given valid creds, When login, Then token returned"]
                ]
            }
        ]
    }
    
    revised_processed = manage_srs_ids(revised_doc, previous_doc=processed)
    rev_sec_titles = [s["title"] for s in revised_processed["sections"]]
    assert any("Deprecated" in t for t in rev_sec_titles)


def test_srs_validator():
    """Verify pre-export validation checks quality score and structural completeness."""
    analysis = analyze_project_context(db=None, doc_context="Project specification for REFYNE AI")
    doc = _build_grounded_fallback_document(
        doc_type="SRS",
        title="REFYNE Requirements Engine",
        audit_json={"summary": "Verified summary"},
        domain_profile={"domain": "ENTERPRISE"},
        doc_excerpt="System specification",
        project_analysis=analysis
    )
    
    report = validate_srs_document(doc, project_analysis=analysis)
    assert "valid" in report
    assert "score" in report
    assert report["score"] >= 70
    assert report["valid"] is True


def test_pdf_export_compilation():
    """Verify multi-page ReportLab vector PDF export compiles without errors."""
    analysis = analyze_project_context(db=None, doc_context="Project specification")
    doc = _build_grounded_fallback_document(
        doc_type="SRS",
        title="REFYNE Requirements Engine",
        audit_json={"summary": "Summary"},
        domain_profile={"domain": "ENTERPRISE"},
        doc_excerpt="Excerpt",
        project_analysis=analysis
    )
    
    pdf_bytes = build_pdf_document(
        title=doc["title"],
        doc_type=doc["doc_type"],
        sections=doc["sections"],
        tenant_name="REFYNE Enterprise Workspace",
        version="v1.0"
    )
    
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")
