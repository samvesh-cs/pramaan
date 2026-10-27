from datetime import date, timedelta
import pytest
import pymupdf
from httpx import AsyncClient

from app.rules.cross_document_check import InstitutionNameConsistencyRule, text_similarity
from app.rules.expiry_check import ExpiryDateRule
from app.rules.field_completeness import FieldCompletenessRule
from app.rules.presence_check import DocumentPresenceRule
from app.services.validation_engine import calculate_overall_status


def create_dummy_pdf(text: str = "Test Content") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_validation_missing_documents(institution_client: AsyncClient):
    # Create application without documents
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Synthetic ABC College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    # Run validation
    val_res = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    assert report["overall_status"] == "processing_incomplete"
    assert len(report["missing_document_types"]) == 3
    assert report["summary"]["missing"] >= 3


@pytest.mark.asyncio
async def test_validation_with_present_documents_and_unextractable_fields_does_not_pass(institution_client: AsyncClient):
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Synthetic ABC Engineering College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    # Upload all 3 documents
    doc_types = ["fire_safety_certificate", "building_completion_certificate", "affidavit_2"]
    for dt in doc_types:
        pdf_bytes = create_dummy_pdf(f"Content for {dt}")
        files = {"file": (f"{dt}.pdf", pdf_bytes, "application/pdf")}
        data = {"document_type": dt}
        upload_res = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
        assert upload_res.status_code == 201

    # Validate
    val_res = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    assert len(report["missing_document_types"]) == 0
    # Presence does not substitute for extracted evidence. The old synthetic fallback
    # values were removed, so these generic PDFs must not pass field or expiry checks.
    assert report["summary"]["missing"] > 0
    assert report["overall_status"] == "missing_documents"


@pytest.mark.asyncio
async def test_expiry_date_rule_unit():
    rule = ExpiryDateRule()

    class MockDoc:
        id = "doc_1"
        document_type = "fire_safety_certificate"
        original_filename = "fire.pdf"

    class MockExtraction:
        processing_status = "processed"
        fields = {
            "expiry_date": {
                "value": (date.today() - timedelta(days=10)).isoformat(),
                "page_number": 1,
                "raw_text": "Valid Until: 2025-01-01",
                "bbox": [100, 200, 300, 250],
            }
        }

    context = {
        "documents": [MockDoc()],
        "extractions": {"doc_1": MockExtraction()},
        "reference_date": date.today(),
    }

    findings = rule.evaluate(context)
    assert len(findings) == 1
    assert findings[0].status == "flagged"
    assert findings[0].rule_id == "EXPIRY_001"
    assert "expired" in findings[0].title.lower()


@pytest.mark.asyncio
async def test_institution_name_mismatch_unit():
    rule = InstitutionNameConsistencyRule()

    class MockApp:
        institution_name = "Government Engineering College Salem"

    class MockDoc:
        id = "doc_2"
        document_type = "building_completion_certificate"
        original_filename = "bcc.pdf"

    class MockExtraction:
        processing_status = "processed"
        fields = {
            "institution_name": {
                "value": "Private Institute of Technology Chennai",
                "page_number": 1,
                "raw_text": "Institution: Private Institute of Technology Chennai",
                "bbox": [100, 100, 400, 150],
            }
        }

    context = {
        "application": MockApp(),
        "documents": [MockDoc()],
        "extractions": {"doc_2": MockExtraction()},
    }

    findings = rule.evaluate(context)
    assert len(findings) == 1
    assert findings[0].status == "flagged"
    assert findings[0].rule_id == "CONSISTENCY_001"
    assert "mismatch" in findings[0].title.lower()


@pytest.mark.asyncio
async def test_low_confidence_required_field_is_unresolved():
    rule = FieldCompletenessRule()

    class MockDoc:
        id = "doc_low_confidence"
        document_type = "fire_safety_certificate"
        original_filename = "fire.pdf"

    class MockExtraction:
        processing_status = "processed"
        fields = {
            "institution_name": {"value": "Synthetic ABC Engineering College", "confidence": 0.92},
            "certificate_number": {"value": "FS-2026-100", "confidence": 0.64},
            "issue_date": {"value": "2026-01-01", "confidence": 0.90},
            "expiry_date": {"value": "2027-01-01", "confidence": 0.90},
            "issuing_authority": {"value": "Fire Services", "confidence": 0.88},
        }

    findings = rule.evaluate({
        "documents": [MockDoc()],
        "extractions": {"doc_low_confidence": MockExtraction()},
    })

    assert len(findings) == 1
    assert findings[0].status == "unresolved"
    assert "certificate_number" in findings[0].evidence["fields"]


@pytest.mark.asyncio
async def test_get_report_endpoint(institution_client: AsyncClient):
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Synthetic ABC Engineering College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    # Validate first
    await institution_client.post(f"/api/applications/{app_id}/validate")

    # Fetch report
    report_res = await institution_client.get(f"/api/applications/{app_id}/report")
    assert report_res.status_code == 200
    report = report_res.json()
    assert report["application_id"] == app_id
    assert "summary" in report
    assert "findings" in report

