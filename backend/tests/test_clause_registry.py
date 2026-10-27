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
        "APH_2024_27_ANNEX_2_CLAUSE_2_1",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_I",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_II",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_III",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_IV",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_V",
        "APH_2024_27_CHAP_2_TABLE_2_1",
        "APH_2024_27_CLAUSE_6_17_G",
        "APH_2024_27_CLAUSE_6_17_H",
        "APH_2024_27_CLAUSE_6_17_I",
        "APH_2024_27_CLAUSE_6_17_J",
        "APH_2024_27_ANNEX_3_CLAUSE_3_1_D",
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
        assert len(citation.excerpt) > 0, f"Clause {cid} must have a non-empty verbatim excerpt"


def test_declarative_rules_yaml_validates():
    """Validates rules_eoa.yaml schema against DeclarativeRuleConfig model and ClauseRegistry."""
    engine = DeclarativeRuleEngine(DEFAULT_RULES_YAML_PATH)
    assert len(engine.rules) >= 6

    rule_ids = [r.rule_id for r in engine.rules]
    assert "DOC_PRESENCE_001" in rule_ids
    assert "FIELD_001" in rule_ids
    assert "EXPIRY_001" in rule_ids
    assert "CONSISTENCY_001" in rule_ids
    assert "TER_PAYMENT_001" in rule_ids
    assert "STRUCTURAL_001" in rule_ids

    # Verify that every rule has a valid registered clause or is an internal check
    for rule in engine.rules:
        if rule.clause_id is not None:
            clause = engine.clause_registry.get(rule.clause_id)
            assert clause is not None, f"Rule {rule.rule_id} references ungrounded clause {rule.clause_id}"
        else:
            assert rule.signal_type == "internal_check", (
                f"Rule {rule.rule_id} has null clause_id but signal_type is not 'internal_check'"
            )


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


def test_every_clause_excerpt_matches_pdf_page():
    """
    CI test asserting that every statutory registry entry has a verbatim excerpt
    that exists character-for-character on its stated PDF page in AICTE rulebook.pdf.
    """
    import fitz  # PyMuPDF
    pdf_path = Path(__file__).resolve().parent.parent.parent / "AICTE rulebook.pdf"
    assert pdf_path.exists(), f"AICTE rulebook.pdf not found at {pdf_path}"

    doc = fitz.open(str(pdf_path))
    registry = ClauseRegistry(DEFAULT_CLAUSES_PATH)
    clauses = registry.all()

    assert len(clauses) >= 14

    for cid, citation in clauses.items():
        assert citation.excerpt, f"Clause {cid} must have a non-empty verbatim excerpt"
        assert 1 <= citation.pdf_page <= len(doc), f"Invalid pdf_page {citation.pdf_page} for {cid}"

        page = doc[citation.pdf_page - 1]
        page_text = page.get_text()

        # Normalize whitespace for robust comparison
        normalized_page_text = " ".join(page_text.split())
        normalized_excerpt = " ".join(citation.excerpt.split())

        assert normalized_excerpt in normalized_page_text, (
            f"Statutory excerpt for '{cid}' not found on PDF page {citation.pdf_page}!\n"
            f"Expected excerpt:\n{normalized_excerpt}\n"
            f"Page content sample:\n{normalized_page_text[:300]}"
        )
