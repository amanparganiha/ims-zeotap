"""
/health endpoint — checks all downstream dependencies.
"""
import time
import logging
from fastapi import APIRouter
from sqlalchemy import text

from core.database import get_redis, get_mongo_db, AsyncSessionLocal

log = logging.getLogger(__name__)
router = APIRouter(tags=["Observability"])

_START_TIME = time.monotonic()


@router.get("/health")
async def health_check():
    results = {"postgres": "ok", "mongo": "ok", "redis": "ok"}

    # Postgres
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
    except Exception as exc:
        results["postgres"] = f"error: {exc}"

    # Mongo
    try:
        db = get_mongo_db()
        await db.command("ping")
    except Exception as exc:
        results["mongo"] = f"error: {exc}"

    # Redis
    try:
        r = get_redis()
        await r.ping()
    except Exception as exc:
        results["redis"] = f"error: {exc}"

    overall = "healthy" if all(v == "ok" for v in results.values()) else "degraded"
    return {
        "status": overall,
        **results,
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
    }
