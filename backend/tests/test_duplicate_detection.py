import pytest
from unittest.mock import MagicMock
from app.models.application import Application
from app.models.document import Document
from app.models.extraction import ExtractionRun
from app.rules.duplicate_check import DuplicateDocumentRule


def test_intra_application_duplicate_detection():
    rule = DuplicateDocumentRule()

    app = Application(id="app-1", institution_name="ABC College of Engineering")
    doc1 = Document(
        id="doc-1",
        application_id="app-1",
        document_type="fire_safety_certificate",
        original_filename="fire_safety.pdf",
        file_hash="hash_abc_123",
    )
    doc2 = Document(
        id="doc-2",
        application_id="app-1",
        document_type="fire_safety_certificate",
        original_filename="fire_safety_copy.pdf",
        file_hash="hash_abc_123",
    )

    context = {
        "application": app,
        "documents": [doc1, doc2],
        "extractions": {},
        "all_system_documents": [doc1, doc2],
    }

    findings = rule.evaluate(context)
    # Intra-app duplicate should yield info/pass finding noting multiple uploads
    assert len(findings) == 1
    assert findings[0].status == "pass"
    assert "multiple times" in findings[0].title
    assert "possible duplicate, requires review" in findings[0].reason.lower()


def test_cross_institution_duplicate_detection():
    rule = DuplicateDocumentRule()

    app1 = Application(id="app-1", institution_name="ABC College")
    app2 = Application(id="app-2", institution_name="XYZ Institute")

    doc1 = Document(
        id="doc-1",
        application_id="app-1",
        document_type="fire_safety_certificate",
        original_filename="fire_safety.pdf",
        file_hash="hash_xyz_999",
    )
    doc2 = Document(
        id="doc-2",
        application_id="app-2",
        document_type="fire_safety_certificate",
        original_filename="stolen_fire_safety.pdf",
        file_hash="hash_xyz_999",
    )
    doc2.application = app2

    context = {
        "application": app1,
        "documents": [doc1],
        "extractions": {},
        "all_system_documents": [doc1, doc2],
    }

    findings = rule.evaluate(context)
    # Cross-institution duplicate must be flagged with manual review required
    flagged = [f for f in findings if f.status == "flagged"]
    assert len(flagged) == 1
    assert "possible duplicate" in flagged[0].title.lower()
    assert "possible duplicate, requires review" in flagged[0].reason.lower()
    assert "fraud" not in flagged[0].reason.lower()
    assert "forged" not in flagged[0].reason.lower()
    assert flagged[0].evidence["matched_application_id"] == "app-2"


def test_same_institution_earlier_application_reuse():
    rule = DuplicateDocumentRule()

    app_current = Application(id="app-2026", institution_name="ABC College")
    app_prev = Application(id="app-2025", institution_name="ABC College")

    doc_curr = Document(
        id="doc-curr",
        application_id="app-2026",
        document_type="building_completion_certificate",
        original_filename="building_plan.pdf",
        file_hash="hash_bld_444",
    )
    doc_prev = Document(
        id="doc-prev",
        application_id="app-2025",
        document_type="building_completion_certificate",
        original_filename="building_plan_2025.pdf",
        file_hash="hash_bld_444",
    )
    doc_prev.application = app_prev

    context = {
        "application": app_current,
        "documents": [doc_curr],
        "extractions": {},
        "all_system_documents": [doc_curr, doc_prev],
    }

    findings = rule.evaluate(context)
    assert len(findings) == 1
    assert findings[0].status == "pass"
    assert "reused from earlier submission" in findings[0].title.lower()
    assert "fraud" not in findings[0].reason.lower()


def test_cross_institution_duplicate_certificate_number():
    rule = DuplicateDocumentRule()

    app1 = Application(id="app-1", institution_name="ABC College")
    app2 = Application(id="app-2", institution_name="XYZ Institute")

    doc1 = Document(
        id="doc-1",
        application_id="app-1",
        document_type="fire_safety_certificate",
        original_filename="fire_safety_1.pdf",
        file_hash="hash_diff_111",
    )
    doc2 = Document(
        id="doc-2",
        application_id="app-2",
        document_type="fire_safety_certificate",
        original_filename="fire_safety_2.pdf",
        file_hash="hash_diff_222",
    )
    doc2.application = app2

    ext1 = ExtractionRun(
        id="ext-1",
        document_id="doc-1",
        processing_status="processed",
        fields={"certificate_number": {"value": "FS-MATCH-888"}},
    )
    ext2 = ExtractionRun(
        id="ext-2",
        document_id="doc-2",
        processing_status="processed",
        fields={"certificate_number": {"value": "FS-MATCH-888"}},
    )
    doc2.extractions = [ext2]

    context = {
        "application": app1,
        "documents": [doc1],
        "extractions": {doc1.id: ext1},
        "all_system_documents": [doc1, doc2],
    }

    findings = rule.evaluate(context)
    flagged = [f for f in findings if f.status == "flagged"]
    assert len(flagged) == 1
    assert "certificate number" in flagged[0].title.lower()
    assert flagged[0].evidence["type"] == "cross_institution_duplicate_certificate_number"
    assert flagged[0].evidence["matched_application_id"] == "app-2"


@pytest.mark.asyncio
async def test_duplicate_blocks_report_and_acknowledgment_resolves(
    reviewer_client,
):
    from tests.conftest import TestSessionLocal
    from app.models.application import Application
    from app.models.document import Document
    from app.models.finding import Finding

    app_id = "test-dup-app-1"
    async with TestSessionLocal() as session:
        app_obj = Application(
            id=app_id,
            institution_name="Test College",
            academic_year="2026-27",
            status="submitted",
        )
        doc = Document(
            id="doc-dup-1",
            application_id=app_id,
            document_type="fire_safety_certificate",
            original_filename="cert.pdf",
            stored_filename="cert.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            processing_status="processed",
        )
        finding = Finding(
            id="finding-dup-1",
            application_id=app_id,
            document_id="doc-dup-1",
            rule_id="DUPLICATE_DOC_001",
            status="flagged",
            title="Possible duplicate document detected (fire_safety_certificate)",
            reason="Duplicate hash match.",
            evidence={"type": "cross_institution_duplicate_file", "matched_application_id": "other-app"},
        )
        session.add(app_obj)
        session.add(doc)
        session.add(finding)
        await session.commit()

    # 1. Report generation must be blocked with HTTP 409 Conflict
    report_res = await reviewer_client.get(f"/api/applications/{app_id}/report")
    assert report_res.status_code == 409
    data = report_res.json()
    assert data["error"]["code"] == "DUPLICATES_UNRESOLVED"

    # 2. Acknowledge duplicate via endpoint as reviewer
    ack_res = await reviewer_client.post(
        f"/api/applications/{app_id}/duplicates/finding-dup-1/acknowledge",
        json={
            "reviewer_notes": "Verified against physical records and confirmed authentic.",
            "reviewed_by": "Senior Scrutiny Officer",
        },
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["acknowledged"] is True

    # 3. After acknowledgment, report must be accessible
    report_after = await reviewer_client.get(f"/api/applications/{app_id}/report")
    assert report_after.status_code == 200
    report_data = report_after.json()
    assert report_data["application_id"] == app_id
    acknowledged = next(f for f in report_data["findings"] if f["id"] == "finding-dup-1")
    assert acknowledged["reviewed_by"] == "reviewer@aicte-india.org"
    assert acknowledged["reviewer_notes"] == "Verified against physical records and confirmed authentic."

    repeated_ack = await reviewer_client.post(
        f"/api/applications/{app_id}/duplicates/finding-dup-1/acknowledge",
        json={"reviewer_notes": "Attempt to replace the audit note."},
    )
    assert repeated_ack.status_code == 409
    assert repeated_ack.json()["error"]["code"] == "REVIEW_DECISION_ALREADY_RECORDED"



