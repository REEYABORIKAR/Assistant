# REFYNE

REFYNE is an enterprise AI workflow and document intelligence platform.

## Repository layout

- `backend/` FastAPI application and backend tests
- `frontend/` Next.js application boundary
- `workers/` background job boundary
- `docs/` authoritative product and architecture specifications

## Local backend check

From `backend/`, install the project with its test extras and run:

```powershell
python -m pytest
```

The backend loads secrets and runtime settings from a local `.env` file.
Provider credentials must never be committed or copied into source files.

## Current scope

Phase 0 establishes the repository boundaries and a real health endpoint.
Authentication, tenant isolation, persistence, workflows, agents, integrations,
and document generation are intentionally not implemented until their
specification gates are resolved and their backend contracts are wired.

# Assistant
