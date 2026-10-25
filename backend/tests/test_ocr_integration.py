from pathlib import Path
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_e2e_real_sample_fire_safety(client: AsyncClient):
    sample_path = Path("tests/samples/clean_fire_safety.pdf")
    if not sample_path.exists():
        pytest.skip("Synthetic sample not found")

    with open(sample_path, "rb") as f:
        pdf_bytes = f.read()

    # 1. Create application matching sample institution
    app_res = await client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert app_res.status_code == 201
    app_id = app_res.json()["id"]

    # 2. Upload real clean fire safety PDF
    files = {"file": ("clean_fire_safety.pdf", pdf_bytes, "application/pdf")}
    data = {"document_type": "fire_safety_certificate"}
    upload_res = await client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["processing_status"] == "processed"
    assert doc_data["fields"]["institution_name"]["value"] == "Synthetic ABC Institute of Technology"
    assert doc_data["fields"]["institution_name"]["status"] == "extracted"

    application_res = await client.get(f"/api/applications/{app_id}")
    assert application_res.status_code == 200
    assert application_res.json()["documents"][0]["fields"]["institution_name"]["value"] == "Synthetic ABC Institute of Technology"

    # 3. Trigger validation
    val_res = await client.post(f"/api/applications/{app_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()

    # 4. Check findings on the fire safety certificate
    findings = report["findings"]
    fire_presence = next((f for f in findings if f["rule_id"] == "PRESENCE_001"), None)
    assert fire_presence is not None
    assert fire_presence["status"] == "pass"

    fire_expiry = next((f for f in findings if f["rule_id"] == "EXPIRY_001"), None)
    assert fire_expiry is not None
    # clean_fire_safety.pdf has expiry in 2027, so it must pass
    assert fire_expiry["status"] == "pass"
    assert "valid" in fire_expiry["title"].lower()

    fire_consistency = next((f for f in findings if f["rule_id"] == "CONSISTENCY_001"), None)
    assert fire_consistency is not None
    assert fire_consistency["status"] == "pass"
