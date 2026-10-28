from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, field_validator

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


class FindingReviewUpdate(BaseModel):
    reviewer_decision: ReviewerDecision
    reviewer_notes: str
    reviewed_by: Optional[str] = None

    @field_validator("reviewer_notes")
    @classmethod
    def validate_reviewer_notes(cls, v: str) -> str:
        trimmed = (v or "").strip()
        if len(trimmed) < 10:
            raise ValueError("Reviewer justification notes must be at least 10 characters after trimming whitespace.")
        return trimmed



class AcknowledgeDuplicateRequest(BaseModel):
    reviewer_notes: str
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
    reviewer_decision: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
