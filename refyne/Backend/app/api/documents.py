import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents.document.agent import DocumentAgent
from app.agents.document.storage import validate_and_store_file
from app.api.deps import CurrentUser, SessionDep, require_role
from app.core.audit import write_audit_log
from app.core.roles import ProjectRole
from app.models.document import Document
from app.models.membership import ProjectMember
from app.models.project import Project
from app.schemas.document import DocumentResponse, DocumentStatus
from app.storage.object_store import get_object_store

logger = logging.getLogger(__name__)

# Celery is optional — if Redis isn't running, ingest synchronously
_celery_available = False
try:
    from app.tasks import ingest_document
    _celery_available = True
except Exception:
    pass

router = APIRouter(tags=["documents"])


def _verify_project_access(db: Session, project_id: str, user_id: str) -> tuple[Project, ProjectRole | None]:
    """
    Verify user has access to project. Returns (project, role).
    Owner gets ADMIN role. None role means owner (always has full access).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.user_id == user_id:
        return project, ProjectRole.ADMIN

    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Project not found")

    return project, ProjectRole(member.role)


def _verify_document_access(db: Session, document_id: str, user_id: str) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    _verify_project_access(db, document.project_id, user_id)
    return document


@router.post("/api/projects/{project_id}/documents/upload", response_model=DocumentResponse)
async def upload_document(
    project_id: str,
    db: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    _role: None = Depends(require_role(ProjectRole.EDITOR)),
):
    project, _ = _verify_project_access(db, project_id, current_user.id)

    try:
        storage_key, mime_type, file_size, checksum, _ = validate_and_store_file(file, current_user.id, project_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File validation failed: {str(e)}")

    existing = db.query(Document).filter(
        Document.project_id == project_id,
        Document.checksum == checksum
    ).first()

    if existing:
        if existing.status == "failed":
            db.delete(existing)
            db.commit()
        else:
            store = get_object_store()
            store.delete(storage_key)
            raise HTTPException(status_code=409, detail="Duplicate document content detected in this project.")

    document = Document(
        project_id=project_id,
        workspace_id=project.workspace.id,
        user_id=current_user.id,
        file_name=file.filename,
        file_type=mime_type,
        file_size=file_size,
        file_path=storage_key,
        storage_key=storage_key,
        checksum=checksum,
        status="processing"
    )
    db.add(document)
    db.flush()

    write_audit_log(
        db,
        user_id=current_user.id,
        project_id=project_id,
        action="UPLOAD_DOCUMENT",
        resource_type="document",
        resource_id=document.id,
        details={"file_name": file.filename, "file_size": file_size, "file_type": mime_type},
    )
    db.commit()
    db.refresh(document)

    # Process document processing synchronously to ensure instant indexing without external worker dependency
    logger.info(f"Processing document {document.id} ({file.filename}) synchronously")
    try:
        agent = DocumentAgent(db)
        agent.process_document(document)
        db.refresh(document)
    except Exception as err:
        logger.error(f"Synchronous document processing failed: {err}")
        document.status = "failed"
        document.error_message = str(err)
        db.commit()
        db.refresh(document)

    return document


@router.get("/api/projects/{project_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    project_id: str,
    db: SessionDep,
    current_user: CurrentUser,
):
    _verify_project_access(db, project_id, current_user.id)
    return db.query(Document).filter(Document.project_id == project_id).all()


@router.get("/api/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: SessionDep,
    current_user: CurrentUser,
):
    return _verify_document_access(db, document_id, current_user.id)


@router.delete("/api/documents/{document_id}")
def delete_document(
    document_id: str,
    db: SessionDep,
    current_user: CurrentUser,
):
    document = _verify_document_access(db, document_id, current_user.id)

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
    db: SessionDep,
    current_user: CurrentUser,
):
    document = _verify_document_access(db, document_id, current_user.id)
    return document


@router.post("/api/documents/{document_id}/reindex", response_model=DocumentResponse)
def reindex_document(
    document_id: str,
    db: SessionDep,
    current_user: CurrentUser,
    _role: None = Depends(require_role(ProjectRole.EDITOR)),
):
    document = _verify_document_access(db, document_id, current_user.id)

    agent = DocumentAgent(db)
    agent.reindex_document(document)

    return document
