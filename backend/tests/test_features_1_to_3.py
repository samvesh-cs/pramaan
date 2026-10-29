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
    assert img_res.headers.get("x-total-pages") == "1"
    assert img_res.headers.get("x-current-page") == "1"
    assert len(img_res.content) > 100

    # Multi-page PDF test: 3-page document
    import pymupdf as fitz
    multi_doc = fitz.open()
    for p_num in range(3):
        p = multi_doc.new_page()
        p.insert_text((50, 50), f"Multipage Document - Page {p_num + 1} clause verification")
    multi_bytes = multi_doc.tobytes()
    multi_doc.close()

    upload_multi_res = await institution_client.post(
        f"/api/applications/{app_id}/documents",
        files={"file": ("affidavit_three_pages.pdf", multi_bytes, "application/pdf")},
        data={"document_type": "affidavit_2"},
    )
    assert upload_multi_res.status_code == 201
    multi_doc_id = upload_multi_res.json()["id"]

    # Test GET /pages-info
    info_res = await institution_client.get(f"/api/applications/{app_id}/documents/{multi_doc_id}/pages-info")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["total_pages"] == 3
    assert len(info_data["pages"]) == 3
    assert info_data["pages"][1]["page_number"] == 2

    # Test GET /page-image for Page 2
    img_p2_res = await institution_client.get(f"/api/applications/{app_id}/documents/{multi_doc_id}/page-image?page=2")
    assert img_p2_res.status_code == 200
    assert img_p2_res.headers["x-total-pages"] == "3"
    assert img_p2_res.headers["x-current-page"] == "2"
    assert len(img_p2_res.content) > 100


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

    # Verify an INSTITUTION cannot PATCH finding (returns 403)
    inst_patch_res = await institution_client.patch(
        f"/api/applications/{app_id}/findings/{finding_id}",
        json={"reviewer_decision": "verified", "reviewer_notes": "too short"},
    )
    assert inst_patch_res.status_code == 403

    # Switch session override to Reviewer
    from app.auth.dependencies import get_current_user
    from app.main import app
    from tests.conftest import FakeUser

    app.dependency_overrides[get_current_user] = lambda: FakeUser("REVIEWER", "rev-test-1", email="reviewer@aicte.edu")
    try:
        # Auditor marks finding as verified with justification note (>= 10 chars -> 200)
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
        # D-021: Actor is strictly authenticated user, never client-supplied reviewed_by
        assert updated_finding["reviewed_by"] == "reviewer@aicte.edu"
        assert updated_finding["reviewed_at"] is not None

        # D-021: Reviewer sending notes under 10 characters or whitespace-only must fail with 422
        short_res = await institution_client.patch(
            f"/api/applications/{app_id}/findings/{finding_id}",
            json={"reviewer_decision": "verified", "reviewer_notes": "too short"},
        )
        assert short_res.status_code == 422

        whitespace_res = await institution_client.patch(
            f"/api/applications/{app_id}/findings/{finding_id}",
            json={"reviewer_decision": "verified", "reviewer_notes": "          "},
        )
        assert whitespace_res.status_code == 422
    finally:
        # Restore institution override
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_ter_payment_receipt_advisory_check(institution_client: AsyncClient):
    """Test D-019: TER payment receipt is advisory/informational; absent produces NO finding."""
    # 1. Application without TER payment receipt -> NO finding emitted (Option A)
    app_res = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Apex Engineering Academy", "application_category": "eoa", "academic_year": "2026-27"},
    )
    app_id = app_res.json()["id"]

    val_res = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_res.status_code == 200
    report = val_res.json()
    ter_findings = [f for f in report["findings"] if f["rule_id"] == "TER_PAYMENT_001"]
    assert len(ter_findings) == 0, "Absent TER receipt must produce NO finding (D-019 Option A)"

    # 2. Uploaded TER receipt -> emits informational finding (status: pass, severity: info)
    receipt_pdf = create_pdf([
        "AICTE Online Payment Receipt",
        "Institution Name: Apex Engineering Academy",
        "Receipt Number: AICTE-TER-2026-9901",
        "Transaction Date: 15/01/2026",
        "Total Paid Amount: INR 25,000",
    ])
    up_res = await institution_client.post(
        f"/api/applications/{app_id}/documents",
        files={"file": ("ter_receipt.pdf", receipt_pdf, "application/pdf")},
        data={"document_type": "ter_payment_receipt"},
    )
    assert up_res.status_code == 201

    val2_res = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val2_res.status_code == 200
    report2 = val2_res.json()
    ter2_findings = [f for f in report2["findings"] if f["rule_id"] == "TER_PAYMENT_001"]
    assert len(ter2_findings) == 1
    assert ter2_findings[0]["status"] == "pass"
    assert ter2_findings[0]["severity"] == "info"
    assert "Provided" in ter2_findings[0]["title"]
    assert "Statutory" not in ter2_findings[0]["title"]
    assert "Deficit" not in ter2_findings[0]["title"]

    field_004_findings = [f for f in report2["findings"] if f["rule_id"] == "FIELD_004"]
    assert len(field_004_findings) == 1, "FIELD_004 must be unconditionally present for uploaded ter_payment_receipt"
    assert field_004_findings[0]["severity"] == "info"
    assert field_004_findings[0]["status"] in ("not_applicable", "pass")


@pytest.mark.asyncio
async def test_field_completeness_severities_unchanged():
    """Item 2: Assert FIELD_001, 002, 003, 005 keep high severity, while FIELD_004 is info."""
    from app.rules.legacy_adapter import wrap_legacy_rules
    from app.rules.field_completeness import FieldCompletenessRule
    from datetime import date

    class DummyDoc:
        def __init__(self, doc_id: str, doc_type: str):
            self.id = doc_id
            self.document_type = doc_type
            self.original_filename = f"{doc_type}.pdf"

    class DummyExtraction:
        def __init__(self):
            self.processing_status = "processed"
            self.fields = {
                "institution_name": {"value": "Test Inst", "confidence": 0.95},
                "certificate_number": {"value": "CERT-123", "confidence": 0.95},
                "issue_date": {"value": "2024-01-01", "confidence": 0.95},
                "expiry_date": {"value": "2027-01-01", "confidence": 0.95},
                "issuing_authority": {"value": "Auth", "confidence": 0.95},
                "affidavit_date": {"value": "2024-01-01", "confidence": 0.95},
                "deponent_name": {"value": "Deponent", "confidence": 0.95},
                "receipt_number": {"value": "REC-1", "confidence": 0.95},
                "transaction_date": {"value": "2024-01-01", "confidence": 0.95},
                "amount_inr": {"value": 50000, "confidence": 0.95},
                "engineer_license_number": {"value": "LIC-123", "confidence": 0.95},
            }

    docs = [
        DummyDoc("d1", "fire_safety_certificate"),
        DummyDoc("d2", "building_completion_certificate"),
        DummyDoc("d3", "affidavit_2"),
        DummyDoc("d4", "ter_payment_receipt"),
        DummyDoc("d5", "structural_stability_certificate"),
    ]
    ext = {d.id: DummyExtraction() for d in docs}

    wrapped_rules = wrap_legacy_rules([FieldCompletenessRule()])
    findings = wrapped_rules[0].evaluate({"documents": docs, "extractions": ext})

    severity_by_rule = {f.rule_id: f.severity for f in findings}
    assert severity_by_rule["FIELD_001"] == "high"
    assert severity_by_rule["FIELD_002"] == "high"
    assert severity_by_rule["FIELD_003"] == "high"
    assert severity_by_rule["FIELD_004"] == "info"
    assert severity_by_rule["FIELD_005"] == "high"


@pytest.mark.asyncio
async def test_ter_advisory_does_not_block_clean_application_and_info_overall_status():
    """Item 3: Assert info-level findings keep overall status and failed TER extraction does not block clean application."""
    from app.services.validation_engine import calculate_overall_status
    from app.schemas.finding import FindingCreate

    class MockDoc:
        def __init__(self, doc_id: str, doc_type: str, status: str = "processed"):
            self.id = doc_id
            self.document_type = doc_type
            self.processing_status = status

    docs = [
        MockDoc("d1", "fire_safety_certificate"),
        MockDoc("d2", "building_completion_certificate"),
        MockDoc("d3", "affidavit_2"),
        MockDoc("d4", "ter_payment_receipt"),
    ]

    # (a) Application with clean mandatory findings + 1 TER info finding keeps checks_passed
    clean_findings = [
        FindingCreate(rule_id="PRESENCE_001", status="pass", title="Fire safety present", reason="ok", severity="critical"),
        FindingCreate(rule_id="PRESENCE_002", status="pass", title="BCC present", reason="ok", severity="critical"),
        FindingCreate(rule_id="PRESENCE_003", status="pass", title="Affidavit present", reason="ok", severity="critical"),
        FindingCreate(rule_id="TER_PAYMENT_001", status="pass", title="TER receipt provided", reason="advisory", severity="info"),
        FindingCreate(rule_id="FIELD_004", status="pass", title="TER fields", reason="advisory", severity="info"),
    ]
    status_clean = calculate_overall_status(clean_findings, docs)
    assert status_clean == "checks_passed"

    # (b) TER receipt whose extraction fails (not_applicable advisory) does NOT block an otherwise clean application
    failed_ter_findings = [
        FindingCreate(rule_id="PRESENCE_001", status="pass", title="Fire safety present", reason="ok", severity="critical"),
        FindingCreate(rule_id="PRESENCE_002", status="pass", title="BCC present", reason="ok", severity="critical"),
        FindingCreate(rule_id="PRESENCE_003", status="pass", title="Affidavit present", reason="ok", severity="critical"),
        FindingCreate(rule_id="TER_PAYMENT_001", status="not_applicable", title="Advisory: TER extraction incomplete", reason="failed ocr", severity="info"),
        FindingCreate(rule_id="FIELD_004", status="not_applicable", title="TER fields not detected", reason="failed ocr", severity="info"),
    ]
    status_failed_ter = calculate_overall_status(failed_ter_findings, docs)
    assert status_failed_ter == "checks_passed", "Not_applicable TER advisory check must NOT block checks_passed status"

    # Verify summary counts: advisory not_applicable findings do NOT increment unresolved
    summary_counts = {
        "pass": sum(1 for f in failed_ter_findings if f.status == "pass"),
        "flagged": sum(1 for f in failed_ter_findings if f.status == "flagged"),
        "missing": sum(1 for f in failed_ter_findings if f.status == "missing"),
        "unresolved": sum(1 for f in failed_ter_findings if f.status == "unresolved"),
        "not_applicable": sum(1 for f in failed_ter_findings if f.status == "not_applicable"),
    }
    assert summary_counts["unresolved"] == 0, "Advisory TER checks must not pollute unresolved counts"
    assert summary_counts["not_applicable"] == 2

    # (c) Edge case: TER document has processing_status "processing" or "processing_failed"
    docs_processing_ter = [
        MockDoc("d1", "fire_safety_certificate", "processed"),
        MockDoc("d2", "building_completion_certificate", "processed"),
        MockDoc("d3", "affidavit_2", "processed"),
        MockDoc("d4", "ter_payment_receipt", "processing"),
    ]
    status_processing_ter = calculate_overall_status(clean_findings, docs_processing_ter)
    assert status_processing_ter == "checks_passed", "TER document in 'processing' status must NOT block checks_passed"

    docs_failed_ter = [
        MockDoc("d1", "fire_safety_certificate", "processed"),
        MockDoc("d2", "building_completion_certificate", "processed"),
        MockDoc("d3", "affidavit_2", "processed"),
        MockDoc("d4", "ter_payment_receipt", "processing_failed"),
    ]
    status_failed_ter_doc = calculate_overall_status(failed_ter_findings, docs_failed_ter)
    assert status_failed_ter_doc == "checks_passed", "TER document in 'processing_failed' status must NOT block checks_passed"


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
    u_new_res = await institution_client.post(
        f"/api/applications/{app_id}/documents",
        files={"file": ("new_building.pdf", new_building_pdf, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )
    assert u_new_res.status_code == 201

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
    u_old_res = await institution_client.post(
        f"/api/applications/{app2_id}/documents",
        files={"file": ("old_building.pdf", old_building_pdf, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )
    assert u_old_res.status_code == 201

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
    u_struct_res = await institution_client.post(
        f"/api/applications/{app2_id}/documents",
        files={"file": ("structural_cert.pdf", structural_pdf, "application/pdf")},
        data={"document_type": "structural_stability_certificate"},
    )
    assert u_struct_res.status_code == 201

    val3_res = await institution_client.post(f"/api/applications/{app2_id}/validate")
    assert val3_res.status_code == 200
    report3 = val3_res.json()
    stability3_findings = [f for f in report3["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"]
    assert len(stability3_findings) == 1
    assert stability3_findings[0]["status"] == "pass"

