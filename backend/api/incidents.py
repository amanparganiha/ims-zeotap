"""
REST API for work items (incidents) and RCA.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_pg_session, get_mongo_db, get_redis
from models.work_item import WorkItem, RCARecord
from models.schemas import (
    WorkItemResponse, WorkItemStatusUpdate,
    RCASubmission, RCAResponse,
)
from workflow.states import validate_transition, get_state

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/incidents", tags=["Incidents"])

ROOT_CAUSE_CATEGORIES = [
    "Infrastructure Failure",
    "Software Bug",
    "Configuration Error",
    "Network Issue",
    "Dependency Failure",
    "Capacity Exhaustion",
    "Security Incident",
    "Human Error",
    "Unknown",
]


@router.get("", response_model=list[WorkItemResponse])
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_pg_session),
):
    q = select(WorkItem).order_by(WorkItem.severity, WorkItem.created_at.desc()).limit(limit)
    if status:
        q = q.where(WorkItem.status == status)
    if severity:
        q = q.where(WorkItem.severity == severity)
    result = await session.execute(q)
    return result.scalars().all()


@router.get("/{incident_id}", response_model=WorkItemResponse)
async def get_incident(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_pg_session),
):
    item = await session.get(WorkItem, incident_id)
    if not item:
        raise HTTPException(404, "Incident not found")
    return item


@router.get("/{incident_id}/signals")
async def get_incident_signals(
    incident_id: uuid.UUID,
    limit: int = Query(100, le=500),
    mongo_db=Depends(get_mongo_db),
):
    """Raw signals from MongoDB (the audit log)."""
    cursor = (
        mongo_db.signals
        .find({"work_item_id": str(incident_id)}, {"_id": 0})
        .sort("received_at", -1)
        .limit(limit)
    )
    signals = await cursor.to_list(length=limit)
    return {"incident_id": str(incident_id), "signals": signals, "count": len(signals)}


@router.patch("/{incident_id}/status", response_model=WorkItemResponse)
async def update_status(
    incident_id: uuid.UUID,
    body: WorkItemStatusUpdate,
    session: AsyncSession = Depends(get_pg_session),
    redis=Depends(get_redis),
):
    item = await session.get(WorkItem, incident_id)
    if not item:
        raise HTTPException(404, "Incident not found")

    # Validate state machine transition
    try:
        validate_transition(item.status, body.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    # CLOSED requires an RCA
    if body.status == "CLOSED":
        rca = await session.execute(
            select(RCARecord).where(RCARecord.work_item_id == incident_id)
        )
        if not rca.scalar_one_or_none():
            raise HTTPException(
                400,
                "Cannot close incident without a completed RCA. Submit RCA first.",
            )

    # Apply state entry hooks
    state = get_state(body.status)
    item_dict = {
        "created_at": item.created_at,
        "resolved_at": item.resolved_at,
        "closed_at": item.closed_at,
        "mttr_seconds": item.mttr_seconds,
    }
    updated = state.on_enter(item_dict)

    item.status = body.status
    item.resolved_at = updated.get("resolved_at")
    item.closed_at = updated.get("closed_at")
    item.mttr_seconds = updated.get("mttr_seconds")

    await session.commit()
    await session.refresh(item)

    # Invalidate / update cache
    cache_key = f"ims:wi:{incident_id}"
    await redis.hset(cache_key, mapping={"status": item.status})

    return item


@router.post("/{incident_id}/rca", response_model=RCAResponse, status_code=201)
async def submit_rca(
    incident_id: uuid.UUID,
    body: RCASubmission,
    session: AsyncSession = Depends(get_pg_session),
):
    item = await session.get(WorkItem, incident_id)
    if not item:
        raise HTTPException(404, "Incident not found")
    if item.status not in ("INVESTIGATING", "RESOLVED"):
        raise HTTPException(400, "RCA can only be submitted for INVESTIGATING or RESOLVED incidents")

    # Idempotency: reject duplicate RCA
    existing = await session.execute(
        select(RCARecord).where(RCARecord.work_item_id == incident_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "RCA already submitted for this incident")

    rca = RCARecord(
        work_item_id=incident_id,
        incident_start=body.incident_start,
        incident_end=body.incident_end,
        root_cause_category=body.root_cause_category,
        fix_applied=body.fix_applied,
        prevention_steps=body.prevention_steps,
    )
    session.add(rca)
    await session.commit()
    await session.refresh(rca)
    return rca


@router.get("/{incident_id}/rca", response_model=RCAResponse)
async def get_rca(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_pg_session),
):
    result = await session.execute(
        select(RCARecord).where(RCARecord.work_item_id == incident_id)
    )
    rca = result.scalar_one_or_none()
    if not rca:
        raise HTTPException(404, "No RCA found for this incident")
    return rca


@router.get("/meta/categories")
async def get_categories():
    return {"categories": ROOT_CAUSE_CATEGORIES}
