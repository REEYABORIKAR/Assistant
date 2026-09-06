# 06 DATABASE SCHEMA

**Revision:** 2 (2026-08-26) — FINAL ARCHITECTURE RESOLUTION PASS
**Engine:** PostgreSQL
**Migrations:** Alembic

Revision 1 listed 32 tables as bare column names with no types, keys, or indexes.
This revision defines every table completely and adds the 20 entities the architecture
review found missing.

---

# 1. CONVENTIONS

| Rule | Value |
| --- | --- |
| Primary keys | `uuid`, `NOT NULL`, `DEFAULT gen_random_uuid()` (pgcrypto) |
| Timestamps | `timestamptz`, `NOT NULL`, `DEFAULT now()` |
| `updated_at` | present on every mutable table; maintained by trigger |
| Soft delete | `deleted_at timestamptz NULL` — only on resources with a `DELETE` endpoint |
| JSON | `jsonb` — never `json` |
| Case-insensitive text | `citext` (email, keys) |
| Enums | native PostgreSQL `CREATE TYPE ... AS ENUM` — declared in § 3 |
| Money/scores | `numeric(p,s)` — never `float` |
| Human-readable keys | `citext`, unique per tenant, immutable after insert — **format is 🟠 D-09** |
| Naming | tables `snake_case` plural; enum labels `UPPER_SNAKE_CASE` (matches `07`'s error-code convention) |
| FK actions | stated per column. `ON DELETE CASCADE` only where the child cannot exist without the parent and has no audit value |

**Extensions required:** `pgcrypto` (gen_random_uuid), `citext`.

---

# 2. TENANCY OWNERSHIP MODEL

`11 § 3` states: *"Every tenant-owned entity must be associated with tenant scope **directly or
through a guaranteed tenant-scoped parent relationship**."*

That sentence defines **ownership**, not **enforcement**. Ownership is therefore resolved here;
enforcement is 🟠 **D-01** (§ 2.3).

## 2.1 The rule applied

A table carries a **DIRECT** `tenant_id` if and only if it is addressable by a top-level API path
of the form `/{resource}/{id}` — because that is the IDOR surface `12 § 31` requires tested.
A table reachable only through a parent path is **DERIVED** and carries no `tenant_id`.

This is why `tenant_id` is **not** added everywhere: 24 tables are DERIVED and adding a
redundant `tenant_id` to them would create two sources of truth for the same fact.

## 2.2 Classification

| Class | Tables |
| --- | --- |
| **ROOT** (no tenant) | `tenants` |
| **GLOBAL** (not tenant-owned) | `users`, `permissions`, `password_reset_tokens`, `consents`, `tool_registry` |
| **DIRECT** (has `tenant_id`) | `tenant_members`, `roles`, `user_roles`, `sessions`, `projects`, `conversations`, `files`, `workflow_definitions`, `workflow_runs`, `requirements`, `agent_runs`, `model_configurations`, `templates`, `policies`, `risks`, `security_findings`, `compliance_findings`, `design_elements`, `test_cases`, `evidence`, `traceability_relationships`, `documents`, `generation_runs`, `reviews`, `approvals`, `tool_bindings`, `tool_calls`, `integrations`, `audit_events`, `notifications`, `quotas`, `jobs` |
| **DERIVED** (via FK parent) | `role_permissions`, `refresh_tokens`, `project_members`, `messages`, `file_chunks`, `workflow_steps`, `workflow_state_transitions`, `workflow_events`, `requirement_links`, `validation_runs`, `policy_versions`, `policy_rules`, `policy_evaluations`, `test_case_results`, `document_versions`, `document_sections`, `document_sources`, `document_renditions`, `generation_run_sources`, `review_assignments`, `review_sections`, `review_comments`, `approval_steps`, `integration_credentials`, `quota_usage`, `job_attempts` |

`users` is GLOBAL because `tenant_members` exists — one identity may belong to several tenants.
`audit_events.tenant_id` is **nullable**: `11 § 21` requires auditing failed authentication, which
occurs before a tenant is resolved.

## 2.3 🟠 DECISION REQUIRED — PRODUCT OWNER — D-01 tenant isolation strategy

**Question:** Which mechanism enforces tenant isolation — application-level filtering,
PostgreSQL Row Level Security, or schema-per-tenant?

**Options already present in repository:** exactly these three, enumerated in `11 § 3`, which
also states *"Do not silently choose."* No other file expresses a preference. **Not decided here.**

**Why it affects implementation:** the § 2.2 ownership model is stable under all three, but the
physical schema is not:

| Strategy | Effect on this schema |
| --- | --- |
| Application-level filtering | Schema as written. Every repository method must take a tenant scope; enforcement is a code-review property, not a database property. |
| PostgreSQL RLS | Every DIRECT table needs a `FORCE ROW LEVEL SECURITY` policy on `tenant_id` plus a session GUC (`app.tenant_id`). Each of the 26 **DERIVED** tables additionally needs either a join-based policy or a denormalised `tenant_id` — i.e. the § 2.1 rule is overridden and `tenant_id` is added to all 58 tenant-owned tables. |
| Schema-per-tenant | `tenant_id` is **removed** from all 32 DIRECT tables; `tenants` and `users` move to a shared schema; Alembic must run N migrations per release. |

**Files affected:** `06` (this file, all tenant-owned tables), `04 § Tenant Service`, `11 § 3`,
`12 § 8`, `12 § 42.20`.

**What cannot proceed until decided:** the **first migration**, and therefore implementation
phases 3–33. Retrofitting means rewriting every query and backfilling every row.

**Interim posture:** the schema below is written in the form that is convertible to any of the
three with the least loss (DIRECT/DERIVED per § 2.1). This is a **presentation choice, not a
decision** — no isolation code may be written until D-01 is answered.

---

# 3. ENUM TYPES

```sql
CREATE TYPE tenant_status          AS ENUM ('ACTIVE','SUSPENDED','DELETED');
CREATE TYPE user_status            AS ENUM ('PENDING','ACTIVE','DISABLED','LOCKED');
CREATE TYPE membership_status      AS ENUM ('INVITED','ACTIVE','SUSPENDED','REMOVED');
CREATE TYPE role_scope             AS ENUM ('TENANT','PROJECT');
CREATE TYPE project_status         AS ENUM ('ACTIVE','ARCHIVED');
CREATE TYPE conversation_status    AS ENUM ('ACTIVE','ARCHIVED');
CREATE TYPE message_role           AS ENUM ('USER','ASSISTANT','SYSTEM','TOOL');
CREATE TYPE message_status         AS ENUM ('PENDING','STREAMING','COMPLETE','FAILED','CANCELLED');

-- 03 § 11 terminal set, plus the pre-terminal stages of the 11 § 8 flow
CREATE TYPE file_status            AS ENUM (
  'UPLOADING','SCANNING','QUARANTINED','EXTRACTING','READY','FAILED');
CREATE TYPE scan_result            AS ENUM ('PENDING','CLEAN','INFECTED','ERROR','SKIPPED');

CREATE TYPE definition_status      AS ENUM ('DRAFT','PUBLISHED','DEPRECATED');

-- 05 § 2 — the 19 authoritative workflow states
CREATE TYPE workflow_state         AS ENUM (
  'CREATED','INPUT_VALIDATION','DATA_COLLECTION','REQUIREMENT_ANALYSIS',
  'SECURITY_ANALYSIS','COMPLIANCE_ANALYSIS','DATA_AVAILABILITY','RISK_ANALYSIS',
  'VALIDATION','POLICY_EVALUATION','HUMAN_REVIEW','APPROVAL',
  'DOCUMENT_GENERATION','DOCUMENT_VALIDATION',
  'WAITING_FOR_INPUT','COMPLETED','FAILED','REJECTED','CANCELLED');

CREATE TYPE run_status             AS ENUM ('RUNNING','WAITING','COMPLETED','FAILED','REJECTED','CANCELLED');
CREATE TYPE step_status            AS ENUM ('PENDING','RUNNING','SUCCEEDED','FAILED','SKIPPED','CANCELLED');
CREATE TYPE step_type              AS ENUM ('SYSTEM','AGENT','VALIDATION','POLICY','HUMAN','DOCUMENT');

-- 05 § 4 — transition trigger taxonomy. RETRY is a trigger, not a state.
CREATE TYPE transition_trigger     AS ENUM (
  'START','SUCCESS','FAILURE','RETRY','SKIP','TIMEOUT',
  'POLICY','HUMAN_APPROVE','HUMAN_REJECT','HUMAN_REQUEST_CHANGES',
  'HUMAN_REQUEST_INFORMATION','HUMAN_ESCALATE','INPUT_SUPPLIED','CANCEL');

CREATE TYPE requirement_type       AS ENUM ('BUSINESS','FUNCTIONAL','NON_FUNCTIONAL','SECURITY','COMPLIANCE','DATA','INTERFACE');
CREATE TYPE requirement_status     AS ENUM ('DRAFT','PROPOSED','ACCEPTED','AMBIGUOUS','DUPLICATE','REJECTED','OBSOLETE');
CREATE TYPE link_relationship      AS ENUM ('DERIVES_FROM','DUPLICATES','CONFLICTS_WITH','REFINES','DEPENDS_ON');

CREATE TYPE agent_type             AS ENUM (
  'SUPERVISOR','REQUIREMENT','SECURITY','COMPLIANCE','RISK',
  'DATA_AVAILABILITY','VALIDATION','DOCUMENT_SUPERVISOR');
CREATE TYPE agent_run_status       AS ENUM ('RUNNING','SUCCEEDED','SCHEMA_INVALID','EVIDENCE_INVALID','POLICY_BLOCKED','FAILED','CANCELLED');
CREATE TYPE validation_outcome     AS ENUM ('PASSED','FAILED');
CREATE TYPE validation_kind        AS ENUM ('AGENT_OUTPUT','DOCUMENT','TRACEABILITY','POLICY');

-- 08 § 9 / 03 § 16
CREATE TYPE availability_state     AS ENUM ('AVAILABLE','PARTIAL','MISSING');

CREATE TYPE severity_level         AS ENUM ('INFO','LOW','MEDIUM','HIGH','CRITICAL');
CREATE TYPE likelihood_level       AS ENUM ('RARE','UNLIKELY','POSSIBLE','LIKELY','ALMOST_CERTAIN');
CREATE TYPE risk_status            AS ENUM ('OPEN','MITIGATING','MITIGATED','ACCEPTED','CLOSED');
CREATE TYPE finding_status         AS ENUM ('OPEN','IN_REMEDIATION','REMEDIATED','ACCEPTED','FALSE_POSITIVE');
-- 09 § 17 / 12 § 42.25 — CONFORMANT requires evidence
CREATE TYPE compliance_status      AS ENUM ('CONFORMANT','PARTIAL','GAP','NOT_APPLICABLE','UNVERIFIED');

-- 09 § 2 — the 11 authoritative document types
CREATE TYPE document_type          AS ENUM (
  'BRD','SRS','FRD','NFRD','RTM','TEST_PLAN','TEST_CASES',
  'RISK_ASSESSMENT','SECURITY_ASSESSMENT','COMPLIANCE_ASSESSMENT','TECHNICAL_DOCUMENTATION');

-- 09 § 4 — exactly 9 states
CREATE TYPE document_status        AS ENUM (
  'DRAFT','GENERATING','VALIDATING','REVIEW','CHANGES_REQUESTED',
  'APPROVED','REJECTED','FAILED','ARCHIVED');

CREATE TYPE rendition_format       AS ENUM ('PDF','DOCX','XLSX');
CREATE TYPE rendition_status       AS ENUM ('PENDING','RENDERING','READY','FAILED');
CREATE TYPE generation_status      AS ENUM ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED');

-- 09 § 19
CREATE TYPE source_type            AS ENUM (
  'FILE','FILE_CHUNK','REQUIREMENT','RISK','SECURITY_FINDING','COMPLIANCE_FINDING',
  'TEST_CASE','DESIGN_ELEMENT','EVIDENCE','DOCUMENT_VERSION','CONVERSATION_MESSAGE',
  'JIRA_ISSUE','CONFLUENCE_PAGE','NOTION_PAGE','UNVERIFIED');

CREATE TYPE review_status          AS ENUM ('PENDING','IN_PROGRESS','APPROVED','CHANGES_REQUESTED','REJECTED','ESCALATED','CANCELLED');
CREATE TYPE review_section_status  AS ENUM ('PENDING','APPROVED','CHANGES_REQUESTED','REJECTED');
CREATE TYPE review_priority        AS ENUM ('LOW','NORMAL','HIGH','URGENT');
CREATE TYPE assignment_status      AS ENUM ('ASSIGNED','ACCEPTED','COMPLETED','DECLINED','REASSIGNED','EXPIRED');
CREATE TYPE comment_resolution     AS ENUM ('OPEN','RESOLVED','WONT_FIX');

CREATE TYPE approval_status        AS ENUM ('PENDING','IN_PROGRESS','APPROVED','REJECTED','CHANGES_REQUESTED','CANCELLED','EXPIRED');
CREATE TYPE approval_step_status   AS ENUM ('PENDING','ACTIVE','APPROVED','REJECTED','CHANGES_REQUESTED','SKIPPED','EXPIRED');
-- D-04: all three candidate models are representable; see § 22
CREATE TYPE approval_step_mode     AS ENUM ('SINGLE','QUORUM','UNANIMOUS');

CREATE TYPE integration_type       AS ENUM ('JIRA','CONFLUENCE','NOTION');
CREATE TYPE integration_status     AS ENUM ('DISCONNECTED','CONNECTING','CONNECTED','ERROR','REVOKED');
CREATE TYPE credential_kind        AS ENUM ('OAUTH2','API_TOKEN');

CREATE TYPE tool_risk_level        AS ENUM ('READ','LOW_WRITE','HIGH_WRITE');
-- 11 § 17 — one label per rejecting stage of the 11-stage chain, plus outcomes
CREATE TYPE tool_call_status       AS ENUM (
  'REQUESTED','SCHEMA_REJECTED','DENIED_AUTHENTICATION','DENIED_TENANT',
  'DENIED_PERMISSION','DENIED_POLICY','DENIED_UNREGISTERED','DENIED_DISABLED',
  'EXECUTED','RESULT_INVALID','EXECUTION_FAILED');

CREATE TYPE actor_type             AS ENUM ('USER','SYSTEM','AGENT','INTEGRATION');
CREATE TYPE policy_scope_type      AS ENUM ('TENANT','PROJECT','WORKFLOW_DEFINITION');
CREATE TYPE policy_status          AS ENUM ('DRAFT','ACTIVE','SUPERSEDED');
CREATE TYPE template_kind          AS ENUM ('DOCUMENT_SECTION','PROMPT','EXPORT');
CREATE TYPE job_status             AS ENUM ('QUEUED','RUNNING','SUCCEEDED','FAILED','DEAD_LETTER','CANCELLED');
CREATE TYPE quota_metric           AS ENUM (
  'PROJECTS','STORAGE_BYTES','API_CALLS','AI_TOKENS','DOCUMENT_GENERATIONS','WORKFLOW_RUNS','ACTIVE_USERS');
CREATE TYPE consent_kind           AS ENUM ('TERMS_OF_SERVICE','PRIVACY_POLICY','DATA_PROCESSING');
CREATE TYPE trace_node_kind        AS ENUM (
  'BUSINESS_REQUIREMENT','FUNCTIONAL_REQUIREMENT','SRS_REQUIREMENT',
  'DESIGN_ELEMENT','TEST_CASE','RISK','EVIDENCE');
```

**`audit_events.event_type`** is **not** an enum. It is `citext NOT NULL` constrained by
`CHECK (event_type = upper(event_type))` and validated against the authoritative catalogue in
`11 § 21.2`. Rationale: the catalogue is expected to grow with every new endpoint, and an enum
would require a migration per event. The catalogue is the contract; the check constraint plus the
`12 § 32` test enforce it.

---

# 4. tenants

**Purpose:** the isolation root. ROOT — no `tenant_id`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `slug` | `citext` | NOT NULL | **UNIQUE** | — |
| `name` | `varchar(200)` | NOT NULL | | — |
| `status` | `tenant_status` | NOT NULL | | `'ACTIVE'` |
| `settings` | `jsonb` | NOT NULL | | `'{}'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(slug)`; `INDEX(status)`.
**Soft delete:** none — deletion is `status='DELETED'` plus the retention policy (`11 § 22`).

---

# 5. users

**Purpose:** global identity. GLOBAL — deliberately no `tenant_id` (§ 2.2).

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `email` | `citext` | NOT NULL | **UNIQUE** | — |
| `password_hash` | `text` | NULL | | — |
| `name` | `varchar(200)` | NOT NULL | | — |
| `status` | `user_status` | NOT NULL | | `'PENDING'` |
| `email_verified_at` | `timestamptz` | NULL | | — |
| `failed_login_count` | `integer` | NOT NULL | `CHECK (>= 0)` | `0` |
| `locked_until` | `timestamptz` | NULL | | — |
| `last_login_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

`password_hash` is nullable to permit SSO-only accounts. **`login.png` shows Google and Microsoft
SSO buttons and no specification defines them** → 🔵 **MISSING CONTRACT**: no `identities`
table is defined here, because the provider set, claim mapping, and just-in-time provisioning
rules are unspecified. SSO cannot be implemented until that contract exists.

**Indexes:** `UNIQUE(email)`; `INDEX(status)`.
`11 § 4`: passwords are never stored plaintext. `12 § 6`: invalid login returns a generic failure.

---

# 6. tenant_members

**Purpose:** membership of a user in a tenant. DIRECT.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `status` | `membership_status` | NOT NULL | | `'INVITED'` |
| `invited_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `joined_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, user_id)`; `INDEX(user_id)`; `INDEX(tenant_id, status)`.

---

# 7. roles

**Purpose:** a named permission bundle within a tenant. DIRECT.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `key` | `citext` | NOT NULL | | — |
| `name` | `varchar(120)` | NOT NULL | | — |
| `description` | `text` | NULL | | — |
| `scope` | `role_scope` | NOT NULL | | — |
| `is_system` | `boolean` | NOT NULL | | `false` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, key)`.

🟠 **D-13** — the **set** of roles is not defined. `11 § 6` states role management is
`DECISION REQUIRED` and requires *"available roles, role assignment UI, role assignment API, who
can assign roles, tenant/project scope, audit behavior"* to be defined first. No role rows are
seeded here. The only role name evidenced anywhere is **`Admin`**, from the user footer in
`chat.png`, `documents.png`, `document-generator.png` and `workflow-running.png` — one label is
not a role model. See § 45.

---

# 8. permissions

**Purpose:** the global permission catalogue. GLOBAL.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `key` | `citext` | NOT NULL | **UNIQUE** | — |
| `resource` | `varchar(60)` | NOT NULL | | — |
| `action` | `varchar(60)` | NOT NULL | | — |
| `description` | `text` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Seed — 21 rows, verbatim from `11 § 5`:**
`PROJECT_READ`, `PROJECT_WRITE`, `PROJECT_DELETE`, `FILE_READ`, `FILE_UPLOAD`, `FILE_DELETE`,
`WORKFLOW_RUN`, `WORKFLOW_CANCEL`, `WORKFLOW_RETRY`, `DOCUMENT_READ`, `DOCUMENT_GENERATE`,
`DOCUMENT_EDIT`, `DOCUMENT_REVIEW`, `DOCUMENT_APPROVE`, `INTEGRATION_READ`,
`INTEGRATION_MANAGE`, `AUDIT_READ`, `ADMIN_USERS`, `ADMIN_ROLES`, `ADMIN_WORKFLOWS`,
`ADMIN_TOOLS`.

🔵 **MISSING CONTRACT — MC-02.** `11 § 5` labels these *"Example permissions"*, so the catalogue is
**illustrative, not exhaustive**. `12 § 4` requires an authorization test for every endpoint, and
the endpoints in `07` need at least these permissions which `11 § 5` does not name:

`REQUIREMENT_READ`, `REQUIREMENT_WRITE`, `CONVERSATION_READ`, `CONVERSATION_WRITE`,
`CONVERSATION_DELETE`, `WORKFLOW_READ`, `RISK_READ`, `RISK_WRITE`, `SECURITY_READ`,
`COMPLIANCE_READ`, `TRACEABILITY_READ`, `TEST_CASE_READ`, `TEST_CASE_WRITE`, `DOCUMENT_DOWNLOAD`,
`DOCUMENT_REJECT`, `REPORT_READ`, `ADMIN_MODELS`, `ADMIN_TEMPLATES`, `ADMIN_POLICIES`,
`ADMIN_QUOTA`, `AGENT_TRACE_READ`.

**These are named as the gap, not adopted.** `11 § 5` must be extended and closed by the product
owner before any endpoint's authorization rule is written. Until then every endpoint in `07`
that needs one of the 21 unnamed permissions is `STATUS = BLOCKED` per `12 § 43`.

---

# 9. role_permissions

**Purpose:** role → permission grant. DERIVED via `roles`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `role_id` | `uuid` | NOT NULL | **PK** part, **FK** → `roles.id` `ON DELETE CASCADE` | — |
| `permission_id` | `uuid` | NOT NULL | **PK** part, **FK** → `permissions.id` `ON DELETE RESTRICT` | — |
| `granted_at` | `timestamptz` | NOT NULL | | `now()` |
| `granted_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |

**PK:** `(role_id, permission_id)`. **Index:** `INDEX(permission_id)`.
No `DENY` rows: `11 § 27` is *"If permission is not explicitly granted: DENY"* — absence is denial.

---

# 10. user_roles — NEW

**Purpose:** assignment of a role to a user at tenant or project scope. DIRECT.
Resolves the missing storage for `03 § 28` role management. Shape only — see 🟠 **D-13**.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE CASCADE` | — |
| `role_id` | `uuid` | NOT NULL | **FK** → `roles.id` `ON DELETE RESTRICT` | — |
| `scope_type` | `role_scope` | NOT NULL | | — |
| `scope_id` | `uuid` | NULL | `CHECK (scope_type='TENANT' AND scope_id IS NULL) OR (scope_type='PROJECT' AND scope_id IS NOT NULL)` | — |
| `assigned_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(user_id, role_id, scope_type, scope_id)`; `INDEX(tenant_id, user_id)`.
`scope_id` is intentionally **not** an FK — it targets `projects.id` only when
`scope_type='PROJECT'`; the referential rule is enforced by the Tenant Service and by
`12 § 42.21`. 🔵 A polymorphic FK is unavoidable here unless D-13 restricts scope to one kind.

---

# 11. sessions — NEW

**Purpose:** an authenticated session. DIRECT — a session is bound to one tenant context.
Required by `11 § 7` (*expire, be revocable*) and `12 § 6` (*logout → session invalidated*).

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE CASCADE` | — |
| `issued_at` | `timestamptz` | NOT NULL | | `now()` |
| `expires_at` | `timestamptz` | NOT NULL | | — |
| `revoked_at` | `timestamptz` | NULL | | — |
| `revoked_reason` | `varchar(60)` | NULL | | — |
| `ip_address` | `inet` | NULL | | — |
| `user_agent` | `text` | NULL | | — |
| `last_seen_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `INDEX(user_id, revoked_at)`; `INDEX(expires_at)`; `INDEX(tenant_id)`.
No session token is stored — only `refresh_tokens` holds a hashed secret (§ 12).
🟠 **D-25** — session and access-token lifetimes are not specified anywhere. `11 § 7` requires
*"expire"* without a duration. See § 45.

---

# 12. refresh_tokens — NEW

**Purpose:** rotation-capable refresh credential. DERIVED via `sessions`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `session_id` | `uuid` | NOT NULL | **FK** → `sessions.id` `ON DELETE CASCADE` | — |
| `token_hash` | `bytea` | NOT NULL | **UNIQUE** | — |
| `expires_at` | `timestamptz` | NOT NULL | | — |
| `used_at` | `timestamptz` | NULL | | — |
| `revoked_at` | `timestamptz` | NULL | | — |
| `replaced_by` | `uuid` | NULL | **FK** → `refresh_tokens.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(token_hash)`; `INDEX(session_id)`; `INDEX(expires_at)`.
Only the hash is stored (`11 § 9`: secrets must not exist in logs or source). `used_at` plus
`replaced_by` detect replay, satisfying `11 § 7` *"prevent unauthorized reuse"*.

---

# 13. password_reset_tokens — NEW

**Purpose:** single-use reset credential. GLOBAL — reset precedes tenant resolution.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE CASCADE` | — |
| `token_hash` | `bytea` | NOT NULL | **UNIQUE** | — |
| `expires_at` | `timestamptz` | NOT NULL | | — |
| `used_at` | `timestamptz` | NULL | | — |
| `requested_ip` | `inet` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(token_hash)`; `INDEX(user_id)`; `INDEX(expires_at)`.
`12 § 6`: the reset flow must not reveal whether an account exists — the API response is
identical whether or not a row is created.
🟠 **D-25** also covers reset-token TTL.

---

# 14. consents — NEW

**Purpose:** persisted registration consent. GLOBAL — consent precedes tenant membership.
Resolves 🟠 **D-20**'s *storage* requirement; `03 § 6` demands exactly these five facts and states
*"Do not implement a checkbox without persistence."*

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE CASCADE` | — |
| `consent_kind` | `consent_kind` | NOT NULL | | — |
| `policy_version` | `varchar(40)` | NOT NULL | | — |
| `granted` | `boolean` | NOT NULL | | — |
| `granted_at` | `timestamptz` | NOT NULL | | `now()` |
| `ip_address` | `inet` | NULL | | — |
| `user_agent` | `text` | NULL | | — |

**Indexes:** `UNIQUE(user_id, consent_kind, policy_version)`; `INDEX(user_id)`.

**Remaining part of D-20 is still open:** which `consent_kind` values are mandatory at
registration, and what `policy_version` string identifies. `register.png` shows a **single,
pre-checked** consent box — which cannot express three kinds and which contradicts an affirmative
consent record. 🟠 See § 45.

---

# 15. projects

**Purpose:** the unit of work. DIRECT. Soft-deletable (`DELETE /projects/{id}` exists).

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_key` | `citext` | NOT NULL | | — |
| `name` | `varchar(200)` | NOT NULL | | — |
| `description` | `text` | NULL | | — |
| `status` | `project_status` | NOT NULL | | `'ACTIVE'` |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |
| `deleted_at` | `timestamptz` | NULL | | — |

**Indexes:** `UNIQUE(tenant_id, project_key)`; `INDEX(tenant_id, status) WHERE deleted_at IS NULL`;
`INDEX(tenant_id, name)` for `03 § 7` search.
`project_key` format is 🟠 **D-09**.

---

# 16. project_members

**Purpose:** project-scoped membership. DERIVED via `projects`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE CASCADE` | — |
| `role_id` | `uuid` | NOT NULL | **FK** → `roles.id` `ON DELETE RESTRICT` | — |
| `added_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(project_id, user_id)`; `INDEX(user_id)`.
`03 § 7`: *"Project visibility is determined by backend authorization."*

---

# 17. conversations

**Purpose:** a chat thread. DIRECT. Soft-deletable.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `document_id` | `uuid` | NULL | **FK** → `documents.id` `ON DELETE CASCADE` | — |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `title` | `varchar(300)` | NULL | | — |
| `status` | `conversation_status` | NOT NULL | | `'ACTIVE'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |
| `deleted_at` | `timestamptz` | NULL | | — |

**Indexes:** `INDEX(tenant_id, created_by, updated_at DESC) WHERE deleted_at IS NULL`;
`INDEX(project_id)`; `INDEX(document_id)`.
**Constraint:** `CHECK (project_id IS NULL OR document_id IS NULL)` — a conversation is global
(`03 § 9` `/chat`), project-scoped (`03 § 10`), or document-scoped, never two at once.
`document_id` exists because `CLAUDE.md` requires *document chat* and implementation phase 27 is
document chat; the **page and endpoint for it remain 🔵 MISSING CONTRACT** (no route in `03`).

---

# 18. messages

**Purpose:** one turn. DERIVED via `conversations`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `conversation_id` | `uuid` | NOT NULL | **FK** → `conversations.id` `ON DELETE CASCADE` | — |
| `parent_message_id` | `uuid` | NULL | **FK** → `messages.id` `ON DELETE SET NULL` | — |
| `sequence` | `integer` | NOT NULL | `CHECK (>= 0)` | — |
| `role` | `message_role` | NOT NULL | | — |
| `status` | `message_status` | NOT NULL | | `'COMPLETE'` |
| `content` | `text` | NULL | | — |
| `metadata` | `jsonb` | NOT NULL | | `'{}'` |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `regenerated_from` | `uuid` | NULL | **FK** → `messages.id` `ON DELETE SET NULL` | — |
| `error_code` | `varchar(80)` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(conversation_id, sequence)`; `INDEX(conversation_id, created_at)`.
`regenerated_from` and `status='FAILED'` + `error_code` give **retry** and **regenerate** real
storage — `12 § 9` tests both and `13 § CHAT` requires regenerate.
`content` is nullable for a `PENDING`/`STREAMING` assistant row; `12 § 9` requires *"Verify no mock
response is returned"*, so a streaming row is persisted empty and filled, never pre-filled.

---

# 19. files

**Purpose:** an uploaded artifact. DIRECT. Soft-deletable.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `name` | `varchar(500)` | NOT NULL | | — |
| `mime_type` | `varchar(200)` | NOT NULL | | — |
| `size_bytes` | `bigint` | NOT NULL | `CHECK (> 0)` | — |
| `checksum_sha256` | `bytea` | NOT NULL | | — |
| `storage_key` | `text` | NOT NULL | **UNIQUE** | — |
| `status` | `file_status` | NOT NULL | | `'UPLOADING'` |
| `scan_result` | `scan_result` | NOT NULL | | `'PENDING'` |
| `scanned_at` | `timestamptz` | NULL | | — |
| `scanner_name` | `varchar(100)` | NULL | | — |
| `quarantined_at` | `timestamptz` | NULL | | — |
| `quarantine_reason` | `text` | NULL | | — |
| `extraction_error` | `text` | NULL | | — |
| `page_count` | `integer` | NULL | | — |
| `uploaded_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |
| `deleted_at` | `timestamptz` | NULL | | — |

**Indexes:** `UNIQUE(storage_key)`; `INDEX(tenant_id, project_id, status) WHERE deleted_at IS NULL`;
`INDEX(tenant_id, checksum_sha256)` — duplicate detection, tested by `12 § 10`.
`scan_result`, `quarantined_at`, `quarantine_reason` and `scanner_name` are added to satisfy
`11 § 8`'s *Security scan → Quarantine if required* and `12 § 10`'s *"Verify quarantine behavior."*
🟠 **D-26** — max upload size and the accepted MIME allow-list are not specified in any file, yet
`12 § 10` tests *oversized file* and *unsupported type*. See § 45.
🔵 The scanner itself is unspecified (`11 § 8` names the stage only).

---

# 20. file_chunks

**Purpose:** extracted, retrievable text. DERIVED via `files`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `file_id` | `uuid` | NOT NULL | **FK** → `files.id` `ON DELETE CASCADE` | — |
| `chunk_index` | `integer` | NOT NULL | `CHECK (>= 0)` | — |
| `content` | `text` | NOT NULL | | — |
| `token_count` | `integer` | NULL | | — |
| `page_from` | `integer` | NULL | | — |
| `page_to` | `integer` | NULL | | — |
| `metadata` | `jsonb` | NOT NULL | | `'{}'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(file_id, chunk_index)`.
`page_from`/`page_to` exist so `document_sources.source_location` (§ 36) can cite a real
location, satisfying `09 § 19`.
🔵 **Embeddings are not modelled.** `CLAUDE.md` lists *context assembly* and retrieval is implied,
but no specification defines an embedding model, dimension, or index type. Adding a `vector`
column would be inventing that contract. Retrieval over `file_chunks` is `STATUS = BLOCKED`
until a retrieval contract exists.

---

# 21. workflow_definitions

**Purpose:** a versioned, immutable **capability profile** over the fixed state machine in `05`.
DIRECT. See § 21.1 for why this is a profile and not a graph.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `definition_key` | `citext` | NOT NULL | | — |
| `name` | `varchar(200)` | NOT NULL | | — |
| `description` | `text` | NULL | | — |
| `version` | `varchar(20)` | NOT NULL | | — |
| `state_machine_id` | `varchar(40)` | NOT NULL | | `'REFYNE_CORE_V1'` |
| `capabilities` | `jsonb` | NOT NULL | | see below |
| `policy_id` | `uuid` | NULL | **FK** → `policies.id` `ON DELETE RESTRICT` | — |
| `status` | `definition_status` | NOT NULL | | `'DRAFT'` |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `published_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, definition_key, version)`;
`INDEX(tenant_id, status)`.
**Immutability:** a row with `status='PUBLISHED'` is immutable except `status → 'DEPRECATED'`.
A change publishes a new `version`. This mirrors `09 § 5`'s document rule and is what
`workflow.png`'s *v1.0 … v1.3* template versions require.

`capabilities` shape — exactly the flags `05` and `12 § 11` already require, no more:

```json
{
  "security_analysis_enabled":   true,
  "compliance_analysis_enabled": true,
  "risk_analysis_enabled":        true,
  "compliance_frameworks":       [],
  "document_types":              []
}
```

## 21.1 ✅ RESOLVED — DERIVED — D-02 fixed vs configurable

**The state graph is FIXED. Capability enablement is CONFIGURABLE.**

Evidence, all already in the repository:

| Source | Statement |
| --- | --- |
| `05` | Defines **exactly one** state machine, by name, with no authoring construct |
| `01 § Workflow` | *"configurable, conditional, stateful, retryable, auditable, human-in-the-loop"* |
| `05 § CONDITIONAL SECURITY/COMPLIANCE/RISK` | Branches are gated on *"If … enabled"* — i.e. flags |
| `12 § 11` Scenario B | *"Security disabled. Expected: Security agent does not execute."* |
| `12 § 11` Scenario C | *"Compliance disabled. Expected: Compliance agent does not execute."* |
| `13 § CONDITIONAL` | Same two conditions restated as acceptance criteria |
| `03 § 14` | Workflow detail **displays** *states, conditions, agents, enabled capabilities* — read-only |
| `workflow.png` | Five named templates at v1.0–v1.3 — versioned configurations |

Every occurrence of *"configurable"* in the repository is satisfied by capability flags plus
policy binding. **Nothing anywhere defines a node, edge, or graph-authoring construct.** So the
`definition` column of revision 1 is replaced by `capabilities` + `policy_id`, and
`state_machine_id` is a constant pointing at `05`.

## 21.2 🟠 DECISION REQUIRED — D-02b user-authored state graphs

**Question:** May a tenant author a **new state graph** (not merely a capability profile) in a
later release?

**Options already present in repository:** `03 § 13` states verbatim: *"Whether users may create
arbitrary workflows is: DECISION REQUIRED. The implementation must not expose workflow authoring
until the workflow architecture has been finalized."* `workflow.png` contains a template list with
All / My / Shared tabs, which is consistent with either answer.

**Why it affects implementation:** a graph interpreter and a fixed machine are different systems.
If the answer is later *yes*, `state_machine_id` becomes a discriminator and a `workflow_nodes` /
`workflow_edges` pair is added — additive. If a graph interpreter is built now, `05` becomes
unenforceable and `12 § 42.3` cannot be tested.

**Files affected:** `05`, `06 § 21`, `07 § WORKFLOWS`, `03 § 13`, `03 § 14`, `12 § 11`.

**What cannot proceed until decided:** the **Create / edit workflow** UI only. Running,
listing, versioning and viewing workflows are unblocked by § 21.1. Per `03 § 13`, authoring
**must not be exposed** in the interim.

---

# 22. workflow_runs

**Purpose:** one execution. DIRECT — `tenant_id` **added** (revision 1 omitted it while
`/workflow-runs/{id}` is a top-level path, an IDOR gap under `12 § 31`).

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `run_key` | `citext` | NOT NULL | | — |
| `workflow_definition_id` | `uuid` | NOT NULL | **FK** → `workflow_definitions.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `conversation_id` | `uuid` | NULL | **FK** → `conversations.id` `ON DELETE SET NULL` | — |
| `policy_version_id` | `uuid` | NOT NULL | **FK** → `policy_versions.id` `ON DELETE RESTRICT` | — |
| `capabilities_snapshot` | `jsonb` | NOT NULL | | — |
| `initiated_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `status` | `run_status` | NOT NULL | | `'RUNNING'` |
| `current_state` | `workflow_state` | NOT NULL | | `'CREATED'` |
| `resume_state` | `workflow_state` | NULL | | — |
| `data_availability` | `availability_state` | NULL | | — |
| `failure_code` | `varchar(80)` | NULL | | — |
| `failure_message` | `text` | NULL | | — |
| `started_at` | `timestamptz` | NOT NULL | | `now()` |
| `completed_at` | `timestamptz` | NULL | | — |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, run_key)`; `INDEX(tenant_id, project_id, status)`;
`INDEX(workflow_definition_id)`; `INDEX(current_state)`.
**Constraint:** `CHECK ((status IN ('COMPLETED','FAILED','REJECTED','CANCELLED')) = (completed_at IS NOT NULL))`.

`policy_version_id` and `capabilities_snapshot` freeze the governing configuration at start, so a
later policy edit cannot retroactively change a completed run — the same integrity guarantee
`09 § 7` gives documents.
`resume_state` is what `WAITING_FOR_INPUT` returns to (`05 § 5.15`), which is the column revision 1
lacked and the reason that state had no exit.
**There is no `progress_percent` column.** `workflow-running.png` shows *60%* and *"Estimated
completion Aug 26, 2026 10:45 AM"*; no specification defines how either is computed. `CLAUDE.md § 1`
forbids fake progress and `03 § 11` forbids a fabricated percentage. 🔵 **MISSING CONTRACT.**

---

# 23. workflow_steps

**Purpose:** one attempt at one state. DERIVED via `workflow_runs`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `workflow_run_id` | `uuid` | NOT NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `state` | `workflow_state` | NOT NULL | | — |
| `step_type` | `step_type` | NOT NULL | | — |
| `sequence` | `integer` | NOT NULL | `CHECK (>= 0)` | — |
| `attempt` | `integer` | NOT NULL | `CHECK (>= 1)` | `1` |
| `status` | `step_status` | NOT NULL | | `'PENDING'` |
| `skipped_reason` | `varchar(80)` | NULL | | — |
| `input` | `jsonb` | NULL | | — |
| `output` | `jsonb` | NULL | | — |
| `error_code` | `varchar(80)` | NULL | | — |
| `error` | `text` | NULL | | — |
| `retryable` | `boolean` | NULL | | — |
| `started_at` | `timestamptz` | NULL | | — |
| `completed_at` | `timestamptz` | NULL | | — |

**Indexes:** `UNIQUE(workflow_run_id, sequence)`;
`UNIQUE(workflow_run_id, state, attempt)`; `INDEX(workflow_run_id, status)`.
`attempt` is where **RETRY** lives: a retry inserts a new row for the same `state` with
`attempt = previous + 1`. This is why RETRY is a transition trigger and not a state (`05 § 4`).
`skipped_reason` records a disabled capability, so `12 § 11` Scenarios B and C are provable by
the absence of a `RUNNING` row and the presence of a `SKIPPED` one.

---

# 24. workflow_state_transitions — NEW

**Purpose:** the authoritative, append-only state history. DERIVED via `workflow_runs`.
Required by `03 § 15` (*state history*, *timeline*, *retry information*) and
`12 § 12` (*"Every permitted transition must have valid source state, valid target state,
condition, authorization, audit event where required"*).

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `workflow_run_id` | `uuid` | NOT NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `sequence` | `integer` | NOT NULL | `CHECK (>= 0)` | — |
| `from_state` | `workflow_state` | NULL | | — |
| `to_state` | `workflow_state` | NOT NULL | | — |
| `trigger` | `transition_trigger` | NOT NULL | | — |
| `condition_expression` | `text` | NULL | | — |
| `policy_rule_id` | `uuid` | NULL | **FK** → `policy_rules.id` `ON DELETE SET NULL` | — |
| `actor_type` | `actor_type` | NOT NULL | | — |
| `actor_id` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `source_step_id` | `uuid` | NULL | **FK** → `workflow_steps.id` `ON DELETE SET NULL` | — |
| `audit_event_id` | `uuid` | NULL | **FK** → `audit_events.id` `ON DELETE SET NULL` | — |
| `metadata` | `jsonb` | NOT NULL | | `'{}'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(workflow_run_id, sequence)`; `INDEX(workflow_run_id, created_at)`;
`INDEX(to_state)`.
**Append-only:** no `UPDATE` or `DELETE` grant. `from_state IS NULL` only for `sequence = 0`.
`policy_rule_id` is what makes `12 § 42.4` testable: a policy-driven transition points at the rule
that produced it.

---

# 25. workflow_events

**Purpose:** the realtime event log projected to the client. DERIVED via `workflow_runs`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `workflow_run_id` | `uuid` | NOT NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `sequence` | `bigint` | NOT NULL | `CHECK (>= 0)` | — |
| `event_type` | `varchar(80)` | NOT NULL | | — |
| `payload` | `jsonb` | NOT NULL | | `'{}'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(workflow_run_id, sequence)`.
`sequence` is the resume cursor for `GET /workflow-runs/{id}/events`. ✅ **D-17** (transport is SSE, `04 § 17.1`)
does not affect this table.

---

# 26. requirements

**Purpose:** a structured requirement. DIRECT — `tenant_id` **added** (`/requirements/{id}` is
top-level in `07`).

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `requirement_key` | `citext` | NOT NULL | | — |
| `version` | `integer` | NOT NULL | `CHECK (>= 1)` | `1` |
| `type` | `requirement_type` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `description` | `text` | NOT NULL | | — |
| `status` | `requirement_status` | NOT NULL | | `'DRAFT'` |
| `source_type` | `source_type` | NOT NULL | | — |
| `source_id` | `uuid` | NULL | | — |
| `source_location` | `varchar(200)` | NULL | | — |
| `confidence` | `numeric(4,3)` | NULL | `CHECK (BETWEEN 0 AND 1)` | — |
| `missing_information` | `jsonb` | NOT NULL | | `'[]'` |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, project_id, requirement_key, version)`;
`INDEX(project_id, type, status)`; `INDEX(project_id, requirement_key)`.
`version` is **added** and is mandatory: `09 § 7`'s source freeze cites *"Requirement BR-001
Version 3"* and cannot be stored without it. `confidence` is `numeric(4,3)` to hold `08 § 5`'s
`0.0`–`1.0` exactly. `missing_information` matches `08 § 5`'s array.
`requirement_key` format is 🟠 **D-09**; `08 § 5` illustrates `BR-001` but `09 § 6` forbids
hard-coding an identifier format before approval.

---

# 27. requirement_links

**Purpose:** requirement-to-requirement relationships. DERIVED via `requirements`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `source_requirement_id` | `uuid` | NOT NULL | **FK** → `requirements.id` `ON DELETE CASCADE` | — |
| `target_requirement_id` | `uuid` | NOT NULL | **FK** → `requirements.id` `ON DELETE CASCADE` | — |
| `relationship` | `link_relationship` | NOT NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(source_requirement_id, target_requirement_id, relationship)`;
`INDEX(target_requirement_id)`.
**Constraint:** `CHECK (source_requirement_id <> target_requirement_id)`.
This table carries **requirement↔requirement** edges only (`08 § 5` duplicate/ambiguity
detection). Cross-entity traceability is § 33, not here.

---

# 28. agent_runs

**Purpose:** one agent execution. DIRECT — `tenant_id` **added** (agent traces are a top-level
read in `04 § Agent Service`). Revision 1 could not store six of the fields `08` requires.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `workflow_run_id` | `uuid` | NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `workflow_step_id` | `uuid` | NULL | **FK** → `workflow_steps.id` `ON DELETE SET NULL` | — |
| `conversation_id` | `uuid` | NULL | **FK** → `conversations.id` `ON DELETE SET NULL` | — |
| `agent_type` | `agent_type` | NOT NULL | | — |
| `attempt` | `integer` | NOT NULL | `CHECK (>= 1)` | `1` |
| `status` | `agent_run_status` | NOT NULL | | `'RUNNING'` |
| `provider` | `varchar(60)` | NOT NULL | | — |
| `model` | `varchar(120)` | NOT NULL | | — |
| `model_configuration_id` | `uuid` | NULL | **FK** → `model_configurations.id` `ON DELETE SET NULL` | — |
| `configuration` | `jsonb` | NOT NULL | | `'{}'` |
| `prompt_template_id` | `uuid` | NULL | **FK** → `templates.id` `ON DELETE SET NULL` | — |
| `input` | `jsonb` | NULL | | — |
| `input_hash` | `bytea` | NOT NULL | | — |
| `output` | `jsonb` | NULL | | — |
| `validation_outcome` | `validation_outcome` | NULL | | — |
| `validation_run_id` | `uuid` | NULL | **FK** → `validation_runs.id` `ON DELETE SET NULL` | — |
| `error_code` | `varchar(80)` | NULL | | — |
| `error` | `text` | NULL | | — |
| `prompt_tokens` | `integer` | NULL | | — |
| `completion_tokens` | `integer` | NULL | | — |
| `duration_ms` | `integer` | NULL | | — |
| `started_at` | `timestamptz` | NOT NULL | | `now()` |
| `completed_at` | `timestamptz` | NULL | | — |

**Indexes:** `INDEX(tenant_id, workflow_run_id, started_at)`; `INDEX(agent_type, status)`;
`UNIQUE(workflow_step_id, attempt)` where `workflow_step_id IS NOT NULL`.

**Columns added versus revision 1, each traced to a requirement:**
`attempt`, `input_hash`, `error` (`08 § 15`); `provider`, `configuration`, `duration_ms`,
`prompt_tokens`, `completion_tokens`, `validation_outcome` (`08 § 16`); `tenant_id` (`11 § 3`);
`workflow_step_id`, `conversation_id`, `model_configuration_id`, `prompt_template_id`,
`validation_run_id`, `error_code` (referential completeness).
`input_hash` is `NOT NULL` because `08 § 15` requires it on **every** execution.
`08 § 16`: token usage is *"where available"*, hence nullable.

---

# 29. validation_runs

**Purpose:** one validation pass. DERIVED via `workflow_runs`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `workflow_run_id` | `uuid` | NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `workflow_step_id` | `uuid` | NULL | **FK** → `workflow_steps.id` `ON DELETE SET NULL` | — |
| `target_step_id` | `uuid` | NULL | **FK** → `workflow_steps.id` `ON DELETE SET NULL` | — |
| `document_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE CASCADE` | — |
| `validation_kind` | `validation_kind` | NOT NULL | | — |
| `status` | `validation_outcome` | NOT NULL | | — |
| `retryable` | `boolean` | NOT NULL | | `false` |
| `coverage` | `numeric(4,3)` | NULL | `CHECK (BETWEEN 0 AND 1)` | — |
| `errors` | `jsonb` | NOT NULL | | `'[]'` |
| `warnings` | `jsonb` | NOT NULL | | `'[]'` |
| `missing` | `jsonb` | NOT NULL | | `'[]'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `INDEX(workflow_run_id, created_at)`; `INDEX(document_version_id)`.
**Constraint:** `CHECK (workflow_run_id IS NOT NULL OR document_version_id IS NOT NULL)`.
`errors`, `warnings`, `missing`, `coverage` and `status` are exactly `08 § 10`'s output object.
**`target_step_id` is the column that fixes VALIDATION_FAILED routing:** it names the step whose
output failed, so the retry transition has a deterministic destination instead of `05`'s
*"appropriate previous state"*.

---

# 30. policies — NEW · policy_versions · policy_rules · policy_evaluations

Resolves **BL-4**. `04` names a *Policy Engine*, `05` has a `POLICY_EVALUATION` state, and
`08 §§ 8, 9, 10, 15` plus `09 § 15` defer to *"configured policy"* — with no store anywhere.

## 30.1 policies — DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `policy_key` | `citext` | NOT NULL | | — |
| `name` | `varchar(200)` | NOT NULL | | — |
| `scope_type` | `policy_scope_type` | NOT NULL | | — |
| `scope_id` | `uuid` | NULL | `CHECK (scope_type='TENANT') = (scope_id IS NULL)` | — |
| `active_version_id` | `uuid` | NULL | **FK** → `policy_versions.id` `ON DELETE SET NULL` | — |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, policy_key)`; `INDEX(tenant_id, scope_type, scope_id)`.

## 30.2 policy_versions — DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `policy_id` | `uuid` | NOT NULL | **FK** → `policies.id` `ON DELETE CASCADE` | — |
| `version` | `integer` | NOT NULL | `CHECK (>= 1)` | — |
| `status` | `policy_status` | NOT NULL | | `'DRAFT'` |
| `activated_at` | `timestamptz` | NULL | | — |
| `superseded_at` | `timestamptz` | NULL | | — |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(policy_id, version)`.
**Immutability:** a version with `status='ACTIVE'` or `'SUPERSEDED'` and its `policy_rules` are
immutable. An edit creates version + 1. This is what lets `workflow_runs.policy_version_id`
freeze the governing rules for the life of a run.

## 30.3 policy_rules — DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `policy_version_id` | `uuid` | NOT NULL | **FK** → `policy_versions.id` `ON DELETE CASCADE` | — |
| `rule_key` | `citext` | NOT NULL | | — |
| `value` | `jsonb` | NOT NULL | | — |
| `description` | `text` | NULL | | — |

**Indexes:** `UNIQUE(policy_version_id, rule_key)`.

### 30.4 The rule-key registry — every *"configured policy"* reference now resolves

Each row below is a place an existing specification defers to policy. **No `value` is supplied**
— the values are the open product decisions, listed in § 45.

| `rule_key` | Consumed by | Type | Value status |
| --- | --- | --- | --- |
| `retry.max_attempts.agent` | `08 § 15`, `05 § 5.9` | integer | 🟠 D-05 |
| `retry.max_attempts.document_validation` | `05 § 5.14` | integer | 🟠 D-05 |
| `retry.max_attempts.tool` | `10`, `11 § 17` | integer | 🟠 D-05 |
| `retry.backoff_strategy` | `CLAUDE.md § TECHNOLOGY` (retry) | enum | 🟠 D-05 |
| `retry.exhausted_action` | `08 § 10`, `12 § 11-G` | `HUMAN_REVIEW` \| `FAILED` | 🟠 D-05 |
| `risk.scoring_method` | `08 § 8`, `09 § 15` | enum | 🟠 D-06 |
| `risk.likelihood_weights` | `08 § 8` | object | 🟠 D-06 |
| `risk.severity_weights` | `08 § 8` | object | 🟠 D-06 |
| `risk.approval_threshold` | `05 § 5.10`, `12 § 11-E`, `13 § CONDITIONAL` | numeric | 🟠 D-06 |
| `approval.required` | `05 § 5.10` | boolean/expr | 🟠 D-04 |
| `approval.model` | `09 § 22`, `03 § 24` | `SINGLE` \| `SEQUENTIAL` \| `STAGED` | 🟠 D-04 |
| `approval.steps` | § 42 | array | 🟠 D-04 |
| `human_review.required` | `08 § 18`, `05 § 5.10` | boolean/expr | 🟠 D-04 |
| `human_review.escalation_role` | `05 § 5.11` ESCALATE | role key | 🟠 D-07 |
| `human_review.sla_hours` | `03 § 23` due date | integer | 🟠 D-04 |
| `data_availability.partial_action` | `08 § 9`, `03 § 16`, `05 § 5.7` | `CONTINUE` \| `WAIT` \| `HUMAN_REVIEW` | 🟠 **D-03** |
| `data_availability.required_sources` | `08 § 9` | array | 🟠 D-03 |
| `agent.allowed_tools.<agent_type>` | `08 § 14`, `11 § 16` | array of `tool_id` | 🟠 D-27 |
| `tool.requires_policy_approval.<tool_id>` | `11 § 18` | boolean | 🟠 D-27 |
| `validation.traceability_missing_action` | `12 § 19` | `FAILED` \| `WARNING` | 🟠 D-31 |
| `retention.documents_days` | `11 § 22` | integer | 🟠 D-16 |
| `retention.audit_days` | `11 § 22` | integer | 🟠 D-16 |
| `retention.files_days` | `11 § 22` | integer | 🟠 D-16 |
| `retention.deleted_resource_action` | `11 § 22` | enum | 🟠 D-16 |
| `quota.<quota_metric>` | § 43, `admin.png` | integer | 🟠 D-14 |
| `rate_limit.<operation_class>` | `11 § 12` | object | 🟠 D-11 |
| `waiting_for_input.timeout_hours` | `05 § 5.15` | integer | 🟠 D-29 |

**Missing-policy behaviour is specified, not chosen.** `08 § 8` already fixes it: *"If no risk
policy exists: BLOCKED / DECISION REQUIRED. Do not invent scoring rules."* Generalised in
`05 § 6`: a state whose transition requires an absent `rule_key` **must not guess**; the run
records the absent key and halts. This is why 🟠 rule values block implementation phases rather
than being silently defaulted.

## 30.5 policy_evaluations — DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `workflow_run_id` | `uuid` | NOT NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `workflow_step_id` | `uuid` | NULL | **FK** → `workflow_steps.id` `ON DELETE SET NULL` | — |
| `policy_version_id` | `uuid` | NOT NULL | **FK** → `policy_versions.id` `ON DELETE RESTRICT` | — |
| `rule_key` | `citext` | NOT NULL | | — |
| `input` | `jsonb` | NOT NULL | | — |
| `result` | `jsonb` | NOT NULL | | — |
| `decision` | `varchar(60)` | NOT NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `INDEX(workflow_run_id, created_at)`; `INDEX(rule_key)`.
Append-only. Makes `12 § 42.4` and `12 § 13` (*"Supervisor must not bypass policy"*) testable by
inspection rather than by inference.

---

# 31. risks

**Purpose:** an assessed risk. DIRECT — `tenant_id` **added**.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `risk_key` | `citext` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `description` | `text` | NOT NULL | | — |
| `likelihood` | `likelihood_level` | NOT NULL | | — |
| `severity` | `severity_level` | NOT NULL | | — |
| `score` | `numeric(6,2)` | NULL | | — |
| `scoring_method` | `varchar(60)` | NULL | | — |
| `policy_version_id` | `uuid` | NULL | **FK** → `policy_versions.id` `ON DELETE SET NULL` | — |
| `impact` | `text` | NULL | | — |
| `mitigation` | `text` | NULL | | — |
| `owner_user_id` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `status` | `risk_status` | NOT NULL | | `'OPEN'` |
| `source_type` | `source_type` | NOT NULL | | — |
| `source_id` | `uuid` | NULL | | — |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, project_id, risk_key)`; `INDEX(project_id, status, severity)`.
`score` is **nullable** and `scoring_method` + `policy_version_id` are recorded with it. This is
`08 § 8` enforced in the schema: with no risk policy, a risk may be stored with `likelihood` and
`severity` but **no score** — the platform cannot fabricate one. `impact`, `mitigation`,
`owner_user_id` and `scoring_method` are the columns revision 1 lacked against `09 § 15`'s
11 required fields.

---

# 32. security_findings · compliance_findings · evidence

## 32.1 security_findings — DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `finding_key` | `citext` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `description` | `text` | NOT NULL | | — |
| `severity` | `severity_level` | NOT NULL | | — |
| `control` | `varchar(120)` | NULL | | — |
| `affected_requirement_id` | `uuid` | NULL | **FK** → `requirements.id` `ON DELETE SET NULL` | — |
| `remediation` | `text` | NULL | | — |
| `status` | `finding_status` | NOT NULL | | `'OPEN'` |
| `verified` | `boolean` | NOT NULL | | `false` |
| `confidence` | `numeric(4,3)` | NULL | `CHECK (BETWEEN 0 AND 1)` | — |
| `source_type` | `source_type` | NOT NULL | | — |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, project_id, finding_key)`; `INDEX(project_id, status, severity)`.
`verified` is a separate boolean, not a status label, so the invariant in `08 § 6`
(*"The agent cannot claim verification without evidence"*), `03 § 18` and `12 § 42.26` can be
enforced as a database rule: **`verified = true` requires at least one `evidence` row linked to
this finding** (enforced by trigger; `evidence` cannot be a FK because the link is polymorphic).
`control`, `remediation`, `affected_requirement_id`, `verified` and `confidence` are the columns
revision 1 lacked against `09 § 16` and `08 § 6`.

## 32.2 compliance_findings — DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `finding_key` | `citext` | NOT NULL | | — |
| `framework` | `varchar(80)` | NOT NULL | | — |
| `control` | `varchar(120)` | NOT NULL | | — |
| `requirement_id` | `uuid` | NULL | **FK** → `requirements.id` `ON DELETE SET NULL` | — |
| `status` | `compliance_status` | NOT NULL | | `'UNVERIFIED'` |
| `gap` | `text` | NULL | | — |
| `remediation` | `text` | NULL | | — |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, project_id, framework, control)`; `INDEX(project_id, status)`.
Revision 1's free-text `evidence` column is **removed** and replaced by rows in § 32.3, because
`09 § 12` requires *"Every relationship must point to an actual stored entity"* and
`09 § 17`/`12 § 42.25` require evidence before a confirmed status. Trigger:
**`status='CONFORMANT'` requires ≥ 1 linked `evidence` row.**
🟠 **D-30** — the framework set is not specified anywhere; `08 § 7` says *"configured
frameworks"*. Stored as free text until decided. See § 45.

## 32.3 evidence — NEW, DIRECT

The seventh node of `09 § 12`'s chain. Without it, *"→ Evidence"* has no stored entity.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `evidence_key` | `citext` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `description` | `text` | NULL | | — |
| `source_type` | `source_type` | NOT NULL | | — |
| `source_id` | `uuid` | NULL | | — |
| `source_location` | `varchar(200)` | NULL | | — |
| `file_id` | `uuid` | NULL | **FK** → `files.id` `ON DELETE SET NULL` | — |
| `collected_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `collected_at` | `timestamptz` | NOT NULL | | `now()` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, project_id, evidence_key)`; `INDEX(project_id, source_type)`.
Evidence attaches to findings, risks, controls and test cases through
`traceability_relationships` (§ 33), never by free text.

---

# 33. design_elements · test_cases · test_case_results · traceability_relationships — NEW

Resolves **BL-8** and the storage half of 🟠 **D-19**.

## 33.1 design_elements — NEW, DIRECT

The **Design** node. `12 § 23`, `09 § 12`, `03 § 25` and `13 § TRACEABILITY` all require Design in
the chain; no entity existed anywhere in the repository.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `design_key` | `citext` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `description` | `text` | NULL | | — |
| `element_kind` | `varchar(60)` | NOT NULL | | — |
| `document_section_id` | `uuid` | NULL | **FK** → `document_sections.id` `ON DELETE SET NULL` | — |
| `source_type` | `source_type` | NOT NULL | | — |
| `source_id` | `uuid` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, project_id, design_key)`.
🔵 **MISSING CONTRACT — MC-03.** `element_kind` is `varchar`, not an enum, because **no
specification defines what a Design element is**. `09 § 18` lists *architecture, components,
APIs, database…* as things TECHNICAL_DOCUMENTATION *"can contain"* — that is not a design
taxonomy, and there is no design-authoring page, endpoint, or agent. The **entity now exists so
the chain is storable**, but the chain cannot be *populated* until the product owner defines
where design elements come from. See 🟠 D-19 in § 45.

## 33.2 test_cases — NEW, DIRECT

All 11 fields of `09 § 14`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `test_case_key` | `citext` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `objective` | `text` | NULL | | — |
| `preconditions` | `text` | NULL | | — |
| `steps` | `jsonb` | NOT NULL | | `'[]'` |
| `expected_result` | `text` | NOT NULL | | — |
| `test_level` | `varchar(40)` | NULL | | — |
| `priority` | `severity_level` | NULL | | — |
| `document_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE SET NULL` | — |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, project_id, test_case_key)`; `INDEX(project_id)`.
`steps` is an ordered array of `{ "index": int, "action": text, "data": text }`.
**`actual_result` and `status` are NOT on this table** — a test case is a definition and may be
executed many times. They live in § 33.3, which is why `test_case_results` is a separate entity.
`test_level` values come from `12 § 2`'s ten levels.

## 33.3 test_case_results — NEW, DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `test_case_id` | `uuid` | NOT NULL | **FK** → `test_cases.id` `ON DELETE CASCADE` | — |
| `executed_at` | `timestamptz` | NOT NULL | | `now()` |
| `executed_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `status` | `varchar(20)` | NOT NULL | `CHECK (IN ('PASSED','FAILED','BLOCKED','SKIPPED','NOT_RUN'))` | `'NOT_RUN'` |
| `actual_result` | `text` | NULL | | — |
| `notes` | `text` | NULL | | — |
| `evidence_id` | `uuid` | NULL | **FK** → `evidence.id` `ON DELETE SET NULL` | — |

**Indexes:** `INDEX(test_case_id, executed_at DESC)`.
🔵 Result **ingestion** has no contract — no endpoint, page, or CI hook is specified for entering
a result. `09 § 14` requires the field; nothing says who writes it.

## 33.4 traceability_relationships — NEW, DIRECT

The typed edge set for `09 § 12`'s chain. Replaces free-form strings, as
`12 § 42.13` requires.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `from_kind` | `trace_node_kind` | NOT NULL | | — |
| `from_id` | `uuid` | NOT NULL | | — |
| `to_kind` | `trace_node_kind` | NOT NULL | | — |
| `to_id` | `uuid` | NOT NULL | | — |
| `created_by_agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(project_id, from_kind, from_id, to_kind, to_id)`;
`INDEX(project_id, from_kind, from_id)`; `INDEX(project_id, to_kind, to_id)`.

**Allowed `(from_kind → to_kind)` pairs — the chain, enforced by `CHECK`:**

| From | To |
| --- | --- |
| `BUSINESS_REQUIREMENT` | `FUNCTIONAL_REQUIREMENT` |
| `FUNCTIONAL_REQUIREMENT` | `SRS_REQUIREMENT` |
| `SRS_REQUIREMENT` | `DESIGN_ELEMENT` |
| `DESIGN_ELEMENT` | `TEST_CASE` |
| `TEST_CASE` | `RISK` |
| `RISK` | `EVIDENCE` |
| `SRS_REQUIREMENT` | `TEST_CASE` |
| `FUNCTIONAL_REQUIREMENT` | `RISK` |
| `TEST_CASE` | `EVIDENCE` |
| `RISK` \| `SRS_REQUIREMENT` \| `FUNCTIONAL_REQUIREMENT` | `EVIDENCE` |

The first six rows are `09 § 12`'s chain **exactly and in order**. The last four are the shortcuts
`03 § 25`'s RTM columns require in order to render one row per requirement when an intermediate
node is absent. `BUSINESS_REQUIREMENT`, `FUNCTIONAL_REQUIREMENT` and `SRS_REQUIREMENT` all
resolve to `requirements.id`, discriminated by `requirements.type`.

**Referential integrity is enforced by trigger**, not FK, because `from_id`/`to_id` are
polymorphic. The trigger asserts the target row exists, is in the same `project_id`, and matches
`*_kind`. `12 § 42.11`, `§ 42.12` and `§ 42.13` test exactly this.

🟠 **D-19 remains open** on two points that this table cannot settle: (a) the authoritative RTM
**column set** — `03 § 25` lists 9, `rtm.png` shows 6, `12 § 23` names a 6-link chain and
`09 § 12` a 7-link one; (b) where `DESIGN_ELEMENT` rows come from (MC-03). See § 45.

---

# 34. documents

**Purpose:** the stable document identity. DIRECT — `tenant_id` **added**.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `document_key` | `citext` | NOT NULL | | — |
| `document_type` | `document_type` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `status` | `document_status` | NOT NULL | | `'DRAFT'` |
| `current_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE SET NULL` | — |
| `approved_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE SET NULL` | — |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, document_key)`;
`INDEX(tenant_id, document_type, status)` — serves `documents.png`'s global list with its
*All Types* / *All Status* filters; `INDEX(project_id, document_type)`;
`INDEX(tenant_id, updated_at DESC)` — the *Updated* sort column.

**One status column, not three.** `03 § 20` displays *status*, *validation status* and *approval
status* as three columns. Those are not three independent fields: `09 § 4`'s nine states already
encode validation (`VALIDATING`) and approval (`REVIEW`, `CHANGES_REQUESTED`, `APPROVED`,
`REJECTED`). The two derived columns are computed for display from
`document_versions.validation_run_id` and the live `approvals` row — never stored, per
`CLAUDE.md § 2`. `documents.png` displays a single *Status* column, which is consistent.

`approved_version_id` is the immutability anchor: once set it may only change to a **newer**
approved version, and the version it points at can never be updated (§ 35).

---

# 35. document_versions

**Purpose:** an immutable-once-approved snapshot. DERIVED via `documents`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `document_id` | `uuid` | NOT NULL | **FK** → `documents.id` `ON DELETE CASCADE` | — |
| `version_major` | `integer` | NOT NULL | `CHECK (>= 0)` | — |
| `version_minor` | `integer` | NOT NULL | `CHECK (>= 0)` | — |
| `version_label` | `varchar(20)` | NOT NULL | | generated |
| `status` | `document_status` | NOT NULL | | `'DRAFT'` |
| `generation_run_id` | `uuid` | NULL | **FK** → `generation_runs.id` `ON DELETE SET NULL` | — |
| `validation_run_id` | `uuid` | NULL | **FK** → `validation_runs.id` `ON DELETE SET NULL` | — |
| `supersedes_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE SET NULL` | — |
| `content_hash` | `bytea` | NULL | | — |
| `approved_at` | `timestamptz` | NULL | | — |
| `approved_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `frozen_at` | `timestamptz` | NULL | | — |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(document_id, version_major, version_minor)`;
`INDEX(document_id, created_at DESC)`.
`version_label` is `'v' || version_major || '.' || version_minor`, matching `09 § 5`'s
`v0.1 → v0.2 → v1.0 → v1.1` and the `v1.0`/`v0.3`/`v0.2`/`v0.1` values in `documents.png`.
Storing the pair rather than a string makes ordering correct and `12 § 24` testable.

**Immutability mechanism — resolves the enforcement gap.** `09 § 5` and `12 § 42.15` require it;
no mechanism existed. Three layers:
1. `frozen_at IS NOT NULL` ⇒ a `BEFORE UPDATE` trigger raises on any column change, and a
   `BEFORE DELETE` trigger raises unconditionally.
2. The same trigger guards `document_sections`, `document_sources` and `generation_run_sources`
   rows belonging to a frozen version.
3. `content_hash` is `sha256` over the canonical section serialisation, written at freeze time.
   `12 § 24`'s *"Verify v1.0 remains unchanged"* is a hash comparison, not an eyeball check.
Freezing happens on transition to `APPROVED`. `revoked`/un-approve does not exist: a change
creates `version_minor + 1`.

**`storage_key` is removed** from this table. One version has up to three renditions (`09 §§ 23–25`),
so a single key cannot represent them. See § 38.

---

# 36. document_sections · document_sources

## 36.1 document_sections — DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `document_version_id` | `uuid` | NOT NULL | **FK** → `document_versions.id` `ON DELETE CASCADE` | — |
| `section_key` | `citext` | NOT NULL | | — |
| `title` | `varchar(300)` | NOT NULL | | — |
| `order_index` | `integer` | NOT NULL | `CHECK (>= 1)` | — |
| `parent_section_id` | `uuid` | NULL | **FK** → `document_sections.id` `ON DELETE CASCADE` | — |
| `content` | `text` | NULL | | — |
| `provenance_state` | `varchar(20)` | NOT NULL | `CHECK (IN ('SOURCED','UNVERIFIED'))` | `'UNVERIFIED'` |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(document_version_id, section_key)`;
`UNIQUE(document_version_id, order_index)`; `INDEX(parent_section_id)`.
`order_index` plus the required section list in `09 §§ 8–18` is what makes `09 § 20`'s
*section order* check and `12 § 20`'s *section ordering* check executable.
`provenance_state='UNVERIFIED'` is `09 § 19`'s explicit fallback — a section with no
`document_sources` row is marked, never silently presented as sourced.

## 36.2 document_sources — DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `document_section_id` | `uuid` | NOT NULL | **FK** → `document_sections.id` `ON DELETE CASCADE` | — |
| `source_type` | `source_type` | NOT NULL | | — |
| `source_id` | `uuid` | NULL | | — |
| `source_version` | `varchar(40)` | NULL | | — |
| `source_location` | `varchar(200)` | NULL | | — |
| `excerpt` | `text` | NULL | | — |
| `metadata` | `jsonb` | NOT NULL | | `'{}'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `INDEX(document_section_id)`; `INDEX(source_type, source_id)`.
**`source_version` is added** — it is the second of `09 § 19`'s four required provenance fields and
was absent in revision 1, which is why source freeze was unstorable.

---

# 37. generation_runs · generation_run_sources — NEW

Resolves the storage gap behind `09 § 3` (*Source Version Freeze*) and `09 § 7`.

## 37.1 generation_runs — NEW, DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `generation_key` | `citext` | NOT NULL | | — |
| `project_id` | `uuid` | NOT NULL | **FK** → `projects.id` `ON DELETE CASCADE` | — |
| `document_id` | `uuid` | NULL | **FK** → `documents.id` `ON DELETE SET NULL` | — |
| `document_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE SET NULL` | — |
| `document_type` | `document_type` | NOT NULL | | — |
| `workflow_run_id` | `uuid` | NULL | **FK** → `workflow_runs.id` `ON DELETE SET NULL` | — |
| `template_id` | `uuid` | NULL | **FK** → `templates.id` `ON DELETE SET NULL` | — |
| `instructions` | `text` | NULL | | — |
| `status` | `generation_status` | NOT NULL | | `'QUEUED'` |
| `frozen_at` | `timestamptz` | NULL | | — |
| `attempt` | `integer` | NOT NULL | `CHECK (>= 1)` | `1` |
| `retry_of_id` | `uuid` | NULL | **FK** → `generation_runs.id` `ON DELETE SET NULL` | — |
| `error_code` | `varchar(80)` | NULL | | — |
| `error_message` | `text` | NULL | | — |
| `retryable` | `boolean` | NULL | | — |
| `request_id` | `varchar(80)` | NULL | | — |
| `requested_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `started_at` | `timestamptz` | NULL | | — |
| `completed_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, generation_key)`; `INDEX(project_id, status)`;
`INDEX(document_id)`.
`error_code`, `error_message`, `request_id`, `retryable` are exactly `09 § 28`'s four required
failure fields. `instructions` holds the generator's *additional instructions* field (`03 § 21`).

## 37.2 generation_run_sources — NEW, DERIVED

The frozen source set. One row per source, captured at `frozen_at`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `generation_run_id` | `uuid` | NOT NULL | **FK** → `generation_runs.id` `ON DELETE CASCADE` | — |
| `source_type` | `source_type` | NOT NULL | | — |
| `source_id` | `uuid` | NOT NULL | | — |
| `source_version` | `varchar(40)` | NULL | | — |
| `source_hash` | `bytea` | NULL | | — |
| `selected_by` | `varchar(20)` | NOT NULL | `CHECK (IN ('USER','SYSTEM'))` | — |

**Indexes:** `UNIQUE(generation_run_id, source_type, source_id)`.
Immutable after `generation_runs.frozen_at` is set. This is the table that makes
`09 § 7`'s example — *Requirement BR-001 Version 3 · Document DOC-001 · Generation Run GEN-001* —
an actual join rather than prose.

---

# 38. document_renditions — NEW, DERIVED

The rendered artifact per format. Required by `09 §§ 23–25` and `07`'s `/pdf`, `/docx` plus the
XLSX export; revision 1 had a single `storage_key` and so could hold only one.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `document_version_id` | `uuid` | NOT NULL | **FK** → `document_versions.id` `ON DELETE CASCADE` | — |
| `format` | `rendition_format` | NOT NULL | | — |
| `status` | `rendition_status` | NOT NULL | | `'PENDING'` |
| `storage_key` | `text` | NULL | **UNIQUE** | — |
| `size_bytes` | `bigint` | NULL | | — |
| `checksum_sha256` | `bytea` | NULL | | — |
| `page_count` | `integer` | NULL | | — |
| `renderer_version` | `varchar(40)` | NULL | | — |
| `error_code` | `varchar(80)` | NULL | | — |
| `rendered_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(document_version_id, format)`; `UNIQUE(storage_key)`.
`storage_key` is nullable only while `status IN ('PENDING','RENDERING','FAILED')`;
`CHECK ((status='READY') = (storage_key IS NOT NULL))`. This is how `09 § 26`
(*"The frontend must not generate fake download files"*) and `12 § 25` (*"actual PDF generated"*)
become enforceable: a download requires a `READY` row.

---

# 39. reviews · review_assignments · review_sections · review_comments — NEW

Resolves **BL-6**. All four entities are named by `09 § 21` and `03 § 23` and existed nowhere.

## 39.1 reviews — NEW, DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `review_key` | `citext` | NOT NULL | | — |
| `document_id` | `uuid` | NULL | **FK** → `documents.id` `ON DELETE CASCADE` | — |
| `document_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE CASCADE` | — |
| `workflow_run_id` | `uuid` | NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `target_step_id` | `uuid` | NULL | **FK** → `workflow_steps.id` `ON DELETE SET NULL` | — |
| `status` | `review_status` | NOT NULL | | `'PENDING'` |
| `priority` | `review_priority` | NOT NULL | | `'NORMAL'` |
| `due_at` | `timestamptz` | NULL | | — |
| `escalation_level` | `integer` | NOT NULL | `CHECK (>= 0)` | `0` |
| `sections_total` | `integer` | NOT NULL | `CHECK (>= 0)` | `0` |
| `sections_reviewed` | `integer` | NOT NULL | `CHECK (>= 0)` | `0` |
| `opened_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `completed_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, review_key)`; `INDEX(document_version_id)`;
`INDEX(workflow_run_id)`; `INDEX(tenant_id, status, due_at)`.
**Constraint:** `CHECK (document_version_id IS NOT NULL OR workflow_run_id IS NOT NULL)` and
`CHECK (sections_reviewed <= sections_total)`.
`sections_total` / `sections_reviewed` are maintained by trigger from § 39.3. They exist because
`review.png` renders a donut labelled *"3 of 5 sections reviewed"* and `03 § 29` plus
`12 § 42.22`/`§ 42.23` forbid a hard-coded UI count — the numbers must come from the backend.
`target_step_id` is the deterministic destination for `HUMAN_REQUEST_CHANGES`, replacing
`05`'s *"appropriate previous state"*.
`escalation_level` implements ESCALATE as a self-loop with a new assignment (`05 § 5.11`).

## 39.2 review_assignments — NEW, DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `review_id` | `uuid` | NOT NULL | **FK** → `reviews.id` `ON DELETE CASCADE` | — |
| `reviewer_user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `role_id` | `uuid` | NULL | **FK** → `roles.id` `ON DELETE SET NULL` | — |
| `assigned_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `assigned_at` | `timestamptz` | NOT NULL | | `now()` |
| `due_at` | `timestamptz` | NULL | | — |
| `priority` | `review_priority` | NOT NULL | | `'NORMAL'` |
| `status` | `assignment_status` | NOT NULL | | `'ASSIGNED'` |
| `escalation_level` | `integer` | NOT NULL | `CHECK (>= 0)` | `0` |
| `decision` | `review_status` | NULL | | — |
| `decided_at` | `timestamptz` | NULL | | — |
| `completed_at` | `timestamptz` | NULL | | — |

**Indexes:** `UNIQUE(review_id, reviewer_user_id, escalation_level)`;
`INDEX(reviewer_user_id, status)`.
Covers all eight facts `03 § 23` and `09 § 21` require: reviewer, role, assigned_by, due date,
priority, overall status, plus § 39.3 section status and § 39.4 comments.

## 39.3 review_sections — NEW, DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `review_id` | `uuid` | NOT NULL | **FK** → `reviews.id` `ON DELETE CASCADE` | — |
| `document_section_id` | `uuid` | NOT NULL | **FK** → `document_sections.id` `ON DELETE CASCADE` | — |
| `status` | `review_section_status` | NOT NULL | | `'PENDING'` |
| `reviewed_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `reviewed_at` | `timestamptz` | NULL | | — |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(review_id, document_section_id)`; `INDEX(review_id, status)`.
Satisfies `12 § 42.9` (*section-level review status is persisted*).

## 39.4 review_comments — NEW, DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `review_id` | `uuid` | NOT NULL | **FK** → `reviews.id` `ON DELETE CASCADE` | — |
| `document_section_id` | `uuid` | NULL | **FK** → `document_sections.id` `ON DELETE CASCADE` | — |
| `parent_comment_id` | `uuid` | NULL | **FK** → `review_comments.id` `ON DELETE CASCADE` | — |
| `author_user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `body` | `text` | NOT NULL | | — |
| `anchor` | `jsonb` | NULL | | — |
| `resolution` | `comment_resolution` | NOT NULL | | `'OPEN'` |
| `resolved_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `resolved_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `INDEX(review_id, created_at)`; `INDEX(document_section_id)`.
Satisfies `12 § 42.10`. `review.png` shows three section-anchored comments, which
`document_section_id` + `anchor` support.

---

# 40. approvals · approval_steps

Resolves the storage half of 🟠 **D-04**. Revision 1's single `approved_by` column could represent
only one of the three candidate models.

## 40.1 approvals — DIRECT, `tenant_id` added

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `approval_key` | `citext` | NOT NULL | | — |
| `document_id` | `uuid` | NULL | **FK** → `documents.id` `ON DELETE CASCADE` | — |
| `document_version_id` | `uuid` | NULL | **FK** → `document_versions.id` `ON DELETE CASCADE` | — |
| `workflow_run_id` | `uuid` | NULL | **FK** → `workflow_runs.id` `ON DELETE CASCADE` | — |
| `model` | `approval_step_mode` | NOT NULL | | — |
| `policy_version_id` | `uuid` | NOT NULL | **FK** → `policy_versions.id` `ON DELETE RESTRICT` | — |
| `status` | `approval_status` | NOT NULL | | `'PENDING'` |
| `current_step_order` | `integer` | NULL | | — |
| `steps_total` | `integer` | NOT NULL | `CHECK (>= 1)` | — |
| `steps_approved` | `integer` | NOT NULL | `CHECK (>= 0)` | `0` |
| `requested_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `decided_at` | `timestamptz` | NULL | | — |
| `comment` | `text` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |
| `lock_version` | `integer` | NOT NULL | | `0` |

**Indexes:** `UNIQUE(tenant_id, approval_key)`; `INDEX(document_version_id)`;
`INDEX(workflow_run_id)`; `INDEX(tenant_id, status)`.
**Constraint:** `CHECK (steps_approved <= steps_total)`;
`CHECK (document_version_id IS NOT NULL OR workflow_run_id IS NOT NULL)`.
`lock_version` is an optimistic-concurrency token — `12 § 35` requires *concurrent approval
attempts* to be race-free.
`steps_total` / `steps_approved` back `approval.png`'s *1/3* donut with real backend numbers.
Note that screen is internally inconsistent (donut reads 1 of 3 while all three chain rows read
*Pending*); the backend value is authoritative per `CLAUDE.md § 2`, and the inconsistency is a
canonical-UI defect recorded in `ARCHITECTURE_REVIEW.md`.

## 40.2 approval_steps — NEW, DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `approval_id` | `uuid` | NOT NULL | **FK** → `approvals.id` `ON DELETE CASCADE` | — |
| `step_order` | `integer` | NOT NULL | `CHECK (>= 1)` | — |
| `stage` | `varchar(60)` | NULL | | — |
| `mode` | `approval_step_mode` | NOT NULL | | `'SINGLE'` |
| `quorum` | `integer` | NOT NULL | `CHECK (>= 1)` | `1` |
| `approver_user_id` | `uuid` | NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `approver_role_id` | `uuid` | NULL | **FK** → `roles.id` `ON DELETE RESTRICT` | — |
| `status` | `approval_step_status` | NOT NULL | | `'PENDING'` |
| `decided_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `decision_comment` | `text` | NULL | | — |
| `decided_at` | `timestamptz` | NULL | | — |
| `due_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(approval_id, step_order)`; `INDEX(approver_user_id, status)`;
`INDEX(approver_role_id, status)`.
**Constraint:** `CHECK (approver_user_id IS NOT NULL OR approver_role_id IS NOT NULL)`.

**How all three candidate models map** — the point of this design, per the instruction to make the
model *capable of storing the approved model once selected*:

| Model | Representation |
| --- | --- |
| **Single approver** | `approvals.model='SINGLE'`, `steps_total=1`, one `approval_steps` row with `step_order=1, mode='SINGLE', quorum=1` |
| **Sequential chain** | `model='SEQUENTIAL'`, N rows with `step_order=1..N`; step *k* activates only when *k−1* is `APPROVED`; `current_step_order` tracks position |
| **Staged pipeline** | `model='STAGED'`, rows grouped by `stage`; every row in a stage shares `step_order`; `mode='QUORUM'`/`'UNANIMOUS'` with `quorum` deciding advancement |

`approval.png` shows a three-row chain, consistent with either of the latter two.
**No default is set**, no rows are seeded, and `approval.required` / `approval.model` /
`approval.steps` remain 🟠 D-04 in § 30.4. `08 § 18` is enforced by
`CHECK`: `decided_by` must reference a real user row, so an agent cannot impersonate approval.

---

# 41. tool_registry · tool_bindings · tool_calls

Resolves **BL-7**. `11 § 16` names seven fields; nothing stored them.

## 41.1 tool_registry — NEW, GLOBAL

A platform-level catalogue. GLOBAL because a tool is code, not tenant data; per-tenant
enable/disable is § 41.2.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tool_id` | `citext` | NOT NULL | **UNIQUE** | — |
| `name` | `varchar(160)` | NOT NULL | | — |
| `description` | `text` | NOT NULL | | — |
| `integration_type` | `integration_type` | NULL | | — |
| `input_schema` | `jsonb` | NOT NULL | | — |
| `output_schema` | `jsonb` | NOT NULL | | — |
| `allowed_agents` | `agent_type[]` | NOT NULL | `CHECK (cardinality >= 1)` | — |
| `required_permissions` | `citext[]` | NOT NULL | `CHECK (cardinality >= 1)` | — |
| `risk_level` | `tool_risk_level` | NOT NULL | | — |
| `enabled` | `boolean` | NOT NULL | | `false` |
| `version` | `varchar(20)` | NOT NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tool_id)`; `INDEX(integration_type, enabled)`.
`enabled` defaults to **`false`** — `11 § 2` is *"Default deny"* and `11 § 27` is *"If permission
is not explicitly granted: DENY."* A newly deployed tool is inert until explicitly enabled.
`allowed_agents` and `required_permissions` are array columns so the check is a single query with
no join, which matters because it runs on every tool request.

**Seed — the nine tools the integration specifications already define.** `10` states the
capabilities; `07` already exposes six of the paths. No tool is invented here.

| `tool_id` | Source | `risk_level` | `required_permissions` |
| --- | --- | --- | --- |
| `jira.issue.search` | `10 § JIRA` *search issues* | `READ` | `INTEGRATION_READ` |
| `jira.issue.get` | `10 § JIRA` *retrieve issue* | `READ` | `INTEGRATION_READ` |
| `jira.issue.create` | `10 § JIRA` *create issue* | `HIGH_WRITE` | `INTEGRATION_MANAGE` |
| `jira.issue.update` | `10 § JIRA` *update issue where permitted* | `HIGH_WRITE` | `INTEGRATION_MANAGE` |
| `jira.issue.link` | `10 § JIRA` *attach links* | `LOW_WRITE` | `INTEGRATION_MANAGE` |
| `confluence.search` | `10 § CONFLUENCE` *search* | `READ` | `INTEGRATION_READ` |
| `confluence.page.get` | `10 § CONFLUENCE` *retrieve pages* | `READ` | `INTEGRATION_READ` |
| `notion.search` | `10 § NOTION` *search* | `READ` | `INTEGRATION_READ` |
| `notion.page.get` | `10 § NOTION` *retrieve authorized pages* | `READ` | `INTEGRATION_READ` |

**Confluence and Notion are read-only** — `10` grants them *search* and *retrieve* only, and
`11 §§ 19–20` restrict them to authorized retrieval. No write tool exists for either.
`allowed_agents` per tool is 🟠 **D-27** (§ 30.4): `11 § 16` requires the field, and nothing in the
repository states which agent may call which tool. Until D-27 is answered every
`allowed_agents` array is empty and, by `11 § 27`, **every tool request is denied** — the safe
posture, and the reason implementation phase 13 is blocked rather than guessed.

## 41.2 tool_bindings — NEW, DIRECT

Per-tenant enablement, backing `03 § 28`'s administrative control over tools and `ADMIN_TOOLS`.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `tool_registry_id` | `uuid` | NOT NULL | **FK** → `tool_registry.id` `ON DELETE CASCADE` | — |
| `integration_id` | `uuid` | NULL | **FK** → `integrations.id` `ON DELETE CASCADE` | — |
| `enabled` | `boolean` | NOT NULL | | `false` |
| `updated_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, tool_registry_id)`.
A tool is callable only when `tool_registry.enabled` **and** `tool_bindings.enabled` are both
true **and** the binding's `integration_id` is `CONNECTED`. Absence of a binding row is denial
(`11 § 27`) — this is what returns `10`'s *"Jira is not connected."* instead of a fabricated
result.

## 41.3 tool_calls — DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `user_id` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `agent_run_id` | `uuid` | NULL | **FK** → `agent_runs.id` `ON DELETE SET NULL` | — |
| `workflow_run_id` | `uuid` | NULL | **FK** → `workflow_runs.id` `ON DELETE SET NULL` | — |
| `tool_id` | `citext` | NOT NULL | | — |
| `tool_registry_id` | `uuid` | NULL | **FK** → `tool_registry.id` `ON DELETE SET NULL` | — |
| `status` | `tool_call_status` | NOT NULL | | `'REQUESTED'` |
| `denied_stage` | `varchar(40)` | NULL | | — |
| `denied_reason` | `text` | NULL | | — |
| `input` | `jsonb` | NULL | | — |
| `output` | `jsonb` | NULL | | — |
| `attempt` | `integer` | NOT NULL | `CHECK (>= 1)` | `1` |
| `external_ref` | `varchar(200)` | NULL | | — |
| `duration_ms` | `integer` | NULL | | — |
| `request_id` | `varchar(80)` | NULL | | — |
| `audit_event_id` | `uuid` | NULL | **FK** → `audit_events.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `completed_at` | `timestamptz` | NULL | | — |

**Indexes:** `INDEX(tenant_id, created_at DESC)`; `INDEX(tool_id, status)`;
`INDEX(agent_run_id)`.
`tool_registry_id` is **nullable** precisely so an **unregistered** tool request is still
recorded, with `status='DENIED_UNREGISTERED'`. `11 § 16`: *"Unknown tools must be rejected"* —
rejected **and** logged.
**This closes 🟠 D-22.** `11 § 15` requires *"audit records any attempted tool request where
applicable"*; the `tool_call_status` enum in § 3 gives one label per rejecting stage of `11 § 17`'s
eleven-stage chain, so a blocked request produces a durable row plus a
`TOOL_REQUEST_DENIED` audit event (`11 § 21.2`). The prompt-injection test in `11 § 15` /
`12 § 30` therefore asserts two things instead of one: **no Jira write occurred**, and **a
`DENIED_*` row exists**.

---

# 42. integrations · integration_credentials

## 42.1 integrations — DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `type` | `integration_type` | NOT NULL | | — |
| `status` | `integration_status` | NOT NULL | | `'DISCONNECTED'` |
| `display_name` | `varchar(160)` | NULL | | — |
| `external_account_id` | `varchar(200)` | NULL | | — |
| `base_url` | `text` | NULL | | — |
| `configuration` | `jsonb` | NOT NULL | | `'{}'` |
| `scopes` | `citext[]` | NOT NULL | | `'{}'` |
| `connected_by` | `uuid` | NULL | **FK** → `users.id` `ON DELETE SET NULL` | — |
| `connected_at` | `timestamptz` | NULL | | — |
| `last_checked_at` | `timestamptz` | NULL | | — |
| `last_error_code` | `varchar(80)` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, type, external_account_id)`; `INDEX(tenant_id, status)`.
**`configuration` must contain no secret.** Revision 1 kept credentials here with only a prose
warning; § 42.2 separates them, which is what `11 § 9` (*"Integration credentials must be
encrypted/protected at rest"*) requires structurally.
`last_checked_at` / `last_error_code` back the **Test Connection** action in `03 § 26`.

## 42.2 integration_credentials — NEW, DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `integration_id` | `uuid` | NOT NULL | **FK** → `integrations.id` `ON DELETE CASCADE` | — |
| `kind` | `credential_kind` | NOT NULL | | — |
| `access_token_ciphertext` | `bytea` | NOT NULL | | — |
| `refresh_token_ciphertext` | `bytea` | NULL | | — |
| `key_id` | `varchar(80)` | NOT NULL | | — |
| `algorithm` | `varchar(40)` | NOT NULL | | — |
| `expires_at` | `timestamptz` | NULL | | — |
| `rotated_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(integration_id, kind)`; `INDEX(expires_at)`.
Ciphertext only. `key_id` names the key in the secrets manager (`11 § 9` production path); the
key material is never in this database, never in source, and never in a log or prompt.
No `SELECT` grant to the general application role — only the Integration Service may read it.
🔵 **MISSING CONTRACT — MC-04.** Confluence and Notion authentication methods are unspecified:
`10` gives Jira *"OAuth-based integration"* and says nothing for the other two. `credential_kind`
admits both shapes so the schema is not blocking, but phases 15 and 16 cannot start.

---

# 43. audit_events

**Purpose:** the security and business record. DIRECT with a nullable tenant.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NULL | **FK** → `tenants.id` `ON DELETE RESTRICT` | — |
| `event_type` | `citext` | NOT NULL | `CHECK (event_type = upper(event_type))` | — |
| `actor_type` | `actor_type` | NOT NULL | | — |
| `actor_id` | `uuid` | NULL | | — |
| `actor_label` | `varchar(200)` | NULL | | — |
| `resource_type` | `varchar(60)` | NULL | | — |
| `resource_id` | `uuid` | NULL | | — |
| `resource_key` | `citext` | NULL | | — |
| `project_id` | `uuid` | NULL | **FK** → `projects.id` `ON DELETE SET NULL` | — |
| `outcome` | `varchar(20)` | NOT NULL | `CHECK (IN ('SUCCEEDED','DENIED','FAILED'))` | — |
| `request_id` | `varchar(80)` | NULL | | — |
| `session_id` | `uuid` | NULL | **FK** → `sessions.id` `ON DELETE SET NULL` | — |
| `ip_address` | `inet` | NULL | | — |
| `metadata` | `jsonb` | NOT NULL | | `'{}'` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `INDEX(tenant_id, created_at DESC)`;
`INDEX(tenant_id, resource_type, resource_id)`; `INDEX(tenant_id, event_type, created_at DESC)`;
`INDEX(actor_id, created_at DESC)`; `INDEX(request_id)`.

Carries all seven fields `11 § 21` and `12 § 32` require — actor, tenant, action (`event_type`),
resource, timestamp, request ID, metadata — plus `outcome`, without which a **denied**
authorization (`11 § 21`, *failed authorization*) could not be distinguished from a successful one.
`tenant_id` is nullable **only** for pre-tenant events (`AUTH_LOGIN_FAILED`,
`AUTH_PASSWORD_RESET_REQUESTED`); a `CHECK` requires it non-null for every other event class.
`actor_id` is not an FK because `actor_type` may be `SYSTEM`, `AGENT` or `INTEGRATION`.
**Append-only:** no `UPDATE` or `DELETE` grant to the application role; deletion happens only
through the retention job under `retention.audit_days` (🟠 D-16).

**The authoritative event catalogue is `11 § 21.2`** — one canonical name per mutating action,
closing **BL-10 / D-23**. It is deliberately not duplicated here; `event_type` is validated
against it at write time and by `12 § 32`.

🔵 **MISSING CONTRACT — MC-05.** `11 § 26` requires audit evidence to be *preserved*; no
specification defines tamper-evidence (hash chain, WORM storage, or external sink). Append-only
grants are necessary but not sufficient. Named, not invented.

---

# 44. notifications · quotas · quota_usage · model_configurations · templates · jobs

## 44.1 notifications — DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `user_id` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE CASCADE` | — |
| `type` | `varchar(80)` | NOT NULL | | — |
| `resource_type` | `varchar(60)` | NULL | | — |
| `resource_id` | `uuid` | NULL | | — |
| `payload` | `jsonb` | NOT NULL | | `'{}'` |
| `read_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `INDEX(user_id, read_at, created_at DESC)`.
🔵 **MISSING CONTRACT.** No page, endpoint, or trigger set is specified for notifications
anywhere in `02`, `03` or `07`. The table is retained from revision 1 and completed, but the
feature is `STATUS = BLOCKED` per `12 § 43`.

## 44.2 quotas — NEW, DIRECT

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `metric` | `quota_metric` | NOT NULL | | — |
| `limit_value` | `bigint` | NOT NULL | `CHECK (>= 0)` | — |
| `period` | `varchar(20)` | NOT NULL | `CHECK (IN ('TOTAL','DAY','MONTH'))` | — |
| `enforced` | `boolean` | NOT NULL | | `false` |
| `policy_version_id` | `uuid` | NULL | **FK** → `policy_versions.id` `ON DELETE SET NULL` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, metric, period)`.
The seven `quota_metric` labels are exactly the seven tiles in `admin.png` — *Users, Projects,
Workflows, Documents, Storage 245 GB / 1 TB, API Usage 12,430 / 100,000, Active Users*.
**No `limit_value` is seeded.** `1 TB` and `100,000` are illustrative values in a mockup;
`CLAUDE.md § 1` forbids presenting demo data as production data. 🟠 **D-14**.
`enforced` defaults to `false` so no request is rejected by an unconfigured quota.

## 44.3 quota_usage — NEW, DERIVED

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `quota_id` | `uuid` | NOT NULL | **FK** → `quotas.id` `ON DELETE CASCADE` | — |
| `period_start` | `date` | NOT NULL | | — |
| `used_value` | `bigint` | NOT NULL | `CHECK (>= 0)` | `0` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(quota_id, period_start)`.

## 44.4 model_configurations — NEW, DIRECT

Backs `08 § 16` (*"Models must be configurable through the model/provider layer"*) and `03 § 28`'s
administrative control over models.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `agent_type` | `agent_type` | NULL | | — |
| `provider` | `varchar(60)` | NOT NULL | | — |
| `model` | `varchar(120)` | NOT NULL | | — |
| `parameters` | `jsonb` | NOT NULL | | `'{}'` |
| `is_default` | `boolean` | NOT NULL | | `false` |
| `enabled` | `boolean` | NOT NULL | | `true` |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, agent_type) WHERE is_default`; `INDEX(tenant_id, enabled)`.
`agent_type IS NULL` is the tenant-wide fallback. No provider or model name is seeded —
`08 § 16`: *"Do not hard-code a provider-specific implementation into agent logic."*
Values come from environment configuration (`CLAUDE.md § SECRETS`), never from source.

## 44.5 templates — NEW, DIRECT

Backs `03 § 28`'s administrative control over templates.

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `template_key` | `citext` | NOT NULL | | — |
| `kind` | `template_kind` | NOT NULL | | — |
| `document_type` | `document_type` | NULL | | — |
| `agent_type` | `agent_type` | NULL | | — |
| `version` | `integer` | NOT NULL | `CHECK (>= 1)` | `1` |
| `body` | `text` | NOT NULL | | — |
| `variables` | `jsonb` | NOT NULL | | `'[]'` |
| `status` | `definition_status` | NOT NULL | | `'DRAFT'` |
| `created_by` | `uuid` | NOT NULL | **FK** → `users.id` `ON DELETE RESTRICT` | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, template_key, version)`; `INDEX(tenant_id, kind, status)`.
`PUBLISHED` rows are immutable; an edit creates version + 1. This is the prompt registry
`CLAUDE.md § TECHNOLOGY` requires, and it is why `agent_runs.prompt_template_id` can be resolved
for a past run.

## 44.6 jobs · job_attempts — NEW

`CLAUDE.md § TECHNOLOGY` requires *"background job queue, retry, dead-letter handling"* and
`04 § ASYNC ARCHITECTURE` requires the queue; no entity existed. Dead-letter handling requires
durable storage regardless of broker.

**jobs — DIRECT**

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `tenant_id` | `uuid` | NOT NULL | **FK** → `tenants.id` `ON DELETE CASCADE` | — |
| `job_type` | `varchar(80)` | NOT NULL | | — |
| `idempotency_key` | `citext` | NULL | | — |
| `payload` | `jsonb` | NOT NULL | | — |
| `status` | `job_status` | NOT NULL | | `'QUEUED'` |
| `attempt` | `integer` | NOT NULL | `CHECK (>= 0)` | `0` |
| `max_attempts` | `integer` | NOT NULL | `CHECK (>= 1)` | — |
| `run_after` | `timestamptz` | NOT NULL | | `now()` |
| `resource_type` | `varchar(60)` | NULL | | — |
| `resource_id` | `uuid` | NULL | | — |
| `last_error` | `text` | NULL | | — |
| `dead_lettered_at` | `timestamptz` | NULL | | — |
| `created_at` | `timestamptz` | NOT NULL | | `now()` |
| `updated_at` | `timestamptz` | NOT NULL | | `now()` |

**Indexes:** `UNIQUE(tenant_id, idempotency_key)` where not null;
`INDEX(status, run_after)`; `INDEX(tenant_id, job_type, status)`.
`max_attempts` has **no default** — it is bound from `retry.max_attempts.*` (🟠 D-05).

**job_attempts — DERIVED**

| Column | Type | Null | Key / Constraint | Default |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL | **PK** | `gen_random_uuid()` |
| `job_id` | `uuid` | NOT NULL | **FK** → `jobs.id` `ON DELETE CASCADE` | — |
| `attempt` | `integer` | NOT NULL | `CHECK (>= 1)` | — |
| `worker_id` | `varchar(120)` | NULL | | — |
| `started_at` | `timestamptz` | NOT NULL | | `now()` |
| `finished_at` | `timestamptz` | NULL | | — |
| `outcome` | `varchar(20)` | NULL | `CHECK (IN ('SUCCEEDED','FAILED','TIMEOUT'))` | — |
| `error` | `text` | NULL | | — |

**Indexes:** `UNIQUE(job_id, attempt)`.
🔵 The **broker** is unnamed in every specification. These tables are the durable record; if a
broker-native DLQ is chosen, `jobs` remains the queryable projection. The technology choice does
not block the schema.

---

# 45. OPEN DECISIONS AFFECTING THIS SCHEMA

Every item below is a **product decision**. None is decided in this file. Each blocks a
`policy_rules.value`, a seed row, or a column type — not a table's existence, so the schema is
complete and the migration can be authored the moment D-01 is answered.

| ID | Question | Options in repository | Affects |
| --- | --- | --- | --- |
| **D-01** | Tenant isolation strategy | `11 § 3`: app filtering / RLS / schema-per-tenant | § 2.3 — the first migration |
| **D-02b** | User-authored state graphs | `03 § 13` | § 21.2 — authoring UI only |
| **D-03** | PARTIAL behaviour | `08 § 9`, `03 § 16`: continue / wait / human review | `data_availability.partial_action` |
| **D-04** | Approval model | `09 § 22`, `03 § 24`: single / sequential / staged | `approval.*` rules, `approval_steps` seed |
| **D-05** | Retry policy | `08 § 15`, `12 § 11-G` | 5 `retry.*` rules, `jobs.max_attempts` |
| **D-06** | Risk scoring policy | `08 § 8`, `09 § 15` | 4 `risk.*` rules, `risks.score` |
| **D-09** | Identifier formats | `09 § 6`; `08 § 5` illustrates `BR-001` | 11 `*_key` columns |
| **D-11** | Rate limits | `11 § 12`'s 7 operation classes | `rate_limit.*` rules |
| **D-13** | Role assignment model | `11 § 6`'s six required definitions | `roles` seed, `user_roles`, `permissions` gap MC-02 |
| **D-14** | Quota model | `admin.png`'s 7 tiles | `quotas.limit_value` |
| **D-16** | Retention periods | `11 § 22`'s 4 categories | 4 `retention.*` rules, `deleted_at` sweep |
| **D-19** | RTM columns; Design provenance | `03 § 25` 9 cols / `rtm.png` 6 / `09 § 12` 7 links / `12 § 23` 6 | § 33.4 shortcuts, MC-03 |
| **D-20** | Mandatory consent kinds | `03 § 6`; `register.png` shows one pre-checked box | § 14 seed |
| **D-25** | Session / token / reset TTLs | `11 § 7` requires expiry, no duration | §§ 11–13 |
| **D-26** | Max upload size; MIME allow-list | `12 § 10` tests both, no values | § 19 |
| **D-27** | Per-agent tool allow-list | `11 § 16` requires the field, no mapping | `tool_registry.allowed_agents` |
| **D-29** | WAITING_FOR_INPUT timeout | none — the state exists with no expiry | `waiting_for_input.timeout_hours` |
| **D-30** | Compliance framework set | `08 § 7` *"configured frameworks"* | § 32.2 `framework` |
| **D-31** | Missing-traceability action | `12 § 19`: FAILED or warning | `validation.traceability_missing_action` |

**Missing contracts recorded, not resolved:** MC-02 permission catalogue ·
MC-03 Design element provenance · MC-04 Confluence/Notion auth · MC-05 audit tamper-evidence ·
SSO identity model (§ 5) · embeddings/retrieval (§ 20) · workflow progress metric (§ 22) ·
test-result ingestion (§ 33.3) · notifications (§ 44.1) · job broker (§ 44.6).

---

# 46. TABLE INVENTORY

**64 tables.** 32 carried forward from revision 1 (all now fully typed), 32 added.

Tenancy classes: 1 ROOT · 5 GLOBAL · 32 DIRECT · 26 DERIVED. Tenant-owned = 58 (§ 2.2).

| # | Table | § | Tenancy | New |
| --- | --- | --- | --- | --- |
| 1 | `tenants` | 4 | ROOT | |
| 2 | `users` | 5 | GLOBAL | |
| 3 | `tenant_members` | 6 | DIRECT | |
| 4 | `roles` | 7 | DIRECT | |
| 5 | `permissions` | 8 | GLOBAL | |
| 6 | `role_permissions` | 9 | DERIVED | |
| 7 | `user_roles` | 10 | DIRECT | ✚ |
| 8 | `sessions` | 11 | DIRECT | ✚ |
| 9 | `refresh_tokens` | 12 | DERIVED | ✚ |
| 10 | `password_reset_tokens` | 13 | GLOBAL | ✚ |
| 11 | `consents` | 14 | GLOBAL | ✚ |
| 12 | `projects` | 15 | DIRECT | |
| 13 | `project_members` | 16 | DERIVED | |
| 14 | `conversations` | 17 | DIRECT | |
| 15 | `messages` | 18 | DERIVED | |
| 16 | `files` | 19 | DIRECT | |
| 17 | `file_chunks` | 20 | DERIVED | |
| 18 | `workflow_definitions` | 21 | DIRECT | |
| 19 | `workflow_runs` | 22 | DIRECT | |
| 20 | `workflow_steps` | 23 | DERIVED | |
| 21 | `workflow_state_transitions` | 24 | DERIVED | ✚ |
| 22 | `workflow_events` | 25 | DERIVED | |
| 23 | `requirements` | 26 | DIRECT | |
| 24 | `requirement_links` | 27 | DERIVED | |
| 25 | `agent_runs` | 28 | DIRECT | |
| 26 | `validation_runs` | 29 | DERIVED | |
| 27 | `policies` | 30.1 | DIRECT | ✚ |
| 28 | `policy_versions` | 30.2 | DERIVED | ✚ |
| 29 | `policy_rules` | 30.3 | DERIVED | ✚ |
| 30 | `policy_evaluations` | 30.5 | DERIVED | ✚ |
| 31 | `risks` | 31 | DIRECT | |
| 32 | `security_findings` | 32.1 | DIRECT | |
| 33 | `compliance_findings` | 32.2 | DIRECT | |
| 34 | `evidence` | 32.3 | DIRECT | ✚ |
| 35 | `design_elements` | 33.1 | DIRECT | ✚ |
| 36 | `test_cases` | 33.2 | DIRECT | ✚ |
| 37 | `test_case_results` | 33.3 | DERIVED | ✚ |
| 38 | `traceability_relationships` | 33.4 | DIRECT | ✚ |
| 39 | `documents` | 34 | DIRECT | |
| 40 | `document_versions` | 35 | DERIVED | |
| 41 | `document_sections` | 36.1 | DERIVED | |
| 42 | `document_sources` | 36.2 | DERIVED | |
| 43 | `generation_runs` | 37.1 | DIRECT | ✚ |
| 44 | `generation_run_sources` | 37.2 | DERIVED | ✚ |
| 45 | `document_renditions` | 38 | DERIVED | ✚ |
| 46 | `reviews` | 39.1 | DIRECT | ✚ |
| 47 | `review_assignments` | 39.2 | DERIVED | ✚ |
| 48 | `review_sections` | 39.3 | DERIVED | ✚ |
| 49 | `review_comments` | 39.4 | DERIVED | ✚ |
| 50 | `approvals` | 40.1 | DIRECT | |
| 51 | `approval_steps` | 40.2 | DERIVED | ✚ |
| 52 | `tool_registry` | 41.1 | GLOBAL | ✚ |
| 53 | `tool_bindings` | 41.2 | DIRECT | ✚ |
| 54 | `tool_calls` | 41.3 | DIRECT | |
| 55 | `integrations` | 42.1 | DIRECT | |
| 56 | `integration_credentials` | 42.2 | DERIVED | ✚ |
| 57 | `audit_events` | 43 | DIRECT (nullable) | |
| 58 | `notifications` | 44.1 | DIRECT | |
| 59 | `quotas` | 44.2 | DIRECT | ✚ |
| 60 | `quota_usage` | 44.3 | DERIVED | ✚ |
| 61 | `model_configurations` | 44.4 | DIRECT | ✚ |
| 62 | `templates` | 44.5 | DIRECT | ✚ |
| 63 | `jobs` | 44.6 | DIRECT | ✚ |
| 64 | `job_attempts` | 44.6 | DERIVED | ✚ |

**All 20 entities named by the architecture review are present:**
`test_cases` 36 · `traceability_relationships` 38 · Design entity (`design_elements`) 35 ·
`reviews` 46 · `review_assignments` 47 · `review_sections` 48 · `review_comments` 49 ·
`approval_steps` 51 · `policies` 27 · `tool_registry` 52 · `model_configurations` 61 ·
`templates` 62 · `generation_runs` 43 · `sessions` 8 · `refresh_tokens` 9 ·
`password_reset_tokens` 10 · `consents` 11 · `workflow_state_transitions` 21 · `quotas` 59 ·
`test_case_results` 37.

**Plus 12 further entities the traceability, document, policy and async requirements needed:**
`user_roles`, `policy_versions`, `policy_rules`, `policy_evaluations`, `evidence`,
`generation_run_sources`, `document_renditions`, `tool_bindings`, `integration_credentials`,
`quota_usage`, `jobs`, `job_attempts`.

**The 15 tables whose columns were incomplete are all resolved:**
`workflow_runs` (+9) · `requirements` (+`version`, +`tenant_id`, +5) · `agent_runs` (+16) ·
`validation_runs` (+8) · `risks` (+5) · `security_findings` (+5) · `compliance_findings`
(evidence → `evidence` rows, +3) · `documents` (+`tenant_id`, +`approved_version_id`) ·
`document_versions` (+9, −`storage_key`) · `document_sources` (+`source_version`, +`excerpt`) ·
`files` (+6 scan/quarantine) · `integrations` (+7, credentials extracted) ·
`tool_calls` (+8, `status` enumerated) · `audit_events` (+7) · `messages` (+7).
