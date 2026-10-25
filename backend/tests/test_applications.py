import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_application(client: AsyncClient):
    payload = {
        "institution_name": "Synthetic ABC Engineering College",
        "application_category": "eoa",
        "academic_year": "2026-27",
    }
    response = await client.post("/api/applications", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["institution_name"] == payload["institution_name"]
    assert data["application_category"] == "eoa"
    assert data["academic_year"] == "2026-27"
    assert data["overall_status"] == "processing_incomplete"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_application(client: AsyncClient):
    # 1. Create application
    payload = {
        "institution_name": "Test Engineering Institute",
        "application_category": "eoa",
        "academic_year": "2026-27",
    }
    create_res = await client.post("/api/applications", json=payload)
    app_id = create_res.json()["id"]

    # 2. Get application
    get_res = await client.get(f"/api/applications/{app_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == app_id
    assert data["institution_name"] == payload["institution_name"]
    assert isinstance(data["documents"], list)
    assert isinstance(data["findings"], list)


@pytest.mark.asyncio
async def test_get_nonexistent_application(client: AsyncClient):
    response = await client.get("/api/applications/non_existent_app_id")
    assert response.status_code == 404
    error = response.json().get("error")
    assert error is not None
    assert error["code"] == "APPLICATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_invalid_application_payload(client: AsyncClient):
    # Invalid academic year format
    payload = {
        "institution_name": "Test",
        "application_category": "eoa",
        "academic_year": "invalid-year",
    }
    response = await client.post("/api/applications", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_FAILED"
