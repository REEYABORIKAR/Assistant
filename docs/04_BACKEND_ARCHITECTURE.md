# 04 BACKEND ARCHITECTURE

**Revision:** 2 (2026-08-26) — FINAL ARCHITECTURE RESOLUTION PASS

Revision 1's request pipeline and async architecture are preserved unchanged. This revision corrects
one **defect** — the Document Generation Service listed 8 of the 11 document types (§ 12.1) — adds
the DOCX and XLSX services `09 § 23` requires, and adds the ten services other specifications
require but revision 1 never named (§ 16).

---

# 1. REQUEST PIPELINE

Frontend
↓
API Gateway
↓
Authentication
↓
Tenant Resolution
↓
RBAC / ABAC
↓
Application Services
↓
Workflow Engine
↓
Supervisor
↓
Agents
↓
Validation
↓
Policy Engine
↓
Tool Registry
↓
Integrations

## 1.1 Ordering is mandatory — ADDED

The order is a security property, not a diagram convention:

| Stage | Failure | Why it precedes the next |
| --- | --- | --- |
| Authentication | `401` | An unauthenticated request has no tenant to resolve |
| Tenant Resolution | `403` | Authorization is meaningless without a tenant scope |
| RBAC / ABAC | `403` | `11 § 27`: *"If permission is not explicitly granted: DENY"* |
| Application Services | `4xx` | Input validation |
| Workflow Engine | `409` | Illegal transitions rejected against `05`'s table |
| Validation | — | `08 § 10` |
| Policy Engine | `422` | Halts on a missing rule; never defaults |
| Tool Registry | `403` | The only path to Integrations |

**Tenant resolution never reads a tenant from the request body or a header the client controls.** It
derives from the authenticated session. A client-supplied tenant identifier would make tenant
isolation a client decision (`CLAUDE.md § 2`).

**Nothing reaches Integrations except through the Tool Registry** (`10 § 4.1`).

---

# SERVICES

## 2. Auth Service

Responsibilities:

- registration
- login
- sessions
- token validation
- password reset

Tables: `users`, `sessions`, `refresh_tokens`, `password_reset_tokens`, `consents`.
🟠 **D-20** consent types · 🟠 **D-25** token lifetimes · 🟠 **D-28** password policy.
**No endpoint returns a raw secret** (`11 § 9.1`).

## 3. Tenant Service

- tenant isolation
- tenant configuration
- membership

🟠 **D-01** — the isolation strategy is undecided, and this service's implementation differs most
between the three candidates (`11 § 3`). *"Do not silently choose."*

## 4. Project Service

- projects
- members
- project settings

## 5. Chat Service

- conversations
- messages
- streaming
- context

Streaming is SSE (`07 § 9`). Context assembly enforces `08 § 12.1`'s seven buckets and re-checks
authorization per source. 🔵 Retrieval strategy undefined (`03 § 10`).

## 6. File Service

- uploads
- metadata
- scanning
- storage
- extraction

Owns `03 § 11`'s twelve-stage flow. 🟠 **D-26** — no MIME allow-list or size ceiling.
*"Files must never be executed as code"* (`11 § 8`).

## 7. Workflow Service

- definitions
- versions
- runs
- state transitions
- retries

**`05` is the sole authority for states and transitions.** This service executes that table; it does
not define one. ✅ **D-02** — fixed graph, configurable capabilities (`03 § 13.1`); no interpreter.
🟠 **D-05** — retry policy unset, so *retries* here means the manual endpoint only.

## 8. Agent Service

- agent execution
- structured outputs
- model routing
- agent traces

Eight agents (`08 § 2.1`). Writes `agent_runs`, 26 columns (`08 § 19`). Model routing goes through
`model_configurations`; *"Do not hard-code a provider-specific implementation into agent logic"*
(`08 § 16`).

## 9. Validation Service

- schema validation
- business validation
- traceability
- policy validation

Four of `08 § 10`'s eight checks are deterministic and run before any model call (`08 § 10.2`).
Writes `validation_runs`, `validation_findings`.

## 10. Tool Registry

Central authorization layer for tools.

Nine tools (`10 § 4.1`), eleven-stage chain (`11 § 17.1`). `enabled` defaults `false`;
`allowed_agents` empty (🟠 **D-27**). **No runtime tool creation.** Every attempt — including a
denied one — writes `tool_calls` + an audit event (`11 § 21.3`).

## 11. Integration Service

Jira
Confluence
Notion

Reachable **only** from the Tool Registry. Jira read+write; Confluence and Notion read-only.
🔵 **MC-04** — no auth method for Confluence or Notion (`10 §§ 2.1, 3.1`).

## 12. Document Service

- documents
- sections
- versions
- sources
- approvals

Approved versions are immutable, enforced by trigger → `410 RESOURCE_IMMUTABLE` (`09 § 5.1`).

## 13. Document Generation Service

- BRD
- SRS
- FRD
- NFRD
- RTM
- TEST_PLAN
- TEST_CASES
- RISK_ASSESSMENT
- SECURITY_ASSESSMENT
- COMPLIANCE_ASSESSMENT
- TECHNICAL_DOCUMENTATION

## 13.1 ✅ Corrected — three types were missing

Revision 1 listed *"BRD, SRS, FRD, NFRD, RTM, testing documents, risk documents"* — collapsing two
types into *"testing documents"*, one into *"risk documents"*, and **omitting SECURITY_ASSESSMENT,
COMPLIANCE_ASSESSMENT and TECHNICAL_DOCUMENTATION entirely.**

`09 § 2.1` identified this as **the one real defect** in the D-08 document-type reconciliation: `01`,
`09 § 2` and `03 § 21` all list eleven; only `04` disagreed. Corrected above to the authoritative
eleven.

Each type's ordered section list is fixed by `09 §§ 10–18`. The service fills a fixed skeleton; it
does not choose sections (`08 § 11.1`).

## 14. Rendering Services

### 14.1 PDF Service

Generates actual PDF files.

### 14.2 DOCX Service — ADDED

Generates actual DOCX files for all eleven types.

### 14.3 XLSX Service — ADDED

Generates actual XLSX workbooks for **RTM** and **TEST_CASES** only (`09 § 25`).

## 14.4 Why three services and not one — ADDED

Revision 1 named only the PDF Service, yet `CLAUDE.md § TECHNOLOGY` requires PDF, DOCX **and** XLSX,
and `09 § 23` defines renditions in all three. DOCX and XLSX were therefore unassigned.

Shared contract for all three:

- a rendition row records `byte_size` and `checksum_sha256`, so *"must be a real file"*
  (`13 § PDF`) is a testable assertion, not a claim
- **there is no synthesise-on-download path** — a download returns a stored artefact or `404`
  (`09 § 23.1`)
- the frontend never generates a file (`09 § 26`)
- **XLSX cells contain no formulas**, so an export cannot execute anything when opened
  (`09 § 25.1`)

They are separate services because the libraries and failure modes are unrelated — a DOCX library
fault must not make PDF generation unavailable.

## 15. Audit Service

Records security-sensitive and business-critical events.

**111 event types across 15 groups** — `11 § 21.2` is the authoritative catalogue. Eight fields per
record, including `outcome` (`11 § 21.1`). Append-only: the application role holds `INSERT` and
`SELECT`, no `UPDATE` or `DELETE`. Metadata carries the input **hash**, not the input
(`11 § 21.3`). 🔵 **MC-05** — no tamper-evidence contract; *"Append-only grants stop the
application; they do not stop a database administrator."*

---

# 16. SERVICES REQUIRED BY OTHER SPECIFICATIONS — ADDED

Revision 1 named 14 services. Ten more are required by contracts elsewhere in the repository and had
no owning service, which is why several `07` endpoint groups had no implementation home.

## 16.1 Policy Service

Appears in revision 1's pipeline diagram (§ 1) but had **no service block** — the pipeline referenced
a component that did not exist in the service list.

Owns `policies`, `policy_versions`, `policy_scopes`, `policy_rules`, `policy_evaluations`. Covers
retry, risk thresholds, approval requirement, human review, agent permissions, tool permissions,
data-availability behaviour, retention and quota.

**Halts rather than defaults.** A missing rule returns `422 POLICY_RULE_MISSING`; `05`'s
`POLICY_EVALUATION` state stops the run (`05 § R4`). Several 🟠 decisions are single unset keys:
`approval.completion_rule` (D-04), `retry.max_attempts` (D-05), `risk.scoring` (D-06),
`rate_limit.*` (D-11).

## 16.2 Requirement Service

`03 § 12` and `07 § 11`'s 8 endpoints had no service. Owns `requirements`, `requirement_versions`,
`requirement_links`. **Assigns requirement identity** — never the agent (`08 § 5.1`).

## 16.3 Analysis Service (risk · security · compliance)

`07 § 12`'s 17 endpoints had no service. Owns `risks`, `security_findings`, `compliance_findings`,
`evidence`.

**Evidence gates are database constraints, not service logic** — `VERIFIED` and `COMPLIANT` require
an evidence row, so the rule cannot be bypassed by any write path (`09 §§ 16.2, 17.2`).
🟠 **D-06** — `risks.score` stays `NULL`. 🔵 **MC-01** — no framework catalogue.

## 16.4 Test Artefact Service

`07 § 13`'s 8 endpoints had no service. Owns `test_cases`, `test_case_steps`, `test_case_results`.

**Results are recorded, never generated** — a generated actual result is a fabricated test result
(`09 § 14.2`, `CLAUDE.md § 5`). 🔵 `POST /test-cases/{id}/results` has no ingestion contract.

## 16.5 Traceability Service

`03 § 25`, `07 § 14` and `09 § 12` had no service. Owns `traceability_relationships` and builds the
RTM's nine columns.

Polymorphic referential integrity is enforced by trigger, so *"Every displayed mapping must
reference actual stored records"* (`03 § 25`) holds at the storage layer.
🔵 **MC-03** — `design_elements` is unspecified, so the Design Reference column renders empty.

## 16.6 Review Service

`03 § 23` and `07 § 18`'s endpoints had no service. Owns `reviews`, `review_assignments`,
`review_sections`, `review_comments`.

Computes `sections_reviewed`/`sections_total` server-side — `review.png`'s *"3 of 5"* is never
counted in the browser. **A reviewer cannot approve the document**: `DOCUMENT_REVIEW` ≠
`DOCUMENT_APPROVE` (`03 § 23.1`).

## 16.7 Approval Service

`03 § 24` and `07 § 19` had no service. Owns `approvals`, `approval_steps`.

Storage supports all three candidate models; 🟠 **D-04** is one unset policy key. Requires
`If-Match` (`12 § 35`). **`actor_type = 'USER'` is enforced by constraint** — *"Agents cannot
impersonate human approval"* (`08 § 18.2`).

## 16.8 Admin Service

`03 § 28` and `07 § 25` had no service. Owns `roles`, `permissions`, `role_permissions`,
`user_roles`, `model_configurations`, `templates`, `quotas`.

🟠 **D-13** role model. 🔵 **MC-02** — five admin areas gated. **No tool-create endpoint**
(`03 § 28.1`). Quota limits are unseeded and `quota.enforced` defaults `false` — `admin.png`'s
*1 TB* and *100,000* are mockup values.

## 16.9 Dashboard Service

`07 § 26`'s `GET /dashboard/metrics` had no service. Returns real counts.
`chat.png`'s **24 / 18 / 7 / 12** must not be reproduced (`03 § 32.1`).

## 16.10 Reporting Service — 🔴 BLOCKED

`03 § 27` marks Reports **BLOCKED**: no report types, data sources, filters, permissions, export
formats, APIs or database requirements are specified. **No endpoint is defined and none is
implemented.**

Reusing dashboard metrics as *reports* would be inventing report functionality, which `03 § 27`
explicitly forbids.

## 16.11 🔵 Notification Service — no contract

`06 § 44.1` defines a `notifications` table, but **no page, endpoint, trigger or delivery channel
exists in any file** (`07 § 27`). The table exists; the service does not. Review assignment and
approval requests would plausibly notify — *plausibly* is not a contract, and choosing a channel
(in-app, email, webhook) is a product decision.

---

# 17. ASYNC ARCHITECTURE

Long-running tasks must not block HTTP requests.

Use:

API
↓
Create Job
↓
Queue
↓
Worker
↓
Database
↓
Event
↓
SSE/WebSocket
↓
Frontend

## 17.1 Contract — ADDED

**Realtime transport is SSE.** `CLAUDE.md` allows *"SSE or WebSockets"*; `07 § 9` defines SSE
endpoints and every stream in the product is server→client only, so no bidirectional channel is
needed. WebSockets would add a second auth surface for no capability gained.

Three async operations, each returning `202` with an identifier:

| Operation | Job | Stream |
| --- | --- | --- |
| File extraction | `POST /files` → `202` | poll `GET /files/{id}` |
| Workflow run | `POST /workflows/{id}/runs` → `202 {run_id}` | `GET /workflow-runs/{id}/stream` |
| Document generation | `POST .../documents/generate` → `202 {document_id, generation_run_id}` | poll `GET /documents/{id}/generation-runs` |

`CLAUDE.md § TECHNOLOGY` requires **retry and dead-letter handling**. Dead-lettered jobs mark their
run `FAILED` with an `error_code`; `05`'s `FAILED` is terminal, so a lost job cannot leave a run
`RUNNING` forever.

**No progress percentage is emitted.** Events carry `current_state`, `steps_completed`,
`steps_total`. `workflow-running.png`'s `60%` and *"Estimated completion"* have no defined
computation and must not be reproduced (`03 § 15.2`) — fabricated progress is forbidden by
`CLAUDE.md § 1`.

**Every stream re-authorizes on connect and is scoped to the caller's tenant.** A long-lived
connection that outlived a permission revocation would be an authorization bypass.

---

# 18. SERVICE INVENTORY — ADDED

| # | Service | § | Status |
| --- | --- | --- | --- |
| 1 | Auth | 2 | 🟠 D-20, D-25, D-28 |
| 2 | Tenant | 3 | 🟠 **D-01** |
| 3 | Project | 4 | ✅ |
| 4 | Chat | 5 | 🔒 MC-02 · 🔵 retrieval |
| 5 | File | 6 | 🟠 D-26 |
| 6 | Workflow | 7 | ✅ (🟠 D-02 residual, D-05) |
| 7 | Agent | 8 | ✅ (🟠 D-27) |
| 8 | Validation | 9 | ✅ |
| 9 | Tool Registry | 10 | ✅ (🟠 D-27) |
| 10 | Integration | 11 | 🔵 MC-04 (2 of 3) |
| 11 | Document | 12 | ✅ |
| 12 | Document Generation | 13 | ✅ **corrected to 11 types** |
| 13 | PDF | 14.1 | ✅ |
| 14 | **DOCX** | 14.2 | ✅ **added** |
| 15 | **XLSX** | 14.3 | ✅ **added** (2 outputs) |
| 16 | Audit | 15 | ✅ (🔵 MC-05) |
| 17 | **Policy** | 16.1 | 🟠 D-04, D-05, D-06, D-11 |
| 18 | **Requirement** | 16.2 | 🔒 MC-02 |
| 19 | **Analysis** | 16.3 | 🔒 MC-02 · 🟠 D-06 · 🔵 MC-01 |
| 20 | **Test Artefact** | 16.4 | 🔒 MC-02 · 🔵 result ingestion |
| 21 | **Traceability** | 16.5 | 🔒 MC-02 · 🔵 MC-03 |
| 22 | **Review** | 16.6 | ✅ |
| 23 | **Approval** | 16.7 | 🟠 D-04 |
| 24 | **Admin** | 16.8 | 🟠 D-13 · 🔒 MC-02 |
| 25 | **Dashboard** | 16.9 | ✅ |
| 26 | **Reporting** | 16.10 | 🔴 **BLOCKED** |
| 27 | **Notification** | 16.11 | 🔵 no contract |

**27 services. Revision 1 named 14.** Twelve are added and one (Document Generation) is corrected.

**11 are fully specified.** 1 is blocked outright, 1 has no contract, and the remainder wait on a
decision or on MC-02 — not on architecture.
