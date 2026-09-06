# 10 INTEGRATION SPECIFICATION

**Revision:** 2 (2026-08-26) — FINAL ARCHITECTURE RESOLUTION PASS

Revision 1 is preserved in full. This revision names the registered tools per integration
(§§ 1.2, 2.2, 3.2), states the ten required aspects per integration (§§ 1.3, 2.3, 3.3), and records
🔵 **MC-04** — Confluence and Notion have **no specified authentication method**.

**No integration capability is added.** Confluence and Notion remain read-only, because revision 1
grants them nothing else.

---

# 1. JIRA

## Connection

OAuth-based integration.

## Capabilities

- search issues
- create issue
- update issue where permitted
- retrieve issue
- attach links

## Before every action

authenticate
↓
authorization
↓
tool validation
↓
execute
↓
validate response
↓
audit

If not connected:

Do not fabricate Jira results.

Show:

"Jira is not connected."

## 1.1 The six-stage flow is a subset of the eleven-stage chain — ADDED

Revision 1's six stages are correct but abbreviated. The authoritative chain is `11 § 17`'s eleven
stages, and the six map onto it without conflict:

| Revision 1 stage | `11 § 17` stages | Denial status |
| --- | --- | --- |
| authenticate | 2 (session) + 10 (provider credential) | `DENIED_AUTHENTICATION` |
| authorization | 3 tenant + 4 permission | `DENIED_TENANT` / `DENIED_PERMISSION` |
| tool validation | 1 schema + 6 registry + 7 `allowed_agents` + 8 `enabled` | `SCHEMA_REJECTED` / `DENIED_UNREGISTERED` / `DENIED_DISABLED` |
| execute | 10 | `EXECUTION_FAILED` |
| validate response | 11 output schema | `RESULT_INVALID` |
| audit | throughout — `TOOL_REQUEST_RECEIVED` first, terminal event last | — |

The chain adds stage 5, **policy** — which revision 1 omits but `CLAUDE.md § 4` requires between
authorization and the Tool Registry, and which § 4 of this document already shows in its own diagram.

## 1.2 Registered tools — ADDED

Five tools, one per capability, matching `11 § 16.2` exactly:

| Tool ID | Capability | Effect | Risk level | Required permission |
| --- | --- | --- | --- | --- |
| `jira.issue.search` | search issues | Read | `LOW` | 🔒 `INTEGRATION_READ` |
| `jira.issue.get` | retrieve issue | Read | `LOW` | 🔒 `INTEGRATION_READ` |
| `jira.issue.create` | create issue | **Write** | `HIGH` | 🔒 `INTEGRATION_WRITE` |
| `jira.issue.update` | update issue *where permitted* | **Write** | `HIGH` | 🔒 `INTEGRATION_WRITE` |
| `jira.issue.link` | attach links | **Write** | `MEDIUM` | 🔒 `INTEGRATION_WRITE` |

*"Where permitted"* is enforced twice: `INTEGRATION_WRITE` in REFYNE, and the OAuth grant's own
scope at Jira. A REFYNE permission cannot grant authority the OAuth token does not carry, and a
Jira `403` surfaces as `EXECUTION_FAILED` — never retried as though transient.

**`allowed_agents` is empty for all five — 🟠 D-27.** No agent can currently invoke any of them
(`11 § 27`). The three write tools are the reason this is left as a decision rather than inferred:
`jira.issue.create` writes to a customer's tracker.

**`enabled` defaults `false`** (`11 § 16.1`). Registration is a deployment act.

## 1.3 Ten aspects — ADDED

| Aspect | Contract |
| --- | --- |
| **Connection** | `POST /integrations/jira/connect` → `302` to the provider; callback `POST /integrations/jira/callback`. State stored in `integrations.status` ∈ `{DISCONNECTED, PENDING, CONNECTED, ERROR}` |
| **Authentication** | OAuth authorization-code flow. Tokens in `integration_credentials`, encrypted at rest (`06`: *"Secrets must not be stored unencrypted"*). Never returned by any endpoint (`11 § 9.1`) |
| **Read** | `jira.issue.search`, `jira.issue.get` |
| **Write** | `jira.issue.create`, `jira.issue.update`, `jira.issue.link` |
| **Permissions** | `INTEGRATION_MANAGE` to connect/disconnect/test; 🔒 `INTEGRATION_READ` / 🔒 `INTEGRATION_WRITE` per tool — both 🔵 **MC-02** |
| **Tool registry** | All five registered; the registry is the only path to the provider. An HTTP client reachable from agent code without a registry lookup would defeat every control above |
| **Authorization** | Eleven stages, `11 § 17.1`. Six Jira-specific preconditions in `11 § 18.1` |
| **Audit** | `INTEGRATION_CONNECT_STARTED`, `INTEGRATION_CONNECTED`, `INTEGRATION_DISCONNECTED`, `INTEGRATION_TESTED`, `INTEGRATION_ERROR`; per call `TOOL_REQUEST_RECEIVED`, then `TOOL_EXECUTED` / `TOOL_REQUEST_DENIED` / `TOOL_EXECUTION_FAILED` |
| **Failure** | Not connected → `503 INTEGRATION_NOT_CONNECTED`, UI shows *"Jira is not connected."* Provider `401` → `integrations.status = ERROR`; `403` → `EXECUTION_FAILED`, not retried; `429`/`5xx` → retryable |
| **Retry** | 🟠 **D-05** — no retry policy. **Interim: no automatic retry.** Writes are additionally guarded (§ 1.4) |

## 1.4 Write idempotency

**A create must not be retried without an idempotency key.** A retried `jira.issue.create` after an
ambiguous timeout would create a second issue in a customer's tracker — an externally visible,
non-rollbackable duplicate.

`tool_calls.idempotency_key` is derived from `(tenant_id, tool_id, input_hash)`. A retry with the
same key returns the recorded result rather than calling the provider again. This is why D-05's
interim position (no automatic retry) is the safe one for writes specifically.

---

# 2. CONFLUENCE

## Capabilities

- search
- retrieve pages
- read authorized content

Never access unauthorized pages.

Never fabricate search results.

## 2.1 🔵 MC-04 — no authentication method specified

Revision 1 specifies OAuth for Jira and **states no connection or authentication method for
Confluence**. Nothing in any of the fourteen specification files supplies one: no OAuth flow, no API
token, no base URL configuration, no credential storage note.

**Consequence, not worked around:** `03 § 26`'s Connect button for Confluence renders **disabled**
with the reason stated. No endpoint is defined (`07 § 22`). Inventing a flow would mean inventing a
credential-handling contract — the highest-consequence thing to guess in this document, because
credentials for a customer's wiki would be involved.

`integration_credentials` is provider-agnostic, so the storage exists the moment the method is
decided.

## 2.2 Registered tools — ADDED

| Tool ID | Capability | Effect | Risk level | Required permission |
| --- | --- | --- | --- | --- |
| `confluence.search` | search | Read | `LOW` | 🔒 `INTEGRATION_READ` |
| `confluence.page.get` | retrieve pages | Read | `LOW` | 🔒 `INTEGRATION_READ` |

**Two tools, no third.** *"Read authorized content"* is not a separate capability — it is the
authorization constraint on the other two. **No write tool exists**, because revision 1 grants
Confluence no write capability. `09`/`13` mention publishing documents nowhere for Confluence, so
none is added.

## 2.3 Ten aspects — ADDED

| Aspect | Contract |
| --- | --- |
| **Connection** | 🔵 **MC-04** |
| **Authentication** | 🔵 **MC-04** |
| **Read** | `confluence.search`, `confluence.page.get` |
| **Write** | **None — by design** |
| **Permissions** | 🔒 `INTEGRATION_READ`; `INTEGRATION_MANAGE` to connect once MC-04 closes |
| **Tool registry** | Both registered, `enabled = false`, `allowed_agents` empty (🟠 D-27) |
| **Authorization** | `11 § 17.1`. *"Never access unauthorized pages"* — the provider's own permission model applies at stage 10; a page the connected account cannot read returns the provider's denial, surfaced as `EXECUTION_FAILED`. REFYNE does not attempt to widen it |
| **Audit** | Same event set as § 1.3 |
| **Failure** | Not connected → `503`; UI states it plainly, never fabricated results |
| **Retry** | 🟠 D-05. Reads are idempotent, so retry is safe once a policy exists |

**Retrieved page bodies enter `UNTRUSTED_EXTERNAL_CONTENT`** (`08 § 12.1`) — a wiki page any
employee can edit is exactly the injection vector `11 § 15` tests for.

---

# 3. NOTION

## Capabilities

- search
- retrieve authorized pages

Never fabricate results.

## 3.1 🔵 MC-04 — no authentication method specified

Identical position to § 2.1. `03 § 26`'s Notion Connect button renders disabled with the reason
stated.

## 3.2 Registered tools — ADDED

| Tool ID | Capability | Effect | Risk level | Required permission |
| --- | --- | --- | --- | --- |
| `notion.search` | search | Read | `LOW` | 🔒 `INTEGRATION_READ` |
| `notion.page.get` | retrieve authorized pages | Read | `LOW` | 🔒 `INTEGRATION_READ` |

Read-only. No write tool.

## 3.3 Ten aspects — ADDED

As § 2.3, substituting the two Notion tools. Retrieved page bodies are untrusted content.

---

# 4. TOOL REGISTRY

Every external operation goes through Tool Registry.

Example:

User
↓
LLM
↓
Tool Request
↓
Schema Validation
↓
Permission
↓
Policy
↓
Tool Registry
↓
Integration
↓
Result
↓
Validation
↓
Audit

## 4.1 Authoritative chain — ADDED

This diagram is correct and is the **abbreviated** form of `11 § 17`'s eleven stages, which is
authoritative. `11 § 17` inserts tenant resolution, the `allowed_agents` check, and the `enabled`
check — three gates this diagram implies but does not name.

**Nine tools total**, and no others: 5 Jira + 2 Confluence + 2 Notion.

*"Every external operation goes through Tool Registry"* means the integration HTTP clients are
reachable **only** from the registry executor. `11 § 16`: *"Unknown tools must be rejected."* An
unregistered attempt is recorded with `tool_registry_id = NULL` and status `DENIED_UNREGISTERED`
(`11 § 16.3`) — it leaves evidence rather than vanishing.

**No runtime tool creation exists.** `07 § 21` and `03 § 28.1` expose enable, disable and binding
edits only. A runtime create would make the sole external-effect gate self-service.

## 4.2 Current effective position

| Gate | State | Effect |
| --- | --- | --- |
| Registered | 9 tools | ✅ |
| `enabled` | `false` for all 9 | No execution |
| `allowed_agents` | empty for all 9 (🟠 D-27) | No agent may invoke any tool |
| `INTEGRATION_READ` / `INTEGRATION_WRITE` | not in `11 § 5` (🔵 MC-02) | No user holds them |
| Jira connection | contract exists | Connectable |
| Confluence / Notion connection | 🔵 MC-04 | Not connectable |

**No tool can execute today.** Every gate fails closed, and each closure is a specification gap
rather than a defect. `11 § 15.1` notes that this makes the current posture *stricter* than the
finished product's — the correct direction while decisions are outstanding.

---

# 5. INTEGRATION INVENTORY — ADDED

| Aspect | Jira | Confluence | Notion |
| --- | --- | --- | --- |
| Connection | ✅ OAuth | 🔵 MC-04 | 🔵 MC-04 |
| Authentication | ✅ | 🔵 MC-04 | 🔵 MC-04 |
| Read | ✅ 2 tools | ✅ 2 tools | ✅ 2 tools |
| Write | ✅ 3 tools | — none by design | — none by design |
| Permissions | 🔵 MC-02 | 🔵 MC-02 | 🔵 MC-02 |
| Tool registry | ✅ 5 registered | ✅ 2 registered | ✅ 2 registered |
| Authorization | ✅ 11 stages | ✅ 11 stages | ✅ 11 stages |
| Audit | ✅ 5 + 4 events | ✅ | ✅ |
| Failure | ✅ | ✅ | ✅ |
| Retry | 🟠 D-05 | 🟠 D-05 | 🟠 D-05 |

**30 aspects: 19 ✅, 7 gated on MC-02/MC-04, 3 on D-05, 1 intentionally absent.**

**No integration returns fabricated data under any state.** Disconnected returns `503`; an empty
result returns an empty list; a provider error returns the error. `13 § INTEGRATIONS`: *"If
disconnected: Do not return fake data."*
