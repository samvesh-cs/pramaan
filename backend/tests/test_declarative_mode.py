import logging
import pytest
from unittest.mock import patch
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_legacy_mode_default_execution(institution_client: AsyncClient):
    """Verify that default RULE_ENGINE_MODE='legacy' executes normally."""
    settings.RULE_ENGINE_MODE = "legacy"

    # Create an application
    create_resp = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Test Engineering College Mode Legacy",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # Validate
    val_resp = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_resp.status_code == 200
    data = val_resp.json()
    assert data["application_id"] == app_id
    assert "overall_status" in data
    assert len(data["findings"]) > 0


@pytest.mark.asyncio
async def test_declarative_mode_success_execution(institution_client: AsyncClient):
    """Verify that RULE_ENGINE_MODE='declarative' executes declarative engine and returns 200."""
    settings.RULE_ENGINE_MODE = "declarative"

    # Create an application
    create_resp = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Test Engineering College Mode Declarative",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    # Validate
    val_resp = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_resp.status_code == 200
    data = val_resp.json()
    assert data["application_id"] == app_id
    assert "overall_status" in data
    assert len(data["findings"]) > 0

    # Reset
    settings.RULE_ENGINE_MODE = "legacy"


@pytest.mark.asyncio
async def test_declarative_mode_fallback_on_unexpected_error(
    institution_client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    """
    Verify that if the declarative engine raises an unexpected error:
    1. It falls back to legacy for that request.
    2. Logs DECLARATIVE_FALLBACK with application_id and rule_id (no document text).
    3. Returns a normal 200 response, never a 500.
    """
    settings.RULE_ENGINE_MODE = "declarative"

    # Create an application
    create_resp = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Test Engineering College Fallback",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert create_resp.status_code == 201
    app_id = create_resp.json()["id"]

    class MockRuleFailure(Exception):
        rule_id = "DOC_PRESENCE_001"

    with caplog.at_level(logging.WARNING):
        with patch("app.rules.declarative_engine.default_declarative_engine.evaluate") as mock_eval:
            mock_eval.side_effect = MockRuleFailure("Simulated engine crash")

            val_resp = await institution_client.post(f"/api/applications/{app_id}/validate")

    # Must return 200, NEVER 500
    assert val_resp.status_code == 200
    data = val_resp.json()
    assert data["application_id"] == app_id
    assert len(data["findings"]) > 0

    # Verify log output format
    fallback_logs = [record for record in caplog.records if "DECLARATIVE_FALLBACK" in record.message]
    assert len(fallback_logs) >= 1
    fallback_message = fallback_logs[0].message
    assert f"application_id={app_id}" in fallback_message
    assert "rule_id=DOC_PRESENCE_001" in fallback_message
    assert "MockRuleFailure" in fallback_message
    # Verify no document content leaked
    assert "Simulated engine crash" not in fallback_message

    # Reset
    settings.RULE_ENGINE_MODE = "legacy"


@pytest.mark.asyncio
async def test_rule_engine_mode_read_per_request(institution_client: AsyncClient):
    """Verify that settings.RULE_ENGINE_MODE is read per request dynamically."""
    # Create application
    create_resp = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Test Per Request Mode",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    app_id = create_resp.json()["id"]

    # Request 1: legacy mode
    settings.RULE_ENGINE_MODE = "legacy"
    with patch("app.rules.declarative_engine.default_declarative_engine.evaluate") as mock_dec:
        resp1 = await institution_client.post(f"/api/applications/{app_id}/validate")
        assert resp1.status_code == 200
        mock_dec.assert_not_called()

    # Request 2: declarative mode
    settings.RULE_ENGINE_MODE = "declarative"
    with patch("app.rules.declarative_engine.default_declarative_engine.evaluate") as mock_dec:
        mock_dec.return_value = []
        resp2 = await institution_client.post(f"/api/applications/{app_id}/validate")
        assert resp2.status_code == 200
        mock_dec.assert_called_once()

    # Reset
    settings.RULE_ENGINE_MODE = "legacy"
