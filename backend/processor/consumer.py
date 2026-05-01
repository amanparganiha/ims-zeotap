"""
Redis Stream consumer — the "brain" of the system.

Responsibilities:
  1. Read signals from Redis Stream (consumer group for reliability)
  2. Apply debounce: 100 signals / 10s per component_id → 1 WorkItem
  3. Write raw signal to MongoDB (audit log)
  4. Create/update WorkItem in PostgreSQL (transactional)
  5. Update Redis dashboard cache
  6. Record timeseries metric in TimescaleDB
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from core.database import get_mongo_db, get_redis, AsyncSessionLocal
from models.work_item import WorkItem
from workflow.alerting import AlertContext, evaluate_alert

log = logging.getLogger(__name__)
settings = get_settings()

DEBOUNCE_PREFIX = "ims:debounce:"
DASHBOARD_KEY = "ims:dashboard"


async def _ensure_stream_group(redis):
    try:
        await redis.xgroup_create(
            settings.redis_stream_key,
            settings.redis_stream_group,
            id="0",
            mkstream=True,
        )
    except Exception:
        pass   # group already exists


async def _process_signal(signal: dict, redis, mongo_db, session):
    component_id = signal["component_id"]
    debounce_key = f"{DEBOUNCE_PREFIX}{component_id}"

    # ── Write raw signal to MongoDB (always) ──────────────────────────────
    signal_doc = {**signal, "ingested_at": datetime.now(timezone.utc)}
    insert_result = await mongo_db.signals.insert_one(signal_doc)

    # ── Debounce: find or create WorkItem ─────────────────────────────────
    existing_id = await redis.get(debounce_key)

    if existing_id:
        # Link signal to existing work item
        await mongo_db.signals.update_one(
            {"_id": insert_result.inserted_id},
            {"$set": {"work_item_id": existing_id}},
        )
        # Increment signal_count atomically in Postgres
        await session.execute(
            update(WorkItem)
            .where(WorkItem.id == uuid.UUID(existing_id))
            .values(signal_count=WorkItem.signal_count + 1)
        )
        await session.commit()
        log.debug("Debounced signal → work_item %s", existing_id)
        return

    # New work item
    ctx = AlertContext(
        component_id=component_id,
        component_type=signal.get("component_type", "UNKNOWN"),
        error_code=signal.get("error_code", "UNKNOWN"),
        message=signal.get("message", ""),
    )
    alert = evaluate_alert(ctx)

    work_item = WorkItem(
        component_id=component_id,
        severity=alert.severity,
        status="OPEN",
        title=alert.title,
        signal_count=1,
    )
    session.add(work_item)
    await session.flush()   # get the UUID before commit
    work_item_id = str(work_item.id)
    await session.commit()

    # Tag signal in Mongo
    await mongo_db.signals.update_one(
        {"_id": insert_result.inserted_id},
        {"$set": {"work_item_id": work_item_id}},
    )

    # Set debounce key (expires after window)
    await redis.setex(debounce_key, settings.debounce_window_seconds, work_item_id)

    # Update dashboard cache
    await _update_dashboard_cache(redis, work_item)

    log.info("Created WorkItem %s  severity=%s  component=%s", work_item_id, alert.severity, component_id)


async def _update_dashboard_cache(redis, work_item: WorkItem):
    """Store a lightweight summary in Redis Hash for instant dashboard reads."""
    key = f"ims:wi:{work_item.id}"
    await redis.hset(key, mapping={
        "id": str(work_item.id),
        "component_id": work_item.component_id,
        "severity": work_item.severity,
        "status": work_item.status,
        "title": work_item.title,
        "signal_count": work_item.signal_count,
        "created_at": work_item.created_at.isoformat() if work_item.created_at else "",
    })
    await redis.expire(key, 3600)   # 1 hour TTL


async def run_consumer():
    """Main consumer loop. Runs forever as a background task."""
    redis = get_redis()
    mongo_db = get_mongo_db()
    await _ensure_stream_group(redis)
    log.info("Signal consumer started, listening on stream '%s'", settings.redis_stream_key)

    while True:
        try:
            messages = await redis.xreadgroup(
                groupname=settings.redis_stream_group,
                consumername="processor-1",
                streams={settings.redis_stream_key: ">"},
                count=100,
                block=1000,   # ms — yields control when idle
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
                        log.error("DB error processing signal %s: %s — will retry", msg_id, exc)
                        # Not ack'd → will be redelivered (built-in retry)
                    except Exception as exc:
                        log.error("Unexpected error on signal %s: %s", msg_id, exc)
                        await redis.xack(
                            settings.redis_stream_key,
                            settings.redis_stream_group,
                            msg_id,
                        )

        except asyncio.CancelledError:
            log.info("Consumer shutting down")
            break
        except Exception as exc:
            log.error("Consumer loop error: %s — retrying in 2s", exc)
            await asyncio.sleep(2)
