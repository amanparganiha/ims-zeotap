"""
Redis Stream consumer — the "brain" of the system.

Responsibilities:
  1. Read signals from Redis Stream (consumer group for reliability)
  2. Apply debounce: 100 signals / 10s per component_id → 1 WorkItem
  3. Write raw signal to MongoDB (audit log)
  4. Create/update WorkItem in PostgreSQL (transactional)
  5. Update Redis dashboard cache
  6. Write timeseries metric to TimescaleDB (every signal)
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, text
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from core.database import get_mongo_db, get_redis, AsyncSessionLocal
from models.work_item import WorkItem
from workflow.alerting import AlertContext, evaluate_alert

log = logging.getLogger(__name__)
settings = get_settings()

DEBOUNCE_PREFIX = "ims:debounce:"


async def _ensure_stream_group(redis):
    try:
        await redis.xgroup_create(
            settings.redis_stream_key,
            settings.redis_stream_group,
            id="0",
            mkstream=True,
        )
    except Exception:
        pass  # group already exists


async def _write_timeseries(session, signal: dict, severity: str = "P3"):
    """
    Write a signal metric to the TimescaleDB hypertable.
    This powers time-bucket aggregations (signals/min per component).
    """
    try:
        await session.execute(
            text("""
                INSERT INTO signal_metrics (time, component_id, signal_count, severity)
                VALUES (:time, :component_id, 1, :severity)
            """),
            {
                "time": datetime.now(timezone.utc),
                "component_id": signal.get("component_id", "UNKNOWN"),
                "severity": severity,
            },
        )
        await session.commit()
    except Exception as exc:
        log.warning("Timeseries write failed (non-critical): %s", exc)


async def _update_dashboard_cache(redis, work_item: WorkItem):
    """
    Store a lightweight summary in a Redis Hash per WorkItem.
    The list endpoint reads from here first — avoids hitting Postgres
    on every UI poll (hot-path cache).
    """
    key = f"ims:wi:{work_item.id}"
    await redis.hset(key, mapping={
        "id": str(work_item.id),
        "component_id": work_item.component_id,
        "severity": work_item.severity,
        "status": work_item.status,
        "title": work_item.title,
        "signal_count": str(work_item.signal_count),
        "created_at": work_item.created_at.isoformat() if work_item.created_at else "",
        "mttr_seconds": str(work_item.mttr_seconds or ""),
    })
    await redis.expire(key, 3600)  # 1 hour TTL

    # Also maintain a sorted set of all work item IDs by severity (P0=0, P3=3)
    severity_score = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(work_item.severity, 3)
    await redis.zadd("ims:wi:index", {str(work_item.id): severity_score})


async def _process_signal(signal: dict, redis, mongo_db, session):
    component_id = signal["component_id"]
    debounce_key = f"{DEBOUNCE_PREFIX}{component_id}"

    # Determine severity early (needed for timeseries write)
    ctx = AlertContext(
        component_id=component_id,
        component_type=signal.get("component_type", "UNKNOWN"),
        error_code=signal.get("error_code", "UNKNOWN"),
        message=signal.get("message", ""),
    )
    alert = evaluate_alert(ctx)

    # ── Write raw signal to MongoDB (always — audit log) ──────────────────
    signal_doc = {**signal, "ingested_at": datetime.now(timezone.utc)}
    insert_result = await mongo_db.signals.insert_one(signal_doc)

    # ── Write timeseries metric to TimescaleDB (every signal) ─────────────
    await _write_timeseries(session, signal, severity=alert.severity)

    # ── Debounce: find or create WorkItem ─────────────────────────────────
    existing_id = await redis.get(debounce_key)

    if existing_id:
        # Link signal to existing work item in Mongo
        await mongo_db.signals.update_one(
            {"_id": insert_result.inserted_id},
            {"$set": {"work_item_id": existing_id}},
        )
        # Increment signal_count in Postgres (atomic)
        await session.execute(
            update(WorkItem)
            .where(WorkItem.id == uuid.UUID(existing_id))
            .values(signal_count=WorkItem.signal_count + 1)
        )
        await session.commit()

        # Keep Redis cache in sync (avoid stale signal_count on dashboard)
        cache_key = f"ims:wi:{existing_id}"
        await redis.hincrby(cache_key, "signal_count", 1)

        log.debug("Debounced signal → work_item %s", existing_id)
        return

    # ── New WorkItem ───────────────────────────────────────────────────────
    work_item = WorkItem(
        component_id=component_id,
        severity=alert.severity,
        status="OPEN",
        title=alert.title,
        signal_count=1,
    )
    session.add(work_item)
    await session.flush()   # get UUID before commit
    work_item_id = str(work_item.id)
    await session.commit()

    # Tag signal in Mongo with work_item_id
    await mongo_db.signals.update_one(
        {"_id": insert_result.inserted_id},
        {"$set": {"work_item_id": work_item_id}},
    )

    # Set debounce key with TTL
    await redis.setex(debounce_key, settings.debounce_window_seconds, work_item_id)

    # Write to Redis dashboard cache
    await _update_dashboard_cache(redis, work_item)

    log.info(
        "Created WorkItem %s  severity=%s  component=%s",
        work_item_id, alert.severity, component_id,
    )


async def run_consumer():
    """Main consumer loop. Runs forever as a background task."""
    redis = get_redis()
    mongo_db = get_mongo_db()
    await _ensure_stream_group(redis)
    log.info("Signal consumer started on stream '%s'", settings.redis_stream_key)

    while True:
        try:
            messages = await redis.xreadgroup(
                groupname=settings.redis_stream_group,
                consumername="processor-1",
                streams={settings.redis_stream_key: ">"},
                count=100,
                block=1000,  # ms — yields event loop when idle
            )
            if not messages:
                continue

            for _stream, entries in messages:
                for msg_id, fields in entries:
                    try:
                        signal = json.loads(fields["data"])
                        async with AsyncSessionLocal() as session:
                            await _process_signal(signal, redis, mongo_db, session)
                        await redis.xack(
                            settings.redis_stream_key,
                            settings.redis_stream_group,
                            msg_id,
                        )
                    except SQLAlchemyError as exc:
                        log.error(
                            "DB error on signal %s: %s — will retry (not ack'd)",
                            msg_id, exc,
                        )
                        # Deliberately NOT ack'd → redelivered by Redis
                    except Exception as exc:
                        log.error("Unexpected error on signal %s: %s", msg_id, exc)
                        await redis.xack(
                            settings.redis_stream_key,
                            settings.redis_stream_group,
                            msg_id,
                        )

        except asyncio.CancelledError:
            log.info("Consumer shutting down gracefully")
            break
        except Exception as exc:
            log.error("Consumer loop error: %s — retrying in 2s", exc)
            await asyncio.sleep(2)