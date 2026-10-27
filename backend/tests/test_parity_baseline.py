"""
Phase 0 Baseline Parity & Advanced Fixture Generation Tests.
Ensures zero regression across existing scenarios and validates deterministic synthetic test fixtures.
"""

from pathlib import Path
import json
import pytest
from httpx import AsyncClient

from tests.fixtures.generate_advanced_fixtures import generate_all_fixtures, ADVANCED_FIXTURES_DIR

SAMPLE_DIR = Path(__file__).parent / "demo_samples"


def read_sample(filename: str) -> bytes:
    path = SAMPLE_DIR / filename
    with open(path, "rb") as f:
        return f.read()


@pytest.mark.asyncio
async def test_baseline_parity_scenario_1_valid(institution_client: AsyncClient):
    """Parity baseline test: Scenario 1 (All 3 mandatory valid documents)."""
    res = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert res.status_code == 201
    app_id = res.json()["id"]

    # Upload 3 valid documents
    for doc_type, filename in [
        ("fire_safety_certificate", "valid_fire_safety.pdf"),
        ("building_completion_certificate", "valid_building_completion.pdf"),
        ("affidavit_2", "valid_affidavit_2.pdf"),
    ]:
        files = {"file": (filename, read_sample(filename), "application/pdf")}
        data = {"document_type": doc_type}
        up = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
        assert up.status_code == 201

    val = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val.status_code == 200
    report = val.json()

    assert report["overall_status"] == "checks_passed"
    assert report["summary"]["pass"] == 10
    assert report["summary"]["flagged"] == 0
    assert report["summary"]["missing"] == 0
    assert len(report["missing_document_types"]) == 0


@pytest.mark.asyncio
async def test_baseline_parity_scenario_3_expired(institution_client: AsyncClient):
    """Parity baseline test: Scenario 3 (Expired document emits flagged EXPIRY_001)."""
    res = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert res.status_code == 201
    app_id = res.json()["id"]

    for doc_type, filename in [
        ("fire_safety_certificate", "expired_fire_safety.pdf"),
        ("building_completion_certificate", "valid_building_completion.pdf"),
        ("affidavit_2", "valid_affidavit_2.pdf"),
    ]:
        files = {"file": (filename, read_sample(filename), "application/pdf")}
        data = {"document_type": doc_type}
        await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data=data)

    val = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val.status_code == 200
    report = val.json()

    assert report["overall_status"] == "discrepancies_found"
    assert report["summary"]["flagged"] >= 1
    assert any(f["rule_id"] == "EXPIRY_001" and f["status"] == "flagged" for f in report["findings"])


def test_advanced_fixtures_generation_and_integrity():
    """Generates and validates all 9 advanced synthetic fixtures."""
    fixtures = generate_all_fixtures()
    assert len(fixtures) == 9

    expected_keys = [
        "unsigned_clean",
        "metadata_anomalous",
        "incremental_save_multiple_eof",
        "qr_bearing_valid_url",
        "qr_bearing_valid_kv",
        "qr_bearing_valid_json",
        "qr_bearing_unparseable",
        "digitally_signed_valid",
        "tampered_after_signing",
    ]

    for key in expected_keys:
        assert key in fixtures
        file_path = fixtures[key]
        assert file_path.exists()
        assert file_path.stat().st_size > 0

    # 1. unsigned_clean.pdf has single %%EOF
    clean_bytes = fixtures["unsigned_clean"].read_bytes()
    assert clean_bytes.count(b"%%EOF") == 1

    # 2. incremental_save_multiple_eof.pdf has >= 3 %%EOF records
    incremental_bytes = fixtures["incremental_save_multiple_eof"].read_bytes()
    assert incremental_bytes.count(b"%%EOF") >= 3

    # 3. metadata_anomalous.pdf contains Canva in metadata
    import fitz
    doc_anomalous = fitz.open(fixtures["metadata_anomalous"])
    meta = doc_anomalous.metadata
    assert "Canva" in meta.get("creator", "")
    assert "Photoshop" in meta.get("producer", "")
    doc_anomalous.close()

    # 4. tampered_after_signing.pdf contains appended tamper marker
    tampered_bytes = fixtures["tampered_after_signing"].read_bytes()
    assert b"TAMPER_BLOCK_APPENDED_AFTER_SIGNING" in tampered_bytes
