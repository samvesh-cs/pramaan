from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class RegionExtraction(BaseModel):
    text: str
    confidence: Optional[float] = None
    bbox: Optional[list[float]] = None


class PageExtraction(BaseModel):
    page_number: int
    text: str
    regions: Optional[list[RegionExtraction]] = []


class FieldExtraction(BaseModel):
    value: Optional[Any] = None
    normalized_value: Optional[Any] = None
    raw_text: Optional[str] = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    bbox: Optional[list[float]] = None


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    document_type: str
    processing_status: str
    pages: Optional[list[PageExtraction]] = []
    fields: Optional[dict[str, FieldExtraction]] = {}
    error: Optional[str] = None
