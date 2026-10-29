from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, index=True)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(100), nullable=False)
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)
    perceptual_hash = Column(String(64), nullable=True, index=True)
    processing_status = Column(String(50), nullable=False, default="uploaded")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    application = relationship("Application", back_populates="documents")
    extractions = relationship("ExtractionRun", back_populates="document", cascade="all, delete-orphan", lazy="selectin")
    findings = relationship("Finding", back_populates="document", lazy="selectin")


Index("idx_documents_application_id", Document.application_id)
