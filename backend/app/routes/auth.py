from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.audit import log_auth_event
from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AdminSetupRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "pramaan_refresh"
REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _build_user_response(user: User) -> UserResponse:
    inst_name = user.institution.display_name if user.institution else None
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        institution_name=inst_name,
        created_at=user.created_at,
    )


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/api/auth",
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/auth",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new institution account",
)
async def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.register_institution(db, payload)
    raw_refresh = await auth_service.create_refresh_token_record(db, user.id)
    _set_refresh_cookie(response, raw_refresh)

    access_token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role,
    })

    log_auth_event(
        event_type="register",
        user_id=user.id,
        email=user.email,
        role=user.role,
        ip_address=request.client.host if request.client else None,
        status="success",
    )

    return TokenResponse(
        access_token=access_token,
        user=_build_user_response(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log into user account",
)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    raw_refresh = await auth_service.create_refresh_token_record(db, user.id)
    _set_refresh_cookie(response, raw_refresh)

    access_token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role,
    })

    log_auth_event(
        event_type="login",
        user_id=user.id,
        email=user.email,
        role=user.role,
        ip_address=request.client.host if request.client else None,
        status="success",
    )

    return TokenResponse(
        access_token=access_token,
        user=_build_user_response(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using httpOnly refresh token cookie",
)
async def refresh(
    response: Response,
    pramaan_refresh: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    if not pramaan_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie is missing.",
        )

    new_access_token, new_raw_refresh, user = await auth_service.refresh_access_token(
        db, pramaan_refresh
    )
    _set_refresh_cookie(response, new_raw_refresh)

    log_auth_event(
        event_type="token_refresh",
        user_id=user.id,
        email=user.email,
        role=user.role,
        status="success",
    )

    return TokenResponse(
        access_token=new_access_token,
        user=_build_user_response(user),
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out and invalidate refresh token",
)
async def logout(
    response: Response,
    pramaan_refresh: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    if pramaan_refresh:
        await auth_service.revoke_refresh_token(db, pramaan_refresh)
    _clear_refresh_cookie(response)

    log_auth_event(
        event_type="logout",
        status="success",
    )

    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user details",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return _build_user_response(current_user)


@router.post(
    "/admin/setup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="One-time admin setup to initialize the initial reviewer account",
)
async def admin_setup(
    payload: AdminSetupRequest,
    x_admin_setup_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if not x_admin_setup_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-Admin-Setup-Token header.",
        )

    reviewer = await auth_service.setup_admin_reviewer(
        db, payload, x_admin_setup_token
    )

    log_auth_event(
        event_type="admin_setup_reviewer",
        user_id=reviewer.id,
        email=reviewer.email,
        role="REVIEWER",
        status="success",
        details="Initial reviewer created via one-time admin setup",
    )

    return _build_user_response(reviewer)
