# ENTERPRISE AI WORKFLOW PLATFORM

## SOURCE OF TRUTH

Before implementing any major feature, read:

- CLAUDE.md
- docs/01_MASTER_PRODUCT_SPEC.md
- docs/02_UI_DESIGN_SPEC.md
- docs/03_PAGE_SPECIFICATION.md
- docs/04_BACKEND_ARCHITECTURE.md
- docs/05_WORKFLOW_SPECIFICATION.md
- docs/06_DATABASE_SCHEMA.md
- docs/07_API_SPECIFICATION.md
- docs/08_AGENT_SPECIFICATION.md
- docs/09_DOCUMENT_GENERATION_SPEC.md
- docs/10_INTEGRATION_SPEC.md
- docs/11_SECURITY_SPEC.md
- docs/12_TEST_PLAN.md
- docs/13_ACCEPTANCE_CRITERIA.md

These files are the source of truth.

If two specifications conflict:

1. identify the conflict
2. do not silently choose
3. report the conflict
4. use the safer behavior until clarified

Do not hallucinate requirements.

---

# PRODUCT

Build a production-oriented enterprise AI platform with:

- ChatGPT-like conversational interface
- project management
- file/document ingestion
- requirement analysis
- security analysis
- compliance analysis
- risk analysis
- data availability checks
- validation
- conditional workflow execution
- supervisor orchestration
- human review
- approval
- Jira integration
- Confluence integration
- Notion integration
- document generation
- BRD
- SRS
- FRD
- NFRD
- RTM
- test documentation
- risk documentation
- security documentation
- compliance documentation
- PDF generation
- DOCX generation
- XLSX generation
- document versioning
- document traceability
- document chat/editing
- audit
- observability
- enterprise security

---

# NON-NEGOTIABLE RULES

## 1. No fake functionality

Never create fake:

- API responses
- workflow progress
- Jira tickets
- Confluence pages
- Notion results
- risk scores
- approvals
- documents
- PDFs
- audit events

If mock data is needed for development, explicitly label it:

DEMO DATA

Never present demo data as production data.

---

## 2. Backend is source of truth

Frontend must never determine:

- authorization
- workflow state
- approval state
- document approval
- tenant access
- permissions
- tool execution
- audit state

The backend is authoritative.

---

## 3. Every button must work

Every interactive button must have:

- frontend handler
- API/action
- backend implementation
- authorization
- validation
- error handling
- loading state
- success state
- audit event where applicable

Do not build decorative buttons.

---

## 4. LLM cannot directly execute privileged operations

The LLM must never directly:

- modify database records
- change permissions
- approve workflows
- execute arbitrary HTTP requests
- access arbitrary files
- access another tenant
- create arbitrary integrations

LLM output must go through:

LLM
→ Structured output
→ Schema validation
→ Authorization
→ Policy
→ Tool Registry
→ Tool execution
→ Validation
→ Audit

---

## 5. No hallucinated project information

Never invent:

- requirements
- evidence
- risks
- compliance controls
- test results
- approval decisions
- source documents
- Jira issues
- Confluence pages
- Notion pages

If information is unavailable:

MISSING INFORMATION

If an assumption is explicitly allowed:

ASSUMPTION

Track assumptions.

---

# UI RULES

Use the provided images in:

docs/ui/

as visual references.

Visual language:

- dark navy
- deep blue
- glassmorphism
- cyan/electric blue
- subtle purple/blue glow
- rounded cards
- premium futuristic AI design
- clean typography
- spacious layouts
- subtle animations
- responsive desktop design

The primary experience must feel like ChatGPT.

The application must not look like a generic admin dashboard.

---

# TECHNOLOGY

Frontend:

- Next.js
- React
- TypeScript
- Tailwind CSS
- TanStack Query
- React Hook Form
- Zod

Backend:

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

Data:

- PostgreSQL
- Redis
- object storage

AI:

- LLM provider abstraction
- structured output
- tool calling
- prompt registry
- model registry
- context assembly

Realtime:

- SSE or WebSockets

Workers:

- background job queue
- retry
- dead-letter handling

Documents:

- PDF
- DOCX
- XLSX

---

# DEVELOPMENT RULE

Before coding a feature:

1. inspect relevant specification
2. inspect existing code
3. identify affected components
4. implement backend contract
5. implement database changes
6. implement frontend
7. implement tests
8. run tests
9. fix failures
10. verify complete user flow

Do not rewrite unrelated working code.

---

# COMPLETION RULE

A feature is NOT complete because:

- the page renders
- the button exists
- a mock response appears
- a hard-coded workflow works once

A feature is complete only when:

Frontend
+
API
+
Backend
+
Database
+
Authorization
+
Validation
+
Error handling
+
Tests

are implemented.

---

# SECRETS

Never:

- print secrets
- commit secrets
- put secrets in frontend code
- hard-code API keys

Use environment variables.

Use `.env.example`.

---

# DOCUMENT RULES

Documents must have:

- stable document ID
- version
- status
- source references
- revision history
- approval history
- traceability
- audit history

Approved documents are immutable.

Changes create a new version.

---

# IMPLEMENTATION ORDER

1. Foundation
2. Authentication
3. Multi-tenancy
4. Projects
5. Chat
6. Files
7. Workflow engine
8. Supervisor
9. Agents
10. Validation
11. Human review
12. Approval
13. Tool Registry
14. Jira
15. Confluence
16. Notion
17. Document engine
18. BRD
19. SRS
20. FRD
21. NFRD
22. RTM
23. Test documents
24. Risk/security/compliance documents
25. Document validation
26. PDF/DOCX/XLSX
27. Document chat
28. Versioning
29. Traceability
30. Audit
31. Observability
32. Security hardening
33. E2E testing

Do not skip foundational work.