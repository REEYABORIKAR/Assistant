# DEPENDENCY MAP

**Revision:** 3 (2026-08-26)
**Purpose:** build ordering, coupling, and the exact gate on every phase
**Companion documents:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)

Status tags: ✅ RESOLVED · 🟠 DECISION REQUIRED · 🔵 MISSING CONTRACT · 🔴 BLOCKER

**Changed since revision 2:** all 13 specifications are now populated — `03`, `08`, `09`, `11`
were written at 16:13–16:15 and `12` gained §§ 42–44. Revision 2's *"four empty specs"* gating
model is **withdrawn**. The critical path no longer runs through missing documents; it now runs
through **six structural gaps** (schema, state machine, policy store, registry, review entities,
traceability) and **24 open decisions**.

---

## 1. SPECIFICATION DEPENDENCY GRAPH

```
CLAUDE.md  (governing rules — overrides on conflict)
    │
    ├── 01_MASTER_PRODUCT_SPEC ✅ ──── scope of everything below
    │
    ├── 02_UI_DESIGN_SPEC ✅ ────┐
    ├── docs/ui/ (15 screens) ───┴──> 03_PAGE_SPECIFICATION ✅ (32 §, 24 routes)
    │                                     │
    │                                     └──> frontend pages
    ├── 04_BACKEND_ARCHITECTURE ✅ ─┬──> 05_WORKFLOW_SPECIFICATION ✅ (18 states, 8 defective)
    │                               ├──> 06_DATABASE_SCHEMA ✅ (32 tables, 20 missing)
    │                               ├──> 07_API_SPECIFICATION ✅ (62 endpoints, 41 missing)
    │                               ├──> 08_AGENT_SPECIFICATION ✅ (18 §, all 8 agents)
    │                               ├──> 09_DOCUMENT_GENERATION_SPEC ✅ (29 §, 11 types)
    │                               ├──> 10_INTEGRATION_SPEC ✅
    │                               └──> 11_SECURITY_SPEC ✅ (27 §)
    │
    ├── 12_TEST_PLAN ✅ ── validates all of the above (44 §)
    │        └── §§ 42–44 now gate the specifications themselves
    └── 13_ACCEPTANCE_CRITERIA ✅ ── gates release
```

**All 13 specifications exist.** `12` has moved from *revealing* gaps to *enforcing* closure:
`§ 42` is a 27-check consistency gate, `§ 43` a completeness gate (`STATUS = BLOCKED` when any
contract is missing), `§ 44` a 16-item decision gate. This map is aligned to all three.

**The dependency edges that are now broken in the other direction.** With every spec present,
the failures are no longer *absent documents* but *documents that disagree*:

| Edge | Failure |
| --- | --- |
| `03` → `docs/ui/` | `03 § 3`'s sidebar contradicts all 13 authenticated screens **and** `03 § 2`'s own precedence rule (N-02, N-03) |
| `03` → `07` | two path conflicts: file upload, workflow run (N-51, N-52) |
| `09` → `06` | source freeze, provenance, review, traceability, test cases have **no schema** (N-44…N-47) |
| `09` → `04` | `04` omits 3 document types and has no DOCX or XLSX service (N-08, N-09) |
| `09` → `07` | no XLSX endpoint; retry endpoint deliberately undecided (N-10, N-12) |
| `11` → `06` | 17 tables lack `tenant_id`; no tool registry; no credential columns (N-53, N-55, N-56) |
| `08` → `06` | `agent_runs` cannot store 6 required fields (N-54) |
| `08` → `05` | Validation Agent routes to `RETRY`, which is not a state (N-21) |
| `05` → `12 § 42.3/42.6` | 8 of 18 states defective; `APPROVAL` unreachable (N-14…N-29) |
| `01` → `05` | `01` ships "configurable" workflows; `05` specifies one fixed machine (N-30) |

---

## 2. HARD DEPENDENCY CHAINS

Each arrow is a strict prerequisite: the right side cannot be correctly built first.

```
git repository
  └─> Phase 0 tooling
        └─> Phase 1 foundation
              └─> Authentication  ──> Tenancy  ──> everything data-touching
                                        │
        ┌───────────────────────────────┘
        ├─> Projects ─> Chat ─> Files ─> extraction ─> chunking ─> retrieval
        │                                                            │
        └─> Policy store ─> Workflow engine <────────────────────────┘
                  └─> Supervisor ─> Agents ─> Validation
                            │
                            ├─> Review entities ─> Human review ─> Approval
                            └─> Tool Registry ─> Jira / Confluence / Notion
                                      │
     test_cases + traceability <──────┤
            └─> Document engine <─────┘
                  └─> N document types (D-08)
                        └─> Document validation
                              └─> PDF / DOCX / XLSX
                                    └─> Versioning ─> Traceability
                                          └─> Audit ─> Observability
                                                └─> Security hardening ─> E2E
```

**Non-negotiable ordering facts**

1. **Tenancy precedes the first migration.** Adding `tenant_id` to 17 tables later means
   rewriting every query and backfilling every row. `11 § 3` and `12 § 8`/`§ 42.20` gate on it.
   🔴 **D-01 / BL-1**
2. **A policy store precedes the workflow engine.** `05 § POLICY_EVALUATION` is a state; four
   agents defer to policy (`08 § 8` risk scoring, `§ 9` PARTIAL, `§ 10` validation routing,
   `§ 15` retry limit); `12 § 42.4` requires every workflow condition to have a defined policy.
   **No policy entity or format exists.** 🔴 **BL-4** — new in revision 3.
3. **The state machine must be repaired before the engine is built.** 8 of 18 states are
   defective, `APPROVAL` is unreachable, and `RETRY` is referenced but does not exist.
   Implementing around these would put workflow decisions in code rather than in the spec —
   a `CLAUDE.md § 2` violation. 🔴 **BL-2**
4. **Review entities precede human review.** `09 § 21` and `03 § 23` require REVIEW,
   REVIEW_ASSIGNMENT, REVIEW_SECTION, REVIEW_COMMENT; `06` defines none; `07` has one verb for
   eight capabilities. 🔴 **BL-6**
5. **Traceability precedes document generation.** `09 § 12` and `12 § 42.11–13` require every
   RTM mapping to reference an actual stored record. `test_cases`,
   `traceability_relationships` and a **Design entity** do not exist. Generating documents
   first produces documents whose traceability cannot be stored. 🔴 **BL-8**
6. **Source-version freeze precedes the first generated document.** `09 § 7` is the integrity
   guarantee of the whole document engine: it needs `requirements.version`, a
   `generation_runs` entity and `document_sources.source_version` — none of which exist.
   Retrofitting means regenerating every document. 🔴
7. **Tool Registry precedes all three integrations.** `CLAUDE.md § 4`, `11 § 16–17` and
   `08 § 14` make it the sole gate for external effects; `12 § 29` tests it independently with
   five cases. **No registry table exists** — only `tool_calls`. 🔴 **BL-7**
8. **The audit event catalogue precedes the first mutating endpoint.** `CLAUDE.md § 3` requires
   an audit event per applicable button; `11 § 21` fixes the 7 record fields; **no spec names a
   single event.** Retrofitting means revisiting every handler. 🔴 **BL-10 / MC-01**
9. **Structured-output validation precedes any agent.** `08 § 3`'s 16-stage pipeline and
   `CLAUDE.md § 4` have no bypass; `12 § 40` makes the schema layer the deterministic one.
   ✅ now fully specified.
10. **Version immutability precedes approval.** `09 § 5` and `12 § 24`/`§ 42.15` require v1.0 be
    unchanged after a v1.1 revision. Approving before immutability exists creates mutable
    "approved" records. 🔵 mechanism undefined.
11. **The navigation model precedes the application shell.** Revision 2 listed the sidebar as
    buildable in phase 1. It is not: `03 § 3` contradicts the canonical UI and `03`'s own
    precedence rule, and the canonical items are global while `03`'s routes are project-scoped.
    🔴 **D-18 / BL-11** — new in revision 3.

---

## 3. PHASE GATES

| # | Phase | CLAUDE.md order | Gate | Status |
| --- | --- | --- | --- | --- |
| 0 | Pre-implementation | — | none | 🟢 **READY** |
| 1 | Foundation | 1 | none for primitives · **sidebar shell blocked by D-18** | 🟢 **READY** (shell excepted) |
| 2 | Authentication | 2 | `sessions` · `refresh_tokens` · `password_reset_tokens` · **D-21** consent · SSO unspecified · **D-13** rate limits · **BL-10** audit names | 🔵 |
| 3 | Multi-tenancy | 3 | **D-01 / BL-1** — strategy undecided; 17 tables lack `tenant_id`; `06` has no types, keys, or indexes | 🔴 |
| 4 | Projects | 4 | phase 3 · activity feed · count aggregates | 🔵 after 3 |
| 5 | Chat | 5 | **D-17** transport · **D-16** action set · retry/regenerate API · View Risks target · project-scoped chat API | 🔵 |
| 6 | Files | 6 | scanner + quarantine column (`11 § 8`, `12 § 10`) · embeddings · **N-51** path conflict | 🔵 |
| 7 | Workflow engine | 7 | **D-02 / BL-3** fixed vs configurable · **BL-2** 8 defective states · **D-03** PARTIAL · **D-05** retry · **BL-4** policy store | 🔴 |
| 8 | Supervisor | 8 | ✅ contract (`08 § 4`) · **BL-4** policy · `agent_runs` 6 missing fields | 🔵 ⬆ *(was 🔴)* |
| 9 | Agents | 9 | ✅ all 8 contracts · **D-06** risk scoring · **D-03** PARTIAL · no per-agent tool allow-list | 🔵 ⬆ *(was 🔴)* |
| 10 | Validation | 10 | ✅ outcomes + 8 dimensions (`08 § 10`) · **N-21** routes to nonexistent `RETRY` · **N-32** two validation states, one endpoint | 🔵 ⬆ *(was 🔴)* |
| 11 | Human review | 11 | **BL-6** — 4 entities absent, every endpoint absent, section status and comments unstorable | 🔴 |
| 12 | Approval | 12 | **D-04 / BL-5** model · **N-14** `APPROVAL` unreachable · reject + request-changes APIs · `12 § 35` concurrency | 🔴 |
| 13 | Tool Registry | 13 | **BL-7** no registry table · no tool catalog · **D-22** blocked-request audit | 🔴 |
| 14 | Jira | 14 | phase 13 · credential columns · sandbox (**D-24**) · retry contract | 🔵 |
| 15 | Confluence | 15 | phase 13 · auth method unstated · test-connection API | 🔵 |
| 16 | Notion | 16 | phase 13 · auth method unstated · test-connection API | 🔵 |
| 17 | Document engine | 17 | **D-08 / BL-9** type set · no `generation_runs` · no `source_version` · immutability mechanism | 🔴 |
| 18 | BRD | 18 | ✅ **21 ordered sections** · phase 17 gates | 🔴 via 17 |
| 19 | SRS | 19 | ✅ **25 ordered sections** · phase 17 gates | 🔴 via 17 |
| 20 | FRD | 20 | 🔵 9 topics, **no ordering** — `09 § 20` validates section order | 🔴 |
| 21 | NFRD | 21 | 🔵 12 topics, no ordering · **D-08** (not a canonical tile) · SLA values deferred | 🔴 |
| 22 | RTM | 22 | **BL-8** entities · **D-19** columns + chain · XLSX | 🔴 |
| 23 | Test documents | 23 | ✅ TEST_CASES 11 fields · **`test_cases` table absent** · TEST_PLAN unordered | 🔴 |
| 24 | Risk / security / compliance docs | 24 | ✅ field sets · **D-06** risk scoring · 3 finding tables lack evidence/remediation columns · **D-08** | 🔴 |
| 25 | Document validation | 25 | ✅ 9 checks (`09 § 20`) · **only BRD and SRS have an order to validate** | 🔴 |
| 26 | PDF / DOCX / XLSX | 26 | ✅ PDF 10 features, DOCX 5 · **no DOCX service, no XLSX service (`04`), no XLSX endpoint (`07`), no workbook spec (D-15)** | 🔴 |
| 27 | Document chat | 27 | 🔵 no page, no endpoint, no document↔conversation link | 🔴 |
| 28 | Versioning | 28 | ✅ scheme + immutability semantics (`09 § 5`) · 🔵 enforcement mechanism · 🔵 `version` type/format (**D-09**) | 🔵 |
| 29 | Traceability | 29 | **BL-8** — `test_cases`, `traceability_relationships`, **Design entity**, **D-19** | 🔴 |
| 30 | Audit | 30 | ✅ 7 fields + 13 categories · **BL-10 / D-23** no event names · **D-11** retention · 🔵 tamper-evidence | 🔵 |
| 31 | Observability | 31 | 🔵 **no spec section exists** · **D-10** quota · **D-12** RPO/RTO | 🔵 |
| 32 | Security hardening | 32 | ✅ model, permissions, injection defence, tool chain · **D-01**, **D-07**, **D-13** · **BL-4** + **BL-7** back the specified policy and registry gates | 🔵 ⬆ *(was 🔴)* |
| 33 | E2E | 33 | ✅ 21-step journey (`12 § 36`) · **D-24** framework, coverage, sandboxes | 🔵 |

**Movement since revision 2:** phases 8, 9, 10 and 32 🔴 → 🔵 — the agent and security designs
now exist. Phases 18–27 are broken out individually because `09` now differentiates them.
Phases 3, 7, 11, 12, 13, 17–27, 29 remain 🔴, for **structural** reasons (schema, state machine,
policy, registry) rather than missing documents. Phase 1's sidebar shell regressed to 🔴 (D-18).

---

## 4. WHAT IS BUILDABLE NOW

Independent of every open item.

### Phase 0 — 🟢
`git init` + `.gitignore` (the repository is still not under version control, and `12 § 37`'s CI
gate presupposes one) · monorepo layout (`apps/web`, `apps/api`, `packages/`) · `.env.example`
with keys and **no values** (`CLAUDE.md § SECRETS`, `11 § 9`) · Python and Node toolchain
pinning · docker-compose for PostgreSQL, Redis and object storage · CI wired to exactly
`12 § 37`'s seven gates: **build · typecheck · lint · unit · integration · migration validation ·
security**.

### Phase 1 — 🟢 (with one exception)
**Backend:** FastAPI app factory · Pydantic settings from environment · SQLAlchemy engine and
session · Alembic baseline with **no tables** (D-01 blocks the first migration) · structured
logging carrying `request_id` · the `07` / `03 § 30` error envelope as one shared exception
handler, testable against `12 § 33` · health endpoint.

**Frontend:** Next.js + TypeScript + Tailwind with tokens sampled from the canonical screens ·
TanStack Query client · React Hook Form + Zod · the six `03 § 4` page states
(LOADING, EMPTY, SUCCESS, ERROR, PERMISSION_DENIED, NOT_FOUND) as reusable primitives ·
glass-card, button and input primitives per `02 § COMPONENT STYLE`.

**Exception — the sidebar shell is NOT buildable.** Revision 2 listed it as safe on the grounds
that all 13 authenticated canonical screens agree. They do agree with each other; they do
**not** agree with `03 § 3`, and `03 § 3` contradicts `03 § 2`'s own precedence rule. Worse, the
canonical items are global while `03`'s routes are project-scoped, so every link target is
undefined. 🔴 **D-18 / BL-11**

### Also safe
The **agent harness without agents**: provider abstraction, prompt registry, model registry, the
structured-output validation gate, and the seven-bucket context assembler from `08 § 12`
(including the `UNTRUSTED_EXTERNAL_CONTENT` channel) can all be built with **zero agents
registered and zero tools registered**. `12 § 40`'s deterministic-schema layer is exactly this,
and `08 § 16`'s *"Do not hard-code a provider-specific implementation into agent logic"* makes
the abstraction mandatory anyway. Registering an agent additionally requires the policy store
(BL-4) and the tool registry (BL-7).

---

## 5. CROSS-CUTTING CONCERNS

Touch nearly every phase; cheapest to establish in phases 0–1, most expensive to retrofit.

| Concern | Touches | Status |
| --- | --- | --- |
| **Tenant scoping** | every table, query, endpoint | 🔴 **D-01** — decide before migration 1 |
| **Column types / keys / indexes** | every table | 🔴 `06` specifies none; `12 § 5` tests all of them |
| **Authorization** | every endpoint (`12 § 4` requires an authz case per endpoint) | 🔵 21 names exist but are labelled *"Example"*; no `REQUIREMENT_*`, `CONVERSATION_*`, `RISK_READ`, `WORKFLOW_READ`, `REPORT_*`, `ADMIN_MODELS`, `TOOL_EXECUTE` |
| **Audit** | every mutation | 🔵 fields ✅ + categories ✅ · **no event names — BL-10 / D-23** |
| **Error envelope** | every endpoint | ✅ `07` + `03 § 30` + `12 § 33` |
| **Six page states** | every page | ✅ `03 § 4` |
| **Permission-gated UI** | every action | 🔵 `02` requires *"Only show permitted actions"*; the catalog is illustrative |
| **Pagination** | every list + every preview | 🔵 shape ✅ (`03 § 29`), **no envelope in `07`** |
| **Realtime events** | chat, workflows, documents | 🟠 **D-17** — `02 § REALTIME` needs three streams, `07` defines one |
| **Job queue** | workflows, documents, files, agents | 🔵 technology unnamed; `CLAUDE.md` requires retry + dead-letter |
| **Structured-output validation** | every agent call | ✅ **now fully specified** (`08 § 3`) |
| **Context bucketing** | every prompt | ✅ **now fully specified** (`08 § 12`) |
| **Policy configuration** | risk threshold, retry limits, PARTIAL, validation routing, approval requirement | 🔴 **BL-4** — five consumers, no entity |
| **Traceability links** | requirements, sections, tests, risks, design, evidence | 🔴 **BL-8** |
| **Source-version freeze** | every generated document | 🔴 specified (`09 § 7`), unstorable |
| **Version immutability** | all documents | 🔵 semantics ✅, mechanism undefined |
| **Human-readable keys** | documents, reviews, approvals, runs, generation runs, requirements, risks, test cases | 🟠 **D-09** |
| **Prompt-injection defence** | every ingested document reaching a prompt | ✅ **design sound** (see [ARCHITECTURE_REVIEW.md § 8](ARCHITECTURE_REVIEW.md)) · 🔴 its policy and registry gates have no backing entity |
| **Rate limiting** | 7 operation classes | 🟠 **D-13** |
| **Accessibility** | every page | 🔵 unspecified in `02` and `03` |

---

## 6. RISK-ORDERED RETROFIT COST

| Item | Cost if deferred | Decide by |
| --- | --- | --- |
| Tenant scoping (**D-01**) | **Extreme** — 17 tables, every query, full backfill | before migration 1 |
| Column types / keys / indexes | **Extreme** — the migration itself | before migration 1 |
| Workflow architecture (**D-02**) | **Extreme** — a state machine and an interpreter are different systems | before phase 7 |
| State-machine repair (**BL-2**) | **Extreme** — transitions leak into code, violating `CLAUDE.md § 2` | before phase 7 |
| Policy store (**BL-4**) | **High** — five consumers across workflow, agents and approval | before phase 7 |
| Traceability storage (**BL-8**) | **High** — regenerate every document to populate links | before phase 17 |
| Source-version freeze | **High** — regenerate every document | before phase 17 |
| Audit event catalogue (**BL-10**) | **High** — every handler revisited; `12 § 32` untestable until then | before phase 2's first mutation |
| Approval model (**D-04**) | **High** — changes downstream state transitions and the approvals schema | before phase 12 |
| Review entities (**BL-6**) | **High** — four tables plus every review endpoint | before phase 11 |
| Tool Registry (**BL-7**) | **High** — the sole gate for all external effects | before phase 13 |
| Authorization catalog (**D-07**) | **High** — every endpoint and every UI action | before phase 2 |
| Navigation model (**D-18**) | **Medium–High** — route restructuring across every page | before phase 1's shell |
| Document type set (**D-08**) | **Medium** — per-type generators are additive, but the wizard and acceptance criteria diverge | before phase 17 |
| Realtime transport (**D-17**) | **Medium** — one adapter layer | before phase 5 |
| Identifier formats (**D-09**) | **Medium** — backfill + uniqueness across 8 entity kinds | before phase 7 |
| Version format (**D-09**) | **Medium** — data migration over existing versions | before phase 17 |
| XLSX contract (**D-15**) | **Medium** — a service plus an endpoint plus a workbook spec | before phase 26 |
| Rate limits (**D-13**) | Low–Medium — middleware configuration | before phase 32 |
| Test framework (**D-24**) | Low — tests are written per phase | before phase 1's first test |
| Accessibility | Medium — component-level rework | before phase 1's primitives |

---

## 7. THE SIX STRUCTURAL GAPS — DOWNSTREAM COST

Revision 2's table listed four empty specifications. All four now exist. What replaces them:

| Gap | Blocks | Phases | Test sections left unsatisfiable |
| --- | --- | --- | --- |
| **Database schema depth** — 20 entities absent, 15 tables with missing columns, no types/keys/indexes anywhere, 17 tables without `tenant_id` | tenancy, review, approval, traceability, tools, policy, quota | **3** — and transitively every data-touching phase | `12 § 5, 8, 42.7–14, 42.20` |
| **Workflow state machine** — 8 of 18 states defective; `APPROVAL` unreachable; `RETRY` not a state; `PARTIAL`, `REJECT`, `ESCALATE` unrouted | the engine, the supervisor loop, approval | **7, 12** | `12 § 11, 12, 18, 42.3, 42.5, 42.6` |
| **Policy store** — no entity, no format, no rules, yet `POLICY_EVALUATION` is a state and four agents defer to policy | conditional branching, risk scoring, retry, PARTIAL, approval requirement | **7, 9, 10, 12** | `12 § 11-E/F/G, 17, 19, 42.4` |
| **Tool Registry** — no table, no catalog; `tool_calls.status` has no enum | every external effect | **13, 14–16** | `12 § 29, 30, 42.17–19` |
| **Review entities** — REVIEW, REVIEW_ASSIGNMENT, REVIEW_SECTION, REVIEW_COMMENT absent; one endpoint for eight capabilities | human review, section status, comments | **11** | `12 § 42.8–10` |
| **Traceability entities** — `test_cases`, `traceability_relationships`, and **no Design entity anywhere** | RTM, test documents, traceability, XLSX | **22, 23, 26, 29** | `12 § 23, 42.11–13` |

Plus **24 open decisions**, of which **D-01, D-02, D-03, D-04, D-08, D-18, D-19** each block a
whole phase group on their own.

The database schema is the deepest: it gates phase 3, and phase 3 gates every phase that
touches data.

---

## 8. CRITICAL PATH

```
git init
  → Phase 0 tooling + CI (12 § 37)
  → Phase 1 foundation primitives   [sidebar shell excluded — D-18]
  → ═══ GATE A: decide D-01 · specify types/keys/indexes · add tenant_id ═══
  → Phase 2 authentication  (also needs sessions/refresh/reset entities, D-21, D-13, D-23)
  → Phase 3 multi-tenancy
  → Phase 4 projects
  → ═══ GATE B: decide D-02 · repair the 8 defective states · decide D-03 + D-05 · define the policy store ═══
  → Phase 7 workflow engine
  → Phases 8–10 supervisor, agents, validation  (also needs D-06 + agent_runs columns)
  → ═══ GATE C: define the 4 review entities · decide D-04 · make APPROVAL reachable ═══
  → Phases 11–12 human review, approval
  → ═══ GATE D: define the tool_registry table + tool catalog + D-22 ═══
  → Phase 13 Tool Registry
  → Phases 14–16 integrations  (also need credential columns + D-24 sandboxes)
  → ═══ GATE E: decide D-08 + D-19 · add test_cases, traceability_relationships, Design, generation_runs, source_version ═══
  → Phases 17–27 documents  (also need D-14, D-15, section ordering for 9 of 11 types)
  → Phases 28–30 versioning, traceability, audit  (D-09, D-11, D-23)
  → Phase 31 observability  (no spec section exists · D-10 · D-12)
  → Phase 32 security hardening  (D-07, D-13 · policy + registry from Gates B and D)
  → Phase 33 E2E  (D-24)
```

**Five gates.** Revision 2's five gates were four missing documents plus one question. All five
are now **structural**: schema, state machine, review entities, tool registry, traceability —
each paired with the decisions that shape it. Every gate is a specification or product action,
not a coding action.

Phases 5 and 6 sit off the critical path and can proceed in parallel after phase 4, subject to
D-16, D-17 and their own 🔵 items.

---

## 9. PARALLELISABLE WORK

Once phase 1 lands and the gates above clear in order, these tracks are independent:

- **Track A** — projects, chat, files (phases 4–6)
- **Track B** — policy store + workflow engine + supervisor + agents (phases 7–10)
- **Track C** — Tool Registry + integrations (phases 13–16)
- **Track D** — document engine + types + renderers (phases 17–27)
- **Track E** — audit + observability (phases 30–31)

Track D depends on B for agent-produced content and on the traceability entities. Track E should
start in phase 2, not phase 30 — audit is cross-cutting, `11 § 21` fixes its fields today, and
only the event names are missing.

**Track F, and it can start immediately:** the agent harness without agents — provider
abstraction, prompt registry, model registry, structured-output gate, and the `08 § 12` context
assembler. It has no dependency on any open decision.

---

## 10. IMMEDIATE NEXT ACTION

Nothing on this map can start until the plan is approved and the decisions in
[IMPLEMENTATION_PLAN.md § 6](IMPLEMENTATION_PLAN.md) are made.

When approved, the first action is `git init` — the repository is still not under version
control, it costs nothing to fix, and `12 § 37`'s CI gate presupposes it.

The first **specification** actions, in order of leverage: **D-01** (tenant isolation) and the
missing column types/keys/indexes, because together they gate the first migration and therefore
every phase after 2; then **BL-2** (repair the state machine) and **D-02**; then **BL-4** (define
the policy store).

No application code has been written.
