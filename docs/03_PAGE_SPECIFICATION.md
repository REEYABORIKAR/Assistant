# 03 PAGE SPECIFICATION

**Revision:** 2 (2026-08-26) — FINAL ARCHITECTURE RESOLUTION PASS

Revision 1 is preserved in full. This revision resolves **D-18** (§ 3), adds the three global pages
the canonical sidebar requires (§§ 12.1, 17.1, 20.1), and adds the complete UI-action → backend map
(§ 33) and the blocked-control register (§ 34).

## 1. PURPOSE

This document defines the functional contract for every application page.

The page specification defines:

- route
- purpose
- access
- UI components
- backend actions
- API dependencies
- validation
- loading state
- empty state
- error state
- permission state
- success state
- navigation
- audit requirements

The frontend is never the source of truth for:

- authentication
- authorization
- workflow state
- document status
- approval status
- validation status
- integration status

---

# 2. CANONICAL UI

The canonical UI reference is the higher-fidelity UI reference contained in:

docs/ui/

Product:

REFYNE — AI Requirement Assistant

The canonical reference takes precedence over older conflicting UI references.

The implementation must follow the canonical screenshots for:

- layout
- navigation
- spacing
- visual hierarchy
- page structure
- components
- terminology

Do not reintroduce elements removed from the canonical reference.

---

# 3. GLOBAL APPLICATION STRUCTURE

## 3.1 ✅ D-18 RESOLVED — the canonical sidebar is authoritative

Revision 1 listed a nine-item sidebar that **contradicted the canonical UI**. The canonical
reference `chat.png` shows a different nine items. § 2 of this same document settles which wins:
*"The canonical reference takes precedence over older conflicting UI references"* and *"Do not
reintroduce elements removed from the canonical reference."*

| Revision 1 § 3 | `chat.png` | Ruling |
| --- | --- | --- |
| Dashboard | — | **Removed.** No route, purpose, component list or API is defined for it anywhere in this document. `chat.png` is itself the authenticated landing surface |
| Projects | Projects | Kept |
| Requirements | Requirements | Kept — now global (§ 12.1) |
| Workflows | Workflows | Kept |
| Documents | Documents | Kept — now global (§ 20.1) |
| Risks | Risks | Kept — now global (§ 17.1) |
| Security | — | **Removed from the sidebar.** The page remains at its project-scoped route (§ 18) |
| Compliance | — | **Removed from the sidebar.** The page remains at its project-scoped route (§ 19) |
| Reports | Reports | Kept — `BLOCKED` (§ 27) |
| — | **New Chat** | **Added** — the primary action in `chat.png` |
| — | **Integrations** | **Added** — § 26 defines the page |
| — | **Admin** | **Added** — § 28 defines the page |

**Revision 1's list was not merely different — it was defective.** It omitted Integrations and
Admin, both of which have fully specified routes in this document (§§ 26, 28), leaving two complete
pages with **no navigation path to them**. It also listed Dashboard, which has no page contract at
all. The canonical set fixes both.

**Removing Security and Compliance orphans nothing.** Both are project-scoped (`/projects/{id}/security`,
`/projects/{id}/compliance`) and are reachable from the project page, which lists *security* and
*compliance* among its components (§ 8).

## 3.2 The authoritative sidebar

Nine items. **All nine are global scope** — the sidebar is rendered outside any project context, so
no item may depend on a `project_id`.

| # | Label | Route | Scope | Permission | Page | Primary API |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | New Chat | action → `/chat/{conversation_id}` | Global | 🔒 `CONVERSATION_WRITE` | § 9 | `POST /conversations` |
| 2 | Projects | `/projects` | Global | `PROJECT_READ` | § 7 | `GET /projects` |
| 3 | Documents | `/documents` | Global | `DOCUMENT_READ` | § 20.1 | `GET /documents` |
| 4 | Workflows | `/workflows` | Global | 🔒 `WORKFLOW_READ` | § 13 | `GET /workflows` |
| 5 | Requirements | `/requirements` | Global | 🔒 `REQUIREMENT_READ` | § 12.1 | `GET /requirements` |
| 6 | Risks | `/risks` | Global | 🔒 `RISK_READ` | § 17.1 | `GET /risks` |
| 7 | Reports | `/reports` | Global | 🔒 `REPORT_READ` | § 27 | **none — BLOCKED** |
| 8 | Integrations | `/integrations` | Global | `INTEGRATION_READ` | § 26 | `GET /integrations` |
| 9 | Admin | `/admin` | Global | `ADMIN_USERS` ∨ `ADMIN_ROLES` ∨ `ADMIN_WORKFLOWS` ∨ `ADMIN_TOOLS` | § 28 | `GET /admin/users` |

🔒 marks a permission not present in `11 § 5`'s list — 🔵 **MC-02**. Five of the nine items are
gated on it.

**Visibility is a backend decision.** `GET /auth/me` returns the caller's effective permissions and
the sidebar hides items the caller cannot use. This is **affordance only** — hiding an item is not a
security control; the route and its endpoints deny independently (`11 § 27`). A hidden item that is
navigated to directly renders `PERMISSION_DENIED` (§ 4), not a blank page.

**Reports** is rendered as a visible, disabled item with an explanatory empty state. It is in the
canonical UI, so removing it would violate § 2; it has no contract, so linking it to a working page
would require inventing report functionality. A disabled item with a stated reason is the only
honest rendering.

## 3.3 Global versus project scope

Four sidebar destinations exist at **both** scopes. This is deliberate, not duplication:

| Global | Project-scoped | Relationship |
| --- | --- | --- |
| `/documents` | `/projects/{id}/documents` (§ 20) | Same page component, different filter. Global is `documents.png` — *"Manage all project documents"* |
| `/requirements` | `/projects/{id}/requirements` (§ 12) | Same |
| `/risks` | `/projects/{id}/risks` (§ 17) | Same |
| `/workflows` | run from `/projects/{id}` (§ 8) | Definitions are tenant-level; runs are project-level |

A global list returns rows across every project the caller may read — **tenant-wide, not
authorization-wide.** A project the caller cannot read contributes nothing, and its absence is not
disclosed (`07 § 1.2`).

**Creation always requires a project.** No global page may create a requirement, risk or document,
because every one of those entities is project-owned. The global pages are read-and-navigate.

---

# 4. GLOBAL PAGE STATES

Every page must support:

LOADING

EMPTY

SUCCESS

ERROR

PERMISSION_DENIED

NOT_FOUND

Every mutation must provide:

- loading state
- success state
- error state
- retry where retry is permitted

## 4.1 State derivation — ADDED

| State | Trigger |
| --- | --- |
| LOADING | Request in flight |
| EMPTY | `200` with `total = 0` — **not** an error, and never a fabricated sample row |
| SUCCESS | `200`/`201`/`202` |
| ERROR | `4xx`/`5xx`, rendering `error.message` and `request_id` (§ 30) |
| PERMISSION_DENIED | `403` |
| NOT_FOUND | `404` — same tenant, absent resource. A **cross-tenant** resource returns `403`, so it renders PERMISSION_DENIED, never NOT_FOUND (`11 § 3.1`) |

*Retry where retry is permitted* — the backend returns `retryable`; the frontend never infers it
(§ 15, § 32).

---

# 5. AUTHENTICATION

## Route

/login

## Purpose

Authenticate an existing user.

## Components

- email
- password
- login
- forgot password
- register

## Action

POST /api/v1/auth/login

## Success

Create authenticated session.

Load:

- user
- tenant membership
- permissions

Navigate to authorized application landing page.

## Failure

Return safe authentication error.

Do not disclose whether a specific email exists.

## 5.1 Landing page — ADDED

*"Authorized application landing page"* resolves to **`/chat`** — `chat.png` is the canonical
authenticated surface and `CLAUDE.md § UI RULES` requires the primary experience feel like ChatGPT.
If the caller lacks `CONVERSATION_READ`, the landing page is the first sidebar item they can access,
evaluated in § 3.2 order.

*"Do not disclose whether a specific email exists"* extends to the audit log: `USER_LOGIN_FAILED`
records the submitted address but not whether the account exists (`11 § 21.2`).

---

# 6. REGISTER

## Route

/register

## Fields

- name
- email
- password
- confirm password
- consent

## Validation

- required fields
- valid email
- password policy
- password confirmation
- consent

Consent storage contract:

DECISION REQUIRED

The backend must define:

- consent type
- version
- timestamp
- user
- policy version

Do not implement a checkbox without persistence.

## Action

POST /api/v1/auth/register

## 6.1 🟠 D-20 — what is and is not blocked — ADDED

**Storage exists.** `consents` holds `user_id`, `consent_type`, `policy_version`, `granted_at`,
`ip_address`, `user_agent` — the five required fields plus provenance.

**Undecided:** which consent types exist, what document each points at, and its version identifier.
No file names a terms-of-service or privacy-policy document. `07 § 4` marks `POST /auth/register`
🟠 for this reason.

*"Do not implement a checkbox without persistence"* is honoured by refusing to render the checkbox
until the type registry exists — a checkbox whose value is written against an unknown policy version
records a consent nobody can later interpret.

**Password policy** is 🟠 **D-28**: `11 § 4` requires hashing but states no complexity, length or
rotation rule. Validation is server-side either way (§ 32).

---

# 7. PROJECT LIST

## Route

/projects

## Components

- project list
- search
- filters
- create project

## Actions

GET /api/v1/projects

POST /api/v1/projects

## Authorization

Project visibility is determined by backend authorization.

## 7.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| List | `GET /projects` | `PROJECT_READ` | — |
| Search (`q`) | `GET /projects?q=` | `PROJECT_READ` | — |
| Filters (`status`) | `GET /projects?status=` | `PROJECT_READ` | — |
| Create project | `POST /projects` | `PROJECT_WRITE` | `PROJECT_CREATED` |

Search and filtering are **server-side**. Client-side filtering of a paginated response would filter
one page and appear to lose rows.

`project.png`'s counts are backend values, not computed in the browser (§ 29, § 32).

---

# 8. PROJECT

## Route

/projects/{project_id}

## Components

- project information
- requirements
- risks
- security
- compliance
- workflows
- documents
- activity

## Actions

Open requirements

Open workflows

Open documents

Open risks

Open security

Open compliance

Run workflow

## 8.1 Control map — ADDED

| Control | Destination / API | Permission |
| --- | --- | --- |
| Project information | `GET /projects/{id}` | `PROJECT_READ` |
| Open requirements | `/projects/{id}/requirements` | 🔒 `REQUIREMENT_READ` |
| Open risks | `/projects/{id}/risks` | 🔒 `RISK_READ` |
| Open security | `/projects/{id}/security` | 🔒 `SECURITY_READ` |
| Open compliance | `/projects/{id}/compliance` | 🔒 `COMPLIANCE_READ` |
| Open workflows | `/projects/{id}/workflow-runs` | 🔒 `WORKFLOW_READ` |
| Open documents | `/projects/{id}/documents` | `DOCUMENT_READ` |
| Activity | `GET /projects/{id}/activity` | `AUDIT_READ` |
| **Run workflow** | `POST /workflows/{workflow_definition_id}/runs` | `WORKFLOW_RUN` |

**This page is the only navigation path to Security and Compliance** once they leave the sidebar
(§ 3.1). Both tabs must therefore be present here.

*Activity* is a project-filtered audit read. It requires `AUDIT_READ`; a caller without it sees the
tab hidden and the endpoint denies.

---

# 9. CHAT

## Route

/chat

## Purpose

General AI workspace.

## Components

- conversation list
- message history
- composer
- attachment
- send
- new conversation

Canonical UI does not display the previously proposed eight-action plus menu or voice action.

Therefore:

Do not implement those actions unless the canonical UI specification is explicitly updated.

## APIs

POST /api/v1/conversations

POST /api/v1/conversations/{id}/messages

GET /api/v1/conversations/{id}

GET /api/v1/conversations

PATCH /api/v1/conversations/{id}

DELETE /api/v1/conversations/{id}

## 9.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Conversation list | `GET /conversations` | 🔒 `CONVERSATION_READ` | — |
| Open conversation | `GET /conversations/{id}` | 🔒 `CONVERSATION_READ` | — |
| New conversation | `POST /conversations` | 🔒 `CONVERSATION_WRITE` | `CONVERSATION_CREATED` |
| Rename | `PATCH /conversations/{id}` | 🔒 `CONVERSATION_WRITE` | `CONVERSATION_UPDATED` |
| Delete | `DELETE /conversations/{id}` | 🔒 `CONVERSATION_DELETE` | `CONVERSATION_DELETED` |
| Composer → Send | `POST /conversations/{id}/messages` | 🔒 `CONVERSATION_WRITE` | `MESSAGE_SENT` |
| Streaming response | `GET /conversations/{id}/stream` (SSE) | 🔒 `CONVERSATION_READ` | — |
| Attachment | `POST /files` then reference | `FILE_UPLOAD` | `FILE_UPLOADED` |
| **Regenerate** | `POST /conversations/{id}/messages/{message_id}/regenerate` | 🔒 `CONVERSATION_WRITE` | `MESSAGE_REGENERATED` |

**Regenerate is required.** `13 § CHAT` lists *"regenerate response"* as an acceptance criterion, and
revision 1 had no control or endpoint for it. Regeneration **supersedes** the prior assistant
message rather than deleting it — the original stays retrievable, because a message that fed a
workflow run must remain auditable.

🔵 **Stop generation** — `13 § CHAT` requires streaming but nothing specifies cancellation: no
control in the canonical UI, no endpoint, no defined state for a half-generated message. `07 § 27`
records it as blocked. **A stop button must not be rendered**, since closing the SSE connection
client-side would leave the server generating and the message row in an undefined state.

The eight-action plus menu and voice action remain excluded, per revision 1.

---

# 10. PROJECT CHAT

## Route

/projects/{project_id}/chat

## Context

Only authorized:

- project data
- project documents
- project requirements
- project integrations
- project conversation data

Cross-tenant and unauthorized project data must never enter context.

## 10.1 Contract — ADDED

Same components and endpoints as § 9, with `project_id` bound at conversation creation and
immutable thereafter. A conversation cannot be moved between projects — its assembled context would
retroactively change.

The five permitted context sources map to `08 § 12`'s buckets: `PROJECT_DATA`,
`AUTHORIZED_DOCUMENT_DATA`, `AUTHORIZED_INTEGRATION_DATA`, `USER_INPUT`. Retrieved file content
enters as `UNTRUSTED_EXTERNAL_CONTENT` and cannot instruct the model (`11 § 14.1`).

*"Cross-tenant and unauthorized project data must never enter context"* is enforced at assembly
time by re-checking the caller's authorization on every candidate source — not by filtering the
model's output, which would be too late.

🔵 **Retrieval strategy** — no file specifies whether context assembly uses embeddings, keyword
search, or whole-document inclusion, nor any chunk budget. `07 § 27` records it. The permission
boundary above holds under every strategy, so this blocks relevance quality, not security.

---

# 11. FILE UPLOAD

## Action

POST /api/v1/files

## Flow

Upload
↓
Authentication
↓
Authorization
↓
Filename validation
↓
MIME/type validation
↓
Size validation
↓
Security scanning
↓
Storage
↓
Metadata persistence
↓
Extraction
↓
Processing
↓
READY / FAILED / QUARANTINED

The frontend must display the actual backend status.

No fabricated processing percentage.

## 11.1 ✅ Path conflict resolved — ADDED

**`POST /api/v1/files` is authoritative.** `07` revision 1 also defined `POST /files/upload`; that
path is **superseded**. This section owns the twelve-stage flow and names the unsuffixed path, and
`/files/upload` was the only verb-suffixed path in the entire API.

## 11.2 Control map

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Upload | `POST /files` | `FILE_UPLOAD` | `FILE_UPLOADED` |
| List | `GET /projects/{id}/files` | `FILE_READ` | — |
| Status poll | `GET /files/{id}` | `FILE_READ` | — |
| Download | `GET /files/{id}/download` → `302` signed URL | `FILE_READ` | `FILE_DOWNLOADED` |
| Delete | `DELETE /files/{id}` | `FILE_DELETE` | `FILE_DELETED` |

`GET /projects/{id}/files` is new — revision 1 had upload without a corresponding list, so an
uploaded file could not be found again.

**Status, not percentage.** The UI displays `files.status` verbatim. There is no progress percentage
because extraction produces no monotonic progress signal — a fabricated one would violate
`CLAUDE.md § 1`. Upload byte progress is a genuine browser measurement and may be shown for the
transfer itself only.

A `QUARANTINED` file is never downloadable and never enters context (`11 § 8.1`). 🟠 **D-26** — no
MIME allow-list or size ceiling is specified, so *MIME/type validation* and *size validation* have
no thresholds to enforce.

---

# 12. REQUIREMENTS

## Route

/projects/{project_id}/requirements

## Components

- requirement list
- requirement ID
- title
- description
- type
- source
- status
- confidence
- traceability

## Actions

Create

Edit

View

Search

Filter

## APIs

GET /api/v1/projects/{project_id}/requirements

POST /api/v1/projects/{project_id}/requirements

PATCH /api/v1/requirements/{requirement_id}

## 12.1 Global requirements page — ADDED

| Property | Value |
| --- | --- |
| Route | `/requirements` |
| Scope | Global (tenant-wide) |
| Purpose | The canonical sidebar's Requirements destination (§ 3.2) |
| Components | As above, plus a **Project** column and a project filter |
| API | `GET /requirements` — new (`07 § 11`) |
| Permission | 🔒 `REQUIREMENT_READ` |
| Create | **Not available.** A requirement is project-owned; creation happens on the project-scoped page |

## 12.2 Control map

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| List | `GET /projects/{id}/requirements` · `GET /requirements` | 🔒 `REQUIREMENT_READ` | — |
| View | `GET /requirements/{id}` | 🔒 `REQUIREMENT_READ` | — |
| Create | `POST /projects/{id}/requirements` | 🔒 `REQUIREMENT_WRITE` | `REQUIREMENT_CREATED` |
| Edit | `PATCH /requirements/{id}` | 🔒 `REQUIREMENT_WRITE` | `REQUIREMENT_UPDATED` |
| Search / Filter | query parameters | 🔒 `REQUIREMENT_READ` | — |
| Traceability | `GET /requirements/{id}/links` | 🔒 `TRACEABILITY_READ` | — |

**`confidence`** is a stored agent-produced value (`08 § 5`), displayed as recorded. It is never
computed or rounded in the frontend.

🟠 **D-09** — `requirement ID` is the human-readable key `09 § 6` leaves undefined. The column
renders the key when present and the short UUID otherwise; **no `BR-001` is minted**.

---

# 13. WORKFLOWS

## Route

/workflows

## Components

- workflow list
- workflow templates
- status
- version
- run action

Whether users may create arbitrary workflows is:

DECISION REQUIRED

The implementation must not expose workflow authoring until the workflow architecture has been finalized.

## 13.1 ✅ D-02 RESOLVED — DERIVED: fixed graph, configurable capabilities

`05 § 1 R1` states the resolution: **the state graph is fixed; capability flags and policy bindings
vary per definition.** Three independent pieces of repository evidence:

| Evidence | Implication |
| --- | --- |
| `05` defines exactly one machine, `REFYNE_CORE_V1`, with a closed transition table | There is no second graph to author |
| `13 § CONDITIONAL` lists 6 rules, all of them **capability toggles** (security on/off, compliance on/off) and **policy thresholds** — not arbitrary topology | Variation is configuration, not authoring |
| `03 § 14` displays *states, conditions, agents, enabled capabilities* — a read-only view | The UI shows a definition; it does not compose one |

**No workflow interpreter is built.** This section's own instruction — *"must not expose workflow
authoring"* — plus `CLAUDE.md`'s prohibition on inventing requirements means a **Create Workflow**
button in a mockup is not authority to build a graph editor. What a definition configures:
`capabilities_snapshot` (which optional states are enabled) and `policy_version_id`.

🟠 **D-02 residual** — whether an administrator may create a *new definition* (a new capability
preset) is still undecided; `07 § 9` marks `POST /workflows` 🟠. Creating a preset is not authoring a
graph, so this residual is much narrower than the original decision.

## 13.2 Control map

| Control | API | Permission |
| --- | --- | --- |
| Workflow list | `GET /workflows` | 🔒 `WORKFLOW_READ` |
| Templates | `GET /workflows?status=PUBLISHED` | 🔒 `WORKFLOW_READ` |
| Version | field of the definition | 🔒 `WORKFLOW_READ` |
| Run | `POST /workflows/{workflow_definition_id}/runs` | `WORKFLOW_RUN` |
| Create definition | `POST /workflows` | `ADMIN_WORKFLOWS` — 🟠 D-02 |

---

# 14. WORKFLOW DETAIL

## Route

/workflows/{workflow_id}

## Display

- workflow ID
- name
- version
- states
- conditions
- agents
- enabled capabilities

## Run

POST /api/v1/workflows/{workflow_id}/runs

## 14.1 ✅ Path conflict resolved — ADDED

**`POST /workflows/{workflow_definition_id}/runs` is authoritative.** `07` revision 1 also defined
`POST /workflows/{id}/run`; that path is **superseded**. The parameter is renamed from `{workflow_id}`
to `{workflow_definition_id}` because `{workflow_id}` was ambiguous between a definition and a run —
the ambiguity that produced the conflict. The route segment stays `/workflows/{workflow_id}` for the
page; only the API parameter name is disambiguated.

`states` renders `05 § 2`'s nineteen states, filtered by `capabilities_snapshot`. It is a projection
of `05`, never a second state list (`05 § 1`: *"No other specification may define states,
transitions, or triggers."*).

---

# 15. WORKFLOW RUN

## Route

/workflow-runs/{run_id}

## Display

- run ID
- workflow
- current state
- state history
- active agent
- validation status
- review status
- errors
- retry information
- timeline

## Actions

Cancel

Retry

The availability of each action must be returned by backend policy.

The frontend must not determine whether an action is allowed.

## 15.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Run detail | `GET /workflow-runs/{id}` | 🔒 `WORKFLOW_READ` | — |
| Live updates | `GET /workflow-runs/{id}/stream` (SSE) | 🔒 `WORKFLOW_READ` | — |
| State history | `GET /workflow-runs/{id}/transitions` | 🔒 `WORKFLOW_READ` | — |
| Steps / active agent | `GET /workflow-runs/{id}/steps` | 🔒 `WORKFLOW_READ` | — |
| **Cancel** | `POST /workflow-runs/{id}/cancel` | `WORKFLOW_CANCEL` | `WORKFLOW_RUN_CANCELLED` |
| **Retry** | `POST /workflow-runs/{id}/retry` | `WORKFLOW_RETRY` | `WORKFLOW_RUN_RETRIED` |
| **Supply input** | `POST /workflow-runs/{id}/input` | 🔒 `WORKFLOW_READ` + `PROJECT_WRITE` | `WORKFLOW_INPUT_SUPPLIED` |

`can_cancel` and `can_retry` are **fields in the run response**, computed from `05`'s transition
table (14 cancellable states) and from retry policy. The frontend renders the flags; it does not
evaluate the state machine. Supply-input is the only exit from `WAITING_FOR_INPUT` (`05 § 5.15`).

## 15.2 🔵 Timeline and progress

`workflow-running.png` shows a **9-step timeline**, a **60%** bar and an **"Estimated completion"**
value. Three findings:

1. **The 9 labels are a projection**, mapped in `05 § 8`. `DATA_AVAILABILITY` does not appear among
   them, so whether the timeline shows 9 or 10 steps is undetermined — 🔵.
2. **60% has no defined computation.** No file states whether progress is step-count, weighted, or
   time-based.
3. **"Estimated completion" has no defined basis.** No duration data, no historical baseline.

**Resolution: the UI displays `steps_completed` / `steps_total` and `current_state`, all returned by
the backend.** `07 § 10` deliberately omits a percentage and an ETA from the response. `13 § WORKFLOW`
requires *"see actual progress"* — completed-of-total is actual; an invented percentage is fabricated
progress, forbidden by `CLAUDE.md § 1`. The mockup's `60%` and ETA **must not be reproduced.**

---

# 16. DATA AVAILABILITY

The system recognizes:

AVAILABLE

PARTIAL

MISSING

The workflow behavior for PARTIAL is:

DECISION REQUIRED

The backend must not silently treat PARTIAL as either AVAILABLE or MISSING.

## 16.1 🟠 D-03 — interim behaviour — ADDED

Resolved for two of three values in `05 § 5.7`: `AVAILABLE` proceeds, `MISSING` →
`WAITING_FOR_INPUT`.

`PARTIAL` remains **DECISION REQUIRED**. `08 § 9`: *"The agent must not invent whether PARTIAL is
sufficient."*

**SAFE INTERIM, explicitly labelled interim and not the decision:** `PARTIAL` routes to
`HUMAN_REVIEW` with reason `DATA_PARTIAL`. This treats it as neither `AVAILABLE` nor `MISSING` — it
asks a person — which is the only behaviour that satisfies this section's prohibition without
choosing an answer. The interim must not be documented as the resolution.

---

# 17. RISKS

## Route

/projects/{project_id}/risks

## Display

- risk ID
- title
- description
- severity
- likelihood
- score
- mitigation
- status
- source

Risk values must come from backend data.

## 17.1 Global risks page — ADDED

| Property | Value |
| --- | --- |
| Route | `/risks` |
| Scope | Global (tenant-wide) |
| Purpose | The canonical sidebar's Risks destination (§ 3.2) |
| Components | As above, plus a **Project** column and filters for project, severity, status |
| API | `GET /risks` — new (`07 § 12`) |
| Permission | 🔒 `RISK_READ` |
| Create | Not available — project-scoped only |

## 17.2 Control map

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| List | `GET /projects/{id}/risks` · `GET /risks` | 🔒 `RISK_READ` | — |
| View | `GET /risks/{id}` | 🔒 `RISK_READ` | — |
| Create | `POST /projects/{id}/risks` | 🔒 `RISK_WRITE` | `RISK_CREATED` |
| Edit | `PATCH /risks/{id}` | 🔒 `RISK_WRITE` | `RISK_UPDATED` |

🟠 **D-06** — *"Risk values must come from backend data"* and **`score` has no backend source.**
`09 § 15` requires *"Risk scoring must use configured policy"*; no policy exists; `08 § 8` forbids
inventing scoring rules. The `score` column therefore renders **empty**, and no endpoint accepts or
returns a computed score (`07 § 12`). Severity and likelihood display as recorded.

This is also why `13 § CONDITIONAL`'s *"If risk exceeds configured threshold: approval required"* is
not evaluable — `05`'s `POLICY_EVALUATION` halts rather than guess.

---

# 18. SECURITY

## Route

/projects/{project_id}/security

## Display

- finding ID
- title
- severity
- description
- evidence
- remediation
- status

No finding may be represented as verified without evidence.

## 18.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| List | `GET /projects/{id}/security-findings` | 🔒 `SECURITY_READ` | — |
| View | `GET /security-findings/{id}` | 🔒 `SECURITY_READ` | — |
| Update status | `PATCH /security-findings/{id}` | 🔒 `SECURITY_READ` + `PROJECT_WRITE` | `SECURITY_FINDING_UPDATED` |
| Attach evidence | `POST /security-findings/{id}/evidence` | `PROJECT_WRITE` | `EVIDENCE_CREATED` |

**The evidence rule is a database constraint, not a UI rule.** `status` cannot become `VERIFIED`
unless an `evidence` row references the finding; `07 § 12` returns `422`. Enforcing it in the
frontend alone would leave every other write path open (`CLAUDE.md § 2`).

Reachable from § 8 only — not from the sidebar (§ 3.1).

---

# 19. COMPLIANCE

## Route

/projects/{project_id}/compliance

## Display

- framework
- control
- evidence
- status
- gap
- remediation

No compliance claim may be presented as confirmed without supporting evidence.

## 19.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| List | `GET /projects/{id}/compliance-findings` | 🔒 `COMPLIANCE_READ` | — |
| View | `GET /compliance-findings/{id}` | 🔒 `COMPLIANCE_READ` | — |
| Update status | `PATCH /compliance-findings/{id}` | 🔒 `COMPLIANCE_READ` + `PROJECT_WRITE` | `COMPLIANCE_FINDING_UPDATED` |
| Attach evidence | `POST /compliance-findings/{id}/evidence` | `PROJECT_WRITE` | `EVIDENCE_CREATED` |

Same constraint-level enforcement as § 18.1: `COMPLIANT` requires an evidence row.

🔵 **MC-01** — no framework catalogue exists anywhere in the repository. `framework` and `control`
are free text from the source document; the platform cannot verify that a named control exists.
**The page is implementable; framework conformance checking is not.**

Reachable from § 8 only.

---

# 20. DOCUMENTS

## Route

/projects/{project_id}/documents

## Display

- document ID
- document type
- title
- version
- status
- validation status
- approval status
- created date

## Actions

Generate

Open

Revise

Validate

Review

Approve when authorized

Download

## 20.1 Global documents page — ADDED

| Property | Value |
| --- | --- |
| Route | `/documents` |
| Scope | Global (tenant-wide) |
| Purpose | `documents.png` — *"Manage all project documents"* |
| Components | As above, plus a **Project** column and filters for type, status, project |
| API | `GET /documents` (`07 § 15`) |
| Permission | `DOCUMENT_READ` |
| Generate | **Not available** — generation requires a project (§ 21) |

## 20.2 Control map

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| List | `GET /projects/{id}/documents` · `GET /documents` | `DOCUMENT_READ` | — |
| Generate | → § 21 | `DOCUMENT_GENERATE` | `DOCUMENT_GENERATION_REQUESTED` |
| Open | `/documents/{id}` (§ 22) | `DOCUMENT_READ` | — |
| Revise | `POST /documents/{id}/revise` | `DOCUMENT_EDIT` | `DOCUMENT_REVISED` |
| Validate | `POST /documents/{id}/validate` | `DOCUMENT_GENERATE` | `DOCUMENT_VALIDATION_REQUESTED` |
| Review | `POST /documents/{id}/review` | `DOCUMENT_REVIEW` | `REVIEW_REQUESTED` |
| **Approve when authorized** | `POST /documents/{id}/approve` | `DOCUMENT_APPROVE` | `APPROVAL_GRANTED` |
| **Reject** | `POST /documents/{id}/reject` | 🔒 `DOCUMENT_REJECT` | `APPROVAL_REJECTED` |
| Download | `GET /documents/{id}/download?format=` | `DOCUMENT_READ` + 🔒 `DOCUMENT_DOWNLOAD` | `DOCUMENT_DOWNLOADED` |
| Retry failed generation | `POST /generation-runs/{id}/retry` | `DOCUMENT_GENERATE` | `DOCUMENT_GENERATION_REQUESTED` |

**Three status columns, one stored field.** `status` is stored; `validation_status` and
`approval_status` are **computed server-side** from `validation_runs` and `approvals` and returned as
read-only fields (`09 § 4.1`). They are never stored twice and never computed in the browser.

*"Approve when authorized"* is backend-determined: the response carries `can_approve`. Hiding the
button is affordance; the endpoint denies independently (`11 § 27`).

🟠 **D-04** — approve and reject exist as contracts but `APPROVAL` halts until the completion rule is
set (`09 § 22.1`).

---

# 21. DOCUMENT GENERATOR

## Route

/projects/{project_id}/documents/generate

## Fields

- document type
- source selection
- additional instructions
- workflow/source context

## Supported document types

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

## Action

POST /api/v1/projects/{project_id}/documents/generate

Generation is asynchronous.

## 21.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Document type | enum, 11 values (`09 § 2.1`) | — | — |
| Source selection | `GET /projects/{id}/files` · `.../requirements` | `FILE_READ`, 🔒 `REQUIREMENT_READ` | — |
| Additional instructions | free text → `USER_INPUT` bucket | — | — |
| Generate | `POST /projects/{id}/documents/generate` | `DOCUMENT_GENERATE` | `DOCUMENT_GENERATION_REQUESTED` |
| Progress | `GET /documents/{id}/generation-runs` | `DOCUMENT_READ` | — |

**Eleven types — this list is authoritative** and agrees exactly with `01` and `09 § 2`
(✅ **D-08**). `document-generator.png` shows 6 tiles because it is a viewport crop of a scrollable
grid; `04` omits three types and is corrected.

*Additional instructions* is user text. It enters the `USER_INPUT` bucket and **cannot grant a
permission, enable a tool, or select a source the caller cannot read** (`11 § 14.1`).

`202 {document_id, generation_run_id}` — the page then polls or streams. No synthetic percentage
(§ 11).

---

# 22. DOCUMENT PREVIEW

## Route

/documents/{document_id}

## Display

- document
- version
- validation
- approval
- sources where applicable
- traceability where applicable

BRD:

Sources tab may be displayed.

SRS:

Traceability tab may be displayed.

Exact tab applicability must follow document type specification.

## 22.1 ✅ Tab applicability RESOLVED — ADDED

`09 § 30` resolves it: **both tabs are displayed for all 11 types.** Every type has
`generation_run_sources` rows and every type participates in traceability, so applicability is per
**content**, not per type.

An empty tab **displays its emptiness** rather than being hidden — a missing traceability link is a
finding the user needs to see (`09 § 12.3`). Hiding the tab would conceal it.

## 22.2 Control map

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Document + version | `GET /documents/{id}` | `DOCUMENT_READ` | — |
| Version selector | `GET /documents/{id}/versions` | `DOCUMENT_READ` | — |
| Validation tab | `GET /documents/{id}/validation-runs` | `DOCUMENT_READ` | — |
| Approval tab | `GET /documents/{id}/approvals` | `DOCUMENT_READ` | — |
| Sources tab | `GET /documents/{id}/sources` | `DOCUMENT_READ` | — |
| Traceability tab | `GET /documents/{id}/traceability` | 🔒 `TRACEABILITY_READ` | — |
| Download PDF/DOCX/XLSX | `GET /documents/{id}/download?format=` | 🔒 `DOCUMENT_DOWNLOAD` | `DOCUMENT_DOWNLOADED` |
| Document chat | `POST /documents/{id}/chat` | `DOCUMENT_READ` | `DOCUMENT_CHAT_MESSAGE` |

`brd-preview.png` and `srs-preview.png` render stored section content with provenance. A section
with no source shows its `UNVERIFIED` marker (`09 § 19.1`) — it is never rendered as though sourced.

🔵 **Document chat apply-changes** — chat over a document is contractable as a read-and-discuss
surface, but nothing specifies how a suggested edit becomes a revision: no diff format, no
accept/reject contract, no authorization rule for an LLM-proposed change. `07 § 27` records it.
**Chat may answer questions; it may not write.** An LLM writing document content directly would
breach `CLAUDE.md § 4`.

🔵 **Version diff** — `09 § 27` requires previous versions remain immutable and retrievable, but no
file specifies a diff representation. Versions are viewable side by side; a computed diff is not
contracted.

---

# 23. DOCUMENT REVIEW

## Route

/documents/{document_id}/review

The review system must support:

- reviewer
- role
- assigned_by
- due date
- priority
- overall review status
- section review status
- comments

The canonical review UI indicates section-level review.

Backend must therefore persist section review state and comments.

Required data contracts:

REVIEW

REVIEW_ASSIGNMENT

REVIEW_SECTION

REVIEW_COMMENT

## 23.1 ✅ Control map — ADDED

All four entities exist (`09 § 21.1`).

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Review detail | `GET /reviews/{id}` incl. `sections_reviewed`/`sections_total` | `DOCUMENT_REVIEW` | — |
| Assign reviewer | `POST /reviews/{id}/assignments` | `DOCUMENT_REVIEW` | `REVIEW_ASSIGNED` |
| Remove reviewer | `DELETE /reviews/{id}/assignments/{aid}` | `DOCUMENT_REVIEW` | `REVIEW_ASSIGNMENT_REMOVED` |
| Due date / priority | `PATCH /reviews/{id}` | `DOCUMENT_REVIEW` | `REVIEW_UPDATED` |
| Section status | `PATCH /review-sections/{id}` | `DOCUMENT_REVIEW` | `REVIEW_SECTION_UPDATED` |
| Add comment | `POST /reviews/{id}/comments` | `DOCUMENT_REVIEW` | `REVIEW_COMMENT_ADDED` |
| Edit comment | `PATCH /review-comments/{id}` | `DOCUMENT_REVIEW` | `REVIEW_COMMENT_UPDATED` |
| **Approve / Request changes / Reject / Escalate** | `POST /reviews/{id}/decision` | `DOCUMENT_REVIEW` | `REVIEW_APPROVED` · `REVIEW_CHANGES_REQUESTED` · `REVIEW_REJECTED` · `REVIEW_ESCALATED` |

**One decision endpoint over four outcomes**, because splitting them would allow two outcomes to be
recorded concurrently for one review.

`review.png`'s *"3 of 5"* is `sections_reviewed`/`sections_total`, computed from `review_sections` —
never counted in the browser (§ 32).

**A reviewer cannot approve the document.** `DOCUMENT_REVIEW` ≠ `DOCUMENT_APPROVE` (`11 § 5`), and
`05 § 5.12` keeps `HUMAN_REVIEW` and `APPROVAL` as distinct states for the same reason.

---

# 24. APPROVAL

## Route

/approvals/{approval_id}

The UI supports approval as a workflow step.

However, the exact approval model remains:

DECISION REQUIRED

Possible models identified in existing specifications:

- single approver
- sequential approval chain
- staged pipeline

Do not implement a model without resolving this decision.

## 24.1 🟠 D-04 — storage ready, completion rule undecided — ADDED

`09 § 22.1` shows `approvals` + `approval_steps` can store all three models. What is undecided is
the **completion rule** — one policy key, `approval.completion_rule`, unset. `05`'s `APPROVAL` state
halts under `R4` rather than assume; `07 § 19` returns `422 POLICY_RULE_MISSING`.

## 24.2 Control map

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Approval detail | `GET /approvals/{id}` | `DOCUMENT_APPROVE` ∨ `DOCUMENT_READ` | — |
| Chain / steps | `GET /approvals/{id}/steps` | `DOCUMENT_APPROVE` | — |
| **Approve** | `POST /approvals/{id}/decision` + `If-Match` | `DOCUMENT_APPROVE` | `APPROVAL_GRANTED` |
| **Reject** | `POST /approvals/{id}/decision` + `If-Match` | 🔒 `DOCUMENT_REJECT` | `APPROVAL_REJECTED` |
| **Request changes** | `POST /approvals/{id}/decision` + `If-Match` | `DOCUMENT_REVIEW` | `REVIEW_CHANGES_REQUESTED` |
| Delegate | — | — | 🔵 **blocked** |

`If-Match: <lock_version>` is **mandatory** so two approvers cannot both decide a stale version
(`12 § 35`). A stale decision returns `409 CONFLICT_STALE_VERSION`.

**`APPROVAL_GRANTED` requires a human actor** — `actor_type='USER'` with a real `actor_user_id`,
enforced by constraint (`11 § 21.2`). `08 § 18`: *"Agents cannot impersonate human approval."*

🔵 **Delegation** — no file defines who may delegate, to whom, or whether authority transfers. The
`approval_steps.delegated_from_user_id` column exists so the decision is storable, but no endpoint
is defined (`07 § 27`).

## 24.3 Reported canonical-UI defect

`approval.png`'s donut reads **1 of 3** while all three chain rows read **Pending**. Those two facts
cannot both be true. **The mockup's counts must not be reproduced literally** — the count is computed
from `approval_steps`, and rendering a hard-coded `1 of 3` would be fabricated approval state
(`CLAUDE.md § 1`, § 32).

---

# 25. RTM

## Route

/projects/{project_id}/rtm

Display:

Requirement ID

Business Requirement

Functional Requirement

SRS Reference

Design Reference

Test Case ID

Risk ID

Evidence

Status

Every displayed mapping must reference actual stored records.

## 25.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| Matrix | `GET /projects/{id}/rtm` | 🔒 `TRACEABILITY_READ` | — |
| Create link | `POST /requirements/{id}/links` | 🔒 `REQUIREMENT_WRITE` | `TRACE_LINK_CREATED` |
| Delete link | `DELETE /traceability-relationships/{id}` | 🔒 `REQUIREMENT_WRITE` | `TRACE_LINK_DELETED` |
| Export XLSX | `GET /documents/{id}/xlsx` (RTM document) | 🔒 `DOCUMENT_DOWNLOAD` | `DOCUMENT_DOWNLOADED` |

**These nine columns are authoritative** for both the page and the XLSX export (`09 § 25.1`).

*"Every displayed mapping must reference actual stored records"* is enforced by trigger:
`traceability_relationships` rejects a row pointing at a non-existent entity (`09 § 12.1`).

**Design Reference renders empty for every row** — 🔵 **MC-03**, `design_elements` has no
specification. `13 § TRACEABILITY`'s *"where applicable"* is honoured by an empty cell, never a
placeholder.

🟠 **D-19 residual** — whether *Requirement ID* and *Business Requirement* denote one entity or two
is undecided. Both readings produce the same nine columns, so the layout is not blocked.

---

# 26. INTEGRATIONS

## Route

/integrations

Supported integrations:

- Jira
- Confluence
- Notion

Actions:

Connect

Disconnect

Test Connection

View Status

Integration results must always come from the connected service.

Never display fabricated external data.

## 26.1 Control map — ADDED

| Control | API | Permission | Audit |
| --- | --- | --- | --- |
| View Status | `GET /integrations` | `INTEGRATION_READ` | — |
| **Connect (Jira)** | `POST /integrations/jira/connect` → OAuth | `INTEGRATION_MANAGE` | `INTEGRATION_CONNECT_STARTED` · `INTEGRATION_CONNECTED` |
| Connect (Confluence) | — | — | 🔵 **MC-04** |
| Connect (Notion) | — | — | 🔵 **MC-04** |
| Disconnect | `DELETE /integrations/{id}` | `INTEGRATION_MANAGE` | `INTEGRATION_DISCONNECTED` |
| **Test Connection** | `POST /integrations/{id}/test` | `INTEGRATION_MANAGE` | `INTEGRATION_TESTED` |

**Test Connection performs a real read** against the provider — `jira.issue.search` with an empty
query — and returns its actual outcome. **Never a canned success** (`13 § INTEGRATIONS`,
`CLAUDE.md § 1`). Revision 1 had this button with no endpoint.

A disconnected integration returns `503 INTEGRATION_NOT_CONNECTED` and the UI shows *"Jira is not
connected."* — never fabricated data (`10`).

🔵 **MC-04** — `10` specifies OAuth for Jira but **no authentication method for Confluence or
Notion**. Their Connect buttons are rendered disabled with the reason stated; inventing an auth flow
would mean inventing a credential-handling contract.

**Confluence and Notion are read-only** — `10` grants only search and retrieve, and no write tool
exists for either (`11 § 16.2`).

---

# 27. REPORTS

## Route

/reports

The canonical UI contains Reports.

Functional requirements are not currently specified.

Status:

BLOCKED

Required before implementation:

- report types
- filters
- data sources
- permissions
- export formats
- APIs
- database requirements

## 27.1 Rendering while blocked — ADDED

The item stays in the sidebar (§ 2 forbids removing a canonical element) and the route renders an
empty state naming what is undefined. **No endpoint is defined and no data is displayed.**

`04`'s Reporting Service and `admin.png`'s figures cannot substitute: `admin.png`'s *1 TB* and
*100,000* are mockup values, and reusing dashboard metrics as "reports" would be inventing report
functionality — which this section explicitly forbids.

---

# 28. ADMIN

## Route

/admin

The canonical UI must be respected.

Current architecture requires administrative control over:

- users
- roles
- permissions
- workflows
- agents
- tools
- models
- templates
- integrations
- audit

Role assignment behavior is:

DECISION REQUIRED

The current canonical UI does not fully specify role-management interaction.

## 28.1 Control map — ADDED

| Area | API | Permission | Status |
| --- | --- | --- | --- |
| Users | `GET`/`PATCH /admin/users` | `ADMIN_USERS` | ✅ |
| Roles | `GET`/`POST /admin/roles` | `ADMIN_ROLES` | 🟠 D-13 |
| Permissions | `PUT /admin/roles/{id}/permissions` | `ADMIN_ROLES` | 🟠 D-13 · 🔵 MC-02 |
| Role assignment | `POST`/`DELETE /admin/users/{id}/roles` | `ADMIN_ROLES` | 🟠 D-13 |
| Workflows | `GET`/`POST /workflows` | `ADMIN_WORKFLOWS` | 🟠 D-02 |
| Agents | `GET /admin/agents` | `ADMIN_WORKFLOWS` | ✅ read-only |
| **Tools** | `GET`/`PATCH /admin/tools/{id}` | `ADMIN_TOOLS` | ✅ — **no create** |
| Models | `GET`/`POST`/`PATCH /admin/model-configurations` | 🔒 `ADMIN_MODELS` | 🔒 |
| Templates | `GET`/`POST`/`PATCH /admin/templates` | 🔒 `ADMIN_TEMPLATES` | 🔒 |
| Policies | `GET`/`POST /admin/policies`, `POST .../activate` | 🔒 `ADMIN_POLICIES` | 🔒 |
| Quota | `GET`/`PUT /admin/quota` | 🔒 `ADMIN_QUOTA` | 🔒 |
| Integrations | → § 26 | `INTEGRATION_MANAGE` | ✅ |
| Audit | `GET /audit-events` | `AUDIT_READ` | ✅ |

**No tool-create endpoint.** Tools are registered by deployment, not at runtime — a runtime create
would make the sole external-effect gate self-service (`11 § 16.1`). Admin may enable, disable, and
adjust bindings only.

🟠 **D-13** — role model undecided. Storage exists; six items in `11 § 6` are undefined. Under
`11 § 27` no role can be assigned, so no permission is held.

**Quota limits are not seeded.** `admin.png`'s *1 TB* and *100,000* are mockup values;
`quota.enforced` defaults `false` and no limit is set (`CLAUDE.md § 1`).

**Model configuration never holds an API key** — it names a secrets-manager key
(`11 § 9.1`).

---

# 29. PAGINATION

All list endpoints must define:

page

page_size

total

items

Pagination display must be generated from backend metadata.

Do not hard-code values such as:

1/36

1/45

## 29.1 Contract — ADDED

`07 § 1` specifies cursor pagination with a **real `total`**. `total` is a genuine count query, not
an estimate, because the UI displays it.

`chat.png`'s dashboard counts (**24 / 18 / 7 / 12**) are mockup values. `GET /dashboard/metrics`
returns real counts; the mockup numbers must not be reproduced (§ 32).

---

# 30. ERROR CONTRACT

Backend errors must follow the global API error contract.

Example:

{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "You do not have permission to perform this action.",
    "request_id": "req_..."
  }
}

Frontend must not display stack traces.

The `request_id` shown to the user is the same value recorded on the corresponding `audit_events`
row (`11 § 21.1`), so a reported failure is joinable to its audit record.

---

# 31. AUDIT

Audit applicable actions:

- authentication
- file upload
- workflow execution
- workflow cancellation
- workflow retry
- agent execution
- tool execution
- document generation
- document revision
- review
- approval
- rejection
- integration changes
- administrative changes

All fourteen categories map to named event types in `11 § 21.2`, which is the authoritative
catalogue. No page emits an event that is not listed there.

---

# 32. FRONTEND RULE

No page may contain:

- fake API responses
- hard-coded workflow state
- fake progress
- fake external integration results
- fake document status
- fake approval status

All operational state comes from the backend.

## 32.1 Mockup values that must not be reproduced — ADDED

The canonical PNGs are layout references. These specific values are mockup content and would each
violate a rule above if copied into code:

| Value | File | Rule breached |
| --- | --- | --- |
| `60%`, "Estimated completion" | `workflow-running.png` | fake progress (§ 15.2) |
| `1 of 3` with three Pending rows | `approval.png` | fake approval status (§ 24.3) |
| `24 / 18 / 7 / 12` | `chat.png` | fake API responses (§ 29.1) |
| `1 TB`, `100,000` | `admin.png` | fake configuration (§ 28.1) |
| `1/36`, `1/45` | pagination mockups | § 29 |
| `#REV-2026-001` | document mockups | `09 § 6` forbids hard-coded IDs |

Following the canonical UI means following its **layout, navigation, spacing, hierarchy, structure,
components and terminology** (§ 2) — not its sample data.

---

# 33. UI-TO-BACKEND MAP — ADDED

Every canonical page, its controls, and whether each has a complete backend contract.

| Page | § | Controls | Contracted | Gated | Blocked |
| --- | --- | --- | --- | --- | --- |
| Login | 5 | 5 | 5 | 0 | 0 |
| Register | 6 | 6 | 5 | 1 (D-20) | 0 |
| Chat | 9 | 9 | 0 | 9 (MC-02) | 1 (stop generation) |
| Project chat | 10 | 9 | 0 | 9 (MC-02) | 1 (retrieval strategy) |
| Project list | 7 | 4 | 4 | 0 | 0 |
| Project | 8 | 9 | 3 | 6 (MC-02) | 0 |
| File upload | 11 | 5 | 5 | 0 | 0 |
| Requirements (both scopes) | 12 | 6 | 0 | 6 (MC-02) | 0 |
| Workflows | 13 | 5 | 1 | 3 (MC-02) | 1 (D-02 create) |
| Workflow detail | 14 | 8 | 1 | 7 (MC-02) | 0 |
| Workflow run | 15 | 7 | 2 | 5 (MC-02) | 2 (progress %, ETA) |
| Risks (both scopes) | 17 | 4 | 0 | 4 (MC-02) | 0 |
| Security | 18 | 4 | 1 | 3 (MC-02) | 0 |
| Compliance | 19 | 4 | 1 | 3 (MC-02) | 0 |
| Documents (both scopes) | 20 | 10 | 6 | 2 (MC-02) | 0 |
| Document generator | 21 | 5 | 3 | 2 (MC-02) | 0 |
| Document preview | 22 | 8 | 5 | 2 (MC-02) | 2 (chat apply, diff) |
| Document review | 23 | 8 | 8 | 0 | 0 |
| Approval | 24 | 6 | 4 | 1 (MC-02) | 1 (delegation) |
| RTM | 25 | 4 | 0 | 4 (MC-02) | 0 |
| Integrations | 26 | 6 | 4 | 0 | 2 (MC-04) |
| Reports | 27 | 0 | 0 | 0 | **whole page** |
| Admin | 28 | 13 | 5 | 4 (MC-02) | 4 (D-13, D-02) |
| Sidebar | 3 | 9 | 4 | 4 (MC-02) | 1 (Reports) |
| | **Total** | **164** | **67** | **75** | **18** |

**Contracted** = an endpoint exists whose every precondition is defined. **Gated** = the contract is
complete but the permission or a policy value is missing. **Blocked** = no contract is definable
without inventing a requirement.

Revision 3 of the architecture review counted **35 blocked UI actions**. That number is now **18**:
`07` revision 2 defined contracts for 17 of them — Test Connection, Reject, Request Changes,
Regenerate, Supply Input, file listing, section review status, review comments, escalation, XLSX
export, generation retry, global list pages, and the rest. The remaining 18 are irreducible without
a product decision.

---

# 34. BLOCKED CONTROL REGISTER — ADDED

| # | Control | Page | Why no contract is definable |
| --- | --- | --- | --- |
| 1 | Reports page (all) | 27 | No report types, sources, filters or formats specified |
| 2 | Reports sidebar item | 3 | Same |
| 3 | Stop generation | 9 | No endpoint, no defined state for a half-generated message |
| 4 | Retrieval / embedding strategy | 10 | No chunking, embedding or budget rule |
| 5 | Create workflow definition | 13 | 🟠 D-02 residual; § 13 forbids exposing authoring |
| 6 | Workflow progress percentage | 15 | No computation defined |
| 7 | Estimated completion | 15 | No duration data or baseline |
| 8 | Document chat apply-changes | 22 | No diff format or accept/reject authorization |
| 9 | Version diff | 22 | No diff representation specified |
| 10 | Approval delegation | 24 | No delegation authority rule |
| 11 | Connect Confluence | 26 | 🔵 MC-04 — no auth method |
| 12 | Connect Notion | 26 | 🔵 MC-04 — no auth method |
| 13 | Role creation | 28 | 🟠 D-13 |
| 14 | Role assignment | 28 | 🟠 D-13 |
| 15 | Permission editing | 28 | 🟠 D-13 + 🔵 MC-02 |
| 16 | Quota limit entry | 28 | 🟠 D-14 — no quota model |
| 17 | Design element create/edit | 25 | 🔵 MC-03 — entity undefined |
| 18 | Test result entry | 20 | 🔵 MC-03 — no ingestion contract |

**None of these renders as a working control.** Each is either absent, or present and disabled with
its reason stated. `CLAUDE.md § 3`: *"Do not build decorative buttons."*

---

# 35. PAGE INVENTORY — ADDED

| # | Route | Scope | Section | Status |
| --- | --- | --- | --- | --- |
| 1 | `/login` | Public | 5 | ✅ |
| 2 | `/register` | Public | 6 | 🟠 D-20 |
| 3 | `/chat` · `/chat/{id}` | Global | 9 | 🔒 MC-02 |
| 4 | `/projects` | Global | 7 | ✅ |
| 5 | `/projects/{id}` | Project | 8 | ✅ |
| 6 | `/projects/{id}/chat` | Project | 10 | 🔒 MC-02 |
| 7 | `/requirements` | Global | 12.1 | 🔒 MC-02 |
| 8 | `/projects/{id}/requirements` | Project | 12 | 🔒 MC-02 |
| 9 | `/workflows` | Global | 13 | 🔒 MC-02 |
| 10 | `/workflows/{id}` | Global | 14 | 🔒 MC-02 |
| 11 | `/workflow-runs/{id}` | Project | 15 | 🔒 MC-02 |
| 12 | `/risks` | Global | 17.1 | 🔒 MC-02 |
| 13 | `/projects/{id}/risks` | Project | 17 | 🔒 MC-02 · 🟠 D-06 |
| 14 | `/projects/{id}/security` | Project | 18 | 🔒 MC-02 |
| 15 | `/projects/{id}/compliance` | Project | 19 | 🔒 MC-02 · 🔵 MC-01 |
| 16 | `/documents` | Global | 20.1 | ✅ |
| 17 | `/projects/{id}/documents` | Project | 20 | ✅ |
| 18 | `/projects/{id}/documents/generate` | Project | 21 | ✅ |
| 19 | `/documents/{id}` | Project | 22 | ✅ |
| 20 | `/documents/{id}/review` | Project | 23 | ✅ |
| 21 | `/approvals/{id}` | Project | 24 | 🟠 D-04 |
| 22 | `/projects/{id}/rtm` | Project | 25 | 🔒 MC-02 · 🔵 MC-03 |
| 23 | `/integrations` | Global | 26 | ✅ (🔵 MC-04 for 2 of 3) |
| 24 | `/reports` | Global | 27 | 🔴 **BLOCKED** |
| 25 | `/admin` | Global | 28 | 🟠 D-13 |

**25 routes.** Revision 1 defined 24; `/requirements` and `/risks` are added by § 3.2, and
`/documents` was already global-capable. **8 are fully implementable**, 12 wait on MC-02, 4 on a
product decision, 1 is blocked outright.
