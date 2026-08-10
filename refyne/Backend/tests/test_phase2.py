import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import uuid
import pandas as pd
from pypdf import PdfWriter
import docx

from app.main import app
from app.core.database import Base
from app.api.deps import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.models.project import Project, Workspace
from app.models.document import Document, DocumentChunk
from app.rag.bm25.index import BM25Index
from app.rag.chroma.store import get_chroma_store

# Use a unique DB filename per test session to avoid stale data conflicts
import time as _time
_DB_SUFFIX = str(int(_time.time()))
SQLALCHEMY_DATABASE_URL = f"sqlite:///./test_phase2_{_DB_SUFFIX}.db"
_DB_FILE = f"test_phase2_{_DB_SUFFIX}.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(scope="module", autouse=True)
def set_db_override():
    """Set and restore the DB override for this module only."""
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    user1_id = str(uuid.uuid4())
    user1 = User(id=user1_id, full_name="User One", email="user1@example.com", password_hash=get_password_hash("password123"))
    db.add(user1)
    
    user2_id = str(uuid.uuid4())
    user2 = User(id=user2_id, full_name="User Two", email="user2@example.com", password_hash=get_password_hash("password123"))
    db.add(user2)
    db.commit()

    response = client.post("/api/auth/login", json={"email": "user1@example.com", "password": "password123"})
    token1 = response.json()["access_token"]
    
    response = client.post("/api/auth/login", json={"email": "user2@example.com", "password": "password123"})
    token2 = response.json()["access_token"]

    response = client.post("/api/projects", headers={"Authorization": f"Bearer {token1}"}, json={"name": "Project 1", "description": "Desc"})
    project1_id = response.json()["id"]

    yield db, token1, token2, project1_id
    
    db.close()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_DB_FILE):
        try:
            os.remove(_DB_FILE)
        except Exception:
            pass

@pytest.fixture(scope="module")
def test_files():
    files = {}
    
    with open("test.txt", "w") as f:
        f.write("This is a test document. It contains some simple text for testing embeddings.")
    files["txt"] = "test.txt"
    
    df = pd.DataFrame({"Name": ["Alice", "Bob"], "Age": [25, 30]})
    df.to_csv("test.csv", index=False)
    files["csv"] = "test.csv"
    
    df.to_excel("test.xlsx", index=False)
    files["xlsx"] = "test.xlsx"
    
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with open("test.pdf", "wb") as f:
        writer.write(f)
    files["pdf"] = "test.pdf"
    
    doc = docx.Document()
    doc.add_paragraph("Test docx paragraph.")
    doc.save("test.docx")
    files["docx"] = "test.docx"
    
    with open("test.doc", "w") as f:
        f.write("Fake legacy doc")
    files["doc"] = "test.doc"
    
    with open("empty.txt", "w") as f:
        f.write("")
    files["empty"] = "empty.txt"
    
    yield files
    
    for path in files.values():
        if os.path.exists(path):
            os.remove(path)


def test_upload_txt(setup_db, test_files):
    db, token1, _, project1_id = setup_db
    with open(test_files["txt"], "rb") as f:
        response = client.post(
            f"/api/projects/{project1_id}/documents/upload",
            headers={"Authorization": f"Bearer {token1}"},
            files={"file": ("test.txt", f, "text/plain")}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "indexed"
    
    # Verify chunks in DB
    doc_id = response.json()["id"]
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    assert len(chunks) > 0
    
    # Verify ChromaDB deterministic ID
    chroma = get_chroma_store().get_or_create_collection(project1_id)
    chroma_res = chroma.get(ids=[f"{doc_id}_0"])
    assert len(chroma_res["ids"]) > 0
    assert "test document" in chroma_res["documents"][0]
    
    # Verify BM25 persistence
    bm25 = BM25Index(project1_id)
    assert len(bm25.corpus) > 0

def test_upload_empty_document(setup_db, test_files):
    db, token1, _, project1_id = setup_db
    with open(test_files["empty"], "rb") as f:
        response = client.post(
            f"/api/projects/{project1_id}/documents/upload",
            headers={"Authorization": f"Bearer {token1}"},
            files={"file": ("empty.txt", f, "text/plain")}
        )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_delete_document(setup_db, test_files):
    db, token1, _, project1_id = setup_db
    # Upload docx
    with open(test_files["docx"], "rb") as f:
        response = client.post(
            f"/api/projects/{project1_id}/documents/upload",
            headers={"Authorization": f"Bearer {token1}"},
            files={"file": ("test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    doc_id = response.json()["id"]
    
    # Delete document
    del_response = client.delete(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {token1}"})
    assert del_response.status_code == 200
    
    # Verify chunks are gone from DB
    assert len(db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()) == 0
    
    # Verify Chroma chunk is gone
    chroma = get_chroma_store().get_or_create_collection(project1_id)
    chroma_res = chroma.get(ids=[f"{doc_id}_0"])
    assert len(chroma_res["ids"]) == 0
    
    # Verify BM25 rebuilt without it
    bm25 = BM25Index(project1_id)
    for meta in bm25.metadatas:
        assert meta.get("document_id") != doc_id

def test_reindex_document(setup_db, test_files):
    db, token1, _, project1_id = setup_db
    # Upload csv
    with open(test_files["csv"], "rb") as f:
        response = client.post(
            f"/api/projects/{project1_id}/documents/upload",
            headers={"Authorization": f"Bearer {token1}"},
            files={"file": ("test.csv", f, "text/csv")}
        )
    doc_id = response.json()["id"]
    
    # Reindex
    reindex_res = client.post(f"/api/documents/{doc_id}/reindex", headers={"Authorization": f"Bearer {token1}"})
    assert reindex_res.status_code == 200
    assert reindex_res.json()["status"] == "indexed"
    
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    assert len(chunks) > 0
    
    chroma = get_chroma_store().get_or_create_collection(project1_id)
    chroma_res = chroma.get(ids=[f"{doc_id}_0"])
    assert len(chroma_res["ids"]) > 0

def test_project_ownership(setup_db, test_files):
    db, token1, token2, project1_id = setup_db
    # Upload PDF
    with open(test_files["pdf"], "rb") as f:
        response = client.post(
            f"/api/projects/{project1_id}/documents/upload",
            headers={"Authorization": f"Bearer {token1}"},
            files={"file": ("test.pdf", f, "application/pdf")}
        )
    doc_id = response.json()["id"]
    
    # User 2 tries to GET
    get_res = client.get(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {token2}"})
    assert get_res.status_code == 404
    
    # User 2 tries to DELETE
    del_res = client.delete(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {token2}"})
    assert del_res.status_code == 404
