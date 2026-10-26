from typing import Literal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

DocumentProcessingStatus = Literal["uploaded", "processing", "processed", "processing_failed"]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    document_type: str
    original_filename: str
    mime_type: str
    processing_status: DocumentProcessingStatus
    fields: dict[str, dict[str, Any]] = Field(default_factory=dict)
