import pymupdf
import pytest
from httpx import AsyncClient


def create_pdf(text_lines: list[str]) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 50
    for line in text_lines:
        page.insert_text((50, y), line)
        y += 25
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_document_file_streaming(institution_client: AsyncClient):
    """Feature 2: Test GET /api/applications/{app_id}/documents/{doc_id}/file."""
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Test College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    pdf_bytes = create_pdf(["AICTE EoA Fire Safety Certificate", "Institution Name: Test College"])
    files = {"file": ("fire_safety.pdf", pdf_bytes, "application/pdf")}
    upload_res = await institution_client.post(
        f"/api/applications/{app_id}/documents",
        files=files,
        data={"document_type": "fire_safety_certificate"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Stream file
    stream_res = await institution_client.get(f"/api/applications/{app_id}/documents/{doc_id}/file")
    assert stream_res.status_code == 200
    assert stream_res.headers["content-type"] == "application/pdf"
    assert "inline" in stream_res.headers.get("content-disposition", "")
    assert stream_res.content == pdf_bytes

    # Render page image for visual evidence overlay
    img_res = await institution_client.get(f"/api/applications/{app_id}/documents/{doc_id}/page-image?page=1")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert "x-page-width" in img_res.headers
    assert "x-page-height" in img_res.headers
    assert len(img_res.content) > 100


@pytest.mark.asyncio
async def test_auditor_review_finding_and_status_recalculation(institution_client: AsyncClient):
    """Feature 1: Test PATCH /api/applications/{app_id}/findings/{finding_id}."""
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Review College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    from app.models.document import Document
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        for index, document_type in enumerate((
            "fire_safety_certificate",
            "building_completion_certificate",
            "affidavit_2",
        )):
            db.add(Document(
                id=f"review-test-doc-{index}",
                application_id=app_id,
                document_type=document_type,
                original_filename=f"synthetic-{document_type}.pdf",
                stored_filename=f"synthetic-{document_type}.pdf",
                mime_type="application/pdf",
                file_size_bytes=100,
                processing_status="uploaded",
            ))
        await db.commit()

    # Validate the submitted file set -> produces reviewable findings
    val_res = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    assert report["overall_status"] == "processing_incomplete"
    assert report["findings"]
    reviewable_findings = [finding for finding in report["findings"] if finding["requires_reviewer_decision"]]
    assert reviewable_findings
    finding_id = reviewable_findings[0]["id"]

    # Institution submits application so reviewer can review it
    submit_res = await institution_client.post(f"/api/applications/{app_id}/submit")
    assert submit_res.status_code == 200

    # Switch session override to Reviewer
    from app.auth.dependencies import get_current_user
    from app.main import app
    from tests.conftest import FakeUser

    app.dependency_overrides[get_current_user] = lambda: FakeUser("REVIEWER", "rev-test-1", email="reviewer@aicte.edu")

    # Auditor marks finding as verified with justification note
    patch_res = await institution_client.patch(
        f"/api/applications/{app_id}/findings/{finding_id}",
        json={
            "reviewer_decision": "verified",
            "reviewer_notes": "Physically verified original document at regional office.",
            "reviewed_by": "Dr. A. Sharma (Scrutiny Committee)",
        },
    )
    assert patch_res.status_code == 200
    updated_finding = patch_res.json()
    assert updated_finding["reviewer_decision"] == "verified"
    assert updated_finding["reviewer_notes"] == "Physically verified original document at regional office."
    assert updated_finding["reviewed_by"] == "reviewer@aicte.edu"
    assert updated_finding["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_ter_payment_check_underpaid_and_paid(institution_client: AsyncClient):
    """Feature 3A: Test TER_PAYMENT_001 with underpaid amount vs valid amount."""
    # 1. Underpaid TER payment (₹25,000 paid for private institution which needs ₹1,00,000)
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Apex Engineering Academy", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    underpaid_pdf = create_pdf([
        "AICTE Online Payment Receipt",
        "Institution Name: Apex Engineering Academy",
        "Receipt Number: AICTE-TER-2026-9901",
        "Transaction Date: 15/01/2026",
        "Total Paid Amount: INR 25,000",
    ])
    up_res = await institution_client.post(
        f"/api/applications/{app_id}/documents",
        files={"file": ("ter_receipt_underpaid.pdf", underpaid_pdf, "application/pdf")},
        data={"document_type": "ter_payment_receipt"},
    )
    assert up_res.status_code == 201

    val_res = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    ter_findings = [f for f in report["findings"] if f["rule_id"] == "TER_PAYMENT_001"]
    assert len(ter_findings) == 1
    assert ter_findings[0]["status"] == "flagged"
    assert "Deficit" in ter_findings[0]["title"]

    # 2. Paid in full TER payment (₹1,00,000 paid)
    app2_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Apex Engineering Academy", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app2_id = app2_res.json()["id"]

    full_paid_pdf = create_pdf([
        "AICTE Online Payment Receipt",
        "Institution Name: Apex Engineering Academy",
        "Receipt Number: AICTE-TER-2026-9902",
        "Transaction Date: 15/01/2026",
        "Total Paid Amount: INR 1,00,000",
    ])
    await institution_client.post(
        f"/api/applications/{app2_id}/documents",
        files={"file": ("ter_receipt_full.pdf", full_paid_pdf, "application/pdf")},
        data={"document_type": "ter_payment_receipt"},
    )

    val2_res = await institution_client.post(f"/api/applications/{app2_id}/validate")
    assert val2_res.status_code == 200
    report2 = val2_res.json()
    ter2_findings = [f for f in report2["findings"] if f["rule_id"] == "TER_PAYMENT_001"]
    assert len(ter2_findings) == 1
    assert ter2_findings[0]["status"] == "pass"


@pytest.mark.asyncio
async def test_building_age_structural_stability_rule(institution_client: AsyncClient):
    """Feature 3B: Test STRUCTURAL_STABILITY_001 under 30 yrs (not_applicable) vs over 30 yrs (missing -> pass)."""
    # 1. New Building (Issued 2018 -> age < 30 years -> not_applicable)
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Apex Institute", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    new_building_pdf = create_pdf([
        "Municipal Corporation Building Completion Certificate",
        "Institution Name: Apex Institute",
        "Certificate Number: BCC-2018-004",
        "Issue Date: 12/06/2018",
        "Issuing Authority: Municipal Corporation",
    ])
    await institution_client.post(
        f"/api/applications/{app_id}/documents",
        files={"file": ("new_building.pdf", new_building_pdf, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )

    val_res = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    stability_findings = [f for f in report["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"]
    assert len(stability_findings) == 1
    assert stability_findings[0]["status"] == "not_applicable"

    # 2. Old Building (Issued 1985 -> age > 30 years -> missing structural certificate)
    app2_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Heritage Engineering College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app2_id = app2_res.json()["id"]

    old_building_pdf = create_pdf([
        "Building Completion Certificate - Heritage Engineering College",
        "Town Planning Authority - Historical Structure Scrutiny Division",
        "Certificate Number: BCC-1985-001",
        "Issue Date: 10/04/1985",
        "Issuing Authority: Town Planning Department",
        "Approved Construction Plan Reference: TPD/85/0984/C",
        "Total Built Up Area Approved: 12,450 Square Metres",
        "Number of Floors: Ground Plus Three Floors",
        "Architect In-Charge: Somnath & Associates Reg No CA/82/1004",
        "Structural Engineer: P. K. Sharma & Partners Consulting",
        "Occupancy Sanctioned Under Section 45(1) Municipal Act",
    ])
    await institution_client.post(
        f"/api/applications/{app2_id}/documents",
        files={"file": ("old_building.pdf", old_building_pdf, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )

    val2_res = await institution_client.post(f"/api/applications/{app2_id}/validate")
    assert val2_res.status_code == 200
    report2 = val2_res.json()
    stability2_findings = [f for f in report2["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"]
    assert len(stability2_findings) == 1
    assert stability2_findings[0]["status"] == "missing"
    assert "structural_stability_certificate" in report2["missing_document_types"]

    # 3. Upload Structural Stability Certificate -> now passes!
    structural_pdf = create_pdf([
        "Structural Stability & Soundness Audit Certificate",
        "Institution Name: Heritage Engineering College",
        "Certificate Number: SSC-2026-ENG-44",
        "Chartered Engineer Registration Number: CE-STR-99881",
        "Date of Inspection: 05/01/2026",
        "Building Foundation & Reinforced Concrete Column Inspection Completed",
        "Non-Destructive Testing (NDT) Rebound Hammer Value: Adequate",
        "Structure is Certified Safe and Fit for Educational Occupancy",
        "Empanelled Structural Auditor: Dr. V. R. Deshmukh M.Tech Ph.D FIE",
    ])
    await institution_client.post(
        f"/api/applications/{app2_id}/documents",
        files={"file": ("structural_cert.pdf", structural_pdf, "application/pdf")},
        data={"document_type": "structural_stability_certificate"},
    )

    val3_res = await institution_client.post(f"/api/applications/{app2_id}/validate")
    assert val3_res.status_code == 200
    report3 = val3_res.json()
    stability3_findings = [f for f in report3["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"]
    assert len(stability3_findings) == 1
    assert stability3_findings[0]["status"] == "pass"

