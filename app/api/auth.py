import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import structlog

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models import User, VerificationToken
from app.core.database import get_db
from app.services.email_service import EmailService


router = APIRouter()
logger = structlog.get_logger()


# Pydantic models for request/response
class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    is_verified: bool
    created_at: datetime


@router.post("/register", response_model=dict)
async def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user and create verification token."""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_pw = hash_password(user_data.password)
    new_user = User(
        id=uuid.uuid4(),
        email=user_data.email,
        hashed_password=hashed_pw,
        is_verified=False
    )
    
    db.add(new_user)
    db.flush()  # Get the user ID without committing
    
    # Create verification token
    verification_token = str(uuid.uuid4())
    token_expires = datetime.utcnow() + timedelta(hours=24)
    
    verification_record = VerificationToken(
        id=uuid.uuid4(),
        user_id=new_user.id,
        token=verification_token,
        expires_at=token_expires
    )
    
    db.add(verification_record)
    db.commit()
    
    # Send verification email
    try:
        email_sent = EmailService.send_verification_email(new_user, verification_token)
        if email_sent:
            logger.info(
                "verification_email_sent",
                user_id=str(new_user.id),
                email=user_data.email
            )
        else:
            logger.warning(
                "verification_email_failed",
                user_id=str(new_user.id),
                email=user_data.email
            )
    except Exception as e:
        logger.error(
            "verification_email_error",
            user_id=str(new_user.id),
            email=user_data.email,
            error=str(e)
        )

    # Also log to console for development
    verification_url = f"http://localhost:8000/api/auth/verify-email?token={verification_token}"
    print(f"[DEV] Verification URL for {user_data.email}: {verification_url}")

    return {
        "message": "User registered successfully. Check your email for verification link.",
        "user_id": str(new_user.id)
    }


@router.post("/login", response_model=TokenResponse)
async def login_user(user_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access + refresh tokens."""
    
    # Find user by email
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please verify your email before logging in"
        )
    
    # Create tokens
    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify user email using verification token."""
    
    # Find verification token
    verification_record = db.query(VerificationToken).filter(
        VerificationToken.token == token
    ).first()
    
    if not verification_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired verification token"
        )
    
    # Check if token is expired
    if verification_record.expires_at < datetime.utcnow():
        db.delete(verification_record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired"
        )
    
    # Find and verify user
    user = db.query(User).filter(User.id == verification_record.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user verification status
    user.is_verified = True
    user.updated_at = datetime.utcnow()
    
    # Delete verification token
    db.delete(verification_record)
    db.commit()
    
    return {
        "message": "Email verified successfully. You can now log in.",
        "user_id": str(user.id)
    }