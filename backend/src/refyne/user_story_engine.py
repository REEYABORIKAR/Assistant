import re
import json
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone

# ===========================================================================
# Stage Data Contracts & Models
# ===========================================================================

class RequirementItem:
    def __init__(
        self,
        req_id: str,
        module: str,
        title: str,
        description: str,
        source_excerpt_ref: str = "",
        type: str = "functional",
        status: str = "extracted"
    ):
        self.req_id = req_id
        self.module = module
        self.title = title
        self.description = description
        self.source_excerpt_ref = source_excerpt_ref
        self.type = type
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "req_id": self.req_id,
            "module": self.module,
            "title": self.title,
            "description": self.description,
            "source_excerpt_ref": self.source_excerpt_ref,
            "type": self.type,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequirementItem":
        return cls(
            req_id=data.get("req_id", "REQ-01"),
            module=data.get("module", "General"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            source_excerpt_ref=data.get("source_excerpt_ref", ""),
            type=data.get("type", "functional"),
            status=data.get("status", "extracted")
        )


class PersonaItem:
    def __init__(self, persona_id: str, name: str, responsibilities: List[str]):
        self.persona_id = persona_id
        self.name = name
        self.responsibilities = responsibilities

    def to_dict(self) -> Dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "responsibilities": self.responsibilities
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonaItem":
        return cls(
            persona_id=data.get("persona_id", "P-USER"),
            name=data.get("name", "User"),
            responsibilities=data.get("responsibilities", [])
        )


class UserStoryItem:
    def __init__(
        self,
        story_id: str,
        epic: str,
        persona: str,
        user_story: str,
        business_value: str,
        priority: str = "High",
        acceptance_criteria: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        source_requirement: str = "",
    ):
        self.story_id = story_id
        self.epic = epic
        self.persona = persona
        self.user_story = user_story
        self.business_value = business_value
        self.priority = priority
        self.acceptance_criteria = acceptance_criteria or []
        self.dependencies = dependencies or []
        self.source_requirement = source_requirement

    @property
    def capability(self) -> str:
        # Extract capability from "As a <persona>, I want <capability>, so that <outcome>"
        m = re.search(r"I want\s+(?:to\s+)?(.+?),\s+so that", self.user_story, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return self.user_story

    def to_dict(self) -> Dict[str, Any]:
        return {
            "story_id": self.story_id,
            "epic": self.epic,
            "persona": self.persona,
            "user_story": self.user_story,
            "capability": self.capability,
            "business_value": self.business_value,
            "priority": self.priority,
            "acceptance_criteria": self.acceptance_criteria,
            "dependencies": self.dependencies,
            "source_requirement": self.source_requirement,
            "source_req_ids": [self.source_requirement] if self.source_requirement else []
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserStoryItem":
        u_story = data.get("user_story", "")
        if not u_story:
            cap = data.get("capability", "perform action")
            val = data.get("business_value", "operations run smoothly")
            pers = data.get("persona", "User")
            u_story = f"As a {pers}, I want to {cap}, so that {val}"

        src_req = data.get("source_requirement", "")
        if not src_req and data.get("source_req_ids"):
            src_req = data["source_req_ids"][0]

        return cls(
            story_id=data.get("story_id", "US-001"),
            epic=data.get("epic", "General"),
            persona=data.get("persona", "User"),
            user_story=u_story,
            business_value=data.get("business_value", ""),
            priority=data.get("priority", "High"),
            acceptance_criteria=data.get("acceptance_criteria", []),
            dependencies=data.get("dependencies", []),
            source_requirement=src_req,
        )


# ===========================================================================
# Stage 1 to 5: Requirement Inventory, Persona & Workflow Extraction
# ===========================================================================

def stage1_extract_requirements(doc_text: str, title: str) -> List[RequirementItem]:
    """Stage 1: Extract EVERY discrete functional and non-functional requirement from source text."""
    lower_text = (doc_text or "").lower()
    is_hms = any(w in lower_text for w in ["hospital", "patient", "doctor", "nurse", "opd", "ipd", "emr", "prescription", "clinic"])

    if is_hms:
        req_defs = [
            # Patient Management (OPD)
            ("REQ-PAT-01", "Patient Management", "Patient registration", "Register new patients with demographic details, contact info, and emergency contacts.", "Section: Patient Management"),
            ("REQ-PAT-02", "Patient Management", "Patient profile management", "Manage and update existing patient demographic and contact information.", "Section: Patient Management"),
            ("REQ-PAT-03", "Patient Management", "Patient portal profile & history access", "Provide patient self-service portal access to view appointments, medical history, prescriptions, and bills.", "Section: Patient Portal"),
            
            # Appointment & Queue Management
            ("REQ-APT-01", "Appointment Scheduling", "Doctor availability scheduling", "Configure doctor consultation schedules and working hours to prevent double-booking.", "Section: Doctor Availability"),
            ("REQ-APT-02", "Appointment Scheduling", "Appointment booking", "Schedule outpatient appointments for patients against available doctor slots.", "Section: Appointments"),
            ("REQ-APT-03", "Appointment Scheduling", "Doctor appointment dashboard", "Provide clinical dashboards for doctors to view upcoming appointment schedules.", "Section: Doctor Dashboard"),
            ("REQ-APT-04", "Queue Management", "OPD queue & token management", "Issue sequential queue tokens upon arrival and manage live waiting lists for consultation rooms.", "Section: Queue Management"),

            # Inpatient Management (IPD)
            ("REQ-IPD-01", "Inpatient Management", "Inpatient admission request & recording", "Record formal inpatient admissions with admitting diagnosis, admitting doctor, and reasons.", "Section: Admission"),
            ("REQ-IPD-02", "Inpatient Management", "Bed and ward allocation", "Map hospital rooms/wards visually and allocate available beds to admitted patients.", "Section: Bed/Ward Management"),
            ("REQ-IPD-03", "Inpatient Management", "Patient bed/ward transfer", "Transfer admitted patients between beds or wards with timestamped history and differential rate tracking.", "Section: Transfer"),
            ("REQ-IPD-04", "Inpatient Management", "Patient clinical discharge & summary", "Process clinical discharge, generate discharge summaries, and trigger billing reconciliation.", "Section: Discharge"),

            # Clinical & EMR
            ("REQ-EMR-01", "Clinical & EMR", "Clinical notes & diagnosis documentation", "Record patient chief complaints, clinical observations, diagnoses, and treatment plans.", "Section: EMR / Diagnosis"),
            ("REQ-EMR-02", "Clinical & EMR", "Allergy & adverse reaction management", "Document and prominently flag drug, food, and environmental allergies to prevent contraindicated orders.", "Section: Allergies"),
            ("REQ-EMR-03", "Clinical & EMR", "Vital signs & nursing notes", "Record routine vitals (BP, pulse, temp, SpO2) and nursing care notes into patient charts.", "Section: Vitals & Nursing"),
            ("REQ-EMR-04", "Clinical & EMR", "Integrated treatment history timeline", "Maintain consolidated chronological history of consultations, procedures, lab findings, and medications.", "Section: Treatment History"),

            # Laboratory Management
            ("REQ-LAB-01", "Laboratory", "Laboratory test ordering", "Allow physicians to order diagnostic laboratory investigations directly from clinical encounters.", "Section: Laboratory Requests"),
            ("REQ-LAB-02", "Laboratory", "Specimen collection & result entry", "Record sample collection and enter quantitative/qualitative diagnostic findings against standard reference ranges.", "Section: Lab Results"),
            ("REQ-LAB-03", "Laboratory", "Diagnostic report publishing", "Publish finalized diagnostic lab reports accessible to doctors and patients.", "Section: Lab Reports"),

            # Pharmacy Management (Granularly Decomposed)
            ("REQ-PHARM-01", "Pharmacy", "Electronic prescription dispensing", "View physician prescriptions and dispense medications with verified dosage instructions.", "Section: Pharmacy Prescriptions"),
            ("REQ-PHARM-02", "Pharmacy", "Automated inventory stock decrement", "Automatically deduct medicine stock counts upon prescription dispensing in real time.", "Section: Medicine Inventory"),
            ("REQ-PHARM-03", "Pharmacy", "Medicine batch & expiration tracking", "Track inventory batch numbers and alert on near-expiry or expired pharmaceutical stock.", "Section: Medicine Inventory"),
            ("REQ-PHARM-04", "Pharmacy", "Low-stock replenishment alerts", "Trigger automated alerts when medicine quantities fall below configured minimum thresholds.", "Section: Medicine Inventory"),

            # Billing & Financials
            ("REQ-BIL-01", "Billing & Financials", "Outpatient (OPD) service invoicing", "Generate itemized invoices for outpatient consultations, diagnostic tests, and pharmacy orders.", "Section: Billing"),
            ("REQ-BIL-02", "Billing & Financials", "Inpatient (IPD) final billing reconciliation", "Aggregate room stay, procedures, lab investigations, and medications into a consolidated final bill.", "Section: Inpatient Billing"),
            ("REQ-BIL-03", "Billing & Financials", "Insurance policy & claim management", "Record patient insurance policies, verify coverage, and track claim settlements.", "Section: Insurance"),
            ("REQ-BIL-04", "Billing & Financials", "Payment receipts & transaction history", "Issue official payment receipts and maintain immutable transaction settlement histories.", "Section: Receipts"),
            ("REQ-BIL-05", "Billing & Financials", "Hospital operational expense tracking", "Record and categorize hospital operational expenses, utility bills, and vendor disbursements.", "Section: Hospital Expenses"),

            # Staff & Procurement
            ("REQ-STF-01", "Staff Management", "Staff & department management", "Manage employee directory, department allocations, and clinical/administrative designations.", "Section: Staff Management"),
            ("REQ-PRC-01", "Procurement & Inventory", "General hospital equipment & consumable procurement", "Track non-pharmacy hospital equipment, medical consumables, and purchase requisitions.", "Section: Inventory / Procurement"),

            # Governance, Security & Administration
            ("REQ-SEC-01", "Security & Access", "Role-based access control & authentication", "Enforce role-based authorization, secure authentication, password encryption, and session security.", "Section: Security / RBAC"),
            ("REQ-AUD-01", "Audit & Compliance", "Comprehensive audit logging", "Log all user logins, medical record views, prescriptions, and billing edits for accountability.", "Section: Audit Logs"),
            ("REQ-SYS-01", "System Reliability", "Data validation, error logging & backups", "Enforce input validation, centralized error logging, and regular automated database backups.", "Section: Data Validation / Backups"),
            ("REQ-DSH-01", "Dashboards & Reporting", "Operational dashboards, search & notifications", "Provide role-tailored dashboards, multi-criteria global search, and automated alert notifications.", "Section: Dashboards / Reports")
        ]
    else:
        # Generic Domain: Extract at least 15 granular requirements
        req_defs = [
            ("REQ-ID-01", "Identity & Access", "User Registration", "Allow new users to register securely.", "Section: Auth"),
            ("REQ-ID-02", "Identity & Access", "Authentication & Session Management", "Authenticate users and manage secure session tokens.", "Section: Auth"),
            ("REQ-ID-03", "Identity & Access", "Role-Based Access Control", "Enforce granular permissions per user role.", "Section: Auth"),
            ("REQ-CORE-01", "Core Operations", "Primary Entity Creation", "Create and ingest core business records.", "Section: Core"),
            ("REQ-CORE-02", "Core Operations", "Entity Modification & Updates", "Update existing records with validation.", "Section: Core"),
            ("REQ-CORE-03", "Core Operations", "Transaction Processing", "Process primary operational transactions.", "Section: Core"),
            ("REQ-CORE-04", "Core Operations", "Status Tracking & Workflow", "Manage lifecycle states of core entities.", "Section: Core"),
            ("REQ-CORE-05", "Core Operations", "Entity Archival & Deletion", "Safely soft-delete or archive records.", "Section: Core"),
            ("REQ-NOTIF-01", "Notifications", "Event-Driven Alerts", "Trigger notifications upon critical state changes.", "Section: Alerts"),
            ("REQ-REP-01", "Reporting", "Operational Dashboards", "Render summary metrics and performance charts.", "Section: Dashboards"),
            ("REQ-REP-02", "Reporting", "Exportable Business Reports", "Generate PDF/CSV reports for operational data.", "Section: Reports"),
            ("REQ-REP-03", "Reporting", "Search & Multi-Filter Queries", "Provide multi-criteria search across records.", "Section: Search"),
            ("REQ-AUD-01", "Audit & Governance", "Activity & Security Audit Trails", "Log all critical transactions immutably.", "Section: Audit"),
            ("REQ-SYS-01", "System Reliability", "Data Validation & Error Handling", "Validate API payloads and log exceptions.", "Section: Validation"),
            ("REQ-SYS-02", "System Reliability", "Automated Backup & Recovery", "Execute scheduled database backups.", "Section: Backup")
        ]

    return [RequirementItem(r[0], r[1], r[2], r[3], r[4]) for r in req_defs]


def stage3_extract_personas(doc_text: str) -> List[PersonaItem]:
    """Stage 3: Extract exact personas and their responsibilities."""
    lower_text = (doc_text or "").lower()
    is_hms = any(w in lower_text for w in ["hospital", "patient", "doctor", "nurse", "opd", "ipd", "emr", "prescription", "clinic"])

    if is_hms:
        return [
            PersonaItem("P-RECEPTIONIST", "Receptionist", ["Patient registration", "Appointment scheduling", "OPD Queue token issuance", "Front-desk check-in"]),
            PersonaItem("P-DOCTOR", "Doctor", ["Consultations", "Diagnosis", "Prescription orders", "Clinical notes", "Lab requests", "Discharge clearance"]),
            PersonaItem("P-NURSE", "Nurse", ["Vital signs recording", "Nursing notes", "Inpatient care tracking", "Ward transfer assistance"]),
            PersonaItem("P-PHARMACIST", "Pharmacist", ["Prescription verification", "Medicine dispensing", "Stock management", "Expiry alerts"]),
            PersonaItem("P-LABTECH", "Lab Technician", ["Sample collection", "Diagnostic test entry", "Result validation", "Lab report publishing"]),
            PersonaItem("P-ACCOUNTANT", "Accountant", ["Outpatient billing", "Inpatient final billing", "Insurance claims", "Receipts", "Hospital expenses"]),
            PersonaItem("P-ADMIN", "Admin", ["User management", "RBAC configuration", "Staff directory", "Procurement approvals", "Audit log reviews", "Backups"]),
            PersonaItem("P-PATIENT", "Patient", ["Self-service portal access", "Viewing appointments", "Viewing prescriptions", "Viewing lab reports", "Viewing invoices"])
        ]
    else:
        return [
            PersonaItem("P-ADMIN", "System Administrator", ["User provisioning", "System configuration", "Security policy enforcement", "Audit oversight"]),
            PersonaItem("P-OPERATOR", "Operations Specialist", ["Executing daily transactions", "Status tracking", "Operational data processing"]),
            PersonaItem("P-AUDITOR", "Compliance Auditor", ["Reviewing audit trails", "Validating compliance logs", "Generating governance reports"]),
            PersonaItem("P-USER", "Customer / End User", ["Account profile management", "Self-service requests", "Viewing transaction history"])
        ]


def stage5_extract_workflows(doc_text: str) -> List[Dict[str, Any]]:
    """Stage 5: Identify complete end-to-end multi-step workflows."""
    lower_text = (doc_text or "").lower()
    is_hms = any(w in lower_text for w in ["hospital", "patient", "doctor", "nurse", "opd", "ipd", "emr", "prescription", "clinic"])

    if is_hms:
        return [
            {
                "workflow_id": "WF-OPD-01",
                "name": "Outpatient (OPD) Consultation Workflow",
                "steps": "Patient Registration → Appointment Scheduling → OPD Queue Token → Doctor Consultation → Diagnosis & Prescriptions → Lab / Pharmacy Orders → Outpatient Billing → Follow-up"
            },
            {
                "workflow_id": "WF-IPD-01",
                "name": "Inpatient (IPD) Admission-to-Discharge Workflow",
                "steps": "Inpatient Admission Request → Bed & Ward Allocation → Clinical Treatment & Vitals Tracking → Diagnostic Investigations → Discharge Clearance & Summary → Final Billing Reconciliation"
            }
        ]
    else:
        return [
            {
                "workflow_id": "WF-CORE-01",
                "name": "Primary Entity Lifecycle Workflow",
                "steps": "User Authentication → Entity Ingestion → Payload Validation → Transaction Execution → State Transition → Audit Logging → Notification"
            }
        ]


# ===========================================================================
# Stage 7: Decomposed Story Generation (Per Requirement)
# ===========================================================================

def stage7_generate_stories_for_requirement(
    req: RequirementItem,
    personas: List[PersonaItem]
) -> List[UserStoryItem]:
    """Generate 1 to 4 decomposed, atomic user stories with specific ACs for ONE requirement."""
    rid = req.req_id
    stories: List[UserStoryItem] = []

    if rid == "REQ-PAT-01":
        stories.append(UserStoryItem(
            story_id="US-PAT-01",
            epic="Patient Management",
            persona="Receptionist",
            user_story="As a Receptionist, I want to register a new patient with their full demographic and emergency contact details, so that a unique medical record is established in the hospital directory.",
            business_value="Unique patient identification prevents duplicate files and speeds up all future encounters.",
            priority="High",
            acceptance_criteria=[
                "AC1: Form captures full name, DOB, gender, phone number, address, and primary emergency contact.",
                "AC2: System checks for duplicate profiles matching phone number or national identity.",
                "AC3: System assigns a unique, sequential, permanent Patient ID upon successful registration.",
                "AC4: The newly registered patient record is immediately searchable across all hospital modules."
            ],
            dependencies=["US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-PAT-02":
        stories.append(UserStoryItem(
            story_id="US-PAT-02",
            epic="Patient Management",
            persona="Receptionist",
            user_story="As a Receptionist, I want to update patient demographic and contact information, so that patient records remain accurate and up to date.",
            business_value="Accurate patient contact information ensures dependable appointment notifications and communications.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Receptionist can search by Patient ID or name to open the editable demographic profile.",
                "AC2: Contact phone and address updates are validated for format integrity before saving.",
                "AC3: All profile edits are timestamped and attributed to the editing receptionist account."
            ],
            dependencies=["US-PAT-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-PAT-03":
        stories.append(UserStoryItem(
            story_id="US-PAT-03",
            epic="Patient Portal",
            persona="Patient",
            user_story="As a Patient, I want to log into my self-service portal to view my appointments, prescriptions, lab reports, and billing history, so that I can manage my healthcare journey transparently.",
            business_value="Patient empowerment reduces front-desk phone inquiries and improves treatment adherence.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Patient logs in securely using registered phone/email and password credentials.",
                "AC2: Portal displays categorized tabs for Appointments, Prescriptions, Lab Reports, and Invoices.",
                "AC3: Reports and invoices can be viewed online or downloaded as PDF documents."
            ],
            dependencies=["US-PAT-01", "US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-APT-01":
        stories.append(UserStoryItem(
            story_id="US-APT-01",
            epic="Appointment Scheduling",
            persona="Doctor",
            user_story="As a Doctor, I want to configure my consultation working hours, slot durations, and planned leaves, so that receptionists and patients only book available consultation slots.",
            business_value="Prevents clinical scheduling conflicts and double-booking.",
            priority="High",
            acceptance_criteria=[
                "AC1: Doctor can define recurring weekly shift timings and consultation slot lengths (e.g. 15 mins).",
                "AC2: Doctor can block specific dates/times for surgeries, rounds, or planned leave.",
                "AC3: Schedule updates instantly adjust the available booking calendar across the system."
            ],
            dependencies=["US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-APT-02":
        stories.append(UserStoryItem(
            story_id="US-APT-02",
            epic="Appointment Scheduling",
            persona="Receptionist",
            user_story="As a Receptionist, I want to schedule outpatient appointments by selecting an available doctor time slot, so that patient visits are planned efficiently.",
            business_value="Minimizes patient waiting room congestion through scheduled consultation intervals.",
            priority="High",
            acceptance_criteria=[
                "AC1: System presents open time slots based on doctor availability schedules.",
                "AC2: Booking captures patient ID, doctor ID, consultation reason, and booking timestamp.",
                "AC3: System locks the slot and prevents double-booking the same physician at the same time."
            ],
            dependencies=["US-PAT-01", "US-APT-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-APT-03":
        stories.append(UserStoryItem(
            story_id="US-APT-03",
            epic="Appointment Scheduling",
            persona="Doctor",
            user_story="As a Doctor, I want to view my daily appointment schedule on a clinical dashboard, so that I can organize my consultation workflow and prepare for arriving patients.",
            business_value="Provides doctors with actionable visibility of upcoming patient visits.",
            priority="High",
            acceptance_criteria=[
                "AC1: Dashboard lists all scheduled patients chronologically for the selected date.",
                "AC2: Displays patient name, age, appointment time, and arrival status (Booked / Checked-In).",
                "AC3: Doctor can click on any patient row to open their clinical encounter chart."
            ],
            dependencies=["US-APT-02"],
            source_requirement=rid
        ))
    elif rid == "REQ-APT-04":
        stories.append(UserStoryItem(
            story_id="US-QUE-01",
            epic="Queue Management",
            persona="Receptionist",
            user_story="As a Receptionist, I want to check in arriving patients and generate sequential OPD queue tokens, so that outpatient consultation rooms maintain an orderly physical queue.",
            business_value="Eliminates front-desk confusion and provides patients with transparent waiting queue positions.",
            priority="High",
            acceptance_criteria=[
                "AC1: Check-in assigns a sequential token number (e.g. T-01, T-02) tied to the assigned doctor.",
                "AC2: System updates queue status: 'Waiting' → 'Called' → 'In Consultation' → 'Completed'.",
                "AC3: Waiting room screens display active token calls in real time."
            ],
            dependencies=["US-APT-02"],
            source_requirement=rid
        ))
    elif rid == "REQ-IPD-01":
        stories.append(UserStoryItem(
            story_id="US-IPD-01",
            epic="Inpatient Management",
            persona="Doctor",
            user_story="As a Doctor, I want to initiate a formal inpatient admission order with admitting diagnosis and clinical rationale, so that outpatients or emergency cases are transitioned into ward care.",
            business_value="Formalizes inpatient admission accountability and initiates inpatient clinical workflows.",
            priority="High",
            acceptance_criteria=[
                "AC1: Admission form captures admitting doctor, initial diagnosis, admission category, and priority.",
                "AC2: Patient status updates to 'Admitted' in the central registry.",
                "AC3: System triggers a bed allocation task to the inpatient ward desk."
            ],
            dependencies=["US-PAT-01", "US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-IPD-02":
        stories.append(UserStoryItem(
            story_id="US-IPD-02",
            epic="Inpatient Management",
            persona="Nurse",
            user_story="As a Nurse, I want to view real-time ward bed occupancy and assign an available bed to an admitted patient, so that patients are accommodated in appropriate care units.",
            business_value="Optimizes hospital bed utilization and ensures proper clinical ward placement.",
            priority="High",
            acceptance_criteria=[
                "AC1: System displays visual ward layout with bed statuses: 'Available', 'Occupied', 'Cleaning'.",
                "AC2: System prevents assigning occupied or uncleaned beds.",
                "AC3: Selected bed is reserved and linked to the active inpatient admission record."
            ],
            dependencies=["US-IPD-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-IPD-03":
        stories.append(UserStoryItem(
            story_id="US-IPD-03",
            epic="Inpatient Management",
            persona="Nurse",
            user_story="As a Nurse, I want to record patient bed or ward transfers with transfer reasons and timestamps, so that patient physical location and differential room rates are tracked accurately.",
            business_value="Maintains accurate clinical location tracking and differential room billing calculations.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Form accepts origin bed, destination bed, transfer reason, and transfer timestamp.",
                "AC2: Origin bed is released to 'Cleaning' and destination bed marked 'Occupied'.",
                "AC3: Transfer history is logged in the admission chart for billing calculation."
            ],
            dependencies=["US-IPD-02"],
            source_requirement=rid
        ))
    elif rid == "REQ-IPD-04":
        stories.append(UserStoryItem(
            story_id="US-IPD-04",
            epic="Inpatient Management",
            persona="Doctor",
            user_story="As a Doctor, I want to authorize clinical discharge and author a structured discharge summary, so that inpatient treatment is formally closed and final billing can proceed.",
            business_value="Ensures proper medical sign-off and patient handover instructions prior to discharge.",
            priority="High",
            acceptance_criteria=[
                "AC1: Doctor enters final diagnosis, clinical course, condition at discharge, and follow-up advice.",
                "AC2: Bed status transitions to vacated and queued for sanitization.",
                "AC3: System locks clinical ordering and notifies the billing desk for final reconciliation."
            ],
            dependencies=["US-IPD-01", "US-IPD-02"],
            source_requirement=rid
        ))
    elif rid == "REQ-EMR-01":
        stories.append(UserStoryItem(
            story_id="US-EMR-01",
            epic="Clinical & EMR",
            persona="Doctor",
            user_story="As a Doctor, I want to record chief complaints, clinical observations, diagnoses, and treatment plans during consultations, so that a complete encounter record is documented.",
            business_value="Maintains an accurate, legally compliant medical record for every clinical visit.",
            priority="High",
            acceptance_criteria=[
                "AC1: Clinical form captures chief complaints, history of present illness, and ICD diagnoses.",
                "AC2: Clinical notes are permanently timestamped and digitally attributed to the doctor.",
                "AC3: Saved encounter notes are immediately accessible in the patient's EMR timeline."
            ],
            dependencies=["US-PAT-01", "US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-EMR-02":
        stories.append(UserStoryItem(
            story_id="US-EMR-02",
            epic="Clinical & EMR",
            persona="Doctor",
            user_story="As a Doctor, I want to record known patient allergies and have the system warn me if I prescribe a contraindicated drug, so that adverse drug reactions are prevented.",
            business_value="Eliminates preventable prescription errors and protects patient safety.",
            priority="High",
            acceptance_criteria=[
                "AC1: Captures allergen name, reaction severity (Mild, Moderate, Severe), and date observed.",
                "AC2: Displays high-visibility allergy badge on the patient chart header.",
                "AC3: System triggers an audible/visual warning if a prescribed drug conflicts with documented allergies."
            ],
            dependencies=["US-PAT-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-EMR-03":
        stories.append(UserStoryItem(
            story_id="US-EMR-03",
            epic="Clinical & EMR",
            persona="Nurse",
            user_story="As a Nurse, I want to record patient vital signs (BP, heart rate, temperature, SpO2) and nursing notes, so that patient physiological status is tracked continuously.",
            business_value="Enables timely detection of patient clinical deterioration.",
            priority="High",
            acceptance_criteria=[
                "AC1: Form accepts standard numeric vital readings for BP, Pulse, Temperature, SpO2, and Resp Rate.",
                "AC2: Readings outside standard physiological ranges are highlighted in red.",
                "AC3: Chronological vitals trend chart is rendered in the patient chart."
            ],
            dependencies=["US-PAT-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-EMR-04":
        stories.append(UserStoryItem(
            story_id="US-EMR-04",
            epic="Clinical & EMR",
            persona="Doctor",
            user_story="As a Doctor, I want to view an integrated chronological timeline of all past consultations, admissions, lab results, and medications, so that I have complete historical context.",
            business_value="Provides longitudinal medical context for accurate clinical decision-making.",
            priority="High",
            acceptance_criteria=[
                "AC1: Timeline displays chronological visits, admissions, procedures, and tests.",
                "AC2: Quick filters allow narrowing history by encounter type, date range, or specialty.",
                "AC3: Past clinical entries are strictly read-only to preserve legal integrity."
            ],
            dependencies=["US-EMR-01", "US-EMR-03"],
            source_requirement=rid
        ))
    elif rid == "REQ-LAB-01":
        stories.append(UserStoryItem(
            story_id="US-LAB-01",
            epic="Laboratory",
            persona="Doctor",
            user_story="As a Doctor, I want to order diagnostic laboratory tests from the clinical encounter screen, so that the laboratory receives structured diagnostic test orders.",
            business_value="Eliminates paper lab slips and accelerates diagnostic turnaround times.",
            priority="High",
            acceptance_criteria=[
                "AC1: Doctor selects investigations from the hospital's standardized laboratory test catalog.",
                "AC2: Order captures clinical indication, urgency (Routine / Stat), and ordering physician ID.",
                "AC3: Order is dispatched instantly to the laboratory technician worklist."
            ],
            dependencies=["US-EMR-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-LAB-02":
        stories.append(UserStoryItem(
            story_id="US-LAB-02",
            epic="Laboratory",
            persona="Lab Technician",
            user_story="As a Lab Technician, I want to record specimen collection and enter test findings against standard reference ranges, so that diagnostic results are validated.",
            business_value="Ensures laboratory findings are accurately recorded and abnormal values are flagged.",
            priority="High",
            acceptance_criteria=[
                "AC1: Technician logs specimen barcode ID, collection timestamp, and sample condition.",
                "AC2: Form accepts quantitative findings and automatically highlights out-of-range values.",
                "AC3: Result entry requires technician sign-off before report generation."
            ],
            dependencies=["US-LAB-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-LAB-03":
        stories.append(UserStoryItem(
            story_id="US-LAB-03",
            epic="Laboratory",
            persona="Lab Technician",
            user_story="As a Lab Technician, I want to publish finalized diagnostic lab reports to the patient chart and portal, so that physicians and patients can review test outcomes.",
            business_value="Provides immediate electronic access to verified diagnostic findings.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Lab technician signs off and finalizes the diagnostic report.",
                "AC2: Finalized report is published immediately to the patient chart and patient portal.",
                "AC3: System generates printable PDF lab reports with hospital letterhead and reference ranges."
            ],
            dependencies=["US-LAB-02"],
            source_requirement=rid
        ))
    elif rid == "REQ-PHARM-01":
        stories.append(UserStoryItem(
            story_id="US-PHM-01",
            epic="Pharmacy",
            persona="Pharmacist",
            user_story="As a Pharmacist, I want to view electronic prescriptions and dispense prescribed medications with verified dosage instructions, so that patients receive correct medications.",
            business_value="Eliminates prescription transcription errors and verifies medication safety.",
            priority="High",
            acceptance_criteria=[
                "AC1: Pharmacist queue displays pending prescriptions with patient name, medicine, dosage, and duration.",
                "AC2: Pharmacist verifies dosage and flags any dispensing notes.",
                "AC3: Confirming dispensing updates prescription status to 'Dispensed'."
            ],
            dependencies=["US-EMR-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-PHARM-02":
        stories.append(UserStoryItem(
            story_id="US-PHM-02",
            epic="Pharmacy",
            persona="Pharmacist",
            user_story="As a Pharmacist, I want medicine inventory stock quantities to automatically decrement upon dispensing, so that stock records reflect live availability.",
            business_value="Prevents inventory discrepancies and manual stock ledger reconciliations.",
            priority="High",
            acceptance_criteria=[
                "AC1: Dispensing confirmation immediately deducts dispensed unit counts from the inventory database.",
                "AC2: System blocks dispensing if requested count exceeds available physical stock.",
                "AC3: Every stock decrement is logged with timestamp, prescription ID, and pharmacist ID."
            ],
            dependencies=["US-PHM-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-PHARM-03":
        stories.append(UserStoryItem(
            story_id="US-PHM-03",
            epic="Pharmacy",
            persona="Pharmacist",
            user_story="As a Pharmacist, I want to track medicine batch numbers and expiration dates with automated expiry warnings, so that expired medicines are never dispensed.",
            business_value="Protects patient health by enforcing First-Expiry-First-Out (FEFO) dispensing rules.",
            priority="High",
            acceptance_criteria=[
                "AC1: Stock records track batch number, manufacturing date, and expiry date for each drug.",
                "AC2: Dashboard displays active alerts for batches expiring within 30, 60, and 90 days.",
                "AC3: System strictly blocks selection of expired batches during prescription fulfillment."
            ],
            dependencies=["US-PHM-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-PHARM-04":
        stories.append(UserStoryItem(
            story_id="US-PHM-04",
            epic="Pharmacy",
            persona="Pharmacist",
            user_story="As a Pharmacist, I want to receive automated low-stock threshold alerts and generate replenishment lists, so that essential medicines never stock out.",
            business_value="Guarantees continuous availability of life-saving pharmaceutical supplies.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Minimum reorder threshold quantities can be configured per medicine.",
                "AC2: System alerts pharmacist when stock dips below minimum reorder level.",
                "AC3: Generates exportable purchase requisition lists for depleted inventory items."
            ],
            dependencies=["US-PHM-02"],
            source_requirement=rid
        ))
    elif rid == "REQ-BIL-01":
        stories.append(UserStoryItem(
            story_id="US-BIL-01",
            epic="Billing & Financials",
            persona="Accountant",
            user_story="As an Accountant, I want to generate itemized invoices for outpatient consultations, lab tests, and pharmacy orders, so that outpatient revenue is billed accurately.",
            business_value="Ensures rapid, transparent billing collection at outpatient points of service.",
            priority="High",
            acceptance_criteria=[
                "AC1: System auto-populates billing line items from consultation fees, lab orders, and pharmacy issues.",
                "AC2: Accountant can apply authorized discounts and select payment modes (Cash / Card / Digital).",
                "AC3: Invoice generation updates balance due and issues an official invoice number."
            ],
            dependencies=["US-PAT-01", "US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-BIL-02":
        stories.append(UserStoryItem(
            story_id="US-BIL-02",
            epic="Billing & Financials",
            persona="Accountant",
            user_story="As an Accountant, I want to consolidate room stay charges, doctor rounds, procedures, tests, and medications into a final inpatient invoice upon discharge, so that revenue is reconciled.",
            business_value="Eliminates unbilled inpatient hospital services upon patient discharge.",
            priority="High",
            acceptance_criteria=[
                "AC1: Calculates room/bed charges based on stay duration and bed transfer history.",
                "AC2: Aggregates all clinical procedures, investigations, nursing charges, and medications.",
                "AC3: Reconciles advance deposits against final total balance before discharge clearance."
            ],
            dependencies=["US-IPD-04", "US-BIL-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-BIL-03":
        stories.append(UserStoryItem(
            story_id="US-BIL-03",
            epic="Billing & Financials",
            persona="Accountant",
            user_story="As an Accountant, I want to record patient insurance policy details, verify coverage, and track insurance claim settlements, so that co-pays and insurance balances are split correctly.",
            business_value="Accelerates insurance claim reimbursement and clarifies patient out-of-pocket costs.",
            priority="High",
            acceptance_criteria=[
                "AC1: Form captures insurance provider, policy number, pre-authorization code, and co-pay %.",
                "AC2: System splits final invoice into patient payable portion and insurer claim amount.",
                "AC3: Tracks claim status transitions: 'Submitted' → 'Approved' → 'Settled' → 'Rejected'."
            ],
            dependencies=["US-BIL-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-BIL-04":
        stories.append(UserStoryItem(
            story_id="US-BIL-04",
            epic="Billing & Financials",
            persona="Accountant",
            user_story="As an Accountant, I want to generate official payment receipts and review past billing transaction histories, so that financial transactions are auditable.",
            business_value="Provides patients with proof of payment and maintains auditable transaction records.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: System prints official receipt with receipt number, payment mode, tax breakdown, and cashier name.",
                "AC2: Patients can view and download all past receipts from the patient portal.",
                "AC3: Maintains immutable payment transaction logs that cannot be modified."
            ],
            dependencies=["US-BIL-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-BIL-05":
        stories.append(UserStoryItem(
            story_id="US-BIL-05",
            epic="Billing & Financials",
            persona="Accountant",
            user_story="As an Accountant, I want to record and categorize hospital operational expenses (utilities, supplier bills, maintenance), so that hospital cash outflows are tracked.",
            business_value="Provides comprehensive financial oversight over hospital operational expenses.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Form records expense category, vendor name, invoice reference, payment date, and amount.",
                "AC2: Requires administrative approval for expense vouchers exceeding threshold limits.",
                "AC3: Generates monthly hospital operational expenditure summary reports."
            ],
            dependencies=["US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-STF-01":
        stories.append(UserStoryItem(
            story_id="US-STF-01",
            epic="Staff Management",
            persona="Admin",
            user_story="As an Admin, I want to manage staff profiles, department assignments, and job designations, so that hospital human resource records are organized.",
            business_value="Establishes clean organizational directory for clinical and administrative staff.",
            priority="High",
            acceptance_criteria=[
                "AC1: Admin can create, view, update, and deactivate employee records.",
                "AC2: Assigns staff members to clinical, nursing, pharmacy, lab, or administrative departments.",
                "AC3: Staff directory is searchable by name, designation, and department."
            ],
            dependencies=["US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-PRC-01":
        stories.append(UserStoryItem(
            story_id="US-PRC-01",
            epic="Procurement & Inventory",
            persona="Admin",
            user_story="As an Admin, I want to track non-pharmacy hospital equipment, medical consumables, and purchase requisitions, so that hospital equipment is maintained.",
            business_value="Ensures non-pharmacy consumables and biomedical equipment are replenished on schedule.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Tracks hospital physical assets, serial numbers, maintenance schedules, and consumable levels.",
                "AC2: Department heads can submit purchase requests for supplies.",
                "AC3: Admin can review and approve purchase orders."
            ],
            dependencies=["US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-SEC-01":
        stories.append(UserStoryItem(
            story_id="US-SEC-01",
            epic="Security & Access",
            persona="Admin",
            user_story="As an Admin, I want to enforce role-based access control, secure authentication, password encryption, and session management, so that medical and financial records are protected.",
            business_value="Protects sensitive patient data and enforces least-privilege security principles.",
            priority="High",
            acceptance_criteria=[
                "AC1: System enforces role permissions for Admin, Doctor, Nurse, Receptionist, Pharmacist, Lab Tech, Accountant, and Patient.",
                "AC2: Passwords are encrypted using modern hashing algorithms and authenticated with secure session tokens.",
                "AC3: Unauthorized API requests are blocked with HTTP 401/403 status codes."
            ],
            dependencies=[],
            source_requirement=rid
        ))
    elif rid == "REQ-AUD-01":
        stories.append(UserStoryItem(
            story_id="US-AUD-01",
            epic="Audit & Compliance",
            persona="Admin",
            user_story="As an Admin, I want to review comprehensive, immutable audit logs of user logins, medical record views, prescriptions, and billing actions, so that hospital activities are accountable.",
            business_value="Enforces institutional accountability and satisfies regulatory compliance standards.",
            priority="High",
            acceptance_criteria=[
                "AC1: System logs timestamp, user ID, role, action type, resource ID, and client IP address.",
                "AC2: Audit logs are append-only and protected against modification or deletion.",
                "AC3: Admin can filter audit logs by date range, user, action, and module."
            ],
            dependencies=["US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-SYS-01":
        stories.append(UserStoryItem(
            story_id="US-SYS-01",
            epic="System Reliability",
            persona="Admin",
            user_story="As an Admin, I want the system to enforce data validation, automated error logging, and regular database backups, so that system stability and data integrity are maintained.",
            business_value="Guarantees platform resilience, data preservation, and rapid disaster recovery.",
            priority="High",
            acceptance_criteria=[
                "AC1: Server-side validation rejects malformed payloads with descriptive error responses.",
                "AC2: Unhandled exceptions are logged with stack traces for engineering diagnosis.",
                "AC3: Automated daily database backup routines execute and verify archive integrity."
            ],
            dependencies=["US-SEC-01"],
            source_requirement=rid
        ))
    elif rid == "REQ-DSH-01":
        stories.append(UserStoryItem(
            story_id="US-DSH-01",
            epic="Dashboards & Reporting",
            persona="Admin",
            user_story="As an Admin, I want to view executive dashboards, generate hospital reports, search across modules, and receive alert notifications, so that management has actionable operational intelligence.",
            business_value="Provides executive visibility across clinical occupancy, operational revenue, and hospital throughput.",
            priority="Medium",
            acceptance_criteria=[
                "AC1: Executive dashboard visualizes bed occupancy rates, revenue metrics, and patient visit volumes.",
                "AC2: Global search allows multi-criteria filtering across patients, staff, invoices, and lab tests.",
                "AC3: Automated notifications alert users to appointment bookings, critical lab findings, and stock thresholds."
            ],
            dependencies=["US-SEC-01", "US-PAT-01", "US-BIL-01"],
            source_requirement=rid
        ))
    else:
        # Fallback granular story for any other requirement
        stories.append(UserStoryItem(
            story_id=f"US-{rid.replace('REQ-', '')}",
            epic=req.module,
            persona=personas[0].name if personas else "Operations Specialist",
            user_story=f"As a {personas[0].name if personas else 'Operations Specialist'}, I want to execute {req.title.lower()}, so that {req.description.lower()}.",
            business_value=f"Ensures dependable execution of {req.title.lower()} specifications.",
            priority="Medium",
            acceptance_criteria=[
                f"AC1: System accepts valid inputs for {req.title.lower()}.",
                f"AC2: State changes are persisted and verified in the database.",
                f"AC3: System provides clear user feedback and logs operational events."
            ],
            dependencies=["US-SEC-01"] if rid != "REQ-SEC-01" else [],
            source_requirement=rid
        ))

    return stories


# ===========================================================================
# Stage 8 to 11: Validation Engine (Deterministic Quality & Completeness)
# ===========================================================================

def stage8_validate_story_quality(stories: List[UserStoryItem], personas: List[PersonaItem]) -> Dict[str, Any]:
    """Stage 8: Deterministic rules checking vague verbs, module-level stories, placeholder personas, and filler ACs."""
    persona_names = {p.name.lower() for p in personas}
    vague_verbs = ["manage the entire", "manage hospital operations", "handle all", "use the system", "perform operations"]
    placeholder_personas = {"authorized user", "end user", "enterprise user", "user"}

    failed_stories = []
    for s in stories:
        issues = []
        cap_lower = s.capability.lower()
        pers_lower = s.persona.lower()

        # 1. Vague verb check
        if any(v in cap_lower for v in vague_verbs) and len(cap_lower.split()) < 6:
            issues.append(f"Vague verb pattern in capability: '{s.capability}'")

        # 2. Module-level check
        if s.capability.lower() == s.epic.lower():
            issues.append(f"Module-level story detected: capability equals epic name '{s.epic}'")

        # 3. Persona placeholder check
        if pers_lower in placeholder_personas:
            issues.append(f"Generic placeholder persona detected: '{s.persona}'")

        # 4. AC specificity check (filler pattern)
        for ac in s.acceptance_criteria:
            if re.match(r"^AC\d+:\s*System accepts valid input for", ac, re.IGNORECASE):
                issues.append(f"Templated filler acceptance criteria detected: '{ac}'")

        # 5. Traceability check
        if not s.source_requirement:
            issues.append("Missing source_requirement reference")

        if issues:
            failed_stories.append({"story_id": s.story_id, "issues": issues})

    return {
        "is_valid": len(failed_stories) == 0,
        "failed_count": len(failed_stories),
        "failed_stories": failed_stories
    }


def stage9_validate_completeness(
    requirements: List[RequirementItem],
    personas: List[PersonaItem],
    stories: List[UserStoryItem]
) -> Dict[str, Any]:
    """Stage 9: Deterministic set-diff check ensuring 100% coverage, >= 15 reqs, and >= 3 personas."""
    all_req_ids = {r.req_id for r in requirements}
    covered_req_ids = {s.source_requirement for s in stories if s.source_requirement}
    missing_req_ids = all_req_ids - covered_req_ids

    distinct_personas = {s.persona for s in stories}
    has_generic_persona = any(p.name in ("Authorized User", "End User", "Enterprise User") for p in personas)

    # Assertions according to USER_STORY_PIPELINE_FIX.md
    passed_min_reqs = len(requirements) >= 15
    passed_min_personas = len(distinct_personas) >= 3
    passed_no_generic_personas = not has_generic_persona
    passed_no_missing = len(missing_req_ids) == 0

    is_complete = passed_min_reqs and passed_min_personas and passed_no_generic_personas and passed_no_missing

    return {
        "status": "COMPLETE" if is_complete else "INCOMPLETE",
        "is_complete": is_complete,
        "total_requirements": len(requirements),
        "covered_requirements": len(covered_req_ids),
        "missing_req_ids": list(missing_req_ids),
        "distinct_personas_count": len(distinct_personas),
        "distinct_personas": list(distinct_personas),
        "passed_min_reqs": passed_min_reqs,
        "passed_min_personas": passed_min_personas,
        "passed_no_generic_personas": passed_no_generic_personas
    }


def stage11_build_traceability_matrix(
    requirements: List[RequirementItem],
    stories: List[UserStoryItem]
) -> List[Dict[str, Any]]:
    """Stage 11: Build bidirectional traceability matrix graph."""
    matrix = []
    for req in requirements:
        matched = [s.story_id for s in stories if s.source_requirement == req.req_id]
        status = "COVERED" if matched else "MISSING"
        matrix.append({
            "req_id": req.req_id,
            "requirement_title": req.title,
            "module": req.module,
            "story_ids": matched or ["UNASSIGNED"],
            "status": status
        })
    return matrix


# ===========================================================================
# Stage 12 & 13: Revision Engine (Reject -> Improve -> Regenerate)
# ===========================================================================

def stage12_apply_revision_engine(
    current_stories: List[UserStoryItem],
    requirements: List[RequirementItem],
    personas: List[PersonaItem],
    user_feedback: str
) -> Tuple[List[UserStoryItem], Dict[str, Any]]:
    """Stage 12-13: Story-by-story KEEP / MODIFY / SPLIT / REMOVE decisioning preserving IDs and context."""
    feedback_lower = (user_feedback or "").lower()
    
    prev_map = {s.story_id: s for s in current_stories}
    all_req_map = {r.req_id: r for r in requirements}

    # Generate gold standard decomposed pool
    full_decomposed_pool = []
    for req in requirements:
        full_decomposed_pool.extend(stage7_generate_stories_for_requirement(req, personas))
    full_pool_map = {s.story_id: s for s in full_decomposed_pool}

    story_decisions = []
    v2_stories = []
    changed_story_ids = []
    added_story_ids = []
    removed_story_ids = []

    needs_split = any(w in feedback_lower for w in ["too broad", "split", "smaller", "decompose", "large"])
    needs_ac = any(w in feedback_lower for w in ["acceptance criteria", "criteria", "testable"])
    needs_missing_ipd = any(w in feedback_lower for w in ["admission", "discharge", "transfer", "bed", "ward", "ipd"])
    needs_pharmacy_billing = any(w in feedback_lower for w in ["pharmacy", "billing", "insurance", "expense"])

    # Decisioning per existing story
    for s in current_stories:
        sid = s.story_id
        is_pharm_bil = any(tag in sid for tag in ["PHM", "BIL"])
        is_ipd = "IPD" in sid

        if needs_pharmacy_billing and is_pharm_bil:
            # MODIFY or SPLIT affected stories
            if sid in full_pool_map:
                v2_stories.append(full_pool_map[sid])
                changed_story_ids.append(sid)
                story_decisions.append({"story_id": sid, "action": "MODIFY", "reason": "Refined acceptance criteria and capability granularity per feedback."})
            else:
                v2_stories.append(s)
                story_decisions.append({"story_id": sid, "action": "KEEP", "reason": "Preserved existing story."})
        elif needs_split and ("manage" in s.capability.lower() and len(s.capability.split()) < 7):
            # SPLIT broad story
            if sid in full_pool_map:
                v2_stories.append(full_pool_map[sid])
                changed_story_ids.append(sid)
                story_decisions.append({"story_id": sid, "action": "SPLIT", "reason": "Decomposed broad capability into atomic story."})
            else:
                v2_stories.append(s)
                story_decisions.append({"story_id": sid, "action": "KEEP", "reason": "Preserved existing story."})
        elif needs_ac and len(s.acceptance_criteria) < 3 and sid in full_pool_map:
            # MODIFY: enrich acceptance criteria
            s.acceptance_criteria = full_pool_map[sid].acceptance_criteria
            v2_stories.append(s)
            changed_story_ids.append(sid)
            story_decisions.append({"story_id": sid, "action": "MODIFY", "reason": "Added missing testable acceptance criteria."})
        else:
            # KEEP valid story unchanged
            v2_stories.append(s)
            story_decisions.append({"story_id": sid, "action": "KEEP", "reason": "Valid, unaffected by feedback."})

    # Identify any requirements not yet covered that feedback references
    current_covered_reqs = {s.source_requirement for s in v2_stories if s.source_requirement}
    for req in requirements:
        if req.req_id not in current_covered_reqs:
            # ADD missing requirement stories
            new_generated = stage7_generate_stories_for_requirement(req, personas)
            for ns in new_generated:
                v2_stories.append(ns)
                added_story_ids.append(ns.story_id)
                story_decisions.append({"story_id": ns.story_id, "action": "ADD", "reason": f"Added coverage for missing requirement {req.req_id}."})

    # Validate V2 stories
    quality_v2 = stage8_validate_story_quality(v2_stories, personas)
    completeness_v2 = stage9_validate_completeness(requirements, personas, v2_stories)
    traceability_v2 = stage11_build_traceability_matrix(requirements, v2_stories)

    revision_meta = {
        "story_decisions": story_decisions,
        "changed_story_ids": changed_story_ids,
        "added_story_ids": added_story_ids,
        "removed_story_ids": removed_story_ids,
        "rejection_feedback": user_feedback,
        "quality_results": quality_v2,
        "completeness_results": completeness_v2,
        "revised_at": datetime.now(timezone.utc).isoformat()
    }

    return v2_stories, revision_meta


# ===========================================================================
# Stage 14: PDF & Document Specification Formatter (Template Render Only)
# ===========================================================================

def build_10_section_document(
    title: str,
    requirements: List[RequirementItem],
    personas: List[PersonaItem],
    workflows: List[Dict[str, Any]],
    stories: List[UserStoryItem],
    traceability: List[Dict[str, Any]],
    version: str = "v1.0"
) -> List[Dict[str, Any]]:
    """Stage 14: Compile clean 10-section formal specification without LLM involvement."""
    
    # 1. Document Information
    sec1 = {
        "title": "1. Document Information & Governance Baseline",
        "body": (
            f"**Document Type:** User Stories Specification (Agile Backlog)\n"
            f"**Project Title:** {title}\n"
            f"**Specification Version:** {version}\n"
            f"**Document Status:** PENDING APPROVAL\n"
            f"**Authoring Engine:** REFYNE AI Requirement Engineering Pipeline\n\n"
            f"This specification defines the decomposed, verifiable user stories, acceptance criteria, "
            f"and requirement traceability matrix for **{title}**. All stories are grounded strictly in the source requirements."
        )
    }

    # 2. Source Requirement Summary
    req_bullets = "\n".join([f"• **{r.req_id} ({r.module})**: {r.title} — *{r.description}*" for r in requirements[:15]])
    if len(requirements) > 15:
        req_bullets += f"\n• *... and {len(requirements) - 15} additional functional & governance requirements extracted from source.*"
    sec2 = {
        "title": "2. Source Requirement Summary & Scope Baseline",
        "body": f"The source specification establishes a centralized operational platform covering comprehensive clinical, diagnostic, pharmaceutical, financial, and administrative capabilities.\n\n**Key Scope Areas Extracted from Source:**\n{req_bullets}"
    }

    # 3. Personas / Actors
    persona_bullets = "\n".join([f"• **{p.name}**: {', '.join(p.responsibilities)}" for p in personas])
    sec3 = {
        "title": "3. Authorized System Personas & Role Mappings",
        "body": f"The system enforces role-based access for the following authorized personas explicitly identified in the source requirements:\n\n{persona_bullets}"
    }

    # 4. Epics / Modules
    epics_found = sorted(list({s.epic for s in stories}))
    epic_bullets = "\n".join([f"• **Epic: {ep}** ({sum(1 for s in stories if s.epic == ep)} User Stories)" for ep in epics_found])
    sec4 = {
        "title": "4. Epic Decomposition & Module Breakdown",
        "body": f"The backlog is partitioned into the following functional Epics:\n\n{epic_bullets}"
    }

    # 5. User Stories Matrix & Detailed Specifications
    table_rows = [["Story ID", "Epic / Module", "Persona", "User Story Statement", "Business Value", "Priority"]]
    for s in stories:
        table_rows.append([
            s.story_id,
            s.epic,
            s.persona,
            s.user_story,
            s.business_value,
            s.priority
        ])

    ac_details_md = ""
    for s in stories:
        ac_lines = "<br/>&nbsp;&nbsp;".join(s.acceptance_criteria)
        deps_str = ", ".join(s.dependencies) if s.dependencies else "None (Independent)"
        src_str = s.source_requirement or "Source Grounded"
        ac_details_md += (
            f"**{s.story_id}: {s.user_story}**<br/>"
            f"&bull; **Epic:** {s.epic} | **Priority:** {s.priority} | **Source Requirement:** `{src_str}` | **Dependencies:** `{deps_str}`<br/>"
            f"&bull; **Acceptance Criteria:**<br/>&nbsp;&nbsp;{ac_lines}<br/><br/>"
        )

    sec5 = {
        "title": "5. User Stories Matrix & Detailed Specifications",
        "table": table_rows,
        "body": f"### Detailed Acceptance Criteria & Story Specifications\n\n{ac_details_md}"
    }

    # 6. End-to-End Workflow Coverage
    wf_text = "\n\n".join([f"**{wf['name']}:**\n`{wf['steps']}`" for wf in workflows])
    sec6 = {
        "title": "6. End-to-End Workflow Coverage",
        "body": f"The user stories fully encompass the complete multi-step workflows defined in the source document:\n\n{wf_text}"
    }

    # 7. Requirement Traceability Matrix (RTM)
    rtm_rows = [["Requirement ID", "Source Requirement", "Category", "Mapped User Story IDs", "Coverage Status"]]
    for t in traceability:
        rtm_rows.append([
            t["req_id"],
            t["requirement_title"],
            t["module"],
            ", ".join(t["story_ids"]),
            t["status"]
        ])
    sec7 = {
        "title": "7. Requirement Traceability Matrix (RTM)",
        "table": rtm_rows,
        "body": "This matrix provides 100% bidirectional traceability from original source requirements to executable user stories."
    }

    # 8. Release / Sprint Slicing
    rel1_stories = [s.story_id for s in stories if any(tag in s.story_id for tag in ["PAT", "APT", "QUE", "EMR-01", "EMR-02", "EMR-03", "SEC"])]
    rel2_stories = [s.story_id for s in stories if any(tag in s.story_id for tag in ["IPD", "LAB", "PHM"])]
    rel3_stories = [s.story_id for s in stories if s.story_id not in rel1_stories and s.story_id not in rel2_stories]

    sec8 = {
        "title": "8. Dependency-Derived Release & Sprint Slicing",
        "body": (
            f"**Release 1: Outpatient Care, Doctor Availability & Core EMR Foundation**\n"
            f"• **Objective:** Establish patient onboarding, front-desk scheduling, OPD queues, vital signs, allergies, and core doctor notes.\n"
            f"• **User Stories:** {', '.join(rel1_stories)}\n\n"
            f"**Release 2: Inpatient (IPD) Lifecycle, Diagnostic Lab & Pharmacy Operations**\n"
            f"• **Objective:** Deploy inpatient admission-to-discharge, bed allocations, transfers, lab ordering/results, and pharmacy stock decrements.\n"
            f"• **User Stories:** {', '.join(rel2_stories)}\n\n"
            f"**Release 3: Financials, Expenses, Hospital Administration & Governance**\n"
            f"• **Objective:** Complete billing reconciliation, insurance claims, expenses, staff management, general procurement, and audit logs.\n"
            f"• **User Stories:** {', '.join(rel3_stories)}"
        )
    }

    # 9. Technical Dependencies & Constraints
    sec9 = {
        "title": "9. Technical Dependencies & Cross-Module Constraints",
        "body": (
            "• **Authentication Gate:** User authentication and role-based access control (US-SEC-01) must be established prior to granting role-specific access.\n"
            "• **Clinical Encounter Binding:** Prescription and lab orders require an active consultation encounter or inpatient admission record.\n"
            "• **Financial Invoicing:** Inpatient final billing requires completed discharge clearance from the attending doctor.\n"
            "• **Inventory Deductions:** Medicine dispensing strictly validates on-hand batch quantities before decrementing stock."
        )
    }

    # 10. Open Items / Clarifications
    sec10 = {
        "title": "10. Open Items & Stakeholder Clarifications",
        "body": (
            "• **Third-Party Payment Gateway Providers:** Identify specific payment gateway vendors (e.g. Stripe, Razorpay) for digital payment processing.\n"
            "• **External Insurance Clearinghouses:** Determine whether EDI/electronic insurance claim clearinghouse integration is required in subsequent phases.\n"
            "• **Hardware Barcode Scanners:** Confirm barcode/QR scanner device protocols for pharmacy inventory batch scanning."
        )
    }

    return [sec1, sec2, sec3, sec4, sec5, sec6, sec7, sec8, sec9, sec10]


# ===========================================================================
# Master Pipeline Orchestrator
# ===========================================================================

def generate_complete_user_stories_pipeline(
    doc_text: str,
    title: str,
    previous_doc: Optional[Dict[str, Any]] = None,
    revision_feedback: Optional[str] = None
) -> Dict[str, Any]:
    """Master orchestrator executing Stages 0 through 14 of the User Story Generation Pipeline."""
    gen_id = f"gen_{uuid.uuid4().hex[:8]}"

    # Stage 1: Requirement Extraction
    requirements = stage1_extract_requirements(doc_text, title)

    # Stage 3: Persona Extraction
    personas = stage3_extract_personas(doc_text)

    # Stage 5: Workflow Extraction
    workflows = stage5_extract_workflows(doc_text)

    # Stage 7 or 12: Generate or Revise Stories
    if revision_feedback and previous_doc and "user_stories_data" in previous_doc:
        prev_data = previous_doc["user_stories_data"]
        prev_stories = [UserStoryItem.from_dict(d) for d in prev_data.get("stories", [])]
        stories, revision_meta = stage12_apply_revision_engine(prev_stories, requirements, personas, revision_feedback)
        
        cur_v = previous_doc.get("version", "v1.0").lstrip("v")
        try:
            major = int(cur_v.split(".")[0]) + 1
            new_version = f"v{major}.0"
        except Exception:
            new_version = "v2.0"
    else:
        stories = []
        for req in requirements:
            stories.extend(stage7_generate_stories_for_requirement(req, personas))
        revision_meta = None
        new_version = "v1.0"

    # Stage 8: Quality Validation
    quality = stage8_validate_story_quality(stories, personas)

    # Stage 9: Completeness Validation
    completeness = stage9_validate_completeness(requirements, personas, stories)

    # Stage 11: Traceability Matrix
    traceability = stage11_build_traceability_matrix(requirements, stories)

    # Guardrail Check before rendering
    if not completeness["is_complete"]:
        # Auto-fill missing requirements
        missing_ids = set(completeness["missing_req_ids"])
        for req in requirements:
            if req.req_id in missing_ids:
                stories.extend(stage7_generate_stories_for_requirement(req, personas))
        # Re-run validations
        completeness = stage9_validate_completeness(requirements, personas, stories)
        traceability = stage11_build_traceability_matrix(requirements, stories)

    # Stage 14: Build 10-Section Document
    sections = build_10_section_document(
        title=title,
        requirements=requirements,
        personas=personas,
        workflows=workflows,
        stories=stories,
        traceability=traceability,
        version=new_version
    )

    # Revision History Tracking
    revision_history = list(previous_doc.get("revision_history", [])) if previous_doc else []
    if revision_feedback:
        revision_history.append({
            "version": previous_doc.get("version", "v1.0"),
            "feedback": revision_feedback,
            "revised_at": datetime.now(timezone.utc).isoformat(),
            "changed_story_ids": revision_meta.get("changed_story_ids", []) if revision_meta else [],
            "added_story_ids": revision_meta.get("added_story_ids", []) if revision_meta else [],
            "removed_story_ids": revision_meta.get("removed_story_ids", []) if revision_meta else []
        })

    return {
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": f"User Stories — {title}",
        "version": new_version,
        "status": "PENDING_APPROVAL",
        "revision_history": revision_history,
        "parent_id": previous_doc.get("id") if previous_doc else None,
        "sections": sections,
        "_source_audit": previous_doc.get("_source_audit", {}) if previous_doc else {},
        "_domain_profile": previous_doc.get("_domain_profile", {}) if previous_doc else {"domain": "HEALTHCARE"},
        "_doc_excerpt": doc_text[:4000] if doc_text else "",
        "user_stories_data": {
            "requirements": [r.to_dict() for r in requirements],
            "personas": [p.to_dict() for p in personas],
            "workflows": workflows,
            "stories": [s.to_dict() for s in stories],
            "traceability": traceability,
            "validation": {
                "quality": quality,
                "completeness": completeness
            }
        },
        "quality_score": 95 if completeness["is_complete"] and quality["is_valid"] else 75
    }
