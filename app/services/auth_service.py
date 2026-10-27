from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.models import Role, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


def register_user(db: Session, data: RegisterRequest) -> User:
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("Email is already registered", code="email_taken")

    role = Role.ADMIN if email in get_settings().admin_email_set else Role.TRADER
    user = User(email=email, hashed_password=hash_password(data.password), role=role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # race: same email registered concurrently
        db.rollback()
        raise ConflictError("Email is already registered", code="email_taken") from exc
    db.refresh(user)
    return user


def login(db: Session, data: LoginRequest) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None:
        verify_dummy_password(data.password)
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")
    if not verify_password(data.password, user.hashed_password):
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")

    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(access_token=token, expires_in=expires_in)
