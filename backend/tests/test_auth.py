from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.password import hash_password
from app.config import settings
from app.models.institution import Institution
from app.models.refresh_token import RefreshToken
from app.models.user import User
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_register_institution_success(client: AsyncClient):
    payload = {
        "email": "Principal@AlphaCollege.edu.in",
        "password": "Password123!",
        "institution_name": "Alpha Institute of Technology",
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "principal@alphacollege.edu.in"
    assert data["user"]["role"] == "INSTITUTION"
    assert data["user"]["institution_name"] == "Alpha Institute of Technology"
    assert data["user"]["is_active"] is True

    # Check refresh cookie is set
    assert "pramaan_refresh" in response.cookies


@pytest.mark.asyncio
async def test_register_institution_duplicate_email(client: AsyncClient):
    payload = {
        "email": "duplicate@college.edu",
        "password": "Password123!",
        "institution_name": "College One",
    }
    res1 = await client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    payload2 = {
        "email": "DUPLICATE@college.edu",  # uppercase check
        "password": "OtherPassword123!",
        "institution_name": "College Two",
    }
    res2 = await client.post("/api/auth/register", json=payload2)
    assert res2.status_code == 409
    err = res2.json().get("error", {})
    assert "already exists" in err.get("message", "").lower()


@pytest.mark.asyncio
async def test_register_institution_invalid_inputs(client: AsyncClient):
    # Short password (< 8 chars)
    res = await client.post(
        "/api/auth/register",
        json={"email": "valid@college.edu", "password": "short", "institution_name": "College"},
    )
    assert res.status_code == 422

    # Invalid email
    res2 = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "Password123!", "institution_name": "College"},
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_register_ignores_injected_role(client: AsyncClient):
    # Attempting to inject role="REVIEWER" in register body
    payload = {
        "email": "sneaky@college.edu",
        "password": "Password123!",
        "institution_name": "Sneaky Tech",
        "role": "REVIEWER",
    }
    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "INSTITUTION"  # Always INSTITUTION


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register first
    await client.post(
        "/api/auth/register",
        json={
            "email": "login_test@college.edu",
            "password": "CorrectPassword123!",
            "institution_name": "Login College",
        },
    )

    # Login
    response = await client.post(
        "/api/auth/login",
        json={"email": "LOGIN_TEST@college.edu", "password": "CorrectPassword123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login_test@college.edu"
    assert "pramaan_refresh" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "test_pw@college.edu",
            "password": "RealPassword123!",
            "institution_name": "Test College",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "test_pw@college.edu", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    err = response.json().get("error", {})
    assert "invalid email or password" in err.get("message", "").lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"email": "ghost@college.edu", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    err = response.json().get("error", {})
    assert "invalid email or password" in err.get("message", "").lower()


@pytest.mark.asyncio
async def test_login_deactivated_user(client: AsyncClient):
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "deactivated@college.edu",
            "password": "Password123!",
            "institution_name": "Closed College",
        },
    )
    user_id = reg.json()["user"]["id"]

    # Deactivate directly in DB
    async with TestSessionLocal() as session:
        user = await session.scalar(select(User).where(User.id == user_id))
        user.is_active = False
        await session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "deactivated@college.edu", "password": "Password123!"},
    )
    assert response.status_code == 403
    err = response.json().get("error", {})
    assert "deactivated" in err.get("message", "").lower()


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_usage(client: AsyncClient):
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "refresh_flow@college.edu",
            "password": "Password123!",
            "institution_name": "Refresh College",
        },
    )
    initial_cookie = reg.cookies.get("pramaan_refresh")
    assert initial_cookie is not None

    # Call /api/auth/refresh with the cookie
    refresh_res = await client.post("/api/auth/refresh", cookies={"pramaan_refresh": initial_cookie})
    assert refresh_res.status_code == 200
    new_data = refresh_res.json()
    assert "access_token" in new_data
    new_cookie = refresh_res.cookies.get("pramaan_refresh")
    assert new_cookie is not None
    assert new_cookie != initial_cookie  # Token was rotated!

    # Re-using the old refresh token must be rejected (revoked)
    replay_res = await client.post("/api/auth/refresh", cookies={"pramaan_refresh": initial_cookie})
    assert replay_res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_missing_cookie(client: AsyncClient):
    res = await client.post("/api/auth/refresh")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_token(client: AsyncClient):
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "logout_flow@college.edu",
            "password": "Password123!",
            "institution_name": "Logout College",
        },
    )
    cookie = reg.cookies.get("pramaan_refresh")

    logout_res = await client.post("/api/auth/logout", cookies={"pramaan_refresh": cookie})
    assert logout_res.status_code == 200

    # Attempting to refresh after logout should fail
    refresh_res = await client.post("/api/auth/refresh", cookies={"pramaan_refresh": cookie})
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_get_me_endpoint(client: AsyncClient):
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "me_test@college.edu",
            "password": "Password123!",
            "institution_name": "Me College",
        },
    )
    access_token = reg.json()["access_token"]

    # Without token -> 401
    unauth = await client.get("/api/auth/me")
    assert unauth.status_code == 401

    # With token -> 200
    auth_res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert auth_res.status_code == 200
    assert auth_res.json()["email"] == "me_test@college.edu"
    assert auth_res.json()["institution_name"] == "Me College"


@pytest.mark.asyncio
async def test_admin_setup_reviewer(client: AsyncClient):
    payload = {
        "email": "admin_reviewer@aicte-india.org",
        "password": "ReviewerAdminPass2026!",
    }

    # Wrong token -> 403
    bad_res = await client.post(
        "/api/auth/admin/setup",
        json=payload,
        headers={"X-Admin-Setup-Token": "wrong-token"},
    )
    assert bad_res.status_code == 403

    # Correct token -> 201 Created
    good_res = await client.post(
        "/api/auth/admin/setup",
        json=payload,
        headers={"X-Admin-Setup-Token": settings.ADMIN_SETUP_TOKEN},
    )
    assert good_res.status_code == 201
    assert good_res.json()["role"] == "REVIEWER"
    assert good_res.json()["email"] == "admin_reviewer@aicte-india.org"

    # Second setup attempt -> 409 Conflict (idempotent guard: reviewer already initialized)
    duplicate_res = await client.post(
        "/api/auth/admin/setup",
        json={
            "email": "another_reviewer@aicte-india.org",
            "password": "ReviewerAdminPass2026!",
        },
        headers={"X-Admin-Setup-Token": settings.ADMIN_SETUP_TOKEN},
    )
    assert duplicate_res.status_code == 409
