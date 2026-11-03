"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Service-Aware Energy Agents API"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "production"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@db:5432/saea",
        description="Async PostgreSQL connection URL",
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30

    # Redis
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL",
    )
    redis_max_connections: int = 50

    # Security
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for signing tokens",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins",
    )

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    # Database
    database_echo: bool = False

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # Celery (for background tasks)
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/1"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
