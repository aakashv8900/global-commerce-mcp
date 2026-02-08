"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/commerce_signal"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Scraper
    proxy_url: str | None = None
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    scrape_delay_min: int = 2
    scrape_delay_max: int = 5
    
    # Proxy Services (optional)
    scraper_api_key: str | None = None
    bright_data_user: str | None = None
    bright_data_pass: str | None = None

    # MCP
    mcp_server_name: str = "commerce-signal"
    mcp_server_version: str = "0.1.0"

    # Environment
    environment: str = "development"
    debug: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
