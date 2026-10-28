"""
Declarative Rule Engine for AICTE Scrutiny Platform.
Loads verified statutory clauses from clauses.json and executes declarative rules from rules_eoa.yaml.
Implements robust three-valued Kleene logic (TRUE / FALSE / UNKNOWN) for compound conditions.
"""

from datetime import date, datetime
import difflib
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
from typing import Any, Optional
import yaml

from app.config import settings
from app.rules.banned_terms import validate_rule_text_claims
from app.schemas.finding import FindingCreate
from app.schemas.rule_definition import (
    ClauseCitation,
    DeclarativeRuleConfig,
    EvaluationResult,
    RuleBranch,
    RuleCondition,
)

logger = logging.getLogger(__name__)

RULES_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CLAUSES_PATH = RULES_DATA_DIR / "clauses.json"
DEFAULT_RULES_YAML_PATH = RULES_DATA_DIR / "rules_eoa.yaml"


def calculate_calendar_years_between(start_date: date, end_date: date) -> int:
    """
    Calculates calendar years between start_date and end_date.
    Properly handles leap year boundary:
    If start_date is Feb 29 on leap year, anniversary in non-leap year is Feb 28.
    """
    years = end_date.year - start_date.year
    try:
        anniversary = start_date.replace(year=end_date.year)
    except ValueError:
        # Feb 29 in non-leap year
        anniversary = date(end_date.year, 2, 28)
    if end_date < anniversary:
        years -= 1
    return years


def calculate_text_similarity(str1: str, str2: str) -> float:
    """Calculates normalized sequence similarity ratio between two strings."""
    s1 = " ".join((str1 or "").strip().lower().split())
    s2 = " ".join((str2 or "").strip().lower().split())
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def parse_iso_date(value: Any) -> Optional[date]:
    """Safely parses an ISO date string (YYYY-MM-DD), returning None if unparseable."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    val_str = str(value).strip()[:10]
    try:
        return date.fromisoformat(val_str)
    except Exception:
        # Attempt regex fallback for 4-digit year if YYYY-MM-DD parsing fails
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(value))
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except Exception:
                return None
        return None


class ClauseRegistry:
    """In-memory registry of statutory clauses from AICTE Approval Process Handbook (APH 2024–2027)."""

    def __init__(self, clauses_path: Path = DEFAULT_CLAUSES_PATH):
        self._clauses: dict[str, ClauseCitation] = {}
        self.load(clauses_path)

    def load(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Clause registry file not found at: {path}")

        raw_data = json.loads(path.read_text(encoding="utf-8"))
        for cid, data in raw_data.items():
            self._clauses[cid] = ClauseCitation(**data)

    def get(self, clause_id: str) -> Optional[ClauseCitation]:
        return self._clauses.get(clause_id)

    def all(self) -> dict[str, ClauseCitation]:
        return dict(self._clauses)


class DeclarativeRuleEngine:
    """
    Engine executing declarative Pydantic-validated rules against application validation context.
    Evaluates condition ASTs using three-valued Kleene logic (TRUE / FALSE / UNKNOWN).
    """

    def __init__(
        self,
        rules_path: Path = DEFAULT_RULES_YAML_PATH,
        clause_registry: Optional[ClauseRegistry] = None,
    ):
        self.clause_registry = clause_registry or ClauseRegistry()
        self.rules: list[DeclarativeRuleConfig] = []
        self.ruleset_hash: str = ""
        self.ruleset_version: str = "2024-2027.1.0"
        self.load_rules(rules_path)

    def load_rules(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Rule definition YAML file not found at: {path}")

        content_bytes = path.read_bytes()
        self.ruleset_hash = sha256(content_bytes).hexdigest()[:16]

        try:
            raw_content = yaml.safe_load(content_bytes.decode("utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML syntax in {path}: {exc}") from exc

        if not isinstance(raw_content, dict) or "rules" not in raw_content:
            raise ValueError(f"Invalid rule file format in {path}: must be mapping with 'rules' key")

        base_version = raw_content.get("version", "1.0")
        self.ruleset_version = f"2024-2027.{base_version}+{self.ruleset_hash[:8]}"

        parsed_rules: list[DeclarativeRuleConfig] = []
        seen_rule_ids: set[str] = set()

        for idx, rule_dict in enumerate(raw_content["rules"]):
            try:
                rule_cfg = DeclarativeRuleConfig(**rule_dict)

                # Check duplicate rule ID
                if rule_cfg.rule_id in seen_rule_ids:
                    raise ValueError(f"Duplicate rule_id '{rule_cfg.rule_id}' in {path}")
                seen_rule_ids.add(rule_cfg.rule_id)

                # Verify clause_id exists in registry
                if rule_cfg.clause_id and not self.clause_registry.get(rule_cfg.clause_id):
                    raise ValueError(
                        f"Rule '{rule_cfg.rule_id}' references unknown clause '{rule_cfg.clause_id}'"
                    )
                for cid in (rule_cfg.clause_ids or []):
                    if not self.clause_registry.get(cid):
                        raise ValueError(
                            f"Rule '{rule_cfg.rule_id}' references unknown clause '{cid}'"
                        )

                parsed_rules.append(rule_cfg)
            except Exception as e:
                raise ValueError(f"Schema validation failure for rule at index {idx} in {path}: {e}") from e

        self.rules = parsed_rules

    def get_rule(self, rule_id: str) -> Optional[DeclarativeRuleConfig]:
        for r in self.rules:
            if r.rule_id == rule_id:
                return r
        return None

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        """Evaluates all active declarative rules against the validation context."""
        findings: list[FindingCreate] = []
        for rule_cfg in self.rules:
            if rule_cfg.is_active:
                rule_findings = self.evaluate_rule(rule_cfg, context)
                findings.extend(rule_findings)
        return findings

    def evaluate_condition(
        self,
        cond: RuleCondition,
        context: dict[str, Any],
    ) -> EvaluationResult:
        """
        Evaluates a condition using three-valued Kleene logic:
        - all_of (AND): FALSE if any FALSE; UNKNOWN if no FALSE but any UNKNOWN; else TRUE
        - any_of (OR):  TRUE if any TRUE; UNKNOWN if no TRUE but any UNKNOWN; else FALSE
        - not (NOT):    TRUE -> FALSE; FALSE -> TRUE; UNKNOWN -> UNKNOWN
        """
        # 1. Compound Kleene AND (all_of)
        if cond.all_of is not None:
            has_unknown = False
            for sub in cond.all_of:
                res = self.evaluate_condition(sub, context)
                if res == EvaluationResult.FALSE:
                    return EvaluationResult.FALSE
                if res == EvaluationResult.UNKNOWN:
                    has_unknown = True
            return EvaluationResult.UNKNOWN if has_unknown else EvaluationResult.TRUE

        # 2. Compound Kleene OR (any_of)
        if cond.any_of is not None:
            has_unknown = False
            for sub in cond.any_of:
                res = self.evaluate_condition(sub, context)
                if res == EvaluationResult.TRUE:
                    return EvaluationResult.TRUE
                if res == EvaluationResult.UNKNOWN:
                    has_unknown = True
            return EvaluationResult.UNKNOWN if has_unknown else EvaluationResult.FALSE

        # 3. Compound Kleene NOT (not_)
        if cond.not_ is not None:
            res = self.evaluate_condition(cond.not_, context)
            if res == EvaluationResult.TRUE:
                return EvaluationResult.FALSE
            if res == EvaluationResult.FALSE:
                return EvaluationResult.TRUE
            return EvaluationResult.UNKNOWN

        # 4. Atomic Condition
        return self._evaluate_atomic_condition(cond, context)

    def _evaluate_atomic_condition(
        self,
        cond: RuleCondition,
        context: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluates a single atomic condition against context."""
        docs = context.get("documents", [])
        extractions = context.get("extractions", {})
        app = context.get("application")

        def _get_val(obj: Any, attr: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        target = cond.target or ("document" if cond.document_type else "application")

        # 1. Target: Document presence / count
        if cond.field == "document_presence" or cond.field == "document_count":
            if cond.operator == "exists":
                if cond.document_type:
                    found = any(_get_val(d, "document_type") == cond.document_type for d in docs)
                    return EvaluationResult.TRUE if found else EvaluationResult.FALSE
                return EvaluationResult.TRUE if docs else EvaluationResult.FALSE
            if cond.operator == "not_exists":
                if cond.document_type:
                    found = any(_get_val(d, "document_type") == cond.document_type for d in docs)
                    return EvaluationResult.FALSE if found else EvaluationResult.TRUE
                return EvaluationResult.FALSE if docs else EvaluationResult.TRUE

        # 2. Target: Document-scoped field extraction
        if cond.document_type:
            target_doc = next((d for d in docs if _get_val(d, "document_type") == cond.document_type), None)
            if not target_doc:
                # Document itself missing
                if cond.operator == "not_exists":
                    return EvaluationResult.TRUE
                if cond.operator == "exists":
                    return EvaluationResult.FALSE
                return EvaluationResult.UNKNOWN

            # If checking document existence directly
            if cond.field in ("exists", "document"):
                return EvaluationResult.TRUE

            doc_id = _get_val(target_doc, "id")
            ext = extractions.get(doc_id)
            if not ext or _get_val(ext, "processing_status") != "processed":
                return EvaluationResult.UNKNOWN

            fields = _get_val(ext, "fields", {}) or {}
            fld_data = fields.get(cond.field) if isinstance(fields, dict) else None
            if not fld_data:
                return EvaluationResult.UNKNOWN

            # Check confidence threshold (0.70)
            if isinstance(fld_data, dict):
                conf = fld_data.get("confidence")
                stat = fld_data.get("status")
                val = fld_data.get("value")
                if stat == "uncertain" or (conf is not None and conf < settings.OCR_CONFIDENCE_THRESHOLD):
                    return EvaluationResult.UNKNOWN
            else:
                val = fld_data

            if val is None or (isinstance(val, str) and not val.strip()):
                return EvaluationResult.UNKNOWN

            return self._compare_values(val, cond.operator, cond.target_value, cond.unit, context)

        # 3. Target: Application-scoped field
        if target == "application":
            val = _get_val(app, cond.field)
            if val is None or (isinstance(val, str) and not val.strip()):
                return EvaluationResult.UNKNOWN
            return self._compare_values(val, cond.operator, cond.target_value, cond.unit, context)

        # 4. Target: Cross-document consistency
        if cond.operator == "consistent_across_documents":
            app_inst = (_get_val(app, "institution_name") or "").strip().lower()
            if not app_inst:
                return EvaluationResult.UNKNOWN
            for doc in docs:
                ext = extractions.get(_get_val(doc, "id"))
                if ext and _get_val(ext, "processing_status") == "processed":
                    fields = _get_val(ext, "fields", {}) or {}
                    fld_data = fields.get("institution_name")
                    doc_inst = fld_data.get("value") if isinstance(fld_data, dict) else fld_data
                    if doc_inst and str(doc_inst).strip().lower() != app_inst:
                        return EvaluationResult.FALSE
            return EvaluationResult.TRUE

        return EvaluationResult.UNKNOWN

    def _compare_values(
        self,
        actual: Any,
        operator: Optional[str],
        target_value: Any,
        unit: Optional[str],
        context: dict[str, Any],
    ) -> EvaluationResult:
        """Compares actual value with target value according to operator."""
        if not operator:
            return EvaluationResult.UNKNOWN

        ref_date = context.get("cutoff_date") or date.today()
        if isinstance(ref_date, str):
            ref_date = parse_iso_date(ref_date) or date.today()

        if operator == "exists":
            return EvaluationResult.TRUE if actual is not None else EvaluationResult.FALSE
        if operator == "not_exists":
            return EvaluationResult.FALSE if actual is not None else EvaluationResult.TRUE

        if operator == "equals":
            return EvaluationResult.TRUE if str(actual).strip() == str(target_value).strip() else EvaluationResult.FALSE
        if operator == "not_equals":
            return EvaluationResult.TRUE if str(actual).strip() != str(target_value).strip() else EvaluationResult.FALSE

        if operator == "in":
            if isinstance(target_value, (list, set, tuple)):
                return EvaluationResult.TRUE if actual in target_value else EvaluationResult.FALSE
            return EvaluationResult.FALSE
        if operator == "not_in":
            if isinstance(target_value, (list, set, tuple)):
                return EvaluationResult.TRUE if actual not in target_value else EvaluationResult.FALSE
            return EvaluationResult.FALSE

        if operator == "date_not_expired":
            act_date = parse_iso_date(actual)
            if not act_date:
                return EvaluationResult.UNKNOWN
            return EvaluationResult.TRUE if act_date >= ref_date else EvaluationResult.FALSE

        if operator in ("date_lte_years", "less_or_equal") and unit == "years":
            act_date = parse_iso_date(actual)
            if not act_date:
                return EvaluationResult.UNKNOWN
            years = calculate_calendar_years_between(act_date, ref_date)
            return EvaluationResult.TRUE if years <= int(target_value) else EvaluationResult.FALSE

        if operator in ("date_gte_years", "greater_or_equal") and unit == "years":
            act_date = parse_iso_date(actual)
            if not act_date:
                return EvaluationResult.UNKNOWN
            years = calculate_calendar_years_between(act_date, ref_date)
            return EvaluationResult.TRUE if years >= int(target_value) else EvaluationResult.FALSE

        if operator == "greater_or_equal":
            try:
                return EvaluationResult.TRUE if float(actual) >= float(target_value) else EvaluationResult.FALSE
            except Exception:
                return EvaluationResult.UNKNOWN

        if operator == "greater_than":
            try:
                return EvaluationResult.TRUE if float(actual) > float(target_value) else EvaluationResult.FALSE
            except Exception:
                return EvaluationResult.UNKNOWN

        if operator == "less_or_equal":
            try:
                return EvaluationResult.TRUE if float(actual) <= float(target_value) else EvaluationResult.FALSE
            except Exception:
                return EvaluationResult.UNKNOWN

        if operator == "less_than":
            try:
                return EvaluationResult.TRUE if float(actual) < float(target_value) else EvaluationResult.FALSE
            except Exception:
                return EvaluationResult.UNKNOWN

        if operator == "fuzzy_similarity":
            threshold = target_value if target_value is not None else settings.NAME_SIMILARITY_THRESHOLD
            sim = calculate_text_similarity(str(actual), str(context.get("expected_name", "")))
            return EvaluationResult.TRUE if sim >= float(threshold) else EvaluationResult.FALSE

        return EvaluationResult.UNKNOWN

    def evaluate_rule(
        self,
        rule_cfg: DeclarativeRuleConfig,
        context: dict[str, Any],
    ) -> list[FindingCreate]:
        """Evaluates a single declarative rule configuration against context."""
        if not rule_cfg.is_active:
            return []

        clause_ref = self.clause_registry.get(rule_cfg.clause_id) if rule_cfg.clause_id else None
        findings: list[FindingCreate] = []

        docs = context.get("documents", [])
        extractions = context.get("extractions", {})
        app = context.get("application")

        def _get_v(obj: Any, attr: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        # 1. Specialized logic for Prototype Document Presence check
        if rule_cfg.rule_id == "DOC_PRESENCE_001":
            required_types = ["fire_safety_certificate", "building_completion_certificate", "affidavit_2"]
            present_types = {_get_v(d, "document_type") for d in docs if _get_v(d, "document_type")}
            missing = [t for t in required_types if t not in present_types]
            if not missing:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="pass",
                        title=rule_cfg.pass_title,
                        reason=rule_cfg.pass_reason_template,
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                        next_action=rule_cfg.next_action,
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="missing",
                        title=rule_cfg.flag_title,
                        reason=rule_cfg.flag_reason_template.format(missing_docs=", ".join(missing)),
                        evidence={"missing_document_types": missing},
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                        next_action=rule_cfg.next_action,
                    )
                )
            return findings

        # 2. Specialized logic for Mandatory Field Completeness check
        if rule_cfg.rule_id == "FIELD_001":
            from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
            for doc in docs:
                dtype = _get_v(doc, "document_type")
                if dtype not in EOA_DOCUMENT_CHECKLIST:
                    continue
                req_fields = EOA_DOCUMENT_CHECKLIST[dtype].get("required_fields", [])
                if not req_fields:
                    continue
                ext = extractions.get(_get_v(doc, "id"))
                ext_fields = _get_v(ext, "fields", {}) if ext else {}
                extracted_keys = set()
                if isinstance(ext_fields, dict):
                    for k, f_val in ext_fields.items():
                        if isinstance(f_val, dict) and f_val.get("value") is not None:
                            extracted_keys.add(k)
                        elif f_val is not None and not isinstance(f_val, dict):
                            extracted_keys.add(k)
                missing_fields = [f for f in req_fields if f not in extracted_keys]
                doc_name = _get_v(doc, "original_filename", dtype)
                if not missing_fields:
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="pass",
                            title=rule_cfg.pass_title,
                            reason=rule_cfg.pass_reason_template.format(
                                extracted_count=len(extracted_keys),
                                total_count=len(req_fields),
                                document_type=dtype,
                            ),
                            document_id=_get_v(doc, "id"),
                            document_name=doc_name,
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                        )
                    )
                else:
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="flagged",
                            title=rule_cfg.flag_title,
                            reason=rule_cfg.flag_reason_template.format(
                                document_name=doc_name,
                                missing_fields=", ".join(missing_fields),
                            ),
                            document_id=_get_v(doc, "id"),
                            document_name=doc_name,
                            evidence={"missing_fields": missing_fields},
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action=rule_cfg.next_action,
                        )
                    )
            return findings

        # 3. Specialized logic for Fire Safety Certificate Expiry check
        if rule_cfg.rule_id == "EXPIRY_001":
            target_doc = next((d for d in docs if _get_v(d, "document_type") == "fire_safety_certificate"), None)
            if target_doc:
                ext = extractions.get(_get_v(target_doc, "id"))
                ext_fields = _get_v(ext, "fields", {}) if ext else {}
                expiry_val = None
                conf = None
                stat = None
                if isinstance(ext_fields, dict) and "expiry_date" in ext_fields:
                    fld = ext_fields["expiry_date"]
                    if isinstance(fld, dict):
                        expiry_val = fld.get("value")
                        conf = fld.get("confidence")
                        stat = fld.get("status")
                    else:
                        expiry_val = fld

                doc_name = _get_v(target_doc, "original_filename", "fire_safety_certificate.pdf")

                if stat == "uncertain" or (conf is not None and conf < settings.OCR_CONFIDENCE_THRESHOLD):
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="unresolved",
                            title="Unresolved Fire Safety Certificate Expiry Date",
                            reason=f"Expiry date value '{expiry_val}' has low confidence or uncertain status on document '{doc_name}'.",
                            document_id=_get_v(target_doc, "id"),
                            document_name=doc_name,
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action=rule_cfg.next_action,
                        )
                    )
                    return findings

                if expiry_val:
                    exp_date = parse_iso_date(expiry_val)
                    if exp_date:
                        ref_date = context.get("cutoff_date") or date.today()
                        if isinstance(ref_date, str):
                            ref_date = parse_iso_date(ref_date) or date.today()

                        if exp_date >= ref_date:
                            findings.append(
                                FindingCreate(
                                    rule_id=rule_cfg.rule_id,
                                    status="pass",
                                    title=rule_cfg.pass_title,
                                    reason=rule_cfg.pass_reason_template.format(expiry_date=str(exp_date)),
                                    document_id=_get_v(target_doc, "id"),
                                    document_name=doc_name,
                                    clause_ref=clause_ref,
                                    severity=rule_cfg.severity,
                                    signal_type=rule_cfg.signal_type,
                                    advisory=rule_cfg.advisory,
                                )
                            )
                        else:
                            findings.append(
                                FindingCreate(
                                    rule_id=rule_cfg.rule_id,
                                    status="flagged",
                                    title=rule_cfg.flag_title,
                                    reason=rule_cfg.flag_reason_template.format(expiry_date=str(exp_date)),
                                    document_id=_get_v(target_doc, "id"),
                                    document_name=doc_name,
                                    clause_ref=clause_ref,
                                    severity=rule_cfg.severity,
                                    signal_type=rule_cfg.signal_type,
                                    advisory=rule_cfg.advisory,
                                    next_action=rule_cfg.next_action,
                                )
                            )
                    else:
                        findings.append(
                            FindingCreate(
                                rule_id=rule_cfg.rule_id,
                                status="unresolved",
                                title="Unresolved Fire Safety Certificate Expiry Date",
                                reason=f"Expiry date value '{expiry_val}' is unparseable for document '{doc_name}'.",
                                document_id=_get_v(target_doc, "id"),
                                document_name=doc_name,
                                clause_ref=clause_ref,
                                severity=rule_cfg.severity,
                                signal_type=rule_cfg.signal_type,
                                advisory=rule_cfg.advisory,
                            )
                        )
            return findings

        # 4. Specialized logic for Cross-Document Institution Name Consistency check
        if rule_cfg.rule_id == "CONSISTENCY_001":
            app_inst_name = (_get_v(app, "institution_name") or "").strip().lower()
            mismatches = []
            for doc in docs:
                ext = extractions.get(_get_v(doc, "id"))
                ext_fields = _get_v(ext, "fields", {}) if ext else {}
                doc_inst = None
                if isinstance(ext_fields, dict) and "institution_name" in ext_fields:
                    fld = ext_fields["institution_name"]
                    doc_inst = fld.get("value") if isinstance(fld, dict) else fld
                if doc_inst and str(doc_inst).strip().lower() != app_inst_name:
                    mismatches.append((_get_v(doc, "original_filename", "document"), str(doc_inst)))
            if not mismatches:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="pass",
                        title=rule_cfg.pass_title,
                        reason=rule_cfg.pass_reason_template.format(institution_name=_get_v(app, "institution_name", "Institution")),
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="flagged",
                        title=rule_cfg.flag_title,
                        reason=rule_cfg.flag_reason_template.format(
                            document_name=mismatches[0][0],
                            doc_institution_name=mismatches[0][1],
                            app_institution_name=_get_v(app, "institution_name", "Application Name"),
                        ),
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                        next_action=rule_cfg.next_action,
                    )
                )
            return findings

        # 5. Branched Rule Evaluation (e.g. Structural Stability)
        if rule_cfg.branches:
            has_unknown = False
            for branch in rule_cfg.branches:
                b_res = self.evaluate_condition(branch.condition, context)
                if b_res == EvaluationResult.TRUE:
                    branch_clause_ref = self.clause_registry.get(branch.clause_id) if branch.clause_id else clause_ref
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status=branch.outcome,
                            title=branch.title,
                            reason=branch.reason_template,
                            clause_ref=branch_clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action=branch.next_action or rule_cfg.next_action,
                        )
                    )
                    return findings
                elif b_res == EvaluationResult.UNKNOWN:
                    has_unknown = True

            # If no branch evaluated to TRUE:
            if has_unknown:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="unresolved",
                        title=f"{rule_cfg.title}: Indeterminate Status",
                        reason="Rule conditions could not be deterministically evaluated due to unextracted or uncertain document data.",
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                        next_action="Human reviewer to audit original physical documents.",
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="flagged",
                        title=rule_cfg.flag_title or f"{rule_cfg.title} Flagged",
                        reason=rule_cfg.flag_reason_template or "Rule criteria not satisfied.",
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                        next_action=rule_cfg.next_action,
                    )
                )
            return findings

        # 6. Single Condition Evaluation (Standard Fallback)
        if rule_cfg.condition:
            eval_res = self.evaluate_condition(rule_cfg.condition, context)
            if eval_res == EvaluationResult.TRUE:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="pass",
                        title=rule_cfg.pass_title or rule_cfg.title,
                        reason=rule_cfg.pass_reason_template or "Pass criteria satisfied.",
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                    )
                )
            elif eval_res == EvaluationResult.FALSE:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="flagged",
                        title=rule_cfg.flag_title or rule_cfg.title,
                        reason=rule_cfg.flag_reason_template or "Flag criteria detected.",
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                        next_action=rule_cfg.next_action,
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="unresolved",
                        title=f"{rule_cfg.title}: Indeterminate Status",
                        reason="Required verification fields are missing, unparseable, or have low confidence.",
                        clause_ref=clause_ref,
                        severity=rule_cfg.severity,
                        signal_type=rule_cfg.signal_type,
                        advisory=rule_cfg.advisory,
                        next_action=rule_cfg.next_action or "Review document manually.",
                    )
                )

        return findings


# Global singleton instances for zero-overhead startup and caching
default_clause_registry = ClauseRegistry()
default_declarative_engine = DeclarativeRuleEngine(clause_registry=default_clause_registry)
