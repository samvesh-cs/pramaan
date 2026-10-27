"""
Unit and Schema Integrity Tests for Clause Registry and Declarative Rule Definitions.
Validates statutory clause citations against physical pages of AICTE Approval Process Handbook (APH 2024–2027).
"""

from pathlib import Path
import pytest

from app.rules.declarative_engine import ClauseRegistry, DeclarativeRuleEngine, DEFAULT_CLAUSES_PATH, DEFAULT_RULES_YAML_PATH
from app.schemas.rule_definition import DeclarativeRuleConfig


def test_clause_registry_loads_all_citations():
    """Validates that ClauseRegistry loads all statutory citations."""
    registry = ClauseRegistry(DEFAULT_CLAUSES_PATH)
    clauses = registry.all()

    expected_clauses = [
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_I",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_II",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_III",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_IV",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_V",
        "APH_2024_27_CHAP_2_TABLE_2_1",
        "APH_2024_27_CLAUSE_7_16",
        "APH_2024_27_CLAUSE_7_17",
        "APH_2024_27_ANNEX_14",
        "APH_2024_27_AFFIDAVIT_2",
    ]

    for cid in expected_clauses:
        assert cid in clauses, f"Missing verified statutory clause: {cid}"
        citation = clauses[cid]
        assert citation.clause_id == cid
        assert citation.handbook_page > 0
        assert citation.pdf_page > citation.handbook_page or citation.pdf_page > 0
        assert len(citation.title) > 0


def test_declarative_rules_yaml_validates():
    """Validates rules_eoa.yaml schema against DeclarativeRuleConfig model and ClauseRegistry."""
    engine = DeclarativeRuleEngine(DEFAULT_RULES_YAML_PATH)
    assert len(engine.rules) >= 6

    rule_ids = [r.rule_id for r in engine.rules]
    assert "DOC_PRESENCE_001" in rule_ids
    assert "EXPIRY_001" in rule_ids
    assert "CONSISTENCY_001" in rule_ids
    assert "TER_PAYMENT_001" in rule_ids
    assert "STRUCTURAL_001" in rule_ids

    # Verify that every rule has a valid registered clause
    for rule in engine.rules:
        clause = engine.clause_registry.get(rule.clause_id)
        assert clause is not None, f"Rule {rule.rule_id} references ungrounded clause {rule.clause_id}"


def test_invalid_yaml_fails_loudly_at_startup(tmp_path: Path):
    """(Edge Case E-03) Invalid YAML or schema raises ValueError at startup, never request time."""
    bad_yaml = tmp_path / "bad_rules.yaml"
    bad_yaml.write_text("invalid: [broken yaml", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid YAML syntax"):
        DeclarativeRuleEngine(bad_yaml)

    bad_schema = tmp_path / "bad_schema.yaml"
    bad_schema.write_text("""
version: "1.0"
rules:
  - rule_id: "INCOMPLETE_RULE"
    # Missing title, condition, and templates
""", encoding="utf-8")

    with pytest.raises(ValueError, match="Schema validation failure"):
        DeclarativeRuleEngine(bad_schema)
