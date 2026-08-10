import json
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentChunk
from app.rag.extraction.parsers import extract_document, ExtractionError
from app.rag.chunking.splitter import chunk_document
from app.rag.embeddings.model import get_embedding_model
from app.rag.chroma.store import get_chroma_store
from app.rag.bm25.index import BM25Index
import logging

logger = logging.getLogger(__name__)

class DocumentAgent:
    def __init__(self, db: Session):
        self.db = db

    def process_document(self, document: Document):
        """
        Synchronously processes a document through the entire pipeline.
        Must only be called after document is saved with status 'processing'.
        """
        try:
            # 1. Extraction
            _, ext = document.file_name.rsplit(".", 1) if "." in document.file_name else ("", "")
            ext = f".{ext.lower()}"
            extracted_data = extract_document(document.file_path, ext)
            
            # 2. Chunking
            chunks = chunk_document(
                extracted_data, 
                document_id=document.id, 
                project_id=document.project_id, 
                file_name=document.file_name
            )
            
            if not chunks:
                raise Exception("No content could be extracted or chunked from the document.")

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

            # 3. Embeddings
            model = get_embedding_model()
            texts = [chunk["text"] for chunk in chunks]
            embeddings = model.embed_texts(texts)

            # 4. ChromaDB
            chroma_store = get_chroma_store()
            chroma_store.upsert_chunks(
                project_id=document.project_id, 
                chunks=chunks, 
                embeddings=embeddings
            )

            # 5. BM25
            bm25 = BM25Index(project_id=document.project_id)
            bm25.add_chunks(chunks)

            # 6. Update Status
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
        Removes existing data from Chroma and BM25, and chunks from DB, then re-processes.
        """
        # Cleanup DB Chunks
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
        self.db.commit()
        
        # Cleanup Chroma
        chroma_store = get_chroma_store()
        chroma_store.delete_document_chunks(document.project_id, document.id)
        
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
        Fully deletes document from DB, disk, Chroma, and BM25.
        """
        # 1. ChromaDB
        chroma_store = get_chroma_store()
        chroma_store.delete_document_chunks(document.project_id, document.id)
        
        # 2. BM25
        bm25 = BM25Index(project_id=document.project_id)
        bm25.remove_document(document.id)
        
        # 3. Disk
        try:
            import os
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception:
            pass # Ignore filesystem errors on delete
            
        # 4. DB
        self.db.delete(document)
        self.db.commit()
