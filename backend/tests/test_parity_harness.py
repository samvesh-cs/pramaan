import pytest
from app.rules.parity_harness import run_parity_harness


def test_replay_and_parity_harness_zero_unallowed_discrepancies():
    """Runs Step B5 replay and parity harness and asserts 0 unallowed discrepancies."""
    report = run_parity_harness()
    assert report.total_contexts >= 10
    assert report.total_rule_evaluations > 50
    assert len(report.unallowed_discrepancies) == 0, (
        f"Detected unallowed discrepancies: {report.unallowed_discrepancies}"
    )
    assert report.matches == report.total_rule_evaluations
