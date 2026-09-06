from unittest.mock import MagicMock, patch
import uuid
import pytest
from starlette.testclient import TestClient
from refyne.main import app, DOCUMENT_STORE, _save_persistent_document

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

def test_01_version_history_never_overwrites_always_appends(client):
    """Test that rejecting V1 persists V1 as REJECTED and creates V2 as a distinct new document."""
    gen_id = f"gen_{uuid.uuid4().hex[:8]}"
    v1_id = str(uuid.uuid4())

    v1_doc = {
        "id": v1_id,
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": "Hospital Management System User Stories",
        "version": "v1.0",
        "version_num": 1,
        "parent_version": None,
        "parent_id": None,
        "status": "PENDING_APPROVAL",
        "created_at": "2026-08-30T10:12:00Z",
        "sections": [{"title": "1. Overview", "body": "Initial user story backlog."}],
        "user_stories_data": {
            "requirements": [{"req_id": "REQ-PAT-01", "module": "Patient Management", "title": "Registration"}],
            "personas": [{"persona_id": "P-REC", "name": "Receptionist", "responsibilities": ["Registration"]}],
            "stories": [{"story_id": "US-PAT-01", "capability": "register patient", "business_value": "unique record"}],
            "traceability": []
        }
    }
    _save_persistent_document(v1_id, v1_doc)

    # 1. Reject V1
    feedback_text = "The pharmacy and billing stories are too broad. Split them further."
    resp_reject = client.post(
        f"/api/v1/documents/{v1_id}/reject",
        json={"feedback": feedback_text},
        headers={"Authorization": "Bearer test-token"}
    )
    assert resp_reject.status_code == 200
    v2_doc = resp_reject.json()

    # V2 verification
    assert v2_doc["id"] != v1_id, "V2 must have a distinct unique document ID"
    assert v2_doc["generation_id"] == gen_id, "V2 must share the same generation_id"
    assert v2_doc["version"] in ("v2.0", "v1.1")
    assert v2_doc["version_num"] == 2
    assert v2_doc["parent_id"] == v1_id
    assert v2_doc["status"] == "PENDING_APPROVAL"

    # V1 verification (must be immutable and marked REJECTED)
    v1_stored = DOCUMENT_STORE[v1_id]
    assert v1_stored["status"] == "REJECTED", "V1 status must transition to REJECTED"
    assert v1_stored["rejection_feedback"] == feedback_text, "V1 must store rejection feedback"
    assert v1_stored["reviewed_at"] is not None


def test_02_get_generation_versions_list(client):
    """Test GET /api/v1/generations/{generation_id}/versions returns all versions, newest first."""
    gen_id = f"gen_{uuid.uuid4().hex[:8]}"
    v1_id = str(uuid.uuid4())
    v2_id = str(uuid.uuid4())

    v1_doc = {
        "id": v1_id,
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": "Hospital Management System",
        "version": "v1.0",
        "version_num": 1,
        "status": "REJECTED",
        "rejection_feedback": "Initial feedback",
        "created_at": "2026-08-30T10:12:00Z"
    }
    v2_doc = {
        "id": v2_id,
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": "Hospital Management System",
        "version": "v2.0",
        "version_num": 2,
        "status": "PENDING_APPROVAL",
        "created_at": "2026-08-30T10:25:00Z"
    }
    _save_persistent_document(v1_id, v1_doc)
    _save_persistent_document(v2_id, v2_doc)

    resp = client.get(f"/api/v1/generations/{gen_id}/versions")
    assert resp.status_code == 200
    versions = resp.json()

    assert len(versions) >= 2
    # Verify newest first
    assert versions[0]["version_num"] == 2
    assert versions[0]["status"] == "PENDING_APPROVAL"
    assert versions[1]["version_num"] == 1
    assert versions[1]["status"] == "REJECTED"
    assert versions[1]["rejection_feedback"] == "Initial feedback"


def test_03_get_generation_version_detail(client):
    """Test GET /api/v1/generations/{generation_id}/versions/{version} returns specific version details."""
    gen_id = f"gen_{uuid.uuid4().hex[:8]}"
    v1_id = str(uuid.uuid4())
    v1_doc = {
        "id": v1_id,
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": "HMS V1",
        "version": "v1.0",
        "version_num": 1,
        "status": "REJECTED",
        "sections": [{"title": "1. Scope", "body": "V1 Body"}],
        "created_at": "2026-08-30T10:12:00Z"
    }
    _save_persistent_document(v1_id, v1_doc)

    # Query by version_num (1)
    resp = client.get(f"/api/v1/generations/{gen_id}/versions/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == v1_id
    assert data["version"] == "v1.0"
    assert data["sections"][0]["body"] == "V1 Body"


def test_04_accept_specific_version(client):
    """Test POST /api/v1/generations/{generation_id}/versions/{version}/accept marks target version ACCEPTED."""
    gen_id = f"gen_{uuid.uuid4().hex[:8]}"
    v1_id = str(uuid.uuid4())
    v2_id = str(uuid.uuid4())

    v1_doc = {
        "id": v1_id,
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": "HMS",
        "version": "v1.0",
        "version_num": 1,
        "status": "REJECTED",
        "created_at": "2026-08-30T10:12:00Z"
    }
    v2_doc = {
        "id": v2_id,
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": "HMS",
        "version": "v2.0",
        "version_num": 2,
        "status": "PENDING_APPROVAL",
        "created_at": "2026-08-30T10:25:00Z"
    }
    _save_persistent_document(v1_id, v1_doc)
    _save_persistent_document(v2_id, v2_doc)

    # Accept V2
    resp_accept = client.post(
        f"/api/v1/generations/{gen_id}/versions/2/accept",
        headers={"Authorization": "Bearer test-token"}
    )
    assert resp_accept.status_code == 200
    accepted_doc = resp_accept.json()
    assert accepted_doc["status"] == "ACCEPTED"

    # Verify V1 is still REJECTED and unchanged
    v1_stored = DOCUMENT_STORE[v1_id]
    assert v1_stored["status"] == "REJECTED"


def test_05_generation_reject_endpoint(client):
    """Test POST /api/v1/generations/{generation_id}/reject triggers revision engine and creates next version."""
    gen_id = f"gen_{uuid.uuid4().hex[:8]}"
    v1_id = str(uuid.uuid4())

    v1_doc = {
        "id": v1_id,
        "generation_id": gen_id,
        "doc_type": "USER_STORIES",
        "title": "Hospital Management System",
        "version": "v1.0",
        "version_num": 1,
        "status": "PENDING_APPROVAL",
        "created_at": "2026-08-30T10:12:00Z",
        "sections": [],
        "user_stories_data": {
            "requirements": [{"req_id": "REQ-PAT-01", "module": "Patient Management", "title": "Registration"}],
            "personas": [{"persona_id": "P-REC", "name": "Receptionist", "responsibilities": ["Registration"]}],
            "stories": [],
            "traceability": []
        }
    }
    _save_persistent_document(v1_id, v1_doc)

    resp = client.post(
        f"/api/v1/generations/{gen_id}/reject",
        json={"version": 1, "feedback": "Add lab and pharmacy stories"},
        headers={"Authorization": "Bearer test-token"}
    )
    assert resp.status_code == 200
    v2_doc = resp.json()
    assert v2_doc["generation_id"] == gen_id
    assert v2_doc["version_num"] == 2
    assert v2_doc["status"] == "PENDING_APPROVAL"

    # Verify V1 marked rejected
    assert DOCUMENT_STORE[v1_id]["status"] == "REJECTED"
    assert DOCUMENT_STORE[v1_id]["rejection_feedback"] == "Add lab and pharmacy stories"
