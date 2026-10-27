"""
Pydantic Schemas for Declarative AICTE Scrutiny Rules and Clause Registry.
Conforms to AICTE Approval Process Handbook (APH 2024–2027) statutory grounding.
"""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


SeverityLevel = Literal["critical", "high", "medium", "low", "info"]
SignalType = Literal["rule", "tamper", "issuer", "duplicate"]


class ClauseCitation(BaseModel):
    """Statutory clause reference verified against physical AICTE handbook pages."""
    clause_id: str
    chapter_or_annexure: str
    clause_number: str
    handbook_page: int
    pdf_page: int
    title: str
    summary: Optional[str] = None


class RuleCondition(BaseModel):
    """Declarative condition evaluated against document or application context."""
    field: Optional[str] = None
    operator: Literal[
        "exists",
        "equals",
        "not_equals",
        "date_lte_years",
        "date_not_expired",
        "greater_or_equal",
        "consistent_across_documents",
        "custom",
    ]
    target_value: Optional[Any] = None
    unit: Optional[str] = None
    parameters: Optional[dict[str, Any]] = Field(default_factory=dict)


class DeclarativeRuleConfig(BaseModel):
    """Pydantic model validating declarative YAML rule configurations."""
    rule_id: str
    title: str
    category: str = "eoa"
    document_type: Optional[str] = None
    clause_id: str
    severity: SeverityLevel = "medium"
    signal_type: SignalType = "rule"
    condition: RuleCondition
    pass_title: str
    pass_reason_template: str
    flag_title: str
    flag_reason_template: str
    next_action: Optional[str] = None
    is_active: bool = True
