import json
from unittest.mock import MagicMock, patch
import uuid
from fastapi import status
from fastapi.testclient import TestClient
from refyne.main import app


def test_tenant_isolation_allows_same_tenant():
    client = TestClient(app)

    with patch('refyne.db.session.SessionLocal') as mock_session_local, \
         patch('refyne.main._authenticated_context') as mock_auth_context:

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        # Mock the user and session objects
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.tenant_id = tenant_id
        mock_auth_context.return_value = (mock_user, mock_session)

        project_id = uuid.uuid4()
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.tenant_id = tenant_id
        mock_project.deleted_at = None

        mock_db.scalar.return_value = mock_project

        response = client.get(
            f"/api/v1/projects/{project_id}",
            headers={"Authorization": "Bearer fake-token"}
        )
        # Middleware should allow the request (not return 403).
        assert response.status_code != status.HTTP_403_FORBIDDEN


def test_tenant_isolation_blocks_cross_tenant():
    client = TestClient(app)

    with patch('refyne.db.session.SessionLocal') as mock_session_local, \
         patch('refyne.main._authenticated_context') as mock_auth_context:

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        tenant_a_id = uuid.uuid4()
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        # Mock the user and session objects
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.tenant_id = tenant_a_id
        mock_auth_context.return_value = (mock_user, mock_session)

        project_id = uuid.uuid4()
        # Middleware will call db.scalar to check the project.
        # We want it to return None (so the middleware blocks the request).
        mock_db.scalar.return_value = None

        response = client.get(
            f"/api/v1/projects/{project_id}",
            headers={"Authorization": "Bearer fake-token"}
        )
        # Middleware should block the request with 403.
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {"detail": "Access to resource is forbidden"}


def test_tenant_isolation_allows_no_auth():
    client = TestClient(app)
    with patch('refyne.db.session.SessionLocal') as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        # No authorization header
        response = client.get("/nonexistent")
        # Middleware should skip isolation (no auth), so it should not return 403.
        # The app will return 404 for nonexistent endpoint.
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_tenant_isolation_post_with_json_body():
    client = TestClient(app)
    with patch('refyne.db.session.SessionLocal') as mock_session_local, \
         patch('refyne.main._authenticated_context') as mock_auth_context:

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.tenant_id = tenant_id
        mock_auth_context.return_value = (mock_user, mock_session)

        response = client.post(
            "/api/v1/integrations/jira/configure",
            headers={"Authorization": "Bearer fake-token"},
            json={"config": {"baseUrl": "https://refyne.atlassian.net", "email": "test@test.com", "apiToken": "tok", "projectKey": "REQ"}}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


if __name__ == "__main__":
    test_tenant_isolation_allows_same_tenant()
    test_tenant_isolation_blocks_cross_tenant()
    test_tenant_isolation_allows_no_auth()
    test_tenant_isolation_post_with_json_body()
    print("All tenant isolation tests passed!")