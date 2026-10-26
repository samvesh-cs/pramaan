from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict

CheckStatus = Literal["pass", "flagged", "missing", "unresolved", "not_applicable"]


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
