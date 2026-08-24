"""
Phase 4 Advanced RAG Test Suite

Tests the advanced-retrieval additions on top of the Phase 3 hybrid pipeline:

  1.  Query expansion — PRF term extraction correctness
  2.  Query expansion — stopword / duplicate-term exclusion
  3.  Query expansion — empty-candidate handling
  4.  Query expansion — expanded query construction
  5.  Reranker — reorders candidates by cross-encoder score (stubbed model)
  6.  Reranker — graceful fallback when the model is unavailable
  7.  Reranker — empty-candidate handling
  8.  Generate endpoint — no API key returns configured=false (graceful)
  9.  Generate endpoint — citations present from retrieved context
  10. Generate endpoint — invalid query rejected
  11. Generate endpoint — unauthorized access → 404 (no existence leak)
  12. Generate endpoint — requires authentication
"""

import os
import time as _time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.database import Base
from app.core.security import get_password_hash
from app.main import app
from app.models.user import User
from app.rag.retrieval.query_expansion import expand_query, extract_expansion_terms
from app.rag.retrieval.reranker import RerankerSingleton, rerank_results

_DB_SUFFIX = str(int(_time.time()))
SQLALCHEMY_DATABASE_URL = f"sqlite:///./test_phase4_{_DB_SUFFIX}.db"
_DB_FILE = f"test_phase4_{_DB_SUFFIX}.db"
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
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


@pytest.fixture(scope="module")
def test_env():
    """
    One user, one project, one small uploaded document so the generate
    endpoint has retrievable context.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    user = User(id=str(uuid.uuid4()), full_name="Carol", email="carol@example.com",
                password_hash=get_password_hash("pass1234"))
    db.add(user)
    db.commit()

    r = client.post("/api/auth/login", json={"email": "carol@example.com", "password": "pass1234"})
    token = r.json()["access_token"]

    r = client.post("/api/projects", headers={"Authorization": f"Bearer {token}"},
                    json={"name": "Gamma", "description": ""})
    project_id = r.json()["id"]

    text = (
        "Payment Processing Requirements\n\n"
        "REQ-PAY-001: The system must retry failed payment transactions up to 3 times.\n"
        "REQ-PAY-002: When a payment fails, the user must receive an email notification within 5 minutes.\n"
    )
    with open("phase4_pay.txt", "w") as f:
        f.write(text)

    r = client.post(
        f"/api/projects/{project_id}/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("phase4_payment.txt", open("phase4_pay.txt", "rb"), "text/plain")},
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    doc_id = r.json()["id"]

    yield {
        "db": db,
        "token": token,
        "project_id": project_id,
        "doc_id": doc_id,
    }

    db.close()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    for f in [_DB_FILE, "phase4_pay.txt"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


# ─────────────── UNIT TESTS: Query Expansion ────────────────────────────────

class TestQueryExpansion:
    def test_extracts_discriminating_terms(self):
        candidates = [
            {"text": "REQ-PAY-001: retry failed payment transactions three times"},
            {"text": "REQ-PAY-002: failed payment email notification within minutes"},
            {"text": "REQ-PAY-003: payment data encrypted using AES"},
        ]
        terms = extract_expansion_terms("What happens when a transaction fails?", candidates, top_terms=4)
        assert terms
        # The expanded terms should come from the pseudo-relevant chunks
        assert "payment" in terms
        assert all(len(t) >= 3 for t in terms)

    def test_stopwords_excluded(self):
        candidates = [{"text": "the and of to for payment retry"}]
        terms = extract_expansion_terms("query", candidates, top_terms=10)
        assert "payment" in terms
        assert "the" not in terms
        assert "and" not in terms

    def test_query_terms_not_repeated(self):
        """Terms already present in the query must not be added again."""
        candidates = [{"text": "payment retry failed transaction"}]
        terms = extract_expansion_terms("payment retry", candidates, top_terms=10)
        assert "payment" not in terms
        assert "retry" not in terms

    def test_empty_candidates(self):
        assert extract_expansion_terms("query", [], top_terms=4) == []

    def test_expand_query_appends_terms(self):
        candidates = [{"text": "payment retry failed transaction notification"}]
        expanded, added = expand_query("What is the retry policy?", candidates, top_terms=3)
        assert added
        assert expanded.startswith("What is the retry policy?")
        assert all(term in expanded for term in added)

    def test_expand_query_identity_when_no_terms(self):
        expanded, added = expand_query("the and of", [], top_terms=4)
        assert added == []
        assert expanded == "the and of"


# ─────────────── UNIT TESTS: Reranker ───────────────────────────────────────

class TestReranker:
    def test_rerank_reorders_by_score(self, monkeypatch):
        class FakeModel:
            def predict(self, pairs):
                # Longer candidate text = higher relevance score
                return [float(len(p[1])) for p in pairs]

        monkeypatch.setattr(RerankerSingleton, "_model", FakeModel())
        monkeypatch.setattr(RerankerSingleton, "_load_error", None)

        candidates = [
            {"chunk_id": "a", "text": "short", "hybrid_score": 0.9},
            {"chunk_id": "b", "text": "this is a much longer chunk of text content", "hybrid_score": 0.8},
            {"chunk_id": "c", "text": "medium length text", "hybrid_score": 0.85},
        ]
        results, flag, _ = rerank_results("query", candidates, top_k=2)
        assert flag is True
        assert len(results) == 2
        assert results[0]["chunk_id"] == "b"
        assert results[0]["rerank_score"] >= results[1]["rerank_score"]

    def test_fallback_when_model_unavailable(self, monkeypatch):
        """Without a loaded model, candidates must pass through unchanged."""
        monkeypatch.setattr(RerankerSingleton, "_model", None)
        monkeypatch.setattr(RerankerSingleton, "_load_error", "offline")

        candidates = [
            {"chunk_id": "a", "text": "x", "hybrid_score": 0.5},
            {"chunk_id": "b", "text": "y", "hybrid_score": 0.7},
        ]
        results, flag, _ = rerank_results("query", candidates)
        assert flag is False
        assert [r["chunk_id"] for r in results] == ["a", "b"]
        assert all(r.get("rerank_score") is None for r in results)

    def test_empty_candidates(self, monkeypatch):
        monkeypatch.setattr(RerankerSingleton, "_model", None)
        monkeypatch.setattr(RerankerSingleton, "_load_error", "offline")
        results, flag, _ = rerank_results("query", [])
        assert results == []
        assert flag is False


# ─────────────── INTEGRATION TESTS: Generate endpoint ───────────────────────

class TestGenerateAPI:
    def test_generate_unconfigured_returns_graceful(self, test_env):
        """With no GROQ_API_KEY, the endpoint must not 500 — it reports configured=false."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_id']}/generate",
            headers={"Authorization": f"Bearer {env['token']}"},
            json={"query": "What is the payment retry policy?", "top_k": 3},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["configured"] is False
        assert data["answer"] == ""
        assert data["message"]

    def test_generate_returns_citations_from_context(self, test_env):
        """Retrieval runs before generation, so citations/sources are present."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_id']}/generate",
            headers={"Authorization": f"Bearer {env['token']}"},
            json={"query": "payment retry", "top_k": 3},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["citations"]
        assert data["source_documents"]
        assert "SOURCE 1" in data["context"]

    def test_generate_invalid_query_rejected(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_id']}/generate",
            headers={"Authorization": f"Bearer {env['token']}"},
            json={"query": "   ", "top_k": 3},
        )
        assert r.status_code == 422

    def test_generate_unauthorized_project_no_existence_leak(self, test_env):
        env = test_env
        fake_id = str(uuid.uuid4())
        r = client.post(
            f"/api/projects/{fake_id}/generate",
            headers={"Authorization": f"Bearer {env['token']}"},
            json={"query": "payment", "top_k": 3},
        )
        assert r.status_code == 404

    def test_generate_requires_authentication(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_id']}/generate",
            json={"query": "payment", "top_k": 3},
        )
        assert r.status_code == 401
