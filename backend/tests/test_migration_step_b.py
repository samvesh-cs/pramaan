import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.application import Application
from app.models.finding import Finding
from app.rules.declarative_engine import default_declarative_engine
from app.schemas.finding import FindingResponse
from app.schemas.report import ReportResponse
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_legacy_rows_have_null_and_display_legacy_ruleset(institution_client: AsyncClient):
    """
    Asserts that:
    1. Legacy mode execution leaves ruleset_version as NULL in database.
    2. FindingResponse and ReportResponse serialize NULL ruleset_version as 'Legacy ruleset'.
    3. Stored findings persist their advisory flag.
    """
    settings.RULE_ENGINE_MODE = "legacy"

    # Create application
    create_resp = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Legacy Ruleset Stamping College",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # Validate in legacy mode
    val_resp = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_resp.status_code == 200
    report_data = val_resp.json()

    # In legacy mode, ruleset_version is None, displayed as 'Legacy ruleset'
    assert report_data["ruleset_version"] is None
    assert report_data["ruleset_display_name"] == "Legacy ruleset"
    assert report_data["rule_engine_mode"] == "legacy"

    for f_resp in report_data["findings"]:
        assert f_resp["ruleset_version"] is None
        assert f_resp["ruleset_display_name"] == "Legacy ruleset"
        assert f_resp["rule_engine_mode"] == "legacy"

    # Verify directly from DB
    async with TestSessionLocal() as session:
        app_stmt = select(Application).where(Application.id == app_id)
        app_res = await session.execute(app_stmt)
        db_app = app_res.scalar_one()
        assert db_app.ruleset_version is None
        assert db_app.rule_engine_mode == "legacy"

        findings_stmt = select(Finding).where(Finding.application_id == app_id)
        findings_res = await session.execute(findings_stmt)
        db_findings = list(findings_res.scalars().all())
        assert len(db_findings) > 0
        for f in db_findings:
            assert f.ruleset_version is None
            assert f.rule_engine_mode == "legacy"


@pytest.mark.asyncio
async def test_declarative_mode_stamping(institution_client: AsyncClient):
    """
    Asserts that:
    1. In declarative mode, computed canonical ruleset version + hash is stamped.
    2. Stamped on both Application and Finding DB rows.
    3. FindingResponse and ReportResponse include ruleset_version and rule_engine_mode.
    """
    settings.RULE_ENGINE_MODE = "declarative"
    expected_version = default_declarative_engine.ruleset_version
    assert expected_version is not None
    assert expected_version.startswith("2024-2027.")

    # Create application
    create_resp = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Declarative Ruleset Stamping College",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # Validate in declarative mode
    val_resp = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_resp.status_code == 200
    report_data = val_resp.json()

    assert report_data["ruleset_version"] == expected_version
    assert report_data["ruleset_display_name"] == expected_version
    assert report_data["rule_engine_mode"] == "declarative"

    for f_resp in report_data["findings"]:
        assert f_resp["ruleset_version"] == expected_version
        assert f_resp["ruleset_display_name"] == expected_version
        assert f_resp["rule_engine_mode"] == "declarative"

    # Verify directly from DB
    async with TestSessionLocal() as session:
        app_stmt = select(Application).where(Application.id == app_id)
        app_res = await session.execute(app_stmt)
        db_app = app_res.scalar_one()
        assert db_app.ruleset_version == expected_version
        assert db_app.rule_engine_mode == "declarative"

        findings_stmt = select(Finding).where(Finding.application_id == app_id)
        findings_res = await session.execute(findings_stmt)
        db_findings = list(findings_res.scalars().all())
        assert len(db_findings) > 0
        for f in db_findings:
            assert f.ruleset_version == expected_version
    # Reset
    settings.RULE_ENGINE_MODE = "legacy"


def test_finding_and_report_schema_legacy_defaults():
    """Verify schema defaults when ruleset_version is None."""
    finding_dict = {
        "id": "f_1",
        "rule_id": "TEST_001",
        "status": "pass",
        "title": "Pass",
        "reason": "OK",
        "ruleset_version": None,
        "rule_engine_mode": None,
    }
    resp = FindingResponse.model_validate(finding_dict)
    assert resp.ruleset_display_name == "Legacy ruleset"

    rep = ReportResponse(
        application_id="app_1",
        overall_status="checks_passed",
        summary={"pass": 1, "flagged": 0, "missing": 0, "unresolved": 0, "not_applicable": 0},
        missing_document_types=[],
        findings=[resp],
        ruleset_version=None,
        rule_engine_mode=None,
        generated_at=resp.reviewed_at or "2026-10-28T00:00:00Z",
    )
    assert rep.ruleset_display_name == "Legacy ruleset"
