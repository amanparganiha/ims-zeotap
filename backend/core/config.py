from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    postgres_url: str = "postgresql+asyncpg://ims_user:ims_pass@localhost:5432/ims"
    mongo_url: str = "mongodb://ims_user:ims_pass@localhost:27017/ims?authSource=admin"
    redis_url: str = "redis://localhost:6379"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    log_level: str = "INFO"

    debounce_window_seconds: int = 10
    debounce_threshold: int = 100
    redis_stream_key: str = "ims:signals"
    redis_stream_group: str = "ims:processors"
    max_stream_len: int = 100_000
    rate_limit_per_minute: int = 6000

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
