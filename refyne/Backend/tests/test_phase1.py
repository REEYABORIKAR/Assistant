import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.api.deps import get_db
from app.core.database import Base
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_refyne.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

# ==============================
# AUTH TESTS
# ==============================

def test_register_success():
    response = client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data

def test_register_duplicate_email():
    client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "test2@example.com",
        "password": "password123"
    })
    response = client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "test2@example.com",
        "password": "password123"
    })
    assert response.status_code == 409

def test_register_invalid_data():
    response = client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "123"
    })
    assert response.status_code == 422

def test_login_success():
    client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "login@example.com",
        "password": "password123"
    })
    response = client.post("/api/auth/login", json={
        "email": "login@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_password():
    client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "login2@example.com",
        "password": "password123"
    })
    response = client.post("/api/auth/login", json={
        "email": "login2@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_get_current_user():
    client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "me@example.com",
        "password": "password123"
    })
    login_response = client.post("/api/auth/login", json={
        "email": "me@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"

def test_missing_jwt():
    response = client.get("/api/auth/me")
    assert response.status_code == 401

# ==============================
# PROJECT & WORKSPACE TESTS
# ==============================

@pytest.fixture
def auth_headers():
    client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "proj@example.com",
        "password": "password123"
    })
    response = client.post("/api/auth/login", json={
        "email": "proj@example.com",
        "password": "password123"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_create_project(auth_headers):
    response = client.post("/api/projects", json={
        "name": "My Project",
        "description": "Test description"
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Project"

    # Verify workspace
    ws_response = client.get(f"/api/projects/{data['id']}/workspace", headers=auth_headers)
    assert ws_response.status_code == 200
    assert ws_response.json()["name"] == "My Project Workspace"

def test_list_projects(auth_headers):
    client.post("/api/projects", json={"name": "Proj 1"}, headers=auth_headers)
    client.post("/api/projects", json={"name": "Proj 2"}, headers=auth_headers)

    response = client.get("/api/projects", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

def test_update_project(auth_headers):
    proj_response = client.post("/api/projects", json={"name": "Old Name"}, headers=auth_headers)
    proj_id = proj_response.json()["id"]

    update_response = client.put(f"/api/projects/{proj_id}", json={"name": "New Name"}, headers=auth_headers)
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "New Name"

def test_duplicate_project(auth_headers):
    proj_response = client.post("/api/projects", json={"name": "Original"}, headers=auth_headers)
    proj_id = proj_response.json()["id"]

    dup_response = client.post(f"/api/projects/{proj_id}/duplicate", headers=auth_headers)
    assert dup_response.status_code == 201
    assert dup_response.json()["name"] == "Original (Copy)"

    # check new workspace
    new_id = dup_response.json()["id"]
    ws_response = client.get(f"/api/projects/{new_id}/workspace", headers=auth_headers)
    assert ws_response.status_code == 200
    assert ws_response.json()["name"] == "Original (Copy) Workspace"

def test_delete_project(auth_headers):
    proj_response = client.post("/api/projects", json={"name": "To Delete"}, headers=auth_headers)
    proj_id = proj_response.json()["id"]

    del_response = client.delete(f"/api/projects/{proj_id}", headers=auth_headers)
    assert del_response.status_code == 204

    get_response = client.get(f"/api/projects/{proj_id}", headers=auth_headers)
    assert get_response.status_code == 404

def test_update_workspace(auth_headers):
    proj_response = client.post("/api/projects", json={"name": "My Project"}, headers=auth_headers)
    proj_id = proj_response.json()["id"]

    ws_response = client.get(f"/api/projects/{proj_id}/workspace", headers=auth_headers)
    ws_id = ws_response.json()["id"]

    update_ws_response = client.put(f"/api/workspaces/{ws_id}", json={"name": "New Workspace Name"}, headers=auth_headers)
    assert update_ws_response.status_code == 200
    assert update_ws_response.json()["name"] == "New Workspace Name"

# ==============================
# SECURITY TESTS
# ==============================

def test_security_isolation():
    # User A
    client.post("/api/auth/register", json={"full_name": "User A", "email": "a@example.com", "password": "passwordA"})
    res_a = client.post("/api/auth/login", json={"email": "a@example.com", "password": "passwordA"})
    headers_a = {"Authorization": f"Bearer {res_a.json()['access_token']}"}

    # User B
    client.post("/api/auth/register", json={"full_name": "User B", "email": "b@example.com", "password": "passwordB"})
    res_b = client.post("/api/auth/login", json={"email": "b@example.com", "password": "passwordB"})
    headers_b = {"Authorization": f"Bearer {res_b.json()['access_token']}"}

    # Create Project A
    proj_a = client.post("/api/projects", json={"name": "Proj A"}, headers=headers_a).json()
    proj_a_id = proj_a["id"]
    ws_a = client.get(f"/api/projects/{proj_a_id}/workspace", headers=headers_a).json()
    ws_a_id = ws_a["id"]

    # User B attempts to access Project A
    assert client.get(f"/api/projects/{proj_a_id}", headers=headers_b).status_code == 404
    assert client.put(f"/api/projects/{proj_a_id}", json={"name": "Hack"}, headers=headers_b).status_code == 404
    assert client.delete(f"/api/projects/{proj_a_id}", headers=headers_b).status_code == 404
    assert client.post(f"/api/projects/{proj_a_id}/duplicate", headers=headers_b).status_code == 404
    assert client.get(f"/api/projects/{proj_a_id}/workspace", headers=headers_b).status_code == 404
    assert client.put(f"/api/workspaces/{ws_a_id}", json={"name": "Hack WS"}, headers=headers_b).status_code == 404
