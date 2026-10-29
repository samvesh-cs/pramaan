"""
Unit and Schema Integrity Tests for Clause Registry and Declarative Rule Definitions.
Validates handbook clause citations against physical pages of AICTE Approval Process Handbook (APH 2024–2027).
"""

import os
from pathlib import Path
import pytest

from app.rules.declarative_engine import ClauseRegistry, DeclarativeRuleEngine, DEFAULT_CLAUSES_PATH, DEFAULT_RULES_YAML_PATH
from app.schemas.rule_definition import DeclarativeRuleConfig


def normalize_text(text: str) -> str:
    """Normalizes whitespace, non-breaking spaces, and quotes (smart to straight)."""
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("`", "'")
        .replace("\u00a0", " ")
    )
    return " ".join(text.split())


def get_pdf_path() -> Path:
    """
    Locates the AICTE rulebook PDF file.
    Prefers environment variable PRAMAAN_APH_PDF, with repo-relative lookup as fallback.
    """
    env_path = os.getenv("PRAMAAN_APH_PDF")
    if env_path:
        return Path(env_path)

    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        repo_root / "docs" / "reference" / "AICTE_rulebook.pdf",
        repo_root / "docs" / "reference" / "AICTE rulebook.pdf",
        repo_root / "AICTE_rulebook.pdf",
        repo_root / "AICTE rulebook.pdf",
        repo_root / "AICTE Approval Process Handbook.pdf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return repo_root / "docs" / "reference" / "AICTE_rulebook.pdf"


EXPECTED_RULEBOOK_SHA256 = "153d54816f2cf11489218e239113544e8d49b73680009688baa7dc4880636051"


def test_rulebook_pdf_sha256_and_presence():
    """
    (Item 6) Asserts that the AICTE rulebook PDF exists and matches the verified SHA-256 digest.
    Fails loudly (not skip) if the PDF is missing or corrupted.
    """
    import hashlib

    pdf_path = get_pdf_path()
    assert pdf_path.exists(), (
        f"AICTE rulebook PDF not found at {pdf_path}! "
        f"Place 'AICTE_rulebook.pdf' in docs/reference/ or set PRAMAAN_APH_PDF environment variable. "
        f"Test must fail if PDF is missing."
    )

    actual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    assert actual_hash == EXPECTED_RULEBOOK_SHA256, (
        f"AICTE rulebook SHA-256 hash mismatch! Expected {EXPECTED_RULEBOOK_SHA256}, got {actual_hash}"
    )


def test_clause_registry_loads_all_citations():
    """Validates that ClauseRegistry loads all citations and verifies metadata consistency."""
    registry = ClauseRegistry(DEFAULT_CLAUSES_PATH)
    clauses = registry.all()

    expected_clauses = [
        "APH_2024_27_ANNEX_2_CLAUSE_2_1",
        "APH_2024_27_ANNEX_2_CLAUSE_2_1_PREAMBLE",
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
        "APH_2024_27_AFFIDAVIT_2_ITEM_5",
        "APH_2024_27_AFFIDAVIT_2_ITEM_7",
    ]

    for cid in expected_clauses:
        assert cid in clauses, f"Missing verified clause: {cid}"
        citation = clauses[cid]
        assert citation.clause_id == cid
        assert citation.handbook_page > 0
        assert citation.pdf_page == citation.handbook_page + 16, (
            f"Offset mismatch for {cid}: pdf_page {citation.pdf_page} != handbook_page {citation.handbook_page} + 16"
        )
        assert citation.verified is True
        assert len(citation.title) > 0
        assert len(citation.excerpt) > 0, f"Clause {cid} must have a non-empty verbatim excerpt"


def test_declarative_rules_yaml_validates():
    """
    Validates rules_eoa.yaml schema against DeclarativeRuleConfig model and ClauseRegistry.
    Retains in-memory clause cross-check to guarantee offline unit-test schema grounding without requiring PDF.
    """
    engine = DeclarativeRuleEngine(DEFAULT_RULES_YAML_PATH)
    assert len(engine.rules) >= 7

    rule_ids = [r.rule_id for r in engine.rules]
    assert "DOC_PRESENCE_001" in rule_ids
    assert "FIELD_001" in rule_ids
    assert "EXPIRY_001" in rule_ids
    assert "CONSISTENCY_001" in rule_ids
    assert "TER_PAYMENT_001" in rule_ids
    assert "STRUCTURAL_001" in rule_ids
    assert "STRUCTURAL_002" in rule_ids

    # Verify every referenced clause exists in clauses.json and internal checks have null clause_id
    for rule in engine.rules:
        if rule.clause_id is not None:
            clause = engine.clause_registry.get(rule.clause_id)
            assert clause is not None, f"Rule {rule.rule_id} references ungrounded clause {rule.clause_id}"
        else:
            assert rule.signal_type == "internal_check", (
                f"Rule {rule.rule_id} has null clause_id but signal_type is not 'internal_check'"
            )

        for cid in (rule.clause_ids or []):
            assert engine.clause_registry.get(cid) is not None, (
                f"Rule {rule.rule_id} references ungrounded clause_id '{cid}' in clause_ids list"
            )


def test_clause_id_is_member_of_clause_ids():
    """
    (Item 12) Asserts that for every rule where clause_id is not null, clause_id is a member of clause_ids.
    clause_ids is canonical; clause_id serves as the primary citation entry.
    """
    engine = DeclarativeRuleEngine(DEFAULT_RULES_YAML_PATH)
    for rule in engine.rules:
        if rule.clause_id is not None:
            assert rule.clause_ids is not None and len(rule.clause_ids) > 0, (
                f"Rule '{rule.rule_id}' has primary clause_id '{rule.clause_id}' but clause_ids is empty"
            )
            assert rule.clause_id in rule.clause_ids, (
                f"Rule '{rule.rule_id}' primary clause_id '{rule.clause_id}' is not in clause_ids: {rule.clause_ids}"
            )


def test_no_rule_relies_solely_on_heading_locator():
    """
    (Item 11) Asserts that no rule with statutory citations relies solely on 'heading_locator' excerpts.
    Every rule that cites handbook clauses must cite at least one substantive clause.
    """
    engine = DeclarativeRuleEngine(DEFAULT_RULES_YAML_PATH)
    registry = engine.clause_registry

    for rule in engine.rules:
        supporting_cids = list(rule.clause_ids or [])
        if rule.clause_id and rule.clause_id not in supporting_cids:
            supporting_cids.append(rule.clause_id)

        # Internal checks (FIELD_001, CONSISTENCY_001) have no clause citations
        if not supporting_cids:
            continue

        supporting_clauses = [registry.get(cid) for cid in supporting_cids if registry.get(cid) is not None]
        substantive_clauses = [c for c in supporting_clauses if c.excerpt_type != "heading_locator"]

        assert len(substantive_clauses) > 0, (
            f"Rule '{rule.rule_id}' relies solely on heading_locator clauses: {supporting_cids}. "
            f"At least one substantive excerpt is required."
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
    CI Test:
    1. Fails explicitly (not skip) if AICTE rulebook PDF is missing.
    2. Configurable via PRAMAAN_APH_PDF env var with repo fallback.
    3. For every entry with verified: true in clauses.json:
       - Asserts pdf_page == handbook_page + 16.
       - Extracts text from pdf_page with PyMuPDF inside context manager.
       - Normalizes whitespace and quotes.
       - Asserts verbatim excerpt is present character-for-character.
    """
    import pymupdf

    pdf_path = get_pdf_path()
    assert pdf_path.exists(), (
        f"AICTE rulebook PDF not found at {pdf_path}! "
        f"Set PRAMAAN_APH_PDF environment variable or place 'AICTE rulebook.pdf' at repo root. "
        f"Test must fail if PDF is missing."
    )

    registry = ClauseRegistry(DEFAULT_CLAUSES_PATH)
    clauses = registry.all()
    assert len(clauses) >= 14

    with pymupdf.open(str(pdf_path)) as doc:
        for cid, citation in clauses.items():
            if citation.verified:
                # 1. Page offset check: PDF page = handbook printed page + 16
                assert citation.pdf_page == citation.handbook_page + 16, (
                    f"Offset mismatch for {cid}: pdf_page {citation.pdf_page} != handbook_page {citation.handbook_page} + 16"
                )

                assert 1 <= citation.pdf_page <= len(doc), f"Invalid pdf_page {citation.pdf_page} for {cid}"

                page = doc[citation.pdf_page - 1]
                page_text = page.get_text()

                # 2. Normalize whitespace and quotes
                normalized_page_text = normalize_text(page_text)
                normalized_excerpt = normalize_text(citation.excerpt)

                # 3. Assert excerpt is present character-for-character
                assert normalized_excerpt in normalized_page_text, (
                    f"Excerpt for '{cid}' not found on PDF page {citation.pdf_page}!\n"
                    f"Expected excerpt:\n{normalized_excerpt}\n"
                    f"Page content sample:\n{normalized_page_text[:300]}"
                )


import ast


def test_honest_claims_language_in_rules():
    """
    (Item 13) Asserts no finding text or reason template in rules_eoa.yaml or legacy Python rules makes overreaching claims.
    Forbidden terms:
      - Original four: 'fraud', 'genuine', 'verified issuer', 'valid signature'
      - Extended six: 'contravention', 'violation', 'non-compliant', 'tampered', 'forged', 'authentic'
      - Administrative norm boundary: 'statutory' (the handbook is an administrative norm, not a statute)
      - Verification claim boundary: 'verified' (unless qualified as 'unverified', 'not verified', or 'cannot be verified')
    """
    engine = DeclarativeRuleEngine(DEFAULT_RULES_YAML_PATH)
    forbidden_terms = [
        "fraud",
        "genuine",
        "verified issuer",
        "valid signature",
        "contravention",
        "violation",
        "non-compliant",
        "tampered",
        "forged",
        "authentic",
        "complies",
        "complying",
    ]

    def validate_text(text: str, context_label: str, enforce_verified_statutory_ban: bool = True):
        t = text.lower()
        # 1. 10 core forbidden terms
        for term in forbidden_terms:
            assert term not in t, (
                f"{context_label} contains forbidden claim term '{term}' in finding text: {text}"
            )

        if enforce_verified_statutory_ban:
            # 2. Ban 'statutory'
            assert "statutory" not in t, (
                f"{context_label} contains 'statutory' (handbook norms are not statutes): {text}"
            )
            # 3. Ban 'verified' unless qualified
            t_clean = t.replace("cannot be verified", "").replace("not verified", "").replace("unverified", "")
            assert "verified" not in t_clean, (
                f"{context_label} contains unqualified claim 'verified': {text}"
            )

    # 1. Check declarative rules from rules_eoa.yaml (strictly enforce all bans)
    for rule in engine.rules:
        combined_text = (
            f"{rule.title} {rule.pass_title} {rule.pass_reason_template} "
            f"{rule.flag_title} {rule.flag_reason_template} {rule.next_action or ''}"
        )
        validate_text(combined_text, f"Declarative rule '{rule.rule_id}'", enforce_verified_statutory_ban=True)

    # 2. Check legacy Python rules in app/rules/
    # All legacy rules must satisfy the 10 forbidden terms.
    # Rules other than the 2 live-rule overclaims scheduled for A0/A0b neutralization
    # (ter_payment_check.py and building_age_check.py) also enforce the statutory/verified ban.
    rules_dir = Path(__file__).resolve().parent.parent / "app" / "rules"
    legacy_snippets: list[tuple[str, str, str]] = []
    for py_file in rules_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if func_name == "FindingCreate":
                    for kw in node.keywords:
                        if kw.arg in ("title", "reason", "next_action"):
                            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                                legacy_snippets.append((py_file.name, kw.arg, kw.value.value))
                            elif isinstance(kw.value, ast.JoinedStr):
                                parts = [str(p.value) for p in kw.value.values if isinstance(p, ast.Constant)]
                                legacy_snippets.append((py_file.name, kw.arg, "".join(parts)))

    for file_name, field, text in legacy_snippets:
        validate_text(
            text,
            f"Legacy rule '{file_name}' [{field}]",
            enforce_verified_statutory_ban=True,
        )


def test_load_time_banned_terms_rejection_from_yaml(tmp_path: Path):
    """Proves that DeclarativeRuleEngine rejects a YAML ruleset containing banned terms at load time."""
    banned_yaml_content = """
version: "1.0"
category: "eoa"
description: "Ruleset with banned terms"
rules:
  - rule_id: "BANNED_TEST_001"
    title: "Document genuine check"
    category: "eoa"
    condition:
      operator: "exists"
      field: "doc"
    pass_title: "Valid"
    pass_reason_template: "Document is authentic"
    flag_title: "Document forged or tampered"
    flag_reason_template: "Possible fraud detected"
    next_action: "Report fraud to authority"
"""
    yaml_file = tmp_path / "banned_rules.yaml"
    yaml_file.write_text(banned_yaml_content, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        DeclarativeRuleEngine(rules_path=yaml_file)

    assert "contains forbidden claim term" in str(exc_info.value)



