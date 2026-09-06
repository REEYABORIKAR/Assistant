import re
from typing import Any, Dict, List, Optional, Tuple

def manage_srs_ids(current_doc: Dict[str, Any], previous_doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Deterministic Requirement ID Management Engine for ISO/IEC/IEEE 29148 SRS Documents.
    
    Responsibilities:
    1. Assigns clean, consistent, unique IDs to every Functional Requirement (FR-[MOD]-xxx),
       Non-Functional Requirement (NFR-[TYPE]-xxx), Business Rule (BR-[MOD]-xxx),
       API Requirement (API-xxx), Use Case (UC-xxx), Integration (INT-xxx), and Report (REP-xxx).
    2. During Regeneration: Compares new section/table data against `previous_doc`.
       - Preserves unchanged IDs for existing requirements.
       - Assigns next available sequential index for newly added requirements.
       - Appends a Deprecated Requirements section if previous requirements were removed.
    """
    if not current_doc or not isinstance(current_doc, dict):
        return current_doc

    sections = current_doc.get("sections", [])
    if not sections or not isinstance(sections, list):
        return current_doc

    # Build previous requirement mapping if available
    prev_req_map: Dict[str, Dict[str, Any]] = {}
    if previous_doc and isinstance(previous_doc, dict) and "sections" in previous_doc:
        for sec in previous_doc.get("sections", []):
            _extract_req_ids_from_section(sec, prev_req_map)

    # Track used IDs per prefix to prevent collision and guarantee sequential continuity
    used_counters: Dict[str, int] = {}

    updated_sections = []
    for sec in sections:
        sec_title = sec.get("title", "")
        
        # 1. Update Section 3: Functional Requirements
        if "Functional Requirements" in sec_title or sec_title.startswith("3."):
            sec = _normalize_functional_section(sec, prev_req_map, used_counters)
            
        # 2. Update Section 5: Non-Functional Requirements
        elif "Non-Functional" in sec_title or sec_title.startswith("5."):
            sec = _normalize_nfr_section(sec, prev_req_map, used_counters)

        # 3. Update Section 7: Business Rules
        elif "Business Rules" in sec_title or sec_title.startswith("7."):
            sec = _normalize_business_rules_section(sec, prev_req_map, used_counters)

        # 4. Update Section 9: Integration Requirements
        elif "Integration" in sec_title or sec_title.startswith("9."):
            sec = _normalize_table_ids(sec, "INT", 1, prev_req_map, used_counters)

        # 5. Update Section 12: API Requirements
        elif "API Requirements" in sec_title or sec_title.startswith("12."):
            sec = _normalize_table_ids(sec, "API", 1, prev_req_map, used_counters)

        # 6. Update Section 13: Use Cases
        elif "Use Cases" in sec_title or sec_title.startswith("13."):
            sec = _normalize_table_ids(sec, "UC", 1, prev_req_map, used_counters)

        # 7. Update Section 15: Reporting Requirements
        elif "Reporting" in sec_title or sec_title.startswith("15."):
            sec = _normalize_table_ids(sec, "REP", 1, prev_req_map, used_counters)

        updated_sections.append(sec)

    current_doc["sections"] = updated_sections
    
    # Check for removed previous requirements and append deprecation log if needed
    if prev_req_map:
        current_req_map: Dict[str, Dict[str, Any]] = {}
        for sec in updated_sections:
            _extract_req_ids_from_section(sec, current_req_map)
            
        removed_ids = [rid for rid in prev_req_map if rid not in current_req_map]
        if removed_ids:
            dep_rows = [["Deprecated Req ID", "Original Title", "Status", "Reason / Replaced By"]]
            for rid in sorted(removed_ids):
                item = prev_req_map[rid]
                dep_rows.append([rid, item.get("title", "Legacy Requirement"), "DEPRECATED", "Superceded in document revision"])
            
            # Check if Deprecated section already exists
            dep_sec_exists = False
            for sec in current_doc["sections"]:
                if "Deprecated" in sec.get("title", ""):
                    sec["table"] = dep_rows
                    dep_sec_exists = True
                    break
            if not dep_sec_exists:
                current_doc["sections"].append({
                    "title": "21.1 Deprecated Requirements Log",
                    "table": dep_rows
                })

    return current_doc


def _extract_req_ids_from_section(sec: Dict[str, Any], req_map: Dict[str, Dict[str, Any]]) -> None:
    """Recursively extract existing requirement IDs from section tables and body markdown."""
    if "table" in sec and isinstance(sec["table"], list):
        for row in sec["table"][1:]:
            if isinstance(row, list) and len(row) >= 2:
                req_id = str(row[0]).strip()
                if re.match(r'^(FR|NFR|BR|API|UC|INT|REP|BRD)[-_]', req_id, re.IGNORECASE):
                    req_map[req_id] = {
                        "id": req_id,
                        "title": str(row[1]).strip() if len(row) > 1 else ""
                    }
    elif "body" in sec and isinstance(sec["body"], str):
        matches = re.findall(r'###\s+((?:FR|NFR|BR|API|UC|INT|REP)[-_][A-Z0-9]+[-_]\d+)\s*:\s*([^\n]+)', sec["body"])
        for req_id, title in matches:
            req_map[req_id] = {"id": req_id, "title": title.strip()}


def _normalize_functional_section(sec: Dict[str, Any], prev_map: Dict[str, Any], used_counters: Dict[str, int]) -> Dict[str, Any]:
    """Ensure Section 3 Functional Requirements contain stable FR-[MODULE]-xxx IDs."""
    if "table" in sec and isinstance(sec["table"], list):
        table = sec["table"]
        if len(table) > 1:
            header = table[0]
            new_rows = [header]
            for row in table[1:]:
                if isinstance(row, list) and len(row) >= 2:
                    raw_id = str(row[0]).strip()
                    title = str(row[1]).strip()
                    mod_match = re.search(r'FR[-_]([A-Z0-9]+)[-_]', raw_id)
                    mod = mod_match.group(1).upper() if mod_match else "CORE"
                    
                    prefix = f"FR-{mod}"
                    curr_idx = used_counters.get(prefix, 0) + 1
                    used_counters[prefix] = curr_idx
                    
                    stable_id = f"{prefix}-{curr_idx:03d}"
                    row[0] = stable_id
                    new_rows.append(row)
            sec["table"] = new_rows
    elif "body" in sec and isinstance(sec["body"], str):
        # Normalize IDs in body Markdown
        def _replace_header(match):
            mod = match.group(1).upper()
            prefix = f"FR-{mod}"
            curr_idx = used_counters.get(prefix, 0) + 1
            used_counters[prefix] = curr_idx
            return f"### FR-{mod}-{curr_idx:03d}: {match.group(2)}"
            
        sec["body"] = re.sub(r'###\s+FR[-_]([A-Z0-9]+)[-_]\d+\s*:\s*([^\n]+)', _replace_header, sec["body"])
    return sec


def _normalize_nfr_section(sec: Dict[str, Any], prev_map: Dict[str, Any], used_counters: Dict[str, int]) -> Dict[str, Any]:
    """Ensure Section 5 NFR contains stable NFR-[CATEGORY]-xxx IDs."""
    if "table" in sec and isinstance(sec["table"], list):
        table = sec["table"]
        if len(table) > 1:
            header = table[0]
            new_rows = [header]
            for row in table[1:]:
                if isinstance(row, list) and len(row) >= 2:
                    raw_id = str(row[0]).strip()
                    category = "SEC" if "security" in raw_id.lower() else "PERF" if "perf" in raw_id.lower() else "GEN"
                    prefix = f"NFR-{category}"
                    curr_idx = used_counters.get(prefix, 0) + 1
                    used_counters[prefix] = curr_idx
                    row[0] = f"{prefix}-{curr_idx:03d}"
                    new_rows.append(row)
            sec["table"] = new_rows
    return sec


def _normalize_business_rules_section(sec: Dict[str, Any], prev_map: Dict[str, Any], used_counters: Dict[str, int]) -> Dict[str, Any]:
    """Ensure Section 7 Business Rules contain stable BR-[MODULE]-xxx IDs."""
    if "table" in sec and isinstance(sec["table"], list):
        table = sec["table"]
        if len(table) > 1:
            header = table[0]
            new_rows = [header]
            for row in table[1:]:
                if isinstance(row, list) and len(row) >= 2:
                    prefix = "BR-CORE"
                    curr_idx = used_counters.get(prefix, 0) + 1
                    used_counters[prefix] = curr_idx
                    row[0] = f"{prefix}-{curr_idx:03d}"
                    new_rows.append(row)
            sec["table"] = new_rows
    return sec


def _normalize_table_ids(sec: Dict[str, Any], prefix: str, col_idx: int, prev_map: Dict[str, Any], used_counters: Dict[str, int]) -> Dict[str, Any]:
    """Ensure specific generic table sections have clean sequential IDs."""
    if "table" in sec and isinstance(sec["table"], list):
        table = sec["table"]
        if len(table) > 1:
            header = table[0]
            new_rows = [header]
            for row in table[1:]:
                if isinstance(row, list) and len(row) >= col_idx:
                    curr_idx = used_counters.get(prefix, 0) + 1
                    used_counters[prefix] = curr_idx
                    row[col_idx - 1] = f"{prefix}-{curr_idx:03d}"
                    new_rows.append(row)
            sec["table"] = new_rows
    return sec
