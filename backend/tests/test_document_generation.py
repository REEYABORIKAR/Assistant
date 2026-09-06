import asyncio
import pytest
from refyne.llm_service import generate_document_ai, detect_domain
from refyne.document_service import generate_document_content, generate_document_content_sync
from refyne.main import app, DOCUMENT_STORE
from fastapi.testclient import TestClient


def test_generate_document_ai_domain_differentiation():
    """Verify that generating documents for two different sources produces visibly different, content-grounded outputs."""
    # Healthcare doc audit
    health_audit = {
        "summary": "Telehealth and Patient EHR management system for automated prescriptions.",
        "risk_factors": [
            {"title": "Unencrypted PHI Transmission", "severity": "HIGH", "description": "Patient data sent without TLS encryption.", "mitigation": "Enforce TLS 1.3"}
        ],
        "missing_sections_and_details": [
            {"section_name": "HIPAA Audit Trail Specification", "priority": "CRITICAL"}
        ],
        "rtm_matrix": [
            {"req_id": "REQ-01", "business_goal": "Patient Registration & EMR Record Lookup", "technical_component": "PatientService", "test_case_verification": "Verify EMR patient query with JWT", "status": "COVERED"},
            {"req_id": "REQ-02", "business_goal": "Electronic Prescription Routing", "technical_component": "PrescriptionGateway", "test_case_verification": "Test pharmacy dispatch webhook", "status": "COVERED"}
        ]
    }
    health_domain = detect_domain("patient doctor hospital hipaa emr prescription")
    
    health_doc = asyncio.run(generate_document_ai(
        doc_type="BRD",
        title="Telehealth EMR Platform",
        audit_json=health_audit,
        domain_profile=health_domain,
        doc_excerpt="The hospital platform allows doctors to manage patient prescriptions under HIPAA."
    ))
    
    # E-Commerce doc audit
    ecom_audit = {
        "summary": "Online retail shopping cart with high-concurrency inventory checkout and SKU tracking.",
        "risk_factors": [
            {"title": "Cardholder Data Leakage", "severity": "HIGH", "description": "Credit card CVV logged in plaintext.", "mitigation": "PCI-DSS tokenization"}
        ],
        "missing_sections_and_details": [
            {"section_name": "PCI-DSS Level 1 Compliance Section", "priority": "CRITICAL"}
        ],
        "rtm_matrix": [
            {"req_id": "REQ-01", "business_goal": "Shopping Cart & SKU Inventory Reservation", "technical_component": "CartService", "test_case_verification": "Concurrent stock decrement test", "status": "COVERED"},
            {"req_id": "REQ-02", "business_goal": "Stripe Gateway Checkout & Payment", "technical_component": "PaymentProcessor", "test_case_verification": "Idempotent charge verification", "status": "COVERED"}
        ]
    }
    ecom_domain = detect_domain("cart checkout sku inventory shipping order ecommerce")
    
    ecom_doc = asyncio.run(generate_document_ai(
        doc_type="BRD",
        title="MegaMart Retail Store",
        audit_json=ecom_audit,
        domain_profile=ecom_domain,
        doc_excerpt="The ecommerce store allows shoppers to add SKUs to cart and checkout via Stripe."
    ))

    # 1. Check health doc grounding
    assert health_doc["doc_type"] == "BRD"
    assert "Telehealth" in health_doc["title"]
    assert health_doc["_source_audit"] == health_audit
    assert health_doc["_domain_profile"]["domain"] == "HEALTHCARE"
    assert "HIPAA" in health_doc["_domain_profile"]["compliance"]
    
    health_text = str(health_doc["sections"])
    assert "Patient" in health_text or "EMR" in health_text or "Prescription" in health_text

    # 2. Check ecom doc grounding
    assert ecom_doc["doc_type"] == "BRD"
    assert "MegaMart" in ecom_doc["title"]
    assert ecom_doc["_source_audit"] == ecom_audit
    assert ecom_doc["_domain_profile"]["domain"] == "ECOMMERCE"
    assert "PCI-DSS" in ecom_doc["_domain_profile"]["compliance"]
    
    ecom_text = str(ecom_doc["sections"])
    assert "Cart" in ecom_text or "SKU" in ecom_text or "Checkout" in ecom_text or "Retail" in ecom_text

    # 3. Ensure the two outputs are distinctly different and not a static template
    assert health_text != ecom_text


def test_generate_document_ai_all_types():
    """Verify skeletons for BRD, SRS, RTM, USER_STORIES, and ACCEPTANCE_CRITERIA."""
    audit = {
        "summary": "Core Banking Ledger and Loan Processing Engine.",
        "risk_factors": [{"title": "Transaction Non-Atomicity", "severity": "HIGH", "description": "Ledger mismatch on network timeout."}],
        "missing_sections_and_details": [{"section_name": "SOX Compliance Section"}],
        "rtm_matrix": [
            {"req_id": "REQ-01", "business_goal": "Execute Inter-Bank Fund Transfer", "technical_component": "LedgerService", "test_case_verification": "Double-entry balance check", "status": "COVERED"}
        ]
    }
    domain = detect_domain("bank account balance transaction ledger kyc aml loan")

    for dtype in ["BRD", "SRS", "RTM", "USER_STORIES", "ACCEPTANCE_CRITERIA"]:
        doc = asyncio.run(generate_document_ai(
            doc_type=dtype,
            title="Core Banking Engine",
            audit_json=audit,
            domain_profile=domain,
            doc_excerpt="Ledger transaction engine for bank accounts."
        ))
        assert doc["doc_type"] == dtype
        assert len(doc["sections"]) >= 2
        assert doc["_source_audit"] == audit
        assert doc["_domain_profile"]["domain"] == "BANKING"


def test_sync_document_content_fallback():
    """Test sync fallback generator."""
    doc = generate_document_content_sync(
        doc_type="SRS",
        title="Sync Spec",
        doc_context="Patient records for hospital clinic."
    )
    assert doc["doc_type"] == "SRS"
    assert doc["_domain_profile"]["domain"] == "HEALTHCARE"
    assert len(doc["sections"]) > 0
