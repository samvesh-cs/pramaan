"""
Legacy Rule Adapter for Zero-Regression Compatibility.
Wraps existing Python rules so they emit findings decorated with statutory clause references,
severities, and signal types from the verified ClauseRegistry.
"""

from typing import Any, Optional
from app.rules.base import BaseRule
from app.rules.declarative_engine import ClauseRegistry, default_clause_registry
from app.schemas.finding import FindingCreate
from app.schemas.rule_definition import ClauseCitation, SeverityLevel, SignalType

# Mapping existing rule IDs to statutory clause keys and severities
RULE_STATUTORY_METADATA: dict[str, dict[str, Any]] = {
    "DOC_PRESENCE_001": {
        "clause_id": "APH_2024_27_ANNEX_2_CLAUSE_2_1_V",
        "severity": "critical",
        "signal_type": "rule",
    },
    "FIELD_001": {
        "clause_id": "APH_2024_27_ANNEX_2_CLAUSE_2_1_V",
        "severity": "high",
        "signal_type": "rule",
    },
    "FIELD_002": {
        "clause_id": "APH_2024_27_ANNEX_2_CLAUSE_2_1_V",
        "severity": "high",
        "signal_type": "rule",
    },
    "EXPIRY_001": {
        "clause_id": "APH_2024_27_ANNEX_2_CLAUSE_2_1_V",
        "severity": "critical",
        "signal_type": "rule",
    },
    "CONSISTENCY_001": {
        "clause_id": "APH_2024_27_AFFIDAVIT_2",
        "severity": "critical",
        "signal_type": "rule",
    },
    "TER_PAYMENT_001": {
        "clause_id": "APH_2024_27_ANNEX_2_CLAUSE_2_1_II",
        "severity": "high",
        "signal_type": "rule",
    },
    "STRUCTURAL_001": {
        "clause_id": "APH_2024_27_ANNEX_2_CLAUSE_2_1_IV",
        "severity": "high",
        "signal_type": "rule",
    },
    "DUPLICATE_DOC_001": {
        "clause_id": "APH_2024_27_ANNEX_2_CLAUSE_2_1_I",
        "severity": "critical",
        "signal_type": "duplicate",
    },
}


class EnhancedRuleWrapper(BaseRule):
    """
    Wraps an existing BaseRule.
    Evaluates the inner rule and decorates every generated FindingCreate
    with statutory clause_ref, severity, and signal_type.
    """

    def __init__(self, inner_rule: BaseRule, registry: Optional[ClauseRegistry] = None):
        self.inner_rule = inner_rule
        self.rule_id = getattr(inner_rule, "rule_id", inner_rule.__class__.__name__)
        self.title = getattr(inner_rule, "title", self.rule_id)
        self.registry = registry or default_clause_registry

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        raw_findings = self.inner_rule.evaluate(context)
        decorated_findings: list[FindingCreate] = []

        for f in raw_findings:
            # Check metadata lookup for this rule_id
            meta = RULE_STATUTORY_METADATA.get(f.rule_id, {})
            clause_id = meta.get("clause_id")
            clause_ref = self.registry.get(clause_id) if clause_id else None
            severity: SeverityLevel = meta.get("severity", "medium")
            signal_type: SignalType = meta.get("signal_type", "rule")

            # Update finding with statutory citation
            if hasattr(f, "clause_ref") and getattr(f, "clause_ref", None) is None:
                f.clause_ref = clause_ref
            if hasattr(f, "severity"):
                f.severity = severity
            if hasattr(f, "signal_type"):
                f.signal_type = signal_type

            decorated_findings.append(f)

        return decorated_findings


def wrap_legacy_rules(rules: list[BaseRule], registry: Optional[ClauseRegistry] = None) -> list[BaseRule]:
    """Wraps a list of legacy rules with statutory decoration."""
    return [EnhancedRuleWrapper(r, registry=registry) for r in rules]
