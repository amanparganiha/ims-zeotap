"""
Pydantic schemas for API request/response validation.
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


# ── Signal (incoming from producers) ─────────────────────────────────────────
class SignalPayload(BaseModel):
    component_id: str
    component_type: str          # API | MCP_HOST | CACHE | QUEUE | RDBMS | NOSQL
    error_code: str
    message: str
    latency_ms: Optional[float] = None
    metadata: Optional[dict] = None


# ── Work Item ─────────────────────────────────────────────────────────────────
class WorkItemResponse(BaseModel):
    id: uuid.UUID
    component_id: str
    severity: str
    status: str
    title: str
    signal_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    mttr_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class WorkItemStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


# ── RCA ───────────────────────────────────────────────────────────────────────
class RCASubmission(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    fix_applied: str
    prevention_steps: str

    @field_validator("fix_applied", "prevention_steps", "root_cause_category")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("incident_end")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("incident_start")
        if start and v <= start:
            raise ValueError("incident_end must be after incident_start")
        return v


class RCAResponse(BaseModel):
    id: uuid.UUID
    work_item_id: uuid.UUID
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    fix_applied: str
    prevention_steps: str
    submitted_at: datetime

    class Config:
        from_attributes = True


# ── Health ────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    postgres: str
    mongo: str
    redis: str
    uptime_seconds: float
