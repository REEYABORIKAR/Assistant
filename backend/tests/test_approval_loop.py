import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from refyne.main import app, DOCUMENT_STORE


@pytest.fixture
def auth_mock():
    with patch('refyne.main._authenticated_context') as mock_auth:
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.tenant_id = uuid.uuid4()
        mock_auth.return_value = (mock_user, mock_session)
        yield mock_auth


@pytest.fixture
def client(auth_mock):
    return TestClient(app)


def test_document_generation_default_status(client):
    """Generated documents must start in PENDING_APPROVAL with version v1.0."""
    response = client.post(
        "/api/v1/documents/generate",
        json={"doc_type": "BRD", "title": "Hospital Patient Portal"},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    doc = response.json()
    assert doc["status"] == "PENDING_APPROVAL"
    assert doc["version"] == "v1.0"
    assert doc["revision_history"] == []
    assert "id" in doc
    doc_id = doc["id"]

    # Verify present in DOCUMENT_STORE
    assert doc_id in DOCUMENT_STORE


def test_approve_document_endpoint(client):
    """Approving a document transitions its status to APPROVED."""
    doc_id = str(uuid.uuid4())
    DOCUMENT_STORE[doc_id] = {
        "id": doc_id,
        "doc_type": "BRD",
        "title": "Hospital Patient Portal",
        "version": "v1.0",
        "status": "PENDING_APPROVAL",
        "revision_history": [],
        "sections": [{"title": "1. Overview", "body": "Overview body"}]
    }

    response = client.post(
        f"/api/v1/documents/{doc_id}/approve",
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["status"] == "APPROVED"
    assert "approved_at" in updated


def test_reject_document_validation(client):
    """Rejecting a document without feedback returns 400 Bad Request."""
    doc_id = str(uuid.uuid4())
    DOCUMENT_STORE[doc_id] = {
        "id": doc_id,
        "doc_type": "BRD",
        "title": "Hospital Patient Portal",
        "version": "v1.0",
        "status": "PENDING_APPROVAL",
        "revision_history": [],
        "sections": []
    }

    # Empty feedback
    response = client.post(
        f"/api/v1/documents/{doc_id}/reject",
        json={"feedback": ""},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 400

    # Whitespace feedback
    response = client.post(
        f"/api/v1/documents/{doc_id}/reject",
        json={"feedback": "   "},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 400


def test_reject_and_regenerate_flow(client):
    """Rejecting with feedback increments version to v1.1 and adds revision history."""
    doc_id = str(uuid.uuid4())
    DOCUMENT_STORE[doc_id] = {
        "id": doc_id,
        "doc_type": "SRS",
        "title": "Patient Portal",
        "version": "v1.0",
        "status": "PENDING_APPROVAL",
        "revision_history": [],
        "_source_audit": {},
        "_domain_profile": {"domain": "HEALTHCARE", "compliance": ["HIPAA"], "standard_nfrs": ["P95 latency < 250ms"]},
        "_doc_excerpt": "Hospital EMR patient management system.",
        "sections": [
            {"title": "1. Introduction", "body": "Initial draft of requirements."}
        ]
    }

    response = client.post(
        f"/api/v1/documents/{doc_id}/reject",
        json={"feedback": "Add specific HIPAA encryption at rest and audit logging requirement."},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    revised = response.json()
    assert revised["version"] == "v1.1"
    assert revised["status"] == "PENDING_APPROVAL"
    assert len(revised["revision_history"]) == 1
    assert revised["revision_history"][0]["feedback"] == "Add specific HIPAA encryption at rest and audit logging requirement."


def test_reject_max_cycles_cap(client):
    """After 3 revision cycles, a 4th rejection is rejected with 400 error."""
    doc_id = str(uuid.uuid4())
    DOCUMENT_STORE[doc_id] = {
        "id": doc_id,
        "doc_type": "BRD",
        "title": "Patient Portal",
        "version": "v1.3",
        "status": "PENDING_APPROVAL",
        "revision_history": [
            {"version": "v1.0", "feedback": "Fix 1"},
            {"version": "v1.1", "feedback": "Fix 2"},
            {"version": "v1.2", "feedback": "Fix 3"},
        ],
        "_source_audit": {},
        "_domain_profile": {"domain": "HEALTHCARE"},
        "_doc_excerpt": "Hospital EMR",
        "sections": []
    }

    response = client.post(
        f"/api/v1/documents/{doc_id}/reject",
        json={"feedback": "Fix 4"},
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 400
    assert "Maximum revision limit reached" in response.text


def test_list_documents_filtering(client):
    """GET /api/v1/documents returns all documents and supports status filtering."""
    doc_id_1 = str(uuid.uuid4())
    doc_id_2 = str(uuid.uuid4())
    DOCUMENT_STORE[doc_id_1] = {
        "id": doc_id_1,
        "doc_type": "BRD",
        "title": "Pending Doc",
        "status": "PENDING_APPROVAL"
    }
    DOCUMENT_STORE[doc_id_2] = {
        "id": doc_id_2,
        "doc_type": "SRS",
        "title": "Approved Doc",
        "status": "APPROVED"
    }

    # All
    r_all = client.get("/api/v1/documents", headers={"Authorization": "Bearer test-token"})
    assert r_all.status_code == 200
    assert len(r_all.json()) >= 2

    # Filter PENDING_APPROVAL
    r_pending = client.get("/api/v1/documents?status=PENDING_APPROVAL", headers={"Authorization": "Bearer test-token"})
    assert r_pending.status_code == 200
    pending_list = r_pending.json()
    assert all(d["status"] == "PENDING_APPROVAL" for d in pending_list)
    assert any(d["id"] == doc_id_1 for d in pending_list)
