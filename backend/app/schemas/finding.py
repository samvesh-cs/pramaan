from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, computed_field, field_validator, model_validator

from app.utils.review_policy import finding_requires_reviewer_decision

CheckStatus = Literal["pass", "flagged", "missing", "unresolved", "not_applicable"]
ReviewerDecision = Literal["verified", "confirmed_discrepancy", "requested_resubmission", "escalated"]


class EvidenceSchema(BaseModel):
    page_number: Optional[int] = None
    text: Optional[str] = None
    field: Optional[str] = None
    value: Optional[Any] = None
    bbox: Optional[list[float]] = None


class FindingCreate(BaseModel):
    rule_id: str
    status: CheckStatus
    title: str
    reason: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    evidence: Optional[dict[str, Any]] = None
    next_action: Optional[str] = None
    clause_ref: Optional[Any] = None
    severity: Optional[str] = "medium"
    signal_type: Optional[str] = "rule"
    advisory: Optional[bool] = False


class FindingReviewUpdate(BaseModel):
    reviewer_decision: ReviewerDecision
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

    @field_validator("reviewer_notes")
    @classmethod
    def validate_reviewer_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if len(trimmed) < 10:
                raise ValueError("Reviewer justification notes must be at least 10 characters after trimming whitespace.")
            return trimmed
        return None

    @model_validator(mode="after")
    def require_action_details(self):
        if self.reviewer_decision in {"requested_resubmission", "escalated"} and not (self.reviewer_notes or "").strip():
            raise ValueError("Provide the information requested from the institution or the reason for escalation.")
        return self



class AcknowledgeDuplicateRequest(BaseModel):
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

    @field_validator("reviewer_notes")
    @classmethod
    def validate_reviewer_notes(cls, v: str) -> str:
        trimmed = (v or "").strip()
        if len(trimmed) < 10:
            raise ValueError("Reviewer justification notes must be at least 10 characters after trimming whitespace.")
        return trimmed


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_id: str
    status: CheckStatus
    title: str
    reason: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    evidence: Optional[dict[str, Any]] = None
    next_action: Optional[str] = None
    clause_ref: Optional[Any] = None
    severity: Optional[str] = "medium"
    signal_type: Optional[str] = "rule"
    advisory: Optional[bool] = False
    ruleset_version: Optional[str] = None
    rule_engine_mode: Optional[str] = None
    ruleset_display_name: Optional[str] = None
    reviewer_decision: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    @computed_field
    @property
    def requires_reviewer_decision(self) -> bool:
        return finding_requires_reviewer_decision(self)

    @model_validator(mode="after")
    def resolve_advisory_status(self) -> "FindingResponse":
        if not self.advisory:
            try:
                from app.rules.legacy_adapter import is_advisory_rule
                if is_advisory_rule(self.rule_id):
                    self.advisory = True
            except Exception:
                pass
        if not self.ruleset_display_name:
            self.ruleset_display_name = self.ruleset_version if self.ruleset_version else "Legacy ruleset"
        return self
