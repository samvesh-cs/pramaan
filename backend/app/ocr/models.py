"""Pydantic models for Document OCR and Extraction.
Follows docs/API_CONTRACT.md section 5.
"""

from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field


class Region(BaseModel):
    text: str
    confidence: Optional[float] = None
    bbox: Optional[List[float]] = None  # [x1, y1, x2, y2]


class PageResult(BaseModel):
    page_number: int
    text: str
    regions: List[Region] = Field(default_factory=list)


class ExtractedField(BaseModel):
    value: Optional[Any] = None
    normalized_value: Optional[Any] = None
    raw_text: Optional[str] = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    bbox: Optional[List[float]] = None  # [x1, y1, x2, y2]
    status: Optional[str] = None  # 'extracted' | 'missing' | 'uncertain'


class ExtractionResult(BaseModel):
    document_id: Optional[str] = None
    document_type: Optional[str] = None
    processing_status: str = "processed"  # 'processed' | 'processing_failed'
    pages: List[PageResult] = Field(default_factory=list)
    fields: Dict[str, ExtractedField] = Field(default_factory=dict)
    error: Optional[str] = None
