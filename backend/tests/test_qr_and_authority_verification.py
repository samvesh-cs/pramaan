import json
import pytest
from app.ocr.qr_processor import parse_qr_payload, scan_image_for_qr
from app.services.authority_verification import verify_with_issuing_authority, AuthorityVerificationResult
from app.rules.qr_verification_check import IssuingAuthorityVerificationRule
from app.models.application import Application
from app.models.document import Document
from app.schemas.extraction import ExtractionResponse, FieldExtraction
import numpy as np
import qrcode


def test_parse_qr_payload_json():
    payload = json.dumps({
        "cert_no": "DEL/FS/2026/001",
        "institution": "Government Engineering College, Delhi (Demo)",
        "expiry": "2026-12-31"
    })
    parsed = parse_qr_payload(payload)
    assert parsed["format"] == "json"
    assert parsed["certificate_number"] == "DEL/FS/2026/001"
    assert parsed["institution_name"] == "Government Engineering College, Delhi (Demo)"
    assert parsed["expiry_date"] == "2026-12-31"


def test_parse_qr_payload_url():
    url = "https://edistrict.delhigovt.nic.in/verify?cert_no=FS-2024-9812&inst=Delhi+Tech&valid_till=2026-06-30"
    parsed = parse_qr_payload(url)
    assert parsed["format"] == "url"
    assert parsed["certificate_number"] == "FS-2024-9812"
    assert parsed["institution_name"] == "Delhi Tech"
    assert parsed["expiry_date"] == "2026-06-30"
    assert parsed["issuing_authority"] == "edistrict.delhigovt.nic.in"


def test_parse_qr_payload_plain_text():
    raw = "Certificate No: FS-2024-9812\nInstitution: Delhi Institute of Technology\nValid Upto: 2026-12-31"
    parsed = parse_qr_payload(raw)
    assert parsed["certificate_number"] == "FS-2024-9812"
    assert parsed["institution_name"] == "Delhi Institute of Technology"
    assert parsed["expiry_date"] == "2026-12-31"


def test_scan_image_for_qr():
    # Generate in-memory QR image
    qr = qrcode.QRCode()
    test_data = json.dumps({"cert_no": "MCD/BCC/2024/771", "inst": "Government Engineering College"})
    qr.add_data(test_data)
    qr.make()
    pil_img = qr.make_image().convert("RGB")
    cv_img = np.array(pil_img)

    result = scan_image_for_qr(cv_img)
    assert result is not None
    assert result["detected"] is True
    assert result["parsed"]["certificate_number"] == "MCD/BCC/2024/771"
    assert result["bbox"] is not None
    assert len(result["bbox"]) == 4


def test_authority_verification_all_six_statuses():
    # 1. verified (matches registry)
    res_verified = verify_with_issuing_authority(
        document_type="fire_safety_certificate",
        certificate_number="DEL/FS/2026/001",
        institution_name="Government Engineering College, Delhi (Demo)",
    )
    assert res_verified.status == "verified"
    assert res_verified.is_trusted_source is True

    # 2. mismatch_detected (certificate in registry under different college)
    res_mismatch = verify_with_issuing_authority(
        document_type="fire_safety_certificate",
        certificate_number="DEL/FS/2026/001",
        institution_name="Completely Fraudulent Institute",
    )
    assert res_mismatch.status == "mismatch_detected"
    assert "not" in res_mismatch.discrepancy_reason.lower()

    # 3. expired (authority indicates certificate is expired or lapsed)
    res_expired = verify_with_issuing_authority(
        document_type="fire_safety_certificate",
        certificate_number="FS-EXPIRED-99",
        institution_name="Delhi Institute of Technology",
    )
    assert res_expired.status == "expired"

    # 4. QR code mismatch vs printed document text
    qr_payload = {
        "raw_payload": "some_qr",
        "parsed": {
            "certificate_number": "FS-GENUINE-100",
            "institution_name": "Delhi Institute of Technology"
        }
    }
    res_qr_mismatch = verify_with_issuing_authority(
        document_type="fire_safety_certificate",
        certificate_number="FS-ALTERED-200",  # conflicts with QR
        institution_name="Delhi Institute of Technology",
        qr_payload=qr_payload,
    )
    assert res_qr_mismatch.status == "mismatch_detected"
    assert "does not match" in res_qr_mismatch.discrepancy_reason

    # 5. manual_review_required (no certificate number available)
    res_manual = verify_with_issuing_authority(
        document_type="fire_safety_certificate",
        certificate_number=None,
        institution_name="Government Engineering College",
    )
    assert res_manual.status == "manual_review_required"

    # 6. source_unavailable (external registry not in demo database or offline)
    res_offline = verify_with_issuing_authority(
        document_type="structural_stability_certificate",
        certificate_number="UNKNOWN-STAB-999",
        institution_name="Government Engineering College",
    )
    assert res_offline.status == "source_unavailable"


def test_issuing_authority_rule_evaluation():
    rule = IssuingAuthorityVerificationRule()

    app = Application(
        id="app_test_101",
        institution_name="Government Engineering College, Delhi (Demo)",
        academic_year="2026-27",
    )
    doc = Document(
        id="doc_fire_1",
        application_id="app_test_101",
        document_type="fire_safety_certificate",
        original_filename="fire_safety.pdf",
        stored_filename="stored_fire.pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        processing_status="processed",
    )
    extraction = ExtractionResponse(
        document_id="doc_fire_1",
        document_type="fire_safety_certificate",
        processing_status="processed",
        fields={
            "certificate_number": FieldExtraction(value="DEL/FS/2026/001", raw_text="DEL/FS/2026/001", status="extracted", bbox=[10, 10, 50, 20]),
            "expiry_date": FieldExtraction(value="2026-12-31", raw_text="2026-12-31", status="extracted"),
        }
    )

    context = {
        "application": app,
        "documents": [doc],
        "extractions": {doc.id: extraction},
    }

    findings = rule.evaluate(context)
    assert len(findings) == 1
    assert findings[0].status == "pass"
    assert "Verified" in findings[0].title
    assert findings[0].evidence["authority_status"] == "verified"

