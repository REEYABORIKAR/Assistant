from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.project import Project, Workspace
from app.models.document import Document
from app.schemas.document import DocumentResponse, DocumentStatus
from app.agents.document.storage import validate_and_store_file
from app.agents.document.agent import DocumentAgent
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

def get_project_and_verify_access(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

def get_document_and_verify_access(db: Session, document_id: str, user_id: str) -> Document:
    document = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.post("/api/projects/{project_id}/documents/upload", response_model=DocumentResponse)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = get_project_and_verify_access(db, project_id, current_user.id)
    
    # Store and validate file
    try:
        file_path, mime_type, file_size, checksum = validate_and_store_file(file, current_user.id, project_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File validation failed: {str(e)}")
        
    # Check for duplicate checksum in this project
    existing = db.query(Document).filter(
        Document.project_id == project_id,
        Document.checksum == checksum
    ).first()
    
    if existing:
        import os
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=409, detail="Duplicate document content detected in this project.")
        
    document = Document(
        project_id=project_id,
        workspace_id=project.workspace.id,
        user_id=current_user.id,
        file_name=file.filename,
        file_type=mime_type,
        file_size=file_size,
        file_path=file_path,
        checksum=checksum,
        status="processing"
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Process document synchronously (could be moved to background task later)
    agent = DocumentAgent(db)
    agent.process_document(document)
    
    return document

@router.get("/api/projects/{project_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    get_project_and_verify_access(db, project_id, current_user.id)
    return db.query(Document).filter(Document.project_id == project_id).all()

@router.get("/api/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_document_and_verify_access(db, document_id, current_user.id)

@router.delete("/api/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = get_document_and_verify_access(db, document_id, current_user.id)
    
    try:
        agent = DocumentAgent(db)
        agent.delete_document(document)
    except Exception as e:
        logger.error(f"Failed to delete document fully: {str(e)}")
        raise HTTPException(status_code=500, detail="Cleanup required before deletion failed")
        
    return {"status": "success", "message": "Document and all associated data deleted"}

@router.get("/api/documents/{document_id}/status", response_model=DocumentStatus)
def get_document_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = get_document_and_verify_access(db, document_id, current_user.id)
    return document

@router.post("/api/documents/{document_id}/reindex", response_model=DocumentResponse)
def reindex_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = get_document_and_verify_access(db, document_id, current_user.id)
    
    agent = DocumentAgent(db)
    agent.reindex_document(document)
    
    return document
