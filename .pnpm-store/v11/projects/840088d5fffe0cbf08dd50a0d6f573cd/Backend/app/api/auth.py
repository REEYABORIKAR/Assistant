from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.api.deps import SessionDep, CurrentUser
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.token import Token
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def _authenticate_user(email: str, password: str, db) -> User:
    """
    Shared authentication logic used by both /login and /token.
    Returns the User on success, raises HTTPException on failure.
    """
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: SessionDep):
    # Check if email exists
    user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email.lower(),
        full_name=user_in.full_name,
        password_hash=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token,
             summary="Login with JSON (for frontend / API clients)")
def login(user_in: UserLogin, db: SessionDep):
    """Accepts JSON body: {email, password}. Used by the frontend and direct API clients."""
    user = _authenticate_user(user_in.email, user_in.password, db)
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/token", response_model=Token,
             summary="OAuth2 token endpoint (for Swagger UI)")
def token(
    db: SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2-compatible token endpoint used by Swagger UI's Authorize dialog.
    Accepts application/x-www-form-urlencoded with 'username' and 'password' fields.
    The 'username' field is treated as the user's email address.
    Returns the same JWT bearer token as POST /api/auth/login.
    """
    user = _authenticate_user(form_data.username, form_data.password, db)
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: CurrentUser):
    return current_user
