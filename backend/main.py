"""
IMS Backend — application entry point.
"""
import asyncio
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.config import get_settings
from core.database import init_db, close_db
from api.health import router as health_router
from api.incidents import router as incidents_router
from ingestion.router import router as ingestion_router, limiter
from ingestion.metrics import throughput_reporter
from processor.consumer import run_consumer

# ── Logging ───────────────────────────────────────────────────────────────────
settings = get_settings()
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.log_level),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Incident Management System",
    version="1.0.0",
    description="Mission-critical IMS for monitoring distributed infrastructure.",
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(incidents_router)


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    log.info("Starting IMS backend...")
    await init_db()

    # Launch background tasks
    asyncio.create_task(run_consumer(), name="signal-consumer")
    asyncio.create_task(throughput_reporter(), name="throughput-reporter")
    log.info("IMS backend ready ✓")


@app.on_event("shutdown")
async def shutdown():
    log.info("Shutting down IMS backend...")
    await close_db()


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    log.error("Unhandled error on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
