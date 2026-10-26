from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.application import OverallStatus
from app.schemas.finding import FindingResponse


class SummaryCount(BaseModel):
    pass_: int = 0
    flagged: int = 0
    missing: int = 0
    unresolved: int = 0
    not_applicable: int = 0

    # Serialization alias for 'pass' which is a Python keyword
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: "pass" if field_name == "pass_" else field_name,
    )


class ReportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    application_id: str
    overall_status: OverallStatus
    summary: dict[str, int]
    missing_document_types: list[str] = []
    findings: list[FindingResponse] = []
    generated_at: datetime
