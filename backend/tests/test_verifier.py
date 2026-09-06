import asyncio
import pytest
from refyne.llm_service import verify_claims_ai, analyze_document_intelligence, generate_document_ai, detect_domain


def test_verify_claims_ai_basic():
    """Test batched claim verifier with confidence scoring."""
    doc_excerpt = "The hospital system requires doctors and nurses to login using OAuth2 JWT and access patient records."
    claims = [
        "Doctors and nurses authenticate using OAuth2 JWT to view patient records.",
        "System allows astronauts to control space station thrusters with quantum keys."
    ]

    result = asyncio.run(verify_claims_ai(doc_excerpt, claims))
    assert result["total_claims"] == 2
    assert len(result["verdicts"]) == 2
    
    # Claim 0 is grounded in doc
    v0 = result["verdicts"][0]
    assert v0["confidence"] >= 60
    assert v0["verdict"] == "SUPPORTED"

    # Claim 1 is unsupported
    v1 = result["verdicts"][1]
    assert v1["confidence"] < 60
    assert v1["verdict"] == "LOW_CONFIDENCE"
    assert len(result["flagged_items"]) >= 1


def test_call_site_a_dashboard_audit_verification():
    """Verify that analyze_document_intelligence attaches verification badges to all dashboard items."""
    text = "Enterprise payment checkout platform with PCI-DSS tokenization and Stripe webhook verification."
    audit = asyncio.run(analyze_document_intelligence(text, filename="Payments.pdf"))

    assert "verification_summary" in audit
    summary = audit["verification_summary"]
    assert summary["total_claims"] > 0

    # Risk factors should each carry verification
    for rf in audit.get("risk_factors", []):
        assert "verification" in rf
        assert "confidence" in rf["verification"]
        assert "reason" in rf["verification"]

    # Missing sections should each carry verification
    for ms in audit.get("missing_sections_and_details", []):
        assert "verification" in ms
        assert "confidence" in ms["verification"]


def test_call_site_b_generation_verification_summary():
    """Verify that generate_document_ai attaches a verification summary to the generated document."""
    text = "Hospital EMR platform for managing patient prescriptions under HIPAA."
    domain = detect_domain(text)
    audit = asyncio.run(analyze_document_intelligence(text, filename="Hospital_EMR.pdf"))

    doc = asyncio.run(generate_document_ai(
        doc_type="SRS",
        title="Hospital EMR",
        audit_json=audit,
        domain_profile=domain,
        doc_excerpt=text
    ))

    assert "verification_summary" in doc
    v_sum = doc["verification_summary"]
    assert v_sum["total_claims"] > 0
    assert v_sum["verified_count"] >= 1
