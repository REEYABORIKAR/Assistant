# FIX: User Story Document Version History (Dropdown) — Implementation Prompt

## Problem

When a user rejects a generated User Stories document, provides improvement
feedback, and a new version is generated, the chatbot **overwrites** the
previous version in the chat UI. The old (rejected) version becomes
inaccessible. There is currently no way to see V1 after V2 exists, no way to
compare versions, and no persistent list of all versions ever generated for a
generation thread — whether they were rejected or accepted.

## Goal

Every version generated (rejected or accepted) must be persisted and
retrievable. The chat UI must show a **version dropdown/selector** on the User
Stories artifact so the user can switch between V1, V2, V3... at any time,
see each version's status (REJECTED / ACCEPTED / SUPERSEDED), and see the
feedback that led to each revision — without losing or overwriting any prior
version.

---

## 1. Data model — never overwrite, always append

Each generation attempt is a new row keyed by `(generation_id, version)`.
`generation_id` stays constant across the whole reject→improve→regenerate
thread; `version` increments. **Never UPDATE an existing version's document
content — only INSERT new rows.**

```json
{
  "generation_id": "gen_8841",
  "version": 1,
  "status": "REJECTED",               // GENERATED | ACCEPTED | REJECTED | SUPERSEDED
  "parent_version": null,
  "created_at": "2026-08-30T10:12:00Z",
  "document_url": "/documents/gen_8841/v1.pdf",
  "requirement_inventory_snapshot_id": "inv_001",
  "story_ids": ["US-PAT-01", "US-PAT-02", "..."],
  "rejection_feedback": "The stories are too broad. Split them...",
  "reviewed_at": "2026-08-30T10:20:00Z"
}
```

```json
{
  "generation_id": "gen_8841",
  "version": 2,
  "status": "ACCEPTED",
  "parent_version": 1,
  "created_at": "2026-08-30T10:25:00Z",
  "document_url": "/documents/gen_8841/v2.pdf",
  "requirement_inventory_snapshot_id": "inv_001",
  "story_ids": ["US-PAT-01", "US-PAT-02", "US-PAT-03(split)", "..."],
  "changed_story_ids": ["US-PAT-03"],
  "added_story_ids": ["US-NOT-01", "US-NOT-02"],
  "removed_story_ids": [],
  "rejection_feedback": null,
  "reviewed_at": "2026-08-30T10:31:00Z"
}
```

**Status transition rule:** when V2 is created, set V1's status to
`REJECTED` (final — the user rejected it) — do not delete or hide the row,
do not mark it `SUPERSEDED` unless it was never explicitly rejected/accepted
(e.g. an auto-regenerated intermediate draft that failed validation before
ever being shown to the user gets `SUPERSEDED`, not `REJECTED`).

**Every version must remain independently downloadable/viewable forever**,
regardless of its status.

---

## 2. Backend API additions

```
GET  /api/generations/{generation_id}/versions
  -> [ { version, status, created_at, document_url, summary_of_changes }, ... ]
  Always returns ALL versions, newest first. Never filters out rejected ones.

GET  /api/generations/{generation_id}/versions/{version}
  -> full version object + document content/URL

POST /api/generations/{generation_id}/versions/{version}/accept
  -> sets status = ACCEPTED on that version
  -> does NOT touch other versions' stored documents

POST /api/generations/{generation_id}/reject
  body: { version, feedback }
  -> sets status = REJECTED on `version`
  -> triggers Revision Engine (per the pipeline fix doc) to create version+1
  -> returns the new version object once generation completes
```

**Critical constraint:** `POST /reject` must never mutate or delete the row
for the version being rejected. It only writes feedback onto that row and
creates a brand-new row for the next version.

---

## 3. Chat UI behavior

### 3.1 Version dropdown on the artifact

Render the User Stories document in chat as a card/artifact with a version
selector at the top:

```
┌─────────────────────────────────────────────┐
│  User Stories — Requirements Chat 9          │
│  [ Version: V2 (Current) ▾ ]     [Download]  │
│     ┌─────────────────────────────┐          │
│     │ V2 — Accepted   Aug 30 10:31 │          │
│     │ V1 — Rejected   Aug 30 10:20 │          │
│     └─────────────────────────────┘          │
└─────────────────────────────────────────────┘
```

- Dropdown lists every version for that `generation_id`, most recent first.
- Each entry shows: version number, status badge (color-coded — e.g. green
  ACCEPTED, red REJECTED, gray SUPERSEDED), and timestamp.
- Selecting an older version renders that version's document in place, with
  a persistent "Viewing V1 (Rejected) — [View Current V2]" banner so the
  user always knows they're looking at a historical version, not the active
  one.
- The rejection feedback that produced the *next* version should be visible
  when viewing a rejected version, e.g.:
  `"Rejected with feedback: 'Split pharmacy/billing stories further...'"`

### 3.2 New chat message per version, not an overwritten message

Do not re-render/replace the same chat message bubble when a new version is
generated. Each generation event should either:
- (a) post a **new** chat message containing the new artifact (with the
  dropdown showing full history up to that point), or
- (b) update the single "live" artifact card in place, but **only for
  document content** — the version history data behind the dropdown must be
  additive regardless of which rendering approach is used.

Recommended: (a) — new message per version — because it also gives the user
a natural chronological record of the reject/improve conversation. The
dropdown on the *latest* message is what people will use to jump back, but
older messages in the transcript remain intact too.

### 3.3 Diff view (nice-to-have, high value)

When viewing V2 with V1 selected as "compare against," highlight:
- Stories added (green)
- Stories removed (red, struck through)
- Stories modified/split (yellow) — with a note like "US-PAT-03 → split into US-PAT-03a, US-PAT-03b"

This maps directly to the `changed_story_ids` / `added_story_ids` /
`removed_story_ids` fields already defined in the revision engine's version
record (see the pipeline fix doc, Section 7).

---

## 4. State/storage rules — summary of what must change in the code

| Current (broken) behavior | Required behavior |
|---|---|
| New generation overwrites the stored document for the thread | New generation always creates a new `(generation_id, version)` row; old rows are immutable |
| Chat shows only the latest document | Chat artifact has a version dropdown listing all versions, including rejected ones |
| Rejected version is discarded once feedback is submitted | Rejected version is marked `REJECTED` and kept, fully viewable/downloadable, forever |
| No way to see what changed between versions | Each version stores `changed/added/removed_story_ids` against its parent for diffing |
| No accept/reject state persisted per version | Every version row has an explicit `status` field, set via the accept/reject API calls |

---

## 5. Acceptance test for this fix

1. Generate V1 → reject with feedback → generate V2.
2. Open the version dropdown on the V2 artifact: **V1 must still appear**,
   marked `Rejected`, with the feedback text visible, and its original PDF
   still downloadable and rendering the original (unmodified) content.
3. Reject V2 with new feedback → generate V3.
4. Dropdown now shows V1 (Rejected), V2 (Rejected), V3 (Current) — all three
   independently viewable.
5. Accept V3 → V3 status becomes `Accepted`; V1 and V2 remain `Rejected` and
   still fully accessible — not deleted, not hidden.
6. Refresh/reload the chat — full version history and all documents persist
   (confirms this is backed by real storage, not client-side session state).
