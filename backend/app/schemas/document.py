from typing import Literal
from pydantic import BaseModel, ConfigDict

DocumentProcessingStatus = Literal["uploaded", "processing", "processed", "processing_failed"]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    document_type: str
    original_filename: str
    mime_type: str
    processing_status: DocumentProcessingStatus
