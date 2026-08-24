"""
Security tests for Phase C: authorization, cross-project isolation, role gating.
"""
import os
import sys
import uuid
from unittest.mock import MagicMock

import pytest

# Set env BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite:///./test_security.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ["RERANK_ENABLED"] = "false"
os.environ["QUERY_EXPANSION_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""

# Import validation function BEFORE mocking vector_store
from app.rag.vector_store import validate_chunk_metadata  # noqa: E402

# Mock heavy ML imports after importing validation
for mod in [
    "app.rag.embeddings.model", "sentence_transformers", "chromadb",
]:
    sys.modules.setdefault(mod, MagicMock())

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import projects as projects_router
from app.api.deps import get_current_user, get_db
from app.core.database import Base
from app.core.roles import ProjectRole, role_has_permission
from app.models.membership import ProjectMember
from app.models.project import Project
from app.models.user import User

# ── Test DB Setup ──────────────────────────────────────────────────────────────
TEST_DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./test_security.db")
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()
app.include_router(projects_router.router)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


def _create_user(db, email=None):
    user = User(
        id=str(uuid.uuid4()),
        email=email or f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        full_name="Test User",
    )
    db.add(user)
    db.commit()
    return user


def _create_project(db, user):
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        user_id=user.id,
    )
    db.add(project)
    db.commit()
    return project


def _add_member(db, project, user, role):
    member = ProjectMember(
        id=str(uuid.uuid4()),
        project_id=project.id,
        user_id=user.id,
        role=role,
    )
    db.add(member)
    db.commit()
    return member


# ── Tests: Role Hierarchy ─────────────────────────────────────────────────────

class TestRoleHierarchy:
    def test_admin_has_highest_permissions(self):
        assert role_has_permission(ProjectRole.ADMIN, ProjectRole.ADMIN)
        assert role_has_permission(ProjectRole.ADMIN, ProjectRole.EDITOR)
        assert role_has_permission(ProjectRole.ADMIN, ProjectRole.REVIEWER)
        assert role_has_permission(ProjectRole.ADMIN, ProjectRole.VIEWER)

    def test_viewer_has_lowest_permissions(self):
        assert role_has_permission(ProjectRole.VIEWER, ProjectRole.VIEWER)
        assert not role_has_permission(ProjectRole.VIEWER, ProjectRole.REVIEWER)
        assert not role_has_permission(ProjectRole.VIEWER, ProjectRole.EDITOR)
        assert not role_has_permission(ProjectRole.VIEWER, ProjectRole.ADMIN)

    def test_editor_has_more_permissions_than_reviewer(self):
        # EDITOR (1) <= REVIEWER (2), so EDITOR can do REVIEWER things
        assert role_has_permission(ProjectRole.EDITOR, ProjectRole.EDITOR)
        assert role_has_permission(ProjectRole.EDITOR, ProjectRole.REVIEWER)
        assert role_has_permission(ProjectRole.EDITOR, ProjectRole.VIEWER)

    def test_reviewer_cannot_edit(self):
        assert role_has_permission(ProjectRole.REVIEWER, ProjectRole.REVIEWER)
        assert role_has_permission(ProjectRole.REVIEWER, ProjectRole.VIEWER)
        assert not role_has_permission(ProjectRole.REVIEWER, ProjectRole.EDITOR)
        assert not role_has_permission(ProjectRole.REVIEWER, ProjectRole.ADMIN)


# ── Tests: Project Access ─────────────────────────────────────────────────────

class TestProjectAccess:
    def test_owner_can_access_project(self, db):
        owner = _create_user(db)
        project = _create_project(db, owner)

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: owner

        resp = client.get(f"/api/projects/{project.id}")
        assert resp.status_code == 200
        app.dependency_overrides.clear()

    def test_member_can_access_project(self, db):
        owner = _create_user(db)
        member = _create_user(db)
        project = _create_project(db, owner)
        _add_member(db, project, member, ProjectRole.VIEWER.value)

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: member

        resp = client.get(f"/api/projects/{project.id}")
        assert resp.status_code == 200
        app.dependency_overrides.clear()

    def test_non_member_cannot_access_project(self, db):
        owner = _create_user(db)
        stranger = _create_user(db)
        project = _create_project(db, owner)

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: stranger

        resp = client.get(f"/api/projects/{project.id}")
        assert resp.status_code == 404
        app.dependency_overrides.clear()

    def test_cross_project_isolation(self, db):
        owner_a = _create_user(db)
        owner_b = _create_user(db)
        project_a = _create_project(db, owner_a)
        project_b = _create_project(db, owner_b)

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: owner_a

        resp = client.get(f"/api/projects/{project_b.id}")
        assert resp.status_code == 404
        app.dependency_overrides.clear()


# ── Tests: Vector Store Auth Metadata ─────────────────────────────────────────

class TestVectorStoreAuth:
    def test_upsert_rejects_chunks_without_allowed_roles(self):
        bad_chunk = {
            "text": "test",
            "metadata": {
                "project_id": "proj-1",
                "document_id": "doc-1",
                "chunk_index": 0,
                "owner_id": "user-1",
            }
        }
        with pytest.raises(ValueError, match="allowed_roles"):
            validate_chunk_metadata(bad_chunk)

    def test_upsert_rejects_chunks_without_owner_id(self):
        bad_chunk = {
            "text": "test",
            "metadata": {
                "project_id": "proj-1",
                "document_id": "doc-1",
                "chunk_index": 0,
                "allowed_roles": ["ADMIN"],
            }
        }
        with pytest.raises(ValueError, match="owner_id"):
            validate_chunk_metadata(bad_chunk)

    def test_upsert_accepts_valid_chunk(self):
        good_chunk = {
            "text": "test",
            "metadata": {
                "project_id": "proj-1",
                "document_id": "doc-1",
                "chunk_index": 0,
                "owner_id": "user-1",
                "allowed_roles": ["ADMIN", "EDITOR"],
            }
        }
        validate_chunk_metadata(good_chunk)


# ── Tests: BM25 Auth Filtering ───────────────────────────────────────────────

class TestBM25AuthFilter:
    def test_bm25_filters_by_role(self):
        from app.rag.bm25.index import BM25Index
        from app.rag.retrieval.bm25 import bm25_search

        project_id = str(uuid.uuid4())

        chunks = [
            {
                "text": "admin only content",
                "metadata": {
                    "project_id": project_id,
                    "document_id": "doc-1",
                    "chunk_index": 0,
                    "allowed_roles": ["ADMIN"],
                },
            },
            {
                "text": "viewer accessible content",
                "metadata": {
                    "project_id": project_id,
                    "document_id": "doc-1",
                    "chunk_index": 1,
                    "allowed_roles": ["ADMIN", "EDITOR", "REVIEWER", "VIEWER"],
                },
            },
        ]

        bm25 = BM25Index(project_id=project_id)
        bm25.add_chunks(chunks)

        # VIEWER should only see the viewer-accessible chunk
        results, _ = bm25_search(project_id, "content", n_candidates=10, user_role="VIEWER")
        assert len(results) == 1
        assert "viewer accessible" in results[0]["text"]

        # ADMIN should see both
        results, _ = bm25_search(project_id, "content", n_candidates=10, user_role="ADMIN")
        assert len(results) == 2
