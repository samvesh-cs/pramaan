"""
Declarative Rule Engine for AICTE Scrutiny Platform.
Loads verified statutory clauses from clauses.json and executes declarative rules from rules_eoa.yaml.
"""

from datetime import date, datetime
import json
import logging
from pathlib import Path
from typing import Any, Optional
import yaml

from app.schemas.finding import FindingCreate
from app.schemas.rule_definition import ClauseCitation, DeclarativeRuleConfig

logger = logging.getLogger(__name__)

RULES_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CLAUSES_PATH = RULES_DATA_DIR / "clauses.json"
DEFAULT_RULES_YAML_PATH = RULES_DATA_DIR / "rules_eoa.yaml"


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
    """Engine executing declarative Pydantic-validated rules against application validation context."""

    def __init__(
        self,
        rules_path: Path = DEFAULT_RULES_YAML_PATH,
        clause_registry: Optional[ClauseRegistry] = None,
    ):
        self.clause_registry = clause_registry or ClauseRegistry()
        self.rules: list[DeclarativeRuleConfig] = []
        self.load_rules(rules_path)

    def load_rules(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Rule definition YAML file not found at: {path}")

        try:
            raw_content = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML syntax in {path}: {exc}") from exc

        if not isinstance(raw_content, dict) or "rules" not in raw_content:
            raise ValueError(f"Invalid rule file format in {path}: must be mapping with 'rules' key")

        parsed_rules: list[DeclarativeRuleConfig] = []
        for idx, rule_dict in enumerate(raw_content["rules"]):
            try:
                rule_cfg = DeclarativeRuleConfig(**rule_dict)
                # Verify that clause_id / clause_ids exist in clause registry if specified
                if rule_cfg.clause_id and not self.clause_registry.get(rule_cfg.clause_id):
                    logger.warning(
                        "Rule '%s' references unknown clause '%s'",
                        rule_cfg.rule_id,
                        rule_cfg.clause_id,
                    )
                for cid in (rule_cfg.clause_ids or []):
                    if not self.clause_registry.get(cid):
                        logger.warning(
                            "Rule '%s' references unknown clause '%s'",
                            rule_cfg.rule_id,
                            cid,
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

        # 1. DOC_PRESENCE_001
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

        # 2. FIELD_001
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

        # 3. EXPIRY_001
        if rule_cfg.rule_id == "EXPIRY_001":
            target_doc = next((d for d in docs if _get_v(d, "document_type") == "fire_safety_certificate"), None)
            if target_doc:
                ext = extractions.get(_get_v(target_doc, "id"))
                ext_fields = _get_v(ext, "fields", {}) if ext else {}
                expiry_val = None
                if isinstance(ext_fields, dict) and "expiry_date" in ext_fields:
                    fld = ext_fields["expiry_date"]
                    expiry_val = fld.get("value") if isinstance(fld, dict) else fld
                doc_name = _get_v(target_doc, "original_filename", "fire_safety_certificate.pdf")
                if expiry_val:
                    try:
                        exp_date = date.fromisoformat(str(expiry_val).strip()[:10])
                        today = date.today()
                        if exp_date >= today:
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
                    except Exception:
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

        # 4. CONSISTENCY_001
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

        return findings


# Global singleton instances for zero-overhead startup
default_clause_registry = ClauseRegistry()
default_declarative_engine = DeclarativeRuleEngine(clause_registry=default_clause_registry)
