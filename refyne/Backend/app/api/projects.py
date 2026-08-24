
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, require_role
from app.core.roles import ProjectRole
from app.models.membership import ProjectMember
from app.models.project import Project, Workspace
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, WorkspaceResponse

router = APIRouter(prefix="/api/projects", tags=["Projects"])

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project_in: ProjectCreate, db: SessionDep, current_user: CurrentUser):
    try:
        new_project = Project(
            name=project_in.name,
            description=project_in.description,
            user_id=current_user.id
        )
        db.add(new_project)
        db.flush()

        workspace_name = f"{new_project.name} Workspace"
        new_workspace = Workspace(
            name=workspace_name,
            project_id=new_project.id
        )
        db.add(new_workspace)
        db.commit()
        db.refresh(new_project)
        return new_project
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project and workspace"
        )

@router.get("", response_model=list[ProjectResponse])
def list_projects(db: SessionDep, current_user: CurrentUser, search: str | None = None):
    owned = db.query(Project).filter(Project.user_id == current_user.id)
    member_ids = db.query(ProjectMember.project_id).filter(
        ProjectMember.user_id == current_user.id
    ).subquery()
    member_of = db.query(Project).filter(Project.id.in_(member_ids))
    query = owned.union(member_of)
    if search:
        search_filter = f"%{search}%"
        query = query.filter((Project.name.ilike(search_filter)) | (Project.description.ilike(search_filter)))
    return query.all()

def get_project_or_404(db: Session, project_id: str, user_id: str) -> Project:
    """Verify project access (owner or member)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.user_id == user_id:
        return project
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: SessionDep, current_user: CurrentUser):
    return get_project_or_404(db, project_id, current_user.id)

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, project_in: ProjectUpdate, db: SessionDep, current_user: CurrentUser):
    project = get_project_or_404(db, project_id, current_user.id)

    if project_in.name is not None:
        project.name = project_in.name
    if project_in.description is not None:
        project.description = project_in.description

    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_project(
    project_id: str,
    db: SessionDep,
    current_user: CurrentUser,
    _role: None = Depends(require_role(ProjectRole.ADMIN)),
):
    project = get_project_or_404(db, project_id, current_user.id)
    db.delete(project)
    db.commit()
    return None

@router.post("/{project_id}/duplicate", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def duplicate_project(project_id: str, db: SessionDep, current_user: CurrentUser):
    project = get_project_or_404(db, project_id, current_user.id)

    try:
        new_project = Project(
            name=f"{project.name} (Copy)",
            description=project.description,
            user_id=current_user.id
        )
        db.add(new_project)
        db.flush()

        new_workspace = Workspace(
            name=f"{new_project.name} Workspace",
            project_id=new_project.id
        )
        db.add(new_workspace)
        db.commit()
        db.refresh(new_project)
        return new_project
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to duplicate project"
        )

@router.get("/{project_id}/workspace", response_model=WorkspaceResponse)
def get_project_workspace(project_id: str, db: SessionDep, current_user: CurrentUser):
    project = get_project_or_404(db, project_id, current_user.id)
    if not project.workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return project.workspace
