from typing import Literal, Optional, Any
from pydantic import BaseModel, ConfigDict, Field

DocumentProcessingStatus = Literal["uploaded", "processing", "processed", "processing_failed"]


class DuplicateWarning(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str  # same_file_in_application | same_file_other_application | same_certificate_number | visual_duplicate
    title: str
    message: str
    evidence: dict[str, Any]
    next_action: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    document_type: str
    original_filename: str
    mime_type: str
    file_hash: str | None = None
    perceptual_hash: str | None = None
    processing_status: DocumentProcessingStatus
    fields: dict[str, dict[str, Any]] = Field(default_factory=dict)
    duplicate_warnings: Optional[list[DuplicateWarning | dict[str, Any]]] = None
