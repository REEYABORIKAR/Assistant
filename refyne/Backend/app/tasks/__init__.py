import os
import sys

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.document.agent import DocumentAgent
from app.celery_app import celery_app
from app.core.config import settings
from app.models.document import Document, DocumentChunk

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@celery_app.task(bind=True, name="ingest_document")
def ingest_document(self, document_id: str):
    """
    Celery task to asynchronously ingest a document through the pipeline.
    Updates status at each stage: EXTRACTING -> CHUNKING -> EMBEDDING -> INDEXING -> COMPLETED
    On failure: FAILED with error message.
    """
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": f"Document {document_id} not found"}

        # Stage 1: Extracting
        document.status = "extracting"
        db.commit()

        # Stage 2-5: Process through the agent
        agent = DocumentAgent(db)

        # The agent handles chunking, embedding, and indexing internally
        # We just need to update status before and let the agent handle the rest
        document.status = "processing"
        db.commit()

        agent.process_document(document)

        return {
            "document_id": document_id,
            "status": document.status,
            "error_message": document.error_message,
        }

    except Exception as e:
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                document.error_message = str(e)
                db.commit()
        except Exception:
            pass
        return {"error": str(e), "document_id": document_id}
    finally:
        db.close()
