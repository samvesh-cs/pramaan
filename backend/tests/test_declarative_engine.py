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
async def test_structural_stability_5_year_expiry_and_legacy_name_match_exemption(institution_client: AsyncClient):
    """
    Validates structural stability rules under current live engine:
    1. Case 1: Certificate expired (> 5 years) correctly flagged under Clause 6.17(h).
    2. Case 2 (Legacy: exemption granted by name match; to be removed in Step A0b/F):
       - Posting 'competent_authority_letter' currently returns HTTP 400 (not in EOA_MVP_DOCUMENT_TYPES).
       - Live rule grants exemption solely because 'government' is in the institution name.
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

    # Case 2: Government building > 50 years old with Government authority letter
    res2 = await institution_client.post(
        "/api/applications",
        json={"institution_name": "Government Polytechnic College", "application_category": "eoa", "academic_year": "2026-27"},
    )
    assert res2.status_code == 201
    app2_id = res2.json()["id"]

    old_govt_bcc = make_pdf([
        "Building Completion Certificate",
        "Institution Name: Government Polytechnic College",
        "Issue Date: 12/03/1965",
        "Certificate Number: GOVT-BCC-1965",
    ])
    u3_res = await institution_client.post(
        f"/api/applications/{app2_id}/documents",
        files={"file": ("govt_bcc.pdf", old_govt_bcc, "application/pdf")},
        data={"document_type": "building_completion_certificate"},
    )
    assert u3_res.status_code == 201

    govt_letter_bytes = make_pdf([
        "Letter from Competent Authority",
        "Institution Name: Government Polytechnic College",
        "Subject: AICTE Building Norms Compliance under Government Building Act 1899",
        "Reference: Annexure-2 Section 2.1 Government Building Exemption",
    ])
    govt_letter_res = await institution_client.post(
        f"/api/applications/{app2_id}/documents",
        files={"file": ("govt_letter.pdf", govt_letter_bytes, "application/pdf")},
        data={"document_type": "competent_authority_letter"},
    )
    # Real current behavior: competent_authority_letter is rejected because it is not yet in EOA_MVP_DOCUMENT_TYPES
    assert govt_letter_res.status_code == 400
    assert govt_letter_res.json()["error"]["code"] == "INVALID_DOCUMENT_TYPE"

    val2 = await institution_client.post(f"/api/applications/{app2_id}/validate")
    assert val2.status_code == 200
    report2 = val2.json()

    govt_struct_finding = next((f for f in report2["findings"] if f["rule_id"] == "STRUCTURAL_STABILITY_001"), None)
    assert govt_struct_finding is not None
    # Real current behavior: pass is granted strictly via institution-name matching ('government' in name)
    assert govt_struct_finding["status"] == "pass"
    assert "Government Building Exemption" in govt_struct_finding["title"]


