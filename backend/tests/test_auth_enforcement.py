import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.models.application import Application
from app.models.finding import Finding
from app.models.institution import Institution
from app.models.user import User
from tests.conftest import TestSessionLocal


@pytest_asyncio.fixture
async def users_and_apps():
    """Create two institutions and one reviewer with sample applications in DB."""
    async with TestSessionLocal() as session:
        # Institution 1
        u1 = User(
            id="user-inst-1",
            email="inst1@college.edu",
            password_hash=hash_password("Pass123!"),
            role="INSTITUTION",
            is_active=True,
        )
        session.add(u1)
        inst1 = Institution(user_id=u1.id, display_name="College One")
        session.add(inst1)

        # Institution 2
        u2 = User(
            id="user-inst-2",
            email="inst2@college.edu",
            password_hash=hash_password("Pass123!"),
            role="INSTITUTION",
            is_active=True,
        )
        session.add(u2)
        inst2 = Institution(user_id=u2.id, display_name="College Two")
        session.add(inst2)

        # Reviewer
        u_rev = User(
            id="user-rev-1",
            email="rev1@aicte.edu",
            password_hash=hash_password("Pass123!"),
            role="REVIEWER",
            is_active=True,
        )
        session.add(u_rev)

        # App 1 (owned by user-inst-1, draft)
        app1 = Application(
            id="app-inst1-draft",
            owner_id=u1.id,
            status="draft",
            institution_name="College One",
            application_category="eoa",
            academic_year="2026-27",
            overall_status="processing_incomplete",
        )
        session.add(app1)

        # App 2 (owned by user-inst-1, submitted)
        app2 = Application(
            id="app-inst1-submitted",
            owner_id=u1.id,
            status="submitted",
            institution_name="College One",
            application_category="eoa",
            academic_year="2026-27",
            overall_status="ready_for_review",
        )
        session.add(app2)

        # Finding on App 2 for reviewer test
        finding = Finding(
            id="finding-app2-1",
            application_id=app2.id,
            rule_id="FIRE_SAFETY_001",
            status="flagged",
            title="Fire Safety Certificate Expiry Flag",
            reason="Certificate expires soon",
        )
        session.add(finding)

        # App 3 (owned by user-inst-2, draft)
        app3 = Application(
            id="app-inst2-draft",
            owner_id=u2.id,
            status="draft",
            institution_name="College Two",
            application_category="eoa",
            academic_year="2026-27",
            overall_status="processing_incomplete",
        )
        session.add(app3)

        await session.commit()

    tokens = {
        "inst1": create_access_token({"sub": "user-inst-1", "email": "inst1@college.edu", "role": "INSTITUTION"}),
        "inst2": create_access_token({"sub": "user-inst-2", "email": "inst2@college.edu", "role": "INSTITUTION"}),
        "rev": create_access_token({"sub": "user-rev-1", "email": "rev1@aicte.edu", "role": "REVIEWER"}),
    }
    return tokens


# ==========================================
# 1. IDOR Mitigation Tests (must return 404)
# ==========================================

@pytest.mark.asyncio
async def test_idor_institution_cannot_get_other_application(client: AsyncClient, users_and_apps):
    token2 = users_and_apps["inst2"]
    # Institution 2 attempts to GET App 1 (owned by Institution 1)
    res = await client.get("/api/applications/app-inst1-draft", headers={"Authorization": f"Bearer {token2}"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "APPLICATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_idor_institution_cannot_list_other_documents(client: AsyncClient, users_and_apps):
    token2 = users_and_apps["inst2"]
    res = await client.get("/api/applications/app-inst1-draft/documents", headers={"Authorization": f"Bearer {token2}"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_idor_institution_cannot_upload_to_other_application(client: AsyncClient, users_and_apps):
    token2 = users_and_apps["inst2"]
    files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}
    res = await client.post(
        "/api/applications/app-inst1-draft/documents",
        files=files,
        data={"document_type": "fire_safety_certificate"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_idor_institution_cannot_validate_other_application(client: AsyncClient, users_and_apps):
    token2 = users_and_apps["inst2"]
    res = await client.post("/api/applications/app-inst1-draft/validate", headers={"Authorization": f"Bearer {token2}"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_idor_institution_cannot_submit_other_application(client: AsyncClient, users_and_apps):
    token2 = users_and_apps["inst2"]
    res = await client.post("/api/applications/app-inst1-draft/submit", headers={"Authorization": f"Bearer {token2}"})
    assert res.status_code == 404


# ==========================================
# 2. Application Lock Tests (409 Conflict)
# ==========================================

@pytest.mark.asyncio
async def test_locked_application_rejects_document_upload(client: AsyncClient, users_and_apps):
    token1 = users_and_apps["inst1"]
    files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}
    res = await client.post(
        "/api/applications/app-inst1-submitted/documents",
        files=files,
        data={"document_type": "fire_safety_certificate"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "APPLICATION_LOCKED"


@pytest.mark.asyncio
async def test_locked_application_rejects_validation(client: AsyncClient, users_and_apps):
    token1 = users_and_apps["inst1"]
    res = await client.post(
        "/api/applications/app-inst1-submitted/validate",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "APPLICATION_LOCKED"


# ==========================================
# 3. Role Separation Tests (403 Forbidden)
# ==========================================

@pytest.mark.asyncio
async def test_reviewer_cannot_create_application(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    res = await client.post(
        "/api/applications",
        json={"institution_name": "Reviewer Fake College", "application_category": "eoa", "academic_year": "2026-27"},
        headers={"Authorization": f"Bearer {rev_token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_reviewer_cannot_upload_documents(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    files = {"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}
    res = await client.post(
        "/api/applications/app-inst1-submitted/documents",
        files=files,
        data={"document_type": "fire_safety_certificate"},
        headers={"Authorization": f"Bearer {rev_token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_reviewer_cannot_submit_application(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    res = await client.post(
        "/api/applications/app-inst1-submitted/submit",
        headers={"Authorization": f"Bearer {rev_token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_institution_cannot_patch_finding(client: AsyncClient, users_and_apps):
    token1 = users_and_apps["inst1"]
    res = await client.patch(
        "/api/applications/app-inst1-submitted/findings/finding-app2-1",
        json={"reviewer_decision": "verified", "reviewer_notes": "Trying to verify own finding"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert res.status_code == 403


# ==========================================
# 4. Reviewer Visibility & Actions
# ==========================================

@pytest.mark.asyncio
async def test_reviewer_cannot_see_draft_application(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    # App 1 is draft -> Reviewer should get 404
    res = await client.get("/api/applications/app-inst1-draft", headers={"Authorization": f"Bearer {rev_token}"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reviewer_can_see_submitted_application(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    # App 2 is submitted -> Reviewer gets 200
    res = await client.get("/api/applications/app-inst1-submitted", headers={"Authorization": f"Bearer {rev_token}"})
    assert res.status_code == 200
    assert res.json()["id"] == "app-inst1-submitted"


@pytest.mark.asyncio
async def test_reviewer_list_only_contains_submitted_applications(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    res = await client.get("/api/applications", headers={"Authorization": f"Bearer {rev_token}"})
    assert res.status_code == 200
    apps = res.json()
    assert len(apps) == 1
    assert apps[0]["id"] == "app-inst1-submitted"
    assert apps[0]["status"] == "submitted"


@pytest.mark.asyncio
async def test_reviewer_can_patch_finding_on_submitted_app(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    res = await client.patch(
        "/api/applications/app-inst1-submitted/findings/finding-app2-1",
        json={"reviewer_decision": "verified", "reviewer_notes": "Legitimate AICTE verification."},
        headers={"Authorization": f"Bearer {rev_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["reviewer_decision"] == "verified"
    assert data["reviewed_by"] == "rev1@aicte.edu"


@pytest.mark.asyncio
async def test_reviewer_can_validate_submitted_app(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    res = await client.post(
        "/api/applications/app-inst1-submitted/validate",
        headers={"Authorization": f"Bearer {rev_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["application_id"] == "app-inst1-submitted"
    assert "findings" in data


@pytest.mark.asyncio
async def test_token_in_query_param_authenticates_request(client: AsyncClient, users_and_apps):
    rev_token = users_and_apps["rev"]
    # Request without token fails with 401
    res_no_auth = await client.get("/api/applications/app-inst1-submitted")
    assert res_no_auth.status_code == 401

    # Request with ?token= query parameter succeeds with 200
    res = await client.get(f"/api/applications/app-inst1-submitted?token={rev_token}")
    assert res.status_code == 200
    assert res.json()["id"] == "app-inst1-submitted"


# ==========================================
# 5. Unauthenticated / Invalid Token Tests
# ==========================================

@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    res = await client.get("/api/applications")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token_rejected(client: AsyncClient):
    res = await client.get("/api/applications", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert res.status_code == 401
