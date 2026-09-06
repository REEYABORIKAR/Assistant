# 05 WORKFLOW SPECIFICATION

**Revision:** 2 (2026-08-26) — FINAL ARCHITECTURE RESOLUTION PASS
**State machine ID:** `REFYNE_CORE_V1`

This file is the **single authoritative workflow model**. No other specification may define
states, transitions, or triggers. `06 § 21`'s `workflow_definitions.state_machine_id` points here;
`03 §§ 14–15` render what this file defines; `12 § 11` tests it.

Revision 1 left eight of eighteen states with an undefined, ambiguous, or unreachable transition.
Every defect is resolved below, and every resolution names the evidence it derives from.

---

# 1. STRUCTURAL RULES

| Rule | Statement |
| --- | --- |
| **R1** | The state graph is **fixed**. Only capability flags and policy bindings vary. See `06 § 21.1`. |
| **R2** | **RETRY is a transition trigger, not a state.** It re-enters the same state with `attempt + 1`. |
| **R3** | Every transition is persisted as one `workflow_state_transitions` row. No state changes without one. |
| **R4** | A transition that depends on a policy rule **must** read an existing `policy_rules` row. If the rule is absent the run halts — it must never assume a value. |
| **R5** | An optional state has exactly **one** success edge. Enablement is evaluated by the **predecessor**, which emits `SUCCESS` or `SKIP`. |
| **R6** | Only a human actor may trigger `HUMAN_*`. `08 § 18`: *"Agents cannot impersonate human approval."* |
| **R7** | Terminal states have no outgoing transitions: `COMPLETED`, `FAILED`, `REJECTED`, `CANCELLED`. |
| **R8** | Every transition is authorized before it is applied, and audited where `11 § 21.2` requires. |

---

# 2. STATES

**19 states.** The 18 of revision 1, plus `REJECTED` (§ 2.2). Enum: `06 § 3 workflow_state`.

| # | State | Kind | Optional | Step type |
| --- | --- | --- | --- | --- |
| 1 | `CREATED` | initial | — | `SYSTEM` |
| 2 | `INPUT_VALIDATION` | processing | no | `SYSTEM` |
| 3 | `DATA_COLLECTION` | processing | no | `SYSTEM` |
| 4 | `REQUIREMENT_ANALYSIS` | agent | no | `AGENT` |
| 5 | `SECURITY_ANALYSIS` | agent | **yes** | `AGENT` |
| 6 | `COMPLIANCE_ANALYSIS` | agent | **yes** | `AGENT` |
| 7 | `DATA_AVAILABILITY` | agent | no | `AGENT` |
| 8 | `RISK_ANALYSIS` | agent | **yes** | `AGENT` |
| 9 | `VALIDATION` | validation | no | `VALIDATION` |
| 10 | `POLICY_EVALUATION` | decision | no | `POLICY` |
| 11 | `HUMAN_REVIEW` | wait | **conditional** | `HUMAN` |
| 12 | `APPROVAL` | wait | **conditional** | `HUMAN` |
| 13 | `DOCUMENT_GENERATION` | processing | no | `DOCUMENT` |
| 14 | `DOCUMENT_VALIDATION` | validation | no | `VALIDATION` |
| 15 | `WAITING_FOR_INPUT` | wait | — | `HUMAN` |
| 16 | `COMPLETED` | terminal | — | — |
| 17 | `FAILED` | terminal | — | — |
| 18 | `REJECTED` | terminal | — | — |
| 19 | `CANCELLED` | terminal | — | — |

## 2.1 The authoritative happy path

```
CREATED
  → INPUT_VALIDATION
  → DATA_COLLECTION
  → REQUIREMENT_ANALYSIS
  → [SECURITY_ANALYSIS]      if security_analysis_enabled
  → [COMPLIANCE_ANALYSIS]    if compliance_analysis_enabled
  → DATA_AVAILABILITY
  → [RISK_ANALYSIS]          if risk_analysis_enabled
  → VALIDATION
  → POLICY_EVALUATION
  → [HUMAN_REVIEW]           if human_review.required
  → [APPROVAL]               if approval.required
  → DOCUMENT_GENERATION
  → DOCUMENT_VALIDATION
  → COMPLETED
```

## 2.2 ⚠ AMENDMENT — `REJECTED` added as a nineteenth state

**What changed:** revision 1 had no state for a human rejection. `HUMAN_REVIEW` listed `REJECT`
as an option with no destination, and `FAILED` is defined in revision 1 as the destination for a
*non-recoverable technical failure* — a different fact from a human declining to approve.

**Evidence requiring it:**

| Source | Statement |
| --- | --- |
| `approval.png` | A **Reject** button next to **Approve** and **Request Changes** |
| `03 § 24` | The approval page's actions include rejection |
| `09 § 4` | Document state `REJECTED` exists, distinct from `FAILED` |
| `11 § 21` | *rejection* is audited as its own event, separate from failure |
| `12 § 16` | Rejection is a tested outcome |

**Why not reuse `FAILED`:** a rejected run is a completed governance decision with an accountable
actor; a failed run is a technical fault that may be retried. Collapsing them would make
`12 § 16` untestable and would put a human decision behind
`POST /workflow-runs/{id}/retry`, which `11 § 5`'s `WORKFLOW_RETRY` permission does not
contemplate for approvals.

**Status:** this is an **addition to `05`, reported not silently applied**, per `CLAUDE.md`'s
conflict protocol. It is the safer of the two options: a distinguishable terminal state cannot
be mistaken for a retryable fault. It may be vetoed by the product owner, in which case `REJECT`
must be given an explicit destination before phase 11.

## 2.3 REMOVED from revision 1: `RETRY` as a state

Revision 1's VALIDATION section reads *"If validation fails: RETRY"*, and its FAILURE section
reads *"Any recoverable failure: RETRY"* — but `RETRY` is **not** in its own 18-state list.

**Resolution: RETRY is a trigger.** Evidence: revision 1's own RETRIES section describes an
attempt *record* (attempt number, reason, error, timestamp, actor, result), not a state;
`06 § 23 workflow_steps.attempt` stores it; `07`'s `POST /workflow-runs/{id}/retry` is an action;
`11 § 5`'s `WORKFLOW_RETRY` is a permission over an action.

A retry inserts a new `workflow_steps` row for the **same** `state` with `attempt = n + 1` and
writes a `workflow_state_transitions` row with `trigger = 'RETRY'` and
`from_state = to_state`. There is nowhere in the graph a run can be "in RETRY".

---

# 3. CAPABILITY AND POLICY INPUTS

Frozen at run start into `workflow_runs.capabilities_snapshot` and
`workflow_runs.policy_version_id`, so a mid-run configuration change cannot alter a run.

| Input | Source | Governs |
| --- | --- | --- |
| `security_analysis_enabled` | `capabilities_snapshot` | § 5.4 skip |
| `compliance_analysis_enabled` | `capabilities_snapshot` | § 5.5 skip |
| `risk_analysis_enabled` | `capabilities_snapshot` | § 5.7 skip |
| `compliance_frameworks` | `capabilities_snapshot` | § 5.6 |
| `document_types` | `capabilities_snapshot` | § 5.13 |
| `retry.max_attempts.agent` | `policy_rules` | §§ 5.4–5.8 |
| `retry.max_attempts.document_validation` | `policy_rules` | § 5.14 |
| `retry.exhausted_action` | `policy_rules` | §§ 5.9, 5.14 |
| `risk.approval_threshold` | `policy_rules` | § 5.10 |
| `approval.required`, `approval.model` | `policy_rules` | §§ 5.10, 5.12 |
| `human_review.required`, `human_review.escalation_role` | `policy_rules` | §§ 5.10, 5.11 |
| `data_availability.partial_action` | `policy_rules` | § 5.7 |
| `waiting_for_input.timeout_hours` | `policy_rules` | § 5.15 |

**R4 in force.** Every rule above is an open decision (`06 § 45`). Until a value exists the
run halts at the state that needs it, recording the absent `rule_key` in
`policy_evaluations.result` and `workflow_runs.failure_code = 'POLICY_RULE_MISSING'`. This
generalises `08 § 8`'s existing instruction — *"If no risk policy exists: BLOCKED / DECISION
REQUIRED. Do not invent scoring rules."*

---

# 4. TRANSITION TRIGGERS

Enum: `06 § 3 transition_trigger`.

| Trigger | Actor | Meaning |
| --- | --- | --- |
| `START` | SYSTEM | Run created |
| `SUCCESS` | SYSTEM/AGENT | Processing succeeded |
| `FAILURE` | SYSTEM/AGENT | Processing failed, not retryable |
| `RETRY` | SYSTEM or USER | Re-enter the same state, `attempt + 1` |
| `SKIP` | SYSTEM | Optional state disabled by capability |
| `TIMEOUT` | SYSTEM | A wait state exceeded its policy limit |
| `POLICY` | SYSTEM | Destination chosen by a policy rule |
| `HUMAN_APPROVE` | USER | Reviewer/approver approved |
| `HUMAN_REJECT` | USER | Reviewer/approver rejected |
| `HUMAN_REQUEST_CHANGES` | USER | Return to the step named by `reviews.target_step_id` |
| `HUMAN_REQUEST_INFORMATION` | USER | Additional input needed |
| `HUMAN_ESCALATE` | USER | Raise review to the next escalation level |
| `INPUT_SUPPLIED` | USER | The awaited input arrived |
| `CANCEL` | USER | Authorized cancellation |

`RETRY` has two actors: automatic (a retryable failure inside the retry budget) and manual
(`POST /workflow-runs/{run_id}/retry`, requiring `WORKFLOW_RETRY`).

---

# 5. STATE DEFINITIONS

Each state below is defined with the nine required aspects. Where a transition does not exist for
a state, that is stated explicitly as **none** rather than left blank.

## 5.1 CREATED

| Aspect | Definition |
| --- | --- |
| **Entry** | `POST /workflows/{workflow_definition_id}/runs` authorized with `WORKFLOW_RUN`; definition `status='PUBLISHED'`; project accessible in tenant; an active `policy_versions` row resolves for the definition's scope |
| **Processing** | Insert `workflow_runs` with `capabilities_snapshot` and `policy_version_id` frozen; write transition `sequence=0`, `from_state=NULL`, `to_state='CREATED'`, `trigger='START'`; emit `WORKFLOW_RUN_STARTED` |
| **Success** | → `INPUT_VALIDATION` (`SUCCESS`, immediate) |
| **Failure** | → `FAILED` (`FAILURE`) — only if the definition or policy cannot be resolved |
| **Retry** | none — a new run is created instead |
| **Human review** | none |
| **Cancel** | → `CANCELLED` (`CANCEL`) |
| **Exit** | A `workflow_runs` row exists with a frozen configuration |

## 5.2 INPUT_VALIDATION

| Aspect | Definition |
| --- | --- |
| **Entry** | From `CREATED` |
| **Processing** | Validate the run request against the definition: project exists and is not deleted; every referenced file is `status='READY'` (never `QUARANTINED`, per `11 § 8`); requested `document_types` ⊆ the definition's; the caller may read every referenced resource |
| **Success** | → `DATA_COLLECTION` (`SUCCESS`) |
| **Failure** | → `FAILED` (`FAILURE`) with `failure_code`; input validation is deterministic, so it is **not** retryable |
| **Retry** | none |
| **Human review** | none |
| **Cancel** | → `CANCELLED` |
| **Exit** | Every input is present, readable, and authorized |

A referenced file in any non-`READY` state fails here rather than being silently dropped —
`CLAUDE.md § 5` forbids inventing source documents.

## 5.3 DATA_COLLECTION

| Aspect | Definition |
| --- | --- |
| **Entry** | From `INPUT_VALIDATION` |
| **Processing** | Assemble the authorized context per `08 § 12`'s seven buckets. File content enters **only** as `UNTRUSTED_EXTERNAL_CONTENT`. Cross-tenant and unauthorized project data must never enter context (`03 § 10`) |
| **Success** | → `REQUIREMENT_ANALYSIS` (`SUCCESS`) |
| **Failure** | → same state (`RETRY`) if the fault is transient (storage read, extraction timeout) and `attempt < retry.max_attempts.agent`; otherwise → `FAILED` (`FAILURE`) |
| **Retry** | Self-loop, `attempt + 1` |
| **Human review** | none |
| **Cancel** | → `CANCELLED` |
| **Exit** | An authorized context set is assembled and bucket-labelled |

## 5.4 REQUIREMENT_ANALYSIS

| Aspect | Definition |
| --- | --- |
| **Entry** | From `DATA_COLLECTION` |
| **Processing** | Run the Requirement Agent (`08 § 5`); validate output against its schema; persist `requirements` rows with `source_type`, `source_id`, `confidence`, `missing_information` |
| **Success** | → `SECURITY_ANALYSIS` if `security_analysis_enabled`; else → `COMPLIANCE_ANALYSIS` if `compliance_analysis_enabled`; else → `DATA_AVAILABILITY`. Emitted as `SUCCESS` or `SKIP` per **R5** |
| **Failure** | Retryable (provider error, schema-invalid output) → self `RETRY` while under budget; non-retryable → `FAILED` |
| **Retry** | Self-loop bounded by `retry.max_attempts.agent`; on exhaustion apply `retry.exhausted_action` → `HUMAN_REVIEW` or `FAILED` |
| **Human review** | → `HUMAN_REVIEW` when the agent sets `requires_review`, per `08 § 18` |
| **Cancel** | → `CANCELLED` |
| **Exit** | ≥ 1 `requirements` row persisted, or a recorded reason why none were extracted |

The three-way success target is why enablement is evaluated **here**, not in the successor:
`SECURITY_ANALYSIS` never needs a self-skip edge, which is the defect that produced revision 1's
duplicate branch.

## 5.5 SECURITY_ANALYSIS — optional

| Aspect | Definition |
| --- | --- |
| **Entry** | From `REQUIREMENT_ANALYSIS` with `security_analysis_enabled = true`. If false, no step row is created except a `SKIPPED` marker (`skipped_reason='CAPABILITY_DISABLED'`) |
| **Processing** | Security Agent (`08 § 6`); persist `security_findings`. `verified=true` requires a linked `evidence` row — *"The agent cannot claim verification without evidence"* |
| **Success** | → `COMPLIANCE_ANALYSIS` if `compliance_analysis_enabled`; else → `DATA_AVAILABILITY` |
| **Failure** | As § 5.4 |
| **Retry** | As § 5.4 |
| **Human review** | → `HUMAN_REVIEW` on `requires_review` |
| **Cancel** | → `CANCELLED` |
| **Exit** | Findings persisted, or an explicit *no findings* result recorded |

`12 § 11-B` is provable: with the capability off, no `RUNNING` step and no `agent_runs` row for
`agent_type='SECURITY'` exists, and a `SKIPPED` step row does.

## 5.6 COMPLIANCE_ANALYSIS — optional

| Aspect | Definition |
| --- | --- |
| **Entry** | From `REQUIREMENT_ANALYSIS` or `SECURITY_ANALYSIS` with `compliance_analysis_enabled = true` |
| **Processing** | Compliance Agent (`08 § 7`) over `compliance_frameworks`; persist `compliance_findings`. `status='CONFORMANT'` requires linked `evidence` |
| **Success** | → **`DATA_AVAILABILITY`** (`SUCCESS`) |
| **Failure** | As § 5.4 |
| **Retry** | As § 5.4 |
| **Human review** | → `HUMAN_REVIEW` on `requires_review` |
| **Cancel** | → `CANCELLED` |
| **Exit** | Findings persisted per framework, or `UNVERIFIED` recorded |

**Defect fixed — the missing successor.** Revision 1's COMPLIANCE section gave
`SECURITY_ANALYSIS → COMPLIANCE_ANALYSIS` when enabled and *"Otherwise: DATA_AVAILABILITY"* — it
named the **skip** target but never the target for a compliance run that *succeeds*. Resolved to
`DATA_AVAILABILITY`, the same node, because the skip target is by construction the successor of
the state being skipped.

**Reported conflict:** `01 § CORE USER JOURNEY` orders *Security → Compliance → Risk → Data
Availability*, placing `DATA_AVAILABILITY` after `RISK_ANALYSIS`. Revision 1's DATA CHECK
section places it before, routing *data exists → RISK_ANALYSIS*. Resolved toward `05` — the
narrative in `01` is a capability list, not a transition table, and running risk analysis before
knowing whether the data supporting it exists inverts the dependency. `01`'s journey section
should be corrected to match. `workflow-running.png` does not settle it: its nine-step timeline
omits `DATA_AVAILABILITY` entirely.

## 5.7 DATA_AVAILABILITY

| Aspect | Definition |
| --- | --- |
| **Entry** | From `REQUIREMENT_ANALYSIS`, `SECURITY_ANALYSIS`, or `COMPLIANCE_ANALYSIS` |
| **Processing** | Data Availability Agent (`08 § 9`); classify `AVAILABLE` / `PARTIAL` / `MISSING` against `data_availability.required_sources`; persist to `workflow_runs.data_availability` |
| **Success** | `AVAILABLE` → `RISK_ANALYSIS` if `risk_analysis_enabled`, else → `VALIDATION` |
| **Failure** | As § 5.4 |
| **Retry** | As § 5.4 |
| **Human review** | `PARTIAL` → see below |
| **Cancel** | → `CANCELLED` |
| **Exit** | `workflow_runs.data_availability` is set |

**`MISSING` → `WAITING_FOR_INPUT`**, with `resume_state` = this state. Revision 1 already
specifies this (*"If required data is missing: WAITING_FOR_INPUT"*) and `13 § CONDITIONAL`
confirms *"If data missing: workflow waits."*

**`PARTIAL` → 🟠 DECISION REQUIRED — D-03.**

- **Question:** when data availability is `PARTIAL`, does the run continue, wait for input, or go
  to human review?
- **Options already present in repository:** `08 § 9` states *"PARTIAL behavior is: DECISION
  REQUIRED"* and *"The agent must not invent whether PARTIAL is sufficient."* `03 § 16` repeats it
  for the UI. Those are the only three candidates any file names.
- **Why it affects implementation:** it decides whether an incomplete analysis can reach document
  generation. Choosing *continue* permits documents built on acknowledged gaps; choosing *wait*
  can stall runs indefinitely.
- **Files affected:** `05 § 5.7`, `08 § 9`, `03 § 16`, `06 § 30.4` (`data_availability.partial_action`), `12 § 11-D`.
- **What cannot proceed until decided:** the `DATA_AVAILABILITY` transition, and therefore any
  end-to-end run over incomplete sources.

**SAFE INTERIM — `HUMAN_REVIEW` with `reviews.status='PENDING'` and reason `DATA_PARTIAL`.**
Grounded in `CLAUDE.md`'s *"use the safer behavior until clarified"* and `08 § 18`, which already
requires escalation when *ambiguity cannot be resolved*. This is **labelled interim** and is not
the decision: it neither fabricates completeness nor deadlocks, and it is replaced the moment
`data_availability.partial_action` has a value.

## 5.8 RISK_ANALYSIS — optional

| Aspect | Definition |
| --- | --- |
| **Entry** | From `DATA_AVAILABILITY` with `risk_analysis_enabled = true` |
| **Processing** | Risk Agent (`08 § 8`); persist `risks`. **Scoring requires `risk.scoring_method`** — with no rule, `likelihood` and `severity` are stored and `score` stays `NULL` (`06 § 31`) |
| **Success** | → `VALIDATION` (`SUCCESS`) |
| **Failure** | As § 5.4. Additionally: if a score is required by a downstream rule and `risk.scoring_method` is absent, halt per **R4** — *"Do not invent scoring rules"* |
| **Retry** | As § 5.4 |
| **Human review** | → `HUMAN_REVIEW` on `requires_review` |
| **Cancel** | → `CANCELLED` |
| **Exit** | `risks` rows persisted with a recorded `scoring_method`, or an explicit halt |

**Defect fixed — the duplicate branch.** Revision 1's RISK section reads *"If risk analysis
enabled: RISK_ANALYSIS ↓ VALIDATION. Otherwise: VALIDATION"* — two edges from the same node to
the same target, one of which is really the predecessor's skip edge. Under **R5** the skip edge
belongs to `DATA_AVAILABILITY` (§ 5.7) and this state has exactly one success edge.

## 5.9 VALIDATION

| Aspect | Definition |
| --- | --- |
| **Entry** | From `DATA_AVAILABILITY` or `RISK_ANALYSIS` |
| **Processing** | Validation Agent (`08 § 10`) plus deterministic checks; write one `validation_runs` row with `validation_kind='AGENT_OUTPUT'`, `status`, `errors`, `warnings`, `missing`, `coverage`, `retryable`, and **`target_step_id`** naming the step whose output failed |
| **Success** | `PASSED` → `POLICY_EVALUATION` (`SUCCESS`) |
| **Failure** | `FAILED` **and** `retryable=true` **and** the producing step is under budget → `RETRY` re-entering the state named by `validation_runs.target_step_id`. `FAILED` and not retryable → apply `retry.exhausted_action` |
| **Retry** | Bounded by `retry.max_attempts.agent` **on the target step**, not on `VALIDATION` |
| **Human review** | On exhaustion, `retry.exhausted_action='HUMAN_REVIEW'` → `HUMAN_REVIEW`; `='FAILED'` → `FAILED` |
| **Cancel** | → `CANCELLED` |
| **Exit** | Exactly one `validation_runs` row exists for this attempt |

**Defect fixed — where a failed validation goes.** Revision 1 says *"If validation fails:
RETRY"* without naming what is retried. Re-running `VALIDATION` on unchanged inputs is
deterministic and would fail identically — an infinite loop. The retry therefore targets the
**producing** state via `target_step_id`, which is the column added to `validation_runs` in
`06 § 29` for exactly this purpose.

`13 § CONDITIONAL` is satisfied: *"If validation fails: retry. If retry limit exceeded: human
review"* — the latter is `retry.exhausted_action`, whose value is 🟠 D-05.

## 5.10 POLICY_EVALUATION

| Aspect | Definition |
| --- | --- |
| **Entry** | From `VALIDATION` with `PASSED` |
| **Processing** | Evaluate, against the frozen `policy_version_id`: `human_review.required`, `risk.approval_threshold` versus the run's highest `risks.score`, `approval.required`. Write one `policy_evaluations` row per rule read |
| **Success** | → `HUMAN_REVIEW` if `human_review.required`; else → `APPROVAL` if `approval.required` **or** the risk threshold is exceeded; else → `DOCUMENT_GENERATION`. Trigger `POLICY` |
| **Failure** | → `FAILED` if a required `rule_key` is absent (**R4**), `failure_code='POLICY_RULE_MISSING'` |
| **Retry** | Manual `RETRY` only, after the missing rule is configured |
| **Human review** | This state *selects* human review; it does not enter it directly |
| **Cancel** | → `CANCELLED` |
| **Exit** | A destination is recorded together with the `policy_rules` rows that produced it |

`12 § 11-E` and `13 § CONDITIONAL` — *"If risk exceeds configured threshold: approval required"* —
are decided here, and `policy_evaluations` makes the decision auditable rather than inferred.

## 5.11 HUMAN_REVIEW — conditional

| Aspect | Definition |
| --- | --- |
| **Entry** | From `POLICY_EVALUATION` (`human_review.required`); from any agent state on `requires_review`; from `VALIDATION` on retry exhaustion; from `DATA_AVAILABILITY` on `PARTIAL` (SAFE INTERIM, § 5.7) |
| **Processing** | Create a `reviews` row with `target_step_id`, `priority`, `due_at` (from `human_review.sla_hours`), `sections_total`; create `review_assignments`. Wait. Reviewers act through `review_sections` and `review_comments` |
| **Success** | `HUMAN_APPROVE` → `APPROVAL` if `approval.required`, else → `DOCUMENT_GENERATION` |
| **Failure** | `HUMAN_REJECT` → `REJECTED` (§ 2.2) |
| **Retry** | `HUMAN_REQUEST_CHANGES` → the state of the step named by `reviews.target_step_id`, as a `RETRY` with `attempt + 1`. For a document review, that step is `DOCUMENT_GENERATION` |
| **Human review** | `HUMAN_ESCALATE` → self-loop; `reviews.escalation_level + 1`; a new `review_assignments` row for `human_review.escalation_role` |
| **Cancel** | → `CANCELLED` |
| **Exit** | The review has a terminal `status` and every assignment is decided or superseded |

`HUMAN_REQUEST_INFORMATION` → `WAITING_FOR_INPUT` with `resume_state='HUMAN_REVIEW'`.

**Defects fixed:**
- *"REQUEST_CHANGES returns to the appropriate previous state"* is replaced by
  `reviews.target_step_id` — a stored, deterministic destination (`06 § 39.1`).
- `REJECT` now has a destination (§ 2.2).
- `ESCALATE` now has a mechanism. `08 § 17` requires escalation to be recorded as an event;
  a self-loop plus a new assignment row records both the event and the new responsibility.
  The escalation **target role** is 🟠 D-07.
- `APPROVE` now routes to `APPROVAL`, not directly to `DOCUMENT_GENERATION`. See § 5.12.

## 5.12 APPROVAL — conditional

| Aspect | Definition |
| --- | --- |
| **Entry** | From `POLICY_EVALUATION` (`approval.required` or risk threshold exceeded) or from `HUMAN_REVIEW` on `HUMAN_APPROVE` |
| **Processing** | Create an `approvals` row with `model` from `approval.model` and `steps_total`, plus `approval_steps` from `approval.steps`. Activate step 1. Wait for decisions. `lock_version` guards concurrent decisions (`12 § 35`) |
| **Success** | All required steps `APPROVED` → `DOCUMENT_GENERATION` (`HUMAN_APPROVE`) |
| **Failure** | Any blocking step `REJECTED` → `REJECTED` (`HUMAN_REJECT`) |
| **Retry** | `HUMAN_REQUEST_CHANGES` → the state named by the linked `reviews.target_step_id`, else `DOCUMENT_GENERATION` |
| **Human review** | Already human. Escalation is expressed as an additional `approval_steps` row, not a loop |
| **Cancel** | → `CANCELLED` |
| **Exit** | `approvals.status` is terminal, `decided_at` set, `APPROVAL_GRANTED` or `APPROVAL_REJECTED` audited |

**Defect fixed — `APPROVAL` was unreachable.** Revision 1 lists `APPROVAL` among its 18 states but
no transition anywhere targets it: `POLICY_EVALUATION` routes to `HUMAN_REVIEW` or
`DOCUMENT_GENERATION`, and `HUMAN_REVIEW.APPROVE` routes to `DOCUMENT_GENERATION`.

**Evidence that it must be reachable:**

| Source | Statement |
| --- | --- |
| `01 § CORE USER JOURNEY` | *… Validation → Human Review if required → **Approval** → Document Generation …* |
| `13 § FINAL ACCEPTANCE` | *… Validate → Review → **Approve** → Generate BRD …* |
| `workflow-running.png` | Step **7 of 9** in the canonical run timeline is **Approval**, between *Validation* and *Document Generation* |
| `12 § 42.6` | Requires `APPROVAL` to be reachable |
| `11 § 5` | `DOCUMENT_REVIEW` and `DOCUMENT_APPROVE` are **separate** permissions |

Two inbound edges are added: `POLICY_EVALUATION → APPROVAL` and
`HUMAN_REVIEW --HUMAN_APPROVE--> APPROVAL`. This **overrides** revision 1's
`HUMAN_REVIEW.APPROVE → DOCUMENT_GENERATION` line, which is reported here as the conflict it is.
Review and approval remain distinct gates because `11 § 5` gives them distinct permissions —
collapsing them would let a reviewer approve.

When `approval.required` is false the state is skipped by **R5**; `12 § 11` covers both paths.

## 5.13 DOCUMENT_GENERATION

| Aspect | Definition |
| --- | --- |
| **Entry** | From `POLICY_EVALUATION`, `HUMAN_REVIEW`, or `APPROVAL` |
| **Processing** | For each requested `document_type`: create a `generation_runs` row, **freeze sources** into `generation_run_sources` and set `frozen_at` (`09 § 3`), run the Document Supervisor (`08 § 11`), write `document_versions` + `document_sections` + `document_sources`. A section with no source is `provenance_state='UNVERIFIED'` (`09 § 19`) |
| **Success** | → `DOCUMENT_VALIDATION` (`SUCCESS`) |
| **Failure** | Retryable → self `RETRY`, new `generation_runs` row with `attempt + 1` and `retry_of_id`; non-retryable → `FAILED` with `09 § 28`'s four fields |
| **Retry** | Self-loop bounded by `retry.max_attempts.agent` |
| **Human review** | → `HUMAN_REVIEW` if the Document Supervisor sets `requires_review` |
| **Cancel** | → `CANCELLED`; partial `document_versions` rows stay `status='FAILED'`, never `DRAFT` |
| **Exit** | One `document_versions` row per requested type, each with ≥ 1 section |

Sources are frozen **before** generation so a concurrent requirement edit cannot change the
document's basis mid-run — `09 § 7`'s guarantee, now with `generation_run_sources` behind it.

## 5.14 DOCUMENT_VALIDATION

| Aspect | Definition |
| --- | --- |
| **Entry** | From `DOCUMENT_GENERATION` |
| **Processing** | Run `09 § 20`'s nine checks per version; write `validation_runs` with `validation_kind='DOCUMENT'` and `document_version_id` |
| **Success** | `PASSED` → `COMPLETED` (`SUCCESS`) |
| **Failure** | `FAILED` and under budget → `DOCUMENT_GENERATION` (`RETRY`); at budget → `retry.exhausted_action` |
| **Retry** | Bounded by `retry.max_attempts.document_validation` |
| **Human review** | On exhaustion with `retry.exhausted_action='HUMAN_REVIEW'` → `HUMAN_REVIEW` with `target_step_id` = the generation step |
| **Cancel** | → `CANCELLED` |
| **Exit** | Every generated version has a `validation_runs` row |

**Defect fixed — the unbounded loop.** Revision 1 reads *"If validation fails:
DOCUMENT_GENERATION"* with no cap, so a document that cannot pass validation loops forever. Now
bounded by `retry.max_attempts.document_validation`, with the exhaustion destination taken from
`retry.exhausted_action` exactly as `12 § 11-G` requires. Both values are 🟠 D-05.

## 5.15 WAITING_FOR_INPUT

| Aspect | Definition |
| --- | --- |
| **Entry** | From `DATA_AVAILABILITY` on `MISSING`; from `HUMAN_REVIEW` on `HUMAN_REQUEST_INFORMATION`. `workflow_runs.resume_state` is set to the originating state and `status='WAITING'` |
| **Processing** | None. The run holds. The UI shows what is required, from `validation_runs.missing` or the review comment — never invented |
| **Success** | `INPUT_SUPPLIED` → `workflow_runs.resume_state` as a `RETRY` on that state |
| **Failure** | `TIMEOUT` after `waiting_for_input.timeout_hours` → `FAILED`, `failure_code='INPUT_TIMEOUT'` |
| **Retry** | Resumption *is* the retry |
| **Human review** | none |
| **Cancel** | → `CANCELLED` |
| **Exit** | `resume_state` is cleared and `status` returns to `RUNNING` |

**Defect fixed — the state had no exit.** Revision 1 routes two paths into
`WAITING_FOR_INPUT` and defines no way out, making it a sink. `workflow_runs.resume_state`
(`06 § 22`) is the column that resolves it.

🟠 **D-29** — no file specifies a timeout. Until `waiting_for_input.timeout_hours` exists the
`TIMEOUT` edge is inert and the run waits indefinitely, which is the safer of the two behaviours:
it cannot destroy work, and the user can still cancel.

## 5.16 COMPLETED · 5.17 FAILED · 5.18 REJECTED · 5.19 CANCELLED

| | COMPLETED | FAILED | REJECTED | CANCELLED |
| --- | --- | --- | --- | --- |
| **Entry** | `DOCUMENT_VALIDATION` `PASSED` | Any state, non-recoverable or exhausted | `HUMAN_REVIEW` / `APPROVAL` reject | Any of the 14 non-terminal states |
| **Processing** | Set `completed_at`, `status='COMPLETED'`; emit `WORKFLOW_RUN_COMPLETED` | Set `failure_code`, `failure_message`, `completed_at`; emit `WORKFLOW_RUN_FAILED` | Set `completed_at`; emit `WORKFLOW_RUN_REJECTED` | Set `completed_at`; emit `WORKFLOW_RUN_CANCELLED` |
| **Success / Failure / Retry / Review / Cancel** | none — terminal (**R7**) | none. A manual `POST /retry` creates a **new run**, it does not revive this one | none | none |
| **Exit** | Immutable | Immutable | Immutable | Immutable |

**Cancellable states — all 14 non-terminal:** `CREATED`, `INPUT_VALIDATION`, `DATA_COLLECTION`,
`REQUIREMENT_ANALYSIS`, `SECURITY_ANALYSIS`, `COMPLIANCE_ANALYSIS`, `DATA_AVAILABILITY`,
`RISK_ANALYSIS`, `VALIDATION`, `POLICY_EVALUATION`, `HUMAN_REVIEW`, `APPROVAL`,
`DOCUMENT_GENERATION`, `DOCUMENT_VALIDATION`, `WAITING_FOR_INPUT`.

Revision 1's *"Any cancellable state → CANCELLED"* never said which states those were; the set is
now closed. Cancellation requires `WORKFLOW_CANCEL` and is audited (`WORKFLOW_RUN_CANCELLED`) —
revision 1 already required *"authorized and audited"*, and `workflow-running.png`'s **Cancel Run**
button is the UI for it.

**`FAILED` versus `REJECTED`:** `FAILED` is a technical fault or an exhausted retry budget;
`REJECTED` is an accountable human decision. `11 § 21` audits them as separate events.

---

# 6. RETRY MODEL

| Property | Definition |
| --- | --- |
| **Unit** | One `workflow_steps` row per `(state, attempt)` |
| **Counter** | `workflow_steps.attempt`, starting at 1 |
| **Budget** | `retry.max_attempts.agent` for agent and system states; `retry.max_attempts.document_validation` for § 5.14 |
| **Backoff** | `retry.backoff_strategy` |
| **Exhaustion** | `retry.exhausted_action` ∈ { `HUMAN_REVIEW`, `FAILED` } |
| **Recorded per attempt** | attempt number, reason (`transition_trigger`), error (`error_code` + `error`), timestamp, actor (`workflow_state_transitions.actor_*`), result (`status`) |
| **Manual retry** | `POST /workflow-runs/{run_id}/retry` requires `WORKFLOW_RETRY`, permitted only from `FAILED` or a `HUMAN_REVIEW` awaiting changes; audited as `WORKFLOW_RUN_RETRIED` |
| **Non-retryable** | `INPUT_VALIDATION` (deterministic), `POLICY_EVALUATION` (needs configuration change, not repetition), all terminal states |

The six recorded facts are exactly revision 1's RETRIES list, now with the columns to hold them.
**All four policy values are 🟠 D-05.** Under **R4**, no retry executes until they exist — the
platform must not default to an invented ceiling.

---

# 7. TRANSITION TABLE

Complete and closed. Every state has at least one inbound edge; every non-terminal state has at
least one outbound edge.

| From | Trigger | To | Condition |
| --- | --- | --- | --- |
| — | `START` | `CREATED` | Run created |
| `CREATED` | `SUCCESS` | `INPUT_VALIDATION` | — |
| `CREATED` | `FAILURE` | `FAILED` | Definition/policy unresolvable |
| `INPUT_VALIDATION` | `SUCCESS` | `DATA_COLLECTION` | Inputs valid |
| `INPUT_VALIDATION` | `FAILURE` | `FAILED` | Invalid input |
| `DATA_COLLECTION` | `SUCCESS` | `REQUIREMENT_ANALYSIS` | — |
| `DATA_COLLECTION` | `RETRY` | `DATA_COLLECTION` | Transient, under budget |
| `DATA_COLLECTION` | `FAILURE` | `FAILED` | — |
| `REQUIREMENT_ANALYSIS` | `SUCCESS` | `SECURITY_ANALYSIS` | `security_analysis_enabled` |
| `REQUIREMENT_ANALYSIS` | `SKIP` | `COMPLIANCE_ANALYSIS` | `!security` ∧ `compliance` |
| `REQUIREMENT_ANALYSIS` | `SKIP` | `DATA_AVAILABILITY` | `!security` ∧ `!compliance` |
| `REQUIREMENT_ANALYSIS` | `RETRY` | `REQUIREMENT_ANALYSIS` | Retryable, under budget |
| `REQUIREMENT_ANALYSIS` | `FAILURE` | `FAILED` | — |
| `REQUIREMENT_ANALYSIS` | `POLICY` | `HUMAN_REVIEW` | `requires_review` ∨ exhausted |
| `SECURITY_ANALYSIS` | `SUCCESS` | `COMPLIANCE_ANALYSIS` | `compliance_analysis_enabled` |
| `SECURITY_ANALYSIS` | `SKIP` | `DATA_AVAILABILITY` | `!compliance` |
| `SECURITY_ANALYSIS` | `RETRY` | `SECURITY_ANALYSIS` | Retryable, under budget |
| `SECURITY_ANALYSIS` | `FAILURE` | `FAILED` | — |
| `SECURITY_ANALYSIS` | `POLICY` | `HUMAN_REVIEW` | `requires_review` ∨ exhausted |
| `COMPLIANCE_ANALYSIS` | `SUCCESS` | `DATA_AVAILABILITY` | — |
| `COMPLIANCE_ANALYSIS` | `RETRY` | `COMPLIANCE_ANALYSIS` | Retryable, under budget |
| `COMPLIANCE_ANALYSIS` | `FAILURE` | `FAILED` | — |
| `COMPLIANCE_ANALYSIS` | `POLICY` | `HUMAN_REVIEW` | `requires_review` ∨ exhausted |
| `DATA_AVAILABILITY` | `SUCCESS` | `RISK_ANALYSIS` | `AVAILABLE` ∧ `risk_analysis_enabled` |
| `DATA_AVAILABILITY` | `SKIP` | `VALIDATION` | `AVAILABLE` ∧ `!risk` |
| `DATA_AVAILABILITY` | `POLICY` | `WAITING_FOR_INPUT` | `MISSING` |
| `DATA_AVAILABILITY` | `POLICY` | `HUMAN_REVIEW` | `PARTIAL` — **SAFE INTERIM**, 🟠 D-03 |
| `DATA_AVAILABILITY` | `RETRY` | `DATA_AVAILABILITY` | Retryable, under budget |
| `DATA_AVAILABILITY` | `FAILURE` | `FAILED` | — |
| `RISK_ANALYSIS` | `SUCCESS` | `VALIDATION` | — |
| `RISK_ANALYSIS` | `RETRY` | `RISK_ANALYSIS` | Retryable, under budget |
| `RISK_ANALYSIS` | `FAILURE` | `FAILED` | Incl. missing `risk.scoring_method` |
| `RISK_ANALYSIS` | `POLICY` | `HUMAN_REVIEW` | `requires_review` ∨ exhausted |
| `VALIDATION` | `SUCCESS` | `POLICY_EVALUATION` | `PASSED` |
| `VALIDATION` | `RETRY` | *`target_step_id`'s state* | `FAILED` ∧ retryable ∧ under budget |
| `VALIDATION` | `POLICY` | `HUMAN_REVIEW` | Exhausted ∧ action `HUMAN_REVIEW` |
| `VALIDATION` | `FAILURE` | `FAILED` | Exhausted ∧ action `FAILED` |
| `POLICY_EVALUATION` | `POLICY` | `HUMAN_REVIEW` | `human_review.required` |
| `POLICY_EVALUATION` | `POLICY` | `APPROVAL` | `approval.required` ∨ risk > threshold |
| `POLICY_EVALUATION` | `POLICY` | `DOCUMENT_GENERATION` | Neither required |
| `POLICY_EVALUATION` | `FAILURE` | `FAILED` | Required rule absent (**R4**) |
| `HUMAN_REVIEW` | `HUMAN_APPROVE` | `APPROVAL` | `approval.required` |
| `HUMAN_REVIEW` | `HUMAN_APPROVE` | `DOCUMENT_GENERATION` | `!approval.required` |
| `HUMAN_REVIEW` | `HUMAN_REJECT` | `REJECTED` | — |
| `HUMAN_REVIEW` | `HUMAN_REQUEST_CHANGES` | *`reviews.target_step_id`'s state* | — |
| `HUMAN_REVIEW` | `HUMAN_REQUEST_INFORMATION` | `WAITING_FOR_INPUT` | — |
| `HUMAN_REVIEW` | `HUMAN_ESCALATE` | `HUMAN_REVIEW` | `escalation_level + 1` |
| `APPROVAL` | `HUMAN_APPROVE` | `DOCUMENT_GENERATION` | All required steps approved |
| `APPROVAL` | `HUMAN_REJECT` | `REJECTED` | Blocking step rejected |
| `APPROVAL` | `HUMAN_REQUEST_CHANGES` | *`target_step_id`* ∨ `DOCUMENT_GENERATION` | — |
| `DOCUMENT_GENERATION` | `SUCCESS` | `DOCUMENT_VALIDATION` | — |
| `DOCUMENT_GENERATION` | `RETRY` | `DOCUMENT_GENERATION` | Retryable, under budget |
| `DOCUMENT_GENERATION` | `FAILURE` | `FAILED` | — |
| `DOCUMENT_GENERATION` | `POLICY` | `HUMAN_REVIEW` | `requires_review` |
| `DOCUMENT_VALIDATION` | `SUCCESS` | `COMPLETED` | `PASSED` |
| `DOCUMENT_VALIDATION` | `RETRY` | `DOCUMENT_GENERATION` | `FAILED`, under budget |
| `DOCUMENT_VALIDATION` | `POLICY` | `HUMAN_REVIEW` | Exhausted ∧ action `HUMAN_REVIEW` |
| `DOCUMENT_VALIDATION` | `FAILURE` | `FAILED` | Exhausted ∧ action `FAILED` |
| `WAITING_FOR_INPUT` | `INPUT_SUPPLIED` | *`resume_state`* | Input received |
| `WAITING_FOR_INPUT` | `TIMEOUT` | `FAILED` | 🟠 D-29 |
| *any of the 14 non-terminal* | `CANCEL` | `CANCELLED` | Authorized |

**Reachability — resolved.** All 19 states have an inbound edge. `APPROVAL` has two (§ 5.12);
`REJECTED` has two (§ 2.2); `WAITING_FOR_INPUT` has two in and two out (§ 5.15).

---

# 8. UI PROJECTION

`03 § 15` and `workflow-running.png` render a **step timeline**, not the raw enum.

| Timeline label (canonical) | State |
| --- | --- |
| Input Validation | `INPUT_VALIDATION` |
| Data Collection | `DATA_COLLECTION` |
| Requirements Analysis | `REQUIREMENT_ANALYSIS` |
| Security Analysis | `SECURITY_ANALYSIS` |
| Compliance Analysis | `COMPLIANCE_ANALYSIS` |
| Risk Analysis | `RISK_ANALYSIS` |
| Validation | `VALIDATION` |
| Approval | `APPROVAL` |
| Document Generation | `DOCUMENT_GENERATION` |

**Two reported gaps between the canonical screen and this machine:**

1. **`DATA_AVAILABILITY` is not displayed** in `workflow-running.png`'s nine steps, yet it is a
   mandatory state that can send a run to `WAITING_FOR_INPUT`. A run holding for missing data
   would show no reason. The state is **kept** — `08 § 9`, `13 § CONDITIONAL` and `03 § 16` all
   require it — and the omission is recorded as a canonical-UI gap for the product owner.
   🔵 **MISSING CONTRACT**: whether the timeline shows 9 steps or 10.
2. **Progress percentage and estimated completion.** The screen shows *60%* and an estimated time.
   No file defines how either is computed, and `06 § 22` therefore stores neither.
   `CLAUDE.md § 1` forbids fake workflow progress. 🔵 **MISSING CONTRACT.** Until a formula is
   specified, the UI must show completed-versus-total steps, which is derivable.

`WAITING_FOR_INPUT`, `HUMAN_REVIEW`, `POLICY_EVALUATION` and `DOCUMENT_VALIDATION` appear as
status banners rather than timeline rows. `03 § 15` additionally requires state history, which
`workflow_state_transitions` supplies.

---

# 9. AUTHORIZATION AND AUDIT PER TRANSITION

| Trigger | Permission | Audit event (`11 § 21.2`) |
| --- | --- | --- |
| `START` | `WORKFLOW_RUN` | `WORKFLOW_RUN_STARTED` |
| `SUCCESS`, `SKIP`, `POLICY` | system | `WORKFLOW_STATE_CHANGED` |
| `RETRY` (auto) | system | `WORKFLOW_STEP_RETRIED` |
| `RETRY` (manual) | `WORKFLOW_RETRY` | `WORKFLOW_RUN_RETRIED` |
| `CANCEL` | `WORKFLOW_CANCEL` | `WORKFLOW_RUN_CANCELLED` |
| `HUMAN_APPROVE` (review) | `DOCUMENT_REVIEW` | `REVIEW_APPROVED` |
| `HUMAN_APPROVE` (approval) | `DOCUMENT_APPROVE` | `APPROVAL_GRANTED` |
| `HUMAN_REJECT` | `DOCUMENT_REVIEW` / `DOCUMENT_APPROVE` | `REVIEW_REJECTED` / `APPROVAL_REJECTED` |
| `HUMAN_REQUEST_CHANGES` | `DOCUMENT_REVIEW` | `REVIEW_CHANGES_REQUESTED` |
| `HUMAN_REQUEST_INFORMATION` | `DOCUMENT_REVIEW` | `REVIEW_INFORMATION_REQUESTED` |
| `HUMAN_ESCALATE` | `DOCUMENT_REVIEW` | `REVIEW_ESCALATED` |
| `INPUT_SUPPLIED` | `WORKFLOW_RUN` | `WORKFLOW_INPUT_SUPPLIED` |
| `FAILURE` | system | `WORKFLOW_RUN_FAILED` |
| `TIMEOUT` | system | `WORKFLOW_RUN_FAILED` |

`DOCUMENT_REVIEW` and `DOCUMENT_APPROVE` are distinct in `11 § 5`, so a reviewer cannot approve
and an approver's decision is recorded under a different event. **R6**: `actor_type` must be
`USER` for every `HUMAN_*` trigger — enforced by constraint, tested by `12 § 42.7`.

---

# 10. DEFECT RESOLUTION SUMMARY

| # | Revision-1 defect | Resolution | § |
| --- | --- | --- | --- |
| 1 | `APPROVAL` unreachable | Two inbound edges added; overrides `HUMAN_REVIEW.APPROVE → DOCUMENT_GENERATION` | 5.12 |
| 2 | `REJECT` had no destination | `REJECTED` added as a terminal state (⚠ amendment) | 2.2 |
| 3 | `RETRY` referenced but not a state | Modelled as a trigger + `workflow_steps.attempt` | 2.3, 6 |
| 4 | `PARTIAL` undefined | 🟠 D-03 stated; SAFE INTERIM `HUMAN_REVIEW` | 5.7 |
| 5 | `WAITING_FOR_INPUT` had no exit | `resume_state` + `INPUT_SUPPLIED` + `TIMEOUT` | 5.15 |
| 6 | `COMPLIANCE_ANALYSIS` had no success target | → `DATA_AVAILABILITY` | 5.6 |
| 7 | `RISK_ANALYSIS` had a duplicate branch | Skip edge moved to the predecessor (**R5**) | 5.8 |
| 8 | Validation failure retried nothing specific | Retries `validation_runs.target_step_id` | 5.9 |
| 9 | `REQUEST_CHANGES` → *"appropriate previous state"* | `reviews.target_step_id` | 5.11 |
| 10 | `ESCALATE` had no mechanism | Self-loop + `escalation_level` + new assignment | 5.11 |
| 11 | `DOCUMENT_VALIDATION` loop unbounded | Capped; exhaustion via `retry.exhausted_action` | 5.14 |
| 12 | "Any cancellable state" undefined | The 14 non-terminal states enumerated | 5.19 |
| 13 | No retry ceiling | `retry.max_attempts.*` bound to `policy_rules` (🟠 D-05) | 6 |

---

# 11. REMAINING DECISIONS

| ID | Blocks | Interim behaviour |
| --- | --- | --- |
| 🟠 **D-03** | `DATA_AVAILABILITY` on `PARTIAL` | SAFE INTERIM `HUMAN_REVIEW`, labelled interim (§ 5.7) |
| 🟠 **D-04** | `approval.required`, `approval.model`, `approval.steps`, `human_review.sla_hours` | `POLICY_EVALUATION` halts under **R4** |
| 🟠 **D-05** | All four `retry.*` rules | No retry executes; the run halts |
| 🟠 **D-06** | `risk.approval_threshold`, `risk.scoring_method` | `risks.score` stays `NULL`; threshold routing halts |
| 🟠 **D-07** | `human_review.escalation_role` | `HUMAN_ESCALATE` is unavailable |
| 🟠 **D-29** | `waiting_for_input.timeout_hours` | The `TIMEOUT` edge is inert; runs wait indefinitely |
| ⚠ **A-01** | `REJECTED` as a 19th state | Applied and reported; vetoable |
| 🔵 **MC** | Timeline step count (9 or 10); progress metric | Show completed/total steps only (§ 8) |
