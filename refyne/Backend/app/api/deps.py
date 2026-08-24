from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.roles import ProjectRole, role_has_permission
from app.models.membership import ProjectMember
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]

def get_current_user(db: SessionDep, token: TokenDep) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum_role: ProjectRole):
    """
    FastAPI dependency factory that checks the current user has at least
    `minimum_role` on the project specified by the `project_id` path parameter.

    Usage:
        @router.post("/api/projects/{project_id}/upload")
        async def upload(
            project_id: str,
            user: CurrentUser,
            _role: None = Depends(require_role(ProjectRole.EDITOR)),
        ):
            ...
    """
    def _check(
        project_id: str,
        current_user: CurrentUser,
        db: SessionDep,
    ):
        # Check direct ownership first (project owner is always ADMIN)
        from app.models.project import Project
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id,
        ).first()
        if project:
            return

        # Check project_members table
        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        ).first()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this project",
            )

        user_role = ProjectRole(member.role)
        if not role_has_permission(user_role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher. Your role: {user_role.value}",
            )

    return _check
