"""
Step B5 Replay and Parity Harness.
Runs BOTH legacy rule engine and declarative rule engine across:
(a) The full synthetic dataset / scenarios.
(b) Every application stored in the dev database (read-only).
(c) Generated boundary fixtures from Step B2.

Outputs a structured discrepancy report (rule_id, legacy_status, declarative_status, reason_code).
Exits non-zero on any discrepancy not on the explicit allow-list.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Optional

from app.rules.base import BaseRule
from app.rules.building_age_check import BuildingAgeStructuralStabilityRule
from app.rules.cross_document_check import InstitutionNameConsistencyRule
from app.rules.declarative_engine import default_declarative_engine
from app.rules.duplicate_check import DuplicateDocumentRule
from app.rules.expiry_check import ExpiryDateRule
from app.rules.field_completeness import FieldCompletenessRule
from app.rules.legacy_adapter import wrap_legacy_rules
from app.rules.presence_check import DocumentPresenceRule
from app.rules.ter_payment_check import TerPaymentRule
from app.schemas.finding import FindingCreate

# Explicit allow-list for intentional differences approved by human reviewer.
# Format: {(context_id, rule_id): "written justification"}
ALLOW_LIST: dict[tuple[str, str], str] = {}


@dataclass
class Discrepancy:
    context_id: str
    rule_id: str
    legacy_status: Optional[str]
    declarative_status: Optional[str]
    reason_code: str
    details: str = ""


@dataclass
class ParityReport:
    total_contexts: int = 0
    total_rule_evaluations: int = 0
    matches: int = 0
    discrepancies: list[Discrepancy] = field(default_factory=list)

    @property
    def unallowed_discrepancies(self) -> list[Discrepancy]:
        unallowed: list[Discrepancy] = []
        for d in self.discrepancies:
            key = (d.context_id, d.rule_id)
            if key not in ALLOW_LIST:
                unallowed.append(d)
            else:
                justification = ALLOW_LIST.get(key, "")
                if not justification or len(justification.strip()) < 10:
                    d.reason_code = "ALLOW_LIST_MISSING_JUSTIFICATION"
                    unallowed.append(d)
        return unallowed


def get_legacy_engine_rules() -> list[BaseRule]:
    raw_rules: list[BaseRule] = [
        DocumentPresenceRule(),
        FieldCompletenessRule(),
        ExpiryDateRule(),
        InstitutionNameConsistencyRule(),
        TerPaymentRule(),
        BuildingAgeStructuralStabilityRule(),
        DuplicateDocumentRule(),
    ]
    return wrap_legacy_rules(raw_rules)


def evaluate_legacy_rules(context: dict[str, Any]) -> list[FindingCreate]:
    legacy_rules = get_legacy_engine_rules()
    findings: list[FindingCreate] = []
    for rule in legacy_rules:
        findings.extend(rule.evaluate(context))
    return findings


def compare_context_findings(
    context_id: str,
    context: dict[str, Any],
) -> tuple[int, list[Discrepancy]]:
    """Evaluates context with both engines and returns match count and discrepancies."""
    leg_findings = evaluate_legacy_rules(context)
    dec_findings = default_declarative_engine.evaluate(context)

    leg_map = {f.rule_id: f for f in leg_findings}
    dec_map = {f.rule_id: f for f in dec_findings}

    all_rule_ids = sorted(set(leg_map.keys()) | set(dec_map.keys()))
    discrepancies: list[Discrepancy] = []
    matches = 0

    for rid in all_rule_ids:
        leg_f = leg_map.get(rid)
        dec_f = dec_map.get(rid)

        if leg_f is None and dec_f is not None:
            discrepancies.append(
                Discrepancy(
                    context_id=context_id,
                    rule_id=rid,
                    legacy_status=None,
                    declarative_status=dec_f.status,
                    reason_code="RULE_MISSING_IN_LEGACY",
                    details=f"Declarative produced finding for {rid} but legacy did not.",
                )
            )
        elif leg_f is not None and dec_f is None:
            discrepancies.append(
                Discrepancy(
                    context_id=context_id,
                    rule_id=rid,
                    legacy_status=leg_f.status,
                    declarative_status=None,
                    reason_code="RULE_MISSING_IN_DECLARATIVE",
                    details=f"Legacy produced finding for {rid} but declarative did not.",
                )
            )
        elif leg_f and dec_f:
            if leg_f.status != dec_f.status:
                discrepancies.append(
                    Discrepancy(
                        context_id=context_id,
                        rule_id=rid,
                        legacy_status=leg_f.status,
                        declarative_status=dec_f.status,
                        reason_code="STATUS_MISMATCH",
                        details=f"Status mismatch on {rid}: legacy='{leg_f.status}', declarative='{dec_f.status}'.",
                    )
                )
            else:
                matches += 1

    return matches, discrepancies


def build_boundary_fixture_contexts() -> list[tuple[str, dict[str, Any]]]:
    """Generates all boundary contexts from B2 requirements."""
    contexts = []

    def make_ctx(doc_type, fields, comp_date="2020-01-01", app_name="Pramaan College"):
        doc = SimpleNamespace(
            id="d1",
            document_type=doc_type,
            processing_status="processed",
            original_filename=f"{doc_type}.pdf",
            file_hash="hash1",
            application_id="app_1",
        )
        ext = SimpleNamespace(processing_status="processed", fields=fields)
        app = SimpleNamespace(
            id="app_1",
            institution_name=app_name,
            academic_year="2026-27",
            status="submitted",
        )
        return {
            "application": app,
            "documents": [doc],
            "extractions": {"d1": ext},
            "all_system_documents": [doc],
        }

    # 1. Confidence boundaries (0.70, 0.699, 0.701)
    for conf, label in [(0.70, "conf_0.70"), (0.699, "conf_0.699"), (0.701, "conf_0.701")]:
        ctx = make_ctx(
            "fire_safety_certificate",
            {
                "institution_name": {"value": "Pramaan College", "confidence": conf, "status": "extracted"},
                "certificate_number": {"value": "F-101", "confidence": conf, "status": "extracted"},
                "issue_date": {"value": "2023-01-01", "confidence": conf, "status": "extracted"},
                "expiry_date": {"value": "2028-01-01", "confidence": conf, "status": "extracted"},
                "issuing_authority": {"value": "Fire Dept", "confidence": conf, "status": "extracted"},
            },
        )
        contexts.append((f"boundary_{label}", ctx))

    # 2. Expiry boundaries (cutoff date, cutoff - 1, cutoff + 1)
    cutoff = date.today()
    for exp, label in [
        (cutoff.isoformat(), "expiry_equal_cutoff"),
        ((cutoff - timedelta(days=1)).isoformat(), "expiry_cutoff_minus_1"),
        ((cutoff + timedelta(days=1)).isoformat(), "expiry_cutoff_plus_1"),
    ]:
        ctx = make_ctx(
            "fire_safety_certificate",
            {
                "institution_name": {"value": "Pramaan College", "confidence": 0.95, "status": "extracted"},
                "certificate_number": {"value": "F-101", "confidence": 0.95, "status": "extracted"},
                "issue_date": {"value": "2020-01-01", "confidence": 0.95, "status": "extracted"},
                "expiry_date": {"value": exp, "confidence": 0.95, "status": "extracted"},
                "issuing_authority": {"value": "Fire Dept", "confidence": 0.95, "status": "extracted"},
            },
        )
        contexts.append((f"boundary_{label}", ctx))

    # 3. Building age boundaries (30 yrs, 30 yrs + 1 day)
    ctx_30 = make_ctx(
        "building_completion_certificate",
        {
            "institution_name": {"value": "Pramaan College", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "B-101", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "1994-05-15", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Municipal Corp", "confidence": 0.95, "status": "extracted"},
        },
    )
    contexts.append(("boundary_building_age_30_years", ctx_30))

    ctx_30_plus = make_ctx(
        "building_completion_certificate",
        {
            "institution_name": {"value": "Pramaan College", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "B-101", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "1994-05-14", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Municipal Corp", "confidence": 0.95, "status": "extracted"},
        },
    )
    contexts.append(("boundary_building_age_30_years_plus_1d", ctx_30_plus))

    # 4. Unicode Devanagari Hindi name
    hindi_name = "भारतीय प्रौद्योगिकी संस्थान मुंबई"
    ctx_hindi = make_ctx(
        "affidavit_2",
        {
            "institution_name": {"value": hindi_name, "confidence": 0.95, "status": "extracted"},
            "affidavit_date": {"value": "2024-01-01", "confidence": 0.95, "status": "extracted"},
            "deponent_name": {"value": "अध्यक्ष", "confidence": 0.95, "status": "extracted"},
        },
        app_name=hindi_name,
    )
    contexts.append(("boundary_hindi_name_match", ctx_hindi))

    # 5. Empty / whitespace values
    ctx_empty = make_ctx(
        "fire_safety_certificate",
        {
            "institution_name": {"value": "   \n\t  ", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": None, "confidence": 0.0, "status": "unextracted"},
            "expiry_date": {"value": "   ", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "", "confidence": 0.95, "status": "extracted"},
        },
    )
    contexts.append(("boundary_empty_whitespace_fields", ctx_empty))

    return contexts


def build_synthetic_scenario_contexts() -> list[tuple[str, dict[str, Any]]]:
    """Builds contexts representing all 5 synthetic test scenarios plus A0/A0b cases."""
    contexts = []

    doc_fire = SimpleNamespace(id="d_f", document_type="fire_safety_certificate", processing_status="processed", original_filename="fire.pdf", file_hash="h1", application_id="app_syn")
    doc_bcc = SimpleNamespace(id="d_b", document_type="building_completion_certificate", processing_status="processed", original_filename="bcc.pdf", file_hash="h2", application_id="app_syn")
    doc_aff = SimpleNamespace(id="d_a", document_type="affidavit_2", processing_status="processed", original_filename="aff.pdf", file_hash="h3", application_id="app_syn")

    ext_fire = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "FS-2024-098", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2024-01-10", "confidence": 0.95, "status": "extracted"},
            "expiry_date": {"value": "2027-01-09", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Fire Department", "confidence": 0.95, "status": "extracted"},
        },
    )
    ext_bcc = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "BCC-2018-042", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2018-05-15", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Municipal Corporation", "confidence": 0.95, "status": "extracted"},
        },
    )
    ext_aff = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "affidavit_date": {"value": "2024-01-15", "confidence": 0.95, "status": "extracted"},
            "deponent_name": {"value": "Dr. R. K. Sharma", "confidence": 0.95, "status": "extracted"},
        },
    )

    app_syn = SimpleNamespace(
        id="app_syn",
        institution_name="Synthetic ABC Institute of Technology",
        academic_year="2026-27",
        status="submitted",
    )

    # Scenario 1: All valid
    ctx_syn_1 = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff],
        "extractions": {"d_f": ext_fire, "d_b": ext_bcc, "d_a": ext_aff},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff],
    }
    contexts.append(("synthetic_scenario_1_all_valid", ctx_syn_1))

    # Scenario 2: Missing Document (e.g. fire certificate omitted)
    ctx_syn_2 = {
        "application": app_syn,
        "documents": [doc_bcc, doc_aff],
        "extractions": {"d_b": ext_bcc, "d_a": ext_aff},
        "all_system_documents": [doc_bcc, doc_aff],
    }
    contexts.append(("synthetic_scenario_2_missing_document", ctx_syn_2))

    # Scenario 3: Expired Fire Certificate
    ext_fire_exp = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "FS-2021-001", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2021-01-01", "confidence": 0.95, "status": "extracted"},
            "expiry_date": {"value": "2022-01-01", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Fire Department", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_syn_3 = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff],
        "extractions": {"d_f": ext_fire_exp, "d_b": ext_bcc, "d_a": ext_aff},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff],
    }
    contexts.append(("synthetic_scenario_3_expired_document", ctx_syn_3))

    # Scenario 4: Missing Fields (certificate_number missing from fire cert)
    ext_fire_missing_field = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": None, "confidence": 0.0, "status": "unextracted"},
            "issue_date": {"value": "2024-01-10", "confidence": 0.95, "status": "extracted"},
            "expiry_date": {"value": "2027-01-09", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Fire Department", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_syn_4 = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff],
        "extractions": {"d_f": ext_fire_missing_field, "d_b": ext_bcc, "d_a": ext_aff},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff],
    }
    contexts.append(("synthetic_scenario_4_missing_fields", ctx_syn_4))

    # Scenario 5: Name Mismatch
    ext_fire_mismatch = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Completely Unrelated Polytechnic Institute", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "FS-2024-098", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2024-01-10", "confidence": 0.95, "status": "extracted"},
            "expiry_date": {"value": "2027-01-09", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Fire Department", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_syn_5 = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff],
        "extractions": {"d_f": ext_fire_mismatch, "d_b": ext_bcc, "d_a": ext_aff},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff],
    }
    contexts.append(("synthetic_scenario_5_name_mismatch", ctx_syn_5))

    # A0 Case 2a: Building Age > 50 Years, No Competent Authority Letter
    ext_bcc_1970 = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "BCC-1970-001", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "1970-01-01", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Municipal Corporation", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_a0_2a = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff],
        "extractions": {"d_f": ext_fire, "d_b": ext_bcc_1970, "d_a": ext_aff},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff],
    }
    contexts.append(("a0_case_2a_building_age_gt_50_no_letter", ctx_a0_2a))

    # A0 Case 2b: Building Age > 50 Years, With Competent Authority Letter
    doc_letter = SimpleNamespace(id="d_let", document_type="competent_authority_letter", processing_status="processed", original_filename="letter.pdf", file_hash="h4", application_id="app_syn")
    ext_letter = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2024-01-01", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_a0_2b = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff, doc_letter],
        "extractions": {"d_f": ext_fire, "d_b": ext_bcc_1970, "d_a": ext_aff, "d_let": ext_letter},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff, doc_letter],
    }
    contexts.append(("a0_case_2b_building_age_gt_50_with_letter", ctx_a0_2b))

    # (a) 35-year-old building with a letter but no certificate (vintage 1989)
    ext_bcc_1989 = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "BCC-1989-035", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "1989-01-01", "confidence": 0.95, "status": "extracted"},
            "issuing_authority": {"value": "Municipal Corporation", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_35yo_letter_no_cert = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff, doc_letter],
        "extractions": {"d_f": ext_fire, "d_b": ext_bcc_1989, "d_a": ext_aff, "d_let": ext_letter},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff, doc_letter],
    }
    contexts.append(("building_35yo_letter_no_cert", ctx_35yo_letter_no_cert))

    # (b) Expired 5-year structural certificate (building age > 30, structural cert date > 5 years old)
    doc_ssc = SimpleNamespace(id="d_s", document_type="structural_stability_certificate", processing_status="processed", original_filename="ssc.pdf", file_hash="h5", application_id="app_syn")
    ext_ssc_expired = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "certificate_number": {"value": "SSC-2017-001", "confidence": 0.95, "status": "extracted"},
            "issue_date": {"value": "2017-01-01", "confidence": 0.95, "status": "extracted"},
            "engineer_license_number": {"value": "SE-LIC-12345", "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_expired_ssc = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff, doc_ssc],
        "extractions": {"d_f": ext_fire, "d_b": ext_bcc_1989, "d_a": ext_aff, "d_s": ext_ssc_expired},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff, doc_ssc],
    }
    contexts.append(("structural_certificate_expired_5yr", ctx_expired_ssc))

    # (c) TER receipt present
    doc_ter = SimpleNamespace(id="d_t", document_type="ter_payment_receipt", processing_status="processed", original_filename="ter.pdf", file_hash="h6", application_id="app_syn")
    ext_ter = SimpleNamespace(
        processing_status="processed",
        fields={
            "institution_name": {"value": "Synthetic ABC Institute of Technology", "confidence": 0.95, "status": "extracted"},
            "receipt_number": {"value": "TER-REC-2024-001", "confidence": 0.95, "status": "extracted"},
            "transaction_date": {"value": "2024-01-15", "confidence": 0.95, "status": "extracted"},
            "amount_inr": {"value": 100000, "confidence": 0.95, "status": "extracted"},
        },
    )
    ctx_ter_present = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff, doc_ter],
        "extractions": {"d_f": ext_fire, "d_b": ext_bcc, "d_a": ext_aff, "d_t": ext_ter},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff, doc_ter],
    }
    contexts.append(("ter_receipt_present", ctx_ter_present))

    # (d) TER receipt absent
    ctx_ter_absent = {
        "application": app_syn,
        "documents": [doc_fire, doc_bcc, doc_aff],
        "extractions": {"d_f": ext_fire, "d_b": ext_bcc, "d_a": ext_aff},
        "all_system_documents": [doc_fire, doc_bcc, doc_aff],
    }
    contexts.append(("ter_receipt_absent", ctx_ter_absent))

    return contexts


def load_dev_database_contexts() -> list[tuple[str, dict[str, Any]]]:
    """Loads all applications from dev sqlite database in read-only mode."""
    db_path = Path("sih_prototype.db")
    if not db_path.exists():
        # Look in backend dir
        db_path = Path(__file__).parent.parent.parent / "sih_prototype.db"

    if not db_path.exists():
        return []

    import sqlite3

    contexts = []
    try:
        # Open sqlite database in read-only mode
        conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        cursor = conn.cursor()

        # Check applications table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='applications';")
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("SELECT id, institution_name, academic_year, status FROM applications")
        apps = cursor.fetchall()

        for app_row in apps:
            app_id, inst_name, acad_yr, app_status = app_row
            app_obj = SimpleNamespace(
                id=app_id,
                institution_name=inst_name,
                academic_year=acad_yr,
                status=app_status,
            )

            # Fetch documents
            cursor.execute("SELECT id, document_type, processing_status, original_filename, file_hash FROM documents WHERE application_id=?", (app_id,))
            doc_rows = cursor.fetchall()
            docs = [
                SimpleNamespace(
                    id=dr[0],
                    document_type=dr[1],
                    processing_status=dr[2],
                    original_filename=dr[3],
                    file_hash=dr[4],
                    application_id=app_id,
                )
                for dr in doc_rows
            ]

            # Fetch extractions
            extractions = {}
            for doc in docs:
                cursor.execute(
                    "SELECT id, processing_status, fields FROM extraction_runs WHERE document_id=? ORDER BY created_at DESC LIMIT 1",
                    (doc.id,)
                )
                erow = cursor.fetchone()
                if erow:
                    import json
                    flds = json.loads(erow[2]) if erow[2] else {}
                    extractions[doc.id] = SimpleNamespace(
                        id=erow[0],
                        processing_status=erow[1],
                        fields=flds,
                    )

            ctx = {
                "application": app_obj,
                "documents": docs,
                "extractions": extractions,
                "all_system_documents": docs,
            }
            contexts.append((f"dev_db_app_{app_id}", ctx))

        conn.close()
    except Exception as exc:
        print(f"Warning: Could not read dev database ({exc}), continuing with synthetic and boundary contexts.")

    return contexts


def run_parity_harness() -> ParityReport:
    """Executes replay across synthetic, database, and boundary fixtures."""
    all_contexts: list[tuple[str, dict[str, Any]]] = []

    # (a) Synthetic datasets
    all_contexts.extend(build_synthetic_scenario_contexts())

    # (b) Dev database applications (read-only)
    all_contexts.extend(load_dev_database_contexts())

    # (c) B2 boundary fixtures
    all_contexts.extend(build_boundary_fixture_contexts())

    report = ParityReport(total_contexts=len(all_contexts))

    for ctx_id, ctx in all_contexts:
        matches, discrepancies = compare_context_findings(ctx_id, ctx)
        report.matches += matches
        report.total_rule_evaluations += (matches + len(discrepancies))
        report.discrepancies.extend(discrepancies)

    return report


def main() -> int:
    print("=" * 70)
    print("      RULE ENGINE REPLAY & PARITY HARNESS (STEP B5)")
    print("=" * 70)

    report = run_parity_harness()

    print(f"Total Contexts Evaluated: {report.total_contexts}")
    print(f"Total Rule Checks:        {report.total_rule_evaluations}")
    print(f"Total Matches:            {report.matches}")
    print(f"Total Discrepancies:      {len(report.discrepancies)}")
    print(f"Unallowed Discrepancies:  {len(report.unallowed_discrepancies)}")
    print("=" * 70)

    if report.unallowed_discrepancies:
        print("\n[!] UNALLOWED DISCREPANCIES DETECTED:")
        print(f"{'Context ID':<35} | {'Rule ID':<20} | {'Legacy':<10} | {'Declarative':<12} | {'Reason'}")
        print("-" * 95)
        for d in report.unallowed_discrepancies:
            print(f"{d.context_id:<35} | {d.rule_id:<20} | {str(d.legacy_status):<10} | {str(d.declarative_status):<12} | {d.reason_code}")
        print("\nFailure: One or more unallowed parity discrepancies found.")
        return 1

    print("\nSUCCESS: 100% parity achieved across all evaluated contexts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
