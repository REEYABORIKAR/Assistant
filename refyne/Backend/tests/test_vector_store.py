import os
import tempfile

import pytest

from app.rag.vector_store import ChromaVectorStore, VectorStore


@pytest.fixture
def chroma_store():
    """Create a temporary ChromaDB store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        store = ChromaVectorStore()
        yield store
        os.chdir(os.path.dirname(os.path.dirname(__file__)))


def test_upsert_and_query(chroma_store: VectorStore):
    """Test upserting chunks and querying them."""
    project_id = "test-project-123"
    chunks = [
        {
            "text": "This is a test document about Python programming.",
            "metadata": {"document_id": "doc1", "chunk_index": 0, "topic": "python"}
        },
        {
            "text": "This is about JavaScript development.",
            "metadata": {"document_id": "doc1", "chunk_index": 1, "topic": "javascript"}
        },
    ]
    # Simple embeddings for testing (384 dimensions)
    embeddings = [
        [0.1] * 384,
        [0.2] * 384,
    ]

    chroma_store.upsert_chunks(project_id, chunks, embeddings)

    # Query with similar embedding
    results = chroma_store.query(project_id, embeddings[0], top_k=2)
    assert len(results) > 0
    assert results[0]["text"] == "This is a test document about Python programming."


def test_delete_document_chunks(chroma_store: VectorStore):
    """Test deleting chunks for a specific document."""
    project_id = "test-project-delete"
    chunks = [
        {
            "text": "Document 1 content",
            "metadata": {"document_id": "doc1", "chunk_index": 0}
        },
        {
            "text": "Document 2 content",
            "metadata": {"document_id": "doc2", "chunk_index": 0}
        },
    ]
    embeddings = [[0.1] * 384, [0.2] * 384]

    chroma_store.upsert_chunks(project_id, chunks, embeddings)

    # Delete only doc1
    chroma_store.delete_document_chunks(project_id, "doc1")

    # Query should return only doc2
    results = chroma_store.query(project_id, embeddings[1], top_k=10)
    assert len(results) == 1
    assert results[0]["metadata"]["document_id"] == "doc2"


def test_delete_project(chroma_store: VectorStore):
    """Test deleting all chunks for a project."""
    project_id = "test-project-full-delete"
    chunks = [
        {
            "text": "Some content",
            "metadata": {"document_id": "doc1", "chunk_index": 0}
        },
    ]
    embeddings = [[0.1] * 384]

    chroma_store.upsert_chunks(project_id, chunks, embeddings)

    # Delete entire project
    chroma_store.delete_project(project_id)

    # Query should return empty
    results = chroma_store.query(project_id, embeddings[0], top_k=10)
    assert len(results) == 0
