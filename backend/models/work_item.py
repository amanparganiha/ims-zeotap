"""
SQLAlchemy ORM models for PostgreSQL (Source of Truth).
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)   # P0-P3
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mttr_seconds: Mapped[int | None] = mapped_column(Integer)


class RCARecord(Base):
    __tablename__ = "rca_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    incident_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    incident_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    root_cause_category: Mapped[str] = mapped_column(String(100))
    fix_applied: Mapped[str] = mapped_column(Text)
    prevention_steps: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
