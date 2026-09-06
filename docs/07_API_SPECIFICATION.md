# 07 API SPECIFICATION

**Revision:** 2 (2026-08-26) — FINAL ARCHITECTURE RESOLUTION PASS
**Base path:** `/api/v1`

This file **defines contracts only**. No endpoint here is implemented. Revision 1 defined 62
endpoints; the architecture review found 41 UI actions with no contract and two paths contradicting
`03`. Both conflicts are resolved in § 2 and every missing contract is defined below.

Status labels used throughout:

| Label | Meaning |
| --- | --- |
| ✅ | Contract complete. Implementable once its phase is reached. |
| 🟠 | Contract complete **except** for a product decision. Do not implement until decided. |
| 🔵 | **MISSING CONTRACT.** Behaviour is not specified anywhere. `STATUS = BLOCKED` per `12 § 43`. |
| 🔒 | Contract complete but gated on `MC-02` (permission not in `11 § 5`). |

**Label precedence** where more than one applies: 🔵 > 🟠 > 🔒 > ✅. An endpoint carries the label
of its hardest blocker, so the § 28 inventory counts each endpoint exactly once.

---

# 1. CONVENTIONS

| Concern | Rule |
| --- | --- |
| **Transport** | HTTPS only (`11 § 10`). |
| **Auth** | `Authorization: Bearer <access_token>`. Validated against `sessions` (`06 § 11`). |
| **Tenant** | Resolved **server-side** from the session, never from a header or body. A client-supplied tenant identifier is ignored. `CLAUDE.md § 2`. |
| **Request pipeline** | authenticate → resolve tenant → authorize resource → check permission → validate input → policy check → execute → audit. Exactly `11 § 2`. |
| **Default deny** | An endpoint with no explicitly granted permission returns `403`. `11 § 27`. |
| **Pagination** | `?limit=` (default 25, max 100) `&cursor=`. Response: `{ "data": [...], "page": { "next_cursor": "…", "total": n } }`. `total` is a real count — `03 § 29`: *"Do not hard-code values such as: 1/36 1/45."* |
| **Sorting/filtering** | `?sort=<field>:<asc\|desc>` and per-resource filters, both whitelisted server-side. |
| **Idempotency** | Every `POST` that creates an external effect or a run accepts `Idempotency-Key`. Replay returns the original response. |
| **Concurrency** | Resources with `lock_version` (`approvals`, `documents`) require `If-Match: <lock_version>`; mismatch → `409 CONFLICT_STALE_VERSION` (`12 § 35`). |
| **Streaming** | SSE, `text/event-stream`. Event names are typed per endpoint. |
| **Long operations** | Return `202` with `{ "job_id": … }` (`04 § ASYNC`); progress is read from the resource, never invented. |
| **Timestamps** | RFC 3339 UTC. |
| **Identifiers** | Path IDs are UUIDs. Human-facing keys (`BR-001`, `DOC-001`) are separate fields; their format is 🟠 **D-09**. |
| **Errors** | Exactly revision 1's envelope, preserved verbatim below. |
| **No stack traces** | *"Never expose stack traces to users."* Carried forward from revision 1. |

## 1.1 Error format — unchanged from revision 1

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document was not found.",
    "request_id": "..."
  }
}
```

## 1.2 Status codes

| Code | Use |
| --- | --- |
| `200` | Success with body |
| `201` | Resource created, `Location` header set |
| `202` | Accepted, work queued |
| `204` | Success, no body |
| `400` | `VALIDATION_ERROR`, with a field-level `details` array |
| `401` | `UNAUTHENTICATED` |
| `403` | `FORBIDDEN` — also returned for cross-tenant reads, so existence is not disclosed |
| `404` | `<RESOURCE>_NOT_FOUND` |
| `409` | `CONFLICT_*` — stale version, duplicate key, illegal state transition |
| `410` | `RESOURCE_IMMUTABLE` — write attempted on an approved version (`09 § 5`) |
| `413` | `FILE_TOO_LARGE` — limit is 🟠 **D-26** |
| `415` | `UNSUPPORTED_MEDIA_TYPE` — allow-list is 🟠 **D-26** |
| `422` | `POLICY_RULE_MISSING`, `POLICY_DENIED` |
| `429` | `RATE_LIMITED`, `Retry-After` header. Limits 🟠 **D-11** (`11 § 12`) |
| `500` | `INTERNAL_ERROR` with `request_id` only (`11 § 26`) |
| `503` | `INTEGRATION_UNAVAILABLE` / `INTEGRATION_NOT_CONNECTED` — never a fabricated result (`10`) |

**Cross-tenant reads return `403`, not `404`.** `12 § 7` accepts *"HTTP 403 or appropriate
authorization response"*; `403` is chosen because a `404` on a resource that exists in another
tenant still confirms nothing, whereas a `404` on a resource that does **not** exist and a `403`
on one that does would together form an existence oracle if the codes differed by tenancy.

---

# 2. PATH CONFLICTS — RESOLVED

## 2.1 File upload: `POST /files/upload` vs `POST /api/v1/files`

| Source | Path |
| --- | --- |
| `07` revision 1 | `POST /files/upload` |
| `03 § 11` | `POST /api/v1/files` |

✅ **RESOLVED — `POST /files`.** Derived, not chosen:

1. Every other creating endpoint in revision 1 is a bare collection `POST` — `/projects`,
   `/conversations`, `/projects/{id}/requirements`. `/files/upload` is the only verb-suffixed path
   in the file, i.e. the outlier within `07`'s own convention.
2. `03 § 11` names `POST /api/v1/files` and is the only file that also specifies the
   12-stage request flow behind it, so it is the more complete of the two contracts.
3. Both files agree on the resource; only the suffix differs. Removing the suffix satisfies both
   `03` and `07`'s convention simultaneously.

`POST /files/upload` is **superseded** and must not be implemented.

## 2.2 Workflow start: `POST /workflows/{id}/run` vs `.../runs`

| Source | Path |
| --- | --- |
| `07` revision 1 | `POST /workflows/{id}/run` |
| `03 § 14` | `POST /api/v1/workflows/{workflow_id}/runs` |

✅ **RESOLVED — `POST /workflows/{workflow_definition_id}/runs`.** Derived:

1. The operation creates a `workflow_runs` row (`06 § 22`) — a resource, addressed elsewhere in
   revision 1 as `/workflow-runs/{id}`. A `POST` to the plural collection is the create for that
   resource; `/run` names an action with no corresponding collection.
2. `03 § 14` states the plural form and is the page that owns the button.
3. `{id}` is renamed `{workflow_definition_id}` because `{id}` is ambiguous between a definition
   and a run — the ambiguity that produced this conflict.

`POST /workflows/{id}/run` is **superseded**.

## 2.3 Definitions vs runs — collection naming

`/workflows/*` addresses `workflow_definitions`. `/workflow-runs/*` addresses `workflow_runs`.
Both forms come from revision 1 and are kept.

---

# 3. PERMISSION MODEL

## 3.1 The 21 permissions defined by `11 § 5`

`PROJECT_READ` · `PROJECT_WRITE` · `PROJECT_DELETE` · `FILE_READ` · `FILE_UPLOAD` ·
`FILE_DELETE` · `WORKFLOW_RUN` · `WORKFLOW_CANCEL` · `WORKFLOW_RETRY` · `DOCUMENT_READ` ·
`DOCUMENT_GENERATE` · `DOCUMENT_EDIT` · `DOCUMENT_REVIEW` · `DOCUMENT_APPROVE` ·
`INTEGRATION_READ` · `INTEGRATION_MANAGE` · `AUDIT_READ` · `ADMIN_USERS` · `ADMIN_ROLES` ·
`ADMIN_WORKFLOWS` · `ADMIN_TOOLS`

Seeded in `06 § 8`. `11 § 5` labels them *"Example permissions"*, which is why § 3.2 exists.

## 3.2 🔵 MC-02 — the permission catalogue is incomplete

The endpoints below require 21 permissions that `11 § 5` does not name:

`REQUIREMENT_READ` · `REQUIREMENT_WRITE` · `CONVERSATION_READ` · `CONVERSATION_WRITE` ·
`CONVERSATION_DELETE` · `WORKFLOW_READ` · `RISK_READ` · `RISK_WRITE` · `SECURITY_READ` ·
`COMPLIANCE_READ` · `TRACEABILITY_READ` · `TEST_CASE_READ` · `TEST_CASE_WRITE` ·
`DOCUMENT_DOWNLOAD` · `DOCUMENT_REJECT` · `REPORT_READ` · `AGENT_TRACE_READ` ·
`ADMIN_MODELS` · `ADMIN_TEMPLATES` · `ADMIN_POLICIES` · `ADMIN_QUOTA`

**These are named as the gap, not adopted.** Every endpoint marked 🔒 needs one. Reusing an
existing permission would silently widen it — `DOCUMENT_READ` covering requirement writes, or
`ADMIN_TOOLS` covering model configuration — so no substitution is made. Under `11 § 27` an
un-granted permission denies, which means each 🔒 endpoint currently returns `403` for every
caller: the safe posture, but not a shippable one.

**Decision needed:** adopt these 21 into `11 § 5`, or map each 🔒 endpoint onto an existing
permission explicitly.

---

# 4. AUTH — 9 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `POST /auth/register` | public | `email`, `password`, `full_name`, `tenant_name?`, `invite_token?` | `201` `{user_id}` | `USER_REGISTERED` | 🟠 |
| `POST /auth/login` | public | `email`, `password` | `200` `{access_token, refresh_token, expires_in, user}` | `USER_LOGIN_SUCCEEDED` / `USER_LOGIN_FAILED` | 🟠 |
| `POST /auth/logout` | authn | — | `204` | `USER_LOGOUT` | ✅ |
| `POST /auth/refresh` | public | `refresh_token` | `200` `{access_token, refresh_token, expires_in}` | `TOKEN_REFRESHED` | 🟠 |
| `POST /auth/forgot-password` | public | `email` | `202` — always, regardless of existence | `PASSWORD_RESET_REQUESTED` | 🟠 |
| `POST /auth/reset-password` | public | `token`, `new_password` | `204`; all sessions revoked | `PASSWORD_RESET_COMPLETED` | 🟠 |
| `GET /auth/me` | authn | — | `200` `{user, tenant, roles[], permissions[]}` | — | ✅ |
| `GET /auth/sessions` | authn | — | `200` `sessions[]` — `06 § 11` | — | ✅ |
| `DELETE /auth/sessions/{session_id}` | authn (own) | — | `204` | `SESSION_REVOKED` | ✅ |

`GET /auth/me` returns the caller's effective permissions **for UI affordance only**. The backend
re-checks on every call — `CLAUDE.md § 2`.

🟠 **D-25** — `11 § 7` requires sessions to *expire* but no file gives a duration. Six endpoints
above need `sessions`, `refresh_tokens` and `password_reset_tokens` TTLs. Not inventable.

🔵 **SSO** — `login.png` shows Google and Microsoft buttons. No file defines a provider set, claim
mapping, or JIT provisioning, and `06 § 5` deliberately has no `identities` table. Any
`/auth/sso/*` contract would be invented. `STATUS = BLOCKED`.

---

# 5. TENANT & MEMBERSHIP — 6 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /tenants/current` | authn | — | `200` tenant + settings | — | ✅ |
| `PATCH /tenants/current` | `ADMIN_USERS` | `name?`, `settings?` | `200` | `TENANT_UPDATED` | ✅ |
| `GET /tenants/current/members` | `ADMIN_USERS` | filters | `200` `tenant_members[]` + roles | — | ✅ |
| `POST /tenants/current/members` | `ADMIN_USERS` | `email`, `role_ids[]` | `201` | `TENANT_MEMBER_INVITED` | 🟠 |
| `PATCH /tenants/current/members/{user_id}` | `ADMIN_ROLES` | `role_ids[]`, `status?` | `200` | `ROLE_ASSIGNED` / `ROLE_REVOKED` | 🟠 |
| `DELETE /tenants/current/members/{user_id}` | `ADMIN_USERS` | — | `204` | `TENANT_MEMBER_REMOVED` | ✅ |

🟠 **D-13** — `11 § 6` states *"The canonical UI does not fully specify role assignment"* and lists
six undefined items, and `03 § 28` repeats it. The two role endpoints have a complete shape but no
role set, no scope rule, and no answer to *who may assign*. Implementing them would define the
authorization model by accident.

---

# 6. PROJECTS — 9 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /projects` | `PROJECT_READ` | `status?`, `q?`, page | `200` `projects[]` | — | ✅ |
| `POST /projects` | `PROJECT_WRITE` | `name`, `description?`, `settings?` | `201` | `PROJECT_CREATED` | ✅ |
| `GET /projects/{project_id}` | `PROJECT_READ` | — | `200` project + counts | — | ✅ |
| `PATCH /projects/{project_id}` | `PROJECT_WRITE` | mutable fields | `200` | `PROJECT_UPDATED` | ✅ |
| `DELETE /projects/{project_id}` | `PROJECT_DELETE` | — | `204`; sets `deleted_at` | `PROJECT_DELETED` | 🟠 |
| `GET /projects/{project_id}/members` | `PROJECT_READ` | — | `200` `project_members[]` | — | ✅ |
| `POST /projects/{project_id}/members` | `PROJECT_WRITE` | `user_id`, `project_role` | `201` | `PROJECT_MEMBER_ADDED` | 🟠 |
| `PATCH /projects/{project_id}/members/{user_id}` | `PROJECT_WRITE` | `project_role` | `200` | `PROJECT_MEMBER_UPDATED` | 🟠 |
| `DELETE /projects/{project_id}/members/{user_id}` | `PROJECT_WRITE` | — | `204` | `PROJECT_MEMBER_REMOVED` | ✅ |

`DELETE` is a soft delete (`06 § 15`). 🟠 **D-21** — `11 § 22` requires a *"deleted-resource
handling"* rule with no value, so whether child documents, files and runs become inaccessible
immediately or at retention expiry is undecided. The three member endpoints inherit 🟠 **D-13**.

---

# 7. CHAT — 10 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /conversations` | 🔒 `CONVERSATION_READ` | `project_id?`, page | `200` | — | 🔒 |
| `POST /conversations` | 🔒 `CONVERSATION_WRITE` | `project_id?`, `title?` | `201` | `CONVERSATION_CREATED` | 🔒 |
| `GET /conversations/{conversation_id}` | 🔒 `CONVERSATION_READ` | — | `200` | — | 🔒 |
| `PATCH /conversations/{conversation_id}` | 🔒 `CONVERSATION_WRITE` | `title`, `status` | `200` | `CONVERSATION_UPDATED` | 🔒 |
| `DELETE /conversations/{conversation_id}` | 🔒 `CONVERSATION_DELETE` | — | `204`, soft | `CONVERSATION_DELETED` | 🔒 |
| `GET /conversations/{conversation_id}/messages` | 🔒 `CONVERSATION_READ` | page | `200` `messages[]` | — | 🔒 |
| `POST /conversations/{conversation_id}/messages` | 🔒 `CONVERSATION_WRITE` | `content`, `file_ids[]?` | `201` user msg + `202` assistant msg id | `MESSAGE_SENT` | 🔒 |
| `POST /conversations/{conversation_id}/messages/stream` | 🔒 `CONVERSATION_WRITE` | as above | SSE | `MESSAGE_SENT` | 🔒 |
| `POST /conversations/{conversation_id}/messages/{message_id}/regenerate` | 🔒 `CONVERSATION_WRITE` | `model?` | SSE | `MESSAGE_REGENERATED` | 🔒 |
| `POST /conversations/{conversation_id}/messages/{message_id}/stop` | 🔒 `CONVERSATION_WRITE` | — | `204` | — | 🔵 |

**SSE events** for the two streaming endpoints: `message.created`, `message.delta`,
`message.tool_call`, `message.completed`, `message.failed`. `message.tool_call` carries the
`tool_calls` row id so a denied tool request is visible to the user rather than silently dropped.

**Regenerate is new.** `13 § CHAT` requires *"regenerate response"*; revision 1 had no contract for
it. It supersedes the prior assistant message (`messages.superseded_by_id`, `06 § 18`) rather than
deleting it — `11 § 21` audits message history and a destructive regenerate would erase evidence.

🔵 **Stop generation** — the composer in `chat.png` shows only a paperclip and a send button, so no
canonical UI affordance for cancelling a stream exists, and no file specifies whether a stopped
message is persisted partially or discarded. Contract shape given, behaviour `BLOCKED`.

🔵 **Retrieval** — every message endpoint depends on context assembly over `file_chunks`, but no
file defines an embedding model, dimension, or index (`06 § 20`). Chat over uploaded files cannot
be implemented until it is specified.

---

# 8. FILES — 6 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `POST /files` | `FILE_UPLOAD` | multipart: `file`, `project_id`, `conversation_id?` | `201` `{file_id, status}` | `FILE_UPLOADED` | 🟠 |
| `GET /projects/{project_id}/files` | `FILE_READ` | `status?`, `q?`, page | `200` `files[]` | — | ✅ |
| `GET /files/{file_id}` | `FILE_READ` | — | `200` file + `scan_result` | — | ✅ |
| `GET /files/{file_id}/download` | `FILE_READ` | — | `302` to a short-lived signed URL | `FILE_DOWNLOADED` | ✅ |
| `DELETE /files/{file_id}` | `FILE_DELETE` | — | `204`, soft | `FILE_DELETED` | ✅ |
| `GET /files/{file_id}/extraction` | `FILE_READ` | page | `200` `file_chunks[]` | — | ✅ |

`POST /files` returns immediately with `status='UPLOADING'`→`SCANNING`; the client polls
`GET /files/{file_id}`. A `QUARANTINED` file is never readable and never enters context
(`11 § 8`, `12 § 10`). Download is a redirect so file bytes never pass through the API tier and the
URL expires — files *"must never be executed as code"*, and a signed, short-lived, non-executable
content-disposition response is how that is enforced at the edge.

`GET /projects/{project_id}/files` is new — revision 1 had no way to list files, yet `03 § 11`
specifies a file list.

🟠 **D-26** — `11 § 8` requires type and size validation; `12 § 10` tests an oversized file and a
disallowed type. Neither a maximum size nor a MIME allow-list exists in any file. The `413` and
`415` responses above cannot be produced until both are set. `admin.png` shows *1 TB* against
storage, which is a tenant quota mockup value, not a per-file limit, and `CLAUDE.md § 1` forbids
treating a mockup number as production configuration.

---

# 9. WORKFLOW DEFINITIONS — 6 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /workflows` | 🔒 `WORKFLOW_READ` | `status?`, page | `200` `workflow_definitions[]` | — | 🔒 |
| `GET /workflows/{workflow_definition_id}` | 🔒 `WORKFLOW_READ` | — | `200` + `capabilities`, `state_machine_id` | — | 🔒 |
| `POST /workflows` | `ADMIN_WORKFLOWS` | `name`, `capabilities`, `policy_id` | `201` `status='DRAFT'` | `WORKFLOW_DEFINITION_CREATED` | 🟠 |
| `PATCH /workflows/{workflow_definition_id}` | `ADMIN_WORKFLOWS` | `capabilities`, `policy_id` — `DRAFT` only | `200` | `WORKFLOW_DEFINITION_UPDATED` | 🟠 |
| `POST /workflows/{workflow_definition_id}/publish` | `ADMIN_WORKFLOWS` | — | `200` `status='PUBLISHED'`, immutable | `WORKFLOW_DEFINITION_PUBLISHED` | 🟠 |
| `GET /workflows/{workflow_definition_id}/versions` | 🔒 `WORKFLOW_READ` | — | `200` version chain | — | 🔒 |

The three write endpoints edit **capability flags and a policy binding only** — never a state
graph. `05 § 1 R1` fixes the graph; `06 § 21` stores no graph column.

🟠 **D-02b** — whether an administrator may author a *new* state graph is unresolved. `03 § 13`
requires that authoring **must not be exposed** until decided, so `POST /workflows` must not accept
a graph payload. `workflow.png` shows templates v1.0–v1.3, which these endpoints satisfy without
an interpreter.

---

# 10. WORKFLOW RUNS — 8 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `POST /workflows/{workflow_definition_id}/runs` | `WORKFLOW_RUN` | `project_id`, `file_ids[]?`, `document_types[]?` | `201` `{workflow_run_id, state}` | `WORKFLOW_RUN_STARTED` | ✅ |
| `GET /workflow-runs` | 🔒 `WORKFLOW_READ` | `project_id?`, `status?`, page | `200` | — | 🔒 |
| `GET /workflow-runs/{workflow_run_id}` | 🔒 `WORKFLOW_READ` | — | `200` run + `current_state` + step summary | — | 🔒 |
| `GET /workflow-runs/{workflow_run_id}/steps` | 🔒 `WORKFLOW_READ` | — | `200` `workflow_steps[]` incl. `attempt`, `skipped_reason` | — | 🔒 |
| `GET /workflow-runs/{workflow_run_id}/transitions` | 🔒 `WORKFLOW_READ` | — | `200` `workflow_state_transitions[]` | — | 🔒 |
| `GET /workflow-runs/{workflow_run_id}/events` | 🔒 `WORKFLOW_READ` | — | SSE | — | 🔒 |
| `POST /workflow-runs/{workflow_run_id}/cancel` | `WORKFLOW_CANCEL` | `reason?` | `200` `state='CANCELLED'` | `WORKFLOW_RUN_CANCELLED` | ✅ |
| `POST /workflow-runs/{workflow_run_id}/retry` | `WORKFLOW_RETRY` | `from_state?` | `200` | `WORKFLOW_RUN_RETRIED` | 🟠 |
| `POST /workflow-runs/{workflow_run_id}/input` | `WORKFLOW_RUN` | `inputs{}`, `file_ids[]?` | `200` resumes at `resume_state` | `WORKFLOW_INPUT_SUPPLIED` | ✅ |

**SSE events:** `run.state_changed`, `run.step_started`, `run.step_completed`, `run.step_failed`,
`run.step_retried`, `run.waiting_for_input`, `run.completed`, `run.failed`, `run.cancelled`,
`run.rejected`. Each carries the `workflow_state_transitions.id` that caused it, so the timeline is
reconstructed from persisted rows rather than from client-side accumulation.

`cancel` is valid only from `05 § 5.19`'s 14 non-terminal states; otherwise
`409 CONFLICT_INVALID_STATE`. `/input` is new — it is the only exit from `WAITING_FOR_INPUT`
(`05 § 5.15`).

**Progress:** the response exposes `steps_total`, `steps_completed` and `current_state`. It does
**not** expose a percentage or an estimated completion time. `workflow-running.png` shows *60%* and
*"Estimated completion"*, but no file defines either computation, and `CLAUDE.md § 1` forbids fake
workflow progress while `13 § WORKFLOW` requires *"see actual progress"*. 🔵 **MISSING CONTRACT.**

🟠 **D-05** — `retry` needs `retry.max_attempts.*` and `retry.exhausted_action` to exist before it
can decide whether a retry is permitted.

---

# 11. REQUIREMENTS — 8 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /requirements` | 🔒 `REQUIREMENT_READ` | `project_id?`, `type?`, `status?`, `q?`, page | `200` — tenant-wide | — | 🔒 |
| `GET /projects/{project_id}/requirements` | 🔒 `REQUIREMENT_READ` | `type?`, `status?`, `q?`, page | `200` | — | 🔒 |
| `POST /projects/{project_id}/requirements` | 🔒 `REQUIREMENT_WRITE` | `key?`, `type`, `title`, `description`, `priority?` | `201` | `REQUIREMENT_CREATED` | 🟠 |
| `GET /requirements/{requirement_id}` | 🔒 `REQUIREMENT_READ` | — | `200` + source refs + links | — | 🔒 |
| `PATCH /requirements/{requirement_id}` | 🔒 `REQUIREMENT_WRITE` | mutable fields | `200` | `REQUIREMENT_UPDATED` | 🔒 |
| `DELETE /requirements/{requirement_id}` | 🔒 `REQUIREMENT_WRITE` | — | `204` | `REQUIREMENT_DELETED` | 🟠 |
| `GET /requirements/{requirement_id}/links` | 🔒 `TRACEABILITY_READ` | — | `200` `traceability_relationships[]` | — | 🔒 |
| `POST /requirements/{requirement_id}/links` | 🔒 `REQUIREMENT_WRITE` | `target_kind`, `target_id`, `relationship` | `201` | `TRACE_LINK_CREATED` | 🔒 |

`POST` inherits 🟠 **D-09** — `09 § 6` leaves the key format undecided and forbids hard-coding
example IDs, so the server cannot mint `BR-001`. `DELETE` inherits 🟠 **D-21**: a requirement cited
by an approved document version cannot vanish without breaking that version's traceability, and no
retention rule says which wins. Interim: `409` if referenced by any frozen `generation_run_sources`
row — the safer behaviour.

`GET /requirements` is new. `chat.png`'s canonical sidebar carries a **global** Requirements item
(`03 § 3`), so a tenant-wide list is required; without it that sidebar entry has no backend contract.
Results are filtered to projects the caller may read — the endpoint is tenant-wide, not
authorization-wide.

---

# 12. RISKS · SECURITY · COMPLIANCE · EVIDENCE — 17 endpoints

| Method · Path | Perm | Response | Audit | S |
| --- | --- | --- | --- | --- |
| `GET /risks` | 🔒 `RISK_READ` | `200` — tenant-wide (`project_id?`, `severity?`, `status?`, page) | — | 🔒 |
| `GET /projects/{project_id}/risks` | 🔒 `RISK_READ` | `200` `risks[]` | — | 🔒 |
| `GET /risks/{risk_id}` | 🔒 `RISK_READ` | `200` + evidence + links | — | 🔒 |
| `POST /projects/{project_id}/risks` | 🔒 `RISK_WRITE` | `201` | `RISK_CREATED` | 🟠 |
| `PATCH /risks/{risk_id}` | 🔒 `RISK_WRITE` | `200` | `RISK_UPDATED` | 🟠 |
| `DELETE /risks/{risk_id}` | 🔒 `RISK_WRITE` | `204` | `RISK_DELETED` | 🔒 |
| `GET /projects/{project_id}/security-findings` | 🔒 `SECURITY_READ` | `200` | — | 🔒 |
| `GET /security-findings/{finding_id}` | 🔒 `SECURITY_READ` | `200` + evidence | — | 🔒 |
| `PATCH /security-findings/{finding_id}` | 🔒 `SECURITY_READ` + `PROJECT_WRITE` | `200` `status` only | `SECURITY_FINDING_UPDATED` | 🔒 |
| `GET /projects/{project_id}/compliance-findings` | 🔒 `COMPLIANCE_READ` | `200` | — | 🔒 |
| `GET /compliance-findings/{finding_id}` | 🔒 `COMPLIANCE_READ` | `200` + evidence | — | 🔒 |
| `PATCH /compliance-findings/{finding_id}` | 🔒 `COMPLIANCE_READ` + `PROJECT_WRITE` | `200` `status` only | `COMPLIANCE_FINDING_UPDATED` | 🟠 |
| `GET /projects/{project_id}/evidence` | `PROJECT_READ` | `200` `evidence[]` | — | ✅ |
| `POST /projects/{project_id}/evidence` | `PROJECT_WRITE` | `201` | `EVIDENCE_CREATED` | ✅ |
| `GET /evidence/{evidence_id}` | `PROJECT_READ` | `200` | — | ✅ |
| `DELETE /evidence/{evidence_id}` | `PROJECT_WRITE` | `204` | `EVIDENCE_DELETED` | ✅ |
| `GET /projects/{project_id}/design-elements` | `PROJECT_READ` | `200` | — | 🔵 |

🟠 **D-06** — risk write endpoints accept `likelihood` and `severity` but **cannot return a
`score`**: `risk.scoring_method` does not exist, and `08 § 8` says *"If no risk policy exists:
BLOCKED / DECISION REQUIRED. Do not invent scoring rules."* `risks.score` stays `NULL`
(`06 § 31`). `chat.png`'s *View Risks* button and `risks` list render without a score column until
decided.

`PATCH /security-findings/{id}` cannot set `verified=true` — that requires a linked `evidence` row,
enforced by trigger (`06 § 32.1`), because `08 § 6` states the agent *"cannot claim verification
without evidence"*. The same rule blocks `status='CONFORMANT'` on a compliance finding without
evidence. 🟠 **D-30** — the compliance framework set is unspecified, so no framework value can be
validated on input.

🔵 **MC-03** — `design_elements` exists as a table (`06 § 33.1`) so the traceability chain is
storable, but **no file defines what a Design element is**, where it comes from, or who creates it.
`09 § 12` and `13 § TRACEABILITY` require Design in the chain; neither defines it. Read is
contract-shaped; create/update cannot be defined without inventing the entity. `STATUS = BLOCKED`.

---

# 13. TEST CASES — 8 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /projects/{project_id}/test-cases` | 🔒 `TEST_CASE_READ` | filters, page | `200` | — | 🔒 |
| `POST /projects/{project_id}/test-cases` | 🔒 `TEST_CASE_WRITE` | `09 § 14`'s 11 fields | `201` | `TEST_CASE_CREATED` | 🟠 |
| `GET /test-cases/{test_case_id}` | 🔒 `TEST_CASE_READ` | — | `200` + `steps[]` + links | — | 🔒 |
| `PATCH /test-cases/{test_case_id}` | 🔒 `TEST_CASE_WRITE` | mutable fields | `200` | `TEST_CASE_UPDATED` | 🔒 |
| `DELETE /test-cases/{test_case_id}` | 🔒 `TEST_CASE_WRITE` | — | `204` | `TEST_CASE_DELETED` | 🔒 |
| `GET /test-cases/{test_case_id}/results` | 🔒 `TEST_CASE_READ` | — | `200` `test_case_results[]` | — | 🔒 |
| `POST /test-cases/{test_case_id}/results` | 🔒 `TEST_CASE_WRITE` | `status`, `actual_result`, `executed_at`, `executed_by?` | `201` | `TEST_RESULT_RECORDED` | 🔵 |
| `GET /projects/{project_id}/test-cases/export` | 🔒 `TEST_CASE_READ` + `DOCUMENT_DOWNLOAD` | `format=xlsx` | `200` XLSX | `TEST_CASES_EXPORTED` | 🔒 |

🔵 **Test result ingestion** — `09 § 14` defines a test case's *expected* result; nothing defines
where an **actual** result comes from. There is no CI integration in `10`, no runner contract, and
no UI for manual entry in any canonical PNG. The endpoint shape is defined and the storage exists
(`06 § 33.3`), but the source of truth is unspecified. `CLAUDE.md § 5` forbids inventing test
results, so this must not be populated by any other path. `STATUS = BLOCKED`.

---

# 14. TRACEABILITY & RTM — 5 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /projects/{project_id}/traceability` | 🔒 `TRACEABILITY_READ` | `root_kind?`, `root_id?`, `depth?` | `200` nodes + edges | — | 🟠 |
| `GET /projects/{project_id}/traceability/matrix` | 🔒 `TRACEABILITY_READ` | filters, page | `200` RTM rows | — | 🟠 |
| `GET /projects/{project_id}/traceability/coverage` | 🔒 `TRACEABILITY_READ` | — | `200` coverage per link type | — | 🟠 |
| `POST /projects/{project_id}/traceability/links` | 🔒 `REQUIREMENT_WRITE` | `source_kind/_id`, `target_kind/_id`, `relationship` | `201` | `TRACE_LINK_CREATED` | 🔒 |
| `DELETE /traceability/links/{relationship_id}` | 🔒 `REQUIREMENT_WRITE` | — | `204` | `TRACE_LINK_DELETED` | 🔒 |

Links are validated against `06 § 33.4`'s allowed-pair table; an unlisted pair returns
`400 TRACE_PAIR_NOT_ALLOWED`. Same-project and kind-match are enforced by trigger, so a
cross-project edge cannot be created through any path.

🟠 **D-19** — the RTM's column set is contradicted across three files: `03 § 25` specifies **9
columns**, `09 § 12` a **7-link chain**, and `rtm.png` renders a narrower grid. The three read
endpoints cannot fix a response shape until one is authoritative. Compounded by 🔵 **MC-03**:
whichever shape wins, the Design column has no populating source.

---

# 15. DOCUMENTS — 15 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /documents` | `DOCUMENT_READ` | `type?`, `status?`, `q?`, page | `200` — tenant-wide, for `documents.png` | — | ✅ |
| `GET /projects/{project_id}/documents` | `DOCUMENT_READ` | filters, page | `200` | — | ✅ |
| `POST /projects/{project_id}/documents/generate` | `DOCUMENT_GENERATE` | `document_type`, `source_selection`, `template_id?` | `202` `{document_id, generation_run_id}` | `DOCUMENT_GENERATION_REQUESTED` | ✅ |
| `GET /documents/{document_id}` | `DOCUMENT_READ` | — | `200` + current version + computed validation/approval status | — | ✅ |
| `PATCH /documents/{document_id}` | `DOCUMENT_EDIT` | `title?` | `200` | `DOCUMENT_UPDATED` | ✅ |
| `DELETE /documents/{document_id}` | `PROJECT_DELETE` | — | `204`; `410` if any version is `APPROVED` | `DOCUMENT_DELETED` | 🟠 |
| `POST /documents/{document_id}/validate` | `DOCUMENT_GENERATE` | `document_version_id?` | `202` | `DOCUMENT_VALIDATION_REQUESTED` | ✅ |
| `POST /documents/{document_id}/revise` | `DOCUMENT_EDIT` | `changes[]`, `reason` | `201` new version | `DOCUMENT_REVISED` | ✅ |
| `GET /documents/{document_id}/generation-runs` | `DOCUMENT_READ` | page | `200` incl. failure fields | — | ✅ |
| `POST /generation-runs/{generation_run_id}/retry` | `DOCUMENT_GENERATE` | `If-Match` | `202` `{generation_run_id}` | `DOCUMENT_GENERATION_REQUESTED` | ✅ |
| `GET /documents/{document_id}/sources` | `DOCUMENT_READ` | — | `200` frozen source set | — | ✅ |
| `POST /documents/{document_id}/review` | `DOCUMENT_REVIEW` | `reviewer_ids[]`, `due_date?`, `priority?` | `201` review | `REVIEW_REQUESTED` | 🟠 |
| `POST /documents/{document_id}/approve` | `DOCUMENT_APPROVE` | `comment?`, `If-Match` | `200` | `APPROVAL_GRANTED` | 🟠 |
| `POST /documents/{document_id}/reject` | 🔒 `DOCUMENT_REJECT` | `reason` (required) | `200` | `APPROVAL_REJECTED` | 🟠 |
| `POST /documents/{document_id}/request-changes` | `DOCUMENT_REVIEW` | `comment`, `target_step_id?` | `200` | `REVIEW_CHANGES_REQUESTED` | 🟠 |

`GET /documents` is new and is what `documents.png` — *"Manage all project documents"* — actually
needs; revision 1 had only the project-scoped list.

**One status field, three views.** `GET /documents/{id}` returns `status` from `documents.status`
plus **computed** `validation_status` and `approval_status` derived from `validation_runs` and
`approvals`. `03 § 20` shows three columns; `06 § 34` stores one. Derived values are computed
server-side and never stored, so they cannot drift — and never computed client-side
(`CLAUDE.md § 2`).

`reject` is new: `approval.png` has a **Reject** button that revision 1 had no endpoint for.

`POST /generation-runs/{id}/retry` is new and closes `09 § 28`'s *"Retry endpoint: DECISION
REQUIRED"*. It retries only a run in `FAILED` state, against the **frozen**
`generation_run_sources` set, so a retry regenerates from identical inputs. `409` if the run is not
`FAILED`; `422 NOT_RETRYABLE` if `generation_runs.failure_code` is classified non-retryable. The
`retryable` flag is returned by `GET /documents/{id}/generation-runs` — the frontend never decides
(`03 § 15`), which is what satisfies *"No frontend retry button should call a nonexistent
endpoint."*
`request-changes` is new for the same reason. Both feed `05 § 5.11`/`§ 5.12`.

🟠 **D-04** — `approve` cannot be implemented until the approval model is chosen (`09 § 22`:
*"Do not implement one until the product decision is made"*). `06 § 40` can store all three
candidates. 🟠 **D-21** applies to `DELETE`; an approved version is immutable (`13 § APPROVAL`),
so the safe interim is `410`.

---

# 16. DOCUMENT VERSIONS & RENDITIONS — 8 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /documents/{document_id}/versions` | `DOCUMENT_READ` | page | `200` version chain + `version_label` | — | ✅ |
| `GET /documents/{document_id}/versions/{version_label}` | `DOCUMENT_READ` | — | `200` version + sections | — | ✅ |
| `GET /document-versions/{document_version_id}/sections` | `DOCUMENT_READ` | — | `200` ordered sections + `provenance_state` | — | ✅ |
| `GET /document-versions/{document_version_id}/diff` | `DOCUMENT_READ` | `against=<label>` | `200` section-level diff | — | 🔵 |
| `GET /documents/{document_id}/pdf` | 🔒 `DOCUMENT_DOWNLOAD` | `version?` | `302` signed URL | `DOCUMENT_DOWNLOADED` | 🔒 |
| `GET /documents/{document_id}/docx` | 🔒 `DOCUMENT_DOWNLOAD` | `version?` | `302` signed URL | `DOCUMENT_DOWNLOADED` | 🔒 |
| `GET /documents/{document_id}/xlsx` | 🔒 `DOCUMENT_DOWNLOAD` | `version?` | `302` signed URL | `DOCUMENT_DOWNLOADED` | 🔒 |
| `POST /document-versions/{document_version_id}/renditions` | `DOCUMENT_GENERATE` | `format` | `202` | `RENDITION_REQUESTED` | ✅ |

`GET /documents/{id}/xlsx` is new — `09 § 25` requires XLSX for RTM and test-case matrices, and
revision 1 defined only `/pdf` and `/docx`. It returns `409 RENDITION_NOT_APPLICABLE` for the nine
types that have no XLSX output (`09 § 25`).

All three format endpoints require a `document_renditions` row with `status='READY'`
(`06 § 38`); otherwise `409 RENDITION_NOT_READY`. There is no synthesise-on-download path:
`09 § 26` states *"The frontend must not generate fake download files"* and `13 § PDF` requires a
real file, so a download either serves a stored artefact or fails.

🔵 **Version diff** — `09 § 27` requires revision tracking and `03 § 20` shows a version history,
but no file defines a comparison output. `brd-preview.png` shows no diff view. `STATUS = BLOCKED`.

---

# 17. DOCUMENT CHAT — 3 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /documents/{document_id}/chat` | `DOCUMENT_READ` | page | `200` messages | — | 🔵 |
| `POST /documents/{document_id}/chat` | `DOCUMENT_READ` | `content`, `section_id?` | SSE | `DOCUMENT_CHAT_MESSAGE` | 🔵 |
| `POST /documents/{document_id}/chat/apply` | `DOCUMENT_EDIT` | `message_id`, `section_id` | `201` new version | `DOCUMENT_REVISED` | 🔵 |

🔵 `01 § CHAT` lists document chat as a capability and `CLAUDE.md` lists *document chat/editing* in
scope, but no file defines whether it is a separate conversation, whether a suggestion can be
applied, or whether applying creates a version. `apply` on an `APPROVED` version must be `410` in
any design (`13 § APPROVAL`), which is the only part derivable. `STATUS = BLOCKED`.

---

# 18. REVIEWS — 11 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /reviews` | `DOCUMENT_REVIEW` | `status?`, `assignee?`, page | `200` | — | ✅ |
| `GET /reviews/{review_id}` | `DOCUMENT_REVIEW` | — | `200` + `sections_reviewed`/`sections_total` | — | ✅ |
| `POST /reviews/{review_id}/assignments` | `DOCUMENT_REVIEW` | `user_id`, `role`, `due_date?`, `priority?` | `201` | `REVIEW_ASSIGNED` | 🟠 |
| `DELETE /reviews/{review_id}/assignments/{assignment_id}` | `DOCUMENT_REVIEW` | — | `204` | `REVIEW_ASSIGNMENT_REMOVED` | ✅ |
| `GET /reviews/{review_id}/sections` | `DOCUMENT_REVIEW` | — | `200` per-section status | — | ✅ |
| `PATCH /reviews/{review_id}/sections/{section_id}` | `DOCUMENT_REVIEW` | `status`, `comment?` | `200` | `REVIEW_SECTION_UPDATED` | ✅ |
| `GET /reviews/{review_id}/comments` | `DOCUMENT_REVIEW` | page | `200` | — | ✅ |
| `POST /reviews/{review_id}/comments` | `DOCUMENT_REVIEW` | `body`, `section_id?`, `parent_id?` | `201` | `REVIEW_COMMENT_ADDED` | ✅ |
| `PATCH /reviews/{review_id}/comments/{comment_id}` | `DOCUMENT_REVIEW` (author) | `body?`, `resolution?` | `200` | `REVIEW_COMMENT_UPDATED` | ✅ |
| `POST /reviews/{review_id}/decision` | `DOCUMENT_REVIEW` | `decision` ∈ {`APPROVE`,`REJECT`,`REQUEST_CHANGES`,`REQUEST_INFORMATION`}, `comment?` | `200` + resulting state | `REVIEW_*` per decision | 🟠 |
| `POST /reviews/{review_id}/escalate` | `DOCUMENT_REVIEW` | `reason` | `200` `escalation_level+1` | `REVIEW_ESCALATED` | 🟠 |

**`sections_reviewed` and `sections_total` come from the backend.** `review.png` shows *"3 of 5
sections reviewed"*; `06 § 39.1` maintains both by trigger. The frontend must not count
(`CLAUDE.md § 2`).

`/decision` is a single endpoint over four outcomes because all four are one state transition on
one review with one audit event; splitting them would allow two to be applied concurrently.

🟠 **D-07** — `escalate` has no target role (`human_review.escalation_role` is unset), so it cannot
select an assignee. 🟠 **D-04** — `/decision` with `APPROVE` routes to `APPROVAL` or
`DOCUMENT_GENERATION` depending on `approval.required`.

---

# 19. APPROVALS — 6 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /approvals` | `DOCUMENT_APPROVE` | `status?`, page | `200` | — | ✅ |
| `GET /approvals/{approval_id}` | `DOCUMENT_APPROVE` | — | `200` + `approval_steps[]` + `lock_version` | — | ✅ |
| `POST /approvals/{approval_id}/steps/{step_id}/decision` | `DOCUMENT_APPROVE` | `decision` ∈ {`APPROVE`,`REJECT`,`REQUEST_CHANGES`}, `comment?`, `If-Match` | `200` | `APPROVAL_GRANTED` / `APPROVAL_REJECTED` / `REVIEW_CHANGES_REQUESTED` | 🟠 |
| `GET /approvals/{approval_id}/history` | `DOCUMENT_APPROVE` | — | `200` decision history | — | ✅ |
| `GET /documents/{document_id}/approvals` | `DOCUMENT_READ` | — | `200` approval history for the document | — | ✅ |
| `POST /approvals/{approval_id}/delegate` | `DOCUMENT_APPROVE` | `to_user_id`, `reason` | `200` | `APPROVAL_DELEGATED` | 🔵 |

`If-Match: <lock_version>` is mandatory on `/decision`; two approvers deciding concurrently means
one receives `409` — the `12 § 35` case.

An approver must be a real user: `06 § 40.2` requires `decided_by` to reference `users`, so no
agent can supply a decision — `08 § 18`, *"Agents cannot impersonate human approval."*

🟠 **D-04.** 🔵 **Delegation** — `approval.png` shows a three-step approval chain but no delegation
affordance, and no file defines whether authority can be transferred. `STATUS = BLOCKED`.

**Reported canonical-UI defect:** `approval.png` shows a progress donut reading *1 of 3* while all
three chain rows read *Pending*. Those two facts cannot both be true. The API returns
`steps_total` and `steps_approved` from `approval_steps`, so the screen's numbers must be
re-derived; the mockup must not be reproduced literally.

---

# 20. AGENT RUNS — 4 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /workflow-runs/{workflow_run_id}/agent-runs` | 🔒 `AGENT_TRACE_READ` | — | `200` `agent_runs[]` | — | 🔒 |
| `GET /agent-runs/{agent_run_id}` | 🔒 `AGENT_TRACE_READ` | — | `200` `08 § 15`'s 8 stored fields | — | 🔒 |
| `GET /agent-runs/{agent_run_id}/tool-calls` | 🔒 `AGENT_TRACE_READ` | — | `200` incl. `DENIED_*` rows | — | 🔒 |
| `GET /agent-runs/{agent_run_id}/validation` | 🔒 `AGENT_TRACE_READ` | — | `200` `validation_runs` row | — | 🔒 |

Responses expose the **structured** output and metadata, never a raw prompt: `11 § 9` forbids
secrets in prompts and a trace view that returned assembled context would expose the
`AUTHORIZED_INTEGRATION_DATA` and `UNTRUSTED_EXTERNAL_CONTENT` buckets to any trace reader.
`input_hash` (`06 § 28`) allows reproducibility checks without disclosure.

`GET .../tool-calls` deliberately includes denied attempts — this is the read side of the
`11 § 15` injection test.

---

# 21. TOOL REGISTRY — 6 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /admin/tools` | `ADMIN_TOOLS` | `enabled?`, `risk_level?` | `200` `tool_registry[]` | — | ✅ |
| `GET /admin/tools/{tool_id}` | `ADMIN_TOOLS` | — | `200` incl. input/output schema | — | ✅ |
| `PATCH /admin/tools/{tool_id}` | `ADMIN_TOOLS` | `enabled`, `allowed_agents[]`, `required_permissions[]`, `risk_level` | `200` | `TOOL_REGISTRY_UPDATED` | 🟠 |
| `GET /admin/tools/{tool_id}/bindings` | `ADMIN_TOOLS` | — | `200` `tool_bindings[]` | — | ✅ |
| `PATCH /admin/tools/{tool_id}/bindings/{binding_id}` | `ADMIN_TOOLS` | `enabled` | `200` | `TOOL_BINDING_UPDATED` | ✅ |
| `GET /tool-calls` | 🔒 `AGENT_TRACE_READ` | `status?`, `tool_id?`, page | `200` incl. every `DENIED_*` | — | 🔒 |

There is **no** `POST /admin/tools`. Tools are registered by deployment, not at runtime:
`CLAUDE.md § 4` forbids the LLM creating arbitrary integrations, and a create endpoint would make
the registry's allow-list mutable by whoever holds `ADMIN_TOOLS` — turning the sole external-effect
gate into a self-service one. Nine tools are seeded in `06 § 41.1`.

🟠 **D-27** — `allowed_agents` is empty for all nine tools because no file states which agent may
call which tool. Under `11 § 27` every tool request is therefore denied. This is the correct
posture — `11 § 16`: *"Unknown tools must be rejected"* — but it means no agent can reach any
integration until the matrix is defined.

---

# 22. INTEGRATIONS — 8 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /integrations` | `INTEGRATION_READ` | — | `200` status per type; **never a secret** | — | ✅ |
| `GET /integrations/{integration_id}` | `INTEGRATION_READ` | — | `200` + `last_error`, `connected_at` | — | ✅ |
| `POST /integrations/jira/connect` | `INTEGRATION_MANAGE` | OAuth start | `200` `{authorization_url, state}` | `INTEGRATION_CONNECT_STARTED` | ✅ |
| `GET /integrations/jira/callback` | `INTEGRATION_MANAGE` | `code`, `state` | `302`; stores ciphertext | `INTEGRATION_CONNECTED` | ✅ |
| `POST /integrations/confluence/connect` | `INTEGRATION_MANAGE` | — | — | `INTEGRATION_CONNECTED` | 🔵 |
| `POST /integrations/notion/connect` | `INTEGRATION_MANAGE` | — | — | `INTEGRATION_CONNECTED` | 🔵 |
| `POST /integrations/{integration_id}/disconnect` | `INTEGRATION_MANAGE` | — | `204`; credentials destroyed | `INTEGRATION_DISCONNECTED` | ✅ |
| `POST /integrations/{integration_id}/test` | `INTEGRATION_MANAGE` | — | `200` `{ok, checked_at, detail}` | `INTEGRATION_TESTED` | ✅ |

`/test` is new — `03 § 26` and `integrations.png` show a **Test Connection** button that revision 1
had no endpoint for. It performs a real read against the provider; if the credential is invalid it
returns `503 INTEGRATION_UNAVAILABLE`. It must never return a canned success (`CLAUDE.md § 1`).

No response body from any endpoint here contains a token, refresh token, or client secret.
`06 § 42.2` stores them as ciphertext columns with no `SELECT` grant to the application role;
`11 § 9` forbids secrets in the frontend bundle, logs, or prompts.

🔵 **MC-04** — `10` gives Jira an OAuth flow but says nothing about how Confluence or Notion
authenticate. Notion uses an integration token and Confluence may use OAuth or an API token; both
are provider facts, not repository facts, and picking one would be an invention. The two `connect`
endpoints are `BLOCKED`.

---

# 23. INTEGRATION TOOL ENDPOINTS — 8 endpoints

Every endpoint here passes through the `11 § 17` chain. None accepts free-form LLM text.

| Method · Path | Perm | Tool | Audit | S |
| --- | --- | --- | --- | --- |
| `POST /tools/jira/issues/search` | `INTEGRATION_READ` | `jira.issue.search` | `TOOL_EXECUTED` | ✅ |
| `GET /tools/jira/issues/{issue_key}` | `INTEGRATION_READ` | `jira.issue.get` | `TOOL_EXECUTED` | ✅ |
| `POST /tools/jira/issues` | `INTEGRATION_MANAGE` | `jira.issue.create` (HIGH_WRITE) | `TOOL_EXECUTED` | 🟠 |
| `PATCH /tools/jira/issues/{issue_key}` | `INTEGRATION_MANAGE` | `jira.issue.update` (HIGH_WRITE) | `TOOL_EXECUTED` | 🟠 |
| `POST /tools/jira/issues/{issue_key}/links` | `INTEGRATION_MANAGE` | `jira.issue.link` | `TOOL_EXECUTED` | 🟠 |
| `POST /tools/confluence/search` | `INTEGRATION_READ` | `confluence.search` | `TOOL_EXECUTED` | ✅ |
| `GET /tools/confluence/pages/{page_id}` | `INTEGRATION_READ` | `confluence.page.get` | `TOOL_EXECUTED` | ✅ |
| `POST /tools/notion/search` | `INTEGRATION_READ` | `notion.search` | `TOOL_EXECUTED` | ✅ |
| `GET /tools/notion/pages/{page_id}` | `INTEGRATION_READ` | `notion.page.get` | `TOOL_EXECUTED` | ✅ |

**Confluence and Notion are read-only.** `10` grants only search and retrieve; there is no write
capability to expose, and none is added.

`POST /tools/jira/issues` in revision 1 was the only Jira write path and had no search endpoint
despite `10` listing *search issues* first. Both are now present.

**Not connected → `503 INTEGRATION_NOT_CONNECTED`** with message *"Jira is not connected."*,
verbatim from `10`. Never an empty result set that a caller could mistake for *no matches*, and
never a fabricated one — `10`: *"Do not fabricate Jira results"*, `13 § INTEGRATIONS`: *"Do not
return fake data."*

Retrieved content is returned tagged as untrusted and enters context only as
`UNTRUSTED_EXTERNAL_CONTENT` (`08 § 12`).

🟠 **D-27**, and additionally `tool.requires_policy_approval.<tool_id>` for the three HIGH_WRITE
tools: `11 § 18` requires *"policy approval where required"* without saying when it is required.

---

# 24. AUDIT — 3 endpoints

| Method · Path | Perm | Request | Response | Audit | S |
| --- | --- | --- | --- | --- | --- |
| `GET /audit` | `AUDIT_READ` | `event_type?`, `actor?`, `resource_type?`, `resource_id?`, `outcome?`, `from?`, `to?`, page | `200` | — | ✅ |
| `GET /audit/{audit_event_id}` | `AUDIT_READ` | — | `200` all 8 fields | — | ✅ |
| `GET /audit/export` | `AUDIT_READ` | same filters, `format=xlsx\|csv` | `202` job | `AUDIT_EXPORTED` | ✅ |

Read-only by construction: `06 § 43` grants no `UPDATE` or `DELETE` on `audit_events` to the
application role. `outcome` is filterable so a denied authorization is distinguishable from a
success — without it, `12 § 30`'s injection assertion could not be expressed as a query.

🔵 **MC-05** — no file defines tamper-evidence (hash chain, WORM storage, or an external sink).
`11 § 26` requires audit evidence to be *preserved*; append-only grants are necessary but not
sufficient against a database administrator. Storage exists; the integrity contract does not.

---

# 25. ADMIN — 21 endpoints

## 25.1 Model configuration — 5

| Method · Path | Perm | Response | Audit | S |
| --- | --- | --- | --- | --- |
| `GET /admin/models` | 🔒 `ADMIN_MODELS` | `200` `model_configurations[]` | — | 🔒 |
| `POST /admin/models` | 🔒 `ADMIN_MODELS` | `201` | `MODEL_CONFIGURATION_CREATED` | 🔒 |
| `PATCH /admin/models/{model_configuration_id}` | 🔒 `ADMIN_MODELS` | `200` | `MODEL_CONFIGURATION_UPDATED` | 🔒 |
| `DELETE /admin/models/{model_configuration_id}` | 🔒 `ADMIN_MODELS` | `204` | `MODEL_CONFIGURATION_DELETED` | 🔒 |
| `GET /admin/models/{model_configuration_id}/usage` | 🔒 `ADMIN_MODELS` | `200` token totals from `agent_runs` | — | 🔒 |

Provider API keys are never accepted or returned here — `11 § 9` puts them in a secrets manager.
The row names a key, it does not hold one.

## 25.2 Templates / prompt registry — 5

| Method · Path | Perm | Response | Audit | S |
| --- | --- | --- | --- | --- |
| `GET /admin/templates` | 🔒 `ADMIN_TEMPLATES` | `200` | — | 🔒 |
| `POST /admin/templates` | 🔒 `ADMIN_TEMPLATES` | `201` `DRAFT` | `TEMPLATE_CREATED` | 🔒 |
| `PATCH /admin/templates/{template_id}` | 🔒 `ADMIN_TEMPLATES` | `200` — `DRAFT` only | `TEMPLATE_UPDATED` | 🔒 |
| `POST /admin/templates/{template_id}/publish` | 🔒 `ADMIN_TEMPLATES` | `200` immutable | `TEMPLATE_PUBLISHED` | 🔒 |
| `GET /admin/templates/{template_id}/versions` | 🔒 `ADMIN_TEMPLATES` | `200` | — | 🔒 |

A published template is immutable so an already-generated document's basis cannot change
retroactively — the same guarantee `09 § 7` gives for sources.

## 25.3 Policies — 7

| Method · Path | Perm | Response | Audit | S |
| --- | --- | --- | --- | --- |
| `GET /admin/policies` | 🔒 `ADMIN_POLICIES` | `200` `policies[]` | — | 🔒 |
| `POST /admin/policies` | 🔒 `ADMIN_POLICIES` | `201` | `POLICY_CREATED` | 🔒 |
| `GET /admin/policies/{policy_id}/versions` | 🔒 `ADMIN_POLICIES` | `200` | — | 🔒 |
| `POST /admin/policies/{policy_id}/versions` | 🔒 `ADMIN_POLICIES` | `201` `DRAFT` | `POLICY_VERSION_CREATED` | 🔒 |
| `PUT /admin/policy-versions/{policy_version_id}/rules` | 🔒 `ADMIN_POLICIES` | `200` — `DRAFT` only | `POLICY_RULES_UPDATED` | 🔒 |
| `POST /admin/policy-versions/{policy_version_id}/activate` | 🔒 `ADMIN_POLICIES` | `200` immutable | `POLICY_VERSION_ACTIVATED` | 🔒 |
| `GET /admin/policy-evaluations` | 🔒 `ADMIN_POLICIES` | `200` `policy_evaluations[]` | — | 🔒 |

`rule_key` values are validated against `06 § 30.4`'s **27-key registry**; an unknown key is
`400 POLICY_RULE_KEY_UNKNOWN`. This is the mechanism that resolves **BL-4**: every *"configured
policy"* reference in the specifications now names a real key, and an activated version is frozen
into each run (`06 § 22`).

An activated version cannot be edited. Editing a live policy would silently change the governing
rules of in-flight runs, which `06 § 22`'s `policy_version_id` freeze exists to prevent.

## 25.4 Quotas — 3

| Method · Path | Perm | Response | Audit | S |
| --- | --- | --- | --- | --- |
| `GET /admin/quotas` | 🔒 `ADMIN_QUOTA` | `200` the 7 metrics + usage | — | 🟠 |
| `PATCH /admin/quotas/{quota_id}` | 🔒 `ADMIN_QUOTA` | `200` `limit_value`, `enforced` | `QUOTA_UPDATED` | 🟠 |
| `GET /admin/quotas/usage` | 🔒 `ADMIN_QUOTA` | `200` `quota_usage[]` | — | 🔒 |

Usage is real and computed. **Limits are not seeded** — `admin.png`'s *1 TB* and *100,000* are
mockup values, and `CLAUDE.md § 1` forbids presenting demo data as production. `enforced` defaults
to `false` (`06 § 44.2`), so no request is refused on a quota until a limit is deliberately set.
🟠 **D-14**.

## 25.5 Users & roles — 6

| Method · Path | Perm | Response | Audit | S |
| --- | --- | --- | --- | --- |
| `GET /admin/users` | `ADMIN_USERS` | `200` | — | ✅ |
| `GET /admin/users/{user_id}` | `ADMIN_USERS` | `200` + roles | — | ✅ |
| `PATCH /admin/users/{user_id}` | `ADMIN_USERS` | `200` `status` | `USER_UPDATED` | ✅ |
| `GET /admin/roles` | `ADMIN_ROLES` | `200` roles + permissions | — | ✅ |
| `POST /admin/roles` | `ADMIN_ROLES` | `201` | `ROLE_CREATED` | 🟠 |
| `PUT /admin/roles/{role_id}/permissions` | `ADMIN_ROLES` | `200` | `PERMISSION_CHANGED` | 🟠 |

🟠 **D-13**. `PERMISSION_CHANGED` and `ROLE_ASSIGNED` are audited (`11 § 21`) because a privilege
change is the highest-value event in the system.

---

# 26. DASHBOARD — 1 endpoint

| Method · Path | Perm | Response | S |
| --- | --- | --- | --- |
| `GET /dashboard/metrics` | authn | `200` `{projects, documents, workflow_runs_active, requirements}` | ✅ |

`chat.png` shows four metric tiles reading **24 / 18 / 7 / 12**. Those are mockup values. This
endpoint returns real counts scoped to the caller's tenant and authorized projects. The frontend
must render whatever it returns, including zeros — `03 § 29`: *"Do not hard-code values."*

---

# 27. BLOCKED SURFACES — no contract definable

| Surface | Canonical source | Why blocked |
| --- | --- | --- |
| `/reports` | `chat.png` sidebar item; `03 § 27` marks it **BLOCKED** | No file defines a single report, its inputs, or its output format |
| `/notifications` | `06 § 44.1` has the table | No page, no endpoint, no trigger, and no delivery channel in any file |
| `/auth/sso/*` | `login.png` Google + Microsoft | No provider set, claim mapping, or JIT provisioning |
| Design element writes | `09 § 12`, `13 § TRACEABILITY` | MC-03 — the entity is undefined |
| Test result ingestion | `06 § 33.3` | No runner, CI, or manual-entry contract |
| Document diff | `09 § 27` | No comparison output defined |
| Document chat apply | `01 § CHAT` | No suggestion→version contract |
| Approval delegation | `approval.png` | No transfer-of-authority rule |
| Stop generation | — | Not in the canonical composer |
| Workflow progress % | `workflow-running.png` | No computation defined; `CLAUDE.md § 1` forbids faking it |
| Confluence/Notion connect | `10` | MC-04 — auth method unspecified |

Per `12 § 43` each is `STATUS = BLOCKED`: *"Do not implement a guessed behavior."* Defining any of
them here would be inventing a requirement.

---

# 28. ENDPOINT INVENTORY

| § | Group | Count | ✅ | 🟠 | 🔒 | 🔵 |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | Auth | 9 | 4 | 5 | 0 | 0 |
| 5 | Tenant & membership | 6 | 4 | 2 | 0 | 0 |
| 6 | Projects | 9 | 6 | 3 | 0 | 0 |
| 7 | Chat | 10 | 0 | 0 | 9 | 1 |
| 8 | Files | 6 | 5 | 1 | 0 | 0 |
| 9 | Workflow definitions | 6 | 0 | 3 | 3 | 0 |
| 10 | Workflow runs | 9 | 3 | 1 | 5 | 0 |
| 11 | Requirements | 8 | 0 | 2 | 6 | 0 |
| 12 | Risks/security/compliance/evidence | 17 | 4 | 3 | 9 | 1 |
| 13 | Test cases | 8 | 0 | 1 | 6 | 1 |
| 14 | Traceability & RTM | 5 | 0 | 3 | 2 | 0 |
| 15 | Documents | 15 | 10 | 5 | 0 | 0 |
| 16 | Versions & renditions | 8 | 4 | 0 | 3 | 1 |
| 17 | Document chat | 3 | 0 | 0 | 0 | 3 |
| 18 | Reviews | 11 | 8 | 3 | 0 | 0 |
| 19 | Approvals | 6 | 4 | 1 | 0 | 1 |
| 20 | Agent runs | 4 | 0 | 0 | 4 | 0 |
| 21 | Tool registry | 6 | 4 | 1 | 1 | 0 |
| 22 | Integrations | 8 | 6 | 0 | 0 | 2 |
| 23 | Integration tools | 9 | 6 | 3 | 0 | 0 |
| 24 | Audit | 3 | 3 | 0 | 0 | 0 |
| 25 | Admin | 26 | 4 | 4 | 18 | 0 |
| 26 | Dashboard | 1 | 1 | 0 | 0 | 0 |
| | **Total** | **193** | **76** | **41** | **66** | **10** |

Revision 1 defined **62**. Of those, 2 are superseded (§ 2), 60 are carried forward, and **133 are
new** — the 41 the review identified plus the sub-resources they require.

**76 endpoints (39%) are implementable as specified.** 41 wait on a product decision, 66 wait on
MC-02 alone, and 10 have no definable contract.

**MC-02 is the single highest-leverage gap in this file.** Adopting the 21 permissions in § 3.2
moves 66 endpoints from blocked to implementable in one decision — more than any other item, and
more than all 14 product decisions combined.

Three endpoints were added after the § 28 count was first derived, each closing a gap found while
reconciling another file: `GET /requirements` and `GET /risks` (the canonical sidebar's global items,
`03 § 3`) and `POST /generation-runs/{id}/retry` (`09 § 28`'s undefined retry endpoint).

---

# 29. UNCHANGED FROM REVISION 1

Carried forward verbatim, still binding:

**Every protected endpoint must:** authenticate · resolve tenant · authorize · validate input ·
execute service · return structured response · audit where applicable.

**Error format:** § 1.1. **Never expose stack traces to users.**

---

# 30. OPEN DECISIONS IN THIS FILE

| ID | Question | Endpoints blocked |
| --- | --- | --- |
| 🟠 **D-04** | Approval model | 5 |
| 🟠 **D-05** | Retry policy values | 1 |
| 🟠 **D-06** | Risk scoring + threshold | 4 |
| 🟠 **D-07** | Escalation target role | 2 |
| 🟠 **D-09** | Human-facing ID format | 3 |
| 🟠 **D-11** | Rate limits (`11 § 12`) | all — `429` undefined |
| 🟠 **D-13** | Role assignment model | 7 |
| 🟠 **D-19** | RTM column set | 3 |
| 🟠 **D-14** | Quota limits | 2 |
| 🟠 **D-21** | Deleted-resource handling | 4 |
| 🟠 **D-25** | Session/token/reset TTLs | 6 |
| 🟠 **D-26** | Max upload size + MIME allow-list | 1 |
| 🟠 **D-27** | Per-agent tool allow-list | 9 |
| 🟠 **D-30** | Compliance framework set | 2 |
| 🔵 **MC-02** | Permission catalogue | **66** |
| 🔵 **MC-03** | Design element definition | 2 |
| 🔵 **MC-04** | Confluence/Notion auth | 2 |
| 🔵 **MC-05** | Audit tamper-evidence | 0 — storage exists, integrity does not |
