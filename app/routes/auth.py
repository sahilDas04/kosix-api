from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.controllers.auth_controller import AuthController
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    PasswordChangeRequest,
    AuthResponse,
    TokenResponse,
    AccountResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    - **email**: Valid email address
    - **username**: Unique username (3-100 characters)
    - **password**: Password (minimum 8 characters)
    - **name**: Optional display name
    """
    return AuthController.register(db, request)


@router.post("/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    client_request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access/refresh tokens.
    
    - **email**: User's email address
    - **password**: User's password
    """
    return AuthController.login(db, request, client_request)


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using a valid refresh token.
    
    - **refresh_token**: Valid refresh token from login
    """
    return AuthController.refresh_tokens(db, request)


@router.post("/logout")
def logout(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Logout user by invalidating refresh token.
    
    - **refresh_token**: Refresh token to invalidate
    """
    return AuthController.logout(db, request.refresh_token)


@router.get("/me", response_model=AccountResponse)
def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user's account details.
    
    Requires Bearer token in Authorization header.
    """
    if not authorization.startswith("Bearer "):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = authorization.replace("Bearer ", "")
    account = AuthController.get_current_user(db, token)
    
    return AccountResponse(
        id=account.id,
        email=account.email,
        name=account.name,
        username=account.username,
        role=account.role.value,
        avatar_url=account.avatar_url,
        email_verified=account.email_verified,
        created_at=account.created_at
    )


@router.post("/change-password")
def change_password(
    request: PasswordChangeRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Change current user's password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password (minimum 8 characters)
    
    Requires Bearer token in Authorization header.
    """
    if not authorization.startswith("Bearer "):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token = authorization.replace("Bearer ", "")
    account = AuthController.get_current_user(db, token)
    
    return AuthController.change_password(db, account, request)
