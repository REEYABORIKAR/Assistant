import asyncio
import pytest
from refyne.llm_service import detect_domain, analyze_document_intelligence, generate_document_ai


def test_domain_detection_heuristics():
    """Verify that detect_domain maps domain keywords to compliance and NFR profiles."""
    health = detect_domain("Clinic hospital with patient prescriptions and doctor diagnosis")
    assert health["domain"] == "HEALTHCARE"
    assert "HIPAA" in health["compliance"]
    assert any("PHI" in nfr for nfr in health["standard_nfrs"])

    ecom = detect_domain("Shopping cart checkout with SKU catalog and customer inventory orders")
    assert ecom["domain"] == "ECOMMERCE"
    assert "PCI-DSS" in ecom["compliance"]

    bank = detect_domain("Bank account balance with ledger transactions, loans, and KYC verification")
    assert bank["domain"] == "BANKING"
    assert "SOX" in bank["compliance"] or "AML/KYC" in bank["compliance"] or "PCI-DSS" in bank["compliance"]

    generic = detect_domain("Generic software project without industry keywords")
    assert generic["domain"] == "GENERIC_ENTERPRISE"
    assert "SOC 2" in generic["compliance"]


def test_phase2_audit_and_srs_domain_compliance_mentions():
    """Verify that a healthcare doc, e-commerce doc, and banking doc produce domain-specific compliance mentions in missing sections and generated SRS."""
    # 1. HEALTHCARE
    health_text = "Hospital EMR application for patient admission, prescription management, and doctor schedules."
    health_audit = asyncio.run(analyze_document_intelligence(health_text, filename="Hospital_EMR.pdf"))
    assert health_audit["domain_profile"]["domain"] == "HEALTHCARE"
    
    # Missing sections should mention HIPAA / Healthcare compliance
    missing_str_health = str(health_audit["missing_sections_and_details"])
    assert "HIPAA" in missing_str_health or "HEALTHCARE" in missing_str_health
    
    # Generated SRS should mention HIPAA
    health_srs = asyncio.run(generate_document_ai("SRS", "Hospital EMR", health_audit, health_audit["domain_profile"], health_text))
    srs_str_health = str(health_srs["sections"])
    assert "HIPAA" in srs_str_health or "HEALTHCARE" in srs_str_health

    # 2. E-COMMERCE
    ecom_text = "Online retail store with shopping cart, SKU inventory management, shipping, and checkout."
    ecom_audit = asyncio.run(analyze_document_intelligence(ecom_text, filename="Retail_Store.pdf"))
    assert ecom_audit["domain_profile"]["domain"] == "ECOMMERCE"
    
    missing_str_ecom = str(ecom_audit["missing_sections_and_details"])
    assert "PCI-DSS" in missing_str_ecom or "ECOMMERCE" in missing_str_ecom
    
    ecom_srs = asyncio.run(generate_document_ai("SRS", "Retail Store", ecom_audit, ecom_audit["domain_profile"], ecom_text))
    srs_str_ecom = str(ecom_srs["sections"])
    assert "PCI-DSS" in srs_str_ecom or "ECOMMERCE" in srs_str_ecom

    # 3. BANKING
    bank_text = "Core banking system for managing ledger transactions, loan accounts, account balances, and KYC."
    bank_audit = asyncio.run(analyze_document_intelligence(bank_text, filename="Bank_Ledger.pdf"))
    assert bank_audit["domain_profile"]["domain"] == "BANKING"
    
    missing_str_bank = str(bank_audit["missing_sections_and_details"])
    assert "BANKING" in missing_str_bank or "SOX" in missing_str_bank or "PCI-DSS" in missing_str_bank
    
    bank_srs = asyncio.run(generate_document_ai("SRS", "Bank Ledger", bank_audit, bank_audit["domain_profile"], bank_text))
    srs_str_bank = str(bank_srs["sections"])
    assert "BANKING" in srs_str_bank or "SOX" in srs_str_bank or "PCI-DSS" in srs_str_bank
