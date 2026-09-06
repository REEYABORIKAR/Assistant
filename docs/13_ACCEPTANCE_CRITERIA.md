# ACCEPTANCE CRITERIA

## GENERAL

A feature is complete only when:

- frontend works
- API works
- backend works
- database persistence works
- authorization works
- validation works
- errors work
- tests pass

---

# CHAT

User can:

- create conversation
- send message
- receive streaming response
- upload file
- continue conversation
- regenerate response
- delete conversation

---

# WORKFLOW

User can:

- start workflow
- see actual state
- see actual progress
- cancel where allowed
- retry where allowed
- receive failure state

---

# CONDITIONAL

If security disabled:

Security agent does not run.

If compliance disabled:

Compliance agent does not run.

If data missing:

workflow waits.

If risk exceeds configured threshold:

approval required.

If validation fails:

retry.

If retry limit exceeded:

human review.

---

# DOCUMENTS

User can:

- generate BRD
- generate SRS
- generate FRD
- generate NFRD
- generate RTM
- generate test documents
- generate risk documents
- generate security documents
- generate compliance documents

---

# DOCUMENT VALIDATION

Document must:

- have required sections
- contain source references
- contain valid requirement IDs
- pass validation
- have version
- have status

---

# PDF

Generated PDF must be a real file.

It must contain:

- cover
- metadata
- revision history
- table of contents
- content
- page numbers

---

# APPROVAL

Approved document:

- cannot be overwritten
- remains immutable
- has approval event
- creates audit record

---

# INTEGRATIONS

If integration connected:

Use actual integration.

If disconnected:

Do not return fake data.

---

# SECURITY

Unauthorized access must be rejected by backend.

---

# TRACEABILITY

Requirement:

BR-001

must be traceable through relevant:

FR
SRS
Design
Test
Risk

where applicable.

---

# AUDIT

Important operations must appear in audit history.

---

# FINAL ACCEPTANCE

A real user must be able to complete:

Register
→ Login
→ Create Project
→ Chat
→ Upload Requirements
→ Analyze
→ Run Workflow
→ Validate
→ Review
→ Approve
→ Generate BRD
→ Generate SRS
→ Generate RTM
→ Generate PDF
→ Download
→ Revise
→ Create New Version
→ Audit