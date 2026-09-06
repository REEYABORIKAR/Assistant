# 09 DOCUMENT GENERATION SPECIFICATION

**Revision:** 2 (2026-08-26) — FINAL ARCHITECTURE RESOLUTION PASS

Revision 1 is preserved in full. This revision **adds** what the architecture review found missing:
an explicit, **ordered** section definition for all 11 document types (§§ 8–18), the per-type
contract block phase 9 requires, and the complete XLSX workbook contract (§ 25). Nothing is removed.

## 1. PURPOSE

Define generation, validation, review, approval, versioning and export of enterprise project documents.

---

# 2. DOCUMENT TYPES

The platform supports:

BRD

SRS

FRD

NFRD

RTM

TEST_PLAN

TEST_CASES

RISK_ASSESSMENT

SECURITY_ASSESSMENT

COMPLIANCE_ASSESSMENT

TECHNICAL_DOCUMENTATION

## 2.1 ✅ D-08 RESOLVED — DERIVED

**Eleven types. This list is authoritative.** Three independent statements of the set agree exactly:

| Source | Types |
| --- | --- |
| `01 § DOCUMENT TYPES` | 11 |
| `09 § 2` (this section) | 11 |
| `03 § 21 Supported document types` | 11 |

The two apparent contradictions are not contradictions:

- **`13 § DOCUMENTS`** lists 9 generate abilities, grouping *"test documents"* (TEST_PLAN +
  TEST_CASES) and *"risk documents"*, and omits TECHNICAL_DOCUMENTATION. It is an acceptance
  checklist of user abilities, not a type registry.
- **`documents.png`** shows 8 rows and `document-generator.png` shows 6 tiles. Both are viewport
  crops of a scrollable surface; neither states a total.

**`04 § Document Generation Service` is the one real defect** — it names only BRD, SRS, FRD, NFRD,
RTM, *"testing documents"* and *"risk documents"*, omitting SECURITY_ASSESSMENT,
COMPLIANCE_ASSESSMENT and TECHNICAL_DOCUMENTATION even though `13` explicitly requires *"generate
security documents"* and *"generate compliance documents"*. `04` is corrected to all 11.

`document_type` is a PostgreSQL enum with exactly these 11 labels. A twelfth type requires a
migration — deliberately, so a type cannot be introduced at runtime and bypass its section contract.

---

# 3. GENERATION PIPELINE

User Request
↓
Authorization
↓
Document Type Validation
↓
Source Selection
↓
Source Version Freeze
↓
Data Availability
↓
Document Supervisor
↓
Document Structure
↓
Section Generation
↓
Traceability
↓
Validation
↓
Review if required
↓
Approval if required
↓
Render
↓
Persist
↓
Audit

## 3.1 Persistence of the pipeline — ADDED

| Stage | Where the outcome is stored |
| --- | --- |
| Authorization | `audit_events` (`AUTHORIZATION_DENIED` on refusal) |
| Document Type Validation | rejected before a row is created |
| Source Selection | `generation_run_sources` — one row per selected source |
| Source Version Freeze | `generation_run_sources.source_version` (§ 7) |
| Data Availability | `generation_runs.data_availability` |
| Document Supervisor | `agent_runs` with `agent_type='DOCUMENT_SUPERVISOR'` |
| Document Structure | `document_sections` created from the type's ordered contract |
| Section Generation | `document_sections.body` + provenance columns (§ 19) |
| Traceability | `traceability_relationships` |
| Validation | `validation_runs` + `validation_findings` |
| Review | `reviews`, `review_assignments`, `review_sections`, `review_comments` |
| Approval | `approvals`, `approval_steps` |
| Render | `document_renditions` (one row per format) |
| Persist | `document_versions` |
| Audit | § 29 |

**Generation is asynchronous** (`03 § 21`). The request returns `202 {job_id}`; `generation_runs`
carries the state. The frontend displays the stored state and never a synthesised percentage
(`03 § 11`, `CLAUDE.md § 1`).

---

# 4. DOCUMENT STATES

DRAFT

GENERATING

VALIDATING

REVIEW

CHANGES_REQUESTED

APPROVED

REJECTED

FAILED

ARCHIVED

## 4.1 Stored versus computed — ADDED

`document_versions.status` stores exactly one of these nine. `03 § 20` additionally displays
*validation status* and *approval status*; those are **computed server-side** from
`validation_runs` and `approvals` and returned as separate read-only fields. They are never a second
stored status, and never computed by the frontend (`CLAUDE.md § 2`).

`APPROVED` and `REJECTED` are terminal for a version. `ARCHIVED` is reachable from any non-terminal
state and from `APPROVED` under retention (`11 § 22`); archiving an approved version does not alter
its content — immutability holds (§ 5).

---

# 5. VERSIONING

Draft:

v0.1

Revision:

v0.2

Approval:

v1.0

Post-approval revision:

v1.1

Approved versions are immutable.

A modification to v1.0 creates v1.1.

Versioning must be stored in the database.

## 5.1 Enforcement — ADDED

Immutability is enforced by a database trigger, not by application discipline: once
`document_versions.status='APPROVED'`, `UPDATE` of the content, section, or rendition rows for that
version raises an error. `07` surfaces this as `410 RESOURCE_IMMUTABLE`.

`major`/`minor` are stored as separate integers with `UNIQUE (document_id, major, minor)`, so
`v0.10` sorts after `v0.9`. Storing `"v0.10"` as text would not.

---

# 6. DOCUMENT ID

Document IDs must be generated by the backend.

The exact identifier format:

DECISION REQUIRED

Do not hard-code example IDs such as:

#REV-2026-001

unless the identifier contract is approved.

## 6.1 🟠 D-09 — what is and is not blocked — ADDED

**Not blocked:** every document has a UUID primary key. All 190 endpoints in `07` address documents
by UUID, so the API is fully specifiable without this decision.

**Blocked:** the *human-readable* key shown in `documents.png` and required by `03 § 20`'s
*document ID* column. Undefined: the prefix scheme, whether the sequence is per tenant / per project
/ per type, zero-padding width, whether the year is embedded, and whether the key is stable across
versions. Guessing produces a key that appears in approved PDFs and cannot then be changed.

The column exists in the schema as nullable; it is populated once the format is approved. **No
placeholder is generated in the interim** — a fabricated key in an approved document is worse than
an absent one.

---

# 7. SOURCE FREEZE

A generation run records the exact source versions used.

Example:

Requirement BR-001
Version 3

Document DOC-001
Generation Run GEN-001

This prevents later source changes from silently changing an already-generated document.

## 7.1 Contract — ADDED

One `generation_run_sources` row per source: `generation_run_id`, `source_type`, `source_id`,
`source_version`, `source_location`, `content_hash`. `source_version` and `content_hash` are
captured at selection time and never updated.

A regeneration that produces different content because a source changed is therefore provable:
the two runs' `content_hash` values differ. Without the hash, *"prevents later source changes from
silently changing"* would be an intention rather than a check.

---

# 8. BRD

Required sections:

1. Cover
2. Document Control
3. Revision History
4. Approval History
5. Executive Summary
6. Business Background
7. Problem Statement
8. Objectives
9. Scope
10. Out of Scope
11. Stakeholders
12. Business Requirements
13. Business Rules
14. Assumptions
15. Constraints
16. Dependencies
17. Risks
18. Success Criteria
19. Acceptance Criteria
20. Traceability
21. References

## 8.1 Contract

| Field | Value |
| --- | --- |
| `document_type` | `BRD` |
| Purpose | Business-level statement of problem, objectives, scope and business requirements |
| Sections | **21, ordered as above** |
| Allowed sources | `PROJECT` · `FILE` · `FILE_CHUNK` · `REQUIREMENT` (type `BUSINESS`) · `RISK` · `CONVERSATION_MESSAGE` |
| Validation | All nine § 20 checks. § 12 *Business Requirements* must be non-empty and every item must cite a `REQUIREMENT` |
| Traceability | Source of the chain. Its requirements are the `BR-*` roots of § 12's RTM |
| Review | Section-level (§ 21) |
| Approval | Required (§ 22) |
| PDF | Required |
| DOCX | Required |
| XLSX | Not applicable |

`03 § 22`'s *"BRD: Sources tab may be displayed"* is resolved: the Sources tab **is** displayed for
BRD, because `generation_run_sources` rows always exist for it.

---

# 9. SRS

Required sections:

1. Cover
2. Document Control
3. Revision History
4. Approval History
5. Introduction
6. Purpose
7. Scope
8. Definitions
9. System Overview
10. Functional Requirements
11. Non-Functional Requirements
12. User Roles
13. Use Cases
14. External Interfaces
15. Data Requirements
16. Security Requirements
17. Performance Requirements
18. Availability
19. Scalability
20. Compliance Requirements
21. Error Handling
22. Constraints
23. Assumptions
24. Traceability
25. References

## 9.1 Contract

| Field | Value |
| --- | --- |
| `document_type` | `SRS` |
| Purpose | System-level specification of functional and non-functional requirements |
| Sections | **25, ordered as above** |
| Allowed sources | `PROJECT` · `REQUIREMENT` (all types) · `DOCUMENT_VERSION` (BRD, FRD) · `SECURITY_FINDING` · `COMPLIANCE_FINDING` · `DESIGN_ELEMENT` · `FILE_CHUNK` |
| Validation | All nine. §§ 16, 17, 18, 19, 20 must each cite a stored `REQUIREMENT` or `COMPLIANCE_FINDING`; unsupported claims are `UNVERIFIED` (§ 19) |
| Traceability | `SRS_REF` node of § 12's chain |
| Review | Section-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | Not applicable |

`03 § 22`'s *"SRS: Traceability tab may be displayed"* is resolved: the Traceability tab **is**
displayed for SRS. § 18 *Availability*, § 19 *Scalability* and § 17 *Performance Requirements*
inherit 🟠 **D-10** — no SLA numbers exist (§ 11) — so those sections are generated as
`UNVERIFIED` structure without invented figures.

---

# 10. FRD

Required:

- functional overview
- actors
- functional requirements
- business rules
- workflows
- validation
- errors
- interfaces
- traceability

## 10.1 ✅ Ordered sections — ADDED

**Ordering rule (applies to §§ 10, 11, 12, 13, 14, 15, 16, 17, 18).** `09 § 20` validates
*section order*, and `13 § DOCUMENT VALIDATION` requires *"have required sections"*, so an unordered
list is not an implementable contract. The order is **derived, not invented**:

1. **Front matter** — the four sections that open both BRD and SRS identically: Cover, Document
   Control, Revision History, Approval History. `13 § PDF` independently requires cover, metadata
   and revision history in every generated PDF.
2. **Body** — the type's own listed items, in the order this specification already lists them. No
   item is added, removed, or resequenced.
3. **Back matter** — Traceability then References, the order both BRD and SRS end with. Where the
   body already lists *traceability*, it is not duplicated.

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Functional Overview |
| 6 | Actors |
| 7 | Functional Requirements |
| 8 | Business Rules |
| 9 | Workflows |
| 10 | Validation |
| 11 | Errors |
| 12 | Interfaces |
| 13 | Traceability |
| 14 | References |

**14 sections.**

## 10.2 Contract

| Field | Value |
| --- | --- |
| `document_type` | `FRD` |
| Purpose | Functional behaviour: actors, rules, flows, validation and error handling |
| Sections | 14, ordered above |
| Allowed sources | `PROJECT` · `REQUIREMENT` (type `FUNCTIONAL`) · `DOCUMENT_VERSION` (BRD) · `FILE_CHUNK` · `DESIGN_ELEMENT` |
| Validation | All nine. § 7 must cite `REQUIREMENT` rows |
| Traceability | `FUNCTIONAL_REQUIREMENT` node of § 12's chain |
| Review | Section-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | Not applicable |

---

# 11. NFRD

Required:

- performance
- availability
- scalability
- reliability
- security
- privacy
- compliance
- observability
- maintainability
- disaster recovery
- backup
- compatibility

Production SLA values:

DECISION REQUIRED

Do not invent SLA numbers.

## 11.1 ✅ Ordered sections — ADDED

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Performance |
| 6 | Availability |
| 7 | Scalability |
| 8 | Reliability |
| 9 | Security |
| 10 | Privacy |
| 11 | Compliance |
| 12 | Observability |
| 13 | Maintainability |
| 14 | Disaster Recovery |
| 15 | Backup |
| 16 | Compatibility |
| 17 | Traceability |
| 18 | References |

**18 sections.**

## 11.2 Contract

| Field | Value |
| --- | --- |
| `document_type` | `NFRD` |
| Purpose | Non-functional requirements across twelve quality attributes |
| Sections | 18, ordered above |
| Allowed sources | `PROJECT` · `REQUIREMENT` (type `NON_FUNCTIONAL`) · `SECURITY_FINDING` · `COMPLIANCE_FINDING` · `FILE_CHUNK` |
| Validation | All nine, **plus**: no section may state a numeric target that is not traceable to a stored `REQUIREMENT`. An untraceable figure is `UNVERIFIED`, never a generated number |
| Traceability | Contributes `NON_FUNCTIONAL` requirements to the chain |
| Review | Section-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | Not applicable |

🟠 **D-10.** § 5 Performance, § 6 Availability, § 7 Scalability, § 14 Disaster Recovery and § 15
Backup have no numeric targets anywhere in the repository. `11 § 24` marks RPO/RTO the same way.
The sections are generated with their structure and their sourced content; **empty targets are
rendered as `UNVERIFIED`, not filled with plausible figures** — an invented `99.9%` in an approved
NFRD becomes a contractual commitment nobody agreed to.

---

# 12. RTM

RTM must support:

Requirement

→ Functional Requirement

→ SRS

→ Design

→ Test Case

→ Risk

→ Evidence

Every relationship must point to an actual stored entity.

Required data model:

TEST_CASE

TRACEABILITY_RELATIONSHIP

The exact table names may follow the existing database naming convention.

## 12.1 ✅ The chain — RESOLVED

Seven node types, stored as real rows — never as free-form strings:

| # | Node | Table |
| --- | --- | --- |
| 1 | Business Requirement | `requirements` (`type='BUSINESS'`) |
| 2 | Functional Requirement | `requirements` (`type='FUNCTIONAL'`) |
| 3 | SRS Requirement | `requirements` (`type='SRS'`) |
| 4 | Design | `design_elements` |
| 5 | Test Case | `test_cases` |
| 6 | Risk | `risks` |
| 7 | Evidence | `evidence` |

Relationships are `traceability_relationships` rows: `from_type`, `from_id`, `to_type`, `to_id`,
`relationship_type`, `created_by`, `created_at`, with `UNIQUE (from_type, from_id, to_type, to_id,
relationship_type)`. Because the endpoints are polymorphic, referential integrity is enforced by
trigger — a relationship pointing at a non-existent row is rejected at write time, which is what
*"must point to an actual stored entity"* requires. `13 § TRACEABILITY`'s *"where applicable"* is
honoured by relationship absence, never by a placeholder row.

🔵 **MC-03** — `design_elements` has no specification. No file defines what a design element is,
what fields it carries, or how one is created. `13` requires `Design` in the chain and `03 § 25`
displays a *Design Reference* column, so the node cannot be dropped; but its write endpoints are
`BLOCKED` (`07 §§ 12, 27`). **Consequence: the RTM `Design Reference` column renders empty for every
requirement until MC-03 is closed** — visibly incomplete rather than silently fabricated.

## 12.2 ✅ Sections

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Traceability Matrix |
| 6 | References |

**6 sections.** RTM is a register: § 5 is the matrix itself, so no separate Traceability section
exists.

## 12.3 Contract

| Field | Value |
| --- | --- |
| `document_type` | `RTM` |
| Purpose | Prove every requirement is realised, tested and risk-assessed |
| Sections | 6, ordered above |
| Allowed sources | `REQUIREMENT` · `DESIGN_ELEMENT` · `TEST_CASE` · `RISK` · `EVIDENCE` — **only stored rows.** No narrative source |
| Validation | Metadata · required sections · section order · requirement references · traceability · evidence · consistency. **Unsupported claims and missing information do not apply** — a missing link is an empty cell, which is the document's finding, not a defect |
| Traceability | The RTM *is* the traceability artefact |
| Review | Document-level (a matrix has one section) |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| **XLSX** | **Required** — § 25.1 |

---

# 13. TEST PLAN

Must contain:

- objectives
- scope
- test strategy
- environments
- test levels
- entry criteria
- exit criteria
- test data
- risks
- dependencies
- traceability

## 13.1 ✅ Ordered sections — ADDED

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Objectives |
| 6 | Scope |
| 7 | Test Strategy |
| 8 | Environments |
| 9 | Test Levels |
| 10 | Entry Criteria |
| 11 | Exit Criteria |
| 12 | Test Data |
| 13 | Risks |
| 14 | Dependencies |
| 15 | Traceability |
| 16 | References |

**16 sections.**

## 13.2 Contract

| Field | Value |
| --- | --- |
| `document_type` | `TEST_PLAN` |
| Purpose | Strategy, scope, criteria and environments for verifying the requirements |
| Sections | 16, ordered above |
| Allowed sources | `PROJECT` · `REQUIREMENT` · `RISK` · `TEST_CASE` · `DOCUMENT_VERSION` (SRS, NFRD) |
| Validation | All nine. § 12 *Test Data* must not contain real production or personal data (`12 § 39`) |
| Traceability | Links test levels to requirements |
| Review | Section-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | Not applicable — narrative, not tabular |

---

# 14. TEST CASES

Each test case contains:

- test case ID
- title
- objective
- preconditions
- steps
- expected result
- actual result
- status
- requirement references
- risk references
- evidence

## 14.1 ✅ Sections — ADDED

TEST_CASES is a register. The eleven items above are **columns of the register**, not document
sections — which is why revision 1 could not be implemented as written.

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Test Case Register |
| 6 | Traceability |
| 7 | References |

**7 sections.**

## 14.2 Stored versus generated columns

| Column | Source | Rule |
| --- | --- | --- |
| test case ID | `test_cases` | 🟠 D-09 for the human key; UUID always present |
| title, objective, preconditions, steps, expected result | `test_cases` | Generated by the workflow, stored, editable |
| **actual result, status** | `test_case_results` | **Execution data, not generation data** |
| requirement references, risk references | `traceability_relationships` | Real rows |
| evidence | `evidence` | Real rows |

**`actual result` and `status` are never generated.** A generated actual result would be a
fabricated test result, forbidden by `CLAUDE.md § 5`. They are populated only by recorded execution;
absent execution, the register shows `NOT_EXECUTED`.

🔵 **MC-03 (second instance)** — no file specifies how a test result enters the system: no CI
integration, no import format, no manual-entry contract. `POST /test-cases/{id}/results` is
`BLOCKED` (`07 § 13`). **Consequence: the register's `actual result` and `status` columns stay
`NOT_EXECUTED` until this contract exists.**

## 14.3 Contract

| Field | Value |
| --- | --- |
| `document_type` | `TEST_CASES` |
| Purpose | Enumerate verifiable test cases and their traceability |
| Sections | 7, ordered above |
| Allowed sources | `REQUIREMENT` · `RISK` · `TEST_CASE` · `TEST_CASE_RESULT` · `EVIDENCE` |
| Validation | Metadata · sections · order · requirement references · traceability · evidence · consistency. Every case must cite ≥ 1 `REQUIREMENT` — an untraceable test case is a validation finding |
| Traceability | `TEST_CASE` node of § 12's chain |
| Review | Document-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| **XLSX** | **Required** — § 25.2 |

---

# 15. RISK ASSESSMENT

Contains:

- risk ID
- title
- description
- source
- likelihood
- severity
- score
- impact
- mitigation
- owner
- status

Risk scoring must use configured policy.

## 15.1 ✅ Sections — ADDED

Also a register; the eleven items are columns.

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Risk Register |
| 6 | Traceability |
| 7 | References |

**7 sections.** § 2 *Document Control* records the `policy_version_id` under which scores were
computed, so a score is reproducible and a later policy change is visible as a version difference.

## 15.2 Contract

| Field | Value |
| --- | --- |
| `document_type` | `RISK_ASSESSMENT` |
| Purpose | Identified risks with likelihood, severity, score, mitigation and ownership |
| Sections | 7, ordered above |
| Allowed sources | `PROJECT` · `REQUIREMENT` · `RISK` · `SECURITY_FINDING` · `COMPLIANCE_FINDING` · `FILE_CHUNK` · `EVIDENCE` |
| Validation | All nine. Every risk must cite its `source` |
| Traceability | `RISK` node of § 12's chain |
| Review | Document-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | 🟠 D-15 — see § 25.4 |

🟠 **D-06** — *"Risk scoring must use configured policy"* and no policy exists. `08 § 8`:
*"If no risk policy exists: BLOCKED / DECISION REQUIRED. Do not invent scoring rules."* The
`score` column is nullable and stays `NULL`; `07 § 12` forbids any endpoint accepting or returning a
computed score. `13 § CONDITIONAL`'s *"If risk exceeds configured threshold: approval required"* is
therefore **not evaluable**, which is why `05`'s `POLICY_EVALUATION` halts under `R4` rather than
guessing. Likelihood and severity are recorded as stated by their source; only the derived score is
withheld.

---

# 16. SECURITY ASSESSMENT

Contains:

- finding ID
- title
- description
- severity
- evidence
- affected requirement
- control
- remediation
- status

## 16.1 ✅ Sections — ADDED

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Findings Register |
| 6 | Traceability |
| 7 | References |

**7 sections.**

## 16.2 Contract

| Field | Value |
| --- | --- |
| `document_type` | `SECURITY_ASSESSMENT` |
| Purpose | Security findings with severity, control, evidence and remediation |
| Sections | 7, ordered above |
| Allowed sources | `PROJECT` · `REQUIREMENT` · `SECURITY_FINDING` · `EVIDENCE` · `FILE_CHUNK` |
| Validation | All nine, **plus the evidence gate below** |
| Traceability | Findings link to `REQUIREMENT` via `affected requirement` |
| Review | Document-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | 🟠 D-15 — see § 25.4 |

**Evidence gate.** `03 § 18`: *"No finding may be represented as verified without evidence."*
Enforced in the database — `security_findings.status` cannot become `VERIFIED` unless at least one
`evidence` row references it. `07 § 12` returns `422` on violation. This is a constraint, not a
generation-time check, so the rule cannot be bypassed by any write path.

Required by `13 § DOCUMENTS` (*"generate security documents"*) and omitted from `04` — see § 2.1.

---

# 17. COMPLIANCE ASSESSMENT

Contains:

- framework
- control
- requirement
- evidence
- status
- gap
- remediation

Evidence is required before confirmed compliance status.

## 17.1 ✅ Sections — ADDED

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Compliance Register |
| 6 | Traceability |
| 7 | References |

**7 sections.**

## 17.2 Contract

| Field | Value |
| --- | --- |
| `document_type` | `COMPLIANCE_ASSESSMENT` |
| Purpose | Control-by-control compliance status with evidence and gaps |
| Sections | 7, ordered above |
| Allowed sources | `PROJECT` · `REQUIREMENT` · `COMPLIANCE_FINDING` · `EVIDENCE` · `FILE_CHUNK` |
| Validation | All nine, **plus the evidence gate** |
| Traceability | Controls link to `REQUIREMENT` |
| Review | Document-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | 🟠 D-15 — see § 25.4 |

**Evidence gate.** This section's own rule plus `03 § 19` — enforced identically to § 16.2:
`compliance_findings.status` cannot become `COMPLIANT` without a referencing `evidence` row.

🔵 **MC-01** — no framework catalogue exists. No file names which compliance frameworks are
supported or where their control lists come from. `framework` and `control` are free text populated
from the source document; the platform cannot validate that a named control exists. **The document
is generatable; framework-conformance checking is not.**

Required by `13 § DOCUMENTS` (*"generate compliance documents"*) and omitted from `04` — see § 2.1.

---

# 18. TECHNICAL DOCUMENTATION

Can contain:

- architecture
- components
- APIs
- database
- workflows
- integrations
- deployment
- security
- operations

## 18.1 ⚠ A-02 — AMENDMENT, REPORTED NOT SILENTLY APPLIED

*"Can contain"* is the only definition revision 1 gives, and it is not implementable:

| Requirement | Conflict with *"can contain"* |
| --- | --- |
| `09 § 20` validates *required sections* | An empty required set makes the check vacuous for this type alone |
| `09 § 20` validates *section order* | No order exists to validate |
| `13 § DOCUMENT VALIDATION` — *"have required sections"* | Would fail or trivially pass |
| `03 § 21` lists it as generatable | A generator needs a structure |

**Amendment: the nine listed items become the required body, in the order listed.** This is the
minimal resolution — it adds no section that is not already named, and it does not choose among
alternatives, because the list is the only candidate set in the repository.

| # | Section |
| --- | --- |
| 1 | Cover |
| 2 | Document Control |
| 3 | Revision History |
| 4 | Approval History |
| 5 | Architecture |
| 6 | Components |
| 7 | APIs |
| 8 | Database |
| 9 | Workflows |
| 10 | Integrations |
| 11 | Deployment |
| 12 | Security |
| 13 | Operations |
| 14 | Traceability |
| 15 | References |

**15 sections.** This strengthens *can* to *must*. A product owner may reclassify any of §§ 5–13 as
optional; that changes only the `required` flag on `document_type_sections`, not the schema.
**A-02 is vetoable** — reject it and TECHNICAL_DOCUMENTATION returns to being unimplementable, which
is the honest alternative, not a third option.

## 18.2 Contract

| Field | Value |
| --- | --- |
| `document_type` | `TECHNICAL_DOCUMENTATION` |
| Purpose | Technical description of the delivered system |
| Sections | 15, ordered above (**A-02**) |
| Allowed sources | `PROJECT` · `DESIGN_ELEMENT` · `REQUIREMENT` · `DOCUMENT_VERSION` (SRS, NFRD, FRD) · `FILE_CHUNK` |
| Validation | All nine. § 5 Architecture and § 6 Components depend on `DESIGN_ELEMENT` rows — 🔵 MC-03, so both render `UNVERIFIED` until design elements exist |
| Traceability | Design → Requirement links |
| Review | Section-level |
| Approval | Required |
| PDF | Required |
| DOCX | Required |
| XLSX | Not applicable |

Omitted from both `13 § DOCUMENTS` and `04` — see § 2.1.

---

# 19. SOURCE PROVENANCE

Every generated section should retain:

source_type

source_id

source_version

source_location

If no authoritative source exists:

UNVERIFIED

Do not silently fabricate information.

## 19.1 `source_type` values — ADDED

The enum shared by `document_sections`, `generation_run_sources` and
`traceability_relationships`:

`PROJECT` · `FILE` · `FILE_CHUNK` · `CONVERSATION_MESSAGE` · `REQUIREMENT` · `DESIGN_ELEMENT` ·
`RISK` · `SECURITY_FINDING` · `COMPLIANCE_FINDING` · `TEST_CASE` · `TEST_CASE_RESULT` ·
`EVIDENCE` · `DOCUMENT_VERSION` · `INTEGRATION_OBJECT`

`INTEGRATION_OBJECT` records a Jira/Confluence/Notion object by key **without copying its content
into the provenance row**, so untrusted external text is not duplicated into a record
administrators read (`11 § 21.3`).

A section with no source is stored with `provenance_status='UNVERIFIED'` and is rendered with that
marker visible in the PDF and DOCX. It is never rendered as though sourced — that is the mechanism
behind *"Do not silently fabricate information."*

---

# 20. VALIDATION

Validation checks:

- metadata
- required sections
- section order
- requirement references
- traceability
- evidence
- consistency
- unsupported claims
- missing information

## 20.1 Contract — ADDED

Each check produces zero or more `validation_findings` rows: `validation_run_id`, `check_type`,
`severity` (`INFO` · `WARNING` · `ERROR`), `section_id`, `message`, `detail`.

A run is `PASSED` only with zero `ERROR` findings. `13 § DOCUMENT VALIDATION`'s six requirements map
to `metadata` (version, status), `required sections`, `requirement references` and `traceability`.

**Validation never rewrites the document.** It records findings; a fix is a revision (§ 27). A
validator that silently repaired content would make *"unsupported claims"* undetectable on the next
run.

`check_type` is stable across types; **applicability varies by type** and is declared in each § 12.3
/ 14.3 / etc. contract block. RTM is the one type where `unsupported claims` and `missing
information` do not apply.

---

# 21. REVIEW

Review must support:

- reviewer
- role
- assigned_by
- due date
- priority
- overall status
- section status
- comments

Required entities:

REVIEW

REVIEW_ASSIGNMENT

REVIEW_SECTION

REVIEW_COMMENT

## 21.1 Contract — ADDED

| Requirement | Table.column |
| --- | --- |
| reviewer | `review_assignments.reviewer_user_id` |
| role | `review_assignments.reviewer_role` |
| assigned_by | `review_assignments.assigned_by_user_id` |
| due date | `review_assignments.due_at` |
| priority | `reviews.priority` (`LOW` · `MEDIUM` · `HIGH` · `URGENT`) |
| overall status | `reviews.status` |
| section status | `review_sections.status` (`PENDING` · `APPROVED` · `CHANGES_REQUESTED` · `REJECTED`) |
| comments | `review_comments` — optionally anchored to a section |

Four outcomes, applied through **one** endpoint (`07 § 18`): `APPROVE`, `REQUEST_CHANGES`,
`REJECT`, `ESCALATE`. A single decision endpoint prevents two outcomes being recorded concurrently
for one review.

`review.png`'s *"3 of 5"* is served as `sections_reviewed` / `sections_total`, computed from
`review_sections` — never counted in the browser (`CLAUDE.md § 2`).

`DOCUMENT_REVIEW` ≠ `DOCUMENT_APPROVE` (`11 § 5`). A reviewer approving a section does not approve
the document; § 22 does that, and `05 § 5.12` keeps the two workflow states distinct for the same
reason.

---

# 22. APPROVAL

Approval is a workflow-controlled action.

Approval model:

DECISION REQUIRED

Supported candidate models identified in existing requirements:

- single approver
- sequential approval chain
- staged approval pipeline

Do not implement one until the product decision is made.

## 22.1 🟠 D-04 — storage is model-agnostic — ADDED

The decision stands. **The data model can already store any of the three**, so the schema is not
blocked:

| Table | Purpose |
| --- | --- |
| `approvals` | One per document version under approval: `status`, `requested_by`, `requested_at`, `decided_at`, `policy_version_id` |
| `approval_steps` | Ordered steps: `sequence`, `approver_user_id`, `approver_role`, `status`, `decided_at`, `decision_note`, `delegated_from_user_id` |

- **Single approver** — one `approval_steps` row.
- **Sequential chain** — N rows, ascending `sequence`, each gated on its predecessor.
- **Staged pipeline** — N rows sharing a `sequence` value, all of a stage required before the next.

What the decision determines is the **completion rule** — how many steps at which sequence must be
`APPROVED` for `approvals.status` to become `APPROVED`. That is one policy key
(`approval.completion_rule`, `06 § 30.4`), unset. Under `05 § R4` the `APPROVAL` state halts rather
than assume, and `07 § 19` returns `422 POLICY_RULE_MISSING`.

**Approval is reachable.** `05 § 5.12` gives `APPROVAL` two inbound edges. Revision 1's model, in
which `HUMAN_REVIEW.APPROVE` went straight to `DOCUMENT_GENERATION`, made the state unreachable —
that defect is resolved.

**Approval integrity, independent of D-04:** `APPROVAL_GRANTED` requires `actor_type='USER'` with a
real `actor_user_id`, enforced by constraint (`11 § 21.2`). `08 § 18`: *"Agents cannot impersonate
human approval."* `13 § APPROVAL`'s four criteria — cannot be overwritten, immutable, approval
event, audit record — are all satisfied by § 5.1 and `11 § 21.2` regardless of which model is
chosen. Approval decisions require `If-Match` (`07 § 19`), so two approvers cannot both decide a
stale version.

`approval.png`'s donut reads *1 of 3* while all three chain rows read *Pending* — those cannot both
be true. **The mockup's counts must not be reproduced literally**; the count is computed from
`approval_steps`.

---

# 23. PDF

PDF output must be a real generated file.

Must support:

- cover
- metadata
- table of contents where applicable
- numbered headings
- tables
- headers
- footers
- page numbers
- references
- revision information

## 23.1 Contract — ADDED

Applies to **all 11 types**. `13 § PDF`: *"Generated PDF must be a real file"* with cover, metadata,
revision history, table of contents, content, page numbers.

Stored as a `document_renditions` row: `document_version_id`, `format='PDF'`, `status`,
`storage_key`, `byte_size`, `checksum_sha256`, `page_count`, `generated_at`.

- A rendition is generated **server-side** and stored. `09 § 26`: *"The frontend must not generate
  fake download files."*
- Download requires `status='READY'`. **There is no synthesise-on-download path** — a download that
  built a file on demand could return content differing from the approved version.
- `byte_size` and `checksum_sha256` make *"a real generated file"* verifiable by test
  (`12 § 22`) rather than asserted.
- Table of contents *where applicable*: generated for the **6 narrative types** (BRD, SRS, FRD,
  NFRD, TEST_PLAN, TECHNICAL_DOCUMENTATION) and omitted for the **5 register types** (RTM,
  TEST_CASES, RISK_ASSESSMENT, SECURITY_ASSESSMENT, COMPLIANCE_ASSESSMENT), whose body is a single
  matrix. 6 + 5 = 11 (§ 30).

---

# 24. DOCX

DOCX must preserve:

- headings
- tables
- numbering
- document metadata
- revision history

Applies to **all 11 types**. Stored as a `document_renditions` row with `format='DOCX'`, under the
same rules as § 23.1. `04` lists only a PDF Service and is corrected to add DOCX and XLSX.

---

# 25. XLSX

XLSX is required for structured tabular outputs such as:

- RTM
- test case matrices

XLSX generation contract must define workbook sheets/columns before implementation.

## 25.0 ✅ D-15 RESOLVED for the two named outputs — ADDED

**Definition only. No XLSX implementation is created by this specification.**

Two workbooks are required, one per named output. Stored as `document_renditions` rows with
`format='XLSX'`; `409 RENDITION_NOT_APPLICABLE` for every type without an XLSX contract
(`07 § 16`).

## 25.1 RTM workbook

| Property | Value |
| --- | --- |
| Workbook | `RTM_{project_key}_{document_version}.xlsx` |
| Sheets | `Traceability Matrix` · `Document Control` |
| Export endpoint | `GET /documents/{document_id}/xlsx` |
| Permission | `DOCUMENT_READ` + `DOCUMENT_DOWNLOAD` (🔵 MC-02) |

**Sheet `Traceability Matrix`** — the nine columns of `03 § 25`, in that order:

| # | Column | Type | Source |
| --- | --- | --- | --- |
| 1 | Requirement ID | text | `requirements.human_key` (🟠 D-09) |
| 2 | Business Requirement | text | `requirements.title` where `type='BUSINESS'` |
| 3 | Functional Requirement | text | linked `requirements` where `type='FUNCTIONAL'` |
| 4 | SRS Reference | text | linked `requirements` where `type='SRS'` |
| 5 | Design Reference | text | linked `design_elements` — **empty, 🔵 MC-03** |
| 6 | Test Case ID | text | linked `test_cases` |
| 7 | Risk ID | text | linked `risks` |
| 8 | Evidence | text | linked `evidence` |
| 9 | Status | text | computed coverage status |

**Relationships.** Columns 3–8 are one-to-many. One row per requirement, multiple links joined by
`; ` within the cell — **not** merged cells, which are unreadable by every spreadsheet library and
would make the export unparseable by the tests that must verify it.

**Formatting.** Row 1 bold header, frozen. Auto-filter on row 1. Column widths sized to content.
All cells text-formatted — no cell contains a formula, so the export cannot execute anything when
opened. Empty means empty; no `N/A` placeholder is written, because an absent link is a real finding
(§ 12.3).

**Sheet `Document Control`** — `document_id`, `document_type`, `version`, `status`, `generated_at`,
`generation_run_id`, `policy_version_id`, and one row per `generation_run_sources` entry with its
`source_version` and `content_hash`. This makes an exported workbook self-describing: the source
freeze travels with the file.

🟠 **D-19 residual.** Columns 1 and 2 both denote the business requirement — column 1 its identifier,
column 2 its text — while `09 § 12`'s chain names a single `Requirement` root. Whether these are one
entity or two (a separate *Business Requirement* node above `requirements`) is undecided. The
nine-column layout is authoritative for display and export; only the semantics of columns 1–2
remain open, and both readings produce the same nine columns.

## 25.2 TEST_CASES workbook

| Property | Value |
| --- | --- |
| Workbook | `TEST_CASES_{project_key}_{document_version}.xlsx` |
| Sheets | `Test Cases` · `Document Control` |
| Export endpoints | `GET /documents/{document_id}/xlsx` · `GET /projects/{id}/test-cases/export` |
| Permission | `DOCUMENT_READ` + `DOCUMENT_DOWNLOAD`, or `TEST_CASE_READ` for the register export (🔵 MC-02) |

**Sheet `Test Cases`** — the eleven fields of § 14, in that order:

| # | Column | Type | Source |
| --- | --- | --- | --- |
| 1 | Test Case ID | text | `test_cases.human_key` (🟠 D-09) |
| 2 | Title | text | `test_cases.title` |
| 3 | Objective | text | `test_cases.objective` |
| 4 | Preconditions | text | `test_cases.preconditions` |
| 5 | Steps | text (multi-line) | `test_cases.steps` — one numbered step per line |
| 6 | Expected Result | text | `test_cases.expected_result` |
| 7 | Actual Result | text | `test_case_results.actual_result` — **empty, 🔵 MC-03** |
| 8 | Status | text | `test_case_results.status`, else `NOT_EXECUTED` |
| 9 | Requirement References | text | `traceability_relationships` |
| 10 | Risk References | text | `traceability_relationships` |
| 11 | Evidence | text | `evidence` |

**Formatting.** As § 25.1, plus wrapped text on columns 4–6, and no conditional formatting on
column 8 — a colour scale implying pass/fail on `NOT_EXECUTED` rows would present absence of a
result as a result.

**Sheet `Document Control`** — as § 25.1.

## 25.3 Types without an XLSX rendition

BRD · SRS · FRD · NFRD · TEST_PLAN · TECHNICAL_DOCUMENTATION — narrative documents. Requesting XLSX
returns `409 RENDITION_NOT_APPLICABLE`.

## 25.4 🟠 D-15 residual — the register types

RISK_ASSESSMENT, SECURITY_ASSESSMENT and COMPLIANCE_ASSESSMENT are tabular registers and would
export cleanly, but § 25's list is *"such as: RTM, test case matrices"* — an example list, so it
neither includes nor excludes them.

**Safer behaviour applied:** only the two explicitly named outputs get an XLSX rendition. The other
three return `409 RENDITION_NOT_APPLICABLE` until the decision is made. Adding a workbook later is
additive; publishing one whose column set is then changed is not, because exported files are already
in users' hands.

Were they added, their columns would be § 15's eleven, § 16's nine and § 17's seven respectively —
recorded here so the decision is a yes/no, not a design exercise.

---

# 26. DOWNLOAD

Only authorized users may download documents.

Download action must retrieve the stored generated artifact.

The frontend must not generate fake download files.

## 26.1 Contract — ADDED

`GET /documents/{id}/download?format=PDF|DOCX|XLSX` → **`302` to a short-lived signed object-storage
URL**, so document bytes never traverse the API tier. Preconditions, all server-side:

1. Authenticated, tenant resolved from the session.
2. `DOCUMENT_READ` and `DOCUMENT_DOWNLOAD` (🔵 MC-02).
3. A `document_renditions` row with `status='READY'` — otherwise `409 RENDITION_NOT_READY`.
4. `DOCUMENT_DOWNLOADED` audit event with the format and rendition checksum (`11 § 21.2`).

The signed URL is scoped to one object, one method, one short expiry. It is not a bearer token for
storage, and it is not reusable for another document.

---

# 27. REVISION

Revision:

Existing Version
↓
Create New Draft Version
↓
Apply Changes
↓
Validate
↓
Review
↓
Approval if required
↓
New Version

Previous versions remain immutable.

## 27.1 Contract — ADDED

`POST /documents/{id}/revise` creates a new `document_versions` row with `minor + 1` (or `major + 1`
from an approved version, per § 5), copies sections, and links `derived_from_version_id`. The prior
version is untouched.

Section edits are `PATCH /document-sections/{id}` with `If-Match: <lock_version>`; a stale write
returns `409 CONFLICT_STALE_VERSION`. Editing a section of an `APPROVED` version returns
`410 RESOURCE_IMMUTABLE` from the trigger in § 5.1 — the check is in the database, so no code path
can miss it.

Revision resets validation: the new version's `validation_runs` set is empty, so it cannot inherit a
`PASSED` result from content that has changed.

---

# 28. FAILURE

Generation failure:

FAILED

The failure must include:

- safe user message
- error code
- request ID
- retryability

Retry endpoint:

DECISION REQUIRED

No frontend retry button should call a nonexistent endpoint.

## 28.1 ✅ Retry endpoint — RESOLVED

The endpoint exists: **`POST /generation-runs/{generation_run_id}/retry`** (`07 § 15`), permission
`DOCUMENT_GENERATE`, audit `DOCUMENT_GENERATION_REQUESTED`. It retries the failed run against the
**frozen** `generation_run_sources` set, so a retry regenerates from identical inputs rather than
from sources that may have moved.

`retryable` is returned by the backend from `generation_runs.failure_code` — the frontend never
decides (`CLAUDE.md § 2`, `03 § 15`). A non-retryable failure (invalid type, missing sources,
authorization) renders no retry button, satisfying *"No frontend retry button should call a
nonexistent endpoint."*

The four required fields map to `07 § 1.1`'s envelope: `message`, `code`, `request_id`, plus
`retryable`. No stack trace (`07`).

---

# 29. AUDIT

Audit:

- generation
- revision
- validation
- review
- approval
- rejection
- download where required

## 29.1 Event mapping — ADDED

The authoritative catalogue is `11 § 21.2`. This section's seven categories map to:

| Category | Events |
| --- | --- |
| generation | `DOCUMENT_GENERATION_REQUESTED` · `DOCUMENT_GENERATED` · `DOCUMENT_GENERATION_FAILED` |
| revision | `DOCUMENT_REVISED` · `DOCUMENT_UPDATED` |
| validation | `DOCUMENT_VALIDATION_REQUESTED` · `DOCUMENT_VALIDATED` |
| review | the 11 `REVIEW_*` events |
| approval | `APPROVAL_REQUESTED` · `APPROVAL_GRANTED` |
| rejection | `APPROVAL_REJECTED` · `REVIEW_REJECTED` |
| download | `DOCUMENT_DOWNLOADED` · `RENDITION_REQUESTED` |

*"where required"* for download is resolved to **always**: `13 § APPROVAL` requires an audit record
for approved documents, and an approved document leaving the platform is exactly the event an
auditor needs.

---

# 30. DOCUMENT TYPE INVENTORY — ADDED

| # | Type | Sections | Kind | Sources tab | Traceability tab | XLSX | Section-level review |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | BRD | 21 | narrative | ✅ | ✅ | — | ✅ |
| 2 | SRS | 25 | narrative | ✅ | ✅ | — | ✅ |
| 3 | FRD | 14 | narrative | ✅ | ✅ | — | ✅ |
| 4 | NFRD | 18 | narrative | ✅ | ✅ | — | ✅ |
| 5 | RTM | 6 | register | ✅ | ✅ | ✅ | — |
| 6 | TEST_PLAN | 16 | narrative | ✅ | ✅ | — | ✅ |
| 7 | TEST_CASES | 7 | register | ✅ | ✅ | ✅ | — |
| 8 | RISK_ASSESSMENT | 7 | register | ✅ | ✅ | 🟠 D-15 | — |
| 9 | SECURITY_ASSESSMENT | 7 | register | ✅ | ✅ | 🟠 D-15 | — |
| 10 | COMPLIANCE_ASSESSMENT | 7 | register | ✅ | ✅ | 🟠 D-15 | — |
| 11 | TECHNICAL_DOCUMENTATION | 15 | narrative | ✅ | ✅ | — | ✅ (A-02) |

**All 11 types now have an explicit ordered section list.** All 11 support PDF and DOCX; 2 support
XLSX with 3 undecided.

`03 § 22`'s *"Exact tab applicability must follow document type specification"* is resolved here:
both tabs are shown for every type, because every type has `generation_run_sources` rows and every
type participates in traceability. Applicability is per **content**, not per type — an empty tab
displays its emptiness rather than being hidden, so a missing link is visible.

## 30.1 Per-type status

| Type | Status | Blocking items |
| --- | --- | --- |
| BRD | ✅ implementable | 🟠 D-09 (human key), 🟠 D-04 (approval completion) |
| SRS | ✅ implementable | 🟠 D-09, D-04, D-10 (SLA sections render `UNVERIFIED`) |
| FRD | ✅ implementable | 🟠 D-09, D-04 |
| NFRD | ✅ implementable | 🟠 D-09, D-04, D-10 |
| RTM | 🔵 partial | MC-03 — Design column empty |
| TEST_PLAN | ✅ implementable | 🟠 D-09, D-04 |
| TEST_CASES | 🔵 partial | MC-03 — Actual Result / Status empty |
| RISK_ASSESSMENT | 🟠 partial | D-06 — `score` stays `NULL` |
| SECURITY_ASSESSMENT | ✅ implementable | 🟠 D-09, D-04 |
| COMPLIANCE_ASSESSMENT | 🔵 partial | MC-01 — no framework catalogue |
| TECHNICAL_DOCUMENTATION | ⚠ A-02 | Amendment must be accepted or the type is unimplementable |

**6 of 11 are fully implementable** once D-04 and D-09 are answered. Four render with a visibly
empty column or field rather than fabricated content. One waits on an amendment.

---

# 31. OPEN ITEMS — ADDED

| ID | Item | Effect here |
| --- | --- | --- |
| 🟠 D-04 | Approval completion rule | `APPROVAL` halts for all 11 types (§ 22.1) |
| 🟠 D-06 | Risk scoring policy | `RISK_ASSESSMENT.score` `NULL` (§ 15.2) |
| 🟠 D-09 | Human-readable ID format | Every `*_ID` column and XLSX column 1 (§ 6.1) |
| 🟠 D-10 | SLA values | NFRD §§ 5–7, 14–15 and SRS §§ 17–19 render `UNVERIFIED` (§ 11.2) |
| 🟠 D-15 | XLSX for register types | 3 types return `409` (§ 25.4) |
| 🟠 D-19 | RTM column semantics | Columns 1–2 of the RTM sheet (§ 25.1) |
| 🔵 MC-01 | Compliance framework catalogue | No control validation (§ 17.2) |
| 🔵 MC-02 | Permission catalogue | `DOCUMENT_DOWNLOAD` undefined → downloads deny (§ 26.1) |
| 🔵 MC-03 | Design elements; test-result ingestion | RTM and TEST_CASES columns empty (§§ 12.1, 14.2) |
| ⚠ A-02 | TECHNICAL_DOCUMENTATION sections | Accept or the type is unimplementable (§ 18.1) |
| — | `04` document service list | Corrected to 11 types + DOCX + XLSX (§ 2.1) |
