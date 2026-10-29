"""
Step B2 Boundary and Parity Test Suite.
Validates exact parity between legacy and declarative logic across boundary conditions:
1. Confidence exactly 0.70, 0.699, and 0.701.
2. Expiry date equal to cutoff date, cutoff - 1 day, and cutoff + 1 day.
3. Building age exactly 30 years, 30 years + 1 day, and 29 years 364 days.
4. Feb 29 leap-year anniversaries on non-leap years.
5. Empty, whitespace, newline, and None field values.
6. Unicode and Hindi institution names.
7. Duplicate fields and multiple documents of the same type.
8. Advisory rules (TER_PAYMENT_001, FIELD_004, PRESENCE_004) preserving calculate_overall_status.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
import pytest

from app.rules.declarative_engine import DeclarativeRuleEngine, default_declarative_engine
from app.rules.legacy_adapter import is_advisory_rule, wrap_legacy_rules
from app.rules.presence_check import DocumentPresenceRule
from app.rules.field_completeness import FieldCompletenessRule
from app.rules.expiry_check import ExpiryDateRule
from app.rules.cross_document_check import InstitutionNameConsistencyRule
from app.rules.ter_payment_check import TerPaymentRule
from app.rules.building_age_check import BuildingAgeStructuralStabilityRule
from app.services.validation_engine import calculate_overall_status
from app.schemas.finding import FindingCreate


def make_context(
    institution_name: str = "Pramaan Institute of Technology",
    documents: list[Any] = None,
    extractions: dict[str, Any] = None,
    cutoff_date: date = date(2024, 5, 15),
) -> dict[str, Any]:
    app = SimpleNamespace(
        id="app_b2_test",
        institution_name=institution_name,
        application_category="eoa",
        academic_year="2026-27",
        overall_status="processing_incomplete",
    )
    docs = documents or []
    for d in docs:
        if not hasattr(d, "application_id"):
            d.application_id = app.id
        if not hasattr(d, "original_filename"):
            d.original_filename = f"{getattr(d, 'document_type', 'doc')}.pdf"
        if not hasattr(d, "file_hash"):
            d.file_hash = f"hash_{d.id}"
    exts = extractions or {}
    return {
        "application": app,
        "documents": docs,
        "extractions": exts,
        "all_system_documents": docs,
        "cutoff_date": cutoff_date,
        "reference_date": cutoff_date,
    }


def evaluate_legacy_rules(context: dict[str, Any]) -> list[FindingCreate]:
    raw_rules = [
        DocumentPresenceRule(),
        FieldCompletenessRule(),
        ExpiryDateRule(),
        InstitutionNameConsistencyRule(),
        TerPaymentRule(),
        BuildingAgeStructuralStabilityRule(),
    ]
    wrapped = wrap_legacy_rules(raw_rules)
    findings = []
    for r in wrapped:
        findings.extend(r.evaluate(context))
    return findings


# =========================================================================
# 1. OCR Confidence Boundary (0.699, 0.70, 0.701)
# =========================================================================

@pytest.mark.parametrize("confidence,expected_status", [
    (0.699, "unresolved"),  # Just below threshold -> unresolved
    (0.700, "pass"),        # Exactly at threshold -> accepted
    (0.701, "pass"),        # Just above threshold -> accepted
])
def test_ocr_confidence_boundary_070(confidence: float, expected_status: str):
    doc = SimpleNamespace(
        id="doc_fire",
        document_type="fire_safety_certificate",
        original_filename="fire.pdf",
        processing_status="processed",
    )
    ext = SimpleNamespace(
        id="ext_fire",
        document_id="doc_fire",
        processing_status="processed",
        fields={
            "expiry_date": {
                "value": "2027-12-31",
                "raw_text": "31/12/2027",
                "confidence": confidence,
                "status": "extracted",
            },
            "certificate_number": {"value": "FS-123", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Fire Dept", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2024-01-01", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx = make_context(documents=[doc], extractions={"doc_fire": ext})

    dec_findings = default_declarative_engine.evaluate(ctx)
    expiry_f = next((f for f in dec_findings if f.rule_id == "EXPIRY_001"), None)
    assert expiry_f is not None
    assert expiry_f.status == expected_status

    # Legacy engine parity
    legacy_findings = evaluate_legacy_rules(ctx)
    leg_expiry = next((f for f in legacy_findings if f.rule_id == "EXPIRY_001"), None)
    assert leg_expiry is not None
    assert leg_expiry.status == expiry_f.status


# =========================================================================
# 2. Expiry Date Boundary (cutoff, cutoff - 1 day, cutoff + 1 day)
# =========================================================================

def test_expiry_date_equal_and_boundary_to_cutoff():
    cutoff = date(2024, 6, 1)

    # (a) Exactly equal to cutoff -> pass (valid through cutoff)
    doc_eq = SimpleNamespace(id="d_eq", document_type="fire_safety_certificate", original_filename="fire.pdf")
    ext_eq = SimpleNamespace(
        processing_status="processed",
        fields={"expiry_date": {"value": cutoff.isoformat(), "confidence": 0.95, "status": "extracted"}},
    )
    ctx_eq = make_context(documents=[doc_eq], extractions={"d_eq": ext_eq}, cutoff_date=cutoff)
    dec_eq = next(f for f in default_declarative_engine.evaluate(ctx_eq) if f.rule_id == "EXPIRY_001")
    leg_eq = next(f for f in evaluate_legacy_rules(ctx_eq) if f.rule_id == "EXPIRY_001")
    assert dec_eq.status == "pass"
    assert leg_eq.status == "pass"

    # (b) One day before cutoff -> flagged (expired)
    day_before = cutoff - timedelta(days=1)
    ext_before = SimpleNamespace(
        processing_status="processed",
        fields={"expiry_date": {"value": day_before.isoformat(), "confidence": 0.95, "status": "extracted"}},
    )
    ctx_before = make_context(documents=[doc_eq], extractions={"d_eq": ext_before}, cutoff_date=cutoff)
    dec_before = next(f for f in default_declarative_engine.evaluate(ctx_before) if f.rule_id == "EXPIRY_001")
    leg_before = next(f for f in evaluate_legacy_rules(ctx_before) if f.rule_id == "EXPIRY_001")
    assert dec_before.status == "flagged"
    assert leg_before.status == "flagged"

    # (c) One day after cutoff -> pass
    day_after = cutoff + timedelta(days=1)
    ext_after = SimpleNamespace(
        processing_status="processed",
        fields={"expiry_date": {"value": day_after.isoformat(), "confidence": 0.95, "status": "extracted"}},
    )
    ctx_after = make_context(documents=[doc_eq], extractions={"d_eq": ext_after}, cutoff_date=cutoff)
    dec_after = next(f for f in default_declarative_engine.evaluate(ctx_after) if f.rule_id == "EXPIRY_001")
    leg_after = next(f for f in evaluate_legacy_rules(ctx_after) if f.rule_id == "EXPIRY_001")
    assert dec_after.status == "pass"
    assert leg_after.status == "pass"


# =========================================================================
# 3. Building Age Boundary (30 years, 30 years + 1 day, 29 years 364 days)
# =========================================================================

def test_building_age_30_year_boundaries():
    cutoff = date(2024, 5, 15)

    # (a) Exactly 30 years: issue date 1994-05-15 -> building_age = 30 -> not_applicable (<= 30 years)
    doc_bcc = SimpleNamespace(id="d_bcc", document_type="building_completion_certificate", original_filename="bcc.pdf")
    ext_30 = SimpleNamespace(
        processing_status="processed",
        fields={"issue_date": {"value": "1994-05-15", "confidence": 0.95, "status": "extracted"}},
    )
    ctx_30 = make_context(documents=[doc_bcc], extractions={"d_bcc": ext_30}, cutoff_date=cutoff)
    dec_30 = next(f for f in default_declarative_engine.evaluate(ctx_30) if f.rule_id == "STRUCTURAL_STABILITY_001")
    assert dec_30.status == "not_applicable"
    assert "<= 30 Years" in dec_30.title

    # (b) Exactly 30 years + 1 day: issue date 1994-05-14 -> building_age = 30 years 1 day (> 30 years)
    # Without Structural Stability Certificate -> status="missing"
    ext_30_plus_1 = SimpleNamespace(
        processing_status="processed",
        fields={"issue_date": {"value": "1994-05-14", "confidence": 0.95, "status": "extracted"}},
    )
    ctx_30_plus_1 = make_context(documents=[doc_bcc], extractions={"d_bcc": ext_30_plus_1}, cutoff_date=cutoff)
    dec_30_plus_1 = next(f for f in default_declarative_engine.evaluate(ctx_30_plus_1) if f.rule_id == "STRUCTURAL_STABILITY_001")
    assert dec_30_plus_1.status == "missing"
    assert "> 30 Years" in dec_30_plus_1.title

    # (c) 29 years 364 days: issue date 1994-05-16 -> building_age = 29 -> not_applicable
    ext_29_364 = SimpleNamespace(
        processing_status="processed",
        fields={"issue_date": {"value": "1994-05-16", "confidence": 0.95, "status": "extracted"}},
    )
    ctx_29_364 = make_context(documents=[doc_bcc], extractions={"d_bcc": ext_29_364}, cutoff_date=cutoff)
    dec_29_364 = next(f for f in default_declarative_engine.evaluate(ctx_29_364) if f.rule_id == "STRUCTURAL_STABILITY_001")
    assert dec_29_364.status == "not_applicable"


# =========================================================================
# 4. Feb 29 Leap-Year Handling
# =========================================================================

def test_feb_29_leap_year_handling():
    # Issue date on leap year Feb 29, 1992
    # Non-leap year anniversary in 2022 is clamped to Feb 28
    issue_date = date(1992, 2, 29)

    doc_bcc = SimpleNamespace(id="d_bcc", document_type="building_completion_certificate", original_filename="bcc.pdf")

    # (a) Cutoff 2022-02-28 (anniversary in non-leap year): exactly 30 years -> not_applicable
    ext_leap = SimpleNamespace(
        processing_status="processed",
        fields={"issue_date": {"value": issue_date.isoformat(), "confidence": 0.95, "status": "extracted"}},
    )
    ctx_leap_exact = make_context(documents=[doc_bcc], extractions={"d_bcc": ext_leap}, cutoff_date=date(2022, 2, 28))
    dec_leap_exact = next(f for f in default_declarative_engine.evaluate(ctx_leap_exact) if f.rule_id == "STRUCTURAL_STABILITY_001")
    assert dec_leap_exact.status == "not_applicable"

    # (b) Cutoff 2022-03-01: 30 years and 1 day -> exceeds 30 years -> missing
    ctx_leap_over = make_context(documents=[doc_bcc], extractions={"d_bcc": ext_leap}, cutoff_date=date(2022, 3, 1))
    dec_leap_over = next(f for f in default_declarative_engine.evaluate(ctx_leap_over) if f.rule_id == "STRUCTURAL_STABILITY_001")
    assert dec_leap_over.status == "missing"

    # (c) Expiry date on Feb 29, 2024 evaluated on Feb 29, 2024 -> pass
    doc_fire = SimpleNamespace(id="d_fire", document_type="fire_safety_certificate", original_filename="fire.pdf")
    ext_fire_leap = SimpleNamespace(
        processing_status="processed",
        fields={"expiry_date": {"value": "2024-02-29", "confidence": 0.95, "status": "extracted"}},
    )
    ctx_fire_leap = make_context(documents=[doc_fire], extractions={"d_fire": ext_fire_leap}, cutoff_date=date(2024, 2, 29))
    dec_fire_leap = next(f for f in default_declarative_engine.evaluate(ctx_fire_leap) if f.rule_id == "EXPIRY_001")
    assert dec_fire_leap.status == "pass"


# =========================================================================
# 5. Empty and Whitespace Fields
# =========================================================================

@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n  \r", None])
def test_empty_and_whitespace_fields_yield_unresolved(empty_val: Any):
    doc = SimpleNamespace(id="d_test", document_type="fire_safety_certificate", original_filename="fire.pdf")
    ext = SimpleNamespace(
        processing_status="processed",
        fields={
            "expiry_date": {"value": empty_val, "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": empty_val, "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx = make_context(documents=[doc], extractions={"d_test": ext})

    findings = default_declarative_engine.evaluate(ctx)
    expiry_f = next(f for f in findings if f.rule_id == "EXPIRY_001")
    field_f = next(f for f in findings if f.rule_id == "FIELD_001")

    assert expiry_f.status == "unresolved"
    assert field_f.status == "missing"


# =========================================================================
# 6. Unicode and Hindi Institution Names
# =========================================================================

def test_unicode_and_hindi_institution_names():
    hindi_name = "भारतीय प्रौद्योगिकी संस्थान मुंबई"
    mismatch_hindi_name = "दिल्ली विश्वविद्यालय"

    doc = SimpleNamespace(id="d_aff", document_type="affidavit_2", original_filename="affidavit.pdf")

    # Match case
    ext_match = SimpleNamespace(
        processing_status="processed",
        fields={"institution_name": {"value": hindi_name, "confidence": 0.95, "status": "extracted"}},
    )
    ctx_match = make_context(institution_name=hindi_name, documents=[doc], extractions={"d_aff": ext_match})
    f_match = next(f for f in default_declarative_engine.evaluate(ctx_match) if f.rule_id == "CONSISTENCY_001")
    assert f_match.status == "pass"

    # Mismatch case
    ext_mismatch = SimpleNamespace(
        processing_status="processed",
        fields={"institution_name": {"value": mismatch_hindi_name, "confidence": 0.95, "status": "extracted"}},
    )
    ctx_mismatch = make_context(institution_name=hindi_name, documents=[doc], extractions={"d_aff": ext_mismatch})
    f_mismatch = next(f for f in default_declarative_engine.evaluate(ctx_mismatch) if f.rule_id == "CONSISTENCY_001")
    assert f_mismatch.status == "flagged"


# =========================================================================
# 7. Multiple Documents of Same Type & Duplicate Handling
# =========================================================================

def test_multiple_documents_of_same_type():
    doc1 = SimpleNamespace(id="doc1", document_type="fire_safety_certificate", original_filename="fire_1.pdf", file_hash="hash_fire_1")
    doc2 = SimpleNamespace(id="doc2", document_type="fire_safety_certificate", original_filename="fire_2.pdf", file_hash="hash_fire_1")
    ext1 = SimpleNamespace(
        processing_status="processed",
        fields={"expiry_date": {"value": "2028-01-01", "confidence": 0.95, "status": "extracted"}},
    )
    ext2 = SimpleNamespace(
        processing_status="processed",
        fields={"expiry_date": {"value": "2028-01-01", "confidence": 0.95, "status": "extracted"}},
    )

    ctx = make_context(documents=[doc1, doc2], extractions={"doc1": ext1, "doc2": ext2})
    findings = default_declarative_engine.evaluate(ctx)

    # Must process without error, detecting duplicate hash via DUPLICATE_DOC_001
    dup_f = next((f for f in findings if f.rule_id == "DUPLICATE_DOC_001"), None)
    assert dup_f is not None
    assert "Same file uploaded" in dup_f.title


# =========================================================================
# 8. Advisory Rules Semantics & calculate_overall_status Parity
# =========================================================================

def test_advisory_rules_parity_and_overall_status_invariance():
    """
    Asserts that TER_PAYMENT_001, FIELD_004, and PRESENCE_004 maintain advisory=True
    and that calculate_overall_status produces the exact same outcome in both engines.
    """
    doc_fire = SimpleNamespace(id="d_f", document_type="fire_safety_certificate", processing_status="processed")
    doc_bcc = SimpleNamespace(id="d_b", document_type="building_completion_certificate", processing_status="processed")
    doc_aff = SimpleNamespace(id="d_a", document_type="affidavit_2", processing_status="processed")
    doc_ter = SimpleNamespace(id="d_t", document_type="ter_payment_receipt", processing_status="processed")

    ext_valid = SimpleNamespace(
        processing_status="processed",
        fields={
            "expiry_date": {"value": "2028-01-01", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "123", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Auth", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2020-01-01", "confidence": 0.95, "status": "extracted"},
            "institution_name": {"value": "Pramaan Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "affidavit_date": {"value": "2024-01-01", "confidence": 0.95, "status": "extracted"},
            "deponent_name": {"value": "Dr. John Doe", "confidence": 0.95, "status": "extracted"},
        },
    )

    # Incomplete TER receipt (fields missing / advisory)
    ext_ter = SimpleNamespace(
        processing_status="processed",
        fields={},
    )

    ctx = make_context(
        documents=[doc_fire, doc_bcc, doc_aff, doc_ter],
        extractions={"d_f": ext_valid, "d_b": ext_valid, "d_a": ext_valid, "d_t": ext_ter},
    )

    dec_findings = default_declarative_engine.evaluate(ctx)
    leg_findings = evaluate_legacy_rules(ctx)

    # Check advisory rules in declarative findings
    ter_f = next(f for f in dec_findings if f.rule_id == "TER_PAYMENT_001")
    field4_f = next(f for f in dec_findings if f.rule_id == "FIELD_004")

    assert ter_f.advisory is True
    assert field4_f.advisory is True
    assert is_advisory_rule("PRESENCE_004") is True

    # Calculate overall status on both findings sets
    status_dec = calculate_overall_status(dec_findings, ctx["documents"])
    status_leg = calculate_overall_status(leg_findings, ctx["documents"])
    assert status_dec == status_leg == "checks_passed"

    # Verify a stored legacy finding for PRESENCE_004 (without advisory attribute) doesn't change status
    legacy_pres4 = SimpleNamespace(rule_id="PRESENCE_004", status="missing", reviewer_decision=None)
    status_with_pres4 = calculate_overall_status(dec_findings + [legacy_pres4], ctx["documents"])
    assert status_with_pres4 == "checks_passed"

def test_non_iso_expiry_date_format_unresolved_in_both_engines():
    """Asserts that non-ISO date string '15/08/2026' as expiry_date yields unresolved in both engines."""
    doc_fire = SimpleNamespace(
        id="d_f",
        document_type="fire_safety_certificate",
        original_filename="fire_cert.pdf",
        processing_status="processed",
    )
    ext_non_iso = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Pramaan College", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "FS-123", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2024-01-01", "confidence": 0.95, "status": "extracted"},
            "expiry_date": {"value": "15/08/2026", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Fire Dept", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx = make_context(
        documents=[doc_fire],
        extractions={"d_f": ext_non_iso},
    )

    leg_findings = evaluate_legacy_rules(ctx)
    dec_findings = default_declarative_engine.evaluate(ctx)

    leg_exp = next(f for f in leg_findings if f.rule_id == "EXPIRY_001")
    dec_exp = next(f for f in dec_findings if f.rule_id == "EXPIRY_001")

    assert leg_exp.status == "unresolved"
    assert dec_exp.status == "unresolved"
    assert "Unparseable expiry date" in leg_exp.title
    assert leg_exp.title == dec_exp.title
    assert leg_exp.reason == dec_exp.reason
