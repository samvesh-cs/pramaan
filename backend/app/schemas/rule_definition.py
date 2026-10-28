"""
Pydantic Schemas for Declarative AICTE Scrutiny Rules and Clause Registry.
Conforms to AICTE Approval Process Handbook (APH 2024–2027) statutory grounding.
Supports three-valued logic (TRUE / FALSE / UNKNOWN) and compound conditions.
"""

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.rules.banned_terms import validate_rule_text_claims


SeverityLevel = Literal["critical", "high", "medium", "low", "info"]
SignalType = Literal["rule", "tamper", "issuer", "duplicate", "internal_check"]


class EvaluationResult(str, Enum):
    """Tri-state logic outcomes for declarative rule conditions (Kleene logic)."""
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class ClauseCitation(BaseModel):
    """Statutory clause reference verified against physical AICTE handbook pages."""
    clause_id: str
    chapter_or_annexure: str
    clause_number: str
    handbook_page: int
    pdf_page: int
    verified: bool = True
    title: str
    summary: Optional[str] = None
    notes: Optional[str] = None
    cross_reference_notes: Optional[str] = None
    excerpt_type: Optional[str] = None
    excerpt: str


class RuleCondition(BaseModel):
    """
    Declarative condition evaluated against document or application context.
    Supports atomic operators and recursive compound operators (all_of, any_of, not).
    """
    # Compound operators
    all_of: Optional[list["RuleCondition"]] = None
    any_of: Optional[list["RuleCondition"]] = None
    not_: Optional["RuleCondition"] = Field(default=None, alias="not")

    # Atomic condition fields
    target: Optional[str] = None  # "document" | "application" | "extraction"
    document_type: Optional[str] = None
    field: Optional[str] = None
    operator: Optional[Literal[
        "exists",
        "not_exists",
        "equals",
        "not_equals",
        "greater_or_equal",
        "greater_than",
        "less_or_equal",
        "less_than",
        "in",
        "not_in",
        "date_lte_years",
        "date_gte_years",
        "date_not_expired",
        "years_between",
        "days_between",
        "consistent_across_documents",
        "fuzzy_similarity",
        "custom",
    ]] = None
    target_value: Optional[Any] = None
    unit: Optional[str] = None
    parameters: Optional[dict[str, Any]] = Field(default_factory=dict)
    outcome: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_condition_structure(self) -> "RuleCondition":
        depth = self.get_depth()
        if depth > 5:
            raise ValueError(f"Condition nesting depth exceeds maximum allowed depth of 5 (got {depth})")

        has_compound = bool(self.all_of is not None or self.any_of is not None or self.not_ is not None)
        has_operator = bool(self.operator is not None)

        if not has_compound and not has_operator:
            raise ValueError("RuleCondition must define either a compound operator (all_of, any_of, not) or an atomic operator")
        return self

    def get_depth(self) -> int:
        child_depths = [0]
        if self.all_of:
            child_depths.extend(c.get_depth() for c in self.all_of)
        if self.any_of:
            child_depths.extend(c.get_depth() for c in self.any_of)
        if self.not_:
            child_depths.append(self.not_.get_depth())
        return 1 + max(child_depths)


class RuleBranch(BaseModel):
    """Branch outcome mapping for compound rules (e.g. Structural Stability)."""
    branch_id: str
    condition: RuleCondition
    outcome: Literal["pass", "flagged", "unresolved"] = "pass"
    title: str
    reason_template: str
    next_action: Optional[str] = None
    clause_id: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_branch_texts(self) -> "RuleBranch":
        validate_rule_text_claims(self.title, f"Branch '{self.branch_id}' title")
        validate_rule_text_claims(self.reason_template, f"Branch '{self.branch_id}' reason_template")
        validate_rule_text_claims(self.next_action, f"Branch '{self.branch_id}' next_action")
        return self


class DeclarativeRuleConfig(BaseModel):
    """Pydantic model validating declarative YAML rule configurations."""
    rule_id: str
    title: str
    category: str = "eoa"
    document_type: Optional[str] = None
    clause_id: Optional[str] = None
    clause_ids: Optional[list[str]] = Field(default_factory=list)
    severity: SeverityLevel = "medium"
    signal_type: SignalType = "rule"
    status: Optional[str] = None
    advisory: bool = False
    condition: Optional[RuleCondition] = None
    branches: Optional[list[RuleBranch]] = Field(default_factory=list)
    pass_title: Optional[str] = None
    pass_reason_template: Optional[str] = None
    flag_title: Optional[str] = None
    flag_reason_template: Optional[str] = None
    next_action: Optional[str] = None
    is_active: bool = True

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_rule_config(self) -> "DeclarativeRuleConfig":
        # 1. Must define condition or branches
        if not self.condition and not self.branches:
            raise ValueError(f"Rule '{self.rule_id}' must define either 'condition' or 'branches'")

        # 2. If condition without branches, pass/flag templates are required
        if self.condition and not self.branches:
            if not self.pass_title or not self.pass_reason_template:
                raise ValueError(f"Rule '{self.rule_id}' defines condition but is missing pass_title or pass_reason_template")
            if not self.flag_title or not self.flag_reason_template:
                raise ValueError(f"Rule '{self.rule_id}' defines condition but is missing flag_title or flag_reason_template")

        # 3. Honest claims validation
        validate_rule_text_claims(self.title, f"Rule '{self.rule_id}' title")
        validate_rule_text_claims(self.pass_title, f"Rule '{self.rule_id}' pass_title")
        validate_rule_text_claims(self.pass_reason_template, f"Rule '{self.rule_id}' pass_reason_template")
        validate_rule_text_claims(self.flag_title, f"Rule '{self.rule_id}' flag_title")
        validate_rule_text_claims(self.flag_reason_template, f"Rule '{self.rule_id}' flag_reason_template")
        validate_rule_text_claims(self.next_action, f"Rule '{self.rule_id}' next_action")

        return self
