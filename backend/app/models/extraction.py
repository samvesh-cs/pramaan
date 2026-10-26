from datetime import datetime, timezone
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(String(36), primary_key=True, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    processing_status = Column(String(50), nullable=False)  # processed | processing_failed
    pages = Column(JSON, nullable=True)  # list of {page_number, text, regions[]}
    fields = Column(JSON, nullable=True)  # {field_name: {value, normalized_value, raw_text, confidence, page_number, bbox}}
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("Document", back_populates="extractions")


Index("idx_extraction_runs_document_id", ExtractionRun.document_id)
