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

        # Include duplicate detection check if system documents or application are present
        if context.get("all_system_documents") is not None or context.get("documents"):
            try:
                from app.rules.duplicate_check import DuplicateDocumentRule
                dup_rule = DuplicateDocumentRule()
                findings.extend(dup_rule.evaluate(context))
            except Exception as e:
                logger.warning("Duplicate check failed in declarative evaluation: %s", e)

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
        """Evaluates a single declarative rule configuration against context with full legacy parity."""
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

        from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
        from app.rules.field_completeness import FIELD_RULE_MAP
        from app.rules.presence_check import PRESENCE_RULE_MAP

        docs_by_type = {_get_v(d, "document_type"): d for d in docs if _get_v(d, "document_type")}

        # 1. Specialized logic for Document Presence check (DOC_PRESENCE_001 -> PRESENCE_001..004)
        if rule_cfg.rule_id in ("DOC_PRESENCE_001", "PRESENCE_CHECK"):
            for doc_type, info in EOA_DOCUMENT_CHECKLIST.items():
                if info.get("applicability") == "required_if_applicable":
                    continue
                r_id, r_title = PRESENCE_RULE_MAP.get(doc_type, (f"PRESENCE_{doc_type.upper()}", f"{info['display_name']} Presence"))
                target_doc = docs_by_type.get(doc_type)
                is_ter = (doc_type == "ter_payment_receipt")
                p_clause = self.clause_registry.get("APH_2024_27_ANNEX_2_CLAUSE_2_1_II" if is_ter else "APH_2024_27_ANNEX_2_CLAUSE_2_1")

                if target_doc:
                    findings.append(
                        FindingCreate(
                            rule_id=r_id,
                            status="pass",
                            title=f"{info['display_name']} is present",
                            reason=f"Mandatory document '{info['display_name']}' is uploaded ({_get_v(target_doc, 'original_filename', doc_type)}).",
                            document_id=_get_v(target_doc, "id"),
                            document_name=_get_v(target_doc, "original_filename", doc_type),
                            evidence={"document_type": doc_type, "original_filename": _get_v(target_doc, "original_filename", doc_type)},
                            clause_ref=p_clause,
                            severity="info" if is_ter else "critical",
                            signal_type="rule",
                            advisory=is_ter,
                            next_action=None,
                        )
                    )
                else:
                    findings.append(
                        FindingCreate(
                            rule_id=r_id,
                            status="missing",
                            title=f"{info['display_name']} is missing",
                            reason=f"Mandatory document '{info['display_name']}' is not uploaded. Sourced from {info['source']}.",
                            document_id=None,
                            document_name=None,
                            evidence={"missing_document_type": doc_type},
                            clause_ref=p_clause,
                            severity="info" if is_ter else "critical",
                            signal_type="rule",
                            advisory=is_ter,
                            next_action=f"Upload a valid {info['display_name']} as required by AICTE regulations ({info['source']}).",
                        )
                    )
            return findings

        # 2. Specialized logic for Mandatory Field Completeness check (FIELD_001 -> FIELD_001..005)
        if rule_cfg.rule_id in ("FIELD_001", "FIELD_COMPLETENESS"):
            for doc in docs:
                dtype = _get_v(doc, "document_type")
                if dtype not in EOA_DOCUMENT_CHECKLIST:
                    continue
                req_fields = EOA_DOCUMENT_CHECKLIST[dtype].get("required_fields", [])
                if not req_fields:
                    continue

                r_id, r_title = FIELD_RULE_MAP.get(dtype, (f"FIELD_{dtype.upper()}", f"{dtype} Fields"))
                is_ter = (dtype == "ter_payment_receipt")
                ter_kwargs = {"severity": "info", "advisory": True} if is_ter else {"severity": "high", "advisory": False}
                checklist_info = EOA_DOCUMENT_CHECKLIST[dtype]
                doc_name = _get_v(doc, "original_filename", dtype)
                doc_id = _get_v(doc, "id")

                ext = extractions.get(doc_id)
                if not ext or _get_v(ext, "processing_status") != "processed":
                    findings.append(
                        FindingCreate(
                            rule_id=r_id,
                            status="not_applicable" if is_ter else "unresolved",
                            title=f"{checklist_info['display_name']} extraction incomplete",
                            reason=(
                                f"Fields could not be validated because document '{doc_name}' has not been successfully processed. "
                                + ("(Advisory: TER receipt is optional 'if any')." if is_ter else "")
                            ),
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={"processing_status": getattr(ext, "processing_status", "not_processed") if ext else "not_processed"},
                            clause_ref=None,
                            signal_type="internal_check",
                            next_action=None if is_ter else "Wait for document OCR processing to complete or re-upload if processing failed.",
                            **ter_kwargs,
                        )
                    )
                    continue

                ext_fields = _get_v(ext, "fields", {}) or {}
                missing_fields: list[str] = []
                uncertain_fields: list[str] = []
                extracted_keys: list[str] = []

                for fn in req_fields:
                    f_data = ext_fields.get(fn)
                    if not f_data or (isinstance(f_data, dict) and (f_data.get("value") is None or (isinstance(f_data.get("value"), str) and not str(f_data.get("value")).strip()))):
                        missing_fields.append(fn)
                    elif isinstance(f_data, dict) and (
                        f_data.get("status") == "uncertain"
                        or (f_data.get("confidence") is not None and f_data["confidence"] < settings.OCR_CONFIDENCE_THRESHOLD)
                    ):
                        uncertain_fields.append(fn)
                    else:
                        extracted_keys.append(fn)

                if missing_fields:
                    findings.append(
                        FindingCreate(
                            rule_id=r_id,
                            status="not_applicable" if is_ter else "missing",
                            title=f"Optional fields in {checklist_info['display_name']}" if is_ter else f"Missing required fields in {checklist_info['display_name']}",
                            reason=(
                                f"The following fields were not detected in '{doc_name}': {', '.join(missing_fields)}. (Advisory: TER receipt is optional 'if any')."
                                if is_ter else
                                f"The following required fields could not be extracted from '{doc_name}': {', '.join(missing_fields)}."
                            ),
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={"missing_fields": missing_fields},
                            clause_ref=None,
                            signal_type="internal_check",
                            next_action=None if is_ter else "Ensure the uploaded document contains clear text for all mandatory fields or manually review the file.",
                            **ter_kwargs,
                        )
                    )
                if uncertain_fields:
                    findings.append(
                        FindingCreate(
                            rule_id=r_id,
                            status="not_applicable" if is_ter else "unresolved",
                            title=f"Advisory: low-confidence fields in {checklist_info['display_name']}" if is_ter else f"Low-confidence fields in {checklist_info['display_name']}",
                            reason=(
                                f"OCR confidence was below {settings.OCR_CONFIDENCE_THRESHOLD:.0%} for: "
                                f"{', '.join(uncertain_fields)}. (Advisory: TER receipt is optional 'if any')."
                                if is_ter else
                                f"OCR confidence was below {settings.OCR_CONFIDENCE_THRESHOLD:.0%} for: "
                                f"{', '.join(uncertain_fields)}. These values need human confirmation."
                            ),
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={"fields": {fn: ext_fields[fn] for fn in uncertain_fields}},
                            clause_ref=None,
                            signal_type="internal_check",
                            next_action=None if is_ter else "Review the source page and confirm each low-confidence extracted value.",
                            **ter_kwargs,
                        )
                    )
                if not missing_fields and not uncertain_fields:
                    findings.append(
                        FindingCreate(
                            rule_id=r_id,
                            status="pass",
                            title=f"All fields extracted for {checklist_info['display_name']}",
                            reason=f"All {len(req_fields)} required fields were successfully extracted from '{doc_name}'.",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={"extracted_fields": list(ext_fields.keys())},
                            clause_ref=None,
                            signal_type="internal_check",
                            next_action=None,
                            **ter_kwargs,
                        )
                    )
            return findings

        # 3. Specialized logic for Fire Safety Certificate Expiry check
        if rule_cfg.rule_id == "EXPIRY_001":
            reference_date = context.get("reference_date") or context.get("cutoff_date") or date.today()
            if isinstance(reference_date, str):
                reference_date = parse_iso_date(reference_date) or date.today()

            for doc in docs:
                dtype = _get_v(doc, "document_type")
                checklist_info = EOA_DOCUMENT_CHECKLIST.get(dtype, {})
                if not checklist_info.get("has_expiry", False):
                    continue

                doc_id = _get_v(doc, "id")
                doc_name = _get_v(doc, "original_filename", "fire_safety_certificate.pdf")
                ext = extractions.get(doc_id)

                if not ext or _get_v(ext, "processing_status") != "processed":
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="unresolved",
                            title=f"{checklist_info.get('display_name', 'Fire Safety Certificate')} expiry check unresolved",
                            reason=f"Document '{doc_name}' has not been processed. Expiry date cannot be verified.",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence=None,
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action="Process document OCR before running expiry check.",
                        )
                    )
                    continue

                fields = _get_v(ext, "fields", {}) or {}
                expiry_data = fields.get("expiry_date")
                if not expiry_data or not (expiry_data.get("value") if isinstance(expiry_data, dict) else expiry_data):
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="unresolved",
                            title=f"{checklist_info.get('display_name', 'Fire Safety Certificate')} expiry date not found",
                            reason=f"No valid expiry date was extracted from '{doc_name}'.",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={"raw_text": expiry_data.get("raw_text") if isinstance(expiry_data, dict) else None},
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action="Review the certificate manually to confirm if an expiry date is specified.",
                        )
                    )
                    continue

                conf = expiry_data.get("confidence") if isinstance(expiry_data, dict) else None
                stat = expiry_data.get("status") if isinstance(expiry_data, dict) else None
                if stat == "uncertain" or (conf is not None and conf < settings.OCR_CONFIDENCE_THRESHOLD):
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="unresolved",
                            title=f"{checklist_info.get('display_name', 'Fire Safety Certificate')} expiry date needs review",
                            reason=f"OCR confidence for the extracted expiry date was {conf:.0%}, below the {settings.OCR_CONFIDENCE_THRESHOLD:.0%} review threshold.",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={
                                "page_number": expiry_data.get("page_number", 1) if isinstance(expiry_data, dict) else 1,
                                "text": expiry_data.get("raw_text") if isinstance(expiry_data, dict) else None,
                                "field": "expiry_date",
                                "value": expiry_data.get("value") if isinstance(expiry_data, dict) else expiry_data,
                                "bbox": expiry_data.get("bbox") if isinstance(expiry_data, dict) else None,
                                "confidence": conf,
                            },
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action="Review the certificate and confirm the expiry date before relying on this check.",
                        )
                    )
                    continue

                raw_val = expiry_data.get("value") if isinstance(expiry_data, dict) else expiry_data
                parsed_date = parse_iso_date(raw_val)
                if not parsed_date:
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="unresolved",
                            title=f"Unparseable expiry date in {checklist_info.get('display_name', 'Fire Safety Certificate')}",
                            reason=f"Extracted expiry date '{raw_val}' could not be parsed into a standard date format.",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={"raw_value": str(raw_val)},
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action="A reviewer must manually confirm the expiry date.",
                        )
                    )
                    continue

                evidence = {
                    "page_number": expiry_data.get("page_number", 1) if isinstance(expiry_data, dict) else 1,
                    "text": (expiry_data.get("raw_text") if isinstance(expiry_data, dict) else None) or f"Valid Until: {parsed_date.isoformat()}",
                    "field": "expiry_date",
                    "value": parsed_date.isoformat(),
                    "bbox": expiry_data.get("bbox") if isinstance(expiry_data, dict) else None,
                }

                if parsed_date < reference_date:
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="flagged",
                            title="Document appears expired",
                            reason=f"The extracted expiry date ({parsed_date.isoformat()}) is earlier than the reference date ({reference_date.isoformat()}).",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence=evidence,
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action="Request a current document or have a reviewer confirm the extracted date.",
                        )
                    )
                else:
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="pass",
                            title=f"{checklist_info.get('display_name', 'Fire Safety Certificate')} is currently valid",
                            reason=f"The extracted expiry date ({parsed_date.isoformat()}) is on or after the reference date ({reference_date.isoformat()}).",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence=evidence,
                            clause_ref=clause_ref,
                            severity=rule_cfg.severity,
                            signal_type=rule_cfg.signal_type,
                            advisory=rule_cfg.advisory,
                            next_action=None,
                        )
                    )
            return findings

        # 4. Specialized logic for Cross-Document Institution Name Consistency check
        if rule_cfg.rule_id == "CONSISTENCY_001":
            app_inst_name = (_get_v(app, "institution_name") or "").strip()
            if not app_inst_name:
                return findings

            def _normalize_token_text(text: str) -> str:
                if not text:
                    return ""
                t = text.lower()
                t = re.sub(r"[^\w\s]", " ", t)
                return re.sub(r"\s+", " ", t).strip()

            def _token_similarity(s1: str, s2: str) -> float:
                t1 = set(_normalize_token_text(s1).split())
                t2 = set(_normalize_token_text(s2).split())
                if not t1 or not t2:
                    return 0.0
                return len(t1.intersection(t2)) / len(t1.union(t2))

            norm_app = _normalize_token_text(app_inst_name)

            for doc in docs:
                doc_id = _get_v(doc, "id")
                doc_name = _get_v(doc, "original_filename", "document")
                ext = extractions.get(doc_id)
                if not ext or _get_v(ext, "processing_status") != "processed":
                    continue

                fields = _get_v(ext, "fields", {}) or {}
                name_field = fields.get("institution_name")
                if not name_field or not (name_field.get("value") if isinstance(name_field, dict) else name_field):
                    continue

                conf = name_field.get("confidence") if isinstance(name_field, dict) else None
                stat = name_field.get("status") if isinstance(name_field, dict) else None

                if stat == "uncertain" or (conf is not None and conf < settings.OCR_CONFIDENCE_THRESHOLD):
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="unresolved",
                            title="Institution name consistency check needs review",
                            reason=(
                                f"OCR confidence for the institution name in '{doc_name}' "
                                f"was {conf:.0%}, below the {settings.OCR_CONFIDENCE_THRESHOLD:.0%} review threshold."
                            ),
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence={
                                "page_number": name_field.get("page_number", 1) if isinstance(name_field, dict) else 1,
                                "text": name_field.get("raw_text") if isinstance(name_field, dict) else None,
                                "field": "institution_name",
                                "value": name_field.get("value") if isinstance(name_field, dict) else name_field,
                                "bbox": name_field.get("bbox") if isinstance(name_field, dict) else None,
                                "confidence": conf,
                            },
                            clause_ref=None,
                            signal_type="internal_check",
                            severity=rule_cfg.severity,
                            next_action="Review the institution name on the source page before comparing it with the application record.",
                        )
                    )
                    continue

                doc_name_val = str(name_field.get("value") if isinstance(name_field, dict) else name_field)
                norm_doc = _normalize_token_text(doc_name_val)
                sim = _token_similarity(norm_app, norm_doc)
                is_match = (norm_app == norm_doc) or (sim >= 0.70)

                evidence = {
                    "page_number": name_field.get("page_number", 1) if isinstance(name_field, dict) else 1,
                    "text": (name_field.get("raw_text") if isinstance(name_field, dict) else None) or doc_name_val,
                    "field": "institution_name",
                    "value": doc_name_val,
                    "bbox": name_field.get("bbox") if isinstance(name_field, dict) else None,
                    "similarity_score": round(sim, 2),
                }

                if is_match:
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="pass",
                            title="Institution name matches application record",
                            reason=f"The extracted institution name in '{doc_name}' matches '{app_inst_name}'.",
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence=evidence,
                            clause_ref=None,
                            signal_type="internal_check",
                            severity=rule_cfg.severity,
                            next_action=None,
                        )
                    )
                else:
                    findings.append(
                        FindingCreate(
                            rule_id=rule_cfg.rule_id,
                            status="flagged",
                            title="Potential institution name mismatch",
                            reason=(
                                f"The extracted institution name '{doc_name_val}' in '{doc_name}' "
                                f"does not closely match the application name '{app_inst_name}' (similarity: {sim:.0%})."
                            ),
                            document_id=doc_id,
                            document_name=doc_name,
                            evidence=evidence,
                            clause_ref=None,
                            signal_type="internal_check",
                            severity=rule_cfg.severity,
                            next_action="Review the document manually to verify name spelling, change of name approval, or campus variance.",
                        )
                    )
            return findings

        # 5. Specialized logic for TER Payment Receipt Check
        if rule_cfg.rule_id == "TER_PAYMENT_001":
            ter_doc = next((d for d in docs if _get_v(d, "document_type") == "ter_payment_receipt"), None)
            if not ter_doc:
                # D-019 (Option A): absent TER receipt produces NO finding.
                return []

            ter_id = _get_v(ter_doc, "id")
            ter_name = _get_v(ter_doc, "original_filename", "ter_payment_receipt.pdf")
            ext = extractions.get(ter_id)

            if not ext or _get_v(ext, "processing_status") != "processed":
                findings.append(
                    FindingCreate(
                        rule_id=rule_cfg.rule_id,
                        status="not_applicable",
                        title="Advisory: TER Payment Receipt Extraction Incomplete",
                        reason=(
                            f"Payment receipt '{ter_name}' has not finished OCR processing. "
                            f"(Advisory: TER receipt is optional 'if any' under APH 2024-27 Annexure-2 §2.1(ii))."
                        ),
                        document_id=ter_id,
                        document_name=ter_name,
                        evidence={"processing_status": getattr(ext, "processing_status", "not_processed") if ext else "not_processed"},
                        next_action=None,
                        severity="info",
                        advisory=True,
                        clause_ref=clause_ref,
                    )
                )
                return findings

            fields = _get_v(ext, "fields", {}) or {}
            amount_field = fields.get("amount_inr")
            receipt_num_field = fields.get("receipt_number")
            txn_date_field = fields.get("transaction_date")

            receipt_num = receipt_num_field.get("value") if isinstance(receipt_num_field, dict) else receipt_num_field
            txn_date = txn_date_field.get("value") if isinstance(txn_date_field, dict) else txn_date_field
            amount_val = amount_field.get("value") if isinstance(amount_field, dict) else amount_field

            findings.append(
                FindingCreate(
                    rule_id=rule_cfg.rule_id,
                    status="pass",
                    title="TER Payment Receipt Provided",
                    reason=(
                        f"Payment receipt '{ter_name}' provided per Annexure-2 §2.1(ii) ('if any'). "
                        "This check is advisory/informational; fee amounts are not validated against AICTE portal records."
                    ),
                    document_id=ter_id,
                    document_name=ter_name,
                    evidence={
                        "receipt_number": receipt_num,
                        "transaction_date": txn_date,
                        "amount_inr": amount_val,
                        "page_number": amount_field.get("page_number") if isinstance(amount_field, dict) else None,
                        "bbox": amount_field.get("bbox") if isinstance(amount_field, dict) else None,
                    },
                    next_action=None,
                    severity="info",
                    advisory=True,
                    clause_ref=clause_ref,
                )
            )
            return findings

        # 6. Specialized logic for Building Age & Structural Stability Check
        if rule_cfg.rule_id in ("STRUCTURAL_001", "STRUCTURAL_STABILITY_001"):
            target_rule_id = "STRUCTURAL_STABILITY_001"
            building_doc = next((d for d in docs if _get_v(d, "document_type") == "building_completion_certificate"), None)

            if not building_doc:
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="unresolved",
                        title="Building Age Undetermined (Building Certificate Missing)",
                        reason="Building age cannot be determined because Building Completion Certificate has not been uploaded.",
                        next_action="Upload Building Completion Certificate / Occupancy Certificate to establish building vintage.",
                    )
                )
                return findings

            b_id = _get_v(building_doc, "id")
            b_name = _get_v(building_doc, "original_filename", "building_completion_certificate.pdf")
            b_ext = extractions.get(b_id)

            if not b_ext or _get_v(b_ext, "processing_status") != "processed":
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="unresolved",
                        title="Building Completion Certificate Extraction Incomplete",
                        reason="Cannot determine building age until Building Completion Certificate OCR extraction completes.",
                        document_id=b_id,
                        document_name=b_name,
                        next_action="Wait for OCR processing to complete.",
                    )
                )
                return findings

            b_fields = _get_v(b_ext, "fields", {}) or {}
            issue_date_field = b_fields.get("issue_date")
            if not issue_date_field or not (issue_date_field.get("value") if isinstance(issue_date_field, dict) else issue_date_field):
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="unresolved",
                        title="Building Completion Date Indeterminate",
                        reason="Building Completion Certificate does not have a readable issue date to compute building age.",
                        document_id=b_id,
                        document_name=b_name,
                        next_action="Upload a clear Building Completion Certificate showing the official completion or issue date.",
                    )
                )
                return findings

            conf = issue_date_field.get("confidence") if isinstance(issue_date_field, dict) else None
            stat = issue_date_field.get("status") if isinstance(issue_date_field, dict) else None
            if stat == "uncertain" or (conf is not None and conf < settings.OCR_CONFIDENCE_THRESHOLD):
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="unresolved",
                        title="Building Completion Date Low OCR Confidence",
                        reason=f"Building completion date '{issue_date_field.get('raw_text') if isinstance(issue_date_field, dict) else ''}' has low confidence ({conf:.2f}).",
                        document_id=b_id,
                        document_name=b_name,
                        evidence={"raw_text": issue_date_field.get("raw_text") if isinstance(issue_date_field, dict) else None, "confidence": conf},
                        next_action="Verify building completion date manually.",
                    )
                )
                return findings

            date_str = str(issue_date_field.get("value") if isinstance(issue_date_field, dict) else issue_date_field)
            year_match = re.search(r"(\d{4})", date_str)
            if not year_match:
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="unresolved",
                        title="Invalid Building Completion Date Format",
                        reason=f"Could not parse year from building completion date '{date_str}'.",
                        document_id=b_id,
                        document_name=b_name,
                        next_action="Review building completion certificate date format.",
                    )
                )
                return findings

            completion_year = int(year_match.group(1))
            ref_date = context.get("cutoff_date") or context.get("reference_date") or date.today()
            if isinstance(ref_date, str):
                ref_date = parse_iso_date(ref_date) or date.today()

            parsed_comp_date = parse_iso_date(date_str)
            if parsed_comp_date:
                building_age = calculate_calendar_years_between(parsed_comp_date, ref_date)
                try:
                    anniversary_30 = parsed_comp_date.replace(year=parsed_comp_date.year + 30)
                except ValueError:
                    anniversary_30 = date(parsed_comp_date.year + 30, 2, 28)
                try:
                    anniversary_50 = parsed_comp_date.replace(year=parsed_comp_date.year + 50)
                except ValueError:
                    anniversary_50 = date(parsed_comp_date.year + 50, 2, 28)
                is_lte_30 = (ref_date <= anniversary_30)
                is_gt_50 = (ref_date > anniversary_50)
            else:
                building_age = ref_date.year - completion_year
                is_lte_30 = (building_age <= 30)
                is_gt_50 = (building_age > 50)

            # >50-year check with competent authority letter
            competent_letter = next((d for d in docs if _get_v(d, "document_type") == "competent_authority_letter"), None)
            if is_gt_50 and competent_letter is not None:
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="unresolved",
                        title="Competent Authority letter uploaded: reviewer to confirm it applies",
                        reason=(
                            "The preamble allows a letter from the Competent Authority for "
                            "government-constructed buildings older than 50 years where original documents "
                            "cannot be submitted; Pramaan does not read the letter and does not know whether "
                            "the building is government-constructed or whether the condition applies."
                        ),
                        document_id=_get_v(competent_letter, "id"),
                        document_name=_get_v(competent_letter, "original_filename", "competent_authority_letter.pdf"),
                        evidence={
                            "completion_certificate_issue_date": date_str,
                            "completion_year": completion_year,
                            "building_age_years": building_age,
                            "has_competent_authority_letter": True,
                            "letter_filename": _get_v(competent_letter, "original_filename", "letter.pdf"),
                            "rule_reference": "APH 2024-2027 Annexure-2 Section 2.1 (Preamble)",
                        },
                        clause_ref=self.clause_registry.get("APH_2024_27_ANNEX_2_CLAUSE_2_1_PREAMBLE"),
                        next_action="Reviewer to open the letter and confirm it applies.",
                    )
                )
                return findings

            # <=30 year threshold
            if is_lte_30:
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="not_applicable",
                        title="Structural Stability Certificate Not Applicable (<= 30 Years)",
                        reason=(
                            f"Completion Certificate issue date is {date_str} (building age {building_age} years <= 30 years). "
                            f"Per Clause 6.17(h) and Annexure-2 §2.1(iv), a Structural Stability Certificate is required only "
                            f"after expiry of thirty years from the issue of Completion Certificate."
                        ),
                        document_id=b_id,
                        document_name=b_name,
                        evidence={
                            "completion_certificate_issue_date": date_str,
                            "completion_year": completion_year,
                            "current_year": ref_date.year,
                            "building_age_years": building_age,
                            "threshold_years": 30,
                        },
                        clause_ref=self.clause_registry.get("APH_2024_27_CLAUSE_6_17_H"),
                        next_action="No action required. Building is within the 30-year threshold from Completion Certificate issue date.",
                    )
                )
                return findings

            # >30 years: check structural stability certificate
            structural_doc = next((d for d in docs if _get_v(d, "document_type") == "structural_stability_certificate"), None)
            if not structural_doc:
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="missing",
                        title="Mandatory Structural Stability Certificate Missing (> 30 Years)",
                        reason=(
                            f"Completion Certificate issue date is {date_str} ({building_age} years old, exceeding 30-year threshold). "
                            f"Per APH Clause 6.17(h) and Annexure-2 §2.1(iv), a Structural Stability Certificate from a registered "
                            f"Structural Engineer is mandatory when the building is more than thirty years from the issue of Completion Certificate."
                        ),
                        evidence={
                            "completion_certificate_issue_date": date_str,
                            "completion_year": completion_year,
                            "building_age_years": building_age,
                            "threshold_years": 30,
                            "rule_reference": "APH 2024-2027 Clause 6.17(h) & Annexure-2 §2.1(iv)",
                        },
                        clause_ref=self.clause_registry.get("APH_2024_27_CLAUSE_6_17_H"),
                        next_action="Engage an empanelled/registered Structural Engineer and submit a Structural Stability Certificate.",
                    )
                )
                return findings

            s_id = _get_v(structural_doc, "id")
            s_name = _get_v(structural_doc, "original_filename", "structural_stability_certificate.pdf")
            s_ext = extractions.get(s_id)
            if not s_ext or _get_v(s_ext, "processing_status") != "processed":
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="unresolved",
                        title="Structural Stability Certificate Extraction Incomplete",
                        reason="Structural Stability Certificate has been uploaded but OCR extraction is still in progress.",
                        document_id=s_id,
                        document_name=s_name,
                        next_action="Wait for OCR processing to complete.",
                    )
                )
                return findings

            s_fields = _get_v(s_ext, "fields", {}) or {}
            cert_num_field = s_fields.get("certificate_number")
            license_field = s_fields.get("engineer_license_number")
            s_issue_date_field = s_fields.get("issue_date") or s_fields.get("date_of_inspection") or s_fields.get("valid_until")

            cert_num = cert_num_field.get("value") if isinstance(cert_num_field, dict) else cert_num_field
            license_num = license_field.get("value") if isinstance(license_field, dict) else license_field

            if s_issue_date_field and (s_issue_date_field.get("value") if isinstance(s_issue_date_field, dict) else s_issue_date_field):
                s_date_str = str(s_issue_date_field.get("value") if isinstance(s_issue_date_field, dict) else s_issue_date_field)
                s_year_match = re.search(r"(\d{4})", s_date_str)
                if s_year_match:
                    s_cert_year = int(s_year_match.group(1))
                    parsed_s_date = parse_iso_date(s_date_str)
                    if parsed_s_date:
                        s_cert_age = calculate_calendar_years_between(parsed_s_date, ref_date)
                    else:
                        s_cert_age = ref_date.year - s_cert_year

                    if s_cert_age > 5:
                        findings.append(
                            FindingCreate(
                                rule_id=target_rule_id,
                                status="flagged",
                                title="Structural Stability Certificate Expired (> 5 Years)",
                                reason=(
                                    f"Structural Stability Certificate date is {s_date_str} (age {s_cert_age} years). "
                                    f"Per APH Clause 6.17(h), a Structural Stability Certificate is valid for a period of "
                                    f"FIVE years from the date of issue."
                                ),
                                document_id=s_id,
                                document_name=s_name,
                                evidence={
                                    "structural_certificate_date": s_date_str,
                                    "certificate_age_years": s_cert_age,
                                    "validity_limit_years": 5,
                                    "clause_reference": "APH 2024-2027 Clause 6.17(h)",
                                },
                                clause_ref=self.clause_registry.get("APH_2024_27_CLAUSE_6_17_H"),
                                next_action="Obtain renewed Structural Stability Certificate from a registered Structural Engineer.",
                            )
                        )
                        return findings

            if not cert_num or not license_num:
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="flagged",
                        title="Structural Stability Certificate Missing Key License/Cert Info",
                        reason="Structural Stability Certificate is missing certificate number or registered engineer license number.",
                        document_id=s_id,
                        document_name=s_name,
                        evidence={"certificate_number": cert_num, "engineer_license_number": license_num},
                        clause_ref=self.clause_registry.get("APH_2024_27_CLAUSE_6_17_H"),
                        next_action="Ensure the submitted Structural Stability Certificate includes the registered engineer's official license/registration number.",
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=target_rule_id,
                        status="pass",
                        title="Structural Stability Certificate Provided (> 30 Years)",
                        reason=(
                            f"Building age ({building_age} years from Completion Certificate issue date) is supported by a "
                            f"Structural Stability Certificate (Ref: {cert_num}, Engineer Reg: {license_num}) consistent with "
                            f"Clause 6.17(h) (within 5-year validity period) and Annexure-2 §2.1(iv)."
                        ),
                        document_id=s_id,
                        document_name=s_name,
                        evidence={
                            "completion_certificate_issue_date": date_str,
                            "completion_year": completion_year,
                            "building_age_years": building_age,
                            "certificate_number": cert_num,
                            "engineer_license_number": license_num,
                            "validity_years": 5,
                        },
                        clause_ref=self.clause_registry.get("APH_2024_27_CLAUSE_6_17_H"),
                        next_action="No action required.",
                    )
                )
            return findings

        # 7. Generic Branched Rule Evaluation (Fallback for custom branched rules)
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

        # 8. Single Condition Evaluation (Standard Fallback)
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
