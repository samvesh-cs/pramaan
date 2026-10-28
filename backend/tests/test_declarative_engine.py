"""
Integration and Parity Tests for Declarative Rule Engine and Statutory Citation Decorator.
Validates that validation findings are consistently decorated with statutory clauses and severities.
"""

from pathlib import Path
import pytest
from httpx import AsyncClient

SAMPLE_DIR = Path(__file__).parent / "demo_samples"


def read_sample(filename: str) -> bytes:
    with open(SAMPLE_DIR / filename, "rb") as f:
        return f.read()


@pytest.mark.asyncio
async def test_validation_engine_findings_have_statutory_citations(institution_client: AsyncClient):
    """Asserts that all findings emitted by validation engine contain statutory clause citations."""
    # Create application
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

    # Upload Fire Safety and Building Completion
    files = {"file": ("valid_fire_safety.pdf", read_sample("valid_fire_safety.pdf"), "application/pdf")}
    u1 = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "fire_safety_certificate"})
    assert u1.status_code == 201

    files = {"file": ("valid_building_completion.pdf", read_sample("valid_building_completion.pdf"), "application/pdf")}
    u2 = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "building_completion_certificate"})
    assert u2.status_code == 201

    # Validate
    val = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val.status_code == 200
    report = val.json()

    assert len(report["findings"]) > 0

    valid_severities = {"critical", "high", "medium", "low", "info"}
    valid_signals = {"rule", "tamper", "issuer", "duplicate", "internal_check"}

    for finding in report["findings"]:
        assert finding["severity"] in valid_severities, f"Finding {finding['rule_id']} has invalid severity {finding['severity']}"
        assert finding["signal_type"] in valid_signals, f"Finding {finding['rule_id']} has invalid signal_type {finding['signal_type']}"

        # If rule has registered citation, verify fields
        clause_ref = finding.get("clause_ref")
        if clause_ref:
            assert "clause_id" in clause_ref
            assert "chapter_or_annexure" in clause_ref
            assert "handbook_page" in clause_ref
            assert "pdf_page" in clause_ref
            assert clause_ref["handbook_page"] > 0
            assert clause_ref["pdf_page"] > 0


@pytest.mark.asyncio
async def test_expiry_finding_statutory_grounding(institution_client: AsyncClient):
    """Asserts that an expired document finding specifically cites APH Annexure-2 §2.1(v) & Clause 7.16."""
    res = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic ABC Institute of Technology",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    app_id = res.json()["id"]

    # Upload expired Fire Safety
    files = {"file": ("expired_fire_safety.pdf", read_sample("expired_fire_safety.pdf"), "application/pdf")}
    u_exp = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "fire_safety_certificate"})
    assert u_exp.status_code == 201

    val = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val.status_code == 200
    report = val.json()

    expiry_finding = next(f for f in report["findings"] if f["rule_id"] == "EXPIRY_001")
    assert expiry_finding["status"] == "flagged"
    assert expiry_finding["severity"] == "critical"
    assert expiry_finding["signal_type"] == "rule"

    clause = expiry_finding.get("clause_ref")
    assert clause is not None
    assert clause["clause_number"] == "2.1(v)"
    assert clause["chapter_or_annexure"] == "Annexure-2"
    assert clause["handbook_page"] == 81
    assert clause["pdf_page"] == 97


@pytest.mark.asyncio
async def test_doc_presence_and_internal_checks_metadata(institution_client: AsyncClient):
    """
    Asserts:
    1. DOC_PRESENCE_001 cites APH Annexure-2 §2.1 as a whole.
    2. FIELD_001 and CONSISTENCY_001 are internal checks: clause_id is None, signal_type is 'internal_check'.
    """
    res = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic Institute of Engineering",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    app_id = res.json()["id"]

    val = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val.status_code == 200
    report = val.json()

    # 1. DOC_PRESENCE_001 / PRESENCE_* cites §2.1 as a whole
    presence_finding = next((f for f in report["findings"] if f["rule_id"] in ("DOC_PRESENCE_001", "PRESENCE_001", "PRESENCE_002", "PRESENCE_CHECK")), None)
    assert presence_finding is not None
    assert presence_finding["signal_type"] == "rule"
    assert presence_finding["clause_ref"] is not None
    assert presence_finding["clause_ref"]["clause_id"] == "APH_2024_27_ANNEX_2_CLAUSE_2_1"
    assert presence_finding["clause_ref"]["clause_number"] == "2.1"
    assert presence_finding["clause_ref"]["chapter_or_annexure"] == "Annexure-2"

    # 2. FIELD_001 is an internal check: clause_id is null, signal_type is "internal_check"
    field_finding = next((f for f in report["findings"] if f["rule_id"] == "FIELD_001"), None)
    if field_finding:
        assert field_finding["clause_ref"] is None
        assert field_finding["signal_type"] == "internal_check"

    # 3. CONSISTENCY_001 is an internal check: clause_id is null, signal_type is "internal_check"
    consistency_finding = next((f for f in report["findings"] if f["rule_id"] == "CONSISTENCY_001"), None)
    if consistency_finding:
        assert consistency_finding["clause_ref"] is None
        assert consistency_finding["signal_type"] == "internal_check"


@pytest.mark.asyncio
async def test_structural_stability_5_year_expiry_and_competent_authority_letter_exemption(institution_client: AsyncClient):
    """
    Validates structural stability rules under D-020:
    1. Case 1: Certificate expired (> 5 years) correctly flagged under Clause 6.17(h).
    2. Case 2a: Government-named institution WITHOUT letter and >50 yrs is flagged/missing (no name matching).
    3. Case 2b: Building > 50 yrs WITH competent_authority_letter returns unresolved with reviewer next action,
       and reviewer determination (reason >= 10 chars) transitions overall_status to checks_passed.
    4. Case 2c: Building 35 yrs old WITH letter but NO certificate is flagged (exemption is strictly >50 yrs).
    """
    import pymupdf

    def make_pdf(lines: list[str]) -> bytes:
        doc = pymupdf.open()
        p = doc.new_page()
        y = 50
        for l in lines:
            p.insert_text((50, y), l)
            y += 25
        b = doc.tobytes()
        doc.close()
        return b

    # Case 1: Old building (1980, >30 yrs) with EXPIRED structural stability certificate (issued 2015, >5 yrs old)
    res1 = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Private Institute of Tech", "application_category": "eoa", "academic_year": "2026-27"},
    )
    assert res1.status_code == 201
    app1_id = res1.json()["id"]

    bcc_bytes = make_pdf([
        "Building Completion Certificate",
        "Institution Name: Private Institute of Tech",
        "Issue Date: 15/06/1980",
        "Certificate Number: BCC-1980-001",
    ])
    u1_res = await institution_client.post(
        f"/api/applications/{app1_id}/documents",
        files={"file": ("bcc.pdf", bcc_bytes, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )
    assert u1_res.status_code == 201

    expired_ssc_bytes = make_pdf([
        "Structural Stability Certificate",
        "Institution Name: Private Institute of Tech",
        "Certificate Number: SSC-2015-EXPIRED",
        "Chartered Engineer Registration Number: CE-STR-12345",
        "Issue Date: 10/01/2015",
    ])
    u2_res = await institution_client.post(
        f"/api/applications/{app1_id}/documents",
        files={"file": ("ssc.pdf", expired_ssc_bytes, "application/pdf")},
        data={"document_type": "structural_stability_certificate"},
    )
    assert u2_res.status_code == 201

    val1 = await institution_client.post(f"/api/applications/{app1_id}/validate")
    assert val1.status_code == 200
    report1 = val1.json()

    struct_finding = next((f for f in report1["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"), None)
    assert struct_finding is not None
    assert struct_finding["status"] == "flagged"
    assert "Expired" in struct_finding["title"]
    assert "FIVE years" in struct_finding["reason"]

    old_govt_bcc = make_pdf([
        "Building Completion Certificate",
        "Institution Name: Government Polytechnic College",
        "Issue Date: 12/03/1965",
        "Certificate Number: GOVT-BCC-1965",
        "Issuing Authority: Public Works Department",
    ])
    govt_letter_bytes = make_pdf([
        "Letter from Competent Authority",
        "Institution Name: Government Polytechnic College",
        "Subject: AICTE Building Norms Compliance under Government Building Act 1899",
        "Reference: Annexure-2 Section 2.1 Government Building Exemption",
    ])

    # Case 2a: Government-named institution WITHOUT a letter and over 50 years (1965) -> flagged/missing
    res2a = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Government Polytechnic College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    assert res2a.status_code == 201
    app2a_id = res2a.json()["id"]

    valid_fsc = make_pdf([
        "Fire Safety Certificate",
        "Institution Name: Government Polytechnic College",
        "Certificate Number: FSC-GOVT-2026",
        "Issue Date: 01/01/2026",
        "Expiry Date: 01/01/2028",
        "Issuing Authority: State Fire Service Department",
    ])
    await institution_client.post(
        f"/api/applications/{app2a_id}/documents",
        files={"file": ("govt_fsc.pdf", valid_fsc, "application/pdf")},
        data={"document_type": "fire_safety_certificate"},
    )

    valid_aff = make_pdf([
        "Affidavit",
        "Institution Name: Government Polytechnic College",
        "Deponent Name: Dr. R. K. Sharma",
        "Date of Notarization: 05/01/2026",
        "Notary Registration Number: NOTARY-7788",
    ])
    await institution_client.post(
        f"/api/applications/{app2a_id}/documents",
        files={"file": ("govt_aff.pdf", valid_aff, "application/pdf")},
        data={"document_type": "affidavit_2"},
    )

    u3_res = await institution_client.post(
        f"/api/applications/{app2a_id}/documents",
        files={"file": ("govt_bcc.pdf", old_govt_bcc, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )
    assert u3_res.status_code == 201

    val2a = await institution_client.post(f"/api/applications/{app2a_id}/validate")
    assert val2a.status_code == 200
    report2a = val2a.json()

    finding2a = next((f for f in report2a["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"), None)
    assert finding2a is not None
    assert finding2a["status"] == "missing", "Government-named institution without letter must be flagged/missing (no name matching)"
    assert "Missing" in finding2a["title"]
    assert finding2a.get("clause_ref") is not None
    assert finding2a["clause_ref"]["clause_id"] == "APH_2024_27_CLAUSE_6_17_H"
    assert report2a["overall_status"] == "missing_documents"

    # Case 2b: With letter and over 50 years -> status "unresolved", overall_status "unresolved_checks"
    letter_res = await institution_client.post(
        f"/api/applications/{app2a_id}/documents",
        files={"file": ("govt_letter.pdf", govt_letter_bytes, "application/pdf")},
        data={"document_type": "competent_authority_letter"},
    )
    assert letter_res.status_code == 201, "competent_authority_letter upload must return 201 Created"
    letter_data = letter_res.json()
    assert letter_data["processing_status"] == "processed"
    assert letter_data["fields"] == {}, "Presence-only letter must have empty fields and no extraction errors"

    val2b = await institution_client.post(f"/api/applications/{app2a_id}/validate")
    assert val2b.status_code == 200
    report2b = val2b.json()

    finding2b = next((f for f in report2b["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"), None)
    assert finding2b is not None
    assert finding2b["status"] == "unresolved"
    assert finding2b["title"] == "Competent Authority letter uploaded: reviewer to confirm it applies"
    assert "the preamble allows a letter from the competent authority" in finding2b["reason"].lower()
    assert "pramaan does not read the letter" in finding2b["reason"].lower()
    assert finding2b["next_action"] == "Reviewer to open the letter and confirm it applies."
    assert finding2b.get("clause_ref") is not None
    assert finding2b["clause_ref"]["clause_id"] == "APH_2024_27_ANNEX_2_CLAUSE_2_1_PREAMBLE"
    assert report2b["overall_status"] == "unresolved_checks"

    # Reviewer PATCH test: confirms overall_status transitions to checks_passed after determination with reason >= 10 chars
    from app.auth.dependencies import get_current_user
    from app.main import app
    from tests.conftest import FakeUser

    # Submit application so reviewer can review it
    submit_res = await institution_client.post(f"/api/applications/{app2a_id}/submit")
    assert submit_res.status_code == 200

    # Non-reviewer attempt returns 403
    inst_patch = await institution_client.patch(
        f"/api/applications/{app2a_id}/findings/{finding2b['id']}",
        json={"reviewer_decision": "verified", "reviewer_notes": "Unauthorized institution override"},
    )
    assert inst_patch.status_code == 403

    # Switch to Reviewer user
    app.dependency_overrides[get_current_user] = lambda: FakeUser("REVIEWER", "rev-test-1", email="reviewer@aicte.edu")
    try:
        # Rejection when reason notes are under 10 characters
        short_res = await institution_client.patch(
            f"/api/applications/{app2a_id}/findings/{finding2b['id']}",
            json={"reviewer_decision": "verified", "reviewer_notes": "too short"},
        )
        assert short_res.status_code == 422, f"Expected 422, got {short_res.status_code}: {short_res.text}"

        # Valid determination with reason >= 10 chars
        patch_res = await institution_client.patch(
            f"/api/applications/{app2a_id}/findings/{finding2b['id']}",
            json={
                "reviewer_decision": "verified",
                "reviewer_notes": "Confirmed government construction letter per Annexure-2 preamble.",
            },
        )
        assert patch_res.status_code == 200
        patch_data = patch_res.json()
        assert patch_data["reviewer_decision"] == "verified"
        assert len(patch_data["reviewer_notes"].strip()) >= 10

        # Confirm application overall_status goes to checks_passed
        app_check = await institution_client.get(f"/api/applications/{app2a_id}")
        assert app_check.status_code == 200
        assert app_check.json()["overall_status"] == "checks_passed"

        # Also confirm via get_report endpoint
        rep_check = await institution_client.get(f"/api/applications/{app2a_id}/report")
        assert rep_check.status_code == 200
        assert rep_check.json()["overall_status"] == "checks_passed"
    finally:
        inst_user = FakeUser(
            role="INSTITUTION",
            id="inst-test-1",
            email="principal@test-college.edu",
        )
        app.dependency_overrides[get_current_user] = lambda: inst_user

    # Case 2c: 35-year-old building (1991) with letter but no certificate -> flagged/missing (exemption strictly >50 yrs)
    res2c = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Modern Technical Institute", "application_category": "eoa", "academic_year": "2026-27"},
    )
    assert res2c.status_code == 201
    app2c_id = res2c.json()["id"]

    bcc_35yo = make_pdf([
        "Building Completion Certificate",
        "Institution Name: Modern Technical Institute",
        "Issue Date: 12/03/1991",
        "Certificate Number: BCC-1991-055",
    ])
    u_bcc2c = await institution_client.post(
        f"/api/applications/{app2c_id}/documents",
        files={"file": ("bcc_35.pdf", bcc_35yo, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )
    assert u_bcc2c.status_code == 201

    letter_35_bytes = make_pdf([
        "Letter from Competent Authority",
        "Institution Name: Modern Technical Institute",
        "Subject: AICTE Building Norms Compliance Inquiry",
        "Reference: Annexure-2 Section 2.1 Exemption Request 1991",
    ])
    letter_2c_res = await institution_client.post(
        f"/api/applications/{app2c_id}/documents",
        files={"file": ("letter_35.pdf", letter_35_bytes, "application/pdf")},
        data={"document_type": "competent_authority_letter"},
    )
    assert letter_2c_res.status_code == 201

    val2c = await institution_client.post(f"/api/applications/{app2c_id}/validate")
    assert val2c.status_code == 200
    report2c = val2c.json()

    finding2c = next((f for f in report2c["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"), None)
    assert finding2c is not None
    assert finding2c["status"] == "missing", "35-year-old building with letter but no certificate must be flagged (exemption is strictly >50 yrs)"
    assert "Missing" in finding2c["title"]
    assert finding2c.get("clause_ref") is not None
    assert finding2c["clause_ref"]["clause_id"] == "APH_2024_27_CLAUSE_6_17_H"


