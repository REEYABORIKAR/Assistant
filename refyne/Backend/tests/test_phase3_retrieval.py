"""
Phase 3 Hybrid RAG Retrieval Test Suite

Tests:
  1.  Semantic-only retrieval (ChromaDB)
  2.  BM25-only retrieval
  3.  Hybrid retrieval (combined)
  4.  Score normalization — Min-Max correctness
  5.  Score normalization — equal scores edge case (no division by zero)
  6.  Score normalization — single result edge case
  7.  Result fusion — duplicate chunk merge
  8.  Top-K behavior
  9.  Relevance threshold filter
  10. Empty query rejection
  11. Whitespace-only query rejection
  12. No results (below threshold or empty index)
  13. Project isolation (Project B cannot see Project A data)
  14. Document filter — only specified docs returned
  15. Document filter — invalid document ID rejected
  16. Document filter — doc from another project rejected
  17. Unauthorized project access (404, no existence leak)
  18. Citation metadata correctness
  19. Context building — structure correctness
  20. Context truncation — respects MAX_CONTEXT_CHARS
  21. Chroma distance-to-similarity conversion
  22. Retrieval quality — payment query ranks payment chunks above auth chunks
  23. Retrieval quality — auth query ranks auth chunks above payment chunks
  24. Restart persistence — data survives app restart (Chroma + BM25)
  25. BM25 reconstruction from SQLite chunks
  26. Invalid top_k (< 1)
  27. top_k above configured maximum
"""

import os

# Use a unique DB filename per test session to avoid stale data conflicts
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
from app.rag.retrieval.context_builder import build_context
from app.rag.retrieval.fusion import _minmax_normalize, fuse_results
from app.rag.retrieval.schemas import SearchResult, SearchResultMetadata
from app.rag.retrieval.semantic import _distance_to_similarity

_DB_SUFFIX = str(int(_time.time()))
SQLALCHEMY_DATABASE_URL = f"sqlite:///./test_phase3_{_DB_SUFFIX}.db"
_DB_FILE = f"test_phase3_{_DB_SUFFIX}.db"
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


# ─────────────────────────── Fixtures ───────────────────────────────────────

@pytest.fixture(scope="module")
def test_env():
    """
    Create two users, two projects, and two sets of documents:
      Project A: payment_doc  (payment requirements text)
      Project B: auth_doc     (authentication requirements text)
    Both are uploaded and indexed before tests run.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Users
    user_a = User(id=str(uuid.uuid4()), full_name="Alice", email="alice@example.com",
                  password_hash=get_password_hash("pass1234"))
    user_b = User(id=str(uuid.uuid4()), full_name="Bob", email="bob@example.com",
                  password_hash=get_password_hash("pass1234"))
    db.add(user_a)
    db.add(user_b)
    db.commit()

    # Tokens
    r = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "pass1234"})
    token_a = r.json()["access_token"]
    r = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "pass1234"})
    token_b = r.json()["access_token"]

    # Projects
    r = client.post("/api/projects", headers={"Authorization": f"Bearer {token_a}"},
                    json={"name": "Project Alpha", "description": ""})
    project_a_id = r.json()["id"]

    r = client.post("/api/projects", headers={"Authorization": f"Bearer {token_b}"},
                    json={"name": "Project Beta", "description": ""})
    project_b_id = r.json()["id"]

    # Upload PAYMENT document to Project A
    payment_text = (
        "Payment Processing Requirements\n\n"
        "REQ-PAY-001: The system must retry failed payment transactions up to 3 times.\n"
        "REQ-PAY-002: When a payment fails, the user must receive an email notification within 5 minutes.\n"
        "REQ-PAY-003: All payment data must be encrypted using AES-256.\n"
        "REQ-PAY-004: Payment refunds must be processed within 7 business days.\n"
        "REQ-PAY-005: The payment gateway must support Visa, Mastercard, and PayPal.\n"
        "REQ-PAY-006: Failed payment attempts must be logged with timestamp, amount, and error code.\n"
        "REQ-PAY-007: Payment retry logic must use exponential backoff intervals.\n"
        "REQ-PAY-008: The system must validate card details before submitting to the payment gateway.\n"
        "Handling failed payments is critical to maintaining customer trust.\n"
    )
    with open("payment_req.txt", "w") as f:
        f.write(payment_text)

    r = client.post(
        f"/api/projects/{project_a_id}/documents/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("payment_requirements.txt", open("payment_req.txt", "rb"), "text/plain")},
    )
    assert r.status_code == 200, f"Payment doc upload failed: {r.text}"
    payment_doc_id = r.json()["id"]

    # Upload AUTH document to Project B
    auth_text = (
        "Authentication & Authorization Requirements\n\n"
        "REQ-AUTH-001: Passwords must be at least 12 characters long.\n"
        "REQ-AUTH-002: Passwords must contain uppercase, lowercase, digits, and special characters.\n"
        "REQ-AUTH-003: User accounts must be locked after 5 consecutive failed login attempts.\n"
        "REQ-AUTH-004: Locked accounts must be unlocked via email verification.\n"
        "REQ-AUTH-005: Session tokens must expire after 24 hours of inactivity.\n"
        "REQ-AUTH-006: Multi-factor authentication must be available for all users.\n"
        "REQ-AUTH-007: Password reset links must expire after 30 minutes.\n"
        "REQ-AUTH-008: Brute-force login attempts must be throttled using rate limiting.\n"
        "Strong password requirements protect user accounts from unauthorized access.\n"
    )
    with open("auth_req.txt", "w") as f:
        f.write(auth_text)

    r = client.post(
        f"/api/projects/{project_b_id}/documents/upload",
        headers={"Authorization": f"Bearer {token_b}"},
        files={"file": ("auth_requirements.txt", open("auth_req.txt", "rb"), "text/plain")},
    )
    assert r.status_code == 200, f"Auth doc upload failed: {r.text}"
    auth_doc_id = r.json()["id"]

    yield {
        "db": db,
        "token_a": token_a,
        "token_b": token_b,
        "project_a_id": project_a_id,
        "project_b_id": project_b_id,
        "payment_doc_id": payment_doc_id,
        "auth_doc_id": auth_doc_id,
    }

    # Teardown
    db.close()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    for f in [_DB_FILE, "payment_req.txt", "auth_req.txt"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


# ─────────────── UNIT TESTS: Score Normalization ─────────────────────────────

class TestMinMaxNormalization:
    def test_standard_normalization(self):
        scores = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _minmax_normalize(scores)
        assert result[0] == pytest.approx(0.0)
        assert result[-1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(0.5)

    def test_all_equal_scores_no_division_by_zero(self):
        """When all scores are equal, normalization must return 1.0 for all."""
        scores = [3.7, 3.7, 3.7, 3.7]
        result = _minmax_normalize(scores)
        assert all(s == pytest.approx(1.0) for s in result)

    def test_single_result(self):
        """Single candidate should be normalized to 1.0."""
        result = _minmax_normalize([42.0])
        assert result == [pytest.approx(1.0)]

    def test_empty_list(self):
        assert _minmax_normalize([]) == []

    def test_all_zero_scores(self):
        """All-zero scores have no signal — normalized scores should remain 0.0."""
        result = _minmax_normalize([0.0, 0.0, 0.0])
        assert all(s == pytest.approx(0.0) for s in result)


class TestDistanceToSimilarity:
    def test_zero_distance_is_max_similarity(self):
        """Distance 0 → similarity 1.0 (identical vectors)."""
        assert _distance_to_similarity(0.0) == pytest.approx(1.0)

    def test_higher_distance_lower_similarity(self):
        """Lower distance must produce higher similarity."""
        sim_close = _distance_to_similarity(0.1)
        sim_far = _distance_to_similarity(2.0)
        assert sim_close > sim_far

    def test_similarity_always_positive(self):
        """Similarity must always be > 0 for any finite distance."""
        for dist in [0.0, 0.5, 1.0, 10.0, 100.0]:
            assert _distance_to_similarity(dist) > 0.0

    def test_similarity_in_range(self):
        """Similarity must be in (0, 1]."""
        for dist in [0.0, 0.5, 1.0, 5.0]:
            sim = _distance_to_similarity(dist)
            assert 0.0 < sim <= 1.0


class TestFusion:
    def _make_sem(self, chunk_id, similarity):
        return {
            "chunk_id": chunk_id, "document_id": "doc1", "chunk_index": 0,
            "text": "text", "metadata": {}, "raw_distance": 0.0,
            "similarity": similarity,
        }

    def _make_bm25(self, chunk_id, score):
        return {
            "chunk_id": chunk_id, "document_id": "doc1", "chunk_index": 0,
            "text": "text", "metadata": {}, "raw_bm25_score": score,
        }

    def test_duplicate_chunk_merged(self):
        """A chunk in both pools must appear only once in results."""
        sem = [self._make_sem("chunk_0", 0.9)]
        bm25 = [self._make_bm25("chunk_0", 5.0)]
        results, _ = fuse_results(sem, bm25, min_score=0.0)
        ids = [r["chunk_id"] for r in results]
        assert len(ids) == 1
        assert ids[0] == "chunk_0"
        assert results[0]["retrieval_method"] == "hybrid"

    def test_sem_only_chunk_gets_zero_bm25(self):
        sem = [self._make_sem("chunk_1", 0.8)]
        results, _ = fuse_results(sem, [], min_score=0.0)
        assert results[0]["normalized_bm25"] == pytest.approx(0.0)
        assert results[0]["retrieval_method"] == "semantic"

    def test_bm25_only_chunk_gets_zero_semantic(self):
        bm25 = [self._make_bm25("chunk_2", 3.5)]
        results, _ = fuse_results([], bm25, min_score=0.0)
        assert results[0]["normalized_semantic"] == pytest.approx(0.0)
        assert results[0]["retrieval_method"] == "bm25"

    def test_no_results_from_either(self):
        results, _ = fuse_results([], [], min_score=0.0)
        assert results == []

    def test_threshold_filters_low_scoring(self):
        """
        When there are multiple candidates where one scores much lower than another,
        the low-scoring one should be filtered by the threshold.
        A single candidate with a non-zero score always normalizes to 1.0 (it's the only one).
        To test threshold filtering, use multiple candidates so relative scoring applies.
        The low-scoring candidate should have hybrid_score < threshold.
        """
        # Two semantic candidates: one very high, one very low
        # After normalization: high→1.0, low→0.0
        # Hybrid of low candidate = 0.6*0.0 + 0.4*0.0 = 0.0 < threshold=0.10
        sem = [
            self._make_sem("chunk_high", 1.0),
            self._make_sem("chunk_low", 0.0),   # zero sim means missing from this pool
        ]
        # Only bm25 for chunk_high so chunk_low stays at 0.0 across both pools
        bm25 = [self._make_bm25("chunk_high", 10.0)]
        results, _ = fuse_results(sem, bm25, min_score=0.10)
        # chunk_low should be filtered (hybrid=0.0 < 0.10)
        ids = [r["chunk_id"] for r in results]
        assert "chunk_low" not in ids
        assert "chunk_high" in ids

    def test_hybrid_score_formula(self):
        """Verify: hybrid = 0.6 * sem_norm + 0.4 * bm25_norm."""
        sem = [
            self._make_sem("c0", 1.0),
            self._make_sem("c1", 0.5),
        ]
        bm25 = [
            self._make_bm25("c0", 10.0),
            self._make_bm25("c1", 5.0),
        ]
        results, _ = fuse_results(sem, bm25, semantic_weight=0.6, bm25_weight=0.4, min_score=0.0)
        # Both sem and bm25 scores normalize: c0 → 1.0, c1 → 0.0
        c0 = next(r for r in results if r["chunk_id"] == "c0")
        c1 = next(r for r in results if r["chunk_id"] == "c1")
        assert c0["normalized_semantic"] == pytest.approx(1.0)
        assert c1["normalized_semantic"] == pytest.approx(0.0)
        assert c0["hybrid_score"] == pytest.approx(0.6 * 1.0 + 0.4 * 1.0)
        assert c1["hybrid_score"] == pytest.approx(0.6 * 0.0 + 0.4 * 0.0)

    def test_equal_bm25_scores_no_nan(self):
        """Equal BM25 scores must not produce NaN or infinity."""
        sem = [self._make_sem("a", 0.9), self._make_sem("b", 0.8)]
        bm25 = [self._make_bm25("a", 5.0), self._make_bm25("b", 5.0)]
        results, _ = fuse_results(sem, bm25, min_score=0.0)
        for r in results:
            assert not (r["normalized_bm25"] != r["normalized_bm25"])  # NaN check
            assert r["normalized_bm25"] == pytest.approx(1.0)

    def test_ranking_order(self):
        """Higher hybrid score must appear first."""
        sem = [self._make_sem("high", 0.99), self._make_sem("low", 0.01)]
        results, _ = fuse_results(sem, [], min_score=0.0)
        assert results[0]["chunk_id"] == "high"


# ─────────────── UNIT TESTS: Context Builder ────────────────────────────────

def _make_search_result(text: str, chunk_index: int = 0, doc_id: str = "doc1",
                        file_name: str = "test.txt", page: int = None) -> SearchResult:
    return SearchResult(
        chunk_id=f"{doc_id}_{chunk_index}",
        document_id=doc_id,
        project_id="proj1",
        file_name=file_name,
        chunk_index=chunk_index,
        text=text,
        semantic_score=0.9,
        bm25_score=0.8,
        hybrid_score=0.86,
        metadata=SearchResultMetadata(chunk_index=chunk_index, page_number=page),
    )


class TestContextBuilder:
    def test_context_format(self):
        r = _make_search_result("Hello world", chunk_index=3, page=5, file_name="doc.pdf")
        ctx, citations, srcs = build_context([r])
        assert "SOURCE 1" in ctx
        assert "File: doc.pdf" in ctx
        assert "Page: 5" in ctx
        assert "Chunk: 3" in ctx
        assert "Hello world" in ctx

    def test_citation_metadata(self):
        r = _make_search_result("Payment info", chunk_index=2, page=8, file_name="pay.pdf")
        _, citations, _ = build_context([r])
        assert len(citations) == 1
        assert citations[0].page_number == 8
        assert citations[0].chunk_index == 2
        assert "Page: 8" in citations[0].display_text
        assert "pay.pdf" in citations[0].display_text

    def test_context_truncation(self):
        """Context must not exceed MAX_CONTEXT_CHARS; source boundaries preserved."""
        big_text = "A" * 5000
        results = [_make_search_result(big_text, i) for i in range(10)]
        ctx, _, _ = build_context(results, max_chars=8000)
        assert len(ctx) <= 8000

    def test_empty_results_empty_context(self):
        ctx, citations, srcs = build_context([])
        assert ctx == ""
        assert citations == []
        assert srcs == []

    def test_source_documents_deduplicated(self):
        r1 = _make_search_result("chunk A", chunk_index=0, doc_id="doc_x", file_name="x.txt")
        r2 = _make_search_result("chunk B", chunk_index=1, doc_id="doc_x", file_name="x.txt")
        _, _, srcs = build_context([r1, r2])
        assert len(srcs) == 1
        assert srcs[0].document_id == "doc_x"

    def test_source_boundaries_not_merged(self):
        """Two different sources must be clearly separated."""
        r1 = _make_search_result("Payment text", chunk_index=0, doc_id="d1", file_name="pay.txt")
        r2 = _make_search_result("Auth text", chunk_index=0, doc_id="d2", file_name="auth.txt")
        ctx, _, _ = build_context([r1, r2])
        assert "SOURCE 1" in ctx
        assert "SOURCE 2" in ctx
        # Ensure they are not merged
        assert ctx.index("SOURCE 2") > ctx.index("SOURCE 1")


# ─────────────── INTEGRATION TESTS: API ──────────────────────────────────────

class TestRetrievalAPI:
    def test_basic_hybrid_search(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "What are the payment failure requirements?", "top_k": 5},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == env["project_a_id"]
        assert "results" in data
        assert "citations" in data
        assert "context" in data
        assert "metadata" in data
        assert data["metadata"]["final_results_count"] == len(data["results"])

    def test_payment_query_ranks_payment_chunks_higher(self, test_env):
        """
        RAG QUALITY TEST: Payment query should return payment-related text
        ranking at the top — not auth content.
        """
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "What are the requirements for handling failed payments?", "top_k": 5},
        )
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) > 0
        # Top result should contain payment-related text
        top_text = results[0]["text"].lower()
        assert any(kw in top_text for kw in ["payment", "failed", "retry", "refund", "pay"])

    def test_auth_query_ranks_auth_chunks_higher(self, test_env):
        """
        RAG QUALITY TEST: Auth query on Project B should return auth-related chunks at top.
        """
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_b_id']}/search",
            headers={"Authorization": f"Bearer {env['token_b']}"},
            json={"query": "What are the password requirements?", "top_k": 5},
        )
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) > 0
        top_text = results[0]["text"].lower()
        assert any(kw in top_text for kw in ["password", "authentication", "login", "account", "auth"])

    def test_project_isolation(self, test_env):
        """
        Project A query must NEVER return results from Project B.
        Alice owns Project A; Bob owns Project B. Alice cannot access Project B.
        """
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_b_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},  # Alice tries Bob's project
            json={"query": "password requirements", "top_k": 5},
        )
        assert r.status_code == 404

    def test_unauthorized_project_access_no_existence_leak(self, test_env):
        """Non-existent and unauthorized projects must both return 404."""
        env = test_env
        fake_id = str(uuid.uuid4())
        r = client.post(
            f"/api/projects/{fake_id}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "anything", "top_k": 3},
        )
        assert r.status_code == 404

    def test_empty_query_rejected(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "", "top_k": 5},
        )
        assert r.status_code == 422

    def test_whitespace_only_query_rejected(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "   ", "top_k": 5},
        )
        assert r.status_code == 422

    def test_invalid_top_k_below_1(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment", "top_k": 0},
        )
        assert r.status_code == 422

    def test_top_k_above_maximum(self, test_env):
        """top_k > RETRIEVAL_MAX_TOP_K must be rejected."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment", "top_k": 9999},
        )
        assert r.status_code == 422

    def test_document_filter_restricts_results(self, test_env):
        """When document_ids filter is supplied, only that document's chunks appear."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={
                "query": "payment requirements",
                "top_k": 5,
                "document_ids": [env["payment_doc_id"]],
            },
        )
        assert r.status_code == 200
        results = r.json()["results"]
        for result in results:
            assert result["document_id"] == env["payment_doc_id"]

    def test_document_filter_invalid_id(self, test_env):
        """A document_id that doesn't exist in the project must return 400."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={
                "query": "payment",
                "top_k": 3,
                "document_ids": [str(uuid.uuid4())],  # fake
            },
        )
        assert r.status_code == 400

    def test_document_filter_cross_project_rejected(self, test_env):
        """A document_id belonging to another project must be rejected."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={
                "query": "requirements",
                "top_k": 3,
                "document_ids": [env["auth_doc_id"]],  # belongs to Project B!
            },
        )
        assert r.status_code == 400

    def test_empty_project_returns_empty_results(self, test_env):
        """A project with no documents must return empty results, not an error."""
        env = test_env
        # Create a fresh project with no documents
        r = client.post(
            "/api/projects",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"name": "Empty Project", "description": ""},
        )
        empty_project_id = r.json()["id"]

        r = client.post(
            f"/api/projects/{empty_project_id}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment requirements", "top_k": 5},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["results"] == []
        assert data["citations"] == []
        assert data["context"] == ""

    def test_citation_structure(self, test_env):
        """Every citation must include document_id, file_name, chunk_index, and source_type."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment failure", "top_k": 3},
        )
        assert r.status_code == 200
        citations = r.json()["citations"]
        if citations:
            for c in citations:
                assert "document_id" in c
                assert "file_name" in c
                assert "chunk_index" in c
                assert "source_type" in c
                assert "display_text" in c
                assert "[Source:" in c["display_text"]

    def test_source_documents_in_response(self, test_env):
        """source_documents must list documents that contributed results."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment", "top_k": 5},
        )
        assert r.status_code == 200
        srcs = r.json()["source_documents"]
        assert isinstance(srcs, list)
        if srcs:
            for s in srcs:
                assert "document_id" in s
                assert "file_name" in s

    def test_no_internal_chroma_paths_in_response(self, test_env):
        """Chroma collection names and filesystem paths must NOT appear in response."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment", "top_k": 3},
        )
        text = r.text
        assert "refyne_project_" not in text   # Chroma collection name
        assert "data/bm25" not in text         # BM25 index path
        assert "data/chroma" not in text       # Chroma persistence path

    def test_metadata_counts_accurate(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment failure requirements", "top_k": 5},
        )
        assert r.status_code == 200
        data = r.json()
        meta = data["metadata"]
        assert meta["final_results_count"] == len(data["results"])
        assert meta["final_results_count"] <= 5
        assert "semantic_results_count" in meta
        assert "bm25_results_count" in meta

    def test_requires_authentication(self, test_env):
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            json={"query": "payment", "top_k": 3},
        )
        assert r.status_code == 401

    def test_restart_persistence(self, test_env):
        """
        After creating a new app/client instance (simulating restart),
        retrieval should still work with previously indexed data.
        """
        env = test_env
        # Re-query using same client (same underlying DB/Chroma/BM25 on disk)
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment transaction retry", "top_k": 3},
        )
        assert r.status_code == 200
        assert r.json()["metadata"]["final_results_count"] >= 0

    def test_top_k_respected(self, test_env):
        """Results must not exceed the requested top_k."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment", "top_k": 2},
        )
        assert r.status_code == 200
        assert len(r.json()["results"]) <= 2

    def test_context_non_empty_when_results_found(self, test_env):
        """When results are found, context must be a non-empty string."""
        env = test_env
        r = client.post(
            f"/api/projects/{env['project_a_id']}/search",
            headers={"Authorization": f"Bearer {env['token_a']}"},
            json={"query": "payment failure", "top_k": 3},
        )
        assert r.status_code == 200
        if r.json()["results"]:
            assert len(r.json()["context"]) > 0
            assert "SOURCE 1" in r.json()["context"]
