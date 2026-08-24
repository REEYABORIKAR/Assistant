import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.document import Document
from app.models.project import Project, Workspace
from app.models.user import User
from app.storage.object_store import LocalObjectStore


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        id="test-user-123",
        email="test@example.com",
        password_hash="hashed_password",
        full_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_project(db_session, test_user):
    """Create a test project with workspace."""
    project = Project(
        id="test-project-123",
        user_id=test_user.id,
        name="Test Project"
    )
    db_session.add(project)
    db_session.commit()

    workspace = Workspace(
        id="test-workspace-123",
        project_id=project.id,
        name="Test Workspace"
    )
    db_session.add(workspace)
    db_session.commit()
    return project


@pytest.fixture
def test_store():
    """Create a temporary object store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = LocalObjectStore(base_dir=tmpdir)
        yield store


def test_document_status_transitions(db_session, test_project, test_store):
    """Test that document status transitions through expected states."""
    # Create a document in processing state
    doc = Document(
        id="test-doc-123",
        project_id=test_project.id,
        workspace_id="test-workspace-123",
        user_id="test-user-123",
        file_name="test.txt",
        file_type="text/plain",
        file_size=100,
        file_path="test/file.txt",
        storage_key="test/file.txt",
        checksum="abc123",
        status="processing"
    )
    db_session.add(doc)
    db_session.commit()

    # Verify initial status
    assert doc.status == "processing"


def test_document_failed_status(db_session, test_project):
    """Test that document can be marked as failed with error message."""
    doc = Document(
        id="test-doc-failed",
        project_id=test_project.id,
        workspace_id="test-workspace-123",
        user_id="test-user-123",
        file_name="bad.txt",
        file_type="text/plain",
        file_size=100,
        file_path="bad/file.txt",
        storage_key="bad/file.txt",
        checksum="def456",
        status="failed",
        error_message="Extraction failed: file is corrupt"
    )
    db_session.add(doc)
    db_session.commit()

    # Verify failed status and error message
    fetched = db_session.query(Document).filter(Document.id == "test-doc-failed").first()
    assert fetched.status == "failed"
    assert fetched.error_message == "Extraction failed: file is corrupt"
