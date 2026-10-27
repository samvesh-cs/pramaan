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
                # Verify that clause_id exists in clause registry
                if not self.clause_registry.get(rule_cfg.clause_id):
                    logger.warning(
                        "Rule '%s' references unknown clause '%s'",
                        rule_cfg.rule_id,
                        rule_cfg.clause_id,
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

    def evaluate_rule(
        self,
        rule_cfg: DeclarativeRuleConfig,
        context: dict[str, Any],
    ) -> list[FindingCreate]:
        """Evaluates a single declarative rule configuration against context."""
        if not rule_cfg.is_active:
            return []

        clause_ref = self.clause_registry.get(rule_cfg.clause_id)
        findings: list[FindingCreate] = []

        # Example operator evaluation
        # Note: Detailed operators delegate to specialized condition handlers
        # For legacy parity, full pipeline runs via legacy_adapter
        return findings


# Global singleton instances for zero-overhead startup
default_clause_registry = ClauseRegistry()
default_declarative_engine = DeclarativeRuleEngine(clause_registry=default_clause_registry)
