from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, index=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="draft")
    institution_name = Column(String(500), nullable=False)
    application_category = Column(String(50), nullable=False, default="eoa")
    academic_year = Column(String(10), nullable=False)
    overall_status = Column(String(50), nullable=False, default="processing_incomplete")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    owner = relationship("User", back_populates="applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan", lazy="selectin")
    findings = relationship("Finding", back_populates="application", cascade="all, delete-orphan", lazy="selectin")

