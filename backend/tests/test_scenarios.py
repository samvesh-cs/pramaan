import json
from pathlib import Path
import pytest
from httpx import AsyncClient

SAMPLE_DIR = Path("tests/demo_samples")


def read_sample(filename: str) -> bytes:
    path = SAMPLE_DIR / filename
    with open(path, "rb") as f:
        return f.read()


@pytest.mark.asyncio
async def test_scenario_1_all_valid(client: AsyncClient):
    """Scenario 1: All 3 documents valid and matching -> checks_passed."""
    # 1. Create Application
    res = await client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert res.status_code == 201
    app_id = res.json()["id"]

    # 2. Upload Fire Safety
    files = {"file": ("valid_fire_safety.pdf", read_sample("valid_fire_safety.pdf"), "application/pdf")}
    data = {"document_type": "fire_safety_certificate"}
    u1 = await client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
    assert u1.status_code == 201

    # 3. Upload Building Completion
    files = {"file": ("valid_building_completion.pdf", read_sample("valid_building_completion.pdf"), "application/pdf")}
    data = {"document_type": "building_completion_certificate"}
    u2 = await client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
    assert u2.status_code == 201

    # 4. Upload Affidavit-2
    files = {"file": ("valid_affidavit_2.pdf", read_sample("valid_affidavit_2.pdf"), "application/pdf")}
    data = {"document_type": "affidavit_2"}
    u3 = await client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
    assert u3.status_code == 201

    # 5. Validate
    v = await client.post(f"/api/applications/{app_id}/validate")
    assert v.status_code == 200
    report = v.json()

    assert report["overall_status"] == "checks_passed"
    manifest = json.loads((SAMPLE_DIR / "manifest.json").read_text(encoding="utf-8"))
    scenario = next(item for item in manifest["scenarios"] if item["id"] == "scenario_1_valid")
    for status, expected_count in scenario["expected_summary"].items():
        assert report["summary"][status] == expected_count
    assert len(report["missing_document_types"]) == 0


@pytest.mark.asyncio
async def test_scenario_2_missing_document(client: AsyncClient):
    """Scenario 2: Only 2 of 3 documents uploaded -> missing_documents."""
    res = await client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    app_id = res.json()["id"]

    # Upload only Fire Safety and Building Completion (Affidavit-2 missing)
    files = {"file": ("valid_fire_safety.pdf", read_sample("valid_fire_safety.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "fire_safety_certificate"})

    files = {"file": ("valid_building_completion.pdf", read_sample("valid_building_completion.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "building_completion_certificate"})

    v = await client.post(f"/api/applications/{app_id}/validate")
    assert v.status_code == 200
    report = v.json()

    assert report["overall_status"] == "missing_documents"
    assert "affidavit_2" in report["missing_document_types"]
    assert report["summary"]["missing"] >= 1


@pytest.mark.asyncio
async def test_scenario_3_expired_document(client: AsyncClient):
    """Scenario 3: Expired Fire Safety Certificate -> discrepancies_found with EXPIRY_001 flagged."""
    res = await client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    app_id = res.json()["id"]

    # Upload expired fire safety
    files = {"file": ("expired_fire_safety.pdf", read_sample("expired_fire_safety.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "fire_safety_certificate"})

    # Upload other valid docs
    files = {"file": ("valid_building_completion.pdf", read_sample("valid_building_completion.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "building_completion_certificate"})

    files = {"file": ("valid_affidavit_2.pdf", read_sample("valid_affidavit_2.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "affidavit_2"})

    v = await client.post(f"/api/applications/{app_id}/validate")
    assert v.status_code == 200
    report = v.json()

    assert report["overall_status"] == "discrepancies_found"
    assert report["summary"]["flagged"] >= 1

    expiry_finding = next((f for f in report["findings"] if f["rule_id"] == "EXPIRY_001"), None)
    assert expiry_finding is not None
    assert expiry_finding["status"] == "flagged"
    assert "expired" in expiry_finding["title"].lower()


@pytest.mark.asyncio
async def test_scenario_4_missing_fields(client: AsyncClient):
    """Scenario 4: Building certificate missing certificate number -> missing fields finding."""
    res = await client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    app_id = res.json()["id"]

    # Upload missing fields building cert
    files = {"file": ("missing_fields_building.pdf", read_sample("missing_fields_building.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "building_completion_certificate"})

    v = await client.post(f"/api/applications/{app_id}/validate")
    assert v.status_code == 200
    report = v.json()

    field_finding = next((f for f in report["findings"] if f["rule_id"] == "FIELD_002"), None)
    assert field_finding is not None
    assert field_finding["status"] == "missing"


@pytest.mark.asyncio
async def test_scenario_5_name_mismatch(client: AsyncClient):
    """Scenario 5: Cross-document institution name mismatch -> discrepancies_found with CONSISTENCY_001 flagged."""
    res = await client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    app_id = res.json()["id"]

    # Upload mismatched fire safety
    files = {"file": ("mismatched_fire_safety.pdf", read_sample("mismatched_fire_safety.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "fire_safety_certificate"})

    files = {"file": ("valid_building_completion.pdf", read_sample("valid_building_completion.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "building_completion_certificate"})

    files = {"file": ("valid_affidavit_2.pdf", read_sample("valid_affidavit_2.pdf"), "application/pdf")}
    await client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "affidavit_2"})

    v = await client.post(f"/api/applications/{app_id}/validate")
    assert v.status_code == 200
    report = v.json()

    assert report["overall_status"] == "discrepancies_found"
    consistency_finding = next((f for f in report["findings"] if f["rule_id"] == "CONSISTENCY_001" and f["status"] == "flagged"), None)
    assert consistency_finding is not None
    assert "mismatch" in consistency_finding["title"].lower()
