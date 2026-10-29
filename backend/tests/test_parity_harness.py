from unittest.mock import patch
import pytest

from app.rules.parity_harness import (
    ALLOW_LIST,
    Discrepancy,
    ParityReport,
    main,
    run_parity_harness,
)


def test_replay_and_parity_harness_zero_unallowed_discrepancies():
    """Runs Step B5 replay and parity harness and asserts 0 unallowed discrepancies."""
    report = run_parity_harness()
    assert report.total_contexts >= 10
    assert report.total_rule_evaluations > 50
    assert len(report.unallowed_discrepancies) == 0, (
        f"Detected unallowed discrepancies: {report.unallowed_discrepancies}"
    )
    assert report.matches == report.total_rule_evaluations


def test_harness_exits_non_zero_on_injected_discrepancy():
    """Proves the harness exits non-zero (code 1) when an unallowed discrepancy is detected."""
    fake_report = ParityReport(
        total_contexts=1,
        total_rule_evaluations=1,
        matches=0,
        discrepancies=[
            Discrepancy(
                context_id="test_ctx",
                rule_id="EXPIRY_001",
                legacy_status="pass",
                declarative_status="flagged",
                reason_code="STATUS_MISMATCH",
            )
        ],
    )
    with patch("app.rules.parity_harness.run_parity_harness", return_value=fake_report):
        exit_code = main()
        assert exit_code == 1


def test_harness_exits_non_zero_on_allow_list_entry_without_justification():
    """Proves the harness rejects allow-list entries lacking substantive written justification."""
    fake_report = ParityReport(
        total_contexts=1,
        total_rule_evaluations=1,
        matches=0,
        discrepancies=[
            Discrepancy(
                context_id="test_ctx",
                rule_id="EXPIRY_001",
                legacy_status="pass",
                declarative_status="flagged",
                reason_code="STATUS_MISMATCH",
            )
        ],
    )
    # Entry with empty/short justification
    with patch.dict(ALLOW_LIST, {("test_ctx", "EXPIRY_001"): "too short"}, clear=True):
        with patch("app.rules.parity_harness.run_parity_harness", return_value=fake_report):
            assert len(fake_report.unallowed_discrepancies) == 1
            assert fake_report.unallowed_discrepancies[0].reason_code == "ALLOW_LIST_MISSING_JUSTIFICATION"
            exit_code = main()
            assert exit_code == 1

    # Entry with substantive justification (>= 10 characters)
    with patch.dict(ALLOW_LIST, {("test_ctx", "EXPIRY_001"): "Legitimate approved regulatory difference under D-020"}, clear=True):
        with patch("app.rules.parity_harness.run_parity_harness", return_value=fake_report):
            assert len(fake_report.unallowed_discrepancies) == 0
            exit_code = main()
            assert exit_code == 0
