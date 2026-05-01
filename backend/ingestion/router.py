"""
Signal ingestion endpoint.
Signals are pushed to Redis Streams immediately (non-blocking).
The heavy lifting (debounce, DB writes) happens in the processor.
"""
import json
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import get_settings
from core.database import get_redis
from models.schemas import SignalPayload
from ingestion.metrics import signal_counter

log = logging.getLogger(__name__)
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/signals", tags=["Ingestion"])


@router.post("", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def ingest_signal(
    request: Request,
    payload: SignalPayload,
    redis=Depends(get_redis),
):
    """
    Accepts a signal and enqueues it on Redis Streams.
    Returns 202 Accepted immediately — never blocks on DB.
    """
    entry = payload.model_dump()
    entry["received_at"] = time.time()

    try:
        await redis.xadd(
            settings.redis_stream_key,
            {"data": json.dumps(entry)},
            maxlen=settings.max_stream_len,
            approximate=True,
        )
    except Exception as exc:
        log.error("Redis xadd failed: %s", exc)
        raise HTTPException(status_code=503, detail="Signal queue unavailable")

    signal_counter.inc()
    return {"status": "accepted"}


@router.post("/batch", status_code=202)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def ingest_batch(
    request: Request,
    payloads: list[SignalPayload],
    redis=Depends(get_redis),
):
    """Batch ingest up to 500 signals in one call."""
    if len(payloads) > 500:
        raise HTTPException(status_code=400, detail="Max batch size is 500")

    pipe = redis.pipeline(transaction=False)
    for payload in payloads:
        entry = payload.model_dump()
        entry["received_at"] = time.time()
        pipe.xadd(
            settings.redis_stream_key,
            {"data": json.dumps(entry)},
            maxlen=settings.max_stream_len,
            approximate=True,
        )
    await pipe.execute()
    signal_counter.inc(len(payloads))
    return {"status": "accepted", "count": len(payloads)}
