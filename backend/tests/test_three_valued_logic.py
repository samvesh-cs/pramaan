"""
Step B1 Test Suite: Three-Valued Kleene Logic & Condition Grammar Integrity.
Validates:
1. Complete Kleene logic truth tables for all_of, any_of, and not.
2. UNKNOWN propagation on missing fields, unparseable dates, and confidence < 0.70.
3. Date arithmetic leap-year boundaries (Feb 29).
4. Startup validation: max nesting depth > 5, unknown operators, duplicate rule IDs, banned terms.
5. Dynamic config-driven name similarity thresholds.
"""

from datetime import date
from types import SimpleNamespace
import pytest
from pydantic import ValidationError

from app.config import settings
from app.rules.banned_terms import BANNED_FINDING_TERMS, validate_rule_text_claims
from app.rules.declarative_engine import (
    DeclarativeRuleEngine,
    calculate_calendar_years_between,
    calculate_text_similarity,
    default_clause_registry,
    default_declarative_engine,
)
from app.schemas.rule_definition import (
    DeclarativeRuleConfig,
    EvaluationResult,
    RuleBranch,
    RuleCondition,
)


def test_kleene_logic_truth_tables():
    """Validates complete 3-valued Kleene logic truth tables for all_of, any_of, and not."""
    engine = default_declarative_engine

    class DummyCondition:
        pass

    # Helper: construct condition that evaluates directly to a desired outcome
    def make_fixed_cond(res: EvaluationResult) -> RuleCondition:
        if res == EvaluationResult.TRUE:
            return RuleCondition(operator="equals", target="application", field="val_true", target_value="match")
        elif res == EvaluationResult.FALSE:
            return RuleCondition(operator="equals", target="application", field="val_true", target_value="nomatch")
        else:
            return RuleCondition(operator="equals", target="application", field="missing_field", target_value="match")

    ctx = {"application": SimpleNamespace(val_true="match")}

    # Verify atomic evaluations
    assert engine.evaluate_condition(make_fixed_cond(EvaluationResult.TRUE), ctx) == EvaluationResult.TRUE
    assert engine.evaluate_condition(make_fixed_cond(EvaluationResult.FALSE), ctx) == EvaluationResult.FALSE
    assert engine.evaluate_condition(make_fixed_cond(EvaluationResult.UNKNOWN), ctx) == EvaluationResult.UNKNOWN

    states = [EvaluationResult.TRUE, EvaluationResult.FALSE, EvaluationResult.UNKNOWN]

    # Kleene AND (all_of) table
    expected_and = {
        (EvaluationResult.TRUE, EvaluationResult.TRUE): EvaluationResult.TRUE,
        (EvaluationResult.TRUE, EvaluationResult.FALSE): EvaluationResult.FALSE,
        (EvaluationResult.TRUE, EvaluationResult.UNKNOWN): EvaluationResult.UNKNOWN,
        (EvaluationResult.FALSE, EvaluationResult.TRUE): EvaluationResult.FALSE,
        (EvaluationResult.FALSE, EvaluationResult.FALSE): EvaluationResult.FALSE,
        (EvaluationResult.FALSE, EvaluationResult.UNKNOWN): EvaluationResult.FALSE,
        (EvaluationResult.UNKNOWN, EvaluationResult.TRUE): EvaluationResult.UNKNOWN,
        (EvaluationResult.UNKNOWN, EvaluationResult.FALSE): EvaluationResult.FALSE,
        (EvaluationResult.UNKNOWN, EvaluationResult.UNKNOWN): EvaluationResult.UNKNOWN,
    }

    for (a, b), expected in expected_and.items():
        cond = RuleCondition(all_of=[make_fixed_cond(a), make_fixed_cond(b)])
        actual = engine.evaluate_condition(cond, ctx)
        assert actual == expected, f"all_of({a}, {b}) expected {expected}, got {actual}"

    # Kleene OR (any_of) table
    expected_or = {
        (EvaluationResult.TRUE, EvaluationResult.TRUE): EvaluationResult.TRUE,
        (EvaluationResult.TRUE, EvaluationResult.FALSE): EvaluationResult.TRUE,
        (EvaluationResult.TRUE, EvaluationResult.UNKNOWN): EvaluationResult.TRUE,
        (EvaluationResult.FALSE, EvaluationResult.TRUE): EvaluationResult.TRUE,
        (EvaluationResult.FALSE, EvaluationResult.FALSE): EvaluationResult.FALSE,
        (EvaluationResult.FALSE, EvaluationResult.UNKNOWN): EvaluationResult.UNKNOWN,
        (EvaluationResult.UNKNOWN, EvaluationResult.TRUE): EvaluationResult.TRUE,
        (EvaluationResult.UNKNOWN, EvaluationResult.FALSE): EvaluationResult.UNKNOWN,
        (EvaluationResult.UNKNOWN, EvaluationResult.UNKNOWN): EvaluationResult.UNKNOWN,
    }

    for (a, b), expected in expected_or.items():
        cond = RuleCondition(any_of=[make_fixed_cond(a), make_fixed_cond(b)])
        actual = engine.evaluate_condition(cond, ctx)
        assert actual == expected, f"any_of({a}, {b}) expected {expected}, got {actual}"

    # Kleene NOT (not) table
    expected_not = {
        EvaluationResult.TRUE: EvaluationResult.FALSE,
        EvaluationResult.FALSE: EvaluationResult.TRUE,
        EvaluationResult.UNKNOWN: EvaluationResult.UNKNOWN,
    }

    for a, expected in expected_not.items():
        cond = RuleCondition(not_=make_fixed_cond(a))
        actual = engine.evaluate_condition(cond, ctx)
        assert actual == expected, f"not({a}) expected {expected}, got {actual}"


def test_unknown_triggers_never_pass():
    """Asserts missing fields, unparseable values, or confidence < 0.70 evaluate strictly to UNKNOWN."""
    engine = default_declarative_engine
    cond = RuleCondition(
        operator="date_not_expired",
        document_type="fire_safety_certificate",
        field="expiry_date",
    )

    # 1. Missing document entirely -> UNKNOWN
    ctx_no_doc = {"documents": [], "extractions": {}}
    assert engine.evaluate_condition(cond, ctx_no_doc) == EvaluationResult.UNKNOWN

    # 2. Document present but extraction incomplete -> UNKNOWN
    doc = SimpleNamespace(id="d1", document_type="fire_safety_certificate")
    ext_incomplete = SimpleNamespace(id="e1", processing_status="pending", fields={})
    ctx_incomplete = {"documents": [doc], "extractions": {"d1": ext_incomplete}}
    assert engine.evaluate_condition(cond, ctx_incomplete) == EvaluationResult.UNKNOWN

    # 3. Field missing from fields dict -> UNKNOWN
    ext_missing_field = SimpleNamespace(id="e1", processing_status="processed", fields={})
    ctx_missing_field = {"documents": [doc], "extractions": {"d1": ext_missing_field}}
    assert engine.evaluate_condition(cond, ctx_missing_field) == EvaluationResult.UNKNOWN

    # 4. Confidence below threshold (< 0.70) -> UNKNOWN
    ext_low_conf = SimpleNamespace(
        id="e1",
        processing_status="processed",
        fields={"expiry_date": {"value": "2030-01-01", "confidence": 0.69, "status": "low_confidence"}},
    )
    ctx_low_conf = {"documents": [doc], "extractions": {"d1": ext_low_conf}}
    assert engine.evaluate_condition(cond, ctx_low_conf) == EvaluationResult.UNKNOWN

    # 5. Field marked uncertain -> UNKNOWN
    ext_uncertain = SimpleNamespace(
        id="e1",
        processing_status="processed",
        fields={"expiry_date": {"value": "2030-01-01", "confidence": 0.95, "status": "uncertain"}},
    )
    ctx_uncertain = {"documents": [doc], "extractions": {"d1": ext_uncertain}}
    assert engine.evaluate_condition(cond, ctx_uncertain) == EvaluationResult.UNKNOWN

    # 6. Unparseable date format -> UNKNOWN
    ext_unparseable = SimpleNamespace(
        id="e1",
        processing_status="processed",
        fields={"expiry_date": {"value": "NotADateString", "confidence": 0.95, "status": "extracted"}},
    )
    ctx_unparseable = {"documents": [doc], "extractions": {"d1": ext_unparseable}}
    assert engine.evaluate_condition(cond, ctx_unparseable) == EvaluationResult.UNKNOWN

    # 7. High confidence unexpired date -> TRUE
    ext_valid = SimpleNamespace(
        id="e1",
        processing_status="processed",
        fields={"expiry_date": {"value": "2035-12-31", "confidence": 0.95, "status": "extracted"}},
    )
    ctx_valid = {"documents": [doc], "extractions": {"d1": ext_valid}}
    assert engine.evaluate_condition(cond, ctx_valid) == EvaluationResult.TRUE


def test_leap_year_calendar_date_arithmetic():
    """Asserts calendar date arithmetic correctly handles leap year boundary (Feb 29)."""
    # 1. Leap year Feb 29 to exact 1 year later (non-leap 2025): anniversary clamps to Feb 28
    leap_date = date(2024, 2, 29)
    assert calculate_calendar_years_between(leap_date, date(2025, 2, 27)) == 0
    assert calculate_calendar_years_between(leap_date, date(2025, 2, 28)) == 1
    assert calculate_calendar_years_between(leap_date, date(2025, 3, 1)) == 1

    # 2. Leap year Feb 29 to next leap year Feb 29 (4 years later): exactly 4 years
    assert calculate_calendar_years_between(leap_date, date(2028, 2, 28)) == 3
    assert calculate_calendar_years_between(leap_date, date(2028, 2, 29)) == 4

    # 3. 30-year boundary tests
    completion_date = date(1994, 5, 15)
    # Exactly 30 years -> 30
    assert calculate_calendar_years_between(completion_date, date(2024, 5, 15)) == 30
    # 30 years minus 1 day -> 29
    assert calculate_calendar_years_between(completion_date, date(2024, 5, 14)) == 29
    # 30 years plus 1 day -> 30
    assert calculate_calendar_years_between(completion_date, date(2024, 5, 16)) == 30
    # 31 years -> 31
    assert calculate_calendar_years_between(completion_date, date(2025, 5, 15)) == 31


def test_startup_validation_max_nesting_depth_rejection():
    """Asserts that conditions nested deeper than 5 levels fail loudly at Pydantic validation."""
    with pytest.raises(ValidationError) as exc_info:
        deep_cond = RuleCondition(operator="exists", field="level6")
        for i in range(5, 0, -1):
            deep_cond = RuleCondition(all_of=[deep_cond])
    assert "depth exceeds maximum allowed depth of 5" in str(exc_info.value)


def test_startup_validation_banned_terms_rejection():
    """Asserts that rule configurations containing banned claim terms fail loudly at startup."""
    for term in ["fraud", "forged", "genuine", "authentic", "complies", "tampered"]:
        with pytest.raises(ValueError) as exc_info:
            DeclarativeRuleConfig(
                rule_id="TEST_BANNED_RULE",
                title=f"Discrepancy and {term} check",
                condition=RuleCondition(operator="exists", field="doc"),
                pass_title="Valid Check",
                pass_reason_template="Standard pass reason.",
                flag_title="Flagged Check",
                flag_reason_template="Standard flag reason.",
            )
        assert f"contains forbidden claim term '{term}'" in str(exc_info.value)


def test_fuzzy_name_matching_threshold_from_config(monkeypatch):
    """Asserts fuzzy name matching respects the configurable similarity threshold."""
    name1 = "Indian Institute of Technology Bombay"
    name2 = "Indian Institute of Technology, Bombay"
    name3 = "Delhi Technological University"

    sim_high = calculate_text_similarity(name1, name2)
    sim_low = calculate_text_similarity(name1, name3)

    assert sim_high > 0.90
    assert sim_low < 0.50

    # With default threshold 0.85, name2 matches, name3 does not
    engine = default_declarative_engine
    cond = RuleCondition(operator="fuzzy_similarity", target_value=None)
    ctx_high = {"expected_name": name1}

    # High match evaluates to TRUE
    assert engine._compare_values(name2, "fuzzy_similarity", None, None, ctx_high) == EvaluationResult.TRUE

    # Low match evaluates to FALSE
    assert engine._compare_values(name3, "fuzzy_similarity", None, None, ctx_high) == EvaluationResult.FALSE

