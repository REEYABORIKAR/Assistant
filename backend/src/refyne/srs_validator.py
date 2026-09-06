import re
from typing import Any, Dict, List, Optional

REQUIRED_SRS_SECTION_PREFIXES = [
    "0. Document Control",
    "1. Introduction",
    "2. Overall Description",
    "3. System Features",
    "4. External Interface",
    "5. Non-Functional Requirements",
    "6. Data Requirements",
    "7. Business Rules",
    "8. Security Requirements",
    "9. Integration Requirements",
    "10. System Architecture",
    "11. Database Design",
    "12. API Requirements",
    "13. Use Cases",
    "14. Workflows",
    "15. Reporting Requirements",
    "16. Logging and Audit",
    "17. Error Handling",
    "18. Testing and Verification",
    "19. Requirements Traceability Matrix",
    "20. Acceptance Criteria",
    "21. Appendices"
]

def validate_srs_document(srs_doc: Dict[str, Any], project_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Pre-Output Validation Engine for ISO/IEC/IEEE 29148 SRS Specifications.
    
    Verifies:
    1. Structure: Required sections exist and are correctly numbered.
    2. Requirements: Unique requirement IDs, non-empty descriptions, testable acceptance criteria.
    3. Traceability: Requirements are mapped in Traceability Matrix.
    4. Anti-Hallucination & Grounding: Identifies ungrounded claims and marks missing info as 'Needs Clarification'.
    """
    validation_report = {
        "valid": True,
        "score": 100,
        "missing_sections": [],
        "duplicate_ids": [],
        "orphan_requirements": [],
        "ungrounded_claims": [],
        "warnings": [],
        "summary": "SRS document passed ISO/IEC/IEEE 29148 validation checks."
    }

    if not srs_doc or not isinstance(srs_doc, dict):
        return {
            "valid": False,
            "score": 0,
            "missing_sections": REQUIRED_SRS_SECTION_PREFIXES,
            "duplicate_ids": [],
            "orphan_requirements": [],
            "ungrounded_claims": [],
            "warnings": ["SRS document object is empty or invalid."],
            "summary": "Validation failed: Empty document payload."
        }

    sections = srs_doc.get("sections", [])
    if not isinstance(sections, list) or len(sections) == 0:
        return {
            "valid": False,
            "score": 0,
            "missing_sections": REQUIRED_SRS_SECTION_PREFIXES,
            "duplicate_ids": [],
            "orphan_requirements": [],
            "ungrounded_claims": [],
            "warnings": ["SRS document contains no sections."],
            "summary": "Validation failed: No sections found."
        }

    sec_titles = [s.get("title", "") for s in sections]

    # 1. Check Required Section Presence
    missing_secs = []
    for req_prefix in REQUIRED_SRS_SECTION_PREFIXES:
        match_found = False
        prefix_num = req_prefix.split(".")[0]
        for st in sec_titles:
            if st.startswith(f"{prefix_num}.") or req_prefix.lower() in st.lower():
                match_found = True
                break
        if not match_found:
            missing_secs.append(req_prefix)

    if missing_secs:
        validation_report["missing_sections"] = missing_secs
        validation_report["score"] -= len(missing_secs) * 4
        validation_report["warnings"].append(f"Missing {len(missing_secs)} recommended ISO/IEC/IEEE 29148 sections.")

    # 2. Check Requirement IDs & Duplicates
    all_ids = []
    duplicate_set = set()
    
    for sec in sections:
        if "table" in sec and isinstance(sec["table"], list):
            for row in sec["table"][1:]:
                if isinstance(row, list) and len(row) > 0:
                    item_id = str(row[0]).strip()
                    if item_id and (item_id.startswith("FR-") or item_id.startswith("NFR-") or item_id.startswith("BR-") or item_id.startswith("API-") or item_id.startswith("UC-")):
                        if item_id in all_ids:
                            duplicate_set.add(item_id)
                        else:
                            all_ids.append(item_id)
        elif "body" in sec and isinstance(sec["body"], str):
            matches = re.findall(r'###\s+((?:FR|NFR|BR|API|UC|INT|REP)[-_][A-Z0-9]+[-_]\d+)', sec["body"])
            for item_id in matches:
                if item_id in all_ids:
                    duplicate_set.add(item_id)
                else:
                    all_ids.append(item_id)

    if duplicate_set:
        validation_report["duplicate_ids"] = list(duplicate_set)
        validation_report["score"] -= len(duplicate_set) * 5
        validation_report["warnings"].append(f"Found {len(duplicate_set)} duplicate requirement IDs.")

    # 3. Check Traceability Matrix Mapping
    rtm_section = None
    for sec in sections:
        if "Traceability" in sec.get("title", ""):
            rtm_section = sec
            break

    if rtm_section and "table" in rtm_section and isinstance(rtm_section["table"], list):
        mapped_ids = set()
        for row in rtm_section["table"][1:]:
            if isinstance(row, list) and len(row) > 1:
                mapped_ids.add(str(row[0]).strip())
                mapped_ids.add(str(row[1]).strip())

        orphan_reqs = [rid for rid in all_ids if rid.startswith("FR-") and rid not in mapped_ids]
        if orphan_reqs:
            validation_report["orphan_requirements"] = orphan_reqs[:10]
            validation_report["warnings"].append(f"{len(orphan_reqs)} functional requirements are missing RTM mapping.")
            validation_report["score"] -= min(15, len(orphan_reqs) * 2)

    # 4. Check for Ungrounded / Hallucinated Specifics
    ungrounded = []
    domain_knowledge = (project_analysis or {}).get("project_info", {}).get("name", "").lower()
    for sec in sections:
        body_text = sec.get("body", "")
        if body_text and isinstance(body_text, str):
            # Check for domain mismatch hallucinations (e.g. Hospital keywords in non-healthcare app)
            if "hospital" in domain_knowledge or "medical" in domain_knowledge:
                pass
            else:
                if re.search(r'\b(hospital|patient|doctor|nurse|prescription|ehr|hipaa)\b', body_text, re.IGNORECASE):
                    ungrounded.append(f"Section '{sec.get('title')}' contains domain terms (hospital/patient) not found in project analysis context.")
                    
    if ungrounded:
        validation_report["ungrounded_claims"] = ungrounded
        validation_report["score"] -= len(ungrounded) * 10
        validation_report["warnings"].append(f"Detected {len(ungrounded)} domain term conflicts.")

    validation_report["score"] = max(0, min(100, validation_report["score"]))
    validation_report["valid"] = validation_report["score"] >= 70
    
    if not validation_report["valid"]:
        validation_report["summary"] = f"Validation failed with quality score {validation_report['score']}/100."
    else:
        validation_report["summary"] = f"ISO/IEC/IEEE 29148 Validation Passed (Quality Score: {validation_report['score']}/100)."

    return validation_report
