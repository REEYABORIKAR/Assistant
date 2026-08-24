import json
import logging
import os
import tempfile

from sqlalchemy.orm import Session

from app.core.roles import ProjectRole
from app.models.document import Document, DocumentChunk
from app.models.membership import ProjectMember
from app.rag.bm25.index import BM25Index
from app.rag.chunking.splitter import chunk_document
from app.rag.embeddings.model import get_embedding_model
from app.rag.extraction.parsers import ExtractionError, extract_document
from app.rag.vector_store import get_vector_store
from app.storage.object_store import get_object_store

logger = logging.getLogger(__name__)


def _get_project_allowed_roles(db: Session, project_id: str) -> list[str]:
    """Get all roles present in a project's membership."""
    members = db.query(ProjectMember.role).filter(
        ProjectMember.project_id == project_id
    ).distinct().all()
    return [m[0] for m in members]


class DocumentAgent:
    def __init__(self, db: Session):
        self.db = db

    def process_document(self, document: Document):
        """
        Synchronously processes a document through the entire pipeline.
        Must only be called after document is saved with status 'processing'.
        """
        try:
            # 1. Download from object storage to temp file
            store = get_object_store()
            file_data = store.download(document.storage_key)

            _, ext = document.file_name.rsplit(".", 1) if "." in document.file_name else ("", "")
            ext = f".{ext.lower()}"

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name

            try:
                extracted_data = extract_document(tmp_path, ext)
            finally:
                os.unlink(tmp_path)

            # 2. Chunking
            chunks = chunk_document(
                extracted_data,
                document_id=document.id,
                project_id=document.project_id,
                file_name=document.file_name
            )

            if not chunks:
                raise Exception("No content could be extracted or chunked from the document.")

            # 3. Add authorization metadata to each chunk
            allowed_roles = _get_project_allowed_roles(self.db, document.project_id)
            if not allowed_roles:
                allowed_roles = [r.value for r in ProjectRole]

            roles_str = ",".join(allowed_roles) if isinstance(allowed_roles, list) else str(allowed_roles)
            for chunk in chunks:
                chunk["metadata"]["owner_id"] = document.user_id
                chunk["metadata"]["allowed_roles"] = roles_str
                chunk["metadata"]["classification"] = "internal"

            # Save chunks to DB
            db_chunks = []
            for chunk in chunks:
                meta = chunk["metadata"]
                db_chunk = DocumentChunk(
                    document_id=document.id,
                    project_id=document.project_id,
                    chunk_index=meta["chunk_index"],
                    text=chunk["text"],
                    page_number=meta.get("page_number"),
                    sheet_name=meta.get("sheet_name"),
                    metadata_json=json.dumps(meta)
                )
                self.db.add(db_chunk)
                db_chunks.append(db_chunk)
            self.db.commit()

            # 4. Embeddings
            model = get_embedding_model()
            texts = [chunk["text"] for chunk in chunks]
            embeddings = model.embed_texts(texts)

            # 5. Vector Store
            vector_store = get_vector_store()
            vector_store.upsert_chunks(
                project_id=document.project_id,
                chunks=chunks,
                embeddings=embeddings
            )

            # 6. BM25
            bm25 = BM25Index(project_id=document.project_id)
            bm25.add_chunks(chunks)

            # 7. Update Status
            document.status = "indexed"
            self.db.commit()

        except ExtractionError as e:
            logger.error(f"Extraction error for document {document.id}: {str(e)}")
            self.db.rollback()
            document.status = "failed"
            document.error_message = str(e)
            self.db.commit()

        except Exception as e:
            logger.exception(f"General processing error for document {document.id}: {str(e)}")
            self.db.rollback()
            document.status = "failed"
            document.error_message = f"An unexpected error occurred: {str(e)}"
            self.db.commit()

    def reindex_document(self, document: Document):
        """
        Removes existing data from vector store and BM25, and chunks from DB, then re-processes.
        """
        # Cleanup DB Chunks
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        self.db.commit()

        # Cleanup Vector Store
        vector_store = get_vector_store()
        vector_store.delete_document_chunks(document.project_id, document.id)

        # Cleanup BM25
        bm25 = BM25Index(project_id=document.project_id)
        bm25.remove_document(document.id)

        # Reprocess
        document.status = "processing"
        document.error_message = None
        self.db.commit()

        self.process_document(document)

    def delete_document(self, document: Document):
        """
        Fully deletes document from object storage, DB, vector store, and BM25.
        """
        # 1. Vector Store
        vector_store = get_vector_store()
        vector_store.delete_document_chunks(document.project_id, document.id)

        # 2. BM25
        bm25 = BM25Index(project_id=document.project_id)
        bm25.remove_document(document.id)

        # 3. Object storage
        try:
            store = get_object_store()
            if document.storage_key:
                store.delete(document.storage_key)
        except Exception:
            pass

        # 4. DB
        self.db.delete(document)
        self.db.commit()
