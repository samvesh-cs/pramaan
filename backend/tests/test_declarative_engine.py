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
    await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "fire_safety_certificate"})

    files = {"file": ("valid_building_completion.pdf", read_sample("valid_building_completion.pdf"), "application/pdf")}
    await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "building_completion_certificate"})

    # Validate
    val = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val.status_code == 200
    report = val.json()

    assert len(report["findings"]) > 0

    valid_severities = {"critical", "high", "medium", "low", "info"}
    valid_signals = {"rule", "tamper", "issuer", "duplicate"}

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
    await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": "fire_safety_certificate"})

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
