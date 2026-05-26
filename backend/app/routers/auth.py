from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, get_token_payload
from ..models import User, UserSession
from ..schemas import AuthResponse, MessageResponse, UserLoginRequest, UserPublic, UserSignupRequest
from ..security import create_access_token, create_token_jti, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _issue_auth_response(db: Session, user: User) -> AuthResponse:
    token_jti = create_token_jti()
    token, expires_at = create_access_token(user_id=user.id, email=user.email, jti=token_jti)
    db.add(
        UserSession(
            user_id=user.id,
            token_jti=token_jti,
            expires_at=expires_at,
        )
    )
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return AuthResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserPublic.model_validate(user),
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserSignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_auth_response(db, user)


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return _issue_auth_response(db, user)


@router.post("/logout", response_model=MessageResponse)
def logout(
    token_payload: dict = Depends(get_token_payload),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _ = current_user  # explicitly ensure authenticated user exists
    jti = token_payload.get("jti")
    session_row = db.query(UserSession).filter(UserSession.token_jti == jti).first()
    if session_row and session_row.revoked_at is None:
        session_row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return MessageResponse(message="Logout successful.")


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)
