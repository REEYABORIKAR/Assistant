# IMPLEMENTATION PLAN

**Status:** SPECIFICATION + ARCHITECTURE FINALIZATION — NOT APPROVED, NOT STARTED
**Revision:** 3 (2026-08-26)
**Changed since revision 2:** all four remaining spec stubs are now populated · `12_TEST_PLAN` grew by §§ 42–44 · revision 2's "four empty stubs" finding is **superseded and corrected**

No application code. No migrations. No mock APIs. No placeholder implementations. No invented requirement.

---

## 1. VERIFICATION OF CLAIMED SPEC COMPLETIONS

Verified on disk before any analysis. **All five are present and substantive.**

| Spec | Bytes | Lines | mtime | Verdict |
| --- | --- | --- | --- | --- |
| `03_PAGE_SPECIFICATION.md` | 10,518 | 887 | 16:13 | ✅ **PRESENT** — 32 sections, 24 routes |
| `08_AGENT_SPECIFICATION.md` | 6,446 | 479 | 16:14 | ✅ **PRESENT** — 18 sections, all 8 agents |
| `09_DOCUMENT_GENERATION_SPEC.md` | 6,466 | 571 | 16:14 | ✅ **PRESENT** — 29 sections, all 11 types |
| `11_SECURITY_SPEC.md` | 5,939 | 496 | 16:14 | ✅ **PRESENT** — 27 sections, 21 named permissions |
| `12_TEST_PLAN.md` | 10,821 | 846 | 16:15 | ✅ **PRESENT** — grew from 8,375 B; new §§ 42–44 |

**Correction to revision 2.** Revision 2 reported `03`, `08`, `09`, `11` as unchanged 91–102-byte
TODO stubs. That was accurate when written (15:56–16:08) and is **no longer true** — all four
were written at 16:13–16:15. Revision-2 blockers **B-1** (security), **B-2** (agents),
**B-3** (documents) and **B-4** (pages) are hereby **closed**. Everything downstream of them
in this document has been re-derived from the new text, not carried forward.

**Filename discrepancy.** The task referenced `01_PRODUCT_REQUIREMENTS.md`. **No such file
exists.** The actual file is `01_MASTER_PRODUCT_SPEC.md` (1,524 B, 127 lines), which is the
name `CLAUDE.md § SOURCE OF TRUTH` uses. Analysed under its real name; nothing was renamed.

**Repository state.** Still **not a git repository** (`git rev-parse` → fatal). No application
code, no `package.json`, no `pyproject.toml`, no `.env.example`. `docs/ui/` holds the same 15
canonical PNGs (14:57), all re-inspected this round.

`12 §§ 42–44` now encode this phase's discipline **inside the specification**: a 27-check
architecture-consistency gate, a specification-completeness gate (`STATUS = BLOCKED` when any
contract is missing), and a 16-item decision gate. This document is aligned to all three.

---

## 2. STATUS TAXONOMY

| Tag | Meaning |
| --- | --- |
| ✅ **RESOLVED** | A spec or the canonical UI answers it. Implementable. |
| 🟠 **DECISION REQUIRED** | A product or architecture choice a human must make. |
| 🔵 **MISSING CONTRACT** | No source defines the interface, schema, enum, or format. |
| 🔴 **BLOCKER** | Blocks a phase group. |

**Totals: 31 RESOLVED · 24 DECISION REQUIRED · 41 MISSING CONTRACT · 11 BLOCKER**
(Revision 2: 14 / 12 / 27 / 9. Resolutions more than doubled; the four spec-stub blockers were
replaced by six structural ones the new text made visible.)

---

## 3. WHAT THE FOUR NEW SPECS RESOLVED

| # | Now specified | Source |
| --- | --- | --- |
| 1 | **Prompt-injection defence is fully specified** — external content is data, seven separated context buckets incl. `UNTRUSTED_EXTERNAL_CONTENT`, four gates before any tool runs, same expected outcome stated identically in three places | `08 § 12–13`, `11 § 14–15`, `12 § 30` |
| 2 | **Permission catalog** — 21 permissions, `PROJECT_READ` … `ADMIN_TOOLS`. Labelled *"Example permissions"*, so **illustrative, not exhaustive** — a partial resolution: there is no `REQUIREMENT_*`, `CONVERSATION_*`, `RISK_READ`, `WORKFLOW_READ`, `REPORT_*`, `ADMIN_MODELS` or `TOOL_EXECUTE` | `11 § 5` |
| 3 | **Default deny** + the 8-stage protected-request pipeline | `11 § 2`, `§ 27` |
| 4 | **Transitive tenant scoping is explicitly legitimate** — "directly or through a guaranteed tenant-scoped parent relationship" | `11 § 3` |
| 5 | **Tool Registry contract** — ID, description, input/output schema, allowed agents, permissions, risk level; unknown tools rejected | `11 § 16`, `08 § 14` |
| 6 | **Tool execution chain** — 11 stages, agent → audit | `11 § 17` |
| 7 | **All 8 agent contracts** — purpose, input, output shape, responsibilities, restrictions | `08 § 4–11` |
| 8 | **Global agent pipeline** — 16 stages incl. evidence validation and policy validation | `08 § 3` |
| 9 | **Agent execution record fields** — attempt, input hash, output, model, provider, timestamp, error, validation result | `08 § 15` |
| 10 | **Model governance** — provider/model/config/time/tokens recorded; no provider hard-coded into agent logic | `08 § 16` |
| 11 | **Evidence discipline** — security cannot claim verification without evidence; no compliance claim without evidence; risk must express uncertainty | `08 § 6–8` |
| 12 | **Human-review triggers** (5) and *"Agents cannot impersonate human approval."* | `08 § 18` |
| 13 | **11 document types enumerated** | `09 § 2`, `03 § 21` |
| 14 | **Document state set** — 9 states DRAFT…ARCHIVED | `09 § 4` |
| 15 | **BRD required sections** — 21, ordered | `09 § 8` |
| 16 | **SRS required sections** — 25, ordered | `09 § 9` |
| 17 | **FRD / NFRD / RISK / SECURITY / COMPLIANCE / TECHNICAL field sets** | `09 § 10–11, 15–18` |
| 18 | **TEST_CASES field set** — 11 fields | `09 § 14` |
| 19 | **Source freeze** — a generation run records exact source versions so later source edits cannot silently change a generated document | `09 § 7` |
| 20 | **Per-section provenance** — source_type, source_id, source_version, source_location; `UNVERIFIED` when no authoritative source | `09 § 19` |
| 21 | **Document validation checks** — 9, incl. section order and unsupported claims | `09 § 20` |
| 22 | **Revision pipeline** — previous versions immutable | `09 § 27` |
| 23 | **Version scheme** — v0.1 → v0.2 → v1.0 → v1.1, approved immutable, stored in DB | `09 § 5`, `12 § 24` |
| 24 | **24 routes** with purpose, components, actions, states, audit | `03 § 5–28` |
| 25 | **Six global page states** + per-mutation loading/success/error/retry | `03 § 4` |
| 26 | **Pagination comes from backend metadata** — `page`, `page_size`, `total`, `items`; hard-coded `1/36`, `1/45` explicitly forbidden | `03 § 29` |
| 27 | **`+` menu and voice are OUT** — *"Do not implement those actions unless the canonical UI specification is explicitly updated."* Closes revision 2's C-39 | `03 § 9` |
| 28 | **File pipeline** — 12 stages ending `READY / FAILED / QUARANTINED`; *"No fabricated processing percentage."* | `03 § 11`, `11 § 8` |
| 29 | **Backend owns action availability** — *"The frontend must not determine whether an action is allowed."* | `03 § 15` |
| 30 | **Audit categories** — 14 (`03 § 31`) and 13 security-sensitive (`11 § 21`) with 7 required record fields | `03 § 31`, `11 § 21` |
| 31 | **Three architecture gates** — 27 consistency checks · completeness gate · 16-item decision gate | `12 §§ 42–44` |

**Equally important: 13 places where a spec declines to guess** — SLA values (`09 § 11`,
`12 § 34`), rate limits (`11 § 12`), retention (`11 § 22`), RPO/RTO (`11 § 24`), document ID
format (`09 § 6`), XLSX workbook structure (`09 § 25`), retry limit (`08 § 15`), risk scoring
(`08 § 8`), PARTIAL behaviour (`08 § 9`, `03 § 16`), approval model (`09 § 22`, `03 § 24`),
tenant isolation strategy (`11 § 3`), role assignment (`11 § 6`), Reports (`03 § 27`). That
discipline is the single biggest improvement this revision.

---

## 4. REQUIREMENTS TRACEABILITY MATRIX

Legend: ✅ specified · ❌ missing · 🟠 decision required · 🔵 missing contract · `—` N/A
Columns: **Req · Page/Route · UI action · API · Backend service · Agent · Workflow state · DB entity · Validation · Authorization · Audit · Test · Doc output**

**One global note on the Audit column.** `03 § 31` defines 14 audit **categories**, `11 § 21`
defines 13 plus the 7 required **record fields** — but **no spec names a single audit event or
defines an event catalogue**. Every audit cell below therefore means "category ✅ / event name
❌". Counted once as **MC-01 / D-23**, not repeated per row.

### 4.1 Authentication & identity

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-01 Register | `/register` ✅ | Create Account | `POST /auth/register` ✅ | Auth ✅ | — | — | `users` ✅ | ✅ `03 § 6` | public | ✅ cat. | `12 § 6` ✅ | — |
| R-02 Consent capture | `/register` ✅ | consent checkbox | ❌ | Auth | — | — | ❌ **no entity** | 🟠 **D-21** | — | ❌ | ❌ | — |
| R-03 Login | `/login` ✅ | Sign In | `POST /auth/login` ✅ | Auth ✅ | — | — | `users` ✅ + **`sessions` ❌** | ✅ | public | ✅ | `12 § 6` ✅ | — |
| R-04 SSO Google/Microsoft | `/login` canonical | Google, Microsoft | ❌ | ❌ | — | — | ❌ no provider column | ❌ | — | ❌ | ❌ | — |
| R-05 Logout + revocation | global | user menu | `POST /auth/logout` ✅ | Auth ✅ | — | — | **`sessions` ❌** (`11 § 7` revocable) | ✅ | authn | ✅ | `12 § 6` ✅ | — |
| R-06 Token refresh | — | — | `POST /auth/refresh` ✅ | Auth ✅ | — | — | **`refresh_tokens` ❌** | ✅ | authn | 🔵 | 🔵 | — |
| R-07 Password reset | `/login` ✅ | Forgot password | `POST /auth/forgot-password`, `/reset-password` ✅ | Auth ✅ | — | — | **`password_reset_tokens` ❌** | ✅ | public | ✅ | `12 § 6` ✅ | — |
| R-08 Role assignment | `/admin` ✅ | 🟠 undepicted | ❌ | ❌ | — | — | `roles`, `role_permissions` ✅ / **assignment ❌** | ❌ | `ADMIN_ROLES` ✅ | role change ✅ | `12 § 7`, `§ 42.21` ✅ | — |

### 4.2 Tenancy, projects, requirements

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-09 Tenant isolation | all | — | all | Tenant ✅ | — | — | **17 tables lack `tenant_id`** 🟠 | ✅ `11 § 3` | default deny ✅ | failed authz ✅ | `12 § 8`, `§ 42.20` ✅ | — |
| R-10 List projects | `/projects` ✅ | search, filter, open | `GET /projects` ✅ | Project ✅ | — | — | `projects` ✅ | ✅ | `PROJECT_READ` ✅ | — | `12 § 4` ✅ | — |
| R-11 Create project | `/projects` ✅ | New Project | `POST /projects` ✅ | Project ✅ | — | — | `projects` ✅ | ✅ | `PROJECT_WRITE` ✅ | 🔵 | `12 § 4` ✅ | — |
| R-12 Project detail | `/projects/{id}` ✅ | 8 tabs | `GET /projects/{id}` ✅ | Project ✅ | — | — | `projects` ✅ | ✅ | `PROJECT_READ` ✅ | — | 🔵 | — |
| R-13 Project activity | `/projects/{id}` ✅ | Activity | ❌ | ❌ | — | — | ❌ | ❌ | ❌ | ❌ | ❌ | — |
| R-14 Per-project doc count | `/projects` canonical card | — | ❌ aggregate | Document | — | — | `documents` ✅ | — | `DOCUMENT_READ` ✅ | — | `12 § 42.23` ✅ | — |
| R-15 Requirements CRUD | `/projects/{id}/requirements` ✅ | Create, Edit, View, Search, Filter | 3 endpoints ✅ | ❌ **no Requirement Service in `04`** | Requirement ✅ | `REQUIREMENT_ANALYSIS` ✅ | `requirements` ✅ / **no `version`** ❌ | ✅ | ❌ **no `REQUIREMENT_*` permission** | 🔵 | `12 § 14` ✅ | BRD, SRS, FRD, RTM |
| R-16 Stable requirement IDs | — | — | — | — | Requirement ✅ | — | `requirement_key` ✅ | ✅ | — | — | `12 § 14` ✅ | all |

### 4.3 Chat & files

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-17 Conversation CRUD | `/chat` ✅ | New Chat, rename, delete | 6 endpoints ✅ | Chat ✅ | — | — | `conversations` ✅ | ✅ | ❌ no `CONVERSATION_*` perm | 🔵 | `12 § 9` ✅ | — |
| R-18 Send message | `/chat` ✅ | Send | `POST /conversations/{id}/messages` ✅ | Chat ✅ | Supervisor ✅ | — | `messages` ✅ | ✅ | ❌ | 🔵 | `12 § 9` ✅ | — |
| R-19 Streaming | `/chat` ✅ | — | `POST …/messages/stream` ✅ | Chat ✅ | Supervisor ✅ | — | `messages` ✅ | ✅ | ❌ | — | `12 § 9` ✅ | — |
| R-20 Retry / regenerate message | `/chat` ✅ | — | ❌ **no endpoint** | Chat | — | — | `messages` ✅ | ❌ | ❌ | 🔵 | `12 § 9` ✅ | — |
| R-21 Inline chat actions | `/chat` canonical | Create BRD · Create SRS · Create RTM · **View Risks** | via generate ✅ / **View Risks ❌** | Document ✅ | Doc Supervisor ✅ | `DOCUMENT_GENERATION` ✅ | `documents` ✅ | ✅ | `DOCUMENT_GENERATE` ✅ | generation ✅ | 🔵 | BRD, SRS, RTM |
| R-22 Project-scoped chat | `/projects/{id}/chat` ✅ | — | ❌ **no project-chat endpoint** | Chat ✅ | ✅ | — | `conversations.project_id` ✅ | ✅ `03 § 10` | `PROJECT_READ` ✅ | 🔵 | 🔵 | — |
| R-23 Document chat | ❌ no page | — | ❌ | ❌ | — | — | ❌ no doc↔conversation link | ❌ | ❌ | ❌ | ❌ | — |
| R-24 File upload | `/chat`, project ✅ | Attach | `POST /files/upload` ✅ — **`03 § 11` says `POST /files`** ⚠ | File ✅ | — | `DATA_COLLECTION` ✅ | `files` ✅ / **no scan/quarantine column** ❌ | ✅ 12 stages | `FILE_UPLOAD` ✅ | upload ✅ | `12 § 10` ✅ | — |
| R-25 Quarantine | — | status badge | ❌ status enum | File ✅ | — | — | ❌ | ✅ `11 § 8` | `FILE_READ` ✅ | 🔵 | `12 § 10` ✅ | — |
| R-26 Extraction + chunking | — | status badge | ❌ | File ✅ | — | — | `file_chunks` ✅ / **no embedding** ❌ | 🔵 | — | 🔵 | `12 § 10` ✅ | — |
| R-27 Download / delete file | — | — | `GET /files/{id}/download`, `DELETE` ✅ | File ✅ | — | — | `files` ✅ | ✅ | `FILE_READ` / `FILE_DELETE` ✅ | 🔵 | `12 § 4` ✅ | — |
| R-28 Knowledge search | — (dropped by `03 § 9`) | — | ❌ | ❌ | — | — | `file_chunks` ✅ | ❌ | ❌ | ❌ | ❌ | — |

### 4.4 Workflow

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-29 List workflows | `/workflows` ✅ | tabs, search | `GET /workflows` ✅ | Workflow ✅ | — | — | `workflow_definitions` ✅ | ✅ | ❌ no `WORKFLOW_READ` | — | 🔵 | — |
| R-30 Author workflow | `/workflows` 🟠 | New Workflow | `POST /workflows` ✅ | Workflow ✅ | — | — | `workflow_definitions` ✅ | 🟠 **D-02** | `ADMIN_WORKFLOWS` ✅ | admin ✅ | 🔵 | — |
| R-31 Shared workflows | `/workflows` canonical tab | Shared | ❌ | ❌ | — | — | ❌ no sharing model | ❌ | ❌ | ❌ | ❌ | — |
| R-32 Run workflow | `/workflows/{id}` ✅ | Run | `POST /workflows/{id}/run` ✅ — **`03 § 14` says `/runs`** ⚠ | Workflow ✅ | Supervisor ✅ | `CREATED` ✅ | `workflow_runs` ✅ / **no `tenant_id`, no run_key** ❌ | ✅ | `WORKFLOW_RUN` ✅ | execution ✅ | `12 § 11` ✅ | — |
| R-33 Observe run | `/workflow-runs/{id}` ✅ | — | `GET /workflow-runs/{id}`, `/events` ✅ | Workflow ✅ | — | all ✅ | `workflow_steps`, `workflow_events` ✅ | ✅ | `WORKFLOW_RUN` ✅ | — | `12 § 12` ✅ | — |
| R-34 State history | `/workflow-runs/{id}` ✅ | — | ❌ | Workflow ✅ | — | — | ❌ **no state-transition table** | ✅ `12 § 12` | — | transition ✅ | `12 § 12`, `§ 42.3` ✅ | — |
| R-35 Cancel run | `/workflow-runs/{id}` ✅ | Cancel | `POST /workflow-runs/{id}/cancel` ✅ | Workflow ✅ | — | `CANCELLED` ✅ / **cancellable set ❌** | `workflow_runs` ✅ | 🔵 | `WORKFLOW_CANCEL` ✅ | cancellation ✅ | 🔵 | — |
| R-36 Retry run | `/workflow-runs/{id}` ✅ | Retry | `POST /workflow-runs/{id}/retry` ✅ | Workflow ✅ | — | **`RETRY` is not a state** 🔴 | `workflow_steps.attempt` ✅ / **8-field retry record ❌** | 🟠 **D-05** | `WORKFLOW_RETRY` ✅ | retry ✅ | `12 § 11-G`, `§ 42.16` ✅ | — |
| R-37 Estimated completion | canonical `workflow-running.png` | — | ❌ | ❌ no estimator | — | — | ❌ | ❌ | — | — | ❌ | — |
| R-38 Conditional branching | — | — | — | Workflow ✅ | ✅ | **4 conditional points, 3 defective** 🔴 | `workflow_definitions.definition` ✅ | 🔴 | — | ✅ | `12 § 11 A–C`, `§ 42.3–4` ✅ | — |
| R-39 Data availability outcome | `03 § 16` ✅ | — | ❌ | ❌ **no service in `04`** | Data Availability ✅ | `DATA_AVAILABILITY` ✅ / **PARTIAL unrouted** 🔴 | ❌ no outcome storage | ✅ tri-state | — | 🔵 | `12 § 18`, `§ 42.5` ✅ | — |
| R-40 Policy evaluation | — | — | ❌ | Policy Engine ✅ | — | `POLICY_EVALUATION` ✅ | ❌ **no policy entity** | 🔴 no rules defined | — | 🔵 | `12 § 42.4` ✅ | — |

### 4.5 Agents

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-41 Supervisor orchestration | — | — | ❌ no agent API | Agent ✅ | Supervisor ✅ | all ✅ | `agent_runs` ✅ / **6 fields missing** | ✅ output schema | ✅ 5 restrictions | start/complete/fail ✅ | `12 § 13` ✅ | — |
| R-42 Requirement extraction | `/…/requirements` ✅ | — | — | Agent ✅ | Requirement ✅ | `REQUIREMENT_ANALYSIS` ✅ | `requirements` ✅ | ✅ output schema | — | ✅ | `12 § 14` ✅ | BRD, SRS, FRD |
| R-43 Security analysis | `/projects/{id}/security` ✅ | — | ❌ **no findings endpoint** | Agent ✅ | Security ✅ | `SECURITY_ANALYSIS` ✅ | `security_findings` ✅ / **no evidence, remediation, affected_requirement, control** ❌ | ✅ evidence rule | ❌ | ✅ | `12 § 15`, `§ 42.26` ✅ | SECURITY_ASSESSMENT |
| R-44 Compliance analysis | `/projects/{id}/compliance` ✅ | — | ❌ | Agent ✅ | Compliance ✅ | `COMPLIANCE_ANALYSIS` ✅ / **no outgoing transition** 🔴 | `compliance_findings` ✅ / **no gap, remediation, requirement** ❌ | ✅ evidence rule | ❌ | ✅ | `12 § 16`, `§ 42.25` ✅ | COMPLIANCE_ASSESSMENT |
| R-45 Risk analysis | `/projects/{id}/risks` ✅ | — | ❌ | Agent ✅ | Risk ✅ | `RISK_ANALYSIS` ✅ / **disabled branch is a no-op** 🔴 | `risks` ✅ / **no impact, mitigation, owner** ❌ | 🔴 **no scoring policy** | ❌ | ✅ | `12 § 17` ✅ | RISK_ASSESSMENT |
| R-46 Validation | `/workflow-runs/{id}` ✅ | — | ❌ | Validation ✅ | Validation ✅ | `VALIDATION`, `DOCUMENT_VALIDATION` ✅ | `validation_runs` ✅ | ✅ PASSED/FAILED | — | validation ✅ | `12 § 19` ✅ | — |
| R-47 Document supervision | — | — | — | Agent ✅ | Doc Supervisor ✅ | `DOCUMENT_GENERATION` ✅ | ❌ **no generation-run entity** | ✅ | — | ✅ | 🔵 | all |
| R-48 Agent tracing / model governance | `/admin` ✅ | — | ❌ **no agent-runs endpoint** | Agent ✅ | all | — | `agent_runs` ✅ / **missing attempt, input_hash, provider, error, validation_result, tokens** ❌ | ✅ | ❌ | ✅ | 🔵 | — |
| R-49 Tool Registry | `/admin` ✅ | — | ❌ **no registry endpoint** | Tool Registry ✅ | all | — | ❌ **no registry table** (only `tool_calls`) | ✅ `11 § 16` | `ADMIN_TOOLS` ✅ | tool requested/executed ✅ | `12 § 29`, `§ 42.17–18` ✅ | — |
| R-50 Prompt-injection containment | — | — | — | Tool Registry ✅ | all ✅ | — | `tool_calls` ✅ / **no status enum for blocked** ❌ | ✅ 4-gate chain | ✅ | ✅ / **rejected-request contract ❌** | `12 § 30`, `§ 42.19` ✅ | — |
| R-51 Human escalation | `/documents/{id}/review` ✅ | — | ❌ **no escalate endpoint** | Agent ✅ | Supervisor ✅ | `HUMAN_REVIEW` ✅ / **`ESCALATE` has no target** 🔴 | ❌ no review entity | ✅ 5 triggers | `DOCUMENT_REVIEW` ✅ | escalation ✅ | `12 § 13` ✅ | — |

### 4.6 Documents

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-52 List documents | `/projects/{id}/documents` ✅ | search, 2 filters | `GET /projects/{id}/documents` ✅ | Document ✅ | — | — | `documents` ✅ / **no tenant_id, timestamps, validation_status, approval_status** ❌ | ✅ | `DOCUMENT_READ` ✅ | — | `12 § 20` ✅ | — |
| R-53 Generate document | `/…/documents/generate` ✅ | 3-step wizard, Generate | `POST /projects/{id}/documents/generate` ✅ | Doc Generation ✅ **omits SECURITY / COMPLIANCE / TECHNICAL** 🟠 | Doc Supervisor ✅ | `DOCUMENT_GENERATION` ✅ | `documents`, `document_versions`, `document_sections` ✅ | ✅ `09 § 20` | `DOCUMENT_GENERATE` ✅ | generation ✅ | `12 § 20–22` ✅ | 11 types 🟠 **D-08** |
| R-54 Source selection + freeze | `/…/generate` ✅ | Source Data, Change source | ❌ freeze contract | Doc Generation ✅ | Doc Supervisor ✅ | — | ❌ **no generation_run; `requirements` has no `version`; `document_sources` has no `source_version`** | ✅ `09 § 7`, `§ 19` | `DOCUMENT_GENERATE` ✅ | 🔵 | 🔵 | all |
| R-55 Section contracts | — | — | — | Doc Generation ✅ | ✅ | — | `document_sections` ✅ | ✅ BRD 21 / SRS 25 ordered | — | — | `12 § 20` ✅ | BRD, SRS ✅ · others field-level only |
| R-56 Document validation | `/documents/{id}` ✅ | Validate | `POST /documents/{id}/validate` ✅ | Validation ✅ | Validation ✅ | `DOCUMENT_VALIDATION` ✅ / **uncapped loop** 🔵 | `validation_runs` ✅ | ✅ 9 checks | `DOCUMENT_READ` ✅ | validation ✅ | `12 § 20` ✅ | all |
| R-57 Preview + tabs | `/documents/{id}` ✅ | Preview / Sections / Sources / Traceability / Comments / History | `GET /documents/{id}` ✅ | Document ✅ | — | — | `document_sections`, `document_sources` ✅ | ✅ | `DOCUMENT_READ` ✅ | — | 🔵 | — |
| R-58 Tab applicability per type | `/documents/{id}` 🟠 | — | — | — | — | — | — | 🟠 **D-14** — `03 § 22` defers to `09`, which does not define it | — | — | ❌ | — |
| R-59 Pagination metadata | all lists + preview ✅ | pager | ❌ **no pagination contract in `07`** | — | — | — | — | ✅ `03 § 29` | — | — | `12 § 42.22–23` ✅ | — |
| R-60 Versioning | `/documents/{id}` ✅ | History | `GET /documents/{id}/versions`, `/{version}` ✅ | Document ✅ | — | — | `document_versions` ✅ / **`version` type/format ❌** | ✅ scheme | `DOCUMENT_READ` ✅ | 🔵 | `12 § 24`, `§ 42.14` ✅ | all |
| R-61 Revise | `/documents/{id}` ✅ | Revise | `POST /documents/{id}/revise` ✅ | Document ✅ | — | — | `document_versions` ✅ | ✅ `09 § 27` | `DOCUMENT_EDIT` ✅ | revision ✅ | `12 § 24` ✅ | all |
| R-62 Immutability | — | — | — | Document ✅ | — | — | ❌ **no enforcement mechanism** | ✅ semantics | — | ✅ | `12 § 5`, `§ 42.15` ✅ | all |
| R-63 PDF | `/documents/{id}` ✅ | Download | `GET /documents/{id}/pdf` ✅ | PDF ✅ | — | — | `document_versions.storage_key` ✅ | ✅ 10 features | `DOCUMENT_READ` ✅ | download ✅ | `12 § 25` ✅ | all |
| R-64 DOCX | `/documents/{id}` ✅ | Download | `GET /documents/{id}/docx` ✅ | ❌ **no DOCX service in `04`** | — | — | ✅ | ✅ `09 § 24` | `DOCUMENT_READ` ✅ | download ✅ | `12 § 26` ✅ | all |
| R-65 XLSX | `/…/rtm` ✅ | Export | ❌ **no endpoint** | ❌ **no service** | — | — | ✅ | 🟠 **D-15 workbook undefined** | `DOCUMENT_READ` ✅ | 🔵 | `12 § 27` ✅ | RTM, TEST_CASES |
| R-66 Generation failure + retry | `/documents/{id}` ✅ | Retry | 🟠 **`09 § 28`: retry endpoint DECISION REQUIRED** | Doc Generation ✅ | — | — | ✅ | ✅ safe msg + code + req id + retryability | `DOCUMENT_GENERATE` ✅ | 🔵 | `12 § 42.16` ✅ | — |
| R-67 Share document | canonical `brd-preview.png` | Share | ❌ | ❌ | — | — | ❌ | ❌ | ❌ | ❌ | ❌ | — |

### 4.7 Review, approval, traceability

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-68 Review | `/documents/{id}/review` ✅ | 4 tabs, Add Comment | `POST /documents/{id}/review` ✅ (one verb) | Document ✅ | — | `HUMAN_REVIEW` ✅ | ❌ **REVIEW, REVIEW_ASSIGNMENT, REVIEW_SECTION, REVIEW_COMMENT all missing** | ✅ `09 § 21` | `DOCUMENT_REVIEW` ✅ | review ✅ | `12 § 42.8` ✅ | — |
| R-69 Review assignment | `/…/review` ✅ | — | ❌ | Document | — | — | ❌ reviewer, role, assigned_by, due, priority | ✅ | `DOCUMENT_REVIEW` ✅ | 🔵 | `12 § 42.8` ✅ | — |
| R-70 Section-level review status | `/…/review` ✅ | per-section | ❌ | Document | — | — | ❌ | ✅ | ✅ | 🔵 | `12 § 42.9` ✅ | — |
| R-71 Review comments | `/…/review`, previews ✅ | Add Comment | ❌ | Document | — | — | ❌ | ✅ | ✅ | 🔵 | `12 § 42.10` ✅ | — |
| R-72 Approve | `/approvals/{id}` ✅ | Approve | `POST /documents/{id}/approve` ✅ | Document ✅ | — | `APPROVAL` 🔴 **unreachable** | `approvals` ✅ **single approver vs canonical 3-chain** 🟠 | ✅ | `DOCUMENT_APPROVE` ✅ | approval ✅ | `12 § 35`, `§ 42.6–7` ✅ | — |
| R-73 Reject | `/approvals/{id}` ✅ | Reject | ❌ | Document | — | `REJECT` action 🔴 **no target state** | `approvals.status` ✅ | 🔵 | `DOCUMENT_APPROVE` ✅ | rejection ✅ | 🔵 | — |
| R-74 Request Changes | `/approvals/{id}` ✅ | Request Changes | ❌ | Document | — | 🔴 **"appropriate previous state" is not a mapping** | ❌ | 🔵 | `DOCUMENT_APPROVE` ✅ | 🔵 | 🔵 | — |
| R-75 Approval chain progress | `/approvals/{id}` canonical | — | ❌ | Document | — | — | ❌ **no approval_steps** | 🟠 **D-04** | ✅ | ✅ | `12 § 35` ✅ | — |
| R-76 RTM view | `/projects/{id}/rtm` ✅ | Export, Filter | ❌ **no RTM endpoint** | Document ✅ | — | — | ❌ **TEST_CASE, TRACEABILITY_RELATIONSHIP, Design entity all missing** | ✅ `09 § 12` | `DOCUMENT_READ` ✅ | 🔵 | `12 § 23`, `§ 42.11–13` ✅ | RTM |
| R-77 Traceability chain | — | — | — | Validation ✅ | Validation ✅ | — | ❌ | 🔵 **chain length differs across `03`/`09`/`12`/`13`** | — | — | `12 § 23` ✅ | RTM |

### 4.8 Integrations, admin, reports, audit

| Req | Page | UI action | API | Service | Agent | State | Entity | Validation | Authz | Audit | Test | Doc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-78 List integrations | `/integrations` ✅ | View Status | `GET /integrations` ✅ | Integration ✅ | — | — | `integrations` ✅ | ✅ | `INTEGRATION_READ` ✅ | — | `12 § 28` ✅ | — |
| R-79 Connect ×3 | `/integrations` ✅ | Connect | 3 connect endpoints ✅ | Integration ✅ | — | — | `integrations` ✅ / **no encrypted credential fields** ❌ | ✅ | `INTEGRATION_MANAGE` ✅ | integration change ✅ | `12 § 28` ✅ | — |
| R-80 Disconnect | `/integrations` ✅ | Disconnect | `POST /integrations/{id}/disconnect` ✅ | Integration ✅ | — | — | ✅ | ✅ | `INTEGRATION_MANAGE` ✅ | ✅ | 🔵 | — |
| R-81 Test connection | `/integrations` ✅ `03 § 26` | Test Connection | ❌ **no endpoint** | Integration ✅ | — | — | ✅ | ❌ | `INTEGRATION_READ` ✅ | 🔵 | 🔵 | — |
| R-82 Slack / Teams / GitHub | `/integrations` canonical | Connect ×3 | ❌ | ❌ | — | — | ❌ | ❌ | ❌ | ❌ | ❌ | — |
| R-83 Jira write | — | — | `POST /tools/jira/issues` ✅ | Integration + Tool Registry ✅ | any | — | `tool_calls` ✅ | ✅ 6 preconditions `11 § 18` | ✅ | tool exec ✅ | `12 § 28–30` ✅ | — |
| R-84 Confluence / Notion read | — | — | 4 endpoints ✅ | Integration ✅ | any | — | `tool_calls` ✅ | ✅ authorized-only | ✅ | ✅ | `12 § 28` ✅ | — |
| R-85 Integration failure / retry | — | — | ❌ | Integration ✅ | — | — | ❌ | 🔵 | — | 🔵 | 🔵 | — |
| R-86 Admin metrics | `/admin` ✅ | — | ❌ **no metrics endpoint** | ❌ | — | — | ❌ | ❌ | `ADMIN_USERS` ✅ | admin ✅ | 🔵 | — |
| R-87 Admin: users, models, templates, agents, tools | `/admin` ✅ `03 § 28` | — | ❌ **zero admin endpoints** | ❌ | — | — | ❌ **no model_config, no templates** | ❌ | `ADMIN_*` ✅ | admin ✅ | 🔵 | — |
| R-88 Quota | `/admin` canonical | — | ❌ | ❌ | — | — | ❌ | 🟠 **D-10** | ✅ | — | ❌ | — |
| R-89 Reports | `/reports` ✅ | — | ❌ | ❌ | — | — | ❌ | 🔴 **`03 § 27` = BLOCKED** | ❌ | ❌ | ❌ | — |
| R-90 Notifications | ❌ no page | — | ❌ | ❌ | — | — | `notifications` ✅ **orphan** | ❌ | ❌ | ❌ | ❌ | — |
| R-91 Audit trail | `/admin` ✅ | — | `GET /audit`, `/audit/{id}` ✅ | Audit ✅ | — | — | `audit_events` ✅ | ✅ 7 fields | `AUDIT_READ` ✅ | — | `12 § 32` ✅ | — |
| R-92 Audit event catalogue | — | — | — | Audit ✅ | — | — | `audit_events.event_type` ✅ | ❌ **MC-01 — no event names anywhere** | — | — | `12 § 32` ✅ | — |

**Matrix totals — 92 requirements traced:**

| Outcome | Count |
| --- | --- |
| Complete end-to-end chain, implementable today | **24** |
| Blocked by a missing API endpoint | 31 |
| Blocked by a missing database entity or column | 34 |
| Blocked by an open decision | 24 |
| UI action with **no backend contract at all** → **BLOCKED** per instruction | **35** |

---

## 5. PHASE READINESS

Gate per phase (CLAUDE.md § COMPLETION RULE): Frontend + API + Backend + Database +
Authorization + Validation + Error handling + Tests.

| # | Phase | Status | Blocking items |
| --- | --- | --- | --- |
| 0 | Pre-implementation | 🟢 **READY** | none |
| 1 | Foundation | 🟢 **READY** | none (sidebar shell excepted — D-18) |
| 2 | Authentication | 🔵 | `sessions`, `refresh_tokens`, `password_reset_tokens` · D-21 consent · SSO · D-13 rate limits |
| 3 | Multi-tenancy | 🔴 | **D-01 isolation strategy** |
| 4 | Projects | 🔵 after 3 | activity feed · doc-count aggregate |
| 5 | Chat | 🔵 | **D-17 transport** · D-16 · retry/regenerate API · View Risks API · project-chat API |
| 6 | Files | 🔵 | quarantine enum · scanner · embeddings · `03 § 11` vs `07` path conflict |
| 7 | Workflow engine | 🔴 | **D-02** · **6 state-machine defects** · **D-03 PARTIAL** · **D-05 retry** |
| 8–10 | Supervisor / Agents / Validation | 🔵 ⬆ *(was 🔴)* | ✅ contracts exist · **D-06 risk scoring** · `agent_runs` 6 missing fields · no policy entity |
| 11 | Human review | 🔴 | 4 entities + every endpoint missing |
| 12 | Approval | 🔴 | **D-04** · `APPROVAL` unreachable · reject / request-changes APIs |
| 13 | Tool Registry | 🔴 | no registry table · no tool catalog · **D-22** |
| 14–16 | Jira / Confluence / Notion | 🔵 | credential encryption fields · test-connection API · sandboxes |
| 17–27 | Documents | 🔴 | ✅ sections, versioning, provenance · no `generation_run` · no `source_version` · **D-08** · XLSX · **D-14** |
| 28 | Versioning | 🔵 | ✅ scheme · enforcement mechanism + column type |
| 29 | Traceability | 🔴 | TEST_CASE · TRACEABILITY_RELATIONSHIP · Design entity · **D-19** |
| 30 | Audit | 🔵 | ✅ fields + categories · **MC-01/D-23 event names** · **D-11 retention** |
| 31 | Observability | 🔵 | no spec section · **D-10 quota** · **D-12 RPO/RTO** |
| 32 | Security hardening | 🔵 ⬆ *(was 🔴)* | ✅ model, permissions, injection defence · D-01, D-07, D-13 |
| 33 | E2E | 🔵 | ✅ journey `12 § 36` · **D-24 framework** |

**Movement since revision 2:** phases 8–10 and 32 moved 🔴 → 🔵 — the agent and security
designs now exist. Phases 3, 7, 11, 12, 13, 17–27, 29 remain 🔴 for **structural** reasons
(schema and state-machine gaps), not missing documents.

---

## 6. DECISIONS REQUIRED

`12 § 44` lists 16. All 16 appear below, plus 8 that this cross-check surfaced (D-17…D-24).
**None has been decided here.**

### D-01 · Tenant isolation strategy
**Question:** application-level filtering, PostgreSQL Row Level Security, or schema-per-tenant?
**Why it matters:** determines the shape of every table and query. 17 tables have no
`tenant_id`. `11 § 3` permits transitive scoping through a tenant-scoped parent, but RLS and
schema-per-tenant impose requirements app filtering does not. Retrofitting after the first
migration means rewriting every query and backfilling every row.
**Affected files:** `06`, `07`, `11 § 3`; every future model and repository.
**Affected implementation phases:** 3, and transitively 4–33.

### D-02 · Fixed vs configurable workflows
**Question:** is the 18-state machine in `05` fixed, or may tenants author definitions?
**Why it matters:** a state machine and an interpreter are different systems. **The specs
already disagree about whether this is open:** `01 § PRIMARY CAPABILITIES` lists "configurable"
as a shipped capability, `06 workflow_definitions` stores a `definition` blob, `07` exposes
`POST /workflows`, and `workflow.png` shows 5 independently-versioned templates plus
New Workflow — while `03 § 13` and `12 § 44` both call it undecided.
**Affected files:** `01`, `03 § 13`, `05`, `06`, `07`, `12 § 44`.
**Affected implementation phases:** 7, 8–10, 30.

### D-03 · PARTIAL data-availability behaviour
**Question:** on `PARTIAL`, does the workflow continue, wait for input, or branch on policy?
**Why it matters:** `08 § 9`, `03 § 16` and `12 § 18` all define the tri-state, and both
`03 § 16` and `08 § 9` forbid silently treating it as AVAILABLE or MISSING — yet
`05 § DATA CHECK` has only two branches, so `PARTIAL` has **no target state**. The workflow
cannot be built. `12 § 42.5` gates on this.
**Affected files:** `03 § 16`, `05 § DATA CHECK`, `08 § 9`, `12 § 18`.
**Affected implementation phases:** 7, 9.

### D-04 · Approval model
**Question:** single approver, sequential chain, or staged pipeline?
**Why it matters:** canonical `approval.png` shows an ordered 3-approver chain with a 1/3
progress donut; `06 approvals` has one `approved_by`. `12 § 35` requires concurrent-approval
tests and `12 § 42.7` requires every approval action to map to a persisted entity.
**Affected files:** `03 § 24`, `06 approvals`, `07`, `09 § 22`, `docs/ui/approval.png`.
**Affected implementation phases:** 11, 12.

### D-05 · Retry policy
**Question:** max attempts per agent and per step, retryability classification, backoff?
**Why it matters:** `08 § 15` says the limit must come from policy configuration; `05` routes
to `RETRY`, which is not one of its 18 states; `12 § 11-G` defers to "configured policy".
`07` already exposes `POST /workflow-runs/{id}/retry` with no defined semantics, and
`12 § 42.16` requires every retry button to have a real backend operation.
**Affected files:** `05 § VALIDATION`, `05 § FAILURE`, `08 § 15`, `12 § 11-G`.
**Affected implementation phases:** 7, 9, 10.

### D-06 · Risk scoring policy
**Question:** likelihood and severity scales, score formula, and thresholds?
**Why it matters:** `08 § 8` states it plainly — *"If no risk policy exists: BLOCKED /
DECISION REQUIRED. Do not invent scoring rules."* `13 § CONDITIONAL` makes approval
conditional on a risk threshold, so that workflow branch cannot be evaluated at all.
**Affected files:** `03 § 17`, `06 risks`, `08 § 8`, `09 § 15`, `13`.
**Affected implementation phases:** 7, 9, 24.

### D-07 · Role assignment model
**Question:** which roles exist, who assigns them, at what scope, through which UI and API?
**Why it matters:** `11 § 5` names 21 permissions — but labels them *"Example permissions"*,
so even the catalog is illustrative. `11 § 6` says role assignment is undefined.
`12 § 7` requires wrong-role tests and `12 § 42.21` requires a defined backend contract. The
canonical admin screen shows no role-management interaction, so there is currently no way a
role is ever assigned.
**Affected files:** `03 § 28`, `06 roles` / `role_permissions`, `07`, `11 § 6`.
**Affected implementation phases:** 2, 3, 32.

### D-08 · Document type set
**Question:** which of the 11 types ship, and does the generator expose all of them?
**Why it matters:** five sources disagree. `09 § 2` and `03 § 21` list **11**; canonical
`document-generator.png` shows **6** tiles (no NFRD, TEST_CASES, SECURITY, COMPLIANCE,
TECHNICAL); `documents.png` lists **8**; `04 § Document Generation Service` names **7**;
`13 § DOCUMENTS` explicitly requires generating NFRD, security and compliance documents.
**`03` also contradicts itself** — § 2 says the canonical reference takes precedence and
*"Do not reintroduce elements removed from the canonical reference"*, while § 21 lists all 11.
**Affected files:** `01`, `03 § 2` vs `§ 21`, `04`, `09 § 2`, `13`, `docs/ui/`.
**Affected implementation phases:** 17–27.

### D-09 · Identifier formats
**Question:** format for document, review, approval, workflow-run, generation-run,
requirement, risk and test-case keys?
**Why it matters:** `09 § 6` requires backend-generated IDs and explicitly forbids hard-coding
`#REV-2026-001`. Canonical screens show `#WF-2026-001`, `#REV-2026-001`, `#APP-2026-001`,
`BR-001`, `FR-001`, `TC-001`; `09 § 7` shows `DOC-001` and `GEN-001`. No column or format rule
exists for any of them.
**Affected files:** `06` (all `*_key` columns), `09 § 6–7`, `docs/ui/`.
**Affected implementation phases:** 7, 11, 12, 17–27, 29.

### D-10 · Quota model
**Question:** what is quota-limited, at what scope, and what happens at the limit?
**Why it matters:** `admin.png` shows Storage 245 GB / 1 TB and API Usage 12,430 / 100,000.
No entity, counter, or enforcement point exists anywhere. Rendering these as live numbers
without a backing counter would violate CLAUDE.md § 1.
**Affected files:** `03 § 28`, `06`, `07`.
**Affected implementation phases:** 31.

### D-11 · Retention period
**Question:** retention durations for documents, audit records, files, and deleted resources?
**Why it matters:** `11 § 22` requires retention be configurable and defers the durations.
Audit retention interacts with immutability and with the compliance obligations this platform
is built to analyse.
**Affected files:** `11 § 22`, `06 audit_events`, `06 documents`.
**Affected implementation phases:** 30.

### D-12 · RPO / RTO
**Question:** recovery point objective, recovery time objective, backup frequency, recovery
procedure, recovery validation?
**Why it matters:** `11 § 24` defers the values. `09 § 11` requires the NFRD to document
disaster recovery and backup — that document cannot be generated truthfully without them, and
`09 § 19` would force every such section to `UNVERIFIED`.
**Affected files:** `09 § 11`, `11 § 23–24`.
**Affected implementation phases:** 31, 22.

### D-13 · Rate limits
**Question:** limits for login, password reset, uploads, AI generation, document generation,
integrations, admin operations?
**Why it matters:** `11 § 12` names the operations and defers the numbers with *"Do not invent
production numbers."* `12 § 31` requires API-abuse tests and `11 § 25` requires rate-limiting
tests — neither can assert anything without the values.
**Affected files:** `11 § 12`, `07`.
**Affected implementation phases:** 2, 32.

### D-14 · Document tab applicability
**Question:** which preview tabs apply to each of the 11 document types?
**Why it matters:** `03 § 22` says BRD "may" show Sources and SRS "may" show Traceability,
then defers to "document type specification" — but `09` defines no tab applicability for any
type. The reference is circular, and the two canonical previews are only two samples.
**Affected files:** `03 § 22`, `09`, `docs/ui/brd-preview.png`, `docs/ui/srs-preview.png`.
**Affected implementation phases:** 17–27.

### D-15 · XLSX workbook structure
**Question:** sheets, columns, and ordering for RTM and test-case matrices?
**Why it matters:** `09 § 25` requires the contract be defined **before** implementation;
`12 § 27` tests columns and filters; `rtm.png` has an Export button; `07` has no XLSX
endpoint and `04` has no XLSX service.
**Affected files:** `04`, `07`, `09 § 25`.
**Affected implementation phases:** 26, 29.

### D-16 · Canonical chat action set
**Question:** are the 8 `+`-menu actions and voice input product requirements, or dropped?
**Why it matters:** `02 § CHAT INPUT` mandates both; canonical `chat.png` shows neither.
`03 § 9` resolves it **for implementation** — *"Do not implement those actions unless the
canonical UI specification is explicitly updated"* — but `12 § 44` still lists it as open and
`02` has not been amended. The build direction is clear; the product question is not, and
`02` still contradicts `03`.
**Affected files:** `02 § CHAT INPUT`, `03 § 9`, `12 § 44`.
**Affected implementation phases:** 5.

### D-17 · Realtime transport
**Question:** SSE or WebSockets — and for which streams?
**Why it matters:** `CLAUDE.md § TECHNOLOGY` says "SSE or WebSockets"; `04` says
"SSE/WebSocket"; `02 § REALTIME` requires streaming for chat, workflow status **and** document
generation — but `07` has a stream endpoint for chat only, and
`GET /workflow-runs/{id}/events` states no transport. Not listed in `12 § 44`.
**Affected files:** `CLAUDE.md`, `02 § REALTIME`, `04`, `07`.
**Affected implementation phases:** 5, 7, 17.

### D-18 · Navigation model
**Question:** which sidebar is authoritative, and are Documents / Requirements / Risks /
Workflows global or project-scoped?
**Why it matters:** **`03 § 3`'s sidebar does not match the canonical UI.** `03 § 3` lists
Dashboard, Projects, Requirements, Workflows, Documents, Risks, Security, Compliance, Reports;
all 13 authenticated canonical screens show New Chat, Projects, Documents, Workflows,
Requirements, Risks, Reports, Integrations, Admin. `03 § 3` adds three items the canonical UI
does not have and omits three it does — while `03 § 2` says canonical takes precedence and
`03 § 26`/`§ 28` define `/integrations` and `/admin` as real routes. `03` contradicts itself.
Separately, the canonical items are global while `03`'s routes are project-scoped
(`/projects/{id}/requirements`), so **every sidebar link currently has an undefined target.**
**Affected files:** `03 § 2` vs `§ 3`, `03 § 12`, `§ 17–20`, `§ 25`, all 13 authenticated PNGs.
**Affected implementation phases:** 1, and every page phase 4–29.

### D-19 · RTM column set and canonical traceability chain
**Question:** which columns does the RTM render, and what is the authoritative chain?
**Why it matters:** four different chains are specified — `13 § TRACEABILITY`: BR → FR / SRS /
Design / Test / Risk (5 links); `12 § 23`: Requirement → FR → SRS → Design → Test → Risk (6);
`09 § 12`: the same plus Evidence (7); `03 § 25`: 9 display columns. Canonical `rtm.png` shows
**6 columns** with no SRS, Design, Risk or Evidence column at all. `12 § 42.11–13` requires
every displayed mapping to reference a real stored record, so the column set determines which
entities must exist.
**Affected files:** `03 § 25`, `09 § 12`, `12 § 23`, `13 § TRACEABILITY`, `docs/ui/rtm.png`.
**Affected implementation phases:** 29, 26.

### D-20 · Document status model
**Question:** is document status one field or three — status, validation_status,
approval_status?
**Why it matters:** `03 § 20` requires displaying all three; `06 documents` has a single
`status`; `09 § 4` defines 9 states that mix lifecycle, validation and approval concerns
(`VALIDATING`, `REVIEW`, `APPROVED`, `REJECTED`). Canonical badges read "Pending Approval"
(`approval.png`) and "In Review" (`review.png`), **neither of which is in `09 § 4`**.
**Affected files:** `03 § 20`, `06 documents`, `09 § 4`, `docs/ui/`.
**Affected implementation phases:** 11, 12, 17–27.

### D-21 · Consent storage contract
**Question:** which consent types, policy versions and timestamps are persisted — and is a
pre-checked box acceptable?
**Why it matters:** `03 § 6` requires consent type, version, timestamp, user and policy
version, and states *"Do not implement a checkbox without persistence."* Canonical
`register.png` shows the box **pre-checked**, which is itself a compliance question for a
platform whose purpose includes compliance analysis. No entity or endpoint exists. Not listed
in `12 § 44`.
**Affected files:** `03 § 6`, `06`, `07`.
**Affected implementation phases:** 2.

### D-22 · Blocked-tool-request audit contract
**Question:** how is a *rejected* tool request recorded, and with what status values?
**Why it matters:** `11 § 15` requires audit to record *"any attempted tool request where
applicable"* — that record **is** the evidence the required prompt-injection test asserts on.
`06 tool_calls` has a `status` column with **no defined enum**, and no spec distinguishes
denied-by-permission from denied-by-policy from denied-by-unknown-tool. Without it, `12 § 30`
can prove the absence of a Jira write but not the presence of a containment record.
**Affected files:** `06 tool_calls`, `11 § 15–17`, `12 §§ 29–30`.
**Affected implementation phases:** 13, 32.

### D-23 · Audit event catalogue (MC-01)
**Question:** what are the audit event names?
**Why it matters:** `03 § 31` gives 14 categories, `11 § 21` gives 13 plus the 7 required
fields, `12 § 32` tests per-action — but **no spec names a single event.** Every requirement in
§ 4 with an audit obligation is blocked on this one list. Not in `12 § 44`.
**Affected files:** `03 § 31`, `06 audit_events.event_type`, `11 § 21`.
**Affected implementation phases:** 2 onward (cross-cutting).

### D-24 · Test framework and coverage policy
**Question:** which frameworks, what coverage thresholds, and which integration sandboxes?
**Why it matters:** `12` defines 10 test levels and a 7-check CI gate (§ 37) but names no
framework or threshold. `12 § 28` requires live Jira / Confluence / Notion tests, which need
sandbox tenants and credentials — and `12 § 39` forbids production credentials. Not in `§ 44`.
**Affected files:** `12 § 2`, `§ 28`, `§ 37`, `§ 39`.
**Affected implementation phases:** 0, 33.

---

## 7. WHAT IS BUILDABLE WITHOUT ANY DECISION

**Phase 0** — `git init` + `.gitignore` · monorepo layout · `.env.example` with keys and no
values · toolchain pinning · docker-compose (PostgreSQL, Redis, object storage) · CI wired to
exactly `12 § 37`'s seven gates.

**Phase 1** — FastAPI app factory · Pydantic settings · SQLAlchemy engine and session ·
Alembic baseline with **no tables** (D-01 blocks the first migration) · structured logging
carrying `request_id` · the `07` / `03 § 30` error envelope as one shared exception handler ·
health endpoint · Next.js + Tailwind with tokens sampled from the canonical screens ·
TanStack Query · React Hook Form + Zod · the six `03 § 4` page states as primitives ·
glass-card / button / input primitives per `02 § COMPONENT STYLE`.

**Explicitly not buildable yet:** the application shell's sidebar — D-18 leaves both its item
set and its link targets undefined.

Companion analysis: [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) ·
[DEPENDENCY_MAP.md](DEPENDENCY_MAP.md).

**No application code, migration, API, or component has been created.**
