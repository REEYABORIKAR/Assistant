# Implementation Brief: REFYNE Prompt Builder, Verifier & Approval Loop

Attach this alongside `prompt-builder-design.md` (already in the repo/shared with you). That file
is the full design spec — sections 0-9. This brief tells you the build order, the file targets,
and the definition of done for each phase. Work phase by phase, in order. Do not skip ahead.

## Decision made on verifier placement

The design doc's Section 4 verifier is scoped to dashboard audit claims. We are extending it to
run at **both** points:

1. Right after the audit call (Section 4 as written) — powers verification badges on the 5
   dashboard tabs.
2. Right after document generation/regeneration (before the approval card is shown) — powers a
   verification summary on the approval card itself (e.g. "10 of 12 requirements traced directly
   to source, 2 flagged low-confidence").

This is one extra batched call per generation/regeneration cycle, not per-claim — keep the
batching rule from Section 4 (one call per document, all claims flattened into one list) for both
call sites. Do not verify per-claim; that defeats the token-minimization goal in Section 5.

## Ground rules (apply to every phase)

- Every LLM call must go through the existing model-fallback plumbing in `llm_service.py`
  (`_call_groq_json` or equivalent) — do not bypass it with a new ad-hoc client.
- Every new/changed endpoint needs a test in `backend/tests/` before you consider the phase done.
- Never call `/documents/generate` automatically from any `useEffect` or on-upload hook — it must
  only fire from an explicit user action. Add a test or lint check that fails CI if this is
  violated, since this is a hard product requirement, not a preference.
- Run the full existing test suite after each phase and fix any regressions before moving to the
  next phase.
- Do not remove `analyze_document_intelligence`'s "one call powers all 5 tabs" behavior — every
  change must preserve or improve token efficiency, never regress it.

---

## Phase 1 — Make document generation real (design doc §0, §3, §7.1)

**Problem:** `document_service.generate_document_content()` returns hardcoded template text
regardless of the uploaded document. Fix this first; nothing downstream matters until it's true.

1. In `llm_service.py`, add:
   ```python
   async def generate_document_ai(doc_type: str, title: str, audit_json: dict,
                                   domain_profile: dict, doc_excerpt: str,
                                   revision_feedback: str | None = None,
                                   previous_sections: str | None = None) -> dict:
   ```
   Implement using the system prompt and user-prompt template in design doc §3. Route through the
   existing JSON-calling infra so it benefits from the model fallback list and (after Phase 5) the
   JSON repair retry.
2. In `document_service.py`, replace `generate_document_content()`'s hardcoded bodies with a call
   to `generate_document_ai`, passing in the audit JSON already computed for this file (reuse, do
   not re-run the audit).
3. Store `_source_audit`, `_domain_profile`, `_doc_excerpt` on the resulting `doc_content` dict —
   Phase 3 depends on these being present so a reject/regenerate cycle doesn't re-audit.

**Definition of done:** Generating a BRD/SRS/RTM/User Stories/Acceptance Criteria doc for two
different uploaded files produces two visibly different, content-grounded outputs (not the same
template with the title swapped).

## Phase 2 — Promote domain detection to a first-class step (design doc §2)

1. Extract the existing healthcare/payment/auth keyword heuristic out of the fallback-only code
   path in `llm_service.py` into a standalone `detect_domain(text: str) -> dict` function per §2.
2. Call it once during `analyze_document_intelligence` and store the result alongside the audit
   JSON so Phase 1's generation call can reuse it without re-detecting.
3. Feed the domain profile's `compliance` and `standard_nfrs` into both the audit system prompt
   and the generation system prompt so both stages are domain-primed consistently.

**Definition of done:** Uploading a healthcare doc, an e-commerce doc, and a banking doc each
produce compliance mentions specific to that domain (HIPAA vs. PCI-DSS vs. SOX/AML) in both the
dashboard's missing-sections tab and the generated SRS's non-functional requirements section.

## Phase 3 — Verifier, both call sites (design doc §4, and the placement decision above)

1. Add `verify_claims_ai(doc_excerpt: str, claims: list[dict]) -> dict` to `llm_service.py` per
   §4's batched prompt design. Use confidence scores (§9.2) rather than the ternary verdict —
   build it this way from the start rather than doing §4 then redoing it for §9.2.
2. Call site A: immediately after `analyze_document_intelligence` completes, flatten all risk
   factors / missing sections / RTM rows into one claims list, verify in one call, attach
   `verdicts` (with confidence + reason) back onto the stored audit result.
3. Call site B: immediately after `generate_document_ai` (Phase 1) or a regeneration (Phase 4)
   completes, flatten the generated document's requirement statements into one claims list,
   verify in one call, attach `verdicts` to the doc_content before it's shown to the user.
4. Frontend: add a small badge per dashboard card (site A) and a verification summary line on the
   approval card (site B) — "10 of 12 traced to source, 2 below 60% confidence" with the two flagged
   items expandable.

**Definition of done:** Every dashboard risk/gap/RTM card shows a verification badge; every
generated document's approval card shows an aggregate verification summary before the user
decides to accept or reject.

## Phase 4 — Accept / Reject / Regenerate approval loop (design doc §8)

Implement exactly as specified in §8:

1. Data model fields on `doc_content`: `status`, `version`, `revision_history`, `parent_id`.
2. `POST /api/v1/documents/{document_id}/approve` and
   `POST /api/v1/documents/{document_id}/reject` (feedback required, `400` if empty/whitespace).
3. Reject handler calls `generate_document_ai` with `revision_feedback` and `previous_sections`
   set (do not drop `previous_sections` — the "edit, don't rewrite" instruction in §8 depends on
   it being present).
4. Regeneration reuses the stashed `_source_audit` / `_domain_profile` / `_doc_excerpt` from
   Phase 1 — no re-audit, no re-detection.
5. Frontend `DocumentApprovalCard` component per §8's sketch, rendered via the existing
   `isDocumentCard` chat message metadata pattern.
6. Retire `Approvals.js`'s hardcoded mock array; point it at
   `GET /api/v1/documents?status=PENDING_APPROVAL` so the standalone approvals page and the inline
   chat card share the same underlying data.
7. Cap regeneration at 3 reject cycles per document; on the 4th, show the "consider editing
   findings directly" message from §8 instead of allowing another regenerate call.

**Definition of done:** Rejecting a generated document with feedback produces a materially
different v1.1 that addresses the feedback while keeping unrelated sections intact; accepting
shows a working download button; the approvals queue page reflects real pending documents.

## Phase 5 — Hardening pass (design doc §9, all 8 items)

Implement in this order (roughly cost/effort-adjusted, cheapest/highest-value first):

1. §9.6 Prompt-injection guardrail — one line added to every system prompt touching document
   text. Do this first; it's free and closes a real gap immediately.
2. §9.4 Content-hash caching — SHA-256 the extracted text, key the audit store by hash, skip
   re-auditing identical uploads.
3. §9.3 JSON repair retry — one extra repair call before falling back to the next model/heuristic
   simulation in `_call_groq_json`.
4. §9.1 Page-level citations — thread the `--- Page N ---` markers already produced by
   `extract_text_from_file` into the audit and generation JSON schemas as `source_ref`, and render
   them in the dashboard cards and generated document footnotes.
5. §9.5 Section-by-section generation — for SRS/BRD, generate per module-group (batches of 3-4)
   rather than one call for the whole document; wire this so a reject on one section (post-Phase 4)
   can eventually regenerate just that section rather than the whole doc (stretch goal, not
   required for Phase 5 completion).
6. §9.7 Diff on re-upload/re-audit — compare new audit against the last stored one for the same
   project, surface score deltas and resolved/new risk counts.
7. §9.8 Golden-set eval — commit 3-5 sample documents (start with the hospital PDF already in this
   conversation) with hand-verified expected audit output as pytest fixtures; add a test that runs
   the current prompts against them and flags drift.

**Definition of done for Phase 5:** each of the 7 items above has its own commit and its own test;
none are bundled into "misc hardening" — you want to be able to revert any single one independently
if it causes an issue.

---

## Working agreement

- After each phase, report back: what changed, which files, what tests were added, and any
  deviation from this brief with your reasoning.
- If a design decision in the referenced doc turns out to be impractical given the actual codebase
  (e.g. a data shape that doesn't exist), stop and flag it rather than silently improvising —
  these are architectural decisions, not implementation details.
- Do not start Phase 2 until Phase 1's definition of done is verifiably true, and so on down the
  list. This is a sequential dependency chain, not a backlog to parallelize.

Begin with Phase 1.
