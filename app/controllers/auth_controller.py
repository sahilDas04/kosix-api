import bcrypt
import jwt
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Request

from app.core.config import settings
from app.core.logger import get_logger
from app.models.account import Account, AuthProvider
from app.models.session import Session as SessionModel
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    AccountResponse,
    AuthResponse,
    RefreshTokenRequest,
    PasswordChangeRequest,
)

logger = get_logger(__name__)


class AuthController:
    """Controller for authentication operations."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    @staticmethod
    def create_access_token(account_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": str(account_id),
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(account_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT refresh token."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        
        payload = {
            "sub": str(account_id),
            "exp": expire,
            "type": "refresh"
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    @staticmethod
    def create_tokens(account_id: UUID) -> TokenResponse:
        """Create both access and refresh tokens."""
        access_token = AuthController.create_access_token(account_id)
        refresh_token = AuthController.create_refresh_token(account_id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    @staticmethod
    def register(db: Session, request: RegisterRequest) -> AuthResponse:
        """Register a new user account."""
        logger.info(f"Attempting to register user with email: {request.email}")

        # Check if email already exists
        existing_email = db.query(Account).filter(Account.email == request.email).first()
        if existing_email:
            logger.warning(f"Registration failed: Email {request.email} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Check if username already exists
        existing_username = db.query(Account).filter(Account.username == request.username).first()
        if existing_username:
            logger.warning(f"Registration failed: Username {request.username} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

        # Create new account
        hashed_password = AuthController.hash_password(request.password)
        account = Account(
            email=request.email,
            name=request.name,
            username=request.username,
            password_hash=hashed_password,
            provider=AuthProvider.EMAIL,
            email_verified=False
        )

        db.add(account)
        db.commit()
        db.refresh(account)

        logger.info(f"Successfully registered user: {account.id}")

        # Create tokens
        tokens = AuthController.create_tokens(account.id)

        return AuthResponse(
            account=AccountResponse(
                id=account.id,
                email=account.email,
                name=account.name,
                username=account.username,
                role=account.role.value,
                avatar_url=account.avatar_url,
                email_verified=account.email_verified,
                created_at=account.created_at
            ),
            tokens=tokens
        )

    @staticmethod
    def login(db: Session, request: LoginRequest, client_request: Optional[Request] = None) -> AuthResponse:
        """Authenticate user and return tokens."""
        logger.info(f"Login attempt for email: {request.email}")

        # Find account by email
        account = db.query(Account).filter(Account.email == request.email).first()
        if not account:
            logger.warning(f"Login failed: Account not found for email {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Verify password
        if not account.password_hash or not AuthController.verify_password(request.password, account.password_hash):
            logger.warning(f"Login failed: Invalid password for email {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        logger.info(f"Successful login for user: {account.id}")

        # Create tokens
        tokens = AuthController.create_tokens(account.id)

        # Create session record
        ip_address = None
        if client_request:
            ip_address = client_request.client.host if client_request.client else None

        session = SessionModel(
            account_id=account.id,
            session_token=tokens.refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            is_active=True
        )
        db.add(session)
        db.commit()

        return AuthResponse(
            account=AccountResponse(
                id=account.id,
                email=account.email,
                name=account.name,
                username=account.username,
                role=account.role.value,
                avatar_url=account.avatar_url,
                email_verified=account.email_verified,
                created_at=account.created_at
            ),
            tokens=tokens
        )

    @staticmethod
    def refresh_tokens(db: Session, request: RefreshTokenRequest) -> TokenResponse:
        """Refresh access token using refresh token."""
        logger.info("Attempting to refresh tokens")

        # Decode refresh token
        payload = AuthController.decode_token(request.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        account_id = payload.get("sub")
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        # Check if session exists and is active
        session = db.query(SessionModel).filter(
            SessionModel.session_token == request.refresh_token,
            SessionModel.is_active == True
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found or expired"
            )

        # Verify account exists
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account not found"
            )

        # Invalidate old session
        session.is_active = False
        db.commit()

        # Create new tokens
        tokens = AuthController.create_tokens(account.id)

        # Create new session
        new_session = SessionModel(
            account_id=account.id,
            session_token=tokens.refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=session.ip_address,
            is_active=True
        )
        db.add(new_session)
        db.commit()

        logger.info(f"Successfully refreshed tokens for user: {account.id}")

        return tokens

    @staticmethod
    def logout(db: Session, refresh_token: str) -> dict:
        """Logout user by invalidating their session."""
        logger.info("Attempting to logout user")

        # Find and invalidate session
        session = db.query(SessionModel).filter(
            SessionModel.session_token == refresh_token,
            SessionModel.is_active == True
        ).first()

        if session:
            session.is_active = False
            db.commit()
            logger.info(f"Successfully logged out user: {session.account_id}")
        
        return {"message": "Successfully logged out"}

    @staticmethod
    def get_current_user(db: Session, token: str) -> Account:
        """Get current user from access token."""
        payload = AuthController.decode_token(token)
        
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        account_id = payload.get("sub")
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account not found"
            )

        return account

    @staticmethod
    def change_password(db: Session, account: Account, request: PasswordChangeRequest) -> dict:
        """Change user password."""
        logger.info(f"Password change attempt for user: {account.id}")

        # Verify current password
        if not account.password_hash or not AuthController.verify_password(
            request.current_password, account.password_hash
        ):
            logger.warning(f"Password change failed: Invalid current password for user {account.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        # Hash new password and update
        account.password_hash = AuthController.hash_password(request.new_password)
        db.commit()

        logger.info(f"Successfully changed password for user: {account.id}")

        return {"message": "Password changed successfully"}


# Create a dependency for getting current user
def get_current_user_dependency(db: Session, authorization: str) -> Account:
    """Dependency to get current authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    return AuthController.get_current_user(db, token)
