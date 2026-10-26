from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.document import DocumentResponse
from app.schemas.finding import FindingResponse

OverallStatus = Literal[
    "ready_for_review",
    "missing_documents",
    "discrepancies_found",
    "unresolved_checks",
    "processing_incomplete",
    "checks_passed",
]


class ApplicationCreate(BaseModel):
    institution_name: str = Field(..., min_length=2, max_length=500, description="Full registered institution name")
    application_category: Literal["eoa"] = Field(default="eoa", description="Application category code")
    academic_year: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="Academic year (e.g., 2026-27)")


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_name: str
    application_category: str
    academic_year: str
    created_at: datetime
    overall_status: OverallStatus


class ApplicationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_name: str
    application_category: str
    academic_year: str
    overall_status: OverallStatus
    documents: list[DocumentResponse] = []
    findings: list[FindingResponse] = []
