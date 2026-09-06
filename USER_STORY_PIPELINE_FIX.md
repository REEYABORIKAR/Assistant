# User Story Generation — Root-Cause Fix & Implementation Spec

## 0. What's actually broken (confirmed from the sample PDF)

The story-generation call is receiving only `{ title, epic_name }` — not the source
document, not a requirement inventory. Evidence: the Release Slicing section text
("Outpatient Care," "Inpatient (IPD) Lifecycle") is correct HMS content, but the
User Stories under it are the same 5 generic `US-01..US-05` stories. Two different
code paths have different access to context. **Fix the wiring, not just the prompt.**

---

## 1. Pipeline stages (each is a separate deterministic+LLM call, not one mega-prompt)

```
Stage 0: Ingest & chunk source doc
Stage 1: Requirement Extraction        (LLM, structured output)
Stage 2: Requirement Normalization     (deterministic + LLM merge)
Stage 3: Persona/Actor Extraction      (LLM, structured output)
Stage 4: Epic/Module Identification    (deterministic, derived from Stage 1)
Stage 5: Workflow Identification       (LLM, structured output)
Stage 6: Requirement → Story Mapping   (LLM, per-requirement, NOT per-doc)
Stage 7: Story Generation              (LLM, per-requirement, decomposed)
Stage 8: Story Quality Validation      (deterministic rules)
Stage 9: Completeness Validation       (deterministic, set-diff against Stage 1)
Stage 10: Duplicate Validation         (deterministic, embedding similarity)
Stage 11: Traceability Validation      (deterministic, graph check)
Stage 12: AI Reviewer Pass             (LLM, sees everything, returns diffs)
Stage 13: Apply corrections            (deterministic merge)
Stage 14: PDF Generation               (template render only — no LLM)
```

**Rule: every stage output is a JSON object stored against the `generation_id`.
Every downstream stage reads from storage, never from "the previous LLM message."**
This is what breaks in chat-style pipelines — context silently drops.

---

## 2. Core data contract: Requirement Inventory

This is the backbone. Every other stage reads/writes against it. Generate once,
reuse forever (including all revisions).

```json
{
  "generation_id": "gen_8841",
  "source_document_id": "doc_hms_srs_v1",
  "requirements": [
    {
      "req_id": "REQ-PAT-01",
      "module": "Patient Management",
      "title": "Patient registration",
      "description": "<verbatim or lightly normalized text extracted from source>",
      "source_excerpt_ref": "page 4, para 2",
      "type": "functional",
      "status": "extracted"
    },
    {
      "req_id": "REQ-PHARM-03",
      "module": "Pharmacy",
      "title": "Medicine inventory stock tracking",
      "description": "...",
      "source_excerpt_ref": "page 11",
      "type": "functional",
      "status": "extracted"
    }
  ],
  "personas": [
    {"persona_id": "P-RECEPTIONIST", "name": "Receptionist", "responsibilities": ["registration","appointments","queue"]}
  ],
  "workflows": [
    {"workflow_id": "WF-01", "name": "Outpatient journey", "steps": ["Registration","Appointment","Consultation","Diagnosis","Lab/Pharmacy","Billing","Follow-up"]}
  ]
}
```

**Hard rule for Stage 1 (Requirement Extraction) prompt:**

```
SYSTEM:
You are a requirement extraction engine. You will be given the full text of a
source requirements document (BRD/SRS). Extract EVERY discrete functional and
non-functional requirement mentioned. Do not summarize, do not merge unrelated
requirements, do not invent requirements not present in the text.

Output ONLY valid JSON matching this schema:
{ "requirements": [ { "req_id": string, "module": string, "title": string,
  "description": string, "source_excerpt_ref": string, "type": "functional"|"non_functional" } ] }

Rules:
- Granularity: one requirement per distinct capability, not per module.
  ("Patient registration" and "Patient profile management" are TWO requirements,
  not one "Patient Management" requirement.)
- If the source describes a module (e.g. Pharmacy) with sub-capabilities
  (dispensing, stock tracking, low-stock alerts), extract each sub-capability
  as its own requirement.
- req_id must be prefixed by module abbreviation, e.g. REQ-PHARM-01, REQ-PHARM-02.
- Do not output prose, explanations, or markdown — JSON only.

SOURCE DOCUMENT:
<<FULL SOURCE TEXT — NOT A SUMMARY, NOT A TITLE>>
```

This single change — extracting the *whole document* into 40–80 granular
requirement objects instead of 5 section headers — is what fixes 80% of your
sample PDF's problems (the generic REQ-01..REQ-05 issue).

---

## 3. Stage 7: Story Generation — run PER REQUIREMENT, not per document

The #1 bug pattern in your sample (`US-02: "execute primary transaction
processing"`) happens when the LLM is asked to write stories for an entire
document/epic in one shot. Instead, batch by module but generate 1+ stories
**per requirement**, explicitly forbidding module-level stories.

```
SYSTEM:
You are a Product Owner writing user stories for ONE requirement at a time.

You will receive:
- The requirement (id, title, description, source excerpt)
- The full persona list with responsibilities
- Related requirements in the same module (for context only — do not write
  stories for them here)

Write 1 to 4 user stories that fully cover this single requirement. If the
requirement implies multiple independent user actions (e.g. "prescription
dispensing" implies: view prescription, verify prescription, dispense
medicine, update stock), write a SEPARATE story for each action.

Never write a story like "I want to manage X" or "I want to handle X."
Every story must name ONE specific user action and ONE specific measurable
outcome.

Assign the persona whose responsibilities match the requirement — never
default to "Admin" or "Authorized User" unless the requirement is explicitly
administrative/system-wide.

Output ONLY JSON:
{ "stories": [ {
  "story_id": "US-<module>-<seq>",
  "epic": string,
  "persona": string,
  "user_story": "As a <persona>, I want <capability>, so that <outcome>",
  "business_value": string,
  "priority": "High"|"Medium"|"Low",
  "acceptance_criteria": [string, ...],   // 3-6, specific to THIS capability, not templated filler
  "dependencies": [story_id, ...],
  "source_requirement": "<req_id>"
} ] }

REQUIREMENT:
<<req_id, title, description, source_excerpt>>

PERSONAS:
<<persona list with responsibilities>>
```

Run this once per requirement (40–80 calls, or batched 3–5 requirements per
call max — never "generate stories for the whole Pharmacy module" as one call).

---

## 4. Stage 9: Completeness Validation (deterministic, not LLM)

```python
covered_req_ids = {s["source_requirement"] for s in all_stories}
all_req_ids = {r["req_id"] for r in requirement_inventory}
missing = all_req_ids - covered_req_ids

if missing:
    status = "INCOMPLETE"
    # do NOT proceed to PDF generation
    # send `missing` back into Stage 7 for those requirements only
else:
    status = "COMPLETE"
```

Also assert minimums before allowing PDF generation — this is the guardrail that
would have caught your sample output:

```python
assert len(requirement_inventory) >= 15, "Requirement extraction likely failed — too few requirements"
assert len(set(s["persona"] for s in all_stories)) >= 3, "Persona mapping likely failed — too few distinct personas"
assert not any(p["persona"] in ("Authorized User","End User","Enterprise User") for p in personas), \
    "Generic placeholder persona detected — extraction fell back to template"
```

If any assertion fails: halt, log, and either retry Stage 1 with a stricter
prompt or flag for human review. **Never render a PDF from a failed state.**

---

## 5. Stage 8: Story Quality Validation (deterministic rules, run per story)

| Check | Rule |
|---|---|
| Vague verb check | Reject if user_story matches `manage|handle|use the|perform .* operations` without a specific object+outcome |
| Module-level check | Reject if story title/epic equals a whole module name with no specific capability |
| Persona placeholder check | Reject if persona in `{"Authorized User","User","Admin"}` when a more specific persona is available in the persona list |
| AC specificity check | Reject if any AC is the templated string `"System accepts valid input for {story_title}"` — this is the exact filler pattern in your sample |
| Traceability check | Reject if `source_requirement` is null or not in inventory |

Failed stories go back to Stage 7 for regeneration with the failure reason
appended to the prompt.

---

## 6. Revision engine (Reject → Improve → Regenerate) — the second bug

**Never call story generation fresh on rejection.** Instead:

```json
// Revision Stage input contract
{
  "source_document": "<<full text, always available>>",
  "requirement_inventory": [ /* from Stage 1, unchanged unless feedback implies new reqs */ ],
  "current_stories": [ /* full V1 story objects */ ],
  "validation_results_v1": { /* Stage 8-11 results */ },
  "user_feedback": "The stories are too broad. Split them. Add missing OPD/IPD, admission, discharge..."
}
```

```
SYSTEM:
You are revising an existing user story backlog based on user feedback.
You must NOT regenerate the backlog from scratch. For every existing story,
decide an action: KEEP, MODIFY, SPLIT, or REMOVE, with a reason.

Then, using the requirement inventory, identify any requirements not yet
covered that the user's feedback references (e.g. "add missing admission
stories" -> check requirement inventory for admission-related req_ids not
yet mapped to any story) and generate new stories only for those.

Do not touch stories unrelated to the feedback unless they fail existing
validation rules.

Output ONLY JSON:
{
  "story_decisions": [
    {"story_id": "US-008", "action": "SPLIT", "reason": "...", "resulting_stories": [ ... full new story objects ... ]},
    {"story_id": "US-012", "action": "KEEP", "reason": "Valid, unaffected by feedback"}
  ],
  "new_stories": [ /* stories for previously-uncovered requirements referenced in feedback */ ]
}

CURRENT STORIES:
<<current_stories>>

REQUIREMENT INVENTORY:
<<requirement_inventory>>

VALIDATION RESULTS (V1):
<<validation_results_v1>>

USER FEEDBACK:
<<user_feedback>>
```

Deterministic merge after this call:

```python
v2_stories = []
for decision in story_decisions:
    if decision["action"] == "KEEP":
        v2_stories.append(get_story(decision["story_id"]))          # unchanged object, same ID
    elif decision["action"] == "MODIFY":
        v2_stories.append(decision["resulting_story"])               # same ID, updated fields
    elif decision["action"] == "SPLIT":
        v2_stories.extend(decision["resulting_stories"])              # new child IDs, original ID retired
    elif decision["action"] == "REMOVE":
        pass                                                          # logged in removed_story_ids
v2_stories.extend(new_stories)
```

Then re-run Stage 8–11 validation on `v2_stories` before allowing PDF generation.

**This directly fixes your Test 3 requirement** ("only pharmacy/billing should
change, don't touch unrelated stories") — because every story gets an explicit
KEEP/MODIFY/SPLIT/REMOVE decision instead of being regenerated wholesale.

---

## 7. Revision state persistence

```json
{
  "generation_id": "gen_8841",
  "version": 2,
  "status": "GENERATED",
  "parent_version": 1,
  "revision_feedback": "Stories too broad, split them, add missing admission/discharge...",
  "changed_story_ids": ["US-008"],
  "added_story_ids": ["US-021","US-022","US-023"],
  "removed_story_ids": [],
  "validation_results": { "coverage": "COMPLETE", "quality_score": 0.94 }
}
```

Store every version. Diffing `v1` vs `v2` against this record is how you prove
(and debug) that revision actually iterated rather than replaced.

---

## 8. PDF renderer — template only, zero LLM involvement

The PDF stage should be a pure function: `render(final_story_set, inventory,
traceability_matrix, workflows, release_plan) -> PDF`. No prompt, no
generation, no risk of internal review commentary ("Functional alignment:
65-70%") leaking into the document — because there's no LLM call at this
stage to leak from. Also fixes the `Status: APPROVED` vs `PENDING APPROVAL`
inconsistency you saw — set that field once, from the persisted generation
state, not independently per section.

---

## 9. Guardrail checklist before shipping

- [ ] Stage 1 extracts 15+ requirements for any non-trivial source doc (assert)
- [ ] Stage 7 is called per-requirement or small batch, never per-document
- [ ] No story's AC matches the templated filler pattern
- [ ] No persona is a generic placeholder unless genuinely unmappable
- [ ] Every story has a non-null `source_requirement` that exists in inventory
- [ ] Completeness validator blocks PDF generation on any gap
- [ ] Revision stage receives `current_stories` + `source_document` + `feedback` together, always
- [ ] Every revised story has an explicit KEEP/MODIFY/SPLIT/REMOVE decision logged
- [ ] PDF renderer contains zero LLM calls
- [ ] Version history stored and diffable (v1 vs v2 changed/added/removed IDs)
