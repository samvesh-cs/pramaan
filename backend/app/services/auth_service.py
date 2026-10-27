import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_dummy_password, verify_password
from app.config import settings
from app.models.institution import Institution
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import AdminSetupRequest, RegisterRequest


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def register_institution(db: AsyncSession, payload: RegisterRequest) -> User:
    norm_email = payload.email.strip().lower()

    # Check if user with this email already exists
    existing = await db.scalar(select(User).where(User.email == norm_email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=norm_email,
        password_hash=hash_password(payload.password),
        role="INSTITUTION",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    institution = Institution(
        user_id=user.id,
        display_name=payload.institution_name.strip(),
    )
    db.add(institution)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    norm_email = email.strip().lower()
    user = await db.scalar(select(User).where(User.email == norm_email))

    if not user:
        verify_dummy_password(password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def create_refresh_token_record(db: AsyncSession, user_id: str) -> str:
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    record = RefreshToken(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(record)
    await db.commit()
    return raw_token


async def refresh_access_token(
    db: AsyncSession, raw_refresh_token: str
) -> tuple[str, str, User]:
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing.",
        )

    token_hash = _hash_token(raw_refresh_token)
    now = datetime.now(timezone.utc)

    record = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
        )
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token.",
        )

    # Ensure expires_at is timezone-aware for comparison
    record_expires = record.expires_at
    if record_expires.tzinfo is None:
        record_expires = record_expires.replace(tzinfo=timezone.utc)

    if record_expires < now:
        record.revoked = True
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
        )

    user = await db.scalar(select(User).where(User.id == record.user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found.",
        )

    # Rotate refresh token: revoke current, issue new
    record.revoked = True
    new_raw_token = secrets.token_urlsafe(48)
    new_token_hash = _hash_token(new_raw_token)
    new_record = RefreshToken(
        token_hash=new_token_hash,
        user_id=user.id,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        revoked=False,
    )
    db.add(new_record)
    await db.commit()

    new_access_token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role,
    })

    return new_access_token, new_raw_token, user


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str | None) -> None:
    if not raw_refresh_token:
        return
    token_hash = _hash_token(raw_refresh_token)
    record = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if record:
        record.revoked = True
        await db.commit()


async def setup_admin_reviewer(
    db: AsyncSession, payload: AdminSetupRequest, setup_token: str
) -> User:
    if not secrets.compare_digest(setup_token, settings.ADMIN_SETUP_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin setup token.",
        )

    # Check if a reviewer already exists
    existing_reviewer = await db.scalar(select(User).where(User.role == "REVIEWER"))
    if existing_reviewer:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reviewer account already initialized.",
        )

    norm_email = payload.email.strip().lower()
    existing_email = await db.scalar(select(User).where(User.email == norm_email))
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    reviewer = User(
        email=norm_email,
        password_hash=hash_password(payload.password),
        role="REVIEWER",
        is_active=True,
    )
    db.add(reviewer)
    await db.commit()
    await db.refresh(reviewer)
    return reviewer
