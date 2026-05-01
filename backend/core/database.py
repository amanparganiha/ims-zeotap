"""
Database connection lifecycle management.
All connections are created once at startup and reused.
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis, ConnectionPool

from core.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


# ── PostgreSQL ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


pg_engine = create_async_engine(
    settings.postgres_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(pg_engine, expire_on_commit=False)


async def get_pg_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# ── MongoDB ───────────────────────────────────────────────────────────────────
_mongo_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(settings.mongo_url, maxPoolSize=50)
    return _mongo_client


def get_mongo_db():
    return get_mongo_client()["ims"]


# ── Redis ─────────────────────────────────────────────────────────────────────
_redis_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url, max_connections=50, decode_responses=True
        )
    return _redis_pool


def get_redis() -> Redis:
    return Redis(connection_pool=get_redis_pool())


# ── Lifecycle helpers ─────────────────────────────────────────────────────────
async def init_db():
    """Create all Postgres tables (SQLAlchemy models)."""
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("PostgreSQL tables ready")


async def close_db():
    await pg_engine.dispose()
    if _mongo_client:
        _mongo_client.close()
    if _redis_pool:
        await _redis_pool.aclose()
    log.info("All DB connections closed")
