import abc
import os

REQUIRED_CHUNK_METADATA = {"project_id", "document_id", "chunk_index", "owner_id", "allowed_roles"}


def validate_chunk_metadata(chunk: dict) -> None:
    """Validate that a chunk has required authorization metadata."""
    meta = chunk.get("metadata", {})
    missing = REQUIRED_CHUNK_METADATA - set(meta.keys())
    if missing:
        raise ValueError(f"Chunk missing required metadata fields: {missing}")
    if not isinstance(meta["allowed_roles"], list) or not meta["allowed_roles"]:
        raise ValueError("Chunk metadata 'allowed_roles' must be a non-empty list")


class VectorStore(abc.ABC):
    """Abstract interface for vector storage."""

    @abc.abstractmethod
    def upsert_chunks(self, project_id: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """Upsert chunks with their embeddings. Chunks must include authorization metadata."""

    @abc.abstractmethod
    def query(self, project_id: str, embedding: list[float], top_k: int = 8, filters: dict | None = None) -> list[dict]:
        """Query for similar chunks. Returns list of dicts with 'text', 'metadata', 'score'."""

    @abc.abstractmethod
    def delete_document_chunks(self, project_id: str, document_id: str) -> None:
        """Delete all chunks for a document."""

    @abc.abstractmethod
    def delete_project(self, project_id: str) -> None:
        """Delete all chunks for a project."""


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store implementation."""

    def __init__(self):
        import chromadb
        chroma_dir = os.path.join(os.getcwd(), "data", "chroma")
        os.makedirs(chroma_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=chroma_dir)

    def _get_collection_name(self, project_id: str) -> str:
        return f"refyne_project_{project_id.replace('-', '_')}"

    def _get_collection(self, project_id: str):
        return self._client.get_or_create_collection(name=self._get_collection_name(project_id))

    def upsert_chunks(self, project_id: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
        collection = self._get_collection(project_id)

        ids = []
        texts = []
        metadatas = []

        for chunk in chunks:
            validate_chunk_metadata(chunk)
            doc_id = chunk["metadata"]["document_id"]
            chunk_idx = chunk["metadata"]["chunk_index"]
            chunk_id = f"{doc_id}_{chunk_idx}"

            ids.append(chunk_id)
            texts.append(chunk["text"])

            clean_meta = {}
            for k, v in chunk["metadata"].items():
                if v is not None:
                    clean_meta[k] = v
            metadatas.append(clean_meta)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def query(self, project_id: str, embedding: list[float], top_k: int = 8, filters: dict | None = None) -> list[dict]:
        collection = self._get_collection(project_id)

        where = None
        if filters:
            where = filters if len(filters) > 1 else filters

        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where
        )

        output = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                output.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1.0 - results["distances"][0][i] if results["distances"] else 0.0,
                })
        return output

    def delete_document_chunks(self, project_id: str, document_id: str) -> None:
        try:
            collection = self._get_collection(project_id)
            collection.delete(where={"document_id": document_id})
        except Exception:
            pass

    def delete_project(self, project_id: str) -> None:
        try:
            self._client.delete_collection(self._get_collection_name(project_id))
        except Exception:
            pass


class PgVectorStore(VectorStore):
    """PostgreSQL pgvector implementation."""

    def __init__(self, database_url: str, dimension: int = 384):
        from sqlalchemy import create_engine

        self.dimension = dimension
        self.engine = create_engine(database_url)
        self._ensure_table()

    def _ensure_table(self):
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS vector_chunks (
                    id VARCHAR(100) PRIMARY KEY,
                    project_id VARCHAR(36) NOT NULL,
                    document_id VARCHAR(36) NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json JSONB,
                    embedding vector({self.dimension})
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vector_chunks_project ON vector_chunks(project_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vector_chunks_doc ON vector_chunks(document_id)"))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_vector_chunks_embedding
                ON vector_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
            """))
            conn.commit()

    def upsert_chunks(self, project_id: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
        import json

        from sqlalchemy import text

        with self.engine.connect() as conn:
            for chunk, embedding in zip(chunks, embeddings):
                validate_chunk_metadata(chunk)
                doc_id = chunk["metadata"]["document_id"]
                chunk_idx = chunk["metadata"]["chunk_index"]
                chunk_id = f"{doc_id}_{chunk_idx}"

                conn.execute(text("""
                    INSERT INTO vector_chunks (id, project_id, document_id, chunk_index, text, metadata_json, embedding)
                    VALUES (:id, :project_id, :document_id, :chunk_index, :text, :metadata, :embedding)
                    ON CONFLICT (id) DO UPDATE SET
                        text = EXCLUDED.text,
                        metadata_json = EXCLUDED.metadata_json,
                        embedding = EXCLUDED.embedding
                """), {
                    "id": chunk_id,
                    "project_id": project_id,
                    "document_id": doc_id,
                    "chunk_index": chunk_idx,
                    "text": chunk["text"],
                    "metadata": json.dumps(chunk["metadata"]),
                    "embedding": str(embedding),
                })
            conn.commit()

    def query(self, project_id: str, embedding: list[float], top_k: int = 8, filters: dict | None = None) -> list[dict]:
        import json

        from sqlalchemy import text

        with self.engine.connect() as conn:
            where_clause = "WHERE project_id = :project_id"
            params = {"project_id": project_id, "embedding": str(embedding), "top_k": top_k}

            if filters:
                if "document_id" in filters:
                    where_clause += " AND document_id = :document_id"
                    params["document_id"] = filters["document_id"]

            result = conn.execute(text(f"""
                SELECT id, text, metadata_json, 1 - (embedding <=> :embedding::vector) as score
                FROM vector_chunks
                {where_clause}
                ORDER BY embedding <=> :embedding::vector
                LIMIT :top_k
            """), params)

            output = []
            for row in result:
                output.append({
                    "text": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                    "score": float(row[3]),
                })
            return output

    def delete_document_chunks(self, project_id: str, document_id: str) -> None:
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("DELETE FROM vector_chunks WHERE project_id = :project_id AND document_id = :document_id"),
                         {"project_id": project_id, "document_id": document_id})
            conn.commit()

    def delete_project(self, project_id: str) -> None:
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("DELETE FROM vector_chunks WHERE project_id = :project_id"),
                         {"project_id": project_id})
            conn.commit()


_store_instance: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get the configured vector store instance."""
    global _store_instance
    if _store_instance is None:
        backend = os.environ.get("VECTOR_STORE_BACKEND", "chroma")
        if backend == "pgvector":
            database_url = os.environ.get("DATABASE_URL", "postgresql://refyne:refyne_dev_password@localhost:5432/refyne")
            dimension = int(os.environ.get("EMBEDDING_DIMENSION", "384"))
            _store_instance = PgVectorStore(database_url=database_url, dimension=dimension)
        else:
            _store_instance = ChromaVectorStore()
    return _store_instance
