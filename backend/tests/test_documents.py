import io
import pytest
import pymupdf
from httpx import AsyncClient


def create_dummy_pdf(text: str = "Dummy Test Document") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_upload_valid_pdf_document(institution_client: AsyncClient):
    # Create application
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Synthetic ABC Engineering College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    pdf_bytes = create_dummy_pdf("Fire Safety Certificate for Synthetic ABC Engineering College")
    files = {"file": ("fire_cert.pdf", pdf_bytes, "application/pdf")}
    data = {"document_type": "fire_safety_certificate"}

    res = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
    assert res.status_code == 201
    doc_data = res.json()
    assert doc_data["application_id"] == app_id
    assert doc_data["document_type"] == "fire_safety_certificate"
    assert doc_data["original_filename"] == "fire_cert.pdf"
    assert doc_data["mime_type"] == "application/pdf"
    assert doc_data["processing_status"] in ("processed", "uploaded", "processing")


@pytest.mark.asyncio
async def test_upload_unsupported_file_extension(institution_client: AsyncClient):
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Test College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    files = {"file": ("test.exe", b"binary content", "application/octet-stream")}
    data = {"document_type": "fire_safety_certificate"}

    res = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
    assert res.status_code == 400
    err = res.json().get("error")
    assert err is not None
    assert err["code"] == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.asyncio
async def test_upload_invalid_document_type(institution_client: AsyncClient):
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Test College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    pdf_bytes = create_dummy_pdf("Test Content")
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    data = {"document_type": "unsupported_category_doc"}

    res = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data=data)
    assert res.status_code == 400
    err = res.json().get("error")
    assert err is not None
    assert err["code"] == "INVALID_DOCUMENT_TYPE"


@pytest.mark.asyncio
async def test_list_documents(institution_client: AsyncClient):
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Test College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    pdf_bytes = create_dummy_pdf("Building Certificate")
    files = {"file": ("bcc.pdf", pdf_bytes, "application/pdf")}
    data = {"document_type": "building_completion_certificate"}

    await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data=data)

    list_res = await institution_client.get(f"/api/applications/{app_id}/documents")
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) == 1
    assert docs[0]["document_type"] == "building_completion_certificate"

