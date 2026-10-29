"""
Step A Test Suite: Shadow Declarative Engine & Advisory Attribute Pipeline.
Verifies:
1. Advisory attribute on rules, schemas, and findings.
2. Dynamic overall-status calculation decoupled from hardcoded string rule IDs.
3. In-memory deep-copied shadow context with zero database access in worker thread.
4. Fail-safe isolation (shadow failure or timeout never impacts validation response).
5. Strict discrepancy logging format (application_id, rule_id, legacy_status, shadow_status, discrepancy_code).
6. Feature flag defaults to OFF (False) and preserves exact client responses when toggled.
"""

import copy
import logging
from pathlib import Path
from types import SimpleNamespace
import pytest
from httpx import AsyncClient

from app.config import settings
from app.rules.base import BaseRule
from app.rules.declarative_engine import DeclarativeRuleEngine, default_declarative_engine
from app.rules.legacy_adapter import EnhancedRuleWrapper, is_advisory_rule
from app.rules.shadow_runner import (
    create_shadow_context,
    dispatch_shadow_evaluation,
    run_shadow_evaluation_worker,
)
from app.rules.ter_payment_check import TerPaymentRule
from app.schemas.finding import FindingCreate
from app.schemas.rule_definition import DeclarativeRuleConfig
from app.services.validation_engine import calculate_overall_status

SAMPLE_DIR = Path(__file__).parent / "demo_samples"


def read_sample(filename: str) -> bytes:
    with open(SAMPLE_DIR / filename, "rb") as f:
        return f.read()


def test_advisory_attribute_on_rules_and_schemas():
    """Asserts advisory attribute exists on BaseRule, DeclarativeRuleConfig, and legacy adapter."""
    # 1. BaseRule default
    assert hasattr(BaseRule, "advisory")
    assert BaseRule.advisory is False

    # 2. TerPaymentRule advisory
    ter_rule = TerPaymentRule()
    assert ter_rule.advisory is True

    # 3. Declarative rule config advisory
    yaml_rule = default_declarative_engine.get_rule("TER_PAYMENT_001")
    if yaml_rule:
        assert yaml_rule.advisory is True

    # 4. is_advisory_rule registry lookup
    assert is_advisory_rule("TER_PAYMENT_001") is True
    assert is_advisory_rule("FIELD_004") is True
    assert is_advisory_rule("PRESENCE_004") is True
    assert is_advisory_rule("EXPIRY_001") is False
    assert is_advisory_rule("DOC_PRESENCE_001") is False

    # 5. FindingCreate advisory attribute
    finding = FindingCreate(
        rule_id="TER_PAYMENT_001",
        status="not_applicable",
        title="Advisory check",
        reason="Information only",
        advisory=True,
    )
    assert finding.advisory is True


def test_calculate_overall_status_decoupled_from_hardcoded_rule_ids():
    """Asserts that calculate_overall_status uses finding.advisory attribute rather than hardcoded names."""
    # Dummy document that is processed
    doc = SimpleNamespace(id="doc1", document_type="fire_safety_certificate", processing_status="processed")

    # A custom advisory rule not in any legacy hardcoded list
    custom_advisory_finding = SimpleNamespace(
        rule_id="CUSTOM_ADVISORY_CHECK_999",
        status="flagged",
        advisory=True,
        reviewer_decision=None,
    )
    mandatory_pass_finding = SimpleNamespace(
        rule_id="EXPIRY_001",
        status="pass",
        advisory=False,
        reviewer_decision=None,
    )

    # Even though custom finding is flagged, because advisory is True, it converts to not_applicable
    # and does not block checks_passed
    res = calculate_overall_status([mandatory_pass_finding, custom_advisory_finding], [doc])
    assert res == "checks_passed"


def test_legacy_stored_findings_without_advisory_attribute():
    """
    Asserts that legacy findings stored prior to Step A (which lack an advisory attribute or have advisory=None)
    resolve their advisory nature via is_advisory_rule(rule_id) so that calculate_overall_status is 100% unchanged.
    """
    doc = SimpleNamespace(id="doc1", document_type="fire_safety_certificate", processing_status="processed")

    # 1. Finding without 'advisory' attribute at all (simulating legacy database row or dict)
    legacy_ter = SimpleNamespace(
        rule_id="TER_PAYMENT_001",
        status="flagged",
        reviewer_decision=None,
    )
    assert not hasattr(legacy_ter, "advisory")

    # 2. Finding with advisory=None (simulating unmigrated nullable column)
    legacy_field4 = SimpleNamespace(
        rule_id="FIELD_004",
        status="missing",
        advisory=None,
        reviewer_decision=None,
    )

    legacy_presence4 = SimpleNamespace(
        rule_id="PRESENCE_004",
        status="flagged",
        advisory=None,
        reviewer_decision=None,
    )

    mandatory_pass = SimpleNamespace(
        rule_id="DOC_PRESENCE_001",
        status="pass",
        advisory=None,
        reviewer_decision=None,
    )

    # Legacy advisory findings (even when flagged or missing) do not block checks_passed
    res = calculate_overall_status([mandatory_pass, legacy_ter, legacy_field4, legacy_presence4], [doc])
    assert res == "checks_passed"


def test_shadow_context_is_deep_copied_and_detached():
    """Asserts create_shadow_context creates pure detached objects with zero DB connection handles."""
    app = SimpleNamespace(
        id="app_test",
        institution_name="Test College",
        application_category="eoa",
        academic_year="2026-27",
        overall_status="processing_incomplete",
    )
    doc = SimpleNamespace(
        id="doc_test",
        application_id="app_test",
        document_type="fire_safety_certificate",
        original_filename="sample.pdf",
        processing_status="processed",
    )
    ext = SimpleNamespace(
        id="ext_test",
        document_id="doc_test",
        processing_status="processed",
        fields={"certificate_number": {"value": "FS-123"}},
        raw_text="Sample text",
        confidence=0.95,
        error=None,
    )

    shadow_ctx = create_shadow_context(
        application_id="app_test",
        application=app,
        documents=[doc],
        extractions_by_doc_id={"doc_test": ext},
        all_system_documents=[doc],
    )

    # Context can be deep-copied without session or thread concurrency errors
    copied = copy.deepcopy(shadow_ctx)
    assert copied["application_id"] == "app_test"
    assert copied["documents"][0].original_filename == "sample.pdf"
    assert copied["extractions"]["doc_test"].fields["certificate_number"]["value"] == "FS-123"

    # Modifying the copy does not alter the original
    copied["documents"][0].original_filename = "modified.pdf"
    assert shadow_ctx["documents"][0].original_filename == "sample.pdf"


def test_shadow_evaluation_worker_logs_discrepancies_strictly(caplog):
    """Asserts shadow evaluation worker logs only application_id, rule_id, legacy_status, shadow_status, discrepancy_code."""
    app = SimpleNamespace(
        id="app_shadow_1",
        institution_name="Test College",
        application_category="eoa",
        academic_year="2026-27",
        overall_status="processing_incomplete",
    )
    doc = SimpleNamespace(
        id="doc1",
        application_id="app_shadow_1",
        document_type="fire_safety_certificate",
        original_filename="fire.pdf",
        processing_status="processed",
    )
    ext = SimpleNamespace(
        id="ext1",
        document_id="doc1",
        processing_status="processed",
        fields={"expiry_date": {"value": "2030-01-01"}},
        raw_text="Valid",
        confidence=0.99,
        error=None,
    )

    shadow_ctx = create_shadow_context("app_shadow_1", app, [doc], {"doc1": ext}, [doc])

    # Legacy summary says EXPIRY_001 was flagged, shadow says pass
    legacy_summary = [{"rule_id": "EXPIRY_001", "status": "flagged"}]

    with caplog.at_level(logging.INFO):
        discrepancies = run_shadow_evaluation_worker("app_shadow_1", shadow_ctx, legacy_summary)

    # Discrepancies returned and logged
    expiry_disc = next((d for d in discrepancies if d["rule_id"] == "EXPIRY_001"), None)
    assert expiry_disc is not None
    assert expiry_disc["legacy_status"] == "flagged"
    assert expiry_disc["shadow_status"] == "pass"
    assert expiry_disc["discrepancy_code"] == "STATUS_MISMATCH"

    # Verify log output format
    assert "SHADOW_DISCREPANCY: application_id=app_shadow_1 rule_id=EXPIRY_001 legacy_status=flagged shadow_status=pass discrepancy_code=STATUS_MISMATCH" in caplog.text


def test_shadow_evaluation_fail_safe_isolation(caplog, monkeypatch):
    """Asserts that shadow evaluation failure never raises an exception to the caller."""
    def crash_evaluate(ctx):
        raise RuntimeError("Simulated declarative engine crash")

    monkeypatch.setattr(default_declarative_engine, "evaluate", crash_evaluate)

    with caplog.at_level(logging.WARNING):
        # Should not raise
        discrepancies = run_shadow_evaluation_worker("app_fail_safe", {}, [])

    assert discrepancies == []
    assert "SHADOW_FAILURE: application_id=app_fail_safe shadow declarative evaluation failed: Simulated declarative engine crash" in caplog.text


def test_setting_default():
    """Asserts that the ENABLE_SHADOW_DECLARATIVE_ENGINE setting defaults to False in Settings schema."""
    from app.config import Settings
    assert Settings.model_fields["ENABLE_SHADOW_DECLARATIVE_ENGINE"].default is False


@pytest.mark.asyncio
async def test_feature_flag_and_response_invariance(institution_client: AsyncClient, monkeypatch):
    """Asserts that enabling shadow evaluation does not alter the client response or overall status."""
    # 1. Test with flag OFF
    monkeypatch.setattr(settings, "ENABLE_SHADOW_DECLARATIVE_ENGINE", False)
    assert settings.ENABLE_SHADOW_DECLARATIVE_ENGINE is False

    res = await institution_client.post(
        "/api/applications",
        json={
            "institution_name": "Synthetic Shadow Test Institute",
            "application_category": "eoa",
            "academic_year": "2026-27",
        },
    )
    assert res.status_code == 201
    app_id = res.json()["id"]

    for doc_type, filename in [
        ("fire_safety_certificate", "valid_fire_safety.pdf"),
        ("building_completion_certificate", "valid_building_completion.pdf"),
        ("affidavit_2", "valid_affidavit_2.pdf"),
    ]:
        files = {"file": (filename, read_sample(filename), "application/pdf")}
        up = await institution_client.post(f"/api/applications/{app_id}/documents", files=files, data={"document_type": doc_type})
        assert up.status_code == 201

    val_off = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_off.status_code == 200
    report_off = val_off.json()

    # 2. Test with flag ON on the exact same application state
    monkeypatch.setattr(settings, "ENABLE_SHADOW_DECLARATIVE_ENGINE", True)
    assert settings.ENABLE_SHADOW_DECLARATIVE_ENGINE is True

    val_on = await institution_client.post(f"/api/applications/{app_id}/validate")
    assert val_on.status_code == 200
    report_on = val_on.json()

    # Verify identical summary, overall status, and finding counts
    assert report_on["overall_status"] == report_off["overall_status"]
    assert report_on["summary"] == report_off["summary"]
    assert len(report_on["findings"]) == len(report_off["findings"])
    off_findings = {(f["rule_id"], f["status"]) for f in report_off["findings"]}
    on_findings = {(f["rule_id"], f["status"]) for f in report_on["findings"]}
    assert off_findings == on_findings


@pytest.mark.asyncio
async def test_shadow_task_reference_retained_and_cleaned_up(monkeypatch):
    """Asserts that fire-and-forget shadow background tasks retain strong references in _BACKGROUND_SHADOW_TASKS."""
    import asyncio
    from app.rules.shadow_runner import _BACKGROUND_SHADOW_TASKS

    monkeypatch.setattr(settings, "ENABLE_SHADOW_DECLARATIVE_ENGINE", True)

    app = SimpleNamespace(id="app_task_test", institution_name="Test College")
    doc = SimpleNamespace(id="doc_t", application_id="app_task_test", document_type="fire_safety_certificate")

    # Dispatch shadow evaluation
    await dispatch_shadow_evaluation(
        application_id="app_task_test",
        application=app,
        documents=[doc],
        extractions_by_doc_id={},
        all_system_documents=[doc],
        legacy_findings=[],
    )

    # Allow event loop to run background task to completion
    await asyncio.sleep(0.1)

    # After completion, task reference must be cleanly discarded from the set
    assert len(_BACKGROUND_SHADOW_TASKS) == 0


@pytest.mark.asyncio
async def test_shadow_evaluation_concurrency_limit_skips_when_busy(caplog, monkeypatch):
    """Asserts that when concurrency limit is saturated, new shadow evaluations are skipped and logged as SHADOW_SKIPPED_BUSY."""
    import asyncio
    from app.rules.shadow_runner import _shadow_concurrency_semaphore

    monkeypatch.setattr(settings, "ENABLE_SHADOW_DECLARATIVE_ENGINE", True)

    app = SimpleNamespace(id="app_busy_test", institution_name="Test College")
    doc = SimpleNamespace(id="doc_b", application_id="app_busy_test", document_type="fire_safety_certificate")

    # Acquire all permits to simulate saturated workers
    await _shadow_concurrency_semaphore.acquire()
    await _shadow_concurrency_semaphore.acquire()
    assert _shadow_concurrency_semaphore.locked()

    try:
        with caplog.at_level(logging.INFO):
            await dispatch_shadow_evaluation(
                application_id="app_busy_test",
                application=app,
                documents=[doc],
                extractions_by_doc_id={},
                all_system_documents=[doc],
                legacy_findings=[],
            )
            # Allow event loop to run _safe_run check
            await asyncio.sleep(0.05)

        assert "SHADOW_SKIPPED_BUSY: application_id=app_busy_test shadow evaluation skipped due to concurrency limit" in caplog.text
    finally:
        _shadow_concurrency_semaphore.release()
        _shadow_concurrency_semaphore.release()



