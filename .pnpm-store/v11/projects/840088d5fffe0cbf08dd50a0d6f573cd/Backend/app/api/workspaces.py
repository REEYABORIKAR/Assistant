from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import SessionDep, CurrentUser
from app.models.project import Project, Workspace
from app.schemas.project import WorkspaceUpdate, WorkspaceResponse

router = APIRouter(prefix="/api/workspaces", tags=["Workspaces"])

@router.put("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(workspace_id: str, workspace_in: WorkspaceUpdate, db: SessionDep, current_user: CurrentUser):
    # Verify workspace -> project -> current_user
    workspace = db.query(Workspace).join(Project).filter(
        Workspace.id == workspace_id,
        Project.user_id == current_user.id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or not authorized"
        )
        
    if workspace_in.name is not None:
        workspace.name = workspace_in.name
        
    db.commit()
    db.refresh(workspace)
    return workspace
