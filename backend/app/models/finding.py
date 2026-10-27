from datetime import datetime, timezone
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, index=True)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_id = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)  # pass | flagged | missing | unresolved | not_applicable
    title = Column(String(500), nullable=False)
    reason = Column(Text, nullable=False)
    document_name = Column(String(500), nullable=True)
    evidence = Column(JSON, nullable=True)  # {page_number, text, field, value, bbox}
    next_action = Column(Text, nullable=True)
    clause_ref = Column(JSON, nullable=True)  # {clause_id, chapter_or_annexure, clause_number, handbook_page, pdf_page, title}
    severity = Column(String(20), nullable=True, default="medium")  # critical | high | medium | low | info
    signal_type = Column(String(20), nullable=True, default="rule")  # rule | tamper | issuer | duplicate
    reviewer_decision = Column(String(50), nullable=True)  # verified | confirmed_discrepancy | requested_resubmission | escalated
    reviewer_notes = Column(Text, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    application = relationship("Application", back_populates="findings")
    document = relationship("Document", back_populates="findings")


Index("idx_findings_application_id", Finding.application_id)
Index("idx_findings_document_id", Finding.document_id)
